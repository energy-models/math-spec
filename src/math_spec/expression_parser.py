"""pyparsing-based expression parser for math expressions.

Parses strings like ``sum(p * cost, over=generator) == load`` into an AST
that can be evaluated against a namespace of linopy variables and xarray
parameters.

``ArithmeticNode`` is the arithmetic-only union: every nested expression
position (operands, args, kwargs) accepts it and nothing else, and
``ComparisonNode`` appears only at the top of a parsed expression. The node
dataclasses reference the union in their annotations before it is defined,
which works only because ``from __future__ import annotations`` makes
annotations strings — removing that future-import requires reordering the
definitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, cast

import pyparsing as pp

from lpspec.errors import SchemaError

ComparisonOperator = Literal['<=', '>=', '==']

# ---------------------------------------------------------------------------
# AST nodes
# ---------------------------------------------------------------------------


@dataclass
class NumberNode:
    value: float


@dataclass
class NameNode:
    """An unresolved token — a name whose *kind* is not yet known.

    The parser cannot know whether ``p`` is a variable, a parameter or a
    dimension; only the schema knows. ``resolution.py`` rewrites every one of
    these into one of the typed nodes below, so a NameNode never reaches a
    backend. If you find one there, resolution was skipped.
    """

    name: str


@dataclass
class VariableNode:
    """A resolved reference to a declared decision variable."""

    name: str


@dataclass
class ParameterNode:
    """A resolved reference to a declared parameter."""

    name: str


@dataclass
class DimensionNode:
    """A resolved reference to a declared dimension.

    Only legal in operator kwarg *values* (``sum(x, over=generator)``), never as
    a value in arithmetic — a dimension is a coordinate space, not data.
    """

    name: str


@dataclass
class NameListNode:
    """A bracketed list of names in a kwarg value — ``sum(x, by=[a, b])``.

    Unresolved on purpose, and unresolvable here: which kind of name a kwarg
    admits is the operator's business. Like :class:`NameNode` this never
    reaches a backend — ``resolution.py`` rewrites it into the one typed node
    its kwarg wants, so a pass that meets one ran before resolution.
    """

    names: tuple[str, ...]

    @property
    def shown(self) -> str:
        """The kwarg value as the author wrote it, for an error message."""
        return f'[{", ".join(self.names)}]'


@dataclass
class LookupNode:
    """A resolved reference to one or more declared lookups.

    Only legal in operator kwarg *values* (``sum(x, by=to)``). Like
    :class:`DimensionNode` this names structure, not data. The lookups carry
    their own dimensions: ``dimension`` is the one they are all over — what
    ``sum`` consumes and ``at`` produces — and ``into`` the ones their values
    are labels of, one per name and in the order written, all copied off the
    declarations once here so no backend has to re-derive them.

    Plural because grouping through several lookups at once is one grouping,
    not a composition of two: ``sum(x, by=[gen_bus, gen_tech])`` consumes
    ``generator`` once and produces both targets. The one-name case is the
    same node with one-element tuples, so no consumer branches on arity.
    """

    names: tuple[str, ...]
    dimension: str
    into: tuple[str, ...]

    @property
    def shown(self) -> str:
        """The kwarg value as the author wrote it, for an error message."""
        return self.names[0] if len(self.names) == 1 else f'[{", ".join(self.names)}]'


@dataclass
class KeywordNode:
    """A quoted closed keyword in a kwarg value — ``shift(..., edge='wrap')``.

    Unresolved on purpose: which keywords a kwarg accepts is the operator's
    business, so this only records *that* the author wrote a literal rather
    than a name. ``resolution.py`` turns it into the typed node the kwarg
    wants, or reports it as not one of that kwarg's keywords.
    """

    value: str


@dataclass
class EdgeNode:
    """A resolved edge policy for ``shift(x, over=d, offset=n, edge='wrap')``.

    Only legal as the value of ``shift``'s ``edge=`` kwarg. Like
    :class:`DimensionNode` and :class:`LookupNode` this names neither data
    nor a coordinate — it is a closed keyword, and the only one the language
    has. A *number* in the same position stays an ordinary
    :class:`NumberNode`, the value the vacated positions contribute, so one
    kwarg carries all three edge policies and no second kwarg can contradict
    it.
    """

    policy: str


@dataclass
class UnaryOperatorNode:
    op: str
    operand: ArithmeticNode


@dataclass
class BinaryOperatorNode:
    op: str
    left: ArithmeticNode
    right: ArithmeticNode


@dataclass
class FunctionCallNode:
    name: str
    args: list[ArithmeticNode] = field(default_factory=list)
    kwargs: dict[str, ArithmeticNode] = field(default_factory=dict)


ArithmeticNode = (
    NumberNode
    | NameNode
    | NameListNode
    | VariableNode
    | ParameterNode
    | DimensionNode
    | LookupNode
    | EdgeNode
    | KeywordNode
    | UnaryOperatorNode
    | BinaryOperatorNode
    | FunctionCallNode
)


@dataclass
class ComparisonNode:
    op: ComparisonOperator
    left: ArithmeticNode
    right: ArithmeticNode


ExpressionNode = ArithmeticNode | ComparisonNode


def children(node: ExpressionNode) -> tuple[ArithmeticNode, ...]:
    """The sub-expressions of *node* — the structural half of any walk.

    Every pass that recurses the whole tree and acts only at certain leaves
    goes through here, so a node added later reaches all of them. A pass whose
    *answer* differs per node type dispatches itself and keeps its
    ``assert_never``; this is for the ones that only need to get everywhere.

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


# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------


def _build_grammar() -> pp.ParserElement:
    """Build and return the pyparsing grammar for math expressions.

    Every numeric literal is stored as ``float``, since ``NumberNode.value``
    is declared ``float``. ``inf`` is a ``pp.Keyword``, not a ``pp.Literal``:
    a ``Literal`` matches a prefix, so it would eat the first three characters
    of ``inflow`` and leave the parser meeting ``low`` where it expects the
    end of the expression.

    A quoted value is a **closed keyword**, never a model name — the same
    rule a ``where`` uses, where quoting says "literal, not something to
    resolve" — and the grammar admits it only in a kwarg value: a string has
    no meaning in arithmetic, so allowing it there would only create an error
    to report later. A bracketed list of names is admitted in the same
    position and for the same reason. A comparison appears at most once, and
    only at the top.
    """
    arith = pp.Forward()

    # pyrefly: ignore[implicit-any-lambda]
    integer = pp.Regex(r'-?\d+').set_parse_action(lambda t: NumberNode(float(t[0])))
    # pyrefly: ignore[implicit-any-lambda]
    real = pp.Regex(r'-?\d+\.\d*([eE][+-]?\d+)?').set_parse_action(lambda t: NumberNode(float(t[0])))
    inf_literal = (pp.Keyword('.inf') | pp.Keyword('inf')).set_parse_action(lambda: NumberNode(float('inf')))
    number = real | inf_literal | integer

    name = pp.Regex(r'[a-zA-Z_][a-zA-Z0-9_]*')

    quoted = (pp.QuotedString("'") | pp.QuotedString('"')).set_parse_action(lambda t: KeywordNode(str(t[0])))
    name_list = (pp.Suppress('[') + pp.DelimitedList(name) + pp.Suppress(']')).set_parse_action(
        lambda t: NameListNode(tuple(str(x) for x in t))
    )
    kwarg = (name + pp.Suppress('=') + (quoted | name_list | arith | name)).set_parse_action(lambda t: (t[0], t[1]))
    pos_arg = arith
    arg_list = pp.Optional(pp.DelimitedList(kwarg | pos_arg))
    func_call = (name + pp.Suppress('(') + arg_list + pp.Suppress(')')).set_parse_action(_make_func_call)

    # pyrefly: ignore[implicit-any-lambda]
    name_node = name.copy().set_parse_action(lambda t: NameNode(t[0]))
    atom = func_call | number | name_node | (pp.Suppress('(') + arith + pp.Suppress(')'))

    # pyrefly: ignore[implicit-any-lambda]
    unary = (pp.one_of('+ -') + atom).set_parse_action(lambda t: UnaryOperatorNode(t[0], t[1])) | atom

    power = unary + pp.ZeroOrMore(pp.Literal('**') + unary)
    power.set_parse_action(_make_right_assoc)

    mul_div = power + pp.ZeroOrMore(pp.one_of('* /') + power)
    mul_div.set_parse_action(_make_left_assoc)

    add_sub = mul_div + pp.ZeroOrMore(pp.one_of('+ -') + mul_div)
    add_sub.set_parse_action(_make_left_assoc)

    arith <<= add_sub

    comparator = pp.one_of('<= >= ==')
    # pyrefly: ignore[implicit-any-lambda]
    expr = (arith + comparator + arith).set_parse_action(lambda t: ComparisonNode(t[1], t[0], t[2])) | arith

    return expr


def _make_func_call(tokens: pp.ParseResults) -> FunctionCallNode:
    """Build a FunctionCallNode from parsed tokens.

    A ParseResults element is untyped, so the callee is cast; the grammar
    guarantees an identifier in position 0.
    """
    name = cast('str', tokens[0])
    args = []
    kwargs = {}
    for item in tokens[1:]:
        if isinstance(item, tuple) and len(item) == 2:
            k, v = item
            if isinstance(v, str):
                v = NameNode(v) if not v.replace('.', '').isdigit() else NumberNode(float(v))
            kwargs[k] = v
        else:
            args.append(item)
    return FunctionCallNode(name=name, args=args, kwargs=kwargs)


def _make_left_assoc(tokens: pp.ParseResults) -> Any:
    """Fold tokens into left-associative BinaryOperatorNode chain."""
    items = list(tokens)
    result = items[0]
    i = 1
    while i < len(items):
        op = items[i]
        right = items[i + 1]
        result = BinaryOperatorNode(op, result, right)
        i += 2
    return result


def _make_right_assoc(tokens: pp.ParseResults) -> Any:
    """Fold tokens into right-associative BinaryOperatorNode chain (for **).

    Right-associative: ``a ** b ** c`` is ``a ** (b ** c)``.
    """
    items = list(tokens)
    if len(items) == 1:
        return items[0]
    result = items[-1]
    i = len(items) - 3
    while i >= 0:
        op = items[i + 1]
        left = items[i]
        result = BinaryOperatorNode(op, left, result)
        i -= 2
    return result


_GRAMMAR = _build_grammar()


def parse_expression(text: str) -> ExpressionNode:
    """Parse a math expression string into an AST.

    With ``parse_all`` and a single top-level alternative, element 0 of the
    parse result is the root node.

    Returns:
        One of ``NumberNode``, ``NameNode``, ``UnaryOperatorNode``,
        ``BinaryOperatorNode``, ``ComparisonNode`` or ``FunctionCallNode``.
    """
    try:
        result = _GRAMMAR.parse_string(text, parse_all=True)
    except pp.ParseException as e:
        msg = f'Failed to parse expression: {text!r}\n{e}'
        raise SchemaError(msg) from e
    return cast('ExpressionNode', result[0])
