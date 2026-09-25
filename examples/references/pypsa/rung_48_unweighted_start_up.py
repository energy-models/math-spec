# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 48: a start and a stop cost what they cost — no snapshot weight and no period weight on them, over two weighted periods."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

OPTIMIZE = {'multi_investment_periods': True}


def build():
    """A whole network, not the spine: a committable peaker that starts and stops once in each period."""
    import pypsa

    n = pypsa.Network()
    n.snapshots = pd.MultiIndex.from_tuples(
        [(2020, datetime(2020, 1, 1, t)) for t in range(3)] + [(2030, datetime(2030, 1, 1, t)) for t in range(3)]
    )
    n.investment_periods = [2020, 2030]
    n.investment_period_weightings['objective'] = [1.0, 0.5]
    n.investment_period_weightings['years'] = [10.0, 10.0]
    n.snapshot_weightings['objective'] = [2.0, 1.5, 2.5, 2.0, 1.5, 2.5]
    n.add('Bus', 'grid')
    n.add('Generator', 'base48', bus='grid', p_nom=60, marginal_cost=10)
    n.add('Generator', 'dear48', bus='grid', p_nom=100, marginal_cost=90)
    n.add(
        'Generator',
        'peak48',
        bus='grid',
        p_nom=50,
        marginal_cost=20,
        committable=True,
        p_min_pu=0.4,
        start_up_cost=300,
        shut_down_cost=100,
        up_time_before=0,
    )
    n.add('Load', 'town48', bus='grid', p_set=[50, 100, 50, 50, 100, 50])
    return n
