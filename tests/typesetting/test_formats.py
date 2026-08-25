# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Per-format spelling — fragments, not golden documents — and what compiles."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from math_spec.typesetting import FORMATS, to_latex, to_markdown, to_typst, typeset
from math_spec.typesetting.format import OPERATOR_NAMES
from tests.fixtures import override
from tests.typesetting import golden
from tests.typesetting.fixtures import DISPATCH, EVERY_FORMAT, TYPST, TYPST_SYMBOLS

if TYPE_CHECKING:
    from pathlib import Path

    from math_spec.typesetting.format import Format


@pytest.mark.parametrize(
    'fragment',
    [
        pytest.param('p_{t,g}', id='symbols-follow-the-names-variable'),
        pytest.param(r'\mathrm{load}_{t}', id='symbols-follow-the-names-parameter'),
        pytest.param(r'\mathrm{p}^{\mathrm{max}}_{g}', id='symbols-follow-the-names-qualifier'),
        pytest.param(
            r'\sum_{g \in \mathcal{G}} p_{t,g} & = \mathrm{load}_{t}',
            id='sum-binds-the-dimension-it-reduces',
        ),
        pytest.param(
            r'\sum_{t \in \mathcal{T},\ g \in \mathcal{G}} p_{t,g} \cdot \mathrm{cost}_{g}',
            id='a-sum-naming-no-dim-puts-them-all-in-its-domain',
        ),
        pytest.param(r'0 \le p_{t,g} & \le \mathrm{p}^{\mathrm{max}}_{g}', id='bounds-become-a-domain-line'),
        pytest.param(r'\text{power\_balance}', id='names-are-escaped-in-text-mode'),
    ],
)
def test_latex_spells_the_dispatch_model(fragment: str):
    assert fragment in to_latex(DISPATCH)


@pytest.mark.parametrize(
    ('bounds', 'expected'),
    [
        ({}, r'p_{t,g} & \in \mathbb{R}'),
        ({'lower': 0}, r'p_{t,g} & \ge 0'),
        ({'upper': 10}, r'p_{t,g} & \le 10'),
    ],
)
def test_latex_a_missing_bound_is_not_silently_zero(bounds: dict[str, object], expected: str):
    model = override(DISPATCH, **{'variables.p.bounds': bounds})
    assert expected in to_latex(model)


@pytest.mark.parametrize(
    ('declaration', 'expected'),
    [
        pytest.param(
            {'foreach': ['snapshot', 'generator'], 'domain': 'binary'},
            r'n_{t,g} & \in \{0, 1\}',
            id='binary',
        ),
        pytest.param(
            {'foreach': ['generator'], 'domain': 'integer', 'bounds': {'lower': 0, 'upper': 5}},
            r'0 \le n_{g} & \le 5, n_{g} \in \mathbb{Z}',
            id='integer-with-bounds',
        ),
        pytest.param({'foreach': ['generator'], 'domain': 'integer'}, r'n_{g} & \in \mathbb{Z}', id='integer-free'),
    ],
)
def test_latex_a_variable_states_its_domain(declaration: dict[str, object], expected: str):
    """An integer with bounds says both; one without says only where it lives.

    The free integer is here because it shares every line of the walk with the
    other two — the ternary picking the set is one statement — so nothing but
    an assertion on the output can tell that arm from its neighbour.
    """
    assert expected in to_latex(override(DISPATCH, **{'variables.n': declaration}))


def test_latex_sum_renders_the_coordinate_map_as_a_set_condition():
    """Read off the operator probe rather than a gallery model.

    `sum(by=)` is what the probe exists to show, and the probe travels with the
    renderer where the gallery does not — so this asserts the construct on the
    corpus that will still be beside it. Two maps rather than one: the
    conjunction is the part a single lookup cannot show.
    """
    tex = to_latex('examples/operators/sum_by_lookups.yaml', legend=False)
    assert r'\sum_{g \in \mathcal{G} \,:\, \mathrm{gen\_bus}(g) = b \wedge \mathrm{gen\_tech}(g) = e} p_{t,g}' in tex


def test_latex_a_sum_used_as_a_factor_is_bracketed():
    """Unbracketed, `\\sum_g x_g \\cdot 2` reads as the sum capturing the 2."""
    model = override(DISPATCH, **{'constraints.power_balance.expression': 'sum(p, over=generator) * 2 == load'})
    assert r'\left( \sum_{g \in \mathcal{G}} p_{t,g} \right) \cdot 2' in to_latex(model, legend=False)


def test_latex_standalone_is_a_whole_document():
    tex = to_latex(DISPATCH, standalone=True)
    assert tex.startswith(r'\documentclass')
    assert r'\usepackage{amsmath}' in tex
    assert tex.rstrip().endswith(r'\end{document}')


def test_latex_numbering_can_be_turned_off():
    assert r'\begin{align*}' in to_latex(DISPATCH, numbered=False)
    assert r'\begin{align}' in to_latex(DISPATCH, numbered=True)


# ---------------------------------------------------------------------------
# Typst
# ---------------------------------------------------------------------------


def test_typst_uses_its_own_grouping_and_set_notation():
    typ = to_typst(DISPATCH, legend=False)
    assert 'p_(t,g)' in typ
    assert 'sum_(g in cal(G))' in typ
    assert 'upright("load")_(t)' in typ


def test_typst_sum_renders_the_coordinate_map():
    """The same map in the other notation, off the same travelling probe."""
    typ = to_typst('examples/operators/sum_by_lookups.yaml', legend=False)
    assert 'sum_(g in cal(G) colon upright("gen_bus")(g) = b and upright("gen_tech")(g) = e) p_(t,g)' in typ


# ---------------------------------------------------------------------------
# Markdown — the one that renders where the docs already live
# ---------------------------------------------------------------------------


def test_markdown_is_latex_math_in_a_markdown_wrapper():
    """The math is byte-identical to the LaTeX lane's; only the wrapper differs.
    That is the claim the module makes, so it is the one asserted."""
    md = to_markdown(DISPATCH, legend=False)
    assert r'\sum_{g \in \mathcal{G}} p_{t,g}' in md, 'the math is spelled exactly as LaTeX spells it'
    assert '#### Subject to' in md, 'the document layer is the whole difference'
    assert r'\begin{align}' not in md
    assert r'\paragraph' not in md


def test_markdown_keeps_names_out_of_the_math():
    """`\\text{total\\_cost}` is correct in a LaTeX document and wrong in a
    browser: MathJax renders the `\\_` escape literally, backslash and all. A
    name is not math, so it goes outside the `$$` as a code span."""
    md = to_markdown(DISPATCH, legend=False)
    assert '**`power_balance`**' in md
    for block in md.split('$$')[1::2]:
        assert '\\_' not in block, f'escaped underscore reached the math: {block!r}'


def test_markdown_gives_each_equation_its_own_block():
    """`aligned` columns line up *across rows*. A page shows one equation at a
    time under its own heading, so the separators aligned against nothing and
    rendered as stretches of empty space."""
    md = to_markdown(DISPATCH, legend=False)
    assert md.count('$$') % 2 == 0
    assert 'aligned' not in md
    assert '&' not in md.replace('&&', ''), 'no alignment separators at all'


def test_markdown_renders_the_legend_as_a_table():
    md = to_markdown(DISPATCH)
    assert '| Symbol | Meaning |' in md
    assert '| `p_max` over' in md.replace('$p^{\\mathrm{max}}$ ', '')


#: Reduction operators carry a subscript without being a symbol.


def test_typst_standalone_adds_page_setup():
    assert to_typst(DISPATCH, standalone=True).startswith('#set page')
    assert not to_typst(DISPATCH).startswith('#set page')


@pytest.fixture(scope='module')
def typst():
    return pytest.importorskip('typst', reason='typst is a dev dependency; the bare install skips it')


def test_typst_output_with_a_symbol_table_compiles(typst, tmp_path: Path):
    """The gap that let #321 through: the compile test never ran with `symbols=`."""
    source = tmp_path / 'symbols.typ'
    source.write_text(to_typst(DISPATCH, symbols=TYPST_SYMBOLS, standalone=True))
    typst.compile(str(source), output=str(tmp_path / 'symbols.pdf'))


def test_a_description_of_every_special_compiles(typst, tmp_path: Path):
    """Escapes that are *present* are not necessarily *right*, and only a
    compiler says which.

    The golden model's description carries every character the notations
    escape; this is the Typst half of that claim, and CI's `pdflatex` run over
    the same file is the LaTeX half.
    """
    source = tmp_path / 'specials.typ'
    source.write_text(to_typst(golden.MODEL, standalone=True))
    typst.compile(str(source), output=str(tmp_path / 'specials.pdf'))


def test_every_typst_operator_compiles(typst, tmp_path: Path):
    """Only a handful of operators appear in `examples/`; the rest would
    otherwise first fail on somebody's own model."""
    probe = tmp_path / 'operators.typ'
    probe.write_text('\n'.join(f'$ a {TYPST.operators[name]} b $' for name in sorted(OPERATOR_NAMES)))
    typst.compile(str(probe), output=str(tmp_path / 'operators.pdf'))


@EVERY_FORMAT
def test_the_model_description_opens_the_document(fmt: Format):
    """What the file says it is, printed before anything it declares — and
    printed with `legend=False` too, since it is not a symbol table."""
    described = override(DISPATCH, description='least-cost dispatch of a generator fleet')
    for options in ({}, {'legend': False}):
        out = typeset(described, fmt, **options)
        assert 'least-cost dispatch of a generator fleet' in out, f'missing with {options}'
        assert out.index('least-cost dispatch') < out.index(fmt.operators['minimize']), 'it opens the document'
    assert 'least-cost dispatch' not in typeset(DISPATCH, fmt), 'a model without one prints no empty paragraph'


#: Every character the two typeset notations have to escape, in prose a
#: modeller would plausibly write: the underscore in a coordinate's name is
#: what #827 hit, on a description `examples/ports/pypsa_ac_dc.yaml` carried.
SPECIALS = r'flow to link_to, 100% & #1 costs $5 {net} ~ ^ \ *star* @ref <label>'

ESCAPED = {
    'latex': (r'link\_to', r'100\% \& \#1', r'\$5 \{net\}', r'\textasciitilde{}', r'\textbackslash{}'),
    'typst': (r'link\_to', r'\#1', r'\$5', r'\*star\*', r'\@ref', r'\<label\>'),
}


@pytest.mark.parametrize('notation', sorted(ESCAPED), ids=sorted(ESCAPED))
@pytest.mark.parametrize('position', ['file', 'declaration'], ids=['file-description', 'declaration-description'])
def test_a_description_sets_as_text_rather_than_as_markup(notation: str, position: str):
    """A `description:` is prose in no notation, so a special in it is a
    character rather than an instruction.

    Both places author prose reaches the page: the file's own description,
    which opens the document, and a declaration's, which is the `Meaning` half
    of its legend row. Left raw, `link_to` was a fatal `pdflatex` error instead
    of a document (#827), and the corpus could only avoid that by never writing
    one.
    """
    where = 'description' if position == 'file' else 'parameters.load.description'
    out = typeset(override(DISPATCH, **{where: SPECIALS}), FORMATS[notation])
    for expected in ESCAPED[notation]:
        assert expected in out, f'{notation}: {expected!r} is set as text'
    assert SPECIALS not in out, 'the raw prose reached the document unescaped'
