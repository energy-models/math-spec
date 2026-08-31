# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Provably unbounded models, named before a solver says a bare ``unbounded``.

A variable that is unbounded on the side its objective term improves toward
**and** appears in no constraint runs to infinity for any data at all. Advice
rather than a refusal, because the same shape is what a half-written model
looks like.

Which side improves is read off the *sign* the variable enters the objective
with: under ``minimize`` a ``+v`` term runs down toward ``lower``. Where that
sign is not decidable without data — a parameter coefficient, or occurrences
of both signs — nothing is claimed.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Literal, assert_never

from math_spec.errors import Advice
from math_spec.program import (
    Add,
    At,
    Cases,
    Constant,
    Divide,
    ExpressionNode,
    GroupSum,
    Multiply,
    Negate,
    Parameter,
    Power,
    Sum,
    Translate,
    Variable,
    Window,
    variables_of,
)

if TYPE_CHECKING:
    from math_spec.program import Program, VariableDeclaration

#: The sign a term carries into the objective, or ``None`` where the file does
#: not decide it: a parameter coefficient (which may be zero), a variable
#: appearing with both signs (which may cancel), a divisor carrying one.
Sign = Literal['+', '-'] | None

#: The bound value that leaves each side open. A ``lower`` of ``+inf`` is not
#: this — that model is empty, not unbounded — so the match is by value.
_OPEN = {'lower': -math.inf, 'upper': math.inf}


def unbounded_notes(program: Program) -> list[Advice]:
    """Name every variable the objective can drive to infinity unopposed.

    Asked of the program rather than the file: every fact the rule reads is a
    declaration — the objective's sense and its terms, the variables each
    constraint names, the two bounds — and by the time a program exists a
    ``piecewise:`` block has already become the constraints it expands into,
    which is where the variables it names are held.

    Returns:
        One note per variable that is unbounded on the side its objective term
        improves toward and named by no constraint.
    """
    if program.objective is None:
        return []

    constrained = {block.variable for block in program.sos.values()}
    for constraint in program.constraints.values():
        constrained |= variables_of(constraint.lhs, constraint.rhs)

    signs: dict[str, Sign] = {}
    _walk(program.objective.expression, '+', signs)

    minimize = program.objective.sense == 'minimize'
    notes: list[Advice] = []
    for vname, sign in signs.items():
        if sign is None or vname in constrained:
            continue
        side = 'lower' if minimize == (sign == '+') else 'upper'
        if _is_open(program.variables[vname], side):
            notes.append(
                Advice(
                    'unbounded',
                    vname,
                    f"Variable '{vname}' makes this model unbounded: no constraint names it, and "
                    f'bounds.{side} is {_OPEN[side]}, which is the direction a {sign}{vname} term '
                    f'improves a {program.objective.sense} objective in. No data can change that, so '
                    f'the solve would answer `unbounded` and name nothing.\n'
                    f'Give it a finite bounds.{side}, or the constraint that was meant to define it.',
                )
            )
    return notes


def _is_open(vdef: VariableDeclaration, side: str) -> bool:
    """Whether *vdef* declares nothing at all on *side*.

    A bound naming a parameter is finite or not by data this pass does not
    have, which is why the match is against the open value rather than for a
    missing bound. A ``binary`` variable needs no case of its own: it reaches
    the program with the 0/1 bounds its domain fixes.
    """
    bound = vdef.lower if side == 'lower' else vdef.upper
    return bound == Constant(_OPEN[side])


def _flip(sign: Sign) -> Sign:
    return None if sign is None else ('-' if sign == '+' else '+')


def _times(sign: Sign, other: Sign) -> Sign:
    return None if sign is None or other is None else ('+' if sign == other else '-')


def _coefficient_sign(node: ExpressionNode) -> Sign:
    """The sign *node* scales a term by, or ``None`` unless it is a signed constant.

    ``-2`` lowers to a negation over a constant, so the sign of a literal
    coefficient is not always on the node itself. Zero is ``None`` on purpose:
    a term multiplied away is not in the objective, so the variable it names is
    driven nowhere.
    """
    if isinstance(node, Negate):
        return _flip(_coefficient_sign(node.operand))
    if isinstance(node, Constant) and node.value != 0:
        return '+' if node.value > 0 else '-'
    return None


def _walk(node: ExpressionNode, sign: Sign, signs: dict[str, Sign]) -> None:
    """Record the sign each variable under *node* carries into the objective.

    *signs* accumulates, and a variable reached twice with different signs — or
    once with an undecidable one — lands on ``None``, which claims nothing.
    Every shape node sums its operand's terms with coefficient 1, being a
    reduction, a re-index or a window, so each hands *sign* on unchanged. A
    power carries no sign in either half, which is what makes a degree-2 term
    claim nothing.
    """
    if isinstance(node, Variable):
        signs[node.name] = sign if signs.setdefault(node.name, sign) == sign else None
        return
    if isinstance(node, Constant | Parameter):
        return
    if isinstance(node, Negate):
        _walk(node.operand, _flip(sign), signs)
        return
    if isinstance(node, Add):
        _walk(node.left, sign, signs)
        _walk(node.right, sign, signs)
        return
    if isinstance(node, Multiply):
        _walk(node.left, _times(sign, _coefficient_sign(node.right)), signs)
        _walk(node.right, _times(sign, _coefficient_sign(node.left)), signs)
        return
    if isinstance(node, Divide):
        _walk(node.numerator, _times(sign, _coefficient_sign(node.divisor)), signs)
        _walk(node.divisor, None, signs)
        return
    if isinstance(node, Power):
        _walk(node.base, None, signs)
        _walk(node.exponent, None, signs)
        return
    if isinstance(node, Sum | GroupSum | At | Translate | Window):
        _walk(node.operand, sign, signs)
        return
    if isinstance(node, Cases):
        # a selection, not a sum: whichever region applies stands where the whole value does
        for region in node.regions:
            _walk(region.value, sign, signs)
        return
    assert_never(node)
