# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Does a set of case masks partition a constraint's rows? Decided without data.

A constraint with ``cases:`` is one rule whose expression varies by region. It
is *one* constraint — one name, one row per coordinate, one dual — only if the
cases claim each row **exactly once**. That claim is decidable here, before any
data binds, which is rule 2 in a new position.

Two obligations, both conditioned on the constraint's own ``where`` (the rows
that exist at all), and both the same unsatisfiability question:

* **disjoint** — ``where AND case_i AND case_j`` is unsatisfiable, for every pair
* **exhaustive** — ``where AND NOT (case_1 OR ... OR case_n)`` is unsatisfiable

and one that falls out of the same machinery for free:

* **no dead case** — ``where AND case_i`` unsatisfiable means that block builds
  no rows, which is a mistake rather than a no-op.

Conditioning matters in both directions. Two cases that overlap somewhere the
``where`` already excludes are *not* an ambiguity, and an unconditional check
would refuse them; a ``where`` wider than the cases cover is a real gap that a
"the rows are whatever the cases claim" reading could not even express.

## How it decides

Every atom in the where-grammar talks about exactly one **subject** — a
parameter, a dimension's coordinates, a dimension's *rank*, a lookup, a pair of
lookups. Atoms with different subjects are independent; atoms sharing one are
not, and that is where a propositional reading goes wrong: on `kind == 'battery'`
and `kind == 'h2'` it invents a world where both hold and reports an overlap
that no data can produce.

So each subject is split into **cells** — finitely many regions its value can
sit in, chosen so that every atom over that subject is constant on each cell.
The cells of all subjects are multiplied out, and each masks is evaluated on
each cell. A cell where two cases are true is a witness for overlap; a cell
inside ``where`` where none is, a witness for a gap. Because the cells cover
every value the subject can take, "no witness" is a proof and not a sample.

## Three outcomes, and why the third is not optional

:attr:`Status.PARTITION`, :attr:`Status.VIOLATED` and
:attr:`Status.UNDECIDED`. Undecided is *refused* by the caller, never assumed:
a checker that guesses in the cases it cannot decide buys nothing over no
checker at all. What lands there is named in :class:`Verdict.reason` along with
the rewrite — the common one being two ``position()`` splits counted from
opposite ends of a dimension whose extent only data knows, where ``0`` and
``-1`` are the same row on a one-member axis and the split is a partition
everywhere else.

Independence between subjects is an **over**-approximation: the product of
cells contains worlds the data may never produce, so a spurious world can only
manufacture a witness, never hide one. Every outcome here is therefore
conservative — this refuses groups that would have been fine, and admits none
that would not.

Not wired into the schema: ``cases:`` is not a key the model accepts yet
(energy-models/math-spec#2), and which spelling it lands on does not change
anything below.
"""

from __future__ import annotations

import datetime
import itertools
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

from math_spec.where_parser import (
    AndNode,
    BooleanLiteralNode,
    DimensionComparisonNode,
    DimensionPositionNode,
    LookupComparisonNode,
    LookupDefinedNode,
    LookupPairComparisonNode,
    NotNode,
    OrNode,
    ParameterComparisonNode,
    ParameterDefinedNode,
    VariableDefinedNode,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from math_spec.model import Model
    from math_spec.where_parser import PredicateOperator, WhereNode

#: The product of every subject's cells is enumerated, so the bound is on the
#: product rather than on any one subject. Real masks carry two to four atoms;
#: a group that blows this is telling you it is several constraints.
CELL_BUDGET = 8192


class Status(Enum):
    """What the check established. :attr:`UNDECIDED` is a refusal, not a pass."""

    PARTITION = 'partition'
    VIOLATED = 'violated'
    UNDECIDED = 'undecided'


# ---------------------------------------------------------------------------
# cells
# ---------------------------------------------------------------------------


class Special(Enum):
    """Values a cell can hold that are not values of the subject's own type."""

    #: No row in the table. A null compares false whatever the comparator, and
    #: is not `defined`.
    NULL = 'null'
    #: A magnitude, and the one that is a *value* everywhere else but is not
    #: `defined` — see the bare-name row of the where-string table.
    POS_INF = '+inf'
    NEG_INF = '-inf'
    #: A label none of the masks names. Stands for every such label at once,
    #: which they cannot tell apart.
    OTHER = 'other'


#: What one subject's value is, in one cell.
Cell = float | str | bool | int | datetime.date | Special


@dataclass(frozen=True)
class Subject:
    """What an atom talks about — the key its cells are built for.

    ``kind`` separates the namespaces that could otherwise collide: a
    dimension's coordinates and its *rank* are two subjects over one name, and
    a rank is further split by the ``by=`` lookup it is counted within.
    """

    kind: Literal['param', 'dim', 'rank', 'lookup', 'lookup_pair', 'variable']
    name: str
    qualifier: str | None = None

    def __str__(self) -> str:
        if self.kind == 'rank':
            within = f' within {self.qualifier}' if self.qualifier else ''
            return f'the position of {self.name}{within}'
        if self.kind == 'lookup_pair':
            return f'{self.name} vs {self.qualifier}'
        return self.name


class Undecidable(Exception):  # noqa: N818
    """An atom this procedure will not reason about. Carries the rewrite."""


# ---------------------------------------------------------------------------
# the verdict
# ---------------------------------------------------------------------------

#: One cell, as ``subject -> value``, rendered for a message.
Witness = dict[str, str]


@dataclass(frozen=True)
class Overlap:
    """Two cases that can both claim one row."""

    cases: tuple[str, str]
    witness: Witness


@dataclass(frozen=True)
class Gap:
    """A row the ``where`` builds that no case gives an expression to."""

    witness: Witness


@dataclass(frozen=True)
class Verdict:
    status: Status
    overlaps: tuple[Overlap, ...] = ()
    gaps: tuple[Gap, ...] = ()
    dead: tuple[str, ...] = ()
    reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.status is Status.PARTITION

    def message(self) -> str:
        """What a load error would print. Empty for a proven partition."""
        if self.status is Status.PARTITION:
            return ''
        if self.status is Status.UNDECIDED:
            return f'cannot decide statically: {self.reason}'
        parts = []
        for overlap in self.overlaps:
            first, second = overlap.cases
            parts.append(f"cases '{first}' and '{second}' both claim a row where {_render(overlap.witness)}")
        parts.extend(f'no case claims the row where {_render(gap.witness)}' for gap in self.gaps)
        parts.extend(f"case '{name}' builds no rows" for name in self.dead)
        return '; '.join(parts)


def _render(witness: Witness) -> str:
    return ', '.join(f'{subject} is {value}' for subject, value in witness.items())


@dataclass(frozen=True)
class Case:
    """One case of a group: a mask, and the name the LaTeX prints beside it.

    Every case carries one. An open "everything the others left" case would
    save restating a long mask, but nothing else — ``not (x)`` says the same
    thing, and a mask edited without its restated negation is a gap or an
    overlap here rather than a silent change of model.
    """

    name: str
    when: WhereNode


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def check_partition(where: WhereNode | None, cases: Iterable[Case], schema: Model) -> Verdict:
    """Decide whether *cases* partition the rows *where* builds.

    Args:
        where: The constraint's own mask — the rows that exist. ``None`` is
            everything the ``foreach`` spans.
        cases: The cases, in declaration order, each with its own mask.
        schema: Read for dtypes, and for the declared ``values:`` that give a
            dimension a statically known extent.

    Returns:
        The verdict. :attr:`Status.UNDECIDED` is a refusal — see the module
        docstring.
    """
    cases = list(cases)
    masks = [node for node in [where, *(case.when for case in cases)] if node is not None]
    try:
        domains = _domains(masks, schema)
    except Undecidable as exc:
        return Verdict(Status.UNDECIDED, reason=str(exc))

    # The cells of a rank subject are counted from the front wherever the
    # extent is known, so the positions the atoms carry have to be read in that
    # same frame — `position(dim) == -1` on a three-member axis is rank 2.
    extents = {
        subject: extent
        for subject in domains
        if subject.kind == 'rank' and (extent := _extent_of(subject, schema)) is not None
    }

    size = math.prod(len(cells) for cells in domains.values()) if domains else 1
    if size > CELL_BUDGET:
        return Verdict(
            Status.UNDECIDED,
            reason=f'{size} regions to check exceeds the budget of {CELL_BUDGET} — split this into named constraints',
        )

    overlaps: list[Overlap] = []
    gaps: list[Gap] = []
    live: set[str] = set()
    try:
        for cell in _cells(domains):
            if not _evaluate(where, cell, extents):
                continue
            hits = [case.name for case in cases if _evaluate(case.when, cell, extents)]
            if len(hits) > 1:
                overlaps.append(Overlap((hits[0], hits[1]), _witness(cell)))
            elif not hits:
                gaps.append(Gap(_witness(cell)))
            live.update(hits)
    except Undecidable as exc:
        return Verdict(Status.UNDECIDED, reason=str(exc))

    dead = tuple(case.name for case in cases if case.name not in live)
    if overlaps or gaps or dead:
        return Verdict(Status.VIOLATED, tuple(overlaps[:4]), tuple(gaps[:4]), dead)
    return Verdict(Status.PARTITION)


# ---------------------------------------------------------------------------
# building the cells
# ---------------------------------------------------------------------------


@dataclass
class _Observed:
    """What the masks say about one subject, before it is cut into cells."""

    literals: set[Any] = field(default_factory=set)
    positions: set[int] = field(default_factory=set)
    bare: bool = False
    ordered: bool = False


def _domains(masks: Iterable[WhereNode], schema: Model) -> dict[Subject, list[Cell]]:
    observed: dict[Subject, _Observed] = {}
    for mask in masks:
        for node in _walk(mask):
            _observe(node, observed, schema)
    return {subject: _cells_for(subject, seen, schema) for subject, seen in observed.items()}


def _walk(node: WhereNode | None) -> Iterator[WhereNode]:
    """Every atom in *node*; the connectives are stepped through."""
    if node is None:
        return
    if isinstance(node, NotNode):
        yield from _walk(node.operand)
    elif isinstance(node, AndNode | OrNode):
        yield from _walk(node.left)
        yield from _walk(node.right)
    else:
        yield node


def _observe(node: WhereNode, observed: dict[Subject, _Observed], schema: Model) -> None:
    subject = _subject_of(node)
    if subject is None:
        return
    seen = observed.setdefault(subject, _Observed())
    if isinstance(node, ParameterDefinedNode | VariableDefinedNode | LookupDefinedNode):
        seen.bare = True
    elif isinstance(node, DimensionPositionNode):
        # Every comparator reads here: `position()` converts the dimension to
        # an integer, so an ordering is an ordering of integers (#32).
        seen.positions.add(node.position)
    elif isinstance(node, LookupPairComparisonNode):
        if node.op not in ('==', '!='):
            msg = f'{subject} compared with {node.op!r}; two lookups compare only with == or !='
            raise Undecidable(msg)
    elif isinstance(node, ParameterComparisonNode | DimensionComparisonNode | LookupComparisonNode):
        if node.op not in ('==', '!='):
            seen.ordered = True
        seen.literals.add(node.value)
    if seen.ordered and isinstance(node, ParameterComparisonNode | DimensionComparisonNode | LookupComparisonNode):
        dtype = _dtype_of(subject, schema)
        if dtype not in ('float', 'int', 'datetime', 'date'):
            msg = f'{subject} has dtype {dtype!r} and is ordered with {node.op!r}; only == and != are decided here'
            raise Undecidable(msg)


def _subject_of(node: WhereNode) -> Subject | None:
    match node:
        case BooleanLiteralNode():
            return None
        case ParameterDefinedNode(name=name) | ParameterComparisonNode(name=name):
            return Subject('param', name)
        case VariableDefinedNode(name=name):
            return Subject('variable', name)
        case DimensionComparisonNode(name=name):
            return Subject('dim', name)
        case DimensionPositionNode(name=name, by=by):
            return Subject('rank', name, by)
        case LookupDefinedNode(name=name) | LookupComparisonNode(name=name):
            return Subject('lookup', name)
        case LookupPairComparisonNode(name=name, other=other):
            return Subject('lookup_pair', name, other)
        case _:
            msg = f'{type(node).__name__} is not an atom this procedure knows'
            raise Undecidable(msg)


def _dtype_of(subject: Subject, schema: Model) -> str | None:
    if subject.kind == 'param':
        block = schema.parameters.get(subject.name)
        return None if block is None else block.dtype
    if subject.kind == 'dim':
        block = schema.dimensions.get(subject.name)
        return None if block is None else block.dtype
    return None


def _cells_for(subject: Subject, seen: _Observed, schema: Model) -> list[Cell]:
    if subject.kind == 'rank':
        return _rank_cells(subject, seen, schema)
    if subject.kind == 'lookup_pair':
        return [True, False]
    if subject.kind == 'variable':
        return [True, False]
    dtype = _dtype_of(subject, schema)
    if dtype == 'bool':
        if seen.literals:
            msg = f'{subject} has dtype bool and is compared to a literal'
            raise Undecidable(msg)
        return [Special.NULL, True, False]
    numeric = _numeric(dtype, seen.literals)
    cells: list[Cell] = []
    # A dimension's coordinates are its own index, so there is no null among
    # them; everything else may be absent, and absence is a region of its own
    # because a null compares false and is not `defined`.
    if subject.kind != 'dim':
        cells.append(Special.NULL)
        if numeric:
            # `defined` excludes an infinity, so it needs a region where every
            # comparison still reads normally but the bare name is false.
            cells.extend([Special.NEG_INF, Special.POS_INF])
    cells.extend(_ordered_cells(seen.literals) if numeric or _dated(seen.literals) else _label_cells(seen.literals))
    return cells


def _numeric(dtype: str | None, literals: set[Any]) -> bool:
    """Is this subject a magnitude? The declaration says so where it is known."""
    if dtype is not None:
        return dtype in ('float', 'int')
    return bool(literals) and all(isinstance(value, int | float) and not isinstance(value, bool) for value in literals)


def _dated(literals: set[Any]) -> bool:
    return bool(literals) and all(isinstance(value, datetime.date) for value in literals)


def _ordered_cells(literals: set[Any]) -> list[Cell]:
    """Each literal, and one representative of the gap on either side of it.

    The representatives stand for every value in their gap, which they may
    because each atom over this subject compares against one of the literals —
    so two values with no literal between them are indistinguishable to every
    mask here.
    """
    if not literals:
        return [0.0]
    values = sorted(literals)
    step = _step(values[0])
    cells: list[Cell] = [values[0] - step]
    for index, value in enumerate(values):
        cells.append(value)
        following = values[index + 1] if index + 1 < len(values) else None
        if following is None:
            continue
        between = _between(value, following, step)
        if between is not None:
            cells.append(between)
    cells.append(values[-1] + step)
    return cells


def _step(value: Any) -> Any:
    """How far outside the named literals a representative has to sit."""
    if isinstance(value, datetime.datetime):
        return datetime.timedelta(seconds=1)
    if isinstance(value, datetime.date):
        return datetime.timedelta(days=1)
    return 1.0


def _between(value: Any, following: Any, step: Any) -> Any | None:
    """A value strictly between two literals, where the type admits one.

    A magnitude always does — the midpoint. A date is discrete, so the gap has
    to be wider than one unit before there is anything in it to stand for.
    """
    if isinstance(value, datetime.date):
        return value + step if following - value > step else None
    return (value + following) / 2.0


def _label_cells(literals: set[Any]) -> list[Cell]:
    """Every named label, and one standing for all the labels not named."""
    return [*sorted(literals, key=str), Special.OTHER]


def _rank_cells(subject: Subject, seen: _Observed, schema: Model) -> list[Cell]:
    """Representative ranks, in one frame — counted from the front or the back.

    ``position(dim) == 0`` and ``position(dim) == -1`` are the same row when
    the dimension has one member, so mixing the two frames is only decidable
    where the extent is. A dimension that declares ``values:`` has one; a
    dimension whose coordinates arrive from data does not, and neither does any
    group a ``by=`` lookup makes, whatever the parent dimension declares.

    Within one frame the cells are its own mirror image. Counting from the
    front, ranks run away from 0 and the open end is *after* the last position
    named; counting from the back they run away from -1 and the open end is
    *before* the first. Getting that backwards costs nothing while only ``==``
    and ``!=`` read — a representative on the wrong side still tells the named
    positions apart — and gives wrong answers the moment an ordering does.
    """
    positions = sorted(seen.positions)
    extent = _extent_of(subject, schema)
    if extent is not None:
        positions = sorted({position + extent if position < 0 else position for position in positions})
        positions = [position for position in positions if 0 <= position < extent]
    elif positions and positions[0] < 0 <= positions[-1]:
        within = f' within each {subject.qualifier} group' if subject.qualifier else ''
        msg = (
            f'{subject.name} is split at positions counted from both ends{within} '
            f'({", ".join(str(position) for position in sorted(seen.positions))}), and its extent is not declared, '
            f'so they are the same row on a short axis — declare `values:` for {subject.name}, or split at one end'
        )
        raise Undecidable(msg)
    if not positions:
        return [0]
    from_back = positions[-1] < 0
    cells: list[Cell] = []
    if from_back:
        # The open end is before the earliest position named; there is nothing
        # after -1, which is the last row by definition.
        cells.append(positions[0] - 1)
    elif positions[0] > 0:
        cells.append(positions[0] - 1)
    for index, position in enumerate(positions):
        cells.append(position)
        following = positions[index + 1] if index + 1 < len(positions) else None
        if following is not None and following - position > 1:
            cells.append(position + 1)
    if from_back:
        if positions[-1] < -1:
            cells.append(positions[-1] + 1)
    else:
        beyond = positions[-1] + 1
        if extent is None or beyond < extent:
            cells.append(beyond)
    return cells


def _extent_of(subject: Subject, schema: Model) -> int | None:
    """How many members the axis has, where the file says. ``by=`` never does."""
    if subject.qualifier is not None:
        return None
    block = schema.dimensions.get(subject.name)
    if block is None or block.values is None:
        return None
    return len(block.values)


def _cells(domains: dict[Subject, list[Cell]]) -> Iterator[dict[Subject, Cell]]:
    subjects = list(domains)
    for combination in itertools.product(*(domains[subject] for subject in subjects)):
        yield dict(zip(subjects, combination, strict=True))


def _witness(cell: dict[Subject, Cell]) -> Witness:
    return {str(subject): _shown(subject, value) for subject, value in cell.items()}


def _shown(subject: Subject, value: Cell) -> str:
    if subject.kind == 'rank':
        return f'{value}'
    if subject.kind == 'lookup_pair':
        return 'equal' if value else 'different'
    if isinstance(value, Special):
        return {Special.NULL: 'absent', Special.OTHER: 'anything else'}.get(value, value.value)
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return f'{value!r}'


# ---------------------------------------------------------------------------
# evaluating a mask on one cell
# ---------------------------------------------------------------------------


def _evaluate(node: WhereNode | None, cell: dict[Subject, Cell], extents: dict[Subject, int]) -> bool:
    """Is *node* true in this cell? An absent mask is true everywhere."""
    if node is None:
        return True
    match node:
        case BooleanLiteralNode(value=value):
            return value
        case NotNode(operand=operand):
            return not _evaluate(operand, cell, extents)
        case AndNode(left=left, right=right):
            return _evaluate(left, cell, extents) and _evaluate(right, cell, extents)
        case OrNode(left=left, right=right):
            return _evaluate(left, cell, extents) or _evaluate(right, cell, extents)
        case _:
            return _atom(node, cell, extents)


def _atom(node: WhereNode, cell: dict[Subject, Cell], extents: dict[Subject, int]) -> bool:
    subject = _subject_of(node)
    assert subject is not None
    value = cell[subject]
    match node:
        case ParameterDefinedNode() | LookupDefinedNode():
            # What `defined` means is the declaration's to say: a bool is its
            # own answer, and a number has to be finite as well.
            if isinstance(value, bool):
                return value
            return value not in (Special.NULL, Special.POS_INF, Special.NEG_INF)
        case VariableDefinedNode():
            return bool(value)
        case LookupPairComparisonNode(op=op):
            return bool(value) if op == '==' else not value
        case DimensionPositionNode(op=op, position=position):
            extent = extents.get(subject)
            if extent is not None and position < 0:
                position += extent
            return _compare(value, op, position)
        case ParameterComparisonNode(op=op, value=literal) | LookupComparisonNode(op=op, value=literal):
            # A null compares false, whatever the comparator.
            if value is Special.NULL:
                return False
            return _compare(value, op, literal)
        case DimensionComparisonNode(op=op, value=literal):
            return _compare(value, op, literal)
        case _:
            msg = f'{type(node).__name__} is not an atom this procedure knows'
            raise Undecidable(msg)


def _compare(value: Cell, op: PredicateOperator, literal: Any) -> bool:
    """One atom's truth in one cell. Both sides are already this cell's frame."""
    if isinstance(value, Special):
        if value is Special.OTHER:
            # A label none of the masks names, so it matches none of them and
            # sorts nowhere — an ordering against it is not decided here.
            if op in ('==', '!='):
                return op == '!='
            msg = f'an unnamed label ordered with {op!r}'
            raise Undecidable(msg)
        magnitude = math.inf if value is Special.POS_INF else -math.inf
        return _numeric_compare(magnitude, op, float(literal))
    if isinstance(value, int | float) and isinstance(literal, int | float) and not isinstance(value, bool):
        return _numeric_compare(float(value), op, float(literal))
    if type(value) is not type(literal) and not isinstance(value, type(literal)):
        # Different types cannot be equal, and are not ordered against each
        # other — which resolution has already refused, so this is the
        # date-against-date case reached with one side a representative.
        if op in ('==', '!='):
            return op == '!='
        msg = f'{value!r} ordered against {literal!r}'
        raise Undecidable(msg)
    return _numeric_compare(value, op, literal)


def _numeric_compare(left: Any, op: PredicateOperator, right: Any) -> bool:
    match op:
        case '==':
            return bool(left == right)
        case '!=':
            return bool(left != right)
        case '<':
            return bool(left < right)
        case '<=':
            return bool(left <= right)
        case '>':
            return bool(left > right)
        case '>=':
            return bool(left >= right)
