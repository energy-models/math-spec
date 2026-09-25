# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 56: a security-constrained run over scenarios copies its rows into every scenario.

PyPSA 1.3.0 raises on a security-constrained run on a network with scenarios
(PyPSA/PyPSA#1942). The two futures are identical, so the oracle is the same
network without scenarios.
"""

from __future__ import annotations

import spine

ISSUE = 1942
BRANCH_OUTAGES = ['l56', 'l56_2']


def network():
    """The spine plus two parallel lines, so each must carry the whole import alone when the other is out."""
    n = spine.build()
    n.add('Bus', ['a', 'b'])
    n.add('Generator', 'hydro56', bus='a', p_nom=100, marginal_cost=10)
    n.add('Generator', 'diesel56', bus='b', p_nom=100, marginal_cost=50)
    n.add('Load', 'town56', bus='b', p_set=[50, 40, 55, 45])
    n.add('Line', 'l56', bus0='a', bus1='b', x=0.1, s_nom=30)
    n.add('Line', 'l56_2', bus0='a', bus1='b', x=0.1, s_nom=35)
    return n


def build():
    """The same network over two identical futures."""
    n = network()
    n.set_scenarios({'calm': 0.6, 'stormy': 0.4})
    return n


def oracle():
    """The network without scenarios: the futures are identical, so the expected cost is its cost."""
    return [(1.0, network())]
