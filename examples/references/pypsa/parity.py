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

For each rung, the reference network is built twice from its own script: one
copy goes through `n.optimize(solver_name='highs')`, the other through
`prep.sources` into `lps.solve('examples/pypsa.yaml', …)` — the same HiGHS,
two model builders, one file. Each rung's outcome is stamped into
`references.json` under ``parity``, matched or not, and the run fails if any
rung differs. Run out of band, with the pins above: lpspec is pinned to a
commit because it has no release yet, and it carries its own math-spec.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lpspec as lps  # noqa: E402  the path insert above is what finds prep
import prep  # noqa: E402

MODEL = HERE.parents[1] / 'pypsa.yaml'


def network(script: Path):
    spec = importlib.util.spec_from_file_location(script.stem, script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build


def lanes(script: Path) -> tuple[float, float]:
    """PyPSA's objective and lpspec's, each from its own copy of the rung's network."""
    build = network(script)
    n = build()
    status, condition = n.optimize(solver_name='highs')
    assert status == 'ok', f'{script.stem}: pypsa did not solve — {status} / {condition}'
    result = lps.solve(MODEL, prep.sources(build()))
    assert result.is_ok, f'{script.stem}: lpspec did not solve — {result.termination_condition}'
    return float(n.objective), float(result.objective)


def main() -> int:
    path = HERE / 'references.json'
    stamped = json.loads(path.read_text())
    version = importlib.metadata.version('lpspec')
    differing = []
    for script in sorted(HERE.glob('rung*.py')):
        theirs, ours = lanes(script)
        matches = math.isclose(ours, theirs, rel_tol=1e-9, abs_tol=1e-6)
        stamped[script.stem]['parity'] = {'lpspec': version, 'lpspec_objective': ours, 'matches': matches}
        print(f'{script.stem}: pypsa {theirs} · lpspec {ours} · {"MATCH" if matches else "DIFFER"}')
        if not matches:
            differing.append(script.stem)
    path.write_text(json.dumps(stamped, indent=2, sort_keys=True) + '\n')
    if differing:
        print(f'{len(differing)} rung(s) differ: {", ".join(differing)}', file=sys.stderr)
        return 1
    print('every rung solves to one objective on both lanes')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
