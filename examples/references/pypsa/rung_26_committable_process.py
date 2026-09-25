# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 26: committable processes — rung 25's committable links restated as processes that draw a quarter more than they deliver."""

from __future__ import annotations

import spine


def build():
    """The spine plus an east bus that only committable processes serve."""
    n = spine.build()
    n.add('Bus', 'east')
    n.add(
        'Process',
        'warm_conv',
        bus0='north',
        bus1='east',
        rate0=-1.25,
        committable=True,
        p_nom=60,
        p_min_pu=0.3,
        marginal_cost=8,
        min_up_time=3,
        min_down_time=2,
        up_time_before=1,
        ramp_limit_up=0.5,
        ramp_limit_down=0.5,
        ramp_limit_start_up=0.6,
        ramp_limit_shut_down=0.6,
        start_up_cost=100,
        shut_down_cost=50,
        stand_by_cost=5,
    )
    n.add(
        'Process',
        'cold_conv',
        bus0='north',
        bus1='east',
        rate0=-1.25,
        committable=True,
        p_nom=40,
        p_min_pu=0.2,
        min_up_time=2,
        min_down_time=3,
        up_time_before=0,
        down_time_before=1,
        start_up_cost=20,
    )
    n.add(
        'Process',
        'ext_conv',
        bus0='north',
        bus1='east',
        rate0=-1.25,
        committable=True,
        p_nom_extendable=True,
        p_nom_max=30,
        capital_cost=5,
        p_min_pu=0.2,
        marginal_cost=2,
        up_time_before=0,
        ramp_limit_up=0.5,
        ramp_limit_down=0.5,
    )
    n.add(
        'Process',
        'mod_conv',
        bus0='south',
        bus1='east',
        rate0=-1.25,
        committable=True,
        p_nom_extendable=True,
        p_nom_mod=10,
        p_nom_max=40,
        capital_cost=3,
        p_min_pu=0.5,
    )
    n.add(
        'Process',
        'mod_fix',
        bus0='north',
        bus1='east',
        rate0=-1.25,
        committable=True,
        p_nom=20,
        p_nom_mod=10,
        p_min_pu=0.5,
        marginal_cost=1,
    )
    n.add('Load', 'east_load', bus='east', p_set=[20, 70, 60, 5])
    return n
