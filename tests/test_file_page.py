# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""`docs/reference/language/file.md`, run rather than read.

The page shows how several files become one model, and it did so against paths
that did not exist — an example nothing executes is one that goes stale the
first time a verb's answer changes, and this one could not have run at all.
Now it composes the library in `examples/composed/`, and every
``expression  # value`` line on the page is checked against what the verbs
actually return.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'docs' / 'reference' / 'language' / 'file.md'

_FENCE = re.compile(r'^```python[^\n]*\n(?P<code>.*?)^```$', re.DOTALL | re.MULTILINE)


def _claims(code: str) -> list[tuple[str, object]]:
    """Every ``expression  # value`` line, as the pair it asserts.

    Read off the line the expression *ends* on: prettier formats python inside a
    fence too, so an expression long enough to wrap leaves its comment on a
    different line from the one it starts on.
    """
    lines = code.split('\n')
    return [
        (ast.unparse(node.value), ast.literal_eval(lines[node.end_lineno - 1].partition('#')[2].strip()))
        for node in ast.parse(code).body
        if isinstance(node, ast.Expr)
    ]


def test_the_page_composes_the_library_it_names(monkeypatch):
    monkeypatch.chdir(ROOT)

    namespace: dict[str, object] = {}
    claims: list[tuple[str, object]] = []
    for match in _FENCE.finditer(PAGE.read_text()):
        code = match.group('code')
        # the page is the input, so running it is the point rather than a smell
        exec(compile(code, str(PAGE), 'exec'), namespace)
        claims.extend(_claims(code))

    assert len(claims) == 2, 'every `expression  # value` line on the page is checked; one without one is not'
    for expression, claimed in claims:
        assert eval(expression, namespace) == claimed, f'file.md says `{expression}` is {claimed}'
