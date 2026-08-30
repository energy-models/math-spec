# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Several fragments into one model, and what merging refuses.

Nothing here resolves a name or checks a dim — that is what the merged mapping
goes through ``to_spec`` for, and asserting it twice would be asserting it in
the wrong place. What is under test is which declarations come out, and the
four disagreements that make one model impossible.
"""

from __future__ import annotations

from typing import Any

import pytest

import math_spec as ms
from math_spec import LanguageError, merge

#: A generator's own math. Not a model: nothing here says what `p` is for, and
#: the balance that reads it lives in the fragment below.
GENERATOR: dict[str, Any] = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'generator': {}},
    'parameters': {'cost': {'dims': ['generator']}, 'p_max': {'dims': ['generator']}},
    'variables': {'p': {'foreach': ['snapshot', 'generator'], 'bounds': {'lower': 0, 'upper': 'p_max'}}},
    'objective': {'sense': 'minimize', 'expression': 'sum(p * cost)'},
}

#: The demand side. Also not a model: it names `p` and `generator`, which the
#: fragment above declares.
DEMAND: dict[str, Any] = {
    'dimensions': {'snapshot': {'dtype': 'int'}},
    'parameters': {'load': {'dims': ['snapshot']}},
    'constraints': {'balance': {'foreach': ['snapshot'], 'expression': 'sum(p, over=generator) == load'}},
}


def test_a_fragment_may_name_what_a_sibling_declares():
    """The whole reason a fragment is not a `Spec`: `DEMAND` alone is a load
    error naming `p`, and merged it is an ordinary constraint. Validation runs
    once, on the composition, against one flat namespace."""
    with pytest.raises(LanguageError):
        ms.to_spec(DEMAND)
    program = ms.to_program(merge({'generator': GENERATOR, 'demand': DEMAND}))
    assert sorted(program.constraints) == ['balance'], 'the composed model carries the constraint the fragment wrote'
    assert sorted(program.variables) == ['p'], 'and the variable the other one declared'


def test_a_shared_axis_declared_twice_and_agreeing_is_one_axis():
    program = ms.to_program(merge({'generator': GENERATOR, 'demand': DEMAND}))
    assert sorted(program.dimensions) == ['generator', 'snapshot'], (
        'snapshot is declared by both fragments and is one dimension, not two'
    )


def test_every_objective_is_summed_into_one():
    """Each template prices what it owns and the system pays for all of it."""
    storage = {
        'dimensions': {'snapshot': {'dtype': 'int'}},
        'parameters': {'holding': {'dims': []}},
        'variables': {'soc': {'foreach': ['snapshot'], 'bounds': {'lower': 0}}},
        'objective': {'sense': 'minimize', 'expression': 'sum(soc) * holding'},
    }
    merged = merge({'generator': GENERATOR, 'demand': DEMAND, 'storage': storage})
    assert merged['objective']['expression'] == '(sum(p * cost)) + (sum(soc) * holding)', (
        'both objectives are present, each parenthesised so neither binds into the other'
    )
    assert ms.to_program(merged).objective is not None, 'and the sum is an objective the language accepts'


def test_a_model_with_no_objective_anywhere_stays_a_feasibility_problem():
    assert 'objective' not in merge({'demand': DEMAND}), 'no fragment declares one, so the composition declares none'


def test_the_composition_describes_itself_or_says_nothing():
    """A fragment's `description` is about the fragment. Joining them would
    describe a thing none of them is."""
    described = dict(GENERATOR, description='one generator template')
    assert 'description' not in merge({'generator': described}), 'a fragment description is not carried'
    assert merge({'generator': described}, description='a fleet')['description'] == 'a fleet'


@pytest.mark.parametrize(
    ('fragments', 'fragment_names', 'fragments_of_the_message'),
    [
        pytest.param(
            {'a': {'variables': {'p': {'foreach': []}}}, 'b': {'variables': {'p': {'foreach': []}}}},
            ("'a'", "'b'"),
            ('both declare', "variable 'p'", 'two rows of a dimension', 'call one of them something else'),
            id='two-fragments-claim-one-owned-name',
        ),
        pytest.param(
            {'a': {'sos': {'s': {}}}, 'b': {'sos': {'s': {}}}},
            ("'a'", "'b'"),
            ("special-ordered set 's'",),
            id='a-section-whose-name-is-not-a-plural-is-still-named-in-english',
        ),
        pytest.param(
            {'a': {'dimensions': {'t': {'dtype': 'int'}}}, 'b': {'dimensions': {'t': {'dtype': 'str'}}}},
            ("'a'", "'b'"),
            ('disagree about', "dimension 't'", 'identical'),
            id='two-fragments-disagree-about-a-shared-axis',
        ),
        pytest.param(
            {'a': dict(GENERATOR, version=0), 'b': dict(DEMAND, version=1)},
            ("'a'", "'b'"),
            ('different language versions',),
            id='two-fragments-pin-different-language-versions',
        ),
        pytest.param(
            {
                'a': GENERATOR,
                'b': dict(DEMAND, objective={'sense': 'maximize', 'expression': 'sum(p)'}),
            },
            ("'a'", "'b'"),
            ('which way the objective runs', 'negate the terms'),
            id='two-fragments-disagree-about-the-sense',
        ),
    ],
)
def test_a_composition_that_cannot_be_one_model_is_refused(fragments, fragment_names, fragments_of_the_message):
    with pytest.raises(LanguageError) as exc:
        merge(fragments)
    for name in fragment_names:
        assert name in str(exc.value), f'the message names the fragment {name}, which is what a reader has to open'
    for fragment in fragments_of_the_message:
        assert fragment in str(exc.value), f'the message carries {fragment!r}'


def test_a_fragment_is_whatever_every_other_verb_takes(tmp_path):
    """A `str` is a path here because a `str` is a path in `to_spec`. Composing
    a shipped template with a mapping is what a library does, so it needs no
    conversion at the call site — and no second convention for what a `str` is."""
    shipped = tmp_path / 'generator.yaml'
    shipped.write_text(ms.to_spec(GENERATOR).to_yaml())
    for fragment in (shipped, str(shipped), ms.to_spec(GENERATOR), GENERATOR):
        program = ms.to_program(merge({'generator': fragment, 'demand': DEMAND}))
        assert sorted(program.parameters) == ['cost', 'load', 'p_max'], (
            f'{type(fragment).__name__} contributed its declarations unchanged'
        )


def test_a_composed_model_is_still_one_a_reviewer_can_read(tmp_path):
    """Hard rule 5 wants the model to be the file you review and diff, and a
    composition is a model like any other — so `to_yaml` has to give back a file
    that loads to the same thing. Without this, merging would be a way to reach
    a model no reviewer could open."""
    spec = ms.to_spec(merge({'generator': GENERATOR, 'demand': DEMAND}, description='a fleet'))
    written = tmp_path / 'composed.yaml'
    written.write_text(spec.to_yaml())
    assert ms.to_spec(written).to_dict() == spec.to_dict(), 'the review copy loads to the model it was written from'


@pytest.mark.parametrize('typeset', ['to_latex', 'to_typst', 'to_markdown'])
def test_a_composed_model_prints_as_math(typeset):
    """A construct that cannot be printed is not in the language, and composing
    does not make one: all three formats render the merged model."""
    spec = ms.to_spec(merge({'generator': GENERATOR, 'demand': DEMAND}))
    assert 'balance' in getattr(ms, typeset)(spec), f'{typeset} renders the constraint the composition carries'
