# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The program: what a file declares, with names resolved and shapes fixed.

A :class:`Program` is a complete declarative description of a mathematical
program — every declaration a file makes, and no data in it at all. Data is
bound against these declarations by whatever builds the model;
:func:`~math_spec.lowering.to_program` is what produces one from a spec.

**It is the second public state, and the one a consumer reads.** A
:class:`~math_spec.model.Spec` is what the file *says*; a program is what it
*means*, with macros expanded, names typed, operators resolved to nodes and
every dim rule already checked. Consumers dispatch on these nodes and read
them; nothing here is built by hand, so what ships beside the nodes is the
walk (:func:`children`), not builders. A program is trusted by construction:
:func:`~math_spec.lowering.to_program` is the only thing that builds one, and
nothing checks one assembled by hand. The language's refusals happen at load,
where the file and its author are, and a program put together some other way
is outside that guarantee rather than inside a pass restating it.

What a consumer needs from this module falls in three, and only the middle
one has to be *called* to be got right:

- **Types to match on** — every node and declaration class, the
  :data:`ExpressionNode` union, and the ``Literal`` vocabularies. A backend
  dispatches on these and calls none of them.
- **Rules to call** — :func:`children` and :func:`fan_in`. Neither is visible
  in a node's own structure, so a consumer deriving them derives them wrongly
  the day a node is added.
- **Questions over the walk** — :func:`walk` and the filters beside it. Each is
  a line a consumer could write; they are here so two consumers cannot write it
  differently.

A mask is the language's own resolved ``where`` node
(:mod:`math_spec.where_parser`) rather than a second set spelling the same
predicates — one home, so the two cannot come to disagree about what a
comparison is. Its literals are already decided: a mask admitting every row
arrives as ``None`` and one admitting none as ``BooleanLiteralNode(False)``, so
that node stands at the root of a mask or nowhere in it, and no consumer needs
a constant folder of its own to agree with the others about which rows exist.

The declaration vocabularies are the language's own for the same reason
(:mod:`math_spec.model`): a ``dtype``, a domain and an absence reading cross
into a program by a cast, and a member added to one spelling alone would
arrive as a string no consumer's branch recognises.

Frozen dataclasses only — no execution logic, and nothing imported from a
consumer.

Expressions support operator sugar so programs read naturally in Python:

balance = GroupSum(Variable("p"), over="generator", coordinate=("bus",), into=("bus",)) - Parameter("load")
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from functools import cached_property
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, NamedTuple, assert_never, get_args

import math_spec.model as _model
from math_spec.errors import did_you_mean
from math_spec.where_parser import AndNode, atoms, dims_read, names_read

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from math_spec.where_parser import TypedPredicateNode, WhereNode


#: What ``math_spec.program`` promises. The package's ``__all__`` exports this
#: *module* rather than its names, so this is where a consumer's imports are
#: pinned. Sorted, like the package's own: the grouping a reader wants is in
#: ``tests/test_public_surface.py``, which derives this set from the module
#: rather than restating it, so the two cannot come apart.
__all__ = [
    'QUADRATIC_POSITIONS',
    'Add',
    'At',
    'AtLeastTwo',
    'Cases',
    'Check',
    'ComparisonOperator',
    'Constant',
    'ConstraintDeclaration',
    'ConstraintSense',
    'Contiguous',
    'Curved',
    'Derivation',
    'DimensionDeclaration',
    'DimensionDtype',
    'Divide',
    'Expression',
    'ExpressionNode',
    'FanIn',
    'FirstOf',
    'Footprint',
    'GroupSum',
    'Increasing',
    'LastOf',
    'LookupDeclaration',
    'Mask',
    'MaskOf',
    'Multiply',
    'Negate',
    'ObjectiveDeclaration',
    'ObjectiveSense',
    'Parameter',
    'ParameterDeclaration',
    'ParameterDtype',
    'PiecewiseDeclaration',
    'Power',
    'Program',
    'QuadraticPosition',
    'Region',
    'SosDeclaration',
    'Sum',
    'Translate',
    'Variable',
    'VariableAbsence',
    'VariableDeclaration',
    'VariableType',
    'Window',
    'carries_variable',
    'check_message',
    'children',
    'conjuncts',
    'divisor_parameters',
    'fan_in',
    'is_quadratic',
    'parameters_of',
    'quotients',
    'variables_of',
    'walk',
]


ConstraintSense = Literal['==', '<=', '>=']

#: How a shape operator's output rows relate to its input slots — the absence
#: rules' own distinction, as a field. ``sum``, ``sum(by=)`` and a window put
#: several input slots into one output row, so an absent slot there is one
#: summand fewer and the row stands; a pullback and a translation are one slot
#: for one, so an absent input *is* the output and takes the row with it.
#: Answered by :func:`fan_in` for every node, because a consumer keeping its
#: own list of which is which would be deciding a rule the language has
#: already decided.
FanIn = Literal['one-to-one', 'many-to-one', 'one-to-many']
ObjectiveSense = Literal['minimize', 'maximize']

#: Where a degree-2 product may stand. An objective and a constraint take
#: ``variable * variable``; a bound, a named expression and a ``piecewise:``
#: link are read affinely (``math_spec.degree``), so those are the two.
QuadraticPosition = Literal['objective', 'constraint']

#: The set form, for a consumer pinning its own table against the vocabulary:
#: ``QUADRATIC_POSITIONS <= handled`` is how one says it covers every position
#: and hears about it when the language admits another.
QUADRATIC_POSITIONS = frozenset(get_args(QuadraticPosition))
ComparisonOperator = Literal['==', '!=', '<=', '>=', '<', '>']

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

    Affine everywhere but the objective, where a :class:`Multiply` of two
    variable-carrying operands is degree 2; which position allows what is
    ``math_spec.degree``'s to say and no node here records.

    The four operators exist for the tests that compose plans by hand;
    constructing Programs in Python is not supported API, so there is no
    scalar coercion and no reflected form.
    """

    def __add__(self: ExpressionNode, other: ExpressionNode) -> ExpressionNode:
        return Add(self, other)

    def __sub__(self: ExpressionNode, other: ExpressionNode) -> ExpressionNode:
        return Add(self, Negate(other))

    def __mul__(self: ExpressionNode, other: ExpressionNode) -> ExpressionNode:
        return Multiply(self, other)

    def __neg__(self: ExpressionNode) -> ExpressionNode:
        return Negate(self)


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
class Negate(Expression):
    operand: ExpressionNode


@dataclass(frozen=True)
class Add(Expression):
    left: ExpressionNode
    right: ExpressionNode


@dataclass(frozen=True)
class Multiply(Expression):
    """Product of two operands.

    Affine where at least one factor is variable-free. **Degree 2 where neither
    is**, which the language allows in the objective alone
    (``math_spec.degree``) — so a consumer that cannot represent a quadratic
    term is told which position it is compiling rather than assuming it.
    """

    left: ExpressionNode
    right: ExpressionNode


@dataclass(frozen=True)
class Power(Expression):
    """``base ** exponent``, both variable-free.

    Degree 0 in variables wherever it appears, so no consumer has to ask what
    position it stands in: the language refuses a variable anywhere under it
    (``math_spec.degree``), which is what lets this fold to one number per
    coordinate like any other parameter arithmetic.
    """

    base: ExpressionNode
    exponent: ExpressionNode


@dataclass(frozen=True)
class Divide(Expression):
    """Quotient ``numerator / divisor``. The divisor must be variable-free."""

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

    ``coordinate`` names coordinates carried by dim ``over`` whose values are
    labels of the matching dim in ``into``; the result replaces ``over`` with
    all of them.

    ``into`` restates each coordinate's declared target, because a node is
    read on its own — a consumer places terms from one without consulting the
    program — and lowering is the only thing that writes it.

    Several coordinates are one grouping into a product of targets, not a
    composition of groupings — they are consumed in a single join, so the pair
    of tuples is always the same length and their order pairs them up.
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
    fields are named for the *table* rather than the direction, so the pair
    reads as one relation; the surface says which end you stand on
    (``sum(by=)`` consumes it, ``at(by=)`` produces it, the lookup names the map).

    The join fans out, many ``over`` labels sharing one ``into`` tuple — the
    fan-out ``GroupSum`` pays in reverse, so the locality class is unchanged.
    """

    operand: ExpressionNode
    over: str
    coordinate: tuple[str, ...]
    into: tuple[str, ...]


@dataclass(frozen=True)
class Translate(Expression):
    """Re-index along one dimension: the result at *t* is ``operand`` at *t - by*.

    One node for the whole of ``shift``, whose ``edge=`` decides ``wrap``:
    ``edge='wrap'`` is periodic, absent or numeric is not.

    ``wrap`` carries no default, on this node or on :class:`Window`. Whether an
    axis closes onto itself is the difference between a battery that must end
    as it started and one that need not, and there is no reading of a
    translation that leaves it unsaid — a node that guessed would be answering
    for the file.

    ``fill`` decides what an acyclic shift leaves behind. ``None``, what bare
    ``shift`` lowers to, leaves the vacated positions **absent**: they carry no
    value, the absence rules propagate that, and the row drops. A number makes
    them present and contribute it, which is the only way a file can say
    "before the axis starts, read zero" without inventing coordinates. Always
    ``None`` under ``wrap``, a cyclic map vacating nothing.

    ``offset`` is how far back to reach: an integer, or the name of an integer
    parameter when it differs per entity — a construction lead time, a transit
    time, a minimum up time. A named offset may not depend on the dimension
    being translated, and carries its sign in the values.

    ``partition`` names a lookup over ``dimension``, and then the translation
    happens **inside each group** it makes: the neighbour of a coordinate is the
    one before it *in its own group*, the edge is that group's edge, and a wrap
    closes each group onto itself. A coordinate the lookup sends nowhere is in
    no group and reaches nothing.
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
    instead of stopping short at it, and is stated at every construction for
    the reason :class:`Translate` gives.

    ``partition`` names a lookup over that dimension, and the window then stops
    at each group's edge: a representative day, a season, a scenario's own run
    of hours. Positions are counted inside the group rather than along the
    axis, so a coordinate the lookup places nowhere reaches nothing at all —
    not even itself.

    One node rather than a sum of ``Translate``s, because the number of terms
    would then be read from data and the program's *shape* is fixed before any
    data is bound. What data supplies is the mask's cardinality, exactly as it
    supplies how many snapshots there are.
    """

    operand: ExpressionNode
    dimension: str
    width: int | str
    wrap: bool
    partition: str | None = None


@dataclass(frozen=True)
class Region:
    """One region of a :class:`Cases`: where it applies, and the value there.

    ``when`` is stated on every region, the one the file wrote as
    ``otherwise:`` included — its mask is the negation of the others, resolved
    once here rather than by each consumer in turn. A consumer builds a region
    without holding the rest in mind, and both facts it needs are on the region
    it is reading.
    """

    when: WhereNode
    value: ExpressionNode


@dataclass(frozen=True)
class Cases(Expression):
    """A value defined by region — exactly one region applies at each coordinate.

    The language proves the regions apart before any data binds, and the
    file's ``otherwise:`` covers whatever the rest leave, so they are disjoint
    and total by construction: a consumer adds the regions rather than ranking
    them, and needs neither an order nor a tie-break.

    Not a shape operator — every region spans the dims the expression does, and
    this neither reduces nor replicates. What it adds is the one thing no other
    node here carries: **a mask in a value position**. A consumer that can
    restrict rows but cannot weigh a term by a predicate builds each region
    against its own mask and adds the results.
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

    Total over the node set, so a consumer asks any node rather than keeping a
    list of which kinds carry the answer. Arithmetic and the leaves reshape
    nothing, which is one slot for one row — the same class a pullback and a
    translation are in, reached for a different reason.

    Exhaustive rather than defaulted: a node added without a case here is a
    type error at this function, where the absence rule it needs is decided,
    instead of silently inheriting the class that reshapes nothing.

    :class:`Cases` is in that class too, for a reason of its own: its regions
    are disjoint, so an output row reads exactly one of them — the several
    values it holds are alternatives rather than slots summed together.
    """
    if isinstance(expression, (Sum, GroupSum)):
        return 'many-to-one'
    if isinstance(expression, Window):
        return 'one-to-many'
    if isinstance(
        expression,
        (Constant, Parameter, Variable, Negate, Add, Multiply, Power, Divide, At, Translate, Cases),
    ):
        return 'one-to-one'
    assert_never(expression)


def children(expression: ExpressionNode) -> tuple[ExpressionNode, ...]:
    """The sub-expressions of *expression* — the structural half of any walk.

    Every walk over a program's expressions recurses through here and differs only in
    what it does at the leaves. Enumerating the children once is how a node
    added later reaches all of them rather than one.
    """
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
    """Which of the language's constructs one program actually reaches for.

    A *subset*, never the whole: the language admits more than any one file
    uses, and an empty field says this program does not use that construct —
    not that the construct does not exist. Every field is a set, so
    ``if footprint.x`` asks whether it appears at all and ``y in footprint.x``
    asks about one kind, and a construct admitted later widens a set rather
    than needing a field a consumer does not yet read.

    Facts only. What a sink can ingest is a separate axis
    (``docs/about/ceiling.md``, "Capability is not the ceiling"), where a
    capability is neither a flat set nor one verdict per construct — so there
    is deliberately no verdict here to read instead of giving one.

    Nothing below the kind, either: a sink that takes a window but not a
    wrapped one reads ``Window in shapes`` and then walks, because ``wrap``,
    ``partition`` and a named width are refinements without end and each is one
    line once the set has said where to look.

    Attributes:
        quadratic: Each position a product of two variable-carrying operands
            stands in. Empty is affine throughout. Convexity is not here: it is
            a property of the whole Hessian rather than of any term, and the
            coefficients deciding it arrive with the data — so, as with a
            curve's shape (:class:`Curved`),
            this names where the products are and the caller holding the
            numbers does the checking.
        variable_types: Every domain declared, ``{'continuous'}`` alone being
            the pure-LP case.
        sos_types: The order of each special-ordered set declared. Empty where
            the file declares none.
        shapes: Every expression node kind that appears, complete rather than
            curated — picking the interesting ones would be the judgement this
            leaves to the consumer, and a node added later is reported without
            anyone remembering a filter.
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
        """Seal every group, so a program handed out cannot be written to.

        ``frozen=True`` stops a field being rebound and says nothing about the
        mapping behind it. Wrapping here rather than trusting the caller is
        what makes the guarantee hold for every construction path.
        """
        for f in fields(self):
            group = getattr(self, f.name)
            if isinstance(group, Mapping):
                object.__setattr__(self, f.name, MappingProxyType(dict(group)))

    @property
    def expressions(self) -> tuple[ExpressionNode, ...]:
        """Every expression a row is built from — the objective and both sides of each constraint.

        What a walk over the program *a solver sees* takes. A declared
        :attr:`named_expressions` entry is not among them: it builds no row, so
        a question asked about what will be solved would answer wrongly if it
        counted one.
        """
        return (
            *((self.objective.expression,) if self.objective is not None else ()),
            *(side for c in self.constraints.values() for side in (c.lhs, c.rhs)),
        )

    @cached_property
    def footprint(self) -> Footprint:
        """Which constructs this program uses — walked once, then held.

        Safe to hold: a program cannot change after construction, its groups
        being sealed and every node under them frozen.
        """
        objective = (self.objective.expression,) if self.objective is not None else ()
        sides = tuple(side for c in self.constraints.values() for side in (c.lhs, c.rhs))
        return Footprint(
            quadratic=frozenset(
                position
                for position, group in (('objective', objective), ('constraint', sides))
                if any(is_quadratic(e) for e in group)
            ),
            variable_types=frozenset(v.variable_type for v in self.variables.values()),
            sos_types=frozenset(s.sos_type for s in self.sos.values()),
            shapes=frozenset(type(node) for node in walk(*self.expressions)),
        )

    def dimension(self, name: str) -> DimensionDeclaration:
        return _declared(self.dimensions, name, 'dimension')

    @property
    def lookups(self) -> tuple[tuple[str, LookupDeclaration], ...]:
        """Every targeted map in the program, with the dimension it is over.

        One walk for the several shapes consumers want it in — name to target,
        target to origin, the set of targets — because the nested comprehension
        that produces any of them is the same walk written again.
        """
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
    """Parameters appearing anywhere in a divisor position.

    Static, like :func:`parameters_of`: which names *can* reach a divisor is
    the program's to answer, and *where* they must have values is decided by the
    rows a declaration builds.
    """
    return frozenset().union(*(parameters_of(q.divisor) for q in quotients(*expressions)))


def conjuncts(where: WhereNode) -> tuple[WhereNode, ...]:
    """The predicates a mask joins with ``AND``, its ``AND`` spine flattened.

    ``a AND b AND c`` gives three, and a mask that is not an ``AND`` gives
    itself. The walk stops at the first node that is not an ``AND``: the
    conjuncts of ``a AND (b OR c)`` are ``a`` and ``b OR c``, and of
    ``NOT (a AND b)`` the single ``NOT`` — neither an ``OR`` nor a ``NOT`` is a
    claim the mask makes on its own, so neither is split. A consumer asks the
    split here rather than re-deriving it, so two cannot disagree on what a
    conjunct is.
    """
    if isinstance(where, AndNode):
        return conjuncts(where.left) + conjuncts(where.right)
    return (where,)


@dataclass(frozen=True)
class Mask:
    """A resolved ``where`` and the questions asked of it — a mask, first-class.

    ``root`` is the predicate node the ``where`` field used to hold, unchanged:
    an engine still dispatches on it with ``isinstance`` to build the mask
    against data. The properties are what the *language* answers about a mask,
    asked here so two consumers cannot answer differently — the reason
    :meth:`DimensionDeclaration.maps` sits on the declaration rather than in
    each consumer, one component over.

    Attributes:
        root: The resolved predicate the mask restricts rows by.
    """

    root: WhereNode

    @property
    def conjuncts(self) -> tuple[WhereNode, ...]:
        """The predicates the mask joins with ``AND`` — :func:`conjuncts` of the root."""
        return conjuncts(self.root)

    @property
    def names_read(self) -> frozenset[str]:
        """The parameters, lookups and variables the mask names — :func:`~math_spec.where_parser.names_read` of the root."""
        return names_read(self.root)

    @property
    def atoms(self) -> tuple[TypedPredicateNode, ...]:
        """The mask's leaves, connectives removed — :func:`~math_spec.where_parser.atoms` of the root."""
        return tuple(atoms(self.root))

    def dims_read(self, name_dims: Mapping[str, Sequence[str]]) -> frozenset[str]:
        """The dims the mask is read at — :func:`~math_spec.where_parser.dims_read` of the root.

        A method, not a property, because the answer needs each name's dims,
        which the root alone does not carry.

        Args:
            name_dims: Every declared name to the dims it is read through.

        Returns:
            The dims read, empty for a mask over nothing but literals.
        """
        return dims_read(self.root, name_dims)
