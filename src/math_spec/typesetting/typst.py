# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Typst. The format that compiles without a toolchain.

Here to keep :mod:`math_spec.typesetting.format` honest: a seam with one
implementation behind it is a shape, not an abstraction. Typst's syntax differs
from LaTeX's in every respect that matters — ``sum_(…)``, ``cal(T)``,
function-call grouping instead of brace groups, a term list instead of a
``description`` environment — so if the walk needed changing to accommodate it,
the split was in the wrong place.

Practically: the compiler is one self-contained binary (a pip wheel, so the
suite compiles every example without apt), and multi-letter identifiers in math
are upright by default, which is why names go through ``italic("…")``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar

from math_spec.typesetting.format import TYPST_OPERATORS

if TYPE_CHECKING:
    from collections.abc import Mapping

    from math_spec.typesetting.format import Entry, Line

_PREAMBLE = """#set page(margin: 2.5cm)
#set text(size: 11pt)
"""


#: What Typst reads as markup in text mode, each escaped by a leading
#: backslash. They are not LaTeX's: ``%`` and ``&`` are ordinary characters
#: here, while ``*``, ``@``, ``<``, ``/`` and the square brackets are not.
_SPECIALS = frozenset('\\#$*_@`<>~/[]')

#: A list or heading marker is markup only at the start of a line.
_LEADING_MARKER = re.compile(r'(^|\n)([-+=])(?= )')


def _quote(text: str) -> str:
    """A Typst string literal — only the quote and the backslash can bite."""
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"') + '"'


def _escape(text: str) -> str:
    escaped = ''.join(f'\\{c}' if c in _SPECIALS else c for c in text)
    return _LEADING_MARKER.sub(r'\1\\\2', escaped)


def _raw(text: str) -> str:
    """Inline raw text. Backticks are the only character that can end it."""
    return '`' + text.replace('`', "'") + '`'


class TypstFormat:
    """See :class:`math_spec.typesetting.format.Format`.

    The cyclic operators spell with ``.o``, Typst's circled modifier;
    ``minus.circle`` does not compile.
    """

    suffix: ClassVar[str] = '.typ'
    notation: ClassVar[str] = 'typst'
    #: Typst applies the same substitution TeX does.
    dash: ClassVar[str] = '---'

    operators: ClassVar[Mapping[str, str]] = TYPST_OPERATORS

    # -- atoms -------------------------------------------------------------

    def italic(self, name: str) -> str:
        return f'italic({_quote(name)})'

    def upright(self, name: str) -> str:
        return f'upright({_quote(name)})'

    def script(self, letter: str) -> str:
        return f'cal({letter})'

    def greek(self, name: str) -> str:
        return name

    def prose(self, text: str) -> str:
        return f'upright({_quote(text)})'

    def mono(self, text: str) -> str:
        return _raw(text)

    def escape(self, prose: str) -> str:
        return _escape(prose)

    def math(self, expression: str) -> str:
        return f'${expression}$'

    # -- structure ---------------------------------------------------------

    def subscript(self, base: str, indices: list[str]) -> str:
        return f'{base}_({",".join(indices)})' if indices else base

    def superscript(self, base: str, tail: str) -> str:
        return f'{base}^({tail})'

    def parenthesise(self, inner: str) -> str:
        return f'({inner})'

    def cardinality(self, inner: str) -> str:
        return f'abs({inner})'

    def fraction(self, numerator: str, denominator: str) -> str:
        return f'frac({numerator}, {denominator})'

    def summation(self, domain: str, body: str) -> str:
        return f'sum_({domain}) {body}'

    def apply(self, function: str, argument: str) -> str:
        """``f(x)`` in Typst math is a call on ``f``.

        With an ``upright("bus")`` head that is exactly the notation wanted,
        and it needs no thin space.
        """
        return f'{function}({argument})'

    def joined(self, parts: list[str], operator: str) -> str:
        return f' {operator} '.join(parts) if operator else ', '.join(parts)

    # -- document ----------------------------------------------------------

    def equations(self, lines: list[Line], *, numbered: bool) -> str:
        """A block equation, aligned on ``&``.

        Typst aligns on ``&`` inside a block equation exactly as amsmath
        does, so the :class:`Line` split carries over unchanged — which is
        the point.
        """
        rows = [
            f'{self.prose(line.label) if line.label else ""} & {line.left} & {line.right} & {line.condition}'.rstrip(
                ' &'
            )
            for line in lines
        ]
        body = ' \\\n  '.join(rows)
        numbering = '#set math.equation(numbering: "(1)")\n' if numbered else ''
        return f'{numbering}$ {body} $'

    def glossary(self, title: str, entries: list[Entry]) -> str:
        rows = '\n'.join(f'/ {self.math(e.symbol)}: {e.meaning(self.dash)}' for e in entries)
        return f'== {title}\n{rows}'

    def section(self, title: str, body: str) -> str:
        return f'== {title}\n{body}'

    def note(self, text: str) -> str:
        return text

    def document(self, blocks: list[str], *, standalone: bool) -> str:
        """Join the blocks; ``standalone`` only decides whether page setup is emitted.

        Typst has no preamble/body split — a bare fragment is already a document.
        """
        body = '\n\n'.join(blocks) + '\n'
        return f'{_PREAMBLE}\n{body}' if standalone else body
