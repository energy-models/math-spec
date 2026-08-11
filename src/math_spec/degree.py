"""Degree 1 — the first clause of the expressive ceiling, in one place.

``variable * parameter``, never ``variable * variable``. It is decidable on
the resolved core AST with no data bound, which is what makes ``lps.check()``
a real gate rather than a syntax pass, and it is the one admissibility rule
that is a **scope choice** rather than a consequence of streaming
(docs/design/ceiling.md).

That is why it lives here and not in ``lowering.py``. Degree is a property of
the *language*, not of any plan — the ceiling doc says so in as many words —
so both lanes have to give the same verdict *and the same sentence*, the way
they already do for dim sets (:mod:`lpspec.language.dimensions`) and the
closed helper set (:mod:`lpspec.language.helpers`). Stated once here, every
consumer **asks**; none answers. A copy of the rule in a lane is a second
spelling of one language rule, and the copy is the one no differential test
covers.

The decision is deliberately narrow: :func:`check_binary` decides a *binary
operator node*, which is the only place degree can be lost. Everything else
either preserves degree (``+``, unary ``-``, a reduction) or cannot introduce
a variable at all. :func:`check_expression` is that decision over a whole
expression, for a caller that has one in hand rather than a descent to hang
it on — the formulations, which must judge a link *before* there is a
declaration to name in the error.
"""

from __future__ import annotations

from typing import assert_never

from lpspec.errors import LanguageError
from lpspec.language.expression_parser import (
    BinaryOperatorNode,
    ComparisonNode,
    CoordinateNode,
    DimensionNode,
    EdgeNode,
    ExpressionNode,
    FunctionCallNode,
    KeywordNode,
    NameNode,
    NumberNode,
    ParameterNode,
    UnaryOperatorNode,
    VariableNode,
    children,
)

#: The operators the language has. Anything else is refused by name, with the
#: rewrite — ``**`` parses (the grammar is not the ceiling) and dies here.
ARITHMETIC_OPERATORS = frozenset({'+', '-', '*', '/'})


def carries_variable(node: ExpressionNode) -> bool:
    """Whether *node* contains a decision variable.

    A structural question over the resolved AST — no data, no plan. A
    ``NameNode`` reaching here is a resolution bug rather than a false
    negative, so it is refused rather than silently answered.
    """
    if isinstance(node, VariableNode):
        return True
    if isinstance(node, (NumberNode, ParameterNode, DimensionNode, CoordinateNode, EdgeNode)):
        return False
    if isinstance(node, KeywordNode):
        msg = (
            f'KeywordNode({node.value!r}) reached the degree check. A quoted keyword is '
            f'consumed by its kwarg during resolution (docs/ARCHITECTURE.md hard rule 1).'
        )
        raise AssertionError(msg)
    if isinstance(node, NameNode):
        msg = (
            f'NameNode({node.name!r}) reached the degree check. Expressions must go '
            f'through resolution.expression_of() first (docs/ARCHITECTURE.md hard rule 1).'
        )
        raise AssertionError(msg)
    if isinstance(node, (UnaryOperatorNode, BinaryOperatorNode, ComparisonNode, FunctionCallNode)):
        return any(carries_variable(c) for c in children(node))
    assert_never(node)


def check_binary(node: BinaryOperatorNode, context: str | None = None) -> None:
    """Raise :class:`LanguageError` if *node* would leave degree 1.

    The three ways it can: both factors of a product carrying variables, a
    divisor carrying one, and an operator the language does not have. Callers
    want the *raise*, not the answer — this is the same shape as
    ``dimensions.dims_of`` being asked for its verdict.
    """
    where = f'{context}: ' if context else ''
    if node.op not in ARITHMETIC_OPERATORS:
        raise LanguageError(
            f"{where}operator '{node.op}' is not in the language. Multiply the "
            f'term out, or precompute it as a parameter — a variable base would '
            f'make the model nonlinear (see docs/design/ceiling.md).'
        )
    if node.op == '*' and carries_variable(node.left) and carries_variable(node.right):
        raise LanguageError(
            f'{where}both factors of a product contain variables, which '
            f'is degree 2. Multiply the variable by a parameter instead, or '
            f'model the curve with a piecewise: block — see '
            f'docs/design/ceiling.md.'
        )
    if node.op == '/' and carries_variable(node.right):
        raise LanguageError(
            f'{where}the divisor contains variables, which is not affine. '
            f'Divide by a parameter, or precompute the reciprocal as one.'
        )


def check_expression(node: ExpressionNode, context: str | None = None) -> None:
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
        check_binary(node, context)
    for child in children(node):
        check_expression(child, context)
