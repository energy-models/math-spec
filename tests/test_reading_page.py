"""`docs/reference/language/reading.md`, run rather than read.

The page states the consumer contract in three answers — what `constraints:`
holds before the expansion and what it holds after. A page that shows the
difference and is never executed is a page that stops being true the first time
the expansion emits a fourth declaration, which is exactly the drift the
contract exists to prevent.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / 'docs' / 'reference' / 'language' / 'reading.md'

_FENCE = re.compile(r'^```(?P<lang>yaml|python)[^\n]*\n(?P<code>.*?)^```$', re.DOTALL | re.MULTILINE)


def _block(lang: str) -> str:
    """The page's single fenced block in *lang*."""
    blocks = [m.group('code') for m in _FENCE.finditer(PAGE.read_text()) if m.group('lang') == lang]
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

    code = _block('python')
    namespace: dict[str, object] = {}
    # the page is the input, so running it is the point rather than a smell
    exec(compile(code, str(PAGE), 'exec'), namespace)

    claims = _claims(code)
    assert len(claims) == 3, 'the page answers three questions; a fourth would go unchecked here'
    for expression, claimed in claims:
        assert eval(expression, namespace) == claimed, f'reading.md says `{expression}` is {claimed}'
