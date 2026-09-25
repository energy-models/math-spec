# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 23: transformer losses in secant form — the same loss per transformer, its cuts placed by PyPSA's tolerance loop."""

from __future__ import annotations

import spine

OPTIMIZE = {'transmission_losses': {'mode': 'secants', 'atol': 1, 'rtol': 0.1, 'max_segments': 20}}


def build():
    """Rung 22's triangle, unchanged, so the two modes differ only in the cuts."""
    n = spine.build()
    n.add('Bus', ['a', 'b', 'c'], v_nom=110)
    n.add('Generator', 'hydro23', bus='a', p_nom=80, marginal_cost=10)
    n.add('Generator', 'diesel23', bus='b', p_nom=80, marginal_cost=50)
    n.add('Line', 'ab23', bus0='a', bus1='b', carrier='AC', x=30, r=6, s_nom=60)
    n.add('Transformer', 'bc23', bus0='b', bus1='c', x=0.1, r=0.03, s_nom=60)
    n.add(
        'Transformer',
        'ca23',
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
    n.add('Load', 'town23', bus='c', p_set=[35, 55, 15, 45])
    return n
