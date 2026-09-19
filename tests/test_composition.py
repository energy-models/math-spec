# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""`override` lays a base and its patches, and what it refuses.

A name the patch declares is the point, and what is pinned for it is the
opposite: every collision the caller did not ask for is an error naming both
sides. A patch that lands on nothing, two patches writing one field, and an
axis redeclared under the expressions written over it are the three, and each
one is a model that would otherwise load and mean something nobody wrote.
"""

from __future__ import annotations

import copy

import pytest

from math_spec import LanguageError, override, to_markdown, to_spec
from tests.fixtures import DISPATCH_MODEL

#: A patch that adds what it needs and a constraint that reads it, so the
#: composed model is one `to_spec` accepts rather than only one that lays.
CARBON = {
    'parameters': {'co2': {'dims': ['generator']}},
    'constraints': {'co2_cap': {'dims': [], 'expression': 'sum(p * co2) <= 100'}},
}

#: `DISPATCH_MODEL` with no objective, for the patches that ask about one.
FEASIBILITY = {k: v for k, v in DISPATCH_MODEL.items() if k != 'objective'}


def test_a_patch_names_only_the_field_it_changes():
    laid = override(DISPATCH_MODEL, {'operate': {'variables': {'p': {'where': 'p_max > 0'}}}})
    assert laid['variables']['p'] == {
        'dims': ['snapshot', 'generator'],
        'bounds': {'lower': 0, 'upper': 'p_max'},
        'where': 'p_max > 0',
    }, 'the fields the patch does not name are the ones the base declared'


def test_the_base_and_the_patches_are_never_mutated():
    """The guarantee belongs to the function rather than to the caller's discipline."""
    patches = {'carbon': CARBON, 'operate': {'variables': {'p': {'where': 'p_max > 0'}}}}
    before = copy.deepcopy((DISPATCH_MODEL, patches))
    override(DISPATCH_MODEL, patches)
    assert before == (DISPATCH_MODEL, patches), 'a patched base is a new mapping, and both inputs are untouched'


def test_a_whole_declaration_is_created_and_the_model_loads():
    spec = to_spec(override(DISPATCH_MODEL, {'carbon': CARBON}))
    assert 'co2_cap' in spec.constraints
    assert to_markdown(spec), 'a composed model is one a reviewer can read as math'


@pytest.mark.parametrize(
    ('patch', 'says'),
    [
        pytest.param({'constraints': {'balnce': {'dims': ['snapshot']}}}, "Did you mean 'balance'?", id='a-near-miss'),
        pytest.param(
            {'constraints': {'co2_cap': {'dims': []}}}, 'a constraint needs `expression`', id='short-of-a-field'
        ),
        pytest.param({'parameters': {'co2': {'dtype': 'float'}}}, 'a parameter needs `dims`', id='short-of-its-frame'),
        pytest.param(
            {'expressions': {'spend': {'dims': ['snapshot']}}},
            'one `expression:` or a set of `cases:`',
            id='short-of-what-it-says',
        ),
        pytest.param(
            {'given': {'variables': {'flow': {'domain': 'binary'}}}},
            'a given variable needs `dims`',
            id='a-given-column-short-of-its-frame',
        ),
    ],
)
def test_a_partial_entry_that_lands_on_nothing_is_refused(patch, says):
    """The typo case: laying a partial entry on nothing would invent a declaration nothing refers to."""
    with pytest.raises(LanguageError, match=r'does not declare') as raised:
        override(DISPATCH_MODEL, {'project': patch})
    assert says in str(raised.value), 'the refusal says what the entry is short of, or what it nearly named'


def test_a_null_removes_a_declaration_and_the_model_still_loads():
    laid = override(DISPATCH_MODEL, {'unconstrained': {'constraints': {'balance': None}}})
    assert laid['constraints'] == {}, 'the declaration is gone rather than emptied'
    assert to_spec(laid).constraints == {}


def test_a_stale_removal_is_refused():
    with pytest.raises(LanguageError, match=r"'balnce'.*does not declare.*Did you mean 'balance'\?"):
        override(DISPATCH_MODEL, {'stale': {'constraints': {'balnce': None}}})


def test_a_null_inside_a_declaration_is_a_value_rather_than_a_removal():
    """`where: null` is the mask the schema already takes, so the marker is positional.

    The base carries a mask, so setting the field to `null` and deleting it are
    two different declarations rather than the same one twice.
    """
    masked = override(DISPATCH_MODEL, {'masked': {'variables': {'p': {'where': 'p_max > 0'}}}})
    laid = override(masked, {'unmasked': {'variables': {'p': {'where': None}}}})
    assert 'where' in laid['variables']['p'], 'the field is set to none, and is not deleted from the declaration'
    assert laid['variables']['p']['where'] is None
    assert to_spec(laid).variables['p'].where is None


def test_a_null_two_levels_down_is_a_value_too():
    """The removal marker reaches no deeper than the declaration, however deep the `null` sits."""
    laid = override(DISPATCH_MODEL, {'unbounded': {'variables': {'p': {'bounds': {'upper': None}}}}})
    assert laid['variables']['p']['bounds'] == {'lower': 0, 'upper': None}, (
        'the bound is set to none beside the one the base keeps, and neither is deleted'
    )


def test_the_result_shares_no_declaration_with_the_base_or_the_patch():
    """Both sides are copied, so editing a composed model cannot reach back into either.

    A declaration no patch names is the case worth pinning: it is carried over
    untouched, which is exactly where a reference would be passed on instead.
    """
    laid = override(DISPATCH_MODEL, {'carbon': CARBON})
    assert laid['parameters']['load'] is not DISPATCH_MODEL['parameters']['load'], (
        "a declaration the patches leave alone is a copy, not the base's own object"
    )
    assert laid['parameters']['co2'] is not CARBON['parameters']['co2'], (
        "a declaration a patch adds is a copy, not the patch mapping's own object"
    )


@pytest.mark.parametrize(
    'patches',
    [
        pytest.param(
            {
                'pathway': {'variables': {'p': {'bounds': {'upper': 'p_max'}}}},
                'project': {'variables': {'p': {'bounds': {'upper': 'cost'}}}},
            },
            id='one-field-twice',
        ),
        pytest.param(
            {
                'pathway': {'constraints': {'balance': None}},
                'project': {'constraints': {'balance': {'dims': ['snapshot', 'generator']}}},
            },
            id='removed-here-edited-there',
        ),
        pytest.param(
            {'pathway': {'objective': {'sense': 'maximize'}}, 'project': {'objective': {'sense': 'minimize'}}},
            id='the-objective-twice',
        ),
        pytest.param(
            {'pathway': {'version': 0}, 'project': {'version': 1}},
            id='a-top-level-scalar-twice',
        ),
    ],
)
def test_two_patches_that_write_one_field_are_refused(patches):
    with pytest.raises(LanguageError) as raised:
        override(DISPATCH_MODEL, patches)
    message = str(raised.value)
    assert "'pathway'" in message and "'project'" in message, 'a collision names both patches, not just the second'
    assert 'override(override(' in message, 'the message names the rewrite, which is to lay one on the other'


def test_disjoint_patches_compose_the_same_model_in_either_order():
    """What the disjointness rule buys: the argument's position never decides a model."""
    patches = {'carbon': CARBON, 'operate': {'variables': {'p': {'where': 'p_max > 0'}}}}
    reversed_order = dict(reversed(list(patches.items())))
    assert override(DISPATCH_MODEL, patches) == override(DISPATCH_MODEL, reversed_order)


def test_layering_is_written_out_as_nesting():
    """The second call lays on the first's result, which is where an order is allowed to matter."""
    once = override(DISPATCH_MODEL, {'pathway': {'variables': {'p': {'where': 'p_max > 0'}}}})
    twice = override(once, {'project': {'variables': {'p': {'where': 'cost > 0'}}}})
    assert twice['variables']['p']['where'] == 'cost > 0'


def test_a_patch_adds_an_axis_and_may_restate_one_it_shares():
    laid = override(
        DISPATCH_MODEL,
        {'periods': {'dimensions': {'snapshot': {'dtype': 'int'}, 'investment_period': {'dtype': 'int'}}}},
    )
    assert sorted(laid['dimensions']) == ['generator', 'investment_period', 'snapshot'], (
        'the axis the patch adds joins the two the base declares, and the restated one is not doubled'
    )


def test_a_patch_that_redeclares_an_axis_is_refused():
    """An axis changed under the expressions already written over it is a different model, silently."""
    with pytest.raises(LanguageError, match=r'adjusts the math, not the axes'):
        override(DISPATCH_MODEL, {'relabelled': {'dimensions': {'snapshot': {'dtype': 'str'}}}})


def test_the_objective_is_laid_over_field_by_field():
    laid = override(DISPATCH_MODEL, {'maximised': {'objective': {'sense': 'maximize'}}})
    assert laid['objective'] == {'sense': 'maximize', 'expression': 'sum(p * cost)'}, (
        'the sense the patch names changes, and the expression the base wrote stays'
    )


def test_the_objective_can_be_removed_and_the_model_is_a_feasibility_problem():
    laid = override(DISPATCH_MODEL, {'feasible': {'objective': None}})
    assert 'objective' not in laid
    assert to_spec(laid).objective is None


def test_a_whole_objective_is_created_where_the_base_has_none():
    laid = override(FEASIBILITY, {'priced': {'objective': DISPATCH_MODEL['objective']}})
    assert to_spec(laid).objective is not None


@pytest.mark.parametrize(
    ('patch', 'says'),
    [
        pytest.param({'objective': None}, 'already the feasibility problem', id='removing-one-that-is-not-there'),
        pytest.param(
            {'objective': {'sense': 'maximize'}}, 'an objective needs `expression`', id='editing-one-that-is-not-there'
        ),
    ],
)
def test_an_objective_a_base_does_not_declare_is_refused(patch, says):
    with pytest.raises(LanguageError, match=r'does not declare') as raised:
        override(FEASIBILITY, {'project': patch})
    assert says in str(raised.value)


def test_a_patch_over_one_kind_of_given_leaves_the_other_alone():
    """`given:` is laid over a kind at a time, so patching the columns cannot drop the row families."""
    base = {
        'dimensions': {'g': {'dtype': 'str'}},
        'given': {'variables': {'p': {'dims': ['g']}}, 'constraints': {'cap': {'dims': ['g']}}},
        'expressions': {'price': {'expression': 'dual(cap)'}},
    }
    laid = override(base, {'wider': {'given': {'variables': {'p': {'domain': 'binary'}}}}})
    assert laid['given']['variables']['p'] == {'dims': ['g'], 'domain': 'binary'}, (
        'the given column is edited field by field like any declaration'
    )
    assert sorted(laid['given']['constraints']) == ['cap'], 'the kind the patch did not name is still there'
    assert to_spec(laid).given.variables['p'].domain == 'binary'


def test_a_patch_is_a_path_as_readily_as_a_mapping(tmp_path):
    """Whatever every other verb takes, so a patch travels as a file rather than as a script."""
    patch = tmp_path / 'carbon.yaml'
    patch.write_text('parameters:\n  co2: {dims: [generator]}\n', encoding='utf-8')
    laid = override(DISPATCH_MODEL, {'carbon': str(patch)})
    assert 'co2' in laid['parameters']


def test_a_loaded_spec_is_a_base_as_readily_as_a_mapping():
    laid = override(to_spec(DISPATCH_MODEL), {'carbon': CARBON})
    assert 'co2_cap' in to_spec(laid).constraints
