# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 38: delays per investment period — a link that wraps its delayed flow within each period, and a process that loses what is still in transit at each period's start."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

OPTIMIZE = {'multi_investment_periods': True}

#: The `generators` weighting is uniform, as on rung 16, so a delay of `n` is a
#: shift of exactly `n` positions. The `objective` column stays non-uniform.
WEIGHTINGS = {'objective': [2.0, 1.5, 2.5, 3.0, 2.0, 1.5, 2.5, 3.0], 'generators': [1.0] * 8}

#: Demand differs from snapshot to snapshot, so which snapshot a delayed flow is
#: read from changes what it costs.
DEMAND = [20.0, 15.0, 25.0, 10.0, 30.0, 35.0, 5.0, 40.0]


def build():
    """A whole network, not the spine: eight snapshots over two periods, a source, a delayed link and a delayed process.

    ``pipe_wrap`` delays by two snapshots and wraps cyclically, so the first two
    snapshots of each period read the last two of that same period, never the
    other period. ``conv_lose`` delays by one and does not wrap, so the first
    snapshot of each period, 2030 included, receives nothing and its demand falls
    to the backup. The source is capped, so where each delayed flow is read from
    decides how much of the backup runs.
    """
    import pypsa

    n = pypsa.Network()
    n.snapshots = pd.MultiIndex.from_tuples(
        [(2020, datetime(2020, 1, 1, t)) for t in range(4)] + [(2030, datetime(2030, 1, 1, t)) for t in range(4)]
    )
    n.investment_periods = [2020, 2030]
    n.investment_period_weightings['objective'] = [1.0, 0.5]
    n.investment_period_weightings['years'] = [10.0, 10.0]
    for column, values in WEIGHTINGS.items():
        n.snapshot_weightings[column] = values
    n.add('Bus', ['source', 'sink_wrap', 'sink_lose'])
    n.add('Generator', 'spring38', bus='source', p_nom=60, marginal_cost=5)
    n.add('Generator', 'backup_wrap38', bus='sink_wrap', p_nom=200, marginal_cost=100)
    n.add('Generator', 'backup_lose38', bus='sink_lose', p_nom=200, marginal_cost=100)
    n.add('Link', 'pipe_wrap', bus0='source', bus1='sink_wrap', p_nom=30, delay=2, cyclic_delay=True)
    n.add('Process', 'conv_lose', bus0='source', bus1='sink_lose', p_nom=30, delay1=1, cyclic_delay1=False)
    n.add('Load', 'load_wrap', bus='sink_wrap', p_set=DEMAND)
    n.add('Load', 'load_lose', bus='sink_lose', p_set=DEMAND)
    return n
