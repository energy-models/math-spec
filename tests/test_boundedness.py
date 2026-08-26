# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""What `unbounded_notes` may claim with no data.

A note is a proof that no data can bound the variable, so most rows here are
reasons it must stay silent: a false note is worse than none.
"""

from __future__ import annotations

import pytest

from math_spec import expand_piecewise, unbounded_notes
from tests.fixtures import SMALL_MODEL, override, schema_of

BASE = override(
    SMALL_MODEL,
    variables={'v': {'foreach': ['g']}, 'w': {'foreach': ['g']}},
    objective={'sense': 'minimize', 'expression': 'sum(v, over=g)'},
)


def _notes(**patch) -> list[str]:
    return unbounded_notes(expand_piecewise(schema_of(BASE, **patch)))


@pytest.mark.parametrize(
    ('patch', 'side'),
    [
        pytest.param({}, 'lower', id='minimize-a-positive-term-runs-down'),
        pytest.param({'objective.expression': '-sum(v, over=g)'}, 'upper', id='minimize-a-negated-term-runs-up'),
        pytest.param({'objective.sense': 'maximize'}, 'upper', id='maximize-a-positive-term-runs-up'),
        pytest.param({'objective.expression': 'sum(c * w - v, over=g)'}, 'upper', id='the-right-of-a-minus-is-negated'),
        pytest.param(
            {'objective.expression': 'sum(2 * v, over=g)'}, 'lower', id='a-literal-coefficient-keeps-the-sign'
        ),
        pytest.param({'objective.expression': 'sum(-3 * v, over=g)'}, 'upper', id='a-negative-literal-flips-it'),
        pytest.param({'objective.expression': 'sum(v / 2, over=g)'}, 'lower', id='a-literal-divisor-keeps-it'),
        pytest.param(
            {'objective.expression': 'sum(shift(v, over=g, offset=1), over=g)'},
            'lower',
            id='an-operator-argument-keeps-it',
        ),
        pytest.param(
            {'objective.expression': '-sum(v, over=g)', 'variables.v.bounds': {'lower': 0}},
            'upper',
            id='a-bound-on-the-side-it-runs-away-from-is-beside-the-point',
        ),
    ],
)
def test_a_variable_the_objective_drives_unopposed_is_named_with_its_side(patch, side):
    notes = _notes(**patch)
    assert len(notes) == 1, 'one variable is unbounded, so one note'
    assert "Variable 'v'" in notes[0]
    assert f'bounds.{side}' in notes[0], 'the note names the side the objective improves toward'


@pytest.mark.parametrize(
    'patch',
    [
        pytest.param({'variables.v.bounds': {'lower': 0}}, id='bounded-on-the-improving-side'),
        pytest.param({'variables.v.bounds': {'lower': 'c'}}, id='a-parameter-bound-is-data'),
        pytest.param({'variables.v.domain': 'binary'}, id='a-binary-is-bounded-by-its-domain'),
        pytest.param({'constraints': {'k': {'foreach': ['g'], 'expression': 'v >= c'}}}, id='named-by-a-constraint'),
        pytest.param({'sos': {'s': {'variable': 'v', 'over': 'g', 'type': 1}}}, id='carried-by-a-set'),
        pytest.param({'objective.expression': 'sum(c * v, over=g)'}, id='a-parameter-coefficient-may-be-zero'),
        pytest.param({'objective.expression': 'sum(v - v, over=g)'}, id='both-signs-may-cancel'),
        pytest.param({'objective.expression': 'sum(v * v, over=g)'}, id='a-degree-two-term-carries-no-sign'),
        pytest.param({'objective.expression': 'sum(0 * v, over=g)'}, id='a-zero-coefficient-is-not-a-term'),
        pytest.param({'objective': None}, id='no-objective'),
        pytest.param(
            {'objective.expression': '-sum(v, over=g)', 'variables.v.bounds': {'upper': 10}},
            id='bounded-on-the-improving-side-running-up',
        ),
    ],
)
def test_nothing_is_claimed_where_the_file_does_not_decide_it(patch):
    assert _notes(**patch) == [], 'a note here would be a false proof'


def test_every_unopposed_variable_is_named():
    notes = _notes(**{'objective.expression': 'sum(v + w, over=g)'})
    assert [n.split("'")[1] for n in notes] == ['v', 'w'], 'one note per variable, in objective order'


def test_the_note_names_the_rewrite():
    (note,) = _notes()
    assert 'Give it a finite bounds.lower, or the constraint that was meant to define it.' in note


def test_a_curve_holds_its_variables_through_the_rows_it_emits():
    """A piecewise block names no constraint in the file; its expansion does."""
    model = override(
        BASE,
        **{
            'dimensions.bp': {'dtype': 'int'},
            'parameters.bx': {'dims': ['bp']},
            'parameters.by': {'dims': ['bp']},
            'piecewise': {'curve': {'over': 'bp', 'links': [['v', 'bx'], ['w', 'by']]}},
        },
    )
    assert unbounded_notes(expand_piecewise(schema_of(model))) == []
