# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The program: what a file declares, with names resolved and shapes fixed.

A :class:`Program` is a complete declarative description of a linear program
over named tidy tables — every declaration a file makes, and no data in it at
all. Data is bound against these declarations by whatever builds the model;
:func:`~math_spec.lowering.to_program` is what produces one from a spec.

**It is the second public state, and the one a consumer reads.** A
:class:`~math_spec.model.Spec` is what the file *says*; a program is what it
*means*, with macros expanded, names typed, operators resolved to nodes and
every dim rule already checked. Consumers dispatch on these nodes and read
them; nothing here is built by hand, so what ships beside the nodes is the
walk (:func:`children`), not builders.

A mask is the language's own resolved ``where`` node
(:mod:`math_spec.where_parser`) rather than a second set spelling the same
predicates — one home, so the two cannot come to disagree about what a
comparison is.

Frozen dataclasses only — no execution logic, and nothing imported from a
consumer.

Expressions support operator sugar so programs read naturally in Python:

balance = GroupSum(Variable("p"), over="generator", coordinate=("bus",), into=("bus",)) - Parameter("load")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Literal, NamedTuple

from math_spec.errors import did_you_mean

if TYPE_CHECKING:
    from collections.abc import Iterator

    from math_spec.where_parser import WhereNode


ConstraintSense = Literal['==', '<=', '>=']

#: How a shape operator's output rows relate to its input slots — the absence
#: rules' own distinction, as a field. ``sum``, ``sum(by=)`` and a window put
#: several input slots into one output row, so an absent slot there is one
#: summand fewer and the row stands; a pullback and a translation are one slot
#: for one, so an absent input *is* the output and takes the row with it.
#: Declared on the node because a consumer keeping its own list of which is
#: which would be deciding a rule the language has already decided.
FanIn = Literal['one-to-one', 'many-to-one', 'one-to-many']
ObjectiveSense = Literal['minimize', 'maximize']
ComparisonOperator = Literal['==', '!=', '<=', '>=', '<', '>']
VariableType = Literal['continuous', 'binary', 'integer']

#: What a masked variable's non-existence means where it does not exist.
#: ``undefined`` is the absence rules' default — a term carrying it takes its
#: row. ``zero`` says the quantity *is* zero there, so the term contributes
#: nothing and the row stands.
VariableAbsence = Literal['undefined', 'zero']

#: What a dimension's labels are. ``datetime`` is a dimension's alone — labels
#: on a timeline order and compare, where a *value* of that type is a moment
#: nothing computes with.
DimensionDtype = Literal['float', 'int', 'str', 'datetime']

#: What a parameter's values are. ``bool`` is a parameter's alone — a value
#: column may be a flag a mask reads, where a label set of two members is a
#: dimension nothing indexes by.
ParameterDtype = Literal['float', 'int', 'bool', 'str']


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

    fan_in: ClassVar[FanIn] = 'many-to-one'

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

    fan_in: ClassVar[FanIn] = 'many-to-one'

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

    fan_in: ClassVar[FanIn] = 'one-to-one'

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

    fan_in: ClassVar[FanIn] = 'one-to-one'

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

    fan_in: ClassVar[FanIn] = 'one-to-many'

    operand: ExpressionNode
    dimension: str
    width: int | str
    wrap: bool
    partition: str | None = None


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
)


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
    return ()


# --------------------------------------------------------------------------
# Declarations
# --------------------------------------------------------------------------


class LookupDeclaration(NamedTuple):
    """One declared lookup and the dimension its values are labels of."""

    name: str
    target: str


@dataclass(frozen=True)
class DimensionDeclaration:
    """A dimension and the lookups its labels carry.

    ``lookups`` names each lookup and the dimension its values are labels of,
    checked for containment once the dim tables exist — which keeps a mistyped
    label from silently dropping its terms in the join that places them.

    ``label_spaces`` are the inline kind: maps the dimension owns outright,
    with no target and so nothing to check. They are read for selection and
    rendering, and resolution refuses to group into one, so no expression node
    reaches them.
    """

    name: str
    lookups: tuple[LookupDeclaration, ...] = ()
    label_spaces: tuple[str, ...] = ()
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
        return sorted([*(lk.name for lk in self.lookups), *self.label_spaces])

    @property
    def targets(self) -> dict[str, str]:
        """Each targeted map over the dimension, to the dimension its values are labels of.

        The question every consumer of a ``by=`` asks, and asked here so it has
        one answer: an operator grouping through a lookup names the target as
        the dim it lands on, and a partition array is named for it so an amount
        declared over the group's own dim can be read through it.
        """
        return {lk.name: lk.target for lk in self.lookups}


@dataclass(frozen=True)
class ParameterDeclaration:
    """Shape declaration; data is bound at execution time by name.

    ``dtype`` is what the declaration claims the values are, and a consumer
    binding data refuses a column that is not it — so the *declaration* is
    what is read, rather than whatever the column happens to hold.
    """

    name: str
    dims: tuple[str, ...]
    dtype: ParameterDtype = 'float'


@dataclass(frozen=True)
class VariableDeclaration:
    name: str
    dims: tuple[str, ...]
    where: WhereNode | None = None
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

    name: str
    dims: tuple[str, ...]
    lhs: ExpressionNode
    sense: ConstraintSense
    rhs: ExpressionNode
    where: WhereNode | None = None


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

    name: str
    variable: str
    over: str
    sos_type: Literal[1, 2]
    big_m: float | None = None


@dataclass(frozen=True)
class ObjectiveDeclaration:
    """Objective — scalar, every reduction in it one the file wrote."""

    sense: ObjectiveSense
    expression: ExpressionNode


def _declared[Declaration: (ParameterDeclaration, VariableDeclaration, ConstraintDeclaration)](
    items: tuple[Declaration, ...], name: str, kind: str
) -> Declaration:
    """The declaration called *name*, or a ``KeyError`` naming the near miss."""
    for item in items:
        if item.name == name:
            return item
    raise KeyError(f"unknown {kind} '{name}'. " + did_you_mean(name, [i.name for i in items]))


@dataclass(frozen=True)
class Program:
    """A complete linear program over named tidy tables."""

    parameters: tuple[ParameterDeclaration, ...]
    variables: tuple[VariableDeclaration, ...]
    constraints: tuple[ConstraintDeclaration, ...]
    #: ``None`` where the file declares no objective — a feasibility problem,
    #: whose answer is whether the constraints can be met at all.
    objective: ObjectiveDeclaration | None
    dimensions: tuple[DimensionDeclaration, ...] = ()
    sos: tuple[SosDeclaration, ...] = ()
    #: Declared ``expressions:``, lowered. Not part of the program a solver
    #: sees — none of them builds a row — but lowered with it, so a file whose
    #: named expression is outside the language is refused by every verb that
    #: reads the file rather than only by the one that reads the expression.
    #: Keyed rather than a tuple of declarations because a reader asks for one
    #: by the name it wrote, and nothing iterates them in order.
    expressions: dict[str, ExpressionNode] = field(default_factory=dict)

    def dimension(self, name: str) -> DimensionDeclaration:
        """The dimension called *name*.

        Undeclared is not an error here: a dimension with no lookups has
        nothing to declare.
        """
        for d in self.dimensions:
            if d.name == name:
                return d
        return DimensionDeclaration(name)

    @property
    def lookups(self) -> tuple[tuple[str, LookupDeclaration], ...]:
        """Every targeted map in the program, with the dimension it is over.

        One walk for the several shapes consumers want it in — name to target,
        target to origin, the set of targets — because the nested comprehension
        that produces any of them is the same walk written again.
        """
        return tuple((d.name, lk) for d in self.dimensions for lk in d.lookups)

    def parameter(self, name: str) -> ParameterDeclaration:
        return _declared(self.parameters, name, 'parameter')

    def variable(self, name: str) -> VariableDeclaration:
        return _declared(self.variables, name, 'variable')


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


def declares_quadratic(c: ConstraintDeclaration) -> bool:
    """Whether constraint *c*'s expression multiplies two variable-carrying operands.

    One home, because unrelated readers act on it — what a solver must
    support, which declarations to build last — and a third side added to a
    constraint has to be found by every one of them.
    """
    return is_quadratic(c.lhs) or is_quadratic(c.rhs)


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
