# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""What the loader must refuse to do to a file before anyone else sees it."""

from __future__ import annotations

import importlib

import pytest
import yaml

import math_spec._yaml as _yaml_module
from math_spec._yaml import read_yaml
from math_spec.errors import SchemaError
from math_spec.validation import to_spec
from tests.fixtures import raw_of

MODEL = """dimensions:
  snapshot: {dtype: int}
  generator: {dtype: str}
parameters:
  cost: {dims: [generator]}
variables:
  p:
    foreach: [snapshot, generator]
    where: "cost > 0"
    bounds: {lower: 0, upper: 100}
constraints:
  balance:
    foreach: [snapshot]
    expression: sum(p, over=generator) == 5
objective:
  expression: sum(p * cost)
"""


def _write(tmp_path, text, name='m.yaml'):
    path = tmp_path / name
    path.write_text(text)
    return path


_BOOLISH = ['no', 'se', 'on', 'off', 'yes', 'n', 'y']
_BOOLISH_DIMS = 'dimensions:\n' + ''.join(f'  {name}: {{dtype: str}}\n' for name in _BOOLISH)


def test_only_true_and_false_are_booleans(tmp_path):
    """YAML 1.1 resolved these to bools, so the declaration the file names is not the one that reaches the schema — ``no`` is Norway."""
    path = _write(tmp_path, _BOOLISH_DIMS)

    assert list(read_yaml(path)['dimensions']) == _BOOLISH, 'every boolish word is a str key, in file order'


def test_the_harness_reads_a_model_the_way_the_product_does(tmp_path):
    """``raw_of`` read YAML 1.1, so a dimension named ``no`` reached a test's schema as ``False`` while ``to_spec`` saw the string."""
    path = _write(tmp_path, _BOOLISH_DIMS)

    assert raw_of(path) == read_yaml(path), 'a path is read by the same loader the product uses'
    assert list(raw_of(_BOOLISH_DIMS)['dimensions']) == _BOOLISH, 'and so is a YAML string'


def test_real_booleans_still_parse(tmp_path):
    """The narrowed resolver keeps 1.2's `true`/`false` as booleans, not labels."""
    path = _write(tmp_path, 'flags:\n  a: true\n  b: false\n')

    assert read_yaml(path)['flags'] == {'a': True, 'b': False}, 'the two spellings YAML 1.2 keeps are still bools'


def test_the_loader_yields_plain_types(tmp_path):
    """No loader wrapper may reach the schema or the AST."""
    raw = read_yaml(_write(tmp_path, MODEL))
    assert type(raw) is dict

    schema = to_spec(raw)
    assert all(type(name) is str for name in schema.dimensions), 'a declaration is keyed by a plain str'
    assert type(schema.variables['p'].foreach) is list
    assert all(type(d) is str for d in schema.variables['p'].foreach)


def test_duplicate_key_is_an_error_naming_both_lines(tmp_path):
    """PyYAML keeps the last one, discarding a declaration the file contains."""
    path = _write(
        tmp_path, MODEL.replace('constraints:\n', 'constraints:\n  balance:\n    foreach: []\n    equations: []\n')
    )

    first = MODEL.splitlines().index('  balance:') + 1
    with pytest.raises(SchemaError, match=rf"duplicate key 'balance' .* first declared on line {first}"):
        to_spec(path)


def test_duplicate_top_level_section_is_an_error(tmp_path):
    path = _write(tmp_path, MODEL + 'parameters:\n  other: {dims: [snapshot]}\n')

    with pytest.raises(SchemaError, match="duplicate key 'parameters'"):
        to_spec(path)


def test_a_merge_key_override_is_not_a_duplicate(tmp_path):
    """`<<:` then a key of the same name is an override — the point of merging."""
    path = _write(
        tmp_path,
        'defaults: &d\n  foreach: [generator]\n'
        'dimensions:\n  generator: {dtype: str}\n'
        'variables:\n  p:\n    <<: *d\n    foreach: [generator]\n',
    )

    assert read_yaml(path)['variables']['p']['foreach'] == ['generator'], 'the explicit key wins over the merged one'


@pytest.mark.parametrize(
    'text', [pytest.param('- a\n- b\n', id='a-sequence'), pytest.param('just a string\n', id='a-scalar')]
)
def test_a_non_mapping_document_is_a_load_error(tmp_path, text):
    """Otherwise `Spec(**raw)` raises a bare TypeError about `**`."""
    with pytest.raises(SchemaError, match='must be a mapping of sections'):
        to_spec(_write(tmp_path, text))


def test_an_empty_file_is_an_empty_model(tmp_path):
    assert read_yaml(_write(tmp_path, '')) == {}, 'no document is an empty mapping rather than None'
    assert read_yaml(_write(tmp_path, '# only a comment\n')) == {}, 'and so is a document of comments alone'


def test_a_complex_key_is_refused_in_our_tree(tmp_path):
    """A `? [a, b]` key cannot name a declaration; the refusal is the loader's, not a TypeError."""
    path = _write(tmp_path, MODEL + 'expressions:\n  ? [a, b]\n  : p\n')
    with pytest.raises(SchemaError, match='a key must be a scalar'):
        to_spec(path)


def test_two_merge_keys_accumulate(tmp_path):
    """`<<:` twice in one mapping merges both — PyYAML's reading, and not a duplicate."""
    path = _write(
        tmp_path,
        'anchors:\n  a: &a {dtype: int}\n  b: &b {description: periods}\n'
        + MODEL.replace('snapshot: {dtype: int}', 'snapshot:\n    <<: *a\n    <<: *b'),
    )
    with pytest.raises(SchemaError, match="unknown key 'anchors'"):
        to_spec(path)


#: One document per rule this module owns, plus the two 1.1 coercions it keeps
#: on purpose — what the two scanners have to agree about.
_EVERY_RULE = (
    _BOOLISH_DIMS
    + 'flags: {a: true, b: false}\n'
    + 'kept: {stamp: 2024-01-01, sexagesimal: 12:30}\n'
    + 'merged:\n  base: &b {dtype: int}\n  use:\n    <<: *b\n    dtype: str\n'
    + 'nested: [{a: 1}, [2, 3], null, 4.5, "quoted"]\n'
)


@pytest.mark.skipif(not hasattr(yaml, 'CSafeLoader'), reason='this PyYAML has no libyaml scanner to compare against')
def test_both_scanners_read_a_file_the_same_way(tmp_path, monkeypatch):
    """The loader takes libyaml's scanner where the install has one, and PyYAML's own otherwise — a difference no model may be able to see.

    Only the faster one runs in CI, so the fallback is reachable here only by
    hiding `CSafeLoader` and reloading the module. Both readings are compared
    against each other rather than against a written-out expectation, so this
    cannot drift from the rules the tests above pin.
    """
    path = _write(tmp_path, _EVERY_RULE)
    with_libyaml = read_yaml(path)
    duplicate = _write(tmp_path, _EVERY_RULE + 'flags: {}\n', name='dup.yaml')
    with pytest.raises(SchemaError) as fast:
        read_yaml(duplicate)

    monkeypatch.delattr(yaml, 'CSafeLoader')
    try:
        importlib.reload(_yaml_module)
        assert _yaml_module._StrictLoader.__mro__[1] is yaml.SafeLoader, 'the fallback base is what this test came for'
        assert _yaml_module.read_yaml(path) == with_libyaml, 'the same document, scalar for scalar'
        with pytest.raises(SchemaError) as slow:
            _yaml_module.read_yaml(duplicate)
        assert str(slow.value) == str(fast.value), 'and the same line for a duplicate key, since both carry marks'
    finally:
        monkeypatch.undo()
        importlib.reload(_yaml_module)

    assert _yaml_module._StrictLoader.__mro__[1] is yaml.CSafeLoader, 'the module is left as the suite found it'
