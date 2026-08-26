#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["pypsa==1.3.0", "linopy==0.9.1", "pandas>=2.2", "xarray==2026.7.0", "highspy==1.15.1"]
# ///
"""Reference for rung 9 of `examples/pypsa.yaml` — a multi-link delivering at two ports.

    uv run --script examples/references/pypsa/rung9_multilink.py

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

RUNG = 'rung9_multilink'


def build() -> pypsa.Network:
    """Rung 9's multi-link: one gas flow delivering power and heat at two ports.

    The CHP link withdraws gas at its first bus and injects at the other two
    by its two efficiencies; the heat bus has no other supply, so the link
    runs and the power bus tops up from imports.
    """
    n = pypsa.Network()
    n.set_snapshots(range(4))
    n.add('Bus', ['gas', 'power', 'heat'])
    n.add('Generator', 'well', bus='gas', p_nom=100.0, marginal_cost=5.0)
    n.add(
        'Link',
        'chp',
        bus0='gas',
        bus1='power',
        bus2='heat',
        efficiency=0.4,
        efficiency2=0.45,
        p_nom=60.0,
        marginal_cost=1.0,
    )
    n.add('Generator', 'grid_import', bus='power', p_nom=50.0, marginal_cost=60.0)
    n.add('Load', 'homes', bus='power', p_set=20.0)
    n.add('Load', 'district', bus='heat', p_set=18.0)
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
