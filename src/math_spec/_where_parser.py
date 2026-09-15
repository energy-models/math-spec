# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The where-string grammar and the ``Unresolved*`` nodes it emits, package-private.

The resolved vocabulary lives in :mod:`math_spec.program`.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any, cast, get_args

import pyparsing as pp

from math_spec._expression_parser import (
    ARITHMETIC,
    NAME,
    REAL,
    FunctionCallNode,
    NameNode,
    NumberNode,
    UnaryOperatorNode,
    children,
    parse_text,
)
from math_spec.program import AndNode, BooleanLiteralNode, NotNode, OrNode, PredicateOperator, where_children

if TYPE_CHECKING:
    from collections.abc import Callable

    from math_spec._expression_parser import ArithmeticNode
    from math_spec.program import WhereNode

# ---------------------------------------------------------------------------
# AST nodes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UnresolvedNameNode:
    """A bare name — unresolved. ``resolution.py`` types it."""

    name: str


@dataclass(frozen=True)
class UnresolvedComparisonNode:
    """A comparison against an unresolved name. ``resolution.py`` types it."""

    name: str
    op: PredicateOperator
    value: float | str
    #: Whether the right-hand side arrived in quotes. A bare word is ambiguous
    #: — it may name a declaration — and resolution refuses it for that reason;
    #: a quoted one is unambiguously a label, which is the only way to write
    #: ``combined-cycle`` or a date. Consumed by resolution, never lowered.
    quoted: bool = False


@dataclass(frozen=True)
class UnresolvedExpressionComparisonNode:
    """``expression <op> expression``, both sides still the bare parse — ``resolution.py`` types and judges them.

    The grammar reaches for this only where a side is more than one name or
    literal, so the simpler forms keep their own nodes and their own rules.
    """

    left: ArithmeticNode
    op: PredicateOperator
    right: ArithmeticNode


@dataclass(frozen=True)
class UnresolvedPositionNode:
    """``position(dim[, by=relation[, within=columns]]) <op> i`` before the names are checked; ``resolution.py`` types it."""

    dimension: str
    op: PredicateOperator
    position: int
    by: str | None = None
    into: tuple[str, ...] | None = None


#: What resolution rewrites away on the where side — the three nodes whose
#: left-hand side is still a name the schema has not been asked about.
UnresolvedWhereNode = (
    UnresolvedNameNode | UnresolvedComparisonNode | UnresolvedExpressionComparisonNode | UnresolvedPositionNode
)


# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------


class _Quoted(str):
    """A right-hand side that arrived in quotes; :func:`_comparison` turns it back into a flag."""

    __slots__ = ()


def _position_comparison(tokens: pp.ParseResults) -> UnresolvedPositionNode:
    """``position(dim[, by=relation[, within=columns]]) <op> i`` off the tokens the grammar captured."""
    dimension, *call, op, at = tokens
    by = str(call[0]) if call else None
    into = tuple(str(token) for token in call[1]) if len(call) > 1 else None
    return UnresolvedPositionNode(str(dimension), op, at, by, into)


def _is_plain(node: ArithmeticNode) -> bool:
    """Whether *node* is one name or one signed number — a side the simpler comparison forms own."""
    if isinstance(node, UnaryOperatorNode):
        return isinstance(node.operand, NumberNode)
    return isinstance(node, NameNode | NumberNode)


def _reads_arithmetic(tokens: pp.ParseResults) -> bool:
    """Whether a comparison needs the expression form at all.

    Two plain sides are ``name <op> literal`` or ``name <op> name``, and a
    ``position(...)`` call against a plain side is the position form; each of
    those has a node of its own, so this form stands aside for them.
    """
    left, _, right = tokens
    if _is_plain(left) and _is_plain(right):
        return False
    return not (isinstance(left, FunctionCallNode) and left.name == 'position' and _is_plain(right))


def _expression_comparison(tokens: pp.ParseResults) -> UnresolvedExpressionComparisonNode:
    left, op, right = tokens
    return UnresolvedExpressionComparisonNode(left, op, right)


def _comparison(tokens: pp.ParseResults) -> UnresolvedComparisonNode:
    """``name <op> literal`` off the tokens the grammar captured, the quoted marker turned into a flag."""
    name, op, value = tokens
    quoted = isinstance(value, _Quoted)
    return UnresolvedComparisonNode(str(name), op, str(value) if quoted else value, quoted)


def _build_where_grammar() -> pp.ParserElement:
    """Build the pyparsing grammar for where strings.

    Both quote characters are accepted because YAML already owns one of them.
    ``NOT`` binds tightest, then ``AND``, then ``OR``. The three comparison
    forms are matched longest-first, so ``p > 2 * q`` is not cut short at
    ``p > 2``; the expression form stands aside for the two plain shapes
    (:func:`_reads_arithmetic`), so ``p > 0`` keeps the node its dtype rule
    is written for.
    """
    where_expr = pp.Forward()

    true_lit = pp.CaselessKeyword('True').set_parse_action(lambda: BooleanLiteralNode(True))
    false_lit = pp.CaselessKeyword('False').set_parse_action(lambda: BooleanLiteralNode(False))

    # pyrefly: ignore[implicit-any-lambda]
    number = pp.Regex(rf'-?({REAL}|\d+)').set_parse_action(lambda t: float(t[0]))
    # pyrefly: ignore[implicit-any-lambda]
    position = pp.Regex(r'-?\d+').set_parse_action(lambda t: int(t[0]))

    name = pp.Regex(NAME)

    quoted = (pp.QuotedString("'", esc_char='\\') | pp.QuotedString('"', esc_char='\\')).set_parse_action(
        lambda t: _Quoted(t[0])
    )

    column = pp.Regex(rf'{NAME}(\.{NAME})?')
    columns = name | (pp.Suppress('[') + pp.DelimitedList(name) + pp.Suppress(']'))
    grouped_within = pp.Group(pp.Suppress(',') + pp.Suppress(pp.Keyword('within')) + pp.Suppress('=') + columns)
    grouped_by = (
        pp.Suppress(',') + pp.Suppress(pp.Keyword('by')) + pp.Suppress('=') + name + pp.Optional(grouped_within)
    )
    comparator = pp.one_of(list(get_args(PredicateOperator)))

    position_call = (
        pp.Suppress(pp.Keyword('position')) + pp.Suppress('(') + name + pp.Optional(grouped_by) + pp.Suppress(')')
    )
    position_comparison = (position_call + comparator + position).set_parse_action(_position_comparison)

    comparison = (column + comparator + (number | quoted | column)).set_parse_action(_comparison)
    expression_comparison = (
        (ARITHMETIC + comparator + ARITHMETIC).add_condition(_reads_arithmetic).add_parse_action(_expression_comparison)
    )
    # pyrefly: ignore[implicit-any-lambda]
    existence = name.copy().set_parse_action(lambda t: UnresolvedNameNode(t[0]))

    atom = (
        true_lit
        | false_lit
        | (position_comparison ^ comparison ^ expression_comparison)
        | existence
        | (pp.Suppress('(') + where_expr + pp.Suppress(')'))
    )

    NOT = pp.CaselessKeyword('NOT').suppress()
    # pyrefly: ignore[implicit-any-lambda]
    not_expr = (NOT + atom).set_parse_action(lambda t: NotNode(t[0])) | atom

    AND = pp.CaselessKeyword('AND').suppress()
    and_expr = not_expr + pp.ZeroOrMore(AND + not_expr)
    and_expr.set_parse_action(_folder(AndNode))

    OR = pp.CaselessKeyword('OR').suppress()
    or_expr = and_expr + pp.ZeroOrMore(OR + and_expr)
    or_expr.set_parse_action(_folder(OrNode))

    where_expr <<= or_expr
    return where_expr


def _folder(node_type: type[AndNode] | type[OrNode]) -> Callable[[pp.ParseResults], Any]:
    """A parse action left-folding a flat operator chain into *node_type*."""

    def fold(tokens: pp.ParseResults) -> Any:
        items = list(tokens)
        result: WhereNode | UnresolvedWhereNode = items[0]
        for item in items[1:]:
            result = node_type(cast('WhereNode', result), item)
        return result

    return fold


_WHERE_GRAMMAR = _build_where_grammar()


def _named_rewrite(text: str, loc: int) -> str | None:
    """The rewrite for a connective habit of pandas or C at the token where the grammar gave up, or ``None``.

    ``!=``, ``<`` and ``>`` are legal here, so only the tokens no predicate
    admits are diagnosed.
    """
    rest = text[loc:].lstrip()
    if rest.startswith('&'):
        return "'&' is not the conjunction — both predicates at once is written AND."
    if rest.startswith('|'):
        return "'|' is not the disjunction — either predicate is written OR."
    if rest.startswith(('~', '!')) and not rest.startswith('!='):
        return f"'{rest[0]}' is not the negation — it is written NOT, before the predicate."
    if rest.startswith('=') and not rest.startswith('=='):
        return "'=' compares nothing — equality is written ==."
    return None


#: The rewrite an over-deep where string is given. A long chain of predicates
#: is a test the file could carry as data instead, which is the language's own
#: answer before the general one.
_DEEP_REWRITE = (
    'Declare a parameter or relation carrying part of the test and name that here, or split the '
    'declaration into two, each masked by one half.'
)


def _nested(node: Any) -> tuple[Any, ...]:
    """What a where string nests through: a connective's operands, and the arithmetic under a comparison of expressions."""
    if isinstance(node, UnresolvedExpressionComparisonNode):
        return (node.left, node.right)
    if isinstance(node, UnresolvedWhereNode):
        return ()
    if isinstance(node, AndNode | OrNode | NotNode | BooleanLiteralNode):
        return where_children(node)
    return children(node)


@lru_cache(maxsize=4096)
def parse_where(text: str) -> WhereNode | UnresolvedWhereNode:
    """Parse a where string into an AST, its leaves still unresolved.

    The connectives and literals are the resolved vocabulary's own; the leaves
    naming declarations are ``Unresolved*`` nodes, which only
    :func:`~math_spec.resolution.resolve_where` takes.

    Raises:
        SchemaError: If *text* is not a where string of the language. A
            predictable mistake — ``&``/``|``/``~``/``!`` for a connective, a
            lone ``=`` — is named with its rewrite beside the grammar's own
            complaint.
    """
    return cast(
        'WhereNode | UnresolvedWhereNode',
        parse_text(_WHERE_GRAMMAR, text, 'where string', _named_rewrite, _nested, _DEEP_REWRITE),
    )
