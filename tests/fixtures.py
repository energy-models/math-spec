# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""What the language's own tests build a schema from, owned by this directory.

These used to live in `tests/conftest.py`, which imports `tools.constructs` and
so reaches `api`, `lowering` and `relational`. The fence in #1146 reads direct
`math_spec` imports and never saw that, so the directory was prefix-clean and would
not have started in a package of its own (#1150).

Nothing here reaches past the language. `tests/conftest.py` re-exports the four
names so the forty-odd tests on the other side of the cut are untouched; at the
cut it keeps its own copy of these thirty lines and this file becomes math-spec's
conftest. Two copies of a dict-patching helper is a cost worth paying to keep one
copy of every *rule*.
"""

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
