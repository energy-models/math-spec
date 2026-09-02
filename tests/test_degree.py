# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The degree ceiling, asked of the resolved AST with no data.

`check_binary` is the one rule — a consumer never re-derives it — so each
refusal it can make has a case here, and so does each shape it must let past.
"""

from __future__ import annotations

import pytest

from math_spec import LanguageError
from math_spec._expression_parser import NameNode
from math_spec.degree import carries_variable, check_binary, check_expression, is_reported_grade
from math_spec.resolution import Namespace, expression_of
from tests.fixtures import SMALL_MODEL, override, schema_of

SCHEMA = schema_of(SMALL_MODEL)


def _ast(text: str):
    return expression_of(text, SCHEMA, Namespace.of(SCHEMA), 'test')


@pytest.mark.parametrize(
    'text',
    [
        pytest.param('p * c', id='a-parameter-coefficient'),
        pytest.param('c * k * p', id='two-coefficients'),
        pytest.param('p / c', id='a-parameter-divisor'),
        pytest.param('c ** 2', id='a-power-over-parameters'),
        pytest.param('k ** c', id='a-parameter-exponent'),
        pytest.param('sum(p * c, over=g)', id='a-reduction-of-affine-terms'),
        pytest.param('p + q', id='a-sum-of-variables'),
    ],
)
def test_an_affine_expression_passes_everywhere(text):
    check_expression(_ast(text), 'test', ceiling=1)


@pytest.mark.parametrize(
    ('text', 'fragment'),
    [
        pytest.param('p * q', 'which is degree 2', id='a-product-of-two-variables'),
        pytest.param('p * (c * q)', 'which is degree 2', id='a-variable-under-each-factor'),
        pytest.param('p ** 2', '`**` is not in the language over variables', id='a-variable-base'),
        pytest.param('k ** p', '`**` is not in the language over variables', id='a-variable-exponent'),
        pytest.param('(c + 1) ** 2', 'not a sum', id='a-sum-as-a-base'),
        pytest.param('k ** (c + 1)', 'not a sum', id='a-sum-as-an-exponent'),
        pytest.param('p / q', 'the divisor contains variables', id='a-variable-divisor'),
        pytest.param('p / (c + 1)', 'a divisor must be a single Constant/Parameter factor', id='a-divisor-that-adds'),
        pytest.param(
            'p / sum(c + k, over=g)', 'a divisor must be a single', id='an-addition-under-a-reduction-divisor'
        ),
    ],
)
def test_the_affine_ceiling_refuses_and_names_the_rewrite(text, fragment):
    with pytest.raises(LanguageError, match=r'^test: ') as exc:
        check_expression(_ast(text), 'test', ceiling=1)
    assert fragment in str(exc.value)


@pytest.mark.parametrize(
    'text',
    [
        pytest.param('p * q', id='one-product'),
        pytest.param('sum(p * q, over=g)', id='multiplied-before-reducing'),
        pytest.param('sum(p, over=g) * q', id='one-multi-term-factor'),
        pytest.param('(p + q) * c * p', id='a-sum-against-one-term'),
        pytest.param('p * q / c', id='a-quadratic-over-a-parameter'),
        pytest.param('p * r * c', id='a-broadcast-product-of-disjoint-dims'),
    ],
)
def test_the_objective_takes_degree_two(text):
    check_expression(_ast(text), 'test', ceiling=2)


@pytest.mark.parametrize(
    ('text', 'fragment'),
    [
        pytest.param('p * q * p', 'this product is degree 3', id='a-cubic'),
        pytest.param('(p * q) * (p * q)', 'this product is degree 4', id='a-quartic'),
        pytest.param('sum(p, over=g) * sum(q, over=g)', 'outer product', id='two-reductions'),
        pytest.param('(p + q) * (p + q)', 'outer product', id='two-sums-of-variables'),
        pytest.param('sum_back(p, over=g, within=1) * (p - q)', 'outer product', id='a-window-against-a-difference'),
    ],
)
def test_degree_two_is_one_term_against_one_term_and_no_higher(text, fragment):
    with pytest.raises(LanguageError) as exc:
        check_expression(_ast(text), 'test', ceiling=2)
    assert fragment in str(exc.value)


@pytest.mark.parametrize(
    ('context', 'opening'),
    [
        pytest.param("Constraint 'k'", r"^Constraint 'k': both factors", id='a-context-prefixes-the-sentence'),
        pytest.param('', r'^both factors', id='an-empty-one-leaves-it-bare'),
    ],
)
def test_the_context_prefixes_the_sentence_and_an_empty_one_leaves_it_bare(context, opening):
    with pytest.raises(LanguageError, match=opening):
        check_binary(_ast('p * q'), context, ceiling=1)


def test_carries_variable_refuses_an_unresolved_name():
    with pytest.raises(AssertionError, match=r'resolution\.expression_of'):
        carries_variable(NameNode('p'))


@pytest.mark.parametrize(
    'text',
    [
        pytest.param('p * p * p', id='above-the-degree-cap'),
        pytest.param('sum(p * c, over=g) / sum(p, over=g)', id='a-variable-divisor'),
        pytest.param('k ** p', id='a-variable-exponent'),
        pytest.param('sum(p, over=g) / (k + 1)', id='an-additive-divisor'),
        pytest.param('sum(p, over=g) * (k + 1) ** 2', id='an-additive-base'),
    ],
)
def test_a_body_no_math_position_reads_grades_reported(text):
    """A body that breaks the math's own ceiling is reported grade — no position reads it.

    One case per rule `check_expression(ceiling=2)` enforces above degree 2: the
    ban on a degree-3 product, the variable divisor and exponent, the additive
    divisor and additive base. Each is refused wherever the math reads it (see
    `test_the_affine_ceiling_refuses_and_names_the_rewrite`) and legal only as a
    quantity read off a solve.
    """
    assert is_reported_grade(_ast(text)) is True


@pytest.mark.parametrize(
    'text',
    [
        pytest.param('p * c', id='a-parameter-coefficient'),
        pytest.param('sum(p * c, over=g)', id='a-reduction-of-affine-terms'),
        pytest.param('p / c', id='a-parameter-divisor'),
        pytest.param('p + q', id='a-sum-of-variables'),
        pytest.param('p * q', id='a-degree-two-product'),
    ],
)
def test_a_body_within_the_math_ceiling_grades_math(text):
    """A body the objective and constraints read grades math — up to the degree-2 ceiling the math holds to.

    A degree-2 product `p * q` grades math, not reported: the objective reads
    it, so the grade boundary sits at `ceiling=2`, not the affine ceiling.
    """
    assert is_reported_grade(_ast(text)) is False


@pytest.mark.parametrize(
    ('template', 'reported'),
    [
        pytest.param('x * x * x', True, id='a-macro-that-cubes-a-variable'),
        pytest.param('x * c', False, id='a-macro-that-scales-a-variable'),
    ],
)
def test_the_grade_is_decided_on_the_expanded_body(template, reported):
    """A macro cannot smuggle nonlinearity past the grade: it is read on the inlined body, not the call.

    `cube(p)` looks affine at the call site; its expansion `p * p * p` is degree
    3, above the math's ceiling, so the entry is reported grade. The same call
    over a parameter stays math. The grade is body-local after expansion,
    decided at load with no data.
    """
    schema = schema_of(override(SMALL_MODEL, macros={'cube': {'args': ['x'], 'template': template}}))
    ast = expression_of('cube(p)', schema, Namespace.of(schema), 'test')
    assert is_reported_grade(ast) is reported


def _dual_ast(text: str):
    schema = schema_of(SMALL_MODEL, **{'constraints.lim': {'foreach': ['g'], 'expression': 'p <= c'}})
    return expression_of(text, schema, Namespace.of(schema), 'test')


def test_a_dual_carries_no_variable():
    """A dual is data read after the solve, so it is not a variable term."""
    assert carries_variable(_dual_ast('dual(lim)')) is False


def test_a_body_reading_a_dual_grades_reported():
    """A dual is a number only a solve produces, so the entry reading one is reported grade even where its arithmetic is affine."""
    assert is_reported_grade(_dual_ast('dual(lim) * c')) is True


@pytest.mark.parametrize(
    'text',
    [
        pytest.param('dual(lim)', id='bare'),
        pytest.param('sum(dual(lim), over=g)', id='under-a-reduction'),
    ],
)
def test_a_nested_dual_grades_reported(text):
    """`calls_dual` recurses through a reduction's argument, not only the top node."""
    assert is_reported_grade(_dual_ast(text)) is True


def test_a_dual_inside_a_cased_arm_grades_reported():
    """`calls_dual` recurses through a `CasesNode` arm, not only the top node.

    The reference resolves straight to the `CasesNode` expansion.py builds, so
    this also guards that `children()` walking its arm values reaches a dual a
    non-recursive check — one that only inspected the node it was handed —
    would miss.
    """
    schema = schema_of(
        SMALL_MODEL,
        **{
            'constraints.lim': {'foreach': ['g'], 'expression': 'p <= c'},
            'expressions.dcase': {
                'foreach': ['g'],
                'cases': {'flagged': {'when': 'flag', 'expression': 'dual(lim)'}},
                'otherwise': 0,
            },
        },
    )
    ast = expression_of('dcase', schema, Namespace.of(schema), 'test')
    assert is_reported_grade(ast) is True
