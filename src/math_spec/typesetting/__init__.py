# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Typeset a validated model — a *reading* of the math.

Symbols are **derived** by default, aiming at unambiguous rather than
beautiful, so it prints with no setup; a
:class:`~math_spec.typesetting.symbols.SymbolTable` (``--symbols``) makes it
conventional. It does not line-break: a wide equation runs off the page.

Usage::

    import math_spec

    print(math_spec.to_latex('model.yaml'))
    print(math_spec.to_typst('model.yaml', standalone=True))
    print(math_spec.to_markdown('model.yaml'))  # renders as-is on GitHub
    print(math_spec.to_latex('model.yaml', symbols='model.symbols.yaml'))

or from a shell::

    python -m math_spec latex model.yaml --symbols model.symbols.yaml --standalone -o model.tex
    python -m math_spec typst model.yaml --standalone -o model.typ
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from math_spec.errors import SchemaError, did_you_mean
from math_spec.piecewise import expand_piecewise
from math_spec.resolution import Namespace
from math_spec.typesetting.latex import LatexFormat
from math_spec.typesetting.markdown import MarkdownFormat
from math_spec.typesetting.symbols import Symbols, SymbolTable
from math_spec.typesetting.typst import TypstFormat
from math_spec.typesetting.walk import Walk
from math_spec.validation import to_spec

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from math_spec.model import Spec
    from math_spec.typesetting.format import Format

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


def _walk(
    model: str | Path | dict[str, Any] | Spec,
    fmt: FormatName,
    symbols: str | Path | Mapping[str, Any] | SymbolTable | None,
    *,
    inline_expressions: bool,
) -> Walk:
    """The loaded, symbol-resolved walk every renderer builds from model, format and table."""
    if fmt not in FORMATS:
        msg = f"'{fmt}' is not a format this package prints. Formats: {', '.join(FORMATS)}."
        raise ValueError(msg)
    schema = expand_piecewise(to_spec(model))
    namespace = Namespace.of(schema)
    format_ = FORMATS[fmt]
    if symbols is None:
        symbols = SymbolTable(format_.notation)
    table = symbols if isinstance(symbols, SymbolTable) else SymbolTable.load(symbols)
    return Walk(
        schema,
        namespace,
        Symbols(schema, namespace, format_, table.checked_against(schema)),
        format_,
        inline_expressions=inline_expressions,
    )


def typeset(
    model: str | Path | dict[str, Any] | Spec,
    fmt: FormatName,
    *,
    symbols: str | Path | Mapping[str, Any] | SymbolTable | None = None,
    standalone: bool = False,
    legend: bool = True,
    numbered: bool = True,
    inline_expressions: bool = False,
) -> str:
    """Render *model*'s math in *fmt*.

    Args:
        model: Anything :func:`math_spec.to_spec` accepts. A
            :class:`~math_spec.model.Spec` is rendered as it stands, so
            printing one model in several formats reads and checks the file
            once rather than once per format.
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
    schema, format_ = walk.schema, walk.format

    sections, noticed = walk.equations()
    rendered = [
        format_.section(title, format_.equations(lines, numbered=numbered)) for title, lines in sections if lines
    ]

    blocks = [format_.note(format_.escape(schema.description))] if schema.description else []
    if legend:
        blocks += [format_.glossary(group.title, group.entries) for group in walk.glossaries(noticed)]
        blocks += [format_.note(text) for text in walk.convention_notes()]
        blocks += [format_.note(text) for text in walk.translation_notes(noticed)]
        blocks += [format_.note(text) for text in walk.position_notes(noticed)]
    return format_.document([*blocks, *rendered], standalone=standalone)


def typeset_declaration(
    model: str | Path | dict[str, Any] | Spec,
    name: str,
    fmt: FormatName,
    *,
    symbols: str | Path | Mapping[str, Any] | SymbolTable | None = None,
    inline_expressions: bool = True,
) -> str:
    """Render one declaration as the bare line the document prints for it.

    The line the whole-model render prints for it — a named expression's
    definition, a constraint, or a variable's domain, quantifier included —
    with no document, label, equation number or math delimiters around it, for
    a math context the caller lays out: a docstring, a table cell. A line on
    its own has no Definitions section beside it, so the plain named
    expressions it uses are substituted unless *inline_expressions* says otherwise; a cased
    one prints by symbol, and a second call with its name prints its block.

    Args:
        model: Anything :func:`math_spec.to_spec` accepts.
        name: A named expression, constraint or variable the model declares.
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
        SchemaError: *name* is declared as none of the three, or as two — a
            constraint may share a variable's name; or a symbol table entry
            names nothing in the model.
    """
    walk = _walk(model, fmt, symbols, inline_expressions=inline_expressions)
    schema = walk.schema
    kinds = {'named expression': schema.expressions, 'constraint': schema.constraints, 'variable': schema.variables}
    found = [kind for kind, group in kinds.items() if name in group]
    if not found:
        everything = {n for group in kinds.values() for n in group}
        msg = f"'{name}' is not a named expression, constraint or variable. {did_you_mean(name, everything)}"
        raise SchemaError(msg)
    if len(found) > 1:
        msg = f"'{name}' is both a {found[0]} and a {found[1]}, and one line prints one of them — rename one."
        raise SchemaError(msg)
    return walk.format.equation(walk.line(name))


def to_latex(model: str | Path | dict[str, Any] | Spec, **options: Any) -> str:
    """Render *model* as LaTeX (amsmath ``align``). See :func:`typeset`."""
    return typeset(model, 'latex', **options)


def to_typst(model: str | Path | dict[str, Any] | Spec, **options: Any) -> str:
    """Render *model* as Typst. See :func:`typeset`."""
    return typeset(model, 'typst', **options)


def to_markdown(model: str | Path | dict[str, Any] | Spec, **options: Any) -> str:
    """Render *model* as GitHub-flavoured Markdown. See :func:`typeset`."""
    return typeset(model, 'markdown', **options)
