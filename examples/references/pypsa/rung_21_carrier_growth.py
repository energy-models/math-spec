# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 21: a carrier's growth limit binds its non-generator builds — a storage unit and two stores over two periods."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

OPTIMIZE = {'multi_investment_periods': True}


def build():
    """A whole network, not the spine: cheap solar only at the first snapshot of each period, so battery capacity pays off but its growth is capped."""
    import pypsa

    n = pypsa.Network()
    n.snapshots = pd.MultiIndex.from_tuples(
        [(2020, datetime(2020, 1, 1, t)) for t in range(2)] + [(2030, datetime(2030, 1, 1, t)) for t in range(2)]
    )
    n.investment_periods = [2020, 2030]
    n.investment_period_weightings['objective'] = [1.0, 0.5]
    n.investment_period_weightings['years'] = [10.0, 10.0]
    n.snapshot_weightings['objective'] = [2.0, 1.5, 2.5, 2.0]
    n.add('Bus', 'grid')
    n.add('Carrier', 'solar')
    n.add('Carrier', 'gas')
    n.add('Carrier', 'battery', max_growth=20, max_relative_growth=0.5)
    n.add('Generator', 'solar', bus='grid', carrier='solar', p_nom=100, marginal_cost=1, p_max_pu=[1, 0, 1, 0])
    n.add('Generator', 'backup', bus='grid', carrier='gas', p_nom=200, marginal_cost=80)
    n.add(
        'StorageUnit',
        'bat20',
        bus='grid',
        carrier='battery',
        p_nom_extendable=True,
        p_nom_max=100,
        max_hours=4,
        capital_cost=50,
        build_year=2020,
        lifetime=30,
    )
    n.add(
        'Store',
        'tank20',
        bus='grid',
        carrier='battery',
        e_nom_extendable=True,
        e_nom_max=10,
        capital_cost=10,
        build_year=2020,
        lifetime=30,
    )
    n.add(
        'Store',
        'tank30',
        bus='grid',
        carrier='battery',
        e_nom_extendable=True,
        e_nom_max=100,
        capital_cost=8,
        build_year=2030,
        lifetime=30,
    )
    n.add('Load', 'town', bus='grid', p_set=[40, 60, 40, 80])
    return n
