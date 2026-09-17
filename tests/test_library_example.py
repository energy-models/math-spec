# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The component library under `examples/library/`, held to what its pages claim.

The gallery test holds each page to its generator, so the math on a page cannot
drift from the file above it. What is left for here is what no page states: that
every fragment stands alone, that the composition is one model, and that the
variant patch — the one file in the library that is not a model — still applies
to what the fragments make.
"""

from __future__ import annotations

import pytest

from math_spec import LanguageError, merge, override, to_markdown, to_spec
from math_spec.typesetting import FORMATS, typeset
from tests.fixtures import EXAMPLES
from tools._page import without_header

LIBRARY = EXAMPLES / 'library'
FRAGMENTS = {name: LIBRARY / f'{name}.yaml' for name in ('surface', 'generator', 'load')}
PATCH = LIBRARY / 'variants' / 'commitment.yaml'
PAGE = EXAMPLES.parent / 'docs' / 'examples' / 'library' / 'index.md'


@pytest.mark.parametrize('name', sorted(FRAGMENTS))
def test_every_fragment_loads_and_prints_on_its_own(name):
    """The unit a library ships is the unit somebody reviews, so each one is a model."""
    assert to_markdown(to_spec(FRAGMENTS[name])), f'{name} rendered nothing'


@pytest.mark.parametrize('name', ['generator', 'load'])
def test_a_component_template_reads_the_surface_and_introduces_no_flow(name):
    spec = to_spec(FRAGMENTS[name])
    assert sorted(spec.given_variables) == ['flow']
    assert 'flow' not in spec.variables, 'the surface introduces the column, and a template only writes into it'


def test_the_library_composes_into_one_model():
    spec = to_spec(merge(FRAGMENTS))
    assert sorted(spec.variables) == ['flow', 'gen_p']
    assert sorted(spec.constraints) == ['balance', 'dem_withdraws', 'gen_injects']
    assert not spec.given_variables, 'each read is folded into the declaration that introduces it'
    assert spec.objective is not None and spec.objective.expression == 'sum(gen_p * gen_cost)', (
        "the one fragment that priced anything carries the composed model's objective, as it wrote it"
    )


def test_the_balance_is_written_once_however_many_templates_are_merged():
    one = to_spec(merge({'surface': FRAGMENTS['surface'], 'load': FRAGMENTS['load']}))
    both = to_spec(merge(FRAGMENTS))
    assert one.constraints['balance'].expression == both.constraints['balance'].expression


def test_the_variant_is_a_patch_rather_than_a_model():
    """Which is why `render_tex` skips `variants/`: nothing there loads on its own."""
    with pytest.raises(LanguageError):
        to_spec(PATCH)


def test_the_variant_patch_applies_to_the_composition():
    spec = to_spec(override(merge(FRAGMENTS), {'commitment': PATCH}))
    assert spec.variables['gen_on'].domain == 'binary'
    assert spec.variables['gen_p'].bounds.upper == float('inf'), 'the cap moves from the bound to a constraint'
    assert sorted(spec.constraints) == [
        'balance',
        'dem_withdraws',
        'gen_above_minimum',
        'gen_below_capacity',
        'gen_injects',
    ]


def _unescaped(printed: str) -> str:
    """The document with TeX's escaped underscore put back, so one assertion reads in all three formats."""
    return printed.replace(r'\_', '_')


@pytest.mark.parametrize('fmt', list(FORMATS), ids=list(FORMATS))
def test_the_patched_model_prints_the_variant_math(fmt):
    """A patch is read by the loader through the model it lands on, so what it declares prints like the rest."""
    printed = _unescaped(typeset(to_spec(override(merge(FRAGMENTS), {'commitment': PATCH})), fmt))
    missing = [
        name for name in ('gen_on', 'gen_p_min', 'gen_below_capacity', 'gen_above_minimum') if name not in printed
    ]
    assert not missing, f'the patch declares {missing}, and the typeset document does not name them'


def test_the_variant_needs_the_fragment_it_patches():
    """Picking commitment without the generator is a patch that lands on nothing, and it is refused at load."""
    without_generator = merge({name: FRAGMENTS[name] for name in ('surface', 'load')})
    with pytest.raises(LanguageError, match="edits the variable 'gen_p', which its base does not declare"):
        to_spec(override(without_generator, {'commitment': PATCH}))


def test_the_patch_the_page_shows_is_the_file_it_names():
    """A fenced patch is read by nothing, so the one on the page is compared to the file."""
    fenced = PAGE.read_text().split('```yaml title="variants/commitment.yaml"\n')[1].split('```')[0].strip()
    assert fenced == without_header(PATCH), 'the page shows the patch verbatim, its licence header aside'
