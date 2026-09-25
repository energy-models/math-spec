# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""`piecewise:` expansion, judged at the door that decides it.

Every claim here is one `to_spec` or `Spec.expand` reaches with no data attached:
which declarations a curve emits, which names it may not collide with, which
methods exist, and which gates a block will accept.
"""

from __future__ import annotations

from typing import get_args

import pytest

from math_spec.errors import LanguageError, SchemaError
from math_spec.model import Curvature
from math_spec.piecewise import Emitted, assumptions_of, expand_piecewise
from math_spec.program import Assumption, Variable, assumption_message
from math_spec.validation import to_spec
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
    dims: [snapshot]
    links:
      p: [p, bp_x]
      op_cost: [op_cost, bp_y]

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
        'piecewise.cost_curve.links': {'p': ['p', 'bp_x'], 'op_cost': ['op_cost', 'bp_y', '>=']},
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
        'piecewise.cost_curve.dims': ['snapshot', 'generator'],
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


@pytest.mark.parametrize(
    ('patch', 'written', 'declared'),
    [
        pytest.param({'dimensions.cost_curve_lam': {'dtype': 'int'}}, 'cost_curve_lam', 'dimensions', id='a-dimension'),
        pytest.param({'parameters.cost_curve_lam': {'dims': ['bp']}}, 'cost_curve_lam', 'parameters', id='a-parameter'),
        pytest.param(
            {'expressions.cost_curve_lam': {'expression': 'p'}}, 'cost_curve_lam', 'expressions', id='an-entry'
        ),
        pytest.param(
            {'macros.cost_curve_lam': {'args': ['x'], 'template': 'x + x'}}, 'cost_curve_lam', 'macros', id='a-macro'
        ),
        pytest.param(
            {
                'sos.pick': {'variable': 'p', 'along': 'snapshot', 'type': 1},
                'parameters.pick_seg': {'dims': ['snapshot']},
            },
            'pick_seg',
            'parameters',
            id='a-set-writes-a-variable-too',
        ),
    ],
)
def test_an_emitted_variable_may_not_take_any_name_the_file_declares(patch, written, declared):
    """An emitted variable joins the one flat namespace. The rule checked it
    against variables alone, and the eager expansion caught the rest; once a
    model loaded with its curves intact, the clash loaded and waited for the
    first `expand`."""
    with pytest.raises(
        SchemaError, match=f"writes variable '{written}', which this file already declares under '{declared}:'"
    ):
        schema_of(NONCONVEX_YAML, **patch)


def test_a_written_name_is_refused_once_the_rest_of_the_file_lowers():
    """The rule reads the curve as lowered, so it waits for every other fault, as a dim rule does."""
    clash = {'parameters.cost_curve_lam': {'dims': ['bp']}}
    with pytest.raises(SchemaError) as first:
        schema_of(NONCONVEX_YAML, **clash, **{'constraints.balance.expression': 'p == nope'})
    assert 'nope' in str(first.value)
    assert 'writes variable' not in str(first.value), 'the clash is not listed beside a fault that stops lowering'
    with pytest.raises(SchemaError, match="writes variable 'cost_curve_lam'"):
        schema_of(NONCONVEX_YAML, **clash)


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


def test_a_program_mirrors_the_model_it_was_lowered_from():
    """A model still declaring a curve lowers to a program carrying the curve, and its expansion to one carrying the rows.

    Writing a formulation out is the caller's: a curve is one thing to a
    consumer printing it and another to one building rows, as a set is.
    """
    schema = schema_of(NONCONVEX_YAML)
    program, rows = schema.program, schema.expand('piecewise').program

    curve = program.piecewise['cost_curve']
    assert [link.values for link in curve.links] == ['bp_x', 'bp_y'] and curve.frame == ('snapshot',), (
        'the curve as the file states it, with its links typed and its frame decided'
    )
    assert curve.links[0].expression == Variable('p'), 'a link is the tree the file wrote'
    assert 'cost_curve_lam' not in program.variables, 'the rows are on the expansion'
    assert not rows.piecewise and {'cost_curve_lam', 'p', 'op_cost'} <= set(rows.variables), (
        'the expansion carries the rows and no curve'
    )
    assert schema.expand().program.sos == {} and rows.sos == {}, (
        'an adjacency block writes its own set out; a caller writes the rest out with expand()'
    )


def test_expansion_is_idempotent():
    """One model per set of formulations asked for, and a model with none to expand is its own expansion."""
    schema = schema_of(NONCONVEX_YAML)
    expanded = schema.expand('piecewise')
    assert schema.expand('piecewise') == expanded
    assert expanded.expand('piecewise') is expanded

    curveless = schema_of(DISPATCH_MODEL)
    assert curveless.expand() is curveless, 'a model with no formulation is the one that comes back'


@pytest.mark.parametrize(
    'dims',
    [
        pytest.param(['snapshot', 'generator'], id='snapshot-first'),
        pytest.param(['generator', 'snapshot'], id='generator-first'),
    ],
)
def test_the_emitted_foreach_follows_the_dims_the_block_writes(dims):
    """The weights are over ``dims:`` as written, then the breakpoint dim, whatever order the dimensions are declared in."""
    schema = schema_of(TWO_DIM, **{'piecewise.cost_curve.dims': dims})
    assert expand_piecewise(schema).variables['cost_curve_lam'].dims == [*dims, 'bp']


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
        **{'piecewise.cost_curve.links': {'x': [link, 'bp_x'], 'op_cost': ['op_cost', 'bp_y']}},
    )
    assert expand_piecewise(schema).constraints['cost_curve_x'].expression.startswith(f'({link}) ==')


@pytest.mark.parametrize(
    ('model', 'patch', 'match'),
    [
        pytest.param(
            NONCONVEX_YAML,
            {'piecewise.cost_curve.links': {'p': ['p', 'bp_x', '<='], 'op_cost': ['op_cost', 'bp_y', '>=']}},
            'nothing pins the operating point',
            id='every-link-bounded',
        ),
        pytest.param(
            NONCONVEX_YAML,
            {'piecewise.cost_curve.links': {'p': ['p', 'bp_x']}},
            'at least two links',
            id='a-single-link',
        ),
        pytest.param(
            NONCONVEX_YAML,
            {'piecewise.cost_curve.links': {'p': ['p', 'bp_x'], 'op_cost': ['op_cost', 'bp_y', '>=', 'extra']}},
            r'each link must be \[expression, values\] or \[expression, values, sign\]',
            id='a-link-of-four-elements',
        ),
        pytest.param(
            NONCONVEX_YAML,
            {
                'piecewise.cost_curve.method': 'convex',
                'piecewise.cost_curve.links': {'p': ['p', 'bp_x'], 'op_cost': ['op_cost', 'bp_y'], 'p2': ['p', 'bp_x']},
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
            {'piecewise.cost_curve.links': {'p': ['p', 'bp_x'], 'op_cost': ['op_cost', 'nope']}},
            "undeclared parameter 'nope'",
            id='undeclared-parameter',
        ),
        pytest.param(
            LP,
            {'piecewise.cost_curve.links': {'p': ['p', 'bp_x'], 'op_cost': ['op_cost', 'bp_y']}},
            'needs exactly one link bounded by the curve',
            id='lp-with-both-links-pinned',
        ),
        pytest.param(
            LP,
            {'piecewise.cost_curve.links': {'p': ['p', 'bp_x'], 'op_cost': ['op_cost', 'bp_y'], 'p2': ['p', 'bp_x']}},
            'requires exactly two links',
            id='lp-with-three-links',
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
            "link 'p': values parameter 'bp_x' is declared dtype: bool, and a breakpoint is a number",
            id='values-that-are-not-numbers',
        ),
        pytest.param(
            LP,
            {'piecewise.cost_curve.links': {'x': ['load', 'bp_x'], 'op_cost': ['op_cost', 'bp_y', '>=']}},
            "link 'x': method: lp bounds the curve's domain by rows comparing this link's expression",
            id='lp-with-an-x-link-carrying-no-variable',
        ),
        pytest.param(
            NONCONVEX_YAML,
            {'parameters.bp_x.dims': []},
            "link 'p': values parameter 'bp_x' must carry dim 'bp'",
            id='a-breakpoint-parameter-without-the-breakpoint-dim',
        ),
        pytest.param(
            NONCONVEX_YAML,
            {'piecewise.cost_curve.where': 'nope'},
            "piecewise 'cost_curve' where: 'nope' not found",
            id='an-undeclared-name-in-the-where',
        ),
        pytest.param(
            NONCONVEX_YAML,
            {'piecewise.cost_curve.links': {'p': ['p + bp_x', 'bp_x'], 'op_cost': ['op_cost', 'bp_y']}},
            "link 'p' expression already carries the breakpoint dim 'bp'",
            id='a-link-carrying-the-breakpoint-dim',
        ),
        pytest.param(
            NONCONVEX_YAML,
            {'variables.u': {'dims': ['snapshot', 'bp'], 'domain': 'binary'}, 'piecewise.cost_curve.activity': 'u'},
            r"activity 'u' carries \['bp'\], which dims \['snapshot'\] does not",
            id='a-gate-carrying-a-dim-the-block-does-not',
        ),
        pytest.param(
            NONCONVEX_YAML,
            {'dimensions.generator': {'dtype': 'str'}, 'parameters.bp_x.dims': ['generator', 'bp']},
            r"link 'p' values parameter 'bp_x' carries \['generator'\], which its row",
            id='a-breakpoint-varying-along-a-dim-no-link-carries',
        ),
        pytest.param(
            NONCONVEX_YAML,
            {
                'dimensions.generator': {'dtype': 'str'},
                'parameters.reach': {'dims': ['generator', 'bp'], 'dtype': 'bool'},
                'piecewise.cost_curve.where': 'reach',
            },
            r"where 'reach' tests \['generator'\], which dims \['snapshot'\] does not carry",
            id='a-where-adding-a-coordinate-the-curve-does-not-have',
        ),
    ],
)
def test_a_malformed_block_is_refused(model, patch, match):
    """Schema-level arity rules and the expansion's own preconditions, before any data is attached.

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
    """Lowering would catch these too, but naming ``cost_curve_x`` — a declaration the user never wrote."""
    with pytest.raises(SchemaError, match=message) as exc:
        schema_of(
            NONCONVEX_YAML,
            **{'piecewise.cost_curve.links': {'x': [link_expression, 'bp_x'], 'op_cost': ['op_cost', 'bp_y']}},
        )
    assert "piecewise 'cost_curve' link 'x'" in str(exc.value)


@pytest.mark.parametrize(
    ('model', 'patch'),
    [
        pytest.param(NONCONVEX_YAML, {'parameters.bp_x.dtype': 'str'}, id='a-label-as-a-breakpoint'),
        pytest.param(
            LP,
            {'piecewise.cost_curve.links': {'x': ['load', 'bp_x'], 'op_cost': ['op_cost', 'bp_y', '>=']}},
            id='a-variable-free-x-link',
        ),
    ],
)
def test_a_block_is_refused_on_the_link_the_file_wrote_and_not_on_a_row_it_would_emit(model, patch):
    """Both were refused only once written out, under `cost_curve_increasing` or `cost_curve_domain_lo` — rows the file never declared."""
    with pytest.raises(SchemaError) as exc:
        schema_of(model, **patch)
    assert "piecewise 'cost_curve' link '" in str(exc.value)
    assert 'cost_curve_' not in str(exc.value), 'the refusal names the block, not a declaration the expansion writes'


def test_an_undeclared_breakpoint_dimension_is_refused_once():
    """`along: nope` also said, per link, that the values parameter must carry `nope` — lines that follow from the first."""
    with pytest.raises(SchemaError) as exc:
        schema_of(NONCONVEX_YAML, **{'piecewise.cost_curve.along': 'nope'})
    assert str(exc.value).splitlines() == [
        "piecewise 'cost_curve' references undeclared dimension 'nope'. Declare it under 'dimensions:'."
    ]


def test_a_link_reading_a_refused_entry_names_it_and_its_refusal_is_listed():
    """A link through a failing entry said `Its refusal is listed with it`, and nothing listed the refusal."""
    with pytest.raises(SchemaError) as exc:
        schema_of(
            NONCONVEX_YAML,
            **{
                'expressions': {'bad': 'nope'},
                'piecewise.cost_curve.links': {'p': ['bad', 'bp_x'], 'op_cost': ['op_cost', 'bp_y']},
            },
        )
    message = str(exc.value)
    assert "Named expression 'bad': 'nope' not found" in message
    assert (
        "piecewise 'cost_curve' link 'p': named expression 'bad' does not load. Its refusal is listed with it."
        in message
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
                'piecewise.cost_curve.links': {'ratio': ['ratio', 'bp_x'], 'op_cost': ['op_cost', 'bp_y']},
            },
        )
    assert "piecewise 'cost_curve' link 'ratio'" in str(exc.value)


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
                'piecewise.cost_curve.links': {'sq': ['sq', 'bp_x'], 'op_cost': ['op_cost', 'bp_y']},
            },
        )
    assert "piecewise 'cost_curve' link 'sq'" in str(exc.value)


def test_an_entry_a_link_reads_is_in_the_math():
    """A link's expression stands inside the constraints its expansion emits, so an entry it names is one the math reads."""
    schema = schema_of(
        NONCONVEX_YAML,
        **{
            'expressions': {'twice': 'p * 2'},
            'piecewise.cost_curve.links': {'twice': ['twice', 'bp_x'], 'op_cost': ['op_cost', 'bp_y']},
        },
    )
    assert schema.expand('piecewise').program.expressions['twice'].in_math is True


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
                'piecewise.cost_curve.links': {'price': ['price', 'bp_x'], 'op_cost': ['op_cost', 'bp_y']},
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
        'piecewise.cost_curve.links': {'p': ['p', 'bp_x'], 'op_cost': ['op_cost', 'bp_y', '<=']},
    },
)
#: Both links pinned, so nothing says which way the weights are pushed.
CONVEX = override(raw_of(NONCONVEX_YAML), **{'piecewise.cost_curve.method': 'convex'})
#: The hull bounded below, which is the same relaxation ``lp`` states as its segment lines.
CONVEX_BOUNDED = override(
    CONVEX, **{'piecewise.cost_curve.links': {'p': ['p', 'bp_x'], 'op_cost': ['op_cost', 'bp_y', '>=']}}
)
#: The hull bounded above, so the binding side is the upper one.
CONVEX_BOUNDED_BELOW = override(
    CONVEX, **{'piecewise.cost_curve.links': {'p': ['p', 'bp_x'], 'op_cost': ['op_cost', 'bp_y', '<=']}}
)


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
        a.description for n, a in expanded(raw, 'piecewise').program.assumptions.items() if n.endswith('_curvature')
    ]
    curvatures = get_args(Curvature)
    answer = next((c for c in curvatures if stated and f'a {c} curve' in stated[0]), 'either' if stated else None)
    assert answer == expected, 'the curvature the method is exact for is the shape its sentence names'
    assert answer is None or answer in curvatures, (
        f'{answer!r} is not one of the curvatures the language names, so a consumer '
        f'pinning its table against `Curvature` would never match it'
    )


def test_every_named_curvature_is_one_a_method_can_ask_for():
    """`Curvature` is what a consumer pins its own table against, so a name in
    it that nothing returns is a branch they write and never reach."""
    answered = {case.values[1] for case in _CURVATURE_CASES} - {None}
    assert answered == set(get_args(Curvature)), (
        f'the cases above answer {sorted(answered)} but the language names '
        f'{sorted(get_args(Curvature))} — one of the two is out of date'
    )


def test_a_masked_lp_curve_sits_its_rows_on_predicates_rather_than_on_parameters():
    """An ``lp`` block masked by one of its own values parameters emitted three ``bool``
    parameters — the mask, and the first and last breakpoint of each curve — that the
    caller never supplied and a derivation in private state filled. The ``where``
    language writes each of them, so the rows carry the predicate and the program
    declares the file's parameters and no other."""
    program = schema_of(LP_MASKED).expand('piecewise').program
    rows = {name: program.constraints[f'cost_curve_{name}'].where for name in ('chord', 'domain_lo', 'domain_hi')}

    assert set(program.parameters) == {'bp_x', 'bp_y', 'load'}, 'every parameter is one the file declared'
    assert {name: row.names_read for name, row in rows.items() if row is not None} == {
        'chord': frozenset({'bp_x'}),
        'domain_lo': frozenset({'bp_x'}),
        'domain_hi': frozenset({'bp_x'}),
    }, 'every masked row reads the mask the file named, and nothing the expansion invented'


def test_a_file_supplied_mask_is_what_the_contiguity_condition_reads():
    """A ``where:`` naming a parameter the file declared is bound like any other, and the mask check names it."""
    program = expanded(
        override(LP, **{'parameters.reach': {'dims': ['bp'], 'dtype': 'bool'}, 'piecewise.cost_curve.where': 'reach'}),
        'piecewise',
    ).program

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
        {'p': ['p', 'bp_x'], 'op_cost': ['op_cost', 'bp_y', '>=']}
        if method in {'convex', 'lp'}
        else {'p': ['p', 'bp_x'], 'op_cost': ['op_cost', 'bp_y']}
    )
    spec = schema_of(
        NONCONVEX_YAML,
        **{
            'piecewise.cost_curve.method': method,
            'piecewise.cost_curve.where': 'bp_x',
            'piecewise.cost_curve.links': links,
        },
    )

    assert reason in spec.expand().program.assumptions['cost_curve_contiguous'].description


def test_a_block_assumes_of_its_data_what_the_method_implies():
    """Every condition a curve puts on its data stands with the file's own, carrying its own subjects."""
    program = expanded(LP_MASKED, 'piecewise').program

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

    plain = expanded(NONCONVEX_YAML, 'piecewise').program
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


@pytest.mark.parametrize(
    ('where', 'advice'),
    [
        pytest.param(None, 'declare where: to say how far the curve runs', id='no-where'),
        pytest.param('curved', "let where: 'curved' test 'bp' too", id='a-where-over-dims'),
        pytest.param('curved AND bp_power_on', "narrow where: 'curved AND bp_power_on'", id='a-ragged-where'),
    ],
)
def test_a_missing_breakpoint_names_a_rewrite_the_block_can_take(where, advice):
    """A block with a `where:` over `dims:` was told to declare `where:`, which it already had."""
    model = override(
        WALKED,
        **{
            'parameters.curved': {'dims': ['generator'], 'dtype': 'bool'},
            'parameters.bp_power_on': {'dims': ['generator', 'bp'], 'dtype': 'bool'},
        },
    )
    assumptions = expand_piecewise(schema_of(model, **{'piecewise.coupling.where': where})).assumptions
    for name in ('coupling_complete', 'coupling_power_complete'):
        assert advice in assumptions[name].description, f'{name} names the rewrite for its own where'


@pytest.mark.parametrize('suffix', ['increasing', 'curvature', 'breakpoints', 'contiguous'])
def test_every_check_has_a_sentence(suffix):
    assumptions = expanded(LP_MASKED, 'piecewise').program.assumptions
    name = f'cost_curve_{suffix}'
    assert name in assumptions, 'the fixture is the block that assumes everything'
    message = assumption_message(name, assumptions[name])
    assert message.startswith(f"assumption '{name}' does not hold for the data attached to "), (
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
        pytest.param('cost_curve_p', id='link-p'),
        pytest.param('cost_curve_op_cost', id='link-op_cost'),
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
    """Its every term is a weight, and absence spreads through arithmetic — which is how a ragged `where:` reaches it too."""
    expanded = expand_piecewise(schema_of(MASKED))
    assert expanded.constraints['cost_curve_adjacency'].where is None


def test_a_ragged_where_reaches_the_weights_as_written_and_the_frame_rows_as_a_count():
    """One mask says which coordinates have a curve and how far each runs; a row over the frame alone cannot read it."""
    expanded = expand_piecewise(schema_of(MASKED, **{'piecewise.cost_curve.where': 'has_curve AND bp_x'}))

    assert expanded.variables['cost_curve_lam'].where == 'has_curve AND bp_x'
    assert expanded.constraints['cost_curve_convexity'].where == 'count(has_curve AND bp_x, over=bp) > 0'
    assert expanded.constraints['cost_curve_p'].where == 'count(has_curve AND bp_x, over=bp) > 0'


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
            'piecewise.cost_curve.links': {'p': ['p', 'bp_x'], 'op_cost': ['op_cost', 'bp_y', '>=']},
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


def test_a_where_over_a_dim_a_link_walks_into_is_not_sent_to_dims():
    """The refusal said to add `flow` to `dims:`, and the walk into `flow` was then refused for that very edit."""
    with pytest.raises(LanguageError, match=r"\['flow'\] is what link 'power' walks into") as refused:
        schema_of(
            WALKED,
            **{'parameters.on_flow': {'dims': ['flow'], 'dtype': 'bool'}, 'piecewise.coupling.where': 'on_flow'},
        )
    assert 'to dims:' not in str(refused.value), 'no advice the walk refuses'


def test_segment_lines_carry_the_mask_that_no_weight_can_hand_them():
    """`method: lp` emits no weights, so its three rows take the block's where themselves or stand everywhere."""
    expanded = expand_piecewise(schema_of(LP_WHERE))
    assert expanded.constraints['cost_curve_chord'].where == '(has_curve) AND (position(bp) > 0)'
    assert expanded.constraints['cost_curve_domain_lo'].where == '(has_curve) AND (position(bp) == 0)'
    assert expanded.constraints['cost_curve_domain_hi'].where == '(has_curve) AND (position(bp) == -1)'


@pytest.mark.parametrize(
    ('where', 'method'),
    [
        pytest.param('has_curve', 'lp', id='a-mask-over-the-frame'),
        pytest.param('has_curve AND bp_x', 'lp', id='a-ragged-mask'),
        pytest.param('has_curve', 'convex', id='a-single-bend-over-the-frame'),
    ],
)
def test_a_model_written_out_and_read_back_asks_its_conditions_only_where_a_curve_runs(where, method):
    """The mask lived only on the program's declaration, so the file `to_yaml()` wrote asked every generator.

    Read back, that file held a generator with no curve to breakpoints it has
    no rows for. A ragged mask had the same gap on the conditions over the
    frame alone: a generator the mask admits no breakpoint of failed
    `count(...) == 1`, though it has no curve.
    """
    links = {'p': ['p', 'bp_x'], 'op_cost': ['op_cost', 'bp_y', '>=' if method == 'lp' else '==']}
    model = override(MASKED, **{'piecewise.cost_curve.where': where, 'piecewise.cost_curve.method': method})
    written = schema_of(model, **{'piecewise.cost_curve.links': links}).expand('piecewise')
    read_back = to_spec(raw_of(written.to_yaml())).program

    unmasked = {
        name
        for name, assumption in read_back.assumptions.items()
        if assumption.where is None or 'has_curve' not in assumption.where.names_read
    }
    assert not unmasked, f'{sorted(unmasked)} would be asked at a generator with no curve'


#: fluxopt's converter: one curve per generator, tying however many flows the
#: relation gives it. The link that carries `flow` walks the relation from the
#: curve's `generator` to its own `flow`.
WALKED = {
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
            'links': {
                'power': {
                    'expression': 'power',
                    'values': 'bp_power',
                    'by': 'generator_of',
                    'over': 'generator',
                    'into': 'flow',
                },
                'fuel': ['fuel', 'bp_fuel'],
            },
        }
    },
    'constraints': {'balance': {'dims': ['snapshot'], 'expression': 'sum(power, over=flow) == load'}},
    'objective': {'sense': 'minimize', 'expression': 'sum(fuel)'},
}
#: The walked link alone, which the relation gives its arity.
POWER_ONLY = {
    'piecewise.coupling.links': {
        'power': {
            'expression': 'power',
            'values': 'bp_power',
            'by': 'generator_of',
            'over': 'generator',
            'into': 'flow',
        }
    },
    'objective.expression': 'sum(power)',
}


def test_a_block_builds_one_curve_per_coordinate_of_its_dims():
    """The curve is per generator, though one of its links is per flow."""
    expanded = expand_piecewise(schema_of(WALKED))
    assert expanded.variables['coupling_lam'].dims == ['generator', 'snapshot', 'bp']
    assert expanded.constraints['coupling_convexity'].dims == ['generator', 'snapshot']


def test_a_walked_link_emits_one_row_per_fine_coordinate():
    """The link reads the curve's weights through the relation, so a generator's flows share one curve."""
    link = expand_piecewise(schema_of(WALKED)).constraints['coupling_power']
    assert link.dims == ['flow', 'snapshot'], 'dims: with the consumed dim replaced by the produced one'
    assert link.expression == (
        '(power) == sum(at(coupling_lam, by=generator_of, over=generator, into=flow) * bp_power, over=bp)'
    )


def test_a_link_that_walks_nothing_stays_on_the_blocks_dims():
    link = expand_piecewise(schema_of(WALKED)).constraints['coupling_fuel']
    assert link.dims == ['generator', 'snapshot']
    assert link.expression == '(fuel) == sum(coupling_lam * bp_fuel, over=bp)'


def test_a_link_row_is_named_after_the_link_and_not_after_its_place():
    """Rows named by position renamed every constraint after the one a reordering moved."""
    swapped = override(
        WALKED, **{'piecewise.coupling.links': dict(reversed(WALKED['piecewise']['coupling']['links'].items()))}
    )
    for model in (WALKED, swapped):
        rows = expand_piecewise(schema_of(model)).constraints
        assert rows['coupling_fuel'].expression == '(fuel) == sum(coupling_lam * bp_fuel, over=bp)'


def test_the_checks_still_name_the_values_parameters_a_walked_block_ties():
    curve = schema_of(WALKED).program.piecewise['coupling']
    assert [link.values for link in curve.links] == ['bp_power', 'bp_fuel'], 'the values parameters, in link order'


def test_a_walked_block_round_trips_through_yaml():
    """A link the file wrote as a mapping cannot serialise back as a two-item list."""
    schema = schema_of(WALKED)
    assert to_spec(raw_of(schema.to_yaml())).piecewise['coupling'] == schema.piecewise['coupling']


def _walk(**written: object) -> dict[str, object]:
    """The `power` link with *written* in place of its walk keys, and `None` dropping one."""
    link = {'expression': 'power', 'values': 'bp_power', 'by': 'generator_of', 'over': 'generator', 'into': 'flow'}
    link |= written
    return {'piecewise.coupling.links.power': {k: v for k, v in link.items() if v is not None}}


@pytest.mark.parametrize(
    ('patch', 'match'),
    [
        pytest.param({'piecewise.coupling.dims': None}, 'one curve per coordinate of', id='a-block-without-dims'),
        pytest.param(_walk(over=None, into=None), r"\['over', 'into'\] are missing", id='a-walk-naming-no-columns'),
        pytest.param(_walk(by=None, over=None), r"\['by', 'over'\] are missing", id='into-without-a-relation'),
        pytest.param(_walk(by=None, into=None), r"\['by', 'into'\] are missing", id='over-without-a-relation'),
        pytest.param(
            {'piecewise.coupling.dims': ['generator', 'snapshot', 'bp']},
            'breakpoint dim',
            id='dims-carrying-the-breakpoint-dim',
        ),
        pytest.param(
            {'piecewise.coupling.dims': ['generator']},
            r"link 'power' expression carries \['snapshot'\], which its row \['flow'\] does not",
            id='dims-a-link-expression-leaves',
        ),
        pytest.param(_walk(by='nowhere_of'), 'nowhere_of', id='a-walk-through-an-undeclared-relation'),
        pytest.param(
            {'piecewise.coupling.dims': ['snapshot']},
            r"link 'power': over reaches \['generator'\], which the block's dims \['snapshot'\] do not carry",
            id='a-walk-consuming-a-dim-the-block-lacks',
        ),
        pytest.param(
            {'piecewise.coupling.dims': ['generator', 'flow', 'snapshot']},
            r"link 'power': into reaches \['flow'\], which the block's dims .* already carry",
            id='a-walk-into-a-dim-the-block-has',
        ),
        pytest.param(_walk(into=['flow', 'flow']), r"link 'power': .*names a column twice", id='a-repeated-column'),
        pytest.param(
            {'relations.slot_of': {'key': 'bp', 'values': 'generator'}}
            | _walk(by='slot_of', over='generator', into='bp'),
            r"link 'power': into reaches 'bp', the breakpoint dim",
            id='a-walk-into-the-breakpoint-dim',
        ),
        pytest.param(
            {'piecewise.coupling.links.fuel': ['fuel', 'bp_fuel', '>=']} | _walk(sign='<='),
            'nothing pins the operating point',
            id='every-row-bounded',
        ),
        pytest.param(
            _walk(over=[])
            | {
                'variables.power.dims': ['generator', 'snapshot'],
                'parameters.bp_power.dims': ['generator', 'bp'],
                'constraints.balance.expression': 'sum(power, over=generator) == load',
            },
            r'links.power: over: \[\] names no column',
            id='an-empty-over',
        ),
        pytest.param(
            _walk(into=[])
            | {
                'variables.power.dims': ['snapshot'],
                'parameters.bp_power.dims': ['bp'],
                'constraints.balance.expression': 'power == load',
            },
            r'links.power: into: \[\] names no column',
            id='an-empty-into',
        ),
        pytest.param(
            {
                'piecewise.coupling.dims': ['flow', 'snapshot'],
                'piecewise.coupling.links': {
                    'power': ['power', 'bp_power'],
                    'fuel': {
                        'expression': 'fuel',
                        'values': 'bp_fuel',
                        'by': 'generator_of',
                        'over': 'flow',
                        'into': 'generator',
                    },
                },
            },
            r"link 'fuel': at\(by=generator_of\): into=\['generator'\] names \['generator'\], which the key",
            id='a-walk-landing-off-the-key',
        ),
        pytest.param(
            {
                'dimensions.period': {'dtype': 'int'},
                'relations.generator_of': {'key': ['flow', 'period'], 'values': 'generator'},
            },
            r"link 'power': 'generator_of' is keyed on \['period'\] too, which the block's dims",
            id='a-walk-joining-on-a-dim-the-block-lacks',
        ),
        pytest.param(
            {'relations.generator_of': {'key': {'flow': 'flow', 'site': 'generator'}, 'values': 'generator'}},
            r"link 'power': at\(by=generator_of\) joins 'generator_of' on \['generator'\] through more than one",
            id='a-walk-joining-on-the-dim-it-consumes',
        ),
    ],
)
def test_a_walked_block_the_language_cannot_read_is_refused(patch, match):
    """Each refusal names the link the file wrote, not a constraint its expansion would write."""
    with pytest.raises(LanguageError, match=match):
        schema_of(WALKED, **patch)


def test_a_link_that_only_gains_a_dimension_is_refused_and_names_the_walk():
    """A row finer than the curve is reached through a relation, which says which curve each fine row reads."""
    model = override(
        WALKED,
        **{
            'dimensions.carrier': {'dtype': 'str'},
            'parameters.bp_rate': {'dims': ['generator', 'carrier', 'bp']},
            'variables.rate': {'dims': ['generator', 'carrier', 'snapshot']},
            'piecewise.coupling.links.rate': {'expression': 'rate', 'values': 'bp_rate', 'into': 'carrier'},
        },
    )
    with pytest.raises(LanguageError, match=r"\['by', 'over'\] are missing"):
        schema_of(model)


@pytest.mark.parametrize(
    ('link', 'match'),
    [
        pytest.param('convexity', "link 'convexity' names its row 'coupling_convexity'", id='the-convexity-row'),
        pytest.param('lam', "link 'lam' names its row 'coupling_lam'", id='the-weights'),
        pytest.param('adjacency_below', "link 'adjacency_below'", id='a-row-the-set-writes'),
    ],
)
def test_a_link_named_after_a_row_the_block_writes_is_refused(link, match):
    with pytest.raises(LanguageError, match=match):
        schema_of(WALKED, **{f'piecewise.coupling.links.{link}': ['fuel', 'bp_fuel']})


#: A second curve whose name extends the first's, so a link of the first can spell one of its rows.
BESIDE = override(
    WALKED,
    **{
        'piecewise.coupling_b': {
            'along': 'bp',
            'dims': ['generator', 'snapshot'],
            'links': {'fuel': ['fuel', 'bp_fuel'], 'power': WALKED['piecewise']['coupling']['links']['power']},
        }
    },
)


@pytest.mark.parametrize(
    ('key', 'link', 'match'),
    [
        pytest.param(
            'b_fuel',
            ['fuel', 'bp_fuel'],
            "writes constraint 'coupling_b_fuel', which piecewise 'coupling' also writes",
            id='a-link-row',
        ),
        pytest.param(
            'b_convexity',
            ['fuel', 'bp_fuel'],
            "writes constraint 'coupling_b_convexity', which piecewise 'coupling' also writes",
            id='a-row-the-other-block-writes-for-itself',
        ),
        pytest.param(
            'b',
            WALKED['piecewise']['coupling']['links']['power'],
            "writes assumption 'coupling_b_complete', which piecewise 'coupling' also writes",
            id='a-walked-links-own-condition',
        ),
    ],
)
def test_a_name_two_blocks_would_both_write_is_refused(key, link, match):
    """Links take any name, so `coupling`'s link `b_fuel` spelled `coupling_b`'s row `coupling_b_fuel`.

    Both blocks loaded, and the expansion wrote one row over the other, so
    one block's link was never stated.
    """
    with pytest.raises(LanguageError, match=match):
        schema_of(BESIDE, **{f'piecewise.coupling.links.{key}': link})


def test_a_link_name_no_row_could_take_is_refused():
    with pytest.raises(LanguageError, match=r"links: \['2nd'\] is not a name"):
        schema_of(WALKED, **{'piecewise.coupling.links.2nd': ['fuel', 'bp_fuel']})


def test_a_gate_over_more_than_the_blocks_dims_is_refused():
    """The gate widened a declared `dims:` silently, and built the weights over a dimension the file never gave the curve."""
    with pytest.raises(
        LanguageError, match=r"activity 'u' carries \['generator'\], which dims \['snapshot'\] does not"
    ):
        schema_of(
            TWO_DIM,
            **{
                'piecewise.cost_curve.dims': ['snapshot'],
                'piecewise.cost_curve.links': {'p': ['load', 'bp_z'], 'op_cost': ['load * 2', 'bp_z']},
                'parameters.bp_z': {'dims': ['bp']},
                'variables.u': {'dims': ['snapshot', 'generator'], 'domain': 'binary'},
                'piecewise.cost_curve.activity': 'u',
            },
        )


def test_a_gate_over_fewer_dims_than_the_block_switches_each_curve_it_covers():
    """A unit commitment per generator gates that generator's curve in every snapshot."""
    expanded = expand_piecewise(
        schema_of(
            TWO_DIM,
            **{'variables.u': {'dims': ['generator'], 'domain': 'binary'}, 'piecewise.cost_curve.activity': 'u'},
        )
    )
    assert expanded.constraints['cost_curve_convexity'].expression == 'sum(cost_curve_lam, over=bp) == (u)'
    assert expanded.variables['cost_curve_lam'].dims == ['snapshot', 'generator', 'bp']


#: fluxopt's system: only some generators run on a curve, and the rest have none at all.
CURVED = override(
    WALKED,
    **{
        'parameters.curved': {'dims': ['generator'], 'dtype': 'bool'},
        'piecewise.coupling.where': 'curved',
    },
)


def test_a_block_mask_reaches_a_walked_link_through_its_relation():
    """The row is over flows and the mask over generators, so the row reads the mask at each flow's generator.

    The block refused a mask beside a walk, so a model with one curved
    generator built a curve, a convexity row and its binaries for every
    generator it declared.
    """
    expanded = expand_piecewise(schema_of(CURVED))
    assert expanded.variables['coupling_lam'].where == 'curved', 'no weights where a generator has no curve'
    assert expanded.constraints['coupling_convexity'].where == 'curved'
    assert expanded.constraints['coupling_fuel'].where == 'curved', 'a link on dims: reads the mask as written'
    assert expanded.constraints['coupling_power'].where == ('at(curved, by=generator_of, over=generator, into=flow)'), (
        'a walked link reads it at the generator each flow maps to'
    )


def test_a_ragged_mask_reaches_a_walked_link_as_the_count_of_its_curves_breakpoints():
    """A walked row is over the curve's dims less the walk, so it takes what a row over dims: alone takes, read through."""
    expanded = expand_piecewise(
        schema_of(
            WALKED,
            **{
                'parameters.reach': {'dims': ['generator', 'bp'], 'dtype': 'bool'},
                'piecewise.coupling.where': 'reach',
            },
        )
    )
    assert expanded.variables['coupling_lam'].where == 'reach'
    assert expanded.constraints['coupling_power'].where == (
        'at(count(reach, over=bp) > 0, by=generator_of, over=generator, into=flow)'
    )


def test_a_mask_over_dims_the_walk_keeps_reaches_the_walked_row_as_written():
    """A mask over `snapshot` alone says nothing about generators, and the walked row keeps `snapshot`."""
    expanded = expand_piecewise(
        schema_of(
            WALKED,
            **{
                'parameters.season': {'dims': ['snapshot'], 'dtype': 'bool'},
                'piecewise.coupling.where': 'season',
            },
        )
    )
    assert expanded.constraints['coupling_power'].where == 'season'


def test_a_mask_over_a_dim_the_walk_joins_on_reaches_the_walked_row_as_written():
    """The relation is keyed by flow and snapshot, and `season` tests only `snapshot`, which the walked row keeps.

    The join column was counted with the ones the walk consumes, so this mask
    was refused as carrying part of what the walk reads through, and no
    rewrite kept it.
    """
    expanded = expand_piecewise(
        schema_of(
            WALKED,
            **{
                'relations.generator_of': {'key': ['flow', 'snapshot'], 'values': 'generator'},
                'parameters.season': {'dims': ['snapshot'], 'dtype': 'bool'},
                'piecewise.coupling.where': 'season',
            },
        )
    )
    assert expanded.constraints['coupling_power'].where == 'season'


def test_a_mask_carrying_part_of_what_a_walk_reads_through_is_refused():
    """The relation is keyed by flow and snapshot, so the read joins on snapshot and needs the mask to carry it too."""
    model = override(
        CURVED,
        **{
            'relations.generator_of': {'key': ['flow', 'snapshot'], 'values': 'generator'},
        },
    )
    with pytest.raises(LanguageError, match=r"where 'curved' carries \['generator'\] and not \['snapshot'\]"):
        schema_of(model)


@pytest.mark.parametrize(
    ('model', 'read'),
    [
        pytest.param(WALKED, {'generator_of'}, id='no-mask-asks-only-where-the-relation-reaches'),
        pytest.param(CURVED, {'curved', 'generator_of'}, id='a-mask-read-through'),
    ],
)
def test_a_walked_links_breakpoints_are_asked_only_at_the_rows_it_reads_the_curve_at(model, read):
    """Asked with the other links, `bp_power` was demanded at every flow, including those of a generator with no curve."""
    assumptions = schema_of(model).expand('piecewise').program.assumptions
    walked = assumptions['coupling_power_complete']
    assert walked.predicate.names_read == frozenset({'bp_power'}), 'the walked link asks for its own values alone'
    assert walked.where is not None and walked.where.dims == frozenset({'flow'}), 'asked per flow the walk reaches'
    assert walked.where.names_read == frozenset(read), 'the where reads the mask, if any, and the relation'
    assert assumptions['coupling_complete'].predicate.names_read == frozenset({'bp_fuel'}), (
        'the link on dims: keeps the block condition to itself'
    )


def test_a_walked_links_own_condition_is_a_name_the_block_reserves():
    with pytest.raises(
        LanguageError, match="writes assumption 'coupling_power_complete', which this file already declares"
    ):
        schema_of(WALKED, assumptions={'coupling_power_complete': 'bp_power >= 0'})


def test_a_mask_on_the_links_own_variable_leaves_the_walked_row_unbuilt():
    """Absence spreads through arithmetic, so a flow with no variable has no row, with or without a block mask."""
    expanded = expand_piecewise(
        schema_of(
            WALKED,
            **{
                'parameters.on_a_curve': {'dims': ['flow'], 'dtype': 'bool'},
                'variables.power.where': 'on_a_curve',
            },
        )
    )
    assert expanded.variables['power'].where == 'on_a_curve'


def test_one_walked_link_is_a_curve_because_the_relation_gives_it_its_arity():
    """A converter whose coupled quantities are all flows of one variable is one link, and it ties them all.

    Two links is what a curve needs when a link is one row. A walked link is
    one row per fine coordinate, so the relation supplies the arity that the
    second link otherwise would.
    """
    expanded = expand_piecewise(schema_of(WALKED, **POWER_ONLY))
    assert expanded.constraints['coupling_convexity'].dims == ['generator', 'snapshot'], 'one curve per generator'
    assert expanded.constraints['coupling_power'].dims == ['flow', 'snapshot'], 'one row per flow, sharing it'
    assert 'coupling_fuel' not in expanded.constraints, 'no row for a link the block does not declare'


def test_one_link_that_walks_nothing_is_still_a_bound_rather_than_a_curve():
    with pytest.raises(LanguageError, match='a bound rather than a curve'):
        schema_of(NONCONVEX_YAML, **{'piecewise.cost_curve.links': {'p': ['p', 'bp_x']}})


@pytest.mark.parametrize(
    ('method', 'match'),
    [
        pytest.param('convex', 'no shape left to check', id='convex'),
        pytest.param('lp', 'which row plays it is data', id='lp'),
    ],
)
def test_the_two_restricted_methods_refuse_a_walked_link_for_their_own_reasons(method, match):
    """`lp` loses the abscissa its line is written against; `convex` loses the pair it reads a shape from.

    The two reasons are not one, so neither message may stand in for the other.
    """
    with pytest.raises(LanguageError, match=match):
        schema_of(WALKED, **{'piecewise.coupling.method': method})


def test_links_that_disagree_on_their_dims_are_refused_rather_than_read_as_one_curve_each():
    """A link finer than `dims:` would multiply the rows it builds, each pinning the same `fuel` to a curve of its own."""
    with pytest.raises(LanguageError, match=r"link 'power' expression carries \['flow'\]"):
        schema_of(WALKED, **{'piecewise.coupling.links': {'power': ['power', 'bp_power'], 'fuel': ['fuel', 'bp_fuel']}})


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
        WALKED,
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
            WALKED,
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
    assert expanded.constraints['coupling_power'].dims == ['flow', 'snapshot', 'period']


#: Three quantities on one curve, two of them bounded rather than pinned.
THREE_WAY = override(
    raw_of(NONCONVEX_YAML),
    **{
        'parameters.bp_z': {'dims': ['bp']},
        'variables.heat': {'dims': ['snapshot'], 'bounds': {'lower': 0}},
    },
)


@pytest.mark.parametrize(
    'links',
    [
        pytest.param(
            {'p': ['p', 'bp_x'], 'op_cost': ['op_cost', 'bp_y', '>='], 'heat': ['heat', 'bp_z']},
            id='three-links-one-bounded',
        ),
        pytest.param(
            {'p': ['p', 'bp_x'], 'op_cost': ['op_cost', 'bp_y', '>='], 'heat': ['heat', 'bp_z', '<=']},
            id='two-bounded-signs-at-once',
        ),
        pytest.param(
            {'p': ['p', 'bp_x'], 'op_cost': ['op_cost', 'bp_y', '>=']}, id='the-two-link-case-that-always-worked'
        ),
    ],
)
def test_a_curve_bounds_as_many_links_as_it_likes_while_one_pins_it(links):
    """Under adjacency each link is its own row against the shared weights, so a sign is per link.

    The old rule capped a block at one non-`==` sign and only with exactly two
    links. Nothing in the emission needed that: `_weights` writes
    `(expr) sign sum(lam * values, along=bp)` per link and reaches for no other.
    """
    expanded = expand_piecewise(schema_of(THREE_WAY, **{'piecewise.cost_curve.links': links}))
    for key, link in links.items():
        sign = link[2] if len(link) == 3 else '=='
        expression = expanded.constraints[f'cost_curve_{key}'].expression
        assert f') {sign} sum(' in expression, f'link on {key} carries its own {sign}'


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
                'piecewise.cost_curve.links': {
                    'p': ['p', 'bp_x'],
                    'op_cost': ['op_cost', 'bp_y', '>='],
                    'heat': ['heat', 'bp_z'],
                },
            },
        )


@pytest.mark.parametrize('method', ['adjacency', 'sos2', 'convex', 'lp'])
def test_every_assumption_a_block_may_derive_is_a_name_it_reserves(method):
    """The collision check reserves the assumption names at load, before the mask that decides which are written is typed."""
    links = (
        {'p': ['p', 'bp_x'], 'op_cost': ['op_cost', 'bp_y', '>=']}
        if method in {'convex', 'lp'}
        else {'p': ['p', 'bp_x'], 'op_cost': ['op_cost', 'bp_y']}
    )
    spec = schema_of(NONCONVEX_YAML, **{'piecewise.cost_curve.method': method, 'piecewise.cost_curve.links': links})
    curve = spec.program.piecewise['cost_curve']

    derived = set(assumptions_of('cost_curve', curve, spec.piecewise['cost_curve'].where))
    assert derived <= set(Emitted.of('cost_curve', curve).assumptions), (
        'a condition the block derives under no reserved name'
    )
