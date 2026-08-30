# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Render every model in the tree to standalone LaTeX, for the compile gate.

    pixi run python -m tools.render_tex build/tex

``tools/compile_tex.py`` is the other half, and ``pixi run compile-tex`` runs
both. One interpreter for every model rather than one each: the process starts
were measured at three quarters of the step's wall clock.
"""

from __future__ import annotations

import sys
from pathlib import Path

from math_spec.__main__ import main as render
from tools._page import ROOT, sidecar_for

#: Every model the repository has; `examples/*.yaml` is not recursive, and a glob that narrows is a gate that stops testing.
CORPUS = ('examples/**/*.yaml', 'tests/typesetting/golden/*.yaml')

#: Inside that glob and not models: the symbol tables `sidecar_for` looks up,
#: and the composition fragments, which name what a sibling declares and are a
#: load error alone — being one is what `examples/composed/` is showing. The
#: model they make is rendered by `tools/gallery.py` and typeset in all three
#: formats by `tests/test_merge.py`, so nothing here goes unrendered.
NOT_MODELS = ('examples/symbols', 'examples/composed')


def models() -> list[Path]:
    """Every model file, deduplicated and in a stable order."""
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
        print('no models matched; the corpus globs are stale', file=sys.stderr)
        return 1

    for model in found:
        args = ['latex', str(model), '--standalone', '-o', str(out / f'{model.stem}.tex')]
        if symbols := sidecar_for(model):
            args += ['--symbols', str(symbols)]
        render(args)

    print(f'rendered {len(found)} model(s) to {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
