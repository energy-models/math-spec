# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""``python -m math_spec <format> model.yaml`` — the typeset shell front.

One verb per typeset format, read off :data:`math_spec.typesetting.FORMATS`.
No entry point: ``python -m`` says which environment it ran in, which a bare
name on ``PATH`` does not.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from math_spec.typesetting import FORMATS, typeset


def parser() -> argparse.ArgumentParser:
    """The verbs, built from ``FORMATS``; separate from :func:`main` so a test can read them off it."""
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
