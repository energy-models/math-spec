# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The ``given:`` block: what a file reads and does not introduce.

A layer says all of its own math and none of the math it is laid over. What it
does not say is where the declarations it reads come from — that is bound by
whoever builds the model, the way a parameter's values are.

Two properties carry the whole design, and each has its own section below. The
first is that a given declaration is **complete**: every load-time pass treats
it as it treats any other, so there is no partial ``Spec``. The second is that
it is **not built**: a given row family never reaches ``constraints``, and a
given column carries no bounds for anybody to build against.
"""

from __future__ import annotations

import pytest

from math_spec import (
    DimensionError,
    LanguageError,
    SchemaError,
    advice,
    to_latex,
    to_markdown,
    to_program,
    to_spec,
    to_typst,
)
from tests.fixtures import DISPATCH_MODEL, override

#: A CO2 cap laid over a dispatch model that already exists: it reads the
#: dispatch variable, caps the emissions it implies, and reports the price the
#: base model's own balance carries.
LAYER: dict = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'generator': {'dtype': 'str'}},
    'parameters': {'emission_rate': {'dims': ['generator']}, 'cap': {'dims': []}},
    'given': {
        'variables': {'p': {'foreach': ['snapshot', 'generator']}},
        'constraints': {'balance': {'foreach': ['snapshot'], 'sense': '=='}},
    },
    'constraints': {
        'co2_cap': {
            'foreach': [],
            'expression': 'sum(sum(p * emission_rate, over=generator), over=snapshot) <= cap',
        }
    },
    'expressions': {'price': 'dual(balance)'},
}


# -- a given declaration is complete -----------------------------------------


def test_a_layer_loads_against_declarations_it_does_not_introduce():
    program = to_program(LAYER)
    assert program.variables['p'].dims == ('snapshot', 'generator')
    assert program.given_constraints['balance'].sense == '=='


def test_a_given_variable_is_a_variable_to_every_pass_but_one():
    """It resolves, shapes and lowers like any other; only who builds the column differs."""
    declaration = to_program(LAYER).variables['p']
    assert declaration.given, 'the flag says who builds the column, and nothing else about it'
    assert declaration.domain == 'continuous'


def test_a_given_column_is_unbounded_here_because_its_owner_holds_the_bounds():
    declaration = to_program(LAYER).variables['p']
    assert (declaration.lower.value, declaration.upper.value) == (float('-inf'), float('inf')), (
        'both sides open: a bound stated here would be a second home for a fact the owner already holds'
    )


def test_a_given_binary_still_lowers_to_the_bounds_its_domain_means():
    layer = override(LAYER, **{'given.variables.p.domain': 'binary'})
    declaration = to_program(layer).variables['p']
    assert (declaration.lower.value, declaration.upper.value) == (0.0, 1.0)


def test_a_dual_reads_the_frame_of_the_row_family_it_names():
    program = to_program(LAYER)
    assert program.named_expressions['price'].expression.constraint == 'balance'
    assert program.given_constraints['balance'].dims == ('snapshot',)


def test_a_dimension_only_a_given_declaration_reaches_is_in_use():
    """A layer's dimensions are mostly its interface's, so counting only built rows would advise removing them."""
    assert not advice(LAYER), 'nothing here is unreached, unread or unbounded'


def test_a_dimension_only_a_given_row_family_indexes_is_in_use():
    """`region` is nothing's axis here but the given family's, and its dual is reported rather than built."""
    layered = override(
        LAYER,
        **{
            'dimensions.region': {'dtype': 'str'},
            'given.constraints.transfer': {'foreach': ['region'], 'sense': '<='},
            'expressions.rent': 'dual(transfer)',
        },
    )
    assert [n.kind for n in advice(layered)] == [], 'a given frame is an axis in use, like any other declaration'


def test_a_given_variable_s_mask_is_resolved_like_any_other():
    masked = override(LAYER, **{'given.variables.p.where': 'emission_rate > 0'})
    assert to_program(masked).variables['p'].where is not None, 'a where on a given column is language, not decoration'


def test_a_given_variable_s_mask_is_held_to_the_frame_it_masks():
    masked = override(
        LAYER,
        **{'given.variables.p.foreach': ['snapshot'], 'given.variables.p.where': 'emission_rate > 0'},
    )
    with pytest.raises(DimensionError, match='generator'):
        to_spec(masked)


def test_a_given_declaration_is_named_the_way_an_expression_writes_it():
    with pytest.raises(SchemaError, match='is not a name'):
        to_spec(override(LAYER, **{'given.variables': {'not a name': {'foreach': ['snapshot']}}}))


# -- a given declaration is not built ----------------------------------------


def test_a_given_row_family_is_never_among_the_ones_a_build_reads():
    program = to_program(LAYER)
    assert list(program.constraints) == ['co2_cap'], 'constraints holds what this file builds, and nothing given'
    assert list(program.given_constraints) == ['balance']


def test_the_math_may_not_read_a_dual_of_a_given_row_family_either():
    """`dual()` exists only after a solve, and being given does not make one earlier."""
    layer = override(LAYER, **{'constraints.co2_cap.expression': 'dual(balance) <= cap'})
    with pytest.raises(LanguageError, match='a dual exists only after a solve'):
        to_spec(layer)


# -- what the file may not say -----------------------------------------------


@pytest.mark.parametrize(
    ('patch', 'match'),
    [
        pytest.param(
            {'given.variables.p.bounds': {'lower': 0}},
            "unknown key 'bounds' in a given variable declaration",
            id='bounds-on-a-given-variable',
        ),
        pytest.param(
            {'given.constraints.balance.expression': 'sum(p, over=generator) == cap'},
            "unknown key 'expression' in a given constraint declaration",
            id='a-body-for-a-row-family-it-does-not-build',
        ),
        pytest.param(
            {'given.variables.p.absence': 'zero'},
            'needs a `where:`',
            id='absence-with-nothing-to-be-absent-from',
        ),
        pytest.param(
            {'given.variables.p.foreach': ['snapshot', 'nowhere']},
            "dimension 'nowhere'",
            id='a-frame-over-an-undeclared-dimension',
        ),
        pytest.param(
            {'given.constraints.balance.foreach': ['nowhere']},
            "dimension 'nowhere'",
            id='a-given-frame-over-an-undeclared-dimension',
        ),
        pytest.param(
            {'variables.p': {'foreach': ['snapshot', 'generator']}},
            'collides with the variable of the same name',
            id='a-variable-both-introduced-and-given',
        ),
        pytest.param(
            {'constraints.balance': {'foreach': ['snapshot'], 'expression': 'sum(p, over=generator) == cap'}},
            'either built by this file or given to it',
            id='a-row-family-both-built-and-given',
        ),
    ],
)
def test_the_file_is_refused_and_the_message_names_the_rewrite(patch, match):
    with pytest.raises(SchemaError, match=match):
        to_spec(override(LAYER, **patch))


def test_a_given_constraint_states_the_sense_that_fixes_its_dual_s_sign():
    """Without it a dual is read with no sign convention, which is a wrong number rather than an error."""
    layer = override(LAYER, **{'given.constraints.balance': {'foreach': ['snapshot']}})
    with pytest.raises(SchemaError, match='sense'):
        to_spec(layer)


def test_a_dual_still_has_to_name_a_row_family_the_file_knows():
    layer = override(LAYER, **{'expressions.price': 'dual(nothing_declared)'})
    with pytest.raises(SchemaError, match="'nothing_declared' is not a declared constraint"):
        to_spec(layer)


# -- what a consumer is asked to bind ----------------------------------------


@pytest.mark.parametrize(
    ('patch', 'said'),
    [
        pytest.param(
            {'given.variables.spare': {'foreach': ['snapshot']}},
            'no expression names it',
            id='a-column-nothing-reads',
        ),
        pytest.param(
            {'given.constraints.spare': {'foreach': ['snapshot'], 'sense': '<='}},
            'no dual() names it',
            id='a-row-family-no-dual-names',
        ),
    ],
)
def test_a_given_entry_nothing_reads_is_advised_rather_than_refused(patch, said):
    (note,) = [n for n in advice(override(LAYER, **patch)) if n.kind == 'given-never-read']
    assert note.subject == 'spare'
    assert said in str(note), str(note)


# -- it prints ---------------------------------------------------------------


@pytest.mark.parametrize('render', [to_latex, to_markdown, to_typst], ids=['latex', 'markdown', 'typst'])
def test_a_layer_prints_in_all_three_formats(render):
    """Whatever the loader admits, the typesetter renders — so a given block is a preamble, not a gap."""
    out = render(LAYER)
    assert 'Given' in out, 'the block prints under its own heading, ahead of the math that assumes it'


def test_the_dual_a_given_row_family_offers_prints_as_the_symbol_the_math_uses():
    out = to_markdown(LAYER)
    assert out.count('\\lambda_{\\mathrm{balance},t}') == 2, (
        'once where the given block offers it, once where the definition reads it'
    )


# -- the file survives a round trip ------------------------------------------


def test_the_block_survives_the_round_trip_a_reviewer_reads():
    spec = to_spec(LAYER)
    assert to_spec(spec.to_dict()).to_dict() == spec.to_dict()
    assert 'given:' in spec.to_yaml()


def test_a_file_with_no_given_block_writes_none():
    assert 'given' not in to_spec(DISPATCH_MODEL).to_yaml(), 'an absent section is not serialised'
