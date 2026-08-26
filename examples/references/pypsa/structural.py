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
#   "polars>=1.30",
# ]
# ///
"""The structural gate: PyPSA's linopy model against the file's, label for label.

    uv run --script examples/references/pypsa/structural.py

For each rung, PyPSA's ``n.optimize.create_model()`` and
``lpspec.linopy.build`` produce two ``linopy.Model``s from the same network,
and this compares them — every label's coefficients, sense, right-hand side,
bounds and integrality, no solver involved. The verdict per PyPSA name:

- ``equal`` — one block, the same rows: model-equal, the table's **done**.
- ``region`` — the same rows gathered from several ``where:`` blocks — the
  table's **split**: same feasible region, not yet block-for-block.
- ``mismatch`` — a real difference, printed and failing the run.

A rung whose file `lpspec.linopy` cannot build yet stamps the error instead —
the upstream hardening this gate is waiting on. PyPSA's model is built before
`lpspec.linopy` is imported: that import flips linopy's global ``semantics``
option to ``v1``, and PyPSA speaks ``legacy``, so the option is reset around
each PyPSA build. Run out of band with the pins above; linopy is pinned to a
master commit because `lpspec.linopy` needs the ``semantics`` option no
release carries yet.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import instances  # noqa: E402
import linopy  # noqa: E402
import parity  # noqa: E402

import math_spec  # noqa: E402


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


def compare(theirs, ours, declared) -> dict[str, list[str]]:
    """Verdicts: which PyPSA names are model-equal, which are the same region in several blocks, which differ."""
    rows = defaultdict(list)
    for name, block in declared.constraints.items():
        rows[parity.stands_for(block.description)].append(name)
    columns = defaultdict(list)
    for name, block in declared.variables.items():
        columns[parity.stands_for(block.description)].append(name)

    ours_to_theirs = _label_map(theirs, ours, columns)

    def relabel(label: int) -> int:
        if label == -1:
            return -1
        return ours_to_theirs.get(label, -label - 1000)

    verdict: dict[str, list[str]] = {'equal': [], 'region': [], 'mismatch': []}
    for pypsa_name, our_names in columns.items():
        their_flat = theirs.variables[pypsa_name].flat
        their_kind = pypsa_name in [*theirs.integers, *theirs.binaries]
        ok = True
        for our_name in our_names:
            our_kind = our_name in [*ours.integers, *ours.binaries]
            if our_kind != their_kind:
                ok = False
        bounds_theirs = {int(r.labels): (r.lower, r.upper) for r in their_flat.itertuples()}
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
            typed = {label for label, gc in GC_KINDS.items() if gc == pypsa_name}
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


GC_KINDS: dict[str, str] = {}


def main() -> int:
    from lpspec import linopy as lpl

    stamped = json.loads(instances.RECORDS.read_text())
    version = linopy.__version__
    broken = []
    for script in sorted(HERE.glob('rung_*.py')):
        stem = script.stem
        theirs = pypsa_model(stem)
        n = instances.build(stem)
        GC_KINDS.clear()
        GC_KINDS.update({str(label): str(gc['type']) for label, gc in n.global_constraints.iterrows()})
        model = parity.MODELS.get(stem, parity.MODEL)
        declared = math_spec.load_model(model)
        try:
            ours = lpl.build(model, parity.bound(model, n))
        except Exception as error:
            note = f'{type(error).__name__}: {error}'.splitlines()[0][:200]
            stamped[stem]['structural'] = {'linopy': version, 'error': note}
            print(f'{stem}: lpspec.linopy cannot build — {note}')
            continue
        verdict = compare(theirs, ours, declared)
        stamped[stem]['structural'] = {'linopy': version, **verdict}
        state = 'MISMATCH' if verdict['mismatch'] else 'one model'
        print(f'{stem}: {len(verdict["equal"])} equal · {len(verdict["region"])} region · {state}')
        if verdict['mismatch']:
            broken.append(stem)
    instances.write(stamped)
    if broken:
        print(f'{len(broken)} rung(s) mismatch: {", ".join(broken)}', file=sys.stderr)
        return 1
    print('every rung that builds on both lanes builds one model, up to the documented splits')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
