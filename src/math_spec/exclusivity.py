# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Can two of a named expression's cases claim one coordinate? Decided without data.

Each ``when`` is read over cells: regions of one subject's value on which every
atom is constant. The cells of the pair's subjects are multiplied out, both
masks are evaluated on each, and a cell where both hold is a witness.
Independence between subjects over-approximates, so it can manufacture a
witness but never hide one. The rule itself is stated in
``docs/reference/language/expressions.md``.
"""

from __future__ import annotations

import datetime
import itertools
import math
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Literal, assert_never

from math_spec.program import (
    And,
    ArithmeticComparison,
    BooleanLiteral,
    DimensionComparison,
    DimensionPosition,
    ExpressionComparison,
    Mask,
    Not,
    Or,
    ParameterComparison,
    ParameterDefined,
    RelationComparison,
    RelationDefined,
    RelationPairComparison,
    TypedPredicate,
    VariableDefined,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

    from math_spec.model import DeclaredDtype
    from math_spec.program import PredicateOperator, Predicate

#: The most cells one pair may multiply out to; a pair past it is several expressions.
CELL_BUDGET = 8192

#: The dtypes an ordering is decided against. Everything else compares only
#: with == and !=, which need no order on the values.
_ORDERED_DTYPES: tuple[DeclaredDtype, ...] = ('float', 'int', 'datetime')


class Undecidable(Exception):  # noqa: N818
    """A pair this procedure will not reason about. Carries the rewrite."""


def overlapping(cases: Mapping[str, Predicate], dtypes: Mapping[str, DeclaredDtype]) -> Iterator[str]:
    """One refusal per pair of cases that could both claim a coordinate.

    Args:
        cases: The ``when`` of every case, keyed by the case's name. The
            block's ``otherwise`` is not among them: it claims what the rest
            leave, so it overlaps nothing by construction.
        dtypes: The declared dtype of every name a mask compares against.

    Yields:
        A sentence per pair, naming both cases and either a coordinate they
        both claim or what stopped the pair being decided. Empty where every
        pair is proved apart.
    """
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


def _witness(first: Predicate, second: Predicate, dtypes: Mapping[str, DeclaredDtype]) -> str | None:
    """A coordinate both masks claim, rendered — ``None`` where no cell holds both."""
    masks = (Mask(first), Mask(second))
    grid = _Grid.of(masks, dtypes)
    if grid.size > CELL_BUDGET:
        msg = (
            f'{grid.size} regions to check exceeds the budget of {CELL_BUDGET} — '
            f'split this into fewer, wider cases, or into named expressions of its own'
        )
        raise Undecidable(msg)
    for cell in grid.cells():
        if all(_evaluate(mask.root, cell, grid) for mask in masks):
            return grid.witness(cell)
    return None


# ---------------------------------------------------------------------------
# cells
# ---------------------------------------------------------------------------


class Special(Enum):
    """Values a cell can hold that are not values of the subject's own type."""

    #: No row in the table: compares false under every comparator, and is not `defined`.
    NULL = 'null'
    #: A magnitude every comparison reads normally, and the one that is not `defined`.
    POS_INF = '+inf'
    #: Its negative twin.
    NEG_INF = '-inf'
    #: A label none of the masks names — every such label at once.
    OTHER = 'other'


#: What one subject's value is, in one cell.
Cell = float | str | bool | int | datetime.date | Special

#: What a where comparison is written against: a number, a label, or a date.
#: ``position()`` counts in integers, which are numbers here.
_Literal = float | str | datetime.date


@dataclass(frozen=True)
class Subject:
    """What an atom talks about — the key its cells are built for.

    ``kind`` separates the namespaces that could otherwise collide: a
    dimension's coordinates and its *rank* are two subjects over one name, and
    a rank is further split by the ``by=`` relation it is counted within.
    """

    kind: Literal['param', 'expression', 'dim', 'rank', 'relation', 'relation_pair', 'variable']
    name: str
    qualifier: str | None = None
    #: A rank's group columns: two positions by one relation into different columns are two subjects.
    group: tuple[str, ...] = ()

    def __str__(self) -> str:
        if self.kind == 'rank':
            within = f' within {self.qualifier}' if self.qualifier else ''
            return f'the position of {self.name}{within}'
        if self.kind == 'relation_pair':
            return f'{self.name} vs {self.qualifier}'
        return self.name


@dataclass(frozen=True)
class _Grid:
    """The cells to check, and what reading an atom on one of them needs.

    ``subjects`` is keyed by ``id(node)``: the where nodes are ``@dataclass``
    with ``eq=True`` and so unhashable. The memo is valid while the masks are alive.
    """

    domains: dict[Subject, list[Cell]]
    subjects: dict[int, Subject]

    @classmethod
    def of(cls, masks: Iterable[Mask], dtypes: Mapping[str, DeclaredDtype]) -> _Grid:
        values: dict[Subject, set[_Literal]] = {}
        subjects: dict[int, Subject] = {}
        for mask in masks:
            for node in mask.atoms:
                subject = _subject_of(node)
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


def _observe(
    node: TypedPredicate, subject: Subject, values: set[_Literal], dtypes: Mapping[str, DeclaredDtype]
) -> None:
    """Record what *node* says about its subject: a position, or a literal.

    ``position()`` converts the dimension to an integer, so an ordering over a
    rank is an ordering of integers and every comparator is admitted there.
    """
    if isinstance(node, ArithmeticComparison | ExpressionComparison):
        msg = (
            'it compares expressions, whose values only the data decides — compare one parameter against a '
            'literal, or precompute the test as a boolean parameter and test that'
        )
        raise Undecidable(msg)
    if isinstance(node, DimensionPosition):
        values.add(node.position)
    elif isinstance(node, RelationPairComparison):
        if node.op not in ('==', '!='):
            msg = (
                f'{subject} is ordered with {node.op!r}, and two relations carry no order '
                f'against each other — compare them with == or !=, or precompute the '
                f'ordering as a boolean parameter and test that'
            )
            raise Undecidable(msg)
    elif isinstance(node, ParameterComparison | DimensionComparison | RelationComparison):
        if node.op not in ('==', '!=') and dtypes.get(subject.name) not in _ORDERED_DTYPES:
            msg = (
                f'{subject} has dtype {dtypes.get(subject.name)!r} and is ordered with '
                f'{node.op!r}, which puts no two of its values in order — compare it with '
                f'== or !=, or declare it as a number'
            )
            raise Undecidable(msg)
        values.add(node.value)


def _subject_of(node: TypedPredicate) -> Subject:
    match node:
        case ParameterDefined(name=name) | ParameterComparison(name=name):
            return Subject('param', name)
        case VariableDefined(name=name):
            return Subject('variable', name)
        case DimensionComparison(name=name):
            return Subject('dim', name)
        case DimensionPosition(name=name, partition=partition):
            if partition is None:
                return Subject('rank', name)
            return Subject('rank', name, partition.name, partition.group)
        case RelationDefined(name=name) | RelationComparison(name=name):
            return Subject('relation', name)
        case RelationPairComparison(name=name, other=other):
            return Subject('relation_pair', name, other)
        case ArithmeticComparison() | ExpressionComparison():
            return Subject('expression', 'a comparison of expressions')
        case _:
            assert_never(node)


def _cells_for(subject: Subject, values: set[_Literal], dtypes: Mapping[str, DeclaredDtype]) -> list[Cell]:
    """Every region *subject*'s value can sit in — ordinary values first.

    The order is the order :func:`_witness` searches, so a refusal names an
    absent value or an infinity only where nothing plainer is a witness.
    """
    if subject.kind == 'rank':
        return _rank_cells(subject, {int(v) for v in _numbers(values)})
    if subject.kind in ('relation_pair', 'variable'):
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
    cells: list[Cell]
    if numeric:
        cells = list(_numeric_cells(_numbers(values), discrete=dtype == 'int'))
    elif _dated(values):
        cells = list(_dated_cells({v for v in values if isinstance(v, datetime.date)}))
    else:
        cells = _label_cells(values)
    cells.extend(_absence_cells(subject, numeric=numeric))
    return cells


def _absence_cells(subject: Subject, *, numeric: bool) -> list[Cell]:
    """The regions where *subject* has no ordinary value.

    A dimension's coordinates have no null. ``defined`` excludes an infinity,
    so a magnitude needs a region where every comparison still reads normally
    and the bare name is false.
    """
    if subject.kind == 'dim':
        return []
    return [Special.NULL, Special.NEG_INF, Special.POS_INF] if numeric else [Special.NULL]


def _numeric(dtype: DeclaredDtype | None, literals: set[_Literal]) -> bool:
    """Is this subject a magnitude? The declaration says so where it is known."""
    if dtype is not None:
        return dtype in ('float', 'int')
    return bool(literals) and all(isinstance(value, int | float) and not isinstance(value, bool) for value in literals)


def _dated(literals: set[_Literal]) -> bool:
    return bool(literals) and all(isinstance(value, datetime.date) for value in literals)


def _numbers(literals: set[_Literal]) -> set[float]:
    """The literals of a magnitude, as the numbers the dtype rules guarantee they are."""
    numbers = {float(value) for value in literals if isinstance(value, int | float)}
    assert len(numbers) == len(literals), 'a label or a date reached a magnitude; the dtype rules keep them apart'
    return numbers


def _numeric_cells(literals: set[float], *, discrete: bool) -> list[float]:
    """Each number, and one representative of the gap on either side of it.

    An ``int`` subject has a value between two literals only where the gap is
    wider than one.
    """
    if not literals:
        return [0.0]
    values = sorted(literals)
    cells = [values[0] - 1.0]
    for value, following in itertools.zip_longest(values, values[1:]):
        cells.append(value)
        if following is None:
            continue
        if not discrete:
            cells.append((value + following) / 2.0)
        elif following - value > 1.0:
            cells.append(value + 1.0)
    cells.append(values[-1] + 1.0)
    return cells


def _dated_cells(literals: set[datetime.date]) -> list[datetime.date]:
    """Each date, and one representative of the gap on either side of it.

    A date steps by a day and a datetime by a second, and there is a value
    between two literals only where the gap is wider than one step.
    """
    values = sorted(literals)
    step = datetime.timedelta(seconds=1) if isinstance(values[0], datetime.datetime) else datetime.timedelta(days=1)
    cells = [values[0] - step]
    for value, following in itertools.zip_longest(values, values[1:]):
        cells.append(value)
        if following is not None and following - value > step:
            cells.append(value + step)
    cells.append(values[-1] + step)
    return cells


def _label_cells(literals: set[_Literal]) -> list[Cell]:
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
    for position, following in itertools.zip_longest(positions, positions[1:]):
        cells.append(position)
        if following is not None and following - position > 1:
            cells.append(position + 1)
    if positions[-1] != -1:
        # nothing follows -1, so the open end is only ever past the front frame
        cells.append(positions[-1] + 1)
    return cells


def _shown(subject: Subject, value: Cell) -> str:
    if subject.kind == 'rank':
        return str(value)
    if subject.kind == 'relation_pair':
        return 'equal' if value else 'different'
    if isinstance(value, Special):
        return {Special.NULL: 'absent', Special.OTHER: 'anything else'}.get(value, value.value)
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return f'{value!r}'


# ---------------------------------------------------------------------------
# evaluating a mask on one cell
# ---------------------------------------------------------------------------


def _evaluate(node: Predicate, cell: dict[Subject, Cell], grid: _Grid) -> bool:
    """Is *node* true in this cell?"""
    if isinstance(node, TypedPredicate):
        return _atom(node, cell, grid)
    match node:
        case BooleanLiteral(value=value):
            return value
        case Not(operand=operand):
            return not _evaluate(operand, cell, grid)
        case And(left=left, right=right):
            return _evaluate(left, cell, grid) and _evaluate(right, cell, grid)
        case Or(left=left, right=right):
            return _evaluate(left, cell, grid) or _evaluate(right, cell, grid)
        case _:
            assert_never(node)


def _atom(node: TypedPredicate, cell: dict[Subject, Cell], grid: _Grid) -> bool:
    subject = grid.subjects[id(node)]
    value = cell[subject]
    match node:
        case ParameterDefined() | RelationDefined():
            if isinstance(value, bool):
                return value
            return value not in (Special.NULL, Special.POS_INF, Special.NEG_INF)
        case VariableDefined():
            return bool(value)
        case RelationPairComparison(op=op):
            return bool(value) if op == '==' else not value
        case ArithmeticComparison() | ExpressionComparison():
            msg = 'a comparison of expressions is refused as undecidable before any cell is read'
            raise AssertionError(msg)
        case DimensionPosition(op=op, position=position):
            return _compare(value, op, position)
        case ParameterComparison(op=op, value=literal) | RelationComparison(op=op, value=literal):
            if value is Special.NULL:
                return False
            return _compare(value, op, literal)
        case DimensionComparison(op=op, value=literal):
            return _compare(value, op, literal)
        case _:
            assert_never(node)


def _compare(value: Cell, op: PredicateOperator, literal: _Literal) -> bool:
    """One atom's truth in one cell. Both sides are already this cell's frame.

    Raises:
        AssertionError: The cell and the literal are of different kinds, which
            the dtype rules keep apart before a mask is proved.
    """
    if isinstance(value, Special):
        if value is Special.OTHER:
            # a label none of the masks names sorts nowhere
            if op in ('==', '!='):
                return op == '!='
            msg = f'a label neither case names is ordered with {op!r} — compare labels with == or != instead'
            raise Undecidable(msg)
        value = math.inf if value is Special.POS_INF else -math.inf
    if isinstance(value, int | float) and isinstance(literal, int | float):
        return _ordered(float(value), op, float(literal))
    if isinstance(value, str) and isinstance(literal, str):
        return _ordered(value, op, literal)
    if isinstance(value, datetime.date) and isinstance(literal, datetime.date):
        return _ordered(value, op, literal)
    msg = f'{value!r} is compared with {literal!r}, and the two are of different kinds'
    raise AssertionError(msg)


def _ordered[T: (float, str, datetime.date)](left: T, op: PredicateOperator, right: T) -> bool:
    """One comparison between two values of one kind — the kinds a literal comes in."""
    match op:
        case '==':
            return left == right
        case '!=':
            return left != right
        case '<':
            return left < right
        case '<=':
            return left <= right
        case '>':
            return left > right
        case '>=':
            return left >= right
