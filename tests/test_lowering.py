# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The lowering pass: a resolved model in, a logical plan out.

The plan is read back node by node rather than through the answer it produces —
it is the contract consumers are written against.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import TYPE_CHECKING, get_args

import pytest

from math_spec import LanguageError, Spec, to_program
from math_spec._expression_parser import FunctionCallNode, NumberNode
from math_spec._where_parser import parse_where
from math_spec.exclusivity import overlapping
from math_spec.lowering import _Lowering, lower_program
from math_spec.piecewise import expand_piecewise
from math_spec.program import (
    QUADRATIC_POSITIONS,
    Add,
    AndNode,
    At,
    BooleanLiteralNode,
    Cases,
    Constant,
    DimensionComparisonNode,
    DimensionDeclaration,
    Divide,
    ExpressionNode,
    Footprint,
    GroupSum,
    LookupDeclaration,
    Mask,
    Multiply,
    Negate,
    NotNode,
    OrNode,
    Parameter,
    ParameterComparisonNode,
    ParameterDefinedNode,
    Power,
    Program,
    Region,
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
from math_spec.resolution import Namespace, expression_of, where_of
from tests.fixtures import DISPATCH_MODEL, EXAMPLES, SMALL_MODEL, override, schema_of

if TYPE_CHECKING:
    from math_spec._expression_parser import ArithmeticNode

DISPATCH_YAML = EXAMPLES / 'dispatch.yaml'

#: The mask `examples/dispatch.yaml` puts on `p`, as the plan carries it.
P_MAX_POSITIVE = ParameterComparisonNode('p_max', '>', 0.0, ('generator',))

#: One dimension, one parameter, one bounded variable and a scalar constraint:
#: the smallest model that loads, for a claim about the plan's record rather
#: than about the math in it. A test adds what it judges with :func:`override`.
TINY = {
    'dimensions': {'g': {}},
    'parameters': {'cost': {'dims': ['g']}},
    'variables': {'p': {'foreach': ['g'], 'bounds': {'lower': 0, 'upper': 1}}},
    'constraints': {'c': {'foreach': [], 'expression': 'sum(p, over=g) >= 1'}},
}

#: `fixtures.SMALL_MODEL` plus a second groupable lookup and a per-entity
#: offset. Which node a construct becomes is mostly a claim about the dim it
#: consumes and the dim it lands on, and stating that needs a third dimension
#: and two lookups over one of them.
SHAPES_MODEL = override(
    SMALL_MODEL,
    **{
        'dimensions.z': {'dtype': 'str'},
        'lookups.lk2': {'over': 'g', 'into': 'z'},
        'parameters.lead': {'dims': ['g'], 'dtype': 'int'},
    },
)


def resolved(text: str, schema: Spec) -> ArithmeticNode:
    """Parse, expand and resolve — exactly what the lowering pass receives.

    A raw ``parse_expression`` result still holds ``NameNode``s, and lowering
    asserts those never reach it. The ``'t'`` is the error-context label the
    resolver stamps on refusals, not a dimension.
    """
    return expression_of(text, schema, Namespace.of(schema), 't')


@pytest.fixture
def dispatch_schema() -> Spec:
    return schema_of(DISPATCH_YAML)


@pytest.fixture
def dispatch_program(dispatch_schema) -> Program:
    return lower_program(expand_piecewise(dispatch_schema))


@pytest.fixture
def shapes_schema() -> Spec:
    return schema_of(SHAPES_MODEL)


# ---------------------------------------------------------------------------
# the plan the language lowers to
# ---------------------------------------------------------------------------


def test_lower_program_structure(dispatch_program):
    assert list(dispatch_program.parameters) == ['p_max', 'load', 'cost'], 'keyed by name, in declaration order'
    ((vname, v),) = dispatch_program.variables.items()
    assert vname == 'p'
    assert v.dims == ('snapshot', 'generator'), 'the frame is the foreach, in the order the file wrote it'
    assert v.where == Mask(P_MAX_POSITIVE)
    assert v.upper == Parameter('p_max')

    ((cname, c),) = dispatch_program.constraints.items()
    assert cname == 'power_balance'
    assert c.dims == ('snapshot',), 'the frame is the foreach, in the order the file wrote it'
    assert c.lhs == Sum(Variable('p'), ('generator',))
    assert c.sense == '==', "the comparison crosses as the file's own operator, untranslated"
    assert c.rhs == Parameter('load')

    assert dispatch_program.objective.sense == 'minimize', "the program carries the language's spelling, untranslated"
    assert dispatch_program.objective.expression == Sum(Variable('p') * Parameter('cost'), ('generator', 'snapshot')), (
        'the objective carries the sum the file wrote, over the dims it named none of'
    )


@pytest.mark.parametrize('sense', [pytest.param('minimize', id='minimize'), pytest.param('maximize', id='maximize')])
def test_the_objective_sense_crosses_untranslated(sense: str):
    """One spelling from the file to the program, in both directions — each sink translates at its own edge."""
    program = to_program(override(TINY, objective={'sense': sense, 'expression': 'sum(p * cost, over=g)'}))
    assert program.objective is not None
    assert program.objective.sense == sense, "the file's own word for the direction, unchanged"


def test_a_file_with_no_objective_lowers_to_no_sense():
    """A feasibility problem has no direction, and nothing downstream invents one."""
    program = to_program(TINY)
    assert program.objective is None, 'no objective declared is no objective, not a minimisation of nothing'


def test_a_literal_amount_resolves_to_one_signed_number(dispatch_schema):
    """`offset=-1` parses as a unary minus over `1`; after resolution it is `-1`, for every reader alike."""
    ns = Namespace.of(dispatch_schema)
    node = expression_of('shift(p, over=snapshot, offset=-1, edge=+2)', dispatch_schema, ns, 't')
    assert isinstance(node, FunctionCallNode)
    assert (node.kwargs['offset'], node.kwargs['edge']) == (NumberNode(-1.0), NumberNode(2.0))


@pytest.mark.parametrize(
    ('where', 'expected'),
    [
        pytest.param(None, None, id='no-where-at-all'),
        pytest.param('True', None, id='True-is-no-mask'),
        pytest.param('p_max', ParameterDefinedNode('p_max', ('generator',)), id='a-bare-parameter-name'),
        pytest.param(
            'snapshot > 5',
            DimensionComparisonNode('snapshot', '>', 5),
            id='a-dimension-coordinate-compares-like-a-parameter',
        ),
        pytest.param(
            'p_max > 0 AND NOT load == 0',
            AndNode(P_MAX_POSITIVE, NotNode(ParameterComparisonNode('load', '==', 0.0, ('snapshot',)))),
            id='a-compound-where-keeps-its-connectives',
        ),
        pytest.param('False', BooleanLiteralNode(False), id='the-empty-declaration-keeps-its-own-spelling'),
        pytest.param('p_max > 0 AND True', P_MAX_POSITIVE, id='and-true-is-the-other-side'),
        pytest.param('p_max > 0 OR False', P_MAX_POSITIVE, id='or-false-is-the-other-side'),
        pytest.param('p_max > 0 OR True', None, id='or-true-is-no-mask-at-all'),
        pytest.param('p_max > 0 AND False', BooleanLiteralNode(False), id='and-false-is-the-empty-declaration'),
        pytest.param('NOT True', BooleanLiteralNode(False), id='not-true-is-false'),
        pytest.param('NOT False', None, id='not-false-is-no-mask'),
        pytest.param('NOT (p_max > 0 AND False)', None, id='a-branch-folded-away-folds-the-one-above-it'),
        pytest.param(
            'NOT (NOT p_max)',
            ParameterDefinedNode('p_max', ('generator',)),
            id='a-double-negation-cancels-on-the-load-path',
        ),
        pytest.param(
            '(p_max > 0 OR True) AND load',
            ParameterDefinedNode('load', ('snapshot',)),
            id='an-absorbed-side-takes-its-own-branch-with-it',
        ),
    ],
)
def test_a_where_is_one_resolved_predicate_with_every_literal_folded(dispatch_schema, where, expected):
    """One mask had two lowerings: `True` was dropped at the root and kept under a connective.

    A `BooleanLiteralNode` is a node a consumer meets at the root or nowhere.
    """
    mask = where_of(where, Namespace.of(dispatch_schema), 't')
    assert (mask.root if mask is not None else None) == expected, (
        'the Mask carries exactly the resolved predicate, folded at resolution however the file spelled it'
    )


def test_a_folded_mask_reaches_the_declaration_the_shorter_spelling_would_have():
    """The fold is the program's, not a helper's: two files, one declaration."""
    written_out = lower_program(
        expand_piecewise(schema_of(DISPATCH_MODEL, **{'variables.p.where': 'p_max > 0 AND True'}))
    )
    plain = lower_program(expand_piecewise(schema_of(DISPATCH_MODEL, **{'variables.p.where': 'p_max > 0'})))
    assert written_out.variable('p') == plain.variable('p'), 'the same mask, so the same declaration'


def test_an_unknown_where_name_is_an_error_at_lowering_too(dispatch_schema):
    """It used to be a scalar-False mask in the eager lane: a model that
    builds, solves, and is silently empty. Resolution makes it a load error."""
    with pytest.raises(LanguageError, match="'no_such_param' not found"):
        where_of('no_such_param', Namespace.of(dispatch_schema), 't')


def test_a_lowered_mask_cannot_be_rewritten_in_place(dispatch_program):
    """A consumer handed a program could invert the mask another one reads.

    The where nodes were plain dataclasses while every declaration embedding
    them was frozen, so `variable.where.root.op = '!='` rewrote `p_max > 0` into
    `p_max != 0` on the shared object — two consumers disagreeing about one
    file, which is the failure a program exists to prevent. It also left
    hashability depending on the file: an unmasked declaration hashed and a
    masked one raised TypeError.
    """
    (v,) = dispatch_program.variables.values()
    assert v.where == Mask(P_MAX_POSITIVE)

    with pytest.raises(FrozenInstanceError):
        v.where.root.op = '!='
    assert v.where == Mask(P_MAX_POSITIVE), 'the mask the file wrote, unchanged'
    assert isinstance(hash(v), int), 'a masked declaration hashes like an unmasked one'


def test_a_lowered_where_is_a_mask_that_answers_from_its_root(dispatch_program):
    """The `where` a lowering carries is a `Mask`, and its questions are its root's.

    A consumer asks the mask — `where.names_read`, `where.conjuncts` — the way it
    asks a dimension `dimension.maps`, rather than reaching for a free function
    with the raw node.
    """
    (v,) = dispatch_program.variables.values()

    assert v.where == Mask(P_MAX_POSITIVE)
    assert v.where.names_read == {'p_max'}, 'the declarations the mask names'
    assert v.where.conjuncts == (P_MAX_POSITIVE,), 'a mask that is not an AND is its own only conjunct'
    assert v.where.atoms == (P_MAX_POSITIVE,), 'a single leaf, connectives removed'


@pytest.mark.parametrize(
    ('variable', 'where', 'dims', 'conjuncts', 'atoms'),
    [
        pytest.param(
            'q',
            "lk == 'east' and position(h) == 0",
            {'g', 'h'},
            2,
            2,
            id='a-lookup-is-read-at-the-dim-it-maps-out-of-and-a-position-at-its-own',
        ),
        pytest.param('p', 'k > 0', set(), 1, 1, id='a-scalar-parameter-is-read-at-no-coordinate'),
        pytest.param(
            'p',
            'flag and (c > 0 or k > 0)',
            {'g'},
            2,
            3,
            id='atoms-cross-the-or-that-conjuncts-stop-at',
        ),
    ],
)
def test_a_lowered_mask_answers_its_dims_conjuncts_and_atoms(variable, where, dims, conjuncts, atoms):
    """`Mask.dims` is read off the leaves, which carry their declarations' dims;
    `atoms` crosses the `OR` that `conjuncts` stops at."""
    mask = to_program(override(SMALL_MODEL, **{f'variables.{variable}.where': where})).variables[variable].where

    assert mask.dims == frozenset(dims)
    assert len(mask.conjuncts) == conjuncts, 'an OR is one conjunct, a leaf is one conjunct'
    assert len(mask.atoms) == atoms, 'the leaves of every arm, connectives removed'


def test_a_synthetic_predicate_answers_its_own_dims():
    """A tree built from resolved pieces answers like a declaration's own mask.

    A consumer builds region complements and conjunctions — `NotNode(root)`,
    `AndNode(a, b)` — with no declaration behind them. Because the leaves carry
    their dims, wrapping any such tree in `Mask` answers without a name-to-dims
    mapping, which is what let the mapping die everywhere.
    """
    b = ParameterDefinedNode('load', ('snapshot',))

    assert Mask(NotNode(P_MAX_POSITIVE)).dims == {'generator'}, 'negation keeps the dims it negates'
    assert (Mask(P_MAX_POSITIVE) & Mask(b)).dims == {'generator', 'snapshot'}, 'conjunction unions both sides'
    assert (Mask(P_MAX_POSITIVE) & Mask(b)).root == AndNode(P_MAX_POSITIVE, b), (
        'the conjunction joins the roots under one AND'
    )


def test_mask_construction_folds_so_a_literal_stands_at_the_root_or_nowhere():
    """The fold lives in the constructor, so the invariant holds however a mask is built."""
    x = ParameterDefinedNode('committable', ('g',))
    empty, every = Mask(BooleanLiteralNode(False)), Mask(BooleanLiteralNode(True))

    assert Mask(OrNode(BooleanLiteralNode(True), x)) == every, 'a True side absorbs the OR at the door'
    assert Mask(AndNode(BooleanLiteralNode(False), x)) == empty, 'a False side dominates the AND at the door'
    assert Mask(NotNode(BooleanLiteralNode(True))) == empty, 'NOT over a literal flips at the door'
    assert Mask(NotNode(NotNode(x))) == Mask(x), 'a double negation cancels at the door'

    assert ~Mask(x) == Mask(NotNode(x)), 'a plain predicate negated gains one NOT'
    assert ~Mask(NotNode(x)) == Mask(x), '`not (not x)` cancels rather than stacking, so no consumer evaluates it twice'
    assert ~empty == every, 'the empty mask negated admits every row, with no NOT stacked'
    assert ~every == empty, 'and back again'
    assert empty & Mask(x) == empty, 'a False root dominates the conjunction'
    assert Mask(x) & empty == empty, 'from either side'
    assert every & Mask(x) == Mask(x), 'a True root is the other side'
    assert Mask(x) | empty == Mask(x), 'a False root is the other side of an OR'
    assert Mask(x) | every == every, 'a True root dominates the OR'


def test_a_held_leaf_walk_is_taken_after_the_fold_absorbed_a_branch():
    """`atoms` is held from construction, and construction folds first — so the fold's losses are not in it."""
    absorbed = Mask(AndNode(BooleanLiteralNode(False), ParameterDefinedNode('committable', ('g',))))

    assert absorbed.root == BooleanLiteralNode(False)
    assert absorbed.atoms == (), 'the absorbed leaf is not among them'
    assert absorbed.names_read == frozenset(), 'nor named'
    assert absorbed.dims == frozenset(), 'nor read at any dim'


def test_a_mask_over_an_unresolved_tree_is_refused_at_construction():
    """A tree whose leaves are unresolved is refused where it is wrapped, not where it is read."""
    with pytest.raises(AssertionError, match='reached a predicate walk unresolved'):
        Mask(parse_where('a AND b'))


def test_an_unwritten_where_lowers_to_none_not_an_empty_mask():
    lowered = to_program(DISPATCH_MODEL)
    (v,) = lowered.variables.values()
    (c,) = lowered.constraints.values()

    assert v.where is None, 'no `where:` in the file means no mask, not a mask over nothing'
    assert c.where is None, 'the constraint arm makes the same fold'


def test_a_constraint_where_is_a_mask_like_a_variable_s():
    lowered = to_program(override(DISPATCH_MODEL, **{'constraints.balance.where': 'load > 0'}))
    (c,) = lowered.constraints.values()

    assert c.where == Mask(ParameterComparisonNode('load', '>', 0.0, ('snapshot',)))


def test_a_power_lowers_to_a_node_of_its_own(dispatch_schema):
    lowered = _Lowering(dispatch_schema, 't').expr(resolved('cost ** cost', dispatch_schema))
    assert isinstance(lowered, Power), 'a variable-free power has a plan node of its own'


@pytest.mark.parametrize(
    ('expression', 'expected'),
    [
        pytest.param('sum(q)', Sum(Variable('q'), ('g', 'h')), id='a-bare-sum-consumes-every-dim-the-operand-carries'),
        pytest.param('sum(q, over=h)', Sum(Variable('q'), ('h',)), id='an-over-consumes-the-dim-it-names'),
        pytest.param(
            'sum(p, by=lk)',
            GroupSum(Variable('p'), over='g', coordinate=('lk',), into=('h',)),
            id='a-grouped-sum-names-the-dim-it-consumes-and-the-one-it-lands-on',
        ),
        pytest.param(
            'sum(p, by=[lk])',
            GroupSum(Variable('p'), over='g', coordinate=('lk',), into=('h',)),
            id='a-one-element-list-is-the-plain-form',
        ),
        pytest.param(
            'sum(p, by=[lk, lk2])',
            GroupSum(Variable('p'), over='g', coordinate=('lk', 'lk2'), into=('h', 'z')),
            id='two-coordinates-are-one-grouping-with-paired-tuples',
        ),
        pytest.param(
            'at(r, by=lk)',
            At(Variable('r'), over='g', coordinate=('lk',), into=('h',)),
            id='a-pullback-walks-the-same-table-back',
        ),
        pytest.param(
            "shift(p, over=g, offset=1, edge='wrap')",
            Translate(Variable('p'), 'g', offset=1, wrap=True, fill=None),
            id='a-wrapping-translation-fills-nothing',
        ),
        pytest.param(
            'shift(p, over=g, offset=-2, edge=0)',
            Translate(Variable('p'), 'g', offset=-2, wrap=False, fill=0.0),
            id='a-lead-is-a-negative-offset-and-the-edge-is-what-it-fills-with',
        ),
        pytest.param(
            'shift(p, over=g, offset=lead, edge=0)',
            Translate(Variable('p'), 'g', offset='lead', wrap=False, fill=0.0),
            id='a-named-offset-crosses-as-the-parameter-name',
        ),
        pytest.param(
            'shift(p, over=g, offset=1, by=lk, edge=0)',
            Translate(Variable('p'), 'g', offset=1, wrap=False, fill=0.0, partition='lk'),
            id='a-translation-stops-at-the-edges-of-the-lookup-it-names',
        ),
        pytest.param(
            'sum_back(p, over=g, within=3)',
            Window(Variable('p'), 'g', width=3, wrap=False),
            id='a-window-is-one-node-rather-than-a-fold-of-translations',
        ),
        pytest.param(
            'sum_back(p, over=g, within=k)',
            Window(Variable('p'), 'g', width='k', wrap=False),
            id='a-named-width-crosses-as-the-parameter-name',
        ),
        pytest.param(
            'sum_back(p, over=g, within=2, by=lk)',
            Window(Variable('p'), 'g', width=2, wrap=False, partition='lk'),
            id='a-window-stops-at-the-edges-of-the-lookup-it-names',
        ),
    ],
)
def test_a_construct_lowers_to_its_node(shapes_schema, expression, expected):
    """Which node each surface construct becomes, and every field it arrives with."""
    lowered = _Lowering(shapes_schema, 't').expr(resolved(expression, shapes_schema))
    assert lowered == expected, 'the whole frozen node, so no field is asserted by omission'


def test_a_binary_variable_lowers_to_a_vtype():
    program = to_program(schema_of(DISPATCH_YAML, **{'variables.p.domain': 'binary', 'variables.p.bounds': {}}))
    assert program.variable('p').variable_type == 'binary'


def test_a_divisor_under_a_pullback_is_still_named():
    """`children` has to descend through every node, or a refusal loses its name."""
    quotient = Divide(Variable('x'), Parameter('rate'))
    pulled = At(quotient, over='flow', coordinate=('component',), into=('component',))

    assert divisor_parameters(pulled) == frozenset({'rate'}), 'the walk descends through `At`'
    assert divisor_parameters(Sum(pulled, ('flow',))) == frozenset({'rate'}), 'and through a `Sum` over it'


def test_a_quotient_is_found_whole_so_its_two_halves_stay_paired():
    """`divisor_parameters` flattens, and one caller cannot use the flat answer."""
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
    Cases((Region(Mask(ParameterDefinedNode('c', ('g',))), Variable('p')),)): 'one-to-one',
}


def test_every_expression_node_is_classified_by_fan_in():
    """`fan_in` was a ClassVar on five nodes, so `Add(...).fan_in` was an AttributeError."""
    covered = {type(node) for node in FAN_IN}
    assert covered == set(get_args(ExpressionNode)), (
        'every node in the ExpressionNode union is classified, and nothing retired lingers'
    )


@pytest.mark.parametrize(('node', 'expected'), FAN_IN.items(), ids=[type(node).__name__ for node in FAN_IN])
def test_a_node_answers_its_fan_in(node, expected):
    assert fan_in(node) == expected


def test_a_lookup_names_the_dimension_its_values_label():
    """Five sites asked this and each walked for it; the plan answers it once."""
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


def test_a_label_space_keeps_its_dtype_and_has_no_target():
    """The file's claim about a label-space column used to be dropped at lowering."""
    program = to_program(
        {
            'dimensions': {'snapshot': {'dtype': 'int'}, 'season': {}},
            'lookups': {
                'season_of': {'over': 'snapshot', 'into': 'season'},
                'period': {'over': 'snapshot', 'dtype': 'int'},
            },
            'variables': {'p': {'foreach': ['snapshot'], 'where': 'period == 1'}},
            'constraints': {'k': {'foreach': ['season'], 'expression': 'sum(p, by=season_of) >= 1'}},
        }
    )

    assert program.dimension('snapshot').lookups == (
        LookupDeclaration('season_of', 'season', None),
        LookupDeclaration('period', None, 'int'),
    ), 'both kinds, in declaration order: a targeted lookup carries its target, a label space its dtype'
    assert program.dimension('snapshot').maps == ['period', 'season_of'], 'binding reads both kinds'
    assert program.dimension('snapshot').targets == {'season_of': 'season'}, 'grouping reads only the targeted one'


def test_an_unknown_dimension_is_a_near_miss_rather_than_an_empty_declaration():
    """A typo used to return an empty declaration, silently dropping every join."""
    program = to_program(override(TINY, **{'dimensions.snapshot': {}}))

    assert program.dimension('snapshot').dtype == 'str', 'a declared dimension still comes back'
    with pytest.raises(KeyError, match='snapshto') as excinfo:
        program.dimension('snapshto')
    assert 'snapshot' in str(excinfo.value), 'the message names the near miss, which is the whole point of raising'


def test_a_program_is_built_by_keyword_so_a_field_added_later_cannot_reorder_an_old_call():
    """Positional construction made every field's *position* part of the contract."""
    with pytest.raises(TypeError, match='positional'):
        Program({}, {}, {}, None)  # pyrefly: ignore[bad-argument-count]  the point of the test


@pytest.mark.parametrize('group', ['parameters', 'variables', 'constraints', 'dimensions', 'sos'])
def test_a_program_seals_its_declaration_groups(dispatch_program, group):
    """`frozen=True` sealed the fields and said nothing about what was behind them."""
    with pytest.raises(TypeError):
        getattr(dispatch_program, group)['sneak'] = None  # pyrefly: ignore[unsupported-operation]  the point of the test


def test_expressions_are_the_ones_a_row_is_built_from():
    """`expressions` named the *declared* ones, which build no row at all."""
    program = to_program(
        override(
            TINY,
            expressions={'spend': 'sum(cost, over=g)'},
            objective={'sense': 'minimize', 'expression': 'sum(p * cost, over=g)'},
        )
    )

    assert list(program.named_expressions) == ['spend'], 'the declared ones keep their own name'
    assert program.expressions == (
        program.objective.expression,
        program.constraints['c'].lhs,
        program.constraints['c'].rhs,
    ), 'the objective first, then both sides of each constraint, in declaration order'
    assert program.named_expressions['spend'] not in program.expressions, (
        'a named expression builds no row, so it is not one of the expressions a row is built from'
    )
    assert len(program.expressions) == 3, 'and nothing else is counted'


def _footprint_of(constraint: str, objective: str) -> Footprint:
    return to_program(
        override(
            TINY,
            constraints={'k': {'foreach': ['g'], 'expression': constraint}},
            objective={'sense': 'minimize', 'expression': objective},
        )
    ).footprint


def test_the_footprint_says_which_position_a_quadratic_stands_in():
    """A sink may take a quadratic objective and refuse a quadratic constraint.

    One flag for both would collapse the distinction `ceiling.md` says sinks
    actually make — quadratic is bounded "by convexity and again by what it
    stands beside" — and leave the sink walking the program to recover it.
    """
    assert _footprint_of('p <= 1', 'sum(p * p, over=g)').quadratic == {'objective'}, 'a quadratic objective alone'
    assert _footprint_of('p * p <= 1', 'sum(p, over=g)').quadratic == {'constraint'}, 'a quadratic constraint alone'
    assert _footprint_of('p * p <= 1', 'sum(p * p, over=g)').quadratic == {'objective', 'constraint'}, (
        'both positions, each named'
    )
    assert _footprint_of('p <= 1', 'sum(p, over=g)').quadratic == frozenset(), 'affine throughout is the empty set'


def test_a_construct_the_file_does_not_use_is_an_empty_set_rather_than_none():
    """Absence is the empty collection, so `if footprint.sos_types` is the whole test.

    None would make three states out of two and put a null check in front of
    every read.
    """
    footprint = _footprint_of('p <= 1', 'sum(p, over=g)')

    assert footprint.sos_types == frozenset(), 'a file declaring no sos'
    assert footprint.quadratic == frozenset(), 'a file with no quadratic anywhere'
    assert footprint.variable_types == {'continuous'}, 'never empty — a program has variables'
    assert {type(f) for f in (footprint.sos_types, footprint.quadratic, footprint.shapes)} == {frozenset}, (
        'every field is a set, so one rule reads all of them'
    )
    assert footprint.quadratic <= QUADRATIC_POSITIONS, 'and the vocabulary a consumer pins its table against'
    assert {'objective', 'constraint'} == QUADRATIC_POSITIONS, (
        'a position admitted later widens this, which is what a consumer pins against to hear about it'
    )


def test_the_footprint_is_walked_once_and_held(dispatch_program):
    """Safe to hold only because the program cannot change under it."""
    assert dispatch_program.footprint is dispatch_program.footprint


def test_a_named_expression_is_not_in_the_footprint():
    """It builds no row, so counting it would answer wrongly about what is solved."""
    program = to_program(override(TINY, expressions={'spend': 'sum(p * cost, over=g)'}))

    assert Parameter not in program.footprint.shapes, "the named expression's parameter reaches no row"
    assert Parameter in {type(n) for n in walk(program.named_expressions['spend'])}, 'though it is in the expression'


def test_a_dimension_carries_the_dtype_its_labels_are_checked_against():
    """The declared type travels with the dimension, as a parameter's does.

    A dimension is read from whatever table carries it, so nothing downstream
    can infer what the column should have been.
    """
    program = to_program(override(TINY, **{'dimensions.t': {'dtype': 'int'}}))

    assert program.dimension('t').dtype == 'int', 'a declared dtype reaches the plan'
    assert program.dimension('g').dtype == 'str', "and the schema's default does too, rather than nothing"


CASED = {
    'dimensions': {'t': {'dtype': 'int'}, 'g': {'dtype': 'str'}},
    'parameters': {'committable': {'dims': ['g'], 'dtype': 'bool'}, 'initial': {'dims': ['g']}},
    'variables': {'status': {'foreach': ['t', 'g'], 'domain': 'binary'}},
    'expressions': {
        'previous': {
            'foreach': ['t', 'g'],
            'cases': {
                'always_on': {'when': 'not committable', 'expression': 1},
                'boundary': {'when': 'committable and position(t) == 0', 'expression': 'initial'},
            },
            'otherwise': 'shift(status, over=t, offset=1)',
        }
    },
    'constraints': {'no_restart': {'foreach': ['t', 'g'], 'expression': 'status - previous <= 1'}},
}


def _cases_in(program: Program) -> Cases:
    """The one cased node the fixture's constraint carries."""
    sides = [side for c in program.constraints.values() for side in (c.lhs, c.rhs)]
    found = [n for n in walk(*sides) if isinstance(n, Cases)]
    assert len(found) == 1, 'the fixture has exactly one cased expression, inlined where it is named'
    return found[0]


def test_a_cased_expression_lowers_to_one_region_per_case():
    """The regions come out in file order, values lowered like any other expression."""
    cases = _cases_in(to_program(CASED))

    assert len(cases.regions) == 3, 'one region per case, the `otherwise` among them'
    assert [type(r.value).__name__ for r in cases.regions] == ['Constant', 'Parameter', 'Translate'], (
        'each region carries its own value, lowered — a number, a parameter and a shift'
    )


def test_the_fallback_region_carries_the_mask_the_file_left_unwritten():
    """`otherwise:` writes no `when:`; it arrives with the negation of the rest.

    A consumer adds regions rather than working out which one is left over, so
    the remainder is resolved once here instead of once per consumer.
    """
    remainder = _cases_in(to_program(CASED)).regions[-1]

    assert isinstance(remainder.when.root, AndNode), (
        'two stated cases, so the remainder is a conjunction of two negations'
    )
    assert remainder.when.root.left == ParameterDefinedNode('committable', ('g',)), (
        'the negation of `not committable` is the term itself, not a second `not` around it'
    )


def test_a_region_s_when_is_a_mask_with_its_own_dims():
    """`Region.when` arrives in the same carrier as a declaration's `where`.

    It was the one mask left as a bare node, so a helper written over `Mask`
    branched on where a mask came from — the divergence the carrier exists to
    prevent. The synthesized remainder gets its dims like any stated case.
    """
    always_on, boundary, remainder = _cases_in(to_program(CASED)).regions

    assert all(isinstance(r.when, Mask) for r in (always_on, boundary, remainder)), (
        'every region, the synthesized remainder included, carries its predicate as a Mask'
    )
    assert always_on.when.dims == frozenset({'g'}), "`not committable` reads the parameter's dims"
    assert boundary.when.dims == frozenset({'g', 't'}), 'the position comparison adds its dimension'
    assert remainder.when.dims == frozenset({'g', 't'}), 'the remainder reads every dim the stated cases do'


def test_the_lowered_regions_are_still_proved_apart():
    """The remainder does not collide with the cases it was built from.

    The language proves the *stated* masks apart before lowering runs. This is
    the other half: the mask lowering invents for `otherwise` is put through the
    same prover, against each stated case, and must overlap none of them.
    """
    spec = schema_of(CASED)
    regions = _cases_in(to_program(spec)).regions
    named = {f'region{i}': r.when.root for i, r in enumerate(regions)}

    assert list(overlapping(named, Namespace.of(spec).dtypes)) == [], 'no two lowered regions can claim one coordinate'


def test_a_cased_expression_is_readable_by_the_name_the_file_wrote():
    """`Program.expressions` carries it, so a consumer reads it back whole."""
    program = to_program(CASED)

    assert isinstance(program.named_expressions['previous'], Cases), (
        'a cased expression reaches the program as the node, not as its fallback arm alone'
    )
