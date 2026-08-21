# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The notation reference: every construct beside the math it prints.

    uv run python -m tools.notation           # rewrite the page's block
    uv run python -m tools.notation --check   # fail if it has drifted

The page exists to be *read as a whole*. Whether a notation is good is a
question about the set of it — whether two constructs that mean different
things look different, whether a symbol introduced in one place is the one used
in another — and that question cannot be asked of a gallery page showing one
model, or of an operator table showing one row each. So the page shows every
construct at once, and each row carries the YAML that produced it, because
notation is judged against what it is standing for.

The source is ``tests/typeset/golden/model.yaml``, the one model that carries every
construct. Not a corpus written for this page: a second exhaustive model is a
second thing to keep exhaustive, and the fixture's completeness is already
enforced — ``tests/typeset/test_typeset.py`` holds it to the language's operator set,
its node kinds, and every line of :mod:`math_spec.typeset.walk`. That chain is
what lets this page claim *every*: the guards say the fixture omits no
construct, and this tool emits a row for every declaration in the fixture.

The fixture's own case-label comments become the captions, so what a row is
*for* is written where the case is, and moving the case moves its caption.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from math_spec.model import PIECEWISE_METHODS
from math_spec.typeset import to_markdown

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / 'docs' / 'reference' / 'notation.md'
MODEL = ROOT / 'tests' / 'typeset' / 'golden' / 'model.yaml'

#: One model per ``method:``, because the three expand to three different
#: formulations and a section showing one of them would be showing a third of
#: the construct. ``tests/test_docs_site.py`` holds these keys to
#: :data:`math_spec.model.PIECEWISE_METHODS`, so a method added to the
#: language arrives here or the page stops claiming to be all of them.
#:
#: They come from real models rather than from the fixture because expanding a
#: curve round-trips the model through ``model_dump``, which drops a bound of
#: ``.inf`` on the wrong side of the line — the one thing that makes the walk
#: print ∞ — so a fixture carrying a curve would stop covering two symbols.
PIECEWISE = {
    'adjacency': ROOT / 'examples' / 'ports' / 'transport_pwl.yaml',
    'sos2': ROOT / 'examples' / 'sos.yaml',
    'convex': ROOT / 'examples' / 'piecewise.yaml',
    'lp': ROOT / 'examples' / 'piecewise_lp.yaml',
}
BEGIN, END = '<!-- notation:begin -->', '<!-- notation:end -->'

#: The blocks that declare math, in the order the page walks them, and the
#: heading each gets. ``dimensions``, ``lookups`` and ``parameters`` are absent
#: on purpose: they declare no equation, and what they print is the legend,
#: which the page shows once as a legend rather than a row at a time.
SECTIONS = {
    'objective': 'The objective',
    'constraints': 'Constraints',
    'variables': 'Variable domains',
    'piecewise': 'Curves, as what they expand to',
    'sos': 'Sets carried to the solver',
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
    """Label -> the ``$$…$$`` block the walk printed for it.

    The objective's line carries no label — the block has no name — so it is
    keyed by the section it is the only member of.
    """
    found = {}
    label = 'objective'
    for block in rendered.split('\n\n'):
        if match := re.fullmatch(r'\*\*`(.+)`\*\*', block.strip()):
            label = match[1]
        elif block.startswith('$$'):
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
DECLARED = ('dimensions', 'lookups', 'parameters')


def preamble(text: str) -> str:
    """The fixture's ``dimensions``/``lookups``/``parameters`` blocks, verbatim."""
    blocks = []
    for name in DECLARED:
        body = text[text.index(f'\n{name}:') + 1 :]
        end = re.search(r'\n(?=\w)', body)
        blocks.append(body[: end.start()] if end else body)
    return '\n'.join(blocks).strip()


#: What each section says about itself, where the section needs saying.
NOTES = {
    'piecewise': (
        'A curve is sugar: what prints is the formulation it expands to, which is the math the solver '
        'receives. One row per `method:`, each from the model named under it, so the symbols in this '
        "section are that model's."
    ),
}


def block() -> str:
    """The page's generated half: the legend, then every declaration in turn."""
    rendered = to_markdown(MODEL, numbered=False)
    parts = [
        '### The legend',
        'A dimension, a lookup and a parameter declare no equation; what they '
        'print is the legend every model opens with.',
        f'```yaml\n{preamble(MODEL.read_text())}\n```',
        legend(rendered),
    ]
    printed = equations(rendered)
    for section, title in SECTIONS.items():
        parts.append(f'### {title}')
        if note := NOTES.get(section):
            parts.append(note)
        if section == 'piecewise':
            parts += _curves()
            continue
        parts += [_row(found, printed) for found in declarations(MODEL.read_text())[section]]
    return '\n\n'.join(parts)


def _curves() -> list[str]:
    """One row per ``method:``, each captioned with what that method restricts."""
    rows = []
    for method, source in PIECEWISE.items():
        printed = equations(to_markdown(source, numbered=False))
        found = [block for block in declarations(source.read_text())['piecewise'] if _method(block) == method]
        assert found, f'{source.name} declares no piecewise block with method: {method}'
        for block in found:
            row = _row(block, printed)
            caption = f'**`method: {method}`** --- {PIECEWISE_METHODS[method]}, in `{source.relative_to(ROOT)}`.'
            rows.append(row.replace('\n\n', f'\n\n{caption}\n\n', 1))
    return rows


def _method(block: Declaration) -> str:
    """The block's ``method:``, or the default the language gives it."""
    return block.field('method') or 'adjacency'


def _row(declaration: Declaration, printed: dict[str, str]) -> str:
    """One construct: what it says, what it is for, and what it prints."""
    caption = f'{declaration.caption}\n\n' if declaration.caption else ''
    math = '\n\n'.join(printed[label] for label in _labels(declaration, printed))
    return f'#### `{declaration.name}`\n\n{caption}```yaml\n{declaration.yaml}\n```\n\n{math}'


def _labels(declaration: Declaration, printed: dict[str, str]) -> list[str]:
    """Which printed equations belong to *declaration*.

    Two blocks do not print under their own name. A ``sos:`` block restricts a
    variable, so its line sits with that variable; a ``piecewise:`` block is
    sugar, and what prints is the rows and columns it expands to — every one of
    which the expander names after the block. A declaration printing nothing is
    an error rather than an empty row: it means the walk stopped rendering
    something the file still declares.
    """
    if declaration.name in printed:
        return [declaration.name]
    if (variable := declaration.field('variable')) and f'{variable} sos' in printed:
        return [f'{variable} sos']
    expanded = [label for label in printed if label.startswith(f'{declaration.name}_')]
    assert expanded, f'{declaration.name} declares math and the walk printed none of it'
    return expanded


def rendered_page(page: str) -> str:
    i, j = page.index(BEGIN) + len(BEGIN), page.index(END)
    return page[:i] + '\n' + block() + '\n' + page[j:]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--check', action='store_true', help='fail if the committed block has drifted')
    opts = ap.parse_args(argv)

    page = PAGE.read_text()
    updated = rendered_page(page)
    if opts.check:
        if updated != page:
            print(f'{PAGE.relative_to(ROOT)} is stale — run `uv run python -m tools.notation`', file=sys.stderr)
            return 1
        print(f'{PAGE.relative_to(ROOT)} matches the model')
        return 0
    PAGE.write_text(updated)
    print(f'wrote {PAGE.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
