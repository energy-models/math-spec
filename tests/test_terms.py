# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""A named expression several files add terms to.

A balance reads what every component puts into a bus, and a component file
says what it puts there: a `term:` on its `given: expressions:` entry. The file
reads the name as the whole sum, alone and composed. `merge` defines the name
as the definition one fragment writes, if any, plus every term, so nothing
has to declare that the name is a sum.
"""

from __future__ import annotations

import pytest

import mathspec as ms
from mathspec import (
    FORMATS,
    LanguageError,
    advice,
    merge,
    override,
    to_markdown,
    to_spec,
    typeset,
    typeset_declaration,
)
from mathspec.program import Variable, walk

DIMS = {'snapshot': {'dtype': 'int'}, 'bus': {'dtype': 'str'}}
FRAME = ['snapshot', 'bus']
INJECTION = 'what the components put into a bus'

#: The balance: it reads `injection` over its frame, and adds nothing to it.
BALANCE = {
    'dimensions': DIMS,
    'given': {'expressions': {'injection': {'dims': FRAME, 'description': INJECTION}}},
    'constraints': {'balance': {'dims': FRAME, 'expression': 'injection == 0'}},
}

#: A generator fleet: what it puts in is its term.
FLEET = {
    'dimensions': {**DIMS, 'generator': {'dtype': 'str'}},
    'relations': {'gen_bus': {'key': 'generator', 'values': 'bus'}},
    'variables': {'gen_p': {'dims': ['snapshot', 'generator'], 'bounds': {'lower': 0}}},
    'given': {
        'expressions': {'injection': {'dims': FRAME, 'term': 'sum(gen_p, by=gen_bus, over=generator, into=bus)'}}
    },
    'objective': {'sense': 'minimize', 'expression': 'sum(gen_p)'},
}

#: A demand, subtracting what it draws.
DEMAND = {
    'dimensions': DIMS,
    'parameters': {'load': {'dims': FRAME}},
    'given': {'expressions': {'injection': {'dims': FRAME, 'term': '-load'}}},
}

#: A store, added in a second merge.
STORAGE = {
    'dimensions': {**DIMS, 'store': {'dtype': 'str'}},
    'relations': {'store_bus': {'key': 'store', 'values': 'bus'}},
    'variables': {'store_p': {'dims': ['snapshot', 'store']}},
    'given': {
        'expressions': {'injection': {'dims': FRAME, 'term': 'sum(store_p, by=store_bus, over=store, into=bus)'}}
    },
}

#: A network that defines the injection itself, as its slack, and reads it.
NETWORK = {
    'dimensions': DIMS,
    'variables': {'slack': {'dims': FRAME}},
    'expressions': {'injection': {'expression': 'slack', 'description': 'the slack, and what the components add'}},
    'constraints': {'balance': {'dims': FRAME, 'expression': 'injection == 0'}},
}


def _given(**fields: object) -> dict[str, object]:
    """A demand whose `injection` entry says *fields*."""
    return {**DEMAND, 'given': {'expressions': {'injection': {'dims': FRAME, 'term': '-load', **fields}}}}


# ---------------------------------------------------------------------------
# one file
# ---------------------------------------------------------------------------


def test_a_contributor_loads_alone_and_carries_its_term_resolved():
    program = to_spec(FLEET).program
    term = program.given.expressions['injection'].term
    assert term is not None
    assert any(isinstance(node, Variable) and node.name == 'gen_p' for node in walk(term)), 'resolved in its own file'
    assert not program.expressions, 'a term is not a definition'


def test_a_contributor_reads_the_name_as_the_whole_sum():
    """Alone and composed the file reads one thing, so nothing has to refuse a file that adds and reads."""
    reads = {**FLEET, 'constraints': {'capped': {'dims': FRAME, 'expression': 'injection <= 10'}}}
    assert to_spec(reads).program.constraints['capped'].dims == ('snapshot', 'bus')
    composed = merge({'balance': BALANCE, 'fleet': reads, 'demand': DEMAND})
    assert composed.constraints['capped'].expression == 'injection <= 10'
    assert composed.program.expressions['injection'].in_math, 'composed, the cap reads the sum of every term'


@pytest.mark.parametrize(
    ('spec', 'message'),
    [
        pytest.param(
            _given(dims=['bus']),
            r"Given expression 'injection': its term carries \['snapshot'\], which its dims \['bus'\] do not",
            id='a-term-wider-than-the-entry',
        ),
        pytest.param(
            _given(term='injection - load'),
            r"Given expression 'injection': its term reads 'injection', the sum the term adds to",
            id='a-term-reading-the-sum',
        ),
        pytest.param(
            _given(term='-lod'),
            r"Given expression 'injection': 'lod' not found",
            id='a-term-that-does-not-load',
        ),
        pytest.param(
            {**FLEET, 'given': {'expressions': {'injection': {'dims': FRAME, 'term': 'sum(gen_p * gen_p * gen_p)'}}}},
            r"Given expression 'injection'.*degree",
            id='a-term-of-degree-three',
        ),
        pytest.param(
            {**DEMAND, 'expressions': {'injection': '0'}},
            r"Given expression 'injection' collides with the named expression",
            id='a-term-beside-a-definition',
        ),
    ],
)
def test_what_a_term_may_not_be_is_refused_at_load(spec, message):
    with pytest.raises(LanguageError, match=message):
        to_spec(spec)


def test_a_term_may_be_quadratic():
    """A term is held to what an objective or a constraint admits, since one of them reads the sum."""
    square = {**FLEET, 'given': {'expressions': {'injection': {'dims': FRAME, 'term': 'sum(gen_p * gen_p)'}}}}
    assert to_spec(square).program.given.expressions['injection'].term is not None


def test_the_advice_says_the_file_adds_a_term():
    (note,) = [note for note in advice(DEMAND) if note.kind == 'given']
    assert note.subject == 'injection'
    assert 'adds a term to it' in note.text
    assert 'merge()' in note.text, 'merge completes it, not a host model'


def test_the_canonical_form_normalises_a_term():
    one, other = (
        {**DEMAND, 'given': {'expressions': {'injection': {'dims': FRAME, 'term': text}}}}
        for text in ('load + load', 'load + load')
    )
    other['given']['expressions']['injection']['term'] = '(load) + (load)'
    assert ms.to_spec(one).to_yaml(canonical=True) == ms.to_spec(other).to_yaml(canonical=True)


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------


def test_merging_defines_the_name_as_the_terms_in_fragment_name_order():
    composed = merge({'fleet': FLEET, 'demand': DEMAND, 'balance': BALANCE})
    assert composed.expressions['injection'].expression == (
        '(-load) + (sum(gen_p, by=gen_bus, over=generator, into=bus))'
    )
    assert not composed.given, 'every reading is folded into the definition'
    assert not composed.program.given


def test_the_order_the_fragments_are_given_in_does_not_reach_the_sum():
    one = merge({'fleet': FLEET, 'demand': DEMAND, 'balance': BALANCE})
    other = merge({'balance': BALANCE, 'demand': DEMAND, 'fleet': FLEET})
    assert one == other


def test_a_term_is_added_to_the_definition_one_fragment_writes():
    composed = merge({'network': NETWORK, 'fleet': FLEET, 'demand': DEMAND})
    assert composed.expressions['injection'].expression == (
        '(slack) + (-load) + (sum(gen_p, by=gen_bus, over=generator, into=bus))'
    )
    assert composed.expressions['injection'].description == 'the slack, and what the components add', (
        'the definition keeps its own description'
    )


def test_the_sum_takes_the_readers_description():
    composed = merge({'fleet': FLEET, 'demand': DEMAND, 'balance': BALANCE})
    assert composed.program.expressions['injection'].description == INJECTION


def test_a_composed_spec_takes_more_terms_in_a_second_merge():
    """A composed definition is one a fragment wrote, so a later term adds to it like any other."""
    shipped = merge({'balance': BALANCE, 'demand': DEMAND, 'fleet': FLEET})
    extended = merge({'shipped': shipped, 'storage': STORAGE})
    assert extended.expressions['injection'].expression.startswith('((-load) + (sum(gen_p')
    assert 'store_p' in extended.expressions['injection'].expression


def test_terms_alone_define_a_name_nothing_reads():
    composed = merge({'fleet': FLEET, 'demand': DEMAND})
    assert composed.expressions['injection'].expression == (
        '(-load) + (sum(gen_p, by=gen_bus, over=generator, into=bus))'
    )
    assert not composed.program.expressions['injection'].in_math


def test_one_term_alone_is_carried_as_written():
    composed = merge({'balance': BALANCE, 'storage': STORAGE})
    assert composed.expressions['injection'].expression == 'sum(store_p, by=store_bus, over=store, into=bus)'


def test_two_definitions_collide_and_the_message_names_the_term():
    other = {
        'dimensions': DIMS,
        'variables': {'other_slack': {'dims': FRAME}},
        'expressions': {'injection': 'other_slack'},
        'constraints': {'other_balance': {'dims': FRAME, 'expression': 'injection == 0'}},
    }
    with pytest.raises(LanguageError) as raised:
        merge({'network': NETWORK, 'other': other})
    message = str(raised.value)
    assert "both declare the expression 'injection'" in message
    assert '`term:` under `given: expressions:`' in message


def test_a_cased_definition_a_term_adds_to_is_refused():
    cased = {
        **NETWORK,
        'parameters': {'on': {'dims': FRAME, 'dtype': 'bool'}},
        'expressions': {
            'injection': {'dims': FRAME, 'cases': {'on': {'when': 'on', 'expression': 'slack'}}, 'otherwise': '0'}
        },
    }
    with pytest.raises(LanguageError, match=r"'cased' defines 'injection' as `cases:`, and fragment 'demand' adds"):
        merge({'cased': cased, 'demand': DEMAND})


def test_two_readers_that_disagree_about_the_frame_are_refused():
    narrow = {**BALANCE, 'given': {'expressions': {'injection': {'dims': ['bus']}}}}
    narrow = {**narrow, 'constraints': {'balance': {'dims': ['bus'], 'expression': 'injection == 0'}}}
    with pytest.raises(LanguageError, match=r"say different things about the given expression 'injection'"):
        merge({'balance': narrow, 'fleet': FLEET})


def test_a_term_over_fewer_dimensions_merges_where_another_carries_the_rest():
    flat = {**DEMAND, 'parameters': {'load': {'dims': ['bus']}}}
    composed = merge({'balance': BALANCE, 'demand': flat, 'fleet': FLEET})
    assert composed.program.expressions['injection'].dims == ('snapshot', 'bus')


def test_a_definition_over_a_dimension_the_readers_do_not_state_is_refused():
    wide = {
        **NETWORK,
        'dimensions': {**DIMS, 'carrier': {'dtype': 'str'}},
        'variables': {'slack': {'dims': [*FRAME, 'carrier']}},
    }
    wide = {**wide, 'constraints': {'balance': {'dims': [*FRAME, 'carrier'], 'expression': 'injection == 0'}}}
    with pytest.raises(
        LanguageError, match=r"'demand' reads the given expression 'injection' over \['bus', 'snapshot'\]"
    ):
        merge({'network': wide, 'demand': DEMAND})


def test_a_patch_replaces_a_term_and_null_drops_it():
    doubled = override(DEMAND, {'double': {'given': {'expressions': {'injection': {'term': '-2 * load'}}}}})
    assert doubled.given.expressions['injection'].term == '-2 * load'
    reader = override(DEMAND, {'quiet': {'given': {'expressions': {'injection': {'term': None}}}}})
    assert reader.given.expressions['injection'].term is None, 'the entry is a plain reading again'


# ---------------------------------------------------------------------------
# printing
# ---------------------------------------------------------------------------


def test_the_legend_says_the_file_adds_a_term():
    given = to_markdown(DEMAND).split('#### Given')[1]
    assert 'an expression this file adds a term to' in given


def test_the_term_prints_after_dots_that_stand_for_the_other_files():
    assert typeset_declaration(FLEET, 'injection', 'latex') == (
        r'\mathit{injection}_{t,b} = \cdots + \sum_{g \in \mathcal{G} \,:\, \mathrm{gen\_bus}(g) = b} '
        r'\mathit{gen\_p}_{t,g} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B}'
    )


def test_a_negated_term_prints_as_a_subtraction():
    assert typeset_declaration(DEMAND, 'injection', 'typst') == (
        'italic("injection")_(t,b) = dots.c - upright("load")_(t,b) quad forall t in cal(T), b in cal(B)'
    )


def test_a_reading_with_no_term_still_prints_no_line_of_its_own():
    with pytest.raises(
        LanguageError, match=r"'injection' is a given expression, and a given declaration prints no line"
    ):
        typeset_declaration(BALANCE, 'injection', 'latex')


def test_the_term_prints_under_definitions():
    definitions = to_markdown(DEMAND, legend=False).split('#### Definitions')[1]
    assert r'\cdots - \mathrm{load}' in definitions


@pytest.mark.parametrize('fmt', sorted(FORMATS))
def test_a_contributor_and_a_composition_print_in_every_format(fmt):
    assert typeset(DEMAND, fmt), f'{fmt} rendered nothing for the contributor'
    assert typeset(merge({'fleet': FLEET, 'demand': DEMAND, 'balance': BALANCE}), fmt), f'{fmt}: the composition'
