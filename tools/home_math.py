# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The homepage's model and the math under it, from one file.

    pixi run python -m tools.home_math           # rewrite every block
    pixi run python -m tools.home_math --check   # fail if one has drifted

``examples/dispatch.yaml`` is printed once and spliced into two pages that need
different shapes for it. GitHub renders the Markdown math but not a tabbed
block, so ``README.md`` takes the equations with the other two formats folded
under them, and ``docs/index.md`` takes tabs, plus a third tab holding the call
that produced the other two.
"""

from __future__ import annotations

import textwrap

from math_spec import to_spec
from math_spec.typesetting import to_latex, to_markdown, to_typst
from tools._page import ROOT, sidecar_for, splice, without_header
from tools._page import main as page_main

PAGE = ROOT / 'docs' / 'index.md'
README = ROOT / 'README.md'
MODEL = ROOT / 'examples' / 'dispatch.yaml'
BEGIN, END = '<!-- home-math:begin -->', '<!-- home-math:end -->'
README_BEGIN, README_END = '<!-- readme-math:begin -->', '<!-- readme-math:end -->'
#: The snippet markers `pymdownx.snippets` reads, which is how the same YAML
#: reaches the site without being typed twice.
MODEL_BEGIN, MODEL_END = '<!--- --8<-- [start:model] -->', '<!--- --8<-- [end:model] -->'

#: The tab that is written rather than rendered: how the two beside it were
#: produced. It carries the symbol table as a dict because that is the shortest
#: spelling of it, and the sidecar file the repository actually uses is one
#: line further down.
HOW = """```python
import math_spec as ms

symbols = {
    'notation': 'latex',
    'dimensions': {
        'snapshot': {'index': 's', 'set': '\\\\mathcal{S}'},
        'generator': {'index': 'g', 'set': '\\\\mathcal{G}'},
    },
    'names': {
        'cost': 'c',
        'load': '\\\\ell',
        'capacity': '\\\\bar p',
    },
}

spec = ms.to_spec('dispatch.yaml')  # read and checked once, then printed three ways

ms.to_latex(spec, symbols=symbols)  # amsmath align
ms.to_typst(spec)  # compiles without a TeX toolchain
ms.to_markdown(spec)  # renders as-is on GitHub
```

`symbols` gives every name its conventional spelling. Pass a dict, a YAML path
or a `SymbolTable`. It is optional: drop it and the same model prints from the
names in the file, as $\\mathrm{load}_t$ and $\\mathrm{capacity}_g$.

Or from a shell, where the table is that same YAML on disk. `--standalone` emits
a document that compiles, rather than a fragment to `\\input`:

```bash
python -m math_spec latex dispatch.yaml --symbols dispatch.symbols.yaml
python -m math_spec typst dispatch.yaml --standalone -o dispatch.typ
```

[Typeset the math](reference/typeset.md) documents the three functions, their
options and symbol tables. Each reads the same file every other page here
loads."""


def tab(title: str, body: str) -> str:
    """One tab of the block: its title, and its body indented into it."""
    return f'=== "{title}"\n\n{textwrap.indent(body, "    ")}'


def block() -> str:
    """The three tabs, in the order a reader meets them."""
    spec = to_spec(MODEL)
    symbols = sidecar_for(MODEL)
    printed = to_markdown(spec, symbols=symbols, numbered=False)
    latex = to_latex(spec, symbols=symbols, numbered=False)
    return '\n\n'.join(
        (
            tab('The math', printed.strip()),
            tab('LaTeX', f'```latex\n{latex.strip()}\n```'),
            tab('How', HOW),
        )
    )


def details(summary: str, body: str) -> str:
    """A folded block. GitHub reads what is inside as markdown only across a blank line."""
    return f'<details>\n<summary>{summary}</summary>\n\n{body}\n\n</details>'


def readme_block() -> str:
    """The equations GitHub renders, then the whole document folded under them.

    The visible block carries no legend and no symbol table, because a README
    is read before anything else: three legend tables are half its length, and
    a derived symbol is the file's own name, which needs no table to be read.
    The first fold is what the legend and a table add.

    Typst is printed with no table for a second reason: the sidecar is written
    in LaTeX, and a render in the other notation is refused.
    """
    spec = to_spec(MODEL)
    symbols = sidecar_for(MODEL)
    return '\n\n'.join(
        (
            to_markdown(spec, numbered=False, legend=False).strip(),
            details(
                'The whole document: a symbol table, and the legend it prints',
                to_markdown(spec, symbols=symbols, numbered=False).strip(),
            ),
            details(
                'The same document as LaTeX',
                f'```latex\n{to_latex(spec, symbols=symbols, numbered=False).strip()}\n```',
            ),
            details(
                'The same document as Typst, printed with no symbol table',
                f'```typst\n{to_typst(spec, numbered=False).strip()}\n```',
            ),
        )
    )


def rendered_readme(readme: str) -> str:
    """Prettier wants a blank line on each side of the markers, so each block carries them."""
    model = f'\n```yaml title="{MODEL.name}"\n{without_header(MODEL)}\n```\n'
    return splice(
        splice(readme, MODEL_BEGIN, MODEL_END, model),
        README_BEGIN,
        README_END,
        f'\n{readme_block()}\n',
    )


def rendered_page(page: str) -> str:
    """Prettier wants a blank line on each side of the markers, so the block carries them."""
    return splice(page, BEGIN, END, f'\n{block()}\n')


def main(argv: list[str] | None = None) -> int:
    return page_main(argv, {PAGE: rendered_page, README: rendered_readme}, 'home_math')


if __name__ == '__main__':
    raise SystemExit(main())
