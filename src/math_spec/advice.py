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
from math_spec.program import At, Dual, GroupSum, variables_of, walk

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
        The never-an-axis advice in declaration order, then the unread-given
        advice, then the unboundedness advice; ``str()`` of each is its
        sentence.
    """
    program = to_program(model)
    return tuple(_never_an_axis(program) + _given_never_read(program) + unbounded_notes(program))


def _never_an_axis(program: Program) -> list[Advice]:
    """One piece of advice per dimension nothing reaches.

    A dimension a lookup targets is reached: its members are the labels the
    map's values are checked against, and a ``where`` selects on them, so it
    is in use even where nothing is indexed by it.
    """
    reached: set[str] = set()
    for declaration in (
        *program.parameters.values(),
        *program.variables.values(),
        *program.constraints.values(),
        *program.given_constraints.values(),
    ):
        reached.update(declaration.dims)
    reached |= _produced_axes(program)
    reached |= {lk.target for _, lk in program.lookups}

    return [
        Advice(
            'never-an-axis',
            name,
            f"dimension '{name}' is never used: nothing is indexed by it, nothing "
            f'aggregates into it, and no lookup targets it. Remove it — or keep it '
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
            axes.add(node.over)
    return axes


def _given_never_read(program: Program) -> list[Advice]:
    """One piece of advice per given declaration nothing in the file reads.

    A given block is the interface a layer is written against, so an entry
    nothing names asks whoever binds it to find a column or a row family for
    nothing. That is how a layer drifts from the model it was written for, and
    it is the one thing about a given block that is decidable here — whether
    the entry matches what it binds to is a question only the model can answer.
    """
    bodies = (*program.expressions, *(e.expression for e in program.named_expressions.values()))
    masked = (d.where for d in (*program.variables.values(), *program.constraints.values()) if d.where is not None)
    read = variables_of(*bodies).union(*(mask.names_read for mask in masked))
    dualled = {node.constraint for node in walk(*bodies) if isinstance(node, Dual)}

    return [
        Advice(
            'given-never-read',
            name,
            f"given {kind} '{name}' is never read: this file declares it and then {how}. Remove it, or "
            f'name it in the math — a given block states what a consumer must bind, so an unread entry '
            f'asks for one it has no use for.',
        )
        for kind, names, reached, how in (
            ('variable', [n for n, v in program.variables.items() if v.given], read, 'no expression names it'),
            ('constraint', list(program.given_constraints), dualled, 'no dual() names it'),
        )
        for name in names
        if name not in reached
    ]
