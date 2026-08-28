# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Advice — what is decidable without data and is a note rather than a refusal.

One door, :func:`advice`, over every pass of that kind. A consumer prints what
it returns; the sentences are the language's, so two consumers cannot come to
disagree about them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from math_spec import program as program_
from math_spec.boundedness import unbounded_notes
from math_spec.errors import Advice
from math_spec.lowering import to_program

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from math_spec.model import Spec
    from math_spec.program import ExpressionNode, Program


def advice(model: str | Path | dict[str, Any] | Spec | Program) -> tuple[Advice, ...]:
    """Everything the language advises about *model* — never an error, decidable without data.

    A dimension that is never an axis is a label space wearing the wrong
    declaration, or unused. A variable the objective drives toward an open
    bound with no constraint naming it makes the model unbounded for any data
    there is. Both are what a half-written model looks like too, which is why
    they are advice and ``to_spec`` stays open to them.

    Args:
        model: A YAML path, a mapping, a loaded :class:`Spec`, or a
            :class:`Program`.

    Returns:
        The never-an-axis advice in declaration order, then the unboundedness
        advice; ``str()`` of each is its sentence.
    """
    program = to_program(model)
    notes = _never_an_axis(program)
    if not isinstance(model, program_.Program):
        notes += unbounded_notes(model)
    return tuple(notes)


def _never_an_axis(program: Program) -> list[Advice]:
    """One piece of advice per dimension nothing is indexed by and nothing aggregates into."""
    axes: set[str] = set()
    for declaration in (*program.parameters, *program.variables, *program.constraints):
        axes.update(declaration.dims)
    expressions = [program.objective.expression] if program.objective is not None else []
    expressions.extend(side for c in program.constraints for side in (c.lhs, c.rhs))
    for e in expressions:
        axes |= _produced_axes(e)

    targeted = {lk.target: (dimension, lk.name) for dimension, lk in program.lookups}
    notes: list[Advice] = []
    for d in program.dimensions:
        if d.name in axes:
            continue
        if d.name in targeted:
            owner, cname = targeted[d.name]
            text = (
                f"dimension '{d.name}' is never an axis: nothing is indexed by it and nothing "
                f"aggregates into it — it only serves as the target of lookup '{cname}' over "
                f"'{owner}'. That is a label space, not a dimension of this model; declare the "
                f'lookup as one instead:\n'
                f'  lookups:\n'
                f'    {cname}: {{over: {owner}, dtype: str}}'
            )
        else:
            text = (
                f"dimension '{d.name}' is never used: nothing is indexed by it, nothing "
                f'aggregates into it, and no lookup targets it. Remove it — or keep it '
                f'knowingly, if the declarations that use it are still to be written.'
            )
        notes.append(Advice('never-an-axis', d.name, text))
    return notes


def _produced_axes(e: ExpressionNode) -> set[str]:
    """The axes an expression *creates*, beyond what its declarations index.

    ``sum(by=)`` lands terms on its target and ``at()`` spreads onto its fine
    dimension, so both are axes even when no declaration is indexed by them —
    an objective may group into a dimension and then implicitly sum it away.
    """
    out: set[str] = set()
    if isinstance(e, program_.GroupSum):
        out |= set(e.into)
    if isinstance(e, program_.At):
        out.add(e.over)
    for child in program_.children(e):
        out |= _produced_axes(child)
    return out
