# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 45: ramp limits per snapshot — a generator, a link and a process whose ramp limits change over time, and lift at one snapshot."""

from __future__ import annotations

import math

import spine


def build():
    """The spine plus a steep bus served by a generator, a link and a process with ramp limits per snapshot, with a dear backup."""
    n = spine.build()
    n.add('Bus', 'steep')
    up = [0.1, 0.1, 0.5, 0.1]
    down = [0.1, 0.1, 0.1, math.nan]
    n.add('Generator', 'steep_gen', bus='steep', p_nom=60, marginal_cost=3, ramp_limit_up=up, ramp_limit_down=down)
    n.add(
        'Link',
        'steep_link',
        bus0='north',
        bus1='steep',
        p_nom=40,
        marginal_cost=4,
        ramp_limit_up=up,
        ramp_limit_down=down,
    )
    n.add(
        'Process',
        'steep_proc',
        bus0='south',
        bus1='steep',
        rate0=-1.25,
        p_nom=40,
        marginal_cost=5,
        ramp_limit_up=up,
        ramp_limit_down=down,
    )
    n.add('Generator', 'steep_backup', bus='steep', p_nom=200, marginal_cost=500)
    n.add('Load', 'steep_load', bus='steep', p_set=[10, 20, 90, 10])
    return n
