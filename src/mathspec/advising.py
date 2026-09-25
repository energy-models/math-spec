# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Advice — what is decidable without data and is a note rather than a refusal.

One door, [`advice`][], over every pass of that kind.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mathspec.boundedness import unbounded_notes
from mathspec.errors import Advice
from mathspec.program import GroupSum, Program, Pullback, walk
from mathspec.validation import to_spec

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from mathspec.spec import Spec


def advice(spec: str | Path | Mapping[str, object] | Spec | Program) -> tuple[Advice, ...]:
    """Everything the language advises about *spec*, decided without data.

    Advice is a note, not a refusal: a file with advice still loads.

    Args:
        spec: Anything [`to_spec`][] accepts, or a [`Program`][], read as
            it arrived. A ``piecewise:`` or ``sos:`` block is read as the rows
            it states, so the answer is the one its expansion gets, with
            nothing expanded.

    Returns:
        The never-an-axis advice in declaration order, then one note per
        declaration the program reads and does not build, then the
        unboundedness advice; ``str()`` of each is its sentence.

    Raises:
        LanguageError: *spec* does not load; [`to_spec`][] says why.
        FileNotFoundError: A ``str`` with no newline that names no file.
    """
    program = spec if isinstance(spec, Program) else to_spec(spec).program
    return tuple(_never_an_axis(program) + _given(program) + unbounded_notes(program))


def _given(program: Program) -> list[Advice]:
    """One note per declaration the program reads and does not build.

    A note rather than a refusal: the file is a spec somebody meant, and only
    the consumer can tell whether the model it is layered onto provides the
    name. A sum other files add terms to is completed by `merge` rather than
    by a host, so its note says that instead.
    """
    return [
        Advice('given', name, _sum_note(name) if getattr(block, 'additive', False) else _given_note(kind, name))
        for kind, group in (
            ('parameter', program.given.parameters),
            ('variable', program.given.variables),
            ('expression', program.given.expressions),
            ('row family', program.given.constraints),
        )
        for name, block in group.items()
    ]


def _given_note(kind: str, name: str) -> str:
    return (
        f"{kind} '{name}' is read here and declared elsewhere: the model this one is layered onto "
        f'provides it. A consumer checks that it does, on the same frame, and refuses the program where '
        f'it does not. A fragment is composed instead: merge() folds this declaration into the one a '
        f'sibling introduces.'
    )


def _sum_note(name: str) -> str:
    return (
        f"expression '{name}' is a sum other files add terms to, and this file adds none: merge() sums the "
        f'term every fragment declares under the name. Until one does, the program reads it and does not '
        f'build it.'
    )


def _never_an_axis(program: Program) -> list[Advice]:
    """One piece of advice per dimension nothing reaches.

    A dimension a relation has a column over is reached: its members are the
    labels that column is checked against, and a ``where`` selects on them,
    so it is in use even where nothing is indexed by it. A dimension only a
    given declaration indexes is reached too: the column exists, in another
    file.
    """
    reached: set[str] = set()
    for declaration in (
        *program.parameters.values(),
        *program.variables.values(),
        *program.constraints.values(),
        *program.given.parameters.values(),
        *program.given.variables.values(),
        *program.given.expressions.values(),
        *program.given.constraints.values(),
    ):
        reached.update(declaration.dims)
    reached |= _produced_axes(program)
    reached |= {dim for lk in program.relations.values() for dim in lk.dims}

    return [
        Advice(
            'never-an-axis',
            name,
            f"dimension '{name}' is never used: nothing is indexed by it, nothing "
            f'aggregates into it, and no relation has a column over it. Remove it — or keep it '
            f'knowingly, if the declarations that use it are still to be written.',
        )
        for name in program.dimensions
        if name not in reached
    ]


def _produced_axes(program: Program) -> set[str]:
    """The axes the expressions create beyond what any declaration indexes.

    ``sum(by=)`` lands on its target and ``at()`` spreads onto its fine
    dimension: either way, the dims the direction produces.
    """
    axes: set[str] = set()
    for node in walk(*program.roots):
        if isinstance(node, GroupSum | Pullback):
            axes.update(node.direction.produced_dims)
    return axes
