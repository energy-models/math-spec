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

#: One construct per file; `tools/spec_math.py` renders the operator reference
#: from the same directory, so a probe added for the page is swept here too.
OPERATOR_PROBES = sorted((Path(__file__).resolve().parent.parent / 'examples' / 'operators').glob('*.yaml'))

#: The same math as ``examples/dispatch.yaml``, as a dict a test can vary with
#: :func:`override`.
DISPATCH_MODEL: dict[str, Any] = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'generator': {'dtype': 'str'}},
    'parameters': {
        'p_max': {'dims': ['generator']},
        'cost': {'dims': ['generator']},
        'load': {'dims': ['snapshot']},
    },
    'variables': {'p': {'foreach': ['snapshot', 'generator'], 'bounds': {'lower': 0, 'upper': 'p_max'}}},
    'constraints': {'balance': {'foreach': ['snapshot'], 'expression': 'sum(p, over=generator) == load'}},
    'objective': {'sense': 'minimize', 'expression': 'sum(p * cost)'},
}

#: Two dimensions, a groupable and a label-space lookup, a numeric, a scalar and
#: a boolean parameter, a variable on each frame — one declaration of every kind
#: a rule can name, and no objective, so a test adds what it judges. `p` and `r`
#: share no dimension, which is what a rule about *different* dims needs.
SMALL_MODEL: dict[str, Any] = {
    'dimensions': {'g': {'dtype': 'str'}, 'h': {'dtype': 'str'}},
    'lookups': {'lk': {'over': 'g', 'into': 'h'}, 'tag': {'over': 'g', 'dtype': 'str'}},
    'parameters': {'c': {'dims': ['g']}, 'k': {'dims': []}, 'flag': {'dims': ['g'], 'dtype': 'bool'}},
    'variables': {'p': {'foreach': ['g']}, 'q': {'foreach': ['g', 'h']}, 'r': {'foreach': ['h']}},
}


def override(base: dict[str, Any], **patch: Any) -> dict[str, Any]:
    """A deep copy of ``base`` with dotted paths replaced, missing parents created.

    ``override(DISPATCH_MODEL, **{'variables.p.where': 'p_max > 0'})``.
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
    """A ``Model`` from a YAML path, YAML text, or a raw dict, ``**patch`` applied by :func:`override`.

    ``Path`` means a file, ``str`` means the YAML itself.
    """
    raw = raw_of(source)
    return load_model(override(raw, **patch) if patch else raw)


def raw_of(source: str | Path | dict[str, Any]) -> dict[str, Any]:
    """The parsed mapping behind a path / YAML text / dict, unvalidated."""
    if isinstance(source, dict):
        return source
    return read_yaml(source) if isinstance(source, Path) else parse_yaml(source)
