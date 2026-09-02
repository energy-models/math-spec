# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""LaTeX (amsmath). The preamble must stay installable from a two-package TeX, which is what CI compiles with."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from math_spec.typesetting.format import OPERATOR_SPELLINGS, aligned_rows, paragraphs

if TYPE_CHECKING:
    from collections.abc import Mapping

    from math_spec.typesetting.format import Entry, Line, Notation, OperatorName

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

    notation: ClassVar[Notation] = 'latex'
    #: TeX's own em-dash ligature.
    dash: ClassVar[str] = '---'
    cases_row: ClassVar[str] = r' \\ '

    operators: ClassVar[Mapping[OperatorName, str]] = {name: latex for name, (latex, _) in OPERATOR_SPELLINGS.items()}

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
        r"""The quotes in text mode and the label upright in math mode, since MathJax renders ``\_`` inside ``\text`` literally."""
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

    def cases(self, arms: list[tuple[str, str]]) -> str:
        rows = self.cases_row.join(f'{value} & {condition}' for value, condition in arms)
        return rf'\begin{{cases}} {rows} \end{{cases}}'

    def summation(self, domain: str, body: str) -> str:
        return rf'\sum_{{{domain}}} {body}'

    def apply(self, function: str, argument: str) -> str:
        return f'{function}({argument})'

    def joined(self, parts: list[str], operator: str) -> str:
        return f' {operator} '.join(parts) if operator else r',\ '.join(parts)

    # -- document ----------------------------------------------------------

    def equations(self, lines: list[Line], *, numbered: bool) -> str:
        environment = 'align' if numbered else 'align*'
        body = ' \\\\\n'.join(aligned_rows(lines, self, gap=' && '))
        return f'\\begin{{{environment}}}\n{body}\n\\end{{{environment}}}'

    def glossary(self, title: str, entries: list[Entry]) -> str:
        rows = '\n'.join(rf'\item[{{{self.math(e.symbol)}}}] {e.meaning}' for e in entries)
        return f'\\paragraph{{{title}}}\n\\begin{{description}}\n{rows}\n\\end{{description}}'

    def section(self, title: str, body: str) -> str:
        return f'\\paragraph{{{title}}}\n{body}'

    def note(self, text: str) -> str:
        return f'\\noindent {text}'

    def document(self, blocks: list[str], *, standalone: bool) -> str:
        body = paragraphs(blocks)
        return f'{_PREAMBLE}\n{body}\n\\end{{document}}\n' if standalone else body
