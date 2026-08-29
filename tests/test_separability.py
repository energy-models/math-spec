# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Whether a horizon may be solved in windows, asked before any data binds.

The verdict is what a rolling-horizon or myopic driver needs and cannot
currently get: a model with an annual budget windows into feasible pieces whose
answer is wrong, and nothing says so. Every case below is one model shape and
the verdict it earns, because the value of the pass is entirely in getting the
boundary between the two right.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import math_spec as ms

FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'every_program_node.yaml'

BASE: dict[str, Any] = {
    'dimensions': {'h': {'dtype': 'int'}, 'u': {'dtype': 'str'}, 'zone': {'dtype': 'str'}, 'day': {'dtype': 'int'}},
    'lookups': {'zone_of': {'over': 'u', 'into': 'zone'}, 'day_of': {'over': 'h', 'into': 'day'}},
    'parameters': {
        'cost': {'dims': ['u']},
        'budget': {'dims': []},
        'width': {'dims': ['u'], 'dtype': 'int'},
        'cap': {'dims': ['zone']},
    },
    'variables': {'p': {'foreach': ['h', 'u'], 'bounds': {'lower': 0}}},
    'objective': {'sense': 'minimize', 'expression': 'sum(p * cost)'},
}


def _verdict(dimension: str = 'h', **patch: Any):
    return ms.to_program({**BASE, **patch}).separability(dimension)


def _rows(expression: str, *, foreach: list[str] | None = None, **block: Any) -> dict[str, Any]:
    return {'constraints': {'k': {'foreach': foreach or ['h', 'u'], 'expression': expression, **block}}}


@pytest.mark.parametrize(
    ('patch', 'halo'),
    [
        pytest.param(_rows('p >= 0'), 0, id='pointwise-needs-no-overlap'),
        pytest.param(_rows('p >= shift(p, over=h, offset=1, edge=0)'), 1, id='a-shift-of-one-needs-one-row'),
        pytest.param(_rows('p >= shift(p, over=h, offset=3, edge=0)'), 3, id='a-shift-of-three-needs-three'),
        pytest.param(_rows('sum_back(p, over=h, within=4) >= 0'), 3, id='a-window-of-four-needs-three'),
        pytest.param(_rows('p >= shift(p, over=u, offset=1, edge=0)'), 0, id='a-shift-along-another-axis-is-nothing'),
    ],
)
def test_a_separable_model_reports_the_overlap_two_windows_need(patch, halo):
    verdict = _verdict(**patch)
    assert verdict.windowable, 'nothing here ties the axis together'
    assert verdict.halo == halo, 'the halo is the reach of the widest translation along the axis'


@pytest.mark.parametrize(
    ('patch', 'fragment'),
    [
        pytest.param(_rows('sum(p, over=h) <= budget', foreach=['u']), 'sums over h', id='a-budget-over-the-horizon'),
        pytest.param(_rows("p >= shift(p, over=h, offset=1, edge='wrap')"), 'wraps around h', id='a-cyclic-shift'),
        pytest.param(
            _rows('p >= shift(p, over=h, offset=1, by=day_of, edge=0)'),
            "groups 'day_of' makes",
            id='a-shift-inside-groups-a-window-may-cut',
        ),
        pytest.param(
            _rows('p >= shift(p, over=h, offset=width, edge=0)'), "reaches back by 'width'", id='an-offset-from-data'
        ),
        pytest.param(
            _rows('sum_back(p, over=h, within=width) >= 0'), "reaches back by 'width'", id='a-width-from-data'
        ),
        pytest.param(_rows('p >= 0', where='position(h) == 0'), 'counts a position', id='a-mask-counting-a-position'),
    ],
)
def test_a_model_the_axis_ties_together_names_what_ties_it(patch, fragment):
    verdict = _verdict(**patch)
    assert not verdict.windowable, 'this shape does not survive being cut into windows'
    assert fragment in verdict.coupled["constraint 'k'"], 'the report names the construct, not just the declaration'


def test_a_sum_over_the_axis_couples_a_constraint_and_leaves_the_objective_alone():
    """The crux. An objective *is* a sum, so summing the windows' objectives is
    summing the model's; a constraint row summing the axis ties every window to
    every other. A verdict treating the two alike would refuse every windowable
    model there is — and `BASE`'s objective sums over `h` in every case above."""
    assert _verdict(**_rows('p >= 0')).windowable, 'the objective sums over h and that is not a coupling'
    coupled = _verdict(**_rows('sum(p, over=h) <= budget', foreach=['u']))
    assert not coupled.windowable, 'the same sum in a constraint is one'


def test_a_position_inside_a_cased_region_is_found():
    """`children` descends into a region's value and not its `when`, so a mask
    written inside `cases:` is reachable by no expression walk — and seeding a
    quantity at the start of the axis is exactly what a rolling horizon does."""
    verdict = _verdict(
        expressions={
            'prev': {
                'foreach': ['h', 'u'],
                'cases': {'opening': {'when': 'position(h) == 0', 'expression': 0}},
                'otherwise': 'shift(p, over=h, offset=1, edge=0)',
            }
        },
        **_rows('p - prev <= 1'),
    )
    assert not verdict.windowable, 'the seed fires once over a horizon and once per window'


def test_the_halo_is_the_widest_reach_of_any_block():
    verdict = _verdict(
        constraints={
            'near': {'foreach': ['h', 'u'], 'expression': 'p >= shift(p, over=h, offset=1, edge=0)'},
            'far': {'foreach': ['h', 'u'], 'expression': 'p >= shift(p, over=h, offset=5, edge=0)'},
        }
    )
    assert verdict.halo == 5, 'one window must overlap the next by enough for every block'


def test_a_grouping_that_consumes_the_axis_couples_it():
    program = ms.to_program(
        {**BASE, 'constraints': {'z': {'foreach': ['h', 'zone'], 'expression': 'sum(p, by=zone_of) <= cap'}}}
    )
    verdict = program.separability('u')
    assert not verdict.windowable, 'the grouping consumes u, so a window of u is a different sum'


def test_an_unknown_dimension_is_refused_with_the_near_miss():
    with pytest.raises(KeyError) as exc:
        _verdict('hh', **_rows('p >= 0'))
    assert 'h' in str(exc.value), 'the message names the axis it was probably reaching for'


@pytest.mark.parametrize('dimension', ['t', 'g', 'zone'])
def test_every_node_a_program_can_carry_is_judged_without_raising(dimension):
    """The fixture the node fence maintains carries every construct, so this is
    the pass meeting each of them at least once."""
    verdict = ms.to_program(FIXTURE).separability(dimension)
    assert isinstance(verdict.halo, int), 'a verdict comes back for every axis of the widest model there is'
