# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 27: modular ramps — a committable extendable modular unit ramps against one module through the ordinary ramp rows, not the big-M ones."""

from __future__ import annotations

import spine


def build():
    """The spine plus a peak bus served by a committable modular generator, link and process, each ramp-limited, with a dear backup."""
    n = spine.build()
    n.add('Bus', 'peak')
    common = {
        'committable': True,
        'p_nom_extendable': True,
        'p_nom_mod': 20,
        'p_nom_max': 60,
        'capital_cost': 2,
        'p_min_pu': 0.2,
        'up_time_before': 0,
        'ramp_limit_up': 0.5,
        'ramp_limit_down': 0.5,
        'ramp_limit_start_up': 0.6,
        'ramp_limit_shut_down': 0.6,
    }
    n.add('Generator', 'mod_gen', bus='peak', marginal_cost=3, **common)
    n.add('Link', 'mod_link', bus0='north', bus1='peak', marginal_cost=4, **common)
    n.add('Process', 'mod_proc', bus0='south', bus1='peak', rate0=-1.25, marginal_cost=5, **common)
    n.add('Generator', 'peak_backup', bus='peak', p_nom=200, marginal_cost=500)
    n.add('Load', 'peak_load', bus='peak', p_set=[10, 90, 150, 20])
    return n
