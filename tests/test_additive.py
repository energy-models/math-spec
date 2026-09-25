# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""A named expression several fragments add terms to.

A balance reads what every component puts into a bus, and a component file
says what it puts there. The file that reads the total marks it
`additive: true` on its `given:` entry, and states its frame once. Each
component declares its term as an ordinary named expression under that name,
and `merge` sums the terms. The marked entry stays in the composed model, so a
later merge adds more.
"""

from __future__ import annotations

import pytest

from mathspec import FORMATS, LanguageError, merge, override, to_markdown, to_spec, typeset

DIMS = {'snapshot': {'dtype': 'int'}, 'bus': {'dtype': 'str'}}
INJECTION = 'what the components put into a bus'

#: The balance: it says `injection` is a sum over its frame, and adds nothing to it.
BALANCE = {
    'dimensions': DIMS,
    'given': {'expressions': {'injection': {'dims': ['snapshot', 'bus'], 'additive': True, 'description': INJECTION}}},
    'constraints': {'balance': {'dims': ['snapshot', 'bus'], 'expression': 'injection == 0'}},
}

#: A generator fleet: its term is an ordinary named expression.
FLEET = {
    'dimensions': {**DIMS, 'generator': {'dtype': 'str'}},
    'relations': {'gen_bus': {'key': 'generator', 'values': 'bus'}},
    'variables': {'gen_p': {'dims': ['snapshot', 'generator'], 'bounds': {'lower': 0}}},
    'expressions': {'injection': 'sum(gen_p, by=gen_bus, over=generator, into=bus)'},
    'objective': {'sense': 'minimize', 'expression': 'sum(gen_p)'},
}

#: A demand, subtracting what it draws.
DEMAND = {
    'dimensions': DIMS,
    'parameters': {'load': {'dims': ['snapshot', 'bus']}},
    'expressions': {'injection': '-load'},
}

#: A store, added in a second merge.
STORAGE = {
    'dimensions': {**DIMS, 'store': {'dtype': 'str'}},
    'relations': {'store_bus': {'key': 'store', 'values': 'bus'}},
    'variables': {'store_p': {'dims': ['snapshot', 'store']}},
    'expressions': {'injection': 'sum(store_p, by=store_bus, over=store, into=bus)'},
}

#: A reader that states the frame and does not say the name is a sum.
CAPPED = {
    'dimensions': DIMS,
    'given': {'expressions': {'injection': {'dims': ['snapshot', 'bus']}}},
    'constraints': {'capped': {'dims': ['snapshot', 'bus'], 'expression': 'injection <= 10'}},
}


# ---------------------------------------------------------------------------
# one file
# ---------------------------------------------------------------------------


def test_a_reader_marks_the_sum_and_loads_on_its_own():
    program = to_spec(BALANCE).program
    assert program.given.expressions['injection'].additive
    assert program.given.expressions['injection'].dims == ('snapshot', 'bus')


def test_a_term_is_an_ordinary_named_expression():
    program = to_spec(FLEET).program
    assert not program.expressions['injection'].additive, 'nothing in a plain contributor says it is a term'


#: A file that adds a term of its own and reads the sum: it carries both.
HUB = {
    **FLEET,
    'given': {'expressions': {'injection': {'dims': ['snapshot', 'bus'], 'additive': True}}},
    'constraints': {'capped': {'dims': ['snapshot', 'bus'], 'expression': 'injection <= 10'}},
}


def test_a_file_may_add_a_term_and_read_the_sum_when_it_marks_it():
    """The marked entry says the file reads the sum so far, which alone is its own term."""
    program = to_spec(HUB).program
    assert program.expressions['injection'].additive, 'the entry folds into the definition'
    assert not program.given, 'a name this file defines is not one it reads from elsewhere'


def test_a_term_over_a_dimension_the_sum_does_not_state_is_refused_at_load():
    narrow = {**HUB, 'given': {'expressions': {'injection': {'dims': ['bus'], 'additive': True}}}}
    narrow = {
        **narrow,
        'constraints': {'capped': {'dims': ['bus'], 'expression': 'sum(injection, over=snapshot) <= 10'}},
    }
    with pytest.raises(LanguageError, match=r"Named expression 'injection' carries \['snapshot'\]"):
        to_spec(narrow)


def test_a_cased_term_beside_the_marked_entry_is_refused_at_load():
    cased = {
        **DEMAND,
        'given': {'expressions': {'injection': {'dims': ['snapshot', 'bus'], 'additive': True}}},
        'expressions': {
            'injection': {
                'dims': ['snapshot', 'bus'],
                'cases': {'peak': {'when': 'load > 5', 'expression': '-load'}},
                'otherwise': '0',
            }
        },
    }
    with pytest.raises(LanguageError, match=r'a term of a sum is one `expression:`'):
        to_spec(cased)


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------


def test_merging_sums_every_term_of_a_marked_name_in_fragment_name_order():
    composed = merge({'fleet': FLEET, 'demand': DEMAND, 'balance': BALANCE})
    assert composed.expressions['injection'].expression == (
        '(-load) + (sum(gen_p, by=gen_bus, over=generator, into=bus))'
    )
    assert composed.given.expressions['injection'].additive, 'the marked entry is kept'
    assert not composed.program.given, 'and it folds into the definition, so the composed model reads nothing'
    assert composed.program.expressions['injection'].additive


def test_the_order_the_fragments_are_given_in_does_not_reach_the_sum():
    one = merge({'fleet': FLEET, 'demand': DEMAND, 'balance': BALANCE})
    other = merge({'balance': BALANCE, 'demand': DEMAND, 'fleet': FLEET})
    assert one == other


def test_a_composed_model_takes_more_terms_in_a_second_merge():
    """The kept entry is what lets a framework ship a composed model that a project adds to."""
    shipped = merge({'balance': BALANCE, 'demand': DEMAND, 'fleet': FLEET})
    extended = merge({'shipped': shipped, 'storage': STORAGE})
    assert 'store_p' in extended.expressions['injection'].expression
    assert 'gen_p' in extended.expressions['injection'].expression


def test_the_sum_takes_the_readers_description():
    composed = merge({'fleet': FLEET, 'demand': DEMAND, 'balance': BALANCE})
    assert composed.program.expressions['injection'].description == INJECTION


def test_two_terms_and_no_marked_reader_collide_and_the_message_names_the_fix():
    with pytest.raises(LanguageError) as raised:
        merge({'fleet': FLEET, 'demand': DEMAND})
    message = str(raised.value)
    assert "both declare the expression 'injection'" in message
    assert '`additive: true` on a `given: expressions:` entry' in message, 'the collision says how to make it a sum'


def test_one_term_and_an_unmarked_reader_is_an_ordinary_fold():
    composed = merge({'fleet': FLEET, 'capped': CAPPED})
    assert not composed.given
    assert not composed.program.expressions['injection'].additive


def test_one_reader_marks_the_sum_and_another_states_the_frame():
    composed = merge({'balance': BALANCE, 'capped': CAPPED, 'demand': DEMAND, 'fleet': FLEET})
    assert composed.given.expressions['injection'].additive, 'the flag comes from either entry'
    assert sorted(composed.constraints) == ['balance', 'capped']


def test_two_readers_that_disagree_about_the_frame_are_refused():
    narrow = {**CAPPED, 'given': {'expressions': {'injection': {'dims': ['bus']}}}}
    narrow = {**narrow, 'constraints': {'capped': {'dims': ['bus'], 'expression': 'injection <= 10'}}}
    with pytest.raises(LanguageError, match=r"say different things about the given expression 'injection'"):
        merge({'balance': BALANCE, 'capped': narrow, 'fleet': FLEET})


def test_a_term_over_a_dimension_the_sum_does_not_state_is_refused_by_merge():
    narrow = {
        'dimensions': DIMS,
        'given': {'expressions': {'injection': {'dims': ['bus'], 'additive': True}}},
        'variables': {'slack': {'dims': ['bus']}},
        'constraints': {'balance': {'dims': ['bus'], 'expression': 'injection + slack == 0'}},
    }
    with pytest.raises(LanguageError, match=r"'fleet' adds a term to 'injection' over \['bus', 'snapshot'\]"):
        merge({'balance': narrow, 'demand': {**DEMAND, 'parameters': {'load': {'dims': ['bus']}}}, 'fleet': FLEET})


@pytest.mark.parametrize(
    'others',
    [
        pytest.param({'demand': DEMAND}, id='beside-another-term'),
        pytest.param({}, id='as-the-only-term'),
    ],
)
def test_a_contributor_that_reads_the_sum_without_the_entry_is_refused(others):
    """Alone it reads its own term; composed it would read the sum, so the file would mean two things."""
    reads_itself = {**FLEET, 'constraints': {'capped': {'dims': ['snapshot', 'bus'], 'expression': 'injection <= 10'}}}
    with pytest.raises(LanguageError, match=r"'fleet' adds a term to 'injection' and reads it"):
        merge({'balance': BALANCE, 'fleet': reads_itself, **others})


def test_a_cased_contributor_is_refused_by_merge():
    cased = {
        **DEMAND,
        'expressions': {
            'injection': {
                'dims': ['snapshot', 'bus'],
                'cases': {'peak': {'when': 'load > 5', 'expression': '-load'}},
                'otherwise': '0',
            }
        },
    }
    assert to_spec(cased), 'nothing in the file alone says it is a term'
    with pytest.raises(LanguageError, match=r"'demand' adds a term to 'injection' written as `cases:`"):
        merge({'balance': BALANCE, 'demand': cased, 'fleet': FLEET})


def test_a_marked_sum_nothing_adds_to_stays_under_given():
    """Zero would leave the balance a row with no variable, which the language refuses."""
    composed = merge({'balance': BALANCE, 'other': {'dimensions': DIMS}})
    assert composed.program.given.expressions['injection'].additive


def test_a_patch_replaces_a_term_rather_than_adding_one():
    """`override` edits what is there; a new term is a new fragment for `merge`."""
    laid = override(DEMAND, {'double': {'expressions': {'injection': '-2 * load'}}})
    assert laid.expressions['injection'].expression == '-2 * load'


# ---------------------------------------------------------------------------
# printing
# ---------------------------------------------------------------------------


def test_the_reader_s_legend_says_other_files_add_to_it():
    given = to_markdown(BALANCE).split('#### Given')[1]
    assert 'a sum other files add terms to' in given


def test_the_composed_legend_says_other_files_add_to_it():
    definitions = to_markdown(merge({'fleet': FLEET, 'demand': DEMAND, 'balance': BALANCE})).split('#### Definitions')[
        1
    ]
    assert 'a sum other files add terms to' in definitions


@pytest.mark.parametrize('fmt', sorted(FORMATS))
def test_a_reader_and_a_composition_print_in_every_format(fmt):
    assert typeset(BALANCE, fmt), f'{fmt} rendered nothing for the reader'
    assert typeset(merge({'fleet': FLEET, 'demand': DEMAND, 'balance': BALANCE}), fmt), f'{fmt}: the composition'
