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

import pytest

from math_spec.errors import SchemaError
from math_spec.lowering import to_program
from tests.fixtures import DISPATCH_MODEL, override, schema_of
from tests.test_sos import CURVE
from tools.render_tex import models

#: The curve masked by one of its own values parameters, so its expansion
#: derives the parameters a file cannot declare.
MASKED = override(
    CURVE,
    **{
        'piecewise.cost_curve.method': 'lp',
        'piecewise.cost_curve.points': 'bp_x',
        'piecewise.cost_curve.links': [['p', 'bp_x'], ['op_cost', 'bp_y', '>=']],
    },
)

#: Every model the repository ships, which is what the sources invariant is
#: asserted over — the same corpus the LaTeX gate renders.
MODELS = models()


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


def test_an_expansion_that_derived_parameters_prints_rather_than_round_trips():
    """`model_dump` drops the record of what fills them, so the file would declare data nobody has."""
    expanded = schema_of(MASKED).expand()

    assert 'cost_curve_starts' in expanded.parameters
    with pytest.raises(SchemaError, match=r"'cost_curve_starts'.*derived from a piecewise: block"):
        expanded.to_yaml()


def test_an_expansion_that_derived_nothing_is_still_a_file():
    expanded = schema_of(CURVE).expand()

    assert expanded.to_yaml(), 'a curve with no mask emits no parameter, so nothing is lost by writing it out'


@pytest.mark.parametrize('model', MODELS, ids=[m.stem for m in MODELS])
def test_the_same_sources_bind_a_model_and_its_expansion(model):
    """What a formulation may emit, asserted on every model the repository ships:
    a set emits no parameter, and every parameter a curve emits it derives. A
    consumer's `sources` argument is therefore the same either way."""
    spec = schema_of(model)
    supplied = {name for name, p in to_program(spec).parameters.items() if p.derivation is None}
    written_out = {name for name, p in to_program(spec.expand()).parameters.items() if p.derivation is None}

    assert written_out == supplied, 'writing a formulation out asks for data the model it came from did not'
