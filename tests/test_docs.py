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
