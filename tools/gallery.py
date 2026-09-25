# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""The example gallery: each spec in `examples/`, beside the math it prints.

    pixi run python -m tools.gallery           # rewrite the pages' blocks
    pixi run python -m tools.gallery --check   # fail if one has drifted

The prose above each block is the page's own. Only the fenced spec and the
math below it are written from here.
"""

from __future__ import annotations

import json
import re
import textwrap
from functools import partial
from typing import TYPE_CHECKING, Any

import yaml

from mathspec import merge, override, to_spec, typeset_declaration
from mathspec.program import Add, Constant, Named
from mathspec.typesetting import to_markdown
from tools._page import ROOT, sidecar_for, splice, tab, without_header
from tools._page import main as page_main
from tools.notation import equations
from tools.spec_math import OPERATORS, PROBES, _section, rendered_probe

if TYPE_CHECKING:
    from pathlib import Path

    from mathspec.spec import Spec

PAGES = ROOT / 'docs' / 'examples'
LIBRARY = ROOT / 'examples' / 'library'
PYPSA = ROOT / 'examples' / 'pypsa'
#: How `examples/library/` prints: one table for every fragment, the spec
#: they compose and each variant laid over it. `symbols_for` cuts it to what
#: one spec declares, because a table naming anything else is refused. The
#: PyPSA split prints in the one file's table, cut the same way.
LIBRARY_SYMBOLS = ROOT / 'examples' / 'symbols' / 'library.yaml'
PYPSA_SYMBOLS = ROOT / 'examples' / 'symbols' / 'pypsa.yaml'
BEGIN, END = '<!-- gallery:begin -->', '<!-- gallery:end -->'

#: Page -> the spec it shows. One spec per page, because a gallery of
#: fragments is what the reference pages already are.
MODELS = {
    'dispatch.md': ROOT / 'examples' / 'dispatch.yaml',
    'commitment.md': ROOT / 'examples' / 'commitment.yaml',
    'library/surface.md': LIBRARY / 'surface.yaml',
    'library/generator.md': LIBRARY / 'generator.yaml',
    'library/load.md': LIBRARY / 'load.yaml',
    **{f'pypsa/{path.stem}.md': path for path in sorted(PYPSA.glob('*.yaml'))},
}

#: The index of the PyPSA split: its two tables are read off the fragments.
SPLIT_INDEX = 'pypsa/index.md'

#: Page -> the fragments whose composition it shows, and the patches laid over
#: it. The spec is what `merge` returns, which no file in the tree holds, so
#: the page carries it as YAML beside the math it prints. A patch has no math
#: of its own, so each one prints as the spec it lands on, in a tab of its own.
COMPOSED = {
    'library/composed.md': (
        [LIBRARY / name for name in ('surface.yaml', 'generator.yaml', 'load.yaml')],
        {path.stem: path for path in sorted((LIBRARY / 'variants').glob('*.yaml'))},
    ),
}

#: Page -> the spec it shows one declaration at a time — its YAML, then the
#: equation it renders, headed by the name the other side gives it, read from
#: the declaration's own description.
DECLARED = {
    'pypsa.md': ROOT / 'examples' / 'pypsa.yaml',
    'pypsa_linearized_uc.md': ROOT / 'examples' / 'pypsa_linearized_uc.yaml',
}

#: One PyPSA reference network per rung, run out of band with the versions
#: each script pins; `references.json` beside them holds what each solve
#: recorded.
REFERENCES = ROOT / 'examples' / 'references' / 'pypsa'
RECORDED = json.loads((REFERENCES / 'references.json').read_text())


def model_block(path: Path) -> str:
    """One spec, then the whole document the typesetter prints from it."""
    return f'```yaml\n{without_header(path)}\n```\n\n{to_markdown(path, numbered=False).strip()}'


def symbols_for(model: Spec, table_path: Path = LIBRARY_SYMBOLS) -> dict[str, Any]:
    """The symbol table at *table_path*, cut to the dimensions and names *model* declares or reads."""
    table = yaml.safe_load(table_path.read_text())
    given = model.given
    named = {
        *model.parameters,
        *model.variables,
        *model.expressions,
        *model.constraints,
        *given.parameters,
        *given.variables,
        *given.expressions,
        *given.constraints,
    }
    return {
        'notation': table['notation'],
        'dimensions': {name: symbol for name, symbol in table['dimensions'].items() if name in model.dimensions},
        'names': {name: symbol for name, symbol in table['names'].items() if name in named},
    }


def fragment_block(path: Path, table_path: Path) -> str:
    """One fragment, then its document in the notation the whole composition prints in."""
    model = to_spec(path)
    printed = to_markdown(model, symbols=symbols_for(model, table_path), numbered=False)
    return f'```yaml\n{without_header(path)}\n```\n\n{printed.strip()}'


def split_index_block() -> str:
    """The PyPSA split's two tables: each sum with the fragment that declares it and the terms, and each fragment.

    Both are read off the fragments, so the index cannot name a term or an
    owner the files no longer have.
    """
    specs = {path.stem: to_spec(path) for path in sorted(PYPSA.glob('*.yaml'))}
    owners: dict[str, tuple[str, tuple[str, ...]]] = {}
    terms: dict[str, dict[str, str]] = {}
    for name, spec in specs.items():
        for hub, entry in spec.given.expressions.items():
            if entry.term is not None:
                terms.setdefault(hub, {})[name] = entry.term
        for hub, block in spec.expressions.items():
            if block.expression is None and not block.cases:
                owners[hub] = (name, tuple(block.dims or ()))
    sums = ['| Sum | Over | Declared in | The terms, by the fragment that adds each |', '| --- | --- | --- | --- |']
    for hub, by_fragment in sorted(terms.items(), key=lambda item: -len(item[1])):
        reader, dims = owners[hub]
        cells = ', '.join(f'[`{term}`]({fragment}.md)' for fragment, term in sorted(by_fragment.items()))
        sums.append(f'| `{hub}` | `{", ".join(dims)}` | [{reader}]({reader}.md) | {cells} |')
    files = [
        '| Fragment | Parameters | Variables | Constraints | Reads | Adds to |',
        '| --- | --- | --- | --- | --- | --- |',
    ]
    for name, spec in specs.items():
        given = spec.given
        reads = len(given.parameters) + len(given.variables) + len(given.expressions) + len(given.constraints)
        adds = ', '.join(f'`{hub}`' for hub, entry in given.expressions.items() if entry.term is not None)
        files.append(
            f'| [{name}]({name}.md) | {len(spec.parameters)} | {len(spec.variables)} | {len(spec.constraints)} '
            f'| {reads} | {adds} |'
        )
    return '### The sums\n\n' + '\n'.join(sums) + '\n\n### The fragments\n\n' + '\n'.join(files)


def composed_block(fragments: list[Path], patches: dict[str, Path]) -> str:
    """The spec `merge` returns for *fragments* as YAML, then its document as composed and under each patch.

    The composed YAML is generated rather than committed, so the page cannot
    show a composition the fragments beside it no longer make. A patch is
    refused on its own, so its tab carries the patch file and then the whole
    document of the spec it is laid over.
    """
    model = merge({path.stem: path for path in fragments})
    tabs = [tab('As composed', to_markdown(model, symbols=symbols_for(model), numbered=False).strip())]
    for name, path in patches.items():
        patched = override(model, {name: path})
        tabs.append(
            tab(
                f'With {name}',
                f'```yaml title="variants/{path.name}"\n{without_header(path)}\n```\n\n'
                f'{to_markdown(patched, symbols=symbols_for(patched), numbered=False).strip()}',
            )
        )
    dumped = yaml.safe_dump(
        model.to_dict(), sort_keys=False, default_flow_style=None, allow_unicode=True, width=100
    ).strip()
    return f'```yaml\n{dumped}\n```\n\n' + '\n\n'.join(tabs)


def probe_block() -> str:
    """Every operator probe: the spec, then the one equation it renders."""
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


def _names_for(name: str, description: str | None) -> list[str]:
    """Every other-side name a declaration stands for: the backticked tokens before the ` — ` of its description.

    One declaration answers to one PyPSA name as a rule; a block whose rows PyPSA
    names differently by mode lists them all before the dash, the first canonical.
    """
    text = description or ''
    head = text.split(' — ', 1)[0] if ' — ' in text else (re.match(r'`[^`]+`', text) or [''])[0]
    names = re.findall(r'`([^`]+)`', head)
    if not names:
        msg = (
            f'{name}: a declaration on a declared page opens its description with the name it stands for, in backticks'
        )
        raise ValueError(msg)
    return names


def _stands_for(name: str, description: str | None) -> str:
    """The other side's canonical name for a declaration — the backticked opening of its description."""
    return _names_for(name, description)[0]


def declared_block(path: Path) -> str:
    """The legend, the objective, then every constraint and every named expression as YAML beside its equation."""
    text = without_header(path)
    model = to_spec(path)
    page = to_markdown(model, symbols=sidecar_for(path), numbered=False)
    legend = page[: page.index('#### Objective')].strip()
    objective = _section(page, 'Objective').strip().removeprefix('#### Objective').strip()
    equation = equations(_section(page, 'Subject to'))
    definition = equations(_section(page[page.index('#### Objective') :], 'Definitions')) if model.expressions else {}
    domains = _section(page, 'Variable domains').strip()
    assumption = equations(_section(page, 'Assumptions')) if model.assumptions else {}
    parts = [legend, f'### Objective\n\n```yaml\n{declaration(text, "objective")}\n```\n\n{objective}']
    for name, block in model.constraints.items():
        printed = equation[name]
        if _reads_a_sum(model, name):
            line = typeset_declaration(model, name, 'markdown', symbols=sidecar_for(path), inline_expressions=True)
            printed = f'```math\n{line}\n```'
        parts.append(
            f'### `{_stands_for(name, block.description)}`\n\n'
            f'`{name}`\n\n'
            f'```yaml\n{declaration(text, "constraints", name)}\n```\n\n'
            f'{printed}'
        )
    parts.extend(
        f'### `{name}`\n\n```yaml\n{declaration(text, "expressions", name)}\n```\n\n{definition[name]}'
        for name in model.expressions
    )
    parts.append(domains)
    parts.extend(
        f'### `{name}`\n\n```yaml\n{declaration(text, "assumptions", name)}\n```\n\n{assumption[name]}'
        for name in model.assumptions
    )
    return '\n\n'.join(parts)


def _summands(node: object) -> list[object]:
    """The terms of *node* read as a flat sum."""
    return [*_summands(node.left), *_summands(node.right)] if isinstance(node, Add) else [node]


def _reads_a_sum(model: Spec, name: str) -> bool:
    """Whether the row *name* is ``hub == 0`` over a named expression that is a sum of named expressions.

    Such a row prints with the sum substituted in, as the one file wrote it
    before each term had a name: the row is what the reader came for, and the
    terms print once each as definitions below.
    """
    row = model.program.constraints[name]
    lhs, rhs = row.lhs, row.rhs
    return (
        isinstance(lhs, Named)
        and isinstance(rhs, Constant)
        and rhs.value == 0
        and all(isinstance(term, Named) for term in _summands(lhs.body))
        and len(_summands(lhs.body)) > 1
    )


def _script(name: str) -> str:
    """A rung's PyPSA script, verbatim — the model under review is the code itself."""
    return f'`{name}.py`\n\n```python\n{(REFERENCES / f"{name}.py").read_text().strip()}\n```'


def _banner(recorded: dict) -> str:
    """What PyPSA solved the rung to; for a rung that records a PyPSA bug, also what the file intends and the issue."""
    pypsa = f'`pypsa {recorded["pypsa"]}`'
    if 'diverges' not in recorded:
        return f"> ✔ {pypsa} solves this rung's network at objective `{recorded['objective']}`, {sum(recorded['rows'].values())} rows."
    diverges = recorded['diverges']
    issue = f'[PyPSA/PyPSA#{diverges["issue"]}](https://github.com/PyPSA/PyPSA/issues/{diverges["issue"]})'
    gives = (
        f"raises `{diverges['raises']}` on this rung's network"
        if 'raises' in diverges
        else f"solves this rung's network at objective `{diverges['objective']}`, {sum(recorded['rows'].values())} rows"
    )
    return f'> ✘ {pypsa} {gives}, {issue}. The intended objective is `{recorded["objective"]}`.'


def reference_block(stem: str) -> str:
    """A rung's oracle: the recorded solve, then the PyPSA script that builds its network."""
    return (
        f'{_banner(RECORDED[stem])}\n'
        '\n'
        '<details markdown="1">\n'
        '<summary>The network, as PyPSA code</summary>\n'
        '\n'
        f'{_script(stem)}\n'
        '\n'
        '</details>'
    )


def spine_block() -> str:
    """The shared spine, shown once."""
    return (
        "> Every rung's network is `spine.build()` plus the rung's own `n.add` calls, data inline; a keyword not"
        " passed is PyPSA's default. A banner states what PyPSA solved the rung to; how an engine attaches the network to"
        " the file, and what it makes of it, is that engine's own record.\n"
        '\n'
        '<details markdown="1">\n'
        '<summary>The shared spine, <code>spine.py</code></summary>\n'
        '\n'
        f'{_script("spine")}\n'
        '\n'
        '</details>'
    )


def with_references(text: str) -> str:
    """Every reference block whose marker pair is on this page; a stem on no page at all is the test's business."""
    blocks = {
        'spine': spine_block,
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
    if page in COMPOSED:
        return composed_block(*COMPOSED[page])
    if page == SPLIT_INDEX:
        return split_index_block()
    if MODELS[page].parent == LIBRARY:
        return fragment_block(MODELS[page], LIBRARY_SYMBOLS)
    if MODELS[page].parent == PYPSA:
        return fragment_block(MODELS[page], PYPSA_SYMBOLS)
    return model_block(MODELS[page])


def rendered(page: str, text: str) -> str:
    text = splice(text, BEGIN, END, block(page))
    if page in DECLARED:
        text = with_references(text)
    return text


def pages() -> list[str]:
    return [*MODELS, *COMPOSED, *DECLARED, 'operators.md', SPLIT_INDEX]


def main(argv: list[str] | None = None) -> int:
    return page_main(argv, {PAGES / page: partial(rendered, page) for page in pages()}, 'gallery')


if __name__ == '__main__':
    raise SystemExit(main())
