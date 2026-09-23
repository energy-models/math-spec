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

from math_spec import CURVATURES
from math_spec.errors import LanguageError, SchemaError
from math_spec.lowering import to_program
from math_spec.piecewise import expand_piecewise
from math_spec.program import Assumption, assumption_message
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
    over: bp
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


def test_an_emitted_set_may_not_collide_with_a_declared_one():
    """The emitted-name rule, for the one declaration kind that is new."""
    with pytest.raises(SchemaError, match="writes sos 'cost_curve', which this file already declares"):
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


def test_a_program_holds_the_rows_a_curve_states_and_not_the_curve():
    """A curve states rows and a program holds them, so lowering a model writes every block out.

    Writing a set out stays the caller's: a set is one thing to a consumer
    that takes it and another to one that does not.
    """
    schema = schema_of(NONCONVEX_YAML)
    program = to_program(schema)
    assert program is to_program(schema.expand('piecewise')), 'the program of a model is the program of its rows'
    assert {'cost_curve_lam', 'p', 'op_cost'} <= set(program.variables), 'the weights the block states'
    assert 'cost_curve_link0' in program.constraints and not hasattr(program, 'piecewise'), (
        'the rows are declarations like any other, and nothing records the block they came from'
    )
    assert to_program(schema.expand()).sos == {} and program.sos == {}, (
        'an adjacency block writes its own set out; a caller writes the rest out with expand()'
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
            'needs exactly one link bounded by the curve',
            id='lp-with-three-links-none-bounded',
        ),
        pytest.param(
            LP,
            {'piecewise.cost_curve.activity': 'running'},
            'activity is not supported with method: lp',
            id='lp-with-an-activity-and-nothing-to-gate',
        ),
        pytest.param(
            NONCONVEX_YAML,
            {'parameters.bp_x.dtype': 'bool'},
            "link 0 values parameter 'bp_x' is declared dtype: bool, and a breakpoint is a number",
            id='values-that-are-not-numbers',
        ),
        pytest.param(
            LP,
            {'piecewise.cost_curve.links': [['load', 'bp_x'], ['op_cost', 'bp_y', '>=']]},
            "link 0: method: lp bounds the curve's domain by rows comparing this link's expression",
            id='lp-with-an-x-link-carrying-no-variable',
        ),
        pytest.param(
            NONCONVEX_YAML,
            {'parameters.bp_x.dims': []},
            "link 0 values parameter 'bp_x' must carry dim 'bp'",
            id='a-breakpoint-parameter-without-the-breakpoint-dim',
        ),
        pytest.param(
            NONCONVEX_YAML,
            {'piecewise.cost_curve.points': 'nope'},
            "points references undeclared parameter 'nope'",
            id='undeclared-points',
        ),
        pytest.param(
            NONCONVEX_YAML,
            {'parameters.reach': {'dims': [], 'dtype': 'bool'}, 'piecewise.cost_curve.points': 'reach'},
            "points parameter 'reach' must carry dim 'bp'",
            id='points-without-the-breakpoint-dim',
        ),
        pytest.param(
            NONCONVEX_YAML,
            {'piecewise.cost_curve.links': [['p + bp_x', 'bp_x'], ['op_cost', 'bp_y']]},
            "link 0 expression already carries the breakpoint dim 'bp'",
            id='a-link-carrying-the-breakpoint-dim',
        ),
        pytest.param(
            NONCONVEX_YAML,
            {'variables.u': {'dims': ['snapshot', 'bp'], 'domain': 'binary'}, 'piecewise.cost_curve.activity': 'u'},
            "activity already carries the breakpoint dim 'bp'",
            id='a-gate-carrying-the-breakpoint-dim',
        ),
        pytest.param(
            NONCONVEX_YAML,
            {'dimensions.generator': {'dtype': 'str'}, 'parameters.bp_x.dims': ['generator', 'bp']},
            r"values parameter 'bp_x' carries \['generator'\], which no link expression does",
            id='a-breakpoint-varying-along-a-dim-no-link-carries',
        ),
        pytest.param(
            NONCONVEX_YAML,
            {
                'dimensions.generator': {'dtype': 'str'},
                'parameters.reach': {'dims': ['generator', 'bp'], 'dtype': 'bool'},
                'piecewise.cost_curve.points': 'reach',
            },
            r"points parameter 'reach' carries \['generator'\], which the links do not",
            id='a-mask-adding-a-coordinate-the-curve-does-not-have',
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
    with pytest.raises(SchemaError, match=message) as exc:
        schema_of(NONCONVEX_YAML, **{'piecewise.cost_curve.links': [[link_expression, 'bp_x'], ['op_cost', 'bp_y']]})
    assert "piecewise 'cost_curve' link 0" in str(exc.value)


@pytest.mark.parametrize(
    ('model', 'patch'),
    [
        pytest.param(NONCONVEX_YAML, {'parameters.bp_x.dtype': 'str'}, id='a-label-as-a-breakpoint'),
        pytest.param(
            LP,
            {'piecewise.cost_curve.links': [['load', 'bp_x'], ['op_cost', 'bp_y', '>=']]},
            id='a-variable-free-x-link',
        ),
    ],
)
def test_a_block_is_refused_on_the_link_the_file_wrote_and_not_on_a_row_it_would_emit(model, patch):
    """Both were refused only once written out, under `cost_curve_increasing` or `cost_curve_domain_lo` — rows the file never declared."""
    with pytest.raises(SchemaError) as exc:
        schema_of(model, **patch)
    assert "piecewise 'cost_curve'" in str(exc.value) and 'link 0' in str(exc.value)
    assert 'cost_curve_' not in str(exc.value), 'the refusal names the block, not a declaration the expansion writes'


def test_an_undeclared_breakpoint_dimension_is_refused_once():
    """`over: nope` also said, per link, that the values parameter must carry `nope` — lines that follow from the first."""
    with pytest.raises(SchemaError) as exc:
        schema_of(NONCONVEX_YAML, **{'piecewise.cost_curve.over': 'nope'})
    assert str(exc.value).splitlines() == [
        "piecewise 'cost_curve' references undeclared dimension 'nope'. Declare it under 'dimensions:'."
    ]


def test_a_link_reading_a_refused_entry_names_it_and_its_refusal_is_listed():
    """A link through a failing entry said `Its refusal is listed with it`, and nothing listed the refusal."""
    with pytest.raises(SchemaError) as exc:
        schema_of(
            NONCONVEX_YAML,
            **{'expressions': {'bad': 'nope'}, 'piecewise.cost_curve.links': [['bad', 'bp_x'], ['op_cost', 'bp_y']]},
        )
    message = str(exc.value)
    assert "Named expression 'bad': 'nope' not found" in message
    assert (
        "piecewise 'cost_curve' link 0: named expression 'bad' does not load. Its refusal is listed with it." in message
    )


def test_a_link_reading_a_nonlinear_entry_is_refused():
    """A named entry, nonlinear and so legal on its own, is refused where the link reads it.

    `ratio` loads — nothing bans it at declaration — but a
    piecewise link is affine, so reading it there hits the same divisor ban a
    constraint would. The refusal lives at the reading position, not the
    declaration: the entry-declaration relocation for the other math positions
    is `TestValidateExpressions.test_a_nonlinear_entry_is_refused_where_the_math_reads_it`.
    """
    with pytest.raises(SchemaError, match='the divisor contains variables') as exc:
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
    with pytest.raises(SchemaError, match='which is degree 2') as exc:
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
    with pytest.raises(SchemaError, match='a dual exists only after a solve'):
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
    with pytest.raises(SchemaError, match=match):
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
    program = to_program(schema_of(LP_MASKED))
    rows = {name: program.constraints[f'cost_curve_{name}'].where for name in ('chord', 'domain_lo', 'domain_hi')}

    assert set(program.parameters) == {'bp_x', 'bp_y', 'load'}, 'every parameter is one the file declared'
    assert {name: row.names_read for name, row in rows.items() if row is not None} == {
        'chord': frozenset({'bp_x'}),
        'domain_lo': frozenset({'bp_x'}),
        'domain_hi': frozenset({'bp_x'}),
    }, 'every masked row reads the mask the file named, and nothing the expansion invented'


def test_a_file_supplied_mask_is_what_the_contiguity_condition_reads():
    """A ``points:`` naming a parameter the file declared is bound like any other, and the mask check names it."""
    program = to_program(
        expanded(
            override(
                LP, **{'parameters.reach': {'dims': ['bp'], 'dtype': 'bool'}, 'piecewise.cost_curve.points': 'reach'}
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
            'piecewise.cost_curve.points': 'bp_x',
            'piecewise.cost_curve.links': links,
        },
    )

    assert reason in to_program(spec.expand()).assumptions['cost_curve_contiguous'].description


def test_a_block_assumes_of_its_data_what_the_method_implies():
    """Every condition a curve puts on its data stands with the file's own, carrying its own subjects."""
    program = to_program(expanded(LP_MASKED, 'piecewise'))

    assert list(program.assumptions) == [
        'cost_curve_complete',
        'cost_curve_increasing',
        'cost_curve_curvature',
        'cost_curve_breakpoints',
        'cost_curve_contiguous',
    ], 'an lp curve with a mask assumes all five, each named after the block that implies it'
    assert all(isinstance(a, Assumption) for a in program.assumptions.values()), (
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
    with pytest.raises(
        SchemaError, match="writes assumption 'cost_curve_increasing', which this file already declares"
    ):
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
