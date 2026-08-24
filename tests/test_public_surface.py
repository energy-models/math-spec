# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The export surface, pinned — because a consumer depends on it by name.

`math_spec.__all__` is what another repository is allowed to import. lpspec
holds its own modules to it (`test_the_language_is_imported_as_one_package`
there): a submodule path is a contract nobody agreed to, so `from math_spec
import Model` is the only spelling that fails loudly the day `Model` stops
being exported.

That makes an addition here a decision rather than an import, which is what
the table below is for. A name added to `__all__` and not to `SURFACE` fails,
and so does the reverse — either alone rots.
"""

from __future__ import annotations

import importlib

import math_spec

#: The typeset *package*, which `math_spec.typeset` is not: the re-exported
#: function shadows the attribute, so this resolves through `sys.modules` the
#: way every import statement does. Getting this wrong is the trap the last
#: test in this file pins.
_typeset_pkg = importlib.import_module('math_spec.typeset')

#: Every name `math_spec` promises. Grouped as a reader meets them, not
#: alphabetically: the alphabetical form is `__all__` itself, and repeating it
#: here would make the two one list checked against itself.
SURFACE = frozenset(
    {
        # the front door, and the two model types
        'load_model', 'Model', 'Buildable', 'expand_piecewise',
        # the error tree
        'MathSpecError', 'LanguageError', 'SchemaError', 'DimensionError',
        'PiecewiseExpansionError', 'did_you_mean', 'schema_error',
        # reading a file
        'read_yaml', 'parse_yaml',
        # the core AST — every node a consumer may meet
        'ExpressionNode', 'ArithmeticNode', 'ComparisonNode', 'NumberNode', 'NameNode',
        'NameListNode', 'VariableNode', 'ParameterNode', 'DimensionNode', 'LookupNode',
        'EdgeNode', 'KeywordNode', 'UnaryOperatorNode', 'BinaryOperatorNode',
        'FunctionCallNode', 'children',
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
        'Namespace', 'expression_of', 'where_of', 'dims_of', 'check_binary',
        'carries_variable', 'is_quadratic', 'unbounded_notes', 'mask_of',
        # the closed operator set, and the wording of its refusals
        'BUILTIN_NAMES', 'EDGE_WRAP', 'call_shape_error', 'edge_error',
        'unknown_operator_message',
        # the declaration vocabularies a consumer pins its own tables against
        'DIMENSION_DTYPES', 'PARAMETER_DTYPES', 'VARIABLE_DOMAINS', 'VARIABLE_ABSENCE',
        'SosBlock',
        # typesetting
        'FORMATS', 'SymbolTable', 'typeset', 'to_latex', 'to_typst', 'to_markdown',
    }
)  # fmt: skip


def test_all_matches_the_pinned_surface():
    """Both directions, because either alone rots."""
    declared = set(math_spec.__all__)
    assert declared == SURFACE, (
        f'only in __all__: {sorted(declared - SURFACE)}; '
        f'only in SURFACE: {sorted(SURFACE - declared)} — a name reaches a consumer '
        f'through __all__, so adding one is a decision this table records'
    )


def test_every_exported_name_is_bound():
    """`__all__` naming something the package does not bind is a broken import."""
    missing = sorted(n for n in math_spec.__all__ if not hasattr(math_spec, n))
    assert not missing, f'__all__ names unbound attributes: {missing}'


def test_all_is_sorted_and_unique():
    names = list(math_spec.__all__)
    assert len(names) == len(set(names)), 'duplicate name in __all__'


def test_the_typeset_subpackage_binds_what_it_exports():
    missing = sorted(n for n in _typeset_pkg.__all__ if not hasattr(_typeset_pkg, n))
    assert not missing, f'math_spec.typeset.__all__ names unbound attributes: {missing}'


def test_the_typeset_function_shadows_its_package_without_breaking_imports():
    """`typeset` is a function here and a subpackage one level down.

    Binding the function on the package overwrites the submodule attribute, so
    this pins the forms that must survive it: every import spelling resolves
    through `sys.modules` and is unaffected, which is what lets `__all__` carry
    the name at all. Attribute access off the package is the one casualty and
    is asserted too, so the day someone unshadows it this test says what
    changed rather than a downstream `AttributeError` saying nothing.
    """
    from math_spec.typeset import Walk
    from math_spec.typeset.format import Format

    assert callable(math_spec.typeset)
    assert Walk is importlib.import_module('math_spec.typeset').Walk
    assert Format is importlib.import_module('math_spec.typeset.format').Format
    assert not hasattr(math_spec.typeset, 'to_latex')
