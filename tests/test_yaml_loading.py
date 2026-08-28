# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""What the loader must refuse to do to a file before anyone else sees it."""

from __future__ import annotations

import pytest

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

    assert list(read_yaml(path)['dimensions']) == _BOOLISH


def test_the_harness_reads_a_model_the_way_the_product_does(tmp_path):
    """``raw_of`` read YAML 1.1, so a dimension named ``no`` reached a test's schema as ``False`` while ``to_spec`` saw the string."""
    path = _write(tmp_path, _BOOLISH_DIMS)

    assert raw_of(path) == read_yaml(path)
    assert list(raw_of(_BOOLISH_DIMS)['dimensions']) == _BOOLISH


def test_real_booleans_still_parse(tmp_path):
    """The narrowed resolver keeps 1.2's `true`/`false` as booleans, not labels."""
    path = _write(tmp_path, 'flags:\n  a: true\n  b: false\n')

    assert read_yaml(path)['flags'] == {'a': True, 'b': False}


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

    assert read_yaml(path)['variables']['p']['foreach'] == ['generator']


def test_a_non_mapping_document_is_a_load_error(tmp_path):
    """Otherwise `Spec(**raw)` raises a bare TypeError about `**`."""
    for text in ('- a\n- b\n', 'just a string\n'):
        path = _write(tmp_path, text)
        with pytest.raises(SchemaError, match='must be a mapping of sections'):
            to_spec(path)


def test_an_empty_file_is_an_empty_model(tmp_path):
    assert read_yaml(_write(tmp_path, '')) == {}
    assert read_yaml(_write(tmp_path, '# only a comment\n')) == {}


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
