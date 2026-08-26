# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 12: linearized unit commitment — the status a share in [0, 1], stated by `pypsa_linearized_uc.yaml`."""

from __future__ import annotations

import spine

MODEL = 'pypsa_linearized_uc.yaml'
OPTIMIZE = {'linearized_unit_commitment': True}


def build():
    """The spine plus two committable units, one whose start and stop cost the same, so PyPSA tightens its relaxation."""
    n = spine.build()
    n.add(
        'Generator',
        'uc12',
        bus='north',
        committable=True,
        p_nom=50,
        marginal_cost=5,
        p_min_pu=0.4,
        min_up_time=3,
        min_down_time=2,
        up_time_before=1,
        ramp_limit_up=0.5,
        ramp_limit_down=0.5,
        ramp_limit_start_up=0.6,
        ramp_limit_shut_down=0.6,
        start_up_cost=100,
        shut_down_cost=100,
        stand_by_cost=5,
    )
    n.add(
        'Generator',
        'cold12',
        bus='south',
        committable=True,
        p_nom=30,
        marginal_cost=60,
        p_min_pu=0.3,
        min_up_time=2,
        min_down_time=1,
        ramp_limit_up=0.5,
        ramp_limit_down=0.5,
        ramp_limit_start_up=0.7,
        ramp_limit_shut_down=0.7,
        start_up_cost=80,
        shut_down_cost=40,
    )
    n.add('Load', 'swing12', bus='north', p_set=[25, 45, 45, 10])
    return n
