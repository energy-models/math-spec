# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""What the partition check proves, what it refuses, and what it will not decide.

The three outcomes are the point: a case that lands in ``UNDECIDED`` is refused
by a caller exactly as a violation is, so a test that asserts ``not ok`` has not
said which of the two happened. Every test here names the status.
"""

from __future__ import annotations

import itertools
import random
from typing import TYPE_CHECKING, Any, ClassVar

import pytest

from math_spec.partition import Case, Special, Status, Subject, _evaluate, _Frame, check_partition
from math_spec.resolution import Namespace, where_of
from math_spec.validation import load_model
from math_spec.where_parser import AndNode, NotNode, OrNode

if TYPE_CHECKING:
    from math_spec.model import Model

#: A storage model with the two axes the argument turns on: `snapshot` gets its
#: coordinates from data, `storage` declares its own, so only the second has an
#: extent known before the data arrives.
STORAGE: dict[str, Any] = {
    'dimensions': {
        'snapshot': {'dtype': 'int'},
        'storage': {'values': ['battery', 'reservoir', 'h2']},
        'period': {'dtype': 'int', 'values': [2030, 2040]},
    },
    'lookups': {'period_of': {'over': 'snapshot', 'into': 'period'}},
    'parameters': {
        'cyclic': {'dims': ['storage'], 'dtype': 'bool'},
        'kind': {'dims': ['storage'], 'dtype': 'str'},
        'soc_initial': {'dims': ['storage']},
        'capacity': {'dims': ['storage']},
    },
    'variables': {'soc': {'foreach': ['snapshot', 'storage']}},
    'constraints': {'balance': {'foreach': ['snapshot', 'storage'], 'expression': 'soc == 1'}},
}


@pytest.fixture(scope='module')
def schema() -> Model:
    return load_model(STORAGE)


def check(schema: Model, where: str | None, cases: dict[str, str]):
    """Resolve the masks against *schema*, then decide."""
    namespace = Namespace.of(schema)
    return check_partition(
        where_of(where, namespace, 'the group'),
        [Case(name, _mask(when, namespace, name)) for name, when in cases.items()],
        schema,
    )


def _mask(text: str, namespace: Namespace, name: str):
    mask = where_of(text, namespace, f"case '{name}'")
    assert mask is not None
    return mask


class TestProves:
    def test_the_storage_split_from_the_issue(self, schema: Model):
        """Two atoms, four regions, and the masks are exact complements.

        Spelled as the issue spells it, less `cyclic_state_of_charge == True`,
        which is a load error: a bool's bare name *is* its value.
        """
        verdict = check(
            schema,
            None,
            {
                'first_ts': 'not cyclic and position(snapshot) == 0',
                'all_other_ts': '(not cyclic and position(snapshot) != 0) or cyclic',
            },
        )
        assert verdict.status is Status.PARTITION

    def test_a_written_complement(self, schema: Model):
        verdict = check(
            schema,
            None,
            {'first': 'position(snapshot) == 0', 'rest': 'not (position(snapshot) == 0)'},
        )
        assert verdict.status is Status.PARTITION

    def test_a_category_split_closed_by_the_where(self, schema: Model):
        """Equality against distinct labels is exclusive — the theory step."""
        verdict = check(
            schema,
            "kind == 'battery' or kind == 'h2'",
            {'battery': "kind == 'battery'", 'hydrogen': "kind == 'h2'"},
        )
        assert verdict.status is Status.PARTITION

    def test_overlap_outside_the_where_is_not_an_overlap(self, schema: Model):
        """The conditioning, in the direction that admits rather than refuses."""
        cases = {
            'cyclic': 'cyclic',
            'from_initial': 'soc_initial',
            'neither': 'not cyclic and not soc_initial',
        }
        assert check(schema, 'not (cyclic and soc_initial)', cases).status is Status.PARTITION
        assert check(schema, None, cases).status is Status.VIOLATED

    def test_three_ways_where_the_extent_is_declared(self, schema: Model):
        """`storage` declares `values:`, so 0 and -1 are provably different rows."""
        verdict = check(
            schema,
            None,
            {
                'first': 'position(storage) == 0',
                'last': 'position(storage) == -1',
                'middle': 'position(storage) != 0 and position(storage) != -1',
            },
        )
        assert verdict.status is Status.PARTITION

    def test_an_ordering_on_a_position(self, schema: Model):
        """Every rank is either 0 or greater, whatever order the coordinates arrive in (#32)."""
        verdict = check(schema, None, {'first': 'position(snapshot) == 0', 'rest': 'position(snapshot) > 0'})
        assert verdict.status is Status.PARTITION

    def test_an_ordering_counted_from_the_back(self, schema: Model):
        """The mirrored frame: ranks run away from -1, and nothing follows it."""
        verdict = check(schema, None, {'last': 'position(snapshot) == -1', 'rest': 'position(snapshot) < -1'})
        assert verdict.status is Status.PARTITION

    def test_a_band_counted_from_the_back(self, schema: Model):
        verdict = check(
            schema,
            None,
            {
                'final_two': 'position(snapshot) >= -2',
                'earlier': 'position(snapshot) < -2',
            },
        )
        assert verdict.status is Status.PARTITION

    def test_numeric_bands(self, schema: Model):
        verdict = check(
            schema,
            'capacity > 0',
            {'small': 'capacity <= 10', 'large': 'capacity > 10'},
        )
        assert verdict.status is Status.PARTITION


class TestRefuses:
    def test_an_overlap_names_both_cases_and_a_witness(self, schema: Model):
        verdict = check(schema, None, {'cyclic': 'cyclic', 'battery': "kind == 'battery'"})
        assert verdict.status is Status.VIOLATED
        assert verdict.overlaps[0].cases == ('cyclic', 'battery')
        assert 'cyclic is true' in verdict.message()

    def test_a_gap_is_a_row_with_no_expression(self, schema: Model):
        verdict = check(schema, None, {'first': 'position(snapshot) == 0'})
        assert verdict.status is Status.VIOLATED
        assert verdict.gaps
        assert 'no case claims the row' in verdict.message()

    def test_a_case_the_where_excludes_is_dead(self, schema: Model):
        verdict = check(schema, 'not cyclic', {'cyclic': 'cyclic', 'rest': 'not cyclic'})
        assert verdict.status is Status.VIOLATED
        assert verdict.dead == ('cyclic',)

    def test_defined_is_not_non_zero(self, schema: Model):
        """A bare name and `!= 0` are different questions, so these leave a gap."""
        verdict = check(schema, None, {'has_initial': 'soc_initial', 'zero': 'soc_initial == 0'})
        assert verdict.status is Status.VIOLATED


class TestWillNotDecide:
    def test_both_ends_of_a_data_bound_axis(self, schema: Model):
        """The one that matters: first/last on `snapshot` is a partition unless
        the horizon has a single member, and nothing in the file rules that out.
        """
        verdict = check(
            schema,
            None,
            {
                'first': 'position(snapshot) == 0',
                'last': 'position(snapshot) == -1',
                'middle': 'position(snapshot) != 0 and position(snapshot) != -1',
            },
        )
        assert verdict.status is Status.UNDECIDED
        assert 'declare `values:`' in verdict.message()

    def test_a_group_never_has_a_declared_extent(self, schema: Model):
        """`by=` counts within each group, and no declaration sizes those."""
        verdict = check(
            schema,
            None,
            {
                'first': 'position(snapshot, by=period_of) == 0',
                'last': 'position(snapshot, by=period_of) == -1',
            },
        )
        assert verdict.status is Status.UNDECIDED


class TestSoundness:
    """A proved partition must hold on a grid finer than the cells it reasoned on.

    The claim the check rests on is that its regions cover every value a
    subject can take, so "no witness among the cells" means "no witness". This
    walks a concrete grid — several points inside single cells, both
    infinities, an absent value, labels the masks never name — and asserts that
    anything :attr:`Status.PARTITION` claims survives it.

    What it does not test is the reading of an individual atom: ground truth
    here evaluates through the same ``_evaluate`` the checker uses, so a
    misread atom would agree with itself. That is what `TestProves` and
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
    def test_a_proved_partition_holds_on_a_finer_grid(self, schema: Model, seed: int):
        namespace = Namespace.of(schema)
        atoms = [where_of(text, namespace, 'a probe') for text in self.ATOMS]
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
        proved = 0
        for _ in range(300):
            split = self._mask(rng, atoms)
            cases = [Case('a', split), Case('b', NotNode(split))]
            if rng.random() < 0.5:
                inner = self._mask(rng, atoms)
                cases = [
                    Case('a', AndNode(split, inner)),
                    Case('b', AndNode(split, NotNode(inner))),
                    Case('c', NotNode(split)),
                ]
            where = self._mask(rng, atoms) if rng.random() < 0.4 else None
            if check_partition(where, cases, schema).status is not Status.PARTITION:
                continue
            proved += 1
            # The same frame the check built, so ground truth reads each atom
            # the way it did — what differs is the grid, which is finer.
            frame = _Frame.of([where, *(case.when for case in cases)], schema)
            for point in grid:
                if where is not None and not _evaluate(where, point, frame):
                    continue
                claims = sum(1 for case in cases if _evaluate(case.when, point, frame))
                assert claims == 1, f'{claims} cases claim {point} — the cells hid a witness'
        assert proved > 50, f'only {proved} partitions proved; the fuzz is not exercising the check'
