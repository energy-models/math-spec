#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["pypsa==1.3.0", "pandas>=2.2"]
# ///
"""Write one of PyPSA's example networks as a whole-network rung folder.

    uv run --script examples/references/pypsa/from_example.py ac_dc_meshed data/rung_11_ac_dc_meshed

Static attributes at their default are left out, so the folder holds what
the example sets; what varies goes to `timeseries.csv`.
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import pypsa

SKIP = {
    'color',
    'nice_name',
    'type',
    'control',
    'v_mag_pu_set',
    'v_mag_pu_min',
    'v_mag_pu_max',
    'sub_network',
    'unit',
    'generator',
    'v_nom',
    'num_parallel',
    'terrain_factor',
    'model',
    'g',
    'b',
    'v_ang_min',
    'v_ang_max',
    'active',
    'build_year',
    'lifetime',
    'sign',
    'mu',
    'investment_period',
}
TABLES = {
    'Bus': 'buses.csv',
    'Carrier': 'carriers.csv',
    'Generator': 'generators.csv',
    'Line': 'lines.csv',
    'Link': 'links.csv',
    'Load': 'loads.csv',
    'StorageUnit': 'storage_units.csv',
    'Store': 'stores.csv',
    'GlobalConstraint': 'global_constraints.csv',
}


def _default(value, default) -> bool:
    try:
        return (math.isnan(float(value)) and (default != default or default == '')) or float(value) == float(default)
    except (TypeError, ValueError):
        return str(value) == str(default)


def _cell(value):
    if isinstance(value, float):
        return '' if math.isnan(value) else float(value)
    return value


def write(n: pypsa.Network, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    snaps = list(n.snapshots)
    with (out / 'snapshots.csv').open('w', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['snapshot', 'objective', 'stores', 'generators'])
        for i, t in enumerate(snaps):
            w.writerow([i, *(float(n.snapshot_weightings.at[t, c]) for c in ('objective', 'stores', 'generators'))])
    series = []
    for comp, table in TABLES.items():
        static, attrs = n.static(comp), n.components[comp]['attrs']
        if static.empty:
            continue
        cols = [
            col
            for col in static.columns
            if col in attrs.index
            and col not in SKIP
            and not (comp == 'Bus' and col in ('x', 'y'))
            and not all(_default(v, attrs.at[col, 'default']) for v in static[col])
        ]
        for attr, frame in n.dynamic(comp).items():
            if frame.empty:
                continue
            series += [
                (comp, name, attr, i, float(frame.at[t, name])) for name in frame.columns for i, t in enumerate(snaps)
            ]
            if attr in cols and all(name in frame.columns for name in static.index):
                cols.remove(attr)
        with (out / table).open('w', newline='') as f:
            w = csv.writer(f, lineterminator='\n')
            w.writerow(['name', *cols])
            for name, row in static.iterrows():
                w.writerow([name, *(_cell(row[c]) for c in cols)])
    with (out / 'timeseries.csv').open('w', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['component', 'name', 'attribute', 'snapshot', 'value'])
        w.writerows(series)


if __name__ == '__main__':
    example, folder = sys.argv[1:3]
    write(getattr(pypsa.examples, example)(), Path(__file__).resolve().parent / folder)
