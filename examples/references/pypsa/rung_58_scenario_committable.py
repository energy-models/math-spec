# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 58: a committable unit takes its status rows in every scenario.

PyPSA 1.3.0 raises on a committable component on a network with scenarios
(PyPSA/PyPSA#1913). The two futures are identical, so the oracle is the same
network without scenarios.
"""

from __future__ import annotations

import spine

ISSUE = 1913


def network():
    """The spine plus a cheap committable unit that cannot run below 40 % of its build."""
    n = spine.build()
    n.add(
        'Generator',
        'uc58',
        bus='north',
        committable=True,
        p_nom=50,
        marginal_cost=5,
        p_min_pu=0.4,
        min_up_time=2,
        up_time_before=0,
        start_up_cost=100,
    )
    n.add('Load', 'swing58', bus='north', p_set=[5, 45, 45, 10])
    return n


def build():
    """The same network over two identical futures."""
    n = network()
    n.set_scenarios({'calm': 0.6, 'stormy': 0.4})
    return n


def oracle():
    """The network without scenarios: the futures are identical, so the expected cost is its cost."""
    return [(1.0, network())]
