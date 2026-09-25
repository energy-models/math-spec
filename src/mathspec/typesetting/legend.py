# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""The legend: the glossary of symbols, and a note for each notation the equations use.

What the equations use is read off the program before anything prints
(:func:`notice`), so the legend explains every symbol the walk will print and
nothing the walk decides is asked of it twice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from mathspec.program import (
    CountComparison,
    DimensionComparison,
    DimensionPosition,
    ExpressionComparison,
    PulledBackPredicate,
    Translate,
    TranslatedPredicate,
    WindowSum,
    walk_regions,
)
from mathspec.typesetting.format import Entry

if TYPE_CHECKING:
    from collections.abc import Iterable

    from mathspec.program import Expression, Mask, Program, RelationDeclaration
    from mathspec.typesetting.format import Format, OperatorName
    from mathspec.typesetting.symbols import Symbols

#: What a translation does with the row the shift vacates. Three policies get
#: three spellings because they are three different equations at the boundary.
TranslationPolicy = Literal['plain', 'wrap', 'edge']

#: The positional forms an equation can print, each of which the legend explains once.
PositionForm = Literal['plain', 'grouped', 'from_end']


def policy_of(node: Translate | WindowSum) -> TranslationPolicy:
    """Which translation symbol *node* prints with: cyclic, filled at the edge, or plain."""
    if node.wrap:
        return 'wrap'
    if isinstance(node, Translate) and node.fill is not None:
        return 'edge'
    return 'plain'


@dataclass(frozen=True)
class Noticed:
    """What the equations use that the legend has to explain.

    Attributes:
        policies: Each translation policy some ``shift`` or ``sum_back`` prints.
        grouped: Whether some translation is counted inside a relation's group.
        positions: Each form a ``position()`` prints in.
        numeric_coordinates: Each dimension whose index is compared against a
            number, where "position 3" and "the coordinate 3" are both
            readings of a line.
    """

    policies: frozenset[TranslationPolicy]
    grouped: bool
    positions: frozenset[PositionForm]
    numeric_coordinates: frozenset[str]


def notice(program: Program) -> Noticed:
    """What printing *program* uses, read off every tree the walk prints."""
    policies: set[TranslationPolicy] = set()
    grouped = False
    positions: set[PositionForm] = set()
    numeric: set[str] = set()

    def expressions(*roots: Expression) -> None:
        nonlocal grouped
        for node, regions in walk_regions(*roots):
            if isinstance(node, WindowSum) or (isinstance(node, Translate) and node.offset != 0):
                policies.add(policy_of(node))
                grouped = grouped or node.partition is not None
            for region in regions:
                masks(region)

    seen: set[int] = set()

    def masks(mask: Mask) -> None:
        if id(mask) in seen:
            return
        seen.add(id(mask))
        for atom in mask.atoms:
            if isinstance(atom, DimensionComparison) and isinstance(atom.value, int | float):
                numeric.add(atom.name)
            elif isinstance(atom, DimensionPosition):
                positions.add('grouped' if atom.partition is not None else 'plain')
                if atom.position < 0:
                    positions.add('from_end')
            elif isinstance(atom, ExpressionComparison):
                expressions(atom.left, atom.right)
            elif isinstance(atom, CountComparison):
                masks(atom.predicate)
            elif isinstance(atom, TranslatedPredicate | PulledBackPredicate):
                masks(atom.operand)

    expressions(*program.roots)
    for entry in program.expressions.values():
        expressions(entry.expression)
    for curve in program.piecewise.values():
        expressions(*(link.expression for link in curve.links))
    for declaration in (*program.constraints.values(), *program.variables.values()):
        if declaration.where is not None:
            masks(declaration.where)
    for assumption in program.assumptions.values():
        masks(assumption.predicate)
        if assumption.where is not None:
            masks(assumption.where)
    return Noticed(frozenset(policies), grouped, frozenset(positions), frozenset(numeric))


@dataclass(frozen=True)
class Legend:
    """The glossary and the notes, spelled with one program's symbols in one format."""

    program: Program
    symbols: Symbols
    format: Format

    def _op(self, name: OperatorName) -> str:
        return self.format.operators[name]

    def glossaries(self, noticed: Noticed, defined: Iterable[str]) -> list[tuple[str, list[Entry]]]:
        """The sets, parameters, variables, given declarations and definitions, each with its symbol, its dims and its description.

        *defined* names the expressions that print under their own symbol, so
        a legend row stands exactly where a symbol does.
        """
        fmt, program = self.format, self.program
        sets = [
            self._entry(
                self.symbols.set[d],
                f'index {fmt.math(self.symbols.index[d])} {fmt.dash} {fmt.mono(d)}{self._coords(d, noticed)}',
                block.description,
            )
            for d, block in program.dimensions.items()
        ]
        parameters = [
            self._entry(self.symbols.name[p], f'{fmt.mono(p)}{self._over(list(block.dims))}', block.description)
            for p, block in program.parameters.items()
        ]
        variables = [
            self._entry(self.symbols.name[v], f'{fmt.mono(v)}{self._over(list(block.dims))}', block.description)
            for v, block in program.variables.items()
        ]
        given = [
            *(
                self._entry(
                    self.symbols.name[g],
                    f'{fmt.mono(g)}{self._over(list(block.dims))}, data another file declares',
                    block.description,
                )
                for g, block in program.given.parameters.items()
            ),
            *(
                self._entry(self.symbols.name[g], f'{fmt.mono(g)}{self._over(list(block.dims))}', block.description)
                for g, block in program.given.variables.items()
            ),
            *(
                self._entry(
                    self.symbols.name[g],
                    f'{fmt.mono(g)}{self._over(list(block.dims))}, an expression another file defines',
                    block.description,
                )
                for g, block in program.given.expressions.items()
            ),
            *(
                self._entry(
                    self.symbols.constraint[g],
                    f'{fmt.mono(g)}{self._over(list(block.dims))}, a row family this file reads the dual of',
                    block.description,
                )
                for g, block in program.given.constraints.items()
            ),
        ]
        shown = set(defined)
        definitions = [
            self._entry(
                self.symbols.name[e],
                f'{fmt.mono(e)}{self._over(list(block.dims))}'
                + (', a sum other files add terms to' if block.additive else ''),
                block.description,
            )
            for e, block in program.expressions.items()
            if e in shown
        ]
        groups = (
            ('Sets', sets),
            ('Parameters', parameters),
            ('Variables', variables),
            ('Given', given),
            ('Definitions', definitions),
        )
        return [(title, entries) for title, entries in groups if entries]

    def _entry(self, symbol: str, what: str, description: str | None) -> Entry:
        meaning = f'{what} {self.format.dash} {self.format.escape(description)}' if description else what
        return Entry(symbol, meaning)

    def _over(self, dims: list[str]) -> str:
        if not dims:
            return ' (scalar)'
        product = self.format.joined([self.symbols.set[d] for d in dims], self._op('times'))
        return f' over {self.format.math(product)}'

    def _signature(self, name: str, lk: RelationDeclaration) -> str:
        """A relation in the legend: a function from its key sets to its value sets, or a relation inside the product."""

        def product(roles: Iterable[str]) -> str:
            return self.format.joined([self.symbols.set[lk.dim(r)] for r in roles], self._op('times'))

        if lk.values:
            return f'{self.format.upright(name)}: {product(lk.key)} {self._op("maps_to")} {product(lk.values)}'
        return f'{self.format.upright(name)} {self._op("subset_of")} {product(lk.roles)}'

    def _coords(self, dim: str, noticed: Noticed) -> str:
        """The dimension's carried structure: each relation with a column over it, as the map or relation it is.

        The dtype is named only where an equation compared the index against a
        number, the one place "position 3" and "the coordinate 3" are both
        readings of a line.
        """
        carried = self.program.relations_of(dim)
        clauses = []
        if dim in noticed.numeric_coordinates:
            clauses.append(f' ({self.format.mono(self.program.dimensions[dim].dtype)} coordinates)')
        if carried:
            maps = self.format.joined([self._signature(c, lk) for c, lk in carried.items()], '')
            clauses.append(f' with {self.format.math(maps)}')
        return ''.join(clauses)

    def convention_notes(self) -> list[str]:
        """What the two faces mean, with the model's own symbols.

        Only where the model has both, and quoting only derived symbols: a
        table is the author's to write, so a symbol it supplies is not one this
        note governs.
        """
        derived = [
            next((n for n in names if n not in self.symbols.overridden), None)
            for names in (self.program.parameters, self.program.variables)
        ]
        if not all(derived):
            return []
        given, chosen = (self.format.math(self.symbols.name[n]) for n in derived if n is not None)
        return [
            f'Upright is what the model is given {self.format.dash} a parameter such as {given}, a coordinate '
            f'map, a label {self.format.dash} and italic is what the solver chooses, such as {chosen}. '
            f'An index is italic too, being what a quantifier chooses, and a set is script.'
        ]

    def translation_notes(self, noticed: Noticed) -> list[str]:
        """A sentence for each translation symbol the model printed; plain ``t-k`` needs none."""
        notes = []
        if 'wrap' in noticed.policies:
            cyclic = self.format.math(f't {self._op("cyclic_minus")} k')
            notes.append(
                f'{cyclic} denotes cyclic translation: index {self.format.math("t-k")} taken modulo the size of '
                f'the dimension ({self.format.mono("roll")}). Plain {self.format.math("t-k")} '
                f'({self.format.mono("shift")}) has no wraparound {self.format.dash} terms translated past '
                f'the edge are simply absent.'
            )
        if 'edge' in noticed.policies:
            filled = self.format.math(f't {self.format.subscript(self._op("edge_minus"), ["v"])} k')
            notes.append(
                f'{filled} denotes translation with {self.format.math("v")} standing where index '
                f'{self.format.math("t-k")} leaves the dimension ({self.format.mono("shift(edge=v)")}), so the row '
                f'at that boundary is built and carries {self.format.math("v")} rather than being dropped.'
            )
        if noticed.grouped:
            applied = self.format.apply(self.format.upright('relation'), 't')
            counted = self.format.math(f't {self.format.superscript(self._op("cyclic_minus"), applied)} k')
            note = (
                f'{counted} denotes a translation counted inside the group a relation puts {self.format.math("t")} '
                f'in ({self.format.mono("shift(by=relation)")}), so a term never crosses out of its own group.'
            )
            if 'edge' in noticed.policies:
                both = self.format.superscript(self.format.subscript(self._op('edge_minus'), ['v']), applied)
                note += (
                    f' The two modifiers take different slots {self.format.dash} the group above, the fill '
                    f'below {self.format.dash} so {self.format.math(f"t {both} k")} is both at once.'
                )
            notes.append(note)
        return notes

    def position_notes(self, noticed: Noticed) -> list[str]:
        """A sentence for each positional symbol the model printed; the first says which of ``pos(t)`` and ``t`` is the position."""
        notes = []
        if noticed.positions:
            index = self.format.math('t')
            place = self.format.math(self.format.apply(self._op('position'), 't'))
            dash = self.format.dash
            notes.append(
                f"{place} denotes where index {index} sits along its dimension's own order {dash} the order "
                f'{self.format.mono("shift")} steps along, not the order labels sort in {dash} counted from '
                f'{self.format.math("0")}. The index itself stays the coordinate, so {index} compares against '
                f'labels and {place} against positions.'
            )
        if 'grouped' in noticed.positions:
            applied = self.format.apply(self.format.upright('relation'), 't')
            grouped = self.format.math(self.format.apply(self.format.subscript(self._op('position'), [applied]), 't'))
            group = self.format.math(self.format.subscript(self.format.script('T'), [applied]))
            notes.append(
                f'{grouped} counts within the group a relation puts {self.format.math("t")} in: the subscript names '
                f'the map, {group} is the group it lands in, and that group has a first position of its own.'
            )
        if 'from_end' in noticed.positions:
            size = self.format.cardinality(self.format.script('T'))
            last = self.format.math(f'{size} {self._op("minus")} 1')
            notes.append(
                f'{self.format.math(size)} denotes the size of the set being counted along, and a position '
                f'counted from the end prints against it {self.format.dash} {last} is the last position, one '
                f'less than the size because the first is {self.format.math("0")}.'
            )
        return notes
