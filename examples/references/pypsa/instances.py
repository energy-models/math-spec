# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The instances: every rung's network, built from the corpus tables in `data/`.

One wide CSV per component type for all rungs at once, a `rung` column picking
the instance, a blank cell meaning PyPSA's own default, and one long
`timeseries.csv` for everything that varies — eleven files for the whole
ladder. `build(rung)` reads them back through `n.add`, so the tables are the
single home of the instance data and the scripts keep only their narrative.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import pypsa

DATA = Path(__file__).resolve().parent / 'data'

#: Component -> its table, in the order dependencies load (buses before what sits on them).
TABLES = {
    'Bus': 'buses.csv',
    'Carrier': 'carriers.csv',
    'Generator': 'generators.csv',
    'Link': 'links.csv',
    'Load': 'loads.csv',
    'StorageUnit': 'storage_units.csv',
    'Store': 'stores.csv',
    'Line': 'lines.csv',
    'GlobalConstraint': 'global_constraints.csv',
}


def _rows(table: str, rung: str) -> list[dict[str, str]]:
    with (DATA / table).open() as handle:
        return [row for row in csv.DictReader(handle) if row['rung'] == rung]


def _parsed(component: str, attrs, column: str, cell: str) -> object:
    kind = str(attrs.at[column, 'type']) if column in attrs.index else ''
    if kind.startswith('boolean') or cell in ('True', 'False'):
        return cell == 'True'
    if kind.startswith('int'):
        return int(float(cell))
    if kind.startswith(('float', 'static')):
        return float(cell)
    if kind.startswith('string'):
        return cell
    try:
        return float(cell)
    except ValueError:
        return cell


def build(rung: str) -> pypsa.Network:
    """The rung's network, exactly as its rows in `data/` state it."""
    n = pypsa.Network()
    snapshots = _rows('snapshots.csv', rung)
    n.set_snapshots([int(row['snapshot']) for row in snapshots])
    for column in ('objective', 'stores', 'generators'):
        n.snapshot_weightings[column] = [float(row[column]) for row in snapshots]

    varying: dict[tuple[str, str], dict[str, dict[int, float]]] = {}
    for row in _rows('timeseries.csv', rung):
        cell = row['value']
        value = float(cell) if cell else math.nan
        varying.setdefault((row['component'], row['name']), {}).setdefault(row['attribute'], {})[
            int(row['snapshot'])
        ] = value

    for component, table in TABLES.items():
        attrs = n.components[component]['attrs']
        for row in _rows(table, rung):
            kwargs: dict[str, object] = {
                column: _parsed(component, attrs, column, cell)
                for column, cell in row.items()
                if column not in ('rung', 'name') and cell != ''
            }
            for attribute, points in varying.get((component, row['name']), {}).items():
                kwargs[attribute] = [points.get(int(t['snapshot']), math.nan) for t in snapshots]
            n.add(component, row['name'], **kwargs)
    return n
