"""Rung 4: ramps — ramp limits on fixed and extendable generators and links."""

from __future__ import annotations

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', 'east')
    n.add('Generator', 'coal_slow', bus='north', p_nom=80, marginal_cost=8, ramp_limit_up=0.2, ramp_limit_down=0.2)
    n.add('Link', 'tie', bus0='north', bus1='east', p_nom=50, efficiency=1, ramp_limit_up=0.4, ramp_limit_down=0.4)
    n.add('Load', 'east_load', bus='east', p_set=[5, 20, 25, 10])
    n.add('Load', 'swing', bus='north', p_set=[0, 25, 45, 0])
    return n
