# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 32: storage that stands in one period only — two built in the later period open at its first snapshot, and a cyclic one that retires closes on its own last snapshot."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

OPTIMIZE = {'multi_investment_periods': True}


def build():
    """A whole network, not the spine: eight snapshots over two periods, two storages built in 2030, one cyclic store that retires after 2020."""
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
    n.add('Generator', 'base32', bus='hub', p_nom=100, marginal_cost=10)
    n.add('Generator', 'peak32', bus='hub', p_nom=200, marginal_cost=[80, 20, 90, 30, 80, 20, 90, 30])
    n.add(
        'StorageUnit',
        'su_late',
        bus='hub',
        p_nom=15,
        max_hours=4,
        standing_loss=0.02,
        cyclic_state_of_charge=True,
        build_year=2030,
        lifetime=30,
    )
    n.add('Store', 'e_late', bus='hub', e_nom=30, e_initial=5, build_year=2030, lifetime=30)
    n.add('Store', 'e_retire', bus='hub', e_nom=30, standing_loss=0.01, e_cyclic=True, build_year=2020, lifetime=10)
    n.add('Load', 'hub_load', bus='hub', p_set=[40, 60, 70, 40, 90, 110, 120, 90])
    return n
