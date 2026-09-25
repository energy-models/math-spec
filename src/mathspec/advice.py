# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Advice — what is decidable without data and is a note rather than a refusal.

One door, :func:`advice`, over every pass of that kind.
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

    from mathspec.model import Spec


def advice(model: str | Path | Mapping[str, object] | Spec | Program) -> tuple[Advice, ...]:
    """Everything the language advises about *model* — never an error, decidable without data.

    Args:
        model: A YAML path, a mapping, a loaded :class:`Spec`, or a
            :class:`Program`, read as it arrived. A ``piecewise:`` or ``sos:``
            block is read as the rows it states, so the answer is the one its
            expansion gets, with nothing expanded.

    Returns:
        The never-an-axis advice in declaration order, then the unboundedness
        advice; ``str()`` of each is its sentence.
    """
    program = model if isinstance(model, Program) else to_spec(model).program
    return tuple(_never_an_axis(program) + unbounded_notes(program))


def _never_an_axis(program: Program) -> list[Advice]:
    """One piece of advice per dimension nothing reaches.

    A dimension a relation has a column over is reached: its members are the
    labels that column is checked against, and a ``where`` selects on them,
    so it is in use even where nothing is indexed by it.
    """
    reached: set[str] = set()
    for declaration in (*program.parameters.values(), *program.variables.values(), *program.constraints.values()):
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
