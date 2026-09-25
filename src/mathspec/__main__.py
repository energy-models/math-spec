# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""``python -m mathspec <verb> model.yaml`` — the shell front.

``check`` loads the file and prints the language's advice; one further verb
per typeset format, read off :data:`mathspec.typesetting.FORMATS`. Every verb
reads the file as written, and nothing here writes a formulation out unasked.
The typeset verbs take ``--expand``, because a shell cannot compose
:meth:`~mathspec.model.Spec.expand` the way a caller does and the rows are a
different document; ``check`` has no such flag, because advice reads a block
as the rows it states.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mathspec.advice import advice
from mathspec.errors import MathSpecError
from mathspec.typesetting import FORMATS, typeset
from mathspec.validation import to_spec


def parser() -> argparse.ArgumentParser:
    """The verbs, built from ``FORMATS``."""
    front = argparse.ArgumentParser(prog='python -m mathspec')
    verbs = front.add_subparsers(dest='verb', required=True)

    check = verbs.add_parser('check', help='load a model, and print what the language advises')
    check.add_argument('model', help='path to a mathspec YAML model')

    for name in FORMATS:
        verb = verbs.add_parser(name, help=f'render a model as {name}')
        verb.add_argument('model', help='path to a mathspec YAML model')
        verb.add_argument('-o', '--out', help='write here instead of stdout')
        verb.add_argument('--symbols', help='sidecar YAML saying how names should print')
        verb.add_argument('--standalone', action='store_true', help='emit a compilable document')
        verb.add_argument('--no-legend', action='store_true', help='omit the sets/parameters/variables table')
        verb.add_argument('--no-numbers', action='store_true', help='leave the equations unnumbered')
        verb.add_argument(
            '--inline-expressions', action='store_true', help='substitute each named expression where it is used'
        )
        verb.add_argument(
            '--expand',
            action='store_true',
            help='print the variables and constraints the piecewise: and sos: blocks state, not the blocks',
        )
    return front


def main(argv: list[str] | None = None) -> int:
    """Run one verb; a refused file is its message on stderr and exit status 1.

    Advice is not a refusal: ``check`` prints it and exits 0.
    """
    args = parser().parse_args(argv)
    if args.verb == 'check':
        try:
            notes = advice(args.model)
        except MathSpecError as e:
            sys.stderr.write(f'{e}\n')
            return 1
        sys.stdout.write(''.join(f'{note}\n' for note in notes))
        return 0
    model = to_spec(args.model).expand() if args.expand else args.model
    text = typeset(
        model,
        args.verb,
        symbols=args.symbols,
        standalone=args.standalone,
        legend=not args.no_legend,
        numbered=not args.no_numbers,
        inline_expressions=args.inline_expressions,
    )
    if args.out:
        Path(args.out).write_text(text, encoding='utf-8')
    else:
        sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
