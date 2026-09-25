# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""`examples/pypsa/` is `examples/pypsa.yaml` cut into topic fragments, and `merge` gives the same model back.

Each fragment reads what another topic declares under `given:`. A sum every
component adds to (the bus balance, the operating cost, the global
constraints) is one each component adds a term to: a named expression of its
own, such as `Generator_injection`, which the `term:` of its `given:` entry
names. One fragment reads each sum with its description. So a component is a
family of files, and leaving the family out leaves a whole model.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mathspec import FORMATS, LanguageError, merge, to_spec, typeset
from mathspec.canonical import canonical_yaml
from tools.pypsa_split import SOURCE, SUM_HOME, Model, fragments

FOLDER = Path(__file__).resolve().parent.parent / 'examples' / 'pypsa'
PATHS = {path.stem: path for path in sorted(FOLDER.glob('*.yaml'))}


@pytest.fixture(scope='module')
def model() -> Model:
    return Model()


@pytest.mark.parametrize('name', sorted(PATHS))
def test_a_fragment_loads_on_its_own(name):
    assert to_spec(PATHS[name]).program


def test_the_fragments_merge_to_the_one_file(model):
    merged = merge(PATHS, description=model.data['description'])
    assert canonical_yaml(merged) == canonical_yaml(to_spec(SOURCE))
    assert not merged.program.given, 'every name a fragment reads, another fragment declares'


def test_each_sum_is_its_terms_by_name_and_each_term_stays(model):
    merged = merge(PATHS)
    assert merged.expressions['Bus_injection'].expression == (
        'Generator_injection + Line_injection + Link_injection + Load_injection + Process_injection'
        ' + StorageUnit_injection + Store_injection + Transformer_injection'
    ), 'the terms in the order the fragment names sort in'
    assert set(model.terms) <= set(merged.expressions), 'every term is a named expression of the composed spec'


def test_the_fragments_are_what_the_splitter_writes(model):
    written = fragments(model)
    assert sorted(written) == sorted(PATHS), 'one file per topic, and no stale one'
    assert all(PATHS[name].read_text() == text for name, text in written.items())


#: What a model may leave out, as the fragment names or name prefixes it
#: drops. A component comes as a family; security reads the branches. A
#: reader of a sum no model goes without is not listed: leaving it
#: out leaves its terms nowhere to land, which the test below holds.
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


def test_every_sum_is_read_with_its_description_in_one_fragment(model):
    described = {
        name: sorted(
            stem for stem, path in PATHS.items() if (g := to_spec(path).given.expressions.get(name)) and g.description
        )
        for name in model.sums
    }
    assert described == {name: [SUM_HOME.get(name, 'settings')] for name in model.sums}, (
        'the reader of a sum no model goes without describes it, and settings describes the rest'
    )


@pytest.mark.parametrize(
    ('dropped', 'sum_name'),
    [
        pytest.param('network', 'Bus_injection', id='the-bus-balance'),
        pytest.param('power_flow', 'Cycle_angle_sum', id='kirchhoff-with-the-branches-kept'),
    ],
)
def test_leaving_out_a_reader_no_model_goes_without_is_refused(dropped, sum_name):
    """Only the reader has the sum, so without it the terms land on no name rather than define one."""
    kept = {name: path for name, path in PATHS.items() if name != dropped}
    with pytest.raises(LanguageError, match=rf"add a term to '{sum_name}', which no fragment defines, reads or uses"):
        merge(kept)


@pytest.mark.parametrize('fmt', sorted(FORMATS))
def test_every_fragment_and_the_composition_print(fmt):
    assert all(typeset(path, fmt) for path in PATHS.values()), f'a fragment rendered nothing in {fmt}'
    assert typeset(merge(PATHS), fmt)
