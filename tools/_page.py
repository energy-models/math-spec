# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""What every page generator shares: the marker splice, the `--check` front, and the corpus paths."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

ROOT = Path(__file__).resolve().parent.parent


def splice(text: str, begin: str, end: str, block: str) -> str:
    """*text* with everything between the *begin* and *end* markers replaced by *block*, on its own lines."""
    i, j = text.index(begin) + len(begin), text.index(end)
    return text[:i] + '\n' + block + '\n' + text[j:]


#: One ``math`` fence, which is how a block of math prints.
FENCE = re.compile(r'```math\n(.*?)\n```', re.DOTALL)


def inlined(markdown: str) -> str:
    """*markdown* with every ``math`` fence rewritten as the verbatim inline pair.

    Two places take no block of math. A table cell holds one line, and inside a
    ``<details>`` GitHub leaves the fence as the code block it looks like, so
    the fold prints the TeX rather than the equation. The verbatim pair renders
    in both, and hands the math over untouched, which is why it is the pair the
    typesetter prints inline math in anyway.

    It costs the display style, GitHub having no verbatim block pair, and it
    costs one line: an inline span ends at a newline. TeX reads a newline as a
    space, so the joined lines print the same math.
    """
    return FENCE.sub(lambda m: f'$`{" ".join(m[1].splitlines())}`$', markdown)


def without_header(path: Path) -> str:
    """The file from its first line that is neither blank nor a comment: the licence header is the repository's."""
    lines = path.read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() and not line.startswith('#'))
    return '\n'.join(lines[start:]).strip()


def sidecar_for(model: Path) -> Path | None:
    """The symbol table under ``examples/symbols/`` named after *model*, if one exists."""
    table = ROOT / 'examples' / 'symbols' / f'{model.stem}.yaml'
    return table if table.is_file() else None


def main(argv: list[str] | None, pages: Mapping[Path, Callable[[str], str]], tool: str) -> int:
    """Rewrite every page from its renderer, or with ``--check`` only say which have drifted."""
    ap = argparse.ArgumentParser(prog=f'python -m tools.{tool}')
    ap.add_argument('--check', action='store_true', help='fail if a committed page has drifted')
    check = ap.parse_args(argv).check

    stale = []
    for path, render in pages.items():
        text = path.read_text()
        updated = render(text)
        if not check:
            path.write_text(updated)
            print(f'wrote {path.relative_to(ROOT)}')
        elif updated != text:
            stale.append(str(path.relative_to(ROOT)))
    if stale:
        print(f'{", ".join(stale)} stale — run `pixi run python -m tools.{tool}`', file=sys.stderr)
        return 1
    if check:
        print(f'{len(pages)} page(s) current')
    return 0
