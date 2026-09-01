# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""pyparsing-based parser for where strings — grammar and the unresolved AST, package-private.

Parses strings like ``"p_max > 0 AND NOT is_must_run"`` into an AST. The
resolved node vocabulary lives in :mod:`math_spec.program` beside the rest of
what a consumer dispatches on; what stays here is the grammar and the
``Unresolved*`` nodes it emits, which resolution rewrites away. No consumer
parses a where string — the front door is ``to_spec``, and what a consumer
reads is a program.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import pyparsing as pp

from math_spec._expression_parser import NAME, REAL
from math_spec.errors import SchemaError
from math_spec.program import AndNode, BooleanLiteralNode, NotNode, OrNode

if TYPE_CHECKING:
    from collections.abc import Callable

    from math_spec.program import PredicateOperator, WhereNode

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
    """``position(dim) <op> i`` before the name is checked.

    Kept apart from :class:`UnresolvedComparisonNode` because its left-hand
    side is not a name but an *application* to one, which no bare name can
    carry. ``resolution.py`` types it into
    :class:`~math_spec.program.DimensionPositionNode`.
    """

    dimension: str
    op: PredicateOperator
    position: int
    by: str | None = None


#: What resolution rewrites away on the where side — the three nodes whose
#: left-hand side is still a name the schema has not been asked about. The
#: expression side has :data:`~math_spec._expression_parser.UnresolvedNode` for
#: the same reason, and a pass meeting either ran before resolution.
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
    return UnresolvedPositionNode(
        str(dimension), cast('PredicateOperator', op), cast('int', at), None if by is None else str(by)
    )


def _comparison(tokens: pp.ParseResults) -> UnresolvedComparisonNode:
    """``name <op> literal`` off the tokens the grammar captured, the quoted marker turned into a flag."""
    name, op, value = tokens
    quoted = isinstance(value, _Quoted)
    return UnresolvedComparisonNode(str(name), cast('PredicateOperator', op), str(value) if quoted else value, quoted)


def _build_where_grammar() -> pp.ParserElement:
    """Build the pyparsing grammar for where strings.

    Both quote characters are accepted because YAML already owns one of them.
    ``NOT`` binds tightest, then ``AND``, then ``OR``.
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
    comparator = pp.one_of('<= >= == != < >')

    position_call = (
        pp.Suppress(pp.Keyword('position')) + pp.Suppress('(') + name + pp.Optional(grouped_by) + pp.Suppress(')')
    )
    position_comparison = (position_call + comparator + position).set_parse_action(_position_comparison)

    comparison = (name + comparator + (number | quoted | name)).set_parse_action(_comparison)
    # pyrefly: ignore[implicit-any-lambda]
    existence = name.copy().set_parse_action(lambda t: UnresolvedNameNode(t[0]))

    # `position_comparison` leads: it starts with a keyword that `existence`
    # would otherwise take for a bare name, and `comparison` for a parameter.
    # See `DimensionPositionNode` for why it converts on the left (#32).
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
    """A parse action left-folding a flat operator chain into *node_type*.

    ``AND`` and ``OR`` differ only in the node they build; the fold is the
    grammar's associativity, which is one rule.
    """

    def fold(tokens: pp.ParseResults) -> Any:
        items = list(tokens)
        result: WhereNode | UnresolvedWhereNode = items[0]
        for item in items[1:]:
            result = node_type(cast('WhereNode', result), item)
        return result

    return fold


_WHERE_GRAMMAR = _build_where_grammar()

#: The spelling this grammar dropped, and its rewrite (#32). A retired syntax
#: speaks before the generic mismatch, the same way a retired kwarg does in
#: `operators.call_shape_error`: "Expected end of text, found '('" is what every
#: model written against the old spelling would otherwise get.
_INDEX_CALL = re.compile(r'\bindex\s*\(')
_INDEX_REWRITE = (
    "\n\n  index() is now position(), and converts on the left: write 'position(dim) == i' "
    "for 'dim == index(dim, i)', and 'position(dim, by=lookup) == i' for the grouped form."
)


def _named_rewrite(text: str, loc: int) -> str | None:
    """The rewrite for a predictable mistake at the parse failure, or ``None``.

    The connective habits of pandas and C — ``&``, ``|``, ``~``, ``!``,
    doubled or not — and a lone ``=``. Keyed on the token standing where the
    grammar gave up, as the expression grammar's ``_named_rewrite`` is, so a
    diagnosis never fires on a where string that parses; ``!=``, ``<`` and
    ``>`` are legal here, so only the tokens no predicate admits are
    diagnosed.
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


def parse_where(text: str) -> WhereNode | UnresolvedWhereNode:
    """Parse a where string into an AST, its leaves still unresolved.

    The connectives and literals are the resolved vocabulary's own; the leaves
    naming declarations are ``Unresolved*`` nodes, and the return type says so.
    Only :func:`~math_spec.resolution.resolve_where` takes a tree this shape —
    a :class:`~math_spec.program.Mask` refuses one, and now says so before it
    is built.

    Raises:
        SchemaError: If *text* is not a where string of the language. A
            predictable mistake — ``&``/``|``/``~``/``!`` for a connective, a
            lone ``=``, the retired ``index()`` — is named with its rewrite
            beside the grammar's own complaint.
    """
    try:
        result = _WHERE_GRAMMAR.parse_string(text, parse_all=True)
    except pp.ParseException as e:
        rewrite = _named_rewrite(text, e.loc)
        hint = f'{rewrite}\n' if rewrite is not None else ''
        msg = f'Failed to parse where string: {text!r}\n{hint}{e}'
        if _INDEX_CALL.search(text):
            msg += _INDEX_REWRITE
        raise SchemaError(msg) from e
    return cast('WhereNode | UnresolvedWhereNode', result[0])
