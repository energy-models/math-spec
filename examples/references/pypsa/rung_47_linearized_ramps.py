# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 47: the relaxed file's ramps and signs — tightening at the full build, a ramp limit per snapshot, a `p_init`, a unit that is not committable, and a sign."""

from __future__ import annotations

import math

import spine

MODEL = 'pypsa_linearized_uc.yaml'
OPTIMIZE = {'linearized_unit_commitment': True}


def build():
    """The spine plus a relax bus: five units that each carry one of the rows under review, a feeding load and a dear backup."""
    n = spine.build()
    n.add('Bus', 'relax')
    n.add(
        'Generator',
        'tight47',
        bus='relax',
        committable=True,
        p_nom=50,
        p_min_pu=0.2,
        marginal_cost=2,
        up_time_before=0,
        ramp_limit_start_up=0.5,
        ramp_limit_shut_down=0.5,
        start_up_cost=10,
        shut_down_cost=10,
    )
    n.add(
        'Generator',
        'steep47',
        bus='relax',
        committable=True,
        p_nom=40,
        marginal_cost=3,
        start_up_cost=1,
        ramp_limit_up=[0.25, 0.25, math.nan, 0.25],
        ramp_limit_down=[0.25, 0.25, 0.25, math.nan],
        ramp_limit_start_up=0.25,
    )
    n.add(
        'Generator',
        'warm47',
        bus='relax',
        committable=True,
        p_nom=40,
        marginal_cost=50,
        start_up_cost=1,
        p_init=40,
        ramp_limit_down=0.25,
        ramp_limit_shut_down=0.5,
    )
    n.add('Generator', 'fixed47', bus='relax', p_nom=60, marginal_cost=1, ramp_limit_up=0.25, ramp_limit_down=0.25)
    n.add('Generator', 'sink47', bus='relax', p_nom=20, p_min_pu=0.5, sign=-1)
    n.add('Generator', 'backup47', bus='relax', p_nom=300, marginal_cost=500)
    n.add('Load', 'feed47', bus='relax', p_set=10, sign=1)
    n.add('Load', 'swing47', bus='relax', p_set=[60, 60, 140, 40])
    return n
