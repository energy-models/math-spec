# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The program: what a file declares, with names resolved and shapes fixed.

The second public state, and the one a consumer reads. A :class:`Program` is
every declaration a file makes and no data at all;
:func:`~math_spec.lowering.to_program` is the only thing that builds one, so
nothing here re-checks a hand-built one.

Node and declaration classes are matched with ``isinstance``. The rules a
node's structure does not show are :func:`children` and :func:`fan_in`; the
questions over the walk are :func:`walk` and the filters beside it. A
resolved ``where`` arrives as a :class:`Mask`. Frozen dataclasses only — no
execution logic, and nothing imported from a consumer. How a consumer reads
one: ``docs/reference/language/reading.md``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from functools import cached_property
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, NamedTuple, assert_never, get_args

import math_spec.model as _model
from math_spec._expression_parser import ComparisonOperator
from math_spec.errors import did_you_mean

if TYPE_CHECKING:
    import datetime
    from collections.abc import Iterator


#: What ``math_spec.program`` promises a consumer, sorted.
__all__ = [
    'QUADRATIC_POSITIONS',
    'Add',
    'AndNode',
    'At',
    'AtLeastTwo',
    'BooleanLiteralNode',
    'Cases',
    'Check',
    'ConnectiveWhereNode',
    'Constant',
    'ConstraintDeclaration',
    'ConstraintSense',
    'Contiguous',
    'Curved',
    'Derivation',
    'DimensionComparisonNode',
    'DimensionDeclaration',
    'DimensionDtype',
    'DimensionPositionNode',
    'Divide',
    'Dual',
    'Expression',
    'ExpressionNode',
    'FanIn',
    'FirstOf',
    'Footprint',
    'GroupSum',
    'Increasing',
    'LastOf',
    'LookupComparisonNode',
    'LookupDeclaration',
    'LookupDefinedNode',
    'LookupPairComparisonNode',
    'Mask',
    'MaskOf',
    'Multiply',
    'Negate',
    'NotNode',
    'ObjectiveDeclaration',
    'ObjectiveSense',
    'OrNode',
    'Parameter',
    'ParameterComparisonNode',
    'ParameterDeclaration',
    'ParameterDefinedNode',
    'ParameterDtype',
    'PiecewiseDeclaration',
    'Power',
    'PredicateOperator',
    'Program',
    'QuadraticPosition',
    'Region',
    'SosDeclaration',
    'Sum',
    'Translate',
    'TypedPredicateNode',
    'Variable',
    'VariableAbsence',
    'VariableDeclaration',
    'VariableDefinedNode',
    'VariableType',
    'WhereNode',
    'Window',
    'carries_variable',
    'check_message',
    'children',
    'divisor_parameters',
    'fan_in',
    'is_quadratic',
    'parameters_of',
    'quotients',
    'variables_of',
    'walk',
]


ConstraintSense = ComparisonOperator

#: How a shape operator's output rows relate to its input slots, answered by
#: :func:`fan_in` for every node.
FanIn = Literal['one-to-one', 'many-to-one', 'one-to-many']
ObjectiveSense = Literal['minimize', 'maximize']

#: Where a degree-2 product may stand in the math a solver sees. An objective
#: and a constraint take ``variable * variable``; a bound and a ``piecewise:``
#: link are read affinely (``math_spec.degree``), so those are the two. A
#: post-solve-grade entry (:func:`math_spec.degree.is_postsolve_grade`) is not
#: a position here: its body reaches no solver.
QuadraticPosition = Literal['objective', 'constraint']

#: The set form, for a consumer pinning its own table against the vocabulary:
#: ``QUADRATIC_POSITIONS <= handled`` is how one says it covers every position
#: and hears about it when the language admits another.
QUADRATIC_POSITIONS = frozenset(get_args(QuadraticPosition))

#: What a dimension's labels are — the language's own vocabulary
#: (:data:`~math_spec.model.DimensionDtype`), under the name a consumer reads
#: it by.
DimensionDtype = _model.DimensionDtype

#: What a parameter's values are (:data:`~math_spec.model.ParameterDtype`).
ParameterDtype = _model.ParameterDtype

#: What a masked variable's non-existence means
#: (:data:`~math_spec.model.VariableAbsence`).
VariableAbsence = _model.VariableAbsence

#: A variable's domain (:data:`~math_spec.model.VariableDomain`), under the
#: name this module's field carries.
VariableType = _model.VariableDomain


# --------------------------------------------------------------------------
# Affine expressions
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Expression:
    """Base class for expressions over variables and parameters.

    Affine everywhere but where ``math_spec.degree`` admits a :class:`Multiply`
    of two variable-carrying operands; no node records which position that is.
    """

    def __add__(self: ExpressionNode, other: ExpressionNode) -> ExpressionNode:
        return Add(self, other)

    def __mul__(self: ExpressionNode, other: ExpressionNode) -> ExpressionNode:
        return Multiply(self, other)


@dataclass(frozen=True)
class Constant(Expression):
    """A scalar constant."""

    value: float


@dataclass(frozen=True)
class Parameter(Expression):
    """A parameter reference — contributes to the constant part."""

    name: str


@dataclass(frozen=True)
class Variable(Expression):
    """A variable reference — one term per existing variable row."""

    name: str


@dataclass(frozen=True)
class Dual(Expression):
    """A constraint's dual — its shadow price, read after the solve.

    Reached only from a post-solve-grade entry
    (:func:`math_spec.degree.is_postsolve_grade`): a dual exists once the program
    is solved and nowhere in the math a solver
    ingests, so no node reached from the objective or a constraint carries
    one. One value per coordinate of the
    named constraint's own ``foreach`` frame, which is what :func:`fan_in`
    answers ``one-to-one`` for — the leaf reshapes nothing, like a parameter.
    """

    constraint: str


@dataclass(frozen=True)
class Negate(Expression):
    operand: ExpressionNode


@dataclass(frozen=True)
class Add(Expression):
    left: ExpressionNode
    right: ExpressionNode


@dataclass(frozen=True)
class Multiply(Expression):
    """Product of two operands.

    Affine where at least one factor is variable-free; degree 2 where neither
    is, which ``math_spec.degree`` admits in a :data:`QuadraticPosition` alone.
    A node reached from a post-solve-grade entry
    (:func:`math_spec.degree.is_postsolve_grade`) carries no such bound: that
    body may multiply any number of variables, the degree rules lifting for
    arithmetic nothing ingests.
    """

    left: ExpressionNode
    right: ExpressionNode


@dataclass(frozen=True)
class Power(Expression):
    """``base ** exponent``.

    In the math a solver ingests, both sides are variable-free: the language
    refuses a variable anywhere under it (``math_spec.degree``), so wherever
    it appears in the program a solver sees it is degree 0 and folds to one
    number per coordinate like any other parameter arithmetic. A node reached
    from a post-solve-grade entry (:func:`math_spec.degree.is_postsolve_grade`) carries no
    such guarantee — that body may raise to a variable exponent
    (``growth ** spare``), the degree rules lifting for arithmetic nothing
    ingests.
    """

    base: ExpressionNode
    exponent: ExpressionNode


@dataclass(frozen=True)
class Divide(Expression):
    """Quotient ``numerator / divisor``.

    In the math a solver ingests, the divisor is variable-free
    (``math_spec.degree``). A node reached from a post-solve-grade entry
    (:func:`math_spec.degree.is_postsolve_grade`) carries no such guarantee — that body
    may divide by a variable (``sum(p * cost) / sum(p)``), the degree rules
    lifting for arithmetic nothing ingests.
    """

    numerator: ExpressionNode
    divisor: ExpressionNode


@dataclass(frozen=True)
class Sum(Expression):
    """Sum ``operand`` over the named dims, removing them from the result."""

    operand: ExpressionNode
    over: tuple[str, ...]


@dataclass(frozen=True)
class GroupSum(Expression):
    """Sum ``operand`` through coordinates declared on dim ``over``.

    ``coordinate`` names lookups carried by dim ``over`` whose values are
    labels of the matching dim in ``into``; the result replaces ``over`` with
    all of them. The two tuples are the same length and their order pairs
    them: several coordinates are one grouping into a product of targets,
    consumed in a single join.
    """

    operand: ExpressionNode
    over: str
    coordinate: tuple[str, ...]
    into: tuple[str, ...]


@dataclass(frozen=True)
class At(Expression):
    """Read ``operand`` through a lookup — the adjoint of :class:`GroupSum`.

    Same mapping table, walked the other way: ``GroupSum`` consumes ``over``
    and produces ``into``, this consumes ``into`` and produces ``over``. The
    join fans out, many ``over`` labels sharing one ``into`` tuple.
    """

    operand: ExpressionNode
    over: str
    coordinate: tuple[str, ...]
    into: tuple[str, ...]


@dataclass(frozen=True)
class Translate(Expression):
    """Re-index along one dimension: the result at *t* is ``operand`` at *t - offset*.

    ``wrap`` is ``edge='wrap'`` in the file: periodic, and stated on every
    node. ``fill`` is what an acyclic shift leaves behind: ``None`` leaves the
    vacated positions absent, so the row drops; a number makes them present
    and contribute it. Always ``None`` under ``wrap``.

    ``offset`` is an integer, or the name of an integer parameter that does
    not depend on ``dimension`` and carries its sign in the values.

    ``partition`` names a lookup over ``dimension``, and the translation then
    happens inside each group it makes: the neighbour is the one before in
    the same group, the edge is the group's, and a wrap closes each group onto
    itself. A coordinate the lookup sends nowhere reaches nothing.
    """

    operand: ExpressionNode
    dimension: str
    offset: int | str
    wrap: bool
    fill: float | None = None
    partition: str | None = None


@dataclass(frozen=True)
class Window(Expression):
    """Sum ``operand`` over a trailing window along one dimension.

    The result at *t* is the sum of the operand at every position from
    *t - width + 1* through *t*, so a width of 1 is the operand itself. The
    dimension survives: this replicates terms onto the positions that can see
    them rather than reducing anything away.

    ``width`` is a whole number, or the name of an integer parameter when the
    window differs per entity — a minimum up time, a rolling budget, a delivery
    horizon. A named width may not depend on the dimension being summed over.

    ``wrap`` says whether the window reaches around the start of the axis
    instead of stopping short at it, and is stated on every node.

    ``partition`` names a lookup over that dimension, and the window then stops
    at each group's edge. Positions are counted inside the group, so a
    coordinate the lookup places nowhere reaches nothing — not even itself.
    """

    operand: ExpressionNode
    dimension: str
    width: int | str
    wrap: bool
    partition: str | None = None


@dataclass(frozen=True)
class Region:
    """One region of a :class:`Cases`: where it applies, and the value there.

    ``when`` is stated on every region; the one the file wrote as
    ``otherwise:`` carries the negation of the others.
    """

    when: Mask
    value: ExpressionNode


@dataclass(frozen=True)
class Cases(Expression):
    """A value defined by region — exactly one region applies at each coordinate.

    The regions are disjoint and total, so a consumer adds them rather than
    ranking them. Not a shape operator: every region spans the dims the
    expression does.
    """

    regions: tuple[Region, ...]


#: Every expression node, as one type. The set is *closed* — nothing registers
#: into it — so a consumer that walks it ends in ``assert_never`` and a node
#: added without a branch is a type error at the site that must grow one,
#: rather than a ``LanguageError`` raised at the first model that uses it.
#: ``Expression`` stays the base class the nodes inherit and the operators are
#: declared on; this is what a walk *takes*.
ExpressionNode = (
    Constant
    | Parameter
    | Variable
    | Dual
    | Negate
    | Add
    | Multiply
    | Power
    | Divide
    | Sum
    | GroupSum
    | At
    | Translate
    | Window
    | Cases
)


def fan_in(expression: ExpressionNode) -> FanIn:
    """How *expression*'s output rows relate to its input slots.

    For the absence rules, both classes other than ``'one-to-one'`` sum
    several input slots into an output row.
    """
    if isinstance(expression, (Sum, GroupSum)):
        return 'many-to-one'
    if isinstance(expression, Window):
        return 'one-to-many'
    if isinstance(
        expression,
        (Constant, Parameter, Variable, Dual, Negate, Add, Multiply, Power, Divide, At, Translate, Cases),
    ):
        return 'one-to-one'
    assert_never(expression)


def children(expression: ExpressionNode) -> tuple[ExpressionNode, ...]:
    """The sub-expressions of *expression* — what every walk recurses through."""
    if isinstance(expression, Negate):
        return (expression.operand,)
    if isinstance(expression, (Add, Multiply)):
        return (expression.left, expression.right)
    if isinstance(expression, Divide):
        return (expression.numerator, expression.divisor)
    if isinstance(expression, (Sum, GroupSum, At, Translate, Window)):
        return (expression.operand,)
    if isinstance(expression, Cases):
        return tuple(region.value for region in expression.regions)
    return ()


# --------------------------------------------------------------------------
# Declarations
# --------------------------------------------------------------------------


class LookupDeclaration(NamedTuple):
    """One declared lookup over a dimension, of either kind.

    Exactly one of ``target`` and ``dtype`` is set. A *targeted* lookup's
    values are labels of ``target``, checked for containment once the dim
    tables exist — which keeps a mistyped label from silently dropping its
    terms in the join that places them — and it is what ``sum(by=)`` lands
    terms on. A *label space* owns its values, typed by ``dtype`` the way a
    dimension's labels are: it is read for selection and rendering, and
    resolution refuses to group into one, so no expression node reaches it.
    """

    name: str
    target: str | None
    dtype: DimensionDtype | None = None


@dataclass(frozen=True)
class DimensionDeclaration:
    """A dimension and the lookups its labels carry, of both kinds."""

    lookups: tuple[LookupDeclaration, ...] = ()
    #: What the labels are, as the file declares them. A dimension is read from
    #: whatever table carries it, so the declared type is what that column is
    #: checked against — the same claim ``ParameterDeclaration.dtype`` makes
    #: about a value column, one axis over.
    dtype: DimensionDtype = 'str'

    @property
    def maps(self) -> list[str]:
        """Every map over the dimension, targeted and label-space alike.

        What binding needs a relation for: both kinds are read by a ``where``
        and both arrive the same way, and only the targeted ones have a label
        set to be checked against.
        """
        return sorted(lk.name for lk in self.lookups)

    @property
    def targets(self) -> dict[str, str]:
        """Each targeted map over the dimension, to the dimension its values are labels of.

        The question every consumer of a ``by=`` asks, and asked here so it has
        one answer: an operator grouping through a lookup names the target as
        the dim it lands on, and a partition array is named for it so an amount
        declared over the group's own dim can be read through it.
        """
        return {lk.name: lk.target for lk in self.lookups if lk.target is not None}


@dataclass(frozen=True)
class MaskOf:
    """A ``bool`` parameter true wherever *values* has a row.

    The mask a ``points:`` naming one of the block's own breakpoints derives:
    the curve runs as far as its values do. ``values`` is the name the file
    wrote, so a refusal about the mask can say it.
    """

    block: str
    values: str


@dataclass(frozen=True)
class FirstOf:
    """A ``bool`` parameter marking, per curve, the first breakpoint *mask* admits."""

    block: str
    mask: str


@dataclass(frozen=True)
class LastOf:
    """Its sibling for the last breakpoint."""

    block: str
    mask: str


#: How an emitted parameter is filled — closed, so a consumer binding data
#: dispatches on it and a kind added later is a type error at that match.
#: Each names the ``piecewise:`` block whose expansion emitted the parameter.
Derivation = MaskOf | FirstOf | LastOf


@dataclass(frozen=True)
class Increasing:
    """*parameter* is strictly increasing along *over* within each curve — the x-axis a method sorts by."""

    parameter: str
    over: str


@dataclass(frozen=True)
class Curved:
    """*y* over *x* bends, along *over*, the way *curvature* says.

    That is the shape the method is exact for. ``either`` is the hull's
    weaker condition: any single bend, so only a mixed curve fails it.
    """

    x: str
    y: str
    over: str
    curvature: _model.Curvature


@dataclass(frozen=True)
class AtLeastTwo:
    """Each curve has at least two breakpoints — every position along *over*, or those *mask* admits."""

    over: str
    mask: str | None


@dataclass(frozen=True)
class Contiguous:
    """*mask* admits one consecutive run of at least one breakpoint per curve."""

    mask: str
    #: The breakpoint parameter the mask was derived from, where it was — the
    #: name the file wrote, and the one a refusal names.
    values: str | None


#: What a ``piecewise:`` block assumes of the numbers it is bound to. The data
#: decides whether each holds, so the language names the condition with its
#: subjects and its sentence (:func:`check_message`), and the consumer holding
#: the numbers checks. Closed, like :data:`Derivation`.
Check = Increasing | Curved | AtLeastTwo | Contiguous


@dataclass(frozen=True)
class PiecewiseDeclaration:
    """A ``piecewise:`` block, kept as the facts a consumer binding its data reads.

    The expansion lowered the links into constraints and emitted the
    parameters it needs — each of those says how it is filled, on its own
    :attr:`ParameterDeclaration.derivation`. What is left here is the curve
    and what the block assumes of it.

    Attributes:
        over: The breakpoint dimension.
        method: How the weights are restricted.
        breakpoints: The links' values parameters, in link order.
        checks: What the block assumes of the numbers, each carrying its own
            subjects, for the consumer holding them to check.
    """

    over: str
    method: _model.PiecewiseMethod
    breakpoints: tuple[str, ...]
    checks: tuple[Check, ...]


def check_message(block: str, pw: PiecewiseDeclaration, check: Check) -> str:
    """The sentence a consumer raises when the data bound to *block* fails *check*.

    The language's own wording, so every consumer refuses in the same words;
    a consumer appends what it saw.
    """
    ctx = f"piecewise '{block}'"
    match check:
        case Increasing(parameter, over):
            return (
                f"{ctx}: method: {pw.method} requires strictly increasing breakpoints in '{parameter}' along '{over}'"
            )
        case Curved(x, y, over, curvature):
            shape = 'a single bend' if curvature == 'either' else f'a {curvature} curve'
            return (
                f"{ctx}: method: {pw.method} is exact only for {shape}, and '{y}' over '{x}' along "
                f"'{over}' is not one, so the answer is wrong rather than loose. Use method: adjacency "
                f'or sos2, which take a curve of any shape.'
            )
        case AtLeastTwo():
            return (
                f'{ctx}: method: lp needs at least two breakpoints per curve — the method *is* its segment '
                f'lines, so a curve with no segment states nothing and leaves the bounded link on its own '
                f'bound. Use method: adjacency, sos2 or convex, which pin it to the points it does have.'
            )
        case Contiguous(mask, values):
            return (
                f"{ctx}: points: '{values if values is not None else mask}' must mark a consecutive run of at "
                f'least one breakpoint per curve — the chord row joins a breakpoint to the one before it, and '
                f"the domain rows sit on the curve's own first and last."
            )
        case _:
            assert_never(check)


@dataclass(frozen=True)
class ParameterDeclaration:
    """Shape declaration; data is bound at execution time by name.

    ``dtype`` is what the declaration claims the values are, and a consumer
    binding data refuses a column that is not it — so the *declaration* is
    what is read, rather than whatever the column happens to hold.
    """

    dims: tuple[str, ...]
    dtype: ParameterDtype = 'float'
    #: How this parameter is filled where a ``piecewise:`` expansion emitted
    #: it, or ``None`` for one the file declares. Who supplies the data
    #: follows: the caller binds a declared parameter, and an emitted one is
    #: built from the block's own breakpoints the way its derivation says.
    derivation: Derivation | None = None


@dataclass(frozen=True)
class VariableDeclaration:
    dims: tuple[str, ...]
    where: Mask | None = None
    lower: ExpressionNode = field(default_factory=lambda: Constant(float('-inf')))
    upper: ExpressionNode = field(default_factory=lambda: Constant(float('inf')))
    variable_type: VariableType = 'continuous'
    absence: VariableAbsence = 'undefined'


@dataclass(frozen=True)
class ConstraintDeclaration:
    """``lhs sense rhs`` for each coord combination of ``dims``.

    Either side may carry variables and constants alike; which side a
    consumer gathers them onto is its own arrangement and not stated here.
    ``where`` masks out coord combinations (row absence, like variables).
    """

    dims: tuple[str, ...]
    lhs: ExpressionNode
    sense: ConstraintSense
    rhs: ExpressionNode
    where: Mask | None = None


@dataclass(frozen=True)
class SosDeclaration:
    """One special-ordered set per coordinate of the variable's ``foreach`` minus ``over``.

    The only declaration that adds neither a column nor a row: it names
    columns a consumer already has and says what may be nonzero among them. Which
    dims those are is the variable's own ``foreach`` and is read from it: a
    copy here would be a second home for a fact
    (:meth:`Program.variable`).

    ``big_m`` caps the linking coefficient a consumer without the concept
    reformulates with, and is ``None`` where the variable's own upper bound is
    the only cap.
    """

    variable: str
    over: str
    sos_type: Literal[1, 2]
    big_m: float | None = None


@dataclass(frozen=True)
class ObjectiveDeclaration:
    """Objective — scalar, every reduction in it one the file wrote."""

    sense: ObjectiveSense
    expression: ExpressionNode


@dataclass(frozen=True)
class Footprint:
    """Which of the language's constructs one program uses.

    A subset, never the whole: an empty field says this program does not use
    the construct.

    Attributes:
        quadratic: Each position a product of two variable-carrying operands
            stands in; empty is affine throughout.
        variable_types: Every domain declared.
        sos_types: The order of each special-ordered set declared.
        shapes: Every expression node kind that appears.
    """

    quadratic: frozenset[QuadraticPosition]
    variable_types: frozenset[VariableType]
    sos_types: frozenset[Literal[1, 2]]
    shapes: frozenset[type[ExpressionNode]]


def _declared[Declaration](items: Mapping[str, Declaration], name: str, kind: str) -> Declaration:
    """The declaration called *name*, or a ``KeyError`` naming the near miss."""
    try:
        return items[name]
    except KeyError:
        raise KeyError(f"unknown {kind} '{name}'. " + did_you_mean(name, list(items))) from None


@dataclass(frozen=True, kw_only=True)
class Program:
    """A complete declarative description of a mathematical program, with no data in it.

    Every group of declarations is keyed by the name the file wrote, in the
    order it wrote them, and is read-only: the mappings are wrapped at
    construction, so a consumer cannot rewrite what another consumer reads.
    A whole program is not hashable — the declarations and expression nodes
    inside it are, which is what dedup and memoisation ask for.
    """

    parameters: Mapping[str, ParameterDeclaration]
    variables: Mapping[str, VariableDeclaration]
    constraints: Mapping[str, ConstraintDeclaration]
    #: ``None`` where the file declares no objective — a feasibility problem,
    #: whose answer is whether the constraints can be met at all.
    objective: ObjectiveDeclaration | None
    dimensions: Mapping[str, DimensionDeclaration] = MappingProxyType({})
    sos: Mapping[str, SosDeclaration] = MappingProxyType({})
    #: Each ``piecewise:`` block the file wrote, as facts — see
    #: :class:`PiecewiseDeclaration`.
    piecewise: Mapping[str, PiecewiseDeclaration] = MappingProxyType({})
    #: Declared ``expressions:``, lowered. Not part of the program a solver
    #: sees — none of them builds a row — but lowered with it, so a file whose
    #: named expression is outside the language is refused by every verb that
    #: reads the file rather than only by the one that reads the expression.
    named_expressions: Mapping[str, ExpressionNode] = MappingProxyType({})

    def __post_init__(self) -> None:
        """Seal every group, so a program handed out cannot be written to."""
        for f in fields(self):
            group = getattr(self, f.name)
            if isinstance(group, Mapping):
                object.__setattr__(self, f.name, MappingProxyType(dict(group)))

    def _by_position(self) -> Iterator[tuple[QuadraticPosition, tuple[ExpressionNode, ...]]]:
        """The row-building expressions, grouped by the position they stand in."""
        yield 'objective', (self.objective.expression,) if self.objective is not None else ()
        yield 'constraint', tuple(side for c in self.constraints.values() for side in (c.lhs, c.rhs))

    @property
    def expressions(self) -> tuple[ExpressionNode, ...]:
        """Every expression a row is built from — the objective and both sides of each constraint.

        A :attr:`named_expressions` entry builds no row and is not among them.
        """
        return tuple(e for _, group in self._by_position() for e in group)

    @cached_property
    def footprint(self) -> Footprint:
        """Which constructs this program uses — walked once, then held."""
        return Footprint(
            quadratic=frozenset(
                position for position, group in self._by_position() if any(is_quadratic(e) for e in group)
            ),
            variable_types=frozenset(v.variable_type for v in self.variables.values()),
            sos_types=frozenset(s.sos_type for s in self.sos.values()),
            shapes=frozenset(type(node) for node in walk(*self.expressions)),
        )

    def dimension(self, name: str) -> DimensionDeclaration:
        return _declared(self.dimensions, name, 'dimension')

    @property
    def lookups(self) -> tuple[tuple[str, LookupDeclaration], ...]:
        """Every lookup in the program, targeted and label-space alike, with the dimension it is over."""
        return tuple((dimension, lk) for dimension, d in self.dimensions.items() for lk in d.lookups)

    def parameter(self, name: str) -> ParameterDeclaration:
        return _declared(self.parameters, name, 'parameter')

    def variable(self, name: str) -> VariableDeclaration:
        return _declared(self.variables, name, 'variable')


# --------------------------------------------------------------------------
# Walks, and the questions asked through them
# --------------------------------------------------------------------------


def walk(*expressions: ExpressionNode) -> Iterator[ExpressionNode]:
    """Every node under *expressions*, each expression itself included, parents first.

    The traversal every *question* about a program is a filter of — which names
    it mentions, whether a variable stands under it, which divisions it
    contains. One generator rather than that five-line recursion once per
    question: how a program is traversed is one fact, so a node kind
    :func:`children` learns to descend into reaches every caller at once
    rather than the callers that remembered.
    """
    for expression in expressions:
        yield expression
        yield from walk(*children(expression))


def is_quadratic(expression: ExpressionNode) -> bool:
    """Whether *expression* contains a product of two variable-carrying operands.

    A structural question over the program, and unrelated consumers ask it —
    what a solver must support, which declarations to build last, whether this
    form can be represented at all — so it is answered once here beside the
    other walks rather than once per consumer in its own terms.

    Whether a degree *may be written* is the language's verdict, and this is
    not a second opinion on it: by the time a program exists the question is
    which shape the expression has, and the program is what is in hand to
    answer it.
    """
    return any(
        isinstance(node, Multiply) and all(carries_variable(side) for side in (node.left, node.right))
        for node in walk(expression)
    )


def carries_variable(expression: ExpressionNode) -> bool:
    """Whether a variable appears anywhere under *expression*."""
    return any(isinstance(node, Variable) for node in walk(expression))


def parameters_of(*expressions: ExpressionNode) -> frozenset[str]:
    """Every parameter named anywhere under *expressions*."""
    return frozenset(node.name for node in walk(*expressions) if isinstance(node, Parameter))


def variables_of(*expressions: ExpressionNode) -> frozenset[str]:
    """Every variable named anywhere under *expressions*."""
    return frozenset(node.name for node in walk(*expressions) if isinstance(node, Variable))


def quotients(*expressions: ExpressionNode) -> tuple[Divide, ...]:
    """Every division under *expressions*, each kept whole.

    The divisor and the numerator answer different questions and one consumer
    needs them paired: a divisor is judged against the rows the declaration
    builds *narrowed by the variables in its own numerator*, which the flat
    :func:`divisor_parameters` cannot say.
    """
    return tuple(node for node in walk(*expressions) if isinstance(node, Divide))


def divisor_parameters(*expressions: ExpressionNode) -> frozenset[str]:
    """Every parameter named anywhere in a divisor under *expressions*."""
    return frozenset().union(*(parameters_of(q.divisor) for q in quotients(*expressions)))


# ---------------------------------------------------------------------------
# the resolved where vocabulary
# ---------------------------------------------------------------------------


PredicateOperator = Literal['<=', '>=', '==', '!=', '<', '>']


@dataclass(frozen=True)
class BooleanLiteralNode:
    value: bool


@dataclass(frozen=True)
class ParameterDefinedNode:
    """True wherever the named parameter is non-null and finite.

    ``dims`` is the parameter's own, copied off the declaration during
    resolution; every leaf below that names a declaration carries its dims
    (or ``over``) the same way.
    """

    name: str
    dims: tuple[str, ...]


@dataclass(frozen=True)
class VariableDefinedNode:
    """True at the coordinates where the named variable exists."""

    name: str
    dims: tuple[str, ...]


@dataclass(frozen=True)
class ParameterComparisonNode:
    """Compare a parameter against a literal, element-wise."""

    name: str
    op: PredicateOperator
    value: float | str
    dims: tuple[str, ...]


@dataclass(frozen=True)
class DimensionComparisonNode:
    """Compare a dimension's own coordinates against a literal."""

    name: str
    op: PredicateOperator
    value: float | str | datetime.date


@dataclass(frozen=True)
class DimensionPositionNode:
    """Compare where a row sits along a dimension against a position — ``position(snapshot) == 0``.

    Both sides are integers, negative counting from the end. With ``by`` the
    position is counted within each group the lookup makes.
    """

    name: str
    op: PredicateOperator
    position: int
    by: str | None = None


@dataclass(frozen=True)
class LookupComparisonNode:
    """Compare a lookup's values against a literal — ``period_of == 2030``.

    ``over`` is the dimension the lookup maps out of.
    """

    name: str
    over: str
    op: PredicateOperator
    value: float | str | datetime.date


@dataclass(frozen=True)
class LookupPairComparisonNode:
    """Compare two lookups over one dimension — ``from != to``, row by row on that dimension's table."""

    name: str
    other: str
    over: str
    op: PredicateOperator


@dataclass(frozen=True)
class LookupDefinedNode:
    """True where the named lookup has a value — a null says the label belongs to no group."""

    name: str
    over: str


@dataclass(frozen=True)
class NotNode:
    operand: WhereNode


@dataclass(frozen=True)
class AndNode:
    left: WhereNode
    right: WhereNode


@dataclass(frozen=True)
class OrNode:
    left: WhereNode
    right: WhereNode


#: Every resolved predicate node — what a lowered mask's ``root`` is built of.
#: The parser's ``Unresolved*`` nodes are not members: they live with the
#: grammar in :mod:`math_spec._where_parser`, and resolution rewrites them away
#: before anything here is asked.
WhereNode = (
    BooleanLiteralNode
    | DimensionPositionNode
    | ParameterDefinedNode
    | VariableDefinedNode
    | ParameterComparisonNode
    | DimensionComparisonNode
    | LookupComparisonNode
    | LookupPairComparisonNode
    | LookupDefinedNode
    | NotNode
    | AndNode
    | OrNode
)

#: Every predicate resolution has typed: it names a declaration and the kind is
#: settled. Resolution passes these straight through, having nothing left to
#: decide about them.
TypedPredicateNode = (
    ParameterComparisonNode
    | ParameterDefinedNode
    | VariableDefinedNode
    | DimensionComparisonNode
    | DimensionPositionNode
    | LookupComparisonNode
    | LookupPairComparisonNode
    | LookupDefinedNode
)

#: The boolean connectives — the only where nodes carrying other where nodes,
#: and so the only place a walk over a predicate recurses. The grammar builds
#: these classes directly, over leaves still unresolved, so a pre-resolution
#: tree shares them — the transient impurity resolution normalizes away.
ConnectiveWhereNode = NotNode | AndNode | OrNode


def _atoms(where: WhereNode) -> Iterator[TypedPredicateNode]:
    """Every node in *where* that reads a declaration, connectives removed.

    A boolean literal yields nothing.

    Raises:
        AssertionError: An unresolved node reached the walk.
    """
    if isinstance(where, NotNode):
        yield from _atoms(where.operand)
    elif isinstance(where, (AndNode, OrNode)):
        yield from _atoms(where.left)
        yield from _atoms(where.right)
    elif isinstance(where, BooleanLiteralNode):
        return
    elif isinstance(where, TypedPredicateNode):
        yield where
    else:
        msg = f'{type(where).__name__} reached a predicate walk unresolved.'
        raise AssertionError(msg)


def _atom_dims(atom: TypedPredicateNode) -> frozenset[str]:
    """One leaf's dims — the rule :attr:`Mask.dims` is the union of.

    A parameter or variable leaf carries its own dims off the declaration; a
    comparison on a dimension is read through that dimension, and a lookup
    through the dimension it maps out of — the dim it leaves, not the one it
    lands in. Separate from the union because the load-time frame check
    reports per leaf. Closed by ``assert_never``: a predicate node added
    without a reading is a type error here, at the one place that has to grow
    a branch, rather than a wrong dim set at the first model to use it.
    """
    match atom:
        case ParameterComparisonNode() | ParameterDefinedNode() | VariableDefinedNode():
            return frozenset(atom.dims)
        case DimensionComparisonNode() | DimensionPositionNode():
            return frozenset({atom.name})
        case LookupComparisonNode() | LookupPairComparisonNode() | LookupDefinedNode():
            return frozenset({atom.over})
        case _:
            assert_never(atom)


def _atom_names(atom: TypedPredicateNode) -> frozenset[str]:
    """One leaf's declarations, its dimension apart — the rule :attr:`Mask.names_read` is the union of.

    A comparison on a dimension names no declaration — a coordinate is not
    data to feed — and a lookup pair names both maps it compares.
    ``assert_never``-closed for the reason :func:`_atom_dims` is: a predicate
    node added without a reading is a type error at this one branch rather
    than a name silently dropped at the first model to use it.
    """
    match atom:
        case (
            ParameterComparisonNode()
            | ParameterDefinedNode()
            | VariableDefinedNode()
            | LookupComparisonNode()
            | LookupDefinedNode()
        ):
            return frozenset({atom.name})
        case LookupPairComparisonNode():
            return frozenset({atom.name, atom.other})
        case DimensionComparisonNode() | DimensionPositionNode():
            return frozenset()
        case _:
            assert_never(atom)


def _conjuncts(where: WhereNode) -> tuple[WhereNode, ...]:
    """The flatten rule behind :attr:`Mask.conjuncts` — the one home of the split.

    ``a AND b AND c`` gives three, and a predicate that is not an ``AND`` gives
    itself. The walk stops at the first node that is not an ``AND``: the
    conjuncts of ``a AND (b OR c)`` are ``a`` and ``b OR c``, and of
    ``NOT (a AND b)`` the single ``NOT`` — neither an ``OR`` nor a ``NOT`` is a
    claim the predicate makes on its own, so neither is split.
    """
    if isinstance(where, AndNode):
        return _conjuncts(where.left) + _conjuncts(where.right)
    return (where,)


def _fold(node: WhereNode) -> WhereNode:
    """*node* with every connective a literal or a double negation decides evaluated away.

    ``X AND True`` is ``X``, ``X OR True`` is every row, ``X AND False`` is
    none, ``NOT True`` is ``False`` and ``NOT NOT X`` is ``X``. What survives
    is a predicate over data, or the one literal the whole mask reduces to —
    the invariant :class:`Mask` applies at construction, so it holds wherever
    a mask is built.
    """
    if isinstance(node, NotNode):
        operand = _fold(node.operand)
        if isinstance(operand, BooleanLiteralNode):
            return BooleanLiteralNode(not operand.value)
        if isinstance(operand, NotNode):
            return operand.operand
        return NotNode(operand)
    if isinstance(node, AndNode):
        left, right = _fold(node.left), _fold(node.right)
        if isinstance(left, BooleanLiteralNode):
            return right if left.value else left
        if isinstance(right, BooleanLiteralNode):
            return left if right.value else right
        return AndNode(left, right)
    if isinstance(node, OrNode):
        left, right = _fold(node.left), _fold(node.right)
        if isinstance(left, BooleanLiteralNode):
            return left if left.value else right
        if isinstance(right, BooleanLiteralNode):
            return right if right.value else left
        return OrNode(left, right)
    return node


@dataclass(frozen=True)
class Mask:
    """A resolved ``where`` and the questions the language answers about it.

    ``root`` is the predicate a consumer dispatches on with ``isinstance``;
    every question below is derived from it. Construction folds, so a boolean
    literal stands at the root or nowhere in it, and refuses an unresolved
    tree.

    Attributes:
        root: The resolved predicate the mask restricts rows by, folded.
    """

    root: WhereNode

    def __post_init__(self) -> None:
        object.__setattr__(self, 'root', _fold(self.root))
        _ = self.atoms  # the walk is the refusal, and runs after the fold

    @cached_property
    def atoms(self) -> tuple[TypedPredicateNode, ...]:
        """The mask's leaves, connectives removed — the one walk the other questions read.

        Held rather than re-walked: construction takes this walk anyway, to
        refuse an unresolved tree, and a mask cannot change afterwards.
        """
        return tuple(_atoms(self.root))

    @property
    def conjuncts(self) -> tuple[WhereNode, ...]:
        """The predicates the mask joins with ``AND`` — its ``AND`` spine flattened, stopping at an ``OR`` or a ``NOT``."""
        return _conjuncts(self.root)

    @property
    def names_read(self) -> frozenset[str]:
        """The parameters, lookups and variables the mask names."""
        return frozenset(name for atom in self.atoms for name in _atom_names(atom))

    @property
    def dims(self) -> frozenset[str]:
        """The dims the mask is read at — the union of what each leaf carries.

        Empty for a mask over nothing but literals. Read off the leaves, which
        resolution stamped with their declarations' dims, so a predicate built
        from resolved pieces answers exactly as a declaration's own does.
        """
        return frozenset(dim for atom in self.atoms for dim in _atom_dims(atom))

    def __invert__(self) -> Mask:
        """The mask admitting exactly the rows this one refuses — construction folds a double negation or a literal flip."""
        return Mask(NotNode(self.root))

    def __and__(self, other: Mask) -> Mask:
        """Both masks at once — construction absorbs a literal side rather than burying it."""
        return Mask(AndNode(self.root, other.root))

    def __or__(self, other: Mask) -> Mask:
        """Either mask — construction absorbs a literal side rather than burying it."""
        return Mask(OrNode(self.root, other.root))
