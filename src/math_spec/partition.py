# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Do a named expression's cases partition its frame? Decided without data.

A named expression with ``cases:`` is one quantity whose value varies by
region — the regime a unit is in, which end of the horizon a row sits at. It is
*one* quantity, with one value per coordinate, only if the cases claim each
coordinate **exactly once**. That claim is decidable here, before any data
binds, which is rule 2 in a new position.

Three obligations, all the same unsatisfiability question:

* **disjoint** — ``case_i AND case_j`` is unsatisfiable, for every pair. Two
  values at one coordinate is not a quantity.
* **exhaustive** — ``NOT (case_1 OR ... OR case_n)`` is unsatisfiable. An
  expression is **total** over its ``foreach``: a gap would leave it undefined,
  and rule 7 would spread that to every constraint referencing it, silently
  deleting rows the constraint never masked.
* **no dead case** — ``case_i`` alone is satisfiable. A case that claims
  nothing is a mistake rather than a no-op.

Nothing is conditioned on a mask, because an expression carries none: it is
total or it is refused. That is what keeps a constraint's row set readable at
the constraint, which is the whole reason the cases sit here rather than there.

Every atom in the where-grammar talks about exactly one **subject** — a
parameter, a dimension's coordinates, a dimension's *rank*, a lookup, a pair of
lookups. Atoms with different subjects are independent; atoms sharing one are
not, and that is where a propositional reading goes wrong: on `kind == 'battery'`
and `kind == 'h2'` it invents a world where both hold and reports an overlap
that no data can produce.

So each subject is split into **cells** — finitely many regions its value can
sit in, chosen so that every atom over that subject is constant on each cell.
The cells of all subjects are multiplied out and each mask is evaluated on each
cell. A cell where two cases are true is a witness for overlap; a cell where
none is, a witness for a gap. Because the cells cover every value the subject
can take, "no witness" is a proof and not a sample.

Independence between subjects is an **over**-approximation: the product of
cells contains worlds the data may never produce, so a spurious world can only
manufacture a witness, never hide one. Every outcome here is therefore
conservative — this refuses case sets that would have been fine, and admits
none that would not.

Run at load by :func:`math_spec.validation.validate_expressions`, once per
cased expression, so a case set that is not a partition is a load error rather
than a build-time surprise.
"""

from __future__ import annotations

import datetime
import itertools
import math
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal, cast

from math_spec.resolution import Namespace
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
    from collections.abc import Iterable, Iterator, Mapping

    from math_spec.model import Model
    from math_spec.where_parser import PredicateOperator, WhereNode

#: The product of every subject's cells is enumerated, so the bound is on the
#: product rather than on any one subject. Real masks carry two to four atoms;
#: an expression that blows this is telling you it is several expressions.
CELL_BUDGET = 8192

#: The dtypes an ordering is decided against. Everything else compares only
#: with == and !=, which need no order on the values.
_ORDERED_DTYPES = ('float', 'int', 'datetime')


class Status(Enum):
    """What the check established.

    :attr:`UNDECIDED` is *refused* by the caller exactly as :attr:`VIOLATED` is:
    a checker that guesses where it cannot decide buys nothing over no checker.
    """

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
    """Two cases that can both claim one coordinate."""

    cases: tuple[str, str]
    witness: Witness


@dataclass(frozen=True)
class Verdict:
    status: Status
    overlaps: tuple[Overlap, ...] = ()
    gaps: tuple[Witness, ...] = ()
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
            parts.append(f"cases '{first}' and '{second}' both claim the value where {_render(overlap.witness)}")
        parts.extend(f'no case claims the value where {_render(gap)}' for gap in self.gaps)
        parts.extend(f"case '{name}' claims nothing" for name in self.dead)
        return '; '.join(parts)


def _render(witness: Witness) -> str:
    return ', '.join(f'{subject} is {value}' for subject, value in witness.items())


@dataclass(frozen=True)
class Case:
    """One case of an expression: its ``when``, and the name the LaTeX prints.

    Every case carries a ``when``; ``NOT (x)`` is how the complement is
    written. The key is not ``where`` because a case selects which value a
    coordinate takes — it creates no absence and deletes no row, which is what
    ``where`` means everywhere else (rule 6).
    """

    name: str
    when: WhereNode


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def check_partition(cases: Iterable[Case], schema: Model) -> Verdict:
    """Decide whether *cases* partition the expression's frame.

    Args:
        cases: The cases, in declaration order, each with its own ``when``.
        schema: Read for dtypes, and for the declared ``values:`` that give a
            dimension a statically known extent.

    Returns:
        The verdict. :attr:`Status.UNDECIDED` is a refusal — see the module
        docstring.
    """
    try:
        return _decide(list(cases), schema)
    except Undecidable as exc:
        return Verdict(Status.UNDECIDED, reason=str(exc))


#: How many witnesses a verdict carries. The loop runs to the end whatever
#: happens — the dead-case check needs every hit — so this bounds the *rendering*
#: rather than the search, and cases covering a thin slice of a wide frame would
#: otherwise render one witness per uncovered cell and throw all but these away.
_WITNESSES = 4


def _decide(cases: list[Case], schema: Model) -> Verdict:
    frame = _Frame.of([case.when for case in cases], schema)
    if frame.size > CELL_BUDGET:
        return Verdict(
            Status.UNDECIDED,
            reason=f'{frame.size} regions to check exceeds the budget of {CELL_BUDGET} — '
            f'split this into named constraints',
        )

    overlaps: list[Overlap] = []
    gaps: list[Witness] = []
    live: set[str] = set()
    for cell in frame.cells():
        hits = [case.name for case in cases if _evaluate(case.when, cell, frame)]
        if len(hits) > 1:
            if len(overlaps) < _WITNESSES:
                overlaps.append(Overlap((hits[0], hits[1]), frame.witness(cell)))
        elif not hits and len(gaps) < _WITNESSES:
            gaps.append(frame.witness(cell))
        live.update(hits)

    dead = tuple(case.name for case in cases if case.name not in live)
    if overlaps or gaps or dead:
        return Verdict(Status.VIOLATED, tuple(overlaps), tuple(gaps), dead)
    return Verdict(Status.PARTITION)


# ---------------------------------------------------------------------------
# building the cells
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Frame:
    """The cells to check, and what reading an atom on one of them needs.

    ``subjects`` is keyed by ``id(node)`` because the where-AST nodes are
    ``@dataclass`` with ``eq=True`` and so unhashable. It is a memo of a pure
    function: without it every atom re-derives and re-allocates its subject once
    per cell, which is the hot path here.
    """

    domains: dict[Subject, list[Cell]]
    #: Rank cells are counted from the front wherever the extent is known, so
    #: the positions the atoms carry have to be read in that same frame —
    #: `position(dim) == -1` on a three-member axis is rank 2.
    extents: dict[Subject, int]
    subjects: dict[int, Subject]

    @classmethod
    def of(cls, masks: Iterable[WhereNode | None], schema: Model) -> _Frame:
        dtypes = Namespace.of(schema).dtypes
        values: dict[Subject, set[Any]] = {}
        subjects: dict[int, Subject] = {}
        for mask in masks:
            for node in _walk(mask):
                if (subject := _subject_of(node)) is None:
                    continue
                subjects[id(node)] = subject
                _observe(node, subject, values.setdefault(subject, set()), dtypes)
        extents = {s: e for s in values if s.kind == 'rank' and (e := _extent_of(s, schema)) is not None}
        domains = {s: _cells_for(s, seen, dtypes, extents.get(s)) for s, seen in values.items()}
        return cls(domains, extents, subjects)

    @property
    def size(self) -> int:
        return math.prod(len(cells) for cells in self.domains.values())

    def cells(self) -> Iterator[dict[Subject, Cell]]:
        for combination in itertools.product(*self.domains.values()):
            yield dict(zip(self.domains, combination, strict=True))

    def witness(self, cell: dict[Subject, Cell]) -> Witness:
        return {str(subject): _shown(subject, value) for subject, value in cell.items()}


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


def _observe(node: WhereNode, subject: Subject, values: set[Any], dtypes: Mapping[str, str]) -> None:
    """Record what *node* says about its subject: a position, or a literal."""
    if isinstance(node, DimensionPositionNode):
        # Every comparator reads here: `position()` converts the dimension to
        # an integer, so an ordering is an ordering of integers (#32).
        values.add(node.position)
    elif isinstance(node, LookupPairComparisonNode):
        if node.op not in ('==', '!='):
            msg = f'{subject} compared with {node.op!r}; two lookups compare only with == or !='
            raise Undecidable(msg)
    elif isinstance(node, ParameterComparisonNode | DimensionComparisonNode | LookupComparisonNode):
        if node.op not in ('==', '!=') and dtypes.get(subject.name) not in _ORDERED_DTYPES:
            msg = (
                f'{subject} has dtype {dtypes.get(subject.name)!r} and is ordered with '
                f'{node.op!r}; only == and != are decided here'
            )
            raise Undecidable(msg)
        values.add(node.value)


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
            # As in `dimensions.py` and the typesetter: an unresolved node here
            # is a caller that skipped `resolve_where`, not a model to refuse.
            msg = f'{type(node).__name__} reached the partition check unresolved.'
            raise AssertionError(msg)


def _cells_for(subject: Subject, values: set[Any], dtypes: Mapping[str, str], extent: int | None) -> list[Cell]:
    if subject.kind == 'rank':
        return _rank_cells(subject, cast('set[int]', values), extent)
    if subject.kind in ('lookup_pair', 'variable'):
        return [True, False]
    dtype = dtypes.get(subject.name)
    if dtype == 'bool':
        if values:
            msg = f'{subject} has dtype bool and is compared to a literal'
            raise Undecidable(msg)
        return [Special.NULL, True, False]
    numeric = _numeric(dtype, values)
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
    cells.extend(_ordered_cells(values) if numeric or _dated(values) else _label_cells(values))
    return cells


def _numeric(dtype: str | None, literals: set[Any]) -> bool:
    """Is this subject a magnitude? The declaration says so where it is known."""
    if dtype is not None:
        return dtype in ('float', 'int')
    return bool(literals) and all(isinstance(value, int | float) and not isinstance(value, bool) for value in literals)


def _dated(literals: set[Any]) -> bool:
    return bool(literals) and all(isinstance(value, datetime.date) for value in literals)


def _ordered_cells(literals: set[Any]) -> list[Cell]:
    """Each literal, and one representative of the gap on either side of it."""
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


def _rank_cells(subject: Subject, positions_seen: set[int], extent: int | None) -> list[Cell]:
    """Representative ranks, in one frame — counted from the front or the back.

    ``position(dim) == 0`` and ``position(dim) == -1`` are the same row when
    the dimension has one member, so mixing the two frames is only decidable
    where the extent is. A dimension that declares ``values:`` has one; a
    dimension whose coordinates arrive from data does not, and neither does any
    group a ``by=`` lookup makes, whatever the parent dimension declares.

    Within one frame the cells are its own mirror image: counting from the
    front the open end is *after* the last position named, counting from the
    back it is *before* the first, since nothing follows -1.
    """
    positions = sorted(positions_seen)
    if extent is not None:
        positions = sorted({position + extent if position < 0 else position for position in positions})
        positions = [position for position in positions if 0 <= position < extent]
    elif positions and positions[0] < 0 <= positions[-1]:
        within = f' within each {subject.qualifier} group' if subject.qualifier else ''
        msg = (
            f'{subject.name} is split at positions counted from both ends{within} '
            f'({", ".join(str(position) for position in positions)}), and its extent is not declared, '
            f'so they are the same row on a short axis — declare `values:` for {subject.name}, or split at one end'
        )
        raise Undecidable(msg)
    if not positions:
        return [0]
    from_back = positions[-1] < 0
    cells: list[Cell] = []
    if positions[0] != 0:
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


def _shown(subject: Subject, value: Cell) -> str:
    if subject.kind == 'rank':
        return str(value)
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


def _evaluate(node: WhereNode | None, cell: dict[Subject, Cell], frame: _Frame) -> bool:
    """Is *node* true in this cell? An absent mask is true everywhere."""
    if node is None:
        return True
    match node:
        case BooleanLiteralNode(value=value):
            return value
        case NotNode(operand=operand):
            return not _evaluate(operand, cell, frame)
        case AndNode(left=left, right=right):
            return _evaluate(left, cell, frame) and _evaluate(right, cell, frame)
        case OrNode(left=left, right=right):
            return _evaluate(left, cell, frame) or _evaluate(right, cell, frame)
        case _:
            return _atom(node, cell, frame)


def _atom(node: WhereNode, cell: dict[Subject, Cell], frame: _Frame) -> bool:
    subject = frame.subjects[id(node)]
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
            extent = frame.extents.get(subject)
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
