"""Rung 10: quadratic costs — a marginal cost quadratic in output, stated by `pypsa_quadratic.yaml`."""

from __future__ import annotations

import spine

#: This rung binds a file of its own.
MODEL = 'pypsa_quadratic.yaml'


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', 'village')
    n.add('Generator', 'steam', bus='north', p_nom=80, marginal_cost=5, marginal_cost_quadratic=0.08)
    n.add('Generator', 'engine', bus='north', p_nom=80, marginal_cost=20, marginal_cost_quadratic=0.01)
    n.add(
        'Link',
        'wire2',
        bus0='north',
        bus1='village',
        p_nom=40,
        p_min_pu=-1,
        efficiency=0.9,
        marginal_cost=1,
        marginal_cost_quadratic=0.02,
    )
    n.add('Load', 'village_load', bus='village', p_set=15)
    n.add('Load', 'extra10', bus='north', p_set=[30, 50, 40, 60])
    return n
