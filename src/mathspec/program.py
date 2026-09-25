# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""The program: what a file declares, with names resolved and shapes fixed.

The second public state, and the one a consumer reads. A [`Program`][] is
the file typed, section for section: every declaration it makes, with names
resolved, shapes fixed and every rule decidable without data checked, and no
data at all. Lowering, as a [`Spec`][] loads, is the only
thing that builds one, so nothing here re-checks a hand-built one.

Node and declaration classes are matched with ``isinstance``. The rules a
node's structure does not show is [`children`][]; the questions over the walk
are [`walk_regions`][], [`walk`][] and the filters beside them. A
resolved ``where`` arrives as a [`Mask`][]. Frozen dataclasses only — no
execution logic, and nothing imported from a consumer. How a consumer reads
one: ``docs/reference/reading.md``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields, replace
from functools import cached_property
from typing import TYPE_CHECKING, Literal, assert_never

from mathspec._expression_parser import ComparisonOperator
from mathspec._sealed import Sealed
from mathspec.errors import did_you_mean

if TYPE_CHECKING:
    import datetime
    from collections.abc import Iterator


#: What ``mathspec.program`` promises a consumer, sorted.
__all__ = [
    'Add',
    'And',
    'Assumption',
    'BooleanLiteral',
    'Cases',
    'Connective',
    'Constant',
    'ConstraintDeclaration',
    'ConstraintSense',
    'CountComparison',
    'DeclaredDtype',
    'DimensionComparison',
    'DimensionDeclaration',
    'DimensionDtype',
    'DimensionPosition',
    'Direction',
    'Divide',
    'Dual',
    'Expression',
    'ExpressionComparison',
    'ExpressionDeclaration',
    'Footprint',
    'GivenDeclaration',
    'GivenTargets',
    'GroupSum',
    'Link',
    'Mask',
    'Multiply',
    'Named',
    'Negate',
    'Not',
    'ObjectiveDeclaration',
    'ObjectiveSense',
    'Or',
    'Parameter',
    'ParameterComparison',
    'ParameterDeclaration',
    'ParameterDefined',
    'ParameterDtype',
    'Partition',
    'PiecewiseDeclaration',
    'PiecewiseMethod',
    'Power',
    'Predicate',
    'PredicateOperator',
    'Program',
    'Pullback',
    'PulledBackPredicate',
    'QuadraticPosition',
    'Reach',
    'Region',
    'RelationComparison',
    'RelationDeclaration',
    'RelationDefined',
    'RelationPairComparison',
    'Separability',
    'SosDeclaration',
    'SosType',
    'Sum',
    'Translate',
    'TranslatedPredicate',
    'TypedPredicate',
    'Variable',
    'VariableAbsence',
    'VariableDeclaration',
    'VariableDefined',
    'VariableDomain',
    'WindowSum',
    'assumption_message',
    'carries_variable',
    'children',
    'is_quadratic',
    'parameters_of',
    'variables_of',
    'walk',
    'walk_regions',
    'where_children',
]


ConstraintSense = ComparisonOperator

#: Where a degree-2 product may stand in the math a solver sees. An objective
#: and a constraint take ``variable * variable``; a bound and a ``piecewise:``
#: link are read affinely (``mathspec.degree``), so those are the two.
QuadraticPosition = Literal['objective', 'constraint']

#: The dtype a dimension index may declare (the declaration rules), and what
#: its labels are. ``datetime`` is a dimension's alone — labels on a timeline
#: order and compare, where a *value* of that type is a moment nothing
#: computes with.
DimensionDtype = Literal['float', 'int', 'str', 'datetime']

#: The dtype a parameter may declare (the declaration rules), and what its bound
#: column must be. ``bool`` is a parameter's alone — a value column may be a
#: flag a mask reads, where a label set of two members is a dimension nothing
#: indexes by.
ParameterDtype = Literal['float', 'int', 'bool', 'str']

#: What a *name* a where comparison tests may be — a parameter's dtype or a
#: dimension's, since a relation's is its target's. The union rather than either
#: half, because a mask names all three kinds and reads the dtype the same way.
DeclaredDtype = ParameterDtype | DimensionDtype

#: The domain a variable may declare.
VariableDomain = Literal['continuous', 'integer', 'binary']

#: What a masked variable's non-existence *means* where it does not exist.
#: ``undefined`` is the absence rules' default — a term carrying it takes its
#: row. ``zero`` says the quantity *is* zero there, so the term contributes
#: nothing and the row stands.
VariableAbsence = Literal['undefined', 'zero']

#: Which way an objective is optimised (the declaration rules).
ObjectiveSense = Literal['minimize', 'maximize']

#: The order of special ordered set.
SosType = Literal[1, 2]

#: How a ``piecewise:`` block restricts its interpolation weights. Kept in step
#: with [`PIECEWISE_METHODS`][mathspec.spec.PIECEWISE_METHODS], which says what each one
#: emits, by ``tests/test_schema.py``.
PiecewiseMethod = Literal['adjacency', 'sos2', 'convex', 'lp']


# --------------------------------------------------------------------------
# Affine expressions
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Constant:
    """A scalar constant."""

    value: float


@dataclass(frozen=True)
class Parameter:
    """A parameter reference — contributes to the constant part."""

    name: str


@dataclass(frozen=True)
class Variable:
    """A variable reference — one term per existing variable row."""

    name: str


@dataclass(frozen=True)
class Dual:
    """A constraint's dual — its shadow price, read after the solve.

    Stands only under an [`ExpressionDeclaration`][] the math never reads:
    the loader refuses ``dual()`` anywhere a solver ingests. One value per
    coordinate of the named constraint's own ``dims`` frame: the leaf reshapes
    nothing, like a parameter.
    """

    constraint: str


@dataclass(frozen=True)
class Negate:
    operand: Expression


@dataclass(frozen=True)
class Add:
    left: Expression
    right: Expression


@dataclass(frozen=True)
class Multiply:
    """Product of two operands.

    Affine where at least one factor is variable-free; degree 2 where neither
    is, which ``mathspec.degree`` admits in a [`QuadraticPosition`][] alone.
    """

    left: Expression
    right: Expression


@dataclass(frozen=True)
class Power:
    """``base ** exponent``, both variable-free wherever the math reads it.

    The language refuses a variable anywhere under it (``mathspec.degree``),
    so in the program a solver sees it is degree 0 and folds to one number per
    coordinate like any other parameter arithmetic.
    """

    base: Expression
    exponent: Expression


@dataclass(frozen=True)
class Divide:
    """Quotient ``numerator / divisor``, the divisor variable-free wherever the math reads it (``mathspec.degree``)."""

    numerator: Expression
    divisor: Expression


@dataclass(frozen=True)
class Sum:
    """Sum ``operand`` over the named dims, removing them from the result."""

    operand: Expression
    over: tuple[str, ...]


@dataclass(frozen=True)
class GroupSum:
    """Sum ``operand`` through a relation: the dims ``direction`` consumes go, the dims it produces arrive, the dims it joins on stay.

    The join keys on the consumed columns and every joined column, and the
    operand carries every dim consumed or joined on.
    """

    operand: Expression
    direction: Direction


@dataclass(frozen=True)
class Pullback:
    """Read ``operand`` through a relation — the adjoint of [`GroupSum`][].

    The dims ``direction`` consumes go and the dims it produces arrive, one
    value per coordinate because the read takes value columns at a key the
    result fixes, which the loader checks. The join fans out, many
    produced tuples sharing one consumed tuple — at each coordinate of the
    joined columns, which the operand carries and the result keeps.
    """

    operand: Expression
    direction: Direction


@dataclass(frozen=True)
class Translate:
    """Re-index along one dimension: the result at *t* is ``operand`` at *t - offset*.

    ``wrap`` is ``edge='wrap'`` in the file: periodic, and stated on every
    node. ``fill`` is what an acyclic shift leaves behind: ``None`` leaves the
    vacated positions absent, so the row drops; a number makes them present
    and contribute it. Always ``None`` under ``wrap``.

    ``offset`` is an integer, or the name of an integer parameter that does
    not depend on ``along`` and carries its sign in the values.

    ``partition`` is a relation with a key column over ``along``
    ([`Partition`][]), and the translation then happens inside each group
    its ``within=`` columns make: the neighbour is the one before in the same
    group, the edge is the group's, and a wrap closes each group onto itself.
    A coordinate the relation sends nowhere reaches nothing.
    """

    operand: Expression
    along: str
    offset: int | str
    wrap: bool
    fill: float | None = None
    partition: Partition | None = None


@dataclass(frozen=True)
class WindowSum:
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

    ``partition`` names a relation over that dimension, and the window then stops
    at each group's edge. Positions are counted inside the group, so a
    coordinate the relation places nowhere reaches nothing — not even itself.
    """

    operand: Expression
    along: str
    width: int | str
    wrap: bool
    partition: Partition | None = None


@dataclass(frozen=True)
class Region:
    """One region of a [`Cases`][]: where it applies, and the value there.

    ``when`` is stated on every region; the one the file wrote as
    ``otherwise:`` carries the negation of the others.
    """

    when: Mask
    value: Expression


@dataclass(frozen=True)
class Cases:
    """A value defined by region — exactly one region applies at each coordinate.

    The regions are disjoint and total, so a consumer adds them rather than
    ranking them. Not a shape operator: every region spans the dims the
    expression does.
    """

    regions: tuple[Region, ...]


@dataclass(frozen=True)
class Named:
    """A use of an ``expressions:`` entry, standing where its name was written, with the entry's body under it.

    Its value is its body's: a consumer building rows steps through it, as
    [`children`][] does. It is kept as a node rather than written in so the
    typesetter can print the symbol where the name stood and define it once.
    Every use of one entry holds the one node resolution built for it, whose
    [`body`][] is the [`ExpressionDeclaration.expression`][] of that entry.
    """

    name: str
    body: Expression


#: Every expression node, as one type — what a walk takes. The set is
#: *closed*: nothing registers into it, so a consumer that walks it ends in
#: ``assert_never`` and a node added without a branch is a type error at the
#: site that must grow one, rather than a ``LanguageError`` raised at the first
#: spec that uses it. The degree rules (``mathspec.degree``) hold on every
#: tree the math reads — [`Program.roots`][], a bound, and a named expression
#: that is ``in_math`` — affine but where a [`QuadraticPosition`][] admits a
#: [`Multiply`][] of two variable-carrying operands. A
#: [`ExpressionDeclaration`][] the math never reads is held to none of them.
#: No node records which tree it stands in.
Expression = (
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
    | Pullback
    | Translate
    | WindowSum
    | Cases
    | Named
)


def children(expression: Expression) -> tuple[Expression, ...]:
    """The sub-expressions of *expression* — what every walk recurses through."""
    if isinstance(expression, Named):
        return (expression.body,)
    if isinstance(expression, Negate):
        return (expression.operand,)
    if isinstance(expression, (Add, Multiply)):
        return (expression.left, expression.right)
    if isinstance(expression, Divide):
        return (expression.numerator, expression.divisor)
    if isinstance(expression, Power):
        return (expression.base, expression.exponent)
    if isinstance(expression, (Sum, GroupSum, Pullback, Translate, WindowSum)):
        return (expression.operand,)
    if isinstance(expression, Cases):
        return tuple(region.value for region in expression.regions)
    if isinstance(expression, (Constant, Parameter, Variable, Dual)):
        return ()
    assert_never(expression)


# --------------------------------------------------------------------------
# Declarations
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RelationDeclaration:
    """One declared relation: a table over its ``columns``, single-valued per ``key``.

    ``columns`` maps each role to its dimension in the order the table
    carries them, the key's roles first; ``key`` is the roles a row is
    identified by, and [`values`][] the rest — every role is a key role for
    a bare relation, which is one with no value columns. Every value is
    checked when the data is attached to be a label of its column's dimension, and the table to
    have one row per key tuple — which keeps a mistyped label from silently
    dropping its terms in the join that places them, and is what lets ``at``
    read one value.
    """

    columns: tuple[tuple[str, str], ...]
    key: tuple[str, ...]
    description: str | None = None

    @property
    def roles(self) -> tuple[str, ...]:
        return tuple(role for role, _ in self.columns)

    @property
    def dims(self) -> tuple[str, ...]:
        return tuple(dim for _, dim in self.columns)

    @property
    def values(self) -> tuple[str, ...]:
        """The roles the key determines."""
        return tuple(role for role in self.roles if role not in self.key)

    @cached_property
    def _dim_of(self) -> Mapping[str, str]:
        """Each role's dimension, built once: [`dim`][] is called per role inside loops over roles."""
        return dict(self.columns)

    def dim(self, role: str) -> str:
        return self._dim_of[role]


@dataclass(frozen=True)
class Direction:
    """One relation as one call reads it — which columns are consumed, which produced, which joined on.

    The declaration fixes no direction; the call does, and this is the one it
    named. ``name`` is the relation's, as [`Program.relations`][] keys it.
    ``consumed``, ``produced`` and ``joined`` are *roles* — column names of
    ``relation``, which maps every role to its dimension and names the key.
    ``joined`` is the key roles the call did not name (every role, for a bare
    relation): the join keys on them, and a value role left unnamed is not
    read.
    """

    name: str
    relation: RelationDeclaration
    consumed: tuple[str, ...]
    produced: tuple[str, ...]
    joined: tuple[str, ...]

    def dim(self, role: str) -> str:
        """The dimension *role* ranges over."""
        return self.relation.dim(role)

    @property
    def consumed_dims(self) -> tuple[str, ...]:
        return tuple(self.dim(role) for role in self.consumed)

    @property
    def produced_dims(self) -> tuple[str, ...]:
        return tuple(self.dim(role) for role in self.produced)

    @property
    def joined_dims(self) -> tuple[str, ...]:
        return tuple(self.dim(role) for role in self.joined)


@dataclass(frozen=True)
class Partition:
    """One relation as a partition steps along it — the key column stepped along, the group columns, and the key columns joined on.

    ``name`` is the relation's, as [`Program.relations`][] keys it.
    ``along``, ``group`` and ``joined`` are *roles* — column names of
    ``relation``, which maps every role to its dimension and names the key.
    ``along`` is the one key column over the dimension stepped along, and
    the frame keeps it. ``group`` is the value columns ``within=`` named,
    read at the row's key. ``joined`` is the other key columns, whose
    dimensions the frame carries. Nothing is consumed and nothing is
    produced: the frame does not change.
    """

    name: str
    relation: RelationDeclaration
    along: str
    group: tuple[str, ...]
    joined: tuple[str, ...]

    def dim(self, role: str) -> str:
        """The dimension *role* ranges over."""
        return self.relation.dim(role)

    @property
    def along_dim(self) -> str:
        return self.dim(self.along)

    @property
    def joined_dims(self) -> tuple[str, ...]:
        return tuple(self.dim(role) for role in self.joined)


@dataclass(frozen=True)
class DimensionDeclaration:
    """A dimension, as the file declares it."""

    #: What the labels are, as the file declares them. A dimension is read from
    #: whatever table carries it, so the declared type is what that column is
    #: checked against — the same claim ``ParameterDeclaration.dtype`` makes
    #: about a value column, one axis over.
    dtype: DimensionDtype = 'str'
    description: str | None = None


@dataclass(frozen=True)
class Assumption:
    """A predicate the file states of its data, under the name it wrote in ``assumptions:``.

    ``predicate`` is true at every coordinate of its frame — the product of
    every dim the two masks name — that ``where`` admits, a missing row
    reading as false as it does in any mask. Nothing here is decidable at
    load: both sides are the data's, which is why the consumer attaching it
    checks.
    """

    predicate: Mask
    where: Mask | None = None
    #: What the file wrote under ``description:``, or the sentence a
    #: ``piecewise:`` method implies. The refusal trails it: the names alone
    #: say which columns are wrong, and not why the rule is there.
    description: str | None = None


def assumption_message(name: str, assumption: Assumption) -> str:
    """The sentence a consumer raises when the data attached to *assumption*, called *name*, fails it.

    The language's own wording, so every consumer refuses in the same words;
    a consumer appends the coordinates it saw. Where the file wrote a
    ``description:``, or a ``piecewise:`` method implied one, it trails the
    sentence: the names say which columns are wrong, and the description says
    why the rule is there.
    """
    read = ', '.join(f"'{n}'" for n in sorted(assumption.predicate.names_read))
    sentence = f"assumption '{name}' does not hold for the data attached to {read}"
    return f'{sentence} — {assumption.description}' if assumption.description else sentence


@dataclass(frozen=True)
class ParameterDeclaration:
    """Shape declaration; data is attached at execution time by name.

    ``dtype`` is what the declaration claims the values are, and a consumer
    attaching data refuses a column that is not it — so the *declaration* is
    what is read, rather than whatever the column happens to hold.
    """

    dims: tuple[str, ...]
    dtype: ParameterDtype = 'float'
    description: str | None = None


@dataclass(frozen=True)
class VariableDeclaration:
    dims: tuple[str, ...]
    where: Mask | None = None
    #: A number or a parameter, or ``None`` where that side is open. What stands
    #: for an open side in a solve is the consumer's to choose.
    lower: Expression | None = None
    #: As [`lower`][], for the other side.
    upper: Expression | None = None
    domain: VariableDomain = 'continuous'
    absence: VariableAbsence = 'undefined'
    description: str | None = None


@dataclass(frozen=True)
class GivenDeclaration:
    """A column or a row family this program reads and does not build.

    The frame is the whole declaration. A consumer looks the name up in the
    model this one is layered onto, checks the frame against what it finds,
    and refuses a name the host does not provide. An empty sum is the one
    entry this program declares itself: its body is what the other files add.
    """

    dims: tuple[str, ...]
    description: str | None = None
    #: The term this program adds to a given expression, or ``None`` where it
    #: only reads the name: the [`Named`][] node of the entry the term names,
    #: read over at most ``dims``.
    term: Named | None = None
    #: Whether this program declares the name itself, as an expression with a
    #: frame and no body, and leaves the body to the files that add terms.
    owned: bool = False


@dataclass(frozen=True)
class GivenTargets:
    """What a program reads and does not build, by kind.

    Every group is empty in a program built from one whole spec. Every group
    is sealed at construction, like every group of [`Program`][].
    """

    #: Data another file declares, by name, with the dtype a where compares against.
    parameters: Mapping[str, ParameterDeclaration] = Sealed({})
    #: Columns the host model provides, by name.
    variables: Mapping[str, GivenDeclaration] = Sealed({})
    #: Row families the host model provides, by name, read back after the solve.
    constraints: Mapping[str, GivenDeclaration] = Sealed({})
    #: Named expressions the host model defines, by name. An expression reads
    #: each as a [`Variable`][] over the frame declared here, since the
    #: body is the host's.
    expressions: Mapping[str, GivenDeclaration] = Sealed({})

    def __post_init__(self) -> None:
        for f in fields(self):
            object.__setattr__(self, f.name, Sealed(getattr(self, f.name)))

    def __bool__(self) -> bool:
        """Whether the program reads anything it does not build."""
        return bool(self.parameters or self.variables or self.constraints or self.expressions)


@dataclass(frozen=True)
class ConstraintDeclaration:
    """``lhs sense rhs`` for each coord combination of ``dims``.

    Either side may carry variables and constants alike; which side a
    consumer gathers them onto is its own arrangement and not stated here.
    ``where`` masks out coord combinations (row absence, like variables).
    """

    dims: tuple[str, ...]
    lhs: Expression
    sense: ConstraintSense
    rhs: Expression
    where: Mask | None = None
    description: str | None = None


@dataclass(frozen=True)
class SosDeclaration:
    """One special-ordered set per coordinate of the variable's ``dims`` minus ``along``.

    The only declaration that adds neither a column nor a row: it names
    columns a consumer already has and says what may be nonzero among them. Which
    dims those are is the variable's own ``dims`` and is read from it: a
    copy here would be a second home for a fact
    ([`Program.variables`][]).
    """

    variable: str
    along: str
    sos_type: SosType
    description: str | None = None


@dataclass(frozen=True)
class ObjectiveDeclaration:
    """Objective — scalar, every reduction in it one the file wrote."""

    sense: ObjectiveSense
    expression: Expression
    description: str | None = None


@dataclass(frozen=True)
class ExpressionDeclaration:
    """A named quantity — one the math reads, or one only read back after a solve.

    ``in_math`` where the objective, a constraint or a term this program
    adds to a given expression reads it, directly or through another entry or
    a macro; its body then stands inside
    [`Program.roots`][] and is held to the degree rules where it is
    read. Otherwise nothing a solver sees contains it: it is a reported
    quantity, its body held to no degree, the one place a [`Dual`][] may
    stand. A bound and a ``where`` name no entry, so neither decides this.
    """

    expression: Expression
    #: The frame the entry is read over: the ``dims:`` a cased entry
    #: declares, or the dims a plain entry's body carries.
    dims: tuple[str, ...]
    in_math: bool
    description: str | None = None


@dataclass(frozen=True)
class Link:
    """One link of a ``piecewise:`` block: an expression tied to the breakpoints a values parameter holds.

    ``sign`` is ``'=='`` where the link is pinned to the curve, and one side
    of it where the link is bounded by the curve instead.
    """

    expression: Expression
    values: str
    sign: ConstraintSense = '=='


@dataclass(frozen=True)
class PiecewiseDeclaration:
    """A ``piecewise:`` block as the curve it states, which [`expand`][mathspec.spec.Spec.expand] writes out as rows.

    A program of a spec that still declares one carries it here, typed; a
    program of the expanded spec carries the rows instead, under
    [`Program.variables`][] and [`Program.constraints`][], and what the
    method assumes of the breakpoints under [`Program.assumptions`][]. A
    consumer building rows takes the expanded spec.

    Attributes:
        over: The breakpoint dimension.
        links: The links, in the order the file wrote them.
        method: How the weights are restricted.
        activity: The binary the weights sum to, or ``None`` where they sum
            to 1.
        points: The parameter saying how far each curve runs, or ``None``.
        frame: The dimensions the block builds one curve per coordinate of,
            in declaration order.
        description: What the file wrote under ``description:``, or ``None``.
    """

    over: str
    links: tuple[Link, ...]
    method: PiecewiseMethod
    frame: tuple[str, ...]
    activity: str | None = None
    points: str | None = None
    description: str | None = None

    @property
    def nominated(self) -> str | None:
        """The block's own values parameter ``points:`` names, so the mask is derived from it — or ``None``."""
        return self.points if self.points in {link.values for link in self.links} else None

    @property
    def curve(self) -> tuple[Link, Link]:
        """The two links as ``(x, y)``, the bounded one last. Two-link blocks only."""
        x, y = self.links
        return (y, x) if x.sign != '==' else (x, y)


@dataclass(frozen=True)
class Footprint:
    """Which of the language's constructs one program uses.

    A subset, never the whole: an empty field says this program does not use
    the construct.

    Attributes:
        quadratic: Each position a product of two variable-carrying operands
            stands in; empty is affine throughout.
        domains: Every domain declared.
        sos_types: The order of each special-ordered set declared.
        kinds: Every expression node kind that appears.
    """

    quadratic: frozenset[QuadraticPosition]
    domains: frozenset[VariableDomain]
    sos_types: frozenset[SosType]
    kinds: frozenset[type[Expression]]


@dataclass(frozen=True)
class Reach:
    """One read along an axis whose distance only data can say.

    Attributes:
        label: The declaration reading, as the lowering's messages label it.
        name: The parameter or relation that says how far.
        kind: An ``offset`` is a parameter's values, which
            [`Separability.resolved`][] folds in; a ``partition`` and a
            ``coordinate`` are a relation's groups, which it does not.
    """

    label: str
    name: str
    kind: Literal['offset', 'partition', 'coordinate']


@dataclass(frozen=True)
class Separability:
    """What building one dimension a window at a time asks of a driver, and what it would break.

    A rolling-horizon or myopic driver cuts an axis into windows and builds
    each on its own, and a decomposition cuts the same axis and solves each
    piece on its own. What the program can say is whether every row it builds
    is then complete inside one window: how far a row reads ahead along the
    axis, which declarations tie the axis together so that no window holds
    them, and — the same fact read as a set — which rows and columns are left
    over as the border every window shares. It cannot say whether the windowed
    answer is the one a whole-horizon solve would give — a store carried over
    one row windows cleanly, and a rolling solve of it is still a different
    answer — which is the driver's design and not the spec's.

    What a row reads *behind* is not reported. A window starts where the
    driver puts it, and what its first rows meet there is the edge policy:
    the opening state a rolling horizon seeds, and the driver's to carry.

    Attributes:
        dimension: The axis asked about.
        ahead: Coordinates a window must see after its last row for every row
            it builds to be complete — what a negative ``shift`` reads. ``0``
            is pointwise; a ``shift`` of ``-2`` is ``2``.
        coupled: Each declaration that ties the axis together, to what ties it
            and the one change to the spec that would not: a sum over the axis
            in a constraint, a grouping that consumes it, a wrapped
            translation, a set. No window satisfies these, and no rewrite here
            would keep the spec's meaning, so the remedy is named rather than
            applied.
        undecided: Each read along the axis whose reach only data can say —
            a named offset, a partition whose groups a window may cut, a read
            through a relation at a coordinate the data chooses.
            [`resolved`][] folds a parameter's values in.
        restarts: Each declaration counting a position along the axis, which a
            window restarts at its first row. Whether that is wanted — a seed
            once per window, or once per horizon — is for the spec's author to decide, so it is
            reported rather than refused.
        linking_rows: Each constraint no one window holds whole, in declaration
            order: one the axis does not index, whose row stands in every
            window, and one [`coupled`][] names. A reach the data decides is
            not one, so a row waiting on [`undecided`][] may span two windows.
        linking_columns: Each variable the axis does not index, in declaration
            order, whose column every window reads. A decomposition calls a
            window a block, and with [`linking_rows`][] this is the border of
            a bordered block-diagonal form cut along the axis, whole where
            nothing is [`undecided`][] and no set runs through it. A set
            couples the axis without building a row, so it stands in neither
            field. The form is exactly that where [`ahead`][] is ``0``: a
            positive lookahead is neighbouring blocks overlapping by that much.
    """

    dimension: str
    ahead: int
    coupled: Mapping[str, str]
    undecided: tuple[Reach, ...]
    restarts: Mapping[str, str]
    linking_rows: tuple[str, ...]
    linking_columns: tuple[str, ...]

    @property
    def windowable(self) -> bool:
        """Whether every row builds complete inside a window looking [`ahead`][] past its last row.

        ``False`` while a reach is [`undecided`][], which a driver holding
        the data may resolve; [`restarts`][] do not count against it.
        """
        return not self.coupled and not self.undecided

    def resolved(self, least: Mapping[str, int]) -> Separability:
        """The same verdict with each named offset folded into [`ahead`][].

        A driver holding the data reads the least value of each parameter an
        [`undecided`][] reach names and hands it here, so the rule that
        turns a value into a reach — a negative offset reads ahead by that
        much, a positive one reads behind and asks nothing — has one home.

        Args:
            least: Parameter name to the least of its values. A reach through
                a relation — a partition, a coordinate — cannot be folded this
                way and stays undecided, as does a parameter left out.

        Raises:
            KeyError: A name no undecided reach along this axis waits on.
        """
        waiting = {reach.name for reach in self.undecided if reach.kind == 'offset'}
        for name in least:
            if name not in waiting:
                raise KeyError(
                    f"'{name}' is not a parameter an undecided reach along '{self.dimension}' waits on. "
                    + did_you_mean(name, sorted(waiting))
                )
        folded = {reach for reach in self.undecided if reach.kind == 'offset' and reach.name in least}
        ahead = max([self.ahead, *(-least[reach.name] for reach in folded)])
        return replace(self, ahead=ahead, undecided=tuple(r for r in self.undecided if r not in folded))


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
    dimensions: Mapping[str, DimensionDeclaration] = Sealed({})
    relations: Mapping[str, RelationDeclaration] = Sealed({})
    sos: Mapping[str, SosDeclaration] = Sealed({})
    #: Each ``piecewise:`` block the spec still declares, as the curve it
    #: states; empty on a program of a spec whose curves are written out.
    piecewise: Mapping[str, PiecewiseDeclaration] = Sealed({})
    #: What the data has to satisfy for the answer to mean anything, by the
    #: name a refusal quotes: every ``assumptions:`` entry the file wrote, then
    #: what each ``piecewise:`` block's method assumes of its breakpoints. The
    #: language decides none of it, so the consumer attaching the data checks
    #: each and refuses with [`assumption_message`][].
    assumptions: Mapping[str, Assumption] = Sealed({})
    #: Declared ``expressions:``, each saying whether the math reads it. None
    #: builds a row of its own — one the math reads stands as a [`Named`][]
    #: where it is read — but all are lowered with the program, so a file whose
    #: named expression is outside the language is refused by every verb that
    #: reads the file rather than only by the one that reads the expression.
    expressions: Mapping[str, ExpressionDeclaration] = Sealed({})
    #: What this program reads and does not build ([`GivenTargets`][]). A
    #: model it is layered onto provides each name; nothing here emits a
    #: column or a row.
    given: GivenTargets = GivenTargets()
    #: What the file as a whole is, as its ``description:`` says.
    description: str | None = None

    def __post_init__(self) -> None:
        """Seal every group, so a program handed out cannot be written to."""
        for f in fields(self):
            group = getattr(self, f.name)
            if isinstance(group, Mapping):
                object.__setattr__(self, f.name, Sealed(group))

    def _by_position(self) -> Iterator[tuple[QuadraticPosition, tuple[Expression, ...]]]:
        """The row-building expressions, grouped by the position they stand in."""
        yield 'objective', (self.objective.expression,) if self.objective is not None else ()
        yield 'constraint', tuple(side for c in self.constraints.values() for side in (c.lhs, c.rhs))

    def relations_of(self, dimension: str) -> Mapping[str, RelationDeclaration]:
        """The relations with a column over *dimension*, by name."""
        return Sealed({n: lk for n, lk in self.relations.items() if dimension in lk.dims})

    @property
    def roots(self) -> tuple[Expression, ...]:
        """Every tree a row is built from — the objective and both sides of each constraint.

        An [`expressions`][] entry builds no row and is not among them. Nor is
        a curve still under [`piecewise`][]: it is not a row until
        [`expand`][mathspec.spec.Spec.expand] writes it out, and its rows are in
        the program of the expansion.
        """
        return tuple(e for _, group in self._by_position() for e in group)

    @cached_property
    def footprint(self) -> Footprint:
        """Which constructs this program uses — walked once, then held.

        It answers for the rows this program holds. A curve still under
        [`piecewise`][] is not counted, so a ``sos2`` curve adds no set order
        here; ask the program of ``spec.expand('piecewise')`` for its rows.
        """
        return Footprint(
            quadratic=frozenset(
                position for position, group in self._by_position() if any(is_quadratic(e) for e in group)
            ),
            domains=frozenset(v.domain for v in self.variables.values()),
            sos_types=frozenset(s.sos_type for s in self.sos.values()),
            kinds=frozenset(type(node) for node in walk(*self.roots)),
        )

    @cached_property
    def separability(self) -> Mapping[str, Separability]:
        """Every axis, to what building it a window at a time asks and what it would break.

        The locality :doc:`the ceiling </about/ceiling>` argues in — pointwise,
        bounded halo, global — asked about the axes rather than about the
        operators, so a driver may know before it cuts a horizon whether every
        row it builds is complete inside some window.

        **A reduction means opposite things by position**, which is the whole of
        the care: in a constraint a sum over the axis ties every window to every
        other, and in the objective it is additively separable, an objective
        being a sum already.

        Every declared dimension has an entry, an axis nothing mentions being
        trivially windowable. Walked once and held, like [`footprint`][] and
        for the same reason — a program cannot change after construction — and
        answering for every axis costs what answering for one did, every
        construct that ties an axis naming the axis it ties (#248).

        It answers for the rows this program holds, as [`footprint`][] does.
        A curve still under [`piecewise`][] ties nothing here, although its
        rows sum over its breakpoint dimension; ask the program of
        ``spec.expand('piecewise')``.
        """
        from mathspec.separability import separabilities

        return Sealed(separabilities(self))


# --------------------------------------------------------------------------
# Walks, and the questions asked through them
# --------------------------------------------------------------------------


def walk_regions(*expressions: Expression) -> Iterator[tuple[Expression, tuple[Mask, ...]]]:
    """Every node under *expressions*, each with the regions it stands inside, outermost first.

    The traversal every *question* about a program is a filter of — which names
    it mentions, whether a variable stands under it, which divisions it
    contains, which rows a piece owes data at. One generator rather than that
    five-line recursion once per question: how a program is traversed is one
    fact, so a node kind [`children`][] learns to descend into reaches every
    caller at once rather than the callers that remembered.

    The regions are the ``when`` of every [`Cases`][] region the node's
    value stands under, the outermost first, which is the order the masks
    conjoin in. A node outside any ``cases:`` block carries the empty tuple,
    and a ``Cases`` node carries only the regions above it, not its own. The
    tuple rather than one conjoined mask: what a consumer does with the
    regions is its own, and the conjunction is one ``&`` away.
    """
    yield from _walk_regions(expressions, ())


def _walk_regions(
    expressions: tuple[Expression, ...], above: tuple[Mask, ...]
) -> Iterator[tuple[Expression, tuple[Mask, ...]]]:
    """The recursion under [`walk_regions`][], with the regions above *expressions* carried down.

    A ``Cases`` descends by its regions rather than by [`children`][], because
    only the region pairs a value with its ``when``; every other node kind
    descends by [`children`][], which stays the one home of what sits under
    a node.
    """
    for expression in expressions:
        yield expression, above
        if isinstance(expression, Cases):
            for region in expression.regions:
                yield from _walk_regions((region.value,), (*above, region.when))
        else:
            yield from _walk_regions(children(expression), above)


def walk(*expressions: Expression) -> Iterator[Expression]:
    """Every node under *expressions*, each expression itself included, parents first.

    [`walk_regions`][] with the regions dropped, for the questions that do
    not ask where a node stands.
    """
    return (node for node, _ in walk_regions(*expressions))


def is_quadratic(expression: Expression) -> bool:
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


def carries_variable(expression: Expression) -> bool:
    """Whether a variable appears anywhere under *expression*."""
    return any(isinstance(node, Variable) for node in walk(expression))


def parameters_of(*expressions: Expression) -> frozenset[str]:
    """Every parameter named anywhere under *expressions*."""
    return frozenset(node.name for node in walk(*expressions) if isinstance(node, Parameter))


def variables_of(*expressions: Expression) -> frozenset[str]:
    """Every variable named anywhere under *expressions*."""
    return frozenset(node.name for node in walk(*expressions) if isinstance(node, Variable))


# ---------------------------------------------------------------------------
# the resolved where vocabulary
# ---------------------------------------------------------------------------


PredicateOperator = Literal['<=', '>=', '==', '!=', '<', '>']


@dataclass(frozen=True)
class BooleanLiteral:
    value: bool


@dataclass(frozen=True)
class ParameterDefined:
    """True wherever the named parameter is non-null and finite.

    ``dims`` is the parameter's own, copied off the declaration during
    resolution; every leaf below that names a declaration carries its dims
    (or ``over``) the same way.
    """

    name: str
    dims: tuple[str, ...]


@dataclass(frozen=True)
class VariableDefined:
    """True at the coordinates where the named variable exists."""

    name: str
    dims: tuple[str, ...]


@dataclass(frozen=True)
class ParameterComparison:
    """Compare a parameter against a literal, element-wise."""

    name: str
    op: PredicateOperator
    value: float | str
    dims: tuple[str, ...]


@dataclass(frozen=True)
class ExpressionComparison:
    """Compare two variable-free expressions, coordinate by coordinate — ``p_min <= 0.5 * p_max``.

    ``dims`` is every dim either side carries. A side whose value is absent at
    a coordinate — a parameter row missing, a translation that vacated it —
    makes the comparison false there, as a null does in every other
    comparison; under a summing operator the absent term is one fewer.
    """

    left: Expression
    op: PredicateOperator
    right: Expression
    dims: tuple[str, ...]


@dataclass(frozen=True)
class DimensionComparison:
    """Compare a dimension's own coordinates against a literal."""

    name: str
    op: PredicateOperator
    value: float | str | datetime.date


@dataclass(frozen=True)
class DimensionPosition:
    """Compare where a row sits along a dimension against a position — ``position(snapshot) == 0``.

    Both sides are integers, negative counting from the end. With a
    ``partition`` the position is counted within each group the relation makes
    ([`Partition`][]), whose joined columns' dimensions the frame carries.
    """

    name: str
    op: PredicateOperator
    position: int
    partition: Partition | None = None


@dataclass(frozen=True)
class RelationComparison:
    """Compare one value column of a keyed relation against a literal — ``period_of == 2030``.

    ``column`` is the role read, and ``dims`` the dimensions of the key
    columns: the leaf is read at them, one value per coordinate.
    """

    name: str
    column: str
    op: PredicateOperator
    value: float | str | datetime.date
    dims: tuple[str, ...] = ()


@dataclass(frozen=True)
class RelationPairComparison:
    """Compare a value column of one keyed relation with one of another — ``from_bus != to_bus`` — row by row on the key.

    Both keys are over the same ``dims``, and the two columns are over one
    dimension, so a match is possible at all.
    """

    name: str
    column: str
    other: str
    other_column: str
    op: PredicateOperator
    dims: tuple[str, ...] = ()


@dataclass(frozen=True)
class RelationDefined:
    """True where the relation has a row at the frame's coordinates.

    ``dims`` is what the frame supplies: the key's dimensions, whose row is
    then the one the key finds — every column's for a bare relation, where a
    row is the whole tuple.
    """

    name: str
    dims: tuple[str, ...] = ()


@dataclass(frozen=True)
class CountComparison:
    """How many coordinates *predicate* admits along *over*, against a literal — ``count(points, over=bp) >= 2``.

    The count is one number per coordinate of ``dims``, which is every dim
    *predicate* reads minus *over*, so a claim about each curve is written
    without saying "each curve". A predicate a leaf reads arrives as a
    [`Mask`][], where a connective's operand is a bare [`Predicate`][]:
    a walk recurses through the second and stops at the first.
    """

    predicate: Mask
    over: str
    op: PredicateOperator
    value: float
    dims: tuple[str, ...]


@dataclass(frozen=True)
class TranslatedPredicate:
    """*operand* read at a neighbouring coordinate — ``shift(points, along=bp, offset=1)``.

    False where the translation vacates, and there is no ``edge=`` to state.
    The arithmetic translation needs one because no number is neutral and
    inventing one changes the answer; false is what a missing row already
    means in a mask, so the predicate form has the value the language already
    gives it.
    """

    operand: Mask
    along: str
    offset: int
    dims: tuple[str, ...]


@dataclass(frozen=True)
class PulledBackPredicate:
    """*operand* read through a relation — ``at(has_curve, by=converter_of, over=converter, into=flow)``.

    True at a coordinate where the relation has a row and *operand* holds at
    the coordinate that row reads. False where the relation has no row, which
    is what a missing row already means in a mask. The dims ``direction``
    consumes go and the dims it produces arrive, as [`Pullback`][]'s do.
    """

    operand: Mask
    direction: Direction
    dims: tuple[str, ...]


@dataclass(frozen=True)
class Not:
    operand: Predicate


@dataclass(frozen=True)
class And:
    left: Predicate
    right: Predicate


@dataclass(frozen=True)
class Or:
    left: Predicate
    right: Predicate


#: Every predicate resolution has typed: it names a declaration and the kind is
#: settled. Resolution passes these straight through, having nothing left to
#: decide about them.
TypedPredicate = (
    ParameterComparison
    | ExpressionComparison
    | ParameterDefined
    | VariableDefined
    | DimensionComparison
    | DimensionPosition
    | RelationComparison
    | RelationPairComparison
    | RelationDefined
    | CountComparison
    | TranslatedPredicate
    | PulledBackPredicate
)

#: The boolean connectives — the only where nodes carrying other where nodes,
#: and so the only place a walk over a predicate recurses. The grammar builds
#: these classes directly, over leaves still unresolved, so a pre-resolution
#: tree shares them — the transient impurity resolution normalizes away.
Connective = Not | And | Or

#: Every resolved predicate node. The parser's ``Unresolved*`` nodes are not members: they live with the
#: grammar in [`mathspec._where_parser`][], and resolution rewrites them away
#: before anything here is asked.
Predicate = BooleanLiteral | TypedPredicate | Connective


def where_children(where: Predicate) -> tuple[Predicate, ...]:
    """The predicates under *where* — a connective's operands, and nothing under a leaf.

    What every walk over a predicate recurses through, as [`children`][] is
    for an expression. A leaf has nothing under it whether or not it is
    resolved, so the grammar measures its own output with this too.
    """
    if isinstance(where, Not):
        return (where.operand,)
    if isinstance(where, (And, Or)):
        return (where.left, where.right)
    return ()


def _atoms(where: Predicate) -> Iterator[TypedPredicate]:
    """Every node in *where* that reads a declaration, connectives removed.

    A boolean literal yields nothing.

    Raises:
        AssertionError: An unresolved node reached the walk.
    """
    if isinstance(where, TypedPredicate):
        yield where
    elif isinstance(where, BooleanLiteral | Connective):
        for child in where_children(where):
            yield from _atoms(child)
    else:
        msg = f'{type(where).__name__} reached a predicate walk unresolved.'
        raise AssertionError(msg)


def _atom_dims(atom: TypedPredicate) -> frozenset[str]:
    """One leaf's dims — the rule [`Mask.dims`][] is the union of.

    A parameter or variable leaf carries its own dims off the declaration; a
    comparison on a dimension is read through that dimension, and a relation
    through the dimensions of the columns it is read at — its key for a
    comparison, every column for a bare existence.
    Separate from the union because the load-time frame check reports per
    leaf. Closed by ``assert_never``: a predicate node added without a reading
    is a type error here, at the one place that has to grow a branch, rather
    than a wrong dim set at the first spec to use it.
    """
    match atom:
        case (
            ParameterComparison()
            | ExpressionComparison()
            | ParameterDefined()
            | VariableDefined()
            | CountComparison()
            | TranslatedPredicate()
            | RelationComparison()
            | RelationPairComparison()
            | RelationDefined()
            | PulledBackPredicate()
        ):
            return frozenset(atom.dims)
        case DimensionComparison():
            return frozenset({atom.name})
        case DimensionPosition():
            return frozenset({atom.name, *(atom.partition.joined_dims if atom.partition is not None else ())})
        case _:
            assert_never(atom)


def _atom_names(atom: TypedPredicate) -> frozenset[str]:
    """One leaf's declarations, its dimension apart — the rule [`Mask.names_read`][] is the union of.

    A comparison on a dimension names no declaration — a coordinate is not
    data to feed — a relation pair names both maps it compares, and a
    comparison of expressions names every parameter and relation its sides
    read, answered on the program's form of it since only a program mask is
    asked. ``assert_never``-closed for the reason [`_atom_dims`][] is: a predicate
    node added without a reading is a type error at this one branch rather
    than a name silently dropped at the first spec to use it.
    """
    match atom:
        case ParameterComparison() | ParameterDefined() | VariableDefined() | RelationComparison() | RelationDefined():
            return frozenset({atom.name})
        case RelationPairComparison():
            return frozenset({atom.name, atom.other})
        case ExpressionComparison():
            return _names_under(atom.left, atom.right)
        case CountComparison():
            return atom.predicate.names_read
        case TranslatedPredicate():
            return atom.operand.names_read
        case PulledBackPredicate():
            return atom.operand.names_read | {atom.direction.name}
        case DimensionComparison() | DimensionPosition():
            return frozenset()
        case _:
            assert_never(atom)


def _names_under(*expressions: Expression) -> frozenset[str]:
    """Every parameter and relation the data has to supply for *expressions* — what a mask's ``names_read`` promises.

    [`parameters_of`][] alone misses the data an operator reads beside its
    operand: the relation a grouping or a pullback reads through, the one a
    translation or a window is partitioned by, the parameter a named offset or
    width is read from, and whatever decides which region of a cased value
    applies.
    """
    names: set[str] = set(parameters_of(*expressions))
    for node in walk(*expressions):
        if isinstance(node, Cases):
            names.update(*(region.when.names_read for region in node.regions))
        elif isinstance(node, (GroupSum, Pullback)):
            names.add(node.direction.name)
        elif isinstance(node, (Translate, WindowSum)):
            if node.partition is not None:
                names.add(node.partition.name)
            amount = node.offset if isinstance(node, Translate) else node.width
            if isinstance(amount, str):
                names.add(amount)
    return frozenset(names)


def _conjuncts(where: Predicate) -> tuple[Predicate, ...]:
    """The flatten rule behind [`Mask.conjuncts`][] — the one home of the split.

    ``a AND b AND c`` gives three, and a predicate that is not an ``AND`` gives
    itself. The walk stops at the first node that is not an ``AND``: the
    conjuncts of ``a AND (b OR c)`` are ``a`` and ``b OR c``, and of
    ``NOT (a AND b)`` the single ``NOT`` — neither an ``OR`` nor a ``NOT`` is a
    claim the predicate makes on its own, so neither is split.
    """
    if isinstance(where, And):
        return _conjuncts(where.left) + _conjuncts(where.right)
    return (where,)


def _fold(node: Predicate) -> Predicate:
    """*node* with every connective a literal or a double negation decides evaluated away.

    ``X AND True`` is ``X``, ``X OR True`` is every row, ``X AND False`` is
    none, ``NOT True`` is ``False`` and ``NOT NOT X`` is ``X``. What survives
    is a predicate over data, or the one literal the whole mask reduces to —
    the invariant [`Mask`][] applies at construction, so it holds wherever
    a mask is built.
    """
    if isinstance(node, Not):
        operand = _fold(node.operand)
        if isinstance(operand, BooleanLiteral):
            return BooleanLiteral(not operand.value)
        if isinstance(operand, Not):
            return operand.operand
        return Not(operand)
    if isinstance(node, And):
        left, right = _fold(node.left), _fold(node.right)
        if isinstance(left, BooleanLiteral):
            return right if left.value else left
        if isinstance(right, BooleanLiteral):
            return left if right.value else right
        return And(left, right)
    if isinstance(node, Or):
        left, right = _fold(node.left), _fold(node.right)
        if isinstance(left, BooleanLiteral):
            return left if left.value else right
        if isinstance(right, BooleanLiteral):
            return right if right.value else left
        return Or(left, right)
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

    root: Predicate

    def __post_init__(self) -> None:
        object.__setattr__(self, 'root', _fold(self.root))
        _ = self.atoms  # the walk is the refusal, and runs after the fold

    @cached_property
    def atoms(self) -> tuple[TypedPredicate, ...]:
        """The mask's leaves, connectives removed — the one walk the other questions read.

        Held rather than re-walked: construction takes this walk anyway, to
        refuse an unresolved tree, and a mask cannot change afterwards.
        """
        return tuple(_atoms(self.root))

    @property
    def conjuncts(self) -> tuple[Predicate, ...]:
        """The predicates the mask joins with ``AND`` — its ``AND`` spine flattened, stopping at an ``OR`` or a ``NOT``."""
        return _conjuncts(self.root)

    @property
    def names_read(self) -> frozenset[str]:
        """The parameters, relations and variables the mask names."""
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
        return Mask(Not(self.root))

    def __and__(self, other: Mask) -> Mask:
        """Both masks at once — construction absorbs a literal side rather than burying it."""
        return Mask(And(self.root, other.root))

    def __or__(self, other: Mask) -> Mask:
        """Either mask — construction absorbs a literal side rather than burying it."""
        return Mask(Or(self.root, other.root))
