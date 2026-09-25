# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""`examples/pypsa/` is `examples/pypsa.yaml` cut into topic fragments, and `merge` gives the same model back.

Each fragment reads what another topic declares under `given:`, and adds its
terms to the sums every component contributes to (the bus balance, the
operating cost, the global constraints) as an additive expression. So a
component is a family of files, and leaving the family out leaves a whole
model.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mathspec import FORMATS, merge, to_spec, typeset
from mathspec.canonical import canonical_yaml
from tools.pypsa_split import Model, fragments, same_rows

FOLDER = Path(__file__).resolve().parent.parent / 'examples' / 'pypsa'
PATHS = {path.stem: path for path in sorted(FOLDER.glob('*.yaml'))}


@pytest.fixture(scope='module')
def model() -> Model:
    return Model()


@pytest.mark.parametrize('name', sorted(PATHS))
def test_a_fragment_loads_on_its_own(name):
    assert to_spec(PATHS[name]).program


def test_the_fragments_merge_to_the_one_file_with_its_hubs_additive(model):
    merged = merge(PATHS, description=model.data['description'])
    assert canonical_yaml(merged) == canonical_yaml(to_spec(model.data))
    assert not merged.given, 'every name a fragment reads, another fragment declares'


def test_the_one_file_with_its_hubs_additive_states_the_rows_of_pypsa_yaml(model):
    assert same_rows(model.original, model.data) == [], 'each hub substituted back gives the rows the file wrote'


def test_the_fragments_are_what_the_splitter_writes(model):
    written = fragments(model)
    assert sorted(written) == sorted(PATHS), 'one file per topic, and no stale one'
    assert all(PATHS[name].read_text() == text for name, text in written.items())


#: What a model may leave out, as the fragment names or name prefixes it
#: drops. A component comes as a family; security reads the branches.
OPTIONAL = [
    'carrier',
    'cost',
    'global_constraints',
    'network',
    'power_flow',
    'security',
    'load',
    'storage_unit',
    'store',
    'generator',
    'link',
    'process',
    'generator_ramping',
    'link_ramping',
    'process_ramping',
    'line security',
    'transformer security',
    'line transformer security power_flow',
]


def _family(name: str, dropped: list[str]) -> bool:
    return any(name == d or (name.startswith(f'{d}_') and d in ('generator', 'link', 'process')) for d in dropped)


@pytest.mark.parametrize('dropped', OPTIONAL, ids=[d.replace(' ', '+') for d in OPTIONAL])
def test_leaving_a_topic_out_leaves_a_whole_model(dropped):
    kept = {name: path for name, path in PATHS.items() if not _family(name, dropped.split())}
    assert len(kept) < len(PATHS), f'{dropped} names a fragment'
    assert not merge(kept).given, f'nothing that stays reads what {dropped} declares'


@pytest.mark.parametrize('fmt', sorted(FORMATS))
def test_every_fragment_and_the_composition_print(fmt):
    assert all(typeset(path, fmt) for path in PATHS.values()), f'a fragment rendered nothing in {fmt}'
    assert typeset(merge(PATHS), fmt)
