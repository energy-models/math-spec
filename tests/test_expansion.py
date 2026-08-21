# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Named sub-expressions and macros — YAML-defined, schema-local.

Both expand to core AST before backend dispatch, so one differential test at
the end proves the whole feature works identically on both backends.
"""

from __future__ import annotations

import pytest

from math_spec.expansion import parse_and_expand
from math_spec.expression_parser import parse_expression
from math_spec.model import Model
from tests.fixtures import DISPATCH_MODEL, schema_of

WEIGHTED_SUM = {
    'args': ['array', 'weights'],
    'kwargs': ['over'],
    'template': 'sum(array * weights, over=over)',
}


def make_schema(
    expressions: dict[str, str] | None = None,
    macros: dict | None = None,
    **overrides,
) -> Model:
    """``DISPATCH_MODEL`` as a loaded schema, with whole sections swapped in."""
    if expressions is not None:
        overrides['expressions'] = expressions
    if macros is not None:
        overrides['macros'] = macros
    return schema_of(DISPATCH_MODEL, **overrides)


# ---------------------------------------------------------------------------
# named sub-expressions
# ---------------------------------------------------------------------------


def test_named_expression_splices():
    schema = make_schema({'gen_cost': 'p * cost'})
    got = parse_and_expand('sum(gen_cost, over=generator)', schema)
    want = parse_expression('sum(p * cost, over=generator)')
    assert got == want


def test_named_expressions_nest():
    schema = make_schema({'gen_cost': 'p * cost', 'total_cost': 'sum(gen_cost, over=generator)'})
    got = parse_and_expand('total_cost + 1', schema)
    want = parse_expression('sum(p * cost, over=generator) + 1')
    assert got == want


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
    with pytest.raises(ValueError, match=match):
        make_schema(expressions)


def test_expand_handles_comparison_at_top():
    schema = make_schema({'total_gen': 'sum(p, over=generator)'})
    got = parse_and_expand('total_gen == load', schema)
    want = parse_expression('sum(p, over=generator) == load')
    assert got == want


# ---------------------------------------------------------------------------
# macros
# ---------------------------------------------------------------------------


def test_macro_expansion():
    schema = make_schema(macros={'weighted_sum': WEIGHTED_SUM})
    got = parse_and_expand('weighted_sum(p, cost, over=generator)', schema)
    want = parse_expression('sum(p * cost, over=generator)')
    assert got == want


def test_macro_formals_shadow_model_names():
    """A formal named `load` shadows the model parameter of the same name."""
    schema = make_schema(macros={'double': {'args': ['load'], 'template': 'load + load'}})
    got = parse_and_expand('double(p)', schema)
    want = parse_expression('p + p')
    assert got == want


def test_macro_args_may_use_named_expressions():
    schema = make_schema(
        {'gen_cost': 'p * cost'},
        macros={'twice': {'args': ['x'], 'template': 'x + x'}},
    )
    got = parse_and_expand('twice(gen_cost)', schema)
    want = parse_expression('(p * cost) + (p * cost)')
    assert got == want


def test_macro_body_may_use_macros_and_named_expressions():
    schema = make_schema(
        macros={
            'total': {'args': ['x'], 'template': 'sum(x, over=generator)'},
            'total_cost': {'template': 'total(p * cost)'},
        }
    )
    got = parse_and_expand('total_cost()', schema)
    want = parse_expression('sum(p * cost, over=generator)')
    assert got == want


@pytest.mark.parametrize(
    ('call', 'match'),
    [
        pytest.param('ws(p, over=generator)', 'expects 2 positional', id='too-few-positionals'),
        pytest.param('ws(p, cost)', 'keyword argument', id='a-missing-keyword'),
    ],
)
def test_macro_arity_errors(call, match):
    schema = make_schema(macros={'ws': WEIGHTED_SUM})
    with pytest.raises(ValueError, match=match):
        parse_and_expand(call, schema)


def test_macro_cycle_raises():
    with pytest.raises(ValueError, match='circular macro reference'):
        make_schema(
            macros={
                'loop_a': {'template': 'loop_b() + 1'},
                'loop_b': {'template': 'loop_a() + 1'},
            }
        )


@pytest.mark.parametrize(
    ('build', 'match'),
    [
        pytest.param(
            lambda: make_schema(macros={'load': {'args': ['a'], 'template': 'a'}}),
            'collides with the parameter of the same name',
            id='a-parameter',
        ),
        pytest.param(
            lambda: make_schema({'thing': 'p * cost'}, macros={'thing': {'args': ['a'], 'template': 'a'}}),
            'collides with the named expression',
            id='a-named-expression',
        ),
        pytest.param(
            lambda: make_schema(macros={'sum': {'args': ['a'], 'template': 'a'}}),
            "collides with the built-in operator 'sum'",
            id='a-built-in-operator',
        ),
        pytest.param(
            lambda: Model(dimensions={'sum': {'values': [1]}}),
            "collides with the built-in operator 'sum'",
            id='a-built-in-operator-taken-by-a-dimension',
        ),
    ],
)
def test_macro_collisions_rejected(build, match):
    """Helper names are reserved for every kind of declaration, not just macros.

    The collision is caught building the schema rather than validating it.
    """
    with pytest.raises(ValueError, match=match):
        build()


def test_duplicate_formals_rejected():
    with pytest.raises(ValueError, match='duplicate formal'):
        make_schema(macros={'m': {'args': ['a'], 'kwargs': ['a'], 'template': 'a'}})


@pytest.mark.parametrize(
    ('macros', 'match'),
    [
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
    ],
)
def test_macro_templates_validated_even_when_unused(macros, match):
    """Schema-local macros make load-time validation complete: a typo in a
    template the model never calls is still caught."""
    with pytest.raises(ValueError, match=match):
        make_schema(macros=macros)


# ---------------------------------------------------------------------------
# end to end: both backends, same self-contained YAML, same answer
# ---------------------------------------------------------------------------


EXPANSION_YAML = """
dimensions:
  snapshot: {dtype: int}
  generator: {values: [wind, solar, gas]}
parameters:
  p_max: {dims: [generator]}
  cost: {dims: [generator]}
  load: {dims: [snapshot]}
expressions:
  total_generation: sum(p, over=generator)
macros:
  weighted_sum:
    args: [array, weights]
    kwargs: [over]
    template: sum(array * weights, over=over)
variables:
  p:
    foreach: [snapshot, generator]
    where: "p_max > 0"
    bounds: {lower: 0, upper: p_max}
constraints:
  balance:
    foreach: [snapshot]
    expression: total_generation == load
objective:
  sense: minimize
  expression: sum(weighted_sum(p, cost, over=generator))
"""


def test_unknown_operator_rejected_at_load_time_with_the_rewrite():
    """An unknown operator fails validation, before either backend is chosen."""
    with pytest.raises(ValueError) as exc:
        make_schema(
            constraints={
                'c': {
                    'foreach': ['snapshot'],
                    'expression': 'my_python_helper(p) <= load',
                }
            }
        )

    message = str(exc.value)
    assert 'my_python_helper' in message
    assert 'macros:' in message, 'the rejection teaches the rewrite'
    assert 'escape' in message, 'the rejection teaches the rewrite'
    assert 'eager' not in message.lower(), 'and never points at another backend'
