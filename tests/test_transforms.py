# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""A decided variable becoming a supplied number, and what that costs it.

The move itself is a rename and the tests are not about the rename. They are
about the two translations that are decisions — a mask into a coverage claim,
a domain into a dtype — because those are what a driver writing its own four
lines gets wrong, and one of them gets wrong silently.
"""

from __future__ import annotations

from typing import Any

import pytest

import math_spec as ms
from math_spec import LanguageError
from math_spec.transforms import fix

MODEL: dict[str, Any] = {
    'dimensions': {'g': {'dtype': 'str'}},
    'parameters': {'p_max': {'dims': ['g']}, 'cost': {'dims': ['g']}},
    'variables': {
        'cap': {'foreach': ['g'], 'bounds': {'lower': 0, 'upper': 'p_max'}, 'description': 'capacity built'},
        'masked': {'foreach': ['g'], 'where': 'p_max > 0', 'bounds': {'lower': 0}},
        'on': {'foreach': ['g'], 'domain': 'binary'},
        'count': {'foreach': ['g'], 'domain': 'integer'},
    },
    'constraints': {'k': {'foreach': ['g'], 'expression': 'cap + masked + on + count <= p_max'}},
    'objective': {'sense': 'minimize', 'expression': 'sum(cap * cost)'},
}


def test_a_fixed_variable_is_a_parameter_of_the_same_name_and_dims():
    """The name not moving is the whole point: every expression naming it goes
    on reading, so a decomposition is this call rather than a second file."""
    spec = fix(MODEL, 'cap')
    assert 'cap' not in spec.variables, 'it is no longer decided'
    assert spec.parameters['cap'].dims == ['g'], 'and it is supplied over what it was decided over'
    assert ms.to_program(spec).constraints['k'], 'the constraint naming it still builds'


def test_a_masked_variable_becomes_a_parameter_that_says_its_rows_are_missing():
    """The one that goes wrong silently. A `where:` deleted rows, so as a
    parameter those coordinates have no value — and the obvious rewrite leaves
    it `total`, claiming a number everywhere and binding cleanly against data
    that has none."""
    assert fix(MODEL, 'masked').parameters['masked'].coverage == 'masked', 'the mask became a claim about the data'
    assert fix(MODEL, 'cap').parameters['cap'].coverage == 'total', 'and an unmasked one still covers its dims'


@pytest.mark.parametrize(
    ('name', 'dtype'),
    [
        pytest.param('cap', 'float', id='a-continuous-decision-is-a-float'),
        pytest.param('count', 'int', id='an-integer-decision-is-an-int'),
        pytest.param('on', 'int', id='a-binary-decision-is-an-int-not-a-bool'),
    ],
)
def test_a_domain_becomes_the_dtype_its_values_are(name, dtype):
    """`bool` is a mask and never a number, so a fixed commitment that a
    constraint multiplies by has to arrive as `int`."""
    assert fix(MODEL, name).parameters[name].dtype == dtype, 'the declaration says what the values are'


def test_a_description_survives_and_bounds_do_not():
    """A description describes the quantity, which the fix does not change.
    Bounds constrained a decision the model no longer makes, and whether the
    supplied numbers respect them is a question about data."""
    fixed = fix(MODEL, 'cap').parameters['cap']
    assert fixed.description == 'capacity built', 'still the same quantity'
    assert not hasattr(fixed, 'bounds'), 'a parameter has none to carry'


def test_one_call_fixes_every_variable_it_names():
    """A myopic step fixes what earlier periods built, which is many at once.
    Composing calls does the same, at one revalidation each."""
    spec = fix(MODEL, 'cap', 'count')
    assert sorted(spec.variables) == ['masked', 'on'], 'both named variables became parameters'
    assert spec.to_dict() == fix(fix(MODEL, 'cap'), 'count').to_dict(), 'and composing the calls says the same'


def test_a_constraint_whose_every_variable_is_fixed_is_refused():
    """`fix` revalidates, so a rewrite that made the model unsayable says so
    here rather than downstream. A Benders master is this shape and is not this
    move: it drops the dispatch rather than fixing it."""
    with pytest.raises(LanguageError) as exc:
        fix(MODEL, 'cap', 'masked', 'on', 'count')
    assert 'decides nothing' in str(exc.value), 'the language names what is wrong with the rewritten model'


def test_an_unknown_variable_is_refused_with_the_near_miss():
    with pytest.raises(KeyError) as exc:
        fix(MODEL, 'capp')
    assert 'cap' in str(exc.value), 'the message names the variable it was probably reaching for'


def test_the_fixed_model_is_still_one_a_reviewer_can_open(tmp_path):
    """A decomposition reached by a function rather than a second file is only
    an improvement if the thing it reaches is still a file — otherwise it is a
    model nobody can review, which is what hard rule 5 refuses."""
    spec = fix(MODEL, 'cap')
    written = tmp_path / 'subproblem.yaml'
    written.write_text(spec.to_yaml())
    assert ms.to_spec(written).to_dict() == spec.to_dict(), 'the rewritten model round-trips like any other'
    assert 'coverage: total' in written.read_text(), 'and the claim about its data is on the page a reviewer reads'
