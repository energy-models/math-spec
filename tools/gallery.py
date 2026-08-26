# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The example gallery: each model in `examples/`, beside the math it prints.

    pixi run python -m tools.gallery           # rewrite the pages' blocks
    pixi run python -m tools.gallery --check   # fail if one has drifted

The prose above each block is the page's own. Only the fenced model and the
math below it are written from here.
"""

from __future__ import annotations

import ast
import json
import re
import textwrap
from functools import partial
from typing import TYPE_CHECKING

from math_spec import load_model
from math_spec.typesetting import to_markdown
from tools._page import ROOT, splice, without_header
from tools._page import main as page_main
from tools.spec_math import OPERATORS, PROBES, _section, rendered_probe

if TYPE_CHECKING:
    from pathlib import Path

PAGES = ROOT / 'docs' / 'examples'
BEGIN, END = '<!-- gallery:begin -->', '<!-- gallery:end -->'

#: Page -> the model it shows. One model per page, because a gallery of
#: fragments is what the reference pages already are.
MODELS = {
    'dispatch.md': ROOT / 'examples' / 'dispatch.yaml',
}

#: Page -> (the model, how it prints), shown a **declaration** at a time: the
#: YAML of one constraint, then the equation it renders. For a model that
#: states someone else's — PyPSA's — the question a reader brings is "where is
#: *this* row", so each block is headed by the name the other side gives it,
#: read from the declaration's own description.
DECLARED = {
    'pypsa.md': (ROOT / 'examples' / 'pypsa.yaml', ROOT / 'examples' / 'symbols' / 'pypsa.yaml'),
    'pypsa_quadratic.md': (
        ROOT / 'examples' / 'pypsa_quadratic.yaml',
        ROOT / 'examples' / 'symbols' / 'pypsa_quadratic.yaml',
    ),
}

#: One PyPSA reference network per rung of the declared page, run out of band
#: with the versions each script pins; `references.json` beside them holds
#: what each solve recorded. The page shows the shared spine once and, under
#: each rung's table, the data the rung's own folder adds — the YAML and the
#: instance it binds, side by side.
REFERENCES = ROOT / 'examples' / 'references' / 'pypsa'


def model_block(path: Path) -> str:
    """One model, then the whole document the typesetter prints from it."""
    return f'```yaml\n{without_header(path)}\n```\n\n{to_markdown(path, numbered=False).strip()}'


def probe_block() -> str:
    """Every operator probe: the model, then the one equation it renders."""
    parts = []
    for signature, name in OPERATORS.items():
        equation, _ = rendered_probe(name)
        parts.append(
            f'### `{signature}`\n\n'
            f'`examples/operators/{name}.yaml`\n\n'
            f'```yaml\n{without_header(PROBES / f"{name}.yaml")}\n```\n\n'
            f'{equation}'
        )
    return '\n\n'.join(parts)


def declaration(text: str, section: str, name: str | None = None) -> str:
    """One declaration as written: ``section:`` itself, or ``name:`` under it."""
    lines = text.splitlines()
    i = lines.index(f'{section}:')
    if name is not None:
        i = next(k for k in range(i + 1, len(lines)) if lines[k].startswith(f'  {name}:'))
    deeper = '    ' if name is not None else '  '
    j = i + 1
    while j < len(lines) and (lines[j].startswith(deeper) or not lines[j].strip()):
        j += 1
    return textwrap.dedent('\n'.join(lines[i:j])).rstrip()


def _equation(subject: str, name: str) -> str:
    """The display equation the typesetter printed for constraint *name*."""
    body = subject[subject.index(f'**`{name}`**') :]
    return next(line for line in body.splitlines() if line.startswith('$$'))


def _stands_for(name: str, description: str | None) -> str:
    """The other side's name for a declaration — the backticked opening of its description."""
    found = re.match(r'`([^`]+)`', description or '')
    if found is None:
        msg = (
            f'{name}: a declaration on a declared page opens its description with the name it stands for, in backticks'
        )
        raise ValueError(msg)
    return found.group(1)


def declared_block(path: Path, symbols: Path) -> str:
    """The legend, the objective, then every constraint as YAML beside its equation."""
    text = without_header(path)
    page = to_markdown(path, symbols=symbols, numbered=False)
    legend = page[: page.index('#### Objective')].strip()
    objective = _section(page, 'Objective').strip()
    subject = _section(page, 'Subject to')
    domains = _section(page, 'Variable domains').strip()
    parts = [
        legend,
        f'### Objective\n\n```yaml\n{declaration(text, "objective")}\n```\n\n{objective.removeprefix("#### Objective").strip()}',
    ]
    for name, block in load_model(path).constraints.items():
        parts.append(
            f'### `{_stands_for(name, block.description)}`\n\n'
            f'`{name}`\n\n'
            f'```yaml\n{declaration(text, "constraints", name)}\n```\n\n'
            f'{_equation(subject, name)}'
        )
    parts.append(domains)
    return '\n\n'.join(parts)


def _story(script: Path) -> str:
    """The fixture's narrative — ``build()``'s docstring, as prose."""
    tree = ast.parse(script.read_text())
    build = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'build')
    story = ast.get_docstring(build)
    if story is None:
        msg = f"{script.name}: build() carries the fixture's story in its docstring, and the page shows it"
        raise ValueError(msg)
    return story


def _folder(name: str) -> str:
    """Every table in ``data/<name>/``, verbatim — the file is the artifact under review."""
    return '\n\n'.join(
        f'`data/{name}/{path.name}`\n\n```csv\n{path.read_text().strip()}\n```'
        for path in sorted((REFERENCES / 'data' / name).glob('*.csv'))
    )


def reference_block(stem: str) -> str:
    """A rung's oracle: the recorded solve, then the data its folder adds to the spine."""
    recorded = json.loads((REFERENCES / 'references.json').read_text())[stem]
    rows = sum(recorded['rows'].values())
    parity = recorded.get('parity', {})
    agreement = (
        f' `lpspec {parity["lpspec"]}` binds `{parity["model"]}` against the same network and lands on the'
        ' same objective (`parity.py`).'
        if parity.get('matches')
        else ''
    )
    return (
        f"> ✔ `pypsa {recorded['pypsa']}` solves this rung's reference network through its own linopy model "
        f'at objective `{recorded["objective"]}`, {rows} rows — recorded by '
        f'`examples/references/pypsa/{stem}.py`.{agreement}'
        f'{f" Its instance is `data/base/` plus `data/{stem}/`." if agreement else ""}\n'
        '\n'
        '<details markdown="1">\n'
        '<summary>What this rung adds, as data</summary>\n'
        '\n'
        f'{_story(REFERENCES / f"{stem}.py")}\n'
        '\n'
        f'{_folder(stem)}\n'
        '\n'
        '</details>'
    )


def spine_block() -> str:
    """The shared spine, shown once, under the one sentence of how folders combine."""
    return (
        "> Every rung's network is the spine below plus the rung's own folder of additions, read by"
        ' `examples/references/pypsa/instances.py`. Folders combine by appending rows, table by table: each row'
        " keeps its own file's columns and becomes one `n.add`, so no table is column-joined and no empty cells"
        " are invented — a blank cell is an attribute the row does not set, PyPSA's default. The one"
        ' cross-folder touch is `timeseries.csv`, which may put a schedule on a spine component.\n'
        '\n'
        '<details markdown="1">\n'
        '<summary>The shared spine, <code>data/base/</code></summary>\n'
        '\n'
        f'{_folder("base")}\n'
        '\n'
        '</details>'
    )


def with_references(page: str, text: str) -> str:
    """Every reference script's block whose marker pair is on this page.

    A rung's marker lives on whichever declared page carries its section, so a
    stem absent here is another page's; a stem on no page at all is what
    ``tests/test_pypsa_references.py`` says out loud. The spine's own marker
    pair lives on the page that carries the rung ladder.
    """
    begin, end = '<!-- reference:spine:begin -->', '<!-- reference:spine:end -->'
    if begin in text and end in text:
        text = splice(text, begin, end, spine_block())
    for script in sorted(REFERENCES.glob('rung*.py')):
        begin, end = f'<!-- reference:{script.stem}:begin -->', f'<!-- reference:{script.stem}:end -->'
        if begin in text and end in text:
            text = splice(text, begin, end, reference_block(script.stem))
    return text


def block(page: str) -> str:
    if page == 'operators.md':
        return probe_block()
    if page in DECLARED:
        return declared_block(*DECLARED[page])
    return model_block(MODELS[page])


def rendered(page: str, text: str) -> str:
    text = splice(text, BEGIN, END, block(page))
    if page in DECLARED:
        text = with_references(page, text)
    return text


def pages() -> list[str]:
    return [*MODELS, *DECLARED, 'operators.md']


def main(argv: list[str] | None = None) -> int:
    return page_main(argv, {PAGES / page: partial(rendered, page) for page in pages()}, 'gallery')


if __name__ == '__main__':
    raise SystemExit(main())
