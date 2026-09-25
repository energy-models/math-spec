# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 35: a global constraint for one investment period — a CO2 cap on 2030 alone, one over the horizon, and a 2020 limit on a carrier with storage that reopens per period."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

OPTIMIZE = {'multi_investment_periods': True}


def build():
    """A whole network, not the spine: eight snapshots over two periods of unequal years, two emitting units, a hydro carrier with a unit and storage."""
    import pypsa

    n = pypsa.Network()
    n.snapshots = pd.MultiIndex.from_tuples(
        [(2020, datetime(2020, 1, 1, t)) for t in range(4)] + [(2030, datetime(2030, 1, 1, t)) for t in range(4)]
    )
    n.investment_periods = [2020, 2030]
    n.investment_period_weightings['objective'] = [1.0, 0.5]
    n.investment_period_weightings['years'] = [5.0, 10.0]
    n.snapshot_weightings['generators'] = [1.0, 2.0, 1.0, 2.0, 1.0, 2.0, 1.0, 2.0]
    n.add('Carrier', 'coal35', co2_emissions=1.0)
    n.add('Carrier', 'gas35', co2_emissions=0.4)
    n.add('Carrier', 'hydro35')
    n.add('Bus', 'hub')
    n.add('Generator', 'coal35', bus='hub', carrier='coal35', p_nom=100, marginal_cost=10, efficiency=0.4)
    n.add('Generator', 'gas35', bus='hub', carrier='gas35', p_nom=100, marginal_cost=30, efficiency=0.5)
    n.add('Generator', 'clean35', bus='hub', p_nom=200, marginal_cost=60)
    n.add('Generator', 'river35', bus='hub', carrier='hydro35', p_nom=30, marginal_cost=5)
    n.add(
        'StorageUnit',
        'dam35',
        bus='hub',
        carrier='hydro35',
        p_nom=15,
        max_hours=4,
        state_of_charge_initial=20,
        state_of_charge_initial_per_period=True,
    )
    n.add('Store', 'pond35', bus='hub', carrier='hydro35', e_nom=30, e_initial=10, e_initial_per_period=True)
    n.add('Load', 'town35', bus='hub', p_set=[60, 80, 70, 50, 90, 110, 100, 80])
    n.add(
        'GlobalConstraint',
        'co2_2030',
        type='primary_energy',
        carrier_attribute='co2_emissions',
        sense='<=',
        constant=3500,
        investment_period=2030,
    )
    n.add(
        'GlobalConstraint',
        'co2_all',
        type='primary_energy',
        carrier_attribute='co2_emissions',
        sense='<=',
        constant=6000,
    )
    n.add(
        'GlobalConstraint',
        'hydro_2020',
        type='operational_limit',
        carrier_attribute='hydro35',
        sense='<=',
        constant=600,
        investment_period=2020,
    )
    return n
