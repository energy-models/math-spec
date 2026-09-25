# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""What a file reads and does not build: a parameter, a column, a named expression, and a row family.

A fragment reads a column the file beside it introduces, and `merge` folds the
two together, so the composed model carries no trace of the reading. A layer
reads a column, or the dual of a row family, that a model outside the language
holds, so there is nothing to fold into and the program carries the name for a
host model to provide. What both need is that the file stands on its own: it loads,
it lowers, and it prints as math, without the thing that owns what it reads.
"""

from __future__ import annotations

import pytest

from math_spec import FORMATS, LanguageError, advice, merge, to_markdown, to_spec, typeset

#: One component file: it pins the flow at its own port, and the column it
#: pins belongs to another fragment.
SUPPLY = {
    'description': 'A fleet of generators, each on one port.',
    'dimensions': {'snapshot': {'dtype': 'int'}, 'port': {'dtype': 'str'}, 'generator': {'dtype': 'str'}},
    'relations': {'gen_port': {'key': 'generator', 'values': 'port'}},
    'given': {'variables': {'flow': {'dims': ['snapshot', 'port'], 'description': 'what a port puts into its bus'}}},
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

#: The fragment that introduces `flow`, with the bounds and the balance that go with it.
SURFACE = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'port': {'dtype': 'str'}, 'bus': {'dtype': 'str'}},
    'relations': {'port_bus': {'key': 'port', 'values': 'bus'}},
    'variables': {'flow': {'dims': ['snapshot', 'port'], 'bounds': {'lower': -1000, 'upper': 1000}}},
    'constraints': {
        'balance': {'dims': ['snapshot', 'bus'], 'expression': 'sum(flow, by=port_bus, over=port, into=bus) == 0'}
    },
}


def test_given_holds_four_kinds_and_refuses_a_fifth():
    """The section is closed, so a kind nobody has admitted yet is the schema's own refusal."""
    with pytest.raises(LanguageError) as raised:
        to_spec({**SUPPLY, 'given': {'macros': {'twice': {'params': ['x'], 'template': '2 * x'}}}})
    assert 'Valid keys: constraints, expressions, parameters, variables' in str(raised.value), (
        'the refusal names what the block takes'
    )


def test_a_fragment_that_says_what_it_reads_loads_on_its_own():
    spec = to_spec(SUPPLY)
    assert sorted(spec.given.variables) == ['flow'], 'the column it reads is a declaration like any other'
    assert sorted(spec.variables) == ['gen_p'], 'and it is not one of the columns this file introduces'


def test_a_given_name_is_held_to_the_name_rule():
    """`_names_are_names` walks the top-level mappings, and `given:` nests its two one level down."""
    with pytest.raises(LanguageError, match=r"given: variables: 'no-flow' is not a name"):
        to_spec({**SUPPLY, 'given': {'variables': {'no-flow': {'dims': ['snapshot', 'port']}}}})


def test_a_whole_model_writes_no_given_block():
    whole = to_spec({**SUPPLY, 'given': {}, 'constraints': {}})
    assert 'given' not in whole.to_dict(), 'an empty section is an absence, and is left out'


def test_a_fragment_round_trips_through_its_own_data():
    spec = to_spec(SUPPLY)
    assert to_spec(spec.to_dict()) == spec


@pytest.mark.parametrize('fmt', sorted(FORMATS))
def test_a_fragment_prints_as_math_in_every_format(fmt):
    assert typeset(SUPPLY, fmt), f'{fmt} rendered nothing'


def test_the_given_column_prints_under_its_own_heading():
    printed = to_markdown(SUPPLY)
    assert '#### Given' in printed, 'the legend says which symbols the file does not introduce'
    assert '`flow`' in printed.split('#### Given')[1]


def test_a_program_carries_the_column_it_reads_apart_from_the_ones_it_builds():
    """The distinction a builder needs: create this column, or use the one the host model provides."""
    program = to_spec(SUPPLY).program
    assert sorted(program.variables) == ['gen_p'], 'a build reads this group and creates a column for each'
    assert sorted(program.given.variables) == ['flow'], (
        'and uses, for each of these, the column the host model provides'
    )
    assert program.given.variables['flow'].dims == ('snapshot', 'port'), (
        'the frame is what a consumer checks against the host'
    )


def test_what_a_program_reads_is_sealed_like_what_it_builds():
    program = to_spec(SUPPLY).program
    with pytest.raises(TypeError, match='does not support item assignment'):
        program.given.variables['p'] = program.given.variables['flow']


def test_the_advice_says_which_columns_a_consumer_has_to_bind():
    (note,) = [note for note in advice(SUPPLY) if note.kind == 'given']
    assert note.subject == 'flow'


def test_a_given_column_in_the_objective_is_not_advised_unbounded():
    """The unboundedness pass reads a variable's bounds, and a given column's bounds are the owner's."""
    priced = {**SUPPLY, 'constraints': {}, 'objective': {'sense': 'minimize', 'expression': 'sum(flow)'}}
    assert not [note for note in advice(priced) if note.kind == 'unbounded']


def test_a_name_both_introduced_and_given_in_one_file_is_refused():
    both = {**SUPPLY, 'variables': {**SUPPLY['variables'], 'flow': {'dims': ['snapshot', 'port']}}}
    with pytest.raises(LanguageError, match=r"Given variable 'flow' collides with the variable"):
        to_spec(both)


@pytest.mark.parametrize(
    ('block', 'says'),
    [
        pytest.param({'dims': ['snapshot', 'nowhere']}, 'nowhere', id='a-frame-over-an-undeclared-dimension'),
        pytest.param({'dims': ['snapshot', 'snapshot']}, 'twice', id='a-frame-naming-one-dimension-twice'),
        pytest.param({'dims': ['snapshot'], 'bounds': {'lower': 0}}, 'bounds', id='bounds-the-owner-holds'),
        pytest.param({'dims': ['snapshot'], 'where': 'gen_cost > 0'}, 'where', id='a-mask-the-owner-holds'),
    ],
)
def test_a_given_declaration_is_refused_where_it_oversteps(block, says):
    with pytest.raises(LanguageError) as raised:
        to_spec({**SUPPLY, 'given': {'variables': {'flow': block}}})
    assert says in str(raised.value)


def test_an_expression_reads_a_given_column_as_it_reads_any_other():
    """Resolution and the dim algebra see one namespace, so the walk lands on the generator frame."""
    spec = to_spec(SUPPLY)
    assert spec.constraints['gen_injects'].dims == ['snapshot', 'generator']


def test_merging_folds_the_given_declaration_into_the_one_that_introduces_it():
    spec = merge({'surface': SURFACE, 'supply': SUPPLY})
    assert not spec.given, 'the expectation is spent once the column is in the composition'
    assert sorted(spec.variables) == ['flow', 'gen_p']
    assert spec.variables['flow'].bounds.lower == -1000, "the introducer's declaration is the one that survives"
    assert sorted(to_spec(spec).program.variables) == ['flow', 'gen_p'], 'a composed library lowers like any model'


@pytest.mark.parametrize(
    'reads',
    [
        pytest.param({'dims': ['snapshot', 'port']}, id='the-frame-alone'),
        pytest.param({'dims': ['snapshot', 'port'], 'domain': 'continuous'}, id='the-domain-the-introducer-defaults'),
        pytest.param({'dims': ['snapshot', 'port'], 'description': 'the flow, in my words'}, id='its-own-prose'),
    ],
)
def test_a_given_declaration_may_say_less_than_the_introducer(reads):
    """Bounds are the introducer's, so the reader states the frame and stops."""
    composed = merge({'surface': SURFACE, 'supply': {**SUPPLY, 'given': {'variables': {'flow': reads}}}})
    assert composed.variables['flow'].bounds.upper == 1000


#: A fragment that reads `flow` over `port` alone, and loads so: it only
#: declares what it reads.
PORTS_ONLY = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'port': {'dtype': 'str'}},
    'given': {'variables': {'flow': {'dims': ['port']}}},
}


@pytest.mark.parametrize(
    'misread',
    [
        pytest.param(PORTS_ONLY, id='another-frame'),
        pytest.param(
            {**SUPPLY, 'given': {'variables': {'flow': {'dims': ['snapshot', 'port'], 'domain': 'binary'}}}},
            id='another-domain',
        ),
    ],
)
def test_a_given_declaration_that_disagrees_with_the_introducer_is_refused(misread):
    with pytest.raises(LanguageError, match=r'says the same as the declaration it is folded into, or less') as raised:
        merge({'surface': SURFACE, 'supply': misread})
    message = str(raised.value)
    assert "'supply'" in message and "'surface'" in message, 'both sides of a disagreement are named'


def test_two_fragments_must_read_one_column_the_same_way():
    with pytest.raises(LanguageError, match=r'say different things about the given variable'):
        merge({'supply': SUPPLY, 'other': PORTS_ONLY})


@pytest.mark.parametrize(
    ('given', 'says'),
    [
        pytest.param(
            {'variables': {**SUPPLY['given']['variables'], 'gen_p': {'dims': ['snapshot', 'generator']}}},
            "Given variable 'gen_p' collides with the variable",
            id='a-column-it-builds',
        ),
        pytest.param(
            {**SUPPLY['given'], 'constraints': {'gen_injects': {'dims': ['snapshot', 'generator']}}},
            "Given constraint 'gen_injects' is also declared under 'constraints:'",
            id='a-row-family-it-builds',
        ),
    ],
)
def test_a_fragment_that_reads_what_it_builds_is_refused(given, says):
    """`to_spec` refuses such a file, so a composition refuses it too rather than folding the reading away."""
    with pytest.raises(LanguageError, match=r"fragment 'supply' does not load on its own") as raised:
        merge({'surface': SURFACE, 'supply': {**SUPPLY, 'given': given}})
    assert says in str(raised.value), "the fragment's own refusal names the name it reads twice"


def test_a_given_declaration_nothing_introduces_stays_for_a_consumer_to_bind():
    composed = merge({'supply': SUPPLY, 'other': {'dimensions': {'snapshot': {'dtype': 'int'}}}})
    assert composed.given.variables['flow'].dims == ['snapshot', 'port'], 'a name nothing introduces is still read'
    assert sorted(composed.program.given.variables) == ['flow']


#: A layer over a model this language never sees: it reads a column and the
#: dual of a row family, and adds one constraint of its own.
LAYER = {
    'description': 'A carbon cap laid over a model that already exists.',
    'dimensions': {'snapshot': {'dtype': 'int'}, 'bus': {'dtype': 'str'}},
    'given': {
        'variables': {'p': {'dims': ['snapshot', 'bus']}},
        'constraints': {'balance': {'dims': ['snapshot', 'bus'], 'description': 'the host clears each bus'}},
    },
    'parameters': {'rate': {'dims': ['bus']}},
    'constraints': {'cap': {'dims': [], 'expression': 'sum(p * rate) <= 100'}},
    'expressions': {'price': {'expression': 'dual(balance)'}},
}


def test_a_dual_may_name_a_row_family_this_file_does_not_build():
    spec = to_spec(LAYER)
    assert sorted(spec.given.constraints) == ['balance']
    assert sorted(spec.constraints) == ['cap'], 'the row families it builds are its own, and that is not one'


def test_the_program_carries_the_row_family_a_consumer_binds():
    program = to_spec(LAYER).program
    assert sorted(program.given.constraints) == ['balance']
    assert program.given.constraints['balance'].dims == ('snapshot', 'bus'), (
        'the frame is what a consumer checks against the host'
    )


def test_the_dual_takes_its_frame_from_the_given_declaration():
    """Without the frame the reported expression has no dims, and nothing downstream could shape it."""
    assert to_markdown(LAYER).count(r'\lambda_{\mathrm{balance},t,b}') == 1


def test_a_given_row_family_prints_under_the_given_heading():
    given = to_markdown(LAYER).split('#### Given')[1]
    assert '`balance`' in given
    assert 'reads the dual of' in given, 'the legend says what the file may do with it'


def test_a_row_family_both_built_and_given_is_refused():
    both = {**LAYER, 'constraints': {**LAYER['constraints'], 'balance': {'dims': [], 'expression': 'sum(p) >= 0'}}}
    with pytest.raises(LanguageError, match=r"'balance'.*either built by this file or given to it"):
        to_spec(both)


def test_a_dual_naming_nothing_says_where_to_declare_it():
    mistyped = {**LAYER, 'expressions': {'price': {'expression': 'dual(balnce)'}}}
    with pytest.raises(LanguageError) as raised:
        to_spec(mistyped)
    message = str(raised.value)
    assert "'constraints:'" in message and "'given: constraints:'" in message, (
        'the message names both places the row family could be declared'
    )


@pytest.mark.parametrize(
    ('block', 'says'),
    [
        pytest.param({'dims': [], 'expression': 'sum(p) >= 0'}, 'expression', id='a-body-the-owner-holds'),
        pytest.param({'dims': [], 'sense': '<='}, 'sense', id='a-sense-nothing-here-could-check'),
    ],
)
def test_a_given_row_family_is_refused_where_it_oversteps(block, says):
    with pytest.raises(LanguageError) as raised:
        to_spec({**LAYER, 'given': {**LAYER['given'], 'constraints': {'balance': block}}})
    assert says in str(raised.value)


def test_merging_folds_a_row_family_into_the_file_that_builds_it():
    builder = {
        'dimensions': {'snapshot': {'dtype': 'int'}, 'bus': {'dtype': 'str'}},
        'variables': {'p': {'dims': ['snapshot', 'bus'], 'bounds': {'lower': 0}}},
        'constraints': {'balance': {'dims': ['snapshot', 'bus'], 'expression': 'p >= 0'}},
    }
    composed = merge({'builder': builder, 'layer': LAYER})
    assert not composed.given
    program = composed.program
    assert sorted(program.constraints) == ['balance', 'cap']
    assert not program.given.constraints, 'nothing is left for a host model to provide'


def test_the_advice_names_every_declaration_a_consumer_has_to_bind():
    subjects = {note.subject for note in advice(LAYER) if note.kind == 'given'}
    assert subjects == {'p', 'balance'}, 'both the column and the row family are named'


#: `port` is named by nothing but the given column's frame, and `bus` by
#: nothing but the given row family's, so each is in use only through a
#: declaration this file does not build.
REACHED_ONLY_BY_A_GIVEN_FRAME = {
    'dimensions': {'g': {'dtype': 'str'}, 'port': {'dtype': 'str'}, 'bus': {'dtype': 'str'}},
    'given': {'variables': {'flow': {'dims': ['port']}}, 'constraints': {'balance': {'dims': ['bus']}}},
    'variables': {'p': {'dims': ['g'], 'bounds': {'lower': 0, 'upper': 1}}},
    'constraints': {'tie': {'dims': ['g'], 'expression': 'p >= sum(flow, over=port)'}},
    'expressions': {'price': {'expression': 'dual(balance)'}},
}


def test_a_dimension_only_a_given_declaration_indexes_is_in_use():
    """The never-an-axis pass reads the frames a build emits, and these two are in neither."""
    unreached = {note.subject for note in advice(REACHED_ONLY_BY_A_GIVEN_FRAME) if note.kind == 'never-an-axis'}
    assert not unreached, 'a dimension a given column or row family is indexed by is used'


# ---------------------------------------------------------------------------
# a parameter another file declares
# ---------------------------------------------------------------------------

#: A cost file: it reads the fleet's output and its price, and declares
#: neither. The price is data the fleet file declares.
PRICED = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'generator': {'dtype': 'str'}},
    'given': {
        'parameters': {
            'gen_cost': {'dims': ['generator'], 'description': 'what one unit of output costs'},
            'gen_on': {'dims': ['generator'], 'dtype': 'bool'},
        },
        'variables': {'gen_p': {'dims': ['snapshot', 'generator']}},
    },
    'parameters': {'weight': {'dims': ['snapshot']}},
    'objective': {'sense': 'minimize', 'expression': 'sum(gen_p * gen_cost * weight)'},
    'constraints': {
        'off_units_idle': {'dims': ['snapshot', 'generator'], 'where': 'not gen_on', 'expression': 'gen_p <= 0'}
    },
}


def test_a_fragment_reads_a_parameter_it_does_not_declare():
    spec = to_spec(PRICED)
    assert sorted(spec.given.parameters) == ['gen_cost', 'gen_on']
    assert sorted(spec.parameters) == ['weight'], 'the data it declares is its own, and the price is not'


def test_a_program_carries_the_parameter_it_reads_apart_from_the_ones_it_declares():
    program = to_spec(PRICED).program
    assert sorted(program.parameters) == ['weight']
    assert program.given.parameters['gen_on'].dims == ('generator',)
    assert program.given.parameters['gen_on'].dtype == 'bool', 'a where compares against the dtype the reader states'


def test_a_given_parameter_is_read_in_a_bound_as_any_parameter_is():
    bounded = {
        **PRICED,
        'given': {**PRICED['given'], 'parameters': {'gen_p_max': {'dims': ['generator']}}},
        'variables': {'spill': {'dims': ['snapshot', 'generator'], 'bounds': {'lower': 0, 'upper': 'gen_p_max'}}},
        'constraints': {},
        'objective': {'sense': 'minimize', 'expression': 'sum(spill + gen_p)'},
    }
    assert to_spec(bounded).variables['spill'].bounds.upper == 'gen_p_max'


def test_a_given_parameter_prints_under_the_given_heading():
    given = to_markdown(PRICED).split('#### Given')[1]
    assert '`gen_cost`' in given and '`gen_on`' in given


@pytest.mark.parametrize(
    ('block', 'says'),
    [
        pytest.param({'dims': ['nowhere']}, 'nowhere', id='a-frame-over-an-undeclared-dimension'),
        pytest.param({'dims': ['generator'], 'default': 0}, 'default', id='a-field-a-parameter-does-not-have'),
    ],
)
def test_a_given_parameter_is_refused_where_it_oversteps(block, says):
    with pytest.raises(LanguageError) as raised:
        to_spec({**PRICED, 'given': {**PRICED['given'], 'parameters': {'gen_cost': block}}})
    assert says in str(raised.value)


def test_a_parameter_both_declared_and_given_in_one_file_is_refused():
    both = {**PRICED, 'parameters': {**PRICED['parameters'], 'gen_cost': {'dims': ['generator']}}}
    with pytest.raises(LanguageError, match=r"Given parameter 'gen_cost' collides with the parameter"):
        to_spec(both)


#: The fleet file, which declares the data `PRICED` reads.
FLEET = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'generator': {'dtype': 'str'}},
    'parameters': {
        'gen_cost': {'dims': ['generator']},
        'gen_on': {'dims': ['generator'], 'dtype': 'bool'},
        'gen_p_max': {'dims': ['generator']},
    },
    'variables': {'gen_p': {'dims': ['snapshot', 'generator'], 'bounds': {'lower': 0, 'upper': 'gen_p_max'}}},
}


def test_merging_folds_a_given_parameter_into_the_declaration():
    composed = merge({'fleet': FLEET, 'cost': PRICED})
    assert not composed.given, 'every reading is spent once the fleet is in the composition'
    assert sorted(composed.parameters) == ['gen_cost', 'gen_on', 'gen_p_max', 'weight']


@pytest.mark.parametrize(
    'misread',
    [
        pytest.param({'dims': ['snapshot', 'generator']}, id='another-frame'),
        pytest.param({'dims': ['generator'], 'dtype': 'int'}, id='another-dtype'),
    ],
)
def test_a_given_parameter_that_disagrees_with_the_declaration_is_refused(misread):
    cost = {**PRICED, 'given': {**PRICED['given'], 'parameters': {**PRICED['given']['parameters'], 'gen_on': misread}}}
    with pytest.raises(LanguageError, match=r"reads the given parameter 'gen_on' as"):
        merge({'fleet': FLEET, 'cost': cost})


def test_a_given_parameter_nothing_declares_stays_for_the_data_to_bind():
    composed = merge({'cost': PRICED, 'other': {'dimensions': {'snapshot': {'dtype': 'int'}}}})
    assert sorted(composed.program.given.parameters) == ['gen_cost', 'gen_on']


def test_the_advice_names_a_given_parameter_as_data_a_consumer_binds():
    notes = {note.subject: note.text for note in advice(PRICED) if note.kind == 'given'}
    assert 'gen_cost' in notes and 'parameter' in notes['gen_cost']


# ---------------------------------------------------------------------------
# a named expression another file defines
# ---------------------------------------------------------------------------

#: A balance file: it clears each bus of what every component injects, and
#: defines none of the injections.
BALANCE = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'bus': {'dtype': 'str'}},
    'given': {
        'expressions': {'injection': {'dims': ['snapshot', 'bus'], 'description': 'what the components put into a bus'}}
    },
    'constraints': {'balance': {'dims': ['snapshot', 'bus'], 'expression': 'injection == 0'}},
}

#: A component file that defines the injection.
INJECTOR = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'bus': {'dtype': 'str'}, 'generator': {'dtype': 'str'}},
    'relations': {'gen_bus': {'key': 'generator', 'values': 'bus'}},
    'parameters': {'load': {'dims': ['snapshot', 'bus']}},
    'variables': {'gen_p': {'dims': ['snapshot', 'generator'], 'bounds': {'lower': 0}}},
    'expressions': {'injection': {'expression': 'sum(gen_p, by=gen_bus, over=generator, into=bus) - load'}},
    'objective': {'sense': 'minimize', 'expression': 'sum(gen_p)'},
}


def test_a_fragment_reads_an_expression_it_does_not_define():
    spec = to_spec(BALANCE)
    assert sorted(spec.given.expressions) == ['injection']
    assert spec.constraints['balance'].dims == ['snapshot', 'bus'], 'the frame the reader states is the one read'


def test_a_program_carries_the_expression_it_reads_apart_from_the_ones_it_defines():
    program = to_spec(BALANCE).program
    assert not program.expressions
    assert program.given.expressions['injection'].dims == ('snapshot', 'bus')


def test_a_given_expression_prints_under_the_given_heading():
    given = to_markdown(BALANCE).split('#### Given')[1]
    assert '`injection`' in given
    assert 'an expression another file defines' in given, 'the legend says what kind of thing the file reads'


@pytest.mark.parametrize('fmt', sorted(FORMATS))
def test_a_fragment_reading_an_expression_prints_in_every_format(fmt):
    assert typeset(BALANCE, fmt), f'{fmt} rendered nothing'


def test_a_given_expression_is_no_mask():
    """A mask is built before any variable exists, and a given expression may read variables."""
    masked = {**BALANCE, 'constraints': {'balance': {**BALANCE['constraints']['balance'], 'where': 'injection > 0'}}}
    with pytest.raises(LanguageError, match='before variables exist'):
        to_spec(masked)


def test_an_expression_both_defined_and_given_in_one_file_is_refused():
    both = {**BALANCE, 'expressions': {'injection': {'expression': '0'}}}
    with pytest.raises(LanguageError, match=r"Given expression 'injection' collides with the named expression"):
        to_spec(both)


def test_merging_folds_a_given_expression_into_its_definition():
    composed = merge({'balance': BALANCE, 'injector': INJECTOR})
    assert not composed.given
    assert composed.constraints['balance'].expression == 'injection == 0'
    assert composed.program.expressions['injection'].in_math, 'the balance reads the definition once folded'


def test_a_definition_over_a_dimension_the_reader_does_not_state_is_refused():
    """The reader's frame bounds what it reads, so a body carrying more is a disagreement `merge` names."""
    narrow = {**BALANCE, 'given': {'expressions': {'injection': {'dims': ['bus']}}}}
    narrow = {**narrow, 'constraints': {'balance': {'dims': ['bus'], 'expression': 'injection == 0'}}}
    with pytest.raises(LanguageError, match=r"'balance' reads the given expression 'injection' over \['bus'\]"):
        merge({'balance': narrow, 'injector': INJECTOR})


#: An injector whose output does not vary by snapshot: its injection is over `bus` alone.
FLAT_INJECTOR = {
    'dimensions': {'bus': {'dtype': 'str'}, 'generator': {'dtype': 'str'}},
    'relations': {'gen_bus': {'key': 'generator', 'values': 'bus'}},
    'variables': {'gen_p': {'dims': ['generator'], 'bounds': {'lower': 0}}},
    'expressions': {'injection': {'expression': 'sum(gen_p, by=gen_bus, over=generator, into=bus)'}},
    'objective': {'sense': 'minimize', 'expression': 'sum(gen_p)'},
}


def test_a_definition_over_fewer_dimensions_merges_where_the_row_carries_the_rest():
    """The reader's `dims` is an upper bound: a row that carries `snapshot` through another term is sound."""
    demand = {
        **BALANCE,
        'parameters': {'demand': {'dims': ['snapshot', 'bus']}},
        'constraints': {'balance': {'dims': ['snapshot', 'bus'], 'expression': 'injection == demand'}},
    }
    composed = merge({'balance': demand, 'injector': FLAT_INJECTOR})
    assert composed.program.expressions['injection'].dims == ('bus',)


def test_the_composed_load_refuses_a_row_a_narrower_definition_repeats():
    """With nothing else carrying `snapshot`, the row would repeat per snapshot, which the composed model refuses."""
    with pytest.raises(LanguageError, match='repeated across'):
        merge({'balance': BALANCE, 'injector': FLAT_INJECTOR})


def test_a_given_expression_a_sibling_introduces_as_a_variable_is_refused():
    as_column = {
        **INJECTOR,
        'expressions': {},
        'variables': {**INJECTOR['variables'], 'injection': {'dims': ['snapshot', 'bus']}},
    }
    with pytest.raises(
        LanguageError,
        match=r"reads 'injection' as a given expression, where 'injector' introduces it under 'variables:'",
    ):
        merge({'balance': BALANCE, 'injector': as_column})


def test_the_composed_model_holds_a_definition_to_the_rules_of_where_it_is_read():
    """A fragment reads a given expression as a column, so a square of it is quadratic there and quartic once folded."""
    squares = {
        **BALANCE,
        'constraints': {'capped': {'dims': ['snapshot', 'bus'], 'expression': 'injection * injection <= 1'}},
    }
    squared = {
        **INJECTOR,
        'expressions': {'injection': {'expression': 'sum(gen_p * gen_p, by=gen_bus, over=generator, into=bus)'}},
    }
    assert to_spec(squares) and to_spec(squared), 'each file loads on its own'
    with pytest.raises(LanguageError, match='degree'):
        merge({'balance': squares, 'injector': squared})


def test_the_advice_names_a_given_expression():
    notes = {note.subject: note.text for note in advice(BALANCE) if note.kind == 'given'}
    assert 'injection' in notes and 'expression' in notes['injection']
