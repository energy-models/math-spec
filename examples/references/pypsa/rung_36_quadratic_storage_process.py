# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 36: quadratic costs on a process, a storage unit and a store — the storage unit pays on dispatch only, the store on its net power both ways."""

from __future__ import annotations

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', 'hub')
    n.add('Process', 'conv36', bus0='north', bus1='hub', p_nom=60, marginal_cost=1, marginal_cost_quadratic=0.05)
    n.add(
        'StorageUnit',
        'battery36',
        bus='south',
        p_nom=20,
        max_hours=4,
        state_of_charge_initial=40,
        marginal_cost=0.5,
        marginal_cost_quadratic=[0.2, 0.1, 0.3, 0.1],
    )
    n.add('Store', 'tank36', bus='hub', e_nom=60, e_initial=20, marginal_cost_quadratic=0.4)
    n.add('Load', 'hub_load', bus='hub', p_set=[20, 45, 30, 50])
    n.add('Load', 'peak36', bus='south', p_set=[10, 40, 20, 60])
    return n
