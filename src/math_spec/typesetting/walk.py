# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The walk: resolved tree → typeset lines. Written once, for every format.

Everything here is a decision about the *math* — where a bracket changes the
reading, which dimension a reduction binds, that a mask belongs on the ∀ rather
than in the equation, that a translation shows at the leaf it re-indexes. None
of it is about syntax, so none is duplicated per format.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Literal, assert_never

from math_spec.dimensions import dims_of
from math_spec.piecewise import curve_frame
from math_spec.program import (
    Add,
    And,
    BooleanLiteral,
    Cases,
    Constant,
    CountComparison,
    DimensionComparison,
    DimensionPosition,
    Direction,
    Divide,
    Dual,
    Expression,
    ExpressionComparison,
    GroupSum,
    Mask,
    Multiply,
    Named,
    Negate,
    Not,
    Or,
    Parameter,
    ParameterComparison,
    ParameterDefined,
    Partition,
    Power,
    Predicate,
    PredicateOperator,
    Pullback,
    PulledBackPredicate,
    RelationComparison,
    RelationDefined,
    RelationPairComparison,
    Sum,
    Translate,
    TranslatedPredicate,
    Variable,
    VariableDefined,
    WindowSum,
)
from math_spec.typesetting.format import Entry, Line, OperatorName

if TYPE_CHECKING:
    import datetime
    from collections.abc import Iterable, Mapping

    from math_spec._expression_parser import BinaryOperator
    from math_spec.model import PiecewiseBlock, RelationBlock, SosBlock, Spec
    from math_spec.typesetting.format import Format
    from math_spec.typesetting.symbols import Symbols

#: Operator precedence, for deciding brackets. A reduction sits at the bottom
#: with ``+``: an unbracketed sum reads as capturing whatever follows it, so as
#: a factor it has to be bracketed.
_PRECEDENCE: dict[BinaryOperator, int] = {'+': 1, '-': 1, '*': 2, '/': 2, '**': 3}
_ATOM = 5

#: The same for a predicate: ``OR`` binds loosest, then ``AND``, then ``NOT``;
#: a comparison sits above the connectives and is bracketed under none.
_WHERE_PRECEDENCE = {'or': 0, 'and': 1, 'comparison': 2, 'not': 3}

#: The predicates that are one relation between two sides, which a line may
#: align on the way it aligns a constraint.
AlignedComparison = (
    ParameterComparison
    | ExpressionComparison
    | CountComparison
    | DimensionComparison
    | DimensionPosition
    | RelationComparison
    | RelationPairComparison
)

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


def _unsigned(node: Expression) -> Expression | None:
    """*node* without its leading minus — on the node, or on the first factor of a product it heads — else ``None``."""
    if isinstance(node, Negate):
        return node.operand
    if isinstance(node, Multiply | Divide):
        first, second = (node.left, node.right) if isinstance(node, Multiply) else (node.numerator, node.divisor)
        if (head := _unsigned(first)) is not None:
            return Multiply(head, second) if isinstance(node, Multiply) else Divide(head, second)
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

    def __init__(
        self,
        schema: Spec,
        symbols: Symbols,
        fmt: Format,
        *,
        inline_expressions: bool = False,
    ) -> None:
        self.schema = schema
        self.symbols = symbols
        self.format = fmt
        #: Substitute each plain named expression where it is used, rather than
        #: printing its symbol there and its definition once.
        self.inline_expressions = inline_expressions
        self.noticed = Noticed()
        #: The dims a named expression is read over: a cased one declares them,
        #: a plain one's fall out of its body.
        self.frames: dict[str, list[str]] = {name: self._frame_of(name) for name in schema.expressions}

    def _frame_of(self, name: str) -> list[str]:
        block = self.schema.expressions[name]
        if block.cases:
            return list(block.dims or ())
        return self._sorted(dims_of(self.schema.resolved.expressions[name].body, self.schema, f"expression '{name}'"))

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

    def _relation_read(self, name: str, at: Mapping[str, str], read: str) -> str:
        """Relation *name*'s column *read* as a function at the columns *at* fixes: ``bus(g)``, ``zone_of(g, p)`` or ``ends.bus0(l)``.

        *at* maps each key role to the index it is read at. The function is
        named after the relation alone where the key determines one column, and
        after the column read otherwise.
        """
        lk = self.schema.relations[name]
        function = name if len(lk.value_roles) == 1 else f'{name}.{read}'
        return self.format.apply(self.format.upright(function), self.format.joined([at[k] for k in lk.key_roles], ''))

    def _relation_row(self, name: str, at: Mapping[str, str]) -> str:
        """That relation *name* has a row at the key *at* fixes.

        A keyed table is a function, so the claim is that it is defined there:
        ``gen_zone(g, t) is defined``. A bare one is a set of rows, and every
        column of it is a key column, so the row is written out:
        ``(g, b) ∈ connection``.
        """
        lk = self.schema.relations[name]
        key = self.format.joined([at[k] for k in lk.key_roles], '')
        if lk.value_roles:
            return f'{self.format.apply(self.format.upright(name), key)} {self.format.prose(" is defined")}'
        return f'{self.format.parenthesise(key)} {self._op("in")} {self.format.upright(name)}'

    def _frame_key(self, name: str, ctx: _Context) -> dict[str, str]:
        """Relation *name*'s key roles at the frame's own indices of their dimensions."""
        lk = self.schema.relations[name]
        return {k: ctx.subscript(dict(lk.pairs)[k]) for k in lk.key_roles}

    def _value_read(self, name: str, column: str, ctx: _Context) -> str:
        """A keyed relation's value *column* read at the frame's own indices of its key: ``period_of(t)``."""
        return self._relation_read(name, self._frame_key(name, ctx), column)

    def _tuple(self, reads: list[str]) -> str:
        """Several reads as one group label: the read alone where there is one, a bracketed tuple otherwise."""
        return reads[0] if len(reads) == 1 else self.format.parenthesise(self.format.joined(reads, ''))

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

    def _expression(self, node: Expression, ctx: _Context, *, need: int = 0) -> str:
        text, precedence = self._arithmetic(node, ctx)
        return self.format.parenthesise(text) if precedence < need else text

    def _arithmetic(self, node: Expression, ctx: _Context) -> tuple[str, int]:
        """Render *node*, returning the text and the precedence it binds at."""
        if isinstance(node, Named):
            if self.inline_expressions and not isinstance(node.body, Cases):
                return self._arithmetic(node.body, ctx)
            return ctx.indexed(self.symbols.name[node.name], self.frames[node.name]), _ATOM

        if isinstance(node, Constant):
            return self._number(node.value), _ATOM if node.value >= 0 else 1

        if isinstance(node, Parameter):
            return ctx.indexed(self.symbols.name[node.name], list(self.schema.parameters[node.name].dims)), _ATOM

        if isinstance(node, Variable):
            return ctx.indexed(self.symbols.name[node.name], list(self.schema.variables[node.name].dims)), _ATOM

        if isinstance(node, Negate):
            text, precedence = self._arithmetic(node.operand, ctx)
            operand = self.format.parenthesise(text) if precedence < 2 else text
            return f'{self._op("minus")}{operand}', 2

        if isinstance(node, Add | Multiply | Divide | Power):
            return self._binary(node, ctx)

        if isinstance(node, Sum):
            return self._sum(node, ctx)

        if isinstance(node, GroupSum):
            return self._group_sum(node, ctx)

        if isinstance(node, Pullback):
            return self._pullback(node, ctx)

        if isinstance(node, Translate):
            return self._translate(node, ctx)

        if isinstance(node, WindowSum):
            return self._window_sum(node, ctx)

        if isinstance(node, Cases):
            return self.format.cases(self._arms(node, ctx)), _ATOM

        if isinstance(node, Dual):
            return self._dual(node, ctx), _ATOM

        assert_never(node)

    def _dual(self, node: Dual, ctx: _Context) -> str:
        """λ subscripted by the constraint's symbol, then the indices of the constraint's own frame."""
        frame = self._sorted(frozenset(self.schema.constraints[node.constraint].dims))
        return self.format.subscript(
            self._op('dual'), [self.symbols.constraint[node.constraint], *(ctx.subscript(d) for d in frame)]
        )

    def _binary(self, node: Add | Multiply | Divide | Power, ctx: _Context) -> tuple[str, int]:
        """Render a binary operator, bracketing only where the reading demands.

        A subtraction arrives as an addition of a negation and prints as the
        subtraction it was: ``a + -b`` is ``a - b`` and ``a - -b`` is ``a + b``,
        the sign folding until the right operand carries none. Subtraction
        raises the requirement on its right operand by one: ``a - (b - c)``
        and ``a - (b + c)`` need the bracket; ``a - b*c`` does not. A negated
        factor is bracketed, since ``a · -b`` is a spelling nobody reads. A
        power is atomic to everything but another power, a stacked
        superscript being ambiguous.
        """
        if isinstance(node, Divide):
            top = self._expression(node.numerator, ctx)
            bottom = self._expression(node.divisor, ctx)
            return self.format.fraction(top, bottom), _ATOM
        if isinstance(node, Power):
            base = self._expression(node.base, ctx, need=_PRECEDENCE['**'] + 1)
            return self.format.superscript(base, self._expression(node.exponent, ctx)), _PRECEDENCE['**']
        op: BinaryOperator = '*' if isinstance(node, Multiply) else '+'
        precedence = _PRECEDENCE[op]
        left = self._expression(node.left, ctx, need=precedence)
        operand = node.right
        if op == '+':
            while (unsigned := _unsigned(operand)) is not None:
                operand, op = unsigned, '-' if op == '+' else '+'
        negated_factor = op == '*' and isinstance(operand, Negate)
        need = _ATOM if negated_factor else _PRECEDENCE[op] + (1 if op == '-' else 0)
        right = self._expression(operand, ctx, need=need)
        names: dict[BinaryOperator, OperatorName] = {'*': 'cdot', '+': 'plus', '-': 'minus'}
        return self.format.joined([left, right], self._op(names[op])), precedence

    def _sum(self, node: Sum, ctx: _Context) -> tuple[str, int]:
        """A reduction over named dims: one dummy index per dim, in declaration order."""
        memberships = []
        inner = ctx
        for d in self._sorted(frozenset(node.over)):
            dummy, inner = inner.reducing(d)
            memberships.append(self._membership(d, dummy))
        domain = self.format.joined(memberships, '')
        return self.format.summation(domain, self._reduction_body(node.operand, inner)), _PRECEDENCE['+']

    def _group_sum(self, node: GroupSum, ctx: _Context) -> tuple[str, int]:
        """A sum through a relation: a dummy per consumed dim, and the row it joins on as the domain's condition."""
        direction = node.direction
        dummies: dict[str, str] = {}
        inner = ctx
        for d in direction.consumed_dims:
            dummies[d], inner = inner.reducing(d)
        conditions = list(self._grouping(direction, dummies, ctx))
        domain = (
            f'{self.format.joined([self._membership(d, dummies[d]) for d in direction.consumed_dims], "")} '
            f'{self._op("such_that")} {self.format.joined(conditions, self._op("and"))}'
        )
        return self.format.summation(domain, self._reduction_body(node.operand, inner)), _PRECEDENCE['+']

    def _pullback(self, node: Pullback, ctx: _Context) -> tuple[str, int]:
        """``at`` emits no operator of its own: it re-indexes the operand, so the read shows at the leaves."""
        return self._arithmetic(node.operand, self._pulled_back(node.direction, ctx))

    def _translate(self, node: Translate, ctx: _Context) -> tuple[str, int]:
        """``shift`` emits no operator of its own: it re-indexes the operand, so the translation shows at the leaves.

        ``edge='wrap'`` and a number are the two policies that print a symbol
        of their own; absent is the bare shift, whose vacated positions are
        absent.
        """
        policy: TranslationPolicy = 'wrap' if node.wrap else 'edge' if node.fill is not None else 'plain'
        fill = '' if node.fill is None else self._number(node.fill)
        self.noticed.policies.add(policy)
        step = _Step(node.offset, policy, fill, self._group(node.partition))
        return self._arithmetic(node.operand, ctx.translated(node.along, step))

    def _window_sum(self, node: WindowSum, ctx: _Context) -> tuple[str, int]:
        """``sum_back``: a sum over the positions behind the row, the lag written as a translation of the index."""
        policy: TranslationPolicy = 'wrap' if node.wrap else 'plain'
        step = _Step(1, policy, within=self._group(node.partition))
        self.noticed.policies.add(step.policy)
        source, inner = ctx.reducing(node.along)
        lag = f'{ctx.subscript(node.along)} {self._translation(step)} {source}'
        domain = (
            f'{source} {self._op("in")} {self.symbols.set[node.along]} {self._op("such_that")} '
            f'0 {self._op("le")} {lag} {self._op("lt")} {self._width(node.width)}'
        )
        body = self._reduction_body(node.operand, inner)
        return self.format.summation(domain, body), _PRECEDENCE['+']

    def _pulled_back(self, direction: Direction, ctx: _Context) -> _Context:
        """*ctx* with each dimension *direction* consumes read at the relation, as ``at`` re-indexes a leaf."""
        at = {r: ctx.subscript(direction.dim(r)) for r in (*direction.produced, *direction.joined)}
        for read in direction.consumed:
            ctx = ctx.pulled_back(direction.dim(read), self._relation_read(direction.name, at, read))
        return ctx

    def _grouping(self, direction: Direction, dummies: Mapping[str, str], ctx: _Context) -> list[str]:
        """The conditions a grouped sum's domain carries for one direction: what it fixes of the row it joins on.

        A direction fixes its relation's key either way, so each value column
        it fixes — consumed or produced, one lookup at the key either way — is
        that column read there. One that fixes none of them asks only that the
        row is there, because a value column it does not touch is not read,
        and a bare relation has no value column to read at all.
        """
        at = {
            **{r: dummies[direction.dim(r)] for r in direction.consumed},
            **{r: ctx.subscript(direction.dim(r)) for r in (*direction.joined, *direction.produced)},
        }
        fixed = [r for r in self.schema.relations[direction.name].value_roles if r in at]
        if not fixed:
            return [self._relation_row(direction.name, at)]
        return [f'{self._relation_read(direction.name, at, r)} {self._op("equal")} {at[r]}' for r in fixed]

    def _group(self, partition: Partition | None) -> str:
        """A ``by=`` as the superscript its translation operator carries.

        The bare index, not the subscript in force: the group is a property of
        the row being written, and a window whose operand is itself translated
        still asks which group *that row* is in.
        """
        if partition is None:
            return ''
        at = {r: self.symbols.index[partition.dim(r)] for r in (partition.along, *partition.joined)}
        return self._tuple([self._relation_read(partition.name, at, r) for r in partition.group])

    def _width(self, width: int | str) -> str:
        """``sum_back``'s ``window=``: a number, or a parameter's own symbol.

        Unsubscripted where it is named, as a translation's named offset is:
        the symbol identifies the parameter and the legend carries its dims,
        where repeating them inside a summation's domain crowds out the
        condition that domain exists to state.
        """
        if isinstance(width, str):
            return self.symbols.name[width]
        return self._number(float(width))

    def _membership(self, dim: str, index: str | None = None) -> str:
        return f'{index or self.symbols.index[dim]} {self._op("in")} {self.symbols.set[dim]}'

    def _reduction_body(self, node: Expression, ctx: _Context) -> str:
        """What sits to the right of a sum, bracketed only where it must be.

        A sum binds everything up to the next ``+`` or ``-`` at its own level,
        so an additive body needs the bracket and nothing else does — including
        a nested reduction, which is unambiguous.
        """
        additive = isinstance(node, Negate | Add)
        return self._expression(node, ctx, need=2 if additive else 0)

    # -- where strings -----------------------------------------------------

    def _predicate(self, node: Predicate, ctx: _Context, *, need: int = 0) -> str:
        text, precedence = self._where(node, ctx)
        return self.format.parenthesise(text) if precedence < need else text

    def _where(self, node: Predicate, ctx: _Context) -> tuple[str, int]:
        comparison = _WHERE_PRECEDENCE['comparison']
        if isinstance(node, BooleanLiteral):
            assert not node.value, 'an always-true mask is folded away or refused before anything prints it'
            return self._op('false'), _ATOM

        if isinstance(node, ParameterDefined):
            indexed = ctx.indexed(self.symbols.name[node.name], list(node.dims))
            if self.schema.parameters[node.name].dtype == 'bool':
                return indexed, _ATOM
            return f'{indexed} {self.format.prose(" is defined")}', comparison

        if isinstance(node, VariableDefined):
            return (
                f'{ctx.indexed(self.symbols.name[node.name], list(node.dims))} {self.format.prose(" exists")}',
                comparison,
            )

        if isinstance(node, AlignedComparison):
            left, right = self.sides(node, ctx)
            return f'{left} {right}', comparison

        if isinstance(node, TranslatedPredicate):
            moved = ctx.translated(node.along, _Step(node.offset, 'plain'))
            return self._where(node.operand.root, moved)

        if isinstance(node, PulledBackPredicate):
            return self._where(node.operand.root, self._pulled_back(node.direction, ctx))

        if isinstance(node, RelationDefined):
            return self._relation_row(node.name, self._frame_key(node.name, ctx)), comparison

        if isinstance(node, Not):
            return (
                f'{self._op("not")} {self._predicate(node.operand, ctx, need=_WHERE_PRECEDENCE["not"])}',
                _WHERE_PRECEDENCE['not'],
            )

        if isinstance(node, And):
            need = _WHERE_PRECEDENCE['and']
            sides = [self._predicate(node.left, ctx, need=need), self._predicate(node.right, ctx, need=need)]
            return self.format.joined(sides, self._op('and')), need

        if isinstance(node, Or):
            need = _WHERE_PRECEDENCE['or']
            sides = [self._predicate(node.left, ctx, need=need), self._predicate(node.right, ctx, need=need)]
            return self.format.joined(sides, self._op('or')), need

        assert_never(node)

    def sides(self, node: AlignedComparison, ctx: _Context) -> tuple[str, str]:
        """One comparison as its two sides, the relation symbol leading the right.

        Split so that a line whose whole predicate is one comparison aligns on
        the relation, as a constraint does.
        """
        if isinstance(node, ParameterComparison):
            left, right = ctx.indexed(self.symbols.name[node.name], list(node.dims)), self._literal(node.value)
        elif isinstance(node, ExpressionComparison):
            left, right = self._expression(node.left, ctx), self._expression(node.right, ctx)
        elif isinstance(node, DimensionComparison):
            if isinstance(node.value, int | float):
                self.noticed.numeric_coordinates.add(node.name)
            left, right = ctx.subscript(node.name), self._literal(node.value)
        elif isinstance(node, DimensionPosition):
            grouping = (
                None
                if node.partition is None
                else self._tuple([self._value_read(node.partition.name, c, ctx) for c in node.partition.group])
            )
            left = self._position(ctx.subscript(node.name), grouping)
            right = self._ordinal(node.name, node.position, grouping)
        elif isinstance(node, RelationComparison):
            left, right = self._value_read(node.name, node.column, ctx), self._literal(node.value)
        elif isinstance(node, RelationPairComparison):
            left = self._value_read(node.name, node.column, ctx)
            right = self._value_read(node.other, node.other_column, ctx)
        elif isinstance(node, CountComparison):
            index, inner = ctx.reducing(node.over)
            counted = self.format.set_of(
                self._membership(node.over, index), self._predicate(node.predicate.root, inner)
            )
            left, right = self.format.cardinality(counted), self._number(node.value)
        else:
            assert_never(node)
        return left, f'{self._op(_PREDICATES[node.op])} {right}'

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

    def equations(self) -> tuple[list[tuple[str, list[Line]]], Noticed]:
        """Every titled section of equations, and what printing them noticed for the legend."""
        sections = [
            ('Objective', self._objective()),
            ('Subject to', self._constraints()),
            ('Definitions', self._definitions()),
            ('Variable domains', self._variables()),
            ('Assumptions', self._assumptions()),
        ]
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
        objective = self.schema.resolved.objective
        assert objective is not None, 'validation resolves the objective the file declares'
        return [Line(label='', left=sense, right=self._expression(objective.expression, self._context()))]

    def _constraints(self) -> list[Line]:
        """Every constraint, then every curve.

        A ``piecewise:`` block restricts what its link expressions may be
        together, which is what a row does, so it prints here rather than among
        the domains — where a set prints, being a property of one variable.
        """
        return [
            *(self._constraint(name) for name in self.schema.constraints),
            *(self._piecewise(name) for name in self.schema.piecewise),
        ]

    def _constraint(self, name: str) -> Line:
        block = self.schema.constraints[name]
        constraint = self.schema.resolved.constraints[name]
        ctx = self._context(frame=block.dims)
        condition = self._condition(ctx, constraint.where)
        return Line(
            label=name,
            left=self._expression(constraint.lhs, ctx),
            right=f'{self._op(_PREDICATES[constraint.sense])} {self._expression(constraint.rhs, ctx)}',
            condition=self._quantifier(list(block.dims), condition),
        )

    def _definitions(self) -> list[Line]:
        """One line per named expression, in declaration order, defining it.

        A use prints the symbol and the block prints here, as a paper states a
        quantity it names. Every declared one prints, used or not. Inlining
        substitutes away the plain ones the math reads; a ``cases`` block has
        no single body to substitute, and an entry the math never reads has
        nowhere to be substituted *into*, so both still print.
        """
        return [self.definition(name) for name in self._defined()]

    def _defined(self) -> list[str]:
        """The named expressions that print under their own symbol: every one, or only the unsubstitutable when inlining.

        Inlining leaves a name standing only where substitution cannot reach
        it — a ``cases`` block, and an entry the objective and constraints
        never read, which is a quantity reported back rather than solved for.
        """
        if not self.inline_expressions:
            return list(self.schema.expressions)
        read = self.schema.resolved.read_by_the_math
        return [name for name, block in self.schema.expressions.items() if block.cases or name not in read]

    def definition(self, name: str) -> Line:
        """The line defining one named expression, ``symbol = body`` over its frame."""
        entry = self.schema.resolved.expressions[name]
        frame = self.frames[name]
        ctx = self._context(frame)
        body = (
            self.format.cases(self._arms(entry.body, ctx))
            if isinstance(entry.body, Cases)
            else self._expression(entry.body, ctx)
        )
        return Line(
            label=name,
            left=ctx.indexed(self.symbols.name[name], frame),
            right=f'{self._op("equal")} {body}',
            condition=self._quantifier(frame, ''),
        )

    def line(self, name: str) -> Line:
        """The one line *name* prints as: a named expression, a constraint, an assumption, a curve, or a variable's domain.

        *name* is one of the five; :func:`~math_spec.typesetting.typeset_declaration`
        refuses the rest, and a name declared as two of them. An assumption is
        looked up where the document prints it from, so a condition a curve's
        method states is a line a reader can ask for before the curve is
        written out.
        """
        if name in self.schema.expressions:
            return self.definition(name)
        if name in self.schema.constraints:
            return self._constraint(name)
        if name in self.schema.resolved.assumptions:
            return self._assumption(name)
        if name in self.schema.piecewise:
            return self._piecewise(name)
        return self._variable(name)

    def _arms(self, node: Cases, ctx: _Context) -> list[tuple[str, str]]:
        """Each region as its value and the words saying where it applies.

        Which region is the fallback is a fact about the math, so the *walk*
        says "if" or "otherwise" and a Format only stacks the rows: the last
        region is the ``otherwise``, since resolution builds it as the
        remainder of the others, and its mask is never printed.
        """
        *stated, last = node.regions
        arms = [(self._expression(region.value, ctx), self._arm_condition(region.when, ctx)) for region in stated]
        return [*arms, (self._expression(last.value, ctx), self.format.prose('otherwise'))]

    def _arm_condition(self, when: Mask, ctx: _Context) -> str:
        return f'{self.format.prose("if ")} {self._predicate(when.root, ctx, need=_WHERE_PRECEDENCE["and"])}'

    def _variables(self) -> list[Line]:
        """One line per variable, and one more for a set the variable carries.

        A ``sos:`` block restricts the *domain* — which members of a family may
        be nonzero at once — so it prints under this heading, beside the
        variable it is a property of, rather than among the constraints, where
        it would read as a row a solver holds.
        """
        sets = {block.variable: (key, block) for key, block in self.schema.sos.items()}
        lines = []
        for name, block in self.schema.variables.items():
            lines.append(self._variable(name))
            if name in sets:
                lines.append(self._sos(name, *sets[name], self._context(frame=block.dims)))
        return lines

    def _variable(self, name: str) -> Line:
        block = self.schema.variables[name]
        ctx = self._context(frame=block.dims)
        symbol = ctx.indexed(self.symbols.name[name], list(block.dims))
        where = self.schema.resolved.variables[name]
        condition = self._quantifier(list(block.dims), self._condition(ctx, where))
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
        return Line(label=name, left=left, right=right, condition=condition)

    def _sos(self, name: str, key: str, block: SosBlock, ctx: _Context) -> Line:
        """The variable's family along the set's dim, as one member of the SOS set, quantified over the other dims."""
        dims = self.schema.variables[name].dims
        family = self.format.parenthesise(ctx.indexed(self.symbols.name[name], list(dims)))
        return Line(
            label=key,
            left=self.format.subscript(family, [self._membership(block.along)]),
            right=f'{self._op("in")} {self._op("sos_set")}{block.type}',
            condition=self._quantifier([d for d in dims if d != block.along], ''),
        )

    # -- assumptions -------------------------------------------------------

    def _assumptions(self) -> list[Line]:
        """What the model assumes of its data, in the order a program carries it.

        A curve's conditions stand here with the file's own, because the
        method states them in the same language: the reader sees every
        condition the data is held to, whoever stated it.
        """
        return [self._assumption(name) for name in self.schema.resolved.assumptions]

    def _assumption(self, name: str) -> Line:
        """One assumption: the predicate over the frame both its masks name, under its ``where``."""
        assumption = self.schema.resolved.assumptions[name]
        holds, where = assumption.predicate, assumption.where
        frame = self._sorted(holds.dims | (where.dims if where is not None else frozenset()))
        ctx = self._context(frame)
        if isinstance(holds.root, AlignedComparison):
            left, right = self.sides(holds.root, ctx)
        else:
            left, right = self._predicate(holds.root, ctx), ''
        return Line(label=name, left=left, right=right, condition=self._quantifier(frame, self._condition(ctx, where)))

    def _piecewise(self, name: str) -> Line:
        """One ``piecewise:`` block as the curve it states, over the frame it states one per coordinate of.

        The links' expressions are a point, and the block says that point lies
        on the piecewise-linear locus through the breakpoints. A bounded link
        states one side of the locus instead, so there the locus prints as the
        function of the pinned link that it is and the link's own sign says
        which side.
        """
        block = self.schema.piecewise[name]
        links = self.schema.resolved.piecewise[name]
        frame = list(curve_frame(self.schema, name, block, links))
        ctx = self._context([*frame, block.over])
        locus = self._locus(block, ctx)
        bounded = next((i for i, link in enumerate(block.links) if link.sign != '=='), None)
        if bounded is None:
            left = self._tuple([self._expression(node, ctx) for node in links])
            right = f'{self._op("in")} {locus}'
        else:
            pinned = links[1 - bounded]
            left = self._expression(links[bounded], ctx)
            sign = self._op(_PREDICATES[block.links[bounded].sign])
            right = f'{sign} {self.format.apply(locus, self._expression(pinned, ctx))}'
        return Line(label=name, left=left, right=right, condition=self._quantifier(frame, ''))

    def _locus(self, block: PiecewiseBlock, ctx: _Context) -> str:
        """The set the links lie on: the curve through the breakpoints, or the hull ``convex`` relaxes it onto.

        A gate multiplies it, which is what gating a curve does — the weights
        sum to the gate, so the locus is the origin where the gate is 0 and the
        curve where it is 1.
        """
        operator = self._op('hull' if block.method == 'convex' else 'curve')
        through = self.format.subscript(operator, [self._breakpoints(block, ctx)])
        values = self.format.joined(
            [
                ctx.indexed(self.symbols.name[link.values], list(self.schema.parameters[link.values].dims))
                for link in block.links
            ],
            '',
        )
        locus = self.format.apply(through, values)
        gate = self._gate(block, ctx)
        return f'{gate} {self._op("cdot")} {locus}' if gate else locus

    def _breakpoints(self, block: PiecewiseBlock, ctx: _Context) -> str:
        """Which breakpoints the curve runs through: every one of the dimension, or the ones ``points:`` admits.

        A ``points:`` naming a boolean parameter reads as the flag it is, and
        one naming a values parameter as the rows that parameter has, which is
        the same reading a ``where`` gives either of them.
        """
        over = self._membership(block.over)
        if block.points is None:
            return over
        admitted = ParameterDefined(block.points, tuple(self.schema.parameters[block.points].dims))
        return f'{over} {self._op("such_that")} {self._predicate(admitted, ctx)}'

    def _gate(self, block: PiecewiseBlock, ctx: _Context) -> str:
        """The factor an ``activity:`` puts on the locus, or ``''`` where the block has none.

        Where the gate is a variable that does not exist at every coordinate
        the curve is built for, the factor is the gate where it exists and 1
        where it does not — the two rows the expansion writes there, because a
        variable that does not exist takes its row with it and would leave the
        curve unstated rather than ungated. ``absence: zero`` is the other
        reading and pins the curve off, which is the factor on its own.
        """
        if (activity := block.activity) is None:
            return ''
        gate = self.schema.variables[activity]
        symbol = ctx.indexed(self.symbols.name[activity], list(gate.dims))
        mask = self.schema.resolved.variables[activity]
        if mask is None or gate.absence == 'zero':
            return symbol
        where = self._predicate(mask.root, ctx, need=_WHERE_PRECEDENCE['and'])
        return self.format.cases(
            [(symbol, f'{self.format.prose("if ")} {where}'), ('1', self.format.prose('otherwise'))]
        )

    def _bound(self, ctx: _Context, value: float | str) -> str:
        if isinstance(value, str):
            return ctx.indexed(self.symbols.name[value], list(self.schema.parameters[value].dims))
        return self._number(value)

    def _sorted(self, dims: frozenset[str]) -> list[str]:
        order = list(self.schema.dimensions)
        return sorted(dims, key=order.index)

    # -- legend ------------------------------------------------------------

    def glossaries(self, noticed: Noticed) -> list[tuple[str, list[Entry]]]:
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
            self._entry(self.symbols.name[v], f'{fmt.mono(v)}{self._over(list(block.dims))}', block.description)
            for v, block in self.schema.variables.items()
        ]
        definitions = [
            self._entry(self.symbols.name[e], f'{fmt.mono(e)}{self._over(self.frames[e])}', block.description)
            for e, block in self.schema.expressions.items()
            if e in self._defined()
        ]
        groups = (('Sets', sets), ('Parameters', parameters), ('Variables', variables), ('Definitions', definitions))
        return [(title, entries) for title, entries in groups if entries]

    def _entry(self, symbol: str, what: str, description: str | None) -> Entry:
        meaning = f'{what} {self.format.dash} {self.format.escape(description)}' if description else what
        return Entry(symbol, meaning)

    def _over(self, dims: list[str]) -> str:
        if not dims:
            return ' (scalar)'
        product = self.format.joined([self.symbols.set[d] for d in dims], self._op('times'))
        return f' over {self.format.math(product)}'

    def _signature(self, name: str, lk: RelationBlock) -> str:
        """A relation in the legend: a function from its key sets to its value sets, or a relation inside the product."""
        columns = dict(lk.pairs)

        def product(roles: Iterable[str]) -> str:
            return self.format.joined([self.symbols.set[columns[r]] for r in roles], self._op('times'))

        if lk.value_roles:
            return (
                f'{self.format.upright(name)}: {product(lk.key_roles)} {self._op("maps_to")} {product(lk.value_roles)}'
            )
        return f'{self.format.upright(name)} {self._op("subset_of")} {product(lk.roles)}'

    def _coords(self, dim: str, noticed: Noticed) -> str:
        """The dimension's carried structure: each relation with a column over it, as the map or relation it is.

        The dtype is named only where an equation compared the index against a
        number, the one place "position 3" and "the coordinate 3" are both
        readings of a line.
        """
        carried = self.schema.relations_of(dim)
        clauses = []
        if dim in noticed.numeric_coordinates:
            clauses.append(f' ({self.format.mono(self.schema.dimensions[dim].dtype)} coordinates)')
        if carried:
            maps = self.format.joined([self._signature(c, lk) for c, lk in carried.items()], '')
            clauses.append(f' with {self.format.math(maps)}')
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
            applied = self.format.apply(self.format.upright('relation'), 't')
            counted = self.format.math(f't {self.format.superscript(self._op("cyclic_minus"), applied)} k')
            note = (
                f'{counted} denotes a translation counted inside the group a relation puts {self.format.math("t")} '
                f'in ({self.format.mono("shift(by=relation)")}), so a term never crosses out of its own group.'
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
                f'{self.format.mono("shift")} steps along, not the order labels sort in {dash} counted from '
                f'{self.format.math("0")}. The index itself stays the coordinate, so {index} compares against '
                f'labels and {place} against positions.'
            )
        if 'grouped' in noticed.positions:
            applied = self.format.apply(self.format.upright('relation'), 't')
            grouped = self.format.math(self.format.apply(self.format.subscript(self._op('position'), [applied]), 't'))
            group = self.format.math(self.format.subscript(self.format.script('T'), [applied]))
            notes.append(
                f'{grouped} counts within the group a relation puts {self.format.math("t")} in: the subscript names '
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
