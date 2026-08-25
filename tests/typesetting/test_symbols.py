# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The symbol table."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from math_spec.errors import SchemaError
from math_spec.typesetting import SymbolTable, to_latex, to_markdown, to_typst, typeset
from tests.fixtures import override
from tests.typesetting.fixtures import DISPATCH, EVERY_FORMAT, SYMBOLS, TYPST_SYMBOLS

if TYPE_CHECKING:
    from math_spec.typesetting.format import Format


WITH_MARGINAL_COST = override(
    DISPATCH,
    **{'parameters.marginal_cost': {'dims': ['generator']}, 'objective.expression': 'sum(p * marginal_cost)'},
)


def test_the_table_overrides_and_the_rest_is_still_derived():
    tex = to_latex(WITH_MARGINAL_COST, symbols=SYMBOLS, legend=False)
    assert r'\pi_{t,u}' in tex, 'both the symbol and its subscripts were overridden'
    assert r'c^{\mathrm{marg}}_{u}' in tex
    assert r'\mathrm{load}_{t}' in tex, 'untouched, so still derived'
    assert r'u \in \mathcal{U}' in tex


DESCRIBED = override(
    DISPATCH,
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
        assert text in out, f'{text!r} never reached the legend'
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
        to_latex(DISPATCH, symbols={'notation': 'latex', **symbols})


def test_a_table_prints_its_own_notation_verbatim():
    typ = to_typst(DISPATCH, symbols=TYPST_SYMBOLS)
    assert 'pi_(t,u)' in typ
    assert 'bar(p)_(u)' in typ
    assert 'u in cal(U)' in typ


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
        render(DISPATCH, symbols=symbols)


def test_notation_is_case_insensitive():
    assert to_latex(DISPATCH, symbols={'notation': 'LaTeX', 'names': {'p': r'\pi'}}) == to_latex(
        DISPATCH, symbols={'notation': 'latex', 'names': {'p': r'\pi'}}
    ), 'load lower-cases the notation, so casing never changes the render'


def test_an_empty_override_is_used_not_fallen_through():
    tex = to_latex(DISPATCH, symbols={'notation': 'latex', 'names': {'p_max': ''}})
    assert r'p^{\mathrm{max}}' not in tex, 'an entry in the table is used verbatim, even empty — never re-derived'


def test_a_model_renders_identically_with_an_empty_table():
    assert to_latex(DISPATCH) == to_latex(DISPATCH, symbols=SymbolTable('latex'))


def test_exported_from_the_package():
    assert to_latex is to_latex
    assert to_typst is to_typst
