# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""GitHub-flavoured Markdown. GitHub renders math with MathJax, so the math is :class:`LatexFormat`'s and only the document layer differs."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar, override

from math_spec.typesetting.format import escaped, paragraphs
from math_spec.typesetting.latex import LatexFormat

if TYPE_CHECKING:
    from collections.abc import Mapping

    from math_spec.typesetting.format import Entry, Line, OperatorName


#: What Markdown reads as markup inside a paragraph, each escaped by a leading
#: backslash — CommonMark lets any ASCII punctuation be. ``$`` is GitHub's
#: inline math, ``~`` its strikethrough; the pipe is a table cell's to escape.
_SPECIALS = frozenset('\\`*_[]<>~$#')

#: A list, quote or heading marker is markup only at the start of a line.
_LEADING_MARKER = re.compile(r'(^|\n)([-+>]|\d+[.)])(?= )')


def _escape(text: str) -> str:
    escaped = ''.join(f'\\{c}' if c in _SPECIALS else c for c in text)
    return _LEADING_MARKER.sub(r'\1\\\2', escaped)


def _cell(text: str) -> str:
    """*text* as one table cell: a pipe would end it and a newline would end the row."""
    return text.replace('|', r'\|').replace('\n', ' ')


class MarkdownFormat(LatexFormat):
    """See :class:`math_spec.typesetting.format.Format`. Math is LaTeX's; prose is not."""

    #: The character, not TeX's ligature: no Markdown renderer this output
    #: is aimed at substitutes one, so `---` reaches the reader as three
    #: hyphens in the middle of a legend row.
    dash: ClassVar[str] = '\N{EM DASH}'

    #: TeX's own row primitive, not ``\\``: Markdown's escape pass eats one of
    #: those two backslashes, so MathJax would never break the row.
    cases_row: ClassVar[str] = r' \cr '

    #: LaTeX's, with letter-named spacing macros: GitHub's escape pass runs inside
    #: ``$$`` and turns ``\,`` into a bare comma, while ``\thinspace`` passes through.
    operators: ClassVar[Mapping[OperatorName, str]] = {
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
        """Prose with every special escaped, as the other two notations do, and a backtick span kept as the code span it is."""
        return escaped(prose, _escape, self.mono)

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
            block = f'$${self.equation(line)}$$'
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
        body = paragraphs(blocks)
        return f'## The math\n\n{body}' if standalone else body
