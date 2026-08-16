"""The walk: resolved AST → typeset lines. Written once, for every format.

Everything here is a decision about the *math* — where a bracket changes the
reading, which dimension a reduction binds, that a mask belongs on the ∀ rather
than in the equation, that a translation shows at the leaf it re-indexes. None
of it is about syntax, so none is duplicated per format.

The walk holds no opinion the lanes do not: names come from ``resolution``, dim
sets from ``dimensions``, operator shapes from the closed ``BUILTINS`` set, and a
operator it forgot is an ``assert_never`` rather than a blank.
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
    DimensionNode,
    EdgeNode,
    FunctionCallNode,
    KeywordNode,
    LookupNode,
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
    LookupComparisonNode,
    LookupDefinedNode,
    LookupPairComparisonNode,
    NotNode,
    OrNode,
    ParameterComparisonNode,
    ParameterDefinedNode,
    UnresolvedComparisonNode,
    UnresolvedNameNode,
    VariableDefinedNode,
    WhereNode,
)
from lpspec.typeset.format import Entry, Glossary, Line

if TYPE_CHECKING:
    import datetime

    from lpspec.language.model import Model, SosBlock
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


#: Edge policy -> the operator pair that renders it, backward then forward.
#: Three policies get three spellings because they are three different
#: equations at the boundary — the vacated row dropped, wrapped, or filled.
_TRANSLATIONS = {
    'plain': ('minus', 'plus'),
    'wrap': ('cyclic_minus', 'cyclic_plus'),
    'edge': ('edge_minus', 'edge_plus'),
}


def _amount(node: ArithmeticNode) -> int | str:
    """``shift``'s ``by=``: a signed number, or the name of a parameter.

    A negated literal parses as a unary minus over a number rather than as a
    negative one, so reading the ``NumberNode`` alone both aborted on ``by=-1``
    and left the forward direction of every translation operator unreachable.

    A named offset comes back as its name. It is always backward — the language
    refuses ``by=-p``, so the direction lives in the data — and it renders as
    the parameter's own symbol rather than as a number.
    """
    if isinstance(node, ParameterNode):
        return node.name
    if isinstance(node, UnaryOperatorNode):
        assert isinstance(node.operand, NumberNode)
        return -int(node.operand.value) if node.op == '-' else int(node.operand.value)
    assert isinstance(node, NumberNode)
    return int(node.value)


def _added(left: int | str, right: int | str) -> int:
    """Two absorbed steps as one. Only numbers absorb, which ``absorbs`` decides."""
    assert isinstance(left, int) and isinstance(right, int)
    return left + right


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
    policy: str
    fill: str = ''

    def absorbs(self, other: _Step) -> bool:
        """Whether *other* applied under this one is still a single translation.

        Only an identical policy composes: two cyclic steps are one cyclic step
        of their sum, and two identical fills likewise. A cyclic step under an
        acyclic one is genuinely two, and folding them into ``t ⊖ 2`` claims the
        outer step wraps when it drops.
        """
        if isinstance(self.by, str) or isinstance(other.by, str):
            return False  # a named offset is not a number, so two do not add
        return (self.policy, self.fill) == (other.policy, other.fill)


@dataclass(frozen=True)
class _Context:
    """What a subscript means at this point in the tree.

    ``offsets`` is how ``shift`` renders: it emits no operator of its own but
    re-indexes its operand, so the translation shows at the *leaves*. Its steps
    are outermost first, the order they apply to the index — the outer shift of
    ``shift(shift(x, by=a), by=b)`` moves ``t`` to ``t - b``, and the inner one
    reads ``x`` from there.
    """

    walk: Walk
    offsets: dict[str, tuple[_Step, ...]] = field(default_factory=dict)
    #: dim -> the subscript that replaces its own index. ``at`` re-indexes its
    #: operand exactly as ``shift`` does, so it shows up at the *leaves* too —
    #: but through a coordinate rather than an offset, so it renders as an
    #: application, ``period(t)``, and not as arithmetic on the index.
    pullbacks: dict[str, str] = field(default_factory=dict)

    def translated(self, dim: str, step: _Step) -> _Context:
        steps = self.offsets.get(dim, ())
        merged = (
            (*steps[:-1], _Step(_added(steps[-1].by, step.by), step.policy, step.fill))
            if steps and steps[-1].absorbs(step)
            else (*steps, step)
        )
        return _Context(self.walk, {**self.offsets, dim: merged}, self.pullbacks)

    def pulled_back(self, dim: str, rendered: str) -> _Context:
        return _Context(self.walk, self.offsets, {**self.pullbacks, dim: rendered})

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
            text = f'{base} {self.walk.translation(step)} {amount}'
            translated = True
        return text

    def indexed(self, symbol: str, dims: list[str]) -> str:
        return self.walk.format.subscript(symbol, [self.subscript(d) for d in dims])


class Walk:
    """Walks a validated schema, emitting :class:`Line`s in one format.

    Stateful only in what it has *noticed* — which edge policies appeared,
    which the legend needs in order to explain the symbols they print.
    """

    def __init__(self, schema: Model, namespace: Namespace, symbols: Symbols, fmt: Format) -> None:
        self.schema = schema
        self.namespace = namespace
        self.symbols = symbols
        self.format = fmt
        self.policies: set[str] = set()

    def op(self, name: str) -> str:
        return self.format.operators[name]

    def translation(self, step: _Step) -> str:
        """The operator for one translation, carrying its fill where it has one."""
        backward, forward = _TRANSLATIONS[step.policy]
        # a named offset is always backward: `by=-p` is refused, so the sign is
        # in the data and the operator cannot read it off the call
        operator = self.op(backward if isinstance(step.by, str) or step.by > 0 else forward)
        return self.format.subscript(operator, [step.fill]) if step.fill else operator

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

        if isinstance(node, (NameNode, KeywordNode, DimensionNode, LookupNode, EdgeNode)):
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
        """Render an operator: a translation at the leaves, or a summation.

        ``shift`` is one node carrying all three edge policies, and each gets
        its own translation operator. ``at`` is not a reduction — it re-indexes
        its operand, so like ``shift`` it emits no operator and the
        substitution appears at the leaves; falling through to the summation
        would render it as a sum over the fine dim, silently the wrong
        equation.
        """
        if node.name == 'shift':
            dim = node.kwargs['over']
            assert isinstance(dim, DimensionNode)
            step = self._step(_amount(node.kwargs['by']), node.kwargs.get('edge'))
            self.policies.add(step.policy)
            return self._arithmetic(node.args[0], ctx.translated(dim.name, step))

        if node.name == 'at':
            by = node.kwargs['by']
            assert isinstance(by, LookupNode)
            mapping = self.format.apply(self.format.upright(by.name), ctx.subscript(by.dimension))
            return self._arithmetic(node.args[0], ctx.pulled_back(by.into, mapping))

        if (by := node.kwargs.get('by')) is not None:
            assert isinstance(by, LookupNode)
            domain = self.membership(by.dimension)
            mapping = self.format.apply(self.format.upright(by.name), self.symbols.index[by.dimension])
            domain = f'{domain} {self.op("such_that")} {mapping} {self.op("equal")} {ctx.subscript(by.into)}'
        else:
            over = node.kwargs['over']
            assert isinstance(over, DimensionNode)
            domain = self.membership(over.name)
        return self.format.summation(domain, self.reduction_body(node.args[0], ctx)), _PRECEDENCE['+']

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
        return _Step(by, 'edge', self.number(edge.value))

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
            block = self.schema.parameters[node.name]
            indexed = ctx.indexed(self.symbols.name[node.name], list(block.dims))
            if block.dtype == 'bool':
                # a bool is the predicate, so there is no word to add — absence reads as false anyway
                return indexed, _ATOM
            return f'{indexed} {self.format.prose(" is defined")}', 2

        if isinstance(node, VariableDefinedNode):
            dims = list(self.schema.variables[node.name].foreach)
            return f'{ctx.indexed(self.symbols.name[node.name], dims)} {self.format.prose(" exists")}', 2

        if isinstance(node, ParameterComparisonNode):
            dims = list(self.schema.parameters[node.name].dims)
            left = ctx.indexed(self.symbols.name[node.name], dims)
            return f'{left} {self.op(_PREDICATES[node.op])} {self.literal(node.value)}', 2

        if isinstance(node, DimensionComparisonNode):
            return f'{ctx.subscript(node.name)} {self.op(_PREDICATES[node.op])} {self.literal(node.value)}', 2

        if isinstance(node, LookupComparisonNode):
            applied = self.format.apply(self.format.upright(node.name), ctx.subscript(node.over))
            return f'{applied} {self.op(_PREDICATES[node.op])} {self.literal(node.value)}', 2

        if isinstance(node, LookupPairComparisonNode):
            index = ctx.subscript(node.over)
            left = self.format.apply(self.format.upright(node.name), index)
            right = self.format.apply(self.format.upright(node.other), index)
            return f'{left} {self.op(_PREDICATES[node.op])} {right}', 2

        if isinstance(node, LookupDefinedNode):
            applied = self.format.apply(self.format.upright(node.name), ctx.subscript(node.over))
            return f'{applied} {self.format.prose(" is defined")}', 2

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

    def objective(self) -> list[Line]:
        """The objective's line, with its implied reduction made explicit.

        An objective sums each term over every dim it carries; the reduction is
        implied by the declaration, so it is spelled out rather than assumed.
        The line carries no label: the block has no name, and the section
        heading already says what it is.
        """
        block = self.schema.objective
        if block is None:
            return []
        sense = self.op('minimize' if block.sense == 'minimize' else 'maximize')
        context = 'the objective'
        node = expression_of(block.expression, self.schema, self.namespace, context)
        assert not isinstance(node, ComparisonNode)
        ctx = self.context()
        dims = self._sorted(dims_of(node, self.schema, context))
        body = self.reduction_body(node, ctx) if dims else self.arithmetic(node, ctx)
        if dims:
            domain = self.format.joined([self.membership(d) for d in dims], '')
            body = self.format.summation(domain, body)
        return [Line(label='', left=sense, right=body)]

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
        """One line per variable, and one more for a set the variable carries.

        A ``sos:`` block restricts the *domain* — which members of a family may
        be nonzero at once — so it prints under this heading, beside the
        variable it is a property of, rather than among the constraints, where
        it would read as a row a solver holds.
        """
        sets = {block.variable: block for block in self.schema.sos.values()}
        lines = []
        for name, block in self.schema.variables.items():
            ctx = self.context()
            symbol = ctx.indexed(self.symbols.name[name], list(block.foreach))
            where = where_of(block.where, self.namespace, f"variable '{name}'", self_variable=name)
            condition = self.quantifier(list(block.foreach), self.conjoined(ctx, where))
            lower, upper = block.bounds.lower, block.bounds.upper

            if block.domain == 'binary':
                left, right = symbol, f'{self.op("in")} {self.op("binary_set")}'
            else:
                below, above = lower == float('-inf'), upper == float('inf')
                if below and above:
                    domain = self.op('integers' if block.domain == 'integer' else 'reals')
                    left, right = symbol, f'{self.op("in")} {domain}'
                elif below:
                    left, right = symbol, f'{self.op("le")} {self._bound(ctx, upper)}'
                elif above:
                    left, right = symbol, f'{self.op("ge")} {self._bound(ctx, lower)}'
                else:
                    left = f'{self._bound(ctx, lower)} {self.op("le")} {symbol}'
                    right = f'{self.op("le")} {self._bound(ctx, upper)}'
                if block.domain == 'integer' and not (below and above):
                    right = f'{right}, {symbol} {self.op("in")} {self.op("integers")}'
            lines.append(Line(label=name, left=left, right=right, condition=condition))
            if name in sets:
                lines.append(self._sos(name, sets[name], ctx))
        return lines

    def _sos(self, name: str, block: SosBlock, ctx: _Context) -> Line:
        """``(x_{s,o})_{o ∈ O} ∈ SOS2  ∀ s ∈ S`` — the family, and its order.

        The set runs along one dim and there is one of it per coordinate of the
        rest, which is exactly the split between the subscript on the family
        and the quantifier beside it.
        """
        foreach = self.schema.variables[name].foreach
        family = self.format.parenthesise(ctx.indexed(self.symbols.name[name], list(foreach)))
        return Line(
            label=f'{name} sos',
            left=self.format.subscript(family, [self.membership(block.over)]),
            right=f'{self.op("in")} {self.op("sos_set")}{block.type}',
            condition=self.quantifier([d for d in foreach if d != block.over], ''),
        )

    def _bound(self, ctx: _Context, value: float | str) -> str:
        if isinstance(value, str):
            return ctx.indexed(self.symbols.name[value], list(self.schema.parameters[value].dims))
        return self.number(value)

    def _sorted(self, dims: frozenset[str]) -> list[str]:
        order = list(self.schema.dimensions)
        return sorted(dims, key=order.index)

    # -- legend ------------------------------------------------------------

    def glossaries(self) -> list[Glossary]:
        fmt = self.format
        sets = [
            Entry(
                symbol=self.symbols.set[d],
                name=f'index {fmt.math(self.symbols.index[d])} --- {fmt.mono(d)}',
                detail=self._coords(d),
                description=block.description or '',
            )
            for d, block in self.schema.dimensions.items()
        ]
        parameters = [
            Entry(
                symbol=self.symbols.name[p],
                name=fmt.mono(p),
                detail=self._over(list(block.dims)),
                description=block.description or '',
            )
            for p, block in self.schema.parameters.items()
        ]
        variables = [
            Entry(
                symbol=self.symbols.name[v],
                name=fmt.mono(v),
                detail=self._over(list(block.foreach)),
                description=block.description or '',
            )
            for v, block in self.schema.variables.items()
        ]
        groups = (Glossary('Sets', sets), Glossary('Parameters', parameters), Glossary('Variables', variables))
        return [group for group in groups if group.entries]

    def _over(self, dims: list[str]) -> str:
        if not dims:
            return ' (scalar)'
        product = self.format.joined([self.symbols.set[d] for d in dims], self.op('times'))
        return f' over {self.format.math(product)}'

    def _coords(self, dim: str) -> str:
        """The dimension's carried structure, groupable maps before plain labels.

        A targeted lookup renders as the map it is (``bus_of: G ↦ B``); a
        label-space lookup has no target set to point at, so it renders as the
        label it is (``period — a label on T``).
        """
        targeted = self.schema.targeted_of(dim)
        labels = self.schema.labels_of(dim)
        clauses = []
        if targeted:
            maps = self.format.joined(
                [
                    f'{self.format.upright(c)}: {self.symbols.set[dim]} {self.op("maps_to")} {self.symbols.set[target]}'
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

    def translation_notes(self) -> list[str]:
        """A sentence for each translation symbol the model actually printed.

        Only those: a legend explaining a symbol that is nowhere on the page is
        a dead end, and plain ``t-k`` needs no note until something else stands
        beside it.
        """
        notes = []
        if 'wrap' in self.policies:
            cyclic = self.format.math(f't {self.op("cyclic_minus")} k')
            notes.append(
                f'{cyclic} denotes cyclic translation: index {self.format.math("t-k")} taken modulo the size of '
                f'the dimension ({self.format.mono("roll")}). Plain {self.format.math("t-k")} '
                f'({self.format.mono("shift")}) has no wraparound --- terms translated past the edge are '
                f'simply absent.'
            )
        if 'edge' in self.policies:
            filled = self.format.math(f't {self.format.subscript(self.op("edge_minus"), ["v"])} k')
            notes.append(
                f'{filled} denotes translation with {self.format.math("v")} standing where index '
                f'{self.format.math("t-k")} leaves the dimension ({self.format.mono("shift(edge=v)")}), so the row '
                f'at that boundary is built and carries {self.format.math("v")} rather than being dropped.'
            )
        return notes
