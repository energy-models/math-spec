# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The export surface, pinned — because a consumer depends on it by name.

`math_spec.__all__` is what another repository is allowed to import, so an
addition to it is a decision, and the table below is where it is recorded.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import math_spec
from math_spec import program, typesetting

#: Every name `math_spec` promises. Grouped as a reader meets them, not
#: alphabetically: the alphabetical form is `__all__` itself, and repeating it
#: here would make the two one list checked against itself.
SURFACE = frozenset(
    {
        # the two public states, and the conversion to each
        'Spec', 'to_spec', 'program', 'to_program',
        # the error tree
        'MathSpecError', 'LanguageError', 'SchemaError', 'DimensionError',
        'PiecewiseExpansionError', 'did_you_mean', 'schema_error',
        # the verdicts a consumer asks for rather than re-deriving
        'advice', 'Advice',
        # the closed operator set, and the wording of its refusals
        'BUILTIN_NAMES', 'EDGE_WRAP', 'call_shape_error', 'edge_error',
        'unknown_operator_message',
        # the declaration vocabularies a consumer pins its own tables against
        'DIMENSION_DTYPES', 'PARAMETER_DTYPES', 'VARIABLE_DOMAINS', 'VARIABLE_ABSENCE', 'ADVICE_KINDS',
        'CURVATURES', 'SosBlock',
        # typesetting
        'FORMATS', 'SymbolTable', 'typeset', 'to_latex', 'to_typst', 'to_markdown',
    }
)  # fmt: skip

#: The modules whose `__all__` a consumer imports from.
MODULES = [
    pytest.param(math_spec, id='math_spec'),
    pytest.param(typesetting, id='typesetting'),
    pytest.param(program, id='program'),
]


def test_all_matches_the_pinned_surface():
    """Both directions, because either alone rots."""
    declared = set(math_spec.__all__)
    assert declared == SURFACE, (
        f'only in __all__: {sorted(declared - SURFACE)}; only in SURFACE: {sorted(SURFACE - declared)}'
    )


@pytest.mark.parametrize('module', MODULES)
def test_every_exported_name_is_bound(module):
    """`__all__` naming something the module does not bind is a broken import."""
    missing = sorted(n for n in module.__all__ if not hasattr(module, n))
    assert not missing, f'{module.__name__}.__all__ names unbound attributes: {missing}'


@pytest.mark.parametrize('module', MODULES)
def test_all_names_nothing_twice(module):
    names = list(module.__all__)
    assert len(names) == len(set(names)), f'duplicate name in {module.__name__}.__all__'


def _defined_by(module: object) -> set[str]:
    """Every public name *module* binds itself, the bare ``Literal`` aliases included.

    Read from the source rather than ``dir()``: an alias is a plain assignment
    with no ``__module__`` to tell it apart from an imported one, so a runtime
    walk cannot say which names the module owns and which it merely imported.
    """
    tree = ast.parse(Path(module.__file__).read_text())  # pyrefly: ignore[missing-attribute]
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return {n for n in names if not n.startswith('_')}


def test_the_program_module_exports_everything_it_defines():
    """`math_spec.__all__` exports the module, so this is the consumers' surface — both
    directions, so a public name added without a decision fails here."""
    declared = set(program.__all__)
    defined = _defined_by(program)
    assert declared == defined, (
        f'only in __all__: {sorted(declared - defined)}; defined but unexported: {sorted(defined - declared)}'
    )
