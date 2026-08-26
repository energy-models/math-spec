# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The example gallery: each model in `examples/`, beside the math it prints.

    pixi run python -m tools.gallery           # rewrite the pages' blocks
    pixi run python -m tools.gallery --check   # fail if one has drifted

The prose above each block is the page's own. Only the fenced model and the
math below it are written from here.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from math_spec.typesetting import to_markdown
from tools._page import ROOT, splice, without_header
from tools._page import main as page_main
from tools.spec_math import OPERATORS, PROBES, rendered_probe

if TYPE_CHECKING:
    from pathlib import Path

PAGES = ROOT / 'docs' / 'examples'
BEGIN, END = '<!-- gallery:begin -->', '<!-- gallery:end -->'

#: Page -> the model it shows. One model per page, because a gallery of
#: fragments is what the reference pages already are.
MODELS = {
    'dispatch.md': ROOT / 'examples' / 'dispatch.yaml',
}


def model_block(path: Path) -> str:
    """One model, then the whole document the typesetter prints from it."""
    return f'```yaml\n{without_header(path)}\n```\n\n{to_markdown(path, numbered=False).strip()}'


def probe_block() -> str:
    """Every operator probe: the model, then the one equation it renders."""
    parts = []
    for signature, name in OPERATORS.items():
        equation, _ = rendered_probe(name)
        parts.append(
            f'### `{signature}`\n\n'
            f'`examples/operators/{name}.yaml`\n\n'
            f'```yaml\n{without_header(PROBES / f"{name}.yaml")}\n```\n\n'
            f'{equation}'
        )
    return '\n\n'.join(parts)


def block(page: str) -> str:
    return probe_block() if page == 'operators.md' else model_block(MODELS[page])


def rendered(page: str, text: str) -> str:
    return splice(text, BEGIN, END, block(page))


def pages() -> list[str]:
    return [*MODELS, 'operators.md']


def main(argv: list[str] | None = None) -> int:
    return page_main(argv, {PAGES / page: partial(rendered, page) for page in pages()}, 'gallery')


if __name__ == '__main__':
    raise SystemExit(main())
