# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The instances: every rung's network is the shared spine plus its own folder.

`data/base/` is rung 1's transport spine, the network every rung starts from;
`data/<rung>/` holds only what that rung adds — its components as wide CSVs in
PyPSA's vocabulary and a `timeseries.csv` for what varies, which may also put
a schedule on a base component. The rung's folder therefore *is* its
construct, in data form, and no table carries a rung column.

Folders combine by appending rows, table by table — never by replacing a
table and never by a column-wise join. Each row keeps its own file's columns
and becomes one ``n.add``, so two files of different widths invent no empty
cells in each other; a blank cell is an attribute the row does not set, and
PyPSA supplies its default, exactly as for an unpassed keyword.
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


def _rows(folders: list[Path], table: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for folder in folders:
        path = folder / table
        if path.exists():
            with path.open() as handle:
                rows.extend(csv.DictReader(handle))
    return rows


def _parsed(attrs, column: str, cell: str) -> object:
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
    """The rung's network: the spine, plus exactly what the rung's folder adds."""
    folders = [DATA / 'base', DATA / rung]
    n = pypsa.Network()
    snapshots = _rows([DATA / 'base'], 'snapshots.csv')
    n.set_snapshots([int(row['snapshot']) for row in snapshots])
    for column in ('objective', 'stores', 'generators'):
        n.snapshot_weightings[column] = [float(row[column]) for row in snapshots]

    varying: dict[tuple[str, str], dict[str, dict[int, float]]] = {}
    for row in _rows(folders, 'timeseries.csv'):
        cell = row['value']
        value = float(cell) if cell else math.nan
        varying.setdefault((row['component'], row['name']), {}).setdefault(row['attribute'], {})[
            int(row['snapshot'])
        ] = value

    for component, table in TABLES.items():
        attrs = n.components[component]['attrs']
        for row in _rows(folders, table):
            kwargs: dict[str, object] = {
                column: _parsed(attrs, column, cell) for column, cell in row.items() if column != 'name' and cell != ''
            }
            for attribute, points in varying.get((component, row['name']), {}).items():
                kwargs[attribute] = [points.get(int(t['snapshot']), math.nan) for t in snapshots]
            n.add(component, row['name'], **kwargs)
    return n
