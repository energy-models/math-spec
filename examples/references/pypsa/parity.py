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
`lps.solve` — the same HiGHS, two model builders, one file. Each rung's
outcome is stamped into `references.json` under ``parity``, matched or not,
and the run fails if any rung differs. Run out of band, with the pins above:
lpspec is pinned to a commit because it has no release yet, and it carries
its own math-spec.
"""

from __future__ import annotations

import importlib.metadata
import json
import math
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


def bound(model: Path, n) -> dict[str, object]:
    """`prep.sources` cut to what *model* declares — lpspec refuses a key the model does not take."""
    declared = math_spec.load_model(model)
    names = {*declared.dimensions, *declared.parameters, *declared.lookups}
    return {name: table for name, table in prep.sources(n).items() if name in names}


def lanes(stem: str) -> tuple[float, float, str]:
    """PyPSA's and lpspec's objectives and the file lpspec bound, each lane from its own copy of the network."""
    n = instances.build(stem)
    status, condition = n.optimize(solver_name='highs')
    assert status == 'ok', f'{stem}: pypsa did not solve — {status} / {condition}'
    model = MODELS.get(stem, MODEL)
    result = lps.solve(model, bound(model, instances.build(stem)))
    assert result.is_ok, f'{stem}: lpspec did not solve — {result.termination_condition}'
    return float(n.objective), float(result.objective), str(model.relative_to(HERE.parents[2]))


def main() -> int:
    stamped = json.loads(instances.RECORDS.read_text())
    version = importlib.metadata.version('lpspec')
    differing = []
    for script in sorted(HERE.glob('rung_*.py')):
        theirs, ours, model = lanes(script.stem)
        matches = math.isclose(ours, theirs, rel_tol=1e-9, abs_tol=1e-6)
        stamped[script.stem]['parity'] = {
            'lpspec': version,
            'lpspec_objective': ours,
            'matches': matches,
            'model': model,
        }
        print(f'{script.stem}: pypsa {theirs} · lpspec {ours} · {"MATCH" if matches else "DIFFER"}')
        if not matches:
            differing.append(script.stem)
    instances.write(stamped)
    if differing:
        print(f'{len(differing)} rung(s) differ: {", ".join(differing)}', file=sys.stderr)
        return 1
    print('every rung solves to one objective on both lanes')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
