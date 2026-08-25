# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The symbol table."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from math_spec.errors import SchemaError
from math_spec.typesetting import SymbolTable, to_latex, to_markdown, to_typst, typeset
from tests.fixtures import DISPATCH_MODEL, override
from tests.typesetting.fixtures import EVERY_FORMAT, TYPST_SYMBOLS

if TYPE_CHECKING:
    from math_spec.typesetting.format import Format


WITH_MARGINAL_COST = override(
    DISPATCH_MODEL,
    **{'parameters.marginal_cost': {'dims': ['generator']}, 'objective.expression': 'sum(p * marginal_cost)'},
)


@pytest.mark.parametrize(
    ('render', 'symbols', 'fragments'),
    [
        pytest.param(
            to_latex,
            {
                'notation': 'latex',
                'dimensions': {'generator': {'index': 'u', 'set': r'\mathcal{U}'}},
                'names': {'p': r'\pi', 'marginal_cost': r'c^{\mathrm{marg}}'},
            },
            (r'\pi_{t,u}', r'c^{\mathrm{marg}}_{u}', r'u \in \mathcal{U}', r'\mathrm{load}_{t}'),
            id='latex',
        ),
        pytest.param(
            to_typst,
            TYPST_SYMBOLS,
            ('pi_(t,u)', 'bar(p)_(u)', 'u in cal(U)', 'upright("load")_(t)'),
            id='typst',
        ),
    ],
)
def test_the_table_prints_verbatim_and_the_rest_is_still_derived(render, symbols, fragments):
    """A symbol the table supplies, with its subscripts, is printed as written;
    `load` is in no table, so it is still derived."""
    out = render(WITH_MARGINAL_COST, symbols=symbols, legend=False)
    for fragment in fragments:
        assert fragment in out


DESCRIBED = override(
    DISPATCH_MODEL,
    **{
        'dimensions.generator.description': 'dispatchable units',
        'parameters.p_max.description': 'installed capacity',
        'variables.p.description': 'output of a generator in a snapshot',
    },
)


@EVERY_FORMAT
def test_a_description_reaches_the_legend_without_hiding_the_name(fmt: Format):
    """The declaration's own `description:` is what the legend reads — no
    sidecar involved, so a model carries its prose wherever it goes."""
    out = typeset(DESCRIBED, fmt)
    for text in ('dispatchable units', 'installed capacity', 'output of a generator in a snapshot'):
        assert text in out
    assert 'generator' in out, 'the description sits beside the name, it does not replace it'


@pytest.mark.parametrize(
    ('symbols', 'match'),
    [
        pytest.param({'names': {'p_maxx': 'x'}}, "Did you mean 'p_max'", id='a-misspelled-name'),
        pytest.param(
            {'dimensions': {'generatr': {'index': 'g'}}},
            "Did you mean 'generator'",
            id='a-misspelled-dimension',
        ),
        pytest.param({'symbols': {'p': 'x'}}, 'unknown section', id='an-unknown-section'),
        pytest.param(
            {'descriptions': {'p': 'the output'}},
            r"unknown section\(s\) \['descriptions'\]",
            id='a-table-still-carrying-descriptions',
        ),
        pytest.param({'dimensions': {'generator': {'letter': 'g'}}}, 'unknown key', id='an-unknown-key'),
    ],
)
def test_an_entry_naming_nothing_is_an_error_with_the_near_miss(symbols, match):
    """A silent typo means a symbol that never applies and a reader who never
    finds out — so it fails, and says what it probably meant."""
    with pytest.raises(SchemaError, match=match):
        to_latex(DISPATCH_MODEL, symbols={'notation': 'latex', **symbols})


@pytest.mark.parametrize(
    ('render', 'symbols', 'match'),
    [
        pytest.param(
            to_typst,
            {'notation': 'latex', 'names': {'p_max': r'\bar p'}},
            'written in latex, but this is a typst render',
            id='a-latex-table-into-typst',
        ),
        pytest.param(to_latex, TYPST_SYMBOLS, 'written in typst, but this is a latex render', id='typst-table-latex'),
        pytest.param(
            to_markdown, TYPST_SYMBOLS, 'written in typst, but this is a latex render', id='typst-table-markdown'
        ),
        pytest.param(to_latex, {'names': {'p': 'x'}}, "'notation:' is required", id='a-table-that-does-not-say'),
        pytest.param(
            to_latex,
            {'notation': 'latx', 'names': {'p': 'x'}},
            "unknown notation 'latx'. Valid notations",
            id='a-notation-outside-the-vocabulary',
        ),
    ],
)
def test_a_table_in_the_wrong_notation_refuses(render, symbols, match):
    """#321 was this failing silently — LaTeX passed into a Typst document,
    breaking three tools later; now it stops at the call, naming both notations."""
    with pytest.raises(SchemaError, match=match):
        render(DISPATCH_MODEL, symbols=symbols)


def test_notation_is_case_insensitive():
    assert to_latex(DISPATCH_MODEL, symbols={'notation': 'LaTeX', 'names': {'p': r'\pi'}}) == to_latex(
        DISPATCH_MODEL, symbols={'notation': 'latex', 'names': {'p': r'\pi'}}
    ), 'load lower-cases the notation, so casing never changes the render'


def test_an_empty_override_is_used_not_fallen_through():
    tex = to_latex(DISPATCH_MODEL, symbols={'notation': 'latex', 'names': {'p_max': ''}})
    assert r'p^{\mathrm{max}}' not in tex, 'an entry in the table is used verbatim, even empty — never re-derived'


def test_a_model_renders_identically_with_an_empty_table():
    assert to_latex(DISPATCH_MODEL) == to_latex(DISPATCH_MODEL, symbols=SymbolTable('latex'))
