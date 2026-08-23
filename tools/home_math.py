# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The homepage's model and the math block under it, from one file.

    pixi run python -m tools.home_math           # rewrite both blocks
    pixi run python -m tools.home_math --check   # fail if either has drifted

The homepage claims that a file says exactly this, with no data and no solver
in between. A block typed by hand would be that claim asserted; this one is the
claim executed — every symbol on the page came out of ``examples/dispatch.yaml``
and ``examples/symbols/dispatch.yaml`` on the commit being built, through the
same two functions the docs tell a reader to call.

Two files carry it, because the model has to be readable in both renderings:
``README.md`` holds the YAML, which the site pulls in as a snippet, and
``docs/index.md`` holds the math, which is a tabbed block and would be raw
markup on GitHub. Writing both from here is what stops the model shown from
drifting away from the model rendered.

The third tab is not rendered output but the call that produced the other two,
so the page never shows math without showing where it came from.
"""

from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

from math_spec.typeset import to_latex, to_markdown
from tools import pages

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / 'docs' / 'index.md'
README = ROOT / 'README.md'
MODEL = ROOT / 'examples' / 'dispatch.yaml'
SYMBOLS = ROOT / 'examples' / 'symbols' / 'dispatch.yaml'
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

ms.to_latex('dispatch.yaml', symbols=symbols)  # amsmath align
ms.to_typst('dispatch.yaml')  # compiles without a TeX toolchain
ms.to_markdown('dispatch.yaml')  # renders as-is on GitHub
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
    printed = to_markdown(MODEL, symbols=SYMBOLS, numbered=False)
    latex = to_latex(MODEL, symbols=SYMBOLS, numbered=False)
    return '\n\n'.join(
        (
            tab('The math', printed.strip()),
            tab('LaTeX', f'```latex\n{latex.strip()}\n```'),
            tab('How', HOW),
        )
    )


def model_block() -> str:
    """The model as the README shows it: the file, without its licence header.

    The header is the repository's, not the model's, and a reader meeting the
    language for the first time should not have to read past it.
    """
    lines = MODEL.read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() and not line.startswith('#'))
    return '```yaml title="{}"\n{}\n```'.format(MODEL.name, '\n'.join(lines[start:]).strip())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--check', action='store_true', help='fail if the committed block has drifted')
    opts = ap.parse_args(argv)

    written = {
        PAGE: pages.rewrite(PAGE.read_text(), BEGIN, END, block()),
        README: pages.rewrite(README.read_text(), MODEL_BEGIN, MODEL_END, model_block()),
    }
    return pages.update(written, check=opts.check, tool='tools.home_math', subject='the model')


if __name__ == '__main__':
    raise SystemExit(main())
