# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The language: what a YAML file may say, and what it means.

Everything from the bytes on disk to a fully typed, dim-checked core AST —
the file reader, the schema, the two grammars, expansion, resolution, the dim
rules, and the load-time pass that runs them all. The AST this package
produces is the narrow waist of docs/about/architecture.md: everything downstream
reads it, and nothing downstream is visible from here.

**The directory is the rule, in the direction the engine's is not.** Hard rule
2 says the engine never sees the schema or the AST; this is its mirror —
nothing under ``language/`` may import ``lowering``, ``sources``, ``api``, or
any of the three consuming subpackages. What a model *means* cannot depend on
what any consumer does with it, which is what makes ``lps.check()`` a pass with
no data and no plan, and a second consumer cheap.

**This module is the seam, and the names below are the whole of it.** A
consumer imports ``math_spec``; reaching a submodule is a lint failure,
because a submodule path is not a contract anyone agreed to and a name reached
that way cannot be counted. The count is the review surface: an addition here
widens what every consumer may depend on, and what a future package boundary
would have to keep stable, so it is a decision rather than an import.

Two consequences the fence does not state on its own. **A rule stated here is
stated once** — ``dims_of`` and ``check_binary`` are asked for a verdict, never
re-derived, so a consumer that reimplements one has broken the waist without
importing anything it should not. And **the error text for a language rule
belongs to the language**: ``call_shape_error`` and friends are exported so
that two consumers cannot word the same refusal differently.

**This package imports nothing outside itself**, and ``LANGUAGE_MAY_IMPORT``
is the empty set that says so. The errors it raises are its own
(``errors.py`` beside this file, re-exported from ``math_spec.errors`` so a caller
keeps saying ``lps.LanguageError``); the root of the hierarchy lives here too,
because a base class cannot sit downstream of the classes that extend it. What
that buys is not neatness: the directory can be lifted into a package of its
own without an edit, and a test says so rather than a plan.

``tests/test_architecture.py`` reads membership off the path, so a new
front-end module cannot land outside the fence by being spelled differently,
and checks every consumer's imports against ``__all__`` below.
"""

from math_spec._yaml import parse_yaml, read_yaml
from math_spec.boundedness import unbounded_notes
from math_spec.degree import carries_variable, check_binary, is_quadratic
from math_spec.dimensions import dims_of
from math_spec.errors import (
    DimensionError,
    LanguageError,
    MathSpecError,
    PiecewiseExpansionError,
    SchemaError,
    did_you_mean,
    schema_error,
)
from math_spec.expression_parser import (
    ArithmeticNode,
    BinaryOperatorNode,
    BranchNode,
    ComparisonNode,
    DimensionNode,
    EdgeNode,
    ExpressionNode,
    FunctionCallNode,
    KeywordNode,
    KwargNode,
    LeafNode,
    LookupNode,
    NameListNode,
    NameNode,
    NumberNode,
    ParameterNode,
    UnaryOperatorNode,
    UnresolvedNode,
    VariableNode,
    children,
)
from math_spec.model import (
    DIMENSION_DTYPES,
    PARAMETER_DTYPES,
    VARIABLE_ABSENCE,
    VARIABLE_DOMAINS,
    Buildable,
    Model,
    SosBlock,
)
from math_spec.operators import (
    BUILTIN_NAMES,
    EDGE_WRAP,
    call_shape_error,
    edge_error,
    unknown_operator_message,
)
from math_spec.piecewise import expand_piecewise, mask_of
from math_spec.resolution import Namespace, expression_of, where_of
from math_spec.validation import load_model
from math_spec.where_parser import (
    AndNode,
    BooleanLiteralNode,
    ConnectiveWhereNode,
    DimensionComparisonNode,
    DimensionPositionNode,
    LookupComparisonNode,
    LookupDefinedNode,
    LookupPairComparisonNode,
    NotNode,
    OrNode,
    ParameterComparisonNode,
    ParameterDefinedNode,
    TypedPredicateNode,
    UnresolvedComparisonNode,
    UnresolvedNameNode,
    UnresolvedPositionNode,
    UnresolvedWhereNode,
    VariableDefinedNode,
    WhereNode,
)

# Last, and deliberately out of alphabetical order. `math_spec.typesetting` imports
# `Namespace`, `expand_piecewise` and `load_model` back from this module, so
# those names have to be bound before it runs. Sorted into place with the rest
# it would sit above `validation`, and the import would fail on a partially
# initialised module. Upstream had no cycle to avoid: the root package and the
# language subpackage were two modules there, and flattening them into this one
# is what put both ends of the import in the same file.
# isort: split
from math_spec.typesetting import (
    FORMATS,
    SymbolTable,
    to_latex,
    to_markdown,
    to_typst,
    typeset,
)

__all__ = [
    'BUILTIN_NAMES',
    'DIMENSION_DTYPES',
    'EDGE_WRAP',
    'FORMATS',
    'PARAMETER_DTYPES',
    'VARIABLE_ABSENCE',
    'VARIABLE_DOMAINS',
    'AndNode',
    'ArithmeticNode',
    'BinaryOperatorNode',
    'BooleanLiteralNode',
    'BranchNode',
    'Buildable',
    'ComparisonNode',
    'ConnectiveWhereNode',
    'DimensionComparisonNode',
    'DimensionError',
    'DimensionNode',
    'DimensionPositionNode',
    'EdgeNode',
    'ExpressionNode',
    'FunctionCallNode',
    'KeywordNode',
    'KwargNode',
    'LanguageError',
    'LeafNode',
    'LookupComparisonNode',
    'LookupDefinedNode',
    'LookupNode',
    'LookupPairComparisonNode',
    'MathSpecError',
    'Model',
    'NameListNode',
    'NameNode',
    'Namespace',
    'NotNode',
    'NumberNode',
    'OrNode',
    'ParameterComparisonNode',
    'ParameterDefinedNode',
    'ParameterNode',
    'PiecewiseExpansionError',
    'SchemaError',
    'SosBlock',
    'SymbolTable',
    'TypedPredicateNode',
    'UnaryOperatorNode',
    'UnresolvedComparisonNode',
    'UnresolvedNameNode',
    'UnresolvedNode',
    'UnresolvedPositionNode',
    'UnresolvedWhereNode',
    'VariableDefinedNode',
    'VariableNode',
    'WhereNode',
    'call_shape_error',
    'carries_variable',
    'check_binary',
    'children',
    'did_you_mean',
    'dims_of',
    'edge_error',
    'expand_piecewise',
    'expression_of',
    'is_quadratic',
    'load_model',
    'mask_of',
    'parse_yaml',
    'read_yaml',
    'schema_error',
    'to_latex',
    'to_markdown',
    'to_typst',
    'typeset',
    'unbounded_notes',
    'unknown_operator_message',
    'where_of',
]

import warnings as _warnings
from importlib import metadata as _metadata

try:
    __version__ = _metadata.version(__name__)
except _metadata.PackageNotFoundError as e:  # pragma: no cover
    _warnings.warn(f'Could not determine version of {__name__}\n{e!s}', stacklevel=2)
    __version__ = 'unknown'
