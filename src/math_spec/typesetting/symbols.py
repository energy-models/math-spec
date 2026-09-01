# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Which symbol each declared name prints as — and the sidecar that overrides it.

Derivation aims at *unambiguous*, not beautiful, so a model prints with no
setup; :class:`SymbolTable` is where a reader makes it conventional, in a file
of its own, since presentation is not language. What a declaration *is* stays
``description:`` on the declaration. This module decides *which* symbol a name
gets; a :class:`~math_spec.typesetting.format.Format` decides how it is written.
"""

from __future__ import annotations

import string
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from math_spec._yaml import read_yaml
from math_spec.degree import carries_variable
from math_spec.errors import SchemaError, did_you_mean
from math_spec.resolution import Namespace, expression_of
from math_spec.typesetting.format import NOTATIONS

if TYPE_CHECKING:
    from collections.abc import Iterator

    from math_spec.model import ExpressionBlock, _ExpandedSpec
    from math_spec.typesetting.format import Format, Notation

__all__ = ['SymbolTable', 'Symbols']

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


def printed_expressions(schema: _ExpandedSpec) -> tuple[str, ...]:
    """The named expressions that print under their own name, in declaration order.

    A named expression is substituted where it is used, so it normally prints
    nothing a symbol could stand for. A **cased** one is the exception: it
    prints as a definition of its own, which the equations using it name. The
    order is the file's, because the definitions print in it.
    """
    return tuple(name for name, block in schema.expressions.items() if block.cases)


def chosen_expressions(schema: _ExpandedSpec) -> frozenset[str]:
    """The cased expressions the solver decides, rather than is handed.

    A ``when`` does not move one: a variable there asks whether the variable
    *exists*, which the model settles when it is built. Only a value reaching a
    variable does — through a second cased expression's arms too, since
    :func:`~math_spec.expression_of` expands those where the name stood.
    """
    namespace = Namespace.of(schema)
    return frozenset(
        name
        for name in printed_expressions(schema)
        if any(
            carries_variable(expression_of(text, schema, namespace, f"expression '{name}', {where}"))
            for text, where in _values_of(schema.expressions[name])
        )
    )


def _values_of(block: ExpressionBlock) -> Iterator[tuple[str, str]]:
    """Every value a cased block holds, the ``otherwise:`` included, and where it sits.

    The fallback is a value of the quantity like any case's, so it decides what
    the block *is* alongside them: a block whose only variable is there is one
    the solver returns, and printing it upright would call it data.
    """
    for label, case in block.cases.items():
        yield case.expression, f"case '{label}'"
    assert block.otherwise is not None
    yield block.otherwise, 'otherwise'


class Symbols:
    r"""How every declared name prints: overrides first, derivation for the rest.

    Name symbols settle *before* dimension indices, so an index is kept off a
    single letter a variable owns — a dimension ``plant`` beside a variable
    ``p`` would otherwise render ``p_{t,p}``. A parameter is upright, so
    ``\mathrm{p}`` beside an index ``p`` is not a collision.

    Raises:
        SchemaError: If *table* is written in a notation *fmt* does not read.
    """

    def __init__(self, schema: _ExpandedSpec, fmt: Format, table: SymbolTable) -> None:
        if table.notation != fmt.notation:
            msg = (
                f'symbol table: written in {table.notation}, but this is a {fmt.notation} render '
                f'and nothing translates between notations — write a {fmt.notation} table.'
            )
            raise SchemaError(msg)
        printed = printed_expressions(schema)
        chosen = frozenset(schema.variables) | chosen_expressions(schema)
        names = (*schema.parameters, *schema.variables, *printed)
        declared = frozenset(names)

        #: Names whose symbol came from the table rather than the derivation;
        #: the convention note quotes only the others, a table being free to
        #: map a parameter to an italic symbol.
        self.overridden = frozenset(table.names) & declared
        self.name: dict[str, str] = {
            name: table.names[name]
            if name in table.names
            else _derive_name_symbol(name, declared, fmt, given=name not in chosen)
            for name in names
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
        notation: The language the entries are written in; :meth:`load`
            lower-cases it.
    """

    notation: Notation
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
        if notation not in NOTATIONS:
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
            notation=cast('Notation', notation),
            indices=indices,
            sets=sets,
            names={k: str(v) for k, v in (raw.get('names') or {}).items()},
        )

    def checked_against(self, schema: _ExpandedSpec) -> SymbolTable:
        """Reject entries naming nothing in *schema*, with the near miss."""
        dims = set(schema.dimensions)
        everything = dims | set(schema.parameters) | set(schema.variables) | set(printed_expressions(schema))
        errors = [
            *(_unknown_entry(d, 'dimensions', dims) for d in {*self.indices, *self.sets} - dims),
            *(_unknown_entry(n, 'names', everything - dims) for n in set(self.names) - everything),
        ]
        if errors:
            raise SchemaError('\n'.join(sorted(errors)))
        return self


def _unknown_entry(name: str, section: str, known: set[str]) -> str:
    return f"symbol table: '{name}' under {section}: is not declared by the model. {did_you_mean(name, known)}"
