# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""``python -m math_spec <format> model.yaml`` — the typeset shell front.

**A document build step, not a command line under construction.** Rendering a
model to LaTeX belongs in a Makefile next to ``pdflatex``, where a Python
script would be awkward. One verb per typeset format, read off
:data:`math_spec.typesetting.FORMATS`, so a new format arrives with its verb written.

**No verb becomes a second way to spell the source mapping.** ``lps.solve``
takes a dict, and ``--source p_max=a.parquet`` is that dict with worse errors;
``solve_over`` cannot be said in flags at all, its axis being a typed object.
So data-binding verbs live in a caller's script. That bans a *spelling*, not a
shell: driving a solve from a Makefile would arrive as one path argument over a
run manifest (#479), where the file *is* the mapping.

No entry point either — ``python -m`` says which environment it ran in, which a
bare name on ``PATH`` does not.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from math_spec.typesetting import FORMATS, typeset


def parser() -> argparse.ArgumentParser:
    """The verbs, built from ``FORMATS`` — so the list exists in one place.

    Separate from :func:`main` so a test can read the verbs off it rather than
    grep the help text, which would pass on a format merely *mentioned* in
    prose.
    """
    front = argparse.ArgumentParser(prog='python -m math_spec')
    verbs = front.add_subparsers(dest='verb', required=True)

    for name in FORMATS:
        verb = verbs.add_parser(name, help=f'render a model as {name}')
        verb.add_argument('model', help='path to a math_spec YAML model')
        verb.add_argument('-o', '--out', help='write here instead of stdout')
        verb.add_argument('--symbols', help='sidecar YAML saying how names should print')
        verb.add_argument('--standalone', action='store_true', help='emit a compilable document')
        verb.add_argument('--no-legend', action='store_true', help='omit the sets/parameters/variables table')
        verb.add_argument('--no-numbers', action='store_true', help='leave the equations unnumbered')
    return front


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    text = typeset(
        args.model,
        FORMATS[args.verb],
        symbols=args.symbols,
        standalone=args.standalone,
        legend=not args.no_legend,
        numbered=not args.no_numbers,
    )
    if args.out:
        Path(args.out).write_text(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
