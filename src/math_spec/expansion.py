# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Named sub-expressions and expression macros — YAML-defined, schema-local.

Both are expanded into the AST before anything reads the expression.

Two mechanisms, one substitution engine, zero global state:

- **Named sub-expressions**: the YAML ``expressions:`` block maps a name to
  an expression string. Referencing the name splices in the parsed subtree.
  Substitution is only half of what the block means, though: a named
  expression has fixed dims and is readable after a solve (the rules for named expressions), which a
  macro — parameterised, dimensionless until called — never is.

- **Macros**: the YAML ``macros:`` block declares parameterised expression
  templates — language, not code::

      macros:
        weighted_sum:
          args: [array, weights]
          kwargs: [over]
          template: sum(array * weights, over=over)

  Usage: ``weighted_sum(p, cost, over=generator)``. Formal names shadow
  model names inside the body; everything else resolves against the model
  namespace as usual.

Because macros live in the schema, a YAML file is fully self-contained: its
meaning never depends on Python-side registration state. This also makes
load-time validation complete — every template can be name-checked against
this schema (see ``validation.py``), used or not.

There is no Python operator registry: the built-in set is closed, macros cover
composition, and math the language cannot say goes in a declared ``escape:``
island (#38) — visible in the file and bounded by its ``where`` mask, rather
than a registered function that reads like a built-in on the page.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, assert_never, overload

from math_spec.errors import SchemaError
from math_spec.expression_parser import (
    ArithmeticNode,
    BinaryOperatorNode,
    ComparisonNode,
    ExpressionNode,
    FunctionCallNode,
    LeafNode,
    NameNode,
    UnaryOperatorNode,
    parse_expression,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from math_spec.model import MacroBlock, Model


def parse_and_expand(text: str, schema: Model, context: str = 'expression') -> ExpressionNode:
    """Parse *text* and expand named sub-expressions and macros to core AST."""
    return expand(parse_expression(text), schema, context)


@overload
def expand(node: ArithmeticNode, schema: Model, context: str = ...) -> ArithmeticNode: ...
@overload
def expand(node: ComparisonNode, schema: Model, context: str = ...) -> ComparisonNode: ...


def expand(node: ExpressionNode, schema: Model, context: str = 'expression') -> ExpressionNode:
    """Expand all named sub-expressions and macro calls under *node*.

    Expansion never changes the shape of the root: a comparison stays a
    comparison, an arithmetic node stays arithmetic. The overloads say so, so
    callers holding an ``ArithmeticNode`` keep it across the call.
    """
    if isinstance(node, ComparisonNode):
        return ComparisonNode(
            node.op,
            _expand(node.left, schema, context, ()),
            _expand(node.right, schema, context, ()),
        )
    return _expand(node, schema, context, ())


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


def _descend(node: ArithmeticNode, recurse: Callable[[ArithmeticNode], ArithmeticNode]) -> ArithmeticNode:
    """Rebuild *node* with *recurse* applied to each child.

    The structural half of a tree walk, shared by the two walks below: they
    differ only in what they do at NameNode and FunctionCallNode, and duplicating
    the other four cases is how the two drift apart.
    """
    if isinstance(node, LeafNode):
        return node
    if isinstance(node, UnaryOperatorNode):
        return UnaryOperatorNode(node.op, recurse(node.operand))
    if isinstance(node, BinaryOperatorNode):
        return BinaryOperatorNode(node.op, recurse(node.left), recurse(node.right))
    if isinstance(node, FunctionCallNode):
        return FunctionCallNode(
            node.name,
            [recurse(a) for a in node.args],
            {k: recurse(v) for k, v in node.kwargs.items()},
        )
    assert_never(node)


def _expand(
    node: ArithmeticNode,
    schema: Model,
    context: str,
    stack: tuple[str, ...],
) -> ArithmeticNode:
    def _cycle(name: str, kind: str) -> None:
        if name in stack:
            chain = ' -> '.join([*stack, name])
            msg = f'{context}: circular {kind} reference: {chain}'
            raise SchemaError(msg)

    if isinstance(node, NameNode) and node.name in schema.expressions:
        _cycle(node.name, 'expression')
        body = _parse_named(node.name, schema, context)
        return _expand(body, schema, context, (*stack, node.name))

    if isinstance(node, FunctionCallNode) and node.name in schema.macros:
        _cycle(node.name, 'macro')
        return _expand_macro(node, schema, context, stack)

    return _descend(node, lambda child: _expand(child, schema, context, stack))


def _parse_named(name: str, schema: Model, context: str) -> ArithmeticNode:
    body = parse_expression(schema.expressions[name].expression)
    if isinstance(body, ComparisonNode):
        msg = (
            f"{context}: named expression '{name}' must not contain a "
            f'comparison operator. Got: {schema.expressions[name].expression!r}'
        )
        raise SchemaError(msg)
    return body


def _expand_macro(
    call: FunctionCallNode,
    schema: Model,
    context: str,
    stack: tuple[str, ...],
) -> ArithmeticNode:
    """Expand one macro call to its substituted, fully expanded body.

    Call-by-value: arguments are expanded before substitution, so they may
    themselves use named expressions and macros. The substituted body is then
    expanded again, since a template may reference named expressions or other
    macros of its own.
    """
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
        **{formal: _expand(arg, schema, context, stack) for formal, arg in zip(macro.args, call.args, strict=False)},
        **{formal: _expand(call.kwargs[formal], schema, context, stack) for formal in macro.kwargs},
    }
    body = parse_template(call.name, macro, context)
    substituted = _substitute(body, bindings)
    return _expand(substituted, schema, context, (*stack, call.name))


def _substitute(node: ArithmeticNode, bindings: dict[str, ArithmeticNode]) -> ArithmeticNode:
    """Replace formal-name NameNodes in *node* with their bound subtrees."""
    if isinstance(node, NameNode) and node.name in bindings:
        return bindings[node.name]
    return _descend(node, lambda child: _substitute(child, bindings))
