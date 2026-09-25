# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 55: a cycle of two transformers takes its Kirchhoff voltage row in every scenario.

PyPSA 1.3.0 raises on a transformer in a cycle on a network with scenarios
(PyPSA/PyPSA#1942). The two futures are identical, so the oracle is the same
network without scenarios.
"""

from __future__ import annotations

import spine

ISSUE = 1942


def network():
    """The spine plus two parallel transformers of unequal reactance, so the one that takes more flow caps the pair."""
    n = spine.build()
    n.add('Bus', ['a', 'b'])
    n.add('Generator', 'hydro55', bus='a', p_nom=100, marginal_cost=10)
    n.add('Generator', 'diesel55', bus='b', p_nom=100, marginal_cost=50)
    n.add('Load', 'town55', bus='b', p_set=[50, 40, 55, 45])
    n.add('Transformer', 't55', bus0='a', bus1='b', x=0.1, s_nom=30)
    n.add('Transformer', 't55_2', bus0='a', bus1='b', x=0.2, s_nom=30)
    return n


def build():
    """The same network over two identical futures."""
    n = network()
    n.set_scenarios({'calm': 0.6, 'stormy': 0.4})
    return n


def oracle():
    """The network without scenarios: the futures are identical, so the expected cost is its cost."""
    return [(1.0, network())]
