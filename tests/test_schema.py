# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""The published JSON Schema is the pydantic models, verbatim.

`schema/mathspec.schema.json` is a generated artefact that ships in the
repository so an editor can offer completion without importing the package.
Nothing regenerates it on the way to a release, so the only thing keeping it
equal to the models is this file.
"""

import json
from typing import get_args

import pytest

from mathspec import spec
from tools import schema


def test_the_checked_in_json_schema_has_not_drifted():
    assert schema.PATH.read_text() == schema.rendered(), (
        'schema/mathspec.schema.json no longer matches the models — run `pixi run python -m tools.schema`'
    )


@pytest.mark.parametrize(
    ('definition', 'shorthand', 'spelling'),
    [
        pytest.param('PiecewiseLink', 'array', '`[expression, values, sign?]`', id='link-shorthand'),
        pytest.param('ExpressionBlock', 'string', 'bare-string', id='bare-string-expression'),
    ],
)
def test_the_json_schema_admits_the_shorthand_the_loader_admits(definition, shorthand, spelling):
    """A shorthand lives in a before-validator, which pydantic's generated schema
    cannot see — each needs its own schema hook in spec.py, and losing the hook
    loses the shorthand from every editor silently."""
    forms = json.loads(schema.PATH.read_text())['$defs'][definition].get('anyOf', [])
    assert any(form.get('type') == shorthand for form in forms), (
        f'the schema lost the {spelling} form of {definition} the loader accepts'
    )


def test_no_definition_refers_only_to_itself():
    """`handler()` inside a `__get_pydantic_json_schema__` override returns a `$ref` on some
    pydantic versions; wrapped, the entry loops on itself and the mapping form is unreachable.
    Rendered rather than read from the file, so it fails on whichever pydantic is installed."""
    doc = json.loads(schema.rendered())
    for name, entry in doc['$defs'].items():
        assert {'$ref': f'#/$defs/{name}'} not in entry.get('anyOf', []), (
            f'{name} refers to itself, so its mapping form is unreachable from the schema'
        )


@pytest.mark.parametrize(
    ('block', 'field', 'alias'),
    [
        pytest.param('ObjectiveBlock', 'sense', spec.ObjectiveSense, id='sense'),
        pytest.param('VariableBlock', 'domain', spec.VariableDomain, id='domain'),
        pytest.param('VariableBlock', 'absence', spec.VariableAbsence, id='absence'),
        pytest.param('ParameterBlock', 'dtype', spec.ParameterDtype, id='parameter-dtype'),
        pytest.param('DimensionBlock', 'dtype', spec.DimensionDtype, id='dimension-dtype'),
        pytest.param('PiecewiseBlock', 'method', spec.PiecewiseMethod, id='method'),
        pytest.param('SosBlock', 'type', spec.SosType, id='sos-type'),
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
    assert set(get_args(spec.PiecewiseMethod)) == set(spec.PIECEWISE_METHODS), (
        'the typed methods and the emitting ones disagree, so a method is accepted that emits nothing or the reverse'
    )
