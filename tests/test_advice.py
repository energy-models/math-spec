# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""One door for every note that is decidable without data.

The unboundedness pass argues for itself in ``test_boundedness.py``; what is
pinned here is the never-an-axis pass, and that both reach a consumer through
the one call.
"""

from __future__ import annotations

import pytest

from math_spec import advice, to_program
from tests.fixtures import SMALL_MODEL, override

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


def test_both_kinds_of_note_come_through_the_one_door():
    model = override(LABEL_SPACE, **{'objective.expression': 'sum(p)', 'variables.p.bounds': {'lower': -float('inf')}})
    notes = advice(model)
    assert [(n.kind, n.subject) for n in notes] == [('never-an-axis', 'h'), ('unbounded', 'p')], (
        'the never-an-axis advice comes first, then the unboundedness advice'
    )
    assert advice(to_program(model)) == notes[:1], 'a program has no file left to ask about bounds'
