# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 57: `p_nom_set` pins an extendable build on a network with scenarios.

PyPSA 1.3.0 raises on any `*_nom_set` on a network with scenarios
(PyPSA/PyPSA#1942). The two futures are identical, so the oracle is the same
network without scenarios.
"""

from __future__ import annotations

import spine

ISSUE = 1942


def network():
    """The spine plus a cheap extendable wind unit whose build is pinned below what it would choose."""
    n = spine.build()
    n.add(
        'Generator',
        'wind57',
        bus='south',
        p_nom_extendable=True,
        p_nom_max=100,
        capital_cost=5,
        p_nom_set=20,
    )
    return n


def build():
    """The same network over two identical futures."""
    n = network()
    n.set_scenarios({'calm': 0.6, 'stormy': 0.4})
    return n


def oracle():
    """The network without scenarios: the futures are identical, so the expected cost is its cost."""
    return [(1.0, network())]
