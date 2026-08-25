# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""`piecewise:` expansion, judged at the door that decides it.

Every claim here is one `load_model` or `expand_piecewise` reaches with no data
bound: which declarations a curve emits, which names it may not collide with,
which methods exist, and which gates a block will accept. What a solver then
*does* with those declarations is `tests/test_piecewise.py`, which stays.
"""

from __future__ import annotations

import pytest
import yaml as pyyaml

from math_spec import Buildable, expand_piecewise
from math_spec.errors import LanguageError, PiecewiseExpansionError, SchemaError
from tests.fixtures import DISPATCH_MODEL, override, raw_of, schema_of
from tests.piecewise_models import (
    CHP_YAML,
    GATED_YAML,
    NONCONVEX_YAML,
    SOS2_MODEL,
    TWO_DIM_YAML,
)
from tests.piecewise_models import (
    LP_MODEL as MODEL,
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
    raw = override(raw_of(SOS2_MODEL), **{'sos.cost_curve': {'variable': 'p', 'over': 'snapshot', 'type': 1}})
    with pytest.raises(PiecewiseExpansionError, match="emitted sos 'cost_curve' collides"):
        schema_of(raw)


@pytest.mark.parametrize('method', [pytest.param('incremental', id='unknown'), pytest.param(['sos2'], id='a list')])
def test_a_method_this_project_does_not_have_is_refused(method):
    """The refusal names the formulations that exist rather than picking one.

    A list used to escape it as a `TypeError` from the membership test."""
    raw = raw_of(NONCONVEX_YAML)
    raw['piecewise']['cost_curve']['method'] = method
    with pytest.raises(SchemaError, match='unknown piecewise method'):
        schema_of(raw)


def test_the_file_is_not_a_buildable_and_the_expansion_is():
    """The type is the difference between what was written and what is built.

    A `Model` may still owe declarations to a `piecewise:` block; a `Buildable`
    owes none, which is the whole of what it promises and the reason a builder
    asks for one. Without the distinction a consumer that never expanded reads
    a model missing declarations and gets an answer rather than an error.
    """
    schema = schema_of(NONCONVEX_YAML)

    assert not isinstance(schema, Buildable), 'load_model answers the file, and the file still carries its curves'
    assert isinstance(expand_piecewise(schema), Buildable), 'the expansion is what a builder may read'


@pytest.mark.parametrize(
    'raw',
    [pytest.param(NONCONVEX_YAML, id='with-curves'), pytest.param(MODEL, id='with-curves-as-lines')],
)
def test_every_expansion_answers_a_buildable(raw: str):
    assert isinstance(expand_piecewise(schema_of(raw)), Buildable)


def test_a_model_with_no_curve_is_still_answered_as_a_buildable():
    """Nothing to expand is not nothing to say: the caller asked what it may build.

    The shortcut returns the same object every time so the memo still holds,
    and it is retyped rather than revalidated — the promise is about
    `piecewise:` alone, and that is already empty here.
    """
    schema = schema_of(DISPATCH_MODEL)

    buildable = expand_piecewise(schema)
    assert isinstance(buildable, Buildable), 'a curve-free file is buildable, and says so in its type'
    assert expand_piecewise(schema) is buildable, 'the shortcut memoises like the expansion does'
    assert buildable.constraints.keys() == schema.constraints.keys(), 'retyping declares nothing new'


def test_expanding_a_buildable_is_that_buildable():
    """Idempotent, so a consumer unsure whether it expanded yet can just ask."""
    expanded = expand_piecewise(schema_of(NONCONVEX_YAML))

    assert expand_piecewise(expanded) is expanded


def test_a_buildable_will_not_be_built_around_a_curve():
    """The promise is checked where it is made, not trusted from the caller.

    `expand_piecewise` is the only thing that should produce one; a `Buildable`
    validated straight out of a file that declares `piecewise:` would be the
    type saying a model is complete while its declarations are still owed.
    """
    with pytest.raises(SchemaError, match='expand_piecewise is what produces one'):
        Buildable.model_validate(raw_of(NONCONVEX_YAML))


def test_a_validated_model_expands_once():
    """Validation already built the expansion, so asking again returns it.

    One object from both calls is the observable form of "once is enough": a
    second ``Model`` would be a second full validation of every emitted
    declaration.
    """
    schema = schema_of(NONCONVEX_YAML)
    assert expand_piecewise(schema) is expand_piecewise(schema)


def test_the_emitted_foreach_follows_declaration_order():
    """The frame is a *set* of dims until something orders it, and iterating a
    set spends randomised string hashing — so the emitted ``foreach``, and every
    solver column index behind it, used to vary between processes building the
    same file. Asserted both ways round: within one process a set iterates the
    same way for the same names, so a run that reads the set rather than the
    declaration would have to fail one of the two.
    """
    raw = raw_of(TWO_DIM_YAML)
    assert list(raw['dimensions']) == ['snapshot', 'generator', 'bp']
    assert expand_piecewise(schema_of(raw)).variables['cost_curve_lam'].foreach == [
        'snapshot',
        'generator',
        'bp',
    ]

    flipped = raw_of(TWO_DIM_YAML)
    flipped['dimensions'] = {d: flipped['dimensions'][d] for d in ('generator', 'snapshot', 'bp')}
    assert expand_piecewise(schema_of(flipped)).variables['cost_curve_lam'].foreach == [
        'generator',
        'snapshot',
        'bp',
    ]


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
    raw = override(
        raw_of(NONCONVEX_YAML),
        macros={'twice': {'args': ['x'], 'template': 'x * 2'}},
        expressions={'doubled': 'p * 2'},
    )
    raw['piecewise']['cost_curve']['links'][0] = [link, 'bp_x']
    expanded = expand_piecewise(schema_of(raw))
    assert expanded.constraints['cost_curve_link0'].expression.startswith(f'({link}) ==')


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
            CHP_YAML, {'piecewise.chp.method': 'convex'}, 'exactly two links', id='convex-needs-exactly-two-links'
        ),
        pytest.param(
            GATED_YAML,
            {'piecewise.cost_curve.method': 'convex'},
            'activity is not supported',
            id='convex-cannot-be-gated',
        ),
        pytest.param(
            GATED_YAML,
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
    ],
)
def test_a_malformed_block_is_refused(model, patch, match):
    """Schema-level arity rules and the expansion's own preconditions — both
    have to fire before any data is bound."""
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
    """The formulation checks its links itself, and that is the whole point.

    Lowering would catch these anyway — but only after expansion, so the error
    would name ``cost_curve_link0``, a declaration the user never wrote. The
    guard in ``_expr_dims`` exists to keep the message pointing at the
    ``piecewise:`` block and the link index instead.
    """
    raw = raw_of(NONCONVEX_YAML)
    block = next(iter(raw['piecewise']))
    raw['piecewise'][block]['links'][0][0] = link_expression

    with pytest.raises(PiecewiseExpansionError, match=message) as exc:
        expand_piecewise(schema_of(raw))
    assert f"piecewise '{block}' link 0" in str(exc.value)


@pytest.mark.parametrize(
    ('activity', 'match'),
    [
        pytest.param('at(u_unit, by=unit_of)', 'is not a declared variable', id='a-pullback-through-a-lookup'),
        pytest.param('shift(u, over=snapshot, offset=1)', 'is not a declared variable', id='a-shifted-gate'),
        pytest.param('u * 2', 'is not a declared variable', id='an-arithmetic-gate'),
    ],
)
def test_a_gate_that_is_not_a_variable_is_refused(activity, match):
    """A gate is a variable or it is nothing.

    An expression has no declaration to say what its absence means, and the
    block needs that answer: `absence: zero` pins the curve off where the gate
    is missing, and the default leaves it ungated there.
    """
    with pytest.raises(PiecewiseExpansionError, match=match):
        expand_piecewise(schema_of(GATED_YAML, **{'piecewise.cost_curve.activity': activity}))


@pytest.mark.parametrize(
    ('patch', 'match'),
    [
        pytest.param(
            {'links': [['p', 'bp_x'], ['op_cost', 'bp_y']]},
            'needs exactly one link bounded by the curve',
            id='both-links-pinned',
        ),
        pytest.param(
            {'links': [['p', 'bp_x'], ['op_cost', 'bp_y'], ['p', 'bp_x']]},
            'needs exactly one link bounded by the curve',
            id='three-links-none-bounded',
        ),
        pytest.param(
            {'activity': 'running'},
            'activity is not supported with method: lp',
            id='an-activity-with-nothing-to-gate',
        ),
    ],
)
def test_a_block_lp_cannot_state_is_refused_at_load(patch, match):
    """Refused rather than fallen back from: a method written down is a
    formulation chosen, and quietly building a different one is the thing a
    reviewer of the file could not see."""
    model = pyyaml.safe_load(MODEL)
    model['piecewise']['cost_curve'].update(patch)
    with pytest.raises(SchemaError, match=match):
        schema_of(model)
