# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""pyparsing-based parser for where strings — grammar and AST only.

Parses strings like ``"p_max > 0 AND NOT is_must_run"`` into an AST. What a
mask *means* is the consumer's business: it evaluates the AST against the data
it holds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, cast

import pyparsing as pp

from math_spec.errors import SchemaError
from math_spec.expression_parser import REAL

if TYPE_CHECKING:
    import datetime
    from collections.abc import Callable

PredicateOperator = Literal['<=', '>=', '==', '!=', '<', '>']

# ---------------------------------------------------------------------------
# AST nodes
# ---------------------------------------------------------------------------


@dataclass
class BooleanLiteralNode:
    value: bool


@dataclass
class UnresolvedNameNode:
    """A bare name — unresolved. ``resolution.py`` types it."""

    name: str


@dataclass
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


@dataclass
class UnresolvedPositionNode:
    """``position(dim) <op> i`` before the name is checked.

    Kept apart from :class:`UnresolvedComparisonNode` because its left-hand
    side is not a name but an *application* to one, which no bare name can
    carry. ``resolution.py`` types it into :class:`DimensionPositionNode`.
    """

    dimension: str
    op: PredicateOperator
    position: int
    by: str | None = None


@dataclass
class ParameterDefinedNode:
    """True wherever the named parameter is non-null and finite."""

    name: str


@dataclass
class VariableDefinedNode:
    """True at the coordinates where the named variable exists.

    The variable counterpart of :class:`ParameterDefinedNode`, and spelled the
    same way — a bare name. A parameter's bare name asks whether it has a value
    here; a variable's asks whether it exists here.
    """

    name: str


@dataclass
class ParameterComparisonNode:
    """Compare a parameter against a literal, element-wise."""

    name: str
    op: PredicateOperator
    value: float | str


@dataclass
class DimensionComparisonNode:
    """Compare a dimension's own coordinates against a literal."""

    name: str
    op: PredicateOperator
    value: float | str | datetime.date


@dataclass
class DimensionPositionNode:
    """Compare where a row sits along a dimension against a position — ``position(snapshot) == 0``.

    Both sides are integers, negative counting from the end; comparing
    coordinates against the label *at* a position would read differently on an
    axis whose coordinates do not arrive sorted (#32). With ``by`` the position
    is counted within each group the lookup makes.
    """

    name: str
    op: PredicateOperator
    position: int
    by: str | None = None


@dataclass
class LookupComparisonNode:
    """Compare a lookup's values against a literal — ``period_of == 2030``.

    ``over`` is the dimension the lookup maps out of, copied off the
    declaration during resolution so the frame check and every consumer read it
    here rather than looking the lookup up again.
    """

    name: str
    over: str
    op: PredicateOperator
    value: float | str | datetime.date


@dataclass
class LookupPairComparisonNode:
    """Compare two lookups over one dimension — ``from != to``.

    The one comparison whose both sides are structure: two maps out of the
    same dimension, tested row by row on that dimension's own table. Over
    different dims there is no row to compare them on, which resolution
    refuses.
    """

    name: str
    other: str
    over: str
    op: PredicateOperator


@dataclass
class LookupDefinedNode:
    """True where the named lookup has a value — the partial-lookup case.

    A lookup may be partial: a null says the label belongs to no group (a
    generator on no bus, a line with one open end). This is how a declaration
    asks for the labels that *do* map, spelled as a bare name exactly as a
    parameter's definedness is.
    """

    name: str
    over: str


@dataclass
class NotNode:
    operand: WhereNode


@dataclass
class AndNode:
    left: WhereNode
    right: WhereNode


@dataclass
class OrNode:
    left: WhereNode
    right: WhereNode


WhereNode = (
    BooleanLiteralNode
    | UnresolvedNameNode
    | UnresolvedComparisonNode
    | UnresolvedPositionNode
    | DimensionPositionNode
    | ParameterDefinedNode
    | VariableDefinedNode
    | ParameterComparisonNode
    | DimensionComparisonNode
    | LookupComparisonNode
    | LookupPairComparisonNode
    | LookupDefinedNode
    | NotNode
    | AndNode
    | OrNode
)

#: What resolution rewrites away on the where side — the three nodes whose
#: left-hand side is still a name the schema has not been asked about. The
#: expression side has :data:`~math_spec.expression_parser.UnresolvedNode` for
#: the same reason, and a pass meeting either ran before resolution.
UnresolvedWhereNode = UnresolvedNameNode | UnresolvedComparisonNode | UnresolvedPositionNode

#: Every predicate resolution has typed: it names a declaration and the kind is
#: settled. Resolution passes these straight through, having nothing left to
#: decide about them.
TypedPredicateNode = (
    ParameterComparisonNode
    | ParameterDefinedNode
    | VariableDefinedNode
    | DimensionComparisonNode
    | DimensionPositionNode
    | LookupComparisonNode
    | LookupPairComparisonNode
    | LookupDefinedNode
)

#: The boolean connectives — the only where nodes carrying other where nodes,
#: and so the only place a walk over a predicate recurses.
ConnectiveWhereNode = NotNode | AndNode | OrNode


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

    name = pp.Regex(r'[a-zA-Z_][a-zA-Z0-9_]*')

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
        result = items[0]
        for item in items[1:]:
            result = node_type(result, item)
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


def parse_where(text: str) -> WhereNode:
    """Parse a where string into an AST.

    Raises:
        SchemaError: If *text* is not a where string of the language.
    """
    try:
        result = _WHERE_GRAMMAR.parse_string(text, parse_all=True)
    except pp.ParseException as e:
        msg = f'Failed to parse where string: {text!r}\n{e}'
        if _INDEX_CALL.search(text):
            msg += _INDEX_REWRITE
        raise SchemaError(msg) from e
    return cast('WhereNode', result[0])
