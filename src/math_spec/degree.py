# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Degree — the one admissibility rule that is a scope choice (docs/about/ceiling.md).

**Degree 2 in the math, degree 1 in what stands beside it.** An objective and a
constraint both take ``variable * variable``; a *bound*, a named expression and
a ``piecewise:`` link do not — each of those is read affinely.

A degree-2 product has a second rule: **at most one factor may be a sum of
terms**. ``sum(x, over=i) * sum(y, over=j)`` is a cross join whose size the
file states nowhere. Factors carrying *different dims* are not that: ``x[i] *
y[j]`` broadcasts.

A divisor's **shape** is decided here too: a quotient is multiplication by one
reciprocal factor, so a divisor that adds is refused at load, where the message
can name the rewrite.
"""

from __future__ import annotations

from typing import assert_never

from math_spec.errors import LanguageError
from math_spec.expression_parser import (
    BinaryOperatorNode,
    BranchNode,
    ExpressionNode,
    FunctionCallNode,
    KwargNode,
    NumberNode,
    ParameterNode,
    UnresolvedNode,
    VariableNode,
    children,
)


def carries_variable(node: ExpressionNode) -> bool:
    """Whether *node* contains a decision variable.

    An unresolved node reaching here is a resolution bug, so it is refused
    rather than silently answered.
    """
    if isinstance(node, VariableNode):
        return True
    if isinstance(node, NumberNode | ParameterNode | KwargNode):
        return False
    if isinstance(node, UnresolvedNode):
        msg = f'{node!r} reached the degree check. Expressions go through resolution.expression_of() first.'
        raise AssertionError(msg)
    if isinstance(node, BranchNode):
        return any(carries_variable(c) for c in children(node))
    assert_never(node)


def _adds(node: ExpressionNode) -> bool:
    """Whether *node* adds anywhere inside it.

    Anywhere, not only at its head: every operator over a variable-free
    expression maps over its parts rather than folding them, so an addition
    under a ``sum`` or a product reaches the quotient as two factors just as
    one at the top does.
    """
    if isinstance(node, BinaryOperatorNode) and node.op in ('+', '-'):
        return True
    if isinstance(node, BranchNode):
        return any(_adds(c) for c in children(node))
    return False


def is_quadratic(node: ExpressionNode) -> bool:
    """Whether *node* multiplies two variable-carrying operands.

    What :func:`check_binary` refuses at ``ceiling=1``, asked of a whole
    expression rather than of one node.
    """
    if (
        isinstance(node, BinaryOperatorNode)
        and node.op == '*'
        and carries_variable(node.left)
        and carries_variable(node.right)
    ):
        return True
    return any(is_quadratic(child) for child in children(node))


def check_binary(node: BinaryOperatorNode, context: str | None = None, *, ceiling: int = 1) -> None:
    """Check that *node* stays inside the degree its position allows.

    Args:
        node: The product, quotient or sum to judge.
        context: What to name in the message — the declaration being read.
        ceiling: The highest degree this position can honour — 2 in an
            objective or a constraint, 1 everywhere else.

    Raises:
        LanguageError: A product of two variable-carrying factors where the
            position allows only degree 1 or where both factors are sums of
            terms, a power over anything carrying a variable, a divisor carrying
            a variable or adding.
    """
    where = f'{context}: ' if context else ''
    if node.op == '**':
        if carries_variable(node):
            raise LanguageError(_a_variable_under_a_power_message(where))
        if _adds(node.left) or _adds(node.right):
            raise LanguageError(
                f'{where}a base and an exponent must each be a single Constant/Parameter factor, '
                f'not a sum — addition does not distribute over `**`, so `(1 + rate) ** period` is '
                f'refused where `growth ** period` is not. Bind the factor itself.'
            )
    if node.op == '/' and carries_variable(node.right):
        raise LanguageError(
            f'{where}the divisor contains variables, which is not affine. '
            f'Divide by a parameter, or precompute the reciprocal as one.'
        )
    if node.op == '/' and _adds(node.right):
        raise LanguageError(
            f'{where}a divisor must be a single Constant/Parameter factor, '
            f'not a sum — rewrite as multiplication by a precomputed parameter'
        )
    if node.op != '*' or not (carries_variable(node.left) and carries_variable(node.right)):
        return
    if ceiling < 2:
        raise LanguageError(_degree_two_here_message(where))
    if (degree := _degree(node)) > ceiling:
        raise LanguageError(_above_the_ceiling_message(where, degree))
    _check_single_term_factor(node, where)


def _degree(node: ExpressionNode) -> int:
    """The polynomial degree *node* stands for, counted structurally.

    A product adds its factors' degrees and a division keeps the dividend's
    (:func:`check_binary` has already refused a divisor carrying a variable);
    everything else — a sum, a reduction, a shape operator — is the highest
    degree beneath it. No data, so this answers at ``check`` time, which is
    what stops a cubic from reaching a lane to be refused by whichever one
    happens to notice.
    """
    if isinstance(node, VariableNode):
        return 1
    if isinstance(node, BinaryOperatorNode) and node.op == '*':
        return _degree(node.left) + _degree(node.right)
    if isinstance(node, BinaryOperatorNode) and node.op == '/':
        return _degree(node.left)
    return max((_degree(child) for child in children(node)), default=0)


def _above_the_ceiling_message(where: str, degree: int) -> str:
    """About the product's own degree, since ``p * p * p`` is two admissible products nested."""
    return (
        f'{where}this product is degree {degree}. The language takes degree 2 and nothing above it.\n'
        f'Multiply by a parameter instead, or give the inner product a name — a variable '
        f'constrained to equal it is degree 1 wherever it is used.'
    )


def _a_variable_under_a_power_message(where: str) -> str:
    """A variable base is a degree question; a variable exponent has no degree until the data arrives."""
    return (
        f'{where}`**` is not in the language over variables: it takes a base and an exponent that '
        f'carry none.\n'
        f'Write the product out — `x * x` for a square — or precompute the factor as a parameter. '
        f'A variable base above degree 2 has no rewrite at all, and one whose exponent is data has '
        f'no degree until the data arrives — see docs/about/ceiling.md.'
    )


def _degree_two_here_message(where: str) -> str:
    """Names the position, not the math — the same product is admissible one declaration away."""
    return (
        f'{where}both factors of a product contain variables, which is degree 2. '
        f'The **objective and constraints** take that; a bound, a named expression '
        f'and a piecewise: link do not — each of those is read affinely by '
        f'something downstream.\n'
        f'Multiply the variable by a parameter instead, or state the product where '
        f'it can stand: as a constraint of its own, with a variable holding the '
        f'result.'
    )


def _check_single_term_factor(node: BinaryOperatorNode, where: str) -> None:
    """Refuse a degree-2 product of two multi-term factors."""
    if not (_multi_term(node.left) and _multi_term(node.right)):
        return
    raise LanguageError(
        f'{where}both factors of this product are sums of more than one term, so it is an outer '
        f'product — every term of one against every term of the other, and nothing in the file '
        f'says how many that is.\n'
        f'Multiply *before* reducing (``sum(x * y, over=d)`` rather than '
        f'``sum(x, over=d) * sum(y, over=d)``).'
    )


def _multi_term(node: ExpressionNode) -> bool:
    """Whether *node* stands for more than one variable term at a coordinate.

    A reduction does, and so does an addition of two variable-carrying
    operands; a product is multi-term exactly when one of its factors is, a
    coefficient not multiplying the count. Structural, so it needs no data.
    """
    if isinstance(node, FunctionCallNode):
        if node.name in _REDUCTIONS and any(carries_variable(a) for a in node.args):
            return True
        return any(_multi_term(c) for c in children(node))
    if isinstance(node, BinaryOperatorNode):
        if node.op in ('+', '-') and carries_variable(node.left) and carries_variable(node.right):
            return True
        return _multi_term(node.left) or _multi_term(node.right)
    return any(_multi_term(c) for c in children(node))


#: The operators that fold several coordinates onto one, and so turn a term
#: into a sum of terms. ``at`` and ``shift`` re-index and are not here: they
#: move a term, leaving one term where there was one.
_REDUCTIONS = frozenset({'sum', 'sum_back'})


def check_expression(node: ExpressionNode, context: str, *, ceiling: int = 1) -> None:
    """Apply :func:`check_binary` everywhere in *node*.

    Degree only, deliberately: what a plan node can represent is a consuming
    lane's question.
    """
    if isinstance(node, BinaryOperatorNode):
        check_binary(node, context, ceiling=ceiling)
    for child in children(node):
        check_expression(child, context, ceiling=ceiling)
