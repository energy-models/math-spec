# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""`piecewise:` expansion, judged at the door that decides it.

Every claim here is one `to_spec` or `expand_piecewise` reaches with no data
bound: which declarations a curve emits, which names it may not collide with,
which methods exist, and which gates a block will accept.
"""

from __future__ import annotations

from typing import get_args

import pytest

from math_spec import CURVATURES, to_spec
from math_spec.errors import LanguageError, PiecewiseExpansionError, SchemaError
from math_spec.lowering import lower_program, to_program
from math_spec.model import _ExpandedSpec
from math_spec.piecewise import expand_piecewise
from math_spec.program import (
    AtLeastTwo,
    Check,
    Contiguous,
    Curved,
    FirstOf,
    Increasing,
    LastOf,
    MaskOf,
    check_message,
)
from tests.fixtures import DISPATCH_MODEL, override, raw_of, schema_of

#: Larger than a minimal probe on purpose: a curve that exercises adjacency
#: binaries and links is not something a smaller one can stand in for.
NONCONVEX_YAML = """
dimensions:
  snapshot: {dtype: int}
  bp: {dtype: int}

parameters:
  load: {dims: [snapshot]}
  bp_x: {dims: [bp]}
  bp_y: {dims: [bp]}

variables:
  p:
    dims: [snapshot]
    bounds: {lower: 0, upper: 100}
  op_cost:
    dims: [snapshot]
    bounds: {lower: 0}

piecewise:
  cost_curve:
    along: bp
    links:
      - [p, bp_x]
      - [op_cost, bp_y]

constraints:
  balance:
    dims: [snapshot]
    expression: p == load

objective:
  sense: minimize
  expression: sum(op_cost, over=snapshot)
"""
GATED = override(
    raw_of(NONCONVEX_YAML),
    **{'variables.u': {'dims': ['snapshot'], 'domain': 'binary'}, 'piecewise.cost_curve.activity': 'u'},
)
#: The convex curve stated as its segment lines, plus a binary the method cannot gate on.
LP = override(
    raw_of(NONCONVEX_YAML),
    **{
        'piecewise.cost_curve.method': 'lp',
        'piecewise.cost_curve.links': [['p', 'bp_x'], ['op_cost', 'bp_y', '>=']],
        'variables.running': {'dims': ['snapshot'], 'domain': 'binary'},
    },
)
#: The ``lp`` curve masked by one of its own values-parameters, so every check a block can carry is on it.
LP_MASKED = override(LP, **{'piecewise.cost_curve.points': 'bp_x'})
#: Two dims in the frame, so the emitted ``dims`` has an order to get wrong.
TWO_DIM = override(
    raw_of(NONCONVEX_YAML),
    **{
        'dimensions.generator': {'dtype': 'str'},
        'parameters.bp_x.dims': ['generator', 'bp'],
        'parameters.bp_y.dims': ['generator', 'bp'],
        'variables.p.dims': ['snapshot', 'generator'],
        'variables.op_cost.dims': ['snapshot', 'generator'],
        'constraints.balance.expression': 'sum(p, over=generator) == load',
        'objective.expression': 'sum(op_cost)',
    },
)


def test_expansion_emits_the_lambda_declarations():
    expanded = expand_piecewise(schema_of(NONCONVEX_YAML))

    assert not expanded.piecewise, 'the block is spent once its declarations are emitted'
    assert 'cost_curve_lam' in expanded.variables
    assert expanded.variables['cost_curve_seg'].domain == 'binary'
    assert set(expanded.constraints) >= {
        'cost_curve_convexity',
        'cost_curve_pick',
        'cost_curve_adjacency',
        'cost_curve_link0',
        'cost_curve_link1',
        'balance',
    }, "the adjacency formulation's five rows, one link each, beside the constraint the file wrote"


def test_an_emitted_set_may_not_collide_with_a_declared_one():
    """The emitted-name rule, for the one declaration kind that is new."""
    with pytest.raises(PiecewiseExpansionError, match="emitted sos 'cost_curve' collides"):
        schema_of(NONCONVEX_YAML, sos={'cost_curve': {'variable': 'p', 'along': 'snapshot', 'type': 1}})


@pytest.mark.parametrize('method', [pytest.param('incremental', id='unknown'), pytest.param(['sos2'], id='a list')])
def test_a_method_this_project_does_not_have_is_refused(method):
    """A list used to escape the membership test as a `TypeError`."""
    with pytest.raises(SchemaError, match='unknown piecewise method'):
        schema_of(NONCONVEX_YAML, **{'piecewise.cost_curve.method': method})


def test_the_file_is_not_an_expansion_and_the_expansion_is():
    """A `Spec` may still owe declarations to a `piecewise:` block; an `_ExpandedSpec` owes none."""
    schema = schema_of(NONCONVEX_YAML)

    assert not isinstance(schema, _ExpandedSpec)
    assert isinstance(expand_piecewise(schema), _ExpandedSpec)


def test_expansion_is_memoised_and_idempotent():
    """One object from every call: validation already built the expansion, and an `_ExpandedSpec` is its own."""
    schema = schema_of(NONCONVEX_YAML)
    expanded = expand_piecewise(schema)
    assert expand_piecewise(schema) is expanded
    assert expand_piecewise(expanded) is expanded

    curveless = schema_of(DISPATCH_MODEL)
    expanded = expand_piecewise(curveless)
    assert isinstance(expanded, _ExpandedSpec), 'a curve-free file is its own expansion, and says so in its type'
    assert expand_piecewise(curveless) is expanded
    assert expanded.constraints.keys() == curveless.constraints.keys(), 'retyping declares nothing new'


def test_an_expansion_will_not_be_built_around_a_curve():
    """`expand_piecewise` is the only thing that produces one; validated straight from a file, the type would lie."""
    with pytest.raises(SchemaError, match='expand_piecewise is what produces one'):
        _ExpandedSpec.model_validate(raw_of(NONCONVEX_YAML))


@pytest.mark.parametrize(
    'order',
    [
        pytest.param(['snapshot', 'generator', 'bp'], id='snapshot-first'),
        pytest.param(['generator', 'snapshot', 'bp'], id='generator-first'),
    ],
)
def test_the_emitted_foreach_follows_declaration_order(order):
    """The frame is a set until something orders it, and a set iterates the
    same way for the same names within one process — so a run that reads the
    set rather than the declaration fails one of the two orderings."""
    schema = schema_of(TWO_DIM, dimensions={d: TWO_DIM['dimensions'][d] for d in order})
    assert expand_piecewise(schema).variables['cost_curve_lam'].dims == order


@pytest.mark.parametrize(
    'link',
    [
        pytest.param('p * 2', id='arithmetic'),
        pytest.param('twice(p)', id='a-macro-call'),
        pytest.param('doubled', id='a-named-expression'),
        pytest.param('twice(doubled) + 1', id='both'),
    ],
)
def test_any_affine_expression_is_a_legal_link(link):
    """A link is read as a constraint's expression is — a macro or a named expression in it expands."""
    schema = schema_of(
        NONCONVEX_YAML,
        macros={'twice': {'args': ['x'], 'template': 'x * 2'}},
        expressions={'doubled': 'p * 2'},
        **{'piecewise.cost_curve.links': [[link, 'bp_x'], ['op_cost', 'bp_y']]},
    )
    assert expand_piecewise(schema).constraints['cost_curve_link0'].expression.startswith(f'({link}) ==')


@pytest.mark.parametrize(
    ('model', 'patch', 'match'),
    [
        pytest.param(
            NONCONVEX_YAML,
            {'piecewise.cost_curve.links': [['p', 'bp_x', '<='], ['op_cost', 'bp_y', '>=']]},
            'nothing pins the operating point',
            id='every-link-bounded',
        ),
        pytest.param(
            NONCONVEX_YAML,
            {
                'piecewise.cost_curve.method': 'convex',
                'piecewise.cost_curve.links': [['p', 'bp_x'], ['op_cost', 'bp_y'], ['p', 'bp_x']],
            },
            'exactly two links',
            id='convex-needs-exactly-two-links',
        ),
        pytest.param(
            GATED,
            {'piecewise.cost_curve.method': 'convex'},
            'activity is not supported',
            id='convex-cannot-be-gated',
        ),
        pytest.param(
            GATED,
            {'variables.u': {'dims': ['snapshot'], 'bounds': {'lower': 0, 'upper': 1}}},
            'must be binary',
            id='activity-must-be-binary',
        ),
        pytest.param(
            NONCONVEX_YAML,
            {'piecewise.cost_curve.links': [['p', 'bp_x'], ['op_cost', 'nope']]},
            "undeclared parameter 'nope'",
            id='undeclared-parameter',
        ),
        pytest.param(
            NONCONVEX_YAML,
            {'parameters.reach': {'dims': ['bp']}, 'piecewise.cost_curve.points': 'reach'},
            "points parameter 'reach' is float, and a mask is a bool parameter",
            id='points-that-are-not-a-mask',
        ),
        pytest.param(
            LP,
            {'piecewise.cost_curve.links': [['p', 'bp_x'], ['op_cost', 'bp_y']]},
            'needs exactly one link bounded by the curve',
            id='lp-with-both-links-pinned',
        ),
        pytest.param(
            LP,
            {'piecewise.cost_curve.links': [['p', 'bp_x'], ['op_cost', 'bp_y'], ['p', 'bp_x']]},
            'requires exactly two links',
            id='lp-with-three-links',
        ),
        pytest.param(
            LP,
            {'piecewise.cost_curve.activity': 'running'},
            'activity is not supported with method: lp',
            id='lp-with-an-activity-and-nothing-to-gate',
        ),
    ],
)
def test_a_malformed_block_is_refused(model, patch, match):
    """Schema-level arity rules and the expansion's own preconditions, before any data is bound.

    Refused rather than fallen back from: a method written down is a formulation chosen.
    """
    with pytest.raises(LanguageError, match=match):
        expand_piecewise(schema_of(model, **patch))


@pytest.mark.parametrize(
    ('link_expression', 'message'),
    [
        pytest.param('p ** 2', 'over variables', id='a-power-of-a-variable'),
        pytest.param('p * p', 'both factors of a product contain variables', id='a-product-of-variables'),
    ],
)
def test_a_link_outside_the_language_is_named_where_the_user_wrote_it(link_expression, message):
    """Lowering would catch these too, but naming ``cost_curve_link0`` — a declaration the user never wrote."""
    with pytest.raises(PiecewiseExpansionError, match=message) as exc:
        schema_of(NONCONVEX_YAML, **{'piecewise.cost_curve.links': [[link_expression, 'bp_x'], ['op_cost', 'bp_y']]})
    assert "piecewise 'cost_curve' link 0" in str(exc.value)


def test_a_link_reading_a_nonlinear_entry_is_refused():
    """A named entry, nonlinear and so legal on its own, is refused where the link reads it.

    `ratio` loads — nothing bans it at declaration — but a
    piecewise link is affine, so reading it there hits the same divisor ban a
    constraint would. The refusal lives at the reading position, not the
    declaration: the entry-declaration relocation for the other math positions
    is `TestValidateExpressions.test_a_nonlinear_entry_is_refused_where_the_math_reads_it`.
    """
    with pytest.raises(PiecewiseExpansionError, match='the divisor contains variables') as exc:
        schema_of(
            NONCONVEX_YAML,
            **{
                'expressions': {'ratio': 'op_cost / sum(p, over=snapshot)'},
                'piecewise.cost_curve.links': [['ratio', 'bp_x'], ['op_cost', 'bp_y']],
            },
        )
    assert "piecewise 'cost_curve' link 0" in str(exc.value)


def test_a_link_reading_a_degree_two_product_entry_is_refused():
    """A degree-2 product entry, legal on its own, is refused where a link reads it affinely.

    The other reading positions that refuse a degree-2 product — the bound —
    name no expression, so a piecewise link is the one affine position that both
    reads a named entry and rejects the product. A constraint and the objective
    accept degree 2, so they are not the refusing site here.
    """
    with pytest.raises(PiecewiseExpansionError, match='which is degree 2') as exc:
        schema_of(
            NONCONVEX_YAML,
            **{
                'expressions': {'sq': 'p * op_cost'},
                'piecewise.cost_curve.links': [['sq', 'bp_x'], ['op_cost', 'bp_y']],
            },
        )
    assert "piecewise 'cost_curve' link 0" in str(exc.value)


def test_an_entry_a_link_reads_is_in_the_math():
    """A link's expression stands inside the constraints its expansion emits, so an entry it names is one the math reads."""
    schema = schema_of(
        NONCONVEX_YAML,
        **{'expressions': {'twice': 'p * 2'}, 'piecewise.cost_curve.links': [['twice', 'bp_x'], ['op_cost', 'bp_y']]},
    )
    assert to_program(schema).named_expressions['twice'].in_math is True


def test_a_link_reading_a_dual_entry_is_refused():
    """A link is math a build ingests, so the dual placement rule fires here as at every other reading position.

    Without the guard the entry's `dual(balance)` would pass the affine check —
    a dual carries no variable — and hand lowering a leaf no piecewise
    expansion can build.
    """
    with pytest.raises(PiecewiseExpansionError, match='a dual exists only after a solve'):
        schema_of(
            NONCONVEX_YAML,
            **{
                'expressions': {'price': 'dual(balance)'},
                'piecewise.cost_curve.links': [['price', 'bp_x'], ['op_cost', 'bp_y']],
            },
        )


@pytest.mark.parametrize(
    ('activity', 'match'),
    [
        pytest.param('at(u_unit, by=unit_of)', 'is not a declared variable', id='a-pullback-through-a-relation'),
        pytest.param('shift(u, along=snapshot, offset=1)', 'is not a declared variable', id='a-shifted-gate'),
        pytest.param('u * 2', 'is not a declared variable', id='an-arithmetic-gate'),
    ],
)
def test_a_gate_that_is_not_a_variable_is_refused(activity, match):
    """Only a variable has a declaration to say what its absence means, and the block needs that answer."""
    with pytest.raises(PiecewiseExpansionError, match=match):
        expand_piecewise(schema_of(GATED, **{'piecewise.cost_curve.activity': activity}))


#: ``lp`` bounded the other way: the same curve read as its lower envelope.
LP_CONCAVE = override(
    raw_of(NONCONVEX_YAML),
    **{
        'piecewise.cost_curve.method': 'lp',
        'piecewise.cost_curve.links': [['p', 'bp_x'], ['op_cost', 'bp_y', '<=']],
    },
)
CONVEX = override(raw_of(NONCONVEX_YAML), **{'piecewise.cost_curve.method': 'convex'})


#: Named so the completeness check below can read the answers back off them.
_CURVATURE_CASES = [
    pytest.param(raw_of(NONCONVEX_YAML), None, id='adjacency-takes-any-shape'),
    pytest.param(CONVEX, 'either', id='convex-cuts-corners-off-a-mixed-curve'),
    pytest.param(LP, 'convex', id='lp-bounded-above-states-a-convex-curve'),
    pytest.param(LP_CONCAVE, 'concave', id='lp-bounded-below-states-a-concave-curve'),
]


@pytest.mark.parametrize(('raw', 'expected'), _CURVATURE_CASES)
def test_a_method_names_the_curvature_it_is_exact_for(raw, expected):
    """The consumer holding the breakpoints checks the shape; this says what to check for."""
    answer = next((c.curvature for c in to_program(raw).piecewise['cost_curve'].checks if isinstance(c, Curved)), None)
    assert answer == expected
    assert answer is None or answer in CURVATURES, (
        f'{answer!r} is not one of the curvatures the package publishes, so a consumer '
        f'pinning its table against CURVATURES would never match it'
    )


def test_every_published_curvature_is_one_a_method_can_ask_for():
    """`CURVATURES` is what a consumer pins its own table against, so a name in
    it that nothing returns is a branch they write and never reach."""
    answered = {case.values[1] for case in _CURVATURE_CASES} - {None}
    assert answered == set(CURVATURES), (
        f'the cases above answer {sorted(answered)} but the package publishes '
        f'{sorted(CURVATURES)} — one of the two is out of date'
    )


def test_an_emitted_parameter_says_how_it_is_filled():
    """Who binds a parameter, and from what, is the program's to say rather than a suffix a consumer re-spells.

    An ``lp`` block masked by one of its own values-parameters emits three
    ``bool`` parameters the caller never supplies; each carries the
    derivation that fills it, and every parameter the file declared carries
    none.
    """
    program = lower_program(expand_piecewise(schema_of(LP_MASKED)))

    assert {n: p.derivation for n, p in program.parameters.items() if p.derivation is not None} == {
        'cost_curve_points': MaskOf('cost_curve', 'bp_x'),
        'cost_curve_starts': FirstOf('cost_curve', 'cost_curve_points'),
        'cost_curve_ends': LastOf('cost_curve', 'cost_curve_points'),
    }, 'the mask derived from bp_x and the two edge flags it carries, and nothing else'
    assert {n for n, p in program.parameters.items() if p.derivation is None} == {'bp_x', 'bp_y', 'load'}, (
        "every declared parameter is the caller's to bind"
    )


def test_a_file_supplied_mask_derives_nothing():
    """A ``points:`` naming a parameter the file declared is bound like any other, and the mask check still names it."""
    program = to_program(
        override(LP, **{'parameters.reach': {'dims': ['bp'], 'dtype': 'bool'}, 'piecewise.cost_curve.points': 'reach'})
    )

    assert program.parameters['reach'].derivation is None, 'the file declared it, so the caller binds it'
    assert Contiguous('reach', None) in program.piecewise['cost_curve'].checks, (
        'the mask is still one the data has to make contiguous, with no values parameter behind it'
    )


def test_a_block_is_kept_as_the_checks_a_consumer_binding_it_runs():
    """Every condition a curve puts on its data arrives carrying its own subjects."""
    curve = to_program(LP_MASKED).piecewise['cost_curve']

    assert curve.breakpoints == ('bp_x', 'bp_y'), 'the values parameters, in link order'
    assert set(curve.checks) == {
        Increasing('bp_x', 'bp'),
        Curved('bp_x', 'bp_y', 'bp', 'convex'),
        AtLeastTwo('bp', 'cost_curve_points'),
        Contiguous('cost_curve_points', 'bp_x'),
    }, 'an lp curve with a mask assumes all four, each against the names the file wrote'

    plain = to_program(raw_of(NONCONVEX_YAML)).piecewise['cost_curve']
    assert plain.checks == (), 'adjacency over a whole curve is exact for any shape, and masks nothing'


@pytest.mark.parametrize('kind', get_args(Check), ids=lambda k: k.__name__)
def test_every_check_has_a_sentence(kind):
    curve = to_program(LP_MASKED).piecewise['cost_curve']
    check = next((c for c in curve.checks if isinstance(c, kind)), None)
    assert check is not None, 'the fixture is the block that assumes everything'
    assert check_message('cost_curve', curve, check).startswith("piecewise 'cost_curve':")


#: A curve only some members have: the frame is two dims, and the mask names one of them.
MASKED = override(
    TWO_DIM,
    **{
        'parameters.has_curve': {'dims': ['generator'], 'dtype': 'bool'},
        'piecewise.cost_curve.where': 'has_curve',
    },
)
#: The same mask on the block that states its curve as segment lines, which emits no weights to inherit one.
LP_WHERE = override(
    override(LP, **{'parameters.has_curve': {'dims': ['bp'], 'dtype': 'bool'}}),
    **{'parameters.has_curve.dims': ['snapshot'], 'piecewise.cost_curve.where': 'has_curve'},
)


@pytest.mark.parametrize(
    'emitted',
    [
        pytest.param('cost_curve_link0', id='link0'),
        pytest.param('cost_curve_link1', id='link1'),
        pytest.param('cost_curve_convexity', id='convexity'),
        pytest.param('cost_curve_pick', id='pick'),
    ],
)
def test_a_where_reaches_every_row_the_block_emits(emitted):
    """A link row left unmasked is the bug: the weighted sum is empty off the mask, so the row pins `p == 0`.

    The convexity and pick rows are reductions too, and absence does not
    spread out of one — unmasked they would read `0 == 1` at a member with no
    curve.
    """
    expanded = expand_piecewise(schema_of(MASKED))
    assert expanded.constraints[emitted].where == 'has_curve'


@pytest.mark.parametrize(
    'emitted', [pytest.param('cost_curve_lam', id='lam'), pytest.param('cost_curve_seg', id='seg')]
)
def test_a_where_reaches_the_weights(emitted):
    assert expand_piecewise(schema_of(MASKED)).variables[emitted].where == 'has_curve'


def test_the_adjacency_row_inherits_the_mask_rather_than_restating_it():
    """Its every term is a weight, and absence spreads through arithmetic — which is how `points:` already reaches it."""
    expanded = expand_piecewise(schema_of(MASKED))
    assert expanded.constraints['cost_curve_adjacency'].where is None


def test_a_where_and_a_points_both_reach_the_weights():
    """Two masks, one row: which coordinates have a curve, and how far each curve runs."""
    schema = schema_of(MASKED, **{'piecewise.cost_curve.points': 'bp_x'})
    assert expand_piecewise(schema).variables['cost_curve_lam'].where == '(has_curve) AND (cost_curve_points)'


def test_a_where_joins_both_gate_rows():
    """`activity:` splits the convexity row across the gate's own mask, and the block's where holds over both halves."""
    schema = schema_of(
        MASKED,
        **{
            'variables.u': {'dims': ['snapshot', 'generator'], 'domain': 'binary', 'where': 'committable'},
            'parameters.committable': {'dims': ['generator'], 'dtype': 'bool'},
            'piecewise.cost_curve.activity': 'u',
        },
    )
    expanded = expand_piecewise(schema)
    assert expanded.constraints['cost_curve_convexity'].where == '(has_curve) AND (u)'
    assert expanded.constraints['cost_curve_convexity_ungated'].where == '(has_curve) AND (NOT u)'


def test_a_disjunction_in_a_where_is_grouped_where_it_is_joined():
    """Unparenthesised, `a OR b AND points` binds the AND to `b` alone and the curve is built off its mask."""
    schema = schema_of(
        MASKED,
        **{
            'parameters.also_curved': {'dims': ['generator'], 'dtype': 'bool'},
            'piecewise.cost_curve.where': 'has_curve OR also_curved',
            'piecewise.cost_curve.points': 'bp_x',
        },
    )
    assert expand_piecewise(schema).variables['cost_curve_lam'].where == (
        '(has_curve OR also_curved) AND (cost_curve_points)'
    )


@pytest.mark.parametrize(
    ('patch', 'match'),
    [
        pytest.param({'piecewise.cost_curve.where': 'bp_x > 0'}, 'points:', id='the-breakpoint-dim'),
        pytest.param(
            {
                'dimensions.region': {'dtype': 'str'},
                'parameters.onshore': {'dims': ['region'], 'dtype': 'bool'},
                'piecewise.cost_curve.where': 'onshore',
            },
            'cannot add coordinates',
            id='outside-the-frame',
        ),
        pytest.param({'piecewise.cost_curve.where': 'nowhere'}, 'nowhere', id='naming-nothing'),
    ],
)
def test_a_where_the_block_cannot_read_is_refused(patch, match):
    with pytest.raises(LanguageError, match=match):
        schema_of(MASKED, **patch)


def test_segment_lines_carry_the_mask_that_no_weight_can_hand_them():
    """`method: lp` emits no weights, so its three rows take the block's where themselves or stand everywhere."""
    expanded = expand_piecewise(schema_of(LP_WHERE))
    assert expanded.constraints['cost_curve_chord'].where == '(has_curve) AND (position(bp) != 0)'
    assert expanded.constraints['cost_curve_domain_lo'].where == '(has_curve) AND (position(bp) == 0)'
    assert expanded.constraints['cost_curve_domain_hi'].where == '(has_curve) AND (position(bp) == -1)'


def test_the_declaration_carries_the_mask_the_data_guards_are_read_under():
    """Without it every guard runs at a member with no curve, and refuses the breakpoints it has no rows for."""
    curve = to_program(MASKED).piecewise['cost_curve']
    assert curve.where is not None, 'a masked block states which coordinates its checks are asked at'
    assert curve.where.names_read == frozenset({'has_curve'})

    assert to_program(raw_of(NONCONVEX_YAML)).piecewise['cost_curve'].where is None, 'no where, no mask'


#: fluxopt's converter: one curve per generator, tying however many flows the
#: relation gives it. The link that carries `flow` sits on a refinement of the
#: curve's frame, which is why the frame has to be declared rather than inferred.
REFINED = {
    'dimensions': {
        'snapshot': {'dtype': 'int'},
        'generator': {'dtype': 'str'},
        'flow': {'dtype': 'str'},
        'bp': {'dtype': 'int'},
    },
    'relations': {'generator_of': {'key': 'flow', 'values': 'generator'}},
    'parameters': {
        'load': {'dims': ['snapshot']},
        'bp_power': {'dims': ['flow', 'bp']},
        'bp_fuel': {'dims': ['generator', 'bp']},
    },
    'variables': {
        'power': {'dims': ['flow', 'snapshot'], 'bounds': {'lower': 0}},
        'fuel': {'dims': ['generator', 'snapshot'], 'bounds': {'lower': 0}},
    },
    'piecewise': {
        'coupling': {
            'along': 'bp',
            'dims': ['generator', 'snapshot'],
            'links': [
                {
                    'expression': 'power',
                    'values': 'bp_power',
                    'by': 'generator_of',
                    'over': 'generator',
                    'into': 'flow',
                },
                ['fuel', 'bp_fuel'],
            ],
        }
    },
    'constraints': {'balance': {'dims': ['snapshot'], 'expression': 'sum(power, over=flow) == load'}},
    'objective': {'sense': 'minimize', 'expression': 'sum(fuel)'},
}


def test_a_declared_frame_builds_one_curve_per_coordinate_of_it():
    """The curve is per generator, though one of its links is per flow — which the inferred frame could not say."""
    expanded = expand_piecewise(schema_of(REFINED))
    assert expanded.variables['coupling_lam'].dims == ['generator', 'snapshot', 'bp']
    assert expanded.constraints['coupling_convexity'].dims == ['generator', 'snapshot']


def test_a_refined_link_emits_one_row_per_fine_coordinate():
    """The link reads the curve's weights through the relation, so a generator's flows share one curve."""
    link = expand_piecewise(schema_of(REFINED)).constraints['coupling_link0']
    assert link.dims == ['flow', 'snapshot'], 'the frame with the consumed dim replaced by the produced one'
    assert link.expression == (
        '(power) == sum(at(coupling_lam, by=generator_of, over=generator, into=flow) * bp_power, over=bp)'
    )


def test_an_unrefined_link_beside_a_refined_one_stays_on_the_curve_frame():
    link = expand_piecewise(schema_of(REFINED)).constraints['coupling_link1']
    assert link.dims == ['generator', 'snapshot']
    assert link.expression == '(fuel) == sum(coupling_lam * bp_fuel, over=bp)'


def test_a_refined_links_values_follow_its_own_frame():
    """`bp_power` is per flow, which the curve's frame does not carry — the link's frame is what it is read against."""
    assert 'coupling_link0' in expand_piecewise(schema_of(REFINED)).constraints


def test_the_checks_still_name_the_values_parameters_a_refined_block_ties():
    curve = to_program(REFINED).piecewise['coupling']
    assert curve.breakpoints == ('bp_power', 'bp_fuel'), 'the values parameters, in link order'


def test_a_refined_block_round_trips_through_yaml():
    """A link the file wrote as a mapping cannot serialise back as a two-item list."""
    schema = schema_of(REFINED)
    assert to_spec(raw_of(schema.to_yaml())).piecewise['coupling'] == schema.piecewise['coupling']


@pytest.mark.parametrize(
    ('patch', 'match'),
    [
        pytest.param({'piecewise.coupling.dims': None}, 'dims:', id='refined-link-without-a-declared-frame'),
        pytest.param(
            {'piecewise.coupling.links': [{'expression': 'power', 'values': 'bp_power', 'by': 'generator_of'}]},
            'into',
            id='a-walk-that-does-not-name-both-ends',
        ),
        pytest.param(
            {'piecewise.coupling.dims': ['generator', 'snapshot', 'bp']},
            'breakpoint dim',
            id='a-frame-carrying-the-breakpoint-dim',
        ),
        pytest.param(
            {'piecewise.coupling.dims': ['generator']},
            r"link 0 expression carries \['snapshot'\], which its row's frame \['flow'\] does not",
            id='a-frame-a-link-expression-leaves',
        ),
        pytest.param(
            {
                'piecewise.coupling.links': [
                    {
                        'expression': 'power',
                        'values': 'bp_power',
                        'by': 'nowhere_of',
                        'over': 'generator',
                        'into': 'flow',
                    },
                    ['fuel', 'bp_fuel'],
                ]
            },
            'nowhere_of',
            id='a-walk-through-an-undeclared-relation',
        ),
    ],
)
def test_a_refined_block_the_language_cannot_read_is_refused(patch, match):
    """Each refusal names what the file wrote.

    Without the link-frame check the stray-dim case is still refused, by
    `Constraint 'coupling_link0'` — a constraint the author never wrote, which
    is the message the upfront checks exist to replace.
    """
    with pytest.raises(LanguageError, match=match):
        schema_of(REFINED, **patch)


def test_a_block_mask_that_cannot_reach_a_refined_link_is_refused():
    """The mask is on the curve's frame and the row is on a refinement, so the row would pin its expression to zero.

    Left to the emitted declarations the refusal is a dimension error about
    `coupling_link0`; emitted without the mask it is the silent `rate == 0`
    that `where:` exists to prevent.
    """
    with pytest.raises(LanguageError, match="Mask the link's own variable"):
        schema_of(
            REFINED,
            **{
                'parameters.curved': {'dims': ['generator'], 'dtype': 'bool'},
                'piecewise.coupling.where': 'curved',
            },
        )


def test_the_rewrite_that_refusal_names_leaves_the_refined_row_unbuilt():
    """A mask on the link's own variable takes its row with it, which is what absence through arithmetic does."""
    expanded = expand_piecewise(
        schema_of(
            REFINED,
            **{
                'parameters.on_a_curve': {'dims': ['flow'], 'dtype': 'bool'},
                'variables.power.where': 'on_a_curve',
            },
        )
    )
    assert expanded.variables['power'].where == 'on_a_curve'


def test_one_refined_link_is_a_curve_because_the_relation_gives_it_its_arity():
    """A converter whose coupled quantities are all flows of one variable is one link, and it ties them all.

    Two links is what a curve needs when a link is one row. A refined link is
    one row per fine coordinate, so the relation supplies the arity that the
    second link otherwise would.
    """
    expanded = expand_piecewise(
        schema_of(
            REFINED,
            **{
                'piecewise.coupling.links': [
                    {
                        'expression': 'power',
                        'values': 'bp_power',
                        'by': 'generator_of',
                        'over': 'generator',
                        'into': 'flow',
                    }
                ],
                'objective.expression': 'sum(power)',
            },
        )
    )
    assert expanded.constraints['coupling_convexity'].dims == ['generator', 'snapshot'], 'one curve per generator'
    assert expanded.constraints['coupling_link0'].dims == ['flow', 'snapshot'], 'one row per flow, sharing it'
    assert 'coupling_link1' not in expanded.constraints


def test_one_unrefined_link_is_still_a_bound_rather_than_a_curve():
    with pytest.raises(LanguageError, match='a bound rather than a curve'):
        schema_of(NONCONVEX_YAML, **{'piecewise.cost_curve.links': [['p', 'bp_x']]})


def test_points_naming_a_refined_links_values_is_refused():
    """`bp_power` is per flow and the weights are per generator, so the derived mask cannot reach them.

    Left to the emitted declarations the refusal names `coupling_lam`, a
    variable the file never wrote.
    """
    with pytest.raises(LanguageError, match='Raggedness is a property of the curve'):
        schema_of(REFINED, **{'piecewise.coupling.points': 'bp_power'})


def test_points_still_nominates_an_unrefined_links_values():
    """The curve's own frame is where raggedness lives, and an unrefined link's values sit on it."""
    expanded = expand_piecewise(schema_of(REFINED, **{'piecewise.coupling.points': 'bp_fuel'}))
    assert expanded.parameters['coupling_points'].dims == ['generator', 'bp']
    assert expanded.variables['coupling_lam'].where == 'coupling_points'


@pytest.mark.parametrize('method', [pytest.param('convex', id='convex'), pytest.param('lp', id='lp')])
def test_the_two_methods_that_name_an_abscissa_refuse_a_refined_link(method):
    """Both state the curve as one quantity against another, so each needs a link that plays the x-axis.

    `lp` writes a segment line and `convex` a hull between two values
    parameters. Under a refinement the rows are one quantity at many fine
    coordinates, so which of them is the abscissa is data rather than
    declaration.
    """
    with pytest.raises(LanguageError, match='which row plays it is data'):
        schema_of(REFINED, **{'piecewise.coupling.method': method})


@pytest.mark.parametrize('method', [pytest.param('convex', id='convex'), pytest.param('lp', id='lp')])
def test_the_same_two_methods_refuse_a_split_link(method):
    """A split refines the row the same way a walk does, and leaves the abscissa just as unnamed."""
    with pytest.raises(LanguageError, match='which row plays it is data'):
        schema_of(SPLIT, **{'piecewise.op.method': method})


def test_links_that_disagree_on_their_dims_are_refused_rather_than_read_as_one_curve_each():
    """Two links at different grains built one curve per fine coordinate, and loaded clean.

    `power` is per flow and `fuel` per generator, so the inferred frame was
    their union and the block built a curve per (snapshot, flow, generator) —
    N unrelated curves each separately pinning the same `fuel`, which is not
    the coupling the file reads as.
    """
    with pytest.raises(LanguageError, match=r'does not carry \[.generator.\]'):
        schema_of(
            REFINED,
            **{
                'piecewise.coupling.dims': None,
                'piecewise.coupling.links': [['power', 'bp_power'], ['fuel', 'bp_fuel']],
            },
        )


@pytest.mark.parametrize(
    ('patch', 'match'),
    [
        pytest.param(
            {'variables.power.dims': ['flow', 'snapshot', 'period']},
            r'carries \[.period.\]',
            id='finer-than-its-row',
        ),
        pytest.param(
            {
                'piecewise.coupling.dims': ['generator', 'snapshot', 'period'],
                'variables.fuel.dims': ['generator', 'snapshot', 'period'],
            },
            r'does not carry \[.period.\]',
            id='coarser-than-its-row',
        ),
    ],
)
def test_a_link_spanning_a_dimension_its_row_does_not_is_refused_both_ways(patch, match):
    """A curve and the quantity on it vary together or the file says which — neither direction is guessed."""
    model = override(
        REFINED,
        **{
            'dimensions.period': {'dtype': 'int'},
            'parameters.load': {'dims': ['snapshot', 'period']},
            'constraints.balance': {'dims': ['snapshot', 'period'], 'expression': 'sum(power, over=flow) == load'},
        },
    )
    with pytest.raises(LanguageError, match=match):
        schema_of(model, **patch)


def test_a_period_the_curve_and_its_links_both_carry_loads():
    """The rewrite both refusals name: put the dimension in dims:, and the curve varies along it."""
    expanded = expand_piecewise(
        schema_of(
            REFINED,
            **{
                'dimensions.period': {'dtype': 'int'},
                'parameters.load': {'dims': ['snapshot', 'period']},
                'constraints.balance': {
                    'dims': ['snapshot', 'period'],
                    'expression': 'sum(power, over=flow) == load',
                },
                'variables.power.dims': ['flow', 'snapshot', 'period'],
                'variables.fuel.dims': ['generator', 'snapshot', 'period'],
                'piecewise.coupling.dims': ['generator', 'snapshot', 'period'],
            },
        )
    )
    assert expanded.variables['coupling_lam'].dims == ['generator', 'snapshot', 'period', 'bp']
    assert expanded.constraints['coupling_link0'].dims == ['flow', 'snapshot', 'period']


#: A converter whose ties are indexed by a dimension of its own rather than by a
#: relation: every carrier of a converter is a tie to the one operating point.
SPLIT = {
    'dimensions': {
        'snapshot': {'dtype': 'int'},
        'converter': {'dtype': 'str'},
        'carrier': {'dtype': 'str'},
        'bp': {'dtype': 'int'},
    },
    'parameters': {
        'demand': {'dims': ['carrier', 'snapshot']},
        'bp_rate': {'dims': ['converter', 'carrier', 'bp']},
    },
    'variables': {'rate': {'dims': ['converter', 'carrier', 'snapshot']}},
    'piecewise': {
        'op': {
            'along': 'bp',
            'dims': ['converter', 'snapshot'],
            'links': [{'expression': 'rate', 'values': 'bp_rate', 'into': 'carrier'}],
        }
    },
    'constraints': {'balance': {'dims': ['carrier', 'snapshot'], 'expression': 'sum(rate, over=converter) == demand'}},
    'objective': {'sense': 'minimize', 'expression': 'sum(rate)'},
}


def test_a_link_split_along_a_dimension_reads_the_curve_once_per_coordinate_of_it():
    """`into:` with no `by:` gains a dimension and consumes none, so the weights broadcast across it."""
    expanded = expand_piecewise(schema_of(SPLIT))
    assert expanded.variables['op_lam'].dims == ['converter', 'snapshot', 'bp'], 'one curve per converter'
    assert expanded.constraints['op_convexity'].dims == ['converter', 'snapshot']
    link = expanded.constraints['op_link0']
    assert link.dims == ['converter', 'snapshot', 'carrier'], 'the frame, plus the dimension the link spans'
    assert link.expression == '(rate) == sum(op_lam * bp_rate, over=bp)', 'no walk — the weights broadcast'


def test_a_split_link_is_a_curve_on_its_own():
    """Its rows share one set of weights, which is the coupling a second link would otherwise supply."""
    assert 'op_link1' not in expand_piecewise(schema_of(SPLIT)).constraints


def test_a_block_mask_reaches_a_split_link():
    """Unlike a relation walk, a split keeps every dimension the frame has, so the mask still tests them."""
    expanded = expand_piecewise(
        schema_of(
            SPLIT,
            **{
                'parameters.has_curve': {'dims': ['converter'], 'dtype': 'bool'},
                'piecewise.op.where': 'has_curve',
            },
        )
    )
    assert expanded.constraints['op_link0'].where == 'has_curve'


@pytest.mark.parametrize(
    ('patch', 'match'),
    [
        pytest.param(
            {'piecewise.op.links': [{'expression': 'rate', 'values': 'bp_rate', 'over': 'carrier'}]},
            'into',
            id='over-without-a-relation',
        ),
        pytest.param({'piecewise.op.dims': None}, 'dims:', id='a-split-without-a-declared-frame'),
        pytest.param(
            {'piecewise.op.links': [{'expression': 'rate', 'values': 'bp_rate', 'into': 'bp'}]},
            'breakpoint dim',
            id='splitting-along-the-breakpoint-dim',
        ),
        pytest.param(
            {'piecewise.op.links': [{'expression': 'rate', 'values': 'bp_rate', 'into': 'converter'}]},
            'already carries',
            id='splitting-along-a-dim-the-frame-has',
        ),
    ],
)
def test_a_split_the_language_cannot_read_is_refused(patch, match):
    with pytest.raises(LanguageError, match=match):
        schema_of(SPLIT, **patch)


def test_a_split_link_and_a_walked_one_live_in_one_block():
    """The two forms are one law — a row gains `into` and loses `over` — so a block may use both."""
    model = override(
        SPLIT,
        **{
            'dimensions.flow': {'dtype': 'str'},
            'relations.converter_of': {'key': 'flow', 'values': 'converter'},
            'parameters.bp_power': {'dims': ['flow', 'bp']},
            'variables.power': {'dims': ['flow', 'snapshot']},
            'piecewise.op.links': [
                {'expression': 'rate', 'values': 'bp_rate', 'into': 'carrier'},
                {
                    'expression': 'power',
                    'values': 'bp_power',
                    'by': 'converter_of',
                    'over': 'converter',
                    'into': 'flow',
                },
            ],
        },
    )
    expanded = expand_piecewise(schema_of(model))
    assert expanded.constraints['op_link0'].dims == ['converter', 'snapshot', 'carrier'], 'gains carrier'
    assert expanded.constraints['op_link1'].dims == ['flow', 'snapshot'], 'loses converter, gains flow'


#: Three quantities on one curve, two of them bounded rather than pinned.
THREE_WAY = override(
    NONCONVEX_YAML if isinstance(NONCONVEX_YAML, dict) else raw_of(NONCONVEX_YAML),
    **{
        'parameters.bp_z': {'dims': ['bp']},
        'variables.heat': {'dims': ['snapshot'], 'bounds': {'lower': 0}},
    },
)


@pytest.mark.parametrize(
    'links',
    [
        pytest.param([['p', 'bp_x'], ['op_cost', 'bp_y', '>='], ['heat', 'bp_z']], id='three-links-one-bounded'),
        pytest.param(
            [['p', 'bp_x'], ['op_cost', 'bp_y', '>='], ['heat', 'bp_z', '<=']],
            id='two-bounded-signs-at-once',
        ),
        pytest.param([['p', 'bp_x'], ['op_cost', 'bp_y', '>=']], id='the-two-link-case-that-always-worked'),
    ],
)
def test_a_curve_bounds_as_many_links_as_it_likes_while_one_pins_it(links):
    """Under adjacency each link is its own row against the shared weights, so a sign is per link.

    The old rule capped a block at one non-`==` sign and only with exactly two
    links. Nothing in the emission needed that: `_weights` writes
    `(expr) sign sum(lam * values, along=bp)` per link and reaches for no other.
    """
    expanded = expand_piecewise(schema_of(THREE_WAY, **{'piecewise.cost_curve.links': links}))
    emitted = [expanded.constraints[f'cost_curve_link{i}'].expression for i in range(len(links))]
    for link, expression in zip(links, emitted, strict=True):
        sign = link[2] if len(link) == 3 else '=='
        assert f') {sign} sum(' in expression, f'link on {link[0]} carries its own {sign}'


def test_a_single_refined_link_still_needs_pinning():
    """A refinement supplies the arity, not the pin — its rows all bound and none fixes the operating point."""
    with pytest.raises(LanguageError, match='nothing pins the operating point'):
        schema_of(
            REFINED,
            **{
                'piecewise.coupling.links': [
                    {
                        'expression': 'power',
                        'values': 'bp_power',
                        'by': 'generator_of',
                        'over': 'generator',
                        'into': 'flow',
                        'sign': '<=',
                    }
                ],
                'objective.expression': 'sum(power)',
            },
        )


@pytest.mark.parametrize('method', [pytest.param('convex', id='convex'), pytest.param('lp', id='lp')])
def test_the_two_methods_that_name_an_abscissa_take_exactly_two_links(method):
    """`lp` had no such rule and leaned on the sign cap for it, so three links raised `ValueError`."""
    with pytest.raises(LanguageError, match='requires exactly two links'):
        schema_of(
            THREE_WAY,
            **{
                'piecewise.cost_curve.method': method,
                'piecewise.cost_curve.links': [['p', 'bp_x'], ['op_cost', 'bp_y', '>='], ['heat', 'bp_z']],
            },
        )
