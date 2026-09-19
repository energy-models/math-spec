# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The symbol table."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from math_spec.errors import SchemaError
from math_spec.typesetting import SymbolTable, to_latex, to_markdown, to_typst, typeset
from math_spec.validation import to_spec
from tests.fixtures import DISPATCH_MODEL, varied
from tests.typesetting.fixtures import EVERY_FORMAT, TYPST_SYMBOLS

if TYPE_CHECKING:
    from math_spec.model import Spec
    from math_spec.typesetting import FormatName
    from math_spec.typesetting.format import Format


WITH_MARGINAL_COST = varied(
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


DESCRIBED = varied(
    DISPATCH_MODEL,
    **{
        'dimensions.generator.description': 'dispatchable units',
        'parameters.p_max.description': 'installed capacity',
        'variables.p.description': 'output of a generator in a snapshot',
        'expressions.spend': {'expression': 'sum(p * cost, over=generator)', 'description': 'what a snapshot costs'},
        'objective.expression': 'sum(spend)',
    },
)


@EVERY_FORMAT
def test_a_description_reaches_the_legend_without_hiding_the_name(name: FormatName, fmt: Format):
    """The declaration's own `description:` is what the legend reads — no
    sidecar involved, so a model carries its prose wherever it goes."""
    out = typeset(DESCRIBED, name)
    for text in (
        'dispatchable units',
        'installed capacity',
        'output of a generator in a snapshot',
        'what a snapshot costs',
    ):
        assert text in out
    assert 'generator' in out, 'the description sits beside the name, it does not replace it'


@EVERY_FORMAT
def test_a_named_expression_has_a_legend_row_exactly_while_its_symbol_prints(name: FormatName, fmt: Format):
    """The legend explains the symbols the equations print.

    Inlined, `spend` is substituted into the objective that reads it and prints
    no symbol, so it earns no row.
    """
    assert 'what a snapshot costs' in typeset(DESCRIBED, name)
    assert 'what a snapshot costs' not in typeset(DESCRIBED, name, inline_expressions=True)


#: The dispatch model with a curve on it, so one model has two readings and one
#: table has to spell both.
CURVED = varied(
    DISPATCH_MODEL,
    **{
        'dimensions.bp': {'dtype': 'int'},
        'parameters.bp_x': {'dims': ['generator', 'bp']},
        'parameters.bp_y': {'dims': ['generator', 'bp']},
        'variables.op_cost': {'dims': ['snapshot', 'generator'], 'bounds': {'lower': 0}},
        'piecewise.curve': {'over': 'bp', 'links': [['p', 'bp_x'], ['op_cost', 'bp_y']]},
    },
)


def test_one_table_spells_the_blocks_a_file_states_and_the_rows_they_state():
    """The weights are named after the block, which no equation can carry, and the
    table that renames them has to render the file they came from too."""
    spec = to_spec(CURVED)
    table = {'notation': 'latex', 'names': {'curve_lam': r'\lambda'}}

    assert r'\lambda' not in to_latex(spec, symbols=table, legend=False), 'no weight stands where the curve prints'
    assert r'\lambda_{t,g,b}' in to_latex(spec.expand(), symbols=table, legend=False)


def test_a_misspelled_name_is_still_a_typo_where_a_formulation_could_have_emitted_it():
    with pytest.raises(SchemaError, match="Did you mean 'curve_lam'"):
        to_latex(CURVED, symbols={'notation': 'latex', 'names': {'curve_laam': 'x'}})


def _names(spec: Spec) -> set[str]:
    return {*spec.parameters, *spec.variables, *spec.expressions, *spec.constraints}


@pytest.mark.parametrize(
    'patch',
    [
        pytest.param({}, id='adjacency'),
        pytest.param({'piecewise.curve.method': 'sos2'}, id='sos2'),
        pytest.param({'piecewise.curve.method': 'convex'}, id='convex'),
        pytest.param(
            {'piecewise.curve.method': 'lp', 'piecewise.curve.links': [['p', 'bp_x'], ['op_cost', 'bp_y', '>=']]},
            id='lp',
        ),
        pytest.param(
            {
                'variables.u': {'dims': ['generator'], 'domain': 'binary', 'where': 'p_max'},
                'piecewise.curve.activity': 'u',
            },
            id='a-gate-that-leaves-coordinates-ungated',
        ),
    ],
)
def test_a_table_spells_the_names_the_expansion_declares_and_no_other(patch):
    """A name any method could write counted as declared, so a table naming the
    chord of a curve that has none, or the curve's own set, was ignored rather
    than refused."""
    spec = to_spec(varied(CURVED, **patch))
    written = _names(spec.expand()) - _names(spec)
    reserved = {
        'curve',
        *(f'curve_{s}' for s in ('lam', 'convexity', 'convexity_ungated', 'chord', 'domain_lo', 'domain_hi')),
        *(f'curve_{s}' for s in ('seg', 'pick', 'adjacency', 'adjacency_below', 'link0', 'link1')),
        *(f'curve_{s}' for s in ('complete', 'increasing')),
    }
    assert written <= reserved, 'the reserved names cover every name the expansion writes'

    def accepted(name: str) -> bool:
        try:
            to_latex(spec, symbols={'notation': 'latex', 'names': {name: 'x'}}, legend=False)
        except SchemaError:
            return False
        return True

    assert {n for n in reserved if accepted(n)} == written


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
        pytest.param({'dimensions': ['generator']}, 'dimensions: must be a mapping', id='a-section-that-is-a-list'),
        pytest.param({'names': 'p_max'}, 'names: must be a mapping', id='a-section-that-is-a-string'),
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
