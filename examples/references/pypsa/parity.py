#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT
#
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "lpspec @ git+https://github.com/fluxopt/lpspec@3d05a57f1774bf11778011083573de493f2bd732",
#   "pypsa==1.3.0",
#   "linopy==0.9.1",
#   "pandas>=2.2",
#   "xarray==2026.7.0",
#   "highspy==1.15.1",
#   "polars>=1.30",
# ]
# ///
"""Both lanes over every rung: PyPSA solves its network, lpspec solves the file.

    uv run --script examples/references/pypsa/parity.py

For each rung the network is built twice from `data/`: one copy goes through
`n.optimize(solver_name='highs')`, the other through `prep.sources` into
`lps.solve` — the same HiGHS, two model builders, one file. Asserted lane to
lane: the objective; the row and column count under every PyPSA name (split
`where:` blocks sum to their one PyPSA row, GlobalConstraint rows sum by
type); and the bus-balance duals against PyPSA's `marginal_price` where both
lanes price (lpspec refuses duals on a mixed-integer model, stamped ``mip``).
Primals are deliberately not compared — an optimum need not be unique. Each
rung's outcome is stamped into `references.json` under ``parity`` and the run
fails if any rung differs. Run out of band, with the pins above: lpspec is
pinned to a commit because it has no release yet, and it carries its own
math-spec.
"""

from __future__ import annotations

import importlib.metadata
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import instances  # noqa: E402
import lpspec as lps  # noqa: E402  the path insert above is what finds the siblings
import prep  # noqa: E402

import math_spec  # noqa: E402  lpspec's own pin, used to read what a model declares

MODEL = HERE.parents[1] / 'pypsa.yaml'

#: A rung that states a different file says so here; every other rung binds the one file.
MODELS = {'rung_10_quadratic_costs': HERE.parents[1] / 'pypsa_quadratic.yaml'}


def stands_for(description: str | None) -> str:
    """The PyPSA name a declaration's description opens with, in backticks — the declared pages' convention."""
    return re.match(r'`([^`]+)`', description or '').group(1)


def bound(model: Path, n) -> dict[str, object]:
    """`prep.sources` cut to what *model* declares — lpspec refuses a key the model does not take."""
    declared = math_spec.load_model(model)
    names = {*declared.dimensions, *declared.parameters, *declared.lookups}
    return {name: table for name, table in prep.sources(n).items() if name in names}


def _by_pypsa_name(declared_blocks, count) -> dict[str, int]:
    """*count* summed under each block's PyPSA name — split ``where:`` blocks sum to their one row."""
    counts: dict[str, int] = {}
    for name, block in declared_blocks.items():
        key = stands_for(block.description)
        counts[key] = counts.get(key, 0) + count(name)
    return counts


def structure(result, model: Path, record: dict) -> tuple[bool, bool]:
    """Whether lpspec built the same row and column counts PyPSA recorded, name by name."""
    declared = math_spec.load_model(model)
    ours_rows = _by_pypsa_name(declared.constraints, lambda name: len(result.activity(name)))
    ours_columns = _by_pypsa_name(declared.variables, lambda name: len(result.primal(name)))
    theirs_rows: dict[str, int] = {}
    for row, count in record['rows'].items():
        if row.startswith('GlobalConstraint-'):
            row = record['global_constraints'][row.removeprefix('GlobalConstraint-')]['type']
        theirs_rows[row] = theirs_rows.get(row, 0) + count
    theirs_columns = dict(record['columns'])
    same = []
    for label, ours, theirs in [('rows', ours_rows, theirs_rows), ('columns', ours_columns, theirs_columns)]:
        unequal = {key for key in {*ours, *theirs} if ours.get(key, 0) != theirs.get(key, 0)}
        for key in sorted(unequal):
            print(f'  {label} {key}: lpspec {ours.get(key, 0)} · pypsa {theirs.get(key, 0)}', file=sys.stderr)
        same.append(not unequal)
    return same[0], same[1]


def prices(result, record: dict) -> str:
    """Bus-balance duals against PyPSA's recorded `marginal_price`: match, differ, mip, or unpriced."""
    if not record['marginal_price']:
        return 'unpriced'
    try:
        frame = result.dual('Bus_nodal_balance')
    except Exception:
        return 'mip'
    for row in frame.iter_rows(named=True):
        want = record['marginal_price'][row['bus']][int(row['snapshot'])]
        if not math.isclose(row['value'], want, rel_tol=1e-6, abs_tol=1e-6):
            print(f'  dual ({row["snapshot"]}, {row["bus"]}): lpspec {row["value"]} · pypsa {want}', file=sys.stderr)
            return 'differ'
    return 'match'


def lanes(stem: str, record: dict) -> dict[str, object]:
    """One rung through both lanes, compared: objective, per-name counts, and duals where both lanes price."""
    n = instances.build(stem)
    status, condition = n.optimize(solver_name='highs')
    assert status == 'ok', f'{stem}: pypsa did not solve — {status} / {condition}'
    model = MODELS.get(stem, MODEL)
    result = lps.solve(model, bound(model, instances.build(stem)))
    assert result.is_ok, f'{stem}: lpspec did not solve — {result.termination_condition}'
    rows, columns = structure(result, model, record)
    return {
        'lpspec_objective': float(result.objective),
        'matches': math.isclose(float(result.objective), float(n.objective), rel_tol=1e-9, abs_tol=1e-6),
        'rows_match': rows,
        'columns_match': columns,
        'duals': prices(result, record),
        'model': str(model.relative_to(HERE.parents[2])),
    }


def main() -> int:
    stamped = json.loads(instances.RECORDS.read_text())
    version = importlib.metadata.version('lpspec')
    differing = []
    for script in sorted(HERE.glob('rung_*.py')):
        stem = script.stem
        parity = {'lpspec': version, **lanes(stem, stamped[stem])}
        stamped[stem]['parity'] = parity
        good = parity['matches'] and parity['rows_match'] and parity['columns_match'] and parity['duals'] != 'differ'
        print(
            f'{stem}: pypsa {stamped[stem]["objective"]} · lpspec {parity["lpspec_objective"]} · '
            f'{"MATCH" if parity["matches"] else "DIFFER"} · rows {"=" if parity["rows_match"] else "≠"} · '
            f'columns {"=" if parity["columns_match"] else "≠"} · duals {parity["duals"]}'
        )
        if not good:
            differing.append(stem)
    instances.write(stamped)
    if differing:
        print(f'{len(differing)} rung(s) differ: {", ".join(differing)}', file=sys.stderr)
        return 1
    print('every rung solves to one objective, one structure, on both lanes')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
