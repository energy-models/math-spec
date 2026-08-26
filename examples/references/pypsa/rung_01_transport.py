#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["pypsa==1.3.0", "linopy==0.9.1", "pandas>=2.2", "xarray==2026.7.0", "highspy==1.15.1"]
# ///
"""Reference for rung 1 of `examples/pypsa.yaml` — transport.

    uv run --script examples/references/pypsa/rung_01_transport.py

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

RUNG = 'rung_01_transport'


def build() -> pypsa.Network:
    """Rung 1's transport: the spine as it stands, plus a must-run its schedule pins.

    Coal in the north is cheap and the wire loses a tenth on the way south, so
    the south's load splits between imports, a small must-run pinned by its
    given schedule, and its own gas at the link's rating.
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
