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
from math_spec.degree import carries_variable, check_binary, check_expression, is_postsolve_grade, is_quadratic
from math_spec.expression_parser import NameNode
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


def test_the_context_is_optional_and_prefixes_the_sentence():
    with pytest.raises(LanguageError, match=r"^Constraint 'k': both factors"):
        check_binary(_ast('p * q'), "Constraint 'k'")
    with pytest.raises(LanguageError, match=r'^both factors'):
        check_binary(_ast('p * q'))


@pytest.mark.parametrize(
    ('text', 'quadratic'),
    [
        pytest.param('p * q', True, id='a-product'),
        pytest.param('sum(p * c * q, over=g)', True, id='under-a-reduction'),
        pytest.param('c + shift(p * q, over=g, offset=1)', True, id='under-an-operator'),
        pytest.param('p * c', False, id='affine'),
        pytest.param('p + q', False, id='a-sum-is-not-a-product'),
        pytest.param('c ** 2', False, id='no-variable'),
    ],
)
def test_is_quadratic_finds_a_product_of_variables_anywhere(text, quadratic):
    assert is_quadratic(_ast(text)) is quadratic


def test_carries_variable_refuses_an_unresolved_name():
    with pytest.raises(AssertionError, match=r'resolution\.expression_of'):
        carries_variable(NameNode('p'))


@pytest.mark.parametrize(
    'text',
    [
        pytest.param('p * q', id='the-degree-cap'),
        pytest.param('p * p * p', id='above-the-degree-cap'),
        pytest.param('sum(p * c, over=g) / sum(p, over=g)', id='a-variable-divisor'),
        pytest.param('k ** p', id='a-variable-exponent'),
        pytest.param('sum(p, over=g) / (k + 1)', id='an-additive-divisor'),
        pytest.param('sum(p, over=g) * (k + 1) ** 2', id='an-additive-base'),
    ],
)
def test_a_body_that_breaks_an_affine_rule_grades_post_solve(text):
    """Every rule the affine ceiling holds lifts here — each such body is post-solve grade.

    One case per rule `check_expression(ceiling=1)` enforces: the degree cap and
    the ban above it, the variable divisor and exponent, the additive divisor
    and additive base. Each is refused wherever the math reads it (see
    `test_the_affine_ceiling_refuses_and_names_the_rewrite`) and legal only as a
    quantity read off a solve.
    """
    assert is_postsolve_grade(_ast(text)) is True


@pytest.mark.parametrize(
    'text',
    [
        pytest.param('p * c', id='a-parameter-coefficient'),
        pytest.param('sum(p * c, over=g)', id='a-reduction-of-affine-terms'),
        pytest.param('p / c', id='a-parameter-divisor'),
        pytest.param('p + q', id='a-sum-of-variables'),
    ],
)
def test_an_affine_body_grades_math(text):
    """A body inside the affine ceiling grades math — it behaves exactly as a named expression always has."""
    assert is_postsolve_grade(_ast(text)) is False


@pytest.mark.parametrize(
    ('template', 'postsolve'),
    [
        pytest.param('x * x', True, id='a-macro-that-squares-a-variable'),
        pytest.param('x * c', False, id='a-macro-that-scales-a-variable'),
    ],
)
def test_the_grade_is_decided_on_the_expanded_body(template, postsolve):
    """A macro cannot smuggle nonlinearity past the grade: it is read on the inlined body, not the call.

    `sq(p)` looks affine at the call site; its expansion `p * p` is degree 2, so
    the entry grades post-solve. The same call over a parameter stays math. The
    grade is body-local after expansion, decided at load with no data.
    """
    schema = schema_of(override(SMALL_MODEL, macros={'sq': {'args': ['x'], 'template': template}}))
    ast = expression_of('sq(p)', schema, Namespace.of(schema), 'test')
    assert is_postsolve_grade(ast) is postsolve
