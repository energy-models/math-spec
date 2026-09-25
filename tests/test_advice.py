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
from pathlib import Path
from typing import get_args

import pytest

from math_spec import AdviceKind, advice, to_spec
from tests.fixtures import SMALL_MODEL, override, raw_of

EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'

#: ``h`` is the target of ``lk`` and nothing else reaches it; ``g`` is an axis.
TARGET_ONLY = override(
    SMALL_MODEL,
    variables={'p': {'dims': ['g']}},
    objective={'sense': 'minimize', 'expression': 'sum(p * c)'},
)

#: The same with the relation gone, so nothing reaches ``h`` at all.
UNREACHED = override(TARGET_ONLY, relations={})

#: A curve on ``p``, so the program of the file as written carries a block and
#: the program of its expansion carries the rows. The objective drives ``p``
#: down unopposed by anything but the curve.
CURVED = override(
    UNREACHED,
    objective={'sense': 'minimize', 'expression': 'sum(p)'},
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
BOTH_KINDS = override(UNREACHED, **{'objective.expression': 'sum(p)', 'variables.p.bounds': {'lower': None}})


def test_both_kinds_of_note_come_through_the_one_door():
    notes = advice(BOTH_KINDS)
    assert [(n.kind, n.subject) for n in notes] == [('never-an-axis', 'h'), ('unbounded', 'p')], (
        'the never-an-axis advice comes first, then the unboundedness advice'
    )
    assert {n.kind for n in notes} == set(get_args(AdviceKind)), (
        'every kind a consumer can pin against is one this file produces'
    )


def _written(model: dict, tmp_path: Path) -> Path:
    """The model as a file on disk — JSON is YAML."""
    path = tmp_path / 'model.yaml'
    path.write_text(json.dumps(model))
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


@pytest.mark.parametrize(
    'arrive',
    [
        pytest.param(lambda model: model, id='a-mapping'),
        pytest.param(to_spec, id='a-spec'),
        pytest.param(lambda model: to_spec(model).program, id='a-program'),
    ],
)
def test_a_curve_is_read_as_the_rows_it_states_however_the_model_arrives(arrive):
    """Advice expanded a curve on the caller's behalf, then refused one left as written; a program with a
    block was once let through and advised on the file's rows as if the curve stated none.

    A curve states its rows the way a set does: each link names the variables
    a link row would. Nothing is expanded, and the answer is the expansion's.
    """
    rows = [(n.kind, n.subject) for n in advice(to_spec(CURVED).expand('piecewise'))]
    assert rows == [('never-an-axis', 'h')], 'the link row holds p, so only the unreached dimension draws a note'
    assert [(n.kind, n.subject) for n in advice(arrive(CURVED))] == rows, 'the block and its rows get one answer'


@pytest.mark.parametrize('example', ['piecewise', 'piecewise_lp', 'piecewise_ragged', 'sos'])
def test_every_shipped_formulation_gets_the_answer_its_expansion_gets(example):
    """The claim of the test above on every model the repository ships with a block.

    As shipped, each example's constraints hold its variables, so the answer
    was empty however the curve was read and the test passed with the curve
    ignored. With the constraints gone and the cost maximized, the curve is
    all that holds ``op_cost``.
    """
    raw = override(raw_of(EXAMPLES / f'{example}.yaml'), constraints={}, **{'objective.sense': 'maximize'})
    assert [(n.kind, n.subject) for n in advice(override(raw, piecewise={}))] == [('unbounded', 'op_cost')], (
        'without its curve nothing holds op_cost, so the answer below turns on reading the curve'
    )
    spec = to_spec(raw)
    as_written = [(n.kind, n.subject) for n in advice(spec)]
    assert as_written == [(n.kind, n.subject) for n in advice(spec.expand())] == [], (
        'one model, one answer, block or rows'
    )
