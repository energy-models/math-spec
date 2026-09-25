# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""The notation reference: every construct beside the math it prints.

    pixi run python -m tools.notation           # rewrite the page's block
    pixi run python -m tools.notation --check   # fail if it has drifted

The source is ``tests/typesetting/golden/model.yaml``, the one spec that
carries every construct — ``tests/typesetting/test_golden.py`` holds it to the
language, and this tool emits a row for every declaration in it. The fixture's
own case-label comments become the captions; :data:`FAMILIES` gives each row
its heading and its place on the page.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from mathspec.spec import PIECEWISE_METHODS
from mathspec.typesetting import to_markdown
from mathspec.validation import to_spec
from tools._page import ROOT, sidecar_for, splice, without_header
from tools._page import main as page_main

if TYPE_CHECKING:
    from pathlib import Path
PAGE = ROOT / 'docs' / 'reference' / 'notation.md'
MODEL = ROOT / 'tests' / 'typesetting' / 'golden' / 'model.yaml'

#: One spec per ``method:``, because the four restrict the weights four
#: different ways and a section showing one of them would be showing a quarter
#: of the construct. ``tests/test_docs.py`` holds these keys to
#: :data:`mathspec.spec.PIECEWISE_METHODS`, so a method added to the
#: language arrives here or the page stops claiming to be all of them.
#:
#: They come from real specs rather than from the fixture because a caption
#: saying what a method is for reads against a spec that had a reason to
#: choose it.
PIECEWISE = {
    'adjacency': ('Adjacency method', ROOT / 'examples' / 'ports' / 'transport_pwl.yaml'),
    'sos2': ('SOS2 method', ROOT / 'examples' / 'sos.yaml'),
    'convex': ('Convex method', ROOT / 'examples' / 'piecewise.yaml'),
    'lp': ('LP method', ROOT / 'examples' / 'piecewise_lp.yaml'),
}
BEGIN, END = '<!-- notation:begin -->', '<!-- notation:end -->'

#: The blocks of the fixture that declare math. ``dimensions``, ``relations``
#: and ``parameters`` are absent on purpose: they declare no equation, and what
#: they print is the legend, which the page shows once rather than a row at a
#: time.
BLOCKS = ('objective', 'constraints', 'expressions', 'variables', 'piecewise', 'sos', 'assumptions')

#: The page's sections in the order of the language reference, and in each the
#: fixture's declarations under the construct they show. The declaration name
#: is the fixture's and no reader searches for it, so it stays in the YAML and
#: the heading names the construct. Within a section the order is the file's
#: wherever a caption reads against the row above it ("its adjoint", "the same
#: window"). Every declaration of the fixture is here exactly once, or the
#: tool refuses to write the page.
FAMILIES: dict[str, dict[str, str]] = {
    'Variable domains': {
        'p': 'Lower and upper bounds',
        'spill': 'Lower bound only',
        'slack': 'Upper bound only',
        'theta': 'Unbounded variable',
        'on': 'Binary domain',
        'units': 'Bounded integer domain',
        'spare': 'Unbounded integer domain',
        'reserve': 'Scalar variable',
        'headroom': 'Scalar variable with a condition',
        'weight': 'Variable in a special ordered set',
        'fuel': 'Second axis of a curve',
        'heat': 'Third axis of a curve',
        'op_cost': 'Variable bounded by a curve',
        'warm': 'Binary variable with a condition',
    },
    'Objective': {
        'objective': 'Products and powers in the objective',
    },
    'Relations': {
        'balance': 'Sum through a relation',
        'total': 'Sum over every dimension',
        'pullback': '`at` through a relation',
        'grouped_once': 'Sum into two value columns',
        'pulled_back_once': '`at` through two value columns',
        'within_bus': 'Shift within one value column',
        'relational': 'Sum through a bare relation',
        'connected': 'Bare relation as a condition',
        'representative': 'Map into its own dimension',
        'zonal': 'Sum through a two-key map',
        'zonal_history': 'Sum over the other key of a two-key map',
        'zonal_membership': 'Sum between the two keys of a map',
        'zonal_pullback': '`at` through a two-key map',
    },
    'Arithmetic and literals': {
        'arithmetic': 'Signs, division and number literals',
        'efficiency': 'Greek parameter name',
        'ceiling': 'Infinity literal',
    },
    'Named expressions': {
        'budgeted': 'Plain expression in a constraint',
        'netted': 'Signed sum substituted into a plus',
        'starts': 'Cased expression in a constraint',
        'spend': 'Plain named expression',
        'net': 'Plain expression that is a signed sum',
        'startup_cost': 'Expression defined by cases',
        'spend_cap': 'Data-only expression',
        'capped': 'Named expression in a condition',
        'lcoe': 'Reported expression',
        'marginal_price': 'Dual of a constraint',
    },
    'Shifts': {
        'ramp': 'Cyclic and acyclic shift',
        'edges': 'Filled and forward shifts',
        'ahead': 'Cyclic forward shift',
        'composed': 'Composed shifts',
        'uncomposed': 'Nested shifts that do not compose',
        'crossed': 'Shift along two dimensions',
        'lead_time': 'Shift by a parameter offset',
        'in_season': 'Cyclic shift within a group',
        'held_in_season': 'Filled shift within a group',
    },
    'Trailing windows': {
        'window': 'Window of fixed width',
        'history': 'Window with a parameter width',
        'seasonal_window': 'Window within a group',
    },
    'Piecewise curves': {},
    'Special ordered sets': {
        'adjacent': 'Special ordered set of type 2',
    },
    'Assumptions': {
        'bounds_do_not_cross': 'Two parameters compared',
        'efficiency_is_a_fraction': 'Connective in an assumption',
        'lead_times_are_short': 'Parameter compared to a literal',
        'zones_agree': 'Two relations compared',
        'budget_covers_the_peak': 'Reduction in an assumption',
        'ramps_are_gentle': 'Shift in an assumption',
        'flexible_units_have_headroom': 'Assumption with a boolean condition',
        'northern_demand_is_real': 'Assumption with a relation condition',
    },
    'Where conditions': {
        'scalar': 'Parameter as a condition',
        'running': 'Variable and label conditions',
        'first': 'Position in a dimension',
        'last': 'Position counted from the end',
        'northern': 'Relation compared to a label',
        'always': 'Constant true condition',
        'redundant': 'Constant true inside a condition',
        'never': 'Constant false condition',
        'margin': 'Comparison of two expressions',
        'ramped': 'Shift and pullback in a condition',
        'covered': 'Reduction in a scalar condition',
        'counted': 'Count over a dimension',
        'counted_here': 'Count along a dimension of the frame',
        'run_start': 'Predicate at the previous coordinate',
        'zoned': 'Predicate through a relation',
    },
}

#: Declarations whose caption says nothing its heading does not, so the page
#: prints the heading alone.
NAMED_BY_HEADING = frozenset({'spill', 'slack', 'theta', 'balance'})


class Declaration:
    """One block of the fixture: its name, the block it sits in, its YAML, and the caption beside it."""

    def __init__(self, name: str, block: str, lines: list[str], caption: str) -> None:
        self.name, self.block, self.lines, self.caption = name, block, lines, caption

    def field(self, key: str) -> str:
        """One scalar the block declares — ``''`` where it declares no such key."""
        for line in self.lines:
            if match := re.match(rf'^\s+{key}:\s*(\S+)', line):
                return match[1]
        return ''

    @property
    def yaml(self) -> str:
        """The declaration under the key of its block, with the caption comment removed.

        The key is kept because the heading names the construct rather than
        the block, and a section mixes blocks: the fragment is where a reader
        sees whether the row is a constraint, an expression or a variable.
        """
        kept = [line for line in self.lines if not _described(line, self.lines)]
        kept[0] = re.sub(r'[ ]+#.*$', '', kept[0])
        key = [] if self.block == 'objective' else [f'{self.block}:']
        return '\n'.join([*key, *kept])


def _described(line: str, lines: list[str]) -> bool:
    """Whether *line* belongs to a ``description:`` — prose, not notation.

    A row is a construct beside its math, and a paragraph arguing for the
    modelling choice is neither. The specs the curve rows come from are real
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
    found: dict[str, list[Declaration]] = {section: [] for section in BLOCKS}
    section, current = None, None
    for line in text.splitlines():
        if match := re.match(r'^(\w+):', line):
            section = match[1] if match[1] in BLOCKS else None
            current = None
            if section == 'objective':
                current = Declaration('objective', section, [line], _caption(line))
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
            current = Declaration(match[1], section, [line], _caption(line))
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
    """The tables and the translation notes, without the spec's description.

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
    """The page's generated half: the legend, then every construct in its family."""
    rendered = to_markdown(MODEL, numbered=False)
    parts = [
        '### Legend',
        'A dimension, a relation and a parameter declare no equation; what they '
        'print is the legend every spec opens with.',
        f'```yaml\n{preamble(MODEL.read_text())}\n```',
        legend(rendered),
    ]
    printed = equations(rendered)
    written = equations(to_markdown(to_spec(MODEL).expand('sos'), numbered=False))
    found = {
        one.name: one
        for section, ones in declarations(MODEL.read_text()).items()
        if section != 'piecewise'
        for one in ones
    }
    placed = [name for rows in FAMILIES.values() for name in rows]
    twice = sorted({name for name in placed if placed.count(name) > 1})
    assert set(placed) == set(found) and not twice, (
        f'every declaration of the fixture has one heading in FAMILIES: missing '
        f'{sorted(set(found) - set(placed))}, not in the fixture {sorted(set(placed) - set(found))}, twice {twice}'
    )
    for family, rows in FAMILIES.items():
        parts.append(f'### {family}')
        if family == 'Piecewise curves':
            parts.append(
                'A curve prints as the curve it states, over the frame the block builds one per coordinate of, '
                'and its expansion prints the rows that curve stands for. One row per `method:`, each from the '
                "spec named under it, so the symbols in this section are that spec's."
            )
            parts += _curves()
            continue
        if family == 'Special ordered sets':
            parts.append(
                'A set prints beside the variable it restricts, because it restricts that variable rather than '
                'adding a row of its own. Under it are the rows it is written out as.'
            )
            parts += [
                f'{_row(found[name], heading, printed)}\n\n{_written_out(name, written)}'
                for name, heading in rows.items()
            ]
            continue
        parts += [_row(found[name], heading, printed) for name, heading in rows.items()]
    page = '\n\n'.join(parts)
    headings = re.findall(r'^#{3,4} (.+)$', page, re.MULTILINE)
    shared = sorted({heading for heading in headings if headings.count(heading) > 1})
    assert not shared, f'two sections share a heading, so one anchor is lost: {shared}'
    return page


def _curves() -> list[str]:
    """One row per ``method:``, each captioned with what that method restricts.

    Both readings come from one spec and one symbol table: the block as the
    file states it, and the rows ``expand('piecewise')`` writes out — which for
    ``sos2`` keeps the set and for ``adjacency`` is the binaries that set states.
    """
    rows = []
    for method, (heading, source) in PIECEWISE.items():
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
            row = _row(block, heading, stated)
            caption = f'`method: {method}` \N{EM DASH} {PIECEWISE_METHODS[method]}, in `{source.relative_to(ROOT)}`.'
            derived = [math for label, math in stated.items() if label.startswith(f'{block.name} ')]
            assumed = (
                '\n\n'.join(['What the method assumes of the numbers attached to it:', *derived]) if derived else ''
            )
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


def _row(declaration: Declaration, heading: str, printed: dict[str, str]) -> str:
    """One construct: what it is called, what it is for, what it says, and what it prints."""
    shown = declaration.caption and declaration.name not in NAMED_BY_HEADING
    caption = f'{declaration.caption}\n\n' if shown else ''
    assert declaration.name in printed, f'{declaration.name} declares math and the walk printed none of it'
    math = printed[declaration.name]
    return f'#### {heading}\n\n{caption}```yaml\n{declaration.yaml}\n```\n\n{math}'


def rendered_page(page: str) -> str:
    return splice(page, BEGIN, END, block())


def main(argv: list[str] | None = None) -> int:
    return page_main(argv, {PAGE: rendered_page}, 'notation')


if __name__ == '__main__':
    raise SystemExit(main())
