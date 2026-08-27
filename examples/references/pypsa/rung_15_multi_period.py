# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 15: two investment periods — build years, lifetimes, period weights and a carrier's growth limit, stated by `pypsa_multi_period.yaml`."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

MODEL = 'pypsa_multi_period.yaml'
OPTIMIZE = {'multi_investment_periods': True}


def build():
    """A whole network, not the spine: eight snapshots over two periods, a unit that retires, two wind builds capped by growth."""
    import pypsa

    n = pypsa.Network()
    n.snapshots = pd.MultiIndex.from_tuples(
        [(2020, datetime(2020, 1, 1, t)) for t in range(4)] + [(2030, datetime(2030, 1, 1, t)) for t in range(4)]
    )
    n.investment_periods = [2020, 2030]
    n.investment_period_weightings['objective'] = [1.0, 0.5]
    n.investment_period_weightings['years'] = [10.0, 10.0]
    n.snapshot_weightings['objective'] = [2.0, 1.5, 2.5, 2.0, 2.0, 1.5, 2.5, 2.0]
    n.add('Bus', ['north', 'south'])
    n.add('Carrier', 'wind', max_growth=50, max_relative_growth=0.5)
    n.add('Carrier', 'gas')
    n.add('Generator', 'old_gas', bus='north', carrier='gas', p_nom=40, marginal_cost=30, build_year=2010, lifetime=15)
    n.add(
        'Generator',
        'wind20',
        bus='north',
        carrier='wind',
        p_nom_extendable=True,
        p_nom_max=200,
        marginal_cost=1,
        capital_cost=100,
        build_year=2020,
        lifetime=30,
        p_max_pu=[0.8, 0.6, 0.7, 0.5, 0.8, 0.6, 0.7, 0.5],
    )
    n.add(
        'Generator',
        'wind30',
        bus='south',
        carrier='wind',
        p_nom_extendable=True,
        p_nom_max=200,
        marginal_cost=1,
        capital_cost=80,
        build_year=2030,
        lifetime=30,
        p_max_pu=[0.9, 0.7, 0.6, 0.8, 0.9, 0.7, 0.6, 0.8],
    )
    n.add(
        'Generator',
        'gas30',
        bus='south',
        carrier='gas',
        p_nom_extendable=True,
        p_nom_max=200,
        marginal_cost=40,
        capital_cost=50,
        build_year=2030,
        lifetime=30,
    )
    n.add('Link', 'wire15', bus0='north', bus1='south', p_nom=60, p_min_pu=-1, efficiency=0.95)
    n.add('Load', 'town15', bus='north', p_set=[20, 30, 25, 20, 35, 45, 40, 30])
    n.add('Load', 'port15', bus='south', p_set=[10, 20, 15, 10, 30, 40, 35, 25])
    return n
