# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 53: a `transmission_volume_expansion_limit` row holds in every scenario under `multi_investment_periods`.

PyPSA 1.3.0 builds no such row on a network with scenarios and investment
periods (PyPSA/PyPSA#1939). The two futures are identical, so the oracle is the
same network without scenarios, which PyPSA solves with the row.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

ISSUE = 1939
OPTIMIZE = {'multi_investment_periods': True}


def network():
    """Two periods, a cheap unit behind an extendable line whose volume a limit of 60 caps."""
    import pypsa

    n = pypsa.Network()
    n.snapshots = pd.MultiIndex.from_tuples(
        [(2020, datetime(2020, 1, 1, t)) for t in range(2)] + [(2030, datetime(2030, 1, 1, t)) for t in range(2)]
    )
    n.investment_periods = [2020, 2030]
    n.investment_period_weightings['objective'] = [1.0, 0.5]
    n.investment_period_weightings['years'] = [10.0, 10.0]
    n.snapshot_weightings['objective'] = [2.0, 1.5, 2.5, 2.0]
    n.add('Bus', ['hill', 'town'])
    n.add('Carrier', 'AC')
    n.add('Generator', 'hydro53', bus='hill', p_nom=100, marginal_cost=5)
    n.add('Generator', 'diesel53', bus='town', p_nom=100, marginal_cost=90)
    n.add(
        'Line',
        'tie53',
        bus0='hill',
        bus1='town',
        x=0.1,
        carrier='AC',
        length=3,
        s_nom_extendable=True,
        s_nom_max=100,
        capital_cost=1,
        build_year=2020,
        lifetime=30,
    )
    n.add('Load', 'town_load', bus='town', p_set=[40, 50, 60, 45])
    n.add(
        'GlobalConstraint',
        'volume53',
        type='transmission_volume_expansion_limit',
        carrier_attribute='AC',
        sense='<=',
        constant=60,
    )
    return n


def build():
    """The same network over two identical futures."""
    n = network()
    n.set_scenarios({'calm': 0.6, 'stormy': 0.4})
    return n


def oracle():
    """The network without scenarios: the futures are identical, so the expected cost is its cost."""
    return [(1.0, network())]
