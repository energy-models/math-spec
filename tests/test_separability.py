# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Whether a horizon may be built in windows, asked before any data binds.

The verdict is what a rolling-horizon or myopic driver needs and cannot
currently get: a model with an annual budget windows into feasible pieces whose
rows are incomplete, and nothing says so. Every case below is one model shape
and the verdict it earns, because the value of the pass is entirely in getting
the boundary between the categories right.
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
    return ms.to_program({**BASE, **patch}).separability[dimension]


def _rows(expression: str, *, foreach: list[str] | None = None, **block: Any) -> dict[str, Any]:
    return {'constraints': {'k': {'foreach': foreach or ['h', 'u'], 'expression': expression, **block}}}


@pytest.mark.parametrize(
    ('patch', 'behind', 'ahead'),
    [
        pytest.param(_rows('p >= 0'), 0, 0, id='pointwise-needs-no-overlap'),
        pytest.param(_rows('p >= shift(p, over=h, offset=1, edge=0)'), 1, 0, id='a-shift-of-one-reads-one-row-behind'),
        pytest.param(_rows('p >= shift(p, over=h, offset=3, edge=0)'), 3, 0, id='a-shift-of-three-reads-three-behind'),
        pytest.param(_rows('p >= shift(p, over=h, offset=-2, edge=0)'), 0, 2, id='a-negative-shift-reads-ahead'),
        pytest.param(_rows('sum_back(p, over=h, within=4) >= 0'), 3, 0, id='a-window-of-four-reads-three-behind'),
        pytest.param(
            _rows('p >= shift(p, over=u, offset=1, edge=0)'), 0, 0, id='a-shift-along-another-axis-is-nothing'
        ),
    ],
)
def test_a_separable_model_reports_the_overlap_a_window_needs_on_each_side(patch, behind, ahead):
    verdict = _verdict(**patch)
    assert verdict.windowable, 'nothing here ties the axis together'
    assert (verdict.behind, verdict.ahead) == (behind, ahead), (
        'a window must see what the widest translation reads before its first row and after its last'
    )


@pytest.mark.parametrize(
    ('patch', 'fragment'),
    [
        pytest.param(_rows('sum(p, over=h) <= budget', foreach=['u']), 'sums over h', id='a-budget-over-the-horizon'),
        pytest.param(_rows("p >= shift(p, over=h, offset=1, edge='wrap')"), 'wraps around h', id='a-cyclic-shift'),
    ],
)
def test_a_model_the_axis_ties_together_names_what_ties_it(patch, fragment):
    verdict = _verdict(**patch)
    assert not verdict.windowable, 'this shape does not survive being cut into windows'
    assert fragment in verdict.coupled["constraint 'k'"], 'the report names the construct, not just the declaration'
    assert not verdict.undecided and not verdict.restarts, 'a coupling is not something data or a driver resolves'


@pytest.mark.parametrize(
    ('patch', 'named'),
    [
        pytest.param(_rows('p >= shift(p, over=h, offset=1, by=day_of, edge=0)'), 'day_of', id='a-shift-inside-groups'),
        pytest.param(_rows('p >= shift(p, over=h, offset=width, edge=0)'), 'width', id='an-offset-from-data'),
        pytest.param(_rows('sum_back(p, over=h, within=width) >= 0'), 'width', id='a-width-from-data'),
    ],
)
def test_a_reach_only_data_can_say_names_what_says_it(patch, named):
    """A driver holding the data can compute this reach itself — the max of an
    offset parameter, the runs a partition makes — so the verdict names the
    parameter or lookup rather than refusing the model."""
    verdict = _verdict(**patch)
    assert not verdict.windowable, 'undecided until data binds'
    assert verdict.undecided["constraint 'k'"] == named, 'the report names what the driver has to read'
    assert not verdict.coupled, 'and nothing structural ties the axis'


def test_a_read_through_a_lookup_is_undecided_on_the_axis_it_reads():
    """`at(cap, by=zone_of)` reads `zone` at whatever coordinate the lookup
    chooses, so how far that reaches along `zone` is the lookup's data to say."""
    verdict = _verdict('zone', **_rows('p - at(cap, by=zone_of) <= 0'))
    assert not verdict.windowable and not verdict.coupled, 'undecided until the lookup binds'
    assert verdict.undecided["constraint 'k'"] == 'zone_of', 'the report names the lookup a driver has to read'


@pytest.mark.parametrize(
    ('patch', 'independent'),
    [
        pytest.param(_rows('p >= 0'), True, id='pointwise-slices-in-any-order'),
        pytest.param(_rows('p >= shift(p, over=h, offset=1, edge=0)'), False, id='a-row-reading-another-is-not'),
        pytest.param(_rows('p >= 0', where='position(h) == 0'), False, id='a-position-means-something-else-per-slice'),
        pytest.param(_rows('p >= shift(p, over=h, offset=width, edge=0)'), False, id='an-undecided-reach-is-not'),
    ],
)
def test_independence_is_windowability_with_nothing_read_across_and_nothing_counted(patch, independent):
    verdict = _verdict(**patch)
    assert verdict.independent is independent, 'one coordinate per slice needs no row to read or count another'


def test_a_coupling_names_the_change_that_would_lift_it():
    coupled = _verdict(**_rows('sum(p, over=h) <= budget', foreach=['u'])).coupled["constraint 'k'"]
    assert 'sum_back(within=n)' in coupled, 'a horizon total becomes a rolling one'
    wrapped = _verdict(**_rows("p >= shift(p, over=h, offset=1, edge='wrap')")).coupled["constraint 'k'"]
    assert 'position(h) == 0' in wrapped, 'a wrap becomes an opening-state seed'


def test_a_mask_counting_a_position_is_reported_and_not_refused():
    """`position(h) == 0` fires once over a horizon and once per window, and a
    rolling horizon seeding its opening state means the second. The verdict
    stays windowable and says where a window would restart the count."""
    verdict = _verdict(**_rows('p >= 0', where='position(h) == 0'))
    assert verdict.windowable, 'a seed is a modelling intent, not a coupling'
    assert verdict.restarts == {"constraint 'k'": 'counts a position along h'}, 'the report names the declaration'


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
    assert "constraint 'k'" in verdict.restarts, 'the seed fires once over a horizon and once per window'


def test_the_overlap_is_the_widest_reach_of_any_block():
    verdict = _verdict(
        constraints={
            'near': {'foreach': ['h', 'u'], 'expression': 'p >= shift(p, over=h, offset=1, edge=0)'},
            'far': {'foreach': ['h', 'u'], 'expression': 'p >= shift(p, over=h, offset=5, edge=0)'},
        }
    )
    assert verdict.behind == 5, 'one window must see behind its first row as far as any block reads'


def test_a_grouping_that_consumes_the_axis_couples_it():
    program = ms.to_program(
        {**BASE, 'constraints': {'z': {'foreach': ['h', 'zone'], 'expression': 'sum(p, by=zone_of) <= cap'}}}
    )
    verdict = program.separability['u']
    assert not verdict.windowable, 'the grouping consumes u, so a window of u is a different sum'


def test_every_declared_axis_has_a_verdict_and_nothing_else_does():
    """The mapping is complete over the program's dimensions, so an axis nothing
    mentions is trivially windowable rather than missing, and a name that is not
    an axis is a `KeyError` rather than a verdict nobody should trust."""
    program = ms.to_program({**BASE, **_rows('p >= 0')})
    assert sorted(program.separability) == sorted(program.dimensions), 'every declared axis is answered for'
    assert program.separability['zone'].windowable, 'an axis no construct mentions is trivially windowable'
    with pytest.raises(KeyError):
        program.separability['hh']


@pytest.mark.parametrize('dimension', ['t', 'g', 'zone'])
def test_every_node_a_program_can_carry_is_judged_without_raising(dimension):
    """The fixture the node fence maintains carries every construct, so this is
    the pass meeting each of them at least once."""
    verdict = ms.to_program(FIXTURE).separability[dimension]
    assert isinstance(verdict.behind, int), 'a verdict comes back for every axis of the widest model there is'


def test_a_reduction_over_several_axes_couples_every_one_of_them():
    """`sum(p)` with no `over=` collapses every dimension its operand carries,
    so the verdict for each of them has to say so — a walk that read only the
    first would call the rest windowable."""
    program = ms.to_program({**BASE, 'constraints': {'all': {'foreach': [], 'expression': 'sum(p) <= budget'}}})
    assert not program.separability['h'].windowable, 'the reduction consumes h'
    assert not program.separability['u'].windowable, 'and u, in the same node'
