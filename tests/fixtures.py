# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The schema the tests build from, and the helpers that vary it."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import TYPE_CHECKING, Any

from math_spec._yaml import parse_yaml, read_yaml
from math_spec.validation import load_model

if TYPE_CHECKING:
    from math_spec import Model

#: The operator probes: one construct per file, and the corpus that travels with
#: the language. `tools/spec_math.py` generates the operator reference
#: from the same directory, so a probe added for the page is swept here too.
OPERATOR_PROBES = sorted((Path(__file__).resolve().parent.parent / 'examples' / 'operators').glob('*.yaml'))

#: The dispatch model as a dict, for tests that need to mutate a declaration
#: rather than read a file. Deliberately the same math as
#: ``examples/dispatch.yaml`` so a reader who knows one knows the other; use
#: :func:`override` to vary it.
DISPATCH_MODEL: dict[str, Any] = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'generator': {'values': ['wind', 'gas']}},
    'parameters': {
        'p_max': {'dims': ['generator']},
        'cost': {'dims': ['generator']},
        'load': {'dims': ['snapshot']},
    },
    'variables': {'p': {'foreach': ['snapshot', 'generator'], 'bounds': {'lower': 0, 'upper': 'p_max'}}},
    'constraints': {'balance': {'foreach': ['snapshot'], 'expression': 'sum(p, over=generator) == load'}},
    'objective': {'sense': 'minimize', 'expression': 'sum(p * cost)'},
}


def override(base: dict[str, Any], **patch: Any) -> dict[str, Any]:
    """A deep copy of ``base`` with dotted paths replaced.

    ``override(DISPATCH_MODEL, **{'variables.p.where': 'p_max > 0'})``. Missing
    intermediate keys are created, so this both edits an existing declaration
    and adds a new one — which is what makes a whole family of "the base model
    but for one thing" tests a one-liner each.
    """
    raw = copy.deepcopy(base)
    for dotted, value in patch.items():
        node = raw
        *parents, leaf = dotted.split('.')
        for key in parents:
            node = node.setdefault(key, {})
        node[leaf] = value
    return raw


def schema_of(source: str | Path | dict[str, Any], **patch: Any) -> Model:
    """A ``Model`` from a YAML path, YAML text, or a raw dict.

    ``Path`` means a file, ``str`` means the YAML itself — the distinction is
    the type, never a guess about the content. ``**patch`` applies
    :func:`override` first, which is how a test says "this example, but with
    ``**`` in the objective".
    """
    raw = raw_of(source)
    return load_model(override(raw, **patch) if patch else raw)


def raw_of(source: str | Path | dict[str, Any]) -> dict[str, Any]:
    """The parsed mapping behind a path / YAML text / dict, unvalidated."""
    if isinstance(source, dict):
        return source
    return read_yaml(source) if isinstance(source, Path) else parse_yaml(source)
