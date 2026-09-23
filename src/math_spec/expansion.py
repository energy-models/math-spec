# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Macro calls, expanded into the syntax tree before resolution reads it.

A named expression is resolution's: it resolves the entry once and puts that
node where the name stood.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, overload

from math_spec._expression_parser import (
    ArithmeticNode,
    ColumnsNode,
    ComparisonNode,
    FunctionCallNode,
    NameNode,
    ParsedNode,
    parse_expression,
    with_children,
)
from math_spec.errors import SchemaError

if TYPE_CHECKING:
    from math_spec.model import MacroBlock
    from math_spec.resolution import Namespace


def parse_and_expand(text: str, ns: Namespace, context: str) -> ParsedNode:
    """Parse *text* and expand every macro call in it.

    Args:
        text: The expression as the file wrote it.
        ns: Where the macros are declared.
        context: What an error names.
    """
    return expand(parse_expression(text), ns, context)


@overload
def expand(node: ArithmeticNode, ns: Namespace, context: str) -> ArithmeticNode: ...
@overload
def expand(node: ComparisonNode, ns: Namespace, context: str) -> ComparisonNode: ...


def expand(node: ParsedNode, ns: Namespace, context: str) -> ParsedNode:
    """Expand every macro call under *node*; a comparison stays a comparison and arithmetic stays arithmetic.

    Args:
        node: The parsed expression.
        ns: Where the macros are declared.
        context: What an error names.
    """
    if isinstance(node, ComparisonNode):
        return ComparisonNode(node.op, _expand(node.left, ns, context, ()), _expand(node.right, ns, context, ()))
    return _expand(node, ns, context, ())


def macro_signature(name: str, macro: MacroBlock) -> str:
    """Human-readable call signature, for error messages."""
    parts = [*macro.args, *(f'{k}=...' for k in macro.kwargs)]
    return f'{name}({", ".join(parts)})'


def parse_template(name: str, macro: MacroBlock, context: str) -> ArithmeticNode:
    """Parse a macro template, rejecting comparisons."""
    body = parse_expression(macro.template)
    if isinstance(body, ComparisonNode):
        msg = f"{context}: macro '{name}' template must not contain a comparison operator. Got: {macro.template!r}"
        raise SchemaError(msg)
    return body


def _expand(node: ArithmeticNode, ns: Namespace, context: str, stack: tuple[str, ...]) -> ArithmeticNode:
    """*node* with every macro call under it substituted; *stack* is the macros this walk is inside.

    A name a template reads is checked against the entries being resolved
    here, where the macros it came through are known, so a cycle closed
    through a macro is reported with the macros in its chain.
    """
    if isinstance(node, NameNode) and stack and (refusal := ns.cycle(node.name, context, stack)) is not None:
        raise SchemaError(refusal)
    if isinstance(node, FunctionCallNode) and node.name in ns.schema.macros:
        if node.name in stack:
            msg = f'{context}: circular macro reference: {" -> ".join([*stack, node.name])}'
            raise SchemaError(msg)
        return _expand_macro(node, ns, context, stack)
    return with_children(node, lambda child: _expand(child, ns, context, stack))


def _expand_macro(call: FunctionCallNode, ns: Namespace, context: str, stack: tuple[str, ...]) -> ArithmeticNode:
    """Call-by-value: arguments are expanded before substitution, and the substituted body is expanded again."""
    macro = ns.schema.macros[call.name]
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
        **{formal: _expand(arg, ns, context, stack) for formal, arg in zip(macro.args, call.args, strict=True)},
        **{formal: _expand(call.kwargs[formal], ns, context, stack) for formal in macro.kwargs},
    }
    body = parse_template(call.name, macro, context)
    substituted = _substitute(body, bindings, context)
    return _expand(substituted, ns, context, (*stack, call.name))


def _substitute(node: ArithmeticNode, bindings: dict[str, ArithmeticNode], context: str) -> ArithmeticNode:
    """Replace formal-name NameNodes in *node* with their bound subtrees, and formal names inside a column selection."""
    if isinstance(node, NameNode) and node.name in bindings:
        return bindings[node.name]
    if isinstance(node, ColumnsNode):
        return _substitute_columns(node, bindings, context)
    return with_children(node, lambda child: _substitute(child, bindings, context))


def _substitute_columns(node: ColumnsNode, bindings: dict[str, ArithmeticNode], context: str) -> ColumnsNode:
    """``relation[column, …]`` with each formal in it replaced by the bare name bound to it.

    A selection holds names only, so a formal there takes a name and nothing
    else: a number or an expression has no place between the brackets.
    """
    names: list[str] = []
    for name in (node.relation, *node.columns):
        bound = bindings.get(name)
        if bound is not None and not isinstance(bound, NameNode):
            msg = (
                f"{context}: the formal '{name}' stands inside {node}, where only a name fits, and the call "
                f'passes {bound}. Pass the bare name of a relation or of its column.'
            )
            raise SchemaError(msg)
        names.append(name if bound is None else bound.name)
    return ColumnsNode(names[0], tuple(names[1:]))
