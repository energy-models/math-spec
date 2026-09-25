# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""The expansion how-to's before and after tabs, from the pairs the suite compares.

    pixi run python -m tools.expansion_math           # rewrite every block
    pixi run python -m tools.expansion_math --check   # fail if one has drifted

Each block is one row of tabs, a stage of the expansion per tab, and each
stage holds its file and the math the typesetter prints from it. The inner
tabs share their labels, so ``content.tabs.link`` switches every one of them
on the page at once.
"""

from __future__ import annotations

import re
import textwrap

from mathspec import to_spec
from mathspec.typesetting import to_markdown
from tools._page import ROOT, splice
from tools._page import main as page_main

PAGE = ROOT / 'docs' / 'howto' / 'see-an-expansion.md'
PAIRS = ROOT / 'tests' / 'expand'

#: Each block on the page: the stages a reader compares, as a tab title and the
#: file under `tests/expand/` that holds that stage.
BLOCKS: dict[str, list[tuple[str, str]]] = {
    'set': [
        ('Before', 'set-type1/before.yaml'),
        ('`expand()`', 'set-type1/after.yaml'),
    ],
    'curve': [
        ('Before', 'curve-sos2/before.yaml'),
        ("`expand('piecewise')`", 'curve-sos2-piecewise/after.yaml'),
        ('`expand()`', 'curve-sos2/after.yaml'),
    ],
}

#: A section heading of the typeset document.
HEADING = re.compile(r'^#{1,6} (.+)$', re.MULTILINE)


def tab(title: str, body: str) -> str:
    """One tab: its title, and its body indented into it."""
    return f'=== "{title}"\n\n{textwrap.indent(body, "    ")}'


def math(path: str) -> str:
    """The document the typesetter prints from *path*, its headings as labels.

    A heading inside a tab still enters the page's table of contents, which
    would then list every section of every stage.
    """
    printed = to_markdown(to_spec(PAIRS / path), numbered=False, legend=False).strip()
    return HEADING.sub(r'_\1_', printed)


def stage(path: str) -> str:
    """One stage: the file, and the math beside it."""
    return '\n\n'.join((tab('YAML', f'```yaml\n{(PAIRS / path).read_text().strip()}\n```'), tab('Math', math(path))))


def block(name: str) -> str:
    """The row of tabs for block *name*, a stage per tab."""
    return '\n\n'.join(tab(title, stage(path)) for title, path in BLOCKS[name])


def rendered_page(page: str) -> str:
    """Prettier wants a blank line on each side of the markers, so each block carries them."""
    for name in BLOCKS:
        page = splice(page, f'<!-- expansion:{name}:begin -->', f'<!-- expansion:{name}:end -->', f'\n{block(name)}\n')
    return page


def main(argv: list[str] | None = None) -> int:
    return page_main(argv, {PAGE: rendered_page}, 'expansion_math')


if __name__ == '__main__':
    raise SystemExit(main())
