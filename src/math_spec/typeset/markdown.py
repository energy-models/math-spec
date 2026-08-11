"""GitHub-flavoured Markdown. The format that renders where the docs already live.

Markdown has no math of its own — GitHub, and every renderer worth using,
delegates to MathJax, which eats LaTeX. So this is **not** a third spelling: it
forwards every math method to :class:`LatexFormat` and writes only the document
layer itself.

Forwarding rather than subclassing, deliberately. Inheritance would mean a
method later added to ``LatexFormat`` is silently inherited here — and the two
differ precisely in the *document* methods, so the silent case is a
``\\paragraph`` appearing in a Markdown file. Written out, a new seam method is
simply missing until someone decides which side it belongs on.

Two departures from the LaTeX format:

- ``aligned`` inside ``$$``, not ``align``. GitHub's MathJax renders the
  former; the latter is a numbered top-level environment and does not survive
  a ``$$`` block.
- No equation numbers. ``aligned`` cannot carry them, so ``numbered`` is
  accepted and ignored rather than producing something that looks numbered and
  is not.

Why it exists: `docs/models/` writes its math by hand, and nothing checks it
against the model beside it. This is what lets a page be generated instead —
see `test_the_gallery_notation_is_reproducible_from_the_model` in
`tests/test_typeset.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from lpspec.typeset.latex import LatexFormat

if TYPE_CHECKING:
    from collections.abc import Mapping

    from lpspec.typeset.format import Entry, Line

_LATEX = LatexFormat()


class MarkdownFormat:
    """See :class:`lpspec.typeset.format.Format`. Math is LaTeX's; prose is not."""

    suffix: ClassVar[str] = '.md'

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

    def fraction(self, numerator: str, denominator: str) -> str:
        return _LATEX.fraction(numerator, denominator)

    def summation(self, domain: str, body: str) -> str:
        return _LATEX.summation(domain, body)

    def apply(self, function: str, argument: str) -> str:
        return _LATEX.apply(function, argument)

    def joined(self, parts: list[str], operator: str) -> str:
        """``a op b op c``, with ``\\enspace`` as the bare separator.

        LaTeX's ``,\\ `` would be safe here too — a backslash before a *space*
        is not a Markdown escape — but spelling it ``\\enspace`` says why
        without the reader having to know that.
        """
        return f' {operator} '.join(parts) if operator else r',\enspace '.join(parts)

    # -- the document layer, which is the whole difference -------------------

    def mono(self, text: str) -> str:
        """A backtick span — this one lands in prose, not in math."""
        return f'`{text}`'

    def equations(self, lines: list[Line], *, numbered: bool) -> str:
        """One display block per equation, with the name *outside* the math.

        Not the `aligned` environment the LaTeX format uses, for two reasons
        that only show up in a browser:

        * A name is not math. ``\\text{total\\_cost}`` is right in a LaTeX
          document and wrong here — MathJax renders the ``\\_`` escape
          literally, backslash and all. Outside the math it is a plain
          backtick span, and the question does not arise.
        * `aligned` columns align *across rows*. A page shows one equation at
          a time under its own heading, so the columns have nothing to line up
          against and the ``&`` separators become stretches of empty space.

        The LaTeX format keeps its alignment, because a paper prints the
        constraints as one block where the relations genuinely do line up.
        That difference is the reason these are two formats and not one.
        """
        del numbered
        blocks = []
        for line in lines:
            body = f'{line.left} {line.right}'.strip()
            if line.condition:
                body = f'{body} \\qquad {line.condition}'
            blocks.append(f'**{self.mono(line.label)}**\n\n$${body}$$')
        return '\n\n'.join(blocks)

    def glossary(self, title: str, entries: list[Entry]) -> str:
        rows = '\n'.join(f'| {self.math(e.symbol)} | {e.meaning} |' for e in entries)
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
