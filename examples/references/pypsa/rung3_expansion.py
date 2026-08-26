#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["pypsa==1.3.0", "linopy==0.9.1", "pandas>=2.2", "xarray==2026.7.0", "highspy==1.15.1"]
# ///
"""Reference for rung 3 of `examples/pypsa.yaml` — capacity expansion.

    uv run --script examples/references/pypsa/rung3_expansion.py

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

RUNG = 'rung3_expansion'


def build() -> pypsa.Network:
    """Rung 3's expansion: a wind build decided by the solver against a fixed gas fleet.

    Wind is free to run but costs capacity, its availability varies, and its
    build is floored and capped; gas is fixed, dear, and budgeted in energy
    over the horizon, so the optimum has to buy some wind — at least the
    energy floor it also carries. The cable to the island is the extendable
    link, and the pump and tank are the extendable storage.
    """
    n = pypsa.Network()
    n.set_snapshots(range(4))
    n.add('Bus', 'grid')
    n.add(
        'Generator',
        'wind',
        bus='grid',
        p_nom_extendable=True,
        capital_cost=50.0,
        p_nom_min=5.0,
        p_nom_max=80.0,
        p_max_pu=[0.3, 0.8, 0.5, 0.9],
        marginal_cost=0.0,
        e_sum_min=40.0,
    )
    n.add('Generator', 'gas', bus='grid', p_nom=60.0, marginal_cost=40.0, e_sum_max=70.0)
    n.add(
        'StorageUnit',
        'pump',
        bus='grid',
        p_nom_extendable=True,
        capital_cost=15.0,
        p_nom_max=30.0,
        max_hours=4.0,
        efficiency_store=0.9,
        efficiency_dispatch=0.9,
        cyclic_state_of_charge=True,
        p_nom_set=20.0,
    )
    n.add(
        'Store',
        'tank',
        bus='grid',
        e_nom_extendable=True,
        capital_cost=2.0,
        e_nom_max=80.0,
        e_cyclic=True,
        e_nom_set=50.0,
    )
    n.add(
        'Generator',
        'solar',
        bus='grid',
        p_nom_extendable=True,
        capital_cost=60.0,
        p_max_pu=[0.5, 0.6, 0.4, 0.2],
        p_nom_max=40.0,
        p_nom_set=15.0,
        marginal_cost=0.0,
    )
    n.add('Load', 'town', bus='grid', p_set=40.0)
    n.add('Bus', 'island')
    n.add('Load', 'island_load', bus='island', p_set=10.0)
    n.add(
        'Link',
        'cable',
        bus0='grid',
        bus1='island',
        p_nom_extendable=True,
        capital_cost=20.0,
        p_nom_max=30.0,
        efficiency=0.95,
        p_nom_set=25.0,
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
