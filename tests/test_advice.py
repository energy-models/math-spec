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

from math_spec import ADVICE_KINDS, LanguageError, advice, to_spec
from tests.fixtures import SMALL_MODEL, override

if TYPE_CHECKING:
    from pathlib import Path

#: ``h`` is the target of ``lk`` and nothing else reaches it; ``g`` is an axis.
TARGET_ONLY = override(
    SMALL_MODEL,
    variables={'p': {'dims': ['g']}},
    objective={'sense': 'minimize', 'expression': 'sum(p * c)'},
)

#: The same with the relation gone, so nothing reaches ``h`` at all.
UNREACHED = override(TARGET_ONLY, relations={})

#: A curve on ``p``, so the program of the file as written carries a block and
#: the program of its expansion carries the rows.
CURVED = override(
    UNREACHED,
    dimensions={'g': {'dtype': 'str'}, 'h': {'dtype': 'str'}, 'bp': {'dtype': 'int'}},
    parameters={'c': {'dims': ['g']}, 'bp_x': {'dims': ['bp']}, 'bp_y': {'dims': ['bp']}},
    variables={'p': {'dims': ['g']}, 'cost': {'dims': ['g']}},
    piecewise={'curve': {'over': 'bp', 'links': [['p', 'bp_x'], ['cost', 'bp_y']]}},
)


def test_a_dimension_nothing_reaches_is_named():
    (note,) = advice(UNREACHED)
    assert (note.kind, note.subject) == ('never-an-axis', 'h')
    assert "dimension 'h' is never used" in str(note)


@pytest.mark.parametrize(
    'patch',
    [
        pytest.param({}, id='targeted-by-a-relation'),
        pytest.param(
            {'constraints': {'cap': {'dims': ['h'], 'expression': 'sum(p, by=lk, over=g, into=h) <= k'}}},
            id='grouping-into-it',
        ),
        pytest.param({'variables.r': {'dims': ['h']}}, id='indexing-by-it'),
    ],
)
def test_a_dimension_something_reaches_is_in_use(patch):
    assert not advice(override(TARGET_ONLY, **patch)), (
        'a dimension a relation targets, a declaration indexes or a grouping lands on is in use'
    )


#: A model with one note of each kind: nothing reaches `h`, and `p` is driven
#: down by the objective with an open lower bound and no constraint on it.
BOTH_KINDS = override(UNREACHED, **{'objective.expression': 'sum(p)', 'variables.p.bounds': {'lower': -float('inf')}})


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
        pytest.param(lambda model, _: to_spec(model).program, id='a-program'),
    ],
)
def test_the_answer_does_not_turn_on_which_state_it_is_asked_of(form, tmp_path):
    """A `Program` was advised of one kind and every other input of two (#210), with no signal that a rule had been skipped."""
    assert [(n.kind, n.subject) for n in advice(form(BOTH_KINDS, tmp_path))] == [
        ('never-an-axis', 'h'),
        ('unbounded', 'p'),
    ], 'one model, one answer, whichever of the four the caller happens to hold'


def test_a_curve_is_written_out_before_advice_reads_it():
    """Advice reads the rows a curve states, so a file is expanded first and a program still carrying one is refused.

    The refusal was added without a test; deleting the guard let a program
    with a block advise on the file's own rows as if the curve stated none.
    """
    from_file = advice(CURVED)
    from_rows = advice(to_spec(CURVED).expand('piecewise').program)
    assert [(n.kind, n.subject) for n in from_file] == [(n.kind, n.subject) for n in from_rows], (
        'a file and the program of its expansion are advised alike'
    )
    with pytest.raises(LanguageError, match="piecewise: 'curve' states rows") as refusal:
        advice(to_spec(CURVED).program)
    assert "expand('piecewise')" in str(refusal.value), 'the refusal names the expansion to pass'
