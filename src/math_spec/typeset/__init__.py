"""Typeset a validated model — a *reading* of the math, not a lane.

SPIKE. A third consumer of the resolved core AST, and deliberately not a
backend: it produces no model, binds no data and never touches the plan. It
exists because the file's whole point is that the math is declared, and a
declared thing can be printed the way a paper prints it — which is also the
cheapest review tool we have for "does this YAML say what I meant".

It reads the same seam both lanes read (hard rule 1): expand ``piecewise:``,
resolve names to typed nodes, then walk. Because expansion runs first, a
``piecewise:`` block prints as the λ-formulation it *is* rather than as the
sugar it was written as — the honest rendering, if a verbose one.

**One walk, many formats.** ``walk.py`` decides everything about the math and
nothing about the syntax; a :class:`~lpspec.typeset.format.Format` decides only
how to spell it. See the [README](README.md) for what adding one costs.

Symbols are **derived** by default, so it prints with no setup at all, and
derivation aims at unambiguous rather than beautiful. A
:class:`~lpspec.typeset.symbols.SymbolTable` (a sidecar YAML, ``--symbols``)
is what makes it conventional.

What it does not do: line-breaking — a wide equation runs off the page.

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
from lpspec.language.validation import load_schema
from lpspec.typeset.latex import LatexFormat
from lpspec.typeset.markdown import MarkdownFormat
from lpspec.typeset.symbols import Symbols, SymbolTable
from lpspec.typeset.typst import TypstFormat
from lpspec.typeset.walk import Walk

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from lpspec.language.schema import MathSchema
    from lpspec.typeset.format import Format

__all__ = ['FORMATS', 'SymbolTable', 'to_latex', 'to_markdown', 'to_typst', 'typeset']

#: Every format, by the name the CLI takes. Adding one is a module plus a row.
FORMATS: dict[str, Format] = {
    'latex': LatexFormat(),
    'markdown': MarkdownFormat(),
    'typst': TypstFormat(),
}


def typeset(
    model: str | Path | dict[str, Any] | MathSchema,
    fmt: Format,
    *,
    symbols: str | Path | Mapping[str, Any] | SymbolTable | None = None,
    standalone: bool = False,
    legend: bool = True,
    numbered: bool = True,
) -> str:
    """Render *model* in *fmt*.

    Accepts anything :func:`lpspec.load_schema` accepts. ``symbols`` is an
    optional :class:`SymbolTable` — a path, a mapping, or the object — saying
    how names should print; everything it does not name is derived.
    ``standalone`` emits a compilable document rather than a fragment;
    ``legend`` prepends the sets / parameters / variables table; ``numbered``
    numbers the equations.

    The model is validated on the way in, so a file that does not compile does
    not print either — the error is the same one :func:`lpspec.check` raises.
    A symbol table is checked against it too: an entry naming nothing in the
    model is an error, since the alternative is a symbol that silently never
    applies.
    """
    schema = expand_piecewise(load_schema(model))
    table = symbols if isinstance(symbols, SymbolTable) else SymbolTable.load(symbols or {})
    walk = Walk(schema, Namespace.of(schema), Symbols(schema, fmt, table.checked_against(schema)), fmt)

    # The walk runs before the legend is assembled: `saw_wraparound` is
    # something it *discovers*, and the legend has to explain what was emitted.
    sections = [
        ('Objective', walk.objectives()),
        ('Subject to', walk.constraints()),
        ('Variable domains', walk.variables()),
    ]
    rendered = [fmt.section(title, fmt.equations(lines, numbered=numbered)) for title, lines in sections if lines]

    blocks = []
    if legend:
        blocks += [fmt.glossary(title, entries) for title, entries in walk.glossaries()]
        if walk.saw_wraparound:
            blocks.append(fmt.note(walk.wraparound_note()))
    return fmt.document([*blocks, *rendered], standalone=standalone)


def to_latex(model: str | Path | dict[str, Any] | MathSchema, **options: Any) -> str:
    """Render *model* as LaTeX (amsmath ``align``). See :func:`typeset`."""
    return typeset(model, FORMATS['latex'], **options)


def to_typst(model: str | Path | dict[str, Any] | MathSchema, **options: Any) -> str:
    """Render *model* as Typst. See :func:`typeset`."""
    return typeset(model, FORMATS['typst'], **options)


def to_markdown(model: str | Path | dict[str, Any] | MathSchema, **options: Any) -> str:
    """Render *model* as GitHub-flavoured Markdown. See :func:`typeset`."""
    return typeset(model, FORMATS['markdown'], **options)
