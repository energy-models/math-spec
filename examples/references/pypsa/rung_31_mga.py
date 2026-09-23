# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 31: MGA — the most wind a network builds within a tenth above its least cost."""

from __future__ import annotations

import spine

MGA = {'weights': {'Generator': {'p_nom': {'wind31': 1}}}, 'sense': 'max', 'slack': 0.1}


def build():
    """The spine plus a bus that extendable wind and gas and a fixed hydro unit with a capital cost serve; the wind carries a build already, so the objective has a constant."""
    n = spine.build()
    n.add('Bus', 'mga31')
    n.add(
        'Generator',
        'wind31',
        bus='mga31',
        p_nom=10,
        p_nom_extendable=True,
        capital_cost=20,
        p_max_pu=[0.3, 0.9, 0.5, 0.6],
    )
    n.add('Generator', 'gas31', bus='mga31', p_nom_extendable=True, capital_cost=8, marginal_cost=40)
    n.add('Generator', 'hydro31', bus='mga31', p_nom=15, capital_cost=3, marginal_cost=5)
    n.add('Load', 'mga31_load', bus='mga31', p_set=[50, 80, 60, 70])
    return n
