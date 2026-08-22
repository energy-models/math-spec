# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Which symbol each declared name prints as — and the sidecar that overrides it.

Derivation aims at *unambiguous*, not beautiful: it runs with no setup, so it
has to be right rather than elegant. :class:`SymbolTable` is where a reader
makes it conventional, in a file of its own — presentation is not language, so
it never becomes keys on ``Model``. What a declaration *is* travels the other
way: ``description:`` is a key on the declaration, because it is the model
talking about itself rather than a reader choosing notation.

This module decides *which* symbol a name gets; a
:class:`~math_spec.typeset.format.Format` decides how it is written.
"""

from __future__ import annotations

import string
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from math_spec import read_yaml
from math_spec.errors import SchemaError, did_you_mean

if TYPE_CHECKING:
    from math_spec import Buildable
    from math_spec.typeset.format import Format

__all__ = ['SymbolTable', 'Symbols']

#: Dimensions whose conventional index letter is not their own first letter.
#: Small on purpose — a lookup table of everybody's naming habits is a
#: maintenance sink; anything unlisted falls back to its own initial.
_INDEX_ALIASES = {'snapshot': 't', 'snapshots': 't', 'time': 't', 'timestep': 't', 'timesteps': 't'}


#: Names that are a Greek letter written out. A variable called ``theta``
#: printed as the italic word *theta* is the one derived symbol a paper would
#: never accept, and the fix is the same shape as ``_INDEX_ALIASES``: a small
#: curated map, with ``--symbols`` for anything it does not know. Lower case
#: only — every one of these has a letter in LaTeX and in Typst, which the
#: capitals do not, and ``omicron`` is left out because LaTeX spells it ``o``.
_GREEK = frozenset(
    {
        'alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 'theta',
        'iota', 'kappa', 'lambda', 'mu', 'nu', 'xi', 'rho', 'sigma', 'tau',
        'upsilon', 'phi', 'chi', 'psi', 'omega',
    }
)  # fmt: skip


def _word(name: str, fmt: Format, *, given: bool) -> str:
    r"""One name as one symbol, upright where it is *given*.

    **Upright is what the data supplies; italic is what the solver chooses.**
    Which of the two a symbol is, is the distinction a linear model cannot
    afford to leave to a legend — quote one equation on a slide and a reader
    has to know which side of it the solver is on — and it completes a system
    the page was already three-quarters of the way through: script for index
    sets, upright for the maps and qualifiers a model is handed, italic for
    quantities. The cut this adds is *inside* italic.

    A name that *is* a Greek letter is set as the letter **where it is
    chosen**, which is what the author meant by writing it out. Where it is
    given, the rule wins and the name prints upright as the word: LaTeX has no
    upright lower-case Greek without ``upgreek``, and taking that dependency
    would break two things this repository holds — a preamble installable from
    a two-package TeX, and `to_markdown` output that renders the same on GitHub
    as on the docs site, GitHub's MathJax being unconfigurable. An italic
    ``\eta`` that might be either is worse than an upright ``\mathrm{eta}``
    that is one; a table entry is how an author whose own preamble loads
    ``upgreek`` writes ``\upeta`` instead.
    """
    if given:
        return fmt.upright(name)
    if name in _GREEK:
        return fmt.greek(name)
    return name if len(name) == 1 else fmt.italic(name)


def _derive_name_symbol(name: str, declared: frozenset[str], fmt: Format, *, given: bool = False) -> str:
    r"""``p`` → ``p``; ``load`` → ``\mathit{load}``; ``p_max`` → ``p^{\mathrm{max}}``.

    An underscore is a **qualifier** only when what precedes it is a symbol in
    its own right — a single letter (``p_max``), a Greek letter written out
    (``theta_max``), or another declared **quantity** (``soc_max``).
    Everywhere else it is word separation, where splitting produces nonsense:
    ``marginal_cost`` is not *marginal* raised to *cost*.

    A quantity, not a dimension: ``zone_cap`` is a capacity *indexed by* zone,
    not a zone qualified by cap, and reading the axis as the head made a
    parameter's symbol depend on whether some unrelated dimension happened to
    share its prefix.
    The fallback therefore prints the name as written, underscore and all,
    which is plain rather than beautiful; ``--symbols`` is what makes it
    pretty. A qualifier lands in the superscript, the subscript slot being
    spoken for by the dimensions.
    """
    head, _, tail = name.partition('_')
    if tail and (len(head) == 1 or head in _GREEK or head in declared):
        return fmt.superscript(_word(head, fmt, given=given), fmt.upright(tail.replace('_', ',')))
    return _word(name, fmt, given=given)


def printed_expressions(schema: Buildable) -> frozenset[str]:
    """The named expressions that reach the page under their own name.

    A named expression is substituted where it is used, so it normally prints
    nothing a symbol could stand for. A **cased** one is the exception: its
    value is defined by region, which reads as a definition of its own and is
    referred to by name from the equations that use it.
    """
    return frozenset(name for name, block in schema.expressions.items() if block.cases)


class Symbols:
    r"""How every declared name prints: overrides first, derivation for the rest.

    Assignment order is load-bearing. Name symbols settle *before* dimension
    indices, so an index can be kept off a letter a variable owns — derived
    independently, a model with a dimension ``plant`` and a variable ``p``
    renders ``p_{t,p}`` and no reader can tell which ``p`` is which. Only
    single-letter name symbols are kept off the index letters, a
    ``\mathit{load}`` never colliding with a ``t``.

    Which now means **variables**, since a parameter is upright: a dimension
    may take ``p`` beside a parameter ``p``, because ``\mathrm{p}`` and ``p``
    are not the same symbol on the page. The guard shrank to exactly the
    collisions that are still collisions.

    Raises:
        SchemaError: If *table* is written in a notation *fmt* does not read.
    """

    def __init__(self, schema: Buildable, fmt: Format, table: SymbolTable) -> None:
        if table.notation != fmt.notation:
            msg = (
                f'symbol table: written in {table.notation}, but this is a {fmt.notation} render '
                f'and nothing translates between notations — write a {fmt.notation} table.'
            )
            raise SchemaError(msg)
        printed = printed_expressions(schema)
        # quantities only — see `_derive_name_symbol` for why an axis is not a
        # head a qualifier may hang off. A cased expression is one of them: it
        # is a quantity the file names, which is why it prints at all.
        declared = frozenset({*schema.parameters, *schema.variables, *printed})

        #: Names whose symbol came from the table rather than the derivation.
        #: The convention note quotes only the others: a table is printed
        #: verbatim and is the author's to write, so a symbol it supplies is
        #: not one the note governs — the homepage's own table maps two
        #: parameters to italic symbols, and the note quoting one of those
        #: contradicted itself on the page.
        self.overridden = frozenset(table.names) & {*schema.parameters, *schema.variables}
        self.name: dict[str, str] = {
            name: table.names[name]
            if name in table.names
            else _derive_name_symbol(name, declared, fmt, given=name in schema.parameters)
            for name in (*schema.parameters, *schema.variables, *printed)
        }
        spoken_for = {s for s in self.name.values() if len(s) == 1}

        self.index: dict[str, str] = {}
        self.set: dict[str, str] = {}
        taken_index, taken_set = set(spoken_for), set()
        for dim in schema.dimensions:
            overridden = dim in table.indices
            letter = table.indices[dim] if overridden else _first_free(_index_candidates(dim), taken_index)
            taken_index.add(letter)
            self.index[dim] = letter if len(letter) <= 1 or overridden else fmt.upright(letter)
            upper = _first_free(_set_candidates(dim, letter), taken_set)
            taken_set.add(upper)
            self.set[dim] = table.sets[dim] if dim in table.sets else fmt.script(upper)


def _index_candidates(dim: str) -> list[str]:
    alias = _INDEX_ALIASES.get(dim)
    letters = [c for c in dim.lower() if c.isalpha()]
    return [*([alias] if alias else []), *letters, *string.ascii_lowercase, dim]


def _set_candidates(dim: str, index_letter: str) -> list[str]:
    first = next((c for c in index_letter if c.isalpha()), '')
    letters = [c.upper() for c in dim if c.isalpha()]
    return [*([first.upper()] if first else []), *letters, *string.ascii_uppercase]


def _first_free(candidates: list[str], taken: set[str]) -> str:
    return next((c for c in candidates if c not in taken), candidates[-1])


# ---------------------------------------------------------------------------
# the symbol table (a sidecar file, not the model)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SymbolTable:
    r"""How a *reader* wants the model to print — kept out of the model.

    Presentation is not language: nothing here changes what the file means, no
    lane reads it, and a model with no table still renders. *Notation* is all it
    carries — what a declaration **is** is the model's own ``description:``,
    which travels with the declaration and reaches every consumer.

    Every entry is a spelling, printed verbatim — nothing parses or translates
    notation. ``notation:`` says which language they are written in, and a
    render in the other one refuses::

        notation: latex
        dimensions:
          snapshot: {index: t, set: "\\mathcal{T}"}
          plant:    {index: n}
        names:
          marginal_cost: "c^{\\mathrm{marg}}"

    Deliberately strict — an unrecognised name is an error naming the near
    miss, the failure mode of a silent typo being a symbol that never applies
    and a reader who never finds out.

    Attributes:
        notation: The language the entries are written in, ``latex`` or
            ``typst``; :meth:`load` lower-cases it.
    """

    notation: str
    indices: dict[str, str] = field(default_factory=dict)
    sets: dict[str, str] = field(default_factory=dict)
    names: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, source: str | Path | Mapping[str, Any]) -> SymbolTable:
        """A table from a YAML path or the mapping it parses to.

        Raises:
            SchemaError: An unknown section, a malformed dimension, or a
                ``notation:`` that is missing or not ``latex``/``typst``.
        """
        raw = dict(source) if isinstance(source, Mapping) else read_yaml(Path(source))
        unknown = set(raw) - {'notation', 'dimensions', 'names'}
        if unknown:
            msg = f'symbol table: unknown section(s) {sorted(unknown)}. Valid sections: notation, dimensions, names.'
            raise SchemaError(msg)
        if 'notation' not in raw:
            msg = "symbol table: 'notation:' is required — latex or typst, the language the entries are written in."
            raise SchemaError(msg)
        notation = str(raw['notation']).lower()
        if notation not in ('latex', 'typst'):
            msg = f'symbol table: unknown notation {raw["notation"]!r}. Valid notations: latex, typst.'
            raise SchemaError(msg)

        indices: dict[str, str] = {}
        sets: dict[str, str] = {}
        for dim, spec in (raw.get('dimensions') or {}).items():
            if not isinstance(spec, Mapping):
                msg = f"symbol table: dimension '{dim}' must be a mapping like {{index: t, set: '\\\\mathcal{{T}}'}}"
                raise SchemaError(msg)
            extra = set(spec) - {'index', 'set'}
            if extra:
                msg = f"symbol table: dimension '{dim}' has unknown key(s) {sorted(extra)}. Valid keys: index, set."
                raise SchemaError(msg)
            if 'index' in spec:
                indices[dim] = str(spec['index'])
            if 'set' in spec:
                sets[dim] = str(spec['set'])

        return cls(
            notation=notation,
            indices=indices,
            sets=sets,
            names={k: str(v) for k, v in (raw.get('names') or {}).items()},
        )

    def checked_against(self, schema: Buildable) -> SymbolTable:
        """Reject entries naming nothing in *schema*, with the near miss."""
        dims = set(schema.dimensions)
        everything = dims | set(schema.parameters) | set(schema.variables) | printed_expressions(schema)
        errors = [
            *(_unknown_entry(d, 'dimensions', dims) for d in {*self.indices, *self.sets} - dims),
            *(_unknown_entry(n, 'names', everything - dims) for n in set(self.names) - everything),
        ]
        if errors:
            raise SchemaError('\n'.join(sorted(errors)))
        return self


def _unknown_entry(name: str, section: str, known: set[str]) -> str:
    return f"symbol table: '{name}' under {section}: is not declared by the model. {did_you_mean(name, known)}"
