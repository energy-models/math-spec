"""The walk: resolved AST → typeset lines. Written once, for every format.

Everything here is a decision about the *math* — where a bracket changes the
reading, which dimension a reduction binds, that a mask belongs on the ∀ rather
than in the equation, that a translation shows at the leaf it re-indexes. None
of it is about syntax, so none is duplicated per format.

The walk holds no opinion the lanes do not: names come from ``resolution``, dim
sets from ``dimensions``, helper shapes from the closed ``BUILTINS`` set, and a
helper it forgot is an ``assert_never`` rather than a blank.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, assert_never

from lpspec.language import degree
from lpspec.language.dimensions import dims_of
from lpspec.language.expression_parser import (
    ArithmeticNode,
    BinaryOperatorNode,
    ComparisonNode,
    CoordinateNode,
    DimensionNode,
    EdgeNode,
    FunctionCallNode,
    KeywordNode,
    NameNode,
    NumberNode,
    ParameterNode,
    UnaryOperatorNode,
    VariableNode,
)
from lpspec.language.resolution import expression_of, where_of
from lpspec.language.where_parser import (
    AndNode,
    BooleanLiteralNode,
    DimensionComparisonNode,
    NotNode,
    OrNode,
    ParameterComparisonNode,
    ParameterDefinedNode,
    UnresolvedComparisonNode,
    UnresolvedNameNode,
    VariableDefinedNode,
    WhereNode,
)
from lpspec.typeset.format import Entry, Line

if TYPE_CHECKING:
    import datetime

    from lpspec.language.model import Model
    from lpspec.language.resolution import Namespace
    from lpspec.typeset.format import Format
    from lpspec.typeset.symbols import Symbols

#: Operator precedence, for deciding brackets. A reduction sits at the bottom
#: with ``+``: an unbracketed sum reads as capturing whatever follows it, so as
#: a factor it has to be bracketed.
_PRECEDENCE = {'+': 1, '-': 1, '*': 2, '/': 2}
_ATOM = 5

_RELATIONS = {'==': 'equal', '<=': 'le', '>=': 'ge'}
_PREDICATES = {'==': 'equal', '!=': 'ne', '<=': 'le', '>=': 'ge', '<': 'lt', '>': 'gt'}


@dataclass(frozen=True)
class _Context:
    """What a subscript means at this point in the tree.

    ``offsets`` is how ``shift`` renders: it emits no operator of its own but
    re-indexes its operand, so the translation shows at the *leaves*.
    """

    walk: Walk
    offsets: dict[str, tuple[int, bool]] = field(default_factory=dict)
    #: dim -> the subscript that replaces its own index. ``at`` re-indexes its
    #: operand exactly as ``shift`` does, so it shows up at the *leaves* too —
    #: but through a coordinate rather than an offset, so it renders as an
    #: application, ``period(t)``, and not as arithmetic on the index.
    pullbacks: dict[str, str] = field(default_factory=dict)

    def translated(self, dim: str, by: int, *, wrap: bool) -> _Context:
        previous, previous_wrap = self.offsets.get(dim, (0, wrap))
        return _Context(self.walk, {**self.offsets, dim: (previous + by, wrap or previous_wrap)}, self.pullbacks)

    def pulled_back(self, dim: str, rendered: str) -> _Context:
        return _Context(self.walk, self.offsets, {**self.pullbacks, dim: rendered})

    def subscript(self, dim: str) -> str:
        if dim in self.pullbacks:
            return self.pullbacks[dim]
        base = self.walk.symbols.index[dim]
        by, wrap = self.offsets.get(dim, (0, False))
        if by == 0:
            return base
        forward = 'cyclic_minus' if wrap else 'minus'
        backward = 'cyclic_plus' if wrap else 'plus'
        operator = self.walk.op(forward if by > 0 else backward)
        return f'{base} {operator} {abs(by)}'

    def indexed(self, symbol: str, dims: list[str]) -> str:
        return self.walk.format.subscript(symbol, [self.subscript(d) for d in dims])


class Walk:
    """Walks a validated schema, emitting :class:`Line`s in one format.

    Stateful only in what it has *noticed* — whether any ``edge='wrap'`` appeared,
    which the legend needs in order to explain cyclic translation.
    """

    def __init__(self, schema: Model, namespace: Namespace, symbols: Symbols, fmt: Format) -> None:
        self.schema = schema
        self.namespace = namespace
        self.symbols = symbols
        self.format = fmt
        self.saw_wraparound = False

    def op(self, name: str) -> str:
        return self.format.operators[name]

    def context(self) -> _Context:
        return _Context(self)

    def number(self, value: float) -> str:
        if value == float('inf'):
            return self.op('infinity')
        if value == float('-inf'):
            return self.op('minus_infinity')
        return str(int(value)) if value == int(value) else repr(value)

    # -- arithmetic --------------------------------------------------------

    def arithmetic(self, node: ArithmeticNode, ctx: _Context, *, need: int = 0) -> str:
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
            return self.number(node.value), _ATOM if node.value >= 0 else 1

        if isinstance(node, ParameterNode):
            return ctx.indexed(self.symbols.name[node.name], list(self.schema.parameters[node.name].dims)), _ATOM

        if isinstance(node, VariableNode):
            return ctx.indexed(self.symbols.name[node.name], list(self.schema.variables[node.name].foreach)), _ATOM

        if isinstance(node, UnaryOperatorNode):
            operand = self.arithmetic(node.operand, ctx, need=2)
            return (f'{self.op("minus")}{operand}' if node.op == '-' else operand), 1

        if isinstance(node, BinaryOperatorNode):
            return self._binary(node, ctx)

        if isinstance(node, FunctionCallNode):
            return self._call(node, ctx)

        if isinstance(node, (NameNode, KeywordNode, DimensionNode, CoordinateNode, EdgeNode)):
            msg = f'{type(node).__name__} reached the typesetter; resolve the expression first.'
            raise AssertionError(msg)

        assert_never(node)

    def _binary(self, node: BinaryOperatorNode, ctx: _Context) -> tuple[str, int]:
        """Render a binary operator, bracketing only where the reading demands.

        Subtraction raises the requirement on its right operand by one:
        ``a - (b - c)`` and ``a - (b + c)`` need the bracket; ``a - b*c``
        does not.

        ``degree.check_binary`` first, so the typesetter renders exactly what
        the language accepts and says so in the language's own sentence: ``**``
        and a quadratic product parse but are refused, and printing them would
        typeset math no lane can build.
        """
        degree.check_binary(node)
        if node.op == '/':
            top = self.arithmetic(node.left, ctx)
            bottom = self.arithmetic(node.right, ctx)
            return self.format.fraction(top, bottom), _ATOM
        precedence = _PRECEDENCE[node.op]
        left = self.arithmetic(node.left, ctx, need=precedence)
        right = self.arithmetic(node.right, ctx, need=precedence + (1 if node.op == '-' else 0))
        names = {'*': 'cdot', '+': 'plus', '-': 'minus'}
        return self.format.joined([left, right], self.op(names[node.op])), precedence

    def _call(self, node: FunctionCallNode, ctx: _Context) -> tuple[str, int]:
        """Render a helper: a translation at the leaves, or a summation.

        ``shift`` is one node, so the render reads the edge *policy* rather
        than the spelling: only ``edge='wrap'`` is cyclic. ``at`` is not a
        reduction — it re-indexes its operand, so like ``shift`` it emits no
        operator and the substitution appears at the leaves; falling through to
        the summation would render it as a sum over the fine dim, silently the
        wrong equation.
        """
        if node.name == 'shift':
            dim = node.kwargs['over']
            amount = node.kwargs['by']
            assert isinstance(dim, DimensionNode)
            assert isinstance(amount, NumberNode)
            wrap = isinstance(node.kwargs.get('edge'), EdgeNode)
            self.saw_wraparound = self.saw_wraparound or wrap
            return self._arithmetic(node.args[0], ctx.translated(dim.name, int(amount.value), wrap=wrap))

        if node.name == 'at':
            onto = node.kwargs['onto']
            assert isinstance(onto, DimensionNode)
            by = node.kwargs['by']
            assert isinstance(by, CoordinateNode)
            mapping = self.format.apply(self.format.upright(by.name), ctx.subscript(onto.name))
            return self._arithmetic(node.args[0], ctx.pulled_back(by.into, mapping))

        over = node.kwargs['over']
        assert isinstance(over, DimensionNode)
        domain = self.membership(over.name)
        if (by := node.kwargs.get('group_by')) is not None:
            assert isinstance(by, CoordinateNode)
            mapping = self.format.apply(self.format.upright(by.name), self.symbols.index[over.name])
            domain = f'{domain} {self.op("such_that")} {mapping} {self.op("equal")} {ctx.subscript(by.into)}'
        return self.format.summation(domain, self.reduction_body(node.args[0], ctx)), _PRECEDENCE['+']

    def membership(self, dim: str) -> str:
        return f'{self.symbols.index[dim]} {self.op("in")} {self.symbols.set[dim]}'

    def reduction_body(self, node: ArithmeticNode, ctx: _Context) -> str:
        """What sits to the right of a sum, bracketed only where it must be.

        A sum binds everything up to the next ``+`` or ``-`` at its own level,
        so an additive body needs the bracket and nothing else does — including
        a nested reduction, which is unambiguous. The precedence rule would
        bracket that too, and a renderer that brackets everything is one nobody
        trusts to bracket the thing that matters.
        """
        additive = isinstance(node, UnaryOperatorNode) or (
            isinstance(node, BinaryOperatorNode) and node.op in ('+', '-')
        )
        return self.arithmetic(node, ctx, need=2 if additive else 0)

    # -- where strings -----------------------------------------------------

    def where(self, node: WhereNode, ctx: _Context, *, need: int = 0) -> str:
        text, precedence = self._where(node, ctx)
        return self.format.parenthesise(text) if precedence < need else text

    def _where(self, node: WhereNode, ctx: _Context) -> tuple[str, int]:
        if isinstance(node, BooleanLiteralNode):
            return self.op('true' if node.value else 'false'), _ATOM

        if isinstance(node, ParameterDefinedNode):
            dims = list(self.schema.parameters[node.name].dims)
            return f'{ctx.indexed(self.symbols.name[node.name], dims)} {self.format.prose(" is defined")}', 2

        if isinstance(node, VariableDefinedNode):
            dims = list(self.schema.variables[node.name].foreach)
            return f'{ctx.indexed(self.symbols.name[node.name], dims)} {self.format.prose(" exists")}', 2

        if isinstance(node, ParameterComparisonNode):
            dims = list(self.schema.parameters[node.name].dims)
            left = ctx.indexed(self.symbols.name[node.name], dims)
            return f'{left} {self.op(_PREDICATES[node.op])} {self.literal(node.value)}', 2

        if isinstance(node, DimensionComparisonNode):
            return f'{ctx.subscript(node.name)} {self.op(_PREDICATES[node.op])} {self.literal(node.value)}', 2

        if isinstance(node, NotNode):
            return f'{self.op("not")} {self.where(node.operand, ctx, need=2)}', 2

        if isinstance(node, AndNode):
            sides = [self.where(node.left, ctx, need=1), self.where(node.right, ctx, need=1)]
            return self.format.joined(sides, self.op('and')), 1

        if isinstance(node, OrNode):
            sides = [self.where(node.left, ctx, need=1), self.where(node.right, ctx, need=1)]
            return self.format.joined(sides, self.op('or')), 0

        if isinstance(node, (UnresolvedNameNode, UnresolvedComparisonNode)):
            msg = f'{type(node).__name__} reached the typesetter; resolve the where string first.'
            raise AssertionError(msg)

        assert_never(node)

    def literal(self, value: float | str | datetime.date) -> str:
        return self.number(value) if isinstance(value, (int, float)) else self.format.prose(str(value))

    def conjoined(self, ctx: _Context, *nodes: WhereNode | None) -> str:
        parts = [self.where(n, ctx, need=1) for n in nodes if n is not None]
        return self.format.joined(parts, self.op('and')) if parts else ''

    def quantifier(self, dims: list[str], condition: str) -> str:
        if not dims and not condition:
            return ''
        over = self.format.joined([self.membership(d) for d in dims], '')
        if not condition:
            return f'{self.op("forall")} {over}'
        if not over:
            return f'{self.format.prose("where ")} {condition}'
        return f'{self.op("forall")} {over} {self.op("such_that")} {condition}'

    # -- declarations ------------------------------------------------------

    def objectives(self) -> list[Line]:
        """One line per objective, with its implied reduction made explicit.

        An objective sums each term over every dim it carries; the reduction is
        implied by the declaration, so it is spelled out rather than assumed.
        """
        lines = []
        for name, block in self.schema.objectives.items():
            sense = self.op('minimize' if block.sense == 'minimize' else 'maximize')
            context = f"objective '{name}'"
            node = expression_of(block.expression, self.schema, self.namespace, context)
            assert not isinstance(node, ComparisonNode)
            ctx = self.context()
            dims = self._sorted(dims_of(node, self.schema, context))
            body = self.reduction_body(node, ctx) if dims else self.arithmetic(node, ctx)
            if dims:
                domain = self.format.joined([self.membership(d) for d in dims], '')
                body = self.format.summation(domain, body)
            lines.append(Line(label=name, left=sense, right=body))
        return lines

    def constraints(self) -> list[Line]:
        lines = []
        for name, block in self.schema.constraints.items():
            context = f"constraint '{name}'"
            node = expression_of(block.expression, self.schema, self.namespace, context)
            if not isinstance(node, ComparisonNode):
                msg = f'{context}: expected a comparison, got {type(node).__name__}'
                raise AssertionError(msg)
            ctx = self.context()
            condition = self.conjoined(ctx, where_of(block.where, self.namespace, context))
            lines.append(
                Line(
                    label=name,
                    left=self.arithmetic(node.left, ctx),
                    right=f'{self.op(_RELATIONS[node.op])} {self.arithmetic(node.right, ctx)}',
                    condition=self.quantifier(list(block.foreach), condition),
                )
            )
        return lines

    def variables(self) -> list[Line]:
        lines = []
        for name, block in self.schema.variables.items():
            ctx = self.context()
            symbol = ctx.indexed(self.symbols.name[name], list(block.foreach))
            where = where_of(block.where, self.namespace, f"variable '{name}'", self_variable=name)
            condition = self.quantifier(list(block.foreach), self.conjoined(ctx, where))
            lower, upper = block.bounds.lower, block.bounds.upper

            if block.binary:
                left, right = symbol, f'{self.op("in")} {self.op("binary_set")}'
            else:
                below, above = lower == float('-inf'), upper == float('inf')
                if below and above:
                    domain = self.op('integers' if block.integer else 'reals')
                    left, right = symbol, f'{self.op("in")} {domain}'
                elif below:
                    left, right = symbol, f'{self.op("le")} {self._bound(ctx, upper)}'
                elif above:
                    left, right = symbol, f'{self.op("ge")} {self._bound(ctx, lower)}'
                else:
                    left = f'{self._bound(ctx, lower)} {self.op("le")} {symbol}'
                    right = f'{self.op("le")} {self._bound(ctx, upper)}'
                if block.integer and not (below and above):
                    right = f'{right}, {symbol} {self.op("in")} {self.op("integers")}'
            lines.append(Line(label=name, left=left, right=right, condition=condition))
        return lines

    def _bound(self, ctx: _Context, value: float | str) -> str:
        if isinstance(value, str):
            return ctx.indexed(self.symbols.name[value], list(self.schema.parameters[value].dims))
        return self.number(value)

    def _sorted(self, dims: frozenset[str]) -> list[str]:
        order = list(self.schema.dimensions)
        return sorted(dims, key=order.index)

    # -- legend ------------------------------------------------------------

    def glossaries(self) -> list[tuple[str, list[Entry]]]:
        fmt = self.format
        sets = [
            Entry(
                symbol=self.symbols.set[d],
                name=f'index {fmt.math(self.symbols.index[d])} --- {fmt.mono(d)}',
                detail=self._coords(d),
                description=self.symbols.description.get(d, ''),
            )
            for d in self.schema.dimensions
        ]
        parameters = [
            Entry(
                symbol=self.symbols.name[p],
                name=fmt.mono(p),
                detail=self._over(list(block.dims)),
                description=self.symbols.description.get(p, ''),
            )
            for p, block in self.schema.parameters.items()
        ]
        variables = [
            Entry(
                symbol=self.symbols.name[v],
                name=fmt.mono(v),
                detail=self._over(list(block.foreach)),
                description=self.symbols.description.get(v, ''),
            )
            for v, block in self.schema.variables.items()
        ]
        return [group for group in (('Sets', sets), ('Parameters', parameters), ('Variables', variables)) if group[1]]

    def _over(self, dims: list[str]) -> str:
        if not dims:
            return ' (scalar)'
        product = self.format.joined([self.symbols.set[d] for d in dims], self.op('times'))
        return f' over {self.format.math(product)}'

    def _coords(self, dim: str) -> str:
        """The dimension's carried structure, groupable maps before plain labels.

        A targeted coordinate renders as the map it is (``bus: G ↦ B``); an
        inline label space has no target set to point at, so it renders as the
        label it is (``period — a label on T``).
        """
        block = self.schema.dimensions[dim]
        clauses = []
        if block.targeted:
            maps = self.format.joined(
                [
                    f'{self.format.upright(c)}: {self.symbols.set[dim]} {self.op("maps_to")} {self.symbols.set[target]}'
                    for c, target in block.targeted.items()
                ],
                '',
            )
            clauses.append(f' with {self.format.math(maps)}')
        if block.labels:
            named = self.format.joined([self.format.upright(c) for c in block.labels], '')
            plural = 's' if len(block.labels) > 1 else ''
            clauses.append(f' carrying label{plural} {self.format.math(named)}')
        return ''.join(clauses)

    def wraparound_note(self) -> str:
        cyclic = self.format.math(f't {self.op("cyclic_minus")} k')
        return (
            f'{cyclic} denotes cyclic translation: index {self.format.math("t-k")} taken modulo the size of '
            f'the dimension ({self.format.mono("roll")}). Plain {self.format.math("t-k")} '
            f'({self.format.mono("shift")}) has no wraparound --- terms translated past the edge are '
            f'simply absent.'
        )
