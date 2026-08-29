# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The waist as a value another language can read.

A consumer written in Python imports :class:`~math_spec.program.Program` and is
done. A consumer written in anything else has, until now, had one way to reach
the same model: implement the language a second time — a second parser, a second
name resolution, a second dim algebra — which is the one thing hard rule 1
exists to forbid. Two implementations of name resolution is the failure the
whole design is built to prevent, and shipping the waist only as importable
Python quietly guarantees it.

So the program is written as JSON, and read back from it. Everything in a
program is already resolved, so the form carries no grammar, no expression
strings and nothing to parse: a reader dispatches on a tag and builds a node.

**Every node is tagged with its class name and nothing else is.** A dataclass or
named tuple becomes an object carrying ``$``; a mapping becomes an object
without one; a tuple becomes an array. That is the whole encoding, and it is
reflective rather than hand-written so a node added to the program is
serialisable the day it exists — ``tests/test_program_nodes.py`` already refuses
a node no file reaches, so the round trip covers every node by construction.

**Reading is closed.** A tag is looked up in a registry built from the two
modules that define nodes; nothing is imported, evaluated or constructed by
name from the document. An unknown tag is refused naming it, which is what lets
a reader of a newer document say so rather than guess.
"""

from __future__ import annotations

import dataclasses
import json
import math
from functools import cache
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from math_spec import program as _program
from math_spec import where_parser as _where
from math_spec.errors import LanguageError, did_you_mean
from math_spec.lowering import to_program

if TYPE_CHECKING:
    from pathlib import Path

    from math_spec.model import Spec

#: The wire format's own version, which moves when the *encoding* changes and
#: not when the language does. A document declaring one this release does not
#: know is refused by number, so a reader never guesses at a shape it was not
#: written for.
WIRE_VERSION = 0

#: The key a tagged object carries. Chosen because no declaration name can be
#: it: names are identifiers, so a mapping of declarations can never collide
#: with a node.
TAG = '$'

#: How a float JSON cannot hold is written. ``allow_nan=False`` is what makes
#: this necessary rather than optional — an unbounded variable's bound is
#: ``-inf``, so every program with a one-sided bound contains one, and a reader
#: in a language whose JSON is strict would otherwise meet ``-Infinity`` and
#: stop.
NOT_FINITE = {'inf': math.inf, '-inf': -math.inf, 'nan': math.nan}


@cache
def _registry() -> dict[str, type]:
    """Every class a document may name, by the name it is written under.

    Built by reflection over the two modules that define program nodes, so a
    node added to either is readable without an entry here — the alternative
    being a table that goes stale silently the first time somebody forgets it.
    Held, because the reflection is per-read and the answer is per-release.
    """
    found: dict[str, type] = {}
    for module in (_program, _where):
        for name in dir(module):
            value = getattr(module, name)
            if isinstance(value, type) and (dataclasses.is_dataclass(value) or _is_named_tuple(value)):
                found[name] = value
    return found


def _is_named_tuple(value: type) -> bool:
    """A named tuple, which is a tuple subclass carrying ``_fields``."""
    return issubclass(value, tuple) and hasattr(value, '_fields')


def to_json(model: str | Path | dict[str, Any] | Spec | _program.Program, *, indent: int | None = None) -> str:
    """A model as the JSON a consumer in any language reads.

    Args:
        model: Whatever every other verb takes — a YAML path, a mapping, a
            loaded :class:`~math_spec.model.Spec`, or a
            :class:`~math_spec.program.Program` already.
        indent: Passed to :func:`json.dumps`. ``None`` is the compact form;
            an integer is what a document meant to be read or diffed wants.

    Returns:
        Strict JSON — no ``Infinity``, no ``NaN``, nothing a conforming reader
        in another language refuses.

    Raises:
        LanguageError: The model is not one, named with its rewrite.
    """
    document = {'version': WIRE_VERSION, 'program': _encode(to_program(model))}
    return json.dumps(document, indent=indent, allow_nan=False)


def from_json(text: str) -> _program.Program:
    """The program a document holds.

    Nothing is imported or evaluated: a tag names a class in a closed registry
    or the document is refused.

    Args:
        text: What :func:`to_json` wrote.

    Returns:
        The same :class:`~math_spec.program.Program` that was written.

    Raises:
        LanguageError: The document is not one this release can read — a wire
            version it does not know, or a tag naming no node.
    """
    document = json.loads(text)
    if (version := document.get('version')) != WIRE_VERSION:
        raise LanguageError(
            f'this is a program document at wire version {version!r}, and this release reads '
            f'{WIRE_VERSION}. The wire version moves when the encoding changes, so a document '
            f'from a newer release is not one to guess at — read it with the release that wrote it.'
        )
    return _decode(document['program'])


def _encode(value: Any) -> Any:
    """One value as the JSON shape that reads back as it."""
    if isinstance(value, float) and not math.isfinite(value):
        return {TAG: 'float', 'value': 'nan' if math.isnan(value) else ('inf' if value > 0 else '-inf')}
    if isinstance(value, (str, int, bool, float)) or value is None:
        return value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        fields = {f.name: _encode(getattr(value, f.name)) for f in dataclasses.fields(value)}
        return {TAG: type(value).__name__, **fields}
    if isinstance(value, tuple) and hasattr(value, '_fields'):
        fields = {name: _encode(getattr(value, name)) for name in value._fields}
        return {TAG: type(value).__name__, **fields}
    if isinstance(value, (dict, MappingProxyType)):
        return {str(key): _encode(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_encode(item) for item in value]
    raise LanguageError(
        f'a program carried a {type(value).__name__}, which the wire format has no shape for. '
        f'Every value in a program is a node, a mapping, a tuple or a JSON scalar; a new kind '
        f'of value is a decision to make in math_spec.serialisation rather than one to encode here.'
    )


def _decode(value: Any) -> Any:
    """One JSON shape as the value it was written from."""
    if isinstance(value, list):
        return tuple(_decode(item) for item in value)
    if not isinstance(value, dict):
        return value
    if (tag := value.get(TAG)) is None:
        return {key: _decode(item) for key, item in value.items()}
    if tag == 'float':
        return NOT_FINITE[value['value']]
    if (found := _registry().get(tag)) is None:
        raise LanguageError(
            f"this document names a node '{tag}', which is not one this release has. "
            + did_you_mean(tag, sorted(_registry()))
        )
    fields = {key: _decode(item) for key, item in value.items() if key != TAG}
    return found(**fields)
