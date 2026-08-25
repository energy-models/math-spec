# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Dim sets are a type system, checked before any data is bound.

Every case here used to build a model and solve it — wrongly, or larger than
the file reads as. None of them needs data to be caught.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from math_spec.dimensions import DimensionError, check_schema, dims_of
from math_spec.resolution import Namespace, expression_of
from tests.fixtures import OPERATOR_PROBES, schema_of

if TYPE_CHECKING:
    from math_spec.model import Model

#: A *network* dispatch model: `fixtures.DISPATCH_MODEL` plus buses, so
#: `sum` and per-bus loads are in scope. The dim rules are mostly about
#: expressions that carry a dim their frame does not, which needs three dims to
#: state at all.
BASE = {
    'dimensions': {
        'snapshot': {'dtype': 'int'},
        'generator': {'values': ['wind', 'gas']},
        'bus': {'values': ['n', 's']},
    },
    'lookups': {
        'gen_bus': {'over': 'generator', 'into': 'bus'},
        # over `snapshot`, so it can partition the axis the translations walk
        'snap_bus': {'over': 'snapshot', 'into': 'bus'},
    },
    'parameters': {
        'p_max': {'dims': ['generator']},
        'cost': {'dims': ['generator']},
        'load': {'dims': ['snapshot', 'bus']},
        # a named offset or width counts positions, so the two rules about it
        # need a parameter that obeys them and one that spans the axis walked
        'spinup': {'dims': ['generator'], 'dtype': 'int'},
        'horizon': {'dims': ['snapshot'], 'dtype': 'int'},
        # over a dim `p` does not carry, so it is readable only through a `by=`
        'bus_lead': {'dims': ['bus'], 'dtype': 'int'},
    },
    'variables': {'p': {'foreach': ['snapshot', 'generator'], 'bounds': {'lower': 0, 'upper': 'p_max'}}},
    'constraints': {
        'balance': {
            'foreach': ['snapshot', 'bus'],
            'expression': 'sum(p, by=gen_bus) == load',
        }
    },
    'objective': {'sense': 'minimize', 'expression': 'sum(p * cost)'},
}


def _schema(**overrides) -> Model:
    return schema_of(BASE, **overrides)


def _dims(expr: str, schema: Model | None = None) -> frozenset[str]:
    s = schema or _schema()
    return dims_of(expression_of(expr, s, Namespace.of(s), 't'), s, 't')


def test_the_base_model_typechecks():
    check_schema(_schema())


# ---------------------------------------------------------------------------
# the rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('expr', 'expected'),
    [
        ('7', set()),
        ('cost', {'generator'}),
        ('p', {'snapshot', 'generator'}),
        ('-p', {'snapshot', 'generator'}),
        ('p * cost', {'snapshot', 'generator'}),
        ('sum(p)', set()),
        ('sum(p * cost)', set()),
        ('sum(p, over=generator)', {'snapshot'}),
        ('sum(p * cost, over=generator)', {'snapshot'}),
        ('sum(p, by=gen_bus)', {'snapshot', 'bus'}),
        ("shift(p, over=snapshot, offset=1, edge='wrap')", {'snapshot', 'generator'}),
        ("shift(p, over=snapshot, offset=spinup, edge='wrap')", {'snapshot', 'generator'}),
        ('sum_back(p, over=snapshot, within=spinup)', {'snapshot', 'generator'}),
        # the same offset a `by=` makes readable: one lag per group it maps into
        ("shift(p, over=snapshot, offset=bus_lead, edge='wrap', by=snap_bus)", {'snapshot', 'generator'}),
        ('sum_back(p, over=snapshot, within=bus_lead, by=snap_bus)', {'snapshot', 'generator'}),
    ],
)
def test_dim_inference(expr, expected):
    assert _dims(expr) == expected


@pytest.mark.parametrize(
    ('expr', 'match'),
    [
        # the operator rules used to return the array unchanged. `sum(p, over=bus)` then
        # built and solved a model that silently never summed anything.
        pytest.param(
            'sum(p, over=bus)',
            r'sum\(over=bus\) but the expression has dims',
            id='sum-over-an-absent-dim-is-an-error-not-a-noop',
        ),
        pytest.param(
            'sum(sum(p))',
            r'the expression is already a scalar',
            id='a-bare-sum-of-a-scalar-is-an-error-not-a-noop',
        ),
        pytest.param(
            'sum(load, by=gen_bus)',
            r"sum\(by=gen_bus\) consumes 'generator', the dim it maps out of",
            id='sum-requires-the-grouped-dim',
        ),
        # `(inner - {over}) | {into}` is a union, and a union absorbs a collision.
        #
        # `sum(load, by=gen_bus)` -- with `load` already
        # carrying `bus` -- asks for `bus` twice: once as the operand's own dim, once
        # as the group its terms are placed into. The union returns one, so the rule reports
        # a shape no consumer can build: an array with a repeated dim is one that
        # fails silently or raises from outside any exception tree the language owns.
        #
        # Refusing it at load time is the one answer every consumer receives, which
        # is why the rule lives here.
        pytest.param(
            'sum(load * p, by=gen_bus)',
            'already carries',
            id='sum-into-a-dim-the-operand-already-carries',
        ),
        pytest.param(
            "shift(cost, over=snapshot, offset=1, edge='wrap')",
            r'shift\(over=snapshot\) but the expression has dims',
            id='shift-requires-the-dim',
        ),
        # A named offset or width counts positions along the axis its operator
        # walks. Both rules below were documented as load errors and enforced
        # nowhere (#58), so a fractional lag or a width that changed along the
        # very axis it measured rendered as though it were neither.
        pytest.param(
            "shift(p, over=snapshot, offset=cost, edge='wrap')",
            r'declared dtype: float',
            id='a-named-offset-is-integral',
        ),
        pytest.param(
            "shift(p, over=snapshot, offset=horizon, edge='wrap')",
            r'varies along the axis it walks is a permutation rather than a lag',
            id='a-named-offset-does-not-span-the-axis-it-walks',
        ),
        pytest.param(
            'sum_back(p, over=snapshot, within=cost)',
            r'declared dtype: float',
            id='a-named-width-is-integral',
        ),
        pytest.param(
            'sum_back(p, over=snapshot, within=horizon)',
            r'no longer "the last n"',
            id='a-named-width-does-not-span-the-summed-axis',
        ),
        # Before this was refused, it loaded clean and then raised a bare
        # `AssertionError` out of the typesetter (#62) — on the very rule
        # `walk.py` reads a named offset as always-backward *because of*.
        pytest.param(
            "shift(p, over=snapshot, offset=-spinup, edge='wrap')",
            r'negates a named offset',
            id='a-named-offset-is-not-negated-at-the-call',
        ),
        pytest.param(
            'sum_back(p, over=snapshot, within=-spinup)',
            r'which way a window reaches is the operator',
            id='a-named-width-has-no-direction-to-negate',
        ),
        pytest.param(
            "shift(p, over=snapshot, offset=bus_lead, edge='wrap')",
            r"varies over \['bus'\], which that coordinate does not carry",
            id='a-named-offset-is-read-where-the-expression-has-a-coordinate',
        ),
    ],
)
def test_an_ill_dimensioned_expression_is_rejected(expr, match):
    with pytest.raises(DimensionError, match=match):
        _dims(expr)


def test_an_outer_product_is_legal_and_carries_both_dim_sets():
    """Binary ops union. Requiring subset instead would reject the convex
    piecewise epigraph, which multiplies a per-segment slope by a per-snapshot
    variable on purpose. The guard is the constraint rule below: the *frame*
    has to declare the result."""
    assert _dims('cost + load') == {'generator', 'snapshot', 'bus'}


def test_broadcast_is_legal_when_one_side_contains_the_other():
    assert _dims('p * cost') == {'snapshot', 'generator'}
    assert _dims('p + 1') == {'snapshot', 'generator'}


# ---------------------------------------------------------------------------
# declaration-level rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('patch', 'match'),
    [
        # The rule that matters most: a dim the foreach does not declare
        # multiplies the rows this constraint builds.
        pytest.param(
            {'constraints.stray': {'foreach': ['snapshot'], 'expression': 'p <= p_max'}},
            r"carries dims \['generator'\] that are not in foreach",
            id='stray-dim-in-a-constraint',
        ),
        pytest.param(
            {'constraints.unused': {'foreach': ['snapshot', 'generator', 'bus'], 'expression': 'p <= p_max'}},
            r"does not carry \['bus'\]",
            id='foreach-dim-the-equation-never-uses',
        ),
        # the absence rules once documented an `any()` reduction here — a mask that fails
        # *open*, silently including everything.
        pytest.param(
            {'variables.cap': {'foreach': ['generator'], 'where': 'load > 0'}},
            r"where-parameter 'load' has dims \['bus', 'snapshot'\]",
            id='where-dim-outside-the-frame',
        ),
        pytest.param(
            {'variables.cap': {'foreach': ['generator'], 'where': 'snapshot > 0'}},
            "where-comparison on dimension 'snapshot'",
            id='where-comparison-on-a-dim-outside-the-frame',
        ),
        pytest.param(
            {'variables.cap': {'foreach': ['generator'], 'bounds': {'lower': 0, 'upper': 'load'}}},
            r"bounds.upper parameter 'load' has dims \['bus', 'snapshot'\]",
            id='bound-parameter-dim-outside-foreach',
        ),
    ],
)
def test_an_ill_dimensioned_declaration_is_rejected(patch, match):
    with pytest.raises(DimensionError, match=match):
        _schema(**patch)


@pytest.mark.parametrize('path', OPERATOR_PROBES, ids=lambda p: p.name)
def test_every_operator_probe_typechecks(path):
    """The corpus that lives with the language, swept by the rules above.

    The probes are the language's own corpus (#1149): one construct per file,
    and the same directory the operator reference is generated from, so a
    probe added for the page is typechecked here too.
    """
    check_schema(schema_of(path))
