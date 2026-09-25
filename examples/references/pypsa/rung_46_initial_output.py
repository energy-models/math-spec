# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 46: the output brought in — units that came in running with a given `p_init` ramp from it into the first snapshot."""

from __future__ import annotations

import spine


def build():
    """The spine plus a warm bus served by fixed, extendable and committable units that each carry a `p_init`, with a dear backup."""
    n = spine.build()
    n.add('Bus', 'warm')
    ramps = {'ramp_limit_up': 0.25, 'ramp_limit_down': 0.25}
    n.add('Generator', 'warm_gen', bus='warm', p_nom=60, marginal_cost=3, p_init=10, **ramps)
    n.add('Link', 'warm_link', bus0='north', bus1='warm', p_nom=40, marginal_cost=4, p_init=0, **ramps)
    n.add(
        'Process', 'warm_proc', bus0='south', bus1='warm', rate0=-1.25, p_nom=40, marginal_cost=600, p_init=40, **ramps
    )
    n.add(
        'Generator',
        'warm_ext',
        bus='warm',
        p_nom_extendable=True,
        p_nom_max=40,
        capital_cost=5,
        marginal_cost=2,
        p_init=5,
        **ramps,
    )
    n.add(
        'Generator',
        'warm_com',
        bus='warm',
        committable=True,
        p_nom=50,
        p_min_pu=0.2,
        marginal_cost=2.5,
        p_init=30,
        ramp_limit_start_up=0.4,
        ramp_limit_shut_down=0.4,
        **ramps,
    )
    n.add(
        'Generator',
        'warm_com_ext',
        bus='warm',
        committable=True,
        p_nom_extendable=True,
        p_nom_max=40,
        capital_cost=5,
        marginal_cost=2.2,
        p_init=5,
        **ramps,
    )
    n.add('Generator', 'warm_backup', bus='warm', p_nom=300, marginal_cost=500)
    n.add('Load', 'warm_load', bus='warm', p_set=[150, 150, 60, 60])
    return n
