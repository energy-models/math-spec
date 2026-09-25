# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 54: each scenario delays a link's and a process's flow by its own `delay`.

PyPSA 1.3.0 groups the ports by delay over all scenarios and shifts every group
in every scenario, so a port whose delay differs by scenario delivers twice
(PyPSA/PyPSA#1941). Nothing is extendable, so the scenarios do not interact: the
oracle is each future solved alone, weighted by its probability.
"""

from __future__ import annotations

from datetime import datetime

ISSUE = 1941

#: The `generators` weighting is uniform, as on rung 16, so a delay of `n` is a
#: shift of exactly `n` positions. The `objective` column stays non-uniform.
WEIGHTINGS = {'objective': [2.0, 1.5, 2.5, 3.0], 'generators': [1.0] * 4}
DEMAND = [20.0, 35.0, 5.0, 30.0]
SCENARIOS = {'calm': 0.6, 'stormy': 0.4}

#: each future's own delay, per port: the calm one delivers at once, the stormy one a snapshot late
DELAYS = {
    'calm': {'pipe54': {'delay': 0, 'cyclic_delay': True}, 'conv54': {'delay1': 0, 'cyclic_delay1': True}},
    'stormy': {'pipe54': {'delay': 1, 'cyclic_delay': True}, 'conv54': {'delay1': 1, 'cyclic_delay1': False}},
}


def network(delays: dict[str, dict[str, object]]):
    """A capped source feeding two sinks, one through a link and one through a process, with the given delays."""
    import pypsa

    n = pypsa.Network()
    n.set_snapshots([datetime(2015, 1, 1, hour) for hour in range(4)])
    for column, values in WEIGHTINGS.items():
        n.snapshot_weightings[column] = values
    n.add('Bus', ['source', 'sink_link', 'sink_process'])
    n.add('Generator', 'spring54', bus='source', p_nom=50, marginal_cost=5)
    n.add('Generator', 'backup_link54', bus='sink_link', p_nom=200, marginal_cost=100)
    n.add('Generator', 'backup_process54', bus='sink_process', p_nom=200, marginal_cost=100)
    n.add('Link', 'pipe54', bus0='source', bus1='sink_link', p_nom=30, **delays['pipe54'])
    n.add('Process', 'conv54', bus0='source', bus1='sink_process', p_nom=30, **delays['conv54'])
    n.add('Load', 'load_link54', bus='sink_link', p_set=DEMAND)
    n.add('Load', 'load_process54', bus='sink_process', p_set=DEMAND)
    return n


def build():
    """The network over two futures, each with its own delays."""
    n = network(DELAYS['calm'])
    n.set_scenarios(SCENARIOS)
    for scenario, ports in DELAYS.items():
        for name, values in ports.items():
            component = n.c.links if name == 'pipe54' else n.c.processes
            for column, value in values.items():
                component.static.loc[(scenario, name), column] = value
    return n


def oracle():
    """Each future alone, with its own delays, weighted by its probability."""
    return [(weight, network(DELAYS[scenario])) for scenario, weight in SCENARIOS.items()]
