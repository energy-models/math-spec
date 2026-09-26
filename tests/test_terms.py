# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""A named expression several files add terms to.

A balance reads what every component puts into a bus, and a component file
says what it puts there: a named expression of its own, which the `term:` on
its `given: expressions:` entry names. The file reads the name as the whole
sum, alone and composed. `merge` defines the name as the definition one
fragment writes, if any, plus every term by name, and keeps each term, so
nothing has to declare that the name is a sum.
"""

from __future__ import annotations

import pytest

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
from mathspec.program import Named, Variable, walk
from tests.fixtures import BALANCE, BUS_DIMS, BUS_FRAME, INJECTION, NETWORK

#: A generator fleet: what it puts in is its term.
FLEET = {
    'dimensions': {**BUS_DIMS, 'generator': {'dtype': 'str'}},
    'relations': {'gen_bus': {'key': 'generator', 'values': 'bus'}},
    'variables': {'gen_p': {'dims': ['snapshot', 'generator'], 'bounds': {'lower': 0}}},
    'given': {'expressions': {'injection': {'dims': BUS_FRAME, 'term': 'generator_injection'}}},
    'expressions': {
        'generator_injection': {
            'expression': 'sum(gen_p, by=gen_bus, over=generator, into=bus)',
            'description': 'what the generators put in',
        }
    },
    'objective': {'sense': 'minimize', 'expression': 'sum(gen_p)'},
}

#: A demand, subtracting what it draws.
DEMAND = {
    'dimensions': BUS_DIMS,
    'parameters': {'load': {'dims': BUS_FRAME}},
    'given': {'expressions': {'injection': {'dims': BUS_FRAME, 'term': 'demand_injection'}}},
    'expressions': {'demand_injection': '-load'},
}

#: A store, added in a second merge.
STORAGE = {
    'dimensions': {**BUS_DIMS, 'store': {'dtype': 'str'}},
    'relations': {'store_bus': {'key': 'store', 'values': 'bus'}},
    'variables': {'store_p': {'dims': ['snapshot', 'store']}},
    'given': {'expressions': {'injection': {'dims': BUS_FRAME, 'term': 'store_injection'}}},
    'expressions': {'store_injection': 'sum(store_p, by=store_bus, over=store, into=bus)'},
}

#: A network that defines the injection with a body of its own, its slack, and reads it.
SLACKED = {
    'dimensions': BUS_DIMS,
    'variables': {'slack': {'dims': BUS_FRAME}},
    'expressions': {'injection': {'expression': 'slack', 'description': 'the slack, and what the components add'}},
    'constraints': {'balance': {'dims': BUS_FRAME, 'expression': 'injection == 0'}},
}


def _demand(term: str = 'demand_injection', body: object = '-load', **fields: object) -> dict[str, object]:
    """A demand whose `injection` entry names *term*, with *body* as `demand_injection` and *fields* on the entry."""
    return {
        **DEMAND,
        'given': {'expressions': {'injection': {'dims': BUS_FRAME, 'term': term, **fields}}},
        'expressions': {'demand_injection': body},
    }


# ---------------------------------------------------------------------------
# one file
# ---------------------------------------------------------------------------


def test_an_empty_sum_loads_alone_and_reads_as_a_column():
    """The owner declares the name with a frame and no body; alone, its math reads a column nothing defines yet."""
    program = to_spec(NETWORK).program
    assert 'injection' not in program.expressions, 'no body, so no definition'
    sum_ = program.given.expressions['injection']
    assert sum_.owned and sum_.dims == ('snapshot', 'bus') and sum_.description == INJECTION
    assert program.constraints['balance'].dims == ('snapshot', 'bus'), 'the row reads it over the frame'


def test_an_empty_sum_needs_a_frame():
    with pytest.raises(LanguageError, match=r'this has neither.*An entry with a `dims:` and no body is a sum'):
        to_spec({**NETWORK, 'expressions': {'injection': {'description': INJECTION}}})


def test_an_empty_sum_round_trips():
    assert to_spec(NETWORK).to_dict()['expressions']['injection'] == {'dims': BUS_FRAME, 'description': INJECTION}


def test_the_advice_says_other_files_fill_the_sum():
    (note,) = [note for note in advice(NETWORK) if note.kind == 'given']
    assert note.subject == 'injection'
    assert 'a sum this file declares and other files add terms to' in note.text
    assert 'merge()' in note.text


def test_a_contributor_loads_alone_and_its_term_is_its_named_expression():
    program = to_spec(FLEET).program
    term = program.given.expressions['injection'].term
    assert isinstance(term, Named)
    assert term.name == 'generator_injection'
    assert any(isinstance(node, Variable) and node.name == 'gen_p' for node in walk(term)), 'resolved in its own file'


def test_a_term_is_read_by_the_math():
    """The sum it lands in is read by a constraint, so it is held to what the math admits."""
    assert to_spec(FLEET).program.expressions['generator_injection'].in_math


def test_a_contributor_reads_the_name_as_the_whole_sum():
    """Alone and composed the file reads one thing, so nothing has to refuse a file that adds and reads."""
    reads = {**FLEET, 'constraints': {'capped': {'dims': BUS_FRAME, 'expression': 'injection <= 10'}}}
    assert to_spec(reads).program.constraints['capped'].dims == ('snapshot', 'bus')
    composed = merge({'network': NETWORK, 'fleet': reads, 'demand': DEMAND})
    assert composed.constraints['capped'].expression == 'injection <= 10'
    assert composed.program.expressions['injection'].in_math, 'composed, the cap reads the sum of every term'


@pytest.mark.parametrize(
    ('spec', 'message'),
    [
        pytest.param(
            _demand(dims=['bus']),
            r"Given expression 'injection': its term carries \['snapshot'\], which its dims \['bus'\] do not",
            id='a-term-wider-than-the-entry',
        ),
        pytest.param(
            _demand(body='injection - load'),
            r"Given expression 'injection': its term 'demand_injection' reads 'injection', the sum the term adds to",
            id='a-term-reading-the-sum-through-its-name',
        ),
        pytest.param(
            _demand(term='-load'),
            r"Given expression 'injection': its term '-load' is no expression this file declares",
            id='a-term-written-inline',
        ),
        pytest.param(
            _demand(term='demand_injecton'),
            r"its term 'demand_injecton' is no expression.*Did you mean 'demand_injection'\?",
            id='a-mistyped-term',
        ),
        pytest.param(
            {**FLEET, 'expressions': {'generator_injection': 'sum(gen_p * gen_p * gen_p, over=generator)'}},
            r"Given expression 'injection'.*degree",
            id='a-term-of-degree-three',
        ),
        pytest.param(
            {**DEMAND, 'expressions': {**DEMAND['expressions'], 'injection': '0'}},
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
    square = {**FLEET, 'expressions': {'generator_injection': 'sum(gen_p * gen_p, over=generator)'}}
    assert to_spec(square).program.given.expressions['injection'].term is not None


def test_the_advice_says_the_file_adds_a_term():
    (note,) = [note for note in advice(DEMAND) if note.kind == 'given']
    assert note.subject == 'injection'
    assert 'adds a term to it' in note.text
    assert 'merge()' in note.text, 'merge completes it, not a host model'


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------


def test_merging_adds_the_terms_by_name_in_fragment_name_order_and_keeps_them():
    composed = merge({'fleet': FLEET, 'demand': DEMAND, 'network': NETWORK})
    assert composed.expressions['injection'].expression == 'demand_injection + generator_injection'
    assert composed.expressions['demand_injection'].expression == '-load', 'each term stays a named expression'
    assert composed.program.expressions['generator_injection'].description == 'what the generators put in'
    assert not composed.given, 'every reading is folded into the definition'


def test_the_order_the_fragments_are_given_in_does_not_reach_the_sum():
    one = merge({'fleet': FLEET, 'demand': DEMAND, 'network': NETWORK})
    other = merge({'network': NETWORK, 'demand': DEMAND, 'fleet': FLEET})
    assert one == other


def test_a_term_is_added_to_the_definition_one_fragment_writes():
    composed = merge({'network': SLACKED, 'fleet': FLEET, 'demand': DEMAND})
    assert composed.expressions['injection'].expression == 'slack + demand_injection + generator_injection'
    assert composed.expressions['injection'].description == 'the slack, and what the components add', (
        'the definition keeps its own description'
    )


def test_the_file_that_defines_the_name_reads_the_extended_sum_once_composed():
    """A contributor decides alone. The defining file does not opt in, and whoever composes answers for the sum."""
    assert to_spec(SLACKED).expressions['injection'].expression == 'slack'
    composed = merge({'network': SLACKED, 'demand': DEMAND})
    assert composed.constraints['balance'].expression == 'injection == 0'
    assert composed.expressions['injection'].expression == 'slack + demand_injection'


def test_a_definition_that_is_more_than_a_name_is_bracketed():
    network = {**SLACKED, 'expressions': {'injection': 'slack - slack / 2'}}
    composed = merge({'network': network, 'demand': DEMAND})
    assert composed.expressions['injection'].expression == '(slack - slack / 2) + demand_injection'


def test_the_sum_takes_the_readers_description():
    composed = merge({'fleet': FLEET, 'demand': DEMAND, 'network': NETWORK})
    assert composed.program.expressions['injection'].description == INJECTION


def test_two_readers_that_word_the_sum_apart_give_it_the_first_wording_in_name_order():
    """The sum once took the wording of whichever reader was passed first."""
    capped = {**BALANCE, 'given': {'expressions': {'injection': {'dims': BUS_FRAME, 'description': 'a cap'}}}}
    capped = {**capped, 'constraints': {'capped': {'dims': BUS_FRAME, 'expression': 'injection <= 10'}}}
    for fragments in (
        {'capped': capped, 'network': NETWORK, 'fleet': FLEET},
        {'network': NETWORK, 'capped': capped, 'fleet': FLEET},
    ):
        assert merge(fragments).expressions['injection'].description == INJECTION, "the wording of 'balance'"


def test_a_composed_spec_takes_more_terms_in_a_second_merge():
    """A composed definition is one a fragment wrote, so a later term adds to it like any other."""
    shipped = merge({'network': NETWORK, 'demand': DEMAND, 'fleet': FLEET})
    extended = merge({'shipped': shipped, 'storage': STORAGE})
    assert extended.expressions['injection'].expression == (
        '(demand_injection + generator_injection) + store_injection'
    )


def test_a_cased_term_is_added_like_any_other():
    """The sum names the term, so how the term is written is its own file's business."""
    cased = _demand(
        body={
            'dims': BUS_FRAME,
            'cases': {'peak': {'when': 'load > 5', 'expression': '-load'}},
            'otherwise': '0',
        }
    )
    composed = merge({'network': NETWORK, 'demand': cased, 'fleet': FLEET})
    assert composed.expressions['injection'].expression == 'demand_injection + generator_injection'
    assert composed.program.expressions['demand_injection'].in_math


@pytest.mark.parametrize(
    ('fragments', 'message'),
    [
        pytest.param(
            {'fleet': FLEET, 'demand': DEMAND},
            r"fragments 'demand' and 'fleet' add a term to 'injection', which no fragment declares\. "
            r'.*or fix the spelling\.$',
            id='terms-and-nothing-else-with-no-near-miss',
        ),
        pytest.param(
            {
                'network': NETWORK,
                'fleet': {**FLEET, 'given': {'expressions': {'injecton': FLEET['given']['expressions']['injection']}}},
            },
            r"fragment 'fleet' adds a term to 'injecton', which no fragment.*Did you mean 'injection'\?",
            id='a-mistyped-name',
        ),
    ],
)
def test_terms_that_land_on_no_name_are_refused(fragments, message):
    """Merge fills or extends a block a file declared; it never invents a name, which is what a typo would ask for."""
    with pytest.raises(LanguageError, match=message):
        merge(fragments)


def test_a_reading_is_no_place_for_a_term_to_land():
    """A file that reads the name, or uses it in its own math, has not declared it; only an `expressions:` block has."""
    capped = {**FLEET, 'constraints': {'capped': {'dims': BUS_FRAME, 'expression': 'injection <= 10'}}}
    for fragments in ({'fleet': capped, 'demand': DEMAND}, {'balance': BALANCE, 'demand': DEMAND}):
        with pytest.raises(LanguageError, match=r'which no fragment declares'):
            merge(fragments)


def test_the_composed_sum_keeps_the_owner_s_frame():
    """The frame the owner declared holds the terms to it when the composed spec loads."""
    composed = merge({'network': NETWORK, 'fleet': FLEET, 'demand': DEMAND})
    assert composed.expressions['injection'].dims == BUS_FRAME
    narrow = {**NETWORK, 'expressions': {'injection': {'dims': ['bus'], 'description': INJECTION}}}
    narrow = {**narrow, 'constraints': {'balance': {'dims': ['bus'], 'expression': 'injection == 0'}}}
    with pytest.raises(LanguageError, match=r"the body carries dims \['snapshot'\] outside the dims: \['bus'\]"):
        merge({'network': narrow, 'fleet': FLEET})


def test_one_term_alone_is_its_name():
    composed = merge({'network': NETWORK, 'storage': STORAGE})
    assert composed.expressions['injection'].expression == 'store_injection'


def test_two_definitions_collide_and_the_message_names_the_term():
    other = {
        'dimensions': BUS_DIMS,
        'variables': {'other_slack': {'dims': BUS_FRAME}},
        'expressions': {'injection': 'other_slack'},
        'constraints': {'other_balance': {'dims': BUS_FRAME, 'expression': 'injection == 0'}},
    }
    with pytest.raises(LanguageError) as raised:
        merge({'network': SLACKED, 'other': other})
    message = str(raised.value)
    assert "both declare the expression 'injection'" in message
    assert '`term:` under `given: expressions:`' in message


def test_two_terms_of_one_name_collide():
    """A term is an ordinary named expression, so two fragments name theirs apart."""
    twin = {**FLEET, 'expressions': {'demand_injection': FLEET['expressions']['generator_injection']}}
    twin = {**twin, 'given': {'expressions': {'injection': {'dims': BUS_FRAME, 'term': 'demand_injection'}}}}
    with pytest.raises(
        LanguageError,
        match=r"both declare the expression 'demand_injection', which a fragment adds to 'injection' as a term\. "
        r"A term shares one namespace.*name each fragment's term apart",
    ):
        merge({'network': NETWORK, 'demand': DEMAND, 'fleet': twin})


def test_a_cased_definition_a_term_adds_to_is_refused():
    cased = {
        **SLACKED,
        'parameters': {'on': {'dims': BUS_FRAME, 'dtype': 'bool'}},
        'expressions': {
            'injection': {'dims': BUS_FRAME, 'cases': {'on': {'when': 'on', 'expression': 'slack'}}, 'otherwise': '0'}
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
    composed = merge({'network': NETWORK, 'demand': flat, 'fleet': FLEET})
    assert composed.program.expressions['injection'].dims == ('snapshot', 'bus')


def test_a_definition_over_a_dimension_the_readers_do_not_state_is_refused():
    wide = {
        **SLACKED,
        'dimensions': {**BUS_DIMS, 'carrier': {'dtype': 'str'}},
        'variables': {'slack': {'dims': [*BUS_FRAME, 'carrier']}},
    }
    wide = {**wide, 'constraints': {'balance': {'dims': [*BUS_FRAME, 'carrier'], 'expression': 'injection == 0'}}}
    with pytest.raises(
        LanguageError,
        match=r"'demand' reads the given expression 'injection' as .*'network' introduces it over \['bus', 'carrier', 'snapshot'\]",
    ):
        merge({'network': wide, 'demand': DEMAND})


def test_a_patch_changes_a_term_by_its_name_and_null_drops_it():
    doubled = override(DEMAND, {'double': {'expressions': {'demand_injection': '-2 * load'}}})
    assert doubled.expressions['demand_injection'].expression == '-2 * load'
    reader = override(DEMAND, {'quiet': {'given': {'expressions': {'injection': {'term': None}}}}})
    assert reader.given.expressions['injection'].term is None, 'the entry is a plain reading again'


# ---------------------------------------------------------------------------
# printing
# ---------------------------------------------------------------------------


def test_the_legend_names_the_term_the_file_adds():
    given = to_markdown(DEMAND).split('#### Given')[1]
    assert 'an expression this file adds `demand_injection` to' in given


def test_the_owner_s_sum_prints_as_a_definition_with_no_body():
    """The owner declares the name, so it prints under Definitions as ``symbol = ⋯``, and not under Given."""
    rendered = to_markdown(NETWORK)
    assert '#### Given' not in rendered, 'the file declares the sum rather than reading one another file defines'
    assert '`injection` over' in rendered.split('#### Definitions')[1]
    assert typeset_declaration(NETWORK, 'injection', 'latex') == (
        r'\mathit{injection}_{t,b} = \cdots \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B}'
    )


@pytest.mark.parametrize('spec', [BALANCE, FLEET], ids=['a-reader', 'a-contributor'])
def test_a_given_expression_prints_no_line_of_its_own(spec):
    """The term prints as the definition it is; the name it adds to prints in the legend."""
    with pytest.raises(
        LanguageError, match=r"'injection' is a given expression, and a given declaration prints no line"
    ):
        typeset_declaration(spec, 'injection', 'latex')


def test_the_composed_sum_prints_its_terms_by_name():
    composed = merge({'fleet': FLEET, 'demand': DEMAND, 'network': NETWORK})
    assert typeset_declaration(composed, 'injection', 'typst', inline_expressions=False) == (
        'italic("injection")_(t,b) = upright("demand_injection")_(t,b) + italic("generator_injection")_(t,b) '
        'quad forall t in cal(T), b in cal(B)'
    )


@pytest.mark.parametrize('fmt', sorted(FORMATS))
def test_a_contributor_and_a_composition_print_in_every_format(fmt):
    assert typeset(DEMAND, fmt), f'{fmt} rendered nothing for the contributor'
    assert typeset(merge({'fleet': FLEET, 'demand': DEMAND, 'network': NETWORK}), fmt), f'{fmt}: the composition'
