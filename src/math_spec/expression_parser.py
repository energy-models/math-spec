# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""pyparsing-based expression parser for math expressions.

Parses strings like ``sum(p * cost, over=generator) == load`` into an AST
that can be evaluated against a namespace of linopy variables and xarray
parameters.

``ArithmeticNode`` is the arithmetic-only union: every nested expression
position (operands, args, kwargs) accepts it and nothing else, and
``ComparisonNode`` appears only at the top of a parsed expression.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal, cast

import pyparsing as pp

from math_spec.errors import SchemaError

if TYPE_CHECKING:
    from collections.abc import Mapping

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

# ---------------------------------------------------------------------------
# AST nodes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NumberNode:
    value: float


@dataclass(frozen=True)
class NameNode:
    """An unresolved token — a name whose *kind* is not yet known.

    The parser cannot know whether ``p`` is a variable, a parameter or a
    dimension; only the schema knows. ``resolution.py`` rewrites every one of
    these into one of the typed nodes below, so a NameNode never reaches a
    backend. If you find one there, resolution was skipped.
    """

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
class ConstraintNode:
    """A resolved reference to a declared constraint, legal only as ``dual()``'s argument.

    Constraints sit outside the flat namespace, so a bare name never resolves to
    one — only ``dual(c)`` reaches the constraint store. A dual is data read
    after the solve, so this leaf is reached only from a post-solve-grade entry;
    the loader refuses ``dual`` anywhere the math is built.
    """

    name: str


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
    """A resolved edge policy, legal only as an ``edge=`` value.

    A *number* in the same position stays a :class:`NumberNode`: the value the
    vacated positions contribute.
    """

    policy: str


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
    """An operator or macro call — like every node, unrewritable once built.

    ``kwargs`` is copied behind a read-only view at construction, so neither a
    holder of the mapping passed in nor a reader of the node can rewrite an
    argument under another pass; it is excluded from the hash because a
    mapping has none, which is lawful — equal nodes still hash equal on
    ``name`` and ``args``.
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
    """Where an error inside one arm of a cased expression is reported: the declaration, not the use site.

    A cased expression is expanded where its name stood, so the context in hand
    at that point is the constraint's — and naming it would report a case on a
    constraint that has none.

    Args:
        name: The named expression the arm belongs to.
        label: The case's name, or ``None`` for the block's ``otherwise:``,
            which is not a case and is not named as one.

    Returns:
        The context prefix an error message carries.
    """
    where = 'otherwise' if label is None else f"case '{label}'"
    return f"Named expression '{name}', {where}"


@dataclass(frozen=True)
class CasesNode:
    """A value defined by region — a named expression's ``cases:``, inlined.

    Built by :mod:`math_spec.expansion` where a reference to a cased expression
    stood; there is no grammar for it, since a file writes the cases on the
    declaration rather than at the use site.

    Exactly one arm applies at every coordinate: no two ``when`` masks can hold
    at once, which :mod:`math_spec.exclusivity` proves at load, and the last arm
    — the block's ``otherwise:`` — carries no ``when`` and so takes whatever the
    rest leave. So the arms may be read in any order; the file's is kept because
    it is the order they print in. The frame is not carried here: it is on the
    declaration, which every consumer needing it already holds.
    """

    name: str
    arms: tuple[CaseArm, ...]


ArithmeticNode = (
    NumberNode
    | NameNode
    | NameListNode
    | VariableNode
    | ParameterNode
    | ConstraintNode
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


ExpressionNode = ArithmeticNode | ComparisonNode


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
#: downstream means the expression skipped :func:`~math_spec.expression_of`.
UnresolvedNode = NameNode | NameListNode | KeywordNode

#: Every leaf — nothing below it to descend into.
LeafNode = NumberNode | VariableNode | ParameterNode | ConstraintNode | KwargNode | UnresolvedNode

#: Every node carrying sub-expressions, which is exactly what :func:`children`
#: descends and the only place a walk recurses.
BranchNode = UnaryOperatorNode | BinaryOperatorNode | ComparisonNode | FunctionCallNode | CasesNode


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
    if isinstance(node, CasesNode):
        # the values only: a `when` is a mask over the frame, not a value in it
        return tuple(arm.value for arm in node.arms)
    return ()


# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------


def _build_grammar() -> pp.ParserElement:
    """Build the pyparsing grammar for math expressions.

    ``inf`` is a ``pp.Keyword``, not a ``pp.Literal``: a ``Literal`` matches a
    prefix, so it would eat the first three characters of ``inflow`` and leave
    the parser meeting ``low`` where it expects the end of the expression. A
    quoted value or a bracketed list of names is admitted only in a kwarg
    value; a comparison appears at most once, and only at the top.
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

    comparator = pp.one_of('<= >= ==')
    return (arith + pp.Optional(comparator + arith)).set_parse_action(
        lambda t: ComparisonNode(t[1], t[0], t[2]) if len(t) == 3 else t[0]
    )


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
            if k in kwargs:
                msg = f'{name}({k}=) is given twice. A keyword names one value; drop one of them.'
                raise SchemaError(msg)
            kwargs[k] = v
        else:
            args.append(item)
    return FunctionCallNode(name=name, args=tuple(args), kwargs=kwargs)


def _make_left_assoc(tokens: pp.ParseResults) -> Any:
    """Fold tokens into a left-associative BinaryOperatorNode chain."""
    result, *rest = tokens
    for op, right in zip(rest[::2], rest[1::2], strict=True):
        result = BinaryOperatorNode(op, result, right)
    return result


def _make_power(tokens: pp.ParseResults) -> Any:
    """A base and at most one exponent — right-associative, since the exponent is itself a ``unary``."""
    items = list(tokens)
    return items[0] if len(items) == 1 else BinaryOperatorNode('**', items[0], items[2])


#: What an expression writes to refer to a declaration, and so what a
#: declaration may be named.
NAME = r'[a-zA-Z_][a-zA-Z0-9_]*'

#: A float — a fractional part or an exponent. A sign is the unary operator's.
REAL = r'\d+\.\d*([eE][+-]?\d+)?|\d+[eE][+-]?\d+'

_GRAMMAR = _build_grammar()


def _named_rewrite(text: str, loc: int) -> str | None:
    """The rewrite for a predictable mistake at the parse failure, or ``None``.

    Keyed on the token standing where the grammar gave up, so a diagnosis
    never fires on an expression that parses — ``over=d`` inside a call is
    legal and reaches no failure, while a lone ``=`` between two sides does.
    A two-character token is tested before its one-character prefix.
    """
    rest = text[loc:].lstrip()
    if rest.startswith(('<=', '>=', '==')):
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
def parse_expression(text: str) -> ExpressionNode:
    """Parse a math expression string into an AST.

    The same string parses to the same tree, and a node is unrewritable once
    built, so the tree is shared rather than rebuilt — a model writes its
    expressions far more often than it writes distinct ones, and every
    expression is parsed twice over, once to validate the file and once to
    lower it.

    Raises:
        SchemaError: If *text* is not an expression of the language. A
            predictable mistake — a strict or chained comparison, ``!=``, a
            lone ``=``, ``^`` for power — is named with its rewrite before the
            grammar's own complaint.
    """
    try:
        result = _GRAMMAR.parse_string(text, parse_all=True)
    except pp.ParseException as e:
        rewrite = _named_rewrite(text, e.loc)
        hint = f'{rewrite}\n' if rewrite is not None else ''
        msg = f'Failed to parse expression: {text!r}\n{hint}{e}'
        raise SchemaError(msg) from e
    return cast('ExpressionNode', result[0])
