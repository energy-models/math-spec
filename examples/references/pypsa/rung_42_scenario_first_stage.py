# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 42: an extendable unit's capital cost and build cap differ by scenario."""

from __future__ import annotations

import spine

#: each scenario's own value, per attribute of the extendable unit
PER_SCENARIO = {
    'calm': {'capital_cost': 20, 'p_nom_max': 100},
    'stormy': {'capital_cost': 60, 'p_nom_max': 30},
}


def build():
    """The spine over two futures, with an extendable wind unit that costs more and may be built less in the stormy one."""
    n = spine.build()
    n.add('Generator', 'wind42', bus='south', p_nom_extendable=True, p_nom_max=100, marginal_cost=1, capital_cost=20)
    n.set_scenarios({'calm': 0.6, 'stormy': 0.4})
    for scenario, values in PER_SCENARIO.items():
        for column, value in values.items():
            n.c.generators.static.loc[(scenario, 'wind42'), column] = value
    return n
