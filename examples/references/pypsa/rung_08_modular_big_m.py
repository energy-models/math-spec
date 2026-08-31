"""Rung 8: modular and big-M — capacity in whole modules, built or already standing, and a committable unit whose capacity is also built."""

from __future__ import annotations

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', 'mill')
    n.add(
        'Generator',
        'block',
        bus='mill',
        p_nom_extendable=True,
        committable=True,
        p_nom_mod=25,
        p_nom_max=100,
        capital_cost=30,
        marginal_cost=20,
        p_min_pu=0.2,
        up_time_before=0,
    )
    n.add(
        'Generator',
        'flex',
        bus='mill',
        p_nom_extendable=True,
        committable=True,
        p_nom_max=80,
        capital_cost=50,
        marginal_cost=10,
        p_min_pu=0.3,
        up_time_before=0,
        ramp_limit_up=0.25,
        ramp_limit_down=0.25,
    )
    n.add(
        'Generator',
        'sink',
        bus='mill',
        p_nom_extendable=True,
        committable=True,
        p_nom_max=30,
        capital_cost=40,
        marginal_cost=15,
        p_min_pu=-0.2,
        up_time_before=0,
    )
    n.add(
        'Generator',
        'array',
        bus='mill',
        committable=True,
        p_nom=90,
        p_nom_mod=30,
        marginal_cost=12,
        p_min_pu=0.2,
        up_time_before=0,
    )
    n.add('Load', 'mill_load', bus='mill', p_set=[40, 80, 120, 60])
    return n
