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

from math_spec import to_spec
from math_spec.program import Reach

FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'every_program_node.yaml'

BASE: dict[str, Any] = {
    'dimensions': {'h': {'dtype': 'int'}, 'u': {'dtype': 'str'}, 'zone': {'dtype': 'str'}, 'day': {'dtype': 'int'}},
    'relations': {'zone_of': {'key': 'u', 'values': 'zone'}, 'day_of': {'key': 'h', 'values': 'day'}},
    'parameters': {
        'cost': {'dims': ['u']},
        'budget': {'dims': []},
        'width': {'dims': ['u'], 'dtype': 'int'},
        'cap': {'dims': ['zone']},
    },
    'variables': {'p': {'dims': ['h', 'u'], 'bounds': {'lower': 0}}},
    'objective': {'sense': 'minimize', 'expression': 'sum(p * cost)'},
}


def _verdict(dimension: str = 'h', **patch: Any):
    return to_spec({**BASE, **patch}).program.separability[dimension]


def _rows(expression: str, *, dims: list[str] | None = None, **block: Any) -> dict[str, Any]:
    return {'constraints': {'k': {'dims': dims or ['h', 'u'], 'expression': expression, **block}}}


@pytest.mark.parametrize(
    ('patch', 'ahead'),
    [
        pytest.param(_rows('p >= 0'), 0, id='pointwise-needs-no-overlap'),
        pytest.param(
            _rows('p >= shift(p, along=h, offset=1, edge=0)'), 0, id='a-shift-behind-is-the-edge-and-asks-nothing'
        ),
        pytest.param(_rows('p >= shift(p, along=h, offset=-2, edge=0)'), 2, id='a-negative-shift-reads-ahead'),
        pytest.param(_rows('sum_back(p, along=h, window=4) >= 0'), 0, id='a-trailing-window-reads-behind-only'),
        pytest.param(_rows('sum_back(p, along=h, window=width) >= 0'), 0, id='and-so-does-one-of-a-width-from-data'),
        pytest.param(_rows('p >= shift(p, along=u, offset=-1, edge=0)'), 0, id='a-shift-along-another-axis-is-nothing'),
    ],
)
def test_a_separable_model_reports_the_lookahead_a_window_needs(patch, ahead):
    verdict = _verdict(**patch)
    assert verdict.windowable, 'nothing here ties the axis together'
    assert verdict.ahead == ahead, 'a window must see past its last row what the widest translation reads ahead'


@pytest.mark.parametrize(
    ('patch', 'fragment'),
    [
        pytest.param(_rows('sum(p, over=h) <= budget', dims=['u']), 'sums over h', id='a-budget-over-the-horizon'),
        pytest.param(_rows("p >= shift(p, along=h, offset=1, edge='wrap')"), 'wraps around h', id='a-cyclic-shift'),
    ],
)
def test_a_model_the_axis_ties_together_names_what_ties_it(patch, fragment):
    verdict = _verdict(**patch)
    assert not verdict.windowable, 'this shape does not survive being cut into windows'
    assert fragment in verdict.coupled["constraint 'k'"], 'the report names the construct, not just the declaration'
    assert not verdict.undecided and not verdict.restarts, 'a coupling is not something data or a driver resolves'


@pytest.mark.parametrize(
    ('patch', 'reach'),
    [
        pytest.param(
            _rows('p >= shift(p, along=h, offset=1, within=day_of[day], edge=0)'),
            Reach("constraint 'k'", 'day_of', 'partition'),
            id='a-shift-inside-groups',
        ),
        pytest.param(
            _rows('p >= shift(p, along=h, offset=width, edge=0)'),
            Reach("constraint 'k'", 'width', 'offset'),
            id='an-offset-from-data',
        ),
    ],
)
def test_a_reach_only_data_can_say_names_what_says_it(patch, reach):
    """The verdict names the parameter or relation and what it stands as, rather
    than refusing the model, so a driver holding the data knows what to read
    and `resolved` knows how to fold it."""
    verdict = _verdict(**patch)
    assert not verdict.windowable, 'undecided until data binds'
    assert verdict.undecided == (reach,), 'the report names what the driver has to read, once'
    assert not verdict.coupled, 'and nothing structural ties the axis'


@pytest.mark.parametrize(
    ('patch', 'least', 'ahead'),
    [
        pytest.param(_rows('p >= shift(p, along=h, offset=width, edge=0)'), 1, 0, id='offsets-behind-ask-nothing'),
        pytest.param(
            _rows('p >= shift(p, along=h, offset=width, edge=0)'), -3, 3, id='offsets-ahead-read-by-the-least'
        ),
        pytest.param(
            _rows('shift(p, along=h, offset=width, edge=0) + shift(p, along=h, offset=-1, edge=0) + p >= 0'),
            -3,
            3,
            id='a-folded-value-widens-what-the-model-reads-on-its-own',
        ),
    ],
)
def test_a_named_reach_resolves_to_the_lookahead_its_values_need(patch, least, ahead):
    """The rule turning a value into a reach lives here and nowhere in a driver:
    the driver reads the least value and hands it over."""
    verdict = _verdict(**patch).resolved({'width': least})
    assert verdict.windowable, 'with every named reach folded in, nothing is undecided'
    assert verdict.ahead == ahead, 'the value decides the lookahead, by its sign'


def test_resolving_keeps_the_static_reach_and_what_a_relation_decides():
    verdict = _verdict(
        constraints={
            'fixed': {'dims': ['h', 'u'], 'expression': 'p >= shift(p, along=h, offset=-2, edge=0)'},
            'named': {'dims': ['h', 'u'], 'expression': 'p >= shift(p, along=h, offset=width, edge=0)'},
            'grouped': {
                'dims': ['h', 'u'],
                'expression': 'p >= shift(p, along=h, offset=1, within=day_of[day], edge=0)',
            },
        }
    ).resolved({'width': -1})
    assert verdict.ahead == 2, 'a folded value never narrows what the model reads on its own'
    assert verdict.undecided == (Reach("constraint 'grouped'", 'day_of', 'partition'),), (
        'a reach a relation decides is not a value and stays undecided'
    )
    assert not verdict.windowable, 'so the axis is still not windowable'


def test_resolving_a_name_nothing_waits_on_is_refused():
    with pytest.raises(KeyError, match="'depth' is not a parameter an undecided reach along 'h' waits on"):
        _verdict(**_rows('p >= shift(p, along=h, offset=width, edge=0)')).resolved({'depth': 0})


def test_a_read_through_a_relation_is_undecided_on_the_axis_it_reads():
    """`at(cap, by=zone_of[zone])` reads `zone` at whatever coordinate the relation
    chooses, so how far that reaches along `zone` is the relation's data to say."""
    verdict = _verdict('zone', **_rows('p - at(cap, by=zone_of[zone]) <= 0'))
    assert not verdict.windowable and not verdict.coupled, 'undecided until the relation binds'
    assert verdict.undecided == (Reach("constraint 'k'", 'zone_of', 'coordinate'),), (
        'the report names the relation a driver has to read'
    )


def test_a_sum_over_a_lookup_is_a_sum_and_a_lookup_not_a_grouping():
    """A plain `sum` over an `at` lowered to the `Sum` over a `Join` that a grouped sum lowered to.

    Separability read the shape, so it reported a grouping of `u` into `u` and
    lost the read of `zone` the lookup waits on. Which call a join is comes
    from its columns, not from the node above it.
    """
    variables = {**BASE['variables'], 'q': {'dims': ['h', 'zone'], 'bounds': {'lower': 0}}}
    rows = _rows('sum(at(q, by=zone_of[zone]), over=u) <= budget', dims=['h'])
    program = to_spec({**BASE, 'variables': variables, **rows}).program
    assert list(program.separability['u'].coupled.values()) == [
        'sums over u — a rolling sum_back(window=n) windows, a total over the horizon does not'
    ], 'the sum over u is a plain sum, reported as one'
    assert program.separability['zone'].undecided == (Reach("constraint 'k'", 'zone_of', 'coordinate'),), (
        'the lookup under it still reads zone at a coordinate the relation chooses'
    )


def test_a_coupling_names_the_change_that_would_lift_it():
    coupled = _verdict(**_rows('sum(p, over=h) <= budget', dims=['u'])).coupled["constraint 'k'"]
    assert 'sum_back(window=n)' in coupled, 'a horizon total becomes a rolling one'
    wrapped = _verdict(**_rows("p >= shift(p, along=h, offset=1, edge='wrap')")).coupled["constraint 'k'"]
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
    coupled = _verdict(**_rows('sum(p, over=h) <= budget', dims=['u']))
    assert not coupled.windowable, 'the same sum in a constraint is one'


def test_a_position_inside_a_cased_region_is_found():
    """`children` descends into a region's value and not its `when`, so a mask
    written inside `cases:` is reachable by no expression walk — and seeding a
    quantity at the start of the axis is exactly what a rolling horizon does."""
    verdict = _verdict(
        expressions={
            'prev': {
                'dims': ['h', 'u'],
                'cases': {'opening': {'when': 'position(h) == 0', 'expression': 0}},
                'otherwise': 'shift(p, along=h, offset=1, edge=0)',
            }
        },
        **_rows('p - prev <= 1'),
    )
    assert "constraint 'k'" in verdict.restarts, 'the seed fires once over a horizon and once per window'


def test_the_lookahead_is_the_widest_reach_of_any_block():
    verdict = _verdict(
        constraints={
            'near': {'dims': ['h', 'u'], 'expression': 'p >= shift(p, along=h, offset=-1, edge=0)'},
            'far': {'dims': ['h', 'u'], 'expression': 'p >= shift(p, along=h, offset=-5, edge=0)'},
        }
    )
    assert verdict.ahead == 5, 'one window must see past its last row as far as any block reads'


def test_a_grouping_that_sums_the_axis_away_couples_it():
    program = to_spec(
        {
            **BASE,
            'constraints': {'z': {'dims': ['h', 'zone'], 'expression': 'sum(p, over=u, by=zone_of[zone]) <= cap'}},
        }
    ).program
    verdict = program.separability['u']
    assert not verdict.windowable, 'the grouping sums u away, so a window of u is a different sum'
    assert verdict.coupled == {
        "constraint 'z'": 'groups u into zone — window that dimension instead, or cut only at the group edges'
    }, 'the sum over the join is the grouping, reported once'
    assert not verdict.undecided, 'the join under the sum is not also a lookup waiting on the relation'


def test_every_declared_axis_has_a_verdict_and_nothing_else_does():
    """The mapping is complete over the program's dimensions, so an axis nothing
    mentions is trivially windowable rather than missing, and a name that is not
    an axis is a `KeyError` rather than a verdict nobody should trust."""
    program = to_spec({**BASE, **_rows('p >= 0')}).program
    assert sorted(program.separability) == sorted(program.dimensions), 'every declared axis is answered for'
    assert program.separability['zone'].windowable, 'an axis no construct mentions is trivially windowable'
    with pytest.raises(KeyError):
        program.separability['hh']


@pytest.mark.parametrize('dimension', ['t', 'g', 'zone'])
def test_every_node_a_program_can_carry_is_judged_without_raising(dimension):
    """The fixture the node fence maintains carries every construct, so this is
    the pass meeting each of them at least once."""
    verdict = to_spec(FIXTURE).program.separability[dimension]
    assert isinstance(verdict.ahead, int), 'a verdict comes back for every axis of the widest model there is'


def test_a_reduction_over_several_axes_couples_every_one_of_them():
    """`sum(p)` with no `over=` collapses every dimension its operand carries,
    so the verdict for each of them has to say so — a walk that read only the
    first would call the rest windowable."""
    program = to_spec({**BASE, 'constraints': {'all': {'dims': [], 'expression': 'sum(p) <= budget'}}}).program
    assert not program.separability['h'].windowable, 'the reduction sums h away'
    assert not program.separability['u'].windowable, 'and u, in the same node'


#: A model with a border along `h`, and none along `u`. `built` is a column
#: every window of `h` reads, `cap` is a row one coordinate of `h` holds on its
#: own, `budget` is a row the horizon ties together, and `peak` is a row the
#: horizon does not index at all.
BORDER: dict[str, Any] = {
    'variables': {
        'p': {'dims': ['h', 'u'], 'bounds': {'lower': 0}},
        'built': {'dims': ['u'], 'bounds': {'lower': 0}},
    },
    'constraints': {
        'cap': {'dims': ['h', 'u'], 'expression': 'p <= built'},
        'budget': {'dims': ['u'], 'expression': 'sum(p, over=h) <= built'},
        'peak': {'dims': ['u'], 'expression': 'built <= budget'},
    },
}


def test_the_border_of_a_block_form_is_what_no_one_block_holds():
    """The same walk read as a set. A driver that cuts `h` into blocks builds
    each block from the rows and columns the axis indexes, and what is left over
    is the border it shares: the linking rows and the linking columns of a
    bordered block-diagonal form."""
    verdict = _verdict(**BORDER)
    assert verdict.linking_rows == ('budget', 'peak'), (
        'a row the axis ties together and a row it does not index, in declaration order, and no third'
    )
    assert verdict.linking_columns == ('built',), 'the one column every block reads, p being a column per block'
    along_u = _verdict('u', **BORDER)
    assert along_u.linking_rows == (), "cut along u instead, every row is one block's own"
    assert along_u.linking_columns == (), 'and every column is, so that cut needs no border at all'


@pytest.mark.parametrize(
    ('patch', 'rows'),
    [
        pytest.param(_rows('p >= 0'), (), id='a-pointwise-row-belongs-to-one-block'),
        pytest.param(_rows('p >= shift(p, along=h, offset=-2, edge=0)'), (), id='and-so-is-one-a-lookahead-completes'),
        pytest.param(
            _rows('p >= shift(p, along=h, offset=width, edge=0)'), (), id='an-undecided-reach-is-not-yet-a-border-row'
        ),
        pytest.param(_rows('sum(p, over=h) <= budget', dims=['u']), ('k',), id='a-horizon-total-is-one'),
        pytest.param(_rows("p >= shift(p, along=h, offset=1, edge='wrap')"), ('k',), id='and-so-is-a-row-that-wraps'),
    ],
)
def test_a_row_reaches_the_border_only_when_no_one_block_holds_it(patch, rows):
    assert _verdict(**patch).linking_rows == rows, 'the border names each constraint and no other, whole'


@pytest.mark.parametrize(
    ('patch', 'label'),
    [
        pytest.param(
            {
                'objective': {'sense': 'minimize', 'expression': "sum(shift(p, along=h, offset=1, edge='wrap'))"},
                **_rows('p >= 0'),
            },
            'the objective',
            id='an-objective-that-wraps-around-the-axis',
        ),
        pytest.param(
            {
                'sos': {'s': {'variable': 'p', 'along': 'h', 'type': 1}},
                'variables': {'p': {'dims': ['h', 'u'], 'bounds': {'lower': 0, 'upper': 10}}},
                **_rows('p >= 0'),
            },
            "set 's'",
            id='a-set-the-axis-runs-through',
        ),
    ],
)
def test_a_coupling_carried_by_a_declaration_that_builds_no_row_stays_off_the_border(patch, label):
    """The objective is one row that no cut of the axis divides, and a set names
    columns that already exist. Neither builds a constraint row for a block to
    hold, so neither reaches the border. The coupling is reported all the same,
    because a window still cannot honour it."""
    verdict = _verdict(**patch)
    assert label in verdict.coupled, 'the coupling is reported against the declaration that carries it'
    assert verdict.linking_rows == (), 'and the one constraint here is pointwise, so the border holds no row'
