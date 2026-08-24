# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The example gallery: each model in `examples/`, beside the math it prints.

    pixi run python -m tools.gallery           # rewrite the pages' blocks
    pixi run python -m tools.gallery --check   # fail if one has drifted

The reference pages show what a *construct* prints; nothing showed a **model**.
A reader could see the equation `sum(by=)` renders as and never see a file that
declares one, which is the wrong way round for a language whose pitch is that
the file and the math are the same thing.

So each page is one model, in full, followed by the document the typesetter
prints from it. Generated for the reason the other two blocks are: math typed
into a page is math nothing checks, and this project has the renderer that
would have caught it.

The prose above each block is the page's own — what the model is for, and which
construct it is here to show. Only the fenced model and the math below it are
written from here.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from math_spec.typesetting import to_markdown
from tools.spec_math import OPERATORS, rendered_probe

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / 'docs' / 'examples'
BEGIN, END = '<!-- gallery:begin -->', '<!-- gallery:end -->'

#: Page -> the model it shows. One model per page, because a gallery of
#: fragments is what the reference pages already are.
MODELS = {
    'dispatch.md': ROOT / 'examples' / 'dispatch.yaml',
}

#: The probe page shows every model under `examples/operators/`, keyed by the
#: signature it demonstrates — :data:`tools.spec_math.OPERATORS` is that map,
#: and reusing it is what keeps the two pages naming the same probes.
PROBES = ROOT / 'examples' / 'operators'


def source(path: Path) -> str:
    """The model as written, without the licence header a reader did not ask for."""
    return re.sub(r'\A(#[^\n]*\n)+\n', '', path.read_text()).strip()


def model_block(path: Path) -> str:
    """One model, then the whole document the typesetter prints from it."""
    return f'```yaml\n{source(path)}\n```\n\n{to_markdown(path, numbered=False).strip()}'


def probe_block() -> str:
    """Every operator probe: the model, then the one equation it renders."""
    parts = []
    for signature, name in OPERATORS.items():
        equation, _ = rendered_probe(name)
        parts.append(
            f'### `{signature}`\n\n'
            f'`examples/operators/{name}.yaml`\n\n'
            f'```yaml\n{source(PROBES / f"{name}.yaml")}\n```\n\n'
            f'{equation}'
        )
    return '\n\n'.join(parts)


def block(page: str) -> str:
    return probe_block() if page == 'operators.md' else model_block(MODELS[page])


def rendered(page: str, text: str) -> str:
    i, j = text.index(BEGIN) + len(BEGIN), text.index(END)
    return text[:i] + '\n' + block(page) + '\n' + text[j:]


def pages() -> list[str]:
    return [*MODELS, 'operators.md']


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--check', action='store_true', help='fail if a committed block has drifted')
    opts = ap.parse_args(argv)

    stale = []
    for page in pages():
        path = PAGES / page
        text = path.read_text()
        updated = rendered(page, text)
        if opts.check:
            if updated != text:
                stale.append(page)
            continue
        path.write_text(updated)
        print(f'wrote {path.relative_to(ROOT)}')

    if stale:
        names = ', '.join(stale)
        print(f'{names} stale — run `pixi run python -m tools.gallery`', file=sys.stderr)
        return 1
    if opts.check:
        print(f'{len(pages())} page(s) match their models')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
