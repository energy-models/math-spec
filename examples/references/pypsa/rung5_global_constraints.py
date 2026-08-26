#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["pypsa==1.2.4", "linopy==0.9.0", "pandas>=2.2", "xarray==2026.7.0", "highspy==1.15.1"]
# ///
"""Reference for rung 5 of `examples/pypsa.yaml` — a CO2 cap priced through the carrier map.

    uv run --script examples/references/pypsa/rung5_global_constraints.py

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

RUNG = 'rung5_global_constraints'


def build() -> pypsa.Network:
    """Rung 5's global constraint: a primary-energy CO2 cap over three carriers.

    Coal is cheap and dirty, gas dearer and cleaner, wind clean and dearest to
    run here; the cap decides the mix, and its shadow price is the carbon
    price.
    """
    n = pypsa.Network()
    n.set_snapshots(range(4))
    n.add('Carrier', 'coal', co2_emissions=0.9)
    n.add('Carrier', 'gas', co2_emissions=0.4)
    n.add('Carrier', 'wind', co2_emissions=0.0)
    n.add('Bus', 'grid')
    n.add('Generator', 'coal', bus='grid', carrier='coal', p_nom=60.0, marginal_cost=10.0, efficiency=0.35)
    n.add('Generator', 'gas', bus='grid', carrier='gas', p_nom=60.0, marginal_cost=25.0, efficiency=0.5)
    n.add('Generator', 'wind', bus='grid', carrier='wind', p_nom=60.0, marginal_cost=40.0)
    n.add('Load', 'town', bus='grid', p_set=50.0)
    n.add(
        'GlobalConstraint',
        'co2_cap',
        type='primary_energy',
        carrier_attribute='co2_emissions',
        sense='<=',
        constant=150.0,
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
