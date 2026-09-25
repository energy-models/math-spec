# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""The symbol table."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import yaml

from mathspec.errors import SchemaError
from mathspec.typesetting import to_latex, to_markdown, to_typst, typeset
from mathspec.validation import to_spec
from tests.fixtures import DISPATCH_MODEL, override
from tests.typesetting.fixtures import EVERY_FORMAT, TYPST_SYMBOLS

if TYPE_CHECKING:
    from mathspec.model import Spec
    from mathspec.typesetting import FormatName
    from mathspec.typesetting.format import Format


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
                'latex': {
                    'dimensions': {'generator': {'index': 'u', 'set': r'\mathcal{U}'}},
                    'names': {'p': r'\pi', 'marginal_cost': r'c^{\mathrm{marg}}'},
                }
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


#: The dispatch model spelling its own symbols, one table per notation.
SPELLED = override(
    DISPATCH_MODEL,
    **{'symbols.latex.names': {'p': r'\pi'}, 'symbols.typst.names': {'p': 'pi'}},
)


@pytest.mark.parametrize(
    'model',
    [
        pytest.param(lambda: SPELLED, id='a-mapping'),
        pytest.param(lambda: yaml.safe_dump(SPELLED), id='the-yaml'),
        pytest.param(lambda: to_spec(SPELLED), id='a-spec'),
        pytest.param(lambda: to_spec(SPELLED).program, id='a-program'),
        pytest.param(lambda: to_spec(to_spec(SPELLED).to_yaml()), id='the-yaml-a-spec-writes'),
    ],
)
@pytest.mark.parametrize(
    ('render', 'symbol'),
    [
        pytest.param(to_latex, r'\pi_{t,g}', id='latex'),
        pytest.param(to_markdown, r'\pi_{t,g}', id='markdown'),
        pytest.param(to_typst, 'pi_(t,g)', id='typst'),
    ],
)
def test_the_model_carries_its_own_symbols_and_each_render_reads_its_notation(model, render, symbol):
    """#492: the symbols lived in a sidecar written in one notation, so a model
    documented in LaTeX could not print as Typst without a second file that
    drifts. Markdown's math is MathJax's, so it reads the `latex` table."""
    assert symbol in render(model(), legend=False)


def test_a_notation_the_model_does_not_spell_prints_derived():
    """A model with only a LaTeX table used to be refused by a Typst render."""
    latex_only = override(DISPATCH_MODEL, **{'symbols.latex.names': {'p': r'\pi'}})
    assert to_typst(latex_only) == to_typst(DISPATCH_MODEL), 'no typst table, so every symbol is derived'


@pytest.mark.parametrize(
    ('symbols', 'expected'),
    [
        pytest.param({}, lambda: to_latex(DISPATCH_MODEL), id='an-empty-block-derives-every-symbol'),
        pytest.param(
            {'latex': {'names': {'cost': 'c'}}},
            lambda: to_latex(DISPATCH_MODEL, symbols={'latex': {'names': {'cost': 'c'}}}),
            id='a-block-replaces-the-models-whole',
        ),
    ],
)
def test_the_symbols_argument_replaces_the_models_block(symbols, expected):
    """An author whose symbols need a package the reader lacks, such as
    `upgreek`, is not stuck with them: `symbols=` replaces the block rather than
    merging into it, so `p` is no longer `\\pi` in either case."""
    assert to_latex(SPELLED, symbols=symbols) == expected()


def test_a_render_reads_only_the_table_for_its_own_notation():
    """#321 was LaTeX passed into a Typst document, which failed three tools
    later. A table is now picked by the render's notation, so a LaTeX spelling
    never reaches a Typst document."""
    latex_only = {'latex': {'names': {'p_max': r'\bar p'}}}
    assert to_typst(DISPATCH_MODEL, symbols=latex_only) == to_typst(DISPATCH_MODEL)


DESCRIBED = override(
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
CURVED = override(
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
    spec = to_spec(override(CURVED, **{'symbols.latex.names': {'curve_lam': r'\lambda'}}))

    assert r'\lambda' not in to_latex(spec, legend=False), 'no weight stands where the curve prints'
    assert r'\lambda_{t,g,b}' in to_latex(spec.expand(), legend=False), 'the expansion keeps the block'


def test_a_misspelled_name_is_still_a_typo_where_a_formulation_could_have_emitted_it():
    with pytest.raises(SchemaError, match="Did you mean 'curve_lam'"):
        to_spec(override(CURVED, **{'symbols.latex.names': {'curve_laam': 'x'}}))


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
    spec = to_spec(override(CURVED, **patch))
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
            to_latex(spec, symbols={'latex': {'names': {name: 'x'}}}, legend=False)
        except SchemaError:
            return False
        return True

    assert {n for n in reserved if accepted(n)} == written


@pytest.mark.parametrize(
    'load',
    [
        pytest.param(lambda symbols: to_spec({**DISPATCH_MODEL, 'symbols': symbols}), id='in-the-file'),
        pytest.param(lambda symbols: to_latex(DISPATCH_MODEL, symbols=symbols), id='passed'),
    ],
)
@pytest.mark.parametrize(
    ('symbols', 'match'),
    [
        pytest.param({'latex': {'names': {'p_maxx': 'x'}}}, "Did you mean 'p_max'", id='a-misspelled-name'),
        pytest.param(
            {'typst': {'dimensions': {'generatr': {'index': 'g'}}}},
            "symbols: typst: 'generatr' under dimensions: .* Did you mean 'generator'",
            id='a-misspelled-dimension',
        ),
        pytest.param({'latex': {'namez': {'p': 'x'}}}, "unknown key 'namez' .* Did you mean 'names'", id='a-section'),
        pytest.param(
            {'latex': {'dimensions': {'generator': {'letter': 'g'}}}},
            "unknown key 'letter' .* Valid keys: index, set",
            id='a-dimension-key',
        ),
        pytest.param({'latx': {}}, "Input should be 'latex' or 'typst'", id='a-notation-outside-the-vocabulary'),
        pytest.param({'latex': {'dimensions': ['generator']}}, 'dimensions: Input should be a valid dict', id='a-list'),
    ],
)
def test_an_entry_naming_nothing_is_an_error_with_the_near_miss(load, symbols, match):
    """A silent typo means a symbol that never applies and a reader who never
    finds out, so it fails at load and says what it probably meant."""
    with pytest.raises(SchemaError, match=match):
        load(symbols)


def test_an_empty_override_is_used_not_fallen_through():
    tex = to_latex(DISPATCH_MODEL, symbols={'latex': {'names': {'p_max': ''}}})
    assert r'p^{\mathrm{max}}' not in tex, 'an entry in the table is used verbatim, even empty — never re-derived'
