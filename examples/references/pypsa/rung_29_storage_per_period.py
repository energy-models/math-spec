# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 29: storage per investment period — a storage unit and a store that cycle within each period, two that reopen on their initial level, and a ramp that restarts at a period start."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

OPTIMIZE = {'multi_investment_periods': True}


def build():
    """A whole network, not the spine: eight snapshots over two periods, four storages that each close or reopen per period, a ramp-limited coal unit."""
    import pypsa

    n = pypsa.Network()
    n.snapshots = pd.MultiIndex.from_tuples(
        [(2020, datetime(2020, 1, 1, t)) for t in range(4)] + [(2030, datetime(2030, 1, 1, t)) for t in range(4)]
    )
    n.investment_periods = [2020, 2030]
    n.investment_period_weightings['objective'] = [1.0, 0.5]
    n.investment_period_weightings['years'] = [10.0, 10.0]
    n.snapshot_weightings['objective'] = [2.0, 1.5, 2.5, 2.0, 2.0, 1.5, 2.5, 2.0]
    n.snapshot_weightings['stores'] = [0.5, 2.0, 1.5, 2.5, 0.5, 2.0, 1.5, 2.5]
    n.add('Bus', 'hub')
    n.add('Generator', 'coal29', bus='hub', p_nom=100, marginal_cost=10, ramp_limit_up=0.1, ramp_limit_down=0.1)
    n.add('Generator', 'peak29', bus='hub', p_nom=200, marginal_cost=[80, 20, 90, 30, 80, 20, 90, 30])
    n.add('StorageUnit', 'su_cycle', bus='hub', p_nom=15, max_hours=4, cyclic_state_of_charge_per_period=True)
    n.add(
        'StorageUnit',
        'su_reset',
        bus='hub',
        p_nom=15,
        max_hours=4,
        state_of_charge_initial=20,
        state_of_charge_initial_per_period=True,
    )
    n.add('Store', 'e_cycle', bus='hub', e_nom=30, e_cyclic_per_period=True)
    n.add('Store', 'e_reset', bus='hub', e_nom=30, e_initial=10, e_initial_per_period=True)
    n.add('Load', 'hub_load', bus='hub', p_set=[40, 60, 70, 40, 90, 110, 120, 90])
    return n
