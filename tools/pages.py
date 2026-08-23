# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Writing a generated block into a page that prettier also formats.

Three tools here rewrite a marked-off region of a documentation page from a
model, and each then met the same wall. `pixi run lint` runs prettier over
`docs/`; prettier wants a blank line either side of an HTML comment and pads
markdown table cells out to a common width; no generator emitted either. So the
committed page never matched what its own generator had just written, and
``--check`` returned 1 on a tree nobody had touched --- a gate that cannot pass
is a gate nobody reads.

The split drawn here is **the generator owns the content, prettier owns the
whitespace.**

:func:`rewrite` emits the blank lines, because that part is free and it keeps a
freshly generated page from being rewritten by the very next commit hook. Cell
padding is not free: reproducing it means reimplementing prettier's width rules
and drifting from them at the next release. So :func:`matches` compares the two
sides with the padding taken back out --- exactly the thing prettier is allowed
to decide and a generator is not. What it still catches is every difference that
is somebody's, rather than a formatter's: a row that changed, a row that
appeared, a row that went away.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def rewrite(page: str, begin: str, end: str, block: str) -> str:
    """*page* with everything between *begin* and *end* replaced by *block*.

    The markers stay; the blank lines around them are prettier's and are
    written here so it has nothing left to change.
    """
    i, j = page.index(begin) + len(begin), page.index(end)
    return f'{page[:i]}\n\n{block}\n\n{page[j:]}'


def matches(one: str, other: str) -> bool:
    """Whether two pages differ by anything other than markdown whitespace."""
    return _content(one) == _content(other)


def _content(text: str) -> str:
    """*text* with the decisions prettier owns taken out of it.

    Blank lines, trailing space, and the padding inside a table cell --- which
    includes a separator row's run of hyphens, whose *length* is padding and
    whose alignment colons are not.
    """
    kept = []
    for line in text.splitlines():
        line = line.rstrip()
        if not line:
            continue
        if line.startswith('|'):
            cells = [cell.strip() for cell in line.strip('|').split('|')]
            line = '|'.join('-' + cell.strip('-') if _is_rule(cell) else cell for cell in cells)
        kept.append(line)
    return '\n'.join(kept)


def _is_rule(cell: str) -> bool:
    """Whether *cell* is a separator row's rule, e.g. ``---`` or ``:---:``."""
    return bool(cell) and set(cell) <= {'-', ':'} and '-' in cell


def update(pages: dict[Path, str], *, check: bool, tool: str, subject: str) -> int:
    """Write each page, or report which of them has drifted. An exit status.

    Args:
        pages: what each path should contain.
        check: report rather than write.
        tool: the module name, for the message telling a reader how to fix it.
        subject: what the pages are generated from, for the passing message.
    """
    stale = [path for path, updated in pages.items() if not matches(updated, path.read_text())]

    if check:
        for path in stale:
            print(f'{path.relative_to(ROOT)} is stale — run `pixi run python -m {tool}`', file=sys.stderr)
        if stale:
            return 1
        print(f'up to date with {subject}: {_named(pages)}')
        return 0

    # Only the stale ones. A page whose content already matches differs from
    # `updated` by prettier's padding alone, and rewriting it would strip that
    # padding for the commit hook to put straight back — turning every run on a
    # clean tree into a diff.
    for path in stale:
        path.write_text(pages[path])
        print(f'wrote {path.relative_to(ROOT)}')
    if not stale:
        print(f'already up to date with {subject}: {_named(pages)}')
    return 0


def _named(paths: dict[Path, str]) -> str:
    """The paths as a reader would name them, relative to the repository."""
    return ', '.join(str(path.relative_to(ROOT)) for path in paths)
