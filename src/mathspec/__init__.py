# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""The language: what a YAML file may say, and what it means.

Two public states — a [`Spec`][] is what the file *says*,
and its [`program`][mathspec.spec.Spec.program] is what it *means* — and
[`to_spec`][], the one door to both. Everything between them — both grammars
and the tree they build — is package-private, because a consumer reads a
program instead.
"""

from mathspec import program
from mathspec.advising import advice
from mathspec.composition import merge, override
from mathspec.errors import Advice, AdviceKind, DimensionError, LanguageError, MathSpecError, SchemaError, did_you_mean
from mathspec.operators import BUILTIN_NAMES
from mathspec.spec import Spec
from mathspec.typesetting import (
    FORMATS,
    SymbolTable,
    to_latex,
    to_markdown,
    to_typst,
    typeset,
    typeset_declaration,
)
from mathspec.validation import to_spec

__all__ = [
    'BUILTIN_NAMES',
    'FORMATS',
    'Advice',
    'AdviceKind',
    'DimensionError',
    'LanguageError',
    'MathSpecError',
    'SchemaError',
    'Spec',
    'SymbolTable',
    'advice',
    'did_you_mean',
    'merge',
    'override',
    'program',
    'to_latex',
    'to_markdown',
    'to_spec',
    'to_typst',
    'typeset',
    'typeset_declaration',
]

import warnings as _warnings
from importlib import metadata as _metadata

try:
    __version__ = _metadata.version(__name__)
except _metadata.PackageNotFoundError as e:  # pragma: no cover
    _warnings.warn(f'Could not determine version of {__name__}\n{e!s}', stacklevel=2)
    __version__ = 'unknown'
