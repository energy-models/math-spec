# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 18: transformer — passive branches under KVL in a meshed triangle, one fixed and on a set flow, two extendable in parallel."""

from __future__ import annotations

from math import nan

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', 'a')
    n.add('Bus', 'b')
    n.add('Bus', 'c')
    n.add('Generator', 'hydro18', bus='a', p_nom=80, marginal_cost=10)
    n.add('Generator', 'diesel18', bus='b', p_nom=80, marginal_cost=50)
    n.add('Load', 'town18', bus='c', p_set=45)
    n.add('Line', 'ab', bus0='a', bus1='b', carrier='AC', length=30, x=0.1, r=0.01, s_nom=60)
    n.add(
        'Transformer',
        'bc',
        bus0='b',
        bus1='c',
        x=0.1,
        r=0.01,
        s_nom=60,
        phase_shift=10,
        s_set=[16, nan, nan, nan],
    )
    n.add(
        'Transformer',
        'ca',
        bus0='c',
        bus1='a',
        x=0.15,
        r=0.01,
        s_nom=60,
        s_nom_extendable=True,
        capital_cost=10,
        s_nom_min=5,
        s_nom_max=40,
        s_nom_set=30,
        tap_ratio=1.05,
    )
    n.add(
        'Transformer',
        'ca2',
        bus0='c',
        bus1='a',
        x=0.12,
        r=0.01,
        s_nom=60,
        s_nom_extendable=True,
        capital_cost=8,
        s_nom_min=5,
        s_nom_max=40,
    )
    return n
