# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The generated half of the documentation, held to what generates it.

The site shows models beside the math the typesetter prints from them. Written
by hand, that math would be a claim nothing checks — on a site whose subject is
the math a file means, and in a repository that owns the renderer which would
have caught it. So the blocks are generated, and this is what makes
"generated" true of the committed files rather than of scripts nobody runs.
"""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from math_spec.dimensions import _shift_over_data_message
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
    """What the page's `_curves()` claims: one row per `method:`, all of them.

    `PIECEWISE_METHODS` is the closed set, so a method added to the language
    lands here as a missing key rather than as a section quietly showing three
    of four formulations.
    """
    assert set(notation.PIECEWISE) == set(PIECEWISE_METHODS)


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


def test_the_operators_page_quotes_the_shift_refusal_word_for_word():
    """The page pastes the message the loader prints, and nothing else keeps the two in step.

    A message rewritten in `dimensions.py` leaves the reference page quoting an
    error no reader will ever see, which is worse than the prose the block
    replaced.
    """
    quoted = _shift_over_data_message('ctx').removeprefix('ctx: ')
    indented = '\n'.join('  ' + line if line else '' for line in quoted.split('\n'))
    page = (ROOT / 'docs/reference/language/operators.md').read_text()
    assert indented in page, (
        'docs/reference/language/operators.md no longer quotes '
        '`_shift_over_data_message` verbatim — paste the message as it prints, unwrapped'
    )
