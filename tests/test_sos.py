# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""`sos:` as a formulation: what a set is written out as, and what it may not lose.

Every claim here is one `Spec.expand` reaches with no data bound — which
declarations a set emits, which coefficient links them, and that the adjacency
method is the same rows under the same names.
"""

from __future__ import annotations

import pytest

from math_spec.lowering import to_program
from tests.fixtures import SMALL_MODEL, override, schema_of

#: A set over a bounded member, which is the smallest model `expand('sos')` acts on.
PICKED = override(
    SMALL_MODEL,
    **{
        'variables.p.bounds': {'lower': 0, 'upper': 10},
        'constraints': {'used': {'dims': ['g'], 'expression': 'p <= c'}},
        'sos': {'pick': {'variable': 'p', 'over': 'g', 'type': 1}},
    },
)

#: The curve of `examples/sos.yaml`, as a dict a test can vary.
CURVE = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'bp': {'dtype': 'int'}},
    'parameters': {'load': {'dims': ['snapshot']}, 'bp_x': {'dims': ['bp']}, 'bp_y': {'dims': ['bp']}},
    'variables': {
        'p': {'dims': ['snapshot'], 'bounds': {'lower': 0, 'upper': 100}},
        'op_cost': {'dims': ['snapshot'], 'bounds': {'lower': 0}},
    },
    'piecewise': {'cost_curve': {'over': 'bp', 'method': 'sos2', 'links': [['p', 'bp_x'], ['op_cost', 'bp_y']]}},
    'constraints': {'balance': {'dims': ['snapshot'], 'expression': 'p == load'}},
    'objective': {'sense': 'minimize', 'expression': 'sum(op_cost, over=snapshot)'},
}


def test_a_set_of_order_one_admits_a_member_only_where_its_own_binary_is_one():
    expanded = schema_of(PICKED).expand('sos')

    assert not expanded.sos, 'the block is spent once its declarations are emitted'
    assert expanded.variables['pick_seg'].domain == 'binary'
    assert expanded.variables['pick_seg'].dims == ['g'], "the binary runs over the member's own dims"
    assert expanded.constraints['pick_pick'].expression == 'sum(pick_seg, over=g) <= 1'
    assert expanded.constraints['pick_nonzero'].expression == 'p <= 10.0 * (pick_seg)'


def test_a_set_of_order_two_admits_a_member_in_either_half_of_one_segment():
    schema = schema_of(override(PICKED, **{'sos.pick.type': 2}))
    expanded = schema.expand('sos')

    assert expanded.constraints['pick_adjacency'].expression == (
        'p <= 10.0 * (pick_seg + shift(pick_seg, along=g, offset=1, edge=0))'
    )
    assert 'pick_nonzero' not in expanded.constraints, 'the order decides which linking row is written'


def test_the_declared_bound_is_the_coefficient_rather_than_the_tighter_of_it_and_the_upper():
    """Two consumers took different sides of this and solved different models."""
    schema = schema_of(override(PICKED, **{'sos.pick.bound': 500}))

    assert schema.expand('sos').constraints['pick_nonzero'].expression == 'p <= 500.0 * (pick_seg)'


def test_a_binary_member_links_by_the_one_its_domain_fixes():
    """A binary carries no bounds block, and its upper bound is 1 all the same."""
    schema = schema_of(override(PICKED, **{'variables.p': {'dims': ['g'], 'domain': 'binary'}}))

    assert schema.expand('sos').constraints['pick_nonzero'].expression == 'p <= 1.0 * (pick_seg)'


def test_the_emitted_binary_carries_the_members_own_mask():
    """A member that does not exist is not in the set, so its binary is not there either."""
    schema = schema_of(override(PICKED, **{'variables.p.where': 'flag'}))

    assert schema.expand('sos').variables['pick_seg'].where == 'flag'


def test_a_set_emits_no_parameter_so_the_same_sources_bind_both():
    program, written_out = to_program(schema_of(PICKED)), to_program(schema_of(PICKED).expand('sos'))

    assert set(written_out.parameters) == set(program.parameters), 'a set states rows and columns, never data'


def test_the_adjacency_method_is_the_sos2_curve_with_its_set_written_out():
    """The one spelling of the binaries, so the two methods cannot drift apart."""
    sos2 = to_program(schema_of(CURVE).expand())
    adjacency = to_program(schema_of(override(CURVE, **{'piecewise.cost_curve.method': 'adjacency'})))

    assert sos2.variables == adjacency.variables
    assert sos2.constraints == adjacency.constraints
    assert not sos2.sos and not adjacency.sos, 'neither hands a solver a set'
    assert sos2.piecewise['cost_curve'].method == 'sos2', 'the block still records the method it declared'
    assert adjacency.piecewise['cost_curve'].method == 'adjacency'


@pytest.mark.parametrize(
    ('kinds', 'sets', 'curves'),
    [
        pytest.param(('piecewise',), ['cost_curve'], [], id='curves-only-leaves-the-set-it-emitted'),
        pytest.param(('sos',), [], ['cost_curve'], id='sets-only-reaches-no-set-a-curve-has-not-emitted-yet'),
        pytest.param((), [], [], id='both-writes-out-the-set-the-curve-emitted'),
    ],
)
def test_a_curve_emits_a_set_and_no_set_emits_a_curve(kinds, sets, curves):
    """Which is why the order is fixed rather than the caller's."""
    expanded = schema_of(CURVE).expand(*kinds)

    assert sorted(expanded.sos) == sets
    assert sorted(expanded.piecewise) == curves
