#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["pypsa==1.3.0", "linopy==0.9.1", "pandas>=2.2", "xarray==2026.7.0", "highspy==1.15.1"]
# ///
"""Reference for rung 6 of `examples/pypsa.yaml` — passive lines and the voltage law.

    uv run --script examples/references/pypsa/rung6_kvl.py

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

RUNG = 'rung6_kvl'


def build() -> pypsa.Network:
    """Rung 6's voltage law: three buses in a triangle of lines.

    Two generators and one load; with a cycle in the graph the flows split by
    impedance rather than by cost, which is what the KVL row enforces; one
    line is extendable, so its rating is a decision.
    """
    n = pypsa.Network()
    n.set_snapshots(range(4))
    n.add('Bus', ['a', 'b', 'c'])
    n.add('Line', 'ab', bus0='a', bus1='b', x=0.1, r=0.01, s_nom=60.0)
    n.add(
        'Line',
        'bc',
        bus0='b',
        bus1='c',
        x=0.2,
        r=0.01,
        s_nom=60.0,
        s_set=[10.0, float('nan'), float('nan'), float('nan')],
    )
    n.add('Line', 'ca', bus0='c', bus1='a', x=0.1, r=0.01, s_nom=60.0)
    n.add(
        'Line',
        'ca2',
        bus0='c',
        bus1='a',
        x=0.15,
        r=0.01,
        s_nom_extendable=True,
        capital_cost=10.0,
        s_nom_max=40.0,
        s_nom_set=30.0,
    )
    n.add('Generator', 'hydro', bus='a', p_nom=80.0, marginal_cost=10.0)
    n.add('Generator', 'diesel', bus='b', p_nom=80.0, marginal_cost=50.0)
    n.add('Load', 'town', bus='c', p_set=45.0)
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
