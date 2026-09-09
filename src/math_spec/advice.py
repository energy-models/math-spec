# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Advice — what is decidable without data and is a note rather than a refusal.

One door, :func:`advice`, over every pass of that kind.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from math_spec.boundedness import unbounded_notes
from math_spec.errors import Advice
from math_spec.lowering import to_program
from math_spec.program import At, GroupSum, walk

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from math_spec.model import Spec
    from math_spec.program import Program


def advice(model: str | Path | dict[str, Any] | Spec | Program) -> tuple[Advice, ...]:
    """Everything the language advises about *model* — never an error, decidable without data.

    Args:
        model: A YAML path, a mapping, a loaded :class:`Spec`, or a
            :class:`Program`. Both passes read the program, so the four
            answer alike.

    Returns:
        The never-an-axis advice in declaration order, then the unboundedness
        advice; ``str()`` of each is its sentence.
    """
    program = to_program(model)
    return tuple(_never_an_axis(program) + unbounded_notes(program))


def _never_an_axis(program: Program) -> list[Advice]:
    """One piece of advice per dimension nothing reaches.

    A dimension a lookup has a column over is reached: its members are the
    labels that column is checked against, and a ``where`` selects on them,
    so it is in use even where nothing is indexed by it.
    """
    reached: set[str] = set()
    for declaration in (*program.parameters.values(), *program.variables.values(), *program.constraints.values()):
        reached.update(declaration.dims)
    reached |= _produced_axes(program)
    reached |= {dim for lk in program.lookups.values() for dim in lk.dims}

    return [
        Advice(
            'never-an-axis',
            name,
            f"dimension '{name}' is never used: nothing is indexed by it, nothing "
            f'aggregates into it, and no lookup has a column over it. Remove it — or keep it '
            f'knowingly, if the declarations that use it are still to be written.',
        )
        for name in program.dimensions
        if name not in reached
    ]


def _produced_axes(program: Program) -> set[str]:
    """The axes the expressions create beyond what any declaration indexes.

    ``sum(by=)`` lands on its target and ``at()`` spreads onto its fine dimension.
    """
    axes: set[str] = set()
    for node in walk(*program.expressions):
        if isinstance(node, GroupSum):
            axes.update(node.into)
        elif isinstance(node, At):
            axes.update(node.over)
    return axes
