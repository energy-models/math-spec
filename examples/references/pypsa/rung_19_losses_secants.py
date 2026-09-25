# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 19: transmission losses in secant form — the same loss per line, its cuts placed by PyPSA's tolerance loop."""

from __future__ import annotations

import spine

OPTIMIZE = {'transmission_losses': {'mode': 'secants', 'atol': 1, 'rtol': 0.1, 'max_segments': 20}}


def build():
    """Rung 13's 110 kV triangle, unchanged, so the two modes differ only in the cuts."""
    n = spine.build()
    n.add('Bus', ['a', 'b', 'c'], v_nom=110)
    n.add('Generator', 'hydro19', bus='a', p_nom=80, marginal_cost=10)
    n.add('Generator', 'diesel19', bus='b', p_nom=80, marginal_cost=50)
    n.add('Line', 'ab19', bus0='a', bus1='b', carrier='AC', x=30, r=6, s_nom=60)
    n.add('Line', 'bc19', bus0='b', bus1='c', carrier='AC', x=60, r=9.7, s_nom=60)
    n.add(
        'Line',
        'ca19',
        bus0='c',
        bus1='a',
        carrier='AC',
        x=45,
        r=6,
        s_nom=40,
        s_nom_extendable=True,
        s_nom_max=90,
        capital_cost=4,
    )
    n.add('Load', 'town19', bus='c', p_set=[35, 55, 15, 45])
    return n
