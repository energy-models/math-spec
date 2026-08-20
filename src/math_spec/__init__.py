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
consumer imports ``lpspec.language``; reaching a submodule is a lint failure,
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

``errors.py`` stays outside deliberately: it is the dependency-free leaf both
this package and the engine may import (``ENGINE_MAY_IMPORT``), and moving it
in would put the language's path on the engine's import list.

``tests/test_architecture.py`` reads membership off the path, so a new
front-end module cannot land outside the fence by being spelled differently,
and checks every consumer's imports against ``__all__`` below.
"""

from lpspec.language._yaml import read_yaml
from lpspec.language.boundedness import unbounded_notes
from lpspec.language.degree import carries_variable, check_binary
from lpspec.language.dimensions import dims_of
from lpspec.language.expression_parser import (
    ArithmeticNode,
    BinaryOperatorNode,
    ComparisonNode,
    DimensionNode,
    EdgeNode,
    ExpressionNode,
    FunctionCallNode,
    KeywordNode,
    LookupNode,
    NameListNode,
    NameNode,
    NumberNode,
    ParameterNode,
    UnaryOperatorNode,
    VariableNode,
    children,
)
from lpspec.language.model import Model, SosBlock
from lpspec.language.operators import (
    EDGE_WRAP,
    call_shape_error,
    edge_error,
    unknown_operator_message,
)
from lpspec.language.piecewise import expand_piecewise, mask_of
from lpspec.language.resolution import Namespace, expression_of, where_of
from lpspec.language.validation import load_model
from lpspec.language.where_parser import (
    AndNode,
    BooleanLiteralNode,
    DimensionComparisonNode,
    DimensionPositionNode,
    LookupComparisonNode,
    LookupDefinedNode,
    LookupPairComparisonNode,
    NotNode,
    OrNode,
    ParameterComparisonNode,
    ParameterDefinedNode,
    UnresolvedComparisonNode,
    UnresolvedNameNode,
    UnresolvedPositionNode,
    VariableDefinedNode,
    WhereNode,
)

__all__ = [
    'EDGE_WRAP',
    'AndNode',
    'ArithmeticNode',
    'BinaryOperatorNode',
    'BooleanLiteralNode',
    'ComparisonNode',
    'DimensionComparisonNode',
    'DimensionNode',
    'DimensionPositionNode',
    'EdgeNode',
    'ExpressionNode',
    'FunctionCallNode',
    'KeywordNode',
    'LookupComparisonNode',
    'LookupDefinedNode',
    'LookupNode',
    'LookupPairComparisonNode',
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
    'SosBlock',
    'UnaryOperatorNode',
    'UnresolvedComparisonNode',
    'UnresolvedNameNode',
    'UnresolvedPositionNode',
    'VariableDefinedNode',
    'VariableNode',
    'WhereNode',
    'call_shape_error',
    'carries_variable',
    'check_binary',
    'children',
    'dims_of',
    'edge_error',
    'expand_piecewise',
    'expression_of',
    'load_model',
    'mask_of',
    'read_yaml',
    'unbounded_notes',
    'unknown_operator_message',
    'where_of',
]
