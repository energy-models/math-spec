# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The notation reference: every construct beside the math it prints.

    pixi run python -m tools.notation           # rewrite the page's block
    pixi run python -m tools.notation --check   # fail if it has drifted

The source is ``tests/typesetting/golden/model.yaml``, the one model that
carries every construct — ``tests/typesetting/test_golden.py`` holds it to the
language, and this tool emits a row for every declaration in it. The fixture's
own case-label comments become the captions.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from math_spec.model import PIECEWISE_METHODS
from math_spec.typesetting import to_markdown
from math_spec.validation import to_spec
from tools._page import ROOT, sidecar_for, splice, without_header
from tools._page import main as page_main

if TYPE_CHECKING:
    from pathlib import Path
PAGE = ROOT / 'docs' / 'reference' / 'notation.md'
MODEL = ROOT / 'tests' / 'typesetting' / 'golden' / 'model.yaml'

#: One model per ``method:``, because the four restrict the weights four
#: different ways and a section showing one of them would be showing a quarter
#: of the construct. ``tests/test_docs.py`` holds these keys to
#: :data:`math_spec.model.PIECEWISE_METHODS`, so a method added to the
#: language arrives here or the page stops claiming to be all of them.
#:
#: They come from real models rather than from the fixture because a caption
#: saying what a method is for reads against a model that had a reason to
#: choose it.
PIECEWISE = {
    'adjacency': ROOT / 'examples' / 'ports' / 'transport_pwl.yaml',
    'sos2': ROOT / 'examples' / 'sos.yaml',
    'convex': ROOT / 'examples' / 'piecewise.yaml',
    'lp': ROOT / 'examples' / 'piecewise_lp.yaml',
}
BEGIN, END = '<!-- notation:begin -->', '<!-- notation:end -->'

#: The blocks that declare math, in the order the page walks them, and the
#: heading each gets. ``dimensions``, ``relations`` and ``parameters`` are absent
#: on purpose: they declare no equation, and what they print is the legend,
#: which the page shows once as a legend rather than a row at a time.
SECTIONS = {
    'objective': 'The objective',
    'constraints': 'Constraints',
    'expressions': 'Definitions',
    'variables': 'Variable domains',
    'piecewise': 'Curves',
    'sos': 'Sets carried to the solver',
    'assumptions': 'What the data has to satisfy',
}


class Declaration:
    """One block of the fixture: its name, its YAML, and the caption beside it."""

    def __init__(self, name: str, lines: list[str], caption: str) -> None:
        self.name, self.lines, self.caption = name, lines, caption

    def field(self, key: str) -> str:
        """One scalar the block declares — ``''`` where it declares no such key."""
        for line in self.lines:
            if match := re.match(rf'^\s+{key}:\s*(\S+)', line):
                return match[1]
        return ''

    @property
    def yaml(self) -> str:
        """The block as written, dedented, with the caption comment removed.

        Dedented because a fragment is read on its own: two spaces of leading
        indent are what the block's position in the file costs it, and every
        line of every row would carry them.
        """
        kept = [line.removeprefix('  ') for line in self.lines if not _described(line, self.lines)]
        body = '\n'.join(kept)
        return re.sub(r'[ ]+#[^\n]*', '', body, count=1) if self.caption else body


def _described(line: str, lines: list[str]) -> bool:
    """Whether *line* belongs to a ``description:`` — prose, not notation.

    A row is a construct beside its math, and a paragraph arguing for the
    modelling choice is neither. The models the curve rows come from are real
    ones and carry long ones; the fixture carries none.
    """
    start = next((i for i, text in enumerate(lines) if text.strip().startswith('description:')), None)
    if start is None:
        return False
    indent = len(lines[start]) - len(lines[start].lstrip())
    end = next(
        (i for i in range(start + 1, len(lines)) if len(lines[i]) - len(lines[i].lstrip()) <= indent),
        len(lines),
    )
    return line in lines[start:end]


def declarations(text: str) -> dict[str, list[Declaration]]:
    """The fixture's blocks, by section, in file order.

    Scanned rather than parsed by a YAML reader: the comments are the captions,
    and a reader that keeps them is a dependency this repo does not have.
    """
    found: dict[str, list[Declaration]] = {section: [] for section in SECTIONS}
    section, current = None, None
    for line in text.splitlines():
        if match := re.match(r'^(\w+):', line):
            section = match[1] if match[1] in SECTIONS else None
            current = None
            if section == 'objective':
                current = Declaration('objective', [], _caption(line))
                found[section].append(current)
            continue
        if section is None:
            continue
        if section == 'objective':
            if line.strip():
                assert current is not None
                current.lines.append(line)
            continue
        if match := re.match(r'^  (\w+):', line):
            current = Declaration(match[1], [line], _caption(line))
            found[section].append(current)
        elif current is not None and line.strip():
            current.lines.append(line)
    return found


def _caption(line: str) -> str:
    """The trailing comment on a declaration's first line, if it carries one."""
    match = re.search(r'#\s*(.+)$', line)
    return match[1].strip() if match else ''


def equations(rendered: str) -> dict[str, str]:
    """Label -> the ``math`` fence the walk printed for it.

    The objective's line carries no label — the block has no name — so it is
    keyed by the section it is the only member of.
    """
    found = {}
    label = 'objective'
    for block in rendered.split('\n\n'):
        if match := re.fullmatch(r'\*\*`(.+)`\*\*', block.strip()):
            label = match[1]
        elif block.startswith('```math'):
            found[label] = block.strip()
    return found


def legend(rendered: str) -> str:
    """The tables and the translation notes, without the model's description.

    The description is the fixture's own — a line of escaping torture, there so
    CI's LaTeX run proves the escapes right — and it says nothing about
    notation, which is what this page is for.
    """
    blocks = rendered.split('\n\n')
    start = next(i for i, block in enumerate(blocks) if block.startswith('#### '))
    end = next(i for i, block in enumerate(blocks) if block.startswith('#### Objective'))
    return '\n\n'.join(blocks[start:end]).strip()


#: What the legend is made of. No equation comes from these, so they are shown
#: once, together, above the tables they turn into.
DECLARED = ('dimensions', 'relations', 'parameters')


def preamble(text: str) -> str:
    """The fixture's ``dimensions``/``relations``/``parameters`` blocks, verbatim."""
    blocks = []
    for name in DECLARED:
        body = text[text.index(f'\n{name}:') + 1 :]
        end = re.search(r'\n(?=\w)', body)
        blocks.append(body[: end.start()] if end else body)
    return '\n'.join(blocks).strip()


def block() -> str:
    """The page's generated half: the legend, then every declaration in turn."""
    rendered = to_markdown(MODEL, numbered=False)
    parts = [
        '### The legend',
        'A dimension, a relation and a parameter declare no equation; what they '
        'print is the legend every model opens with.',
        f'```yaml\n{preamble(MODEL.read_text())}\n```',
        legend(rendered),
    ]
    printed = equations(rendered)
    written = equations(to_markdown(to_spec(MODEL).expand('sos'), numbered=False))
    for section, title in SECTIONS.items():
        parts.append(f'### {title}')
        found = declarations(MODEL.read_text())[section]
        if section == 'piecewise':
            parts.append(
                'A curve prints as the curve it states, over the frame the block builds one per coordinate of, '
                'and its expansion prints the rows that curve stands for. One row per `method:`, each from the '
                "model named under it, so the symbols in this section are that model's."
            )
            parts += _curves()
            continue
        if section == 'sos':
            parts.append(
                'A set prints beside the variable it restricts, because it restricts that variable rather than '
                'adding a row of its own. Under it are the rows it is written out as.'
            )
            parts += [f'{_row(one, printed)}\n\n{_written_out(one.name, written)}' for one in found]
            continue
        parts += [_row(one, printed) for one in found]
    return '\n\n'.join(parts)


def _curves() -> list[str]:
    """One row per ``method:``, each captioned with what that method restricts.

    Both readings come from one model and one symbol table: the block as the
    file states it, and the rows ``expand('piecewise')`` writes out — which for
    ``sos2`` keeps the set and for ``adjacency`` is the binaries that set states.
    """
    rows = []
    for method, source in PIECEWISE.items():
        table = sidecar_for(source)
        spec = to_spec(source)
        stated = equations(to_markdown(spec, symbols=table, numbered=False))
        written = equations(to_markdown(spec.expand('piecewise'), symbols=table, numbered=False))
        found = [
            block
            for block in declarations(source.read_text())['piecewise']
            if (block.field('method') or 'adjacency') == method
        ]
        assert found, f'{source.name} declares no piecewise block with method: {method}'
        for block in found:
            row = _row(block, stated)
            caption = (
                f'**`method: {method}`** \N{EM DASH} {PIECEWISE_METHODS[method]}, in `{source.relative_to(ROOT)}`.'
            )
            derived = [math for label, math in stated.items() if label.startswith(f'{block.name} ')]
            assumed = '\n\n'.join(['What the method assumes of the numbers bound to it:', *derived]) if derived else ''
            rows.append(
                row.replace('\n\n', f'\n\n{caption}\n\n{_table_shown(table)}', 1)
                + f'\n\n{_written_out(block.name, written)}'
            )
            if assumed:
                rows.append(assumed)
    return rows


def _written_out(name: str, printed: dict[str, str]) -> str:
    """The rows the formulation *name* states, as its expansion prints them.

    Everything an expansion writes is named after the block that stated it, so
    the block's own name is what collects the lines back together. The set a
    ``sos2`` curve keeps takes that name whole.
    """
    rows = [math for label, math in printed.items() if label == name or label.startswith(f'{name}_')]
    assert rows, f'{name} states rows and its expansion printed none of them'
    body = '\n\n'.join(rows)
    return f'Written out by `spec.expand()`:\n\n{body}'


def _table_shown(table: Path | None) -> str:
    """The symbol table, printed beside the math it renamed.

    A curve prints through its breakpoint parameters, whose names are the data
    preparation's rather than the literature's. Renaming them in the typesetter
    would be a symbol a reader could not trace back to the file, so the rename
    is a **declaration** — the same ``--symbols`` sidecar any reader may write —
    and the page shows it rather than performing it.
    """
    if table is None:
        return ''
    body = without_header(table)
    return (
        f'Rendered with the sidecar symbol table `{table.relative_to(ROOT)}`, '
        f'which is what the breakpoints print as:\n\n```yaml\n{body}\n```\n\n'
    )


def _row(declaration: Declaration, printed: dict[str, str]) -> str:
    """One construct: what it says, what it is for, and what it prints."""
    caption = f'{declaration.caption}\n\n' if declaration.caption else ''
    assert declaration.name in printed, f'{declaration.name} declares math and the walk printed none of it'
    math = printed[declaration.name]
    return f'#### `{declaration.name}`\n\n{caption}```yaml\n{declaration.yaml}\n```\n\n{math}'


def rendered_page(page: str) -> str:
    return splice(page, BEGIN, END, block())


def main(argv: list[str] | None = None) -> int:
    return page_main(argv, {PAGE: rendered_page}, 'notation')


if __name__ == '__main__':
    raise SystemExit(main())
