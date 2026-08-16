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

    comparator = pp.one_of('<= >= == != < >')
    comparison = (name + comparator + (number | quoted | name)).set_parse_action(
        # pyrefly: ignore[implicit-any-lambda]
        lambda t: UnresolvedComparisonNode(t[0], t[1], _bare(t[2]), quoted=isinstance(t[2], _Quoted))
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
