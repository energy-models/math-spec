"""Which symbol each declared name prints as — and the sidecar that overrides it.

Derivation aims at *unambiguous*, not beautiful: it runs with no setup, so it
has to be right rather than elegant. :class:`SymbolTable` is where a reader
makes it conventional, and it is a file of its own — presentation is not
language, so it never becomes keys on ``MathSchema``, which is the versioned
contract every lane sees.

Spelling comes from a :class:`~lpspec.typeset.format.Format`: this module
decides *which* symbol a name gets, never how that symbol is written.
"""

from __future__ import annotations

import string
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lpspec._yaml import read_yaml
from lpspec.errors import SchemaError, did_you_mean

if TYPE_CHECKING:
    from lpspec.schema import MathSchema
    from lpspec.typeset.format import Format

__all__ = ['SymbolTable', 'Symbols']

#: Dimensions whose conventional index letter is not their own first letter.
#: Small on purpose — a lookup table of everybody's naming habits is a
#: maintenance sink; anything unlisted falls back to its own initial.
_INDEX_ALIASES = {'snapshot': 't', 'snapshots': 't', 'time': 't', 'timestep': 't', 'timesteps': 't'}


def _word(name: str, fmt: Format) -> str:
    """One name as one symbol: a letter stays a letter, a word is set italic."""
    return name if len(name) == 1 else fmt.italic(name)


def _derive_name_symbol(name: str, declared: frozenset[str], fmt: Format) -> str:
    """``p`` → ``p``; ``load`` → ``\\mathit{load}``; ``p_max`` → ``p^{\\mathrm{max}}``.

    An underscore is a **qualifier** only when what precedes it is a symbol in
    its own right — a single letter (``p_max``), or another declared name
    (``soc_max``, ``bp_x``). Everywhere else it is word separation, and
    splitting there produced nonsense: ``marginal_cost`` is not *marginal*
    raised to *cost*, and ``shut_down`` is one word with a down-arrow's worth
    of meaning in it.

    So the fallback prints the name as written, underscore and all. That is
    plain rather than beautiful, and deliberately: a derived symbol has to be
    *unambiguous*, and a symbol table (``--symbols``) is what makes it pretty.
    A qualifier lands in the superscript because the subscript slot is spoken
    for — it carries the dimensions.
    """
    head, _, tail = name.partition('_')
    if tail and (len(head) == 1 or head in declared):
        return fmt.superscript(_word(head, fmt), fmt.upright(tail.replace('_', ',')))
    return _word(name, fmt)


class Symbols:
    """How every declared name prints: overrides first, derivation for the rest.

    Assignment order is load-bearing. Name symbols are settled *before*
    dimension indices, so an index can be kept off a letter a variable already
    owns — without that, a model with a dimension ``plant`` and a variable
    ``p`` renders ``p_{t,p}`` and no reader can tell which ``p`` is which.
    Deriving the two independently is exactly how that got through.
    """

    def __init__(self, schema: MathSchema, fmt: Format, table: SymbolTable | None = None) -> None:
        table = table or SymbolTable()
        declared = frozenset({*schema.dimensions, *schema.parameters, *schema.variables})

        self.name: dict[str, str] = {
            name: table.names.get(name) or _derive_name_symbol(name, declared, fmt)
            for name in (*schema.parameters, *schema.variables)
        }
        # Only single-letter symbols can be mistaken for an index; a
        # `\mathit{load}` never collides with a `t`.
        spoken_for = {s for s in self.name.values() if len(s) == 1}

        self.index: dict[str, str] = {}
        self.set: dict[str, str] = {}
        taken_index, taken_set = set(spoken_for), set()
        for dim in schema.dimensions:
            override = table.indices.get(dim)
            letter = override or _first_free(_index_candidates(dim), taken_index)
            taken_index.add(letter)
            self.index[dim] = letter if len(letter) <= 1 or override else fmt.upright(letter)
            given = table.sets.get(dim)
            upper = _first_free(_set_candidates(dim, letter), taken_set)
            taken_set.add(upper)
            self.set[dim] = given or fmt.script(upper)

        self.description: dict[str, str] = dict(table.descriptions)


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
    """How a *reader* wants the model to print — kept out of the model.

    This is presentation, and presentation is not language: nothing here
    changes what the file means, no lane reads it, and a model with no table
    still renders. So it lives in its own file rather than as keys on
    ``MathSchema``, which is the versioned contract every consumer sees.

    Its own format, deliberately strict: a name it does not recognise is an
    error naming the near miss, because the failure mode of a silent typo is a
    symbol that simply never applies and a reader who never finds out::

        dimensions:
          snapshot: {index: t, set: "\\\\mathcal{T}"}
          plant:    {index: n}
        names:
          marginal_cost: "c^{\\\\mathrm{marg}}"
        descriptions:
          snapshot: hourly, over one year
    """

    indices: dict[str, str] = field(default_factory=dict)
    sets: dict[str, str] = field(default_factory=dict)
    names: dict[str, str] = field(default_factory=dict)
    descriptions: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, source: str | Path | Mapping[str, Any]) -> SymbolTable:
        raw = dict(source) if isinstance(source, Mapping) else read_yaml(Path(source))
        unknown = set(raw) - {'dimensions', 'names', 'descriptions'}
        if unknown:
            msg = (
                f'symbol table: unknown section(s) {sorted(unknown)}. Valid sections: dimensions, names, descriptions.'
            )
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
            indices=indices,
            sets=sets,
            names={k: str(v) for k, v in (raw.get('names') or {}).items()},
            descriptions={k: str(v) for k, v in (raw.get('descriptions') or {}).items()},
        )

    def checked_against(self, schema: MathSchema) -> SymbolTable:
        """Reject entries naming nothing in *schema*, with the near miss."""
        dims = set(schema.dimensions)
        everything = dims | set(schema.parameters) | set(schema.variables)
        errors = [
            *(_unknown_entry(d, 'dimensions', dims) for d in {*self.indices, *self.sets} - dims),
            *(_unknown_entry(n, 'names', everything - dims) for n in set(self.names) - everything),
            *(_unknown_entry(n, 'descriptions', everything) for n in set(self.descriptions) - everything),
        ]
        if errors:
            raise SchemaError('\n'.join(sorted(errors)))
        return self


def _unknown_entry(name: str, section: str, known: set[str]) -> str:
    return f"symbol table: '{name}' under {section}: is not declared by the model. {did_you_mean(name, known)}"
