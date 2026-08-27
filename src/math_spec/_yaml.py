# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""How this project reads a YAML file.

`yaml.safe_load` implements YAML 1.1, and two of its rules are actively wrong
for a language whose scalars are user data. The loader is the only layer that
can see them, so both are fixed here:

- **1.2 booleans.** ``on``/``off``/``yes``/``no``/``y``/``n`` are ordinary
  names in this language — a country code as a dimension, a mode as a lookup.
  YAML 1.1 resolves them to ``True``/``False``, so the declaration the file
  writes is not the one that reaches the schema. Only ``true``/``false`` are
  booleans here, which is the YAML 1.2 core schema.
- **Duplicate keys.** 1.1 lets the last one win silently, discarding a
  declaration the file plainly contains.

Two further 1.1 coercions survive on purpose — the implicit timestamp
(``2024-01-01`` → ``date``) and sexagesimal ints (``12:30`` → ``750``). Neither
reaches a coordinate, which is data and never written here; a literal on the
other side of a ``where`` comparison is where one would be read as a label, and
there it is checked against the declared ``dtype`` (``resolution.py``).
``dtype: datetime`` is implemented — a label needs only an order and equality,
and nothing does arithmetic on a coordinate — so the timestamp coercion is the
*useful* reading there, not a hazard to route around.

The output is plain ``dict``/``str``: no loader wrapper reaches the schema
or the AST.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from math_spec.errors import SchemaError

#: The YAML 1.2 core-schema boolean set — nothing else resolves to a bool.
_BOOL_1_2 = re.compile(r'^(?:true|True|TRUE|false|False|FALSE)$')


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader with 1.2 booleans. Duplicate keys are checked on the nodes."""


#: The resolver table is rebuilt, not edited in place: it is inherited from
#: ``SafeLoader``, and mutating it would reconfigure PyYAML for the whole process.
_StrictLoader.yaml_implicit_resolvers = {
    ch: [(tag, rx) for tag, rx in pairs if tag != 'tag:yaml.org,2002:bool']
    for ch, pairs in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_StrictLoader.add_implicit_resolver('tag:yaml.org,2002:bool', _BOOL_1_2, list('tTfF'))


#: PyYAML's tag for ``<<:``, the one key a mapping may carry more than once.
_MERGE = 'tag:yaml.org,2002:merge'


def _check_duplicate_keys(node: yaml.Node, origin: str) -> None:
    """Reject a mapping that declares the same key twice, or a key that is not a scalar.

    Checked on the node tree before construction, so a ``<<:`` merge key that
    a mapping overrides is not a duplicate — the override is the point — and
    two merge keys are two merges, which PyYAML accumulates.
    """
    if isinstance(node, yaml.MappingNode):
        seen: dict[Any, int] = {}
        for key_node, value_node in node.value:
            line = key_node.start_mark.line + 1
            if not isinstance(key_node, yaml.ScalarNode):
                msg = f'{origin}:{line}: a key must be a scalar — a name, not a list or a mapping.'
                raise SchemaError(msg)
            key = key_node.value
            if key_node.tag == _MERGE:
                _check_duplicate_keys(value_node, origin)
                continue
            if key in seen:
                msg = (
                    f'{origin}:{line}: duplicate key {key!r} — first declared on '
                    f'line {seen[key]}. YAML would silently keep the last one, '
                    f'discarding a declaration the file contains.'
                )
                raise SchemaError(msg)
            seen[key] = line
            _check_duplicate_keys(value_node, origin)
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            _check_duplicate_keys(item, origin)


def read_yaml(path: Path | str) -> dict[str, Any]:
    """Read *path* off disk and parse it, in YAML 1.2's reading of scalars."""
    return parse_yaml(Path(path).read_text(), str(path))


def parse_yaml(text: str, origin: str = '<string>') -> dict[str, Any]:
    """Parse YAML *text* as a mapping of sections.

    The half of :func:`read_yaml` that does not touch the filesystem, so a
    caller holding the text rather than the path — a test fixture, a doc block
    — resolves scalars the same way. ``yaml.safe_load`` is 1.1 and would read
    ``no`` as a boolean, which is the divergence this module exists to remove.

    Args:
        text: The YAML source.
        origin: What a load error calls this source — a file's path, or the default for text that never was one.
    """
    loader = _StrictLoader(text)
    try:
        node = loader.get_single_node()
        if node is None:
            return {}
        _check_duplicate_keys(node, origin)
        data = loader.construct_document(node)
    finally:
        loader.dispose()
    if not data:
        return {}
    if not isinstance(data, dict):
        msg = f'{origin}: a model file must be a mapping of sections (dimensions:, variables:, …), got {type(data).__name__}.'
        raise SchemaError(msg)
    return data
