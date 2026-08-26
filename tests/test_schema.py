# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The published JSON Schema is the pydantic models, verbatim.

`schema/math-spec.schema.json` is a generated artefact that ships in the
repository so an editor can offer completion without importing the package.
Nothing regenerates it on the way to a release, so the only thing keeping it
equal to the models is this file. What a validation rule *means* is
`test_validation.py`'s business; this one is about the artefact.
"""

import json
from typing import get_args

import pytest

from math_spec import model
from tools import schema


def test_the_checked_in_json_schema_has_not_drifted():
    assert schema.PATH.read_text() == schema.rendered(), (
        'schema/math-spec.schema.json no longer matches the models — run `pixi run python -m tools.schema`'
    )


def test_the_json_schema_admits_what_the_loader_admits():
    """The two shorthands live in before-validators, which pydantic's generated
    schema cannot see — each needs its own schema hook in model.py, and losing a
    hook loses the shorthand from every editor silently."""
    doc = json.loads(schema.PATH.read_text())
    link = doc['$defs']['PiecewiseLink']
    assert any(form.get('type') == 'array' for form in link.get('anyOf', [])), (
        'the schema lost the `[expression, values, sign?]` link shorthand the loader accepts'
    )
    expression = doc['$defs']['ExpressionBlock']
    assert {'type': 'string'} in expression.get('anyOf', []), (
        'the schema lost the bare-string form a named expression is written in'
    )


def test_no_definition_refers_only_to_itself():
    """`handler()` inside a `__get_pydantic_json_schema__` override returns a `$ref` on some
    pydantic versions; wrapped, the entry loops on itself and the mapping form is unreachable.
    Rendered rather than read from the file, so it fails on whichever pydantic is installed."""
    doc = json.loads(schema.rendered())
    for name, entry in doc['$defs'].items():
        assert {'$ref': f'#/$defs/{name}'} not in entry.get('anyOf', []), name


@pytest.mark.parametrize(
    ('block', 'field', 'alias'),
    [
        pytest.param('ObjectiveBlock', 'sense', model.ObjectiveSense, id='sense'),
        pytest.param('VariableBlock', 'domain', model.VariableDomain, id='domain'),
        pytest.param('VariableBlock', 'absence', model.VariableAbsence, id='absence'),
        pytest.param('ParameterBlock', 'dtype', model.ParameterDtype, id='parameter-dtype'),
        pytest.param('DimensionBlock', 'dtype', model.DimensionDtype, id='dimension-dtype'),
        pytest.param('LookupBlock', 'dtype', model.DimensionDtype, id='lookup-dtype'),
        pytest.param('PiecewiseBlock', 'method', model.PiecewiseMethod, id='method'),
        pytest.param('SosBlock', 'type', model.SosType, id='sos-type'),
    ],
)
def test_a_closed_vocabulary_is_published_as_an_enum(block, field, alias):
    """Read off the `Literal` rather than restated, so widening one is a one-line change."""
    published = json.loads(schema.PATH.read_text())['$defs'][block]['properties'][field]
    enum = published.get('enum') or next(
        (branch['enum'] for branch in published.get('anyOf', []) if 'enum' in branch), None
    )
    assert enum == list(get_args(alias)), f'{block}.{field} stopped publishing its closed vocabulary'


def test_the_piecewise_method_vocabulary_has_one_home():
    """`PiecewiseMethod` types the field and `PIECEWISE_METHODS` says what each emits."""
    assert set(get_args(model.PiecewiseMethod)) == set(model.PIECEWISE_METHODS)
