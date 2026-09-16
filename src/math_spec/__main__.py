# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""``python -m math_spec <verb> model.yaml`` — the shell front.

``check`` loads the file and prints the language's advice, ``compose`` writes
the model several files make — fragments merged, patches laid over — and one
further verb per typeset format, read off :data:`math_spec.typesetting.FORMATS`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from math_spec.advice import advice
from math_spec.composition import _Change, _compose, merge
from math_spec.errors import MathSpecError
from math_spec.typesetting import FORMATS, typeset
from math_spec.validation import to_spec


def parser() -> argparse.ArgumentParser:
    """The verbs, built from ``FORMATS``."""
    front = argparse.ArgumentParser(prog='python -m math_spec')
    verbs = front.add_subparsers(dest='verb', required=True)

    check = verbs.add_parser('check', help='load a model, and print what the language advises')
    check.add_argument('model', help='path to a math_spec YAML model')

    compose = verbs.add_parser('compose', help='merge fragments, lay patches over them, and write the model')
    compose.add_argument('models', nargs='+', help='the model, or the fragments to merge as peers')
    compose.add_argument(
        '-p', '--patch', action='append', default=[], metavar='PATH', help='a patch to lay over the base; repeatable'
    )
    compose.add_argument('-o', '--out', help='write here instead of stdout')

    for name in FORMATS:
        verb = verbs.add_parser(name, help=f'render a model as {name}')
        verb.add_argument('model', help='path to a math_spec YAML model')
        verb.add_argument('-o', '--out', help='write here instead of stdout')
        verb.add_argument('--symbols', help='sidecar YAML saying how names should print')
        verb.add_argument('--standalone', action='store_true', help='emit a compilable document')
        verb.add_argument('--no-legend', action='store_true', help='omit the sets/parameters/variables table')
        verb.add_argument('--no-numbers', action='store_true', help='leave the equations unnumbered')
        verb.add_argument(
            '--inline-expressions', action='store_true', help='substitute each named expression where it is used'
        )
    return front


def main(argv: list[str] | None = None) -> int:
    """Run one verb; a refused file is its message on stderr and exit status 1.

    Advice is not a refusal: ``check`` prints it and exits 0.
    """
    args = parser().parse_args(argv)
    if args.verb == 'compose':
        return _composed(args.models, args.patch, args.out)
    if args.verb == 'check':
        try:
            notes = advice(args.model)
        except MathSpecError as e:
            sys.stderr.write(f'{e}\n')
            return 1
        sys.stdout.write(''.join(f'{note}\n' for note in notes))
        return 0
    text = typeset(
        args.model,
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


def _composed(models: list[str], patches: list[str], out: str | None) -> int:
    """The ``compose`` verb: the composed model to stdout, and what it took to stderr.

    The model and the summary are split across the two streams so that a
    redirected ``compose`` writes a file a reviewer diffs, with the account of
    how it got that way still on the terminal.
    """
    try:
        base = merge(_named(models)) if len(models) > 1 else models[0]
        model, changes = _compose(base, _named(patches))
        text = to_spec(model).to_yaml()
    except (MathSpecError, FileNotFoundError) as e:
        sys.stderr.write(f'{e}\n')
        return 1
    if out:
        Path(out).write_text(text, encoding='utf-8')
    else:
        sys.stdout.write(text)
    if len(models) > 1:
        sys.stderr.write(f'merged {len(models)} fragments\n')
    sys.stderr.write(_summary(changes))
    return 0


def _named(patches: list[str]) -> dict[str, str]:
    """Each patch under its file's stem, and under its whole path where two files share one."""
    named: dict[str, str] = {}
    for patch in patches:
        stem = Path(patch).stem
        named[patch if stem in named else stem] = patch
    return named


def _summary(changes: list[_Change]) -> str:
    """What the patches did, one line each and a count, for the stream a person reads."""
    lines = [f'{change.action:>7}  {change.section}.{change.name}  ({change.patch})' for change in changes]
    counted = [
        f'{sum(change.action == action for change in changes)} {action}'
        for action in ('added', 'edited', 'removed')
        if any(change.action == action for change in changes)
    ]
    lines.append(', '.join(counted) or 'nothing to lay over')
    return ''.join(f'{line}\n' for line in lines)


if __name__ == '__main__':
    raise SystemExit(main())
