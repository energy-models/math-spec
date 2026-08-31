# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 16: link delay — a source feeding two sinks over links whose energy arrives late, one wrapping cyclically and one losing what is still in transit at the horizon's edge."""

from __future__ import annotations

from datetime import datetime

#: Four hourly stamps. The `generators` weighting is uniform here, and only here
#: on the ladder, because PyPSA measures `delay` in those units: a uniform column
#: makes a delay of `n` a shift of exactly `n` snapshot positions, which is what a
#: positional `shift(offset=n)` reproduces. The `objective` and `stores` columns
#: stay non-uniform, so no cost or storage factor passes as identity.
SNAPSHOTS = [datetime(2015, 1, 1, hour) for hour in range(4)]
WEIGHTINGS = {'objective': [2.0, 1.5, 2.5, 3.0], 'stores': [0.5, 2.0, 1.5, 2.5], 'generators': [1.0, 1.0, 1.0, 1.0]}

#: Each sink carries the same demand, so the only thing that separates their cost
#: is how each link treats the horizon's edge.
DEMAND = [20.0, 15.0, 25.0, 10.0]


def build():
    """A source, two delayed links, and two sinks, stated as the calls that build it.

    ``pipe_wrap`` delays by two snapshots and wraps cyclically, so every unit the
    cheap source sends reaches its sink and the expensive backup stays dark.
    ``pipe_lose`` delays by one and does not wrap, so the flow that would arrive
    in the first snapshot is lost and that snapshot's demand falls to the backup.
    The two links differ in both a per-link number (`delay`) and a per-link kind
    (`cyclic_delay`), which is what the model's ``cases:`` block turns on.
    """
    import pypsa

    n = pypsa.Network()
    n.set_snapshots(SNAPSHOTS)
    for column, values in WEIGHTINGS.items():
        n.snapshot_weightings[column] = values
    n.add('Bus', 'source')
    n.add('Bus', 'sink_wrap')
    n.add('Bus', 'sink_lose')
    n.add('Generator', 'spring', bus='source', p_nom=200, marginal_cost=5)
    n.add('Generator', 'backup_wrap', bus='sink_wrap', p_nom=200, marginal_cost=100)
    n.add('Generator', 'backup_lose', bus='sink_lose', p_nom=200, marginal_cost=100)
    n.add('Link', 'pipe_wrap', bus0='source', bus1='sink_wrap', p_nom=100, delay=2, cyclic_delay=True)
    n.add('Link', 'pipe_lose', bus0='source', bus1='sink_lose', p_nom=100, delay=1, cyclic_delay=False)
    n.add('Load', 'load_wrap', bus='sink_wrap', p_set=DEMAND)
    n.add('Load', 'load_lose', bus='sink_lose', p_set=DEMAND)
    return n
