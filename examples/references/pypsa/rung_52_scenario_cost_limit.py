# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 52: a `transmission_expansion_cost_limit` row holds in every scenario.

PyPSA 1.3.0 builds no such row on a network with scenarios (PyPSA/PyPSA#1939).
The two futures are identical, so the oracle is the same network without
scenarios, which PyPSA solves with the row.
"""

from __future__ import annotations

import spine

ISSUE = 1939


def network():
    """The spine plus an extendable DC link whose build a cost limit of 150 caps."""
    n = spine.build()
    n.add('Carrier', 'DC')
    n.add(
        'Link',
        'hvdc52',
        bus0='north',
        bus1='south',
        carrier='DC',
        p_nom_extendable=True,
        p_nom_max=100,
        capital_cost=10,
    )
    n.add('Load', 'port52', bus='south', p_set=40)
    n.add(
        'GlobalConstraint',
        'cost52',
        type='transmission_expansion_cost_limit',
        carrier_attribute='DC',
        sense='<=',
        constant=150,
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
