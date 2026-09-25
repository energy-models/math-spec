# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 22: transformer losses in tangent form — a loss per transformer, as per line."""

from __future__ import annotations

import spine

OPTIMIZE = {'transmission_losses': {'mode': 'tangents', 'segments': 3}}


def build():
    """The spine plus a triangle of one 110 kV line and two transformers, one extendable and off-nominal tap, per-unit resistances a real transformer has, so its loss stays a few percent of the flow."""
    n = spine.build()
    n.add('Bus', ['a', 'b', 'c'], v_nom=110)
    n.add('Generator', 'hydro22', bus='a', p_nom=80, marginal_cost=10)
    n.add('Generator', 'diesel22', bus='b', p_nom=80, marginal_cost=50)
    n.add('Line', 'ab22', bus0='a', bus1='b', carrier='AC', x=30, r=6, s_nom=60)
    n.add('Transformer', 'bc22', bus0='b', bus1='c', x=0.1, r=0.03, s_nom=60)
    n.add(
        'Transformer',
        'ca22',
        bus0='c',
        bus1='a',
        x=0.12,
        r=0.02,
        s_nom=40,
        s_nom_extendable=True,
        s_nom_max=90,
        capital_cost=4,
        tap_ratio=1.05,
    )
    n.add('Load', 'town22', bus='c', p_set=[35, 55, 15, 45])
    return n
