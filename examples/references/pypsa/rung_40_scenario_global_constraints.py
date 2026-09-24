# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 40: a global constraint takes its own constant and sense in each scenario."""

from __future__ import annotations

import spine

#: each scenario's own constant and sense, per row
PER_SCENARIO = {
    ('calm', 'volume40'): {'constant': 60},
    ('stormy', 'volume40'): {'constant': 20},
    ('calm', 'co2_40'): {'constant': 250, 'sense': '<='},
    ('stormy', 'co2_40'): {'constant': 200, 'sense': '=='},
}


def build():
    """The spine over two futures, with an extendable line under a volume limit and a CO2 row that differ by scenario."""
    n = spine.build()
    n.add('Carrier', 'AC')
    n.add('Carrier', 'coalc', co2_emissions=0.5)
    n.c.generators.static.loc['coal', 'carrier'] = 'coalc'
    n.add(
        'Line',
        'tie40',
        bus0='north',
        bus1='south',
        x=0.1,
        carrier='AC',
        length=2,
        s_nom_extendable=True,
        capital_cost=1,
    )
    n.add('Load', 'port40', bus='south', p_set=30)
    n.add(
        'GlobalConstraint',
        'volume40',
        type='transmission_volume_expansion_limit',
        carrier_attribute='AC',
        sense='<=',
        constant=60,
    )
    n.add(
        'GlobalConstraint', 'co2_40', type='primary_energy', carrier_attribute='co2_emissions', sense='<=', constant=250
    )
    n.set_scenarios({'calm': 0.6, 'stormy': 0.4})
    for row, values in PER_SCENARIO.items():
        for column, value in values.items():
            n.c.global_constraints.static.loc[row, column] = value
    return n
