# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""What the exclusivity check proves apart, what it refuses, and what it will not decide.

A pair it cannot decide is refused exactly as an overlapping one is, so a test
asserting "there is a refusal" has not said which of the two happened. Every
test here matches the sentence.
"""

from __future__ import annotations

import itertools
import random
from typing import TYPE_CHECKING, Any, ClassVar

import pytest

from math_spec._where_parser import parse_where
from math_spec.exclusivity import CELL_BUDGET, Special, Subject, _evaluate, _Frame, overlapping
from math_spec.program import AndNode, Mask, NotNode, OrNode
from math_spec.resolution import Namespace, resolve_where
from math_spec.validation import to_spec

if TYPE_CHECKING:
    from math_spec.model import Spec
    from math_spec.program import WhereNode

#: A storage model carrying one atom of every kind a `when` can be built from.
#: Every axis takes its coordinates from data, so nothing here sizes one.
STORAGE: dict[str, Any] = {
    'dimensions': {
        'snapshot': {'dtype': 'int'},
        'storage': {},
        'period': {'dtype': 'int'},
    },
    'lookups': {'period_of': {'over': 'snapshot', 'into': 'period'}},
    'parameters': {
        'cyclic': {'dims': ['storage'], 'dtype': 'bool'},
        'committable': {'dims': ['storage'], 'dtype': 'bool'},
        'kind': {'dims': ['storage'], 'dtype': 'str'},
        'soc_initial': {'dims': ['storage']},
        'capacity': {'dims': ['storage']},
        'age': {'dims': ['storage'], 'dtype': 'int'},
    },
    'variables': {'soc': {'foreach': ['snapshot', 'storage']}},
    'constraints': {'balance': {'foreach': ['snapshot', 'storage'], 'expression': 'soc == 1'}},
}


@pytest.fixture(scope='module')
def schema() -> Spec:
    return to_spec(STORAGE)


def refusals(schema: Spec, cases: dict[str, str]) -> list[str]:
    """Resolve each case's `when` against *schema*, then decide every pair."""
    namespace = Namespace.of(schema)
    return list(overlapping({name: _mask(when, namespace, name) for name, when in cases.items()}, namespace.dtypes))


def _mask(text: str, namespace: Namespace, name: str) -> WhereNode:
    """Resolved but not folded, which is the shape a case's `when` reaches the prover in."""
    errors: list[str] = []
    mask = resolve_where(parse_where(text), namespace, f"case '{name}'", errors)
    assert not errors, errors
    assert mask is not None
    return mask


class TestProvesApart:
    def test_the_storage_split_from_the_issue(self, schema: Spec):
        """Two atoms, four regions, and the two masks are exact complements.

        Spelled as the issue spells it, less `cyclic_state_of_charge == True`,
        which is a load error: a bool's bare name *is* its value.
        """
        cases = {
            'first_ts': 'not cyclic and position(snapshot) == 0',
            'all_other_ts': '(not cyclic and position(snapshot) != 0) or cyclic',
        }
        assert refusals(schema, cases) == [], 'the two regimes are written as complements'

    def test_a_category_split(self, schema: Spec):
        """Equality against distinct labels is exclusive — the theory step.

        A purely propositional reading invents a storage that is both a battery
        and hydrogen, and refuses the split the feature exists for.
        """
        cases = {'battery': "kind == 'battery'", 'hydrogen': "kind == 'h2'"}
        assert refusals(schema, cases) == [], 'a storage carries one kind, so the two labels are apart'

    @pytest.mark.parametrize(
        'cases',
        [
            pytest.param({'boundary': 'position(snapshot) == 0'}, id='boundary'),
            pytest.param({'modular': 'cyclic'}, id='modular'),
            pytest.param(
                {'always_on': 'not committable', 'boundary': 'committable and position(snapshot) == 0'},
                id='always_on',
            ),
        ],
    )
    def test_the_ramp_regimes_from_the_issue(self, schema: Spec, cases: dict[str, str]):
        """The three quantities #2 factors a PyPSA ramp limit into, less each one's `otherwise`.

        The point of putting cases on an expression rather than on the
        constraint: three independent axes multiply into eight constraint cases
        and add into seven expression cases, and the inequality is written once
        instead of eight times.
        """
        assert refusals(schema, cases) == [], f'{cases} claims no coordinate twice'

    def test_an_ordering_on_a_position(self, schema: Spec):
        """Every rank is either 0 or greater, whatever order the coordinates arrive in (#32)."""
        cases = {'first': 'position(snapshot) == 0', 'rest': 'position(snapshot) > 0'}
        assert refusals(schema, cases) == [], 'no row sits at rank 0 and past it at once'

    def test_a_band_counted_from_the_back(self, schema: Spec):
        """The mirrored frame: ranks run away from -1, and nothing follows it."""
        cases = {'final_two': 'position(snapshot) >= -2', 'earlier': 'position(snapshot) < -2'}
        assert refusals(schema, cases) == [], 'a rank is inside the last two or before them'

    def test_numeric_bands(self, schema: Spec):
        """And the same for a magnitude, with the absent capacity a region of its own."""
        cases = {'small': 'capacity and capacity <= 10', 'large': 'capacity and capacity > 10'}
        assert refusals(schema, cases) == [], 'a capacity is at most 10 or above it'

    def test_an_integer_admits_no_value_between_its_bands(self, schema: Spec):
        """`age` is declared `int`, and the two bands are complements over the integers.

        A midpoint invented in the gap is a coordinate the subject cannot take,
        and the refusal it manufactures names `0.5` — a value no data produces,
        with a rewrite the file has already followed.
        """
        cases = {'new': 'age < 1', 'old': 'age > 0'}
        assert refusals(schema, cases) == [], 'an integer is below 1 or above 0, never between'

    def test_a_magnitude_still_admits_one(self, schema: Spec):
        """The mirror: `capacity` is a float, so 0.5 is a coordinate it can take."""
        cases = {'small': 'capacity < 1', 'large': 'capacity > 0'}
        assert refusals(schema, cases), 'a float between the two bands is claimed by both'

    def test_a_when_of_true_is_not_a_fallback(self, schema: Spec):
        """The fallback is the block's `otherwise:`, and nothing inside `cases:` stands in for it.

        A mask that happens to be true everywhere is read as any other mask is,
        so it collides with every case beside it.
        """
        cases = {'first': 'position(snapshot) == 0', 'everything': 'True'}
        assert refusals(schema, cases), 'a case whose `when` is True claims every coordinate'


class TestRefuses:
    def test_an_overlap_names_both_cases_and_a_witness(self, schema: Spec):
        [refusal] = refusals(schema, {'cyclic': 'cyclic', 'battery': "kind == 'battery'"})
        assert "cases 'cyclic' and 'battery' both claim the value where" in refusal
        assert 'cyclic is true' in refusal

    def test_every_overlapping_pair_is_named(self, schema: Spec):
        """Not the first: a set with three problems has three sentences."""
        cases = {'a': 'cyclic', 'b': 'committable', 'c': "kind == 'battery'"}
        assert len(refusals(schema, cases)) == 3, 'each of the three pairs overlaps'

    def test_defined_is_not_non_zero(self, schema: Spec):
        """A bare name and `== 0` are different questions, so a zero capacity is in both."""
        [refusal] = refusals(schema, {'has_initial': 'soc_initial', 'zero': 'soc_initial == 0'})
        assert 'soc_initial is 0.0' in refusal

    def test_the_refusal_names_the_rewrite(self, schema: Spec):
        [refusal] = refusals(schema, {'cyclic': 'cyclic', 'battery': "kind == 'battery'"})
        assert 'narrow one of the two `when:` strings by the negation of the other' in refusal


class TestWillNotDecide:
    def test_both_ends_of_one_axis(self, schema: Spec):
        """The one that matters: first and last are the same row on a one-member
        horizon, and how many members an axis has is data.
        """
        [refusal] = refusals(schema, {'first': 'position(snapshot) == 0', 'last': 'position(snapshot) == -1'})
        assert 'cannot be told apart before the data arrives' in refusal
        assert 'count from one end only' in refusal

    def test_a_group_is_named_as_the_group_it_is(self, schema: Spec):
        """`by=` counts within each group, and the refusal says which."""
        cases = {
            'first': 'position(snapshot, by=period_of) == 0',
            'last': 'position(snapshot, by=period_of) == -1',
        }
        [refusal] = refusals(schema, cases)
        assert 'within each period_of group' in refusal

    def test_a_pair_with_more_regions_than_the_budget(self):
        """Cells multiply across subjects, and a pair wide enough to blow the
        budget is several expressions wearing one name.
        """
        bands = ' or '.join(f'p{axis} == {value}' for axis in range(4) for value in range(8))
        model = {
            'dimensions': {'generator': {}},
            'parameters': {f'p{axis}': {'dims': ['generator']} for axis in range(4)},
            'variables': {'x': {'foreach': ['generator']}},
            'constraints': {'c': {'foreach': ['generator'], 'expression': 'x >= 0'}},
        }
        [refusal] = refusals(to_spec(model), {'wide': bands, 'rest': 'not (' + bands + ')'})
        assert f'exceeds the budget of {CELL_BUDGET}' in refusal

    def test_a_bool_compared_to_a_number(self, schema: Spec):
        """Resolution admits it, and truth is not a magnitude to put in order."""
        [refusal] = refusals(schema, {'on': 'cyclic == 1', 'off': 'not cyclic'})
        assert 'write the bare name, or `not cyclic`' in refusal


class TestSoundness:
    """A pair proved apart must stay apart on a grid finer than the cells it reasoned on.

    The claim the check rests on is that its regions cover every value a
    subject can take, so "no witness among the cells" means "no witness". This
    walks a concrete grid — several points inside single cells, both
    infinities, an absent value, labels the masks never name — and asserts that
    nothing it proved apart has a point claimed by both.

    **The two masks are drawn independently**, and only the pairs the check
    proves apart are walked. A pair built as a complement — `m` against
    `not m` — makes the assertion `X and not X`, false at every point under
    every implementation, so a fuzz over those shapes cannot fail and certifies
    nothing.

    What it does not test is the reading of an individual atom: ground truth
    here evaluates through the same `_evaluate` the checker uses, so a misread
    atom would agree with itself. That is what `TestProvesApart` and
    `TestRefuses` pin, one atom at a time.
    """

    ATOMS: ClassVar[tuple[str, ...]] = (
        'capacity',
        'capacity > 0',
        'capacity <= 10',
        'capacity == 0',
        'cyclic',
        'kind',
        "kind == 'battery'",
        "kind != 'h2'",
        'position(storage) == 0',
        'position(storage) != 0',
        'position(storage) == -1',
        'position(storage) > 0',
    )

    #: Finer than the cells: two points inside bands the masks cannot tell
    #: apart, both infinities, absence, and labels no mask names.
    GRID: ClassVar[dict[str, list[Any]]] = {
        'capacity': [Special.NULL, Special.NEG_INF, Special.POS_INF, -5.0, -0.5, 0.0, 0.5, 9.5, 10.0, 10.5],
        'cyclic': [Special.NULL, True, False],
        'kind': [Special.NULL, 'battery', 'h2', 'coal', 'nuclear'],
        'storage': [0, 1, 2],
    }

    def _mask(self, rng: random.Random, atoms: list[Any], depth: int = 0) -> Any:
        if depth >= 2 or rng.random() < 0.45:
            atom = rng.choice(atoms)
            return NotNode(atom) if rng.random() < 0.25 else atom
        left = self._mask(rng, atoms, depth + 1)
        right = self._mask(rng, atoms, depth + 1)
        node = AndNode(left, right) if rng.random() < 0.5 else OrNode(left, right)
        return NotNode(node) if rng.random() < 0.15 else node

    @pytest.mark.parametrize('seed', [1, 7])
    def test_a_pair_proved_apart_stays_apart_on_a_finer_grid(self, schema: Spec, seed: int):
        namespace = Namespace.of(schema)
        atoms = [_mask(text, namespace, 'a probe') for text in self.ATOMS]
        subjects = {
            'capacity': Subject('param', 'capacity'),
            'cyclic': Subject('param', 'cyclic'),
            'kind': Subject('param', 'kind'),
            'storage': Subject('rank', 'storage'),
        }
        grid = [
            {subjects[name]: value for name, value in zip(self.GRID, combination, strict=True)}
            for combination in itertools.product(*self.GRID.values())
        ]

        rng = random.Random(seed)
        dtypes = namespace.dtypes
        proved = 0
        for _ in range(2000):
            first, second = self._mask(rng, atoms), self._mask(rng, atoms)
            if list(overlapping({'a': first, 'b': second}, dtypes)):
                continue
            proved += 1
            # The same frame the check built, so ground truth reads each atom
            # the way it did — what differs is the grid, which is finer.
            frame = _Frame.of([Mask(first), Mask(second)], dtypes)
            for point in grid:
                both = _evaluate(first, point, frame) and _evaluate(second, point, frame)
                assert not both, f'both cases claim {point} — the cells hid a witness'
        assert proved > 150, f'only {proved} pairs proved apart; the fuzz is not exercising the check'
