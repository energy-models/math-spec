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

from math_spec._expression_parser import NAME, REAL, parse_text
from math_spec.program import AndNode, BooleanLiteralNode, NotNode, OrNode, PredicateOperator

if TYPE_CHECKING:
    from collections.abc import Callable

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
class UnresolvedPositionNode:
    """``position(dim[, by=lookup]) <op> i`` before the names are checked; ``resolution.py`` types it."""

    dimension: str
    op: PredicateOperator
    position: int
    by: str | None = None


#: What resolution rewrites away on the where side — the three nodes whose
#: left-hand side is still a name the schema has not been asked about.
UnresolvedWhereNode = UnresolvedNameNode | UnresolvedComparisonNode | UnresolvedPositionNode


# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------


class _Quoted(str):
    """A right-hand side that arrived in quotes; :func:`_comparison` turns it back into a flag."""

    __slots__ = ()


def _position_comparison(tokens: pp.ParseResults) -> UnresolvedPositionNode:
    """``position(dim[, by=lookup]) <op> i`` off the tokens the grammar captured."""
    *call, op, at = tokens
    dimension, by = call[0], call[1] if len(call) > 1 else None
    return UnresolvedPositionNode(str(dimension), op, at, None if by is None else str(by))


def _comparison(tokens: pp.ParseResults) -> UnresolvedComparisonNode:
    """``name <op> literal`` off the tokens the grammar captured, the quoted marker turned into a flag."""
    name, op, value = tokens
    quoted = isinstance(value, _Quoted)
    return UnresolvedComparisonNode(str(name), op, str(value) if quoted else value, quoted)


def _build_where_grammar() -> pp.ParserElement:
    """Build the pyparsing grammar for where strings.

    Both quote characters are accepted because YAML already owns one of them.
    ``NOT`` binds tightest, then ``AND``, then ``OR``. ``position(...)`` leads
    the alternation, since ``position`` would otherwise be read as a bare name.
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

    grouped_by = pp.Suppress(',') + pp.Suppress(pp.Keyword('by')) + pp.Suppress('=') + name
    comparator = pp.one_of(list(get_args(PredicateOperator)))

    position_call = (
        pp.Suppress(pp.Keyword('position')) + pp.Suppress('(') + name + pp.Optional(grouped_by) + pp.Suppress(')')
    )
    position_comparison = (position_call + comparator + position).set_parse_action(_position_comparison)

    comparison = (name + comparator + (number | quoted | name)).set_parse_action(_comparison)
    # pyrefly: ignore[implicit-any-lambda]
    existence = name.copy().set_parse_action(lambda t: UnresolvedNameNode(t[0]))

    atom = (
        true_lit
        | false_lit
        | position_comparison
        | comparison
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
    return cast('WhereNode | UnresolvedWhereNode', parse_text(_WHERE_GRAMMAR, text, 'where string', _named_rewrite))
