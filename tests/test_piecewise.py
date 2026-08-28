# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""`piecewise:` expansion, judged at the door that decides it.

Every claim here is one `to_spec` or `expand_piecewise` reaches with no data
bound: which declarations a curve emits, which names it may not collide with,
which methods exist, and which gates a block will accept.
"""

from __future__ import annotations

import pytest

from math_spec import CURVATURES, curvature_required
from math_spec.errors import LanguageError, PiecewiseExpansionError, SchemaError
from math_spec.model import _ExpandedSpec
from math_spec.piecewise import expand_piecewise
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
    foreach: [snapshot]
    bounds: {lower: 0, upper: 100}
  op_cost:
    foreach: [snapshot]
    bounds: {lower: 0}

piecewise:
  cost_curve:
    over: bp
    links:
      - [p, bp_x]
      - [op_cost, bp_y]

constraints:
  balance:
    foreach: [snapshot]
    expression: p == load

objective:
  sense: minimize
  expression: sum(op_cost, over=snapshot)
"""
GATED = override(
    raw_of(NONCONVEX_YAML),
    **{'variables.u': {'foreach': ['snapshot'], 'domain': 'binary'}, 'piecewise.cost_curve.activity': 'u'},
)
#: The convex curve stated as its segment lines, plus a binary the method cannot gate on.
LP = override(
    raw_of(NONCONVEX_YAML),
    **{
        'piecewise.cost_curve.method': 'lp',
        'piecewise.cost_curve.links': [['p', 'bp_x'], ['op_cost', 'bp_y', '>=']],
        'variables.running': {'foreach': ['snapshot'], 'domain': 'binary'},
    },
)
#: Two dims in the frame, so the emitted ``foreach`` has an order to get wrong.
TWO_DIM = override(
    raw_of(NONCONVEX_YAML),
    **{
        'dimensions.generator': {'dtype': 'str'},
        'parameters.bp_x.dims': ['generator', 'bp'],
        'parameters.bp_y.dims': ['generator', 'bp'],
        'variables.p.foreach': ['snapshot', 'generator'],
        'variables.op_cost.foreach': ['snapshot', 'generator'],
        'constraints.balance.expression': 'sum(p, over=generator) == load',
        'objective.expression': 'sum(op_cost)',
    },
)


def test_expansion_emits_the_lambda_declarations():
    expanded = expand_piecewise(schema_of(NONCONVEX_YAML))

    assert not expanded.piecewise
    assert 'cost_curve_lam' in expanded.variables
    assert expanded.variables['cost_curve_seg'].domain == 'binary'
    assert set(expanded.constraints) >= {
        'cost_curve_convexity',
        'cost_curve_pick',
        'cost_curve_adjacency',
        'cost_curve_link0',
        'cost_curve_link1',
        'balance',
    }


def test_an_emitted_set_may_not_collide_with_a_declared_one():
    """The emitted-name rule, for the one declaration kind that is new."""
    with pytest.raises(PiecewiseExpansionError, match="emitted sos 'cost_curve' collides"):
        schema_of(NONCONVEX_YAML, sos={'cost_curve': {'variable': 'p', 'over': 'snapshot', 'type': 1}})


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


def test_a_curve_stated_as_lines_expands_to_an_expanded_spec():
    assert isinstance(expand_piecewise(schema_of(LP)), _ExpandedSpec)


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


@pytest.mark.parametrize('order', [['snapshot', 'generator', 'bp'], ['generator', 'snapshot', 'bp']])
def test_the_emitted_foreach_follows_declaration_order(order):
    """The frame is a set until something orders it, and a set iterates the
    same way for the same names within one process — so a run that reads the
    set rather than the declaration fails one of the two orderings."""
    schema = schema_of(TWO_DIM, dimensions={d: TWO_DIM['dimensions'][d] for d in order})
    assert expand_piecewise(schema).variables['cost_curve_lam'].foreach == order


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
            'at most one link',
            id='at-most-one-link',
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
            {'variables.u': {'foreach': ['snapshot'], 'bounds': {'lower': 0, 'upper': 1}}},
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
            'needs exactly one link bounded by the curve',
            id='lp-with-three-links-none-bounded',
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
        ('p ** 2', 'over variables'),
        ('p * p', 'both factors of a product contain variables'),
    ],
)
def test_a_link_outside_the_language_is_named_where_the_user_wrote_it(link_expression, message):
    """Lowering would catch these too, but naming ``cost_curve_link0`` — a declaration the user never wrote."""
    with pytest.raises(PiecewiseExpansionError, match=message) as exc:
        schema_of(NONCONVEX_YAML, **{'piecewise.cost_curve.links': [[link_expression, 'bp_x'], ['op_cost', 'bp_y']]})
    assert "piecewise 'cost_curve' link 0" in str(exc.value)


@pytest.mark.parametrize(
    ('activity', 'match'),
    [
        pytest.param('at(u_unit, by=unit_of)', 'is not a declared variable', id='a-pullback-through-a-lookup'),
        pytest.param('shift(u, over=snapshot, offset=1)', 'is not a declared variable', id='a-shifted-gate'),
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
    """The consumer holding the breakpoints checks the shape; this says what to
    check for. It is the block's own semantics, so it is answered here rather
    than re-derived by every repository that binds data to a curve."""
    answer = curvature_required(schema_of(raw).piecewise['cost_curve'])
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
