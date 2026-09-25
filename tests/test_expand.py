# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""`Spec.expand`: what it takes, what comes back, and what data still attaches to it.

The kinds are a closed pair and the result is a plain `Spec`, so the claims here
are about the verb rather than about either formulation — those are in
`test_piecewise.py` and `test_sos.py`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from math_spec import piecewise, to_spec
from tests.fixtures import DISPATCH_MODEL, EXAMPLES, schema_of, varied
from tests.test_sos import CURVE
from tools.render_tex import models

if TYPE_CHECKING:
    from math_spec.model import Spec

#: The curve masked by one of its own values parameters, the one block whose
#: rows sit on more than the file's own names.
MASKED = varied(
    CURVE,
    **{
        'piecewise.cost_curve.method': 'lp',
        'piecewise.cost_curve.points': 'bp_x',
        'piecewise.cost_curve.links': [['p', 'bp_x'], ['op_cost', 'bp_y', '>=']],
    },
)

#: One directory per rule: a `before.yaml`, and the `after.yaml` it expands to,
#: written by hand. A name ending in `-piecewise` or `-sos` asks for that kind
#: alone, and any other name asks for both.
PAIRS = Path(__file__).parent / 'expand'


#: Every model the repository ships, which is what the sources invariant is
#: asserted over — the same corpus the LaTeX gate renders.
MODELS = models()


@pytest.mark.parametrize('case', sorted(PAIRS.iterdir()), ids=lambda case: case.name)
def test_a_model_expands_to_the_file_written_beside_it(case: Path):
    """Both files load and print through the same code, so `after.yaml` may leave a
    default out and still be compared whole: every name, bound, row and assumption."""
    kinds = [kind for kind in ('piecewise', 'sos') if case.name.endswith(f'-{kind}')]
    expanded = to_spec(case / 'before.yaml').expand(*kinds)

    assert expanded.to_yaml() == to_spec(case / 'after.yaml').to_yaml()


@pytest.mark.parametrize(
    'kinds',
    [
        pytest.param(('reformulate',), id='a-verb-rather-than-a-kind'),
        pytest.param(('piecewise', 'sos1'), id='one-known-and-one-not'),
    ],
)
def test_a_kind_this_language_does_not_have_is_refused_naming_both(kinds):
    with pytest.raises(ValueError, match=re.escape("is not a formulation. Expand 'piecewise' and 'sos'")):
        schema_of(CURVE).expand(*kinds)


def test_the_order_is_the_languages_rather_than_the_callers():
    """A curve states a set, so asking for the set first would leave one behind."""
    asked_backwards = schema_of(CURVE).expand('sos', 'piecewise')

    assert not asked_backwards.sos and not asked_backwards.piecewise, 'both are written out either way round'


def test_a_model_with_nothing_to_write_out_is_the_one_that_comes_back():
    schema = schema_of(DISPATCH_MODEL)

    assert schema.expand() is schema
    assert schema.expand('sos') is schema


def test_one_set_of_kinds_expands_to_one_model():
    schema = schema_of(CURVE)

    assert schema.expand('piecewise') == schema.expand('piecewise')
    assert schema.expand() == schema.expand('piecewise', 'sos')
    assert schema.expand() != schema.expand('piecewise'), 'a set left standing is a different model'


def test_asking_for_an_expansion_leaves_the_model_equal_to_itself():
    """Each expansion was cached in the spec's private state, which pydantic compares,
    so two loads of one file stopped being equal once one of them had been expanded."""
    asked, untouched = schema_of(CURVE), schema_of(CURVE)
    asked.expand('piecewise')
    assert asked == untouched


@pytest.mark.parametrize('kinds', [pytest.param((), id='everything'), pytest.param(('piecewise',), id='curves')])
def test_loading_writes_no_curve_out_and_each_ask_writes_them_out_once(monkeypatch, kinds):
    """`expand()` called the curve expander and then asked for the curves again, so one full
    ask wrote them out twice. A full ask writes the sets out of the model the curves
    were written out to."""
    schema = schema_of(CURVE)
    asked: list[Spec] = []
    written_out = piecewise.expand_piecewise
    monkeypatch.setattr(piecewise, 'expand_piecewise', lambda spec: asked.append(spec) or written_out(spec))

    assert asked == [], 'loading a model writes no curve out'
    assert not schema.expand(*kinds).piecewise
    assert asked == [schema], 'one ask writes the curves out once, from this model'


def test_an_expansion_declares_exactly_the_parameters_the_file_declared():
    """A masked ``lp`` curve emitted three ``bool`` parameters the file never declared, filled by a
    derivation the expanded model carried in private state, so the expansion asked for data the
    model it came from did not and ``to_yaml`` refused it. Every one of them is a predicate a
    ``where:`` writes, so the expansion emits none."""
    schema = schema_of(MASKED)
    expanded = schema.expand()

    assert expanded.parameters == schema.parameters, 'a curve emits no parameter, so the same data attaches to both'
    assert schema_of(expanded.to_yaml()).to_dict() == expanded.to_dict(), (
        'the expansion is a file like any other, and loading it back changes nothing'
    )


#: The two methods a curve is exact for only under a condition on its numbers,
#: which is the contract an expansion must not drop.
ASSUMED = [
    pytest.param(EXAMPLES / 'piecewise_lp.yaml', id='lp'),
    pytest.param(EXAMPLES / 'piecewise.yaml', id='convex'),
]


@pytest.mark.parametrize('model', ASSUMED)
def test_what_a_curve_assumes_of_its_numbers_rides_on_the_expansion_too(model):
    """`lp` and `convex` are exact only for a curve of the right shape, which no load
    decides. The program carries the condition for the consumer that has the numbers,
    and writing the curve out must not be the way a model loses it."""
    spec = schema_of(model)
    stated = spec.expand('piecewise').program.assumptions
    written_out = spec.expand().program.assumptions

    assert {'cost_curve_increasing', 'cost_curve_curvature'} <= set(stated), (
        'the breakpoints increase and the curve bends one way, both checked where the data is'
    )
    assert written_out == stated, 'and the expansion carries every condition the block came with'


@pytest.mark.parametrize('model', MODELS, ids=[m.stem for m in MODELS])
def test_the_same_sources_bind_a_model_and_its_expansion(model):
    """What a formulation may emit, asserted on every model the repository ships:
    neither a set nor a curve emits a parameter. A consumer's `sources` argument
    is therefore the same either way."""
    spec = schema_of(model)
    supplied = set(spec.expand('piecewise').program.parameters)
    written_out = set(spec.expand().program.parameters)

    assert written_out == supplied, 'writing a formulation out asks for data the model it came from did not'


def test_an_expansion_is_a_different_model_and_has_nothing_left_to_write_out():
    """What `expand()` returns: a new model, which a second expansion hands back unchanged."""
    spec = schema_of(CURVE)
    expanded = spec.expand()

    assert expanded != spec, 'the expansion declares more rows, so it is a different model'
    assert expanded.expand() is expanded, 'an expansion has no formulation left, so it comes back as itself'


def test_a_model_with_no_formulation_expands_to_itself():
    spec = schema_of(DISPATCH_MODEL)

    assert spec.expand() is spec, 'nothing to write out returns the same object, not a copy'
