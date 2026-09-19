# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The where-string grammar and the ``Unresolved*`` nodes it emits, package-private.

A where string is a boolean algebra over comparisons, and a comparison's
sides are the expression grammar's own arithmetic. What a side *is* — a
parameter, a dimension, a relation column, a ``position()`` — only the schema
knows, so the grammar hands both sides over bare and
:mod:`math_spec.resolution` reads them. The resolved vocabulary lives in
:mod:`math_spec.program`.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, cast, get_args

import pyparsing as pp

from math_spec._expression_parser import ARITHMETIC, NAME, ArithmeticNode, children, parse_text
from math_spec.program import (
    AndNode,
    BooleanLiteralNode,
    ConnectiveWhereNode,
    NotNode,
    OrNode,
    PredicateOperator,
    WhereNode,
    where_children,
)

if TYPE_CHECKING:
    from collections.abc import Callable

# ---------------------------------------------------------------------------
# AST nodes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UnresolvedNameNode:
    """A bare name — unresolved. ``resolution.py`` types it."""

    name: str


@dataclass(frozen=True)
class ColumnNode:
    """``relation.column`` on a side of a comparison — the one place the language names a column."""

    relation: str
    column: str

    @property
    def shown(self) -> str:
        """The column as the file wrote it, for an error message."""
        return f'{self.relation}.{self.column}'


@dataclass(frozen=True)
class QuotedNode:
    """A right-hand side that arrived in quotes.

    A bare word is ambiguous — it may name a declaration — and resolution
    refuses it for that reason; a quoted one is unambiguously a label, which
    is the only way to write ``combined-cycle`` or a date.
    """

    value: str


@dataclass(frozen=True)
class UnresolvedComparisonNode:
    """``side <op> side`` before the sides are read; ``resolution.py`` decides what each is.

    A side is the expression grammar's arithmetic, so a name, a number and a
    ``position(...)`` call all arrive as the nodes an expression would carry
    them in; a relation column and a quoted label have nodes of their own.
    """

    left: ArithmeticNode | ColumnNode
    op: PredicateOperator
    right: ArithmeticNode | ColumnNode | QuotedNode


#: What resolution rewrites away on the where side — the two nodes whose
#: leaves are still names the schema has not been asked about.
UnresolvedWhereNode = UnresolvedNameNode | UnresolvedComparisonNode

#: Every node a parsed where string is built of: the connectives and literals,
#: the unresolved leaves, and the arithmetic and the two side nodes under a
#: comparison. What the depth measurement walks.
_ParsedWhere = WhereNode | UnresolvedWhereNode | ArithmeticNode | ColumnNode | QuotedNode


# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------


def _build_where_grammar() -> pp.ParserElement:
    """Build the pyparsing grammar for where strings.

    Both quote characters are accepted because YAML already owns one of them.
    ``NOT`` binds tightest, then ``AND``, then ``OR``. A comparison is tried
    before a bare name, since its left side begins with one.
    """
    where_expr = pp.Forward()

    true_lit = pp.CaselessKeyword('True').set_parse_action(lambda: BooleanLiteralNode(True))
    false_lit = pp.CaselessKeyword('False').set_parse_action(lambda: BooleanLiteralNode(False))

    name = pp.Regex(NAME)
    # pyrefly: ignore[implicit-any-lambda]
    column = pp.Regex(rf'({NAME})\.({NAME})').set_parse_action(lambda t: ColumnNode(*t[0].split('.')))
    quoted = (pp.QuotedString("'", esc_char='\\') | pp.QuotedString('"', esc_char='\\')).set_parse_action(
        # pyrefly: ignore[implicit-any-lambda]
        lambda t: QuotedNode(t[0])
    )
    comparator = pp.one_of(list(get_args(PredicateOperator)))

    comparison = ((column | ARITHMETIC) + comparator + (quoted | column | ARITHMETIC)).set_parse_action(
        # pyrefly: ignore[implicit-any-lambda]
        lambda t: UnresolvedComparisonNode(t[0], t[1], t[2])
    )
    # pyrefly: ignore[implicit-any-lambda]
    existence = name.copy().set_parse_action(lambda t: UnresolvedNameNode(t[0]))

    atom = true_lit | false_lit | comparison | existence | (pp.Suppress('(') + where_expr + pp.Suppress(')'))

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


def _folder(node_type: type[AndNode] | type[OrNode]) -> Callable[[pp.ParseResults], WhereNode | UnresolvedWhereNode]:
    """A parse action left-folding a flat operator chain into *node_type*."""

    def fold(tokens: pp.ParseResults) -> WhereNode | UnresolvedWhereNode:
        items: list[WhereNode | UnresolvedWhereNode] = list(tokens)
        result = items[0]
        for item in items[1:]:
            result = node_type(cast('WhereNode', result), cast('WhereNode', item))
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


def _nested(node: _ParsedWhere) -> tuple[_ParsedWhere, ...]:
    """What a where string nests through: a connective's operands, and the arithmetic on a comparison's sides."""
    if isinstance(node, UnresolvedComparisonNode):
        return (node.left, node.right)
    if isinstance(node, ArithmeticNode):
        return children(node)
    if isinstance(node, ConnectiveWhereNode):
        return where_children(node)
    return ()


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
            complaint. A side nesting past what an expression may is refused
            as an expression is.
    """
    return cast(
        'WhereNode | UnresolvedWhereNode',
        parse_text(_WHERE_GRAMMAR, text, 'where string', _named_rewrite, _nested, _DEEP_REWRITE),
    )
