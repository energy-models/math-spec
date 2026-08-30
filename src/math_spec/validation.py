# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Load-time validation: every expression and where string is parsed, expanded and resolved through the same pass the backends use, collecting every problem rather than raising on the first."""

from __future__ import annotations

from pathlib import Path
from typing import Any, assert_never

from math_spec._yaml import read_yaml
from math_spec.degree import carries_variable, check_expression
from math_spec.dimensions import check_schema
from math_spec.errors import LanguageError, SchemaError
from math_spec.expansion import expand, parse_and_expand, parse_template
from math_spec.expression_parser import (
    ArithmeticNode,
    BinaryOperatorNode,
    ComparisonNode,
    FunctionCallNode,
    KeywordNode,
    KwargNode,
    NameListNode,
    NameNode,
    NumberNode,
    ParameterNode,
    UnaryOperatorNode,
    VariableNode,
)
from math_spec.model import CheckBlock, Spec
from math_spec.operators import BUILTINS, unknown_operator_message
from math_spec.resolution import Namespace, resolve_expression, resolve_where, where_of
from math_spec.where_parser import (
    AndNode,
    BooleanLiteralNode,
    NotNode,
    OrNode,
    VariableDefinedNode,
    WhereNode,
    parse_where,
)


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
        msg = 'a model is one file, one dict or one Spec, never a list of them; merge the declarations into one dict (#30).'
        raise TypeError(msg)
    if isinstance(model, Spec):
        return model
    return Spec.model_validate(model if isinstance(model, dict) else read_yaml(Path(model)))


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
        _check_template_names(body_ast, macro.template, context, ns, formals, errors)

    for ename, block in schema.expressions.items():
        _check_expression(
            block.expression, schema, ns, f"Named expression '{ename}'", errors, comparison=False, ceiling=1
        )

    for vname, vdef in schema.variables.items():
        _check_where(vdef.where, ns, f"Variable '{vname}'", errors, self_variable=vname)

    for cname, cdef in schema.constraints.items():
        context = f"Constraint '{cname}'"
        _check_where(cdef.where, ns, context, errors)
        _check_expression(cdef.expression, schema, ns, context, errors, comparison=True, ceiling=2)

    if schema.objective is not None:
        _check_expression(schema.objective.expression, schema, ns, 'The objective', errors, comparison=False, ceiling=2)

    for kname, kdef in schema.checks.items():
        _check_check(kname, kdef, ns, errors)

    if errors:
        raise SchemaError('\n'.join(errors))

    check_schema(schema)


def _prefixed(context: str, e: ValueError) -> str:
    """*e* under *context*, once — expansion errors already carry it."""
    return str(e) if str(e).startswith(context) else f'{context}: {e}'


def _check_expression(
    expression: str,
    schema: Spec,
    ns: Namespace,
    context: str,
    errors: list[str],
    *,
    comparison: bool,
    ceiling: int,
) -> None:
    """Parse, expand, resolve and degree-check one expression — nothing resolves once the shape is wrong, and a comparison must carry a variable (#1171)."""
    try:
        ast = parse_and_expand(expression, schema, context)
    except ValueError as e:
        errors.append(_prefixed(context, e))
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
    if isinstance(resolved, ComparisonNode) and not carries_variable(resolved):
        errors.append(
            f'{context}: neither side of the comparison carries a variable, so the row decides nothing.\n'
            f'Got: {expression!r}\n'
            f'A constraint is a claim about a decision, and a comparison of numbers and parameters '
            f'is settled before the solve — no lane builds a row for it. Name the variable it should '
            f'bound, or drop the declaration and check the fact where the data is prepared.'
        )
    try:
        check_expression(resolved, context, ceiling=ceiling)
    except LanguageError as e:
        errors.append(str(e))


def _check_check(name: str, block: CheckBlock, ns: Namespace, errors: list[str]) -> None:
    """A check is a predicate over data alone, and one that data cannot decide is a mistake the file can see.

    Folding is what makes the second half reachable: ``where_of`` reduces a
    predicate the connectives settle to a literal, so a check no table can
    fail arrives as ``None`` and one no table can pass as ``False``.
    """
    context = f"Check '{name}'"
    try:
        folded = where_of(block.holds, ns, context)
    except ValueError as e:
        errors.append(_prefixed(context, e))
        return
    if variables := sorted(_variables_in(folded)):
        errors.append(
            f'{context}: reads variable(s) {variables}, and a check is a condition on the data, '
            f'settled before any variable has a value. Test the parameters the variable is '
            f'built from, or make it a constraint.'
        )
        return
    if folded is None:
        errors.append(
            f'{context}: holds at every coordinate whatever the data says, so it checks nothing. '
            f'Write the condition the data could break, or drop the check.'
        )
    elif isinstance(folded, BooleanLiteralNode):
        errors.append(
            f'{context}: no data satisfies it, so every table is refused. Write the condition '
            f'the data could meet, or drop the check.'
        )


def _variables_in(node: WhereNode | None) -> set[str]:
    """Every variable a predicate reads — empty for one that reads only data."""
    if isinstance(node, VariableDefinedNode):
        return {node.name}
    if isinstance(node, NotNode):
        return _variables_in(node.operand)
    if isinstance(node, (AndNode, OrNode)):
        return _variables_in(node.left) | _variables_in(node.right)
    return set()


def _check_where(
    text: str | None,
    ns: Namespace,
    context: str,
    errors: list[str],
    self_variable: str | None = None,
) -> None:
    if text is None:
        return
    try:
        node = parse_where(text)
    except ValueError as e:
        errors.append(f'{context}: {e}')
        return
    resolve_where(node, ns, context, errors, self_variable)


def _names_in(value: ArithmeticNode) -> tuple[str, ...]:
    """The names a lookup kwarg carries: one bare, several bracketed, none otherwise."""
    if isinstance(value, NameNode):
        return (value.name,)
    return value.names if isinstance(value, NameListNode) else ()


def _check_template_names(
    node: ArithmeticNode,
    template: str,
    context: str,
    ns: Namespace,
    formals: frozenset[str],
    errors: list[str],
) -> None:
    """Name-check a macro body treating formals as bound — not resolution, since a formal has no kind until a call site binds it."""
    if isinstance(node, NumberNode | VariableNode | ParameterNode | KwargNode | KeywordNode | NameListNode):
        return

    if isinstance(node, NameNode):
        if node.name not in formals and ns.kind(node.name) is None:
            errors.append(
                f"{context}: '{node.name}' not found in template {template!r}.\n"
                f'  Formals:    {sorted(formals)}\n'
                f'  Variables:  {sorted(ns.variables)}\n'
                f'  Parameters: {sorted(ns.parameters)}\n'
                f"Check for typos, or ensure '{node.name}' is declared."
            )
        return

    if isinstance(node, UnaryOperatorNode):
        _check_template_names(node.operand, template, context, ns, formals, errors)
        return

    if isinstance(node, BinaryOperatorNode):
        _check_template_names(node.left, template, context, ns, formals, errors)
        _check_template_names(node.right, template, context, ns, formals, errors)
        return

    if isinstance(node, FunctionCallNode):
        builtin = BUILTINS.get(node.name)
        if builtin is None:
            errors.append(f'{context}: {unknown_operator_message(node.name)}')
        for arg in node.args:
            _check_template_names(arg, template, context, ns, formals, errors)
        dimension_kwargs, lookup_kwargs, edge_kwargs = (
            (builtin.dimension_kwargs, builtin.lookup_kwargs, builtin.edge_kwargs) if builtin else ((), (), ())
        )
        for kwarg, value in node.kwargs.items():
            if kwarg in dimension_kwargs:
                if isinstance(value, NameNode) and value.name not in ns.dimensions | formals:
                    errors.append(
                        f'{context}: {node.name}({kwarg}={value.name}) does not name a '
                        f'declared dimension or a formal of this macro.'
                    )
            elif kwarg in lookup_kwargs:
                errors.extend(
                    f'{context}: {node.name}({kwarg}={one}) does not name a lookup or a formal of this macro.'
                    for one in _names_in(value)
                    if one not in formals and ns.kind(one) != 'lookup'
                )
            elif kwarg not in edge_kwargs:
                _check_template_names(value, template, context, ns, formals, errors)
        return

    assert_never(node)
