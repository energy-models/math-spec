# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The normal form: one text for every file that means the same thing.

A reviewer diffs two models in an editor, and a text diff reports key order,
spacing and the order of terms in a sum — none of which is a difference in the
model. What is left after this form is applied is what the two files mean
differently, which is the question `to_yaml(canonical=True)` exists to answer.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import math_spec as ms
from math_spec.__main__ import main
from math_spec.canonical import canonical_text
from tests.fixtures import DISPATCH_MODEL, EXAMPLES, override

#: Every model in the repository, the operator probes included. The symbol
#: tables under `examples/symbols/` are not models and do not load as one.
MODELS = [path for path in sorted(EXAMPLES.rglob('*.yaml')) if 'symbols' not in path.parts]
FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'every_program_node.yaml'


def _dumped(**patch: object) -> str:
    return ms.to_spec(override(DISPATCH_MODEL, **patch)).to_yaml(canonical=True)


def test_two_files_that_mean_the_same_thing_write_the_same_text():
    """The claim the form makes, over the three ambiguities a file carries: the
    order two declarations are written in, the order of the terms of a sum, and
    the order of the factors of a product."""
    one = ms.to_spec(
        {
            'dimensions': {'h': {'dtype': 'int'}, 'u': {'dtype': 'str'}},
            'parameters': {'cost': {'dims': ['u']}, 'cap': {'dims': ['u']}},
            'variables': {'p': {'dims': ['h', 'u'], 'bounds': {'lower': 0}}},
            'constraints': {'k': {'dims': ['h', 'u'], 'expression': 'p * cost + p - cap <= 10'}},
            'objective': {'sense': 'minimize', 'expression': 'sum(p * cost)'},
        }
    )
    other = ms.to_spec(
        {
            'parameters': {'cap': {'dims': ['u']}, 'cost': {'dims': ['u']}},
            'dimensions': {'u': {'dtype': 'str'}, 'h': {'dtype': 'int'}},
            'variables': {'p': {'dims': ['h', 'u'], 'bounds': {'lower': 0}}},
            'constraints': {'k': {'dims': ['h', 'u'], 'expression': '-cap + p + cost * p <= 10'}},
            'objective': {'sense': 'minimize', 'expression': 'sum(cost * p)'},
        }
    )
    assert one.to_yaml(canonical=True) == other.to_yaml(canonical=True), 'the two files say one model'
    assert one.to_yaml() != other.to_yaml(), 'and the dump that keeps the file as written still tells them apart'


@pytest.mark.parametrize('path', [*MODELS, FIXTURE], ids=lambda path: path.stem)
def test_the_form_loads_and_is_already_in_the_form(path):
    """Every model in the tree, dumped, re-read and dumped again.

    Idempotence is the property that makes the text a *normal* form rather than
    a rewriting: a second pass that moved anything would mean two files in the
    form could still differ. It is also what catches a print the grammar reads
    back as a different tree, which a leading negative term did.
    """
    text = ms.to_spec(path).to_yaml(canonical=True)
    assert ms.to_spec(text).to_yaml(canonical=True) == text, 'the form is a fixed point of itself'


@pytest.mark.parametrize(
    ('written', 'canonical'),
    [
        pytest.param('a + c + b', 'a\n+ b\n+ c', id='the-terms-of-a-sum-are-sorted'),
        pytest.param('c * a * b', '(a * b) * c', id='and-the-factors-of-a-product'),
        pytest.param('b - a', '-a\n+ b', id='a-term-carries-its-sign-as-it-moves'),
        pytest.param('a + -b', 'a\n- b', id='and-a-sign-written-twice-is-folded-once'),
        pytest.param('a - (b - c)', 'a\n- (b - c)', id='a-bracketed-group-stays-one-term'),
        pytest.param('b - a - c', '-a\n+ b\n- c', id='terms-sort-under-the-signs-they-keep'),
        pytest.param('2 * 3 * a', '(2 * 3) * a', id='a-constant-is-never-folded-into-another'),
        pytest.param('b / a', 'b / a', id='a-division-is-not-reordered'),
        pytest.param('b ** a', 'b ** a', id='nor-is-an-exponent'),
        pytest.param('shift(p, edge=0, along=t)', 'shift(p, along=t, edge=0)', id='a-calls-kwargs-are-sorted'),
        pytest.param('at(q, by=r) - p', 'at(q, by=r)\n- p', id='a-call-sorts-as-the-text-it-prints'),
    ],
)
def test_an_expression_is_written_one_way(written, canonical):
    assert canonical_text(written) == canonical, 'the normal form of the expression, whole'


def test_a_positional_argument_keeps_the_place_the_file_gave_it():
    """`sum(a, b)` is not `sum(b, a)` for any operator that takes two operands,
    so position is meaning and only keywords are sorted."""
    assert canonical_text('max(b, a)') == 'max(b, a)', 'the arguments stand where they were written'


def test_an_expression_of_one_term_stays_on_one_line():
    dumped = _dumped(**{'constraints.balance.expression': 'sum(p, over=generator) == load'})
    assert 'expression: sum(p, over=generator) == load' in dumped, 'nothing to break across lines'


def test_a_sum_is_broken_one_term_to_a_line():
    """What a term-per-line layout buys: a changed term is one line of a diff
    rather than a rewritten expression."""
    dumped = _dumped(**{'constraints.balance.expression': 'sum(p, over=generator) - load + 1 == 0'})
    assert '\n      1\n      - load\n      + sum(p, over=generator)\n      == 0\n' in dumped, (
        'the block scalar holds one term per line, each under its own sign, and the comparison closes it'
    )


def test_the_declarations_of_a_section_are_sorted_by_name():
    dumped = ms.to_spec(
        override(DISPATCH_MODEL, **{'constraints.a_cap.dims': [], 'constraints.a_cap.expression': 'sum(p) >= 0'})
    ).to_yaml(canonical=True)
    assert dumped.index('a_cap:') < dumped.index('balance:'), 'a section reads in name order, not file order'


def test_the_dump_that_keeps_the_file_as_written_is_unchanged():
    """The default is the round trip `reading.md` documents, and the form is an
    argument away rather than a change to it."""
    spec = ms.to_spec(DISPATCH_MODEL)
    assert ms.to_spec(spec.to_yaml()) == spec, 'the file as written still reproduces the spec it came from'


def test_the_shell_writes_the_form_a_reviewer_diffs(tmp_path, capsys):
    """The verb is the whole point of the form: a reviewer works in a shell and
    a version control diff, not in Python."""
    model = tmp_path / 'model.yaml'
    model.write_text(ms.to_spec(DISPATCH_MODEL).to_yaml())
    assert main(['canonical', str(model)]) == 0, 'a model the language accepts exits 0'
    assert capsys.readouterr().out == ms.to_spec(model).to_yaml(canonical=True), 'stdout is the form, whole'


def test_the_shell_refuses_a_model_the_language_refuses(tmp_path, capsys):
    model = tmp_path / 'broken.yaml'
    model.write_text('constraints: {k: {dims: [], expression: "p >= "}}\n')
    assert main(['canonical', str(model)]) == 1, 'a refused file is exit status 1'
    assert capsys.readouterr().err, 'and its message on stderr'
