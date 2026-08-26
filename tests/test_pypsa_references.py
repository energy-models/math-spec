# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""What the PyPSA references pin the model to, without a build engine.

The scripts under ``examples/references/pypsa/`` run out of band — PyPSA is
not a dependency of this project — and record the variables and constraints
PyPSA actually built. That makes the *names* assertable in both directions
today: PyPSA builds nothing the file does not stand for, and everything the
file declares is built by some reference network. Row **counts** and the
recorded duals stay recorded rather than asserted — comparing those takes the
build engine the parity harness is waiting on. The page blocks the records
feed are held current by ``tests/test_docs.py`` through ``tools.gallery``.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pytest

from math_spec import load_model
from tools.gallery import _stands_for

REFERENCES = Path(__file__).resolve().parent.parent / 'examples' / 'references' / 'pypsa'
SCRIPTS = sorted(REFERENCES.glob('rung*.py'))
RECORDED: dict[str, dict] = json.loads((REFERENCES / 'references.json').read_text())

MODEL = load_model(REFERENCES.parents[1] / 'pypsa.yaml')
ROWS_DECLARED = {_stands_for(name, block.description) for name, block in MODEL.constraints.items()}
COLUMNS_DECLARED = {_stands_for(name, block.description) for name, block in MODEL.variables.items()}
#: The five GlobalConstraint formulas open with their *type* — PyPSA names
#: those rows after each row's own label, so they are matched through the
#: recorded type and sense instead of by name.
GC_TYPES = {name for name in ROWS_DECLARED if not name[0].isupper()}
RECORDED_ROWS: set[str] = set().union(*(record['rows'] for record in RECORDED.values()))
RECORDED_COLUMNS: set[str] = set().union(*(record['columns'] for record in RECORDED.values()))
GC_RECORDED: dict[str, dict] = {
    label: gc for record in RECORDED.values() for label, gc in record['global_constraints'].items()
}


@pytest.mark.parametrize('script', SCRIPTS, ids=[script.stem for script in SCRIPTS])
def test_every_rung_has_its_marker_pair_on_exactly_one_declared_page(script: Path):
    from tools import gallery

    pages = [(gallery.PAGES / page).read_text() for page in gallery.DECLARED]
    carrying = sum(f'<!-- reference:{script.stem}:begin -->' in text for text in pages)
    assert carrying == 1, (
        'a rung shows its reference on one declared page — the generator skips a page without the marker'
    )


@pytest.mark.parametrize('script', SCRIPTS, ids=[script.stem for script in SCRIPTS])
def test_every_rung_is_the_spine_plus_its_own_folder(script: Path):
    """`instances.build` reads `data/base/` plus `data/<rung>/`, so a rung without a folder adds nothing."""
    folder = REFERENCES / 'data' / script.stem
    assert any(folder.glob('*.csv')), 'no addition tables — the rung folder is where its construct lives, as data'


def test_every_reference_script_has_a_recorded_solve():
    assert {script.stem for script in SCRIPTS} == set(RECORDED), (
        'a reference script without a record, or a record without a script — run the scripts, or delete the orphan'
    )


@pytest.mark.parametrize('script', SCRIPTS, ids=[script.stem for script in SCRIPTS])
def test_the_record_is_from_the_pinned_pypsa(script: Path):
    pinned = re.search(r'"pypsa==([^"]+)"', script.read_text())
    assert pinned is not None, 'a reference script pins pypsa in its PEP 723 block'
    assert RECORDED[script.stem]['pypsa'] == pinned.group(1), (
        'the recorded solve is from another pypsa than the script pins — re-run it in the pinned environment'
    )


@pytest.mark.parametrize('stem', sorted(RECORDED), ids=sorted(RECORDED))
def test_the_recorded_solve_is_usable_as_an_oracle(stem: str):
    recorded = RECORDED[stem]
    assert math.isfinite(recorded['objective']), 'an oracle needs a finite objective'
    assert recorded['rows'], 'an oracle needs the row counts a parity gate would compare'


@pytest.mark.parametrize('stem', sorted(RECORDED), ids=sorted(RECORDED))
def test_both_lanes_solve_the_rung_to_one_objective(stem: str):
    parity = RECORDED[stem].get('parity')
    assert parity is not None, 'the rung has no cross-lane record — run parity.py in its pinned environment'
    assert parity['matches'], (
        f'lpspec and pypsa disagree: {parity["lpspec_objective"]} against {RECORDED[stem]["objective"]} '
        f'— re-run parity.py and read its per-rung report'
    )


def test_pypsa_builds_no_variable_the_file_does_not_declare():
    unmatched = RECORDED_COLUMNS - COLUMNS_DECLARED
    assert not unmatched, f'pypsa builds these and the file declares nothing that stands for them: {sorted(unmatched)}'


def test_every_declared_variable_is_built_by_some_reference():
    unbuilt = COLUMNS_DECLARED - RECORDED_COLUMNS
    assert not unbuilt, f'no reference network builds these declared variables — extend a fixture: {sorted(unbuilt)}'


def test_pypsa_builds_no_row_the_file_does_not_declare():
    named = {row for row in RECORDED_ROWS if not row.startswith('GlobalConstraint-')}
    unmatched = named - ROWS_DECLARED
    assert not unmatched, f'pypsa builds these and the file declares nothing that stands for them: {sorted(unmatched)}'


def test_every_declared_row_is_built_by_some_reference():
    unbuilt = ROWS_DECLARED - GC_TYPES - RECORDED_ROWS
    assert not unbuilt, f'no reference network builds these declared rows — extend a fixture: {sorted(unbuilt)}'


@pytest.mark.parametrize('row', sorted(row for row in RECORDED_ROWS if row.startswith('GlobalConstraint-')), ids=str)
def test_a_global_constraint_row_has_a_block_of_its_recorded_type_and_sense(row: str):
    gc = GC_RECORDED[row.removeprefix('GlobalConstraint-')]
    matching = [
        name
        for name, block in MODEL.constraints.items()
        if _stands_for(name, block.description) == gc['type'] and f"'{gc['sense']}'" in (block.where or '')
    ]
    assert matching, f'no declared block takes a {gc["type"]} row of sense {gc["sense"]}'
