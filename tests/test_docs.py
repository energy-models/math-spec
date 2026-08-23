# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The generated half of the documentation, held to what generates it.

`docs/examples/` shows each model beside the math the typesetter prints from
it. Written by hand, that math would be a claim nothing checks — on a site
whose subject is the math a file means, and in a repository that owns the
renderer which would have caught it. So the block is generated, and this is
what makes "generated" true of the committed file rather than of a script
nobody runs.
"""

from __future__ import annotations

import pytest

from math_spec.model import PIECEWISE_METHODS
from tools import gallery, home_math, notation


@pytest.mark.parametrize('page', gallery.pages())
def test_the_gallery_math_is_current(page: str):
    path = gallery.PAGES / page
    text = path.read_text()
    assert gallery.rendered(page, text) == text, (
        f'docs/examples/{page} no longer matches the model it shows — run `pixi run python -m tools.gallery`'
    )


def test_the_notation_page_is_current():
    """The same claim, for the page that shows every construct at once.

    It went unmade for longer, and cost more: four of the models the page
    renders from were left behind when the language was extracted, so
    `tools/notation.py` raised `FileNotFoundError` on the curve section and
    the committed page kept showing math no model here produced. Nothing
    failed, because nothing ran it.
    """
    text = notation.PAGE.read_text()
    assert notation.rendered_page(text) == text, (
        'docs/reference/notation.md no longer matches the fixture it is generated from — '
        'run `pixi run python -m tools.notation`'
    )


def test_the_homepage_math_is_current():
    """The third generated page, and the one that proved the guard was needed.

    `docs/index.md` and `README.md` carry `examples/dispatch.yaml` rendered two
    ways, and nothing was holding either to the renderer: a change to how a
    parameter prints left the homepage stale and every test green. Same claim
    as the two above, for the page a reader arrives at first.
    """
    stale = [
        path.name
        for path, updated in (
            (home_math.PAGE, home_math.rendered_page(home_math.PAGE.read_text())),
            (home_math.README, home_math.rendered_readme(home_math.README.read_text())),
        )
        if updated != path.read_text()
    ]
    assert not stale, f'{", ".join(stale)} no longer matches the model shown — run `pixi run python -m tools.home_math`'


def test_every_piecewise_method_has_a_model_on_the_notation_page():
    """What the page's `_curves()` claims: one row per `method:`, all of them.

    `PIECEWISE_METHODS` is the closed set, so a method added to the language
    lands here as a missing key rather than as a section quietly showing three
    of four formulations.
    """
    assert set(notation.PIECEWISE) == set(PIECEWISE_METHODS)
