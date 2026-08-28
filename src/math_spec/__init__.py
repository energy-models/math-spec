# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The language: what a YAML file may say, and what it means. ``__all__`` is the public surface, pinned by ``tests/test_public_surface.py``."""

from math_spec import program
from math_spec._yaml import parse_yaml, read_yaml
from math_spec.boundedness import unbounded_notes
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
)
from math_spec.lowering import advice, to_program
from math_spec.model import (
    CURVATURES,
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
from math_spec.piecewise import curvature_required, expand_piecewise, mask_of
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

# Last: `math_spec.typesetting` imports `Namespace`, `expand_piecewise` and
# `load_model` back from this module, so those must be bound first.
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
    'CURVATURES',
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
    'advice',
    'call_shape_error',
    'curvature_required',
    'did_you_mean',
    'dims_of',
    'edge_error',
    'expand_piecewise',
    'expression_of',
    'load_model',
    'mask_of',
    'parse_yaml',
    'program',
    'read_yaml',
    'schema_error',
    'to_latex',
    'to_markdown',
    'to_program',
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
