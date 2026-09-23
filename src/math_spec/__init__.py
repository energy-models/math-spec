# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The language: what a YAML file may say, and what it means.

Two public states — a :class:`~math_spec.model.Spec` is what the file *says*,
and its :attr:`~math_spec.model.Spec.program` is what it *means* — and
:func:`to_spec`, the one door to both. Everything between them — both grammars
and the tree they build — is package-private, because a consumer reads a
program instead.
"""

from math_spec import program
from math_spec.advice import advice
from math_spec.errors import Advice, DimensionError, LanguageError, MathSpecError, SchemaError, did_you_mean
from math_spec.model import Spec
from math_spec.typesetting import (
    FORMATS,
    SymbolTable,
    to_latex,
    to_markdown,
    to_typst,
    typeset,
    typeset_declaration,
)
from math_spec.validation import to_spec

__all__ = [
    'FORMATS',
    'Advice',
    'DimensionError',
    'LanguageError',
    'MathSpecError',
    'SchemaError',
    'Spec',
    'SymbolTable',
    'advice',
    'did_you_mean',
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
