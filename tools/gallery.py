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


def _typeset(path: Path) -> tuple[str, dict[str, str], str, str, str]:
    """The file's text, its constraints' equations by name, and the legend, objective and domains prose."""
    text = without_header(path)
    page = to_markdown(load_model(path), symbols=sidecar_for(path), numbered=False)
    legend = page[: page.index('#### Objective')].strip()
    objective = _section(page, 'Objective').strip().removeprefix('#### Objective').strip()
    equation = equations(_section(page, 'Subject to'))
    domains = _section(page, 'Variable domains').strip()
    return text, equation, legend, objective, domains


def _constraint_block(name: str, block, text: str, equation: dict[str, str]) -> str:
    """One constraint as YAML beside its equation, headed by the PyPSA row it stands for."""
    return (
        f'### `{_stands_for(name, block.description)}`\n\n'
        f'`{name}`\n\n'
        f'```yaml\n{declaration(text, "constraints", name)}\n```\n\n'
        f'{equation[name]}'
    )


def turned_on(path: Path) -> dict[str, list[str]]:
    """Rung -> the constraint blocks whose PyPSA rows that rung is the first on the ladder to build.

    A block stands for the row its description opens with; a global-constraint
    row, which PyPSA names after its label, is matched through the recorded
    type and sense the block's ``where:`` selects. Rungs are read in ladder
    order, so a row two rungs build — or one block two labels select — is
    shown under the lower one.
    """
    model = load_model(path)
    stems = [stem for stem in sorted(RECORDED) if REFERENCES.joinpath(f'{stem}.py').exists() and _binds(stem) == path]
    seen: set[str] = set()
    taken: set[str] = set()
    claimed: dict[str, list[str]] = {stem: [] for stem in stems}
    for stem in stems:
        record = RECORDED[stem]
        rows = set(record['rows']) - seen
        seen |= set(record['rows'])
        gcs = [
            record['global_constraints'][row.removeprefix('GlobalConstraint-')]
            for row in rows
            if row.startswith('GlobalConstraint-')
        ]
        for name, block in model.constraints.items():
            stands = _stands_for(name, block.description)
            if name in taken:
                continue
            if stands in rows or any(stands == gc['type'] and f"'{gc['sense']}'" in (block.where or '') for gc in gcs):
                claimed[stem].append(name)
                taken.add(name)
    return claimed


def _binds(stem: str) -> Path:
    """The file a rung binds: ``MODEL`` in its script where it names one, ``pypsa.yaml`` otherwise."""
    found = re.search(r"^MODEL = '([^']+)'", (REFERENCES / f'{stem}.py').read_text(), flags=re.MULTILINE)
    return ROOT / 'examples' / (found.group(1) if found else 'pypsa.yaml')


def declared_block(path: Path) -> str:
    """The legend, the objective, the constraints no rung turns on, and the domains."""
    text, equation, legend, objective, domains = _typeset(path)
    model = load_model(path)
    shown = {name for names in turned_on(path).values() for name in names}
    parts = [legend, f'### Objective\n\n```yaml\n{declaration(text, "objective")}\n```\n\n{objective}']
    rest = [name for name in model.constraints if name not in shown]
    if rest:
        parts.append('Every other block sits under the rung that first builds its row; these none does:')
        parts.extend(_constraint_block(name, model.constraints[name], text, equation) for name in rest)
    else:
        parts.append('Every block sits under the rung that first builds its row.')
    parts.append(domains)
    return '\n\n'.join(parts)


def _script(name: str) -> str:
    """A rung's PyPSA script, verbatim — the model under review is the code itself."""
    return f'`{name}.py`\n\n```python\n{(REFERENCES / f"{name}.py").read_text().strip()}\n```'


def reference_block(stem: str) -> str:
    """A rung's oracle, the PyPSA script that builds its network, then the blocks it is the first to turn on."""
    recorded = RECORDED[stem]
    rows = sum(recorded['rows'].values())
    path = _binds(stem)
    text, equation, *_ = _typeset(path)
    model = load_model(path)
    blocks = turned_on(path).get(stem, [])
    parts = [
        f"> ✔ `pypsa {recorded['pypsa']}` solves this rung's network at objective "
        f'`{recorded["objective"]}`, {rows} rows.\n'
        '\n'
        '<details markdown="1">\n'
        '<summary>The network, as PyPSA code</summary>\n'
        '\n'
        f'{_script(stem)}\n'
        '\n'
        '</details>',
        *(_constraint_block(name, model.constraints[name], text, equation) for name in blocks),
    ]
    return '\n\n'.join(parts)


def spine_block() -> str:
    """The shared spine, shown once."""
    return (
        "> Every rung's network is `spine.build()` plus the rung's own `n.add` calls, data inline; a keyword not"
        " passed is PyPSA's default. A banner states what PyPSA solved the rung to; what an engine makes of the"
        " rung is that engine's own record.\n"
        '\n'
        '<details markdown="1">\n'
        '<summary>The shared spine, <code>spine.py</code></summary>\n'
        '\n'
        f'{_script("spine")}\n'
        '\n'
        '</details>'
    )


def binding_block() -> str:
    """The binding script, shown once: how a network becomes the tables the file declares."""
    return (
        '> A network becomes the tables the file declares through `prep.py`: plain renames, and every parameter the'
        ' file marks "data prep" computed where it says so.\n'
        '\n'
        '<details markdown="1">\n'
        '<summary>The binding, <code>prep.py</code></summary>\n'
        '\n'
        f'{_script("prep")}\n'
        '\n'
        '</details>'
    )


def with_references(text: str) -> str:
    """Every reference block whose marker pair is on this page; a stem on no page at all is the test's business."""
    blocks = {
        'spine': spine_block,
        'binding': binding_block,
        **{stem: partial(reference_block, stem) for stem in sorted(RECORDED)},
    }
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
