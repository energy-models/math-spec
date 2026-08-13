"""Typeset a validated model — a *reading* of the math, not a lane.

SPIKE. A third consumer of the resolved core AST, deliberately not a backend:
it produces no model, binds no data and never touches the plan. It exists
because a declared thing can be printed the way a paper prints it, which is the
cheapest review tool available for "does this YAML say what I meant".

It reads the same seam both lanes read (hard rule 1): expand ``piecewise:``,
resolve names, walk. Expansion runs first, so a ``piecewise:`` block prints as
the λ-formulation it *is* rather than the sugar it was written as.

**One walk, many formats.** ``walk.py`` decides everything about the math and
nothing about the syntax; a :class:`~lpspec.typeset.format.Format` decides only
how to spell it. See the [README](README.md) for what adding one costs.

Symbols are **derived** by default, aiming at unambiguous rather than
beautiful, so it prints with no setup; a
:class:`~lpspec.typeset.symbols.SymbolTable` (``--symbols``) makes it
conventional. It does not line-break: a wide equation runs off the page.

Usage::

    import lpspec as lps

    print(lps.to_latex('model.yaml'))
    print(lps.to_typst('model.yaml', standalone=True))
    print(lps.to_markdown('model.yaml'))  # renders as-is on GitHub
    print(lps.to_latex('model.yaml', symbols='model.symbols.yaml'))

or from a shell::

    python -m lpspec latex model.yaml --symbols model.symbols.yaml --standalone -o model.tex
    python -m lpspec typst model.yaml --standalone -o model.typ
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lpspec.language.piecewise import expand_piecewise
from lpspec.language.resolution import Namespace
from lpspec.language.validation import load_model
from lpspec.typeset.latex import LatexFormat
from lpspec.typeset.markdown import MarkdownFormat
from lpspec.typeset.symbols import Symbols, SymbolTable
from lpspec.typeset.typst import TypstFormat
from lpspec.typeset.walk import Walk

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from lpspec.language.model import Model
    from lpspec.typeset.format import Format

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
        model: Anything :func:`lpspec.load_model` accepts.
        fmt: What spells the math — one of :data:`FORMATS`.
        symbols: How names print, as a :class:`SymbolTable`, a path or a
            mapping. Names it does not carry are derived.
        standalone: Emit a compilable document rather than a fragment.
        legend: Prepend the sets/parameters/variables table.
        numbered: Number the equations.

    Returns:
        The rendered text.

    Raises:
        LanguageError: A model that does not compile; it does not print.
        SchemaError: A symbol table entry naming nothing in the model.
    """
    schema = expand_piecewise(load_model(model))
    table = symbols if isinstance(symbols, SymbolTable) else SymbolTable.load(symbols or {})
    walk = Walk(schema, Namespace.of(schema), Symbols(schema, fmt, table.checked_against(schema)), fmt)

    sections = [
        ('Objective', walk.objectives()),
        ('Subject to', walk.constraints()),
        ('Variable domains', walk.variables()),
    ]
    rendered = [fmt.section(title, fmt.equations(lines, numbered=numbered)) for title, lines in sections if lines]

    blocks = []
    if legend:
        blocks += [fmt.glossary(group.title, group.entries) for group in walk.glossaries()]
        if walk.saw_wraparound:
            blocks.append(fmt.note(walk.wraparound_note()))
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
