#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

# /// script
# requires-python = ">=3.12"
# dependencies = ["pypsa==1.3.0", "linopy==0.9.1", "pandas>=2.2", "xarray==2026.7.0", "highspy==1.15.1"]
# ///
"""Solve every rung's network through PyPSA and record what it saw.

    uv run --script examples/references/pypsa/reference.py            # rewrite references.json
    uv run --script examples/references/pypsa/reference.py --check    # fail where a rung no longer solves to its record

A rung is a `rung_*.py` beside this file whose `build()` returns the network:
the spine (`spine.py`) plus that rung's own `n.add` calls, data inline, so
the PyPSA model under review is the script itself. A rung stated by a file of
its own names it as `MODEL`; one that needs `n.optimize` keywords names them
as `OPTIMIZE`. PyPSA is not a dependency
of this project; this script pins the versions the recorded numbers are from,
and the `PyPSA references` workflow runs `--check` on every change.
"""

from __future__ import annotations

import importlib
import json
import math
import sys
from pathlib import Path

import pypsa

HERE = Path(__file__).resolve().parent
RECORDS = HERE / 'references.json'
sys.path.insert(0, str(HERE))


def rungs() -> list[str]:
    """Every rung, in ladder order."""
    return sorted(path.stem for path in HERE.glob('rung_*.py'))


def build(rung: str) -> pypsa.Network:
    return importlib.import_module(rung).build()


def keywords(rung: str) -> dict[str, object]:
    """What the rung's `n.optimize` takes beyond the solver — the script's `OPTIMIZE`, if it names any."""
    return dict(getattr(importlib.import_module(rung), 'OPTIMIZE', {}))


def record(n: pypsa.Network) -> dict[str, object]:
    """What a solve saw. Row and column counts skip masked labels: what a solver was handed."""
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
    }


def solved(rung: str) -> dict[str, object]:
    n = build(rung)
    status, condition = n.optimize(solver_name='highs', **keywords(rung))
    assert status == 'ok', f'{rung}: HiGHS did not solve — {status} / {condition}'
    return record(n)


def main(argv: list[str]) -> int:
    check = '--check' in argv
    stamped = json.loads(RECORDS.read_text()) if RECORDS.exists() else {}
    stale = []
    for rung in rungs():
        seen = solved(rung)
        print(f'{rung}: objective {seen["objective"]}')
        if check:
            kept = stamped.get(rung)
            if (
                kept is None
                or not math.isclose(kept['objective'], seen['objective'], rel_tol=1e-9, abs_tol=1e-6)
                or {k: v for k, v in kept.items() if k != 'objective'}
                != {k: v for k, v in seen.items() if k != 'objective'}
            ):
                stale.append(rung)
        else:
            stamped[rung] = seen
    if check:
        if stale:
            print(
                f'{len(stale)} rung(s) no longer solve to their record: {", ".join(stale)} — run reference.py',
                file=sys.stderr,
            )
            return 1
        print('every rung solves to its record')
        return 0
    RECORDS.write_text(json.dumps(stamped, indent=2, sort_keys=True) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
