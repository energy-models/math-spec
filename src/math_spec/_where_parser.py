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

from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING, cast, get_args

import pyparsing as pp

from math_spec._expression_parser import ARITHMETIC, NAME, ArithmeticNode, children, parse_text
from math_spec._sealed import Sealed
from math_spec.errors import SchemaError
from math_spec.program import (
    And,
    BooleanLiteral,
    Connective,
    Not,
    Or,
    Predicate,
    PredicateOperator,
    where_children,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

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
class UnresolvedPredicateCallNode:
    """``<name>(<predicate>[, <kwarg>…])`` — an operator reading a predicate rather than arithmetic.

    The expression grammar cannot carry this shape: its call rule takes
    arithmetic arguments, and a predicate is not arithmetic. So the where
    grammar reads it, and resolution decides which operator the name is and
    what the kwargs mean. ``kwargs`` is held and hashed as
    :class:`~math_spec._expression_parser.FunctionCallNode` holds its own.
    """

    name: str
    operand: Predicate | UnresolvedWhereNode
    kwargs: Mapping[str, ArithmeticNode] = field(default_factory=dict, hash=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'kwargs', Sealed(self.kwargs))


@dataclass(frozen=True)
class UnresolvedCountNode:
    """``count(<predicate>, over=<dim>) <op> <number>`` — a count against a literal.

    Its own node rather than an :class:`UnresolvedComparisonNode` with a call
    on the left: every other comparison has arithmetic on both sides, and
    widening that one to carry a predicate would widen every reader of a side
    with it.
    """

    call: UnresolvedPredicateCallNode
    op: PredicateOperator
    value: ArithmeticNode


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


#: What resolution rewrites away on the where side — the nodes whose leaves
#: are still names the schema has not been asked about.
UnresolvedWhereNode = UnresolvedNameNode | UnresolvedComparisonNode | UnresolvedPredicateCallNode | UnresolvedCountNode

#: Every node a parsed where string is built of: the connectives and literals,
#: the unresolved leaves, and the arithmetic and the two side nodes under a
#: comparison. What the depth measurement walks.
_ParsedWhere = Predicate | UnresolvedWhereNode | ArithmeticNode | ColumnNode | QuotedNode


# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------


def _predicate_call(tokens: pp.ParseResults) -> UnresolvedPredicateCallNode:
    """The call node, with a keyword given twice refused as the arithmetic grammar refuses it."""
    name, operand, *pairs = tokens
    kwargs: dict[str, ArithmeticNode] = {}
    for key, value in pairs:
        if key in kwargs:
            msg = f'{name}({key}=) is given twice. A keyword names one value; drop one of them.'
            raise SchemaError(msg)
        kwargs[key] = value
    return UnresolvedPredicateCallNode(name, operand, kwargs)


def _build_where_grammar() -> pp.ParserElement:
    """Build the pyparsing grammar for where strings.

    Both quote characters are accepted because YAML already owns one of them.
    ``NOT`` binds tightest, then ``AND``, then ``OR``. A comparison is tried
    before a bare name, since its left side begins with one.
    """
    where_expr = pp.Forward()

    true_lit = pp.CaselessKeyword('True').set_parse_action(lambda: BooleanLiteral(True))
    false_lit = pp.CaselessKeyword('False').set_parse_action(lambda: BooleanLiteral(False))

    name = pp.Regex(NAME)
    # pyrefly: ignore[implicit-any-lambda]
    column = pp.Regex(rf'({NAME})\.({NAME})').set_parse_action(lambda t: ColumnNode(*t[0].split('.')))
    quoted = (pp.QuotedString("'", esc_char='\\') | pp.QuotedString('"', esc_char='\\')).set_parse_action(
        # pyrefly: ignore[implicit-any-lambda]
        lambda t: QuotedNode(t[0])
    )
    comparator = pp.one_of(list(get_args(PredicateOperator)))

    kwarg = (name + pp.Suppress('=') + (quoted | ARITHMETIC)).set_parse_action(lambda t: (t[0], t[1]))

    def _call(head: pp.ParserElement) -> pp.ParserElement:
        """``<head>(<predicate>[, <kwarg>…])`` — the one shape whose operand is a predicate.

        ``count`` is spelled in the grammar rather than left to resolution, as
        ``position`` is, because only the grammar can decide to read its
        argument as a predicate. Every other predicate-taking call stands where
        arithmetic cannot, so the comparison above it has already been tried
        and the name is free.
        """
        return (
            head + pp.Suppress('(') + where_expr + pp.ZeroOrMore(pp.Suppress(',') + kwarg) + pp.Suppress(')')
        ).set_parse_action(_predicate_call)

    count_call = _call(pp.CaselessKeyword('count'))
    predicate_call = _call(name.copy())

    count_comparison = (count_call + comparator + ARITHMETIC).set_parse_action(
        # pyrefly: ignore[implicit-any-lambda]
        lambda t: UnresolvedCountNode(t[0], t[1], t[2])
    )
    comparison = (
        (column | ARITHMETIC) + comparator + (quoted | column | ARITHMETIC)
        # pyrefly: ignore[implicit-any-lambda]
    ).set_parse_action(lambda t: UnresolvedComparisonNode(t[0], t[1], t[2]))
    # pyrefly: ignore[implicit-any-lambda]
    existence = name.copy().set_parse_action(lambda t: UnresolvedNameNode(t[0]))

    atom = (
        true_lit
        | false_lit
        | count_comparison
        | comparison
        | predicate_call
        | existence
        | (pp.Suppress('(') + where_expr + pp.Suppress(')'))
    )

    NOT = pp.CaselessKeyword('NOT').suppress()
    # pyrefly: ignore[implicit-any-lambda]
    not_expr = (NOT + atom).set_parse_action(lambda t: Not(t[0])) | atom

    AND = pp.CaselessKeyword('AND').suppress()
    and_expr = not_expr + pp.ZeroOrMore(AND + not_expr)
    and_expr.set_parse_action(_folder(And))

    OR = pp.CaselessKeyword('OR').suppress()
    or_expr = and_expr + pp.ZeroOrMore(OR + and_expr)
    or_expr.set_parse_action(_folder(Or))

    where_expr <<= or_expr
    return where_expr


def _folder(node_type: type[And] | type[Or]) -> Callable[[pp.ParseResults], Predicate | UnresolvedWhereNode]:
    """A parse action left-folding a flat operator chain into *node_type*."""

    def fold(tokens: pp.ParseResults) -> Predicate | UnresolvedWhereNode:
        items: list[Predicate | UnresolvedWhereNode] = list(tokens)
        result = items[0]
        for item in items[1:]:
            result = node_type(cast('Predicate', result), cast('Predicate', item))
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
    """What a where string nests through: a connective's operands, a comparison's sides, and a call's predicate."""
    if isinstance(node, UnresolvedCountNode):
        return (node.call, node.value)
    if isinstance(node, UnresolvedPredicateCallNode):
        return (node.operand, *node.kwargs.values())
    if isinstance(node, UnresolvedComparisonNode):
        return (node.left, node.right)
    if isinstance(node, ArithmeticNode):
        return children(node)
    if isinstance(node, Connective):
        return where_children(node)
    return ()


@lru_cache(maxsize=4096)
def parse_where(text: str) -> Predicate | UnresolvedWhereNode:
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
        'Predicate | UnresolvedWhereNode',
        parse_text(_WHERE_GRAMMAR, text, 'where string', _named_rewrite, _nested, _DEEP_REWRITE),
    )
