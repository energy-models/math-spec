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

from math_spec.expression_parser import (
    ArithmeticNode,
    BinaryOperatorNode,
    ComparisonNode,
    ExpressionNode,
    FunctionCallNode,
    KwargNode,
    NumberNode,
    ParameterNode,
    UnaryOperatorNode,
    UnresolvedNode,
    VariableNode,
    children,
)
from math_spec.resolution import Namespace, expression_of

if TYPE_CHECKING:
    from math_spec.model import Model, VariableBlock

#: The sign a term carries into the objective, or ``None`` where the file does
#: not decide it: a parameter coefficient (which may be zero), a variable
#: appearing with both signs (which may cancel), a divisor carrying one.
Sign = Literal['+', '-'] | None

#: The bound value that leaves each side open. A ``lower`` of ``+inf`` is not
#: this — that model is empty, not unbounded — so the match is by value.
_OPEN = {'lower': -math.inf, 'upper': math.inf}


def unbounded_notes(schema: Model) -> list[str]:
    """Name every variable the objective can drive to infinity unopposed.

    Takes an expanded schema: a ``piecewise:`` block holds the variables it
    names, and does so through the constraints it expands into.

    Returns:
        One note per variable that is unbounded on the side its objective term
        improves toward and named by no constraint.
    """
    if schema.objective is None:
        return []

    ns = Namespace.of(schema)
    objective = expression_of(schema.objective.expression, schema, ns, 'The objective')
    assert not isinstance(objective, ComparisonNode), 'an objective holds no comparison — checked before this runs'

    constrained = {block.variable for block in schema.sos.values()}
    for cname, cdef in schema.constraints.items():
        constrained |= _variables(expression_of(cdef.expression, schema, ns, f"Constraint '{cname}'"))

    signs: dict[str, Sign] = {}
    _walk(objective, '+', signs)

    minimize = schema.objective.sense == 'minimize'
    notes = []
    for vname, sign in signs.items():
        if sign is None or vname in constrained:
            continue
        side = 'lower' if minimize == (sign == '+') else 'upper'
        if _is_open(schema.variables[vname], side):
            notes.append(
                f"Variable '{vname}' makes this model unbounded: no constraint names it, and "
                f'bounds.{side} is {_OPEN[side]}, which is the direction a {sign}{vname} term '
                f'improves a {schema.objective.sense} objective in. No data can change that, so '
                f'the solve would answer `unbounded` and name nothing.\n'
                f'Give it a finite bounds.{side}, or the constraint that was meant to define it.'
            )
    return notes


def _is_open(vdef: VariableBlock, side: str) -> bool:
    """Whether *vdef* declares nothing at all on *side*.

    A ``domain: binary`` variable is bounded whatever its bounds block says —
    it is 0/1 whatever its bounds block says — and a bound naming a
    parameter is finite or not by data this pass does not have, which is why
    the match is against the open value rather than for a missing bound.
    """
    return vdef.domain != 'binary' and getattr(vdef.bounds, side) == _OPEN[side]


def _variables(node: ExpressionNode) -> set[str]:
    """Every variable named anywhere under *node*."""
    if isinstance(node, VariableNode):
        return {node.name}
    return {name for child in children(node) for name in _variables(child)}


def _flip(sign: Sign) -> Sign:
    return None if sign is None else ('-' if sign == '+' else '+')


def _times(sign: Sign, other: Sign) -> Sign:
    return None if sign is None or other is None else ('+' if sign == other else '-')


def _coefficient_sign(node: ArithmeticNode) -> Sign:
    """The sign *node* scales a term by, or ``None`` unless it is a signed literal.

    ``-2`` parses as a unary minus over a number, so the sign of a literal
    coefficient is not always on the node itself. Zero is ``None`` on purpose:
    a term multiplied away is not in the objective, so the variable it names is
    driven nowhere.
    """
    if isinstance(node, UnaryOperatorNode) and node.op in ('+', '-'):
        inner = _coefficient_sign(node.operand)
        return inner if node.op == '+' else _flip(inner)
    if isinstance(node, NumberNode) and node.value != 0:
        return '+' if node.value > 0 else '-'
    return None


def _walk(node: ArithmeticNode, sign: Sign, signs: dict[str, Sign]) -> None:
    """Record the sign each variable under *node* carries into the objective.

    *signs* accumulates, and a variable reached twice with different signs — or
    once with an undecidable one — lands on ``None``, which claims nothing.
    Every operator the language has sums its argument's terms with coefficient
    1, being a reduction, a re-index or a window, so each hands *sign* to its
    arguments unchanged; a kwarg carries no term at all. Any other binary
    operator — ``**``, and whatever joins it — carries no sign in its operands,
    which is what makes a degree-2 term claim nothing.
    """
    if isinstance(node, VariableNode):
        signs[node.name] = sign if signs.setdefault(node.name, sign) == sign else None
        return
    if isinstance(node, NumberNode | ParameterNode | KwargNode | UnresolvedNode):
        return
    if isinstance(node, UnaryOperatorNode):
        _walk(node.operand, _flip(sign) if node.op == '-' else sign, signs)
        return
    if isinstance(node, FunctionCallNode):
        for arg in node.args:
            _walk(arg, sign, signs)
        for value in node.kwargs.values():
            _walk(value, None, signs)
        return
    if isinstance(node, BinaryOperatorNode):
        if node.op == '+':
            left, right = sign, sign
        elif node.op == '-':
            left, right = sign, _flip(sign)
        elif node.op == '*':
            left = _times(sign, _coefficient_sign(node.right))
            right = _times(sign, _coefficient_sign(node.left))
        elif node.op == '/':
            left, right = _times(sign, _coefficient_sign(node.right)), None
        else:
            left, right = None, None
        _walk(node.left, left, signs)
        _walk(node.right, right, signs)
        return
    assert_never(node)
