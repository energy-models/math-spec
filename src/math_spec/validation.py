# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Load-time validation: the front door, and the pass that decides every expression."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, assert_never

import math_spec.degree as degree
from math_spec._expression_parser import (
    ArithmeticNode,
    BinaryOperatorNode,
    CasesNode,
    ComparisonNode,
    ConstraintNode,
    FunctionCallNode,
    KeywordNode,
    KwargNode,
    NameListNode,
    NameNode,
    NumberNode,
    ParameterNode,
    UnaryOperatorNode,
    VariableNode,
    case_context,
)
from math_spec._yaml import read_yaml
from math_spec.dimensions import check_schema
from math_spec.errors import LanguageError, SchemaError
from math_spec.exclusivity import overlapping
from math_spec.expansion import expand, parse_and_expand, parse_template
from math_spec.model import Spec
from math_spec.operators import BUILTINS, unknown_operator_message
from math_spec.program import BooleanLiteralNode
from math_spec.resolution import Namespace, resolve_expression, resolve_where_text

if TYPE_CHECKING:
    from math_spec.program import WhereNode


def to_spec(model: str | Path | dict[str, Any] | Spec) -> Spec:
    """Load and validate a model definition — the language's front door.

    Everything decidable without data is decided here: schema shape, every
    expression and where string, every macro template, and every declaration a
    formulation emits.

    Args:
        model: A YAML path, a mapping, or a loaded :class:`Spec`.

    Returns:
        The schema *as the file declares it*, ``piecewise:`` intact.

    Raises:
        LanguageError: Anything the language does not accept.
    """
    if isinstance(model, (list, tuple)):
        msg = 'a model is one file, one dict or one Spec, never a list of them; merge the declarations into one dict.'
        raise SchemaError(msg)
    if isinstance(model, Spec):
        return model
    return Spec.model_validate(model if isinstance(model, dict) else read_yaml(Path(model)))


def _once(errors: list[str]) -> str:
    """The errors as one message, an identical sentence kept only the first time.

    A cased expression is expanded at every use, so a fault in one of its arms
    is found again at each constraint naming it. Every error carries the
    context it was found in, so two that differ at all are two faults and an
    exact repeat is one seen twice.
    """
    return '\n'.join(dict.fromkeys(errors))


def validate_expressions(schema: Spec) -> None:
    """Validate and resolve every expression and where string in *schema*.

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

    Raises:
        SchemaError: Listing every problem found, one per line.
    """
    ns = Namespace.of(schema)
    errors: list[str] = []

    for mname, macro in schema.macros.items():
        context = f"Macro '{mname}'"
        formals = frozenset((*macro.args, *macro.kwargs))
        try:
            body_ast = expand(parse_template(mname, macro, context), schema, context, shadow=formals)
        except ValueError as e:
            errors.append(_prefixed(context, e))
            continue
        errors.extend(
            f"{context}: formal '{f}' collides with declared dimension '{f}'. "
            f'Rename the formal — a dimension name inside a template is '
            f'ambiguous with the dimension itself.'
            for f in sorted(formals & ns.dimensions)
        )
        _check_template_names(body_ast, context, ns, formals, errors)

    for ename, block in schema.expressions.items():
        context = f"Named expression '{ename}'"
        if not block.cases:
            assert block.expression is not None
            _check_expression(block.expression, schema, ns, context, errors, comparison=False, check_degree=False)
            continue
        found = len(errors)
        masks: dict[str, WhereNode] = {}
        for case_name, case in block.cases.items():
            arm_context = case_context(ename, case_name)
            if (mask := resolve_where_text(case.when, ns, arm_context, errors)) is not None:
                if isinstance(mask, BooleanLiteralNode):
                    errors.append(_constant_arm(arm_context, value=mask.value))
                else:
                    masks[case_name] = mask
            _check_expression(case.expression, schema, ns, arm_context, errors, comparison=False, check_degree=False)
        assert block.otherwise is not None
        _check_expression(
            block.otherwise, schema, ns, case_context(ename, None), errors, comparison=False, check_degree=False
        )
        if len(errors) == found:
            errors.extend(f'{context}: {problem}' for problem in overlapping(masks, ns.dtypes))

    for vname, vdef in schema.variables.items():
        resolve_where_text(vdef.where, ns, f"Variable '{vname}'", errors, self_variable=vname)

    for cname, cdef in schema.constraints.items():
        context = f"Constraint '{cname}'"
        resolve_where_text(cdef.where, ns, context, errors)
        _check_expression(cdef.expression, schema, ns, context, errors, comparison=True, ceiling=2)

    if schema.objective is not None:
        _check_expression(schema.objective.expression, schema, ns, 'The objective', errors, comparison=False, ceiling=2)

    if errors:
        raise SchemaError(_once(errors))

    check_schema(schema)


def _prefixed(context: str, e: ValueError) -> str:
    """*e* under *context*, once — expansion errors already carry it."""
    return str(e) if str(e).startswith(context) else f'{context}: {e}'


def _constant_arm(context: str, *, value: bool) -> str:
    """The refusal for a case arm whose mask the connectives already decided.

    Cases are proved apart rather than ranked, so an always-true arm is not
    one that shadows the arms under it — it is one no other arm can be proved
    apart from, and the ``otherwise`` it leaves is empty. An always-false arm
    is the plainer half: nothing to apply to.
    """
    if value:
        return (
            f'{context}: the mask admits every row, so no other arm can hold anywhere '
            f'and `otherwise:` covers nothing. Write the expression without `cases:`, '
            f'or narrow the `when`.'
        )
    return f'{context}: the mask admits no row, so this arm never applies. Delete the arm, or widen the `when`.'


def _check_expression(
    expression: str,
    schema: Spec,
    ns: Namespace,
    context: str,
    errors: list[str],
    *,
    comparison: bool,
    ceiling: int = 1,
    check_degree: bool = True,
) -> None:
    """Parse, expand, resolve and degree-check one expression — nothing resolves once the shape is wrong, and a comparison must carry a variable (#1171).

    ``check_degree`` is off for an ``expressions:`` entry's body: degree and
    the ``dual()`` placement rule are rules about the position that *reads*
    the math, so they fire on the expanded tree of every constraint,
    objective, bound, where and piecewise link, and an entry's declaration
    only decides its grade (:func:`math_spec.degree.is_postsolve_grade`).
    """
    try:
        ast = parse_and_expand(expression, schema, context)
    except ValueError as e:
        errors.append(_prefixed(context, e))
        return
    if check_degree and degree.calls_dual(ast):
        errors.append(degree.dual_in_math_message(context))
        return
    if comparison and not isinstance(ast, ComparisonNode):
        errors.append(
            f'{context}: expression must contain exactly one comparison operator (<=, >=, ==).\nGot: {expression!r}'
        )
        return
    if not comparison and isinstance(ast, ComparisonNode):
        errors.append(f'{context}: expression must not contain a comparison operator.\nGot: {expression!r}')
        return
    resolved = resolve_expression(ast, ns, context, errors)
    if resolved is None:
        return
    if isinstance(resolved, ComparisonNode) and not degree.carries_variable(resolved):
        errors.append(
            f'{context}: neither side of the comparison carries a variable, so the row decides nothing.\n'
            f'Got: {expression!r}\n'
            f'A constraint is a claim about a decision, and a comparison of numbers and parameters '
            f'is settled before the solve — no lane builds a row for it. Name the variable it should '
            f'bound, or drop the declaration and check the fact where the data is prepared.'
        )
    if not check_degree:
        return
    try:
        degree.check_expression(resolved, context, ceiling=ceiling)
    except LanguageError as e:
        errors.append(str(e))


def _names_in(value: ArithmeticNode) -> tuple[str, ...]:
    """The names a lookup kwarg carries: one bare, several bracketed, none otherwise."""
    if isinstance(value, NameNode):
        return (value.name,)
    return value.names if isinstance(value, NameListNode) else ()


def _check_template_names(
    node: ArithmeticNode,
    context: str,
    ns: Namespace,
    formals: frozenset[str],
    errors: list[str],
) -> None:
    """Name-check a macro body treating formals as bound — not resolution, since a formal has no kind until a call site binds it.

    A case arm's value only: its ``when`` is the declaration's, checked there.
    """
    if isinstance(node, NumberNode | VariableNode | ParameterNode | KwargNode | KeywordNode | NameListNode):
        return

    if isinstance(node, NameNode):
        if node.name not in formals and ns.kind(node.name) is None:
            errors.append(ns.unknown(node.name, context, allow_dims=False, formals=formals))
        return

    if isinstance(node, UnaryOperatorNode):
        _check_template_names(node.operand, context, ns, formals, errors)
        return

    if isinstance(node, BinaryOperatorNode):
        _check_template_names(node.left, context, ns, formals, errors)
        _check_template_names(node.right, context, ns, formals, errors)
        return

    if isinstance(node, FunctionCallNode):
        builtin = BUILTINS.get(node.name)
        if builtin is None:
            errors.append(f'{context}: {unknown_operator_message(node.name)}')
        if node.name == 'dual':
            errors.extend(
                f"{context}: dual({arg.name}): '{arg.name}' is not a "
                f'declared constraint or a formal of this macro.\n  Constraints: {sorted(ns.constraints)}'
                for arg in node.args
                if isinstance(arg, NameNode) and arg.name not in formals and arg.name not in ns.constraints
            )
            return
        for arg in node.args:
            _check_template_names(arg, context, ns, formals, errors)
        for kwarg, value in node.kwargs.items():
            match builtin.kind_of(kwarg) if builtin else 'value':
                case 'dimension':
                    if isinstance(value, NameNode) and value.name not in ns.dimensions | formals:
                        errors.append(
                            f'{context}: {node.name}({kwarg}={value.name}) does not name a '
                            f'declared dimension or a formal of this macro.'
                        )
                case 'lookup':
                    errors.extend(
                        f'{context}: {node.name}({kwarg}={one}) does not name a lookup or a formal of this macro.'
                        for one in _names_in(value)
                        if one not in formals and ns.kind(one) != 'lookup'
                    )
                case 'value':
                    _check_template_names(value, context, ns, formals, errors)
                case 'edge':
                    pass  # a keyword or a number: nothing in it to name
        return

    if isinstance(node, CasesNode):
        for arm in node.arms:
            _check_template_names(arm.value, context, ns, formals, errors)
        return

    if isinstance(node, ConstraintNode):
        return

    assert_never(node)
