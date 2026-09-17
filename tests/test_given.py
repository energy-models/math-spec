# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""What a file reads and does not build: a column, and a row family.

Two readings, and each is a model somebody meant. A **fragment** reads a column
the file beside it introduces, and `merge` folds the two together, so the
composed model carries neither the declaration nor any trace of it. A **layer**
reads a column, or the dual of a row family, that a model outside the language
holds — linopy's, say — and there is nothing to fold into, so the program
carries the name and the frame and a consumer binds them.

What both need is that the file stands on its own: it loads, and it prints as
math, without the thing that owns what it reads.
"""

from __future__ import annotations

import pytest

from math_spec import FORMATS, LanguageError, advice, merge, to_markdown, to_program, to_spec, typeset

#: One component file: it pins the flow at its own port, and the column it
#: pins belongs to the surface fragment below.
SUPPLY = {
    'description': 'A fleet of generators, each on one port.',
    'dimensions': {'snapshot': {'dtype': 'int'}, 'port': {'dtype': 'str'}, 'generator': {'dtype': 'str'}},
    'relations': {'gen_port': {'key': 'generator', 'value': 'port'}},
    'given': {'variables': {'flow': {'dims': ['snapshot', 'port'], 'description': 'what a port puts into its bus'}}},
    'parameters': {'gen_cost': {'dims': ['generator']}, 'gen_p_max': {'dims': ['generator']}},
    'variables': {'gen_p': {'dims': ['snapshot', 'generator'], 'bounds': {'lower': 0, 'upper': 'gen_p_max'}}},
    'constraints': {'gen_injects': {'dims': ['snapshot', 'generator'], 'expression': 'at(flow, by=gen_port) == gen_p'}},
    'objective': {'sense': 'minimize', 'expression': 'sum(gen_p * gen_cost)'},
}

#: The fragment that owns `flow`, with the bounds and the balance that go with it.
SURFACE = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'port': {'dtype': 'str'}, 'bus': {'dtype': 'str'}},
    'relations': {'port_bus': {'key': 'port', 'value': 'bus'}},
    'variables': {'flow': {'dims': ['snapshot', 'port'], 'bounds': {'lower': -1000, 'upper': 1000}}},
    'constraints': {'balance': {'dims': ['snapshot', 'bus'], 'expression': 'sum(flow, by=port_bus) == 0'}},
}


def test_given_holds_two_kinds_and_refuses_a_third():
    """The section is closed, so a kind nobody has admitted yet is the schema's own refusal."""
    with pytest.raises(LanguageError) as raised:
        to_spec({**SUPPLY, 'given': {'parameters': {'gen_cost': {'dims': ['generator']}}}})
    assert 'Valid keys: constraints, variables' in str(raised.value), 'the refusal names what the block takes'


def test_a_fragment_that_says_what_it_reads_loads_on_its_own():
    spec = to_spec(SUPPLY)
    assert sorted(spec.given.variables) == ['flow'], 'the column it reads is a declaration like any other'
    assert sorted(spec.variables) == ['gen_p'], 'and it is not one of the columns this file introduces'


@pytest.mark.parametrize('fmt', sorted(FORMATS))
def test_a_fragment_prints_as_math_in_every_format(fmt):
    """The improvement the section exists for: the unit you share is the unit you can read."""
    assert typeset(SUPPLY, fmt), f'{fmt} rendered nothing'


def test_the_given_column_prints_under_its_own_heading():
    printed = to_markdown(SUPPLY)
    assert '#### Given' in printed, 'the legend says which symbols the file does not introduce'
    assert '`flow`' in printed.split('#### Given')[1]


def test_a_program_carries_the_column_it_reads_apart_from_the_ones_it_builds():
    """The distinction a builder needs: create this column, or bind it to one the host already holds."""
    program = to_program(SUPPLY)
    assert sorted(program.variables) == ['gen_p'], 'a build reads this group and creates a column for each'
    assert sorted(program.given.variables) == ['flow'], 'and binds each of these to a column it is given'
    assert program.given.variables['flow'].dims == ('snapshot', 'port'), 'the frame is what a binder checks'


def test_the_advice_says_which_columns_a_consumer_has_to_bind():
    (note,) = [note for note in advice(SUPPLY) if note.kind == 'given']
    assert note.subject == 'flow'


def test_merging_folds_the_given_declaration_into_the_one_that_introduces_it():
    composed = merge({'surface': SURFACE, 'supply': SUPPLY})
    assert 'given' not in composed, 'the expectation is spent once the column is in the composition'
    spec = to_spec(composed)
    assert sorted(spec.variables) == ['flow', 'gen_p']
    assert spec.variables['flow'].bounds.lower == -1000, "the introducer's declaration is the one that survives"
    assert sorted(to_program(spec).variables) == ['flow', 'gen_p'], 'a composed library lowers like any model'


def test_a_given_declaration_may_say_less_than_the_introducer():
    """Bounds are the owner's, so the reader states the frame and stops."""
    assert 'bounds' not in SUPPLY['given']['variables']['flow']
    assert to_spec(merge({'surface': SURFACE, 'supply': SUPPLY})).variables['flow'].bounds.upper == 1000


def test_a_given_declaration_that_disagrees_with_the_introducer_is_refused():
    misread = {**SUPPLY, 'given': {'variables': {'flow': {'dims': ['snapshot', 'generator']}}}}
    with pytest.raises(LanguageError) as raised:
        merge({'surface': SURFACE, 'supply': misread})
    message = str(raised.value)
    assert "'supply'" in message and "'surface'" in message, 'both sides of a disagreement are named'


def test_two_fragments_must_read_one_column_the_same_way():
    other = {
        'dimensions': {'snapshot': {'dtype': 'int'}, 'port': {'dtype': 'str'}},
        'given': {'variables': {'flow': {'dims': ['port']}}},
    }
    with pytest.raises(LanguageError, match=r'say different things about given variable'):
        merge({'supply': SUPPLY, 'other': other})


def test_a_name_both_introduced_and_given_in_one_file_is_refused():
    both = {**SUPPLY, 'variables': {**SUPPLY['variables'], 'flow': {'dims': ['snapshot', 'port']}}}
    with pytest.raises(LanguageError, match=r"'flow'"):
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
    """Resolution and the dim algebra see one namespace, so `at(flow, by=gen_port)` lands on the generator frame."""
    spec = to_spec(SUPPLY)
    assert spec.constraints['gen_injects'].dims == ['snapshot', 'generator']


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
    program = to_program(LAYER)
    assert sorted(program.given.constraints) == ['balance']
    assert program.given.constraints['balance'].dims == ('snapshot', 'bus'), 'the frame is what a binder checks'


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
    assert "'constraints:'" in message and 'given' in message, (
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
    assert 'given' not in composed
    program = to_program(composed)
    assert sorted(program.constraints) == ['balance', 'cap']
    assert not program.given.constraints, 'nothing is left for a consumer to bind'


def test_the_advice_names_every_declaration_a_consumer_has_to_bind():
    subjects = {(note.subject) for note in advice(LAYER) if note.kind == 'given'}
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
