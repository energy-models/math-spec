# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Load-time validation: the front door, and the pass that decides every expression."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from math_spec._yaml import read_model
from math_spec.dimensions import check_schema
from math_spec.errors import SchemaError, prefixed
from math_spec.expansion import expand, parse_template
from math_spec.model import AssumptionBlock, Spec
from math_spec.piecewise import assumptions_of
from math_spec.program import BooleanLiteral, Mask, VariableDefined
from math_spec.resolution import (
    Namespace,
    Resolved,
    ResolvedAssumption,
    ResolvedConstraint,
    mask_of,
    resolve_expression,
    resolve_expression_text,
    resolve_where_text,
)

if TYPE_CHECKING:
    from pathlib import Path

    from math_spec._expression_parser import CasesNode, DefinitionNode


def to_spec(model: str | Path | Mapping[str, object] | Spec) -> Spec:
    """Load and validate a model definition — the language's front door.

    Everything decidable without data is decided here: schema shape, every
    expression and where string, every macro template, and every declaration a
    formulation emits.

    Args:
        model: A YAML path — a :class:`~pathlib.Path`, or a ``str`` with no
            newline in it — the YAML text itself as a ``str`` with one, a
            mapping, or a loaded :class:`Spec`.

    Returns:
        The schema *as the file declares it*, ``piecewise:`` intact.

    Raises:
        LanguageError: Anything the language does not accept, a text that is
            not a mapping of sections included.
        FileNotFoundError: A ``str`` with no newline that names no file.
    """
    if isinstance(model, (list, tuple)):
        msg = 'a model is one file, one dict or one Spec, never a list of them; merge the declarations into one dict.'
        raise SchemaError(msg)
    if isinstance(model, Spec):
        return model
    return Spec.model_validate(model if isinstance(model, Mapping) else read_model(model))


def validate_expressions(schema: Spec) -> Resolved:
    """Validate and resolve every expression and where string in *schema*, once for every reader.

    What is checked:

    - the expression parses, and constraints hold exactly one comparison where
      objectives hold none;
    - every referenced name resolves, and every operator is a built-in whose
      dimension arguments name declared dimensions;
    - where strings parse *and* resolve — an unknown name there is an error,
      not a silently-empty mask;
    - macro formals may shadow model names but not a declared dimension, since
      ``over=snapshot`` under a formal ``snapshot`` cannot say which it means;
    - every dim rule (``dimensions.check_schema``), once names resolve.

    A ``piecewise:`` block's links are resolved here too, so the typesetter
    reads the curve a file states without expanding it.

    Returns:
        Every declaration's typed tree — what the dim rules, lowering and the
        typesetter read instead of resolving the text again.

    Raises:
        SchemaError: Listing every problem found, one per line.
        DimensionError: The first dim rule a declaration breaks, once every
            name resolves.
    """
    ns = Namespace(schema)
    errors: list[str] = []

    for mname, macro in schema.macros.items():
        context = f"Macro '{mname}'"
        formals = frozenset((*macro.args, *macro.kwargs))
        try:
            body_ast = expand(parse_template(mname, macro, context), ns, context, shadow=formals)
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

    expressions: dict[str, CasesNode | DefinitionNode] = {}
    for ename in schema.expressions:
        node, refusals = ns.named_entry(ename)
        errors.extend(refusals)
        if node is not None:
            expressions[ename] = node
    if errors:
        raise SchemaError('\n'.join(errors))

    variables = {
        vname: mask_of(resolve_where_text(vdef.where, ns, f"Variable '{vname}'", errors, self_variable=vname))
        for vname, vdef in schema.variables.items()
    }

    constraints: dict[str, ResolvedConstraint] = {}
    for cname, cdef in schema.constraints.items():
        context = f"Constraint '{cname}'"
        where = resolve_where_text(cdef.where, ns, context, errors)
        expression = resolve_expression_text(cdef.expression, ns, context, errors, comparison=True, ceiling=2)
        if expression is not None:
            constraints[cname] = ResolvedConstraint(expression, mask_of(where))

    objective = None
    if schema.objective is not None:
        objective = resolve_expression_text(
            schema.objective.expression, ns, 'The objective', errors, comparison=False, ceiling=2
        )

    assumptions: dict[str, ResolvedAssumption] = {}
    for aname, adef in schema.assumptions.items():
        if (assumption := _assumption(aname, adef, ns, errors)) is not None:
            assumptions[aname] = assumption

    for block, pw in schema.piecewise.items():
        for aname, assumed in assumptions_of(block, pw).items():
            entry = AssumptionBlock(holds=assumed.holds, where=assumed.where, description=assumed.description)
            if (assumption := _assumption(aname, entry, ns, errors)) is not None:
                assumptions[aname] = assumption

    piecewise = {}
    for pname, pdef in schema.piecewise.items():
        links = [
            resolve_expression_text(
                link.expression, ns, f"piecewise '{pname}' link {i}", errors, comparison=False, ceiling=1
            )
            for i, link in enumerate(pdef.links)
        ]
        if all(link is not None for link in links):
            piecewise[pname] = tuple(link for link in links if link is not None)

    if errors:
        raise SchemaError('\n'.join(errors))

    resolved = Resolved(expressions, variables, constraints, objective, ns.relations, assumptions, piecewise)
    check_schema(schema, resolved)
    return resolved


def _assumption(name: str, block: AssumptionBlock, ns: Namespace, errors: list[str]) -> ResolvedAssumption | None:
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
    return ResolvedAssumption(Mask(holds), mask_of(where), block.description)


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
