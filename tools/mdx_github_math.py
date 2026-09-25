# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""GitHub's verbatim inline math, as a Markdown extension the site enables.

`math_spec.to_markdown` prints GitHub-flavoured Markdown, where inline math is
delimited ``$`…`$`` so that GitHub hands the span to MathJax untouched.
Arithmatex has no syntax for it: python-markdown's own inline code processor
claims the backtick span first. So the site rewrites the pair into the `$…$`
arithmatex reads, and nothing is escaped away on the way in.

This was `docs/static/hooks.py` until the site moved to zensical, which has no
hooks. An extension is what both builders run, and what the suite can load
without a site.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from markdown import Extension
from markdown.preprocessors import Preprocessor

if TYPE_CHECKING:
    from markdown import Markdown

#: A fenced block, indented or not — its contents are nobody's to rewrite, and
#: a ```math one is the superfences entry's in `mkdocs.yml`. The closing run is
#: matched against the opening one, as CommonMark reads a fence: a pattern that
#: only ever closed on three backticks ran from a longer opening fence to the
#: first bare one, and left every span between them unrewritten.
FENCED_BLOCK = re.compile(
    r'^[ \t]*(?P<fence>`{3,})[^\n]*$\n.*?^[ \t]*(?P=fence)`*[ \t]*$',
    re.DOTALL | re.MULTILINE,
)

#: GitHub's verbatim inline math, `$`…`$` — the pair the typesetter prints so
#: that GitHub's escape pass cannot reach into the span. A backtick on either
#: outer edge means a code span quoting the syntax rather than math using it,
#: which is how `docs/reference/typeset.md` spells it.
GITHUB_INLINE_MATH = re.compile(r'(?<!`)\$`(?P<math>[^`\n]+)`\$(?!`)')

#: Between `pymdownx.snippets` (32) and `pymdownx.superfences` (25), so an
#: included page is rewritten and a fence still reaches superfences whole.
PRIORITY = 26


def rewrite(markdown: str) -> str:
    """Rewrite GitHub's verbatim inline math into the `$…$` arithmatex reads.

    A fenced block is left exactly as it is — the YAML a gallery page shows
    beside each equation is not math, and a ```math one is handled by the
    superfences entry in `mkdocs.yml`, which reads it where it is indented
    inside a tab as well.

    Args:
        markdown: Page source, as the file holds it.

    Returns:
        The same page with inline math arithmatex can find.
    """
    spans: list[str] = []
    kept = FENCED_BLOCK.sub(lambda m: spans.append(m[0]) or f'\x00{len(spans) - 1}\x00', markdown)
    rewritten = GITHUB_INLINE_MATH.sub(lambda m: f'${m["math"]}$', kept)
    return re.sub(r'\x00(\d+)\x00', lambda m: spans[int(m[1])], rewritten)


class _GitHubInlineMath(Preprocessor):
    """`rewrite` over the whole page, because the pair may not span a line."""

    def run(self, lines: list[str]) -> list[str]:
        return rewrite('\n'.join(lines)).split('\n')


class GitHubMathExtension(Extension):
    """The extension `mkdocs.yml` names as `tools.mdx_github_math`."""

    def extendMarkdown(self, md: Markdown) -> None:  # noqa: N802  # python-markdown's own spelling
        md.preprocessors.register(_GitHubInlineMath(md), 'github_inline_math', PRIORITY)


def makeExtension(**kwargs: Any) -> GitHubMathExtension:  # noqa: N802  # python-markdown's own spelling
    """What python-markdown calls when the extension is named as a string."""
    return GitHubMathExtension(**kwargs)
