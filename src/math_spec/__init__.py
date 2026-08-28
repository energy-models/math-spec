# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The language: what a YAML file may say, and what it means.

Two public states — a :class:`~math_spec.model.Spec` is what the file *says*,
a :class:`~math_spec.program.Program` is what it *means* — and a conversion to
each. The AST between them is this package's own: it is reachable by module
path for a renderer that needs it, and out of ``__all__`` because a consumer
reads a program instead. ``__all__`` is the public surface, pinned by
``tests/test_public_surface.py``.
"""

from math_spec import program
from math_spec.advice import advice
from math_spec.errors import (
    Advice,
    DimensionError,
    LanguageError,
    MathSpecError,
    PiecewiseExpansionError,
    SchemaError,
    did_you_mean,
    schema_error,
)
from math_spec.lowering import to_program
from math_spec.model import (
    CURVATURES,
    DIMENSION_DTYPES,
    PARAMETER_DTYPES,
    VARIABLE_ABSENCE,
    VARIABLE_DOMAINS,
    SosBlock,
    Spec,
)
from math_spec.operators import (
    BUILTIN_NAMES,
    EDGE_WRAP,
    call_shape_error,
    edge_error,
    unknown_operator_message,
)
from math_spec.piecewise import curvature_required, mask_of

# Last: `math_spec.typesetting` reaches back for the two conversions, so those
# must be bound before it is imported.
from math_spec.typesetting import (
    FORMATS,
    SymbolTable,
    to_latex,
    to_markdown,
    to_typst,
    typeset,
)
from math_spec.validation import to_spec

__all__ = [
    'BUILTIN_NAMES',
    'CURVATURES',
    'DIMENSION_DTYPES',
    'EDGE_WRAP',
    'FORMATS',
    'PARAMETER_DTYPES',
    'VARIABLE_ABSENCE',
    'VARIABLE_DOMAINS',
    'Advice',
    'DimensionError',
    'LanguageError',
    'MathSpecError',
    'PiecewiseExpansionError',
    'SchemaError',
    'SosBlock',
    'Spec',
    'SymbolTable',
    'advice',
    'call_shape_error',
    'curvature_required',
    'did_you_mean',
    'edge_error',
    'mask_of',
    'program',
    'schema_error',
    'to_latex',
    'to_markdown',
    'to_program',
    'to_spec',
    'to_typst',
    'typeset',
    'unknown_operator_message',
]

import warnings as _warnings
from importlib import metadata as _metadata

try:
    __version__ = _metadata.version(__name__)
except _metadata.PackageNotFoundError as e:  # pragma: no cover
    _warnings.warn(f'Could not determine version of {__name__}\n{e!s}', stacklevel=2)
    __version__ = 'unknown'
