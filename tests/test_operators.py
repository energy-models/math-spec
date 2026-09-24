# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The closed operator set, and every table keyed by it."""

from __future__ import annotations

from math_spec.operators import AMOUNTS, BUILTINS


def test_the_amount_words_cover_every_operator_taking_an_amount():
    """An operator added to `BUILTINS` alone fails as a `KeyError` inside resolution (#401).

    The table is keyed by operator name and read with `[]`, so the closed set
    and the table must name the same operators — here, before a model finds
    the missing row.
    """
    keys = frozenset(name for name, builtin in BUILTINS.items() if builtin.required_value_kwargs)
    assert frozenset(AMOUNTS) == keys, (
        f'missing rows: {sorted(keys - set(AMOUNTS))}; stray rows: {sorted(set(AMOUNTS) - keys)}'
    )
