# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""What the PyPSA references pin the model to, without a build engine.

The scripts under ``examples/references/pypsa/`` run out of band — PyPSA is
not a dependency of this project — and record what each lane built and
solved. The suite asserts from the records: names both directions, per-name
row and column counts, bus prices where both lanes price, block-level
coverage, and — where `lpspec.linopy` can build — that the two lanes build
one linopy model, label for label. The page blocks the records feed are held
current by ``tests/test_docs.py`` through ``tools.gallery``.
"""

from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING

import pytest

from math_spec import load_model
from tools import gallery
from tools._page import ROOT
from tools.gallery import DECLARED, RECORDED, REFERENCES, _stands_for

if TYPE_CHECKING:
    from pathlib import Path

SCRIPTS = sorted(REFERENCES.glob('rung_*.py'))
PAGE_TEXTS = [(gallery.PAGES / page).read_text() for page in DECLARED]

MODELS = [load_model(path) for path in DECLARED.values()]
#: Model (by the path parity stamps) -> the loaded model and the rungs that bind it.
BINDINGS = {str(path.relative_to(ROOT)): (load_model(path), []) for path in DECLARED.values()}
for _stem, _record in RECORDED.items():
    BINDINGS[_record['parity']['model']][1].append(_stem)
ROWS_DECLARED = {_stands_for(name, block.description) for m in MODELS for name, block in m.constraints.items()}
COLUMNS_DECLARED = {_stands_for(name, block.description) for m in MODELS for name, block in m.variables.items()}
#: The five GlobalConstraint formulas open with their *type* — PyPSA names
#: those rows after each row's own label, so they are matched through the
#: recorded type and sense instead of by name.
GC_TYPES = {name for name in ROWS_DECLARED if not name[0].isupper()}
RECORDED_ROWS: set[str] = set().union(*(record['rows'] for record in RECORDED.values()))
RECORDED_COLUMNS: set[str] = set().union(*(record['columns'] for record in RECORDED.values()))
GC_RECORDED: dict[str, dict] = {
    label: gc for record in RECORDED.values() for label, gc in record['global_constraints'].items()
}


@pytest.mark.parametrize('key', ['spine', *(script.stem for script in SCRIPTS)])
def test_every_reference_block_has_its_marker_pair_on_exactly_one_declared_page(key: str):
    carrying = sum(f'<!-- reference:{key}:begin -->' in text for text in PAGE_TEXTS)
    assert carrying == 1, (
        'a reference block shows on one declared page — the generator skips a page without the marker pair'
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


@pytest.mark.parametrize('stem', sorted(RECORDED), ids=sorted(RECORDED))
def test_both_lanes_build_the_same_rows_and_columns(stem: str):
    parity = RECORDED[stem]['parity']
    assert parity['rows_match'] and parity['columns_match'], (
        'the two lanes built different counts under some PyPSA name — parity.py prints which'
    )


@pytest.mark.parametrize('stem', sorted(RECORDED), ids=sorted(RECORDED))
def test_bus_prices_agree_wherever_both_lanes_price(stem: str):
    assert RECORDED[stem]['parity']['duals'] in ('match', 'mip', 'unpriced'), (
        "lpspec's bus-balance duals differ from PyPSA's recorded marginal_price — parity.py prints where"
    )


@pytest.mark.parametrize('stem', sorted(RECORDED), ids=sorted(RECORDED))
def test_the_structural_lane_finds_one_model_or_names_its_blocker(stem: str):
    """`structural.py` compares the two linopy models label for label; a rung it cannot build stamps why."""
    structural = RECORDED[stem].get('structural')
    assert structural is not None, 'no structural record — run structural.py in its pinned environment'
    assert not structural.get('mismatch'), (
        f'the two lanes build different models: {structural.get("mismatch")} — structural.py prints each label'
    )
    assert structural.get('error') or 'equal' in structural, 'a structural stamp carries a verdict or its blocker'


@pytest.mark.parametrize('stem', sorted(RECORDED), ids=sorted(RECORDED))
def test_a_region_verdict_is_a_documented_split(stem: str):
    """`region` — same feasible region, several blocks — may cover only names the file states as several blocks."""
    structural = RECORDED[stem].get('structural', {})
    model, _ = BINDINGS[RECORDED[stem]['parity']['model']]
    counts: dict[str, int] = {}
    for name, block in [*model.constraints.items(), *model.variables.items()]:
        key = _stands_for(name, block.description)
        counts[key] = counts.get(key, 0) + 1
    undocumented = set(structural.get('region', [])) - {name for name, n in counts.items() if n > 1}
    assert not undocumented, f'region verdicts on names the file states as one block: {sorted(undocumented)}'


def test_pypsa_builds_no_variable_the_files_do_not_declare():
    unmatched = RECORDED_COLUMNS - COLUMNS_DECLARED
    assert not unmatched, f'pypsa builds these and the files declare nothing that stands for them: {sorted(unmatched)}'


def test_every_declared_variable_is_built_by_some_reference():
    unbuilt = COLUMNS_DECLARED - RECORDED_COLUMNS
    assert not unbuilt, f'no reference network builds these declared variables — extend a fixture: {sorted(unbuilt)}'


def test_pypsa_builds_no_row_the_files_do_not_declare():
    named = {row for row in RECORDED_ROWS if not row.startswith('GlobalConstraint-')}
    unmatched = named - ROWS_DECLARED
    assert not unmatched, f'pypsa builds these and the files declare nothing that stands for them: {sorted(unmatched)}'


def test_every_declared_row_is_built_by_some_reference():
    unbuilt = ROWS_DECLARED - GC_TYPES - RECORDED_ROWS
    assert not unbuilt, f'no reference network builds these declared rows — extend a fixture: {sorted(unbuilt)}'


def _blocks():
    for rel, (model, stems) in BINDINGS.items():
        for kind, blocks in (('built_rows', model.constraints), ('built_columns', model.variables)):
            for name, block in blocks.items():
                yield rel, kind, name, block, stems


@pytest.mark.parametrize(
    ('rel', 'kind', 'name', 'block', 'stems'),
    list(_blocks()),
    ids=[f'{rel}:{name}' for rel, _, name, _, _ in _blocks()],
)
def test_every_block_is_built_by_some_rung(rel, kind, name, block, stems):
    """A declared block no fixture builds is a silent regime — the class #124 tracks."""
    assert sum(RECORDED[stem]['parity'][kind][name] for stem in stems), (
        f'no reference network builds {name} of {rel} — extend a fixture until its rows exist somewhere'
    )


@pytest.mark.parametrize(
    ('rel', 'kind', 'name', 'block', 'stems'),
    [entry for entry in _blocks() if entry[3].where],
    ids=[f'{rel}:{name}' for rel, _, name, block, _ in _blocks() if block.where],
)
def test_every_masked_block_is_partially_masked_somewhere(rel, kind, name, block, stems):
    """A `where:` no rung leaves half-true is untested as a mask — full or empty proves only all-or-nothing."""
    partial = any(
        0
        < RECORDED[stem]['parity'][kind][name]
        < math.prod(RECORDED[stem]['parity']['dims'][dim] for dim in block.foreach)
        for stem in stems
    )
    assert partial, f'{name} of {rel} is always all-or-nothing — give some fixture a label its mask excludes'


@pytest.mark.parametrize('rel', sorted(BINDINGS), ids=sorted(BINDINGS))
def test_every_parameter_is_bound_nonempty_by_some_rung(rel):
    """A parameter every rung leaves empty is data no gate has ever weighed."""
    model, stems = BINDINGS[rel]
    fed = set().union(*(RECORDED[stem]['parity']['bound_nonempty'] for stem in stems))
    unfed = ({*model.parameters, *model.lookups} - fed) - {
        name for name in model.parameters if name in model.dimensions
    }
    assert not unfed, f'no reference network feeds these: {sorted(unfed)}'


def test_the_spine_weightings_are_generic():
    """At weighting 1.0 a missing hours factor builds the identical matrix and passes every gate."""
    header, *rows = (REFERENCES / 'data' / 'base' / 'snapshots.csv').read_text().strip().splitlines()
    columns = list(zip(*(line.split(',')[1:] for line in rows), strict=True))
    for name, values in zip(header.split(',')[1:], columns, strict=True):
        assert len(set(values)) > 1, f'{name} weightings are constant — a swapped or dropped factor cannot show'
        assert '1.0' not in values, f'{name} carries a 1.0 — the identity a missing factor hides behind'


@pytest.mark.parametrize('row', sorted(row for row in RECORDED_ROWS if row.startswith('GlobalConstraint-')), ids=str)
def test_a_global_constraint_row_has_a_block_of_its_recorded_type_and_sense(row: str):
    gc = GC_RECORDED[row.removeprefix('GlobalConstraint-')]
    matching = [
        name
        for m in MODELS
        for name, block in m.constraints.items()
        if _stands_for(name, block.description) == gc['type'] and f"'{gc['sense']}'" in (block.where or '')
    ]
    assert matching, f'no declared block takes a {gc["type"]} row of sense {gc["sense"]}'
