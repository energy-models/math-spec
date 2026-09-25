#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: mathspec Contributors
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
as `OPTIMIZE`; one that names `BRANCH_OUTAGES` is solved by
`n.optimize.optimize_security_constrained` over them.

A rung that names `ISSUE` records a PyPSA bug: the network PyPSA 1.3.0 gets
wrong, until the fix ships. Its `oracle()` returns networks PyPSA solves
correctly, each with the weight its objective takes in the intended one. The
record's `objective` is that intended objective, and `diverges` holds the issue
and what PyPSA gives instead: its objective, or the exception it raises. Rows
and columns are what PyPSA built, where it built any. `--check` fails where
PyPSA no longer diverges, and names the issue. PyPSA is not a dependency
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


def optimized(rung: str, n: pypsa.Network) -> pypsa.Network:
    outages = getattr(importlib.import_module(rung), 'BRANCH_OUTAGES', None)
    if outages is None:
        status, condition = n.optimize(solver_name='highs', **keywords(rung))
    else:
        status, condition = n.optimize.optimize_security_constrained(
            solver_name='highs', branch_outages=outages, **keywords(rung)
        )
    assert status == 'ok', f'{rung}: HiGHS did not solve — {status} / {condition}'
    return n


def close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-6)


def diverged(rung: str, issue: int) -> dict[str, object]:
    """The intended objective from the rung's oracle, beside what PyPSA gives on the rung's own network."""
    intended = sum(weight * float(optimized(rung, n).objective) for weight, n in importlib.import_module(rung).oracle())
    try:
        seen = record(optimized(rung, build(rung)))
    except Exception as error:
        return {
            'pypsa': pypsa.__version__,
            'objective': intended,
            'diverges': {'issue': issue, 'raises': type(error).__name__},
        }
    return {**seen, 'objective': intended, 'diverges': {'issue': issue, 'objective': seen['objective']}}


def solved(rung: str) -> dict[str, object]:
    issue = getattr(importlib.import_module(rung), 'ISSUE', None)
    return record(optimized(rung, build(rung))) if issue is None else diverged(rung, issue)


def fixed(seen: dict[str, object]) -> bool:
    """Whether PyPSA gives the intended objective on a rung that records one of its bugs."""
    diverges = seen.get('diverges', {})
    return 'objective' in diverges and close(diverges['objective'], seen['objective'])


def matches(kept: dict[str, object], seen: dict[str, object]) -> bool:
    """Equal records, every objective compared to a tolerance."""

    def split(r: dict[str, object]) -> tuple[list[float], dict[str, object]]:
        diverges = r.get('diverges', {})
        numbers = [r['objective'], *([diverges['objective']] if 'objective' in diverges else [])]
        rest = {k: v for k, v in diverges.items() if k != 'objective'}
        return numbers, {**r, 'objective': None, 'diverges': rest}

    (a, rest_a), (b, rest_b) = split(kept), split(seen)
    return rest_a == rest_b and len(a) == len(b) and all(map(close, a, b))


def main(argv: list[str]) -> int:
    check = '--check' in argv
    stamped = json.loads(RECORDS.read_text()) if RECORDS.exists() else {}
    stale = []
    for rung in rungs():
        seen = solved(rung)
        print(f'{rung}: objective {seen["objective"]}')
        if fixed(seen):
            issue = seen['diverges']['issue']
            print(
                f'{rung}: pypsa {pypsa.__version__} solves PyPSA/PyPSA#{issue} as intended — drop the divergence',
                file=sys.stderr,
            )
            return 1
        if check:
            if (kept := stamped.get(rung)) is None or not matches(kept, seen):
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
