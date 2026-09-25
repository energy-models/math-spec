# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The component library under `examples/library/`, held to what its pages claim.

The gallery test holds each page to its generator, so the math on a page cannot
drift from the file above it. What is left for here is what no page states: that
every fragment stands alone, that the composition is one model, and that the
variant patch, the one file in the library that is not a model, applies to what
the fragments make.
"""

from __future__ import annotations

import pytest

from math_spec import LanguageError, merge, override, to_markdown, to_spec
from math_spec.typesetting import FORMATS, typeset
from tests.fixtures import EXAMPLES
from tools import gallery

LIBRARY = EXAMPLES / 'library'
FRAGMENTS = {name: LIBRARY / f'{name}.yaml' for name in ('surface', 'generator', 'load')}
PATCH = LIBRARY / 'variants' / 'commitment.yaml'
PATCHED = override(merge(FRAGMENTS), {'commitment': PATCH})


@pytest.mark.parametrize('name', sorted(FRAGMENTS))
def test_every_fragment_loads_and_prints_on_its_own(name):
    """The unit a library ships is the unit somebody reviews, so each one is a model."""
    assert to_markdown(to_spec(FRAGMENTS[name])), f'{name} rendered nothing'


@pytest.mark.parametrize('name', ['generator', 'load'])
def test_a_component_file_reads_the_surface_and_introduces_no_flow(name):
    spec = to_spec(FRAGMENTS[name])
    assert sorted(spec.given.variables) == ['Port_p'], 'the port flow is the one name a component file reads'
    assert 'Port_p' not in spec.variables, 'the surface introduces the flow, and a component file only reads it'


def test_the_library_composes_into_one_model():
    spec = merge(FRAGMENTS)
    assert sorted(spec.variables) == ['Generator_p', 'Port_p'], 'the composition declares each column once'
    assert sorted(spec.constraints) == ['Bus_nodal_balance', 'Generator_injection', 'Load_withdrawal'], (
        'the composition carries every row family of every fragment, and no other'
    )
    assert not spec.given, 'each read is folded into the declaration that introduces it'
    assert spec.objective is not None and spec.objective.expression == 'sum(Generator_p * Generator_marginal_cost)', (
        "the one fragment that priced anything carries the composed model's objective, as it wrote it"
    )


@pytest.mark.parametrize(
    'names',
    [
        pytest.param(('surface', 'load'), id='one component file'),
        pytest.param(('surface', 'generator', 'load'), id='the whole library'),
    ],
)
def test_the_balance_is_written_once_however_many_fragments_are_merged(names):
    merged = merge({name: FRAGMENTS[name] for name in names})
    surface = to_spec(FRAGMENTS['surface'])
    assert merged.constraints['Bus_nodal_balance'] == surface.constraints['Bus_nodal_balance'], (
        'a component file pins the flow at its own port, so merging leaves the balance as the surface wrote it'
    )


def test_the_variant_is_a_patch_rather_than_a_model():
    """Which is why `render_tex` skips `variants/`: nothing there loads on its own."""
    with pytest.raises(LanguageError):
        to_spec(PATCH)


def test_the_variant_patch_applies_to_the_composition():
    spec = to_spec(PATCHED)
    assert spec.variables['Generator_status'].domain == 'binary'
    assert spec.variables['Generator_p'].bounds.upper is None, 'the cap moves from the bound to a constraint'
    assert sorted(spec.constraints) == [
        'Bus_nodal_balance',
        'Generator_com_p_lower',
        'Generator_com_p_upper',
        'Generator_injection',
        'Load_withdrawal',
    ], 'the patch adds its two rows and removes none'


@pytest.mark.parametrize('fmt', list(FORMATS), ids=list(FORMATS))
def test_the_patched_model_prints_the_variant_math(fmt):
    """A patch is read by the loader through the model it lands on, so what it declares prints like the rest."""
    printed = typeset(to_spec(PATCHED), fmt).replace(r'\_', '_')
    declared = ('Generator_status', 'Generator_p_min_pu', 'Generator_com_p_upper', 'Generator_com_p_lower')
    missing = [name for name in declared if name not in printed]
    assert not missing, f'the patch declares {missing}, and the typeset document does not name them'


def test_the_variant_needs_the_fragment_it_patches():
    """Picking commitment without the generator is a patch that lands on nothing, and it is refused at load."""
    without_generator = merge({name: FRAGMENTS[name] for name in ('surface', 'load')})
    with pytest.raises(LanguageError, match="edits the variable 'Generator_p', which its base does not declare"):
        override(without_generator, {'commitment': PATCH})


def test_every_variant_in_the_library_is_typeset_on_the_composed_page():
    """A patch prints only as the model it lands on, so one with no tab is a patch nothing prints."""
    page = (gallery.PAGES / 'library' / 'composed.md').read_text()
    missing = [path.name for path in (LIBRARY / 'variants').glob('*.yaml') if f'=== "With {path.stem}"' not in page]
    assert not missing, f'the composed page gives {missing} no tab, so what they print is on no page'
