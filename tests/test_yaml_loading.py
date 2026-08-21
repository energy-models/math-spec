# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""What the loader must refuse to do to a file before anyone else sees it."""

from __future__ import annotations

import pytest

from math_spec._yaml import read_yaml
from math_spec.validation import load_model
from tests.fixtures import raw_of

MODEL = """dimensions:
  snapshot: {dtype: int, values: [0, 1]}
  generator: {values: [wind, gas]}
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


def test_only_true_and_false_are_booleans(tmp_path):
    """YAML 1.1 resolved these to bools, so the rows they keyed silently vanished.

    ``no`` is Norway, ``on`` is Ontario, ``y``/``n`` are perfectly ordinary
    labels. Two 1.1 coercions deliberately survive — the implicit timestamp
    and sexagesimal ints — because both interact with the unimplemented
    ``dtype: datetime``. They belong to the dtype guard in #65.
    """
    path = _write(tmp_path, 'dimensions:\n  c: {dtype: str, values: [no, se, on, off, yes, n, y]}\n')

    assert read_yaml(path)['dimensions']['c']['values'] == ['no', 'se', 'on', 'off', 'yes', 'n', 'y']


def test_the_harness_reads_a_model_the_way_the_product_does(tmp_path):
    """``raw_of`` is the door every test walks through, and it was a different one.

    It read YAML 1.1, so a ``no`` label reached the schema as ``False`` while
    ``load_model`` saw the string — and a differential test on such a model
    compared two lanes that had loaded different files. The corpus has no
    ``no``/``yes``/``on``/``off`` label today, which is why nothing said so.
    """
    text = 'dimensions:\n  country: {dtype: str, values: [uk, de, no]}\n'
    path = _write(tmp_path, text)

    assert raw_of(path) == read_yaml(path), 'a path through the harness reads what the product reads'
    assert raw_of(text)['dimensions']['country']['values'] == ['uk', 'de', 'no'], (
        'and so does YAML text, which is the form most fixtures take'
    )


def test_real_booleans_still_parse(tmp_path):
    """The narrowed resolver keeps 1.2's `true`/`false` as booleans, not labels."""
    path = _write(tmp_path, 'flags:\n  a: true\n  b: false\n')

    assert read_yaml(path)['flags'] == {'a': True, 'b': False}


def test_the_loader_yields_plain_types(tmp_path):
    """No loader wrapper may reach the schema, the AST, the plan, or the engine."""
    raw = read_yaml(_write(tmp_path, MODEL))
    assert type(raw) is dict

    schema = load_model(raw)
    assert type(schema.dimensions['generator'].values) is list
    assert all(type(v) is str for v in schema.dimensions['generator'].values)
    assert type(schema.variables['p'].foreach) is list


def test_duplicate_key_is_an_error_naming_both_lines(tmp_path):
    """PyYAML keeps the last one, discarding a declaration the file contains."""
    path = _write(
        tmp_path, MODEL.replace('constraints:\n', 'constraints:\n  balance:\n    foreach: []\n    equations: []\n')
    )

    with pytest.raises(ValueError, match=r"duplicate key 'balance' .* first declared on line 12"):
        load_model(path)


def test_duplicate_top_level_section_is_an_error(tmp_path):
    path = _write(tmp_path, MODEL + 'parameters:\n  other: {dims: [snapshot]}\n')

    with pytest.raises(ValueError, match="duplicate key 'parameters'"):
        load_model(path)


def test_a_merge_key_override_is_not_a_duplicate(tmp_path):
    """`<<:` then a key of the same name is an override — the point of merging."""
    path = _write(
        tmp_path,
        'defaults: &d\n  foreach: [generator]\n'
        'dimensions:\n  generator: {values: [wind]}\n'
        'variables:\n  p:\n    <<: *d\n    foreach: [generator]\n',
    )

    assert read_yaml(path)['variables']['p']['foreach'] == ['generator']


def test_a_non_mapping_document_is_a_load_error(tmp_path):
    """Otherwise `Model(**raw)` raises a bare TypeError about `**`."""
    for text in ('- a\n- b\n', 'just a string\n'):
        path = _write(tmp_path, text)
        with pytest.raises(ValueError, match='must be a mapping of sections'):
            load_model(path)


def test_an_empty_file_is_an_empty_model(tmp_path):
    assert read_yaml(_write(tmp_path, '')) == {}
    assert read_yaml(_write(tmp_path, '# only a comment\n')) == {}
