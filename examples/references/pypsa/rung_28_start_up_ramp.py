# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 28: a start-up ramp alone — a committable unit with only a start-up and a shut-down ramp still gets ramp rows, at the full build between them."""

from __future__ import annotations

import spine


def build():
    """The spine plus a pulse bus served by committable generator, link and process that carry only start-up and shut-down ramps, with a dear backup."""
    n = spine.build()
    n.add('Bus', 'pulse')
    common = {
        'committable': True,
        'p_nom': 40,
        'p_min_pu': 0.1,
        'up_time_before': 0,
        'ramp_limit_start_up': 0.4,
        'ramp_limit_shut_down': 0.5,
    }
    n.add('Generator', 'pulse_gen', bus='pulse', marginal_cost=3, **common)
    n.add('Link', 'pulse_link', bus0='north', bus1='pulse', marginal_cost=4, **common)
    n.add('Process', 'pulse_proc', bus0='south', bus1='pulse', rate0=-1.25, marginal_cost=5, **common)
    n.add('Generator', 'pulse_backup', bus='pulse', p_nom=200, marginal_cost=500)
    n.add('Load', 'pulse_load', bus='pulse', p_set=[0, 60, 110, 0])
    return n
