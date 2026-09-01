# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Is a hand-written parser the same parser? Ask the grammar it would replace.

    pixi run python -m tools.prototypes.differential

Two questions, because they catch different things. The corpus check asks
whether every expression and where string the repository actually contains
parses to the same tree. The fuzz asks the same of several hundred thousand
strings nobody wrote, which is where the disagreements were: a bare ``NOT`` is
a *parameter named* NOT, because NOT is only the connective when an atom
follows it, and no reading of the grammar had suggested that.

What neither catches is a token the fuzz alphabet does not contain. The
tokenizer first spelt whitespace ``\\s``, which is 28 characters where the
language allows four, so ``x +\\xa01`` -- a non-breaking space, one paste away
in YAML -- parsed. Nothing here found it; a hand-written list of odd spaces
did. That is the shape of the risk, and the reason pyparsing would have to
stay as a test-only oracle rather than be deleted.
"""

from __future__ import annotations

import itertools
import random
import sys
from pathlib import Path

from math_spec import to_program, to_spec
from math_spec._where_parser import parse_where
from math_spec.expression_parser import parse_expression
from tools.prototypes import expression as hand_expression
from tools.prototypes import where as hand_where

ROOT = Path(__file__).resolve().parent.parent.parent

#: The alphabets each fuzz draws from: every construct of the grammar, plus the
#: operators it must refuse. A token the alphabet omits is a token the fuzz
#: cannot rule on -- see the module docstring.
EXPRESSION_PARTS = [
    'x',
    'y',
    'p_max',
    '_u',
    'inf',
    '1',
    '2.5',
    '1e5',
    '.inf',
    '0.',
    "'wrap'",
    '[a, b]',
    '+',
    '-',
    '*',
    '/',
    '**',
    '<=',
    '>=',
    '==',
    ',',
    '(',
    ')',
    '=',
    ' ',
    '',
    '^',
    '!=',
    '<',
    '&',
    '|',
    '%',
    '.',
    'sum(',
    'shift(',
    'f(',
    'over=',
    'by=[',
]
WHERE_PARTS = [
    'x',
    'p_max',
    'position',
    'by',
    'AND',
    'OR',
    'NOT',
    'and',
    'not',
    'true',
    'False',
    '(',
    ')',
    ',',
    '=',
    '==',
    '!=',
    '<=',
    '>=',
    '<',
    '>',
    '0',
    '-3.5',
    "'l'",
    ' ',
    '',
]


def _outcome(parse, text):
    """What a parser did with *text*, as a comparable value rather than an exception."""
    try:
        return ('ok', parse(text))
    except Exception:
        return ('refused', None)


def corpus():
    """Every expression and where string the repository's own models contain.

    Collected by standing in front of each parser while every model loads,
    then putting back what was there: a caller of this reaches for
    ``parse_expression.__wrapped__`` afterwards, and a capture function left
    installed has no such attribute.
    """
    seen_expressions, seen_wheres = set(), set()

    def capture_expression(text):
        seen_expressions.add(text)
        return parse_expression(text)

    def capture_where(text):
        seen_wheres.add(text)
        return parse_where(text)

    patched = []
    for module in list(sys.modules.values()):
        if module and getattr(module, '__name__', '').startswith('math_spec'):
            for name, capture in (('parse_expression', capture_expression), ('parse_where', capture_where)):
                if hasattr(module, name):
                    patched.append((module, name, getattr(module, name)))
                    setattr(module, name, capture)
    try:
        for path in sorted((ROOT / 'examples').rglob('*.yaml')):
            try:
                to_program(to_spec(path))
            except Exception:
                continue
    finally:
        for module, name, original in patched:
            setattr(module, name, original)
    return sorted(seen_expressions), sorted(seen_wheres)


def compare(label, reference, candidate, texts):
    """Report where *candidate* and *reference* disagree about *texts*."""
    disagreed = [t for t in texts if _outcome(reference, t) != _outcome(candidate, t)]
    print(f'{label}: {len(texts) - len(disagreed)}/{len(texts)} agree')
    for text in disagreed[:8]:
        print(f'    {text!r}  reference={_outcome(reference, text)[0]}  hand={_outcome(candidate, text)[0]}')
    return len(disagreed)


def fuzz(parts, seed, count, longest=8):
    """*count* strings drawn from *parts*, plus every three-token product of its first eight."""
    rnd = random.Random(seed)
    drawn = [''.join(rnd.choice(parts) for _ in range(rnd.randint(1, longest))) for _ in range(count)]
    return drawn + [''.join(p) for p in itertools.product(parts[:8], repeat=3)]


def main() -> int:
    expressions, wheres = corpus()
    # `__wrapped__` is the memoised parser's uncached self: a shared tree would
    # make an `is` comparison meaningless and hide a difference behind a hit.
    reference_expression = parse_expression.__wrapped__
    reference_where = parse_where.__wrapped__

    disagreements = compare('expressions, corpus', reference_expression, hand_expression.parse, expressions)
    disagreements += compare('where, corpus', reference_where, hand_where.parse, wheres)
    disagreements += compare(
        'expressions, fuzz', reference_expression, hand_expression.parse, fuzz(EXPRESSION_PARTS, 20260901, 300_000)
    )
    disagreements += compare('where, fuzz', reference_where, hand_where.parse, fuzz(WHERE_PARTS, 7, 300_000))

    print(f'\n{disagreements} disagreement(s) in total')
    return 1 if disagreements else 0


if __name__ == '__main__':
    raise SystemExit(main())
