# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The program boundary: a malformed `Program` is refused before a consumer sees it.

`to_program` builds one from a validated spec, so a lowered program passes
every case here by construction — the language refuses each of these shapes at
load. What this guards is a program assembled by hand, which reaches a
consumer with none of those checks behind it and would otherwise fail partway
through a build, in whatever error that consumer happened to hit first.

Each case is one invariant and the sentence it fails with.
"""

from __future__ import annotations

import pytest

import math_spec.program as program
from math_spec import LanguageError
from math_spec.where_parser import ParameterComparisonNode, ParameterDefinedNode

DIMENSIONS = (
    program.DimensionDeclaration('g', (program.LookupDeclaration('zone_of', 'zone'),)),
    program.DimensionDeclaration('zone'),
    program.DimensionDeclaration('t'),
)
PARAMETERS = (
    program.ParameterDeclaration('cost', ('g',)),
    program.ParameterDeclaration('load', ('zone',)),
    program.ParameterDeclaration('lead', ('t',)),
    program.ParameterDeclaration('width', ('g',)),
)
VARIABLES = (
    program.VariableDeclaration('x', ('g',)),
    program.VariableDeclaration('u', ('t', 'g')),
)


def constrained(lhs: program.Expression, dims: tuple[str, ...] = ()) -> program.Program:
    """A program whose one constraint carries *lhs* — the flaw under test rides in the expression."""
    constraint = program.ConstraintDeclaration('c', dims, lhs=lhs, sense='<=', rhs=program.Constant(0.0))
    return program.Program(PARAMETERS, VARIABLES, (constraint,), None, DIMENSIONS)


def x() -> program.Expression:
    return program.Variable('x')


@pytest.mark.parametrize(
    ('program', 'match'),
    [
        pytest.param(
            constrained(program.Variable('y'), ('g',)),
            "unknown variable 'y'",
            id='a-variable-nothing-declares',
        ),
        pytest.param(
            constrained(program.Multiply(x(), program.Parameter('price')), ('g',)),
            "unknown parameter 'price'",
            id='a-parameter-nothing-declares',
        ),
        pytest.param(
            program.Program((program.ParameterDeclaration('x', ('g',)), *PARAMETERS), VARIABLES, (), None, DIMENSIONS),
            "'x' is declared twice",
            id='one-name-two-declarations',
        ),
        pytest.param(
            constrained(program.Sum(x(), over=('t',))),
            "sum over \\['t'\\], which the operand does not span",
            id='a-sum-over-a-dim-the-operand-lacks',
        ),
        pytest.param(
            constrained(program.GroupSum(x(), over='g', coordinate=('zone_of', 'other'), into=('zone',)), ('zone',)),
            r'2 lookup\(s\) paired with 1 target dimension\(s\)',
            id='a-grouping-whose-tuples-do-not-pair',
        ),
        pytest.param(
            constrained(program.GroupSum(x(), over='g', coordinate=('zone_of',), into=('t',)), ('t',)),
            "lookup 'zone_of' targets 'zone', not 't'",
            id='a-grouping-into-a-dim-that-is-not-the-target',
        ),
        pytest.param(
            constrained(program.GroupSum(program.Parameter('load'), over='g', coordinate=('zone_of',), into=('zone',))),
            "sum\\(by=\\) over 'g', which the operand does not span",
            id='a-grouping-over-a-dim-the-operand-lacks',
        ),
        pytest.param(
            constrained(program.At(x(), over='g', coordinate=('zone_of',), into=('zone',)), ('g',)),
            "at\\(\\) through \\['zone'\\], which the operand does not span",
            id='a-pullback-through-a-dim-the-operand-lacks',
        ),
        pytest.param(
            constrained(program.Translate(x(), 't', offset=1, wrap=True), ('g',)),
            "shift\\(\\) along 't', which the operand does not span",
            id='a-translation-along-a-dim-the-operand-lacks',
        ),
        pytest.param(
            constrained(program.Translate(program.Variable('u'), 't', offset='lead', wrap=True), ('t', 'g')),
            "shift\\(\\) distance 'lead' varies along 't'",
            id='an-offset-that-varies-along-the-walked-dim',
        ),
        pytest.param(
            constrained(program.Window(program.Variable('u'), 't', width='lead', wrap=False), ('t', 'g')),
            "sum_back\\(\\) distance 'lead' varies along 't'",
            id='a-width-that-varies-along-the-walked-dim',
        ),
        pytest.param(
            constrained(program.Multiply(program.Multiply(x(), x()), x()), ('g',)),
            'a product of degree 3',
            id='a-cubic-product',
        ),
        pytest.param(
            constrained(program.Divide(x(), x()), ('g',)),
            'the divisor contains variables',
            id='a-divisor-carrying-a-variable',
        ),
        pytest.param(
            constrained(program.Power(x(), program.Constant(2.0)), ('g',)),
            'a power over variables',
            id='a-power-over-a-variable',
        ),
        pytest.param(
            program.Program(
                PARAMETERS,
                (program.VariableDeclaration('x', ('g',), lower=program.Variable('x')),),
                (),
                None,
                DIMENSIONS,
            ),
            'unsupported node Variable',
            id='a-bound-carrying-a-variable',
        ),
        pytest.param(
            program.Program(
                PARAMETERS,
                (program.VariableDeclaration('x', ('g',), upper=program.Parameter('nope')),),
                (),
                None,
                DIMENSIONS,
            ),
            "bounds of variable 'x'.*unknown parameter 'nope'",
            id='a-bound-naming-no-parameter',
        ),
        pytest.param(
            program.Program(
                PARAMETERS,
                (program.VariableDeclaration('x', ('g',), where=ParameterComparisonNode('nope', '>', 0)),),
                (),
                None,
                DIMENSIONS,
            ),
            "variable 'x'.*unknown parameter 'nope'",
            id='a-mask-naming-no-parameter',
        ),
        pytest.param(
            program.Program(
                PARAMETERS,
                VARIABLES,
                (),
                program.ObjectiveDeclaration('minimize', program.Sum(program.Variable('y'), over=('g',))),
                DIMENSIONS,
            ),
            "the objective.*unknown variable 'y'",
            id='an-objective-naming-no-variable',
        ),
        pytest.param(
            program.Program(
                PARAMETERS,
                VARIABLES,
                (),
                None,
                DIMENSIONS,
                (program.SosDeclaration('s', 'x', 't', sos_type=1),),
            ),
            "over 't', which variable 'x' is not indexed by",
            id='a-set-over-a-dim-its-variable-lacks',
        ),
        pytest.param(
            program.Program(PARAMETERS, VARIABLES, (), None, DIMENSIONS, (), {'reach': program.Parameter('gone')}),
            "named expression 'reach'.*unknown parameter 'gone'",
            id='a-named-expression-naming-no-parameter',
        ),
        pytest.param(
            program.Program(
                PARAMETERS,
                VARIABLES,
                (),
                program.ObjectiveDeclaration(
                    'minimize', program.Add(program.Sum(x(), over=('g',)), program.Parameter('load'))
                ),
                DIMENSIONS,
            ),
            r"a constant part has dims \['zone'\]",
            id='an-objective-whose-constant-part-is-a-table',
        ),
        pytest.param(
            constrained(program.Parameter('load'), ('g',)),
            r"expression has dims \['zone'\] outside foreach \['g'\] — missing a Sum/GroupSum\?",
            id='a-side-spanning-more-than-the-foreach',
        ),
        pytest.param(
            program.Program(
                PARAMETERS,
                (program.VariableDeclaration('x', ('g',), upper=program.Parameter('load')),),
                (),
                None,
                DIMENSIONS,
            ),
            r"bound parameter 'load' of variable 'x' has dims \['zone'\] outside the foreach dims \['g'\]",
            id='a-bound-wider-than-the-variable',
        ),
        pytest.param(
            program.Program(
                PARAMETERS,
                (program.VariableDeclaration('x', ('g',), where=ParameterDefinedNode('load')),),
                (),
                None,
                DIMENSIONS,
            ),
            r"where reads 'load', which has dims \['zone'\] outside the foreach dims \['g'\]",
            id='a-mask-wider-than-what-it-masks',
        ),
    ],
)
def test_a_malformed_program_is_refused_in_plan_vocabulary(program: program.Program, match: str):
    with pytest.raises(LanguageError, match=match):
        program.check()


def test_a_coherent_program_passes():
    """Every construct the checks read, in one valid program — the boundary admits it whole."""
    balance = program.ConstraintDeclaration(
        'balance',
        ('zone',),
        lhs=program.GroupSum(program.Multiply(x(), program.Parameter('cost')), 'g', ('zone_of',), ('zone',)),
        sense='<=',
        rhs=program.Parameter('load'),
        where=ParameterDefinedNode('load'),
    )
    ramp = program.ConstraintDeclaration(
        'ramp',
        ('t', 'g'),
        lhs=program.Add(
            program.Variable('u'),
            program.Negate(program.Translate(program.Variable('u'), 't', offset='width', wrap=True)),
        ),
        sense='<=',
        rhs=program.Window(program.Variable('u'), 't', width=2, wrap=False),
    )
    coherent = program.Program(
        PARAMETERS,
        VARIABLES,
        (balance, ramp),
        program.ObjectiveDeclaration('minimize', program.Sum(program.Multiply(x(), x()), over=('g',))),
        DIMENSIONS,
        (program.SosDeclaration('s', 'x', 'g', sos_type=2),),
    )
    assert coherent.check() is None, 'a coherent program is admitted without complaint'
