# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

r"""The seam between *what* a model says and *how* a format spells it.

One walk, many formats — the split ``relational/sinks/`` makes at the other end
of the pipeline. :mod:`math_spec.typeset.walk` decides where a bracket is needed,
which dimension a reduction binds and where a mask belongs; a :class:`Format`
decides only that a sum is ``\sum_{…}`` or ``sum_(…)``.

Two rules make the split hold:

- **Everything a walk emits is *bare math*.** No ``$``, no environment; a
  format wraps it with :meth:`Format.math` to embed it in prose, so the walk
  never knows which mode it is in.
- **A format spells; it never decides.** No method takes an AST node or a
  schema. If a format had to look at the model, the question belongs in the
  walk.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping

#: Every operator a walk can emit, by the name the walk uses for it. A format
#: supplies one spelling each, and ``tests/typeset/test_typeset.py`` asserts every
#: format covers exactly this set, so a missing key is a test failure rather
#: than a stray ``None`` in the output. The less obvious names: ``such_that``
#: is the colon in "∀ t ∈ T : condition", ``times`` sits between sets in the
#: legend, ``maps_to`` is the → in a coordinate map. The three translations get
#: one operator each because they are three models: plain ``minus``/``plus``
#: leaves the vacated position absent, ``cyclic_*`` is ``roll``'s wrapping
#: translation, and ``edge_*`` fills that position with the value it carries as
#: a subscript.
OPERATOR_NAMES = frozenset(
    {
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
        'true',
        'false',
        'forall',
        'such_that',
        'infinity',
        'minus_infinity',
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
    }
)


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
    """One legend row: a symbol, the name it stands for, and what it is."""

    symbol: str
    name: str
    detail: str = ''
    description: str = ''

    def meaning(self, dash: str) -> str:
        """Everything opposite the symbol, as one string.

        What the row *says* is the walk's answer, not a spelling, so the three
        formats differ only in the table cell they put it in — and in how
        they spell the dash between a name and its description, which is the
        one piece of punctuation here that is not the same in all three.
        """
        return f'{self.name}{self.detail}' + (f' {dash} {self.description}' if self.description else '')


@dataclass(frozen=True)
class Glossary:
    """One legend section: its title, and the entries under it."""

    title: str
    entries: list[Entry]


class Format(Protocol):
    """How one output format spells what a walk emits."""

    #: File suffix, for the CLI's default output name.
    suffix: ClassVar[str]
    #: The notation a symbol table must be written in — ``latex`` or ``typst``;
    #: markdown reads ``latex``, its math being MathJax's.
    notation: ClassVar[str]
    #: Spelling for each of :data:`OPERATOR_NAMES`.
    operators: ClassVar[Mapping[str, str]]
    #: The em dash, in prose. TeX and Typst both read ``---`` as one and set
    #: it as a dash; Markdown has no such rule and renders three hyphens, so
    #: the character itself is what a Markdown reader has to be given. It is
    #: an atom rather than something the walk spells because the walk is
    #: format-agnostic exactly where this appears — a legend row, a
    #: translation note.
    dash: ClassVar[str]

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

    def prose(self, text: str) -> str:
        """Words inside math."""
        ...

    def mono(self, text: str) -> str:
        """A name exactly as the YAML spells it."""
        ...

    def escape(self, prose: str) -> str:
        """Author prose, made safe for this format's text mode.

        Every other atom escapes as it wraps, so what passes through here is
        what arrives already being prose — a ``description:``. Not
        :meth:`prose`, which is words *inside* math, and not :meth:`note`,
        which is handed generated markup too.
        """
        ...

    def math(self, expression: str) -> str:
        """Wrap bare math for embedding in prose."""
        ...

    # -- structure ---------------------------------------------------------

    def subscript(self, base: str, indices: list[str]) -> str: ...

    def superscript(self, base: str, tail: str) -> str: ...

    def parenthesise(self, inner: str) -> str: ...

    def cardinality(self, inner: str) -> str:
        """How many members a set has: ``|T|``.

        A fence rather than an entry in :data:`OPERATOR_NAMES`, which is a
        vocabulary of *infix* spellings — ``tests/typeset/test_typeset.py``
        compiles every one of them between two operands.
        """
        ...

    def fraction(self, numerator: str, denominator: str) -> str: ...

    def summation(self, domain: str, body: str) -> str: ...

    def apply(self, function: str, argument: str) -> str:
        """A coordinate map applied to an index: ``bus(g)``."""
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
