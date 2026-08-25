# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The errors the language raises.

:class:`LanguageError` is the file saying something the language does not
accept — decidable at load time, with no data bound. :class:`MathSpecError`
is the root a consumer's own errors may derive from, so one ``except`` covers
the package.

``model.py``'s field validators raise plain ``ValueError``, since pydantic
collects those into its own ``ValidationError`` and a custom class does not
survive the trip; :func:`schema_error` turns one back at the API boundary.
"""

from __future__ import annotations

import difflib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable


class MathSpecError(ValueError):
    """Base class for every error this package raises on purpose."""


class LanguageError(MathSpecError):
    """The model is not sayable in the language, or does not obey its rules."""


class SchemaError(LanguageError):
    """**The declarations themselves are wrong**, before any expression is read.

    An unknown key, a bad ``dtype``, a duplicate YAML key, a
    version this reader does not know — as against a bare
    :class:`LanguageError`, which is sound declarations saying something the
    language rejects (an undeclared name, a dim rule, degree 2).
    """


class DimensionError(LanguageError):
    """A dim-set rule was violated. Raised at load time, before any data."""


class PiecewiseExpansionError(LanguageError):
    """A piecewise block references something that doesn't exist or collides."""


def did_you_mean(name: str, known: Iterable[str], *, label: str = 'Declared') -> str:
    """The repair clause for an unrecognised name: the near miss, or the set.

    Only the clause is shared — an unknown declaration, an unknown YAML key and
    an unknown symbol-table entry each frame it with a sentence of their own.
    """
    candidates = sorted(known)
    near = difflib.get_close_matches(name, candidates, n=1, cutoff=0.6)
    if near:
        return f"Did you mean '{near[0]}'?"
    return f'{label}: {", ".join(candidates) or "nothing"}.'


def schema_error(exc: Any) -> LanguageError:
    """A pydantic ``ValidationError`` as one of ours, keeping the class.

    Pydantic wraps whatever a validator raises, so our own class cannot reach
    the caller from inside the model — but the original survives under
    ``ctx['error']``, so a :class:`DimensionError` comes back one. Anything
    else, including several errors at once, is a :class:`SchemaError`.
    """
    errors = exc.errors()
    lines = []
    for error in errors:
        message = str(error.get('msg', '')).removeprefix('Value error, ')
        where = '.'.join(str(part) for part in error.get('loc', ()))
        lines.append(f'{where}: {message}' if where else message)
    text = '\n'.join(lines) or str(exc)

    if len(errors) == 1:
        original = errors[0].get('ctx', {}).get('error')
        if isinstance(original, LanguageError):
            return type(original)(text)
    return SchemaError(text)
