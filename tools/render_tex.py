# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Render every model in the tree to standalone LaTeX, for the compile gate.

    pixi run python -m tools.render_tex build/tex

This is half the gate. ``tools/compile_tex.py`` is the other half, and
``pixi run compile-tex`` runs both — it depends on ``render-tex``, so the
output of this script is what it compiles.

One interpreter for every model rather than one each: upstream measured the
process starts at three quarters of the step's wall clock, against every
engine invocation put together.
"""

from __future__ import annotations

import sys
from pathlib import Path

from math_spec.__main__ import main as render

ROOT = Path(__file__).resolve().parent.parent

# Every model the repository has, not a sample. `examples/*.yaml` is not
# recursive and would cover none of these; a glob that silently narrows is how
# a gate stops testing what it claims to.
CORPUS = ('examples/**/*.yaml', 'tests/typeset/golden/*.yaml')


def models() -> list[Path]:
    """Every model file, deduplicated and in a stable order."""
    found = {path for pattern in CORPUS for path in ROOT.glob(pattern)}
    return sorted(found)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print('usage: python -m tools.render_tex <output-directory>', file=sys.stderr)
        return 2

    out = Path(argv[0])
    out.mkdir(parents=True, exist_ok=True)

    found = models()
    if not found:
        print('no models matched; the corpus globs are stale', file=sys.stderr)
        return 1

    for model in found:
        # A sidecar symbol table is used when one sits beside the model under
        # `examples/symbols/`. None exist yet; the hook is here so adding one
        # does not silently go unrendered.
        args = ['latex', str(model), '--standalone', '-o', str(out / f'{model.stem}.tex')]
        symbols = ROOT / 'examples' / 'symbols' / f'{model.stem}.yaml'
        if symbols.is_file():
            args += ['--symbols', str(symbols)]
        render(args)

    print(f'rendered {len(found)} model(s) to {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
