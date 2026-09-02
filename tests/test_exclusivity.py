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
    @pytest.mark.parametrize(
        ('cases', 'claim'),
        [
            pytest.param(
                {
                    'first_ts': 'not cyclic and position(snapshot) == 0',
                    'all_other_ts': '(not cyclic and position(snapshot) != 0) or cyclic',
                },
                'the two regimes are exact complements, spelled as the issue spells them less '
                "`cyclic_state_of_charge == True`, which is a load error: a bool's bare name is its value",
                id='the-storage-split-from-the-issue',
            ),
            pytest.param(
                {'battery': "kind == 'battery'", 'hydrogen': "kind == 'h2'"},
                'a storage carries one kind, so two labels are apart where a propositional reading invents a '
                'storage that is both',
                id='a-category-split',
            ),
            pytest.param(
                {'first': 'position(snapshot) == 0', 'rest': 'position(snapshot) > 0'},
                'no row sits at rank 0 and past it at once, whatever order the coordinates arrive in (#32)',
                id='an-ordering-on-a-position',
            ),
            pytest.param(
                {'final_two': 'position(snapshot) >= -2', 'earlier': 'position(snapshot) < -2'},
                'a rank is inside the last two or before them: ranks run away from -1, and nothing follows it',
                id='a-band-counted-from-the-back',
            ),
            pytest.param(
                {'small': 'capacity and capacity <= 10', 'large': 'capacity and capacity > 10'},
                'a capacity is at most 10 or above it, with the absent capacity a region of its own',
                id='numeric-bands',
            ),
            pytest.param(
                {'new': 'age < 1', 'old': 'age > 0'},
                '`age` is declared int, so the bands are complements over the integers; a midpoint invented in '
                'the gap is a coordinate the subject cannot take, and the refusal it manufactures names 0.5 — '
                'a value no data produces, with a rewrite the file has already followed',
                id='an-integer-admits-no-value-between-its-bands',
            ),
        ],
    )
    def test_a_pair_that_shares_no_coordinate_is_proved_apart(self, schema: Spec, cases: dict[str, str], claim: str):
        assert refusals(schema, cases) == [], claim

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
        """The three quantities #2 factors a PyPSA ramp limit into, less each one's `otherwise`."""
        assert refusals(schema, cases) == [], f'{cases} claims no coordinate twice'

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


@pytest.fixture(scope='module')
def overlap(schema: Spec) -> str:
    """The one refusal a bool against a label draws, read once for every fragment asserted on it."""
    [refusal] = refusals(schema, {'cyclic': 'cyclic', 'battery': "kind == 'battery'"})
    return refusal


class TestRefuses:
    @pytest.mark.parametrize(
        'fragment',
        [
            pytest.param("cases 'cyclic' and 'battery' both claim the value where", id='both-cases'),
            pytest.param('cyclic is true', id='a-witness'),
            pytest.param('narrow one of the two `when:` strings by the negation of the other', id='the-rewrite'),
        ],
    )
    def test_an_overlap_names_both_cases_a_witness_and_the_rewrite(self, overlap: str, fragment: str):
        assert fragment in overlap

    def test_every_overlapping_pair_is_named(self, schema: Spec):
        """Not the first: a set with three problems has three sentences."""
        cases = {'a': 'cyclic', 'b': 'committable', 'c': "kind == 'battery'"}
        assert len(refusals(schema, cases)) == 3, 'each of the three pairs overlaps'

    def test_defined_is_not_non_zero(self, schema: Spec):
        """A bare name and `== 0` are different questions, so a zero capacity is in both."""
        [refusal] = refusals(schema, {'has_initial': 'soc_initial', 'zero': 'soc_initial == 0'})
        assert 'soc_initial is 0.0' in refusal


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
    nothing it proved apart has a point claimed by both. Only pairs the check
    proves apart are walked; a complement pair asserts X and not X and cannot
    fail.
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

    def _random_mask(self, rng: random.Random, atoms: list[Any], depth: int = 0) -> Any:
        if depth >= 2 or rng.random() < 0.45:
            atom = rng.choice(atoms)
            return NotNode(atom) if rng.random() < 0.25 else atom
        left = self._random_mask(rng, atoms, depth + 1)
        right = self._random_mask(rng, atoms, depth + 1)
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
            first, second = self._random_mask(rng, atoms), self._random_mask(rng, atoms)
            if list(overlapping({'a': first, 'b': second}, dtypes)):
                continue
            proved += 1
            frame = _Frame.of([Mask(first), Mask(second)], dtypes)
            for point in grid:
                both = _evaluate(first, point, frame) and _evaluate(second, point, frame)
                assert not both, f'both cases claim {point} — the cells hid a witness'
        assert proved > 150, f'only {proved} pairs proved apart; the fuzz is not exercising the check'
