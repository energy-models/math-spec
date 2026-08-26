"""Rung 1: transport — two buses, two generators, one controllable link."""

from __future__ import annotations

from math import nan

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.links_t.p_set['wire'] = [10, nan, nan, nan]
    n.add('Generator', 'must_run', bus='south', p_nom=10, marginal_cost=0, p_set=[5, 5, 5, 5])
    return n
