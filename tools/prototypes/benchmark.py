# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""What replacing pyparsing would be worth, measured rather than argued.

    pixi run python -m tools.prototypes.benchmark

Two tables, because one of them is the one that matters. The parser table is
the step in isolation. The load table is a cold `to_spec`, where parsing is
77% of the work -- so the step's speedup and the load's speedup are different
numbers, and the second is the one a consumer feels.

Every load timing clears the parse memo first, so nothing here is a warm-cache
artefact; the last row is the ceiling, the load with nothing left to parse.
"""

from __future__ import annotations

import time
from functools import lru_cache
from pathlib import Path

import math_spec._where_parser as where_parser
import math_spec.expression_parser as expression_parser
from math_spec import to_spec
from tools.prototypes import expression as hand_expression
from tools.prototypes import where as hand_where
from tools.prototypes.differential import corpus

ROOT = Path(__file__).resolve().parent.parent.parent
#: The largest model the repository has: 64 KB, 258 declarations.
MODEL = ROOT / 'examples' / 'pypsa.yaml'


def best(work, runs=9):
    """The fastest of *runs*, in milliseconds -- the least noisy summary of a timing."""
    fastest = float('inf')
    for _ in range(runs):
        started = time.perf_counter()
        work()
        fastest = min(fastest, time.perf_counter() - started)
    return fastest * 1000


def _bind(name, parse):
    """Point every module that reached for a parser at *parse*, memoised as the real one is."""
    memoised = lru_cache(maxsize=4096)(parse)
    import sys

    for module in list(sys.modules.values()):
        if module and getattr(module, '__name__', '').startswith('math_spec') and hasattr(module, name):
            setattr(module, name, memoised)
    return memoised


def main() -> int:
    expressions, wheres = corpus()
    reference_expression = expression_parser.parse_expression.__wrapped__
    reference_where = where_parser.parse_where.__wrapped__

    print(f'the parser alone, on {len(expressions)} distinct expressions and {len(wheres)} where strings')
    slow = best(lambda: [reference_expression(t) for t in expressions] + [reference_where(t) for t in wheres], runs=5)
    fast = best(lambda: [hand_expression.parse(t) for t in expressions] + [hand_where.parse(t) for t in wheres])
    print(f'  pyparsing              {slow:7.1f} ms')
    print(f'  hand-written           {fast:7.1f} ms   {slow / fast:.0f}x')

    expression_memo, where_memo = expression_parser.parse_expression, where_parser.parse_where

    def cold(*memos):
        for memo in memos:
            memo.cache_clear()
        to_spec(MODEL)

    print(f'\na cold to_spec({MODEL.name}) -- the number a consumer feels')
    base = best(lambda: cold(expression_memo, where_memo))
    print(f'  pyparsing (today)      {base:7.1f} ms   1.0x')

    fast_expression = _bind('parse_expression', hand_expression.parse)
    half = best(lambda: cold(fast_expression, where_memo))
    print(f'  expressions replaced   {half:7.1f} ms   {base / half:.1f}x')

    fast_where = _bind('parse_where', hand_where.parse)
    both = best(lambda: cold(fast_expression, fast_where))
    print(f'  both replaced          {both:7.1f} ms   {base / both:.1f}x')

    floor = best(lambda: to_spec(MODEL))
    print(f'  nothing left to parse  {floor:7.1f} ms   {base / floor:.1f}x   <- the ceiling, whatever the parser')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
