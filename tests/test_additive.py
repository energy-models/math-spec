# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""A named expression several fragments add terms to.

A balance reads what every component puts into a bus, and a component file
says what it puts there. With `additive: true` each component file defines its
own share under one name, and `merge` sums the shares, so a new component is a
new file and the balance does not change.
"""

from __future__ import annotations

import pytest

from mathspec import FORMATS, LanguageError, merge, override, to_markdown, to_spec, typeset

DIMS = {'snapshot': {'dtype': 'int'}, 'bus': {'dtype': 'str'}}

#: The balance: it reads the total and defines none of it.
BALANCE = {
    'dimensions': DIMS,
    'given': {'expressions': {'injection': {'dims': ['snapshot', 'bus']}}},
    'constraints': {'balance': {'dims': ['snapshot', 'bus'], 'expression': 'injection == 0'}},
}

#: A generator fleet, adding what it produces to the injection.
FLEET = {
    'dimensions': {**DIMS, 'generator': {'dtype': 'str'}},
    'relations': {'gen_bus': {'key': 'generator', 'values': 'bus'}},
    'variables': {'gen_p': {'dims': ['snapshot', 'generator'], 'bounds': {'lower': 0}}},
    'expressions': {
        'injection': {
            'additive': True,
            'expression': 'sum(gen_p, by=gen_bus, over=generator, into=bus)',
            'description': 'what the components put into a bus',
        }
    },
    'objective': {'sense': 'minimize', 'expression': 'sum(gen_p)'},
}

#: A demand, subtracting what it draws from the injection.
DEMAND = {
    'dimensions': DIMS,
    'parameters': {'load': {'dims': ['snapshot', 'bus']}},
    'expressions': {'injection': {'additive': True, 'expression': '-load'}},
}


def test_a_share_loads_on_its_own_as_the_expression_it_writes():
    spec = to_spec(FLEET)
    assert spec.expressions['injection'].additive
    assert spec.program.expressions['injection'].additive, 'the program carries the flag the legend prints'


def test_merging_sums_the_shares_in_fragment_name_order():
    composed = merge({'fleet': FLEET, 'demand': DEMAND, 'balance': BALANCE})
    assert (
        composed.expressions['injection'].expression == '(-load) + (sum(gen_p, by=gen_bus, over=generator, into=bus))'
    )
    assert composed.expressions['injection'].additive, 'the sum stays open, so a later merge can add to it'
    assert not composed.given, 'the balance reads the sum, which the composition defines'


def test_the_order_the_fragments_are_given_in_does_not_reach_the_sum():
    one = merge({'fleet': FLEET, 'demand': DEMAND})
    other = merge({'demand': DEMAND, 'fleet': FLEET})
    assert one == other


def test_a_merged_sum_takes_more_shares_in_a_second_merge():
    """The flag survives the merge, so composing in two steps gives the same model as in one."""
    storage = {
        'dimensions': {**DIMS, 'store': {'dtype': 'str'}},
        'relations': {'store_bus': {'key': 'store', 'values': 'bus'}},
        'variables': {'store_p': {'dims': ['snapshot', 'store']}},
        'expressions': {
            'injection': {'additive': True, 'expression': 'sum(store_p, by=store_bus, over=store, into=bus)'}
        },
    }
    stepwise = merge({'core': merge({'demand': DEMAND, 'fleet': FLEET}), 'storage': storage})
    assert 'store_p' in stepwise.expressions['injection'].expression
    assert 'gen_p' in stepwise.expressions['injection'].expression


def test_the_first_description_is_carried():
    composed = merge({'fleet': FLEET, 'demand': DEMAND})
    assert composed.expressions['injection'].description == 'what the components put into a bus'


def test_a_given_expression_is_checked_against_every_share():
    """A share over a narrower frame broadcasts into the sum, so the sum's frame is the union."""
    over_bus_only = {**DEMAND, 'parameters': {'load': {'dims': ['bus']}}}
    composed = merge({'fleet': FLEET, 'demand': over_bus_only, 'balance': BALANCE})
    assert composed.program.expressions['injection'].dims == ('snapshot', 'bus')


def test_a_given_expression_over_a_frame_no_share_sums_to_is_refused():
    narrow = {
        'dimensions': DIMS,
        'given': {'expressions': {'injection': {'dims': ['bus']}}},
        'constraints': {'balance': {'dims': ['bus'], 'expression': 'injection == 0'}},
    }
    with pytest.raises(LanguageError, match=r"reads the given expression 'injection' over \['bus'\]"):
        merge({'fleet': FLEET, 'demand': DEMAND, 'balance': narrow})


def test_an_expression_one_fragment_adds_to_and_another_owns_is_refused():
    owned = {**DEMAND, 'expressions': {'injection': {'expression': '-load'}}}
    with pytest.raises(LanguageError, match=r"'demand' defines 'injection' whole, where 'fleet' adds a share"):
        merge({'fleet': FLEET, 'demand': owned})


def test_a_fragment_that_reads_the_sum_it_adds_to_is_refused():
    """Alone it reads its own share; composed it would read the total, so the file would change meaning."""
    reads_itself = {
        **FLEET,
        'constraints': {'capped': {'dims': ['snapshot', 'bus'], 'expression': 'injection <= 10'}},
    }
    with pytest.raises(LanguageError, match=r"'fleet' adds a share to 'injection' and reads it"):
        merge({'fleet': reads_itself, 'demand': DEMAND})


def test_one_share_alone_is_carried_as_written():
    composed = merge({'fleet': FLEET, 'balance': BALANCE})
    assert composed.expressions['injection'].expression == 'sum(gen_p, by=gen_bus, over=generator, into=bus)'


def test_an_additive_expression_is_one_expression_and_not_cases():
    cased = {
        **DEMAND,
        'expressions': {
            'injection': {
                'additive': True,
                'dims': ['snapshot', 'bus'],
                'cases': {'peak': {'when': 'load > 5', 'expression': '-load'}},
                'otherwise': '0',
            }
        },
    }
    with pytest.raises(LanguageError, match=r'`additive: true` takes one `expression:`'):
        to_spec(cased)


def test_a_patch_replaces_a_share_rather_than_adding_one():
    """`override` edits what is there; a new share is a new fragment for `merge`."""
    laid = override(DEMAND, {'double': {'expressions': {'injection': {'expression': '-2 * load'}}}})
    assert laid.expressions['injection'].expression == '-2 * load'
    assert laid.expressions['injection'].additive, 'the patch names only the field it changes'


def test_the_legend_says_other_files_add_to_it():
    definitions = to_markdown(FLEET).split('#### Definitions')[1]
    assert 'a sum other files add terms to' in definitions


@pytest.mark.parametrize('fmt', sorted(FORMATS))
def test_a_share_prints_in_every_format(fmt):
    assert typeset(merge({'fleet': FLEET, 'demand': DEMAND, 'balance': BALANCE}), fmt), f'{fmt} rendered nothing'
