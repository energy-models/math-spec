# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""What `unbounded_notes` may claim with no data.

A note is a proof that no data can bound the variable, so most rows here are
reasons it must stay silent: a false note is worse than none.
"""

from __future__ import annotations

import pytest

from math_spec.boundedness import unbounded_notes
from math_spec.lowering import to_program
from math_spec.operators import BUILTIN_NAMES
from tests.fixtures import SMALL_MODEL, override, schema_of

BASE = override(
    SMALL_MODEL,
    variables={'v': {'foreach': ['g']}, 'w': {'foreach': ['g']}},
    objective={'sense': 'minimize', 'expression': 'sum(v, over=g)'},
)


def _advice(**patch):
    return unbounded_notes(to_program(schema_of(BASE, **patch)))


def _notes(**patch) -> list[str]:
    return [str(a) for a in _advice(**patch)]


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
        pytest.param({'variables.v.domain': 'integer'}, 'lower', id='an-integer-keeps-its-declared-bounds'),
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


#: One objective per built-in, each driving a free variable through that
#: operator and nothing else. Keyed by name rather than listed, so a fifth
#: built-in arrives with a case of its own.
THROUGH_EACH_OPERATOR = {
    'sum': {'objective.expression': 'sum(v, over=g)'},
    'shift': {'objective.expression': 'sum(shift(v, over=g, offset=1), over=g)'},
    'sum_back': {'objective.expression': 'sum(sum_back(v, over=g, within=2), over=g)'},
    # `at` reads onto the lookup's source, so the variable it drives is on `h`
    'at': {'variables.u': {'foreach': ['h']}, 'objective.expression': 'sum(at(u, by=lk), over=g)'},
}

#: `dual` is refused in any objective, and boundedness walks the objective —
#: so its `Dual` leaf never reaches `_walk`, and carries no variable to hand a
#: sign to in any case. Exempt, not a missing case.
REPORTED_ONLY = {'dual'}


@pytest.mark.parametrize('builtin', sorted(BUILTIN_NAMES - REPORTED_ONLY))
def test_every_operator_hands_its_sign_to_its_operand(builtin):
    """`_record_signs` gives all four built-ins one arm, on a claim each of them has to keep.

    The claim is that every operator sums its argument's terms with coefficient
    1 — being a reduction, a re-index or a window — so the sign passes through
    unchanged. An operator that negated, took a magnitude or reversed a sense
    would break it, and would inherit sign-preservation in silence without a
    case of its own here.
    """
    assert builtin in THROUGH_EACH_OPERATOR, (
        f"the built-in '{builtin}' has no case here. Add the objective that drives a free variable "
        f'through it — or, if it does not hand its sign to its operand, split the shape-node arm of `_record_signs`.'
    )
    notes = _notes(**THROUGH_EACH_OPERATOR[builtin])
    assert len(notes) == 1, 'one variable is driven and unopposed, so one note'
    assert 'bounds.lower' in notes[0], 'a minimize objective over a +v term runs down, through the operator too'


def test_every_unopposed_variable_is_named():
    advice = _advice(**{'objective.expression': 'sum(v + w, over=g)'})
    assert [(a.kind, a.subject) for a in advice] == [('unbounded', 'v'), ('unbounded', 'w')], (
        'one piece of advice per variable, in objective order'
    )


def test_the_note_names_the_rewrite():
    (note,) = _notes()
    assert 'Give it a finite bounds.lower, or the constraint that was meant to define it.' in note


def test_a_curve_holds_its_variables_through_the_rows_it_emits():
    """A piecewise block names no constraint in the file; its expansion does."""
    curve = {
        'dimensions.bp': {'dtype': 'int'},
        'parameters.bx': {'dims': ['bp']},
        'parameters.by': {'dims': ['bp']},
        'piecewise': {'curve': {'over': 'bp', 'links': [['v', 'bx'], ['w', 'by']]}},
    }
    assert _notes(**curve) == [], 'the emitted link rows pin v and w, so neither is unopposed'
