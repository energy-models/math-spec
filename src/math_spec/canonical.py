# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The normal form behind ``Spec.to_yaml(canonical=True)`` — one text for every file that means the same thing."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, overload

import yaml

from math_spec._expression_parser import (
    BinaryOperatorNode,
    ComparisonNode,
    FunctionCallNode,
    UnaryOperatorNode,
    operand,
    parse_expression,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from math_spec._expression_parser import ArithmeticNode, ParsedNode
    from math_spec.model import Spec

#: Which sign a term of a sum is written under, which is also the operator that
#: rebuilds it.
Sign = Literal['+', '-']

#: Where a declaration's expression text sits under a section, once the spec is
#: plain data. A link is the odd one: it serialises back to the ``[expression,
#: values]`` list the file wrote, so its expression is a position rather than a
#: key.
_EXPRESSION_KEYS = ('expression', 'otherwise', 'template')


def _signed(sign: Sign, node: ArithmeticNode) -> tuple[Sign, ArithmeticNode]:
    """One term with a leading sign folded into the sign it is written under.

    ``+ -x`` is ``- x`` and ``- -x`` is ``+ x``, so a term sorts and prints
    under one spelling however the file wrote it. Folding is also what makes
    the walk the inverse of :func:`_sum`, which writes a leading minus term as
    the negation it is — without it a second pass would read that minus as part
    of the term and sort by it.
    """
    while isinstance(node, UnaryOperatorNode):
        if node.op == '-':
            sign = '-' if sign == '+' else '+'
        node = node.operand
    return sign, node


def _signed_terms(node: ArithmeticNode) -> Iterator[tuple[Sign, ArithmeticNode]]:
    """The sum *node* is, as each term with the sign it carries.

    Only the left spine is followed, which is how ``a + b - c`` associates. A
    bracketed right operand stays one term, so ``a - (b - c)`` keeps the group
    the file wrote rather than being redistributed into ``a - b + c``.
    """
    if isinstance(node, BinaryOperatorNode) and node.op in ('+', '-'):
        yield from _signed_terms(node.left)
        yield _signed(node.op, node.right)
    else:
        yield _signed('+', node)


def _factors(node: ArithmeticNode) -> Iterator[ArithmeticNode]:
    """The product *node* is, as its factors. A division stays one factor, its own node."""
    if isinstance(node, BinaryOperatorNode) and node.op == '*':
        yield from _factors(node.left)
        yield node.right
    else:
        yield node


def _order(term: tuple[Sign, ArithmeticNode]) -> tuple[str, Sign]:
    """The key a term of a sum sorts under: the text it prints as, then the sign it is written under.

    The sign is the tie-breaker rather than part of the text, so ``a - b`` and
    ``b - a`` order their terms alike and differ only in which one is negative.
    """
    sign, node = term
    return str(node), sign


def _sum(terms: list[tuple[Sign, ArithmeticNode]]) -> ArithmeticNode:
    """The terms back into one left-leaning spine, a leading minus becoming the sign it was."""
    sign, first = terms[0]
    built: ArithmeticNode = first if sign == '+' else UnaryOperatorNode('-', first)
    for sign, term in terms[1:]:
        built = BinaryOperatorNode(sign, built, term)
    return built


@overload
def normalised(node: ArithmeticNode) -> ArithmeticNode: ...
@overload
def normalised(node: ComparisonNode) -> ComparisonNode: ...


def normalised(node: ParsedNode) -> ParsedNode:
    """*node* with every order the math does not fix put into one order.

    Sorting is by the text an operand prints as, which is a total order over
    trees: a printed tree parses back to the tree it came from, so two
    operands that print alike are one tree. Addition and multiplication
    commute and are sorted. Subtraction, division, exponentiation and a call's
    positional arguments are not, and keep the order the file wrote.
    """
    if isinstance(node, ComparisonNode):
        left, right = (normalised(side) for side in (node.left, node.right))
        return ComparisonNode(node.op, left, right)
    if isinstance(node, FunctionCallNode):
        return FunctionCallNode(
            node.name,
            tuple(normalised(arg) for arg in node.args),
            {key: normalised(value) for key, value in sorted(node.kwargs.items())},
        )
    if isinstance(node, UnaryOperatorNode):
        return UnaryOperatorNode(node.op, normalised(node.operand))
    if isinstance(node, BinaryOperatorNode):
        if node.op in ('+', '-'):
            terms: list[tuple[Sign, ArithmeticNode]] = [(sign, normalised(term)) for sign, term in _signed_terms(node)]
            return _sum(sorted(terms, key=_order))
        if node.op == '*':
            factors: list[ArithmeticNode] = sorted((normalised(factor) for factor in _factors(node)), key=str)
            product: ArithmeticNode = factors[0]
            for factor in factors[1:]:
                product = BinaryOperatorNode('*', product, factor)
            return product
        return BinaryOperatorNode(node.op, normalised(node.left), normalised(node.right))
    return node


def laid_out(node: ParsedNode) -> str:
    """*node* as text, one term of its leading sum per line.

    A term that changes is then one line of a diff rather than a rewritten
    expression. Every line after the first opens with its own sign, and a
    comparison's operator opens the last, which is text the grammar reads back
    as the same tree. An expression of one term stays on one line.

    Each term is bracketed the way any operand is, and the first through
    :func:`_sum`, because a line is read back as part of the whole: ``- b - c``
    under a leading ``a`` is ``a - b - c``, where the term written was
    ``(b - c)``. An expression of one term is one line, operator and all.
    """
    head = node.left if isinstance(node, ComparisonNode) else node
    terms = list(_signed_terms(head))
    if len(terms) < 2:
        return str(node)
    lines = [str(_sum(terms[:1]))]
    lines += [f'{sign} {operand(term)}' for sign, term in terms[1:]]
    if isinstance(node, ComparisonNode):
        lines.append(f'{node.op} {node.right}')
    return '\n'.join(lines)


def canonical_text(text: str) -> str:
    """One expression string in the normal form, parsed and printed rather than edited."""
    return laid_out(normalised(parse_expression(text)))


def _canonical_block(block: Any) -> Any:
    """One declaration, with every expression under it normalised and everything else untouched."""
    if isinstance(block, dict):
        return {
            key: canonical_text(value)
            if key in _EXPRESSION_KEYS and isinstance(value, str)
            else _canonical_block(value)
            for key, value in block.items()
        }
    if isinstance(block, list):
        return [_canonical_block(item) for item in block]
    return block


def _canonical_links(links: list[Any]) -> list[Any]:
    """A piecewise block's links, whose expression is the first position of the list the file wrote."""
    return [[canonical_text(link[0]), *link[1:]] for link in links]


def canonical_dict(spec: Spec) -> dict[str, Any]:
    """The spec as plain data, in the form two files that mean the same thing share.

    Declarations are sorted by name and every expression is printed from its
    parsed tree, so what is left of a difference is a difference in the model.
    A ``where`` string, the order of a ``cases:`` block's regions, the order of
    a declaration's ``dims`` and the order of a piecewise block's links are all
    left as written.

    Args:
        spec: The loaded model.

    Returns:
        Plain data, ready for :func:`canonical_yaml`. Loading it gives the same
        model back, and not a spec equal to *spec*: an expression reprinted in
        the normal form is a different string.
    """
    data = spec.to_dict()
    built: dict[str, Any] = {}
    for section, value in data.items():
        if isinstance(value, dict) and section != 'objective':
            built[section] = {name: _canonical_block(block) for name, block in sorted(value.items())}
        else:
            built[section] = _canonical_block(value)
    for block in built.get('piecewise', {}).values():
        block['links'] = _canonical_links(block['links'])
    return built


class _Dumper(yaml.SafeDumper):
    """A dumper writing a multi-line expression as a block scalar, rather than escaping the newlines into one line."""


def _scalar(dumper: yaml.SafeDumper, text: str) -> yaml.ScalarNode:
    return dumper.represent_scalar('tag:yaml.org,2002:str', text, style='|' if '\n' in text else None)


_Dumper.add_representer(str, _scalar)


def canonical_yaml(spec: Spec) -> str:
    """The file a reviewer diffs — :func:`canonical_dict` as YAML, each expression term on its own line."""
    return yaml.dump(canonical_dict(spec), Dumper=_Dumper, sort_keys=False, allow_unicode=True)
