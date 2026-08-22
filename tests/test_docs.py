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

from tools import gallery


@pytest.mark.parametrize('page', gallery.pages())
def test_the_gallery_math_is_current(page: str):
    path = gallery.PAGES / page
    text = path.read_text()
    assert gallery.rendered(page, text) == text, (
        f'docs/examples/{page} no longer matches the model it shows — run `pixi run python -m tools.gallery`'
    )
