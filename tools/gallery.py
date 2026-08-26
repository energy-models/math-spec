# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The example gallery: each model in `examples/`, beside the math it prints.

    pixi run python -m tools.gallery           # rewrite the pages' blocks
    pixi run python -m tools.gallery --check   # fail if one has drifted

The reference pages show what a *construct* prints; nothing showed a **model**.
A reader could see the equation `sum(by=)` renders as and never see a file that
declares one, which is the wrong way round for a language whose pitch is that
the file and the math are the same thing.

So each page is one model, in full, followed by the document the typesetter
prints from it. Generated for the reason the other two blocks are: math typed
into a page is math nothing checks, and this project has the renderer that
would have caught it.

The prose above each block is the page's own — what the model is for, and which
construct it is here to show. Only the fenced model and the math below it are
written from here.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from pathlib import Path

from math_spec import load_model
from math_spec.typesetting import to_markdown
from tools.spec_math import OPERATORS, _section, rendered_probe

ROOT = Path(__file__).resolve().parent.parent
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
}

#: The probe page shows every model under `examples/operators/`, keyed by the
#: signature it demonstrates — :data:`tools.spec_math.OPERATORS` is that map,
#: and reusing it is what keeps the two pages naming the same probes.
PROBES = ROOT / 'examples' / 'operators'

#: One PyPSA reference network per rung of the declared page, run out of band
#: with the versions each script pins; `references.json` beside them holds
#: what each solve recorded. The page shows each rung's `build()` under its
#: table, so the YAML and the PyPSA statements it stands for sit side by side.
REFERENCES = ROOT / 'examples' / 'references' / 'pypsa'


def source(path: Path) -> str:
    """The model as written, without the licence header a reader did not ask for."""
    return re.sub(r'\A(#[^\n]*\n)+\n', '', path.read_text()).strip()


def model_block(path: Path) -> str:
    """One model, then the whole document the typesetter prints from it."""
    return f'```yaml\n{source(path)}\n```\n\n{to_markdown(path, numbered=False).strip()}'


def probe_block() -> str:
    """Every operator probe: the model, then the one equation it renders."""
    parts = []
    for signature, name in OPERATORS.items():
        equation, _ = rendered_probe(name)
        parts.append(
            f'### `{signature}`\n\n'
            f'`examples/operators/{name}.yaml`\n\n'
            f'```yaml\n{source(PROBES / f"{name}.yaml")}\n```\n\n'
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
    text = source(path)
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


def _build_source(script: Path) -> str:
    """The ``build()`` half of a reference script — the PyPSA statements alone."""
    lines = script.read_text().splitlines()
    i = next(k for k, line in enumerate(lines) if line.startswith('def build('))
    j = next(k for k in range(i + 1, len(lines)) if lines[k].startswith('def '))
    return '\n'.join(lines[i:j]).rstrip()


def reference_block(stem: str) -> str:
    """A rung's oracle: the recorded solve, then the network as PyPSA states it."""
    recorded = json.loads((REFERENCES / 'references.json').read_text())[stem]
    rows = sum(recorded['rows'].values())
    return (
        f"> ✔ `pypsa {recorded['pypsa']}` solves this rung's reference network through its own linopy model "
        f'at objective `{recorded["objective"]}`, {rows} rows — recorded by '
        f'`examples/references/pypsa/{stem}.py`.\n'
        '\n'
        '<details markdown="1">\n'
        "<summary>The reference network, in PyPSA's own statements</summary>\n"
        '\n'
        f'```python\n{_build_source(REFERENCES / f"{stem}.py")}\n```\n'
        '\n'
        '</details>'
    )


def with_references(page: str, text: str) -> str:
    """Every reference script's block, between its own marker pair on the page."""
    for script in sorted(REFERENCES.glob('rung*.py')):
        begin, end = f'<!-- reference:{script.stem}:begin -->', f'<!-- reference:{script.stem}:end -->'
        if begin not in text or end not in text:
            msg = f"{page}: no marker pair for {script.stem} — add {begin} and {end} where the rung's table ends"
            raise ValueError(msg)
        i, j = text.index(begin) + len(begin), text.index(end)
        text = text[:i] + '\n' + reference_block(script.stem) + '\n' + text[j:]
    return text


def block(page: str) -> str:
    if page == 'operators.md':
        return probe_block()
    if page in DECLARED:
        return declared_block(*DECLARED[page])
    return model_block(MODELS[page])


def rendered(page: str, text: str) -> str:
    i, j = text.index(BEGIN) + len(BEGIN), text.index(END)
    text = text[:i] + '\n' + block(page) + '\n' + text[j:]
    if page in DECLARED:
        text = with_references(page, text)
    return text


def pages() -> list[str]:
    return [*MODELS, *DECLARED, 'operators.md']


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--check', action='store_true', help='fail if a committed block has drifted')
    opts = ap.parse_args(argv)

    stale = []
    for page in pages():
        path = PAGES / page
        text = path.read_text()
        updated = rendered(page, text)
        if opts.check:
            if updated != text:
                stale.append(page)
            continue
        path.write_text(updated)
        print(f'wrote {path.relative_to(ROOT)}')

    if stale:
        names = ', '.join(stale)
        print(f'{names} stale — run `pixi run python -m tools.gallery`', file=sys.stderr)
        return 1
    if opts.check:
        print(f'{len(pages())} page(s) match their models')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
