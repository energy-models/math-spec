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

import json
import re
import textwrap
from functools import partial
from typing import TYPE_CHECKING

from math_spec import load_model
from math_spec.typesetting import to_markdown
from tools._page import ROOT, sidecar_for, splice, without_header
from tools._page import main as page_main
from tools.notation import equations
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

#: Page -> the model it shows one declaration at a time — its YAML, then the
#: equation it renders, headed by the name the other side gives it, read from
#: the declaration's own description.
DECLARED = {
    'pypsa.md': ROOT / 'examples' / 'pypsa.yaml',
    'pypsa_quadratic.md': ROOT / 'examples' / 'pypsa_quadratic.yaml',
    'pypsa_linearized_uc.md': ROOT / 'examples' / 'pypsa_linearized_uc.yaml',
    'pypsa_losses.md': ROOT / 'examples' / 'pypsa_losses.yaml',
    'pypsa_stochastic.md': ROOT / 'examples' / 'pypsa_stochastic.yaml',
}

#: One PyPSA reference network per rung, run out of band with the versions
#: each script pins; `references.json` beside them holds what each solve
#: recorded.
REFERENCES = ROOT / 'examples' / 'references' / 'pypsa'
RECORDED = json.loads((REFERENCES / 'references.json').read_text())


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


def _stands_for(name: str, description: str | None) -> str:
    """The other side's name for a declaration — the backticked opening of its description."""
    found = re.match(r'`([^`]+)`', description or '')
    if found is None:
        msg = (
            f'{name}: a declaration on a declared page opens its description with the name it stands for, in backticks'
        )
        raise ValueError(msg)
    return found.group(1)


def declared_block(path: Path) -> str:
    """The legend, the objective, then every constraint as YAML beside its equation."""
    text = without_header(path)
    model = load_model(path)
    page = to_markdown(model, symbols=sidecar_for(path), numbered=False)
    legend = page[: page.index('#### Objective')].strip()
    objective = _section(page, 'Objective').strip().removeprefix('#### Objective').strip()
    equation = equations(_section(page, 'Subject to'))
    domains = _section(page, 'Variable domains').strip()
    parts = [legend, f'### Objective\n\n```yaml\n{declaration(text, "objective")}\n```\n\n{objective}']
    for name, block in model.constraints.items():
        parts.append(
            f'### `{_stands_for(name, block.description)}`\n\n'
            f'`{name}`\n\n'
            f'```yaml\n{declaration(text, "constraints", name)}\n```\n\n'
            f'{equation[name]}'
        )
    parts.append(domains)
    return '\n\n'.join(parts)


def _folder(name: str) -> str:
    """Every table in ``data/<name>/``, verbatim — the file is the artifact under review."""
    return '\n\n'.join(
        f'`data/{name}/{path.name}`\n\n```csv\n{path.read_text().strip()}\n```'
        for path in sorted((REFERENCES / 'data' / name).glob('*.csv'))
    )


def reference_block(stem: str) -> str:
    """A rung's oracle: the recorded solve, then the data its folder adds to the spine."""
    recorded = RECORDED[stem]
    rows = sum(recorded['rows'].values())
    parity = recorded.get('parity', {})
    structural = recorded.get('structural', {})
    agreement = (
        f' `lpspec {parity["lpspec"]}` binds `{parity["model"]}` against the same network and lands on the'
        " same objective (lpspec's parity gate)."
        if parity.get('matches')
        else ''
    )
    prices = parity.get('prices', {})
    if agreement and prices.get('compared'):
        agreement += f' Nodal prices agree on {prices["compared"]} rows.'
    if agreement and 'equal' in structural and not structural.get('mismatch'):
        splits = f' up to {len(structural["region"])} documented splits' if structural.get('region') else ''
        agreement += f' **Model-for-model**: the two lanes build one linopy model, label for label{splits}.'
    return (
        f"> ✔ `pypsa {recorded['pypsa']}` solves this rung's reference network at objective "
        f'`{recorded["objective"]}`, {rows} rows.{agreement}\n'
        '\n'
        '<details markdown="1">\n'
        '<summary>What this rung adds, as data</summary>\n'
        '\n'
        f'{_folder(stem)}\n'
        '\n'
        '</details>'
    )


def spine_block() -> str:
    """The shared spine, shown once, under the one sentence of how folders combine."""
    return (
        "> A rung's network is `data/base/` plus `data/<rung>/`, rows appended table by table; a blank cell is"
        " PyPSA's default. A banner states PyPSA's objective, lpspec's parity where its gate agrees, and the"
        ' model-for-model line where `lpspec.linopy` builds the rung.\n'
        '\n'
        '<details markdown="1">\n'
        '<summary>The shared spine, <code>data/base/</code></summary>\n'
        '\n'
        f'{_folder("base")}\n'
        '\n'
        '</details>'
    )


def with_references(text: str) -> str:
    """Every reference block whose marker pair is on this page; a stem on no page at all is the test's business."""
    blocks = {'spine': spine_block, **{stem: partial(reference_block, stem) for stem in sorted(RECORDED)}}
    for key, block in blocks.items():
        begin, end = f'<!-- reference:{key}:begin -->', f'<!-- reference:{key}:end -->'
        if begin in text and end in text:
            text = splice(text, begin, end, block())
    return text


def block(page: str) -> str:
    if page == 'operators.md':
        return probe_block()
    if page in DECLARED:
        return declared_block(DECLARED[page])
    return model_block(MODELS[page])


def rendered(page: str, text: str) -> str:
    text = splice(text, BEGIN, END, block(page))
    if page in DECLARED:
        text = with_references(text)
    return text


def pages() -> list[str]:
    return [*MODELS, *DECLARED, 'operators.md']


def main(argv: list[str] | None = None) -> int:
    return page_main(argv, {PAGES / page: partial(rendered, page) for page in pages()}, 'gallery')


if __name__ == '__main__':
    raise SystemExit(main())
