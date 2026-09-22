# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""`Spec.expand`: what it takes, what comes back, and what still binds it.

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
from math_spec.lowering import to_program
from tests.fixtures import DISPATCH_MODEL, EXAMPLES, override, schema_of
from tests.test_sos import CURVE
from tools.render_tex import models

if TYPE_CHECKING:
    from math_spec.model import Spec

#: The curve masked by one of its own values parameters, the one block whose
#: rows sit on more than the file's own names.
MASKED = override(
    CURVE,
    **{
        'piecewise.cost_curve.method': 'lp',
        'piecewise.cost_curve.where': 'bp_x',
        'piecewise.cost_curve.links': {'p': ['p', 'bp_x'], 'op_cost': ['op_cost', 'bp_y', '>=']},
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


def test_each_set_of_kinds_is_expanded_once():
    schema = schema_of(CURVE)

    assert schema.expand('piecewise') is schema.expand('piecewise')
    assert schema.expand() is schema.expand('piecewise', 'sos')
    assert schema.expand() is not schema.expand('piecewise'), 'a set left standing is a different model'


def test_writing_everything_out_reuses_the_curves_the_load_wrote_out(monkeypatch):
    """`expand()` called the curve expander directly, so the model the load had already
    written out and cached was built again, and validated again, on every full ask."""
    schema = schema_of(CURVE)
    asked: list[Spec] = []
    written_out = piecewise.expand_piecewise
    monkeypatch.setattr(piecewise, 'expand_piecewise', lambda spec: asked.append(spec) or written_out(spec))

    assert not schema.expand().piecewise
    assert [spec for spec in asked if spec.piecewise] == [], (
        'the curves were written out at load, and that is the model the sets are written out of'
    )


def test_an_expansion_declares_exactly_the_parameters_the_file_declared():
    """A masked ``lp`` curve emitted three ``bool`` parameters the file never declared, filled by a
    derivation the expanded model carried in private state, so the expansion asked for data the
    model it came from did not and ``to_yaml`` refused it. Every one of them is a predicate a
    ``where:`` writes, so the expansion emits none."""
    schema = schema_of(MASKED)
    expanded = schema.expand()

    assert expanded.parameters == schema.parameters, 'a curve emits no parameter, so the same data binds both'
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
    stated = to_program(spec.expand('piecewise')).assumptions
    written_out = to_program(spec.expand()).assumptions

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
    supplied = set(to_program(spec.expand('piecewise')).parameters)
    written_out = set(to_program(spec.expand()).parameters)

    assert written_out == supplied, 'writing a formulation out asks for data the model it came from did not'
