#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT
#
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "lpspec @ git+https://github.com/fluxopt/lpspec@3d05a57f1774bf11778011083573de493f2bd732",
#   "linopy @ git+https://github.com/PyPSA/linopy@09c34dd9d771bafcd6900a505b33cb9048145c85",
#   "pypsa==1.3.0",
#   "pandas>=2.2",
#   "xarray>=2024.2",
#   "highspy==1.15.1",
#   "polars>=1.30",
# ]
# ///
"""The parity gate: every rung against PyPSA, as deep as the engines allow.

    uv run --script examples/references/pypsa/parity.py

Per rung, from the same network, three comparisons:

1. **Model against model** — PyPSA's ``n.optimize.create_model()`` and
   ``lpspec.linopy.build``, label for label: coefficients, sense, right-hand
   side, bounds, integrality, objective terms. No solver, so it covers MIP
   and QP alike. The verdict speaks the index table's words: ``equal`` is
   the one block PyPSA builds — **done**; ``region`` is the same rows from
   several ``where:`` blocks — **split**; ``mismatch`` fails the run. A rung
   whose file `lpspec.linopy` cannot build yet stamps the error instead —
   the upstream hardening this gate waits on — and its proof stops at (2).
2. **One solved objective across the fence** — PyPSA's solve against
   `lpspec.relational`'s, both HiGHS, rtol 1e-9 on the generic spine.
3. **Coverage stamps** — what the relational lane built per block, each
   dimension's size, the tables bound non-empty — read by the repository's
   coverage tests, so an equality is never over data that tests nothing.

Primals are deliberately not compared — an optimum need not be unique — and
counts and duals are not compared separately: both are strict subsets of (1).

The comparison reads linopy's own ``.flat`` export but does not call
``linopy.testing``: those asserts hold the raw datasets equal, and two
builders lay the same model out differently — PyPSA pads absent ``_term``
slots with NaN where lpspec writes -0.0, and term order within a row is the
builder's own. A canonicalizing ``assert`` upstream would shrink this file.
PyPSA's model is built before `lpspec.linopy` is imported: that import flips
linopy's global ``semantics`` option to ``v1`` and PyPSA speaks ``legacy``,
so the option is reset around each PyPSA build. Run out of band with the
pins above; linopy is pinned to a master commit because `lpspec.linopy`
needs the ``semantics`` option no release carries yet.
"""

from __future__ import annotations

import importlib.metadata
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import instances  # noqa: E402
import linopy  # noqa: E402
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


def built(result, declared) -> tuple[dict[str, int], dict[str, int]]:
    """The labels the relational lane actually built, per file block — masked ones excluded, like PyPSA's records."""
    return (
        {name: len(result.activity(name)) for name in declared.constraints},
        {name: len(result.primal(name)) for name in declared.variables},
    )


def pypsa_model(stem: str):
    """The network's own linopy model, built under the ``legacy`` semantics PyPSA speaks."""
    linopy.options['semantics'] = 'legacy'
    try:
        return instances.build(stem).optimize.create_model()
    finally:
        linopy.options['semantics'] = 'v1'


def _keyed(labels) -> pd.Series:
    """label per coordinate key — dim names dropped, ``snapshot`` first, so the two spellings align."""
    series = labels.to_series()
    index = series.index
    if index.nlevels > 1:
        order = sorted(index.names, key=lambda name: (name != 'snapshot', name))
        series = series.reorder_levels(order).sort_index()
        series.index = pd.Index(series.index.to_flat_index())
    return series


def _label_map(theirs, ours, pairs: dict[str, list[str]]) -> dict[int, int]:
    """Our variable labels to theirs, matched by name pair and coordinate key."""
    mapping: dict[int, int] = {}
    for pypsa_name, our_names in pairs.items():
        their = _keyed(theirs.variables[pypsa_name].labels)
        for our_name in our_names:
            for key, our_label in _keyed(ours.variables[our_name].labels).items():
                their_label = int(their[key])
                if our_label != -1 and their_label != -1:
                    mapping[int(our_label)] = their_label
    return mapping


def _rows(flat: pd.DataFrame, labels, relabel) -> dict:
    """Constraint rows by coordinate key: (sign, rhs, sorted (variable, coefficient) pairs)."""
    terms = defaultdict(list)
    meta = {}
    for row in flat.itertuples():
        terms[row.labels].append((relabel(int(row.vars)), float(row.coeffs)))
        meta[row.labels] = (row.sign, float(row.rhs))
    return {
        key: (*meta[int(label)], tuple(sorted(terms[int(label)])))
        for key, label in _keyed(labels).items()
        if int(label) != -1
    }


def _objective(model, relabel) -> tuple:
    """The objective as a sorted term tuple — quadratic pairs unordered."""
    flat = model.objective.expression.flat
    terms = []
    for row in flat.itertuples():
        if hasattr(row, 'vars1'):
            pair = tuple(sorted((relabel(int(row.vars1)), relabel(int(row.vars2)))))
        else:
            pair = (relabel(int(row.vars)),)
        terms.append((pair, round(float(row.coeffs), 9)))
    return tuple(sorted(terms))


def compare(theirs, ours, declared, gc_kinds: dict[str, str]) -> dict[str, list[str]]:
    """Verdicts: which PyPSA names are model-equal, which are the same region in several blocks, which differ."""
    rows = defaultdict(list)
    for name, block in declared.constraints.items():
        rows[stands_for(block.description)].append(name)
    columns = defaultdict(list)
    for name, block in declared.variables.items():
        columns[stands_for(block.description)].append(name)

    ours_to_theirs = _label_map(theirs, ours, columns)

    def relabel(label: int) -> int:
        if label == -1:
            return -1
        return ours_to_theirs.get(label, -label - 1000)

    verdict: dict[str, list[str]] = {'equal': [], 'region': [], 'mismatch': []}
    for pypsa_name, our_names in columns.items():
        their_kind = pypsa_name in [*theirs.integers, *theirs.binaries]
        ok = all((our_name in [*ours.integers, *ours.binaries]) == their_kind for our_name in our_names)
        bounds_theirs = {int(r.labels): (r.lower, r.upper) for r in theirs.variables[pypsa_name].flat.itertuples()}
        bounds_ours = {}
        for our_name in our_names:
            for r in ours.variables[our_name].flat.itertuples():
                bounds_ours[ours_to_theirs[int(r.labels)]] = (r.lower, r.upper)
        if bounds_ours != bounds_theirs:
            ok = False
        bucket = 'mismatch' if not ok else ('equal' if len(our_names) == 1 else 'region')
        verdict[bucket].append(pypsa_name)

    for pypsa_name, our_names in rows.items():
        their_names = (
            [n for n in theirs.constraints if n.startswith('GlobalConstraint-')]
            if not pypsa_name[0].isupper()
            else ([pypsa_name] if pypsa_name in theirs.constraints else [])
        )
        their_rows: dict = {}
        for their_name in their_names:
            constraint = theirs.constraints[their_name]
            for key, row in _rows(constraint.flat, constraint.labels, lambda x: x).items():
                their_rows[key if their_name == pypsa_name else their_name.removeprefix('GlobalConstraint-')] = row
        our_rows: dict = {}
        for our_name in our_names:
            constraint = ours.constraints[our_name]
            our_rows |= _rows(constraint.flat, constraint.labels, relabel)
        if not pypsa_name[0].isupper():
            typed = {label for label, gc in gc_kinds.items() if gc == pypsa_name}
            their_rows = {key: row for key, row in their_rows.items() if key in typed}
        if our_rows == their_rows:
            verdict['equal' if len(our_names) == 1 else 'region'].append(pypsa_name)
        else:
            verdict['mismatch'].append(pypsa_name)
            for key in sorted({*our_rows, *their_rows}, key=str):
                if our_rows.get(key) != their_rows.get(key):
                    print(
                        f'  {pypsa_name}[{key}]:\n    ours   {our_rows.get(key)}\n    theirs {their_rows.get(key)}',
                        file=sys.stderr,
                    )

    if _objective(ours, relabel) == _objective(theirs, lambda x: x):
        verdict['equal'].append('objective')
    else:
        verdict['mismatch'].append('objective')
    return {kind: sorted(names) for kind, names in verdict.items()}


def lanes(stem: str) -> tuple[dict[str, object], dict[str, object], bool]:
    """One rung through everything: the objective across the fence, the model against the model, the coverage."""
    from lpspec import linopy as lpl

    theirs = pypsa_model(stem)
    n = instances.build(stem)
    gc_kinds = {str(label): str(gc['type']) for label, gc in n.global_constraints.iterrows()}
    status, condition = n.optimize(solver_name='highs')
    assert status == 'ok', f'{stem}: pypsa did not solve — {status} / {condition}'
    model = MODELS.get(stem, MODEL)
    declared = math_spec.load_model(model)
    tables = bound(model, instances.build(stem))
    result = lps.solve(model, tables)
    assert result.is_ok, f'{stem}: lpspec did not solve — {result.termination_condition}'
    built_rows, built_columns = built(result, declared)
    parity = {
        'lpspec': importlib.metadata.version('lpspec'),
        'lpspec_objective': float(result.objective),
        'matches': math.isclose(float(result.objective), float(n.objective), rel_tol=1e-9, abs_tol=1e-6),
        'model': str(model.relative_to(HERE.parents[2])),
        'built_rows': built_rows,
        'built_columns': built_columns,
        'dims': {name: len(table) for name, table in tables.items() if name in declared.dimensions},
        'bound_nonempty': sorted(name for name, table in tables.items() if len(table)),
    }
    try:
        ours = lpl.build(model, tables)
    except Exception as error:
        note = f'{type(error).__name__}: {error}'.splitlines()[0][:200]
        return parity, {'linopy': linopy.__version__, 'error': note}, parity['matches']
    verdict = compare(theirs, ours, declared, gc_kinds)
    structural = {'linopy': linopy.__version__, **verdict}
    return parity, structural, parity['matches'] and not verdict['mismatch']


def main() -> int:
    stamped = json.loads(instances.RECORDS.read_text())
    broken = []
    for script in sorted(HERE.glob('rung_*.py')):
        stem = script.stem
        parity, structural, good = lanes(stem)
        stamped[stem]['parity'] = parity
        stamped[stem]['structural'] = structural
        proof = (
            f'{len(structural["equal"])} equal · {len(structural["region"])} region'
            if 'equal' in structural
            else f'objective only — {structural["error"]}'
        )
        print(f'{stem}: {"MATCH" if parity["matches"] else "DIFFER"} · {proof}')
        if not good:
            broken.append(stem)
    instances.write(stamped)
    if broken:
        print(f'{len(broken)} rung(s) differ: {", ".join(broken)}', file=sys.stderr)
        return 1
    print('every rung matches PyPSA as deep as the engines allow, and says how deep that is')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
