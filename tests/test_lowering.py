# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The lowering pass: a resolved model in, a logical plan out.

The plan is read back node by node rather than through the answer it produces:
it is the contract both lanes are written against, so its *shape* is the thing
under test here and what either lane then builds from it is not.

Nothing in this module binds data, builds a model or names a lane. That is the
point of it — the pass has one input and one output, both of them values, and a
test that needed a solver to reach it would be testing the assembly instead.
Lowering's verdict reaching a caller is ``test_language_boundary.py``; the two
lanes agreeing about it is ``test_degree_parity.py`` and its siblings.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from math_spec import LanguageError, Spec
from math_spec.lowering import _lower_where, _Lowering, lower_program
from math_spec.piecewise import expand_piecewise
from math_spec.program import (
    At,
    DimensionDeclaration,
    Divide,
    LookupDeclaration,
    Parameter,
    Power,
    Program,
    Sum,
    Variable,
    divisor_parameters,
    quotients,
    variables_of,
)
from math_spec.resolution import Namespace, expression_of
from math_spec.where_parser import (
    DimensionComparisonNode,
    ParameterComparisonNode,
    ParameterDefinedNode,
)
from tests.fixtures import schema_of

if TYPE_CHECKING:
    from math_spec.expression_parser import ArithmeticNode

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / 'examples'


def resolved(text: str, schema: Spec) -> ArithmeticNode:
    """Parse, expand and resolve — exactly what the lowering pass receives.

    A raw ``parse_expression`` result still holds ``NameNode``s, and lowering
    asserts those never reach it. The ``'t'`` is the error-context label the
    resolver stamps on refusals, not a dimension.
    """
    return expression_of(text, schema, Namespace.of(schema), 't')


DISPATCH_YAML = EXAMPLES_DIR / 'dispatch.yaml'


@pytest.fixture
def dispatch_schema() -> Spec:
    return schema_of(DISPATCH_YAML)


# ---------------------------------------------------------------------------
# the plan the language lowers to
# ---------------------------------------------------------------------------


def test_lower_program_structure(dispatch_schema):
    program = lower_program(expand_piecewise(dispatch_schema))

    assert [p.name for p in program.parameters] == ['p_max', 'load', 'cost']
    (v,) = program.variables
    assert v.name == 'p'
    assert v.dims == ('snapshot', 'generator')
    assert v.where == ParameterComparisonNode('p_max', '>', 0.0)
    assert v.upper == Parameter('p_max')

    (c,) = program.constraints
    assert c.name == 'power_balance'
    assert c.dims == ('snapshot',)
    assert c.lhs == Sum(Variable('p'), ('generator',))
    assert c.sense == '=='
    assert c.rhs == Parameter('load')

    assert program.objective.sense == 'minimize', "the program carries the language's spelling, untranslated"
    assert program.objective.expression == Sum(Variable('p') * Parameter('cost'), ('generator', 'snapshot')), (
        'the objective carries the sum the file wrote, over the dims it named none of'
    )


@pytest.mark.parametrize('sense', [pytest.param('minimize', id='minimize'), pytest.param('maximize', id='maximize')])
def test_the_objective_sense_crosses_untranslated(sense: str):
    """One spelling from the file to the program, and each sink translates at its own edge.

    A second spelling here would be two names for one axis inside one package
    once the program is declared beside the language, and a stale one is not a
    type error: the sense is a ``Literal``, so a program built by hand with a
    retired spelling reaches a sink whose comparison quietly fails and flips
    the model rather than refusing it.

    Both directions, because a translation reintroduced for one of them is what
    a single case would miss.
    """
    model = {
        'dimensions': {'g': {'dtype': 'str'}},
        'parameters': {'cost': {'dims': ['g']}},
        'variables': {'p': {'foreach': ['g'], 'bounds': {'lower': 0, 'upper': 1}}},
        'constraints': {'c': {'foreach': [], 'expression': 'sum(p, over=g) >= 1'}},
        'objective': {'sense': sense, 'expression': 'sum(p * cost, over=g)'},
    }
    program = lower_program(expand_piecewise(Spec.model_validate(model)))
    assert program.objective is not None
    assert program.objective.sense == sense, "the file's own word for the direction, unchanged"


def test_a_file_with_no_objective_lowers_to_no_sense():
    """A feasibility problem has no direction, and nothing downstream invents one."""
    model = {
        'dimensions': {'g': {'dtype': 'str'}},
        'variables': {'p': {'foreach': ['g'], 'bounds': {'lower': 0, 'upper': 1}}},
        'constraints': {'c': {'foreach': [], 'expression': 'sum(p, over=g) >= 1'}},
    }
    program = lower_program(expand_piecewise(Spec.model_validate(model)))
    assert program.objective is None, 'no objective declared is no objective, not a minimisation of nothing'


@pytest.mark.parametrize(
    ('where', 'expected'),
    [
        pytest.param(None, None, id='no-where-at-all'),
        pytest.param('True', None, id='True-is-no-mask'),
        pytest.param('p_max', ParameterDefinedNode('p_max'), id='a-bare-parameter-name'),
        pytest.param(
            'snapshot > 5',
            DimensionComparisonNode('snapshot', '>', 5),
            id='a-dimension-coordinate-compares-like-a-parameter',
        ),
    ],
)
def test_where_lowering(dispatch_schema, where, expected):
    assert _lower_where(where, Namespace.of(dispatch_schema), 't') == expected


def test_a_compound_where_lowers_to_something(dispatch_schema):
    assert _lower_where('p_max > 0 AND NOT load == 0', Namespace.of(dispatch_schema), 't') is not None


def test_an_unknown_where_name_is_an_error_at_lowering_too(dispatch_schema):
    """It used to be a scalar-False mask in the eager lane: a model that
    builds, solves, and is silently empty. Resolution makes it a load error."""
    with pytest.raises(LanguageError, match="'no_such_param' not found"):
        _lower_where('no_such_param', Namespace.of(dispatch_schema), 't')


def test_a_lowered_mask_cannot_be_rewritten_in_place(dispatch_schema):
    """A consumer handed a program could invert the mask another one reads.

    The where nodes were plain dataclasses while every declaration embedding
    them was frozen, so `variable.where.op = '!='` rewrote `p_max > 0` into
    `p_max != 0` on the shared object — two consumers disagreeing about one
    file, which is the failure a program exists to prevent. It also left
    hashability depending on the file: an unmasked declaration hashed and a
    masked one raised TypeError.
    """
    program = lower_program(expand_piecewise(dispatch_schema))
    (v,) = program.variables
    assert v.where == ParameterComparisonNode('p_max', '>', 0.0)

    with pytest.raises(FrozenInstanceError):
        v.where.op = '!='
    assert v.where == ParameterComparisonNode('p_max', '>', 0.0), 'the mask the file wrote, unchanged'
    assert isinstance(hash(v), int), 'a masked declaration hashes like an unmasked one'


def test_a_power_lowers_to_a_node_of_its_own(dispatch_schema):
    lowered = _Lowering(dispatch_schema, 't').expr(resolved('cost ** cost', dispatch_schema))
    assert isinstance(lowered, Power), 'a variable-free power has a plan node of its own'


def test_a_binary_variable_lowers_to_a_vtype():
    program = lower_program(
        expand_piecewise(schema_of(DISPATCH_YAML, **{'variables.p.domain': 'binary', 'variables.p.bounds': {}}))
    )
    assert program.variable('p').variable_type == 'binary'


def test_a_divisor_under_a_pullback_is_still_named():
    """`children` has to descend through every node, or a refusal loses its name.

    `divisor_parameters` is what turns "a coefficient came out null" into a
    message naming the parameter the caller has to fix, and it finds those names
    by walking `children`. `At` was missing from that walk, so a quotient inside
    `at(...)` reported an uncovered divisor with an empty list where the name
    belongs — the refusal still fired, and stopped saying what to do about it.

    Asked of the walk directly rather than through a build: the walk is static,
    and a test that needed data to reach it would be testing the assembly.
    """
    quotient = Divide(Variable('x'), Parameter('rate'))
    pulled = At(quotient, over='flow', coordinate=('component',), into=('component',))

    assert divisor_parameters(pulled) == frozenset({'rate'})
    assert divisor_parameters(Sum(pulled, ('flow',))) == frozenset({'rate'})


def test_a_quotient_is_found_whole_so_its_two_halves_stay_paired():
    """`divisor_parameters` flattens, and one caller cannot use the flat answer.

    A divisor has to have values wherever the row is built *and the numerator
    exists*, so the eager lane narrows the mask by the variables in that
    quotient's own numerator — which needs the pair, not the union. Two
    quotients in one expression is the case a flattened set gets wrong.
    """
    left = Divide(Variable('x'), Parameter('rate'))
    right = Divide(Variable('y'), Parameter('loss'))

    found = quotients(Sum(left + right, ('flow',)))
    assert [(variables_of(q.numerator), q.divisor) for q in found] == [
        (frozenset({'x'}), Parameter('rate')),
        (frozenset({'y'}), Parameter('loss')),
    ], 'each quotient keeps its own numerator, in the order the expression writes them'
    assert divisor_parameters(Sum(left + right, ('flow',))) == frozenset({'rate', 'loss'}), (
        'the flat answer is still the union of the same walk'
    )


def test_a_lookup_names_the_dimension_its_values_label():
    """Five sites asked this and each walked for it; the plan answers it once.

    Both shapes are here because both had callers: one dimension's maps, for an
    operator that partitions along it, and every map in the program, for
    binding, which reads them all before it knows which are used.
    """
    program = Program(
        (),
        (),
        (),
        None,
        dimensions=(
            DimensionDeclaration('snapshot', (LookupDeclaration('season_of', 'season'),)),
            DimensionDeclaration('generator', (LookupDeclaration('at_bus', 'bus'),)),
        ),
    )

    assert program.dimension('snapshot').targets == {'season_of': 'season'}, (
        'one dimension names its own maps and no other dimension'
    )
    assert program.dimension('generator').targets == {'at_bus': 'bus'}, 'and the same for the second'
    assert program.dimension('nothing_declared').targets == {}, 'a dimension with no maps has none to name'
    assert [(d, lk.name) for d, lk in program.lookups] == [
        ('snapshot', 'season_of'),
        ('generator', 'at_bus'),
    ], 'every map with the dimension it is over, in declaration order'


def test_a_dimension_carries_the_dtype_its_labels_are_checked_against():
    """The declared type travels with the dimension, as a parameter's does.

    A dimension is read from whatever table carries it, so nothing downstream
    can infer what the column should have been — ``sources.py`` checks the
    labels against this and has no other way to know.
    """
    schema = schema_of(
        {
            'dimensions': {'t': {'dtype': 'int'}, 'g': {}},
            'parameters': {'c': {'dims': ['g']}},
            'variables': {'p': {'foreach': ['g'], 'bounds': {'lower': 0, 'upper': 1}}},
            'constraints': {'k': {'foreach': [], 'expression': 'sum(p, over=g) >= 1'}},
        }
    )
    program = lower_program(expand_piecewise(schema))

    assert program.dimension('t').dtype == 'int', 'a declared dtype reaches the plan'
    assert program.dimension('g').dtype == 'str', "and the schema's default does too, rather than nothing"
