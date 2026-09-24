# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 37: storage dispatch pinned — a store's power delivered, and a storage unit's dispatch and charging, each on its own schedule."""

from __future__ import annotations

from math import nan

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.generators_t.marginal_cost['gas'] = [15, 60, 15, 60]
    n.add('Store', 'tank37', bus='south', e_nom=40, e_initial=20, p_set=[10, nan, nan, -5])
    n.add(
        'StorageUnit',
        'battery37',
        bus='south',
        p_nom=20,
        max_hours=2,
        state_of_charge_initial=10,
        p_dispatch_set=[6, nan, nan, nan],
        p_store_set=[nan, 4, nan, nan],
    )
    return n
