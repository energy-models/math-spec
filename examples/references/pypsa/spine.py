"""The spine every rung starts from: two buses, a coal and a gas unit, one link, two loads.

Four snapshots with three different weighting columns, none of them constant
and none 1.0, so a factor a formula drops or swaps cannot pass as identity.
"""

from __future__ import annotations

SNAPSHOTS = [0, 1, 2, 3]
WEIGHTINGS = {'objective': [2.0, 1.5, 2.5, 3.0], 'stores': [0.5, 2.0, 1.5, 2.5], 'generators': [1.5, 0.5, 3.0, 2.0]}


def build():
    """The spine as a fresh ``pypsa.Network``; each rung adds to what this returns."""
    import pypsa

    n = pypsa.Network()
    n.set_snapshots(SNAPSHOTS)
    for column, values in WEIGHTINGS.items():
        n.snapshot_weightings[column] = values
    n.add('Bus', 'north')
    n.add('Bus', 'south')
    n.add('Generator', 'coal', bus='north', p_nom=100, marginal_cost=10)
    n.add('Generator', 'gas', bus='south', p_nom=100, marginal_cost=30)
    n.add('Link', 'wire', bus0='north', bus1='south', p_nom=40, p_min_pu=-1, efficiency=0.9)
    n.add('Load', 'north_load', bus='north', p_set=30)
    n.add('Load', 'south_load', bus='south', p_set=40)
    return n
