# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""How this project reads a YAML file.

`yaml.safe_load` implements YAML 1.1, and two of its rules are wrong for a
language whose scalars are user data; both are fixed here:

- **1.2 booleans.** ``on``/``off``/``yes``/``no``/``y``/``n`` are ordinary
  names in this language — a country code as a dimension, a mode as a lookup.
  YAML 1.1 resolves them to ``True``/``False``; only ``true``/``false`` are
  booleans here, which is the YAML 1.2 core schema.
- **Duplicate keys.** 1.1 lets the last one win silently, discarding a
  declaration the file plainly contains.

The output is plain ``dict``/``str``: no loader wrapper reaches the schema
or the AST.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from math_spec.errors import SchemaError

#: The YAML 1.2 core-schema boolean set — nothing else resolves to a bool.
_BOOL_1_2 = re.compile(r'^(?:true|True|TRUE|false|False|FALSE)$')


if TYPE_CHECKING:
    # Typed as SafeLoader: typeshed declares CSafeLoader unconditionally, and a PyYAML without libyaml lacks it.
    _BaseLoader = yaml.SafeLoader
else:
    # Same document either way: both drive the Python Resolver and SafeConstructor.
    _BaseLoader = getattr(yaml, 'CSafeLoader', yaml.SafeLoader)


class _StrictLoader(_BaseLoader):
    """SafeLoader with 1.2 booleans. Duplicate keys are checked on the nodes."""


# Rebuilt rather than edited: the table is inherited, and mutating it reconfigures PyYAML process-wide.
_StrictLoader.yaml_implicit_resolvers = {
    ch: [(tag, rx) for tag, rx in pairs if tag != 'tag:yaml.org,2002:bool']
    for ch, pairs in _BaseLoader.yaml_implicit_resolvers.items()
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
        pairs: list[tuple[yaml.Node, yaml.Node]] = node.value
        for key_node, value_node in pairs:
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
    return parse_yaml(Path(path).read_text(encoding='utf-8'), str(path))


def parse_yaml(text: str, origin: str = '<string>') -> dict[str, Any]:
    """Parse YAML *text* as a mapping of sections.

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
