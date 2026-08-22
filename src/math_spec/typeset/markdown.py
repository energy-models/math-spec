# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

r"""GitHub-flavoured Markdown. The format that renders where the docs already live.

Markdown has no math of its own — GitHub delegates to MathJax, which eats
LaTeX — so this is **not** a third spelling: it forwards every math method to
:class:`LatexFormat` and writes only the document layer.

Forwarding rather than subclassing, deliberately. Inheritance would silently
inherit a method later added to ``LatexFormat``, and the two differ precisely
in the *document* methods, so the silent case is a ``\paragraph`` in a
Markdown file. Written out, a new seam method is simply missing until someone
decides which side it belongs on.

It exists because `docs/examples/` would otherwise write its math by hand with
nothing checking it against the model beside it — see
`test_the_gallery_math_is_current`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from math_spec.typeset.latex import LatexFormat

if TYPE_CHECKING:
    from collections.abc import Mapping

    from math_spec.typeset.format import Entry, Line

_LATEX = LatexFormat()


class MarkdownFormat:
    """See :class:`math_spec.typeset.format.Format`. Math is LaTeX's; prose is not."""

    suffix: ClassVar[str] = '.md'
    notation: ClassVar[str] = 'latex'
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

    # -- atoms and structure: LaTeX's, because MathJax is what renders them --

    def italic(self, name: str) -> str:
        return _LATEX.italic(name)

    def upright(self, name: str) -> str:
        return _LATEX.upright(name)

    def script(self, letter: str) -> str:
        return _LATEX.script(letter)

    def greek(self, name: str) -> str:
        return _LATEX.greek(name)

    def prose(self, text: str) -> str:
        return _LATEX.prose(text)

    def math(self, expression: str) -> str:
        return _LATEX.math(expression)

    def subscript(self, base: str, indices: list[str]) -> str:
        return _LATEX.subscript(base, indices)

    def superscript(self, base: str, tail: str) -> str:
        return _LATEX.superscript(base, tail)

    def parenthesise(self, inner: str) -> str:
        return _LATEX.parenthesise(inner)

    def cardinality(self, inner: str) -> str:
        return _LATEX.cardinality(inner)

    def fraction(self, numerator: str, denominator: str) -> str:
        return _LATEX.fraction(numerator, denominator)

    def summation(self, domain: str, body: str) -> str:
        return _LATEX.summation(domain, body)

    def apply(self, function: str, argument: str) -> str:
        return _LATEX.apply(function, argument)

    def joined(self, parts: list[str], operator: str) -> str:
        r"""``a op b op c``, with ``\enspace`` as the bare separator.

        LaTeX's ``,\ `` would be safe here too — a backslash before a *space*
        is not a Markdown escape — but spelling it ``\enspace`` says why
        without the reader having to know that.
        """
        return f' {operator} '.join(parts) if operator else r',\enspace '.join(parts)

    # -- the document layer, which is the whole difference -------------------

    def mono(self, text: str) -> str:
        """A backtick span — this one lands in prose, not in math."""
        return f'`{text}`'

    def escape(self, prose: str) -> str:
        """Markdown's text mode *is* prose, so author prose is already in it."""
        return prose

    def equations(self, lines: list[Line], *, numbered: bool) -> str:
        r"""One display block per equation, with the name *outside* the math.

        Not LaTeX's ``aligned``, for two reasons that only show up in a
        browser: a name is not math (``\text{total\_cost}`` renders its
        ``\_`` escape literally under MathJax, where a backtick span outside
        the math does not), and ``aligned`` columns align *across rows*, which
        a page showing one equation per heading has nothing to line up against.

        ``numbered`` is accepted and ignored — ``aligned`` cannot carry numbers,
        and producing something that looks numbered and is not would be worse.
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

    def glossary(self, title: str, entries: list[Entry]) -> str:
        rows = '\n'.join(f'| {self.math(e.symbol)} | {e.meaning(self.dash)} |' for e in entries)
        return f'#### {title}\n\n| Symbol | Meaning |\n|---|---|\n{rows}'

    def section(self, title: str, body: str) -> str:
        return f'#### {title}\n\n{body}'

    def note(self, text: str) -> str:
        return text

    def document(self, blocks: list[str], *, standalone: bool) -> str:
        """Markdown has no preamble, so ``standalone`` only adds a heading.

        A fragment is meant to be pasted under a heading the page already has.
        """
        body = '\n\n'.join(blocks) + '\n'
        return f'## The math\n\n{body}' if standalone else body
