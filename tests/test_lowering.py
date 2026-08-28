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
from typing import TYPE_CHECKING, get_args

import pytest

from math_spec import LanguageError, Spec
from math_spec.lowering import _lower_where, _Lowering, lower_program
from math_spec.piecewise import expand_piecewise
from math_spec.program import (
    QUADRATIC_POSITIONS,
    Add,
    At,
    Constant,
    DimensionDeclaration,
    Divide,
    ExpressionNode,
    Footprint,
    GroupSum,
    LookupDeclaration,
    Multiply,
    Negate,
    Parameter,
    Power,
    Program,
    Sum,
    Translate,
    Variable,
    Window,
    divisor_parameters,
    fan_in,
    quotients,
    variables_of,
    walk,
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

    assert list(program.parameters) == ['p_max', 'load', 'cost'], 'keyed by name, in declaration order'
    ((vname, v),) = program.variables.items()
    assert vname == 'p'
    assert v.dims == ('snapshot', 'generator')
    assert v.where == ParameterComparisonNode('p_max', '>', 0.0)
    assert v.upper == Parameter('p_max')

    ((cname, c),) = program.constraints.items()
    assert cname == 'power_balance'
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
    (v,) = program.variables.values()
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


FAN_IN = {
    Constant(1.0): 'one-to-one',
    Parameter('c'): 'one-to-one',
    Variable('p'): 'one-to-one',
    Negate(Variable('p')): 'one-to-one',
    Add(Variable('p'), Constant(1.0)): 'one-to-one',
    Multiply(Variable('p'), Parameter('c')): 'one-to-one',
    Power(Parameter('c'), Constant(2.0)): 'one-to-one',
    Divide(Variable('p'), Parameter('c')): 'one-to-one',
    Sum(Variable('p'), ('g',)): 'many-to-one',
    GroupSum(Variable('p'), over='g', coordinate=('at_bus',), into=('bus',)): 'many-to-one',
    At(Variable('p'), over='g', coordinate=('at_bus',), into=('bus',)): 'one-to-one',
    Translate(Variable('p'), 't', offset=1, wrap=False, fill=0.0): 'one-to-one',
    Window(Variable('p'), 't', width=2, wrap=False): 'one-to-many',
}


def test_every_expression_node_answers_fan_in():
    """`fan_in` was a ClassVar on five nodes, so `Add(...).fan_in` was an AttributeError.

    A consumer had to keep its own list of which node kinds carry the answer,
    which is the list the declaration existed to spare it. The table below is
    checked for completeness against `ExpressionNode` so a node added later
    fails here rather than reaching a consumer unclassified.
    """
    covered = {type(node) for node in FAN_IN}
    assert covered == set(get_args(ExpressionNode)), (
        'every node in the ExpressionNode union is classified, and nothing retired lingers'
    )
    assert {type(node).__name__: fan_in(node) for node in FAN_IN} == {
        type(node).__name__: expected for node, expected in FAN_IN.items()
    }


def test_a_lookup_names_the_dimension_its_values_label():
    """Five sites asked this and each walked for it; the plan answers it once.

    Both shapes are here because both had callers: one dimension's maps, for an
    operator that partitions along it, and every map in the program, for
    binding, which reads them all before it knows which are used.
    """
    program = Program(
        parameters={},
        variables={},
        constraints={},
        objective=None,
        dimensions={
            'snapshot': DimensionDeclaration((LookupDeclaration('season_of', 'season'),)),
            'generator': DimensionDeclaration((LookupDeclaration('at_bus', 'bus'),)),
        },
    )

    assert program.dimension('snapshot').targets == {'season_of': 'season'}, (
        'one dimension names its own maps and no other dimension'
    )
    assert program.dimension('generator').targets == {'at_bus': 'bus'}, 'and the same for the second'
    assert [(d, lk.name) for d, lk in program.lookups] == [
        ('snapshot', 'season_of'),
        ('generator', 'at_bus'),
    ], 'every map with the dimension it is over, in declaration order'


def test_an_unknown_dimension_is_a_near_miss_rather_than_an_empty_declaration():
    """A typo used to return an empty declaration, silently dropping every join.

    `dimension()` answered an unknown name with `DimensionDeclaration(name)` —
    no lookups, no label spaces — while its siblings `parameter()` and
    `variable()` raised. So a consumer misspelling a dimension read a
    declaration that mapped nowhere and placed no terms, rather than being
    told. Every dimension a valid model can name is declared: `Spec`'s
    reference check refuses an undeclared one in `dims:`, `foreach:`, a
    lookup's `over:`/`into:` and an sos's `over:`, so the fallback was
    reachable only by a mistake.
    """
    program = lower_program(
        expand_piecewise(
            schema_of(
                {
                    'dimensions': {'snapshot': {}, 'generator': {}},
                    'variables': {'p': {'foreach': ['generator'], 'bounds': {'lower': 0, 'upper': 1}}},
                    'constraints': {'k': {'foreach': [], 'expression': 'sum(p, over=generator) >= 1'}},
                }
            )
        )
    )

    assert program.dimension('snapshot').dtype == 'str', 'a declared dimension still comes back'
    with pytest.raises(KeyError, match='snapshto') as excinfo:
        program.dimension('snapshto')
    assert 'snapshot' in str(excinfo.value), 'the message names the near miss, which is the whole point of raising'


def test_a_program_is_built_by_keyword_so_a_field_added_later_cannot_reorder_an_old_call():
    """Positional construction made every field's *position* part of the contract.

    `Program(parameters, variables, constraints, objective, dimensions, sos,
    expressions)` is seven positional slots on a record consumers read; a field
    inserted anywhere but the end silently rebound the ones after it, with no
    type error where the arguments happen to share a shape.
    """
    with pytest.raises(TypeError, match='positional'):
        Program({}, {}, {}, None)  # pyrefly: ignore[bad-argument-count]  the point of the test


def test_a_program_seals_its_declaration_groups(dispatch_schema):
    """`frozen=True` sealed the fields and said nothing about what was behind them.

    `Program.expressions` was a plain dict, so a consumer could add or replace
    a declaration on the program another consumer was reading — the same
    two-consumers-disagree failure a mutable where node allowed. Every group is
    keyed now, so the seal has to hold for all of them rather than the one.
    """
    program = lower_program(expand_piecewise(dispatch_schema))

    for group in (program.parameters, program.variables, program.constraints, program.dimensions, program.sos):
        with pytest.raises(TypeError):
            group['sneak'] = None  # pyrefly: ignore[unsupported-operation]  the point of the test
    assert list(program.parameters) == ['p_max', 'load', 'cost'], "and the file's own order survives the seal"


def test_expressions_are_the_ones_a_row_is_built_from():
    """`expressions` named the *declared* ones, which build no row at all.

    Two readers walk the objective and both constraint sides — `advice` and
    anything asking what a solver must support — and each wrote that list out.
    A named expression counted among them would answer wrongly about what is
    solved, which is why the declared ones are `named_expressions` now.
    """
    program = lower_program(
        expand_piecewise(
            schema_of(
                {
                    'dimensions': {'g': {}},
                    'parameters': {'cost': {'dims': ['g']}},
                    'variables': {'p': {'foreach': ['g'], 'bounds': {'lower': 0, 'upper': 1}}},
                    'constraints': {'k': {'foreach': [], 'expression': 'sum(p, over=g) >= 1'}},
                    'expressions': {'spend': 'sum(cost, over=g)'},
                    'objective': {'sense': 'minimize', 'expression': 'sum(p * cost, over=g)'},
                }
            )
        )
    )

    assert list(program.named_expressions) == ['spend'], 'the declared ones keep their own name'
    assert program.expressions == (
        program.objective.expression,
        program.constraints['k'].lhs,
        program.constraints['k'].rhs,
    ), 'the objective first, then both sides of each constraint, in declaration order'
    assert program.named_expressions['spend'] not in program.expressions, (
        'a named expression builds no row, so it is not one of the expressions a row is built from'
    )
    assert len(program.expressions) == 3, 'and nothing else is counted'


def _footprint_of(constraint: str, objective: str) -> Footprint:
    return lower_program(
        expand_piecewise(
            schema_of(
                {
                    'dimensions': {'g': {}},
                    'variables': {'p': {'foreach': ['g'], 'bounds': {'lower': 0, 'upper': 1}}},
                    'constraints': {'k': {'foreach': ['g'], 'expression': constraint}},
                    'objective': {'sense': 'minimize', 'expression': objective},
                }
            )
        )
    ).footprint


def test_the_footprint_says_which_position_a_quadratic_stands_in():
    """A sink may take a quadratic objective and refuse a quadratic constraint.

    One flag for both would collapse the distinction `ceiling.md` says sinks
    actually make — quadratic is bounded "by convexity and again by what it
    stands beside" — and leave the sink walking the program to recover it.
    """
    assert _footprint_of('p <= 1', 'sum(p * p, over=g)').quadratic == {'objective'}
    assert _footprint_of('p * p <= 1', 'sum(p, over=g)').quadratic == {'constraint'}
    assert _footprint_of('p * p <= 1', 'sum(p * p, over=g)').quadratic == {'objective', 'constraint'}
    assert _footprint_of('p <= 1', 'sum(p, over=g)').quadratic == frozenset(), 'affine throughout is the empty set'


def test_a_construct_the_file_does_not_use_is_an_empty_set_rather_than_none():
    """Absence is the empty collection, so `if footprint.sos_types` is the whole test.

    None would make three states out of two and put a null check in front of
    every read.
    """
    footprint = _footprint_of('p <= 1', 'sum(p, over=g)')

    assert footprint.sos_types == frozenset(), 'a file declaring no sos'
    assert footprint.quadratic == frozenset()
    assert footprint.variable_types == {'continuous'}, 'never empty — a program has variables'
    assert {type(f) for f in (footprint.sos_types, footprint.quadratic, footprint.shapes)} == {frozenset}, (
        'every field is a set, so one rule reads all of them'
    )
    assert footprint.quadratic <= QUADRATIC_POSITIONS, 'and the vocabulary a consumer pins its table against'
    assert {'objective', 'constraint'} == QUADRATIC_POSITIONS, (
        'a position admitted later widens this, which is what a consumer pins against to hear about it'
    )


def test_the_footprint_is_walked_once_and_held(dispatch_schema):
    """Safe to hold only because the program cannot change under it."""
    program = lower_program(expand_piecewise(dispatch_schema))
    assert program.footprint is program.footprint


def test_a_named_expression_is_not_in_the_footprint():
    """It builds no row, so counting it would answer wrongly about what is solved."""
    program = lower_program(
        expand_piecewise(
            schema_of(
                {
                    'dimensions': {'g': {}},
                    'parameters': {'cost': {'dims': ['g']}},
                    'variables': {'p': {'foreach': ['g'], 'bounds': {'lower': 0, 'upper': 1}}},
                    'constraints': {'k': {'foreach': [], 'expression': 'sum(p, over=g) >= 1'}},
                    'expressions': {'spend': 'sum(p * cost, over=g)'},
                }
            )
        )
    )

    assert Parameter not in program.footprint.shapes, "the named expression's parameter reaches no row"
    assert Parameter in {type(n) for n in walk(program.named_expressions['spend'])}, 'though it is in the expression'


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
