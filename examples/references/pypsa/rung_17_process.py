# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 17: process — generalized converters, one fixed and ramping, one extendable, one on a set schedule, all feeding a hub."""

from __future__ import annotations

from math import nan

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', 'hub')
    n.add(
        'Process',
        'conv_fix',
        bus0='north',
        bus1='hub',
        p_nom=50,
        marginal_cost=2,
        ramp_limit_up=0.3,
        ramp_limit_down=0.3,
    )
    n.add(
        'Process',
        'conv_ext',
        bus0='south',
        bus1='hub',
        p_nom_extendable=True,
        capital_cost=20,
        p_nom_min=5,
        p_nom_max=40,
        marginal_cost=1,
        p_nom_set=25,
    )
    n.add('Process', 'conv_set', bus0='north', bus1='hub', p_nom=20, marginal_cost=3, p_set=[10, nan, nan, nan])
    n.add('Load', 'hub_load', bus='hub', p_set=[15, 20, 25, 10])
    return n
