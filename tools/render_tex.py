# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Render every spec in the tree to standalone LaTeX, for the compile gate.

    pixi run python -m tools.render_tex build/tex

``tools/compile_tex.py`` is the other half, and ``pixi run compile-tex`` runs
both. One interpreter for every spec rather than one each: the process starts
were measured at three quarters of the step's wall clock.
"""

from __future__ import annotations

import sys
from pathlib import Path

from mathspec.__main__ import main as render
from tools._page import ROOT, sidecar_for

#: Every spec the repository has; `examples/*.yaml` is not recursive, and a glob that narrows is a gate that stops testing.
CORPUS = ('examples/**/*.yaml', 'tests/typesetting/golden/*.yaml')

#: Inside that glob and not specs: the symbol tables `sidecar_for` looks up,
#: and the patches a library's variants are written as, which `override` lays
#: over a spec rather than anything loading them on their own.
NOT_MODELS = ('examples/symbols', 'examples/library/variants')


def models() -> list[Path]:
    """Every spec file, deduplicated and in a stable order."""
    found = {path for pattern in CORPUS for path in ROOT.glob(pattern)}
    excluded = {ROOT / part for part in NOT_MODELS}
    return sorted(path for path in found if not excluded.intersection(path.parents))


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print('usage: python -m tools.render_tex <output-directory>', file=sys.stderr)
        return 2

    out = Path(argv[0])
    out.mkdir(parents=True, exist_ok=True)

    found = models()
    if not found:
        print('no specs matched; the corpus globs are stale', file=sys.stderr)
        return 1

    for model in found:
        args = ['latex', str(model), '--standalone', '-o', str(out / f'{model.stem}.tex')]
        if symbols := sidecar_for(model):
            args += ['--symbols', str(symbols)]
        render(args)

    print(f'rendered {len(found)} spec(s) to {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
