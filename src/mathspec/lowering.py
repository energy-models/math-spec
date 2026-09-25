# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Lower a model to a :class:`~mathspec.program.Program` — the pass that decides every expression.

One lowering, on the language side, run when a :class:`~mathspec.model.Spec`
loads: it reads every expression and where string into the program's own
nodes, checks every rule decidable without data, and packages the
declarations, section for section. The program mirrors the model it was
lowered from: a ``piecewise:`` block the model still declares is a curve on
the program, and :meth:`~mathspec.model.Spec.expand` is what writes it out
as rows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mathspec.dimensions import check_schema, dims_of
from mathspec.errors import SchemaError, prefixed
from mathspec.expansion import expand, parse_template
from mathspec.piecewise import assumptions_of, curve_frame, lp_domain_refusal, resolve_links
from mathspec.program import (
    Assumption,
    BooleanLiteral,
    Cases,
    Constant,
    ConstraintDeclaration,
    DimensionDeclaration,
    ExpressionDeclaration,
    GivenDeclaration,
    GivenTargets,
    Link,
    Mask,
    Named,
    ObjectiveDeclaration,
    Parameter,
    ParameterDeclaration,
    PiecewiseDeclaration,
    Program,
    SosDeclaration,
    VariableDeclaration,
    VariableDefined,
    walk,
)
from mathspec.resolution import (
    Namespace,
    mask_of,
    resolve_constraint_text,
    resolve_expression,
    resolve_expression_text,
    resolve_where_text,
)
from mathspec.validation import emitted_name_errors, reference_errors

if TYPE_CHECKING:
    from mathspec.model import AssumptionBlock, Spec
    from mathspec.program import Expression


def lower(schema: Spec) -> Program:
    """Lower *schema*'s own declarations, checking every rule decidable without data.

    What is checked:

    - every rule one declaration is held to against the others
      (:func:`~mathspec.validation.reference_errors`), before any expression
      is read, since resolution assumes each of them;
    - the expression parses, and constraints hold exactly one comparison where
      objectives hold none;
    - every referenced name resolves, and every operator is a built-in whose
      dimension arguments name declared dimensions;
    - where strings parse *and* resolve — an unknown name there is an error,
      not a silently-empty mask;
    - macro formals may shadow model names but not a declared dimension, since
      ``over=snapshot`` under a formal ``snapshot`` cannot say which it means;
    - no name a set or curve writes out is one the file declares
      (:func:`~mathspec.validation.emitted_name_errors`), read off the
      curve as lowered;
    - every dim rule (``dimensions.check_schema``), once names resolve.

    A ``piecewise:`` block's links are resolved and its frame checked here, on
    the link the file wrote, so the expansion writes rows the language has
    already held to every rule; what its method assumes of the breakpoints
    stands under the program's assumptions with the file's own, so a model
    states what it assumes whether or not its curves are written out.

    Returns:
        The program of what *schema* declares, section for section.

    Raises:
        SchemaError: Listing every problem found, one per line. A name a set
            or curve writes that the file declares is listed once every other
            problem is gone, since it is read off the curve as lowered.
        DimensionError: The first dim rule a declaration breaks, once every
            name resolves.
    """
    errors = reference_errors(schema)
    if errors:
        raise SchemaError('\n'.join(errors))

    ns = Namespace(schema)
    for mname, macro in schema.macros.items():
        context = f"Macro '{mname}'"
        formals = frozenset((*macro.args, *macro.kwargs))
        try:
            body_ast = expand(parse_template(mname, macro, context), ns, context)
        except ValueError as e:
            errors.append(prefixed(context, e))
            continue
        errors.extend(
            f"{context}: formal '{f}' collides with declared dimension '{f}'. "
            f'Rename the formal — a dimension name inside a template is '
            f'ambiguous with the dimension itself.'
            for f in sorted(formals & ns.dimensions)
        )
        resolve_expression(body_ast, ns, context, errors, formals=formals)

    entries: dict[str, Named] = {}
    for ename in schema.expressions:
        node, refusals = ns.named_entry(ename)
        errors.extend(refusals)
        if node is not None:
            entries[ename] = node

    variables = {}
    for vname, vdef in schema.variables.items():
        where = resolve_where_text(vdef.where, ns, f"Variable '{vname}'", errors, self_variable=vname)
        if vdef.domain == 'binary':
            lower_bound, upper_bound = Constant(0.0), Constant(1.0)
        else:
            lower_bound, upper_bound = _bound(vdef.bounds.lower), _bound(vdef.bounds.upper)
        variables[vname] = VariableDeclaration(
            tuple(vdef.dims),
            where=mask_of(where),
            lower=lower_bound,
            upper=upper_bound,
            domain=vdef.domain,
            absence=vdef.absence,
            description=vdef.description,
        )

    constraints: dict[str, ConstraintDeclaration] = {}
    for cname, cdef in schema.constraints.items():
        context = f"Constraint '{cname}'"
        where = resolve_where_text(cdef.where, ns, context, errors)
        if (sides := resolve_constraint_text(cdef.expression, ns, context, errors)) is not None:
            lhs, sense, rhs = sides
            constraints[cname] = ConstraintDeclaration(
                tuple(cdef.dims), lhs, sense, rhs, mask_of(where), description=cdef.description
            )

    objective = None
    if schema.objective is not None:
        expression = resolve_expression_text(schema.objective.expression, ns, 'The objective', errors, ceiling=2)
        if expression is not None:
            objective = ObjectiveDeclaration(schema.objective.sense, expression, schema.objective.description)

    assumptions: dict[str, Assumption] = {}
    for aname, adef in schema.assumptions.items():
        if (assumption := _assumption(aname, adef, ns, errors)) is not None:
            assumptions[aname] = assumption

    curves: dict[str, tuple[Expression, ...]] = {}
    for pname, pdef in schema.piecewise.items():
        links = resolve_links(pname, pdef, ns, errors)
        if links is None:
            continue
        if pdef.method == 'lp' and (refusal := lp_domain_refusal(pname, pdef, links)) is not None:
            errors.append(refusal)
        curves[pname] = links

    if errors:
        raise SchemaError('\n'.join(errors))

    roots = [side for c in constraints.values() for side in (c.lhs, c.rhs)]
    if objective is not None:
        roots.append(objective.expression)
    roots.extend(link for links in curves.values() for link in links)
    in_math = frozenset(node.name for node in walk(*roots) if isinstance(node, Named))

    piecewise = {}
    for pname, links in curves.items():
        pdef = schema.piecewise[pname]
        piecewise[pname] = PiecewiseDeclaration(
            over=pdef.over,
            links=tuple(Link(node, link.values, link.sign) for node, link in zip(links, pdef.links, strict=True)),
            method=pdef.method,
            frame=curve_frame(schema, pname, pdef, links),
            activity=pdef.activity,
            points=pdef.points,
            description=pdef.description,
        )
        for aname, assumed in assumptions_of(pname, piecewise[pname]).items():
            assumption = _assumption(aname, assumed, ns, errors)
            assert assumption is not None and not errors, 'what a method assumes is stated in the language'
            assumptions[aname] = assumption

    program = Program(
        parameters={
            name: ParameterDeclaration(tuple(pdef.dims), pdef.dtype, pdef.description)
            for name, pdef in schema.parameters.items()
        },
        variables=variables,
        constraints=constraints,
        objective=objective,
        dimensions={
            name: DimensionDeclaration(ddef.dtype, ddef.description) for name, ddef in schema.dimensions.items()
        },
        relations=ns.relations,
        sos={
            name: SosDeclaration(sdef.variable, sdef.along, sos_type=sdef.type, description=sdef.description)
            for name, sdef in schema.sos.items()
        },
        piecewise=piecewise,
        assumptions=assumptions,
        expressions={
            name: ExpressionDeclaration(
                entry.body,
                _frame_of(name, entry, schema),
                in_math=name in in_math,
                description=schema.expressions[name].description,
            )
            for name, entry in entries.items()
        },
        given=GivenTargets(
            parameters={
                name: ParameterDeclaration(tuple(g.dims), g.dtype, g.description)
                for name, g in schema.given.parameters.items()
            },
            variables={
                name: GivenDeclaration(tuple(g.dims), g.description) for name, g in schema.given.variables.items()
            },
            constraints={
                name: GivenDeclaration(tuple(g.dims), g.description) for name, g in schema.given.constraints.items()
            },
            expressions={
                name: GivenDeclaration(tuple(g.dims), g.description) for name, g in schema.given.expressions.items()
            },
        ),
        description=schema.description,
    )
    if errors := emitted_name_errors(schema, program):
        raise SchemaError('\n'.join(errors))
    check_schema(schema, program)
    return program


def _frame_of(name: str, entry: Named, schema: Spec) -> tuple[str, ...]:
    """The dims an entry is read over, in declaration order: declared for a cased entry, the body's for a plain one."""
    if isinstance(entry.body, Cases):
        return tuple(schema.expressions[name].dims or ())
    carried = dims_of(entry.body, schema, f"Named expression '{name}'")
    return tuple(d for d in schema.dimensions if d in carried)


def _bound(value: float | str | None) -> Constant | Parameter | None:
    if value is None:
        return None
    if isinstance(value, str):
        return Parameter(value)
    return Constant(value)


def _assumption(name: str, block: AssumptionBlock, ns: Namespace, errors: list[str]) -> Assumption | None:
    """One ``assumptions:`` entry typed, or ``None`` once anything in it failed.

    A predicate the connectives decide is refused: one that folds to true
    assumes nothing, and one that folds to false refuses every dataset. A
    variable is refused too, since an assumption is about the data and a
    variable is what the solver decides from it.
    """
    context = f"Assumption '{name}'"
    found = len(errors)
    holds = resolve_where_text(block.holds, ns, context, errors)
    where = resolve_where_text(block.where, ns, f'{context}, where', errors)
    if isinstance(holds, BooleanLiteral):
        errors.append(_decided_assumption(context, block.holds, value=holds.value))
    if isinstance(where, BooleanLiteral):
        assert block.where is not None, 'a where the file did not write resolves to nothing'
        errors.append(_decided_where(context, block.where, value=where.value))
    for mask, part in ((holds, 'assumes'), (where, 'is checked where')):
        if mask is None or isinstance(mask, BooleanLiteral):
            continue
        errors.extend(
            f"{context}: variable '{atom.name}' stands in what the assumption {part}, and an assumption is "
            f'about the data — a variable is what the solver decides from it. Name a parameter, or state the '
            f'rule as a constraint.'
            for atom in Mask(mask).atoms
            if isinstance(atom, VariableDefined)
        )
    if len(errors) > found:
        return None
    assert holds is not None, 'a where string that read to nothing appended an error'
    return Assumption(Mask(holds), mask_of(where), block.description)


def _decided_assumption(context: str, text: str, *, value: bool) -> str:
    """The refusal for a predicate the connectives already decided, whose data is never read."""
    if value:
        return (
            f'{context}: the predicate {text!r} folds to true, so it assumes nothing of the data. '
            f'Delete it, or name a parameter it constrains.'
        )
    return (
        f'{context}: the predicate {text!r} folds to false, so it holds on no data at all. '
        f'Delete it, or write the predicate the data can satisfy.'
    )


def _decided_where(context: str, text: str, *, value: bool) -> str:
    """The refusal for a ``where`` the connectives already decided, which narrows nothing or everything."""
    if value:
        return f'{context}: the where {text!r} folds to true, so it narrows nothing. Delete the where.'
    return (
        f'{context}: the where {text!r} folds to false, so the assumption is checked on no row. '
        f'Delete the entry, or write the where the data can satisfy.'
    )
