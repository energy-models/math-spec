# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The operator reference's operators, each shown as the math it prints.

    pixi run python -m tools.spec_math           # rewrite the block
    pixi run python -m tools.spec_math --check   # fail if it has drifted

The operator table above the block says what each operator *does*, in prose.
This says what each one *looks like*, and it is generated for a reason beyond
the usual one: the three ``shift`` rows differ only at the boundary, and the
three renderings that make them distinguishable are a property of
:mod:`math_spec.typeset.walk` rather than of this page. Printed side by side, two
operators that render the same are visible at a glance — which is exactly the
bug class #830 fixed, three times over.

Every cell comes from a **model**, one per row, under ``examples/operators/``.
That is what makes the block a check rather than a picture: a row whose
operator changed shape stops loading, in CI, in the same run that would
otherwise have shipped the old math. Rendering a fragment instead would only
have proved that a string still formats.

``OPERATORS`` keys are the table's own first cells, verbatim, so
``tests/test_docs_site.py`` can hold the two lists to each other: an operator
added to the language and to the table but not given a probe fails there rather
than quietly rendering a section that claims to be all of them.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from math_spec.typeset import to_markdown
from tools import pages

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / 'docs' / 'reference' / 'language' / 'operators.md'
PROBES = ROOT / 'examples' / 'operators'
BEGIN, END = '<!-- operator-math:begin -->', '<!-- operator-math:end -->'

#: The operator-table row -> the model that renders it. The key is that
#: table's first cell verbatim, which is the whole coupling: it cannot be
#: edited on one side alone without a test noticing.
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
    """One probe's constraint, and any notes its notation needs.

    A probe declares exactly one constraint, so "the equation this operator
    prints" is unambiguous — and the assertion says so rather than silently
    taking the first of several.
    """
    page = to_markdown(PROBES / f'{name}.yaml', numbered=False)
    equations = [line for line in _section(page, 'Subject to').splitlines() if line.startswith('$$')]
    assert len(equations) == 1, f'{name}.yaml should declare exactly one constraint; it rendered {len(equations)}'
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


def table_operators() -> list[str]:
    """The first cell of every row of the operator table, in order.

    Read back out of the page rather than kept beside :data:`OPERATORS`,
    because the point is to catch the two disagreeing.
    """
    table = PAGE.read_text()
    table = table[table.index('| Operator | Result |') :]
    table = table[: table.index('\n\n')]
    rows = [line for line in table.splitlines()[2:] if line.startswith('|')]
    return [row.split('|')[1].strip().strip('`') for row in rows]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--check', action='store_true', help='fail if the committed block has drifted')
    opts = ap.parse_args(argv)

    updated = pages.rewrite(PAGE.read_text(), BEGIN, END, block())
    return pages.update({PAGE: updated}, check=opts.check, tool='tools.spec_math', subject='the operator probes')


if __name__ == '__main__':
    raise SystemExit(main())
