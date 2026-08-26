# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

r"""GitHub-flavoured Markdown. The format that renders where the docs already live.

Markdown has no math of its own — GitHub delegates to MathJax, which reads
LaTeX — so the math is :class:`LatexFormat`'s and only the document layer
differs. It exists so `docs/examples/` does not write its math by hand with
nothing checking it against the model — see `test_the_gallery_math_is_current`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from math_spec.typesetting.latex import LatexFormat

if TYPE_CHECKING:
    from collections.abc import Mapping

    from math_spec.typesetting.format import Entry, Line


def _cell(text: str) -> str:
    """*text* as one table cell: a pipe would end it and a newline would end the row."""
    return text.replace('|', r'\|').replace('\n', ' ')


class MarkdownFormat(LatexFormat):
    """See :class:`math_spec.typesetting.format.Format`. Math is LaTeX's; prose is not."""

    suffix: ClassVar[str] = '.md'
    #: The character, not TeX's ligature: no Markdown renderer this output
    #: is aimed at substitutes one, so `---` reaches the reader as three
    #: hyphens in the middle of a legend row.
    dash: ClassVar[str] = '\N{EM DASH}'

    #: LaTeX's, except where the spelling uses a backslash before punctuation.
    #: GitHub runs Markdown's escape processing *inside* `$$`, so `\,` arrives
    #: as a literal comma and `\;` as a semicolon — `\forall\, s` renders as
    #: "∀, s". Letter-named macros (`\thinspace`, `\quad`) pass through
    #: untouched, and MathJax treats them identically.
    operators: ClassVar[Mapping[str, str]] = {
        **LatexFormat.operators,
        'forall': r'\forall\thinspace',
        'such_that': r'\thinspace:\thinspace',
    }

    @override
    def mono(self, text: str) -> str:
        """A backtick span — this one lands in prose, not in math."""
        return f'`{text}`'

    @override
    def escape(self, prose: str) -> str:
        """Markdown's text mode *is* prose, so author prose is already in it."""
        return prose

    @override
    def joined(self, parts: list[str], operator: str) -> str:
        r"""``,\enspace`` as the bare separator: a letter-named macro, so visibly not a Markdown escape."""
        return f' {operator} '.join(parts) if operator else r',\enspace '.join(parts)

    @override
    def equations(self, lines: list[Line], *, numbered: bool) -> str:
        r"""One display block per equation, with the name *outside* the math.

        ``\text{total\_cost}`` renders its escape literally under MathJax, and
        ``aligned`` has nothing to line up across one-equation blocks.
        ``numbered`` is ignored: ``aligned`` cannot carry numbers.
        """
        del numbered
        blocks = []
        for line in lines:
            body = f'{line.left} {line.right}'.strip()
            if line.condition:
                body = f'{body} \\qquad {line.condition}'
            block = f'$${body}$$'
            if line.label:
                block = f'**{self.mono(line.label)}**\n\n{block}'
            blocks.append(block)
        return '\n\n'.join(blocks)

    @override
    def glossary(self, title: str, entries: list[Entry]) -> str:
        rows = '\n'.join(f'| {_cell(self.math(e.symbol))} | {_cell(e.meaning)} |' for e in entries)
        return f'#### {title}\n\n| Symbol | Meaning |\n|---|---|\n{rows}'

    @override
    def section(self, title: str, body: str) -> str:
        return f'#### {title}\n\n{body}'

    @override
    def note(self, text: str) -> str:
        return text

    @override
    def document(self, blocks: list[str], *, standalone: bool) -> str:
        """No preamble: ``standalone`` adds the heading a fragment is pasted under."""
        body = '\n\n'.join(blocks) + '\n'
        return f'## The math\n\n{body}' if standalone else body
