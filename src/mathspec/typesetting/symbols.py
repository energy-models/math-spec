# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Which symbol each declared name prints as, and the sidecar that overrides it.

This module decides *which* symbol a name gets; a [`Format`][] decides how it is written.
"""

from __future__ import annotations

import string
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, cast

from mathspec._yaml import read_yaml
from mathspec.errors import SchemaError, did_you_mean
from mathspec.piecewise import Emitted, leaves_ungated
from mathspec.program import Dual, Variable, walk
from mathspec.sos import Emitted as EmittedSet
from mathspec.typesetting.format import NOTATIONS

if TYPE_CHECKING:
    from mathspec.program import Program
    from mathspec.typesetting.format import Format, Notation

__all__ = ['SymbolTable', 'Symbols', 'symbols_for']

#: Dimensions whose conventional index letter is not their own initial, which
#: is what anything unlisted falls back to.
_INDEX_ALIASES = {'snapshot': 't', 'snapshots': 't', 'time': 't', 'timestep': 't', 'timesteps': 't'}


#: Names that are a Greek letter written out. Lower case only — every one has
#: a letter in LaTeX and in Typst, which the capitals do not — and ``omicron``
#: is left out because LaTeX spells it ``o``.
_GREEK = frozenset(
    {
        'alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 'theta',
        'iota', 'kappa', 'lambda', 'mu', 'nu', 'xi', 'rho', 'sigma', 'tau',
        'upsilon', 'phi', 'chi', 'psi', 'omega',
    }
)  # fmt: skip


def _word(name: str, fmt: Format, *, given: bool) -> str:
    r"""One name as one symbol: upright where *given*, italic where chosen.

    A Greek name is set as the letter only where chosen. Upright lower-case
    Greek needs ``upgreek``, which the two-package preamble and GitHub's
    MathJax both lack, so a given ``eta`` prints as ``\mathrm{eta}``; a table
    entry is how an author who loads ``upgreek`` writes ``\upeta``.
    """
    if given:
        return fmt.upright(name)
    if name in _GREEK:
        return fmt.greek(name)
    return name if len(name) == 1 else fmt.italic(name)


def _derive_name_symbol(name: str, declared: frozenset[str], fmt: Format, *, given: bool = False) -> str:
    r"""``p`` → ``p``; ``load`` → ``\mathit{load}``; ``p_max`` → ``p^{\mathrm{max}}``.

    An underscore is a qualifier, landing in the superscript, only where its
    head is a symbol in its own right — a single letter, a Greek letter, or a
    declared parameter or variable. A dimension is not a head: ``zone_cap`` is
    a capacity *indexed by* zone. Anywhere else the name prints as written.
    """
    head, _, tail = name.partition('_')
    if tail and (len(head) == 1 or head in _GREEK or head in declared):
        return fmt.superscript(_word(head, fmt, given=given), fmt.upright(tail.replace('_', ',')))
    return _word(name, fmt, given=given)


def chosen_expressions(program: Program) -> frozenset[str]:
    """The named expressions the solver decides, rather than is handed.

    A ``when`` does not move one: a variable there asks whether the variable
    *exists*, which the model settles when it is built. Only a value reaching a
    variable does — through another named expression too, since a use of one
    stands where the name was written.
    A ``dual`` moves one for the same reason a variable does: the solve settles
    it, and no data hands it over.
    """
    return frozenset(
        name
        for name, entry in program.expressions.items()
        if any(isinstance(node, Variable | Dual) for node in walk(entry.expression))
    )


@dataclass(frozen=True)
class Symbols:
    r"""How every declared name prints: overrides first, derivation for the rest.

    Built by [`symbols_for`][]. Name symbols settle *before* dimension
    indices, so an index is kept off a single letter a variable owns — a
    dimension ``plant`` beside a variable ``p`` would otherwise render
    ``p_{t,p}``. A parameter is upright, so ``\mathrm{p}`` beside an index
    ``p`` is not a collision.

    Attributes:
        overridden: Names the table spelled; the convention note quotes only
            derived symbols.
        name: Each parameter's, variable's and expression's symbol.
        constraint: Each constraint's symbol, the subscript ``dual(c)`` prints
            λ against. Off the flat namespace, like the constraints themselves
            — a model may name a constraint after a variable, so this is its
            own map rather than an entry in [`name`][]. Given structure, so
            upright unless a table overrides it.
        index: Each dimension's index letter.
        set: Each dimension's set symbol.
    """

    overridden: frozenset[str]
    name: Mapping[str, str]
    constraint: Mapping[str, str]
    index: Mapping[str, str]
    set: Mapping[str, str]


def symbols_for(program: Program, fmt: Format, table: SymbolTable) -> Symbols:
    """The [`Symbols`][] *program* prints with in *fmt*, *table* overriding the derivation.

    Raises:
        SchemaError: If *table* is written in a notation *fmt* does not read.
    """
    if table.notation != fmt.notation:
        msg = (
            f'symbol table: written in {table.notation}, but this is a {fmt.notation} render '
            f'and nothing translates between notations — write a {fmt.notation} table.'
        )
        raise SchemaError(msg)
    chosen = frozenset(program.variables) | chosen_expressions(program)
    names = (*program.parameters, *program.variables, *program.expressions)
    declared = frozenset(names)

    name = {
        n: table.names[n] if n in table.names else _derive_name_symbol(n, declared, fmt, given=n not in chosen)
        for n in names
    }
    spoken_for = {s for s in name.values() if len(s) == 1}
    constraint = {
        n: table.names[n] if n in table.names else _derive_name_symbol(n, declared, fmt, given=True)
        for n in program.constraints
    }

    index: dict[str, str] = {}
    sets: dict[str, str] = {}
    taken_index, taken_set = set(spoken_for), set()
    for dim in program.dimensions:
        overridden = dim in table.indices
        letter = table.indices[dim] if overridden else _first_free(_index_candidates(dim), taken_index)
        taken_index.add(letter)
        index[dim] = letter if len(letter) <= 1 or overridden else fmt.upright(letter)
        upper = _first_free(_set_candidates(dim, letter), taken_set)
        taken_set.add(upper)
        sets[dim] = table.sets[dim] if dim in table.sets else fmt.script(upper)
    return Symbols(frozenset(table.names) & declared, name, constraint, index, sets)


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
    r"""How a *reader* wants the model to print — notation only, kept out of the model.

    Every entry is a spelling, printed verbatim. ``notation:`` says which
    language they are written in, and a render in the other one refuses::

        notation: latex
        dimensions:
          snapshot: {index: t, set: "\\mathcal{T}"}
          plant:    {index: n}
        names:
          marginal_cost: "c^{\\mathrm{marg}}"

    An entry naming nothing in the model is an error naming the near miss.

    Attributes:
        notation: The language the entries are written in; [`load`][]
            lower-cases it.
    """

    notation: Notation
    indices: dict[str, str] = field(default_factory=dict)
    sets: dict[str, str] = field(default_factory=dict)
    names: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, source: str | Path | Mapping[str, object]) -> SymbolTable:
        """A table from a YAML path or the mapping it parses to.

        Raises:
            SchemaError: An unknown section, a section or a dimension that is
                not a mapping, or a ``notation:`` that is missing or not
                ``latex``/``typst``.
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
        if notation not in NOTATIONS:
            msg = f'symbol table: unknown notation {raw["notation"]!r}. Valid notations: latex, typst.'
            raise SchemaError(msg)

        indices: dict[str, str] = {}
        sets: dict[str, str] = {}
        for dim, spec in _section(raw, 'dimensions').items():
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
            notation=cast('Notation', notation),
            indices=indices,
            sets=sets,
            names={k: str(v) for k, v in _section(raw, 'names').items()},
        )

    def checked_against(self, program: Program) -> SymbolTable:
        """Reject entries naming nothing in *program* or in what its formulations state, with the near miss.

        A name a ``piecewise:`` or ``sos:`` block emits counts as declared, so
        one table spells both readings of a model: the blocks as the file states
        them, and the rows [`expand`][mathspec.spec.Spec.expand] writes out.
        """
        dims = set(program.dimensions)
        everything = dims | _declared(program) | _emitted(program)
        errors = [
            *(_unknown_entry(d, 'dimensions', dims) for d in {*self.indices, *self.sets} - dims),
            *(_unknown_entry(n, 'names', everything - dims) for n in set(self.names) - everything),
        ]
        if errors:
            raise SchemaError('\n'.join(sorted(errors)))
        return self


def _declared(program: Program) -> set[str]:
    """Every name *program* declares that a table entry may spell."""
    return set(program.parameters) | set(program.variables) | set(program.expressions) | set(program.constraints)


def _emitted(program: Program) -> set[str]:
    """Every variable and constraint writing *program*'s curves and sets out would declare."""
    curves = (
        Emitted.of(name, curve).written(
            curve.method,
            ungated=leaves_ungated(program.variables[curve.activity] if curve.activity is not None else None),
        )
        for name, curve in program.piecewise.items()
    )
    sets = (EmittedSet.of(name, block.sos_type).by_kind for name, block in program.sos.items())
    return {
        *(name for names in curves for name in names),
        *(name for by_kind in sets for _, names in by_kind for name in names),
    }


def _section(raw: Mapping[str, object], name: str) -> Mapping[str, object]:
    """The *name* section of a symbol table as the mapping it has to be, empty where it is absent or null.

    Raises:
        SchemaError: The section is something else, such as a list.
    """
    section = raw.get(name)
    if section is None:
        return {}
    if not isinstance(section, Mapping):
        msg = f'symbol table: {name}: must be a mapping of names to entries, got {type(section).__name__}.'
        raise SchemaError(msg)
    return section


def _unknown_entry(name: str, section: str, known: set[str]) -> str:
    return f"symbol table: '{name}' under {section}: is not declared by the model. {did_you_mean(name, known)}"
