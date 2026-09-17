# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Two verbs, and what each one refuses.

`merge` composes peers, so a name two fragments declare is a collision and the
order they are given in means nothing. `override` layers a base and its
patches, so a name the patch declares is the point — and what is pinned for it
is the opposite: every collision the caller did not ask for is an error naming
both sides. A patch that lands on nothing, two patches writing one field, and
an axis redeclared under the expressions written over it are the three, and
each one is a model that would otherwise load and mean something nobody wrote.
"""

from __future__ import annotations

import copy

import pytest

from math_spec import LanguageError, merge, override, to_markdown, to_spec
from tests.fixtures import DISPATCH_MODEL

#: The coupling surface a component library agrees on: one flow per port, and
#: one balance per bus. The two fragments below name `flow` and declare none of
#: it, which is what makes each of them a load error on its own.
SURFACE = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'port': {'dtype': 'str'}, 'bus': {'dtype': 'str'}},
    'relations': {'port_bus': {'key': 'port', 'value': 'bus'}},
    'variables': {'flow': {'dims': ['snapshot', 'port']}},
    'constraints': {'balance': {'dims': ['snapshot', 'bus'], 'expression': 'sum(flow, by=port_bus) == 0'}},
}

SUPPLY = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'port': {'dtype': 'str'}, 'generator': {'dtype': 'str'}},
    'relations': {'gen_port': {'key': 'generator', 'value': 'port'}},
    'parameters': {'gen_cost': {'dims': ['generator']}, 'gen_p_max': {'dims': ['generator']}},
    'variables': {'gen_p': {'dims': ['snapshot', 'generator'], 'bounds': {'lower': 0, 'upper': 'gen_p_max'}}},
    'constraints': {'gen_injects': {'dims': ['snapshot', 'generator'], 'expression': 'at(flow, by=gen_port) == gen_p'}},
    'objective': {'sense': 'minimize', 'expression': 'sum(gen_p * gen_cost)'},
}

DEMAND = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'port': {'dtype': 'str'}, 'demand': {'dtype': 'str'}},
    'relations': {'dem_port': {'key': 'demand', 'value': 'port'}},
    'parameters': {'dem_load': {'dims': ['snapshot', 'demand']}},
    'constraints': {
        'dem_withdraws': {'dims': ['snapshot', 'demand'], 'expression': 'at(flow, by=dem_port) == -dem_load'}
    },
}

LIBRARY = {'surface': SURFACE, 'supply': SUPPLY, 'demand': DEMAND}


def test_a_fragment_names_what_a_sibling_declares():
    """The whole reason merging happens before validation: `supply` reads `flow` and declares none of it."""
    with pytest.raises(LanguageError, match=r'flow'):
        to_spec(SUPPLY)
    spec = to_spec(merge(LIBRARY))
    assert sorted(spec.variables) == ['flow', 'gen_p'], "both fragments' columns are in the one model"
    assert to_markdown(spec), 'a composed library prints as math'


def test_the_balance_does_not_grow_when_a_component_type_is_added():
    """What the port convention buys: a component pins its own flow rather than adding a term."""
    three = to_spec(merge(LIBRARY)).constraints['balance'].expression
    storage = {
        'dimensions': {'snapshot': {'dtype': 'int'}, 'port': {'dtype': 'str'}, 'store': {'dtype': 'str'}},
        'relations': {'st_port': {'key': 'store', 'value': 'port'}},
        'parameters': {'st_capacity': {'dims': ['store']}},
        'variables': {'st_p': {'dims': ['snapshot', 'store'], 'bounds': {'lower': 0, 'upper': 'st_capacity'}}},
        'constraints': {'st_injects': {'dims': ['snapshot', 'store'], 'expression': 'at(flow, by=st_port) == st_p'}},
    }
    four = to_spec(merge({**LIBRARY, 'storage': storage})).constraints['balance'].expression
    assert three == four, 'the balance is written once, whatever is plugged into it'


def test_merging_is_order_independent():
    assert merge(LIBRARY) == merge(dict(reversed(list(LIBRARY.items()))))


def test_a_name_two_fragments_declare_is_refused():
    twin = {**DEMAND, 'parameters': {'gen_cost': {'dims': ['demand']}}}
    with pytest.raises(LanguageError) as raised:
        merge({'supply': SUPPLY, 'twin': twin})
    message = str(raised.value)
    assert "'supply'" in message and "'twin'" in message, 'a collision names both fragments'
    assert 'two rows of a dimension' in message, 'the message names the rewrite it usually is'


def test_an_axis_two_fragments_describe_differently_is_refused():
    relabelled = {**DEMAND, 'dimensions': {**DEMAND['dimensions'], 'snapshot': {'dtype': 'str'}}}
    with pytest.raises(LanguageError, match=r'say different things about dimension'):
        merge({'supply': SUPPLY, 'demand': relabelled})


def test_the_objectives_are_summed_each_term_parenthesised():
    """`a + b * k` reassociates, so an unparenthesised join composes a different objective."""
    priced = {**DEMAND, 'objective': {'sense': 'minimize', 'expression': 'sum(dem_load) * 2'}}
    composed = merge({'surface': SURFACE, 'supply': SUPPLY, 'demand': priced})
    assert composed['objective']['expression'] == '(sum(gen_p * gen_cost)) + (sum(dem_load) * 2)'


def test_one_fragment_s_objective_is_carried_as_it_was_written():
    assert merge(LIBRARY)['objective']['expression'] == SUPPLY['objective']['expression']


def test_objectives_that_run_opposite_ways_are_refused():
    maximised = {**DEMAND, 'objective': {'sense': 'maximize', 'expression': 'sum(dem_load)'}}
    with pytest.raises(LanguageError, match=r'which way the objective runs'):
        merge({'supply': SUPPLY, 'demand': maximised})


def test_fragments_pinning_different_versions_are_refused():
    with pytest.raises(LanguageError, match=r'different language versions'):
        merge({'supply': {**SUPPLY, 'version': 0}, 'demand': {**DEMAND, 'version': 1}})


def test_the_description_belongs_to_the_composition():
    described = merge(LIBRARY, description='a fleet against a load')
    assert described['description'] == 'a fleet against a load'
    assert 'description' not in merge(LIBRARY), "no fragment's own description is carried"


def test_merge_composes_the_model_and_override_configures_the_run():
    """The two verbs meet by taking and returning what the other does."""
    run = override(merge(LIBRARY), {'project': {'variables': {'gen_p': {'where': 'gen_p_max > 0'}}}})
    assert to_spec(run).variables['gen_p'].where == 'gen_p_max > 0'


#: A patch that adds what it needs and a constraint that reads it, so the
#: composed model is one `to_spec` accepts rather than only one that merges.
CARBON = {
    'parameters': {'co2': {'dims': ['generator']}},
    'constraints': {'co2_cap': {'dims': [], 'expression': 'sum(p * co2) <= 100'}},
}


def test_a_patch_names_only_the_field_it_changes():
    laid = override(DISPATCH_MODEL, {'operate': {'variables': {'p': {'where': 'p_max > 0'}}}})
    assert laid['variables']['p'] == {
        'dims': ['snapshot', 'generator'],
        'bounds': {'lower': 0, 'upper': 'p_max'},
        'where': 'p_max > 0',
    }, 'the fields the patch does not name are the ones the base declared'


def test_the_base_is_never_mutated():
    """The guarantee belongs to the function rather than to the caller's discipline."""
    before = copy.deepcopy(DISPATCH_MODEL)
    override(DISPATCH_MODEL, {'carbon': CARBON, 'operate': {'variables': {'p': {'where': 'p_max > 0'}}}})
    assert before == DISPATCH_MODEL, 'a patched base is a new mapping, and the one passed in is untouched'


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
        pytest.param({'expressions': {'spend': {'dims': ['snapshot']}}}, 'expression', id='short-of-what-it-says'),
    ],
)
def test_a_partial_entry_that_lands_on_nothing_is_refused(patch, says):
    """The typo case: laying a partial entry on nothing would invent a declaration nothing refers to."""
    with pytest.raises(LanguageError, match=r'does not declare'):
        override(DISPATCH_MODEL, {'project': patch})
    with pytest.raises(LanguageError) as raised:
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


@pytest.mark.parametrize(
    ('base', 'patch', 'says'),
    [
        pytest.param(
            {k: v for k, v in DISPATCH_MODEL.items() if k != 'objective'},
            {'objective': None},
            'already the feasibility problem',
            id='removing-one-that-is-not-there',
        ),
        pytest.param(
            {k: v for k, v in DISPATCH_MODEL.items() if k != 'objective'},
            {'objective': {'sense': 'maximize'}},
            'an objective needs `expression`',
            id='editing-one-that-is-not-there',
        ),
    ],
)
def test_an_objective_a_base_does_not_declare_is_refused(base, patch, says):
    with pytest.raises(LanguageError) as raised:
        override(base, {'project': patch})
    assert says in str(raised.value)


def test_a_patch_is_a_path_as_readily_as_a_mapping(tmp_path):
    """Whatever every other verb takes, so a patch travels as a file rather than as a script."""
    patch = tmp_path / 'carbon.yaml'
    patch.write_text('parameters:\n  co2: {dims: [generator]}\n', encoding='utf-8')
    laid = override(DISPATCH_MODEL, {'carbon': str(patch)})
    assert 'co2' in laid['parameters']
