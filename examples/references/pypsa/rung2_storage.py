#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["pypsa==1.3.0", "linopy==0.9.1", "pandas>=2.2", "xarray==2026.7.0", "highspy==1.15.1"]
# ///
"""Reference for rung 2 of `examples/pypsa.yaml` — storage units and stores.

    uv run --script examples/references/pypsa/rung2_storage.py

Builds the smallest network that puts this rung's rows in front of a solver,
solves it through PyPSA's own linopy model with HiGHS, and stamps what it saw
into `references.json` beside this file. Run out of band: PyPSA is not a
dependency of this project, and the pins above are the versions the recorded
numbers are from. Nothing here imports math_spec.
"""

from __future__ import annotations

import json
from pathlib import Path

import pypsa

RUNG = 'rung2_storage'


def build() -> pypsa.Network:
    """Rung 2's storage: a cyclic battery, a reservoir that can spill, a cavern store.

    The generator is cheap for two snapshots and dear for two, so the battery
    buys low and sells high and its horizon closes on itself; the reservoir
    opens on a given charge and spills the inflow it cannot hold; the cavern
    drains from its initial fill.
    """
    n = pypsa.Network()
    n.set_snapshots(range(4))
    n.add('Bus', 'grid')
    n.add('Generator', 'gas', bus='grid', p_nom=80.0, marginal_cost=[10.0, 10.0, 60.0, 60.0])
    n.add('Load', 'town', bus='grid', p_set=30.0)
    n.add(
        'StorageUnit',
        'battery',
        bus='grid',
        p_nom=20.0,
        max_hours=4.0,
        efficiency_store=0.95,
        efficiency_dispatch=0.9,
        standing_loss=0.01,
        cyclic_state_of_charge=True,
        marginal_cost=0.5,
        p_set=[0.0, float('nan'), float('nan'), float('nan')],
    )
    n.add(
        'StorageUnit',
        'reservoir',
        bus='grid',
        p_nom=10.0,
        max_hours=2.0,
        inflow=[12.0, 12.0, 12.0, 12.0],
        spill_cost=2.0,
        state_of_charge_initial=5.0,
        marginal_cost_storage=0.1,
        state_of_charge_set=[float('nan'), float('nan'), float('nan'), 10.0],
    )
    n.add(
        'Store',
        'cavern',
        bus='grid',
        e_nom=40.0,
        e_initial=25.0,
        standing_loss=0.005,
        marginal_cost=0.2,
        e_set=[float('nan'), float('nan'), float('nan'), 20.0],
    )
    return n


def record(n: pypsa.Network) -> dict[str, object]:
    """What the solve saw, in the shape `references.json` holds.

    Row and column counts skip masked labels, so they count what a solver was
    handed rather than the coordinate product.
    """
    m = n.model
    return {
        'pypsa': pypsa.__version__,
        'objective': float(n.objective),
        'objective_constant': float(n.objective_constant),
        'columns': {name: int((m.variables[name].labels != -1).sum()) for name in m.variables},
        'rows': {name: int((m.constraints[name].labels != -1).sum()) for name in m.constraints},
        'global_constraints': {
            str(label): {'type': row['type'], 'sense': row['sense']} for label, row in n.global_constraints.iterrows()
        },
        'marginal_price': {
            str(bus): [float(x) for x in n.buses_t.marginal_price[bus]] for bus in n.buses_t.marginal_price.columns
        }
        if not n.buses_t.marginal_price.empty and bool(n.buses_t.marginal_price.notna().all().all())
        else {},
    }


def main() -> None:
    n = build()
    status, condition = n.optimize(solver_name='highs')
    assert status == 'ok', f'HiGHS did not solve: {status} / {condition}'
    path = Path(__file__).with_name('references.json')
    stamped = json.loads(path.read_text()) if path.exists() else {}
    stamped[RUNG] = record(n)
    path.write_text(json.dumps(stamped, indent=2, sort_keys=True) + '\n')
    print(f'{RUNG}: objective {n.objective}')


if __name__ == '__main__':
    main()
