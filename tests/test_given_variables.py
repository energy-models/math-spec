# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""A file that reads a column it does not introduce, and still stands on its own.

The point of the section is what a template could not do before it: load, and
print as math, without the file that owns the column. What it may not do is
lower — a program builds every column it carries — so the two doors this pins
open and shut in the same breath: `to_spec` and the typesetter take a fragment,
`to_program` refuses one and names the composition that fixes it.
"""

from __future__ import annotations

import pytest

from math_spec import FORMATS, LanguageError, merge, to_markdown, to_program, to_spec, typeset

#: One component template: it pins the flow at its own port, and the column it
#: pins belongs to the surface fragment below.
SUPPLY = {
    'description': 'A fleet of generators, each on one port.',
    'dimensions': {'snapshot': {'dtype': 'int'}, 'port': {'dtype': 'str'}, 'generator': {'dtype': 'str'}},
    'relations': {'gen_port': {'key': 'generator', 'value': 'port'}},
    'given_variables': {'flow': {'dims': ['snapshot', 'port'], 'description': 'what a port puts into its bus'}},
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


def test_a_fragment_that_says_what_it_reads_loads_on_its_own():
    spec = to_spec(SUPPLY)
    assert sorted(spec.given_variables) == ['flow'], 'the column it reads is a declaration like any other'
    assert sorted(spec.variables) == ['gen_p'], 'and it is not one of the columns this file introduces'


@pytest.mark.parametrize('fmt', sorted(FORMATS))
def test_a_fragment_prints_as_math_in_every_format(fmt):
    """The improvement the section exists for: the unit you share is the unit you can read."""
    assert typeset(SUPPLY, fmt), f'{fmt} rendered nothing'


def test_the_given_column_prints_under_its_own_heading():
    printed = to_markdown(SUPPLY)
    assert '#### Given' in printed, 'the legend says which symbols the file does not introduce'
    assert '`flow`' in printed.split('#### Given')[1]


def test_a_program_refuses_a_file_that_reads_what_it_does_not_introduce():
    with pytest.raises(LanguageError, match=r"reads a variable it does not introduce: 'flow'"):
        to_program(SUPPLY)


def test_the_refusal_names_the_composition_that_fixes_it():
    with pytest.raises(LanguageError) as raised:
        to_program(SUPPLY)
    assert 'merge(' in str(raised.value), 'a message names the rewrite, and here the rewrite is a verb'


def test_merging_folds_the_given_declaration_into_the_one_that_introduces_it():
    composed = merge({'surface': SURFACE, 'supply': SUPPLY})
    assert 'given_variables' not in composed, 'the expectation is spent once the column is in the composition'
    spec = to_spec(composed)
    assert sorted(spec.variables) == ['flow', 'gen_p']
    assert spec.variables['flow'].bounds.lower == -1000, "the introducer's declaration is the one that survives"
    assert sorted(to_program(spec).variables) == ['flow', 'gen_p'], 'a composed library lowers like any model'


def test_a_given_declaration_may_say_less_than_the_introducer():
    """Bounds are the owner's, so the reader states the frame and stops."""
    assert 'bounds' not in SUPPLY['given_variables']['flow']
    assert to_spec(merge({'surface': SURFACE, 'supply': SUPPLY})).variables['flow'].bounds.upper == 1000


def test_a_given_declaration_that_disagrees_with_the_introducer_is_refused():
    misread = {**SUPPLY, 'given_variables': {'flow': {'dims': ['snapshot', 'generator']}}}
    with pytest.raises(LanguageError) as raised:
        merge({'surface': SURFACE, 'supply': misread})
    message = str(raised.value)
    assert "'supply'" in message and "'surface'" in message, 'both sides of a disagreement are named'


def test_two_fragments_must_read_one_column_the_same_way():
    other = {
        'dimensions': {'snapshot': {'dtype': 'int'}, 'port': {'dtype': 'str'}},
        'given_variables': {'flow': {'dims': ['port']}},
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
        to_spec({**SUPPLY, 'given_variables': {'flow': block}})
    assert says in str(raised.value)


def test_an_expression_reads_a_given_column_as_it_reads_any_other():
    """Resolution and the dim algebra see one namespace, so `at(flow, by=gen_port)` lands on the generator frame."""
    spec = to_spec(SUPPLY)
    assert spec.constraints['gen_injects'].dims == ['snapshot', 'generator']
