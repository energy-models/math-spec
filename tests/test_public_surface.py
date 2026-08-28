# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The export surface, pinned — because a consumer depends on it by name.

`math_spec.__all__` is what another repository is allowed to import, so an
addition to it is a decision, and the table below is where it is recorded.
"""

from __future__ import annotations

import math_spec
from math_spec import typesetting

#: Every name `math_spec` promises. Grouped as a reader meets them, not
#: alphabetically: the alphabetical form is `__all__` itself, and repeating it
#: here would make the two one list checked against itself.
SURFACE = frozenset(
    {
        # the front door, and the two model types
        'load_model', 'Model', 'Buildable', 'expand_piecewise',
        # the second public state, and the door to it
        'to_program', 'program',
        # the error tree
        'MathSpecError', 'LanguageError', 'SchemaError', 'DimensionError',
        'PiecewiseExpansionError', 'did_you_mean', 'schema_error',
        # reading a file
        'read_yaml', 'parse_yaml',
        # the core AST — every node a consumer may meet
        'ExpressionNode', 'ArithmeticNode', 'ComparisonNode', 'NumberNode', 'NameNode',
        'NameListNode', 'VariableNode', 'ParameterNode', 'DimensionNode', 'LookupNode',
        'EdgeNode', 'KeywordNode', 'UnaryOperatorNode', 'BinaryOperatorNode',
        'FunctionCallNode',
        # the groups a pass asks about, rather than re-listing the classes in it
        'LeafNode', 'BranchNode', 'KwargNode', 'UnresolvedNode',
        'UnresolvedWhereNode', 'TypedPredicateNode', 'ConnectiveWhereNode',
        # the where AST
        'WhereNode', 'BooleanLiteralNode', 'AndNode', 'OrNode', 'NotNode',
        'ParameterComparisonNode', 'ParameterDefinedNode', 'VariableDefinedNode',
        'DimensionComparisonNode', 'DimensionPositionNode', 'LookupComparisonNode',
        'LookupPairComparisonNode', 'LookupDefinedNode', 'UnresolvedNameNode',
        'UnresolvedComparisonNode', 'UnresolvedPositionNode',
        # the passes a consumer asks for a verdict rather than re-deriving
        'Namespace', 'expression_of', 'where_of', 'dims_of', 'unbounded_notes',
        'advice', 'mask_of', 'curvature_required',
        # the closed operator set, and the wording of its refusals
        'BUILTIN_NAMES', 'EDGE_WRAP', 'call_shape_error', 'edge_error',
        'unknown_operator_message',
        # the declaration vocabularies a consumer pins its own tables against
        'DIMENSION_DTYPES', 'PARAMETER_DTYPES', 'VARIABLE_DOMAINS', 'VARIABLE_ABSENCE',
        'CURVATURES', 'SosBlock',
        # typesetting
        'FORMATS', 'SymbolTable', 'typeset', 'to_latex', 'to_typst', 'to_markdown',
    }
)  # fmt: skip


def test_all_matches_the_pinned_surface():
    """Both directions, because either alone rots."""
    declared = set(math_spec.__all__)
    assert declared == SURFACE, (
        f'only in __all__: {sorted(declared - SURFACE)}; only in SURFACE: {sorted(SURFACE - declared)}'
    )


def test_every_exported_name_is_bound():
    """`__all__` naming something the package does not bind is a broken import."""
    missing = sorted(n for n in math_spec.__all__ if not hasattr(math_spec, n))
    assert not missing, f'__all__ names unbound attributes: {missing}'


def test_all_names_nothing_twice():
    names = list(math_spec.__all__)
    assert len(names) == len(set(names)), 'duplicate name in __all__'


def test_the_typeset_subpackage_binds_what_it_exports():
    missing = sorted(n for n in typesetting.__all__ if not hasattr(typesetting, n))
    assert not missing, f'math_spec.typesetting.__all__ names unbound attributes: {missing}'
