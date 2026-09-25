# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 44: linearized commitment with the rows the integer file has — a unit that must stay down, ramps read at the full build where a limit is missing, and maintenance."""

from __future__ import annotations

import spine

MODEL = 'pypsa_linearized_uc.yaml'
OPTIMIZE = {'linearized_unit_commitment': True}

#: a start costs more than a stop, so PyPSA does not tighten these units and the rung isolates the rows it adds
UNTIGHTENED = {'committable': True, 'up_time_before': 0, 'start_up_cost': 1}


def build():
    """The spine plus five cheap units on a north bus with a swinging load: each carries one of the rows under review."""
    n = spine.build()
    n.add(
        'Generator',
        'down44',
        bus='north',
        p_nom=40,
        marginal_cost=2,
        min_down_time=3,
        down_time_before=1,
        **UNTIGHTENED,
    )
    n.add('Generator', 'pulse44', bus='north', p_nom=40, marginal_cost=3, ramp_limit_start_up=0.4, **UNTIGHTENED)
    n.add(
        'Generator',
        'ramp44',
        bus='north',
        p_nom=40,
        marginal_cost=4,
        ramp_limit_up=0.5,
        ramp_limit_down=0.5,
        **UNTIGHTENED,
    )
    n.add(
        'Generator',
        'maint44',
        bus='north',
        p_nom=40,
        p_min_pu=0.3,
        marginal_cost=5,
        maintainable=True,
        maintenance_duration=2,
        **UNTIGHTENED,
    )
    n.add('Generator', 'fixed44', bus='north', p_nom=20, marginal_cost=1, maintainable=True, maintenance_duration=1)
    n.add('Load', 'swing44', bus='north', p_set=[40, 120, 160, 60])
    return n
