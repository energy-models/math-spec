# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The homepage's model and the math block under it, from one file.

    pixi run python -m tools.home_math           # rewrite both blocks
    pixi run python -m tools.home_math --check   # fail if either has drifted

Two files carry it: ``README.md`` holds the YAML, which the site pulls in as a
snippet, and ``docs/index.md`` holds the math, which is a tabbed block and
would be raw markup on GitHub. The third tab is the call that produced the
other two.
"""

from __future__ import annotations

import textwrap

from math_spec import to_spec
from math_spec.typesetting import to_latex, to_markdown
from tools._page import ROOT, sidecar_for, splice, without_header
from tools._page import main as page_main

PAGE = ROOT / 'docs' / 'index.md'
README = ROOT / 'README.md'
MODEL = ROOT / 'examples' / 'dispatch.yaml'
BEGIN, END = '<!-- home-math:begin -->', '<!-- home-math:end -->'
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
        'p_max': '\\\\bar p',
    },
}

spec = ms.to_spec('dispatch.yaml')  # read and checked once, then printed three ways

ms.to_latex(spec, symbols=symbols)  # amsmath align
ms.to_typst(spec)  # compiles without a TeX toolchain
ms.to_markdown(spec)  # renders as-is on GitHub
```

`symbols` is optional — drop it and the same model prints as
$\\mathit{load}_t$, $p^{\\mathrm{max}}_g$. A dict, a YAML path or a
`SymbolTable`; a key naming nothing in the model is an error, not a symbol that
silently never applies. Every spelling is printed verbatim — `notation` says
which language they are, and a render in the other one refuses.

Or from a shell, where the table is that same YAML on disk and `--standalone`
emits a document that compiles rather than a fragment to `\\input`:

```bash
python -m math_spec latex dispatch.yaml --symbols dispatch.symbols.yaml
python -m math_spec typst dispatch.yaml --standalone -o dispatch.typ
```

The renderer is [the typesetter](reference/typeset.md), and it reads the same
file every other page here loads."""


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


def rendered_readme(readme: str) -> str:
    """Prettier wants a blank line on each side of the markers, so the block carries them."""
    return splice(readme, MODEL_BEGIN, MODEL_END, f'\n```yaml title="{MODEL.name}"\n{without_header(MODEL)}\n```\n')


def rendered_page(page: str) -> str:
    """Prettier wants a blank line on each side of the markers, so the block carries them."""
    return splice(page, BEGIN, END, f'\n{block()}\n')


def main(argv: list[str] | None = None) -> int:
    return page_main(argv, {PAGE: rendered_page, README: rendered_readme}, 'home_math')


if __name__ == '__main__':
    raise SystemExit(main())
