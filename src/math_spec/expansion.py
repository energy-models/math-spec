# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Named sub-expressions and macros, expanded into the core AST before anything reads the expression."""

from __future__ import annotations

from typing import TYPE_CHECKING, overload

from math_spec._where_parser import parse_where
from math_spec.errors import SchemaError
from math_spec.expression_parser import (
    ArithmeticNode,
    CaseArm,
    CasesNode,
    ComparisonNode,
    ExpressionNode,
    FunctionCallNode,
    NameNode,
    parse_expression,
    with_children,
)

if TYPE_CHECKING:
    from math_spec.model import ExpressionBlock, MacroBlock, Spec


def parse_and_expand(text: str, schema: Spec, context: str) -> ExpressionNode:
    """Parse *text* and expand named sub-expressions and macros to core AST."""
    return expand(parse_expression(text), schema, context)


@overload
def expand(node: ArithmeticNode, schema: Spec, context: str, *, shadow: frozenset[str] = ...) -> ArithmeticNode: ...
@overload
def expand(node: ComparisonNode, schema: Spec, context: str, *, shadow: frozenset[str] = ...) -> ComparisonNode: ...


def expand(node: ExpressionNode, schema: Spec, context: str, *, shadow: frozenset[str] = frozenset()) -> ExpressionNode:
    """Expand all named sub-expressions and macro calls under *node*.

    A comparison stays a comparison and an arithmetic node stays arithmetic.

    Args:
        node: The parsed expression.
        schema: Where names and macros are declared.
        context: What an error names.
        shadow: Names left as written even where a named expression has that
            name — a template's formals, checked without a call to bind them.
    """
    if isinstance(node, ComparisonNode):
        return ComparisonNode(
            node.op,
            _expand(node.left, schema, context, (), shadow),
            _expand(node.right, schema, context, (), shadow),
        )
    return _expand(node, schema, context, (), shadow)


def macro_signature(name: str, macro: MacroBlock) -> str:
    """Human-readable call signature, for error messages."""
    parts = [*macro.args, *(f'{k}=...' for k in macro.kwargs)]
    return f'{name}({", ".join(parts)})'


def parse_template(name: str, macro: MacroBlock, context: str) -> ArithmeticNode:
    """Parse a macro template, rejecting comparisons."""
    return _parse_body(macro.template, f"macro '{name}' template", context)


def _expand(
    node: ArithmeticNode,
    schema: Spec,
    context: str,
    stack: tuple[str, ...],
    shadow: frozenset[str],
) -> ArithmeticNode:
    def _cycle(name: str, kind: str) -> None:
        if name in stack:
            chain = ' -> '.join([*stack, name])
            msg = f'{context}: circular {kind} reference: {chain}'
            raise SchemaError(msg)

    if isinstance(node, NameNode) and node.name in schema.expressions and node.name not in shadow:
        _cycle(node.name, 'expression')
        body = _parse_named(node.name, schema, context)
        return _expand(body, schema, context, (*stack, node.name), shadow)

    if isinstance(node, FunctionCallNode) and node.name in schema.macros:
        _cycle(node.name, 'macro')
        return _expand_macro(node, schema, context, stack, shadow)

    return with_children(node, lambda child: _expand(child, schema, context, stack, shadow))


def _parse_named(name: str, schema: Spec, context: str) -> ArithmeticNode:
    block = schema.expressions[name]
    if block.cases:
        return _parse_cased(name, block, context)
    assert block.expression is not None
    return _parse_body(block.expression, f"named expression '{name}'", context)


def _parse_cased(name: str, block: ExpressionBlock, context: str) -> CasesNode:
    """A cased expression as the node that stands where its name was: the arms in file order, ``otherwise:`` last."""
    arms = []
    for label, case in block.cases.items():
        value = _parse_body(case.expression, f"named expression '{name}', case '{label}'", context)
        # pyrefly: ignore[bad-argument-type]  # the field is typed as resolution leaves it
        arms.append(CaseArm(label, parse_where(case.when), value))
    assert block.otherwise is not None
    fallback = _parse_body(block.otherwise, f"named expression '{name}', otherwise", context)
    arms.append(CaseArm('otherwise', None, fallback))
    return CasesNode(name, tuple(arms))


def _parse_body(text: str, subject: str, context: str) -> ArithmeticNode:
    """Parse one expression string that stands for a value, not a relation."""
    body = parse_expression(text)
    if isinstance(body, ComparisonNode):
        msg = f'{context}: {subject} must not contain a comparison operator. Got: {text!r}'
        raise SchemaError(msg)
    return body


def _expand_macro(
    call: FunctionCallNode,
    schema: Spec,
    context: str,
    stack: tuple[str, ...],
    shadow: frozenset[str],
) -> ArithmeticNode:
    """Call-by-value: arguments are expanded before substitution, and the substituted body is expanded again."""
    macro = schema.macros[call.name]
    signature = macro_signature(call.name, macro)
    if len(call.args) != len(macro.args):
        msg = (
            f"{context}: macro '{call.name}' expects {len(macro.args)} "
            f'positional argument(s), got {len(call.args)}. Signature: {signature}'
        )
        raise SchemaError(msg)
    if set(call.kwargs) != set(macro.kwargs):
        msg = (
            f"{context}: macro '{call.name}' expects keyword argument(s) "
            f'{sorted(macro.kwargs)}, got {sorted(call.kwargs)}. '
            f'Signature: {signature}'
        )
        raise SchemaError(msg)

    bindings = {
        **{
            formal: _expand(arg, schema, context, stack, shadow)
            for formal, arg in zip(macro.args, call.args, strict=True)
        },
        **{formal: _expand(call.kwargs[formal], schema, context, stack, shadow) for formal in macro.kwargs},
    }
    body = parse_template(call.name, macro, context)
    substituted = _substitute(body, bindings)
    return _expand(substituted, schema, context, (*stack, call.name), shadow)


def _substitute(node: ArithmeticNode, bindings: dict[str, ArithmeticNode]) -> ArithmeticNode:
    """Replace formal-name NameNodes in *node* with their bound subtrees."""
    if isinstance(node, NameNode) and node.name in bindings:
        return bindings[node.name]
    return with_children(node, lambda child: _substitute(child, bindings))
