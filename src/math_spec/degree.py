"""Degree — the clause of the expressive ceiling that is a scope choice.

Decidable on the resolved core AST with no data bound, which is what makes
``lps.check()`` a real gate rather than a syntax pass, and the one
admissibility rule that is a **scope choice** rather than a consequence of
streaming (docs/about/ceiling.md).

**Degree 2 in the math, degree 1 in what stands beside it.** An objective and a
constraint both take ``variable * variable``; a *bound*, a named expression and
a ``piecewise:`` link do not — each of those is read affinely by something
downstream.

**Where a quadratic model can *land* is a different axis**, declared by each
consumer and answered by ``check(model, sink=...)``. This module says what is
*sayable* and stops there; refusing degree 2 outright was letting one library's
limits read as a rule about math.

A degree-2 product has a second rule: **at most one factor may be a sum of
terms**. ``sum(x, over=i) * sum(y, over=j)`` is every term of one against every
term of the other, a cross join whose size the file states nowhere — the one
shape "bilinear" hides that the ceiling doc genuinely excludes, and the
boundary linopy's own ``*`` draws, which is what keeps hard rule 3 structural
rather than lucky. Factors carrying *different dims* are not that: ``x[i] *
y[j]`` broadcasts, and ``x[i] * y[j] * a[i, j]`` joins through a declared table.

That is why it lives here and not in ``lowering.py``: degree is a property of
the *language*, so both lanes give the same verdict *and the same sentence*, as
they do for dim sets and the closed operator set. Stated once, every consumer
**asks** — a copy in a lane is the spelling no differential test covers.

A divisor's **shape** is decided here too. A quotient is built as
multiplication by one reciprocal factor, and an addition is what makes a
variable-free expression more than one — so a sum divisor is refused, and
refused at load, where the sentence can name the rewrite. Not a degree
question (``x / (a + b)`` is affine) but the same node, the same verdict owed
to both lanes, and the same answer with no data bound.

Deliberately narrow: :func:`check_binary` decides a *binary operator node*, the
only place degree can be lost, and :func:`check_expression` is that decision
over a whole expression — for the formulations, which judge a link before there
is a declaration to name in the error.
"""

from __future__ import annotations

from typing import assert_never

from lpspec.language.errors import LanguageError
from lpspec.language.expression_parser import (
    BinaryOperatorNode,
    ComparisonNode,
    DimensionNode,
    EdgeNode,
    ExpressionNode,
    FunctionCallNode,
    KeywordNode,
    LookupNode,
    NameListNode,
    NameNode,
    NumberNode,
    ParameterNode,
    UnaryOperatorNode,
    VariableNode,
    children,
)

#: The operators the language has. Anything else is refused by name, with the
#: rewrite — ``**`` parses (the grammar is not the ceiling) and dies here, even
#: where ``x * x`` is allowed: a power is a general exponent wearing a special
#: case.
ARITHMETIC_OPERATORS = frozenset({'+', '-', '*', '/'})


def carries_variable(node: ExpressionNode) -> bool:
    """Whether *node* contains a decision variable.

    A structural question over the resolved AST — no data, no plan. A
    ``NameNode`` reaching here is a resolution bug rather than a false
    negative, so it is refused rather than silently answered.
    """
    if isinstance(node, VariableNode):
        return True
    if isinstance(node, (NumberNode, ParameterNode, DimensionNode, LookupNode, EdgeNode)):
        return False
    if isinstance(node, NameListNode):
        msg = (
            f'NameListNode({list(node.names)!r}) reached the degree check. A bracketed list is '
            f'consumed by its kwarg during resolution (docs/about/architecture.md hard rule 1).'
        )
        raise AssertionError(msg)
    if isinstance(node, KeywordNode):
        msg = (
            f'KeywordNode({node.value!r}) reached the degree check. A quoted keyword is '
            f'consumed by its kwarg during resolution (docs/about/architecture.md hard rule 1).'
        )
        raise AssertionError(msg)
    if isinstance(node, NameNode):
        msg = (
            f'NameNode({node.name!r}) reached the degree check. Expressions must go '
            f'through resolution.expression_of() first (docs/about/architecture.md hard rule 1).'
        )
        raise AssertionError(msg)
    if isinstance(node, (UnaryOperatorNode, BinaryOperatorNode, ComparisonNode, FunctionCallNode)):
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
    if isinstance(node, (UnaryOperatorNode, BinaryOperatorNode, ComparisonNode, FunctionCallNode)):
        return any(_adds(c) for c in children(node))
    return False


def is_quadratic(node: ExpressionNode) -> bool:
    """Whether *node* multiplies two variable-carrying operands.

    What :func:`check_binary` refuses at ``ceiling=1``, asked of a whole
    expression rather than of one node — by a consumer that has to *build* the
    thing rather than judge it, and cannot build this one. Whether an
    expression is quadratic is a fact about the expression; what that costs a
    consumer is the consumer's own to declare.

    A second home reads the same question off the *plan* rather than the AST.
    Two, because the two representations are different types and the lanes
    share neither.
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

    Callers want the *raise*, not the answer — the same shape as
    ``dimensions.dims_of`` being asked for its verdict.

    Args:
        node: The product, quotient or sum to judge.
        context: What to name in the message — the declaration being lowered.
        ceiling: The highest degree this position can honour — 2 in an
            objective, 1 everywhere else, and the module docstring is why.

    Raises:
        LanguageError: A product of two variable-carrying factors where the
            position allows only degree 1 or where both factors are sums of
            terms, a divisor carrying a variable or adding, or an operator the
            language does not have.
    """
    where = f'{context}: ' if context else ''
    if node.op not in ARITHMETIC_OPERATORS:
        raise LanguageError(
            f"{where}operator '{node.op}' is not in the language. Write the product "
            f'out — `x * x` for a square — or precompute the factor as a parameter. '
            f'A variable base above degree 2 has no rewrite at all, and one whose '
            f'exponent is data has no degree until the data arrives '
            f'(see docs/about/ceiling.md).'
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
    """A product inside the position's degree at every step and above it whole.

    ``p * p * p`` is two nested products of a variable-carrying pair, each of
    them admissible on its own, so the sentence is about the product's own
    degree rather than about its factors.
    """
    return (
        f'{where}this product is degree {degree}. The language takes degree 2, in the '
        f'**objective** and nowhere else: a sink takes a quadratic form and none takes a '
        f'cubic one.\n'
        f'Multiply by a parameter instead, or give the inner product a name — a variable '
        f'constrained to equal it is degree 1 wherever it is used.'
    )


def _degree_two_here_message(where: str) -> str:
    """Why a product of variables is refused *in this position*.

    Naming the position rather than the math, which is sayable one line away.
    Blaming a solver instead would be the confusion between the ceiling and the
    capability axis that this module exists on the right side of.
    """
    return (
        f'{where}both factors of a product contain variables, which is degree 2. '
        f'The **objective and constraints** take that; a bound, a named expression '
        f'and a piecewise: link do not — each of those is read affinely by '
        f'something downstream.\n'
        f'Multiply the variable by a parameter instead, or state the product where '
        f'it can stand: as a constraint of its own, with a variable holding the '
        f'result. Where a quadratic model can be *solved* is a separate question — '
        f'ask check(model, sink=...) (see docs/about/ceiling.md).'
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
        f'``sum(x, over=d) * sum(y, over=d)``), or give the reduction a name — a variable '
        f'constrained to equal it is one term, and a product of two of those is one term too.'
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

    Lowering asks per node as it descends, because it is already walking. A
    caller that only wants the verdict on an expression it holds asks here,
    and gets the identical sentence — which is the point: ``piecewise:``
    judges its link expressions this way so that ``p * p`` is refused against
    *the link the user wrote*, not against ``curve_link0``, the declaration
    the expansion went on to generate.

    Degree only, deliberately. What a plan node can represent is a different
    question and a consuming lane's to ask; a formulation runs in lanes that
    build no plan at all.
    """
    if isinstance(node, BinaryOperatorNode):
        check_binary(node, context, ceiling=ceiling)
    for child in children(node):
        check_expression(child, context, ceiling=ceiling)
