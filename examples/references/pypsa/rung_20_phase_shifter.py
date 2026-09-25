# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 20: phase shifter — a transformer whose per-snapshot phase shift is optimised, holding it at its rating and rerouting the surplus around the cycle.

The parallel lines carry low reactance, so a few degrees of shift move tens of
megawatts: the phase-shifting transformer keeps its flow at its ``s_nom`` while
the upstream hydro serves the whole varying load, and the costly local unit
stays off. A fixed shift could not follow the load, so the shift is a decision.
"""

from __future__ import annotations

import spine


def build():
    """The spine plus a triangle where a phase-shifting transformer reroutes cheap power around a binding leg, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', ['a', 'b', 'c'])
    n.add('Generator', 'hydro20', bus='a', p_nom=300, marginal_cost=10)
    n.add('Generator', 'diesel20', bus='c', p_nom=300, marginal_cost=200)
    n.add('Load', 'town20', bus='c', p_set=[90, 75, 120, 105])
    n.add('Line', 'ab20', bus0='a', bus1='b', carrier='AC', x=0.002, r=0.0002, s_nom=120)
    n.add('Line', 'bc20', bus0='b', bus1='c', carrier='AC', x=0.002, r=0.0002, s_nom=120)
    n.add(
        'Transformer',
        'ca20',
        bus0='c',
        bus1='a',
        x=0.002,
        r=0.0002,
        s_nom=40,
        phase_shift_min=-30,
        phase_shift_max=30,
    )
    return n
