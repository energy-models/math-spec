# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 41: a unit's cost and a link's efficiency differ by scenario."""

from __future__ import annotations

import spine

#: each scenario's own value, per component and attribute
PER_SCENARIO = {
    ('calm', 'gas41'): {'marginal_cost': 20},
    ('stormy', 'gas41'): {'marginal_cost': 80},
    ('calm', 'wire41'): {'efficiency': 0.9},
    ('stormy', 'wire41'): {'efficiency': 0.6},
}


def build():
    """The spine over two futures, with a gas unit that costs more and a link that delivers less in the stormy one."""
    n = spine.build()
    n.add('Generator', 'gas41', bus='south', p_nom=100, marginal_cost=20)
    n.add('Link', 'wire41', bus0='north', bus1='south', p_nom=40, efficiency=0.9)
    n.add('Load', 'port41', bus='south', p_set=60)
    n.set_scenarios({'calm': 0.6, 'stormy': 0.4})
    for (scenario, name), values in PER_SCENARIO.items():
        component = n.c.generators if name == 'gas41' else n.c.links
        for column, value in values.items():
            component.static.loc[(scenario, name), column] = value
    return n
