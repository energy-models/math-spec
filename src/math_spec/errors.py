# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""What the language says back about a file: the errors it raises, and the advice it gives."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, get_args

if TYPE_CHECKING:
    from collections.abc import Iterable

    from pydantic import ValidationError


#: Which pass an :class:`Advice` comes from. Closed, like the operator set: a
#: consumer filtering on it can enumerate every value.
AdviceKind = Literal['never-an-axis', 'unbounded']
ADVICE_KINDS = frozenset(get_args(AdviceKind))


@dataclass(frozen=True)
class Advice:
    """One thing the language advises about a file it accepts.

    Never an error: each is what a half-written model looks like too. A
    consumer prints it, or filters on ``kind`` and ``subject``; the text is the
    language's, so no consumer writes its own.

    Attributes:
        kind: The pass that said it.
        subject: The declaration it is about — a dimension name, a variable name.
        text: The sentence, naming the rewrite.
    """

    kind: AdviceKind
    subject: str
    text: str

    def __str__(self) -> str:
        return self.text


class MathSpecError(ValueError):
    """Base class for every error this package raises on purpose."""


class LanguageError(MathSpecError):
    """The model is not sayable in the language, or does not obey its rules."""


class SchemaError(LanguageError):
    """What a load refuses: an unknown key, a bad ``dtype``, a duplicate YAML key, an unparseable or unresolvable expression."""


class DimensionError(LanguageError):
    """A dim-set rule was violated. Raised at load time, before any data."""


class PiecewiseExpansionError(LanguageError):
    """A piecewise block references something that doesn't exist or collides."""


def did_you_mean(name: str, known: Iterable[str], *, label: str = 'Declared') -> str:
    """The repair clause for an unrecognised name: the near miss, or the set."""
    candidates = sorted(known)
    near = difflib.get_close_matches(name, candidates, n=1, cutoff=0.6)
    if near:
        return f"Did you mean '{near[0]}'?"
    return f'{label}: {", ".join(candidates) or "nothing"}.'


def schema_error(exc: ValidationError) -> LanguageError:
    """A pydantic ``ValidationError`` as one of ours.

    Returns the original :class:`LanguageError` subclass where exactly one
    error carries one, and a :class:`SchemaError` otherwise.
    """
    errors = exc.errors()
    lines = []
    for error in errors:
        message = error.get('msg', '').removeprefix('Value error, ')
        where = '.'.join(str(part) for part in error.get('loc', ()))
        lines.append(f'{where}: {message}' if where else message)
    text = '\n'.join(lines) or str(exc)

    if len(errors) == 1:
        original = errors[0].get('ctx', {}).get('error')
        if isinstance(original, LanguageError):
            return type(original)(text)
    return SchemaError(text)
