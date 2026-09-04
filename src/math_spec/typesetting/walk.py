# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The walk: resolved AST → typeset lines. Written once, for every format.

Everything here is a decision about the *math* — where a bracket changes the
reading, which dimension a reduction binds, that a mask belongs on the ∀ rather
than in the equation, that a translation shows at the leaf it re-indexes. None
of it is about syntax, so none is duplicated per format.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Literal, assert_never

from math_spec._expression_parser import (
    ArithmeticNode,
    BinaryOperator,
    BinaryOperatorNode,
    CasesNode,
    ComparisonNode,
    DimensionNode,
    DualNode,
    EdgeNode,
    FunctionCallNode,
    KwargNode,
    LookupNode,
    NumberNode,
    ParameterNode,
    UnaryOperatorNode,
    UnresolvedNode,
    VariableNode,
)
from math_spec.dimensions import dims_of
from math_spec.program import (
    AndNode,
    BooleanLiteralNode,
    DimensionComparisonNode,
    DimensionPositionNode,
    LookupComparisonNode,
    LookupDefinedNode,
    LookupPairComparisonNode,
    Mask,
    NotNode,
    OrNode,
    ParameterComparisonNode,
    ParameterDefinedNode,
    PredicateOperator,
    VariableDefinedNode,
    WhereNode,
)
from math_spec.resolution import (
    expression_of,
    where_of,
)
from math_spec.typesetting.format import Entry, Glossary, Line, OperatorName
from math_spec.typesetting.symbols import printed_expressions, reported_expressions

if TYPE_CHECKING:
    import datetime
    from collections.abc import Iterable

    from math_spec.model import SosBlock, _ExpandedSpec
    from math_spec.resolution import Namespace
    from math_spec.typesetting.format import Format
    from math_spec.typesetting.symbols import Symbols

#: Operator precedence, for deciding brackets. A reduction sits at the bottom
#: with ``+``: an unbracketed sum reads as capturing whatever follows it, so as
#: a factor it has to be bracketed.
_PRECEDENCE: dict[BinaryOperator, int] = {'+': 1, '-': 1, '*': 2, '/': 2, '**': 3}
_ATOM = 5

_PREDICATES: dict[PredicateOperator, OperatorName] = {
    '==': 'equal',
    '!=': 'ne',
    '<=': 'le',
    '>=': 'ge',
    '<': 'lt',
    '>': 'gt',
}


#: What a translation does with the row the shift vacates. Three policies get
#: three spellings because they are three different equations at the boundary.
TranslationPolicy = Literal['plain', 'wrap', 'edge']

#: The positional forms an equation can print, each of which the legend explains once.
PositionForm = Literal['plain', 'grouped', 'from_end']

#: Edge policy -> the operator pair that renders it, backward then forward —
#: the vacated row dropped, wrapped, or filled.
_TRANSLATIONS: dict[TranslationPolicy, tuple[OperatorName, OperatorName]] = {
    'plain': ('minus', 'plus'),
    'wrap': ('cyclic_minus', 'cyclic_plus'),
    'edge': ('edge_minus', 'edge_plus'),
}


def _amount(node: ArithmeticNode) -> int | str:
    """``shift``'s ``offset=``: a signed number, or the name of a parameter.

    A named offset is always backward — a negated one is refused at load, in
    :func:`math_spec.dimensions.check_schema` — which the assert relies on.
    """
    if isinstance(node, ParameterNode):
        return node.name
    assert isinstance(node, NumberNode), 'resolution folds a literal offset to one signed number'
    return int(node.value)


@dataclass(frozen=True)
class _Step:
    """One translation of an index, and what stands where it vacated.

    ``fill`` is the rendered ``edge=`` value, and it rides on the operator
    rather than in the legend because it is per call site: one model may pad a
    sum with ``0`` and a product with ``1``, and one legend entry cannot say
    which term is which. It is empty for the two policies that substitute
    nothing.
    """

    by: int | str
    policy: TranslationPolicy
    fill: str = ''
    #: The rendered group a partitioned translation walks inside, or empty.
    within: str = ''

    def merged(self, other: _Step) -> _Step | None:
        """*other* applied under this one as a single translation, or ``None`` where it is two.

        Only numbers add, and only under an identical policy, fill and group:
        a cyclic step under an acyclic one folded into ``t ⊖ 2`` claims the
        outer step wraps when it drops.
        """
        if isinstance(self.by, str) or isinstance(other.by, str):
            return None
        same = (self.policy, self.fill, self.within) == (other.policy, other.fill, other.within)
        return replace(self, by=self.by + other.by) if same else None


@dataclass(frozen=True)
class _Context:
    """What a subscript means at this point in the tree.

    ``offsets`` is how ``shift`` renders: it emits no operator of its own but
    re-indexes its operand, so the translation shows at the *leaves*. Its steps
    are outermost first, the order they apply to the index — the outer shift of
    ``shift(shift(x, offset=a), offset=b)`` moves ``t`` to ``t - b``, and the inner one
    reads ``x`` from there.
    """

    walk: Walk
    offsets: dict[str, tuple[_Step, ...]] = field(default_factory=dict)
    #: dim -> the rendered subscript that replaces its index, as ``at`` re-indexes a leaf.
    pullbacks: dict[str, str] = field(default_factory=dict)
    #: Every dimension whose index is in use here — the frame, then one entry
    #: per reduction entered — so a reduction over one takes a fresh dummy.
    bound: tuple[str, ...] = ()

    def translated(self, dim: str, step: _Step) -> _Context:
        steps = self.offsets.get(dim, ())
        merged = steps[-1].merged(step) if steps else None
        steps = (*steps[:-1], merged) if merged is not None else (*steps, step)
        return _Context(self.walk, {**self.offsets, dim: steps}, self.pullbacks, self.bound)

    def pulled_back(self, dim: str, rendered: str) -> _Context:
        return _Context(self.walk, self.offsets, {**self.pullbacks, dim: rendered}, self.bound)

    def reducing(self, dim: str) -> tuple[str, _Context]:
        """A dummy index for a reduction over *dim*, and the context its body reads under.

        The plain index where nothing outside the reduction uses it; primed
        once per enclosing use of the same dimension, so ``sum(q, by=bus_of)``
        under ``∀ g`` sums over ``g'`` and its condition can still name ``g``.
        """
        primes = "'" * self.bound.count(dim)
        dummy = f'{self.walk.symbols.index[dim]}{primes}'
        body = _Context(self.walk, self.offsets, {**self.pullbacks, dim: dummy}, (*self.bound, dim))
        return dummy, body

    def subscript(self, dim: str) -> str:
        """The index for *dim* here: its pullback if it has one, then every translation.

        A pullback is a base like any other rather than a stopping point.
        ``at`` and ``shift`` both re-index the leaf and the leaf has one
        subscript, so a reading that showed only whichever ran last dropped the
        other operator out of the equation.
        """
        text = self.pullbacks.get(dim, self.walk.symbols.index[dim])
        translated = False
        for step in self.offsets.get(dim, ()):
            if step.by == 0:
                continue
            base = self.walk.format.parenthesise(text) if translated else text
            amount = self.walk.symbols.name[step.by] if isinstance(step.by, str) else str(abs(step.by))
            text = f'{base} {self.walk._translation(step)} {amount}'
            translated = True
        return text

    def indexed(self, symbol: str, dims: list[str]) -> str:
        return self.walk.format.subscript(symbol, [self.subscript(d) for d in dims])


def _unsigned(node: ArithmeticNode) -> ArithmeticNode | None:
    """*node* without its leading minus — on the node, or on the first factor of a product it heads — else ``None``."""
    if isinstance(node, UnaryOperatorNode) and node.op == '-':
        return node.operand
    if isinstance(node, BinaryOperatorNode) and node.op in ('*', '/') and (left := _unsigned(node.left)) is not None:
        return BinaryOperatorNode(node.op, left, node.right)
    return None


@dataclass
class Noticed:
    """What the equations printed that the legend has to explain."""

    policies: set[TranslationPolicy] = field(default_factory=set)
    grouped: bool = False
    positions: set[PositionForm] = field(default_factory=set)
    numeric_coordinates: set[str] = field(default_factory=set)


class Walk:
    """Walks a validated schema, emitting :class:`Line`s in one format.

    :meth:`equations` prints every section and returns what it :class:`Noticed`;
    the legend methods take that record, so they can only describe symbols the
    equations printed.
    """

    def __init__(self, schema: _ExpandedSpec, namespace: Namespace, symbols: Symbols, fmt: Format) -> None:
        self.schema = schema
        self.namespace = namespace
        self.symbols = symbols
        self.format = fmt
        self.noticed = Noticed()

    def _op(self, name: OperatorName) -> str:
        return self.format.operators[name]

    def _translation(self, step: _Step) -> str:
        """The operator for one translation, its fill below and its group above.

        Two slots, because one subscript holding both says nothing about which
        is the fill and which the group. A named offset is always backward,
        since ``offset=-p`` is refused at load.
        """
        backward, forward = _TRANSLATIONS[step.policy]
        operator = self._op(backward if isinstance(step.by, str) or step.by > 0 else forward)
        if step.fill:
            operator = self.format.subscript(operator, [step.fill])
        if not step.within:
            return operator
        self.noticed.grouped = True
        return self.format.superscript(operator, step.within)

    def _lookup(self, name: str, index: str) -> str:
        """A coordinate map applied to an index: ``bus(g)``."""
        return self.format.apply(self.format.upright(name), index)

    def _context(self, frame: Iterable[str] = ()) -> _Context:
        return _Context(self, bound=tuple(frame))

    def _number(self, value: float) -> str:
        if value == float('inf'):
            return self._op('infinity')
        if value == int(value):
            return str(int(value))
        mantissa, _, exponent = repr(value).partition('e')
        if not exponent:
            return mantissa
        power = self.format.superscript('10', str(int(exponent)))
        return power if mantissa == '1' else f'{mantissa} {self._op("times")} {power}'

    # -- arithmetic --------------------------------------------------------

    def _expression(self, node: ArithmeticNode, ctx: _Context, *, need: int = 0) -> str:
        text, precedence = self._arithmetic(node, ctx)
        return self.format.parenthesise(text) if precedence < need else text

    def _arithmetic(self, node: ArithmeticNode, ctx: _Context) -> tuple[str, int]:
        """Render *node*, returning the text and the precedence it binds at.

        A ``NameNode`` here means resolution was skipped, and a bare dimension
        or coordinate in a value position is a language error caught long
        before this module runs — so meeting either is an assertion, not a
        rendering decision.
        """
        if isinstance(node, NumberNode):
            return self._number(node.value), _ATOM if node.value >= 0 else 1

        if isinstance(node, ParameterNode):
            return ctx.indexed(self.symbols.name[node.name], list(self.schema.parameters[node.name].dims)), _ATOM

        if isinstance(node, VariableNode):
            return ctx.indexed(self.symbols.name[node.name], list(self.schema.variables[node.name].foreach)), _ATOM

        if isinstance(node, UnaryOperatorNode):
            if node.op == '+':
                return self._arithmetic(node.operand, ctx)
            text, precedence = self._arithmetic(node.operand, ctx)
            operand = self.format.parenthesise(text) if precedence < 2 else text
            return f'{self._op("minus")}{operand}', 2

        if isinstance(node, BinaryOperatorNode):
            return self._binary(node, ctx)

        if isinstance(node, FunctionCallNode):
            return self._call(node, ctx)

        if isinstance(node, CasesNode):
            return ctx.indexed(self.symbols.name[node.name], self._frame(node.name)), _ATOM

        if isinstance(node, DualNode):
            return self._dual(node, ctx), _ATOM

        if isinstance(node, UnresolvedNode | KwargNode):
            msg = f'{type(node).__name__} reached the typesetter; resolve the expression first.'
            raise AssertionError(msg)

        assert_never(node)

    def _dual(self, node: DualNode, ctx: _Context) -> str:
        """λ subscripted by the constraint's symbol, then the indices of the constraint's own frame."""
        frame = self._sorted(dims_of(node, self.schema, 'a dual'))
        return self.format.subscript(
            self._op('dual'), [self.symbols.constraint[node.constraint], *(ctx.subscript(d) for d in frame)]
        )

    def _binary(self, node: BinaryOperatorNode, ctx: _Context) -> tuple[str, int]:
        """Render a binary operator, bracketing only where the reading demands.

        Subtraction raises the requirement on its right operand by one:
        ``a - (b - c)`` and ``a - (b + c)`` need the bracket; ``a - b*c``
        does not. A negation folds into the sign beside it — ``a + -b`` is
        ``a - b`` and ``a - -b`` is ``a + b`` — and as a factor it is
        bracketed, since ``a · -b`` is a spelling nobody reads. A power is
        atomic to everything but another power, a stacked superscript being
        ambiguous.
        """
        if node.op == '/':
            top = self._expression(node.left, ctx)
            bottom = self._expression(node.right, ctx)
            return self.format.fraction(top, bottom), _ATOM
        if node.op == '**':
            base = self._expression(node.left, ctx, need=_PRECEDENCE['**'] + 1)
            return self.format.superscript(base, self._expression(node.right, ctx)), _PRECEDENCE['**']
        precedence = _PRECEDENCE[node.op]
        left = self._expression(node.left, ctx, need=precedence)
        operand, op = node.right, node.op
        if op in ('+', '-') and (unsigned := _unsigned(operand)) is not None:
            operand, op = unsigned, '-' if op == '+' else '+'
        negated_factor = op == '*' and isinstance(operand, UnaryOperatorNode) and operand.op == '-'
        need = _ATOM if negated_factor else _PRECEDENCE[op] + (1 if op == '-' else 0)
        right = self._expression(operand, ctx, need=need)
        names: dict[BinaryOperator, OperatorName] = {'*': 'cdot', '+': 'plus', '-': 'minus'}
        return self.format.joined([left, right], self._op(names[op])), precedence

    def _call(self, node: FunctionCallNode, ctx: _Context) -> tuple[str, int]:
        """Render an operator: a translation at the leaves, or a summation.

        ``shift`` and ``at`` emit no operator of their own — they re-index the
        operand, so the substitution shows at the leaves. A ``sum`` naming no
        dim binds every dim its operand carries, and the domain has to say
        which, since the call does not.
        """
        if node.name == 'shift':
            dim = node.kwargs['over']
            assert isinstance(dim, DimensionNode)
            step = self._step(_amount(node.kwargs['offset']), node.kwargs.get('edge'))
            self.noticed.policies.add(step.policy)
            step = replace(step, within=self._group(node.kwargs.get('by'), dim.name))
            return self._arithmetic(node.args[0], ctx.translated(dim.name, step))

        if node.name == 'sum_back':
            over = node.kwargs['over']
            assert isinstance(over, DimensionNode)
            policy = 'wrap' if isinstance(node.kwargs.get('edge'), EdgeNode) else 'plain'
            step = _Step(1, policy, within=self._group(node.kwargs.get('by'), over.name))
            self.noticed.policies.add(step.policy)
            source, inner = ctx.reducing(over.name)
            lag = f'{ctx.subscript(over.name)} {self._translation(step)} {source}'
            domain = (
                f'{source} {self._op("in")} {self.symbols.set[over.name]} {self._op("such_that")} '
                f'0 {self._op("le")} {lag} {self._op("lt")} {self._width(node.kwargs["within"])}'
            )
            body = self._reduction_body(node.args[0], inner)
            return self.format.summation(domain, body), _PRECEDENCE['+']

        if node.name == 'at':
            by = node.kwargs['by']
            assert isinstance(by, LookupNode)
            for name, into in zip(by.names, by.into, strict=True):
                ctx = ctx.pulled_back(into, self._lookup(name, ctx.subscript(by.dimension)))
            return self._arithmetic(node.args[0], ctx)

        if (by := node.kwargs.get('by')) is not None:
            assert isinstance(by, LookupNode)
            dummy, inner = ctx.reducing(by.dimension)
            conditions = [
                f'{self._lookup(name, dummy)} {self._op("equal")} {ctx.subscript(into)}'
                for name, into in zip(by.names, by.into, strict=True)
            ]
            domain = (
                f'{self._membership(by.dimension, dummy)} {self._op("such_that")} '
                f'{self.format.joined(conditions, self._op("and"))}'
            )
        elif (over := node.kwargs.get('over')) is not None:
            assert isinstance(over, DimensionNode)
            dummy, inner = ctx.reducing(over.name)
            domain = self._membership(over.name, dummy)
        else:
            memberships = []
            inner = ctx
            for d in self._sorted(dims_of(node.args[0], self.schema, 'a sum')):
                dummy, inner = inner.reducing(d)
                memberships.append(self._membership(d, dummy))
            domain = self.format.joined(memberships, '')
        return self.format.summation(domain, self._reduction_body(node.args[0], inner)), _PRECEDENCE['+']

    def _group(self, by: ArithmeticNode | None, dim: str) -> str:
        """A ``by=`` as the superscript its translation operator carries.

        The bare index, not the subscript in force: the group is a property of
        the row being written, and a window whose operand is itself translated
        still asks which group *that row* is in.
        """
        if by is None:
            return ''
        assert isinstance(by, LookupNode)
        return self._lookup(by.names[0], self.symbols.index[dim])

    def _width(self, node: ArithmeticNode) -> str:
        """``sum_back``'s ``within=``: a number, or a parameter's own symbol.

        Unsubscripted where it is named, as a translation's named offset is:
        the symbol identifies the parameter and the legend carries its dims,
        where repeating them inside a summation's domain crowds out the
        condition that domain exists to state.
        """
        if isinstance(node, ParameterNode):
            return self.symbols.name[node.name]
        assert isinstance(node, NumberNode)
        return self._number(node.value)

    def _step(self, by: int | str, edge: ArithmeticNode | None) -> _Step:
        """Which of the three edge policies this ``shift`` asked for.

        ``edge='wrap'`` is the language's one keyword and arrives as an
        :class:`EdgeNode`; a number in the same position stays a
        :class:`NumberNode` and is the value the vacated positions contribute;
        absent is the bare shift, whose vacated positions are absent.
        """
        if isinstance(edge, EdgeNode):
            return _Step(by, 'wrap')
        if edge is None:
            return _Step(by, 'plain')
        assert isinstance(edge, NumberNode)
        return _Step(by, 'edge', self._number(edge.value))

    def _membership(self, dim: str, index: str | None = None) -> str:
        return f'{index or self.symbols.index[dim]} {self._op("in")} {self.symbols.set[dim]}'

    def _reduction_body(self, node: ArithmeticNode, ctx: _Context) -> str:
        """What sits to the right of a sum, bracketed only where it must be.

        A sum binds everything up to the next ``+`` or ``-`` at its own level,
        so an additive body needs the bracket and nothing else does — including
        a nested reduction, which is unambiguous.
        """
        additive = isinstance(node, UnaryOperatorNode) or (
            isinstance(node, BinaryOperatorNode) and node.op in ('+', '-')
        )
        return self._expression(node, ctx, need=2 if additive else 0)

    # -- where strings -----------------------------------------------------

    def _predicate(self, node: WhereNode, ctx: _Context, *, need: int = 0) -> str:
        text, precedence = self._where(node, ctx)
        return self.format.parenthesise(text) if precedence < need else text

    def _where(self, node: WhereNode, ctx: _Context) -> tuple[str, int]:
        if isinstance(node, BooleanLiteralNode):
            assert not node.value, 'an always-true mask is folded away or refused before anything prints it'
            return self._op('false'), _ATOM

        if isinstance(node, ParameterDefinedNode):
            indexed = ctx.indexed(self.symbols.name[node.name], list(node.dims))
            if self.schema.parameters[node.name].dtype == 'bool':
                return indexed, _ATOM
            return f'{indexed} {self.format.prose(" is defined")}', 2

        if isinstance(node, VariableDefinedNode):
            return f'{ctx.indexed(self.symbols.name[node.name], list(node.dims))} {self.format.prose(" exists")}', 2

        if isinstance(node, ParameterComparisonNode):
            left = ctx.indexed(self.symbols.name[node.name], list(node.dims))
            return f'{left} {self._op(_PREDICATES[node.op])} {self._literal(node.value)}', 2

        if isinstance(node, DimensionComparisonNode):
            if isinstance(node.value, int | float):
                self.noticed.numeric_coordinates.add(node.name)
            return f'{ctx.subscript(node.name)} {self._op(_PREDICATES[node.op])} {self._literal(node.value)}', 2

        if isinstance(node, DimensionPositionNode):
            grouping = None if node.by is None else self._lookup(node.by, ctx.subscript(node.name))
            place = self._position(ctx.subscript(node.name), grouping)
            ordinal = self._ordinal(node.name, node.position, grouping)
            return f'{place} {self._op(_PREDICATES[node.op])} {ordinal}', 2

        if isinstance(node, LookupComparisonNode):
            applied = self._lookup(node.name, ctx.subscript(node.over))
            return f'{applied} {self._op(_PREDICATES[node.op])} {self._literal(node.value)}', 2

        if isinstance(node, LookupPairComparisonNode):
            index = ctx.subscript(node.over)
            left = self._lookup(node.name, index)
            right = self._lookup(node.other, index)
            return f'{left} {self._op(_PREDICATES[node.op])} {right}', 2

        if isinstance(node, LookupDefinedNode):
            applied = self._lookup(node.name, ctx.subscript(node.over))
            return f'{applied} {self.format.prose(" is defined")}', 2

        if isinstance(node, NotNode):
            return f'{self._op("not")} {self._predicate(node.operand, ctx, need=3)}', 3

        if isinstance(node, AndNode):
            sides = [self._predicate(node.left, ctx, need=1), self._predicate(node.right, ctx, need=1)]
            return self.format.joined(sides, self._op('and')), 1

        if isinstance(node, OrNode):
            sides = [self._predicate(node.left, ctx, need=0), self._predicate(node.right, ctx, need=0)]
            return self.format.joined(sides, self._op('or')), 0

        assert_never(node)

    def _literal(self, value: float | str | datetime.date) -> str:
        return self._number(value) if isinstance(value, int | float) else self.format.quoted(str(value))

    def _position(self, index: str, grouping: str | None) -> str:
        """``position(dim)`` applied to the row, *grouping* as a subscript — as an argument it read as a second position."""
        self.noticed.positions.add('grouped' if grouping is not None else 'plain')
        symbol = self._op('position')
        if grouping is not None:
            symbol = self.format.subscript(symbol, [grouping])
        return self.format.apply(symbol, index)

    def _ordinal(self, dimension: str, at: int, grouping: str | None) -> str:
        """The position compared against; a negative one counts back from the size of the set it is a position in — the group's where grouped."""
        if at >= 0:
            return self._number(at)
        self.noticed.positions.add('from_end')
        size = self.symbols.set[dimension]
        if grouping is not None:
            size = self.format.subscript(size, [grouping])
        return f'{self.format.cardinality(size)} {self._op("minus")} {self._number(-at)}'

    def _condition(self, ctx: _Context, mask: Mask | None) -> str:
        """The mask on a quantifier, printed.

        A mask every row passes arrives as ``None`` — resolution folds it,
        so this prints what a program carries — and a quantifier with no
        condition prints none.
        """
        return '' if mask is None else self._predicate(mask.root, ctx)

    def _quantifier(self, dims: list[str], condition: str) -> str:
        if not dims and not condition:
            return ''
        over = self.format.joined([self._membership(d) for d in dims], '')
        if not condition:
            return f'{self._op("forall")} {over}'
        if not over:
            return f'{self.format.prose("where ")} {condition}'
        return f'{self._op("forall")} {over} {self._op("such_that")} {condition}'

    # -- declarations ------------------------------------------------------

    def equations(self, reported: bool) -> tuple[list[tuple[str, list[Line]]], Noticed]:
        """Every titled section of equations, and what printing them noticed for the legend.

        Args:
            reported: Whether to append the Reported quantities section — the
                entries the objective and constraints never read.
        """
        sections = [
            ('Objective', self._objective()),
            ('Subject to', self._constraints()),
            ('Definitions', self._definitions()),
            ('Variable domains', self._variables()),
        ]
        if reported:
            sections.append(('Reported quantities', self._reported()))
        return sections, self.noticed

    def _objective(self) -> list[Line]:
        """The objective's line.

        The expression is scalar — every reduction in it is one the file wrote
        — so it renders like any other, and the line carries no label: the
        block has no name, and the section heading already says what it is.
        """
        block = self.schema.objective
        if block is None:
            return []
        sense = self._op('minimize' if block.sense == 'minimize' else 'maximize')
        node = expression_of(block.expression, self.schema, self.namespace, 'the objective')
        assert not isinstance(node, ComparisonNode)
        return [Line(label='', left=sense, right=self._expression(node, self._context()))]

    def _constraints(self) -> list[Line]:
        lines = []
        for name, block in self.schema.constraints.items():
            context = f"constraint '{name}'"
            node = expression_of(block.expression, self.schema, self.namespace, context)
            if not isinstance(node, ComparisonNode):
                msg = f'{context}: expected a comparison, got {type(node).__name__}'
                raise AssertionError(msg)
            ctx = self._context(frame=block.foreach)
            condition = self._condition(ctx, where_of(block.where, self.namespace, context))
            lines.append(
                Line(
                    label=name,
                    left=self._expression(node.left, ctx),
                    right=f'{self._op(_PREDICATES[node.op])} {self._expression(node.right, ctx)}',
                    condition=self._quantifier(list(block.foreach), condition),
                )
            )
        return lines

    def _definitions(self) -> list[Line]:
        """One line per cased expression, in declaration order, defining it.

        A use prints the symbol and the block prints here, as a paper states a
        quantity defined by region. Every declared one prints, used or not.
        """
        lines = []
        for name in printed_expressions(self.schema):
            node = expression_of(name, self.schema, self.namespace, f"expression '{name}'")
            assert isinstance(node, CasesNode)
            frame = self._frame(name)
            ctx = self._context(frame)
            lines.append(
                Line(
                    label=name,
                    left=ctx.indexed(self.symbols.name[name], frame),
                    right=f'{self._op("equal")} {self.format.cases(self._arms(node, ctx))}',
                    condition=self._quantifier(frame, ''),
                )
            )
        return lines

    def _frame(self, name: str) -> list[str]:
        """The dims a cased expression is read over — its declaration's, not a copy."""
        return list(self.schema.expressions[name].foreach or ())

    def _arms(self, node: CasesNode, ctx: _Context) -> list[tuple[str, str]]:
        """Each arm as its value and the words saying where it applies.

        Which arm is the fallback is a fact about the math, so the *walk*
        chooses between "if" and "otherwise" and a Format only stacks the rows.
        """
        arms = []
        for arm in node.arms:
            when = (
                self.format.prose('otherwise')
                if arm.when is None
                else f'{self.format.prose("if ")} {self._predicate(arm.when, ctx, need=1)}'
            )
            arms.append((self._expression(arm.value, ctx), when))
        return arms

    def _variables(self) -> list[Line]:
        """One line per variable, and one more for a set the variable carries.

        A ``sos:`` block restricts the *domain* — which members of a family may
        be nonzero at once — so it prints under this heading, beside the
        variable it is a property of, rather than among the constraints, where
        it would read as a row a solver holds.
        """
        sets = {block.variable: block for block in self.schema.sos.values()}
        lines = []
        for name, block in self.schema.variables.items():
            ctx = self._context(frame=block.foreach)
            symbol = ctx.indexed(self.symbols.name[name], list(block.foreach))
            where = where_of(block.where, self.namespace, f"variable '{name}'", self_variable=name)
            condition = self._quantifier(list(block.foreach), self._condition(ctx, where))
            lower, upper = block.bounds.lower, block.bounds.upper

            if block.domain == 'binary':
                left, right = symbol, f'{self._op("in")} {self._op("binary_set")}'
            else:
                below, above = lower == float('-inf'), upper == float('inf')
                if below and above:
                    domain = self._op('integers' if block.domain == 'integer' else 'reals')
                    left, right = symbol, f'{self._op("in")} {domain}'
                elif below:
                    left, right = symbol, f'{self._op("le")} {self._bound(ctx, upper)}'
                elif above:
                    left, right = symbol, f'{self._op("ge")} {self._bound(ctx, lower)}'
                else:
                    left = f'{self._bound(ctx, lower)} {self._op("le")} {symbol}'
                    right = f'{self._op("le")} {self._bound(ctx, upper)}'
                if block.domain == 'integer' and not (below and above):
                    right = f'{right}, {symbol} {self._op("in")} {self._op("integers")}'
            lines.append(Line(label=name, left=left, right=right, condition=condition))
            if name in sets:
                lines.append(self._sos(name, sets[name], ctx))
        return lines

    def _reported(self) -> list[Line]:
        """One line per entry the math never reads — a quantity equated to its body.

        A reported entry *defines* a value, so it prints as ``symbol = body``:
        the right side says what the left is, which is why it needs no legend
        entry the way a variable does. An entry the math reads prints nothing
        here — it is inlined wherever it is read, in the equations above.
        """
        lines = []
        for name in reported_expressions(self.schema):
            context = f"expression '{name}'"
            node = expression_of(name, self.schema, self.namespace, context)
            assert not isinstance(node, ComparisonNode), f'{context}: a named body is arithmetic, not a comparison'
            frame = self._sorted(dims_of(node, self.schema, context))
            ctx = self._context(frame)
            lines.append(
                Line(
                    label=name,
                    left=ctx.indexed(self.symbols.name[name], frame),
                    right=f'{self._op("equal")} {self._expression(node, ctx)}',
                    condition=self._quantifier(frame, ''),
                )
            )
        return lines

    def _sos(self, name: str, block: SosBlock, ctx: _Context) -> Line:
        """The variable's family along the set's dim, as one member of the SOS set, quantified over the other dims."""
        foreach = self.schema.variables[name].foreach
        family = self.format.parenthesise(ctx.indexed(self.symbols.name[name], list(foreach)))
        return Line(
            label=f'{name} sos',
            left=self.format.subscript(family, [self._membership(block.over)]),
            right=f'{self._op("in")} {self._op("sos_set")}{block.type}',
            condition=self._quantifier([d for d in foreach if d != block.over], ''),
        )

    def _bound(self, ctx: _Context, value: float | str) -> str:
        if isinstance(value, str):
            return ctx.indexed(self.symbols.name[value], list(self.schema.parameters[value].dims))
        return self._number(value)

    def _sorted(self, dims: frozenset[str]) -> list[str]:
        order = list(self.schema.dimensions)
        return sorted(dims, key=order.index)

    # -- legend ------------------------------------------------------------

    def glossaries(self, noticed: Noticed) -> list[Glossary]:
        fmt = self.format
        sets = [
            self._entry(
                self.symbols.set[d],
                f'index {fmt.math(self.symbols.index[d])} {fmt.dash} {fmt.mono(d)}{self._coords(d, noticed)}',
                block.description,
            )
            for d, block in self.schema.dimensions.items()
        ]
        parameters = [
            self._entry(self.symbols.name[p], f'{fmt.mono(p)}{self._over(list(block.dims))}', block.description)
            for p, block in self.schema.parameters.items()
        ]
        variables = [
            self._entry(self.symbols.name[v], f'{fmt.mono(v)}{self._over(list(block.foreach))}', block.description)
            for v, block in self.schema.variables.items()
        ]
        groups = (Glossary('Sets', sets), Glossary('Parameters', parameters), Glossary('Variables', variables))
        return [group for group in groups if group.entries]

    def _entry(self, symbol: str, what: str, description: str | None) -> Entry:
        meaning = f'{what} {self.format.dash} {self.format.escape(description)}' if description else what
        return Entry(symbol, meaning)

    def _over(self, dims: list[str]) -> str:
        if not dims:
            return ' (scalar)'
        product = self.format.joined([self.symbols.set[d] for d in dims], self._op('times'))
        return f' over {self.format.math(product)}'

    def _coords(self, dim: str, noticed: Noticed) -> str:
        """The dimension's carried structure, groupable maps before plain labels.

        A targeted lookup renders as the map it is (``bus_of: G ↦ B``); a
        label-space lookup has no target set to point at, so it renders as the
        label it is (``period — a label on T``). The dtype is named only where
        an equation compared the index against a number, the one place
        "position 3" and "the coordinate 3" are both readings of a line.
        """
        targeted = self.schema.targeted_of(dim)
        labels = self.schema.labels_of(dim)
        clauses = []
        if dim in noticed.numeric_coordinates:
            clauses.append(f' ({self.format.mono(self.schema.dimensions[dim].dtype)} coordinates)')
        if targeted:
            maps = self.format.joined(
                [
                    f'{self.format.upright(c)}: {self.symbols.set[dim]} {self._op("maps_to")} {self.symbols.set[target]}'
                    for c, target in targeted.items()
                ],
                '',
            )
            clauses.append(f' with {self.format.math(maps)}')
        if labels:
            named = self.format.joined([self.format.upright(c) for c in labels], '')
            plural = 's' if len(labels) > 1 else ''
            clauses.append(f' carrying label{plural} {self.format.math(named)}')
        return ''.join(clauses)

    def convention_notes(self) -> list[str]:
        """What the two faces mean, with the model's own symbols.

        Only where the model has both, and quoting only derived symbols: a
        table is the author's to write, so a symbol it supplies is not one this
        note governs.
        """
        derived = [
            next((n for n in names if n not in self.symbols.overridden), None)
            for names in (self.schema.parameters, self.schema.variables)
        ]
        if not all(derived):
            return []
        given, chosen = (self.format.math(self.symbols.name[n]) for n in derived if n is not None)
        return [
            f'Upright is what the model is given {self.format.dash} a parameter such as {given}, a coordinate '
            f'map, a label {self.format.dash} and italic is what the solver chooses, such as {chosen}. '
            f'An index is italic too, being what a quantifier chooses, and a set is script.'
        ]

    def translation_notes(self, noticed: Noticed) -> list[str]:
        """A sentence for each translation symbol the model printed; plain ``t-k`` needs none."""
        notes = []
        if 'wrap' in noticed.policies:
            cyclic = self.format.math(f't {self._op("cyclic_minus")} k')
            notes.append(
                f'{cyclic} denotes cyclic translation: index {self.format.math("t-k")} taken modulo the size of '
                f'the dimension ({self.format.mono("roll")}). Plain {self.format.math("t-k")} '
                f'({self.format.mono("shift")}) has no wraparound {self.format.dash} terms translated past '
                f'the edge are simply absent.'
            )
        if 'edge' in noticed.policies:
            filled = self.format.math(f't {self.format.subscript(self._op("edge_minus"), ["v"])} k')
            notes.append(
                f'{filled} denotes translation with {self.format.math("v")} standing where index '
                f'{self.format.math("t-k")} leaves the dimension ({self.format.mono("shift(edge=v)")}), so the row '
                f'at that boundary is built and carries {self.format.math("v")} rather than being dropped.'
            )
        if noticed.grouped:
            applied = self._lookup('lookup', 't')
            counted = self.format.math(f't {self.format.superscript(self._op("cyclic_minus"), applied)} k')
            note = (
                f'{counted} denotes a translation counted inside the group a lookup puts {self.format.math("t")} '
                f'in ({self.format.mono("shift(by=lookup)")}), so a term never crosses out of its own group.'
            )
            if 'edge' in noticed.policies:
                both = self.format.superscript(self.format.subscript(self._op('edge_minus'), ['v']), applied)
                note += (
                    f' The two modifiers take different slots {self.format.dash} the group above, the fill '
                    f'below {self.format.dash} so {self.format.math(f"t {both} k")} is both at once.'
                )
            notes.append(note)
        return notes

    def position_notes(self, noticed: Noticed) -> list[str]:
        """A sentence for each positional symbol the model printed; the first says which of ``pos(t)`` and ``t`` is the position."""
        notes = []
        if noticed.positions:
            index = self.format.math('t')
            place = self.format.math(self.format.apply(self._op('position'), 't'))
            dash = self.format.dash
            notes.append(
                f"{place} denotes where index {index} sits along its dimension's own order {dash} the order "
                f'{self.format.mono("shift")} walks, not the order labels sort in {dash} counted from '
                f'{self.format.math("0")}. The index itself stays the coordinate, so {index} compares against '
                f'labels and {place} against positions.'
            )
        if 'grouped' in noticed.positions:
            applied = self._lookup('lookup', 't')
            grouped = self.format.math(self.format.apply(self.format.subscript(self._op('position'), [applied]), 't'))
            group = self.format.math(self.format.subscript(self.format.script('T'), [applied]))
            notes.append(
                f'{grouped} counts within the group a lookup puts {self.format.math("t")} in: the subscript names '
                f'the map, {group} is the group it lands in, and that group has a first position of its own.'
            )
        if 'from_end' in noticed.positions:
            size = self.format.cardinality(self.format.script('T'))
            last = self.format.math(f'{size} {self._op("minus")} {self._number(1)}')
            notes.append(
                f'{self.format.math(size)} denotes the size of the set being counted along, and a position '
                f'counted from the end prints against it {self.format.dash} {last} is the last position, one '
                f'less than the size because the first is {self.format.math("0")}.'
            )
        return notes
