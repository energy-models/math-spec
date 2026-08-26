"""Rung 9: multi-link and delay — one link with two output buses."""

from __future__ import annotations

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', 'gasb')
    n.add('Bus', 'power')
    n.add('Bus', 'heat')
    n.add('Generator', 'well', bus='gasb', p_nom=100, marginal_cost=5)
    n.add('Generator', 'grid_import', bus='power', p_nom=50, marginal_cost=60)
    n.add(
        'Link',
        'chp',
        bus0='gasb',
        bus1='power',
        bus2='heat',
        efficiency=0.4,
        efficiency2=0.45,
        p_nom=60,
        marginal_cost=1,
    )
    n.add('Load', 'homes', bus='power', p_set=20)
    n.add('Load', 'district', bus='heat', p_set=18)
    return n
