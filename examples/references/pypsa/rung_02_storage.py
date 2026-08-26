"""Rung 2: storage — a cyclic battery, an inflow reservoir with a set state of charge, and a store."""

from __future__ import annotations

from math import nan

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.generators_t.marginal_cost['gas'] = [15, 15, 60, 60]
    n.add(
        'StorageUnit',
        'battery',
        bus='south',
        p_nom=20,
        max_hours=4,
        efficiency_store=0.95,
        efficiency_dispatch=0.9,
        standing_loss=0.01,
        cyclic_state_of_charge=True,
        marginal_cost=0.5,
        p_set=[0, nan, nan, nan],
    )
    n.add(
        'StorageUnit',
        'reservoir',
        bus='south',
        p_nom=10,
        max_hours=2,
        spill_cost=2,
        state_of_charge_initial=5,
        marginal_cost_storage=0.1,
        inflow=[12, 12, 12, 12],
        state_of_charge_set=[nan, nan, nan, 10],
    )
    n.add(
        'Store',
        'cavern',
        bus='south',
        e_nom=40,
        e_initial=25,
        standing_loss=0.005,
        marginal_cost=0.2,
        e_set=[nan, nan, nan, 20],
    )
    return n
