"""``python -m lpspec <verb> ...`` — a shell front for the things that need no data.

One verb per typeset format, read off ``typeset.FORMATS`` rather than listed
again here. Verbs that bind data belong in a caller's script: ``lps.solve``
takes a source mapping, and a CLI that tried to accept one would be inventing
a second way to spell it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lpspec.typeset import FORMATS, typeset


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='python -m lpspec')
    verbs = parser.add_subparsers(dest='verb', required=True)

    for name in FORMATS:
        verb = verbs.add_parser(name, help=f'render a model as {name}')
        verb.add_argument('model', help='path to a lpspec YAML model')
        verb.add_argument('-o', '--out', help='write here instead of stdout')
        verb.add_argument('--symbols', help='sidecar YAML saying how names should print')
        verb.add_argument('--standalone', action='store_true', help='emit a compilable document')
        verb.add_argument('--no-legend', action='store_true', help='omit the sets/parameters/variables table')
        verb.add_argument('--no-numbers', action='store_true', help='leave the equations unnumbered')

    args = parser.parse_args(argv)
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
