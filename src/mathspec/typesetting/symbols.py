# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Which symbol each declared name prints as, and the table that overrides it.

This module decides *which* symbol a name gets; a :class:`~mathspec.typesetting.format.Format` decides how it is written.
"""

from __future__ import annotations

import string
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import TypeAdapter, ValidationError

from mathspec._yaml import read_yaml
from mathspec.errors import SchemaError, schema_error
from mathspec.model import NotationSymbols
from mathspec.program import Dual, Notation, SymbolTable, Variable, walk
from mathspec.validation import symbol_errors

if TYPE_CHECKING:
    from mathspec.program import Program
    from mathspec.typesetting.format import Format

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

    Built by :func:`symbols_for`. Name symbols settle *before* dimension
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
            own map rather than an entry in :attr:`name`. Given structure, so
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
    """The :class:`Symbols` *program* prints with in *fmt*, *table* overriding the derivation."""
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


def load_symbols(source: str | Path | Mapping[str, object], program: Program) -> Mapping[Notation, SymbolTable]:
    """The tables a ``symbols:`` block holds, by notation, from a YAML path or the mapping it parses to.

    The file holds what a model's own ``symbols:`` key holds, so a table
    travels between a model and a file unchanged.

    Raises:
        SchemaError: A notation other than ``latex`` or ``typst``, an unknown
            key, or an entry naming nothing in *program*, each naming what
            was meant.
    """
    raw = source if isinstance(source, Mapping) else read_yaml(Path(source))
    try:
        blocks = _BLOCK.validate_python(raw)
    except ValidationError as exc:
        raise schema_error(exc) from None
    tables = {notation: block.table(notation) for notation, block in blocks.items()}
    if errors := symbol_errors(tables, program):
        raise SchemaError('\n'.join(errors))
    return tables


_BLOCK: TypeAdapter[dict[Notation, NotationSymbols]] = TypeAdapter(dict[Notation, NotationSymbols])
