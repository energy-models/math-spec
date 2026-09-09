# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The closed operator set, and every table keyed by it."""

from __future__ import annotations

import pytest

from math_spec.degree import _REDUCTIONS
from math_spec.dimensions import _AMOUNTS, _CALL_RULES
from math_spec.lowering import _CALLS
from math_spec.operators import BUILTIN_NAMES, BUILTINS

#: Every operator that reaches lowering and the dim rules as a call. ``dual``
#: resolves to a leaf of its own, so no table after resolution has a row for it.
CALLED = BUILTIN_NAMES - {'dual'}


@pytest.mark.parametrize(
    ('table', 'keys'),
    [
        pytest.param(_CALLS, CALLED, id='lowering-has-one-rewrite-per-operator'),
        pytest.param(_CALL_RULES, CALLED, id='the-dim-rules-have-one-rule-per-operator'),
        pytest.param(
            _AMOUNTS,
            frozenset(name for name, builtin in BUILTINS.items() if builtin.required_value_kwargs),
            id='the-amount-words-cover-every-operator-taking-an-amount',
        ),
    ],
)
def test_every_table_keyed_by_operator_agrees_with_the_closed_set(table, keys):
    """An operator added to `BUILTINS` alone fails as a `KeyError` inside lowering (#401).

    Each table is keyed by operator name and read with `[]`, so the closed
    set and every table must name the same operators — here, before a model
    finds the missing row.
    """
    assert frozenset(table) == keys, (
        f'missing rows: {sorted(keys - set(table))}; stray rows: {sorted(set(table) - keys)}'
    )


def test_a_reduction_is_an_operator():
    assert _REDUCTIONS <= BUILTIN_NAMES, f'not operators: {sorted(_REDUCTIONS - BUILTIN_NAMES)}'
