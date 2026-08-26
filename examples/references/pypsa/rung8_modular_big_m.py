#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["pypsa==1.3.0", "linopy==0.9.1", "pandas>=2.2", "xarray==2026.7.0", "highspy==1.15.1"]
# ///
"""Reference for rung 8 of `examples/pypsa.yaml` — modular builds and big M.

    uv run --script examples/references/pypsa/rung8_modular_big_m.py

Builds the smallest network that puts this rung's rows in front of a solver,
solves it through PyPSA's own linopy model with HiGHS, and stamps what it saw
into `references.json` beside this file. Run out of band: PyPSA is not a
dependency of this project, and the pins above are the versions the recorded
numbers are from. Nothing here imports math_spec.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pypsa

sys.path.insert(0, str(Path(__file__).resolve().parent))

import instances

RUNG = 'rung8_modular_big_m'


def build() -> pypsa.Network:
    """Rung 8's modular and big-M builds: whole modules, and a build gated by a status.

    The block plant is bought twenty-five megawatts at a time and gated by a
    status, so its bounds are one module's share; the flexible plant is
    extendable and committable with ramps, which is the pairing PyPSA's big-M
    rows linearize.
    """
    return instances.build(RUNG)


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
