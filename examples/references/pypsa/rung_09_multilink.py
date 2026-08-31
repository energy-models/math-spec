"""Rung 9: a multi-link with four output ports — power and heat sold, waste heat vented, and a station service the link draws back."""

from __future__ import annotations

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', 'gasb')
    n.add('Bus', 'power')
    n.add('Bus', 'heat')
    n.add('Bus', 'flue')
    n.add('Bus', 'aux')
    n.add('Generator', 'well', bus='gasb', p_nom=100, marginal_cost=5)
    n.add('Generator', 'grid_import', bus='power', p_nom=50, marginal_cost=60)
    n.add('Generator', 'vent', bus='flue', p_nom=100, p_min_pu=-1, p_max_pu=0)
    n.add('Generator', 'aux_supply', bus='aux', p_nom=10, marginal_cost=2)
    n.add(
        'Link',
        'chp',
        bus0='gasb',
        bus1='power',
        bus2='heat',
        bus3='flue',
        bus4='aux',
        efficiency=0.4,
        efficiency2=0.45,
        efficiency3=0.1,
        efficiency4=-0.02,
        p_nom=60,
        marginal_cost=1,
    )
    n.add('Load', 'homes', bus='power', p_set=20)
    n.add('Load', 'district', bus='heat', p_set=18)
    return n
