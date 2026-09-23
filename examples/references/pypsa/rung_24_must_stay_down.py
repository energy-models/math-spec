# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 24: must stay down — a committable unit still serving the down time it brought in stays off."""

from __future__ import annotations

import spine


def build():
    """The spine plus a cheap committable unit that stopped one snapshot before the horizon and must stay off for three."""
    n = spine.build()
    n.add(
        'Generator',
        'warm',
        bus='north',
        committable=True,
        p_nom=50,
        marginal_cost=5,
        p_min_pu=0.2,
        min_down_time=3,
        up_time_before=0,
        down_time_before=1,
        start_up_cost=20,
    )
    n.add('Load', 'swing24', bus='north', p_set=[25, 45, 45, 10])
    return n
