# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The operator reference's operators, each shown as the math it prints.

    pixi run python -m tools.spec_math           # rewrite the block
    pixi run python -m tools.spec_math --check   # fail if it has drifted

Every cell comes from a **model**, one per row, under ``examples/operators/``:
a row whose operator changed shape stops loading, in the same run that would
otherwise have shipped the old math.
"""

from __future__ import annotations

from math_spec.typesetting import to_markdown
from tools._page import ROOT, splice
from tools._page import main as page_main

PAGE = ROOT / 'docs' / 'reference' / 'language' / 'operators.md'
PROBES = ROOT / 'examples' / 'operators'
BEGIN, END = '<!-- operator-math:begin -->', '<!-- operator-math:end -->'

#: The operator-table row -> the model that renders it. The key is that
#: table's first cell verbatim.
OPERATORS = {
    'sum(array)': 'sum_all',
    'sum(array, over=dim)': 'sum',
    'sum(array, by=lookup)': 'sum_by',
    'sum(array, by=[lookup, …])': 'sum_by_lookups',
    'at(array, by=lookup)': 'at',
    'shift(array, over=dim, offset=n)': 'shift',
    "shift(array, over=dim, offset=n, edge='wrap')": 'shift_wrap',
    'shift(array, over=dim, offset=n, edge=v)': 'shift_edge',
    'shift(array, over=dim, offset=p, edge=…)': 'shift_by_parameter',
    'shift(array, over=dim, offset=n, by=lookup)': 'shift_partitioned',
    'sum_back(array, over=dim, within=n)': 'sum_back',
    'sum_back(array, over=dim, within=p)': 'sum_back_by_parameter',
    "sum_back(array, over=dim, within=p, edge='wrap')": 'sum_back_wrap',
    'sum_back(array, over=dim, within=n, by=lookup)': 'sum_back_partitioned',
    'dual(constraint)': 'dual',
}


def _section(page: str, title: str) -> str:
    """The body under ``#### title``, up to the next heading of that level."""
    body = page[page.index(f'#### {title}') :]
    tail = body.find('\n#### ')
    return body if tail < 0 else body[:tail]


def _inline(display: str) -> str:
    """A ``$$…$$`` block as ``$…$``, which is what fits in a table cell."""
    return f'${display.strip().removeprefix("$$").removesuffix("$$").strip()}$'


def rendered_probe(name: str) -> tuple[str, list[str]]:
    """One probe's featured equation, and any notes its notation needs.

    A probe features exactly one equation — its single constraint, or, for an
    operator legal only after a solve (`dual`), its single ``Post-solve`` entry,
    whose constraint is scaffolding for the reference. The assertion says so
    rather than silently taking the first of several.
    """
    page = to_markdown(PROBES / f'{name}.yaml', numbered=False)
    title = 'Post-solve' if '#### Post-solve' in page else 'Subject to'
    equations = [line for line in _section(page, title).splitlines() if line.startswith('$$')]
    assert len(equations) == 1, f'{name}.yaml should feature exactly one equation; it rendered {len(equations)}'
    notes = [block.strip() for block in page.split('\n\n') if 'denotes' in block]
    return _inline(equations[0]), notes


def block() -> str:
    """The table, and one note for each symbol it introduces."""
    rows = ['| Operator | Renders as |', '|---|---|']
    notes: list[str] = []
    for signature, name in OPERATORS.items():
        equation, found = rendered_probe(name)
        rows.append(f'| `{signature}` | {equation} |')
        notes += [note for note in found if note not in notes]
    return '\n'.join(rows) + ''.join(f'\n\n{note}' for note in notes)


def rendered(page: str) -> str:
    return splice(page, BEGIN, END, block())


def main(argv: list[str] | None = None) -> int:
    return page_main(argv, {PAGE: rendered}, 'spec_math')


if __name__ == '__main__':
    raise SystemExit(main())
