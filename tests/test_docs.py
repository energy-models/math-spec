# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The committed pages a generator writes, held to their generator."""

from __future__ import annotations

import re
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from math_spec.model import PIECEWISE_METHODS
from tools import gallery, home_math, notation, spec_math

if TYPE_CHECKING:
    from collections.abc import Callable

ROOT = Path(__file__).resolve().parent.parent

#: Every committed page a generator writes: how to re-render it, and which
#: tool rewrites it. Adding a generator means adding a row here, which
#: `test_every_generator_is_asked` is what says out loud.
GENERATED: list[tuple[str, Path, Callable[[str], str], str]] = [
    *(
        (f'gallery:{name}', gallery.PAGES / name, partial(gallery.rendered, name), 'gallery')
        for name in gallery.pages()
    ),
    ('notation', notation.PAGE, notation.rendered_page, 'notation'),
    ('operators', spec_math.PAGE, spec_math.rendered, 'spec_math'),
    ('home:index', home_math.PAGE, home_math.rendered_page, 'home_math'),
    ('home:readme', home_math.README, home_math.rendered_readme, 'home_math'),
]


@pytest.mark.parametrize(
    ('path', 'render', 'tool'),
    [row[1:] for row in GENERATED],
    ids=[row[0] for row in GENERATED],
)
def test_the_generated_page_is_current(path: Path, render: Callable[[str], str], tool: str):
    text = path.read_text()
    assert render(text) == text, (
        f'{path.relative_to(ROOT)} no longer matches what it is generated from — run `pixi run python -m tools.{tool}`'
    )


def test_every_generator_is_asked():
    """Three of the pages above were stale with the suite green (#41): the tool knew and nothing asked it."""
    detects_drift = {path.stem for path in (ROOT / 'tools').glob('*.py') if 'page_main(' in path.read_text()}
    assert detects_drift == {tool for *_, tool in GENERATED}, (
        'a tool that can detect a stale page has no row in GENERATED, or a row names a tool that cannot'
    )


def test_every_piecewise_method_has_a_model_on_the_notation_page():
    """What the page's `_curves()` claims: one row per `method:`, all of them."""
    assert set(notation.PIECEWISE) == set(PIECEWISE_METHODS), (
        'a method added to the language lands here as a missing key rather than as a formulation the page omits'
    )


def _card_bodies(page: Path) -> list[tuple[int, str]]:
    """Every line inside a `grid cards` block that continues a card, numbered from one.

    A card is a list item, so its body has to be indented far enough for
    python-markdown to read it as the item's content — anything less and the
    block still *looks* right in the source.
    """
    lines = page.read_text().split('\n')
    inside, bodies = False, []
    for number, line in enumerate(lines, start=1):
        if line.startswith('<div class="grid cards"'):
            inside = True
        elif inside and line.startswith('</div>'):
            inside = False
        elif inside and line.startswith(' '):
            bodies.append((number, line))
    return bodies


@pytest.mark.parametrize(
    'page',
    sorted(p for p in (ROOT / 'docs').rglob('*.md') if 'grid cards' in p.read_text()),
    ids=lambda page: page.stem,
)
def test_a_card_body_is_indented_far_enough_to_stay_in_its_card(page: Path):
    """Two spaces built a page whose six cards were six loose rules and paragraphs (#87).

    python-markdown wants four, prettier writes two, and the site rendered the
    difference: the `***` separator became a top-level rule and the prose fell
    out of the list. `<!-- prettier-ignore -->` above the list is what keeps
    the formatter off it.
    """
    shallow = [number for number, line in _card_bodies(page) if not line.startswith('    ')]
    assert not shallow, (
        f'{page.relative_to(ROOT)} lines {shallow}: a card body indented under four spaces leaves the list'
    )


def test_the_published_grammar_spells_a_name_the_way_the_code_reads_one():
    """The page said a name opens with a letter; `NAME` has always admitted `_`, and `_x + 1` parsed.

    The EBNF on that page is the language's published definition, and
    `expression_parser.NAME` is the one the loader and the schema both apply —
    `model.py` validates every declaration name against it. A page that refuses
    what the language accepts is the drift this asks about; it went unnoticed
    because nothing compared the two.
    """
    from math_spec._expression_parser import NAME

    page = (ROOT / 'docs' / 'reference' / 'language' / 'expressions.md').read_text()
    published = re.search(r'^NAME\s*::=\s*(.+)$', page, re.MULTILINE)
    assert published is not None, 'the expressions page no longer publishes a NAME production'

    assert published.group(1).strip() == NAME, (
        f'docs/reference/language/expressions.md publishes NAME as {published.group(1).strip()!r}, '
        f'and expression_parser.NAME is {NAME!r} — the page and the loader must spell a name the same way'
    )


#: A math span as the typesetter prints it for GitHub — a fence, which may be
#: indented inside a tab or a list, and the verbatim inline pair.
_FENCED_MATH = re.compile(r'^[ \t]*```math$', re.MULTILINE)
_INLINE_MATH = re.compile(r'\$`[^`\n]+`\$')


def _site_markdown():
    """A renderer configured exactly as the site's, from `mkdocs.yml` itself."""
    markdown = pytest.importorskip('markdown', reason='the docs feature; the bare test environment skips it')
    config = pytest.importorskip('mkdocs.config', reason='the docs feature; the bare test environment skips it')
    site = config.load_config(str(ROOT / 'mkdocs.yml'))
    return markdown.Markdown(extensions=site['markdown_extensions'], extension_configs=site['mdx_configs'])


@pytest.mark.parametrize(
    'page',
    sorted(p for p in (ROOT / 'docs').rglob('*.md') if _FENCED_MATH.search(p.read_text())),
    ids=lambda p: p.stem,
)
def test_the_site_renders_the_math_the_page_prints_for_github(page: Path):
    """Every span the typesetter prints reaches MathJax on the site, not just on GitHub.

    The two delimiters are GitHub's verbatim pair, which is the whole point of
    them — nothing can escape into the span. Arithmatex reads neither: the
    fence is a `superfences` entry in `mkdocs.yml` and the inline pair is the
    hook's, and a page rendering its equations as literal backticks is what
    either of those going missing looks like. The regex that preceded the
    fence entry missed `docs/index.md`, whose math is indented inside a tab.
    """
    source = page.read_text()
    printed = len(_FENCED_MATH.findall(source)) + len(_INLINE_MATH.findall(source))
    html = _site_markdown().convert(_hooks().on_page_markdown(source))
    assert html.count('class="arithmatex"') >= printed, (
        f'{page.relative_to(ROOT)} prints {printed} math spans and the site renders '
        f'{html.count('class="arithmatex"')} — the rest reach the reader as literal text'
    )
    assert '$`' not in html and 'language-math' not in html, 'no delimiter is left for the reader to see'


def _hooks():
    """The site's own hook module, loaded the way `mkdocs.yml` names it."""
    import importlib.util

    spec = importlib.util.spec_from_file_location('hooks', ROOT / 'docs' / 'static' / 'hooks.py')
    assert spec and spec.loader, 'the site loads docs/static/hooks.py, so it has to be importable'
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ('source', 'expected'),
    [
        pytest.param('| $`\\mathcal{T}`$ | index $`t`$ |', '| $\\mathcal{T}$ | index $t$ |', id='inline-math'),
        pytest.param('the pair ``$`x`$`` inline', 'the pair ``$`x`$`` inline', id='the-syntax-quoted-in-prose'),
        pytest.param('```math\n\\mathrm{a\\_b}\n```', '```math\n\\mathrm{a\\_b}\n```', id='a-math-fence'),
        pytest.param(
            '    ```math\n    \\mathrm{a\\_b}\n    ```',
            '    ```math\n    \\mathrm{a\\_b}\n    ```',
            id='a-math-fence-indented-in-a-tab',
        ),
        pytest.param('```yaml\nname: $`x`$\n```', '```yaml\nname: $`x`$\n```', id='a-model-that-shows-the-syntax'),
    ],
)
def test_the_hook_rewrites_math_and_nothing_that_only_quotes_it(source: str, expected: str):
    """Inline math becomes `$…$`; a fence and a code span are left exactly as they are.

    The fence is the `superfences` entry's, not the hook's — reaching into one
    would rewrite the YAML a gallery page shows beside its equation. And a
    backtick on the outer edge is a code span quoting the delimiter rather than
    math using it, which is how `docs/reference/typeset.md` documents it: an
    earlier version rewrote that page's own prose and hid the syntax it was
    explaining.
    """
    assert _hooks().on_page_markdown(source) == expected
