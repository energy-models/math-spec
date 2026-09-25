# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 51: a carrier's growth limit counts an asset in the first period it stands in only, not again after it retires.

PyPSA 1.3.0 counts an asset that retires in every later period too (PyPSA/PyPSA#1938).
The oracle gives each build its own carrier with the same limit: each carrier
then has one asset, which PyPSA counts in its first period, and a retired one
counted again repeats a row it already has.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

ISSUE = 1938
OPTIMIZE = {'multi_investment_periods': True}


def network(carriers: dict[str, str]):
    """Two periods, a solar unit that stands in 2020 only and one built in 2030, each under the carrier named for it."""
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
    n.add('Carrier', 'gas')
    for carrier in sorted(set(carriers.values())):
        n.add('Carrier', carrier, max_growth=10)
    for name, build_year in (('solar_old', 2020), ('solar_new', 2030)):
        n.add(
            'Generator',
            name,
            bus='grid',
            carrier=carriers[name],
            p_nom_extendable=True,
            p_nom_max=50,
            marginal_cost=1,
            capital_cost=5,
            build_year=build_year,
            lifetime=10,
        )
    n.add('Generator', 'backup', bus='grid', carrier='gas', p_nom=100, marginal_cost=80)
    n.add('Load', 'town', bus='grid', p_set=[15, 20, 15, 20])
    return n


def build():
    """Both solar units under one carrier with `max_growth = 10`; the old one retires after 2020."""
    return network({'solar_old': 'solar', 'solar_new': 'solar'})


def oracle():
    """The same network with a carrier per build: PyPSA counts each build in its first period only."""
    return [(1.0, network({'solar_old': 'solar20', 'solar_new': 'solar30'}))]
