# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Named sub-expressions and macros — YAML-defined, schema-local, expanded to core AST at load."""

from __future__ import annotations

from functools import partial

import pytest

from math_spec.errors import LanguageError
from math_spec.expansion import parse_and_expand
from math_spec.expression_parser import parse_expression
from tests.fixtures import DISPATCH_MODEL, schema_of

WEIGHTED_SUM = {
    'args': ['array', 'weights'],
    'kwargs': ['over'],
    'template': 'sum(array * weights, over=over)',
}

schema = partial(schema_of, DISPATCH_MODEL)


@pytest.mark.parametrize(
    ('expressions', 'macros', 'call', 'want'),
    [
        pytest.param(
            {'gen_cost': 'p * cost'},
            {},
            'sum(gen_cost, over=generator)',
            'sum(p * cost, over=generator)',
            id='a-named-expression-splices',
        ),
        pytest.param(
            {'gen_cost': 'p * cost', 'total_cost': 'sum(gen_cost, over=generator)'},
            {},
            'total_cost + 1',
            'sum(p * cost, over=generator) + 1',
            id='named-expressions-nest',
        ),
        pytest.param(
            {'total_gen': 'sum(p, over=generator)'},
            {},
            'total_gen == load',
            'sum(p, over=generator) == load',
            id='a-comparison-at-the-top',
        ),
        pytest.param(
            {},
            {'weighted_sum': WEIGHTED_SUM},
            'weighted_sum(p, cost, over=generator)',
            'sum(p * cost, over=generator)',
            id='a-macro-expands',
        ),
        pytest.param(
            {},
            {'double': {'args': ['load'], 'template': 'load + load'}},
            'double(p)',
            'p + p',
            id='a-formal-shadows-the-model-name-it-shares',
        ),
        pytest.param(
            {'gen_cost': 'p * cost'},
            {'twice': {'args': ['x'], 'template': 'x + x'}},
            'twice(gen_cost)',
            '(p * cost) + (p * cost)',
            id='a-macro-argument-may-be-a-named-expression',
        ),
        pytest.param(
            {},
            {
                'total': {'args': ['x'], 'template': 'sum(x, over=generator)'},
                'total_cost': {'template': 'total(p * cost)'},
            },
            'total_cost()',
            'sum(p * cost, over=generator)',
            id='a-macro-body-may-call-a-macro',
        ),
        pytest.param(
            {'sc': 'm(p)'},
            {'m': {'args': ['sc'], 'template': 'sc + 1'}},
            'sc',
            'p + 1',
            id='a-formal-shadows-a-named-expression-so-it-is-not-a-cycle',
        ),
        pytest.param(
            {f'e{i}': f'e{i + 1} + 1' for i in range(80)} | {'e80': 'p'},
            {},
            'e0',
            ' + '.join(['p', *['1'] * 80]),
            id='a-long-acyclic-chain-expands',
        ),
    ],
)
def test_a_call_expands_to_core_ast(expressions, macros, call, want):
    assert parse_and_expand(call, schema(expressions=expressions, macros=macros)) == parse_expression(want)


@pytest.mark.parametrize(
    ('expressions', 'match'),
    [
        pytest.param({'a': 'b + 1', 'b': 'a + 1'}, 'circular expression reference: a -> b -> a', id='a-cycle'),
        pytest.param({'bad': 'p == load'}, 'must not contain a comparison', id='a-comparison'),
        pytest.param({'load': 'p * cost'}, 'collides with the parameter of the same name', id='a-parameter-collision'),
        pytest.param(
            {'broken': 'sum(nope, over=generator)'},
            "Named expression 'broken'",
            id='a-typo-in-a-named-expression',
        ),
    ],
)
def test_a_bad_named_expression_is_refused_at_load(expressions, match):
    with pytest.raises(LanguageError, match=match):
        schema(expressions=expressions)


def test_a_refusal_names_its_context_once():
    with pytest.raises(LanguageError) as exc:
        schema(expressions={'a': 'a + 1'})
    assert str(exc.value).count("Named expression 'a'") == 1, str(exc.value)


@pytest.mark.parametrize(
    ('call', 'match'),
    [
        pytest.param('ws(p, over=generator)', 'expects 2 positional', id='too-few-positionals'),
        pytest.param('ws(p, cost)', 'keyword argument', id='a-missing-keyword'),
    ],
)
def test_macro_arity_errors(call, match):
    with pytest.raises(LanguageError, match=match):
        parse_and_expand(call, schema(macros={'ws': WEIGHTED_SUM}))


@pytest.mark.parametrize(
    ('patch', 'match'),
    [
        pytest.param(
            {'macros': {'load': {'args': ['a'], 'template': 'a'}}},
            'collides with the parameter of the same name',
            id='a-parameter',
        ),
        pytest.param(
            {'expressions': {'thing': 'p * cost'}, 'macros': {'thing': {'args': ['a'], 'template': 'a'}}},
            'collides with the named expression',
            id='a-named-expression',
        ),
        pytest.param(
            {'macros': {'sum': {'args': ['a'], 'template': 'a'}}},
            "collides with the built-in operator 'sum'",
            id='a-built-in-operator',
        ),
        pytest.param(
            {'dimensions.sum': {'dtype': 'int'}},
            "collides with the built-in operator 'sum'",
            id='a-built-in-operator-taken-by-a-dimension',
        ),
        pytest.param(
            {'macros': {'m': {'args': ['generator'], 'template': 'p * generator'}}},
            "formal 'generator' collides with declared dimension 'generator'",
            id='a-formal-named-after-a-dimension',
        ),
    ],
)
def test_macro_collisions_rejected(patch, match):
    """Helper names are reserved for every kind of declaration, not just macros."""
    with pytest.raises(LanguageError, match=match):
        schema(**patch)


@pytest.mark.parametrize(
    ('macros', 'match'),
    [
        pytest.param(
            {'loop_a': {'template': 'loop_b() + 1'}, 'loop_b': {'template': 'loop_a() + 1'}},
            'circular macro reference',
            id='a-cycle',
        ),
        pytest.param(
            {'m': {'args': ['a'], 'kwargs': ['a'], 'template': 'a'}}, 'duplicate formal', id='a-duplicate-formal'
        ),
        pytest.param(
            {'unused': {'args': ['x'], 'template': 'x * cots'}},
            r"Macro 'unused'.*'cots' not found",
            id='a-typo-in-a-template-nothing-calls',
        ),
        pytest.param(
            {'bad': {'args': ['a', 'b'], 'template': 'a == b'}},
            'must not contain a comparison',
            id='a-comparison-in-a-template',
        ),
        pytest.param(
            {'lag': {'args': ['x'], 'template': 'shift(x, over=snapshot, offset=nope)'}},
            r"Macro 'lag'.*'nope' not found",
            id='a-typo-in-an-amount',
        ),
        pytest.param(
            {'grouped': {'args': ['x'], 'template': 'sum(x, by=nope)'}},
            r"Macro 'grouped'.*sum\(by=nope\) does not name a lookup",
            id='a-typo-in-a-lookup-kwarg',
        ),
        pytest.param(
            {'grouped': {'args': ['x'], 'template': 'sum(x, by=[nope, also])'}},
            r"Macro 'grouped'.*sum\(by=nope\) does not name a lookup",
            id='a-typo-in-a-lookup-list',
        ),
    ],
)
def test_macro_templates_validated_even_when_unused(macros, match):
    """A typo in a template the model never calls is still caught at load."""
    with pytest.raises(LanguageError, match=match):
        schema(macros=macros)


@pytest.mark.parametrize('fragment', ['my_python_helper', 'macros:', 'escape'])
def test_an_unknown_operator_is_refused_at_load_with_the_rewrite(fragment):
    with pytest.raises(LanguageError) as exc:
        schema(constraints={'c': {'foreach': ['snapshot'], 'expression': 'my_python_helper(p) <= load'}})
    assert fragment in str(exc.value)
