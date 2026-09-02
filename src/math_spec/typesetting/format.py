# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The seam between *what* a model says and *how* a format spells it.

The split, and each module's role in it, are in ``README.md`` beside this file.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Literal, Protocol, get_args

if TYPE_CHECKING:
    from collections.abc import Mapping

#: The language a symbol table's entries are written in, and the one a format
#: reads them as. Markdown is absent because its math is MathJax's, so it reads
#: ``latex``; nothing translates between the two.
Notation = Literal['latex', 'typst']

#: The set form, for the sidecar that has to check a string against it.
NOTATIONS = frozenset(get_args(Notation))

#: Every operator a walk can name. A walk asks for one by name and a format
#: spells it, so neither keeps a list of its own; the spellings are below, one
#: row per name, and a name with no row is a type error at that row's table.
OperatorName = Literal[
    'cdot',
    'plus',
    'minus',
    'equal',
    'le',
    'ge',
    'lt',
    'gt',
    'ne',
    'in',
    'and',
    'or',
    'not',
    'false',
    'forall',
    'such_that',
    'infinity',
    'cyclic_minus',
    'cyclic_plus',
    'edge_minus',
    'edge_plus',
    'times',
    'maps_to',
    'reals',
    'integers',
    'binary_set',
    'sos_set',
    'position',
    'minimize',
    'maximize',
]

#: Every operator a walk can emit, by the name the walk uses for it, with its
#: LaTeX spelling first and its Typst spelling second — one row per operator,
#: so no format can be missing one. ``such_that`` is the colon in
#: "∀ t ∈ T : condition", ``times`` sits between sets in the legend,
#: ``maps_to`` is the → in a coordinate map, and the three translations are
#: three models: plain leaves the vacated position absent, ``cyclic_*`` wraps,
#: ``edge_*`` fills it with the value it carries as a subscript.
OPERATOR_SPELLINGS: dict[OperatorName, tuple[str, str]] = {
    'cdot': (r'\cdot', 'dot'),
    'plus': ('+', '+'),
    'minus': ('-', '-'),
    'equal': ('=', '='),
    'le': (r'\le', '<='),
    'ge': (r'\ge', '>='),
    'lt': ('<', '<'),
    'gt': ('>', '>'),
    'ne': (r'\neq', '!='),
    'in': (r'\in', 'in'),
    'and': (r'\wedge', 'and'),
    'or': (r'\vee', 'or'),
    'not': (r'\neg', 'not'),
    'false': (r'\bot', 'bot'),
    'forall': (r'\forall\,', 'forall'),
    'such_that': (r'\,:\,', 'colon'),
    'infinity': (r'\infty', 'infinity'),
    'cyclic_minus': (r'\ominus', 'minus.o'),
    'cyclic_plus': (r'\oplus', 'plus.o'),
    'edge_minus': (r'\boxminus', 'minus.square'),
    'edge_plus': (r'\boxplus', 'plus.square'),
    'times': (r'\times', 'times'),
    'maps_to': (r'\to', 'arrow.r'),
    'reals': (r'\mathbb{R}', 'RR'),
    'integers': (r'\mathbb{Z}', 'ZZ'),
    'binary_set': (r'\{0, 1\}', '{0, 1}'),
    'sos_set': (r'\mathrm{SOS}', 'upright("SOS")'),
    'position': (r'\mathrm{pos}', 'upright("pos")'),
    'minimize': (r'\min', 'min'),
    'maximize': (r'\max', 'max'),
}

#: The set form, for the test pinning each format's table against the vocabulary.
OPERATOR_NAMES = frozenset(get_args(OperatorName))


@dataclass(frozen=True)
class Line:
    """One typeset line of the model, split where a format may align it.

    ``left`` and ``right`` are the two sides of a relation — ``right`` carries
    the relation symbol, so a format aligns on the boundary between them
    without having to parse anything back out.
    """

    label: str
    left: str
    right: str
    condition: str = ''


@dataclass(frozen=True)
class Entry:
    """One legend row: a symbol, and everything opposite it as one string."""

    symbol: str
    meaning: str


@dataclass(frozen=True)
class Glossary:
    """One legend section: its title, and the entries under it."""

    title: str
    entries: list[Entry]


class Format(Protocol):
    """How one output format spells what a walk emits."""

    #: The notation a symbol table must be written in.
    notation: ClassVar[Notation]
    #: Spelling for each of :data:`OPERATOR_NAMES`.
    operators: ClassVar[Mapping[OperatorName, str]]
    #: The em dash in prose: TeX and Typst read ``---`` as one, Markdown does not.
    dash: ClassVar[str]
    #: Between the rows of a ``cases`` block.
    cases_row: ClassVar[str]

    # -- atoms -------------------------------------------------------------

    def italic(self, name: str) -> str:
        """A multi-letter name, set as one italic symbol rather than a product."""
        ...

    def upright(self, name: str) -> str:
        """A qualifier or a function name — upright, because it is not a variable."""
        ...

    def script(self, letter: str) -> str:
        """A set symbol."""
        ...

    def greek(self, name: str) -> str:
        """A lower-case name that *is* a Greek letter, set as the letter."""
        ...

    def prose(self, text: str) -> str:
        """Words inside math."""
        ...

    def quoted(self, label: str) -> str:
        """A string value as the file spells it — quoted, so a label reads as data rather than a name."""
        ...

    def mono(self, text: str) -> str:
        """A name exactly as the YAML spells it."""
        ...

    def escape(self, prose: str) -> str:
        """Author prose — a ``description:`` — made safe for this format's text mode."""
        ...

    def math(self, expression: str) -> str:
        """Wrap bare math for embedding in prose."""
        ...

    # -- structure ---------------------------------------------------------

    def subscript(self, base: str, indices: list[str]) -> str: ...

    def superscript(self, base: str, tail: str) -> str: ...

    def parenthesise(self, inner: str) -> str: ...

    def cardinality(self, inner: str) -> str:
        """An absolute-value fence: ``|x|``."""
        ...

    def fraction(self, numerator: str, denominator: str) -> str: ...

    def summation(self, domain: str, body: str) -> str: ...

    def cases(self, arms: list[tuple[str, str]]) -> str:
        """A value defined by region: ``(value, condition)`` per arm, in order."""
        ...

    def apply(self, function: str, argument: str) -> str:
        """A function applied to an argument: ``f(x)``."""
        ...

    def joined(self, parts: list[str], operator: str) -> str:
        """``a op b op c`` — the one place inter-term spacing is decided."""
        ...

    # -- document ----------------------------------------------------------

    def equations(self, lines: list[Line], *, numbered: bool) -> str: ...

    def glossary(self, title: str, entries: list[Entry]) -> str: ...

    def section(self, title: str, body: str) -> str: ...

    def note(self, text: str) -> str:
        """A paragraph of plain prose between blocks."""
        ...

    def document(self, blocks: list[str], *, standalone: bool) -> str: ...


def aligned_rows(lines: list[Line], fmt: Format, *, gap: str) -> list[str]:
    """One alignment row per line — label, left, right, condition — *gap* around the relation, trailing empty cells stripped."""
    return [
        f'{fmt.prose(line.label) if line.label else ""}{gap}{line.left} & {line.right}{gap}{line.condition}'.rstrip(
            ' &'
        )
        for line in lines
    ]


def paragraphs(blocks: list[str]) -> str:
    """*blocks* separated by blank lines, ending in a newline."""
    return '\n\n'.join(blocks) + '\n'
