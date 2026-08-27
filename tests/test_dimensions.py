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

from math_spec.dimensions import _AMOUNT_WORDING, DimensionError, check_schema, dims_of
from math_spec.operators import BUILTINS
from math_spec.resolution import Namespace, expression_of
from tests.fixtures import OPERATOR_PROBES, schema_of

if TYPE_CHECKING:
    from math_spec.model import Model

#: `fixtures.DISPATCH_MODEL` plus buses: a dim rule is mostly about an
#: expression carrying a dim its frame does not, which needs three dims to
#: state. `snap_bus` is over `snapshot` so it can partition the axis the
#: translations walk; `spinup` and `horizon` are the named amount that obeys
#: the position rules and the one that spans the axis walked; `bus_lead` is
#: over a dim `p` does not carry, so it is readable only through a `by=`.
BASE = {
    'dimensions': {
        'snapshot': {'dtype': 'int'},
        'generator': {'values': ['wind', 'gas']},
        'bus': {'values': ['n', 's']},
    },
    'lookups': {
        'gen_bus': {'over': 'generator', 'into': 'bus'},
        'snap_bus': {'over': 'snapshot', 'into': 'bus'},
    },
    'parameters': {
        'p_max': {'dims': ['generator']},
        'cost': {'dims': ['generator']},
        'load': {'dims': ['snapshot', 'bus']},
        'spinup': {'dims': ['generator'], 'dtype': 'int'},
        'horizon': {'dims': ['snapshot'], 'dtype': 'int'},
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


def _dims(expr: str) -> frozenset[str]:
    s = _schema()
    return dims_of(expression_of(expr, s, Namespace.of(s), 't'), s, 't')


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
        ('sum_forward(p, over=snapshot, within=spinup)', {'snapshot', 'generator'}),
        # the same offset a `by=` makes readable: one lag per group it maps into
        ("shift(p, over=snapshot, offset=bus_lead, edge='wrap', by=snap_bus)", {'snapshot', 'generator'}),
        ('sum_back(p, over=snapshot, within=bus_lead, by=snap_bus)', {'snapshot', 'generator'}),
        pytest.param('p + 1', {'snapshot', 'generator'}, id='a-scalar-broadcasts'),
        pytest.param(
            'sum_forward(p, over=snapshot, within=bus_lead, by=snap_bus)',
            {'snapshot', 'generator'},
            id='a-leading-window-partitioned-by-a-lookup',
        ),
    ],
)
def test_dim_inference(expr, expected):
    assert _dims(expr) == expected


@pytest.mark.parametrize(
    ('expr', 'match'),
    [
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
        pytest.param(
            "shift(p, over=snapshot, offset=cost, edge='wrap')",
            r'declared dtype: float',
            id='a-named-offset-is-integral-58',
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
        pytest.param(
            "shift(p, over=snapshot, offset=-spinup, edge='wrap')",
            r'negates a named offset',
            id='a-named-offset-is-not-negated-at-the-call-62',
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
        # its own wording, because the window it stops being is a different one
        pytest.param(
            'sum_forward(p, over=snapshot, within=horizon)',
            r'no longer "the next n"',
            id='a-named-forward-width-does-not-span-the-summed-axis',
        ),
        pytest.param(
            'sum_forward(p, over=snapshot, within=-spinup)',
            r"operator's own name rather than the sign of its width",
            id='a-named-forward-width-has-no-direction-to-negate',
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


# ---------------------------------------------------------------------------
# declaration-level rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('patch', 'match'),
    [
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
    check_schema(schema_of(path))


def test_every_operator_taking_a_named_amount_carries_its_wording():
    """An operator with an amount lands with its rules, or this fails.

    `sum_forward` was written on a branch beside the one that added these
    tables, so each was right about the operators it knew and neither knew the
    other's. Git merged them without a conflict --- the edits were in different
    places --- both branches were green, and the result raised `KeyError` from
    `_AMOUNT_WORDING[node.name]` on every model that used the new operator. A table
    keyed by operator name is only as good as something asking whether it knows
    them all.
    """
    takes_an_amount = {name for name, builtin in BUILTINS.items() if builtin.required_value_kwargs}
    assert set(_AMOUNT_WORDING) == takes_an_amount
