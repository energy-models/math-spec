# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""What the PyPSA references pin the model files to, without any engine.

This repository holds the corpus — the model files, the reference networks
as PyPSA scripts with the data inline, and `references.json`: what PyPSA
solved each of them to, checked by the `PyPSA references` workflow. Everything here asserts over those
committed files alone: names both directions between what PyPSA built and
what the files declare, a record per rung from the pinned pypsa, generic
spine weightings. What an engine makes of the rungs — one objective across
the fence, coverage, a model-for-model verdict — is that engine's own record
and its own tests (lpspec keeps both under `differential/pypsa/`). The page
blocks the records feed are held current by ``tests/test_docs.py`` through
``tools.gallery``.
"""

from __future__ import annotations

import importlib
import math
import re
import sys

import pytest

from math_spec import to_spec
from tools import gallery
from tools.gallery import DECLARED, RECORDED, REFERENCES, _stands_for

RUNGS = sorted(path.stem for path in REFERENCES.glob('rung_*.py'))
SCRIPT = REFERENCES / 'reference.py'
PAGE_TEXTS = [(gallery.PAGES / page).read_text() for page in DECLARED]

MODELS = [to_spec(path) for path in DECLARED.values()]
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


@pytest.mark.parametrize('key', ['spine', *RUNGS])
def test_every_reference_block_has_its_marker_pair_on_exactly_one_declared_page(key: str):
    carrying = sum(f'<!-- reference:{key}:begin -->' in text for text in PAGE_TEXTS)
    assert carrying == 1, (
        'a reference block shows on one declared page — the generator skips a page without the marker pair'
    )


@pytest.mark.parametrize('rung', RUNGS)
def test_every_rung_script_adds_to_the_spine(rung: str):
    text = (REFERENCES / f'{rung}.py').read_text()
    assert 'pypsa.Network()' in text or ('n = spine.build()' in text and 'n.add(' in text), (
        'a rung is the spine plus its own n.add calls, or a whole network of its own'
    )


@pytest.mark.parametrize('rung', RUNGS)
def test_no_rung_fetches_the_network_it_records(rung: str):
    """`reference.py` reads the model under review off the script, which needs the data in it.

    `pypsa.examples.*` downloads a netCDF instead: the network becomes a binary
    nobody reading this repository can see, the recorded objective becomes an
    oracle for whatever that host last served, and the reference run fails when
    it does not answer — which it did, with a 500, on 2026-08-27.
    """
    text = (REFERENCES / f'{rung}.py').read_text()
    assert 'pypsa.examples' not in text, (
        'a rung states its network rather than downloading one — write out the n.add calls that build it'
    )


def test_every_rung_script_has_a_recorded_solve():
    assert set(RUNGS) == set(RECORDED), (
        'a rung folder without a record, or a record without a folder — run reference.py, or delete the orphan'
    )


@pytest.mark.parametrize('stem', sorted(RECORDED), ids=sorted(RECORDED))
def test_the_record_is_from_the_pinned_pypsa(stem: str):
    pinned = re.search(r'"pypsa==([^"]+)"', SCRIPT.read_text())
    assert pinned is not None, 'reference.py pins pypsa in its PEP 723 block'
    assert RECORDED[stem]['pypsa'] == pinned.group(1), (
        'the recorded solve is from another pypsa than the script pins — re-run it in the pinned environment'
    )


@pytest.mark.parametrize('stem', sorted(RECORDED), ids=sorted(RECORDED))
def test_the_recorded_solve_is_usable_as_an_oracle(stem: str):
    recorded = RECORDED[stem]
    assert math.isfinite(recorded['objective']), 'an oracle needs a finite objective'
    assert recorded['rows'], 'an oracle needs the row counts an engine would compare'


def test_pypsa_builds_no_variable_the_files_do_not_declare():
    unmatched = RECORDED_COLUMNS - COLUMNS_DECLARED - {'objective_constant'}
    assert not unmatched, f'pypsa builds these and the files declare nothing that stands for them: {sorted(unmatched)}'


def test_every_declared_variable_is_built_by_some_reference():
    unbuilt = COLUMNS_DECLARED - RECORDED_COLUMNS
    assert not unbuilt, f'no reference network builds these declared variables — extend a fixture: {sorted(unbuilt)}'


def _stated(name: str, row: str) -> bool:
    """A declared name carries `{k}` or `{s}` where PyPSA names a family of rows, one per segment or scenario."""
    return re.fullmatch(re.sub(r'\\\{[a-z]\\\}', '.+', re.escape(name)), row) is not None


BASE = to_spec(DECLARED['pypsa.md'])


@pytest.mark.parametrize('page', [page for page in DECLARED if page != 'pypsa.md'])
def test_a_file_of_its_own_shares_its_declarations_with_the_base(page: str):
    """A keyword file restates the base surface; a shared name keeps its PyPSA name and its dtype, or it has drifted."""
    own = to_spec(DECLARED[page])
    drifted = []
    for section in ('parameters', 'lookups', 'variables', 'constraints'):
        theirs, ours = getattr(BASE, section), getattr(own, section)
        for name in set(theirs) & set(ours):
            if (theirs[name].description or '').split(' — ')[0] != (ours[name].description or '').split(' — ')[0]:
                drifted.append(f'{section}.{name}: description')
            if section == 'parameters' and theirs[name].dtype != ours[name].dtype:
                drifted.append(f'{section}.{name}: dtype')
    assert not drifted, f'{page} drifted from pypsa.yaml on {sorted(drifted)}'


def test_pypsa_builds_no_row_the_files_do_not_declare():
    named = {row for row in RECORDED_ROWS if not row.startswith('GlobalConstraint-')}
    unmatched = {row for row in named if not any(_stated(name, row) for name in ROWS_DECLARED)}
    assert not unmatched, f'pypsa builds these and the files declare nothing that stands for them: {sorted(unmatched)}'


def test_every_declared_row_is_built_by_some_reference():
    unbuilt = {name for name in ROWS_DECLARED - GC_TYPES if not any(_stated(name, row) for row in RECORDED_ROWS)}
    assert not unbuilt, f'no reference network builds these declared rows — extend a fixture: {sorted(unbuilt)}'


def test_the_spine_weightings_are_generic():
    """At weighting 1.0 a missing hours factor builds the identical matrix and passes every gate."""
    sys.path.insert(0, str(REFERENCES))
    weightings = importlib.import_module('spine').WEIGHTINGS
    for name, values in weightings.items():
        assert len(set(values)) > 1, f'{name} weightings are constant — a swapped or dropped factor cannot show'
        assert 1.0 not in values, f'{name} carries a 1.0 — the identity a missing factor hides behind'


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
