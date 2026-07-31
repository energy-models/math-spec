"""pyparsing-based parser for where strings — grammar and AST only.

Parses strings like ``"p_max > 0 AND NOT is_must_run"`` into an AST. What a
mask *means* is each backend's business: the eager lane evaluates the AST
against an xr.Dataset (``builder.evaluate_where``), the relational lane
lowers it to SQL predicates (``lowering._lower_where``).

Kept dependency-free on purpose — ``validation.py`` and ``lowering.py`` are
linopy-free by hard rule 3, and they import this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, cast

import pyparsing as pp

from lpspec.errors import SchemaError

if TYPE_CHECKING:
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
    value: float | str


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


# NOTE: NotNode / AndNode / OrNode reference `WhereNode` in their annotations
# before this line — that works only because `from __future__ import
# annotations` makes annotations strings. Don't remove that future-import
# unless you also reorder these definitions.
WhereNode = (
    BooleanLiteralNode
    | UnresolvedNameNode
    | UnresolvedComparisonNode
    | ParameterDefinedNode
    | VariableDefinedNode
    | ParameterComparisonNode
    | DimensionComparisonNode
    | NotNode
    | AndNode
    | OrNode
)


# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------


def _build_where_grammar() -> pp.ParserElement:
    """Build and return the pyparsing grammar for where strings."""
    where_expr = pp.Forward()

    true_lit = pp.CaselessKeyword('True').set_parse_action(lambda: BooleanLiteralNode(True))
    false_lit = pp.CaselessKeyword('False').set_parse_action(lambda: BooleanLiteralNode(False))

    real = pp.Regex(r'-?\d+\.\d*([eE][+-]?\d+)?').set_parse_action(lambda t: float(t[0]))
    # float, not int: UnresolvedComparisonNode.value is declared float, so store one
    integer = pp.Regex(r'-?\d+').set_parse_action(lambda t: float(t[0]))
    number = real | integer

    name = pp.Regex(r'[a-zA-Z_][a-zA-Z0-9_]*')

    comparator = pp.one_of('<= >= == != < >')
    comparison = (name + comparator + (number | name)).set_parse_action(
        lambda t: UnresolvedComparisonNode(t[0], t[1], t[2])
    )
    # a bare name is an existence check
    existence = name.copy().set_parse_action(lambda t: UnresolvedNameNode(t[0]))

    atom = true_lit | false_lit | comparison | existence | (pp.Suppress('(') + where_expr + pp.Suppress(')'))

    # NOT binds tightest, then AND, then OR
    NOT = pp.CaselessKeyword('NOT').suppress()
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
    """Parse a where string into an AST."""
    try:
        result = _WHERE_GRAMMAR.parse_string(text, parse_all=True)
    except pp.ParseException as e:
        msg = f'Failed to parse where string: {text!r}\n{e}'
        raise SchemaError(msg) from e
    # parseAll with a single top-level alternative: element 0 is the root node
    return cast('WhereNode', result[0])
