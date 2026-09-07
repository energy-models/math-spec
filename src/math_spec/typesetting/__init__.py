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

from typing import TYPE_CHECKING, Any

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

__all__ = ['FORMATS', 'SymbolTable', 'to_latex', 'to_markdown', 'to_typst', 'typeset', 'typeset_expression']

#: Every format, by the name the CLI takes. Adding one is a module plus a row.
FORMATS: dict[str, Format] = {
    'latex': LatexFormat(),
    'markdown': MarkdownFormat(),
    'typst': TypstFormat(),
}


def _walk(
    model: str | Path | dict[str, Any] | Spec, fmt: Format, symbols: str | Path | Mapping[str, Any] | SymbolTable | None
) -> Walk:
    """The loaded, symbol-resolved walk both renderers build from model, format and table."""
    schema = expand_piecewise(to_spec(model))
    namespace = Namespace.of(schema)
    if symbols is None:
        symbols = SymbolTable(fmt.notation)
    table = symbols if isinstance(symbols, SymbolTable) else SymbolTable.load(symbols)
    return Walk(schema, namespace, Symbols(schema, namespace, fmt, table.checked_against(schema)), fmt)


def typeset(
    model: str | Path | dict[str, Any] | Spec,
    fmt: Format,
    *,
    symbols: str | Path | Mapping[str, Any] | SymbolTable | None = None,
    standalone: bool = False,
    legend: bool = True,
    numbered: bool = True,
) -> str:
    """Render *model*'s math in *fmt*.

    Args:
        model: Anything :func:`math_spec.to_spec` accepts. A
            :class:`~math_spec.model.Spec` is rendered as it stands, so
            printing one model in several formats reads and checks the file
            once rather than once per format.
        fmt: What spells the math — one of :data:`FORMATS`.
        symbols: How names print, as a :class:`SymbolTable`, a path or a
            mapping. Names it does not carry are derived, and it must be
            written in *fmt*'s notation.
        standalone: Emit a compilable document rather than a fragment.
        legend: Prepend the sets/parameters/variables table. The model's own
            ``description:`` opens the document either way — it is what the
            file says it is, not a symbol table.
        numbered: Number the equations.

    Returns:
        The rendered text.

    Raises:
        LanguageError: A model that does not compile; it does not print.
        SchemaError: A symbol table entry naming nothing in the model, or a
            table written in a notation *fmt* does not read.
    """
    walk = _walk(model, fmt, symbols)
    schema = walk.schema

    sections, noticed = walk.equations()
    rendered = [fmt.section(title, fmt.equations(lines, numbered=numbered)) for title, lines in sections if lines]

    blocks = [fmt.note(fmt.escape(schema.description))] if schema.description else []
    if legend:
        blocks += [fmt.glossary(group.title, group.entries) for group in walk.glossaries(noticed)]
        blocks += [fmt.note(text) for text in walk.convention_notes()]
        blocks += [fmt.note(text) for text in walk.translation_notes(noticed)]
        blocks += [fmt.note(text) for text in walk.position_notes(noticed)]
    return fmt.document([*blocks, *rendered], standalone=standalone)


def typeset_expression(
    model: str | Path | dict[str, Any] | Spec,
    name: str,
    fmt: Format,
    *,
    symbols: str | Path | Mapping[str, Any] | SymbolTable | None = None,
) -> str:
    """Render one named expression's defining equation as a bare fragment.

    ``symbol = body`` in *fmt*'s notation, with no document, legend, equation
    number or math delimiters around it — for placing in a math context the
    caller controls. A cased expression prints its ``cases`` layout; a plain one
    prints the affine body it expands to, under a symbol derived on the spot,
    since the language substitutes a plain expression away and prints no symbol
    for it elsewhere.

    Args:
        model: Anything :func:`math_spec.to_spec` accepts.
        name: A named expression the model declares.
        fmt: What spells the math — one of :data:`FORMATS`.
        symbols: How names print; see :func:`typeset`. A plain expression's own
            symbol is always derived — a table names only what the whole-model
            render prints, which a plain expression is not.

    Returns:
        The fragment, math only.

    Raises:
        LanguageError: A model that does not compile; it does not print.
        SchemaError: *name* is not a named expression, or a symbol table entry
            names nothing in the model.
    """
    walk = _walk(model, fmt, symbols)
    if name not in walk.schema.expressions:
        raise SchemaError(f"'{name}' is not a named expression. {did_you_mean(name, set(walk.schema.expressions))}")
    return walk.definition(name)


def to_latex(model: str | Path | dict[str, Any] | Spec, **options: Any) -> str:
    """Render *model* as LaTeX (amsmath ``align``). See :func:`typeset`."""
    return typeset(model, FORMATS['latex'], **options)


def to_typst(model: str | Path | dict[str, Any] | Spec, **options: Any) -> str:
    """Render *model* as Typst. See :func:`typeset`."""
    return typeset(model, FORMATS['typst'], **options)


def to_markdown(model: str | Path | dict[str, Any] | Spec, **options: Any) -> str:
    """Render *model* as GitHub-flavoured Markdown. See :func:`typeset`."""
    return typeset(model, FORMATS['markdown'], **options)
