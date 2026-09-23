# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""What the language says back about a file: the errors it raises, and the advice it gives."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Iterable

    from pydantic import ValidationError


#: Which pass an :class:`Advice` comes from. Closed, like the operator set: a
#: consumer filtering on it can enumerate every value.
AdviceKind = Literal['never-an-axis', 'unbounded']


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


class UnexpandedCurveError(LanguageError):
    """A program still carries a ``piecewise:`` block, and the consumer raising this builds rows.

    The one sentence for that refusal, so every consumer says it in the
    language's words: ``if program.piecewise: raise
    UnexpandedCurveError(program.piecewise)``. The language does not raise it
    at load — a model with a curve is a model like any other, printed and
    edited as written — because only a consumer building rows knows it wants
    the rows.
    """

    def __init__(self, blocks: Iterable[str]) -> None:
        self.blocks = tuple(blocks)
        named = ', '.join(f"'{block}'" for block in self.blocks)
        super().__init__(
            f'piecewise: {named} states rows rather than being one, and a program holds the rows. Pass '
            f"spec.expand('piecewise').program, which writes each block out as the variables and constraints "
            f'it states and keeps every sos: block for a consumer that takes a set — or spec.expand().program, '
            f'which writes the sets out as binaries and linking rows too.'
        )

    def __reduce__(self) -> tuple[type[UnexpandedCurveError], tuple[tuple[str, ...]]]:
        return type(self), (self.blocks,)


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


def prefixed(context: str, e: ValueError) -> str:
    """*e* under *context*, once — an expansion error already carries it."""
    return str(e) if str(e).startswith(context) else f'{context}: {e}'


def case_context(name: str, label: str | None) -> str:
    """The context an error inside one arm of a cased expression is reported under.

    Args:
        name: The named expression the arm belongs to.
        label: The case's name, or ``None`` for the block's ``otherwise:``.
    """
    where = 'otherwise' if label is None else f"case '{label}'"
    return f"Named expression '{name}', {where}"
