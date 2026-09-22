# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""`piecewise:` expansion, judged at the door that decides it.

Every claim here is one `to_spec` or `Spec.expand` reaches with no data bound:
which declarations a curve emits, which names it may not collide with, which
methods exist, and which gates a block will accept.
"""

from __future__ import annotations

import pytest

from math_spec import CURVATURES, to_spec
from math_spec.errors import LanguageError, PiecewiseExpansionError, SchemaError
from math_spec.lowering import lower_program, to_program
from math_spec.piecewise import expand_piecewise
from math_spec.program import Holds, assumption_message
from tests.fixtures import DISPATCH_MODEL, expanded, override, raw_of, schema_of

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
LP_MASKED = override(LP, **{'piecewise.cost_curve.where': 'bp_x'})
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


def test_an_emitted_set_may_not_collide_with_a_declared_one():
    """The emitted-name rule, for the one declaration kind that is new."""
    with pytest.raises(PiecewiseExpansionError, match="emitted sos 'cost_curve' collides"):
        schema_of(NONCONVEX_YAML, sos={'cost_curve': {'variable': 'p', 'along': 'snapshot', 'type': 1}})


@pytest.mark.parametrize('method', [pytest.param('incremental', id='unknown'), pytest.param(['sos2'], id='a list')])
def test_a_method_this_project_does_not_have_is_refused(method):
    """A list used to escape the membership test as a `TypeError`."""
    with pytest.raises(SchemaError, match='unknown piecewise method'):
        schema_of(NONCONVEX_YAML, **{'piecewise.cost_curve.method': method})


def test_the_file_keeps_its_curve_and_the_expansion_has_none():
    """The file is what it says; the expansion is the rows it stands for."""
    schema = schema_of(NONCONVEX_YAML)

    assert 'cost_curve' in schema.piecewise, 'loading a model does not spend its blocks'
    assert not schema.expand('piecewise').piecewise, 'the block is spent once its declarations are emitted'


def test_lowering_refuses_a_model_that_still_owes_rows_to_a_curve():
    """A curve states rows and a program holds them, and nothing here writes them out on the caller's behalf.

    Which formulations to write out is the caller's to say: a set is one thing
    to a consumer that takes it and another to one that does not, so the
    refusal names both spellings.
    """
    with pytest.raises(LanguageError, match="piecewise: 'cost_curve' states rows") as refusal:
        to_program(schema_of(NONCONVEX_YAML))
    assert "expand('piecewise')" in str(refusal.value) and 'expand()' in str(refusal.value), (
        'the refusal names both ways out, because they differ in what a set becomes'
    )


def test_expansion_is_memoised_and_idempotent():
    """One object per set of formulations asked for, and a model with none to expand is its own expansion."""
    schema = schema_of(NONCONVEX_YAML)
    expanded = schema.expand('piecewise')
    assert schema.expand('piecewise') is expanded
    assert expanded.expand('piecewise') is expanded

    curveless = schema_of(DISPATCH_MODEL)
    assert curveless.expand() is curveless, 'a model with no formulation is the one that comes back'


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
    assert to_program(schema.expand('piecewise')).expressions['twice'].in_math is True


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
#: Both links pinned, so nothing says which way the weights are pushed.
CONVEX = override(raw_of(NONCONVEX_YAML), **{'piecewise.cost_curve.method': 'convex'})
#: The hull bounded below, which is the same relaxation ``lp`` states as its segment lines.
CONVEX_BOUNDED = override(CONVEX, **{'piecewise.cost_curve.links': [['p', 'bp_x'], ['op_cost', 'bp_y', '>=']]})
#: The hull bounded above, so the binding side is the upper one.
CONVEX_BOUNDED_BELOW = override(CONVEX, **{'piecewise.cost_curve.links': [['p', 'bp_x'], ['op_cost', 'bp_y', '<=']]})


#: Named so the completeness check below can read the answers back off them.
_CURVATURE_CASES = [
    pytest.param(raw_of(NONCONVEX_YAML), None, id='adjacency-takes-any-shape'),
    pytest.param(CONVEX, 'either', id='convex-pinned-both-ways-states-a-single-bend'),
    pytest.param(CONVEX_BOUNDED, 'convex', id='convex-bounded-above-states-a-convex-curve'),
    pytest.param(CONVEX_BOUNDED_BELOW, 'concave', id='convex-bounded-below-states-a-concave-curve'),
    pytest.param(LP, 'convex', id='lp-bounded-above-states-a-convex-curve'),
    pytest.param(LP_CONCAVE, 'concave', id='lp-bounded-below-states-a-concave-curve'),
]


@pytest.mark.parametrize(('raw', 'expected'), _CURVATURE_CASES)
def test_a_method_names_the_curvature_it_is_exact_for(raw, expected):
    """The consumer holding the breakpoints checks the shape; this says what to check for."""
    stated = [
        a.description for n, a in to_program(expanded(raw, 'piecewise')).assumptions.items() if n.endswith('_curvature')
    ]
    answer = next((c for c in CURVATURES if stated and f'a {c} curve' in stated[0]), 'either' if stated else None)
    assert answer == expected, 'the curvature the method is exact for is the shape its sentence names'
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


def test_a_masked_lp_curve_sits_its_rows_on_predicates_rather_than_on_parameters():
    """An ``lp`` block masked by one of its own values parameters emitted three ``bool``
    parameters — the mask, and the first and last breakpoint of each curve — that the
    caller never supplied and a derivation in private state filled. The ``where``
    language writes each of them, so the rows carry the predicate and the program
    declares the file's parameters and no other."""
    program = lower_program(expand_piecewise(schema_of(LP_MASKED)))
    rows = {name: program.constraints[f'cost_curve_{name}'].where for name in ('chord', 'domain_lo', 'domain_hi')}

    assert set(program.parameters) == {'bp_x', 'bp_y', 'load'}, 'every parameter is one the file declared'
    assert {name: row.names_read for name, row in rows.items() if row is not None} == {
        'chord': frozenset({'bp_x'}),
        'domain_lo': frozenset({'bp_x'}),
        'domain_hi': frozenset({'bp_x'}),
    }, 'every masked row reads the mask the file named, and nothing the expansion invented'


def test_a_file_supplied_mask_is_what_the_contiguity_condition_reads():
    """A ``where:`` naming a parameter the file declared is bound like any other, and the mask check names it."""
    program = to_program(
        expanded(
            override(
                LP, **{'parameters.reach': {'dims': ['bp'], 'dtype': 'bool'}, 'piecewise.cost_curve.where': 'reach'}
            ),
            'piecewise',
        )
    )

    contiguous = program.assumptions['cost_curve_contiguous']
    assert contiguous.predicate.names_read == frozenset({'reach'}), (
        "the mask is still one the data has to make contiguous, and the condition reads the file's own name"
    )


@pytest.mark.parametrize(
    ('method', 'reason'),
    [
        pytest.param('adjacency', 'nonzero only on two neighbouring breakpoints', id='adjacency'),
        pytest.param('sos2', 'nonzero only on two neighbouring breakpoints', id='sos2'),
        pytest.param('convex', 'a bend across a gap goes unchecked', id='convex'),
        pytest.param('lp', 'the chord row joins a breakpoint to the one before it', id='lp'),
    ],
)
def test_a_gap_is_explained_by_the_rows_the_method_writes(method, reason):
    """Every method gave the ``lp`` reason, naming a chord row and domain rows that only ``lp`` writes."""
    links = (
        [['p', 'bp_x'], ['op_cost', 'bp_y', '>=']]
        if method in {'convex', 'lp'}
        else [['p', 'bp_x'], ['op_cost', 'bp_y']]
    )
    spec = schema_of(
        NONCONVEX_YAML,
        **{
            'piecewise.cost_curve.method': method,
            'piecewise.cost_curve.where': 'bp_x',
            'piecewise.cost_curve.links': links,
        },
    )

    assert reason in to_program(spec.expand()).assumptions['cost_curve_contiguous'].description


def test_a_block_assumes_of_its_data_what_the_method_implies():
    """Every condition a curve puts on its data stands with the file's own, carrying its own subjects."""
    program = to_program(expanded(LP_MASKED, 'piecewise'))

    assert program.piecewise['cost_curve'].breakpoints == ('bp_x', 'bp_y'), 'the values parameters, in link order'
    assert list(program.assumptions) == [
        'cost_curve_complete',
        'cost_curve_increasing',
        'cost_curve_curvature',
        'cost_curve_breakpoints',
        'cost_curve_contiguous',
    ], 'an lp curve with a mask assumes all five, each named after the block that implies it'
    assert all(isinstance(a, Holds) for a in program.assumptions.values()), (
        'a method states its conditions in the same language the file does, so a consumer has one kind to read'
    )
    assert program.assumptions['cost_curve_increasing'].predicate.names_read == frozenset({'bp_x'}), (
        'the x-axis is what increases, and the condition reads it and nothing else'
    )

    plain = to_program(expanded(NONCONVEX_YAML, 'piecewise'))
    assert list(plain.assumptions) == ['cost_curve_complete'], (
        'adjacency is exact for a curve of any shape, so it states nothing about the shape — but every '
        'curve states that its breakpoints are there, whatever the method'
    )


def test_a_curves_conditions_cannot_collide_with_a_written_assumption():
    """A condition a method states is a name the block emits, and a file writing it is the collision every emitted name is."""
    with pytest.raises(LanguageError, match="emitted assumption 'cost_curve_increasing' collides"):
        expanded(override(LP, assumptions={'cost_curve_increasing': 'bp_x > 0'}), 'piecewise')


@pytest.mark.parametrize('suffix', ['increasing', 'curvature', 'breakpoints', 'contiguous'])
def test_every_check_has_a_sentence(suffix):
    assumptions = to_program(expanded(LP_MASKED, 'piecewise')).assumptions
    name = f'cost_curve_{suffix}'
    assert name in assumptions, 'the fixture is the block that assumes everything'
    message = assumption_message(name, assumptions[name])
    assert message.startswith(f"assumption '{name}' does not hold for the data bound to "), (
        'the refusal names the columns a consumer has to look at before it says why'
    )
    assert "— piecewise 'cost_curve':" in message, 'and trails the sentence the method implies'


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
    ],
)
def test_a_where_reaches_every_row_the_block_emits(emitted):
    """A link row left unmasked is the bug: the weighted sum is empty off the mask, so the row pins `p == 0`.

    The convexity row is a reduction too, and absence does not spread out of
    one — unmasked it would read `0 == 1` at a member with no curve.
    """
    expanded = expand_piecewise(schema_of(MASKED))
    assert expanded.constraints[emitted].where == 'has_curve'


def test_the_row_the_set_states_needs_no_mask_of_its_own():
    """`adjacency` states its restriction as a set, and the set's row is an inequality.

    Unmasked it reads `0 <= 1` at a member with no curve, which every row is
    free to say. The rows that would read `0 == 1` there are the block's own,
    and those carry the mask.
    """
    expanded = expand_piecewise(schema_of(MASKED))
    assert expanded.constraints['cost_curve_pick'].expression == 'sum(cost_curve_seg, over=bp) <= 1'
    assert expanded.constraints['cost_curve_pick'].where is None, 'the inequality holds off the mask on its own'


@pytest.mark.parametrize(
    'emitted', [pytest.param('cost_curve_lam', id='lam'), pytest.param('cost_curve_seg', id='seg')]
)
def test_a_where_reaches_the_weights(emitted):
    assert expand_piecewise(schema_of(MASKED)).variables[emitted].where == 'has_curve'


def test_the_adjacency_row_inherits_the_mask_rather_than_restating_it():
    """Its every term is a weight, and absence spreads through arithmetic — which is how `points:` already reaches it."""
    expanded = expand_piecewise(schema_of(MASKED))
    assert expanded.constraints['cost_curve_adjacency'].where is None


def test_a_ragged_where_reaches_the_weights_as_written_and_the_frame_rows_as_a_count():
    """One mask says which coordinates have a curve and how far each runs; a row over the frame alone cannot read it."""
    expanded = expand_piecewise(schema_of(MASKED, **{'piecewise.cost_curve.where': 'has_curve AND bp_x'}))

    assert expanded.variables['cost_curve_lam'].where == 'has_curve AND bp_x'
    assert expanded.constraints['cost_curve_convexity'].where == 'count(has_curve AND bp_x, over=bp) > 0'
    assert expanded.constraints['cost_curve_link0'].where == 'count(has_curve AND bp_x, over=bp) > 0'


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


def test_a_ragged_where_is_grouped_where_an_edge_row_shifts_it():
    """Unparenthesised, `a OR b AND shift(…)` binds the AND to `b` alone and the edge is read off half the mask."""
    schema = schema_of(
        MASKED,
        **{
            'parameters.also_curved': {'dims': ['generator'], 'dtype': 'bool'},
            'piecewise.cost_curve.where': 'has_curve OR also_curved AND bp_x',
            'piecewise.cost_curve.method': 'lp',
            'piecewise.cost_curve.links': [['p', 'bp_x'], ['op_cost', 'bp_y', '>=']],
        },
    )
    expanded = expand_piecewise(schema)

    assert expanded.constraints['cost_curve_domain_lo'].where == (
        '(has_curve OR also_curved AND bp_x) AND NOT shift(has_curve OR also_curved AND bp_x, along=bp, offset=1)'
    )


@pytest.mark.parametrize(
    ('patch', 'match'),
    [
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
    assert expanded.constraints['cost_curve_chord'].where == '(has_curve) AND (position(bp) > 0)'
    assert expanded.constraints['cost_curve_domain_lo'].where == '(has_curve) AND (position(bp) == 0)'
    assert expanded.constraints['cost_curve_domain_hi'].where == '(has_curve) AND (position(bp) == -1)'


def test_the_declaration_carries_the_mask_the_data_guards_are_read_under():
    """Without it every guard runs at a member with no curve, and refuses the breakpoints it has no rows for."""
    curve = to_program(expanded(MASKED, 'piecewise')).piecewise['cost_curve']
    assert curve.where is not None, 'a masked block states which coordinates its checks are asked at'
    assert curve.where.names_read == frozenset({'has_curve'})

    assert to_program(expanded(NONCONVEX_YAML, 'piecewise')).piecewise['cost_curve'].where is None, 'no where, no mask'


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
    curve = to_program(expanded(REFINED, 'piecewise')).piecewise['coupling']
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


def test_a_where_naming_a_refined_links_values_is_refused():
    """`bp_rate` is per carrier and the weights are per converter, so a mask reading it cannot reach them.

    Left to the emitted declarations the refusal names `op_lam`, a variable
    the file never wrote.
    """
    with pytest.raises(LanguageError, match='cannot add coordinates'):
        schema_of(SPLIT, **{'piecewise.op.where': 'bp_rate'})


def test_a_split_block_is_ragged_on_the_curves_own_frame():
    """Raggedness is the curve's, so a split link's row reads it as the count of breakpoints its curve has."""
    expanded = expand_piecewise(
        schema_of(
            SPLIT, **{'parameters.reach': {'dims': ['converter', 'bp'], 'dtype': 'bool'}, 'piecewise.op.where': 'reach'}
        )
    )

    assert expanded.variables['op_lam'].where == 'reach', 'the weights run as far as the mask says'
    assert expanded.constraints['op_link0'].where == 'count(reach, over=bp) > 0', (
        'the split row is over the frame and carrier, which cannot read a mask along the breakpoints'
    )


#: Why `convex` and `lp` refuse a refinement. The two reasons are not one, so
#: neither message may stand in for the other.
REFINEMENT_REASON = (
    pytest.param('convex', 'no shape left to check', id='convex'),
    pytest.param('lp', 'which row plays it is data', id='lp'),
)


@pytest.mark.parametrize(('method', 'match'), REFINEMENT_REASON)
def test_the_two_restricted_methods_refuse_a_walked_link_for_their_own_reasons(method, match):
    """`lp` loses the abscissa its line is written against; `convex` loses the pair it reads a shape from."""
    with pytest.raises(LanguageError, match=match):
        schema_of(REFINED, **{'piecewise.coupling.method': method})


@pytest.mark.parametrize(('method', 'match'), REFINEMENT_REASON)
def test_the_two_restricted_methods_refuse_a_split_link_too(method, match):
    """A split refines the row the same way a walk does, and costs each method the same thing."""
    with pytest.raises(LanguageError, match=match):
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


@pytest.mark.parametrize(
    ('method', 'match'),
    [
        pytest.param('convex', 'would ship uncertified', id='convex'),
        pytest.param('lp', 'no line to write', id='lp'),
    ],
)
def test_the_two_restricted_methods_take_exactly_two_links_for_their_own_reasons(method, match):
    """`lp` had no such rule and leaned on the sign cap for it, so three links raised `ValueError`.

    `convex` builds the same rows for any number of links; what it cannot do
    past two is certify that relaxing onto the hull is exact, because the sign
    on the bounded link is what names the direction to check.
    """
    with pytest.raises(LanguageError, match=match):
        schema_of(
            THREE_WAY,
            **{
                'piecewise.cost_curve.method': method,
                'piecewise.cost_curve.links': [['p', 'bp_x'], ['op_cost', 'bp_y', '>='], ['heat', 'bp_z']],
            },
        )
