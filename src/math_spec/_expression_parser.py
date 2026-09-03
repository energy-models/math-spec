# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The core AST every pass reads, and the pyparsing grammar that builds it — package-private.

Arithmetic nests anywhere; a comparison appears only at the top of a parsed
expression.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal, assert_never, cast, get_args

import pyparsing as pp

from math_spec.errors import SchemaError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from math_spec.program import WhereNode

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


@dataclass(frozen=True)
class NameNode:
    """A bare name whose kind only the schema knows; resolution rewrites every one into a typed node."""

    name: str


@dataclass(frozen=True)
class VariableNode:
    """A resolved reference to a declared decision variable."""

    name: str


@dataclass(frozen=True)
class ParameterNode:
    """A resolved reference to a declared parameter."""

    name: str


@dataclass(frozen=True)
class DualNode:
    """A resolved ``dual(c)``: the row dual of the declared constraint *c*, a leaf.

    Constraints sit outside the flat namespace, so a bare name never resolves
    to one; ``dual(c)`` is the one position that reads the constraint store. A
    dual is a number only a solve produces, so the loader refuses this leaf
    anywhere the math is built (:mod:`math_spec.validation`).
    """

    constraint: str


@dataclass(frozen=True)
class DimensionNode:
    """A resolved reference to a declared dimension.

    Only legal in operator kwarg *values* (``sum(x, over=generator)``), never as
    a value in arithmetic — a dimension is a coordinate space, not data.
    """

    name: str


@dataclass(frozen=True)
class NameListNode:
    """A bracketed list of names in a kwarg value — ``sum(x, by=[a, b])``.

    Unresolved: which kind of name the kwarg admits is the operator's business.
    """

    names: tuple[str, ...]

    @property
    def shown(self) -> str:
        """The kwarg value as the author wrote it, for an error message."""
        return shown(self.names)


@dataclass(frozen=True)
class LookupNode:
    """A resolved reference to one or more declared lookups, legal only in a kwarg value.

    ``dimension`` is the one every lookup is over — what ``sum`` consumes and
    ``at`` produces — and ``into`` the targets, one per name in the order
    written; ``sum(x, by=[gen_bus, gen_tech])`` is one grouping, not two.
    """

    names: tuple[str, ...]
    dimension: str
    into: tuple[str, ...]

    @property
    def shown(self) -> str:
        """The kwarg value as the author wrote it, for an error message."""
        return shown(self.names)


@dataclass(frozen=True)
class KeywordNode:
    """A quoted closed keyword in a kwarg value — ``shift(..., edge='wrap')``.

    Unresolved: which keywords the kwarg accepts is the operator's business.
    """

    value: str


@dataclass(frozen=True)
class EdgeNode:
    """The resolved ``edge='wrap'``; a number in the same position stays a :class:`NumberNode`."""


@dataclass(frozen=True)
class UnaryOperatorNode:
    op: UnaryOperator
    operand: ArithmeticNode


@dataclass(frozen=True)
class BinaryOperatorNode:
    op: BinaryOperator
    left: ArithmeticNode
    right: ArithmeticNode


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
        object.__setattr__(self, 'kwargs', MappingProxyType(dict(self.kwargs)))


@dataclass(frozen=True)
class CaseArm:
    """One region of a :class:`CasesNode`: where it applies, and the value there.

    ``when`` is ``None`` on the **last** arm and only there — the block's
    ``otherwise:``, which is what makes the quantity total without anything
    having to prove it. Every other arm's ``when`` is proved apart from every
    other arm's.
    """

    label: str
    when: WhereNode | None
    value: ArithmeticNode


def case_context(name: str, label: str | None) -> str:
    """The context an error inside one arm of a cased expression is reported under.

    Args:
        name: The named expression the arm belongs to.
        label: The case's name, or ``None`` for the block's ``otherwise:``.

    Returns:
        The context prefix an error message carries.
    """
    where = 'otherwise' if label is None else f"case '{label}'"
    return f"Named expression '{name}', {where}"


@dataclass(frozen=True)
class CasesNode:
    """A value defined by region — a named expression's ``cases:``, inlined where its name stood.

    Exactly one arm applies at every coordinate, which :mod:`math_spec.exclusivity`
    proves at load; the last arm is the block's ``otherwise:`` and carries no
    ``when``. The arms are in file order. The frame is not carried here: it is
    on the declaration.
    """

    name: str
    arms: tuple[CaseArm, ...]


ArithmeticNode = (
    NumberNode
    | NameNode
    | NameListNode
    | VariableNode
    | ParameterNode
    | DualNode
    | DimensionNode
    | LookupNode
    | EdgeNode
    | KeywordNode
    | UnaryOperatorNode
    | BinaryOperatorNode
    | FunctionCallNode
    | CasesNode
)


@dataclass(frozen=True)
class ComparisonNode:
    op: ComparisonOperator
    left: ArithmeticNode
    right: ArithmeticNode


#: A whole spec-side expression tree — parse output and the resolved tree alike.
#: Named apart from :data:`math_spec.program.ExpressionNode`, the lowered
#: vocabulary a consumer reads.
ParsedNode = ArithmeticNode | ComparisonNode


def shown(names: tuple[str, ...]) -> str:
    """Names as a kwarg value is written: bare when one, bracketed when several."""
    return names[0] if len(names) == 1 else f'[{", ".join(names)}]'


# Node groups

#: A resolved reference the language admits only as an operator kwarg *value*:
#: ``sum(x, over=d)``, ``sum(x, by=l)``, ``shift(..., edge='wrap')``. None of
#: the three is data, so none may stand in arithmetic — which is why the passes
#: that walk a value position refuse them together.
KwargNode = DimensionNode | LookupNode | EdgeNode

#: What resolution rewrites away: a bare name, whose kind only the schema
#: knows, and the two kwarg-only literals its kwarg consumes. Meeting one
#: downstream means the expression skipped :func:`~math_spec.resolution.expression_of`.
UnresolvedNode = NameNode | NameListNode | KeywordNode

#: Every leaf — nothing below it to descend into.
LeafNode = NumberNode | VariableNode | ParameterNode | DualNode | KwargNode | UnresolvedNode

#: Every node carrying sub-expressions, which is exactly what :func:`children`
#: descends and the only place a walk recurses.
BranchNode = UnaryOperatorNode | BinaryOperatorNode | ComparisonNode | FunctionCallNode | CasesNode


def children(node: ParsedNode) -> tuple[ArithmeticNode, ...]:
    """The sub-expressions of *node* — the structural half of any walk.

    Every pass that recurses the whole tree and acts only at certain leaves
    goes through here, so a node added later reaches all of them. An
    operator's kwargs are children too — a dimension or coordinate is an
    ordinary node in a kwarg value, which is what lets a macro bind a formal.
    A case arm's ``when`` is not: it is a mask over the frame, not a value in it.
    """
    if isinstance(node, UnaryOperatorNode):
        return (node.operand,)
    if isinstance(node, (BinaryOperatorNode, ComparisonNode)):
        return (node.left, node.right)
    if isinstance(node, FunctionCallNode):
        return (*node.args, *node.kwargs.values())
    if isinstance(node, CasesNode):
        return tuple(arm.value for arm in node.arms)
    return ()


def with_children(node: ArithmeticNode, recurse: Callable[[ArithmeticNode], ArithmeticNode]) -> ArithmeticNode:
    """*node* rebuilt with *recurse* applied to each of its :func:`children`; a leaf comes back as is.

    A case arm's ``when`` is a mask over the frame, not a value in it, and is
    carried across unchanged.
    """
    if isinstance(node, LeafNode):
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
    if isinstance(node, CasesNode):
        return CasesNode(node.name, tuple(CaseArm(a.label, a.when, recurse(a.value)) for a in node.arms))
    assert_never(node)


# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------


def _build_grammar() -> pp.ParserElement:
    """``inf`` is a ``pp.Keyword`` rather than a ``pp.Literal``, which would match the prefix of ``inflow``."""
    arith = pp.Forward()

    inf_literal = (pp.Keyword('.inf') | pp.Keyword('inf')).set_parse_action(lambda: NumberNode(float('inf')))
    # pyrefly: ignore[implicit-any-lambda]
    number = inf_literal | pp.Regex(rf'{REAL}|\d+').set_parse_action(lambda t: NumberNode(float(t[0])))

    name = pp.Regex(NAME)

    quoted = (pp.QuotedString("'") | pp.QuotedString('"')).set_parse_action(lambda t: KeywordNode(str(t[0])))
    name_list = (pp.Suppress('[') + pp.DelimitedList(name) + pp.Suppress(']')).set_parse_action(
        lambda t: NameListNode(tuple(str(x) for x in t))
    )
    kwarg = (name + pp.Suppress('=') + (quoted | name_list | arith)).set_parse_action(lambda t: (t[0], t[1]))
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
    return (arith + pp.Optional(comparator + arith)).set_parse_action(
        lambda t: ComparisonNode(t[1], t[0], t[2]) if len(t) == 3 else t[0]
    )


def _make_func_call(tokens: pp.ParseResults) -> FunctionCallNode:
    """The callee is cast: a ParseResults element is untyped, and the grammar guarantees an identifier in position 0."""
    name = cast('str', tokens[0])
    args = []
    kwargs = {}
    for item in tokens[1:]:
        if isinstance(item, tuple) and len(item) == 2:
            k, v = item
            if k in kwargs:
                msg = f'{name}({k}=) is given twice. A keyword names one value; drop one of them.'
                raise SchemaError(msg)
            kwargs[k] = v
        else:
            args.append(item)
    return FunctionCallNode(name=name, args=tuple(args), kwargs=kwargs)


def _make_left_assoc(tokens: pp.ParseResults) -> Any:
    result, *rest = tokens
    for op, right in zip(rest[::2], rest[1::2], strict=True):
        result = BinaryOperatorNode(op, result, right)
    return result


def _make_power(tokens: pp.ParseResults) -> Any:
    """A base and at most one exponent — right-associative, since the exponent is itself a ``unary``."""
    items = list(tokens)
    return items[0] if len(items) == 1 else BinaryOperatorNode('**', items[0], items[2])


_GRAMMAR = _build_grammar()


def parse_text(grammar: pp.ParserElement, text: str, what: str, rewrite: Callable[[str, int], str | None]) -> Any:
    """Parse the whole of *text* with *grammar*, or raise :class:`SchemaError` naming *what* failed to parse.

    *rewrite* is asked for the predictable mistake at the failure position; its
    sentence, if any, precedes the grammar's own complaint.
    """
    try:
        result = grammar.parse_string(text, parse_all=True)
    except pp.ParseException as e:
        hint = rewrite(text, e.loc)
        msg = f'Failed to parse {what}: {text!r}\n{f"{hint}\n" if hint is not None else ""}{e}'
        raise SchemaError(msg) from e
    return result[0]


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


@lru_cache(maxsize=4096)
def parse_expression(text: str) -> ParsedNode:
    """Parse a math expression string into an AST.

    Raises:
        SchemaError: If *text* is not an expression of the language. A
            predictable mistake — a strict or chained comparison, ``!=``, a
            lone ``=``, ``^`` for power — is named with its rewrite before the
            grammar's own complaint.
    """
    return cast('ParsedNode', parse_text(_GRAMMAR, text, 'expression', _named_rewrite))
