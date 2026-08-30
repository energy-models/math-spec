# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Can two of a named expression's cases claim one coordinate? Decided without data.

A named expression with ``cases:`` is one quantity whose value varies by
region — the regime a unit is in, which end of the horizon a row sits at. It is
*one* quantity only if no coordinate is claimed twice, and nothing about the
data decides that — so it is decided at load, and a file leaving two cases free
to collide does not load.

The other half of being a quantity — a value *everywhere* — is the block's
shape rather than anything proved: the ``otherwise:`` beside the cases takes
whatever they leave. Only the ``when`` strings are checked, and only
against each other, pair by pair: ``when_i AND when_j`` unsatisfiable.

Every atom in the where-grammar talks about exactly one **subject** — a
parameter, a dimension's coordinates, a dimension's *rank*, a lookup, a pair of
lookups. Atoms with different subjects are independent; atoms sharing one are
not, and that is where a propositional reading goes wrong: on ``kind ==
'battery'`` and ``kind == 'h2'`` it invents a world where both hold and reports
an overlap that no data can produce.

So each subject is split into **cells** — finitely many regions its value can
sit in, chosen so that every atom over that subject is constant on each cell.
The cells of the pair's subjects are multiplied out and both masks evaluated on
each. A cell where both are true is a witness. Because the cells cover every
value a subject can take, "no witness" is a proof and not a sample.

Independence between subjects is an **over**-approximation: the product of
cells contains worlds the data may never produce, so a spurious world can only
manufacture a witness, never hide one. Every outcome here is therefore
conservative — this refuses case sets that would have been fine, and admits
none that would not.

A pair the procedure will not reason about is refused exactly as an overlapping
one is, and the refusal names the rewrite: a checker that guesses where it
cannot decide buys nothing over no checker.
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

    from math_spec.model import Spec
    from math_spec.where_parser import PredicateOperator, WhereNode

#: The product of the pair's subjects' cells is enumerated, so the bound is on
#: the product rather than on any one subject. Two real masks carry two to four
#: atoms between them; a pair that blows this is telling you it is several
#: expressions.
CELL_BUDGET = 8192

#: The dtypes an ordering is decided against. Everything else compares only
#: with == and !=, which need no order on the values.
_ORDERED_DTYPES = ('float', 'int', 'datetime')


class Undecidable(Exception):  # noqa: N818
    """A pair this procedure will not reason about. Carries the rewrite."""


def overlapping(cases: Mapping[str, WhereNode], schema: Spec) -> Iterator[str]:
    """One refusal per pair of cases that could both claim a coordinate.

    Args:
        cases: The ``when`` of every case, keyed by the case's name. The
            block's ``otherwise`` is not among them: it claims what the rest
            leave, so it overlaps nothing by construction.
        schema: Read for the dtype of every name a mask compares against.

    Yields:
        A sentence per pair, naming both cases and either a coordinate they
        both claim or what stopped the pair being decided. Empty where every
        pair is proved apart.
    """
    dtypes = Namespace.of(schema).dtypes
    for (first, left), (second, right) in itertools.combinations(cases.items(), 2):
        try:
            witness = _witness(left, right, dtypes)
        except Undecidable as exc:
            yield (
                f"cases '{first}' and '{second}' cannot be told apart before the data arrives: {exc}. "
                f'Two cases claiming one coordinate would give it two values, so this is refused '
                f'the way a proven overlap is.'
            )
            continue
        if witness is not None:
            yield (
                f"cases '{first}' and '{second}' both claim the value where {witness}. "
                f'A coordinate two cases claim has two values, so it has none — narrow one of the '
                f'two `when:` strings by the negation of the other, or drop the wider one and let '
                f'`otherwise:` carry that region.'
            )


def _witness(first: WhereNode, second: WhereNode, dtypes: Mapping[str, str]) -> str | None:
    """A coordinate both masks claim, rendered — ``None`` where no cell holds both."""
    frame = _Frame.of([first, second], dtypes)
    if frame.size > CELL_BUDGET:
        msg = (
            f'{frame.size} regions to check exceeds the budget of {CELL_BUDGET} — '
            f'split this into fewer, wider cases, or into named expressions of its own'
        )
        raise Undecidable(msg)
    for cell in frame.cells():
        if _evaluate(first, cell, frame) and _evaluate(second, cell, frame):
            return frame.witness(cell)
    return None


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


@dataclass(frozen=True)
class _Frame:
    """The cells to check, and what reading an atom on one of them needs.

    ``subjects`` is keyed by ``id(node)`` because the where-AST nodes are
    ``@dataclass`` with ``eq=True`` and so unhashable. It is a memo of a pure
    function: without it every atom re-derives and re-allocates its subject once
    per cell, which is the hot path here.
    """

    domains: dict[Subject, list[Cell]]
    subjects: dict[int, Subject]

    @classmethod
    def of(cls, masks: Iterable[WhereNode], dtypes: Mapping[str, str]) -> _Frame:
        values: dict[Subject, set[Any]] = {}
        subjects: dict[int, Subject] = {}
        for mask in masks:
            for node in _walk(mask):
                if (subject := _subject_of(node)) is None:
                    continue
                subjects[id(node)] = subject
                _observe(node, subject, values.setdefault(subject, set()), dtypes)
        return cls({s: _cells_for(s, seen, dtypes) for s, seen in values.items()}, subjects)

    @property
    def size(self) -> int:
        return math.prod(len(cells) for cells in self.domains.values())

    def cells(self) -> Iterator[dict[Subject, Cell]]:
        for combination in itertools.product(*self.domains.values()):
            yield dict(zip(self.domains, combination, strict=True))

    def witness(self, cell: dict[Subject, Cell]) -> str:
        return ', '.join(f'{subject} is {_shown(subject, value)}' for subject, value in cell.items())


def _walk(node: WhereNode) -> Iterator[WhereNode]:
    """Every atom in *node*; the connectives are stepped through."""
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
            msg = (
                f'{subject} is ordered with {node.op!r}, and two lookups carry no order '
                f'against each other — compare them with == or !=, or precompute the '
                f'ordering as a boolean parameter and test that'
            )
            raise Undecidable(msg)
    elif isinstance(node, ParameterComparisonNode | DimensionComparisonNode | LookupComparisonNode):
        if node.op not in ('==', '!=') and dtypes.get(subject.name) not in _ORDERED_DTYPES:
            msg = (
                f'{subject} has dtype {dtypes.get(subject.name)!r} and is ordered with '
                f'{node.op!r}, which puts no two of its values in order — compare it with '
                f'== or !=, or declare it as a number'
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
            msg = f'{type(node).__name__} reached the exclusivity check unresolved.'
            raise AssertionError(msg)


def _cells_for(subject: Subject, values: set[Any], dtypes: Mapping[str, str]) -> list[Cell]:
    """Every region *subject*'s value can sit in — ordinary values first.

    The order is the order :func:`_witness` searches, so a refusal names an
    absent value or an infinity only where nothing plainer is a witness.
    """
    if subject.kind == 'rank':
        return _rank_cells(subject, cast('set[int]', values))
    if subject.kind in ('lookup_pair', 'variable'):
        return [True, False]
    dtype = dtypes.get(subject.name)
    if dtype == 'bool':
        if values:
            msg = (
                f'{subject} has dtype bool and is compared to a literal, which reads as a '
                f'magnitude rather than as truth — write the bare name, or `not {subject}`'
            )
            raise Undecidable(msg)
        return [True, False, Special.NULL]
    numeric = _numeric(dtype, values)
    dated = _dated(values)
    cells: list[Cell] = list(
        _ordered_cells(values, discrete=dated or dtype == 'int') if numeric or dated else _label_cells(values)
    )
    # A dimension's coordinates are its own index, so there is no null among
    # them; everything else may be absent, and absence is a region of its own
    # because a null compares false and is not `defined`.
    if subject.kind != 'dim':
        cells.append(Special.NULL)
        if numeric:
            # `defined` excludes an infinity, so it needs a region where every
            # comparison still reads normally but the bare name is false.
            cells.extend([Special.NEG_INF, Special.POS_INF])
    return cells


def _numeric(dtype: str | None, literals: set[Any]) -> bool:
    """Is this subject a magnitude? The declaration says so where it is known."""
    if dtype is not None:
        return dtype in ('float', 'int')
    return bool(literals) and all(isinstance(value, int | float) and not isinstance(value, bool) for value in literals)


def _dated(literals: set[Any]) -> bool:
    return bool(literals) and all(isinstance(value, datetime.date) for value in literals)


def _ordered_cells(literals: set[Any], *, discrete: bool) -> list[Cell]:
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
        between = _between(value, following, step, discrete=discrete)
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


def _between(value: Any, following: Any, step: Any, *, discrete: bool) -> Any | None:
    """A value strictly between two literals, where the type admits one.

    A continuous magnitude always admits one — the midpoint. A **discrete**
    subject, an ``int`` or a date, need not: between 0 and 1 there is no
    integer and between two adjacent days no date, so the gap has to be wider
    than one unit before there is anything in it to stand for. A midpoint
    invented there is a coordinate the subject cannot take, and the only thing
    it can do is manufacture a witness — refusing ``n < 1`` against ``n > 0``,
    which no integer claims twice, at a coordinate named ``0.5``.
    """
    if discrete:
        return value + step if following - value > step else None
    return (value + following) / 2.0


def _label_cells(literals: set[Any]) -> list[Cell]:
    """Every named label, and one standing for all the labels not named."""
    return [*sorted(literals, key=str), Special.OTHER]


def _rank_cells(subject: Subject, positions_seen: set[int]) -> list[Cell]:
    """Representative ranks, counted from one end — the front, or the back.

    ``position(dim) == 0`` and ``position(dim) == -1`` are the same row on a
    one-member axis, and a file never says how many members an axis has: its
    coordinates are data. So the two frames cannot be told apart, and a pair
    mixing them is refused with the one rewrite left — split at one end.

    Within one frame the cells are its own mirror image: counting from the
    front the open end is *after* the last position named, counting from the
    back it is *before* the first, since nothing follows -1.
    """
    positions = sorted(positions_seen)
    if positions and positions[0] < 0 <= positions[-1]:
        within = f' within each {subject.qualifier} group' if subject.qualifier else ''
        msg = (
            f'{subject.name} is split at positions counted from both ends{within} '
            f'({", ".join(str(position) for position in positions)}), and how many members it has '
            f'is data, so they are the same row on a one-member axis — count from one end only'
        )
        raise Undecidable(msg)
    if not positions:
        return [0]
    cells: list[Cell] = []
    if positions[0] != 0:
        cells.append(positions[0] - 1)
    for index, position in enumerate(positions):
        cells.append(position)
        following = positions[index + 1] if index + 1 < len(positions) else None
        if following is not None and following - position > 1:
            cells.append(position + 1)
    if positions[-1] != -1:
        # nothing follows -1, so the open end is only ever past the front frame
        cells.append(positions[-1] + 1)
    return cells


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


def _evaluate(node: WhereNode, cell: dict[Subject, Cell], frame: _Frame) -> bool:
    """Is *node* true in this cell?"""
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
            return _compare(value, op, position)
        case ParameterComparisonNode(op=op, value=literal) | LookupComparisonNode(op=op, value=literal):
            # A null compares false, whatever the comparator.
            if value is Special.NULL:
                return False
            return _compare(value, op, literal)
        case DimensionComparisonNode(op=op, value=literal):
            return _compare(value, op, literal)
        case _:
            msg = f'{type(node).__name__} reached the exclusivity check unresolved.'
            raise AssertionError(msg)


def _compare(value: Cell, op: PredicateOperator, literal: Any) -> bool:
    """One atom's truth in one cell. Both sides are already this cell's frame."""
    if isinstance(value, Special):
        if value is Special.OTHER:
            # A label none of the masks names sorts nowhere; `_observe` has
            # already refused the ordering that would reach the second arm.
            if op in ('==', '!='):
                return op == '!='
            msg = f'a label neither case names is ordered with {op!r} — compare labels with == or != instead'
            raise Undecidable(msg)
        magnitude = math.inf if value is Special.POS_INF else -math.inf
        return _numeric_compare(magnitude, op, float(literal))
    if isinstance(value, int | float) and isinstance(literal, int | float) and not isinstance(value, bool):
        return _numeric_compare(float(value), op, float(literal))
    if type(value) is not type(literal) and not isinstance(value, type(literal)):
        # Unreachable while one declared dtype types every literal of a subject.
        if op in ('==', '!='):
            return op == '!='
        msg = f'{value!r} is ordered against {literal!r}, and the two carry no order — compare them with == or !='
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
