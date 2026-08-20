"""pyparsing-based parser for where strings — grammar and AST only.

Parses strings like ``"p_max > 0 AND NOT is_must_run"`` into an AST. What a
mask *means* is each backend's business: the eager lane evaluates the AST
against an xr.Dataset (``builder.evaluate_where``), the relational lane
lowers it to SQL predicates (``lowering._lower_where``).

Kept dependency-free on purpose — ``validation.py`` and ``lowering.py`` are
linopy-free by hard rule 3, and they import this module.

``NotNode``, ``AndNode`` and ``OrNode`` reference the ``WhereNode`` union in
their annotations before it is defined, which works only because ``from
__future__ import annotations`` makes annotations strings — removing that
future-import requires reordering the definitions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, cast

import pyparsing as pp

from lpspec.errors import SchemaError

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
    """``lhs <op> index(dim, i)`` before either name is checked.

    Kept apart from :class:`UnresolvedComparisonNode` because its right-hand
    side names a dimension *and* a position, which no literal can carry.
    ``resolution.py`` types it into :class:`DimensionPositionNode`.
    """

    name: str
    op: PredicateOperator
    dimension: str
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
    """Compare a dimension's coordinates against one named by *position*.

    ``where: "snapshot == index(snapshot, 0)"`` — the boundary of a recurrence
    named by where it sits rather than by the label that happens to be there,
    so the clause survives the index being relabelled. Negative counts from
    the end, ``-1`` being the last.

    With ``by`` it is the boundary of *each group* the lookup makes —
    ``index(snapshot, 0, by=period_of)`` is every period's first snapshot, and
    a row reads its own group's, the broadcast ``at(by=)`` already defines.

    Resolved rather than lowered to a literal: which label sits at a position
    is a property of the *data*, so the position travels and each lane reads
    it off the coordinate order it already holds.
    """

    name: str
    op: PredicateOperator
    position: int
    by: str | None = None


@dataclass
class LookupComparisonNode:
    """Compare a lookup's values against a literal — ``period_of == 2030``.

    ``over`` is the dimension the lookup maps out of, copied off the
    declaration during resolution so the frame check and both lanes read it
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


# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------


class _Quoted(str):
    """A right-hand side that arrived in quotes.

    A ``str`` subclass rather than a wrapper so pyparsing's own machinery keeps
    working on it. It lives between the grammar and the comparison's parse
    action and no further — :class:`UnresolvedComparisonNode` records the fact
    as a plain flag, so nothing downstream has to know this type exists.
    """

    __slots__ = ()


def _bare(value: float | str) -> float | str:
    """The literal without the quoted marker, so equality is by value."""
    return str(value) if isinstance(value, _Quoted) else value


def _position(tokens: pp.ParseResults) -> _Position:
    """``index(dim, i)`` off the tokens the grammar captured, ``by=`` included."""
    by = str(tokens[2]) if len(tokens) > 2 else None
    return _Position(str(tokens[0]), int(cast('float', tokens[1])), by)


@dataclass(frozen=True)
class _Position:
    """``index(dim, i)`` as the grammar saw it, before any name is checked.

    Like :class:`_Quoted` this lives between the grammar and the comparison's
    parse action: which dimension the left-hand side names is resolution's
    business, so the triple travels only that far.
    """

    dimension: str
    at: int
    by: str | None = None


def _comparison(name: str, op: Any, value: Any) -> UnresolvedComparisonNode | UnresolvedPositionNode:
    """The comparison node one right-hand side asks for.

    A position is its own node from the start because it is the one right-hand
    side that is neither a literal nor a name — nothing downstream could tell
    it from a parameter called ``index``.
    """
    if isinstance(value, _Position):
        return UnresolvedPositionNode(name, op, value.dimension, value.at, value.by)
    return UnresolvedComparisonNode(name, op, _bare(value), quoted=isinstance(value, _Quoted))


def _build_where_grammar() -> pp.ParserElement:
    """Build and return the pyparsing grammar for where strings.

    Every numeric literal is stored as ``float``, since
    ``UnresolvedComparisonNode.value`` is declared ``float``. Both quote
    characters are accepted because YAML already owns one of them: a where
    lives inside a YAML scalar, so ``where: "generator == 'wind'"`` is the
    spelling that needs no escaping, and the double-quoted form is there for
    the file that quoted the other way round. ``NOT`` binds tightest, then
    ``AND``, then ``OR``.
    """
    where_expr = pp.Forward()

    true_lit = pp.CaselessKeyword('True').set_parse_action(lambda: BooleanLiteralNode(True))
    false_lit = pp.CaselessKeyword('False').set_parse_action(lambda: BooleanLiteralNode(False))

    # pyrefly: ignore[implicit-any-lambda]
    real = pp.Regex(r'-?\d+\.\d*([eE][+-]?\d+)?').set_parse_action(lambda t: float(t[0]))
    # pyrefly: ignore[implicit-any-lambda]
    integer = pp.Regex(r'-?\d+').set_parse_action(lambda t: float(t[0]))
    number = real | integer

    name = pp.Regex(r'[a-zA-Z_][a-zA-Z0-9_]*')

    quoted = (pp.QuotedString("'", esc_char='\\') | pp.QuotedString('"', esc_char='\\')).set_parse_action(
        lambda t: _Quoted(t[0])
    )

    grouped_by = pp.Suppress(',') + pp.Suppress(pp.Keyword('by')) + pp.Suppress('=') + name
    index_call = (
        pp.Suppress(pp.Keyword('index'))
        + pp.Suppress('(')
        + name
        + pp.Suppress(',')
        + integer
        + pp.Optional(grouped_by)
        + pp.Suppress(')')
    ).set_parse_action(_position)

    comparator = pp.one_of('<= >= == != < >')
    comparison = (name + comparator + (index_call | number | quoted | name)).set_parse_action(
        # pyrefly: ignore[implicit-any-lambda]
        lambda t: _comparison(t[0], t[1], t[2])
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


def parse_where(text: str) -> WhereNode:
    """Parse a where string into an AST.

    With ``parse_all`` and a single top-level alternative, element 0 of the
    parse result is the root node.
    """
    try:
        result = _WHERE_GRAMMAR.parse_string(text, parse_all=True)
    except pp.ParseException as e:
        msg = f'Failed to parse where string: {text!r}\n{e}'
        raise SchemaError(msg) from e
    return cast('WhereNode', result[0])
