# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""`examples/pypsa/` is `examples/pypsa.yaml` cut into topic fragments, and `merge` gives the same model back.

Each fragment reads what another topic declares under `given:`. A sum every
component adds to (the bus balance, the operating cost, the global
constraints) is marked `additive: true` on one fragment's `given:` entry, and
each component declares its term as an ordinary named expression. So a
component is a family of files, and leaving the family out leaves a whole
model.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mathspec import FORMATS, LanguageError, merge, to_spec, typeset
from mathspec.canonical import canonical_yaml
from tools.pypsa_split import SUM_HOME, Model, fragments, same_rows

FOLDER = Path(__file__).resolve().parent.parent / 'examples' / 'pypsa'
PATHS = {path.stem: path for path in sorted(FOLDER.glob('*.yaml'))}


@pytest.fixture(scope='module')
def model() -> Model:
    return Model()


@pytest.mark.parametrize('name', sorted(PATHS))
def test_a_fragment_loads_on_its_own(name):
    assert to_spec(PATHS[name]).program


def test_the_fragments_merge_to_the_one_file_with_its_hubs_as_sums(model):
    merged = merge(PATHS, description=model.data['description'])
    assert canonical_yaml(merged) == canonical_yaml(to_spec(model.data))
    assert not merged.program.given, 'every name a fragment reads, another fragment declares'


def test_the_one_file_with_its_hubs_as_sums_states_the_rows_of_pypsa_yaml(model):
    assert same_rows(model.original, model.data) == [], 'each hub substituted back gives the rows the file wrote'


def test_the_fragments_are_what_the_splitter_writes(model):
    written = fragments(model)
    assert sorted(written) == sorted(PATHS), 'one file per topic, and no stale one'
    assert all(PATHS[name].read_text() == text for name, text in written.items())


#: What a model may leave out, as the fragment names or name prefixes it
#: drops. A component comes as a family; security reads the branches. A
#: reader that marks a sum no model goes without is not listed: leaving it
#: out collides, which the test below holds.
OPTIONAL = [
    'carrier',
    'cost',
    'global_constraints',
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
    assert not merge(kept).program.given, f'nothing that stays reads what {dropped} declares'


def test_every_sum_is_marked_in_one_fragment(model):
    marked = {
        name: sorted(
            stem for stem, path in PATHS.items() if (g := to_spec(path).given.expressions.get(name)) and g.additive
        )
        for name in model.sums
    }
    assert marked == {name: [SUM_HOME.get(name, 'core')] for name in model.sums}, (
        'the reader marks a sum no model goes without, and core marks the rest'
    )


@pytest.mark.parametrize(
    ('dropped', 'sum_name'),
    [
        pytest.param('network', 'Bus_injection', id='the-bus-balance'),
        pytest.param('power_flow', 'Cycle_angle_sum', id='kirchhoff-with-the-branches-kept'),
    ],
)
def test_leaving_out_a_reader_no_model_goes_without_is_refused(dropped, sum_name):
    """The reader marks the sum, so without it the components collide rather than merge silently."""
    kept = {name: path for name, path in PATHS.items() if name != dropped}
    with pytest.raises(LanguageError, match=rf"both declare the expression '{sum_name}'.*`additive: true`"):
        merge(kept)


@pytest.mark.parametrize('fmt', sorted(FORMATS))
def test_every_fragment_and_the_composition_print(fmt):
    assert all(typeset(path, fmt) for path in PATHS.values()), f'a fragment rendered nothing in {fmt}'
    assert typeset(merge(PATHS), fmt)
