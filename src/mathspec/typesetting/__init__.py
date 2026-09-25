# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Typeset a validated model — a *reading* of the math.

Symbols are **derived** by default, aiming at unambiguous rather than
beautiful, so it prints with no setup; a
:class:`~mathspec.typesetting.symbols.SymbolTable` (``--symbols``) makes it
conventional. It does not line-break: a wide equation runs off the page.

Usage::

    import mathspec

    print(mathspec.to_latex('model.yaml'))
    print(mathspec.to_typst('model.yaml', standalone=True))
    print(mathspec.to_markdown('model.yaml'))  # renders as-is on GitHub
    print(mathspec.to_latex('model.yaml', symbols='model.symbols.yaml'))

or from a shell::

    python -m mathspec latex model.yaml --symbols model.symbols.yaml --standalone -o model.tex
    python -m mathspec typst model.yaml --standalone -o model.typ
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypedDict, Unpack

from mathspec.errors import SchemaError
from mathspec.program import Program
from mathspec.typesetting.latex import LatexFormat
from mathspec.typesetting.legend import Legend, notice
from mathspec.typesetting.markdown import MarkdownFormat
from mathspec.typesetting.symbols import SymbolTable, symbols_for
from mathspec.typesetting.typst import TypstFormat
from mathspec.typesetting.walk import Walk
from mathspec.validation import to_spec

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from mathspec.model import Spec
    from mathspec.typesetting.format import Format

__all__ = [
    'FORMATS',
    'FormatName',
    'SymbolTable',
    'to_latex',
    'to_markdown',
    'to_typst',
    'typeset',
    'typeset_declaration',
]

#: A format by the name the CLI takes — what every renderer here is asked for.
FormatName = Literal['latex', 'markdown', 'typst']

#: Every format, by name. Adding one is a module plus a row.
FORMATS: dict[FormatName, Format] = {
    'latex': LatexFormat(),
    'markdown': MarkdownFormat(),
    'typst': TypstFormat(),
}


class _Options(TypedDict, total=False):
    """The keyword arguments :func:`typeset` takes, which the three per-format doors forward whole."""

    symbols: str | Path | Mapping[str, object] | SymbolTable | None
    standalone: bool
    legend: bool
    numbered: bool
    inline_expressions: bool


def _walk(
    model: str | Path | Mapping[str, object] | Spec | Program,
    fmt: FormatName,
    symbols: str | Path | Mapping[str, object] | SymbolTable | None,
    *,
    inline_expressions: bool,
) -> Walk:
    """The loaded, symbol-resolved walk every renderer builds from model, format and table."""
    if fmt not in FORMATS:
        msg = f"'{fmt}' is not a format this package prints. Formats: {', '.join(FORMATS)}."
        raise ValueError(msg)
    program = model if isinstance(model, Program) else to_spec(model).program
    format_ = FORMATS[fmt]
    if symbols is None:
        symbols = SymbolTable(format_.notation)
    table = symbols if isinstance(symbols, SymbolTable) else SymbolTable.load(symbols)
    return Walk(
        program,
        symbols_for(program, format_, table.checked_against(program)),
        format_,
        inline_expressions=inline_expressions,
    )


def typeset(
    model: str | Path | Mapping[str, object] | Spec | Program,
    fmt: FormatName,
    *,
    symbols: str | Path | Mapping[str, object] | SymbolTable | None = None,
    standalone: bool = False,
    legend: bool = True,
    numbered: bool = True,
    inline_expressions: bool = False,
) -> str:
    """Render *model*'s math in *fmt*.

    Args:
        model: Anything :func:`mathspec.to_spec` accepts, or a
            :class:`~mathspec.program.Program`. A ``Spec`` or a ``Program``
            is rendered as it stands, so printing one model in several formats
            reads and checks the file once rather than once per format, and a
            curve prints as the curve it states. Pass ``spec.expand()`` for the rows a solver holds
            instead.
        fmt: What spells the math — a key of :data:`FORMATS`.
        symbols: How names print, as a :class:`SymbolTable`, a path or a
            mapping. Names it does not carry are derived, and it must be
            written in *fmt*'s notation.
        standalone: Emit a compilable document rather than a fragment.
        legend: Prepend the sets/parameters/variables table. The model's own
            ``description:`` opens the document either way — it is what the
            file says it is, not a symbol table.
        numbered: Number the equations.
        inline_expressions: Substitute each plain named expression into the equations that
            use it, rather than printing its symbol there and its definition
            once. A cased expression is a definition either way: its block is
            taller than the line it would sit in.

    Returns:
        The rendered text.

    Raises:
        ValueError: *fmt* names no format.
        LanguageError: A model that does not compile; it does not print.
        SchemaError: A symbol table entry naming nothing in the model, or a
            table written in a notation *fmt* does not read.
    """
    walk = _walk(model, fmt, symbols, inline_expressions=inline_expressions)
    program, format_ = walk.program, walk.format

    rendered = [
        format_.section(title, format_.equations(lines, numbered=numbered))
        for title, lines in walk.equations()
        if lines
    ]

    blocks = [format_.note(format_.escape(program.description))] if program.description else []
    if legend:
        explained, noticed = Legend(program, walk.symbols, format_), notice(program)
        blocks += [
            format_.section(title, format_.glossary(entries))
            for title, entries in explained.glossaries(noticed, walk.defined())
        ]
        blocks += [format_.note(text) for text in explained.convention_notes()]
        blocks += [format_.note(text) for text in explained.translation_notes(noticed)]
        blocks += [format_.note(text) for text in explained.position_notes(noticed)]
    return format_.document([*blocks, *rendered], standalone=standalone)


def typeset_declaration(
    model: str | Path | Mapping[str, object] | Spec | Program,
    name: str,
    fmt: FormatName,
    *,
    symbols: str | Path | Mapping[str, object] | SymbolTable | None = None,
    inline_expressions: bool = True,
) -> str:
    """Render one declaration as the bare line the document prints for it.

    The line the whole-model render prints for it — a named expression's
    definition, a constraint, an assumption, a ``piecewise:`` curve, or a
    variable's domain, quantifier included —
    with no document, label, equation number or math delimiters around it, for
    a math context the caller lays out: a docstring, a table cell. A line on
    its own has no Definitions section beside it, so the plain named
    expressions it uses are substituted unless *inline_expressions* says otherwise; a cased
    one prints by symbol, and a second call with its name prints its block.

    Args:
        model: Anything :func:`mathspec.to_spec` accepts, or a :class:`~mathspec.program.Program`.
        name: A named expression, constraint, assumption, ``piecewise:``
            block or variable the model declares.
        fmt: What spells the math — a key of :data:`FORMATS`.
        symbols: How names print; see :func:`typeset`.
        inline_expressions: Substitute the plain named expressions the line uses, so it
            stands on its own; ``False`` prints their symbols, as the document
            does. A plain expression asked for by name prints its definition
            either way.

    Returns:
        The line, math only.

    Raises:
        ValueError: *fmt* names no format.
        LanguageError: A model that does not compile; it does not print.
        SchemaError: *name* is declared as none of the five, as two — a
            constraint may share a variable's name — or under ``given:``, which
            prints in the legend rather than as a line; or a symbol table entry
            names nothing in the model.
    """
    walk = _walk(model, fmt, symbols, inline_expressions=inline_expressions)
    given = walk.program.given
    givens = {
        'parameter': given.parameters,
        'variable': given.variables,
        'expression': given.expressions,
        'constraint': given.constraints,
    }
    given_kind = next((kind for kind, group in givens.items() if name in group), None)
    if given_kind is not None:
        msg = (
            f"'{name}' is a given {given_kind}, and a given declaration prints no line of its own — "
            f"this file reads it and does not build it. It prints in the legend, under 'Given', "
            f'so call typeset() for the whole model.'
        )
        raise SchemaError(msg)
    return walk.format.equation(walk.line(name))


def to_latex(model: str | Path | Mapping[str, object] | Spec | Program, **options: Unpack[_Options]) -> str:
    """Render *model* as LaTeX (amsmath ``align``). See :func:`typeset`."""
    return typeset(model, 'latex', **options)


def to_typst(model: str | Path | Mapping[str, object] | Spec | Program, **options: Unpack[_Options]) -> str:
    """Render *model* as Typst. See :func:`typeset`."""
    return typeset(model, 'typst', **options)


def to_markdown(model: str | Path | Mapping[str, object] | Spec | Program, **options: Unpack[_Options]) -> str:
    """Render *model* as GitHub-flavoured Markdown. See :func:`typeset`."""
    return typeset(model, 'markdown', **options)
