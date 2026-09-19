# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""What a file reads and does not build: a column, and a row family.

A file that reads a column somebody else introduces, or the dual of a row
family somebody else builds, says so under ``given:`` and stands on its own: it
loads, it prints as math, and its program carries the name and the frame for a
consumer to bind.
"""

from __future__ import annotations

import pytest

from math_spec import FORMATS, LanguageError, advice, to_markdown, to_program, to_spec, typeset

#: One component file: it pins the flow at its own port, and the column it
#: pins is introduced by a file beside it.
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


def test_given_holds_two_kinds_and_refuses_a_third():
    """The section is closed, so a kind nobody has admitted yet is the schema's own refusal."""
    with pytest.raises(LanguageError) as raised:
        to_spec({**SUPPLY, 'given': {'parameters': {'gen_cost': {'dims': ['generator']}}}})
    assert 'Valid keys: constraints, variables' in str(raised.value), 'the refusal names what the block takes'


def test_a_fragment_that_says_what_it_reads_loads_on_its_own():
    spec = to_spec(SUPPLY)
    assert sorted(spec.given.variables) == ['flow'], 'the column it reads is a declaration like any other'
    assert sorted(spec.variables) == ['gen_p'], 'and it is not one of the columns this file introduces'
    assert spec.given, 'a file that reads a column says so in one word'
    assert not to_spec({**SUPPLY, 'given': {}, 'constraints': {}}).given, 'and a whole model says it reads nothing'


def test_the_given_column_prints_under_its_own_heading():
    printed = to_markdown(SUPPLY)
    assert '#### Given' in printed, 'the legend says which symbols the file does not introduce'
    assert '`flow`' in printed.split('#### Given')[1]
    assert '`flow`' not in printed.split('#### Variables')[1].split('#### Given')[0], (
        'a column the file reads is not listed among the ones it introduces'
    )


def test_a_given_column_prints_italic_like_a_solver_choice():
    assert r'\mathit{flow}' in typeset(SUPPLY, 'latex'), 'a column somebody solves for is italic, whoever builds it'


def test_a_given_column_prints_no_domain_line():
    """Its bounds are the owner's, so the file states none and the page prints none."""
    printed = to_markdown(SUPPLY, legend=False)
    assert 'flow' in printed.split('#### Subject to')[1], 'the constraint that reads the column prints it'
    assert 'flow' not in printed.split('#### Variable domains')[1], 'and no domain line claims bounds for it'


def test_a_program_carries_the_column_it_reads_apart_from_the_ones_it_builds():
    program = to_program(SUPPLY)
    assert sorted(program.variables) == ['gen_p'], 'a build reads this group and creates a column for each'
    assert sorted(program.given.variables) == ['flow'], 'and binds each of these to a column it is given'
    assert program.given.variables['flow'].dims == ('snapshot', 'port'), 'the frame is what a binder checks'
    assert program.given, 'a program that reads a column says so in one word'


def test_the_advice_says_which_columns_a_consumer_has_to_bind():
    (note,) = [note for note in advice(SUPPLY) if note.kind == 'given']
    assert note.subject == 'flow'
    assert 'binds it to the model' in str(note), 'the note says whose job the column is'


def test_a_name_both_introduced_and_given_in_one_file_is_refused():
    both = {**SUPPLY, 'variables': {**SUPPLY['variables'], 'flow': {'dims': ['snapshot', 'port']}}}
    with pytest.raises(LanguageError, match=r"Given variable 'flow' collides with the variable"):
        to_spec(both)


@pytest.mark.parametrize(
    ('kind', 'block'),
    [
        pytest.param('variables', {'dims': ['snapshot']}, id='a-variable'),
        pytest.param('constraints', {'dims': ['snapshot']}, id='a-constraint'),
    ],
)
def test_a_given_name_is_held_to_the_name_rule(kind, block):
    """The name walk reads the top-level mappings, and ``given:`` nests its two one level down."""
    with pytest.raises(LanguageError, match=rf"given: {kind}: 'not a name' is not a name"):
        to_spec({**SUPPLY, 'given': {kind: {'not a name': block}}})


@pytest.mark.parametrize(
    ('block', 'says'),
    [
        pytest.param({'dims': ['snapshot', 'nowhere']}, 'nowhere', id='a-frame-over-an-undeclared-dimension'),
        pytest.param({'dims': ['snapshot', 'snapshot']}, 'twice', id='a-frame-naming-one-dimension-twice'),
        pytest.param({'dims': ['snapshot'], 'bounds': {'lower': 0}}, 'bounds', id='bounds-the-owner-holds'),
        pytest.param({'dims': ['snapshot'], 'domain': 'binary'}, 'domain', id='a-domain-the-owner-holds'),
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


def test_an_objective_over_a_given_column_gets_no_unboundedness_note():
    """The bounds are the owner's, so this file cannot say whether the column is open.

    No constraint names the column, so the objective is its only reader and the
    pass would ask for bounds this file does not hold.
    """
    reads_flow = {**SUPPLY, 'constraints': {}, 'objective': {'sense': 'minimize', 'expression': 'sum(flow)'}}
    assert [note.kind for note in advice(reads_flow)] == ['given'], 'the one note is that a consumer binds it'


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


@pytest.mark.parametrize(
    'fragment', [pytest.param(SUPPLY, id='reads-a-column'), pytest.param(LAYER, id='reads-a-dual')]
)
@pytest.mark.parametrize('fmt', sorted(FORMATS))
def test_a_fragment_prints_as_math_in_every_format(fragment, fmt):
    assert typeset(fragment, fmt), f'{fmt} rendered nothing'


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
    assert to_markdown(LAYER).count(r'\lambda_{\mathrm{balance},t,b}') == 1, (
        'the dual is subscripted by the frame the given declaration states, once, where price is defined'
    )


def test_a_given_row_family_prints_under_the_given_heading():
    given = to_markdown(LAYER).split('#### Given')[1].split('####')[0]
    assert '`balance`' in given
    assert 'reads the dual of' in given, 'the legend says what the file may do with it'
    assert r'\lambda_{\mathrm{balance}}' in given, 'the symbol is the dual as the math prints it, less the indices'


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
        pytest.param({'dims': ['nowhere']}, 'nowhere', id='a-frame-over-an-undeclared-dimension'),
        pytest.param({'dims': ['bus', 'bus']}, 'twice', id='a-frame-naming-one-dimension-twice'),
        pytest.param({'dims': [], 'expression': 'sum(p) >= 0'}, 'expression', id='a-body-the-owner-holds'),
        pytest.param({'dims': [], 'sense': '<='}, 'sense', id='a-sense-nothing-here-could-check'),
    ],
)
def test_a_given_row_family_is_refused_where_it_oversteps(block, says):
    with pytest.raises(LanguageError) as raised:
        to_spec({**LAYER, 'given': {**LAYER['given'], 'constraints': {'balance': block}}})
    assert says in str(raised.value)


#: A curve gated by a column this file reads: the gate has to be a column this
#: file builds, so the block is refused with the rewrite named.
GATED_BY_A_GIVEN_COLUMN = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'bp': {'dtype': 'int'}},
    'given': {'variables': {'on': {'dims': ['snapshot']}}},
    'parameters': {'bp_x': {'dims': ['bp']}, 'bp_y': {'dims': ['bp']}},
    'variables': {
        'p': {'dims': ['snapshot'], 'bounds': {'lower': 0}},
        'cost': {'dims': ['snapshot'], 'bounds': {'lower': 0}},
    },
    'piecewise': {'curve': {'over': 'bp', 'links': [['p', 'bp_x'], ['cost', 'bp_y']], 'activity': 'on'}},
}


@pytest.mark.parametrize(
    ('model', 'says'),
    [
        pytest.param(
            {**SUPPLY, 'sos': {'s': {'variable': 'flow', 'over': 'port', 'type': 1}}},
            "'flow' is a column this file reads, not one it builds",
            id='a-set-over-a-given-column',
        ),
        pytest.param(
            GATED_BY_A_GIVEN_COLUMN,
            "'on' is a column this file reads, not one it builds",
            id='a-curve-gated-by-a-given-column',
        ),
    ],
)
def test_a_given_column_may_not_carry_a_set_or_gate_a_curve(model, says):
    with pytest.raises(LanguageError) as raised:
        to_spec(model)
    message = str(raised.value)
    assert says in message, 'the refusal says the column is declared, and where'
    assert "under 'variables:'" in message, 'and names the rewrite'


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


def test_a_symbol_table_may_name_a_given_declaration():
    """The table's unknown-entry check knows both kinds, so a chosen symbol lands rather than being refused."""
    table = {'notation': 'latex', 'names': {'p': 'x', 'balance': 'B'}}
    printed = typeset(LAYER, 'latex', symbols=table)
    assert 'x_{t,b}' in printed, 'the given column prints under the symbol the table chose'
    assert r'\lambda_{B,t,b}' in printed, 'the given row family lends the dual its chosen symbol'
