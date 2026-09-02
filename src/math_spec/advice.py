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
    """One piece of advice per dimension nothing is indexed by and nothing aggregates into."""
    axes: set[str] = set()
    for declaration in (*program.parameters.values(), *program.variables.values(), *program.constraints.values()):
        axes.update(declaration.dims)
    axes |= _produced_axes(program)

    targeted = {lk.target: (dimension, lk.name) for dimension, lk in program.lookups if lk.target is not None}
    notes: list[Advice] = []
    for name in program.dimensions:
        if name in axes:
            continue
        if name in targeted:
            owner, cname = targeted[name]
            text = (
                f"dimension '{name}' is never an axis: nothing is indexed by it and nothing "
                f"aggregates into it — it only serves as the target of lookup '{cname}' over "
                f"'{owner}'. That is a label space, not a dimension of this model; declare the "
                f'lookup as one instead:\n'
                f'  lookups:\n'
                f'    {cname}: {{over: {owner}, dtype: str}}'
            )
        else:
            text = (
                f"dimension '{name}' is never used: nothing is indexed by it, nothing "
                f'aggregates into it, and no lookup targets it. Remove it — or keep it '
                f'knowingly, if the declarations that use it are still to be written.'
            )
        notes.append(Advice('never-an-axis', name, text))
    return notes


def _produced_axes(program: Program) -> set[str]:
    """The axes the expressions create beyond what any declaration indexes.

    ``sum(by=)`` lands on its target and ``at()`` spreads onto its fine dimension.
    """
    axes: set[str] = set()
    for node in walk(*program.expressions):
        if isinstance(node, GroupSum):
            axes.update(node.into)
        elif isinstance(node, At):
            axes.add(node.over)
    return axes
