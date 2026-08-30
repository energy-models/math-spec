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

from copy import deepcopy
from typing import Any

import pytest

import math_spec as ms
from math_spec import LanguageError, merge
from math_spec.merge import override

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


def test_merging_one_fragment_gives_back_that_fragment():
    """Composition of one is the thing composed. It is what stops a wrapper
    nobody needs from accumulating: without it a lone objective came back
    parenthesised, and every nested merge added another pair."""
    assert ms.to_spec(merge({'only': GENERATOR})).to_dict() == ms.to_spec(GENERATOR).to_dict(), (
        'merging one fragment changes nothing about it'
    )


def test_a_composition_does_not_depend_on_how_it_was_grouped():
    """Merging is associative, so a library may ship a prelude already merged
    and a caller may merge it with their own fragments, and reach what merging
    all of them at once reaches. Without this a composed library would have to
    document an order."""
    storage = {
        'dimensions': {'snapshot': {'dtype': 'int'}},
        'parameters': {'holding': {'dims': []}},
        'variables': {'soc': {'foreach': ['snapshot'], 'bounds': {'lower': 0}}},
        'objective': {'sense': 'minimize', 'expression': 'sum(soc) * holding'},
    }
    flat = merge({'generator': GENERATOR, 'demand': DEMAND, 'storage': storage})
    grouped = merge({'pair': merge({'generator': GENERATOR, 'demand': DEMAND}), 'storage': storage})
    assert ms.to_spec(grouped).to_dict() == ms.to_spec(flat).to_dict(), (
        'the same fragments compose to the same model however they were grouped'
    )


#: A framework's base math, in the shape a project extends: a decision, the
#: dispatch that uses it, and a cost for both.
BASE: dict[str, Any] = {
    'dimensions': {'g': {'dtype': 'str'}},
    'parameters': {'cap_max': {'dims': ['g']}, 'cost': {'dims': ['g']}, 'load': {'dims': ['g']}},
    'variables': {
        'cap': {'foreach': ['g'], 'bounds': {'lower': 0, 'upper': 'cap_max'}, 'description': 'capacity built'},
        'p': {'foreach': ['g'], 'bounds': {'lower': 0}},
    },
    'constraints': {
        'lim': {'foreach': ['g'], 'expression': 'p <= cap'},
        'meet': {'foreach': ['g'], 'expression': 'p >= load'},
    },
    'objective': {'sense': 'minimize', 'expression': 'sum(cap * cost) + sum(p * cost)'},
}


def test_a_patch_says_only_what_it_changes():
    """The reason a patch can be short, and the reason #13's example is one
    line: a declaration is laid over field by field, so naming `foreach` keeps
    the expression under it."""
    patched = override(BASE, {'pathway': {'constraints': {'lim': {'foreach': ['g', 'g']}}}})
    assert patched['constraints']['lim'] == {'foreach': ['g', 'g'], 'expression': 'p <= cap'}, (
        'the field named is replaced and the rest of the declaration stands'
    )


def test_a_declaration_the_patch_nulls_is_removed():
    """The one thing an ordered list of files cannot say for itself: a
    declaration a patch does not mention is left alone, so without a marker
    there is no way to spell a deletion."""
    patched = ms.to_spec(override(BASE, {'operate': {'constraints': {'lim': None}}}))
    assert sorted(patched.constraints) == ['meet'], 'the nulled constraint is gone and the other stands'


def test_a_null_deeper_than_a_declaration_is_a_value_and_not_a_removal():
    """The marker is positional. `where: null` is a mask the schema already
    takes, so a null inside a declaration replaces the field rather than
    deleting it — otherwise one spelling would mean two things."""
    patched = override(BASE, {'x': {'variables': {'cap': {'description': None}}}})
    assert patched['variables']['cap']['description'] is None, 'the field was set, not dropped'
    assert patched['variables']['cap']['bounds'] == {'lower': 0, 'upper': 'cap_max'}, 'and the rest is untouched'


def test_a_variable_becomes_a_parameter_at_file_level():
    """#13's case, by the route #12 describes: the patch nulls the decision and
    declares the number, and every expression naming it goes on reading."""
    dispatch = {
        'variables': {'cap': None},
        'parameters': {'cap': {'dims': ['g']}},
        'objective': {'sense': 'minimize', 'expression': 'sum(p * cost)'},
    }
    spec = ms.to_spec(override(BASE, {'dispatch': dispatch}))
    assert 'cap' in spec.parameters and 'cap' not in spec.variables, 'the name moved between the two blocks'
    assert spec.constraints['lim'].expression == 'p <= cap', 'and the constraint that reads it is untouched'


def test_the_later_patch_wins():
    """Order is the instruction, which is what makes this the one verb here
    where the same arguments given differently mean a different model."""
    patched = override(
        BASE,
        {'a': {'parameters': {'cost': {'dims': []}}}, 'b': {'parameters': {'cost': {'dims': ['g'], 'dtype': 'int'}}}},
    )
    assert patched['parameters']['cost'] == {'dims': ['g'], 'dtype': 'int'}, 'the last patch to name it decides'


def test_a_patch_may_add_what_no_base_declares():
    patched = ms.to_spec(
        override(BASE, {'extra': {'constraints': {'floor': {'foreach': ['g'], 'expression': 'p >= 0'}}}})
    )
    assert sorted(patched.constraints) == ['floor', 'lim', 'meet'], 'a declaration the base lacks is simply added'


def test_removing_a_declaration_the_base_does_not_have_is_refused():
    """A removal is a claim about what is there, so a stale one is a patch that
    no longer describes the model it lands on — a base that moved on, or a
    section confused for another."""
    with pytest.raises(LanguageError) as exc:
        override(BASE, {'stale': {'constraints': {'limm': None}}})
    assert "'stale'" in str(exc.value), 'the message names the patch to open'
    assert 'lim' in str(exc.value), 'and the declaration it was probably reaching for'


def test_override_composes_with_merge():
    """Both take and return what the other does, so a library composed from
    templates is a base like any other."""
    composed = merge({'generator': GENERATOR, 'demand': DEMAND})
    patched = ms.to_program(override(composed, {'operate': {'constraints': {'balance': None}}}))
    assert sorted(patched.constraints) == [], 'the composed model is a base a patch lands on'


def test_a_patched_model_is_still_one_a_reviewer_can_open(tmp_path):
    """The safety story for a verb designed to collide: the artifact to review
    is the output, and a patch's real effect is a diff of base against result."""
    spec = ms.to_spec(override(BASE, {'operate': {'constraints': {'lim': None}}}))
    written = tmp_path / 'operate.yaml'
    written.write_text(spec.to_yaml())
    assert ms.to_spec(written).to_dict() == spec.to_dict(), 'the composed model round-trips like any other'


def test_the_base_and_the_patches_are_left_alone():
    """A caller's dicts are theirs. Nothing here writes into what it was given."""
    before = deepcopy(BASE)
    patch = {'constraints': {'lim': None}}
    override(BASE, {'operate': patch})
    assert before == BASE, 'the base is unchanged'
    assert patch == {'constraints': {'lim': None}}, 'and so is the patch'
