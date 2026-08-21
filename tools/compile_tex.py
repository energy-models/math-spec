# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Compile every rendered model, so the LaTeX gate is a compile and not a lint.

    pixi run compile-tex            # renders first, then compiles
    pixi run python -m tools.compile_tex build/tex

The suite's structural checks — brace balance, environment nesting,
``\\left``/``\\right`` pairing — are what a *generator* gets wrong, and they
need no toolchain. They are not a compile: a malformed ``\\mathcal`` or a
command from a package the preamble never ``\\usepackage``s passes every one of
them and still fails. Only a real engine settles it.

Serially, not in parallel. The whole corpus compiles in a few seconds once
tectonic has its bundle, and the first run on a cold cache fetches that bundle
— which fourteen concurrent processes would each try to do at once.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print('usage: python -m tools.compile_tex <directory>', file=sys.stderr)
        return 2

    if shutil.which('tectonic') is None:
        print('tectonic is not on PATH — run this through `pixi run compile-tex`', file=sys.stderr)
        return 2

    out = Path(argv[0])
    documents = sorted(out.glob('*.tex'))
    if not documents:
        print(f'no .tex files in {out}; run `pixi run render-tex {out}` first', file=sys.stderr)
        return 1

    failed = []
    for document in documents:
        # `-X compile` is tectonic's v2 interface; the log goes to stderr, and
        # it is only worth printing for the documents that fail.
        result = subprocess.run(
            ['tectonic', '-X', 'compile', '--keep-logs', '--outdir', str(out), str(document)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            failed.append(document)
            print(f'--- {document} did not compile', file=sys.stderr)
            print(result.stderr, file=sys.stderr)

    if failed:
        print(f'{len(failed)} of {len(documents)} document(s) did not compile', file=sys.stderr)
        return 1

    print(f'compiled {len(documents)} document(s) in {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
