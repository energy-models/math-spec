# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The instances: every rung's network is the shared spine plus its own folder.

`data/base/` is rung 1's transport spine, the network every rung starts from;
a folder with its own `snapshots.csv` is a whole network instead.
`data/<rung>/` otherwise holds only what that rung adds — its components as wide CSVs in
PyPSA's vocabulary and a `timeseries.csv` for what varies, which may also put
a schedule on a base component. The folders are the rungs: `reference.py`
runs every one.

Folders combine by appending rows, table by table — never by replacing a
table and never by a column-wise join. Each row keeps its own file's columns
and becomes one ``n.add``; a blank cell is an attribute the row does not set,
and PyPSA supplies its default, exactly as for an unpassed keyword.

`reference.py` beside this file runs out of band — PyPSA is not a dependency
of this project, and the script pins the versions the recorded numbers are
from. It calls `stamp`, which solves a network through PyPSA's own linopy
model and writes what it saw into `references.json`. The engines' side of that
file — the parity and model-for-model stamps — is written by lpspec's
differential runner (`differential/pypsa/parity.py` there), run against this
checkout whenever the corpus changes; nothing in this repository builds or
solves the models it states. To refresh the certificate after a corpus
change, run that runner from a clone of lpspec and commit the rewritten
`references.json` with the change::

    git clone https://github.com/fluxopt/lpspec ../lpspec
    uv run --with-editable '../lpspec[linopy]' \\
        --with 'pypsa==1.3.0' --with 'highspy==1.15.1' --with 'polars>=1.30' \\
        python ../lpspec/differential/pypsa/parity.py .

The advisory `PyPSA parity` workflow runs the same command with a pinned
lpspec, so a corpus change that breaks parity shows on the PR without
gating it.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pypsa

DATA = Path(__file__).resolve().parent / 'data'
RECORDS = Path(__file__).resolve().parent / 'references.json'

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


def settings(rung: str) -> dict[str, object]:
    """The rung's `rung.json`: the model file it binds, the keywords its `n.optimize` takes, its scenarios and risk preference if any."""
    path = DATA / rung / 'rung.json'
    given = json.loads(path.read_text()) if path.exists() else {}
    return {'model': 'examples/pypsa.yaml', 'optimize': {}, **given}


def rungs() -> list[str]:
    """Every rung, in ladder order — the folders beside the spine."""
    return sorted(path.name for path in DATA.iterdir() if path.is_dir() and path.name != 'base')


def build(rung: str) -> pypsa.Network:
    """The rung's network: the spine, plus exactly what the rung's folder adds."""
    folders = [DATA / rung] if (DATA / rung / 'snapshots.csv').exists() else [DATA / 'base', DATA / rung]
    n = pypsa.Network()
    snapshots = _rows(folders[:1], 'snapshots.csv')
    n.set_snapshots([int(row['snapshot']) for row in snapshots])
    for column in ('objective', 'stores', 'generators'):
        n.snapshot_weightings[column] = [float(row[column]) for row in snapshots]

    varying: dict[tuple[str, str], dict[str, dict[int, float]]] = {}
    for row in _rows(folders, 'timeseries.csv'):
        if not row['value'] or row.get('scenario'):
            continue
        varying.setdefault((row['component'], row['name']), {}).setdefault(row['attribute'], {})[
            int(row['snapshot'])
        ] = float(row['value'])

    for component, table in TABLES.items():
        attrs = n.components[component]['attrs']
        for row in _rows(folders, table):
            kwargs: dict[str, object] = {
                column: _parsed(attrs, column, cell) for column, cell in row.items() if column != 'name' and cell != ''
            }
            for attribute, points in varying.get((component, row['name']), {}).items():
                kwargs[attribute] = [points.get(int(t['snapshot']), math.nan) for t in snapshots]
            n.add(component, row['name'], **kwargs)
    given = settings(rung)
    if given.get('scenarios'):
        n.set_scenarios(given['scenarios'])
        for row in _rows(folders, 'timeseries.csv'):
            if row.get('scenario') and row['value']:
                frame = n.dynamic(row['component'])[row['attribute']]
                frame.loc[frame.index[int(row['snapshot'])], (row['scenario'], row['name'])] = float(row['value'])
        if given.get('risk_preference'):
            n.set_risk_preference(**given['risk_preference'])
    return n


def record(n: pypsa.Network) -> dict[str, object]:
    """What a solve saw, in the shape `references.json` holds.

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
            '/'.join(map(str, bus)) if isinstance(bus, tuple) else str(bus): [
                float(x) for x in n.buses_t.marginal_price[bus]
            ]
            for bus in n.buses_t.marginal_price.columns
        }
        if not n.buses_t.marginal_price.empty and bool(n.buses_t.marginal_price.notna().all().all())
        else {},
    }


def write(stamped: dict[str, object]) -> None:
    RECORDS.write_text(json.dumps(stamped, indent=2, sort_keys=True) + '\n')


def stamp(rung: str, n: pypsa.Network) -> None:
    """Solve *n* through PyPSA's own linopy model with HiGHS and record what it saw."""
    status, condition = n.optimize(solver_name='highs', **settings(rung)['optimize'])
    assert status == 'ok', f'HiGHS did not solve: {status} / {condition}'
    stamped = json.loads(RECORDS.read_text()) if RECORDS.exists() else {}
    stamped[rung] = record(n)
    write(stamped)
    print(f'{rung}: objective {n.objective}')
