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
from math_spec.degree import carries_variable, check_binary, check_expression
from math_spec.expression_parser import NameNode
from math_spec.resolution import Namespace, expression_of
from tests.fixtures import SMALL_MODEL, schema_of

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
