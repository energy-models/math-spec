# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The syntax tree the expression grammar builds, and the grammar — package-private.

Only expansion and resolution read it: resolution rewrites it into the
:mod:`math_spec.program` vocabulary, which every pass after reads. Arithmetic
nests anywhere; a comparison appears only at the top of a parsed expression.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING, Literal, assert_never, cast, get_args

import pyparsing as pp

from math_spec._sealed import Sealed
from math_spec.errors import SchemaError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping

#: The relation a comparison may carry — the three an expression may be
#: written with, which is what a constraint's sense is read off.
ComparisonOperator = Literal['<=', '>=', '==']

#: The sign a unary operator applies to its operand.
UnaryOperator = Literal['+', '-']

#: The arithmetic a binary operator may spell. Closed by the grammar, and the
#: vocabulary a renderer dispatching on :attr:`BinaryOperatorNode.op`
#: switches over — it keeps no list of its own.
BinaryOperator = Literal['+', '-', '*', '/', '**']

#: What an expression writes to refer to a declaration, and so what a
#: declaration may be named.
NAME = r'[a-zA-Z_][a-zA-Z0-9_]*'

#: A float — a fractional part or an exponent. A sign is the unary operator's.
REAL = r'\d+\.\d*([eE][+-]?\d+)?|\d+[eE][+-]?\d+'

# ---------------------------------------------------------------------------
# AST nodes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NumberNode:
    value: float

    def __str__(self) -> str:
        """A whole number without its fraction, which is how a file writes one and how it parses back."""
        return str(int(self.value)) if self.value.is_integer() else str(self.value)


@dataclass(frozen=True)
class NameNode:
    """A bare name whose kind only the schema knows; resolution rewrites every one into a program node."""

    name: str

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class NameListNode:
    """A bracketed list of names in a kwarg value — ``sum(x, by=[a, b])``.

    Unresolved: which kind of name the kwarg admits is the operator's business.
    """

    names: tuple[str, ...]

    def __str__(self) -> str:
        return shown(self.names)


@dataclass(frozen=True)
class ColumnsNode:
    """Columns of one relation in a kwarg value — ``sum(x, over=g, by=gen_bus[bus])``.

    The relation is written once and its columns after it, so one call cannot
    name columns of two tables. Unresolved: which columns the kwarg admits is
    the operator's business.
    """

    relation: str
    columns: tuple[str, ...]

    def __str__(self) -> str:
        return f'{self.relation}[{", ".join(self.columns)}]'


@dataclass(frozen=True)
class KeywordNode:
    """A quoted closed keyword in a kwarg value — ``shift(..., edge='wrap')``.

    Unresolved: which keywords the kwarg accepts is the operator's business.
    """

    value: str

    def __str__(self) -> str:
        return f"'{self.value}'"


@dataclass(frozen=True)
class UnaryOperatorNode:
    op: UnaryOperator
    operand: ArithmeticNode

    def __str__(self) -> str:
        return f'{self.op}{operand(self.operand)}'


@dataclass(frozen=True)
class BinaryOperatorNode:
    op: BinaryOperator
    left: ArithmeticNode
    right: ArithmeticNode

    def __str__(self) -> str:
        return f'{operand(self.left)} {self.op} {operand(self.right)}'


@dataclass(frozen=True)
class FunctionCallNode:
    """An operator or macro call.

    ``kwargs`` is held behind a read-only view and excluded from the hash;
    equal nodes still hash equal on ``name`` and ``args``.
    """

    name: str
    args: tuple[ArithmeticNode, ...] = ()
    kwargs: Mapping[str, ArithmeticNode] = field(default_factory=dict, hash=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'kwargs', Sealed(self.kwargs))

    def __str__(self) -> str:
        passed = [*(str(arg) for arg in self.args), *(f'{key}={value}' for key, value in self.kwargs.items())]
        return f'{self.name}({", ".join(passed)})'


#: Every arithmetic node the grammar builds. A name, a name list, a column
#: selection and a quoted keyword are what resolution reads for their kind; the
#: rest is structure.
ArithmeticNode = (
    NumberNode
    | NameNode
    | NameListNode
    | ColumnsNode
    | KeywordNode
    | UnaryOperatorNode
    | BinaryOperatorNode
    | FunctionCallNode
)


@dataclass(frozen=True)
class ComparisonNode:
    op: ComparisonOperator
    left: ArithmeticNode
    right: ArithmeticNode

    def __str__(self) -> str:
        """Both sides bare: a comparison is not an :data:`ArithmeticNode`, so nothing can take one as an operand."""
        return f'{self.left} {self.op} {self.right}'


#: A whole parsed expression: arithmetic, or one comparison over it.
ParsedNode = ArithmeticNode | ComparisonNode


def shown(names: tuple[str, ...]) -> str:
    """Names as a kwarg value is written: bare when one, bracketed when several."""
    return names[0] if len(names) == 1 else f'[{", ".join(names)}]'


def operand(node: ArithmeticNode) -> str:
    """One operand of an operator, bracketed where reading the text back would regroup the tree.

    Whoever writes a node into a larger text — an operator, a line of a dumped
    sum — asks this rather than restating when brackets are needed.

    A leaf and a call are self-delimiting, and an operator node is not. The brackets go on every operator operand rather than only the
    ones precedence would regroup, because a node prints without knowing its
    parent: ``a + (b * c)`` keeps the tree where ``a + b * c`` would rely on the
    reader knowing which binds tighter.
    """
    return f'({node})' if isinstance(node, (UnaryOperatorNode, BinaryOperatorNode)) else str(node)


def children(node: ParsedNode) -> tuple[ArithmeticNode, ...]:
    """The sub-expressions of *node* — the structural half of any walk.

    An operator's kwargs are children too — a dimension or coordinate is an
    ordinary node in a kwarg value, which is what lets a macro bind a formal.
    """
    if isinstance(node, UnaryOperatorNode):
        return (node.operand,)
    if isinstance(node, (BinaryOperatorNode, ComparisonNode)):
        return (node.left, node.right)
    if isinstance(node, FunctionCallNode):
        return (*node.args, *node.kwargs.values())
    return ()


def nodes(*roots: ParsedNode) -> Iterator[ParsedNode]:
    """Every node under *roots*, each root itself included, parents first.

    The traversal a question about a tree is a filter of, the way
    :func:`math_spec.program.walk` is for a program.
    """
    for root in roots:
        yield root
        yield from nodes(*children(root))


def with_children(node: ArithmeticNode, recurse: Callable[[ArithmeticNode], ArithmeticNode]) -> ArithmeticNode:
    """*node* rebuilt with *recurse* applied to each of its :func:`children`; a leaf comes back as is."""
    if isinstance(node, NumberNode | NameNode | NameListNode | ColumnsNode | KeywordNode):
        return node
    if isinstance(node, UnaryOperatorNode):
        return UnaryOperatorNode(node.op, recurse(node.operand))
    if isinstance(node, BinaryOperatorNode):
        return BinaryOperatorNode(node.op, recurse(node.left), recurse(node.right))
    if isinstance(node, FunctionCallNode):
        return FunctionCallNode(
            node.name,
            tuple(recurse(a) for a in node.args),
            {k: recurse(v) for k, v in node.kwargs.items()},
        )
    assert_never(node)


# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------


def _build_grammar() -> tuple[pp.ParserElement, pp.ParserElement, pp.ParserElement]:
    """The arithmetic grammar, the expression grammar that puts one comparison over it, and a column selection.

    ``inf`` is a ``pp.Keyword`` rather than a ``pp.Literal``, which would
    match the prefix of ``inflow``.
    """
    arith = pp.Forward()

    inf_literal = (pp.Keyword('.inf') | pp.Keyword('inf')).set_parse_action(lambda: NumberNode(float('inf')))
    # pyrefly: ignore[implicit-any-lambda]
    number = inf_literal | pp.Regex(rf'{REAL}|\d+').set_parse_action(lambda t: NumberNode(float(t[0])))

    name = pp.Regex(NAME)

    quoted = (pp.QuotedString("'") | pp.QuotedString('"')).set_parse_action(lambda t: KeywordNode(str(t[0])))
    name_list = (pp.Suppress('[') + pp.DelimitedList(name) + pp.Suppress(']')).set_parse_action(
        lambda t: NameListNode(tuple(str(x) for x in t))
    )
    columns = (name + pp.Suppress('[') + pp.DelimitedList(name) + pp.Suppress(']')).set_parse_action(
        lambda t: ColumnsNode(str(t[0]), tuple(str(x) for x in t[1:]))
    )
    kwarg = (name + pp.Suppress('=') + (quoted | columns | name_list | arith)).set_parse_action(lambda t: (t[0], t[1]))
    pos_arg = arith
    arg_list = pp.Optional(pp.DelimitedList(kwarg | pos_arg))
    func_call = (name + pp.Suppress('(') + arg_list + pp.Suppress(')')).set_parse_action(_make_func_call)

    # pyrefly: ignore[implicit-any-lambda]
    name_node = name.copy().set_parse_action(lambda t: NameNode(t[0]))
    atom = func_call | number | name_node | (pp.Suppress('(') + arith + pp.Suppress(')'))

    unary = pp.Forward()
    power = (atom + pp.Optional(pp.Literal('**') + unary)).set_parse_action(_make_power)
    # pyrefly: ignore[implicit-any-lambda]
    unary <<= (pp.one_of('+ -') + unary).set_parse_action(lambda t: UnaryOperatorNode(t[0], t[1])) | power

    mul_div = unary + pp.ZeroOrMore(pp.one_of('* /') + unary)
    mul_div.set_parse_action(_make_left_assoc)

    add_sub = mul_div + pp.ZeroOrMore(pp.one_of('+ -') + mul_div)
    add_sub.set_parse_action(_make_left_assoc)

    arith <<= add_sub

    comparator = pp.one_of(list(get_args(ComparisonOperator)))
    expression = (arith + pp.Optional(comparator + arith)).set_parse_action(
        lambda t: ComparisonNode(t[1], t[0], t[2]) if len(t) == 3 else t[0]
    )
    return arith, expression, columns


def _make_func_call(tokens: pp.ParseResults) -> FunctionCallNode:
    """The callee is cast: a ParseResults element is untyped, and the grammar guarantees an identifier in position 0."""
    name = cast('str', tokens[0])
    args: list[ArithmeticNode] = []
    pairs: list[tuple[str, ArithmeticNode]] = []
    for item in tokens[1:]:
        (pairs if isinstance(item, tuple) and len(item) == 2 else args).append(item)
    return FunctionCallNode(name=name, args=tuple(args), kwargs=keywords(name, pairs))


def keywords[V](name: str, pairs: Iterable[tuple[str, V]]) -> dict[str, V]:
    """A call's keywords, in the order written; a keyword given twice is refused, in both grammars."""
    kwargs: dict[str, V] = {}
    for key, value in pairs:
        if key in kwargs:
            msg = f'{name}({key}=) is given twice. A keyword names one value; drop one of them.'
            raise SchemaError(msg)
        kwargs[key] = value
    return kwargs


def _make_left_assoc(tokens: pp.ParseResults) -> ArithmeticNode:
    result: ArithmeticNode
    result, *rest = tokens
    for op, right in zip(rest[::2], rest[1::2], strict=True):
        result = BinaryOperatorNode(op, result, right)
    return result


def _make_power(tokens: pp.ParseResults) -> ArithmeticNode:
    """A base and at most one exponent — right-associative, since the exponent is itself a ``unary``."""
    items: list[ArithmeticNode] = list(tokens)
    return items[0] if len(items) == 1 else BinaryOperatorNode('**', items[0], items[2])


#: The arithmetic half on its own, for the where grammar to put a predicate's
#: comparator over: one grammar for what a side may say, wherever it stands.
#: The column selection is shared too, so a kwarg reads one the same way in
#: both grammars.
ARITHMETIC, _GRAMMAR, COLUMNS = _build_grammar()


#: How deep a tree the language admits. Every pass over an expression recurses,
#: so a deeper one exhausts the interpreter's stack instead of failing as a
#: ``LanguageError``; the whole pipeline survives 300 on a default stack (#359).
MAX_DEPTH = 100


def depth[T](node: T, child_of: Callable[[T], tuple[T, ...]]) -> int:
    """How many nodes deep *node* is, walked with an explicit stack.

    Iterative deliberately: this measurement is what refuses a tree too deep to
    recurse over, so recursing to take it would be the crash it prevents.
    """
    deepest, pending = 0, [(node, 1)]
    while pending:
        current, reached = pending.pop()
        deepest = max(deepest, reached)
        pending.extend((child, reached + 1) for child in child_of(current))
    return deepest


def _too_deep(what: str, text: str, found: int | None, rewrite: str) -> str:
    """The refusal both grammars raise, so the two say the same thing about the same limit.

    *found* is ``None`` where the parser ran out of stack before a tree existed
    to measure.
    """
    shown = text if len(text) <= 60 else f'{text[:60]}…'
    measured = f'nests {found} deep' if found is not None else 'nests deeper'
    return f'The {what} {measured}, past the {MAX_DEPTH} levels the language admits: {shown!r}\n{rewrite}'


def parse_text[T](
    grammar: pp.ParserElement,
    text: str,
    what: str,
    rewrite: Callable[[str, int], str | None],
    child_of: Callable[[T], tuple[T, ...]],
    deep_rewrite: str,
) -> T:
    """Parse the whole of *text* with *grammar*, or raise :class:`SchemaError` naming *what* failed to parse.

    *rewrite* is asked for the predictable mistake at the failure position; its
    sentence, if any, precedes the grammar's own complaint. A tree nesting past
    :data:`MAX_DEPTH`, measured through *child_of*, is refused with
    *deep_rewrite* — and so is one the parser itself ran out of stack on. The
    node comes back as the type *child_of* walks, which is the grammar's word
    for what it builds.
    """
    try:
        result = grammar.parse_string(text, parse_all=True)
    except pp.ParseException as e:
        hint = rewrite(text, e.loc)
        msg = f'Failed to parse {what}: {text!r}\n{f"{hint}\n" if hint is not None else ""}{e}'
        raise SchemaError(msg) from e
    except RecursionError:
        raise SchemaError(_too_deep(what, text, None, deep_rewrite)) from None
    node = cast('T', result[0])
    found = depth(node, child_of)
    if found > MAX_DEPTH:
        raise SchemaError(_too_deep(what, text, found, deep_rewrite))
    return node


def _named_rewrite(text: str, loc: int) -> str | None:
    """The rewrite for a predictable mistake at the token where the grammar gave up, or ``None``.

    A two-character token is tested before its one-character prefix.
    """
    rest = text[loc:].lstrip()
    if rest.startswith(get_args(ComparisonOperator)):
        return (
            f"'{rest[:2]}' follows a complete comparison, and an expression carries "
            f'one comparison, at the top. Split the chain into two constraints.'
        )
    if rest.startswith('!='):
        return (
            "'!=' is not a constraint sense — the senses are <=, >= and ==. "
            'Holding rows apart is a where matter: write the test in where:, where != is legal.'
        )
    if rest.startswith(('<', '>')):
        return f"'{rest[0]}' is not a constraint sense — the senses are <=, >= and ==. Write the bound inclusive."
    if rest.startswith('='):
        return (
            "'=' on its own is how a kwarg is written inside a call, like sum(x, over=d). "
            'Equality between two sides is written ==.'
        )
    if rest.startswith('^'):
        return "power is written '**', not '^'."
    return None


#: The rewrite an over-deep expression is given. Writing the terms out is
#: what ``sum`` exists to replace, so the refusal points at the language's own
#: answer before it offers the general one.
_DEEP_REWRITE = (
    'Reduce over a dimension with sum() rather than writing the terms out, or name an intermediate '
    'quantity under expressions: and refer to it by name.'
)


@lru_cache(maxsize=4096)
def parse_expression(text: str) -> ParsedNode:
    """Parse a math expression string into an AST.

    Raises:
        SchemaError: If *text* is not an expression of the language. A
            predictable mistake — a strict or chained comparison, ``!=``, a
            lone ``=``, ``^`` for power — is named with its rewrite before the
            grammar's own complaint.
    """
    return parse_text(_GRAMMAR, text, 'expression', _named_rewrite, children, _DEEP_REWRITE)


def names_in(value: ArithmeticNode) -> tuple[str, ...]:
    """The names a relation kwarg carries: one bare, several bracketed, none otherwise."""
    if isinstance(value, NameNode):
        return (value.name,)
    return value.names if isinstance(value, NameListNode) else ()


def literal_number(value: ArithmeticNode) -> NumberNode | None:
    """The number a literal names, its sign folded in — ``None`` where *value* is not one."""
    if isinstance(value, NumberNode):
        return value
    if isinstance(value, UnaryOperatorNode) and isinstance(value.operand, NumberNode):
        return NumberNode(-value.operand.value if value.op == '-' else value.operand.value)
    return None
