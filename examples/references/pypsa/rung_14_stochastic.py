# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 14: two futures and a risk preference — capacity chosen once, dispatch per scenario, stated by `pypsa_stochastic.yaml`."""

from __future__ import annotations

import spine

MODEL = 'pypsa_stochastic.yaml'


def build():
    """The spine plus an extendable wind unit whose availability and the south's load differ between a calm and a stormy future."""
    n = spine.build()
    n.add('Generator', 'wind14', bus='south', p_nom_extendable=True, p_nom_max=100, marginal_cost=1, capital_cost=20)
    n.add('Load', 'port14', bus='south')
    n.set_scenarios({'calm': 0.6, 'stormy': 0.4})
    n.c.loads.dynamic.p_set[('calm', 'port14')] = [10, 20, 15, 10]
    n.c.loads.dynamic.p_set[('stormy', 'port14')] = [40, 60, 50, 30]
    n.c.generators.dynamic.p_max_pu[('calm', 'wind14')] = [0.9, 0.7, 0.8, 0.6]
    n.c.generators.dynamic.p_max_pu[('stormy', 'wind14')] = [0.3, 0.2, 0.4, 0.1]
    n.set_risk_preference(alpha=0.5, omega=0.3)
    return n
