# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Per-format spelling the golden document does not pin, and what compiles."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from math_spec.typesetting import FORMATS, to_latex, to_markdown, to_typst, typeset
from math_spec.typesetting.format import OPERATOR_NAMES
from tests.fixtures import DISPATCH_MODEL, override
from tests.typesetting import golden
from tests.typesetting.fixtures import EVERY_FORMAT, TYPST_SYMBOLS

if TYPE_CHECKING:
    from pathlib import Path

    from math_spec.typesetting.format import Format


def test_latex_numbering_can_be_turned_off():
    assert r'\begin{align*}' in to_latex(DISPATCH_MODEL, numbered=False)


def test_markdown_keeps_names_out_of_the_math():
    """`\\text{total\\_cost}` is correct in a LaTeX document and wrong in a
    browser: MathJax renders the `\\_` escape literally, backslash and all. A
    name is not math, so it goes outside the `$$` as a code span."""
    md = to_markdown(DISPATCH_MODEL, legend=False)
    assert '**`balance`**' in md
    for block in md.split('$$')[1::2]:
        assert '\\_' not in block, f'escaped underscore reached the math: {block!r}'


def test_typst_standalone_adds_page_setup():
    assert to_typst(DISPATCH_MODEL, standalone=True).startswith('#set page')
    assert not to_typst(DISPATCH_MODEL).startswith('#set page'), 'a fragment carries no page setup'


@pytest.fixture(scope='module')
def typst():
    return pytest.importorskip('typst', reason='typst is a dev dependency; the bare install skips it')


def test_typst_output_with_a_symbol_table_compiles(typst, tmp_path: Path):
    """The gap that let #321 through: the compile test never ran with `symbols=`."""
    source = tmp_path / 'symbols.typ'
    source.write_text(to_typst(DISPATCH_MODEL, symbols=TYPST_SYMBOLS, standalone=True))
    typst.compile(str(source), output=str(tmp_path / 'symbols.pdf'))


def test_every_typst_operator_compiles(typst, tmp_path: Path):
    """Only a handful of operators appear in `examples/`; the rest would
    otherwise first fail on somebody's own model."""
    probe = tmp_path / 'operators.typ'
    probe.write_text('\n'.join(f'$ a {FORMATS["typst"].operators[name]} b $' for name in sorted(OPERATOR_NAMES)))
    typst.compile(str(probe), output=str(tmp_path / 'operators.pdf'))


@EVERY_FORMAT
@pytest.mark.parametrize(
    'options', [pytest.param({}, id='with-a-legend'), pytest.param({'legend': False}, id='without-one')]
)
def test_the_model_description_opens_the_document(fmt: Format, options: dict):
    """What the file says it is, printed before anything it declares — and
    printed with `legend=False` too, since it is not a symbol table."""
    described = override(DISPATCH_MODEL, description='least-cost dispatch of a generator fleet')
    out = typeset(described, fmt, **options)
    assert 'least-cost dispatch of a generator fleet' in out
    assert out.index('least-cost dispatch') < out.index(fmt.operators['minimize']), 'it opens the document'
    assert 'least-cost dispatch' not in typeset(DISPATCH_MODEL, fmt), 'a model without one prints no empty paragraph'


# ---------------------------------------------------------------------------
# escaping — prose that each format would otherwise read as markup
# ---------------------------------------------------------------------------


#: Every character the two typeset notations have to escape, in prose a
#: modeller would plausibly write: the underscore in a coordinate's name is
#: what #827 hit, on a description `examples/ports/pypsa_ac_dc.yaml` carried.
SPECIALS = r'flow to link_to, 100% & #1 costs $5 {net} ~ ^ \ *star* @ref <label> a/b [x] `raw`'

ESCAPED = {
    'latex': (
        r'link\_to',
        r'100\% \& \#1',
        r'\$5 \{net\}',
        r'\textasciitilde{} \textasciicircum{} \textbackslash{}',
        r'*star* @ref <label> a/b [x] `raw`',
    ),
    'typst': (
        r'link\_to',
        r'100% & \#1',
        r'\$5 {net}',
        r'\~ ^ \\',
        r'\*star\* \@ref \<label\> a\/b \[x\] \`raw\`',
    ),
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
    out = typeset(override(DISPATCH_MODEL, **{where: SPECIALS}), FORMATS[notation])
    for expected in ESCAPED[notation]:
        assert expected in out, 'each special is escaped, and a character the notation reads as text is left alone'
    assert SPECIALS not in out, 'the raw prose reached the document unescaped'


@pytest.mark.parametrize(
    'model',
    [
        pytest.param(golden.MODEL, id='the-golden-model'),
        pytest.param(override(DISPATCH_MODEL, description=SPECIALS), id='every-special'),
    ],
)
def test_a_description_of_every_special_compiles(typst, tmp_path: Path, model):
    """Escapes that are *present* are not necessarily *right*, and only a
    compiler says which.

    This is the Typst half of that claim; CI's `pdflatex` run over the golden
    model is the LaTeX half.
    """
    source = tmp_path / 'specials.typ'
    source.write_text(to_typst(model, standalone=True))
    typst.compile(str(source), output=str(tmp_path / 'specials.pdf'))


def test_typst_prose_escapes_what_typst_reads_as_markup(typst, tmp_path: Path):
    described = override(DISPATCH_MODEL, description='- a list? a // comment [a link] and = a heading')
    typ = to_typst(described, standalone=True)
    assert r'\- a list? a \/\/ comment \[a link\] and = a heading' in typ, (
        'a leading list marker, a comment and a link are escaped, and an inline `=` is no heading'
    )
    source = tmp_path / 'prose.typ'
    source.write_text(typ)
    typst.compile(str(source), output=str(tmp_path / 'prose.pdf'))


def test_markdown_glossary_cells_survive_a_pipe_and_a_newline():
    described = override(DISPATCH_MODEL, **{'parameters.load.description': 'a | b\nc'})
    md = to_markdown(described)
    assert r'| `load` over $\mathcal{T}$ — a \| b c |' in md, (
        'the pipe is escaped and the newline folded, so the cell stays one cell'
    )


def test_latex_glossary_item_guards_a_bracket_in_the_symbol():
    tex = to_latex(DISPATCH_MODEL, symbols={'notation': 'latex', 'names': {'load': 'L^{[k]}'}})
    assert r'\item[{$L^{[k]}$}]' in tex, (
        r'the symbol is braced, so \item does not read its bracket as the optional argument'
    )
