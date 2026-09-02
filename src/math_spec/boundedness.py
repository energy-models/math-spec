# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Provably unbounded models, named before a solver says a bare ``unbounded``.

A variable unbounded on the side its objective term improves toward, and named
by no constraint, runs to infinity for any data. Which side is read off the
sign the variable enters the objective with: under ``minimize`` a ``+v`` term
runs down toward ``lower``. Where that sign is not decidable without data — a
parameter coefficient, or occurrences of both signs — nothing is claimed.
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
    Dual,
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
    children,
    variables_of,
)

if TYPE_CHECKING:
    from math_spec.program import Program, VariableDeclaration

#: The sign a term carries into the objective, or ``None`` where the file does
#: not decide it: a parameter coefficient (which may be zero), a variable
#: appearing with both signs (which may cancel), a divisor carrying one.
Sign = Literal['+', '-'] | None

#: Which of a variable's two bounds a term drives it toward.
BoundSide = Literal['lower', 'upper']

#: The bound value that leaves each side open. A ``lower`` of ``+inf`` is not
#: this — that model is empty, not unbounded — so the match is by value.
_OPEN: dict[BoundSide, float] = {'lower': -math.inf, 'upper': math.inf}


def unbounded_notes(program: Program) -> list[Advice]:
    """Name every variable the objective can drive to infinity unopposed.

    Args:
        program: The lowered program, in which ``piecewise:`` has already
            become the constraints it expands into.

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
    _record_signs(program.objective.expression, '+', signs)

    minimize = program.objective.sense == 'minimize'
    notes: list[Advice] = []
    for vname, sign in signs.items():
        if sign is None or vname in constrained:
            continue
        side: BoundSide = 'lower' if minimize == (sign == '+') else 'upper'
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


def _is_open(vdef: VariableDeclaration, side: BoundSide) -> bool:
    """Whether *vdef*'s bound on *side* is the open value itself.

    A bound naming a parameter is finite or not by data, so it does not count.
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


def _record_signs(node: ExpressionNode, sign: Sign, signs: dict[str, Sign]) -> None:
    """Record the sign each variable under *node* carries into the objective.

    A variable reached twice with different signs, or once with an undecidable
    one, lands on ``None``, which claims nothing. A reduction, a re-index, a
    window and a cases selection pass *sign* to their children unchanged; a
    power carries no sign in either half.

    A Constant, Parameter or Dual is a variable-free leaf and contributes
    nothing. ``Dual`` is in that arm only to keep the walk exhaustive after the
    union gained it — a dual makes its entry post-solve grade, which no
    objective may read, so this walk never actually meets one; the clause is
    not a claim that a dual would carry no sign into an objective it can never
    enter.
    """
    if isinstance(node, Variable):
        signs[node.name] = sign if signs.setdefault(node.name, sign) == sign else None
        return
    if isinstance(node, Constant | Parameter | Dual):
        return
    if isinstance(node, Negate):
        _record_signs(node.operand, _flip(sign), signs)
        return
    if isinstance(node, Add):
        _record_signs(node.left, sign, signs)
        _record_signs(node.right, sign, signs)
        return
    if isinstance(node, Multiply):
        _record_signs(node.left, _times(sign, _coefficient_sign(node.right)), signs)
        _record_signs(node.right, _times(sign, _coefficient_sign(node.left)), signs)
        return
    if isinstance(node, Divide):
        _record_signs(node.numerator, _times(sign, _coefficient_sign(node.divisor)), signs)
        _record_signs(node.divisor, None, signs)
        return
    if isinstance(node, Power):
        _record_signs(node.base, None, signs)
        _record_signs(node.exponent, None, signs)
        return
    if isinstance(node, Sum | GroupSum | At | Translate | Window | Cases):
        for child in children(node):
            _record_signs(child, sign, signs)
        return
    assert_never(node)
