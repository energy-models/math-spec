# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Typeset a validated model — a *reading* of the math.

A consumer of the resolved core AST that produces no model and binds no data.
It exists because a declared thing can be printed the way a paper prints it,
which is the cheapest review tool available for "does this YAML say what I
meant".

It reads the model as :func:`~math_spec.load_model` validates it: expand
``piecewise:``, resolve names, walk. Expansion runs first, so a ``piecewise:``
block prints as the λ-formulation it *is* rather than the sugar it was written
as.

**One walk, many formats** — the split is :mod:`math_spec.typesetting.format`'s.

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

from math_spec import Namespace, expand_piecewise, load_model
from math_spec.typesetting.latex import LatexFormat
from math_spec.typesetting.markdown import MarkdownFormat
from math_spec.typesetting.symbols import Symbols, SymbolTable
from math_spec.typesetting.typst import TypstFormat
from math_spec.typesetting.walk import Walk

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from math_spec import Model
    from math_spec.typesetting.format import Format

__all__ = ['FORMATS', 'SymbolTable', 'to_latex', 'to_markdown', 'to_typst', 'typeset']

#: Every format, by the name the CLI takes. Adding one is a module plus a row.
FORMATS: dict[str, Format] = {
    'latex': LatexFormat(),
    'markdown': MarkdownFormat(),
    'typst': TypstFormat(),
}


def typeset(
    model: str | Path | dict[str, Any] | Model,
    fmt: Format,
    *,
    symbols: str | Path | Mapping[str, Any] | SymbolTable | None = None,
    standalone: bool = False,
    legend: bool = True,
    numbered: bool = True,
) -> str:
    """Render *model*'s math in *fmt*.

    Args:
        model: Anything :func:`math_spec.load_model` accepts.
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
    schema = expand_piecewise(load_model(model))
    if symbols is None:
        symbols = SymbolTable(fmt.notation)
    table = symbols if isinstance(symbols, SymbolTable) else SymbolTable.load(symbols)
    walk = Walk(schema, Namespace.of(schema), Symbols(schema, fmt, table.checked_against(schema)), fmt)

    sections = [
        ('Objective', walk.objective()),
        ('Subject to', walk.constraints()),
        ('Definitions', walk.definitions()),
        ('Variable domains', walk.variables()),
    ]
    rendered = [fmt.section(title, fmt.equations(lines, numbered=numbered)) for title, lines in sections if lines]

    blocks = [fmt.note(fmt.escape(schema.description))] if schema.description else []
    if legend:
        blocks += [fmt.glossary(group.title, group.entries) for group in walk.glossaries()]
        blocks += [fmt.note(text) for text in walk.convention_notes()]
        blocks += [fmt.note(text) for text in walk.translation_notes()]
        blocks += [fmt.note(text) for text in walk.position_notes()]
    return fmt.document([*blocks, *rendered], standalone=standalone)


def to_latex(model: str | Path | dict[str, Any] | Model, **options: Any) -> str:
    """Render *model* as LaTeX (amsmath ``align``). See :func:`typeset`."""
    return typeset(model, FORMATS['latex'], **options)


def to_typst(model: str | Path | dict[str, Any] | Model, **options: Any) -> str:
    """Render *model* as Typst. See :func:`typeset`."""
    return typeset(model, FORMATS['typst'], **options)


def to_markdown(model: str | Path | dict[str, Any] | Model, **options: Any) -> str:
    """Render *model* as GitHub-flavoured Markdown. See :func:`typeset`."""
    return typeset(model, FORMATS['markdown'], **options)
