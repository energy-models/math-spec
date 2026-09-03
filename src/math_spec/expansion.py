# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Named sub-expressions and macros, expanded into the core AST before anything reads the expression."""

from __future__ import annotations

from typing import TYPE_CHECKING, overload

from math_spec._expression_parser import (
    ArithmeticNode,
    CaseArm,
    CasesNode,
    ComparisonNode,
    FunctionCallNode,
    NameNode,
    ParsedNode,
    parse_expression,
    with_children,
)
from math_spec._where_parser import parse_where
from math_spec.errors import SchemaError

if TYPE_CHECKING:
    from math_spec.model import ExpressionBlock, MacroBlock, Spec


def parse_and_expand(text: str, schema: Spec, context: str, *, used: set[str] | None = None) -> ParsedNode:
    """Parse *text* and expand named sub-expressions and macros to core AST.

    Args:
        text: The expression as the file wrote it.
        schema: Where names and macros are declared.
        context: What an error names.
        used: Where given, every named expression inlined on the way is added
            to it — the ones a reference reaches through another entry or a
            macro included.
    """
    return expand(parse_expression(text), schema, context, used=used)


def read_by_the_math(schema: Spec) -> frozenset[str]:
    """The named expressions the math reads: every entry the objective or a constraint inlines, transitively.

    Decided by expanding those two positions alone: a bound and a ``where``
    name no entry, and a piecewise link's expression reaches here through the
    constraints its expansion emits. The rest of the ``expressions:`` section
    is read back after a solve and never fed to one
    (:attr:`math_spec.program.ExpressionDeclaration.in_math`).

    """
    used: set[str] = set()
    for name, block in schema.constraints.items():
        parse_and_expand(block.expression, schema, f"constraint '{name}'", used=used)
    if schema.objective is not None:
        parse_and_expand(schema.objective.expression, schema, 'the objective', used=used)
    return frozenset(used)


@overload
def expand(
    node: ArithmeticNode, schema: Spec, context: str, *, shadow: frozenset[str] = ..., used: set[str] | None = ...
) -> ArithmeticNode: ...
@overload
def expand(
    node: ComparisonNode, schema: Spec, context: str, *, shadow: frozenset[str] = ..., used: set[str] | None = ...
) -> ComparisonNode: ...


def expand(
    node: ParsedNode,
    schema: Spec,
    context: str,
    *,
    shadow: frozenset[str] = frozenset(),
    used: set[str] | None = None,
) -> ParsedNode:
    """Expand all named sub-expressions and macro calls under *node*.

    A comparison stays a comparison and an arithmetic node stays arithmetic.

    Args:
        node: The parsed expression.
        schema: Where names and macros are declared.
        context: What an error names.
        shadow: Names left as written even where a named expression has that
            name — a template's formals, checked without a call to bind them.
        used: Where given, collects the name of every named expression inlined.
    """
    if isinstance(node, ComparisonNode):
        return ComparisonNode(
            node.op,
            _expand(node.left, schema, context, (), shadow, used),
            _expand(node.right, schema, context, (), shadow, used),
        )
    return _expand(node, schema, context, (), shadow, used)


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
    used: set[str] | None,
) -> ArithmeticNode:
    def _cycle(name: str, kind: str) -> None:
        if name in stack:
            chain = ' -> '.join([*stack, name])
            msg = f'{context}: circular {kind} reference: {chain}'
            raise SchemaError(msg)

    if isinstance(node, NameNode) and node.name in schema.expressions and node.name not in shadow:
        _cycle(node.name, 'expression')
        if used is not None:
            used.add(node.name)
        body = _parse_named(node.name, schema, context)
        return _expand(body, schema, context, (*stack, node.name), shadow, used)

    if isinstance(node, FunctionCallNode) and node.name in schema.macros:
        _cycle(node.name, 'macro')
        return _expand_macro(node, schema, context, stack, shadow, used)

    return with_children(node, lambda child: _expand(child, schema, context, stack, shadow, used))


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
    used: set[str] | None,
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
            formal: _expand(arg, schema, context, stack, shadow, used)
            for formal, arg in zip(macro.args, call.args, strict=True)
        },
        **{formal: _expand(call.kwargs[formal], schema, context, stack, shadow, used) for formal in macro.kwargs},
    }
    body = parse_template(call.name, macro, context)
    substituted = _substitute(body, bindings)
    return _expand(substituted, schema, context, (*stack, call.name), shadow, used)


def _substitute(node: ArithmeticNode, bindings: dict[str, ArithmeticNode]) -> ArithmeticNode:
    """Replace formal-name NameNodes in *node* with their bound subtrees."""
    if isinstance(node, NameNode) and node.name in bindings:
        return bindings[node.name]
    return with_children(node, lambda child: _substitute(child, bindings))
