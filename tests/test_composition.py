# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Two verbs, and what each one refuses.

`merge` composes peers, so a name two fragments declare is a collision and the
order they are given in means nothing. `override` lays a base and its patches,
so a name the patch declares is the point, and what is pinned for it is the
opposite: every collision the caller did not ask for is an error naming both
sides. A patch that lands on nothing, two patches writing one field, a
dimension redeclared or removed under the expressions written over it, and a
whole section set to null are each a model that would otherwise load and mean
something nobody wrote.
"""

from __future__ import annotations

import copy

import pytest

from math_spec import LanguageError, merge, model, override, to_markdown, to_spec
from tests.fixtures import DISPATCH_MODEL, varied

#: The coupling surface a component library agrees on: one flow per port, and
#: one balance per bus. The two fragments below read `flow` under `given:`, so
#: each is a model on its own as well as a piece of the composition.
SURFACE = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'port': {'dtype': 'str'}, 'bus': {'dtype': 'str'}},
    'relations': {'port_bus': {'key': 'port', 'values': 'bus'}},
    'variables': {'flow': {'dims': ['snapshot', 'port']}},
    'constraints': {
        'balance': {'dims': ['snapshot', 'bus'], 'expression': 'sum(flow, by=port_bus, over=port, into=bus) == 0'}
    },
}

SUPPLY = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'port': {'dtype': 'str'}, 'generator': {'dtype': 'str'}},
    'relations': {'gen_port': {'key': 'generator', 'values': 'port'}},
    'given': {'variables': {'flow': {'dims': ['snapshot', 'port']}}},
    'parameters': {'gen_cost': {'dims': ['generator']}, 'gen_p_max': {'dims': ['generator']}},
    'variables': {'gen_p': {'dims': ['snapshot', 'generator'], 'bounds': {'lower': 0, 'upper': 'gen_p_max'}}},
    'constraints': {
        'gen_injects': {
            'dims': ['snapshot', 'generator'],
            'expression': 'at(flow, by=gen_port, over=port, into=generator) == gen_p',
        }
    },
    'objective': {'sense': 'minimize', 'expression': 'sum(gen_p * gen_cost)'},
}

DEMAND = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'port': {'dtype': 'str'}, 'demand': {'dtype': 'str'}},
    'relations': {'dem_port': {'key': 'demand', 'values': 'port'}},
    'given': {'variables': {'flow': {'dims': ['snapshot', 'port']}}},
    'parameters': {'dem_load': {'dims': ['snapshot', 'demand']}},
    'constraints': {
        'dem_withdraws': {
            'dims': ['snapshot', 'demand'],
            'expression': 'at(flow, by=dem_port, over=port, into=demand) == -dem_load',
        }
    },
}

LIBRARY = {'surface': SURFACE, 'supply': SUPPLY, 'demand': DEMAND}


def test_a_fragment_reads_what_a_sibling_declares():
    """`supply` reads `flow` under `given:`, so it is a model on its own and a piece of the composition."""
    assert to_markdown(SUPPLY), 'a fragment prints as math on its own'
    spec = merge(LIBRARY)
    assert sorted(spec.variables) == ['flow', 'gen_p'], "both fragments' columns are in the one model"
    assert not spec.given, 'the reading is spent once the fragment that builds the column is in the composition'
    assert to_markdown(spec), 'a composed library prints as math'


def test_a_fragment_that_does_not_load_on_its_own_is_refused():
    """A sibling's declarations must not make a broken file load: a fragment is a model before it is a piece."""
    unread = {key: value for key, value in SUPPLY.items() if key != 'given'}
    with pytest.raises(LanguageError, match=r"fragment 'supply' does not load on its own") as raised:
        merge({**LIBRARY, 'supply': unread})
    assert "'flow' not found" in str(raised.value), "the fragment's own refusal follows, so the fix is named"


def test_the_balance_does_not_grow_when_a_component_type_is_added():
    """What the port convention buys: a component pins its own flow rather than adding a term."""
    three = merge(LIBRARY).constraints['balance'].expression
    storage = {
        'dimensions': {'snapshot': {'dtype': 'int'}, 'port': {'dtype': 'str'}, 'store': {'dtype': 'str'}},
        'relations': {'st_port': {'key': 'store', 'values': 'port'}},
        'given': {'variables': {'flow': {'dims': ['snapshot', 'port']}}},
        'parameters': {'st_capacity': {'dims': ['store']}},
        'variables': {'st_p': {'dims': ['snapshot', 'store'], 'bounds': {'lower': 0, 'upper': 'st_capacity'}}},
        'constraints': {
            'st_injects': {
                'dims': ['snapshot', 'store'],
                'expression': 'at(flow, by=st_port, over=port, into=store) == st_p',
            }
        },
    }
    four = merge({**LIBRARY, 'storage': storage}).constraints['balance'].expression
    assert three == four, 'the balance is written once, whatever is plugged into it'


@pytest.mark.parametrize(
    'fragments',
    [
        pytest.param(LIBRARY, id='one-objective'),
        pytest.param(
            {**LIBRARY, 'demand': {**DEMAND, 'objective': {'sense': 'minimize', 'expression': 'sum(dem_load)'}}},
            id='an-objective-in-two-fragments',
        ),
    ],
)
def test_merging_is_order_independent(fragments):
    assert merge(fragments) == merge(dict(reversed(list(fragments.items()))))


def test_the_fragments_are_never_mutated():
    before = copy.deepcopy(LIBRARY)
    merge(LIBRARY)
    assert before == LIBRARY, 'a composed model is a new model, and the fragments are untouched'


@pytest.mark.parametrize(
    ('fragments', 'says'),
    [
        pytest.param(
            {
                'supply': SUPPLY,
                'demand': {**DEMAND, 'parameters': {**DEMAND['parameters'], 'gen_cost': {'dims': ['demand']}}},
            },
            'two rows of a dimension',
            id='one-name-declared-twice',
        ),
        pytest.param(
            {
                'supply': SUPPLY,
                'demand': {**DEMAND, 'dimensions': {**DEMAND['dimensions'], 'snapshot': {'dtype': 'str'}}},
            },
            'give one of them a name of its own',
            id='one-dimension-described-two-ways',
        ),
        pytest.param(
            {'supply': SUPPLY, 'demand': {**DEMAND, 'objective': {'sense': 'maximize', 'expression': 'sum(dem_load)'}}},
            'negate the terms',
            id='objectives-that-run-opposite-ways',
        ),
    ],
)
def test_a_disagreement_between_fragments_is_refused(fragments, says):
    """No order of the fragments settles any of these, so each is a refusal rather than a rule."""
    with pytest.raises(LanguageError) as raised:
        merge(fragments)
    message = str(raised.value)
    assert says in message, 'the refusal names the rewrite rather than only what is wrong'
    assert all(f"'{name}'" in message for name in fragments), 'a disagreement names both fragments'


def test_two_descriptions_of_one_dimension_agree_and_the_first_is_carried():
    """Prose is not a claim, so two fragments describing one dimension in their own words agree about it."""
    first = {**SUPPLY, 'dimensions': {**SUPPLY['dimensions'], 'snapshot': {'dtype': 'int', 'description': 'an hour'}}}
    second = {**DEMAND, 'dimensions': {**DEMAND['dimensions'], 'snapshot': {'dtype': 'int', 'description': 'a step'}}}
    composed = merge({'supply': first, 'demand': second})
    assert composed.dimensions['snapshot'].description == 'an hour', (
        "the claim is carried whole, under the first fragment's wording of the prose"
    )


def test_the_objectives_are_summed_each_term_parenthesised():
    """`a + b * k` reassociates, so an unparenthesised join composes a different objective."""
    priced = {**DEMAND, 'objective': {'sense': 'minimize', 'expression': 'sum(dem_load) * 2'}}
    composed = merge({'surface': SURFACE, 'supply': SUPPLY, 'demand': priced})
    assert composed.objective is not None
    assert composed.objective.expression == '(sum(dem_load) * 2) + (sum(gen_p * gen_cost))', (
        "the terms are summed in the fragments' name order, which no argument order can change"
    )


def test_one_fragment_s_objective_is_carried_as_it_was_written():
    objective = merge(LIBRARY).objective
    assert objective is not None
    assert objective.expression == SUPPLY['objective']['expression']


def test_fragments_written_against_two_language_versions_are_refused(monkeypatch):
    """This reader knows one version, so a second is stood up for the fragments to disagree about."""
    monkeypatch.setattr(model, 'SUPPORTED_VERSIONS', (0, 1))
    with pytest.raises(LanguageError, match=r'One model has one version') as raised:
        merge({'supply': {**SUPPLY, 'version': 0}, 'demand': {**DEMAND, 'version': 1}})
    assert "'supply' says 0" in str(raised.value) and "'demand' says 1" in str(raised.value), 'both are named'


def test_the_description_belongs_to_the_composition():
    described = merge({**LIBRARY, 'supply': {**SUPPLY, 'description': 'a fleet'}}, description='a fleet against a load')
    assert described.description == 'a fleet against a load'
    assert merge({**LIBRARY, 'supply': {**SUPPLY, 'description': 'a fleet'}}).description is None, (
        "no fragment's own description is carried"
    )


def test_merge_composes_the_model_and_override_configures_the_run():
    """The two verbs meet by taking and returning what the other does."""
    run = override(merge(LIBRARY), {'project': {'variables': {'gen_p': {'where': 'gen_p_max > 0'}}}})
    assert to_spec(run).variables['gen_p'].where == 'gen_p_max > 0'


def test_every_section_a_fragment_owns_reaches_the_composition():
    """`merge` listed its sections by hand, so `assumptions:` fell out of every composed model."""
    assumed = {**DEMAND, 'assumptions': {'dem_load_positive': 'dem_load >= 0'}}
    composed = merge({**LIBRARY, 'demand': assumed})
    assert sorted(composed.assumptions) == ['dem_load_positive'], "the fragment's assumption is in the one model"


def test_a_fragment_is_a_path_as_readily_as_a_mapping(tmp_path):
    surface = tmp_path / 'surface.yaml'
    surface.write_text(to_spec(SURFACE).to_yaml(), encoding='utf-8')
    assert merge({**LIBRARY, 'surface': str(surface)}) == merge(LIBRARY)


#: A patch that adds what it needs and a constraint that reads it, so the
#: composed model is one `to_spec` accepts rather than only one that lays.
CARBON = {
    'parameters': {'co2': {'dims': ['generator']}},
    'constraints': {'co2_cap': {'dims': [], 'expression': 'sum(p * co2) <= 100'}},
}

#: A base that reads a solved model: one given column, one given constraint and
#: an expression over the constraint, so a patch to `given:` is checked by
#: `to_spec` rather than only laid.
GIVEN_BASE = {
    'dimensions': {'g': {'dtype': 'str'}},
    'given': {'variables': {'p': {'dims': ['g']}}, 'constraints': {'cap': {'dims': ['g']}}},
    'expressions': {'price': {'expression': 'dual(cap)'}},
}

#: `DISPATCH_MODEL` with no objective, for the patches that ask about one.
FEASIBILITY = {k: v for k, v in DISPATCH_MODEL.items() if k != 'objective'}


def test_a_patch_names_only_the_field_it_changes():
    laid = override(DISPATCH_MODEL, {'operate': {'variables': {'p': {'where': 'p_max > 0'}}}})
    p = laid.variables['p']
    assert (p.dims, p.bounds.lower, p.bounds.upper, p.where) == (['snapshot', 'generator'], 0, 'p_max', 'p_max > 0'), (
        'the fields the patch does not name are the ones the base declared'
    )


def test_the_base_and_the_patches_are_never_mutated():
    """The guarantee belongs to the function rather than to the caller's discipline."""
    patches = {'carbon': CARBON, 'operate': {'variables': {'p': {'where': 'p_max > 0'}}}}
    before = copy.deepcopy((DISPATCH_MODEL, patches))
    override(DISPATCH_MODEL, patches)
    assert before == (DISPATCH_MODEL, patches), 'a patched base is a new mapping, and both inputs are untouched'


def test_a_whole_declaration_is_created_and_the_model_loads():
    spec = override(DISPATCH_MODEL, {'carbon': CARBON})
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
    assert laid.constraints == {}, 'the declaration is gone rather than emptied'


def test_a_stale_removal_is_refused():
    with pytest.raises(LanguageError, match=r"'balnce'.*does not declare.*Did you mean 'balance'\?"):
        override(DISPATCH_MODEL, {'stale': {'constraints': {'balnce': None}}})


@pytest.mark.parametrize(
    ('patch', 'field', 'default'),
    [
        pytest.param({'variables': {'p': {'where': None}}}, lambda s: s.variables['p'].where, None, id='a-mask'),
        pytest.param(
            {'variables': {'p': {'bounds': {'upper': None}}}},
            lambda s: s.program.variables['p'].upper,
            None,
            id='a-bound-two-levels-down',
        ),
        pytest.param(
            {'variables': {'p': {'domain': None}}},
            lambda s: s.variables['p'].domain,
            'continuous',
            id='a-field-that-takes-no-null',
        ),
        pytest.param({'version': None}, lambda s: s.version, 0, id='a-top-level-field-that-takes-no-null'),
    ],
)
def test_a_null_field_takes_its_default(patch, field, default):
    """`null` makes what it names absent: a declaration is removed, and a field takes its default.

    A field that takes no null was the case that failed: `domain: null` was laid
    as a value the schema refuses, so a patch could not put a field back to its
    default.
    """
    base = varied(
        DISPATCH_MODEL,
        **{'description': 'dispatch', 'variables.p.where': 'p_max > 0', 'variables.p.domain': 'integer'},
    )
    laid = override(base, {'relaxed': patch})
    assert field(laid) == default
    assert laid.variables['p'].bounds.lower == 0, 'a field the patch does not name stays as the base wrote it'


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
    assert twice.variables['p'].where == 'cost > 0'


def test_a_patch_adds_a_dimension_and_may_restate_one_it_shares():
    laid = override(
        DISPATCH_MODEL,
        {'periods': {'dimensions': {'snapshot': {'dtype': 'int'}, 'investment_period': {'dtype': 'int'}}}},
    )
    assert sorted(laid.dimensions) == ['generator', 'investment_period', 'snapshot'], (
        'the dimension the patch adds joins the two the base declares, and the restated one is not doubled'
    )


@pytest.mark.parametrize(
    ('patch', 'says'),
    [
        pytest.param(
            {'dimensions': {'snapshot': {'dtype': 'str'}}},
            'adjusts the math, not the coordinate space',
            id='declared-as-something-else',
        ),
        pytest.param(
            {'dimensions': {'snapshot': {}}},
            'restate the declaration word for word',
            id='restated-in-part',
        ),
        pytest.param(
            {'dimensions': {'snapshot': None}},
            'remove the declarations written over it one at a time',
            id='removed',
        ),
    ],
)
def test_a_patch_that_rewrites_a_dimension_is_refused(patch, says):
    """A dimension changed under the expressions already written over it is a different model, silently."""
    with pytest.raises(LanguageError) as raised:
        override(DISPATCH_MODEL, {'relabelled': patch})
    assert says in str(raised.value), 'the refusal names the rewrite rather than only what is wrong'


@pytest.mark.parametrize(
    'patch',
    [
        pytest.param({'constraints': None}, id='an-owned-section'),
        pytest.param({'dimensions': None}, id='a-shared-section'),
        pytest.param({'given': {'variables': None}}, id='one-kind-of-given'),
    ],
)
def test_a_whole_section_set_to_null_is_refused(patch):
    """Nulling a section reads as emptying it, and laying it silently changed nothing at all."""
    with pytest.raises(LanguageError, match=r'removes nothing') as raised:
        override(DISPATCH_MODEL, {'blank': patch})
    assert 'one at a time' in str(raised.value), 'the refusal names the rewrite, which is one null per declaration'


def test_the_objective_is_laid_over_field_by_field():
    laid = override(DISPATCH_MODEL, {'maximised': {'objective': {'sense': 'maximize'}}})
    assert laid.objective is not None
    assert (laid.objective.sense, laid.objective.expression) == ('maximize', 'sum(p * cost)'), (
        'the sense the patch names changes, and the expression the base wrote stays'
    )


def test_the_objective_can_be_removed_and_the_model_is_a_feasibility_problem():
    laid = override(DISPATCH_MODEL, {'feasible': {'objective': None}})
    assert laid.objective is None


def test_a_whole_objective_is_created_where_the_base_has_none():
    laid = override(FEASIBILITY, {'priced': {'objective': DISPATCH_MODEL['objective']}})
    assert laid.objective is not None


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
    laid = override(GIVEN_BASE, {'wider': {'given': {'variables': {'p': {'domain': 'binary'}}}}})
    p = laid.given.variables['p']
    assert (p.dims, p.domain) == (['g'], 'binary'), 'the given column is edited field by field like any declaration'
    assert sorted(laid.given.constraints) == ['cap'], 'the kind the patch did not name is still there'


@pytest.mark.parametrize(
    ('base', 'reads'),
    [
        pytest.param(GIVEN_BASE, ['p', 'q'], id='a-base-that-already-reads'),
        pytest.param({'dimensions': {'g': {'dtype': 'str'}}}, ['q'], id='a-base-that-reads-nothing-yet'),
    ],
)
def test_a_whole_given_entry_is_created_and_the_model_loads(base, reads):
    """A patch adds a column to read, whether or not the base opened the block."""
    laid = override(base, {'solved': {'given': {'variables': {'q': {'dims': ['g']}}}}})
    assert sorted(laid.given.variables) == reads, 'the created column joins whatever the base read'


def test_a_patch_is_a_path_as_readily_as_a_mapping(tmp_path):
    """Whatever every other verb takes, so a patch travels as a file rather than as a script."""
    patch = tmp_path / 'carbon.yaml'
    patch.write_text('parameters:\n  co2: {dims: [generator]}\n', encoding='utf-8')
    laid = override(DISPATCH_MODEL, {'carbon': str(patch)})
    assert 'co2' in laid.parameters


def test_a_base_that_does_not_load_is_refused_though_a_patch_would_mend_it():
    """A base is a model a framework ships, so one that does not load is refused before a patch reaches it."""
    unpriced = {**DISPATCH_MODEL, 'parameters': {k: v for k, v in DISPATCH_MODEL['parameters'].items() if k != 'cost'}}
    with pytest.raises(LanguageError, match=r"'cost' not found"):
        override(unpriced, {'priced': {'parameters': {'cost': {'dims': ['generator']}}}})


def test_a_loaded_spec_is_a_base_as_readily_as_a_mapping():
    laid = override(to_spec(DISPATCH_MODEL), {'carbon': CARBON})
    assert 'co2_cap' in laid.constraints
