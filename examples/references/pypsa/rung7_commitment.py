#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["pypsa==1.2.4", "linopy==0.9.0", "pandas>=2.2", "xarray==2026.7.0", "highspy==1.15.1"]
# ///
"""Reference for rung 7 of `examples/pypsa.yaml` — unit commitment.

    uv run --script examples/references/pypsa/rung7_commitment.py

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

RUNG = 'rung7_commitment'


def build() -> pypsa.Network:
    """Rung 7's commitment: a unit that pays to start, to stop, and to idle.

    The base unit may not run below forty percent, must stay up and down two
    snapshots at a time, pays for each start, and ramps against its previous
    status — so the swing between it and the peaker is a schedule, not a
    dispatch.
    """
    n = pypsa.Network()
    n.set_snapshots(range(4))
    n.add('Bus', 'grid')
    n.add(
        'Generator',
        'base',
        bus='grid',
        committable=True,
        p_nom=50.0,
        marginal_cost=10.0,
        p_min_pu=0.4,
        min_up_time=2,
        min_down_time=2,
        up_time_before=0,
        ramp_limit_up=0.3,
        ramp_limit_down=0.3,
        ramp_limit_start_up=0.5,
        ramp_limit_shut_down=0.5,
        start_up_cost=100.0,
        shut_down_cost=50.0,
        stand_by_cost=5.0,
    )
    n.add('Generator', 'peaker', bus='grid', p_nom=100.0, marginal_cost=80.0)
    n.add('Load', 'town', bus='grid', p_set=[10.0, 45.0, 45.0, 10.0])
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
