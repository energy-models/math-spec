# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The checked-in JSON Schema for the YAML surface.

    pixi run python -m tools.schema   # rewrite schema/math-spec.schema.json

The document is ``Model.model_json_schema()`` — the shape pydantic validates,
nothing more: ``expression:`` and ``where:`` are strings to it, so their
grammars stay invisible to any editor reading this. ``tests/test_schema.py``
asserts the committed file equals what this produces, so the artefact cannot
drift from the models.
"""

from __future__ import annotations

import inspect
import json
import math
from pathlib import Path
from typing import Any

from math_spec import Model

PATH = Path(__file__).resolve().parent.parent / 'schema' / 'math-spec.schema.json'
DIALECT = 'https://json-schema.org/draft/2020-12/schema'


def _canonical(node: Any) -> Any:
    """One byte-stable form for what pydantic emits differently across versions.

    The drift test runs both against the locked dev pydantic and at the
    declared floor (the bare-install job resolves ``lowest-direct``), so the
    render must not depend on which generated it. Four rewrites:

    - non-finite ``default`` values are dropped — ``json.dumps`` would write
      the literal ``Infinity``, which JSON cannot spell and every non-Python
      validator refuses; ``default`` is advisory, so nothing is lost;
    - ``description`` is ``inspect.cleandoc``'d — newer pydantic dedents
      docstrings itself, older ships the raw indentation;
    - a one-element ``allOf`` holding a bare ``$ref`` collapses to the
      ``$ref`` — older pydantic wraps a ref that has siblings, 2020-12
      allows it unwrapped and newer pydantic writes it so;
    - ``additionalProperties: true`` is dropped — it is the dialect's default,
      which newer pydantic spells out on an open mapping and older leaves
      implicit. The ``false`` every strict block carries is kept.
    """
    if isinstance(node, list):
        return [_canonical(v) for v in node]
    if not isinstance(node, dict):
        return node
    out = {
        k: _canonical(v)
        for k, v in node.items()
        if not (isinstance(v, float) and math.isinf(v)) and (k, v) != ('additionalProperties', True)
    }
    if isinstance(out.get('description'), str):
        out['description'] = inspect.cleandoc(out['description'])
    wrapped = out.get('allOf')
    if isinstance(wrapped, list) and len(wrapped) == 1 and set(wrapped[0]) == {'$ref'}:
        del out['allOf']
        out['$ref'] = wrapped[0]['$ref']
    return out


def rendered() -> str:
    """The schema document, byte-for-byte as it lives in the repo."""
    document = _canonical({'$schema': DIALECT, **Model.model_json_schema()})
    return json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + '\n'


if __name__ == '__main__':
    PATH.write_text(rendered())
