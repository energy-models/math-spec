# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""One door for every note that is decidable without data.

The unboundedness pass argues for itself in ``test_boundedness.py``; what is
pinned here is the never-an-axis pass, and that both reach a consumer through
the one call.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from math_spec import ADVICE_KINDS, advice, to_program, to_spec
from tests.fixtures import SMALL_MODEL, override

if TYPE_CHECKING:
    from pathlib import Path

#: ``h`` is the target of ``lk`` and nothing else reaches it; ``g`` is an axis.
LABEL_SPACE = override(
    SMALL_MODEL,
    variables={'p': {'foreach': ['g']}},
    objective={'sense': 'minimize', 'expression': 'sum(p * c)'},
)


@pytest.mark.parametrize(
    ('patch', 'expected'),
    [
        pytest.param(
            {},
            ["dimension 'h' is never an axis", "lookup 'lk' over 'g'", 'lk: {over: g, dtype: str}'],
            id='a-target-nothing-reaches-is-a-label-space',
        ),
        pytest.param({'lookups': {}}, ["dimension 'h' is never used"], id='a-dimension-nothing-reaches-is-unused'),
        pytest.param(
            {'constraints': {'cap': {'foreach': ['h'], 'expression': 'sum(p, by=lk) <= k'}}},
            [],
            id='grouping-into-it-makes-it-an-axis',
        ),
        pytest.param({'variables.r': {'foreach': ['h']}}, [], id='indexing-by-it-makes-it-an-axis'),
    ],
)
def test_a_dimension_that_is_never_an_axis_is_named(patch, expected):
    notes = advice(override(LABEL_SPACE, **patch))
    assert len(notes) == (1 if expected else 0), 'one dimension is never an axis, so one piece of advice or none'
    for fragment in expected:
        assert fragment in str(notes[0])
    if expected:
        assert (notes[0].kind, notes[0].subject) == ('never-an-axis', 'h')


#: A model with one note of each kind: `h` is a label space, and `p` is driven
#: down by the objective with an open lower bound and no constraint on it.
BOTH_KINDS = override(LABEL_SPACE, **{'objective.expression': 'sum(p)', 'variables.p.bounds': {'lower': -float('inf')}})


def test_both_kinds_of_note_come_through_the_one_door():
    notes = advice(BOTH_KINDS)
    assert [(n.kind, n.subject) for n in notes] == [('never-an-axis', 'h'), ('unbounded', 'p')], (
        'the never-an-axis advice comes first, then the unboundedness advice'
    )
    assert {n.kind for n in notes} == ADVICE_KINDS, 'every kind a consumer can pin against is one this file produces'


def _written(model: dict, tmp_path: Path) -> Path:
    """The model as a file on disk — JSON is YAML, once infinity is spelled its way."""
    path = tmp_path / 'model.yaml'
    path.write_text(json.dumps(model).replace('-Infinity', '-.inf'))
    return path


@pytest.mark.parametrize(
    'form',
    [
        pytest.param(_written, id='a-path'),
        pytest.param(lambda model, _: model, id='a-mapping'),
        pytest.param(lambda model, _: to_spec(model), id='a-spec'),
        pytest.param(lambda model, _: to_program(model), id='a-program'),
    ],
)
def test_the_answer_does_not_turn_on_which_state_it_is_asked_of(form, tmp_path):
    """A `Program` was advised of one kind and every other input of two (#210).

    The unboundedness pass read the file, and the arm that had already lowered
    skipped it — so a consumer that lowers first, which is every consumer,
    since lowering is what it wanted the program for, got the shorter answer
    and no signal that a rule had been skipped.
    """
    assert [(n.kind, n.subject) for n in advice(form(BOTH_KINDS, tmp_path))] == [
        ('never-an-axis', 'h'),
        ('unbounded', 'p'),
    ], 'one model, one answer, whichever of the four the caller happens to hold'
