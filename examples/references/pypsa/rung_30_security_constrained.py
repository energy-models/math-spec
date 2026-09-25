# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 30: security-constrained — a meshed triangle of lines and two transformers, one extendable, that must carry their flow within their rating after any one of three outages."""

from __future__ import annotations

import pandas as pd
import spine

BRANCH_OUTAGES = pd.MultiIndex.from_tuples([('Line', 'ab'), ('Line', 'ca'), ('Transformer', 'ca_t')])


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', 'a')
    n.add('Bus', 'b')
    n.add('Bus', 'c')
    n.add('Generator', 'hydro30', bus='a', p_nom=100, marginal_cost=10)
    n.add('Generator', 'diesel30', bus='b', p_nom=100, marginal_cost=50)
    n.add('Generator', 'peak30', bus='c', p_nom=100, marginal_cost=200)
    n.add('Load', 'town30', bus='c', p_set=[40, 60, 80, 50])
    n.add('Line', 'ab', bus0='a', bus1='b', x=0.1, s_nom=60)
    n.add('Line', 'bc', bus0='b', bus1='c', x=0.1, s_nom=60, s_max_pu=0.9)
    n.add('Line', 'ca', bus0='c', bus1='a', x=0.1, s_nom_extendable=True, capital_cost=5, s_nom_max=200)
    n.add('Transformer', 'ca_t', bus0='c', bus1='a', x=0.2, s_nom=30)
    n.add('Transformer', 'bc_t', bus0='b', bus1='c', x=0.3, s_nom_extendable=True, capital_cost=3, s_nom_max=50)
    return n
