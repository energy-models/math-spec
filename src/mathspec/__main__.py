# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""``python -m mathspec <verb> spec.yaml`` — the shell front.

``check`` loads the file and prints the language's advice; ``canonical``
writes the spec in the form two files that state the same spec share, or with
``--check`` asks whether the file is already in that form; one further verb per
typeset format, read off [`mathspec.typesetting.FORMATS`][]. Every verb reads
the file as written, and nothing here writes a formulation out unasked.
The typeset verbs take ``--expand``, because a shell cannot compose
[`expand`][mathspec.spec.Spec.expand] the way a caller does and the rows are a
different document; ``check`` has no such flag, because advice reads a block
as the rows it states.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mathspec.advising import advice
from mathspec.errors import MathSpecError
from mathspec.typesetting import FORMATS, typeset
from mathspec.validation import to_spec


def parser() -> argparse.ArgumentParser:
    """The verbs, built from ``FORMATS``."""
    front = argparse.ArgumentParser(prog='python -m mathspec')
    verbs = front.add_subparsers(dest='verb', required=True)

    check = verbs.add_parser('check', help='load a spec, and print what the language advises')
    check.add_argument('spec', help='path to a mathspec YAML file')

    canonical = verbs.add_parser('canonical', help='write a spec in the form two files that state it share')
    canonical.add_argument('spec', help='path to a mathspec YAML file')
    target = canonical.add_mutually_exclusive_group()
    target.add_argument('-o', '--out', help='write here instead of stdout')
    target.add_argument('--write', action='store_true', help='rewrite the file in the form, dropping its comments')
    target.add_argument('--check', action='store_true', help='exit 1 if the file is not in the form, writing nothing')

    for name in FORMATS:
        verb = verbs.add_parser(name, help=f'render a spec as {name}')
        verb.add_argument('spec', help='path to a mathspec YAML file')
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


def _checked(path: str, text: str) -> int:
    """Exit status 0 if the file at *path* already holds *text*, the form, and 1 with the rewrite on stderr if not.

    A CI job runs this, so it compares bytes and writes nothing: the job fails,
    and the author runs the rewrite the message names.
    """
    if Path(path).read_text(encoding='utf-8') == text:
        return 0
    sys.stderr.write(
        f'{path} is not in the canonical form. Run `python -m mathspec canonical --write {path}` to rewrite it.\n'
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    """Run one verb; a refused file is its message on stderr and exit status 1.

    Advice is not a refusal: ``check`` prints it and exits 0. A file that
    ``canonical --check`` finds out of the form exits 1, with the rewrite on
    stderr.
    """
    args = parser().parse_args(argv)
    if args.verb == 'check':
        try:
            notes = advice(args.spec)
        except MathSpecError as e:
            sys.stderr.write(f'{e}\n')
            return 1
        sys.stdout.write(''.join(f'{note}\n' for note in notes))
        return 0
    if args.verb == 'canonical':
        try:
            text = to_spec(args.spec).to_yaml(canonical=True)
        except MathSpecError as e:
            sys.stderr.write(f'{e}\n')
            return 1
        if args.check:
            return _checked(args.spec, text)
        if args.write:
            Path(args.spec).write_text(text, encoding='utf-8')
            return 0
    else:
        spec = to_spec(args.spec).expand() if args.expand else args.spec
        text = typeset(
            spec,
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
