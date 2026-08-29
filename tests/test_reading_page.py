# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""`docs/reference/language/reading.md`, run rather than read.

The page states the consumer contract in three answers — what a `Spec`'s
`constraints:` holds, and what the `Program` lowered from it holds. A page that
shows the difference and is never executed is a page that stops being true the
first time a curve expands into a fourth declaration, which is exactly the
drift the contract exists to prevent.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / 'docs' / 'reference' / 'language' / 'reading.md'

_FENCE = re.compile(r'^```(?P<lang>yaml|python)[^\n]*\n(?P<code>.*?)^```$', re.DOTALL | re.MULTILINE)


def _blocks(lang: str) -> list[str]:
    """Every fenced block in *lang*, in page order."""
    return [m.group('code') for m in _FENCE.finditer(PAGE.read_text()) if m.group('lang') == lang]


def _block(lang: str) -> str:
    """The page's single fenced block in *lang*."""
    blocks = _blocks(lang)
    assert len(blocks) == 1, f'reading.md has {len(blocks)} {lang} blocks — this test reads exactly one'
    return blocks[0]


def _claims(code: str) -> list[tuple[str, object]]:
    """Every ``expression  # value`` line, as the pair it asserts."""
    lines = code.split('\n')
    return [
        (ast.unparse(node.value), ast.literal_eval(lines[node.lineno - 1].partition('#')[2].strip()))
        for node in ast.parse(code).body
        if isinstance(node, ast.Expr)
    ]


def test_the_page_shows_the_declarations_the_expansion_emits(tmp_path, monkeypatch):
    (tmp_path / 'curve.yaml').write_text(_block('yaml'))
    monkeypatch.chdir(tmp_path)

    namespace: dict[str, object] = {}
    claims: list[tuple[str, object]] = []
    for code in _blocks('python'):
        # the page is the input, so running it is the point rather than a smell
        exec(compile(code, str(PAGE), 'exec'), namespace)
        claims.extend(_claims(code))

    assert len(claims) == 9, 'every `expression  # value` line on the page is checked; one without one is not'
    for expression, claimed in claims:
        assert eval(expression, namespace) == claimed, f'reading.md says `{expression}` is {claimed}'
