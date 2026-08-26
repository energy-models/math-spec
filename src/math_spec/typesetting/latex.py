# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""LaTeX (amsmath). The format that lands in a journal.

Verbose source and a toolchain to compile it, in exchange for being the one
target a paper actually accepts. CI compiles every example with a two-package
TeX, which is also a check that the preamble stays installable from a small one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from math_spec.typesetting.format import OPERATOR_SPELLINGS

if TYPE_CHECKING:
    from collections.abc import Mapping

    from math_spec.typesetting.format import Entry, Line

_ESCAPES = {
    '\\': r'\textbackslash{}',
    '&': r'\&',
    '%': r'\%',
    '$': r'\$',
    '#': r'\#',
    '_': r'\_',
    '{': r'\{',
    '}': r'\}',
    '~': r'\textasciitilde{}',
    '^': r'\textasciicircum{}',
}

_PREAMBLE = r"""\documentclass[11pt]{article}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage[margin=2.5cm]{geometry}
\allowdisplaybreaks
\begin{document}
"""


def _escape(text: str) -> str:
    return ''.join(_ESCAPES.get(c, c) for c in text)


class LatexFormat:
    """See :class:`math_spec.typesetting.format.Format`."""

    suffix: ClassVar[str] = '.tex'
    notation: ClassVar[str] = 'latex'
    #: TeX's own em-dash ligature.
    dash: ClassVar[str] = '---'

    operators: ClassVar[Mapping[str, str]] = {name: latex for name, (latex, _) in OPERATOR_SPELLINGS.items()}

    # -- atoms -------------------------------------------------------------

    def italic(self, name: str) -> str:
        return rf'\mathit{{{_escape(name)}}}'

    def upright(self, name: str) -> str:
        return rf'\mathrm{{{_escape(name)}}}'

    def script(self, letter: str) -> str:
        return rf'\mathcal{{{letter}}}'

    def greek(self, name: str) -> str:
        return f'\\{name}'

    def prose(self, text: str) -> str:
        return rf'\text{{{_escape(text)}}}'

    def quoted(self, label: str) -> str:
        r"""The quotes in text mode, the label itself upright in math mode.

        Not one ``\text{'label'}``: MathJax renders ``\_`` inside ``\text``
        as a literal backslash, and this format is what `to_markdown` inherits
        — in math mode the escape works everywhere, which is how every name
        already prints.
        """
        return rf"\text{{'}}{self.upright(label)}\text{{'}}"

    def mono(self, text: str) -> str:
        return rf'\texttt{{{_escape(text)}}}'

    def escape(self, prose: str) -> str:
        return _escape(prose)

    def math(self, expression: str) -> str:
        return f'${expression}$'

    # -- structure ---------------------------------------------------------

    def subscript(self, base: str, indices: list[str]) -> str:
        return f'{base}_{{{",".join(indices)}}}' if indices else base

    def superscript(self, base: str, tail: str) -> str:
        return f'{base}^{{{tail}}}'

    def parenthesise(self, inner: str) -> str:
        return rf'\left( {inner} \right)'

    def cardinality(self, inner: str) -> str:
        return rf'\lvert {inner} \rvert'

    def fraction(self, numerator: str, denominator: str) -> str:
        return rf'\frac{{{numerator}}}{{{denominator}}}'

    def summation(self, domain: str, body: str) -> str:
        return rf'\sum_{{{domain}}} {body}'

    def apply(self, function: str, argument: str) -> str:
        return f'{function}({argument})'

    def joined(self, parts: list[str], operator: str) -> str:
        return f' {operator} '.join(parts) if operator else r',\ '.join(parts)

    # -- document ----------------------------------------------------------

    def equations(self, lines: list[Line], *, numbered: bool) -> str:
        environment = 'align' if numbered else 'align*'
        rows = [
            f'{self.prose(line.label) if line.label else ""} && {line.left} & {line.right} && {line.condition}'.rstrip(
                ' &'
            )
            for line in lines
        ]
        body = ' \\\\\n'.join(rows)
        return f'\\begin{{{environment}}}\n{body}\n\\end{{{environment}}}'

    def glossary(self, title: str, entries: list[Entry]) -> str:
        rows = '\n'.join(rf'\item[{{{self.math(e.symbol)}}}] {e.meaning}' for e in entries)
        return f'\\paragraph{{{title}}}\n\\begin{{description}}\n{rows}\n\\end{{description}}'

    def section(self, title: str, body: str) -> str:
        return f'\\paragraph{{{title}}}\n{body}'

    def note(self, text: str) -> str:
        return f'\\noindent {text}'

    def document(self, blocks: list[str], *, standalone: bool) -> str:
        body = '\n\n'.join(blocks) + '\n'
        return f'{_PREAMBLE}\n{body}\n\\end{{document}}\n' if standalone else body
