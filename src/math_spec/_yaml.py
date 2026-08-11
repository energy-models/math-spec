"""How this project reads a YAML file.

`yaml.safe_load` implements YAML 1.1, and two of its rules are actively wrong
for a language whose scalars are user data. The loader is the only layer that
can see them, so both are fixed here:

- **1.2 booleans.** ``on``/``off``/``yes``/``no``/``y``/``n`` are ordinary
  dimension labels — country codes, region names, tech names. YAML 1.1
  resolves them to ``True``/``False``, and the rows they keyed then vanish
  from the model without a word. Only ``true``/``false`` are booleans here,
  which is the YAML 1.2 core schema.
- **Duplicate keys.** 1.1 lets the last one win silently, discarding a
  declaration the file plainly contains.

Two further 1.1 coercions survive on purpose — the implicit timestamp
(``2024-01-01`` → ``date``) and sexagesimal ints (``12:30`` → ``750``). Both
are load errors where they are wrong rather than problems here: a coerced
coordinate is caught against its declared ``dtype`` (``validation.py``), and so
is a literal on the other side of a ``where`` comparison
(``resolution.py``). ``dtype: datetime`` is implemented — a label needs only an
order and equality, and nothing does arithmetic on a coordinate — so the
timestamp coercion is the *useful* reading here, not a hazard to route around.

The output is plain ``dict``/``str``: no loader wrapper reaches the schema,
the AST, the plan, or the engine.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from lpspec.errors import SchemaError

#: The YAML 1.2 core-schema boolean set — nothing else resolves to a bool.
_BOOL_1_2 = re.compile(r'^(?:true|True|TRUE|false|False|FALSE)$')


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader with 1.2 booleans. Duplicate keys are checked on the nodes."""


def _install_bool_resolver(loader: type[yaml.SafeLoader]) -> None:
    """Give *loader* the 1.2 boolean set in place of 1.1's.

    The table is rebuilt rather than edited: a subclass inherits
    ``yaml_implicit_resolvers`` from ``SafeLoader``, so mutating it in place
    would reconfigure PyYAML for the whole process.
    """
    loader.yaml_implicit_resolvers = {
        ch: [(tag, rx) for tag, rx in pairs if tag != 'tag:yaml.org,2002:bool']
        for ch, pairs in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }
    loader.add_implicit_resolver('tag:yaml.org,2002:bool', _BOOL_1_2, list('tTfF'))


_install_bool_resolver(_StrictLoader)


def _check_duplicate_keys(node: yaml.Node, where: str) -> None:
    """Reject a mapping that declares the same key twice.

    Checked on the node tree before construction, so a ``<<:`` merge key that
    a mapping overrides is not a duplicate — the override is the point.
    """
    if isinstance(node, yaml.MappingNode):
        seen: dict[Any, int] = {}
        for key_node, value_node in node.value:
            key = key_node.value
            line = key_node.start_mark.line + 1
            if key in seen:
                msg = (
                    f'{where}:{line}: duplicate key {key!r} — first declared on '
                    f'line {seen[key]}. YAML would silently keep the last one, '
                    f'discarding a declaration the file contains.'
                )
                raise SchemaError(msg)
            seen[key] = line
            _check_duplicate_keys(value_node, where)
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            _check_duplicate_keys(item, where)


def read_yaml(path: Path | str) -> dict[str, Any]:
    """Load *path* as a mapping of sections, in YAML 1.2's reading of scalars."""
    where = str(path)
    loader = _StrictLoader(Path(path).read_text())
    try:
        node = loader.get_single_node()
        if node is None:
            return {}
        _check_duplicate_keys(node, where)
        data = loader.construct_document(node)
    finally:
        loader.dispose()
    if data is None:
        return {}
    if not isinstance(data, dict):
        msg = f'{where}: a model file must be a mapping of sections (dimensions:, variables:, …), got {type(data).__name__}.'
        raise SchemaError(msg)
    return data
