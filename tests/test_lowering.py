# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The lowering pass: a resolved model in, a logical plan out.

The plan is read back node by node rather than through the answer it produces —
it is the contract consumers are written against.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import get_args

import pytest

from math_spec import LanguageError, Spec, to_spec
from math_spec._where_parser import parse_where
from math_spec.exclusivity import overlapping
from math_spec.program import (
    Add,
    And,
    Assumption,
    BooleanLiteral,
    Cases,
    Constant,
    CountComparison,
    DimensionComparison,
    DimensionDeclaration,
    Divide,
    Dual,
    Expression,
    ExpressionComparison,
    Footprint,
    Join,
    JoinColumns,
    Mask,
    Multiply,
    Not,
    Or,
    Parameter,
    ParameterComparison,
    ParameterDefined,
    Partition,
    Power,
    Program,
    PulledBackPredicate,
    QuadraticPosition,
    Region,
    RelationDeclaration,
    Sum,
    Translate,
    Variable,
    WindowSum,
    assumption_message,
    children,
    parameters_of,
    walk,
    walk_regions,
    where_children,
)
from math_spec.resolution import Namespace
from tests.fixtures import DISPATCH_MODEL, EXAMPLES, SMALL_MODEL, expanded, expression_of, override, schema_of, where_of

DISPATCH_YAML = EXAMPLES / 'dispatch.yaml'

#: The mask `examples/dispatch.yaml` puts on `dispatch`, as the plan carries it.
CAPACITY_POSITIVE = ParameterComparison('capacity', '>', 0.0, ('generator',))

#: One dimension, one parameter, one bounded variable and a scalar constraint:
#: the smallest model that loads, for a claim about the plan's record rather
#: than about the math in it. A test adds what it judges with :func:`override`.
TINY = {
    'dimensions': {'g': {}},
    'parameters': {'cost': {'dims': ['g']}},
    'variables': {'p': {'dims': ['g'], 'bounds': {'lower': 0, 'upper': 1}}},
    'constraints': {'c': {'dims': [], 'expression': 'sum(p, over=g) >= 1'}},
}

#: `lk` as `sum` joins it: joined on the key, grouped by the value, no key column left unnamed.
LK = RelationDeclaration((('g', 'g'), ('h', 'h')), ('g',))
LK2 = RelationDeclaration((('g', 'g'), ('z', 'z')), ('g',))
LK_JOIN = JoinColumns('lk', LK, ('g',), ('h',))
AT_BUS = RelationDeclaration((('g', 'g'), ('bus', 'bus')), ('g',))

#: `fixtures.SMALL_MODEL` plus a second relation and a per-entity
#: offset. Which node a construct becomes is mostly a claim about the dim it
#: joins on and the dim it groups by, and stating that needs a third dimension
#: and two relations over one of them.
SHAPES_MODEL = override(
    SMALL_MODEL,
    **{
        'dimensions.z': {'dtype': 'str'},
        'relations.lk2': {'key': 'g', 'values': 'z'},
        'parameters.lead': {'dims': ['g'], 'dtype': 'int'},
    },
)


def resolved(text: str, schema: Spec) -> Expression:
    """Parse, expand and resolve — the program tree a declaration holds.

    The ``'t'`` is the error-context label the resolver stamps on refusals,
    not a dimension.
    """
    return expression_of(text, Namespace(schema), 't')


@pytest.fixture
def dispatch_schema() -> Spec:
    return schema_of(DISPATCH_YAML)


@pytest.fixture
def dispatch_program(dispatch_schema) -> Program:
    return dispatch_schema.program


@pytest.fixture
def shapes_schema() -> Spec:
    return schema_of(SHAPES_MODEL)


# ---------------------------------------------------------------------------
# the plan the language lowers to
# ---------------------------------------------------------------------------


def test_program_structure(dispatch_program):
    assert list(dispatch_program.parameters) == ['capacity', 'load', 'cost'], 'keyed by name, in declaration order'
    ((vname, v),) = dispatch_program.variables.items()
    assert vname == 'dispatch'
    assert v.dims == ('snapshot', 'generator'), 'the frame is the dims, in the order the file wrote it'
    assert v.where == Mask(CAPACITY_POSITIVE)
    assert v.upper == Parameter('capacity')

    ((cname, c),) = dispatch_program.constraints.items()
    assert cname == 'power_balance'
    assert c.dims == ('snapshot',), 'the frame is the dims, in the order the file wrote it'
    assert c.lhs == Sum(Variable('dispatch'), ('generator',))
    assert c.sense == '==', "the comparison crosses as the file's own operator, untranslated"
    assert c.rhs == Parameter('load')

    assert dispatch_program.objective.sense == 'minimize', "the program carries the language's spelling, untranslated"
    assert dispatch_program.objective.expression == Sum(
        Multiply(Variable('dispatch'), Parameter('cost')), ('generator', 'snapshot')
    ), 'the objective carries the sum the file wrote, over the dims it named none of'


@pytest.mark.parametrize('sense', [pytest.param('minimize', id='minimize'), pytest.param('maximize', id='maximize')])
def test_the_objective_sense_crosses_untranslated(sense: str):
    """One spelling from the file to the program, in both directions — each sink translates at its own edge."""
    program = to_spec(override(TINY, objective={'sense': sense, 'expression': 'sum(p * cost, over=g)'})).program
    assert program.objective is not None
    assert program.objective.sense == sense, "the file's own word for the direction, unchanged"


def test_a_file_with_no_objective_lowers_to_no_sense():
    """A feasibility problem has no direction, and nothing downstream invents one."""
    program = to_spec(TINY).program
    assert program.objective is None, 'no objective declared is no objective, not a minimisation of nothing'


def test_a_literal_amount_resolves_to_one_signed_number(dispatch_schema):
    """`offset=-1` parses as a unary minus over `1`; after resolution it is `-1`, for every reader alike."""
    ns = Namespace(dispatch_schema)
    node = expression_of('shift(dispatch, along=snapshot, offset=-1, edge=+0)', ns, 't')
    assert isinstance(node, Translate)
    assert (node.offset, node.fill) == (-1, 0.0)


@pytest.mark.parametrize(
    ('where', 'expected'),
    [
        pytest.param(None, None, id='no-where-at-all'),
        pytest.param('True', None, id='True-is-no-mask'),
        pytest.param('capacity', ParameterDefined('capacity', ('generator',)), id='a-bare-parameter-name'),
        pytest.param(
            'snapshot > 5',
            DimensionComparison('snapshot', '>', 5),
            id='a-dimension-coordinate-compares-like-a-parameter',
        ),
        pytest.param(
            'capacity > 0 AND NOT load == 0',
            And(CAPACITY_POSITIVE, Not(ParameterComparison('load', '==', 0.0, ('snapshot',)))),
            id='a-compound-where-keeps-its-connectives',
        ),
        pytest.param('False', BooleanLiteral(False), id='the-empty-declaration-keeps-its-own-spelling'),
        pytest.param('capacity > 0 AND True', CAPACITY_POSITIVE, id='and-true-is-the-other-side'),
        pytest.param('capacity > 0 OR False', CAPACITY_POSITIVE, id='or-false-is-the-other-side'),
        pytest.param('capacity > 0 OR True', None, id='or-true-is-no-mask-at-all'),
        pytest.param('capacity > 0 AND False', BooleanLiteral(False), id='and-false-is-the-empty-declaration'),
        pytest.param('NOT True', BooleanLiteral(False), id='not-true-is-false'),
        pytest.param('NOT False', None, id='not-false-is-no-mask'),
        pytest.param('NOT (capacity > 0 AND False)', None, id='a-branch-folded-away-folds-the-one-above-it'),
        pytest.param(
            'NOT (NOT capacity)',
            ParameterDefined('capacity', ('generator',)),
            id='a-double-negation-cancels-on-the-load-path',
        ),
        pytest.param(
            '(capacity > 0 OR True) AND load',
            ParameterDefined('load', ('snapshot',)),
            id='an-absorbed-side-takes-its-own-branch-with-it',
        ),
    ],
)
def test_a_where_is_one_resolved_predicate_with_every_literal_folded(dispatch_schema, where, expected):
    """One mask had two lowerings: `True` was dropped at the root and kept under a connective.

    A `BooleanLiteral` is a node a consumer meets at the root or nowhere.
    """
    mask = where_of(where, Namespace(dispatch_schema), 't')
    assert (mask.root if mask is not None else None) == expected, (
        'the Mask carries exactly the resolved predicate, folded at resolution however the file spelled it'
    )


def test_a_folded_mask_reaches_the_declaration_the_shorter_spelling_would_have():
    """The fold is the program's, not a helper's: two files, one declaration."""
    written_out = schema_of(DISPATCH_MODEL, **{'variables.p.where': 'p_max > 0 AND True'}).program
    plain = schema_of(DISPATCH_MODEL, **{'variables.p.where': 'p_max > 0'}).program
    assert written_out.variables['p'] == plain.variables['p'], 'the same mask, so the same declaration'


def test_an_unknown_where_name_is_an_error_at_lowering_too(dispatch_schema):
    """It used to be a scalar-False mask in the eager lane: a model that
    builds, solves, and is silently empty. Resolution makes it a load error."""
    with pytest.raises(LanguageError, match="'no_such_param' not found"):
        where_of('no_such_param', Namespace(dispatch_schema), 't')


def test_a_lowered_mask_cannot_be_rewritten_in_place(dispatch_program):
    """A consumer handed a program could invert the mask another one reads.

    The where nodes were plain dataclasses while every declaration embedding
    them was frozen, so `variable.where.root.op = '!='` rewrote `capacity > 0` into
    `capacity != 0` on the shared object — two consumers disagreeing about one
    file, which is the failure a program exists to prevent. It also left
    hashability depending on the file: an unmasked declaration hashed and a
    masked one raised TypeError.
    """
    (v,) = dispatch_program.variables.values()
    assert v.where == Mask(CAPACITY_POSITIVE)

    with pytest.raises(FrozenInstanceError):
        v.where.root.op = '!='
    assert v.where == Mask(CAPACITY_POSITIVE), 'the mask the file wrote, unchanged'
    assert isinstance(hash(v), int), 'a masked declaration hashes like an unmasked one'


def test_a_lowered_where_is_a_mask_that_answers_from_its_root(dispatch_program):
    """The `where` a lowering carries is a `Mask`, and its questions are its root's.

    A consumer asks the mask — `where.names_read`, `where.conjuncts` — rather
    than reaching for a free function with the raw node.
    """
    (v,) = dispatch_program.variables.values()

    assert v.where == Mask(CAPACITY_POSITIVE)
    assert v.where.names_read == {'capacity'}, 'the declarations the mask names'
    assert v.where.conjuncts == (CAPACITY_POSITIVE,), 'a mask that is not an AND is its own only conjunct'
    assert v.where.atoms == (CAPACITY_POSITIVE,), 'a single leaf, connectives removed'


@pytest.mark.parametrize(
    ('variable', 'where', 'dims', 'conjuncts', 'atoms'),
    [
        pytest.param(
            'q',
            "lk == 'east' and position(h) == 0",
            {'g', 'h'},
            2,
            2,
            id='a-relation-is-read-at-the-dim-it-maps-out-of-and-a-position-at-its-own',
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
    mask = to_spec(override(SMALL_MODEL, **{f'variables.{variable}.where': where})).program.variables[variable].where

    assert mask.dims == frozenset(dims)
    assert len(mask.conjuncts) == conjuncts, 'an OR is one conjunct, a leaf is one conjunct'
    assert len(mask.atoms) == atoms, 'the leaves of every arm, connectives removed'


FLAG = ParameterDefined('flag', ('generator',))


@pytest.mark.parametrize(
    ('where', 'under'),
    [
        pytest.param(Not(CAPACITY_POSITIVE), (CAPACITY_POSITIVE,), id='a-not-carries-its-operand'),
        pytest.param(And(CAPACITY_POSITIVE, FLAG), (CAPACITY_POSITIVE, FLAG), id='an-and-carries-both-sides'),
        pytest.param(Or(CAPACITY_POSITIVE, FLAG), (CAPACITY_POSITIVE, FLAG), id='an-or-carries-both-sides'),
        pytest.param(CAPACITY_POSITIVE, (), id='a-leaf-carries-nothing'),
        pytest.param(BooleanLiteral(False), (), id='a-literal-carries-nothing'),
    ],
)
def test_where_children_is_the_one_walk_under_a_predicate(where, under):
    """`where_children` is to a mask what `children` is to an expression.

    The where tree was dispatched by hand at every walk — the grammar's depth
    measure, `Mask.atoms`, each consumer's own — with no shared answer to
    what sits under a node (#401). This is that answer, in file order.
    """
    assert where_children(where) == under, (
        'a connective carries its operands, left before right; a leaf carries nothing'
    )


def test_a_synthetic_predicate_answers_its_own_dims():
    """A tree built from resolved pieces answers like a declaration's own mask.

    A consumer builds region complements and conjunctions — `Not(root)`,
    `And(a, b)` — with no declaration behind them. Because the leaves carry
    their dims, wrapping any such tree in `Mask` answers without a name-to-dims
    mapping, which is what let the mapping die everywhere.
    """
    b = ParameterDefined('load', ('snapshot',))

    assert Mask(Not(CAPACITY_POSITIVE)).dims == {'generator'}, 'negation keeps the dims it negates'
    assert (Mask(CAPACITY_POSITIVE) & Mask(b)).dims == {'generator', 'snapshot'}, 'conjunction unions both sides'
    assert (Mask(CAPACITY_POSITIVE) & Mask(b)).root == And(CAPACITY_POSITIVE, b), (
        'the conjunction joins the roots under one AND'
    )


def test_mask_construction_folds_so_a_literal_stands_at_the_root_or_nowhere():
    """The fold lives in the constructor, so the invariant holds however a mask is built."""
    x = ParameterDefined('committable', ('g',))
    empty, every = Mask(BooleanLiteral(False)), Mask(BooleanLiteral(True))

    assert Mask(Or(BooleanLiteral(True), x)) == every, 'a True side absorbs the OR at the door'
    assert Mask(And(BooleanLiteral(False), x)) == empty, 'a False side dominates the AND at the door'
    assert Mask(Not(BooleanLiteral(True))) == empty, 'NOT over a literal flips at the door'
    assert Mask(Not(Not(x))) == Mask(x), 'a double negation cancels at the door'

    assert ~Mask(x) == Mask(Not(x)), 'a plain predicate negated gains one NOT'
    assert ~Mask(Not(x)) == Mask(x), '`not (not x)` cancels rather than stacking, so no consumer evaluates it twice'
    assert ~empty == every, 'the empty mask negated admits every row, with no NOT stacked'
    assert ~every == empty, 'and back again'
    assert empty & Mask(x) == empty, 'a False root dominates the conjunction'
    assert Mask(x) & empty == empty, 'from either side'
    assert every & Mask(x) == Mask(x), 'a True root is the other side'
    assert Mask(x) | empty == Mask(x), 'a False root is the other side of an OR'
    assert Mask(x) | every == every, 'a True root dominates the OR'


def test_a_held_leaf_walk_is_taken_after_the_fold_absorbed_a_branch():
    """`atoms` is held from construction, and construction folds first — so the fold's losses are not in it."""
    absorbed = Mask(And(BooleanLiteral(False), ParameterDefined('committable', ('g',))))

    assert absorbed.root == BooleanLiteral(False)
    assert absorbed.atoms == (), 'the absorbed leaf is not among them'
    assert absorbed.names_read == frozenset(), 'nor named'
    assert absorbed.dims == frozenset(), 'nor read at any dim'


def test_a_mask_over_an_unresolved_tree_is_refused_at_construction():
    """A tree whose leaves are unresolved is refused where it is wrapped, not where it is read."""
    with pytest.raises(AssertionError, match='reached a predicate walk unresolved'):
        Mask(parse_where('a AND b'))


def test_an_unwritten_where_lowers_to_none_not_an_empty_mask():
    lowered = to_spec(DISPATCH_MODEL).program
    (v,) = lowered.variables.values()
    (c,) = lowered.constraints.values()

    assert v.where is None, 'no `where:` in the file means no mask, not a mask over nothing'
    assert c.where is None, 'the constraint arm makes the same fold'


def test_a_constraint_where_is_a_mask_like_a_variable_s():
    lowered = to_spec(override(DISPATCH_MODEL, **{'constraints.balance.where': 'load > 0'})).program
    (c,) = lowered.constraints.values()

    assert c.where == Mask(ParameterComparison('load', '>', 0.0, ('snapshot',)))


def test_a_comparison_of_expressions_lowers_to_program_expressions_on_both_sides():
    """The resolved tree holds the core syntax tree; the program holds the vocabulary a consumer reads, and every mask is rebuilt so."""
    program = to_spec(
        override(
            SHAPES_MODEL,
            **{
                'parameters.zc': {'dims': ['z']},
                'variables.p.where': 'c <= 0.5 * k',
                'constraints.w': {
                    'dims': ['g'],
                    'where': 'c <= at(zc, by=lk2[z]) + sum_back(c, along=g, window=2, within=lk2[z])',
                    'expression': 'p <= c',
                },
            },
        )
    ).program
    where = program.variables['p'].where
    assert where is not None
    assert where.root == ExpressionComparison(Parameter('c'), '<=', Multiply(Constant(0.5), Parameter('k')), ('g',)), (
        'the sides are lowered as a constraint side is, and the dims are what either side carries'
    )
    mask = program.constraints['w'].where
    assert mask is not None and isinstance(mask.root, ExpressionComparison)
    assert isinstance(mask.root.right, Add) and isinstance(mask.root.right.left, Join)
    assert mask.names_read == frozenset({'c', 'zc', 'lk2'}), (
        'the relation a pullback and a partition read through is data the consumer attaches too'
    )


def test_a_predicate_a_leaf_carries_is_lowered_like_any_other_mask():
    """A comparison of expressions inside a count is rebuilt too, so a program mask is program vocabulary throughout."""
    program = to_spec(
        override(
            SHAPES_MODEL,
            **{'constraints.w': {'dims': ['g'], 'where': 'count(c <= 0.5 * k, over=g) >= 2', 'expression': 'p <= c'}},
        )
    ).program
    mask = program.constraints['w'].where
    assert mask is not None and isinstance(mask.root, CountComparison)
    assert mask.root.predicate.root == ExpressionComparison(
        Parameter('c'), '<=', Multiply(Constant(0.5), Parameter('k')), ('g',)
    ), 'the counted predicate is rebuilt, not handed through with the resolved comparison still in it'
    assert mask.names_read == frozenset({'c', 'k'}), 'what the counted predicate reads is data the consumer attaches'


def test_a_translated_predicate_keeps_what_it_reads_in_reach():
    """A walk that asks a mask what it names has to see through the translation, or the column is silently dropped."""
    program = to_spec(
        override(
            SHAPES_MODEL,
            **{
                'constraints.w': {
                    'dims': ['g'],
                    'where': 'flag AND NOT shift(flag, along=g, offset=1)',
                    'expression': 'p <= c',
                }
            },
        )
    ).program
    mask = program.constraints['w'].where
    assert mask is not None
    assert mask.names_read == frozenset({'flag'}), 'the translated half reads the same column as the plain one'
    assert sorted(mask.dims) == ['g']


def test_a_predicate_read_through_a_relation_is_lowered_and_keeps_the_relation_in_reach():
    """The comparison under the read is rebuilt, and the relation is data the consumer attaches as well as the operand."""
    program = to_spec(
        override(
            SHAPES_MODEL,
            **{
                'parameters.zcap': {'dims': ['z']},
                'constraints.w': {
                    'dims': ['g'],
                    'where': 'at(zcap <= 0.5 * k, by=lk2[z])',
                    'expression': 'p <= c',
                },
            },
        )
    ).program
    mask = program.constraints['w'].where
    assert mask is not None and isinstance(mask.root, PulledBackPredicate)
    assert mask.root.operand.root == ExpressionComparison(
        Parameter('zcap'), '<=', Multiply(Constant(0.5), Parameter('k')), ('z',)
    ), 'the read predicate is rebuilt, not handed through with the resolved comparison still in it'
    assert mask.names_read == frozenset({'zcap', 'k', 'lk2'})
    assert sorted(mask.dims) == ['g'], 'z is read at lk2(g), so the mask is over g alone'


def test_assumptions_carry_the_file_s_entries_and_the_curves_behind_them():
    """One mapping holds every fact about the data, so a consumer attaching it has one loop and one refusal.

    The file's entries come first, in the order it wrote them; each
    ``piecewise:`` block's conditions follow under the name a refusal quotes.
    """
    program = expanded(EXAMPLES / 'piecewise_lp.yaml', 'piecewise').program
    derived = [name for name in program.assumptions if name.startswith('cost_curve_')]

    assert all(isinstance(a, Assumption) for a in program.assumptions.values()), (
        'a method states its conditions in the language the file writes, so one kind stands in the mapping'
    )
    assert derived == [
        'cost_curve_complete',
        'cost_curve_increasing',
        'cost_curve_curvature',
        'cost_curve_breakpoints',
    ], 'an lp curve over a whole axis assumes four things of its breakpoints, completeness first'


def test_an_assumption_lowers_both_of_its_masks():
    """The predicate and the ``where`` are rebuilt on program expressions, as every other mask is."""
    program = to_spec(override(SHAPES_MODEL, assumptions={'sound': {'holds': 'c <= 0.5 * k', 'where': 'flag'}})).program
    assumption = program.assumptions['sound']

    assert assumption == Assumption(
        Mask(ExpressionComparison(Parameter('c'), '<=', Multiply(Constant(0.5), Parameter('k')), ('g',))),
        Mask(ParameterDefined('flag', ('g',))),
    ), 'the arithmetic side is a program expression, and the where is the mask the file wrote'
    assert assumption_message('sound', assumption) == (
        "assumption 'sound' does not hold for the data attached to 'c', 'k'"
    ), 'the refusal names what the consumer bound, so it can say which column is wrong'


def test_an_assumption_refuses_in_the_words_the_file_wrote():
    """``description:`` reached no consumer: the block held it and neither the program nor the sentence did.

    The names alone say which columns are wrong. What the author wrote says
    why the rule is there, which is what the reader of a refusal needs, so
    the sentence quotes it where the file wrote one.
    """
    reason = 'a shape with no room between its bounds cannot be cut'
    program = to_spec(override(SHAPES_MODEL, assumptions={'sound': {'holds': 'c <= k', 'description': reason}})).program
    assumption = program.assumptions['sound']

    assert assumption.description == reason, 'the program carries it, so a consumer needs no second read of the file'
    assert assumption_message('sound', assumption) == (
        f"assumption 'sound' does not hold for the data attached to 'c', 'k' \N{EM DASH} {reason}"
    ), 'the sentence trails what the author wrote'


def test_a_cased_side_reads_the_data_its_regions_are_decided_by():
    """`names_read` promised every parameter and relation the sides read, and dropped the
    `when:` of a cased entry: the walk descends a `Cases` by its values alone."""
    program = to_spec(
        override(
            SHAPES_MODEL,
            **{
                'expressions.e': {
                    'dims': ['g'],
                    'cases': {'linked': {'when': 'flag AND lk2', 'expression': 'c'}},
                    'otherwise': 'k',
                },
                'variables.p.where': 'e > 0',
            },
        )
    ).program
    where = program.variables['p'].where
    assert where is not None
    assert where.names_read == frozenset({'c', 'k', 'flag', 'lk2'}), (
        'the flag and the relation decide which region applies, so the consumer attaches them too'
    )


def test_a_mask_with_no_arithmetic_is_the_same_mask_after_lowering(dispatch_program):
    """Every other predicate node is already the program's own, so lowering hands it through unchanged."""
    assert dispatch_program.variables['dispatch'].where == Mask(CAPACITY_POSITIVE)


def test_a_power_resolves_to_a_node_of_its_own(dispatch_schema):
    assert isinstance(resolved('cost ** cost', dispatch_schema), Power), 'a variable-free power has a node of its own'


@pytest.mark.parametrize(
    ('expression', 'expected'),
    [
        pytest.param('sum(q)', Sum(Variable('q'), ('g', 'h')), id='a-bare-sum-sums-away-every-dim-the-operand-carries'),
        pytest.param('sum(q, over=h)', Sum(Variable('q'), ('h',)), id='an-over-sums-away-the-dim-it-names'),
        pytest.param(
            'sum(p, over=g, by=lk[h])',
            Sum(Join(Variable('p'), LK_JOIN), ('lk.g',)),
            id='a-grouped-sum-is-a-sum-over-the-axis-its-join-opens',
        ),
        pytest.param(
            'at(r, by=lk[h])',
            Join(Variable('r'), JoinColumns('lk', LK, ('h',), ('g',))),
            id='an-at-is-the-same-join-the-other-way-with-no-sum-over-it',
        ),
        pytest.param(
            "shift(p, along=g, offset=1, edge='wrap')",
            Translate(Variable('p'), 'g', offset=1, wrap=True, fill=None),
            id='a-wrapping-translation-fills-nothing',
        ),
        pytest.param(
            'shift(p, along=g, offset=-2, edge=0)',
            Translate(Variable('p'), 'g', offset=-2, wrap=False, fill=0.0),
            id='a-lead-is-a-negative-offset-and-the-edge-is-what-it-fills-with',
        ),
        pytest.param(
            'shift(p, along=g, offset=lead, edge=0)',
            Translate(Variable('p'), 'g', offset='lead', wrap=False, fill=0.0),
            id='a-named-offset-crosses-as-the-parameter-name',
        ),
        pytest.param(
            "shift(p, along=g, offset=+lead, edge='wrap')",
            Translate(Variable('p'), 'g', offset='lead', wrap=True, fill=None),
            id='a-named-offset-written-with-a-plus-is-the-parameter',
        ),
        pytest.param(
            'shift(p, along=g, offset=1, within=lk[h], edge=0)',
            Translate(
                Variable('p'),
                'g',
                offset=1,
                wrap=False,
                fill=0.0,
                partition=Partition('lk', LK, 'g', ('h',), ()),
            ),
            id='a-translation-stops-at-the-edges-of-the-relation-it-names',
        ),
        pytest.param(
            'sum_back(p, along=g, window=3)',
            WindowSum(Variable('p'), 'g', width=3, wrap=False),
            id='a-window-is-one-node-rather-than-a-fold-of-translations',
        ),
        pytest.param(
            'sum_back(p, along=g, window=lead)',
            WindowSum(Variable('p'), 'g', width='lead', wrap=False),
            id='a-named-width-crosses-as-the-parameter-name',
        ),
        pytest.param(
            'sum_back(p, along=g, window=2, within=lk[h])',
            WindowSum(
                Variable('p'),
                'g',
                width=2,
                wrap=False,
                partition=Partition('lk', LK, 'g', ('h',), ()),
            ),
            id='a-window-stops-at-the-edges-of-the-relation-it-names',
        ),
    ],
)
def test_a_construct_resolves_to_its_node(shapes_schema, expression, expected):
    """Which node each surface construct becomes, and every field it arrives with."""
    assert resolved(expression, shapes_schema) == expected, 'the whole frozen node, so no field is asserted by omission'


def test_a_partition_keeps_its_group_when_the_relation_gains_a_value_column():
    """`within=` is what the call groups by, so a calendar that gains a `week` column regroups no `shift` through it (#538).

    With `within=` optional, an omitted one meant every value column, and the
    same call grouped by `('day',)` on one calendar and `('day', 'week')` on the
    next.
    """
    grouping = {}
    for values in ('day', ['day', 'week']):
        program = to_spec(
            {
                'dimensions': {'hour': {'dtype': 'int'}, 'day': {}, 'week': {}},
                'relations': {'cal': {'key': 'hour', 'values': values}},
                'variables': {'p': {'dims': ['hour']}},
                'constraints': {
                    'k': {
                        'dims': ['hour'],
                        'expression': 'p >= shift(p, along=hour, offset=1, edge=0, within=cal[day])',
                    }
                },
            }
        ).program
        grouping[str(values)] = _partition_of(program.constraints['k']).grouped
    assert grouping == {'day': ('day',), "['day', 'week']": ('day',)}, (
        'the group is the columns the call named, on both calendars'
    )


def _partition_of(row):
    """The one partition a constraint row's expression carries."""
    nodes = [*walk(row.lhs), *walk(row.rhs)]
    [partition] = [node.partition for node in nodes if isinstance(node, Translate | WindowSum)]
    return partition


def test_a_relation_lowers_with_the_join_each_call_names():
    """Every node reading a relation carries its columns, its key and the join, so a consumer joins on the right columns."""
    program = to_spec(
        {
            'dimensions': {'snapshot': {'dtype': 'int'}, 'generator': {}, 'zone': {}},
            'relations': {'zone_of': {'key': ['generator', 'snapshot'], 'values': 'zone'}},
            'parameters': {'price': {'dims': ['snapshot', 'zone']}},
            'variables': {
                'p': {'dims': ['snapshot', 'generator'], 'where': "zone_of == 'A' AND zone_of"},
                'first': {
                    'dims': ['snapshot', 'generator'],
                    'where': 'position(generator, within=zone_of[zone]) == 0',
                },
            },
            'constraints': {
                'zonal': {
                    'dims': ['snapshot', 'zone'],
                    'expression': 'sum(p, over=generator, by=zone_of[zone]) <= 1',
                },
                'priced': {
                    'dims': ['snapshot', 'generator'],
                    'expression': 'p <= at(price, by=zone_of[zone])',
                },
                'history': {
                    'dims': ['generator', 'zone'],
                    'expression': 'sum(p, over=snapshot, by=zone_of[zone]) <= 1',
                },
            },
        }
    ).program

    columns = (('generator', 'generator'), ('snapshot', 'snapshot'), ('zone', 'zone'))
    declared = RelationDeclaration(columns, ('generator', 'snapshot'))
    assert program.relations == {'zone_of': declared}, 'the relation sits once in the program, under its name'
    zonal = program.constraints['zonal'].lhs
    columns = JoinColumns('zone_of', declared, ('generator', 'snapshot'), ('zone', 'snapshot'))
    assert zonal == Sum(Join(Variable('p'), columns), ('zone_of.generator',)), (
        'a grouped sum is a sum over a join: the join names the column over the over= dim and the unnamed key '
        'column as joined on, the by= column and that key column as grouped by, and the sum stands over the axis '
        'the join opens for the column it drops'
    )
    assert isinstance(zonal, Sum) and isinstance(zonal.operand, Join)
    assert (zonal.operand.columns.dropped_dims, zonal.operand.columns.added_dims, zonal.operand.columns.kept) == (
        ('generator',),
        ('zone',),
        ('snapshot',),
    ), 'the dims a consumer reads are read off the join: dropped, added, and the key columns kept'
    assert zonal.operand.columns.relation is program.relations['zone_of'], (
        'the join holds the one declaration the program holds, not an equal copy built again'
    )
    assert program.constraints['history'].lhs == Sum(
        Join(Variable('p'), JoinColumns('zone_of', declared, ('snapshot', 'generator'), ('zone', 'generator'))),
        ('zone_of.snapshot',),
    ), 'the same table joined on its other key column'
    priced = program.constraints['priced'].rhs
    assert priced == Join(
        Parameter('price'), JoinColumns('zone_of', declared, ('zone', 'snapshot'), ('generator', 'snapshot'))
    ), 'and an at is the bare join, on the value column, grouped by the key columns'
    assert isinstance(priced, Join)
    assert (priced.columns.dropped_dims, priced.columns.added_dims, priced.columns.kept) == (
        ('zone',),
        ('generator',),
        ('snapshot',),
    ), 'an at joins on the coarse dims, groups by the fine, and keeps the rest of the key'
    p_where = program.variables['p'].where
    assert p_where is not None
    assert [(type(a).__name__, a.dims) for a in p_where.atoms] == [
        ('RelationComparison', ('generator', 'snapshot')),
        ('RelationDefined', ('generator', 'snapshot')),
    ], 'a comparison and an existence are both read at the key of a keyed relation'
    first_where = program.variables['first'].where
    assert first_where is not None
    assert first_where.dims == {'generator', 'snapshot'}, 'a position within a group is read at every key column'


def test_a_binary_variable_lowers_to_a_binary_domain():
    program = schema_of(
        DISPATCH_YAML, **{'variables.dispatch.domain': 'binary', 'variables.dispatch.bounds': {}}
    ).program
    assert program.variables['dispatch'].domain == 'binary'


def test_a_divisor_under_a_join_is_still_named():
    """`children` has to descend through every node, or a refusal loses its name."""
    quotient = Divide(Variable('x'), Parameter('rate'))
    component_of = RelationDeclaration((('flow', 'flow'), ('component', 'component')), ('flow',))
    looked_up = Join(quotient, JoinColumns('component_of', component_of, ('component',), ('flow',)))

    assert parameters_of(looked_up) == frozenset({'rate'}), 'the walk descends through `Join`'
    assert parameters_of(Sum(looked_up, ('flow',))) == frozenset({'rate'}), 'and through a `Sum` over it'


def test_a_divisor_under_a_power_is_still_named():
    """`children` had no branch for `Power`, so every walk stopped at it and a divisor written
    `d ** 2` was reported with no parameter at all (#403)."""
    quotient = Divide(Variable('x'), Power(Parameter('d'), Constant(2.0)))

    assert children(quotient.divisor) == (Parameter('d'), Constant(2.0)), 'the base first, then the exponent'
    assert parameters_of(quotient) == frozenset({'d'}), 'the walk descends through `Power`'


OUTER = Mask(ParameterDefined('committable', ('g',)))
INNER = Mask(ParameterDefined('flag', ('g',)))
NESTED = Add(
    Variable('x'),
    Cases(
        (
            Region(OUTER, Cases((Region(INNER, Variable('p')), Region(~INNER, Constant(0.0))))),
            Region(~OUTER, Parameter('q')),
        )
    ),
)


def test_walk_regions_carries_the_regions_a_node_stands_under():
    """Which regions stand above a node decides which rows a piece owes data at,
    and every consumer recursed for it on its own (#473)."""
    assert list(walk_regions(NESTED)) == [
        (NESTED, ()),
        (Variable('x'), ()),
        (NESTED.right, ()),
        (NESTED.right.regions[0].value, (OUTER,)),
        (Variable('p'), (OUTER, INNER)),
        (Constant(0.0), (OUTER, ~INNER)),
        (Parameter('q'), (~OUTER,)),
    ], (
        'parents first; a node outside any block carries nothing; a `Cases` carries only the regions '
        'above it; a value under two blocks carries both, the outer one first'
    )


def test_walk_is_the_node_column_of_walk_regions():
    """One recursion, so a node kind that learns to descend reaches both walks at once."""
    assert list(walk(NESTED)) == [node for node, _ in walk_regions(NESTED)]


def test_a_relation_is_declared_as_the_file_declares_it():
    """One group keyed by name, each entry its columns and its key, and nothing nested under a dimension."""
    program = to_spec(
        override(
            TINY,
            dimensions={'g': {}, 'bus': {}, 'season': {}},
            relations={
                'season_of': {'key': 'g', 'values': 'season'},
                'at_bus': {'key': 'g', 'values': 'bus'},
            },
        )
    ).program

    assert program.relations == {
        'season_of': RelationDeclaration((('g', 'g'), ('season', 'season')), ('g',)),
        'at_bus': RelationDeclaration((('g', 'g'), ('bus', 'bus')), ('g',)),
    }, 'every relation under its own name, in declaration order'
    assert program.relations['season_of'].values == ('season',), 'and each says what its key determines'
    assert program.dimensions['g'] == DimensionDeclaration(dtype='str'), 'a dimension carries its dtype and no relation'


def test_a_program_is_built_by_keyword_so_a_field_added_later_cannot_reorder_an_old_call():
    """Positional construction made every field's *position* part of the contract."""
    with pytest.raises(TypeError, match='positional'):
        Program({}, {}, {}, None)  # pyrefly: ignore[bad-argument-count]  the point of the test


@pytest.mark.parametrize('group', ['parameters', 'variables', 'constraints', 'dimensions', 'relations', 'sos'])
def test_a_program_seals_its_declaration_groups(dispatch_program, group):
    """`frozen=True` sealed the fields and said nothing about what was behind them."""
    with pytest.raises(TypeError):
        getattr(dispatch_program, group)['sneak'] = None  # pyrefly: ignore[unsupported-operation]  the point of the test


def test_roots_are_the_trees_a_row_is_built_from():
    """`expressions` is the file's own section, which builds no row at all; the row-building trees are `roots`."""
    program = to_spec(
        override(
            TINY,
            expressions={'spend': 'sum(cost, over=g)'},
            objective={'sense': 'minimize', 'expression': 'sum(p * cost, over=g)'},
        )
    ).program

    assert list(program.expressions) == ['spend'], 'the declared ones keep their own name'
    assert program.roots == (
        program.objective.expression,
        program.constraints['c'].lhs,
        program.constraints['c'].rhs,
    ), 'the objective first, then both sides of each constraint, in declaration order'
    assert program.expressions['spend'].expression not in program.roots, (
        'a named expression builds no row, so it is not one of the trees a row is built from'
    )
    assert len(program.roots) == 3, 'and nothing else is counted'


def _footprint_of(constraint: str, objective: str) -> Footprint:
    return to_spec(
        override(
            TINY,
            constraints={'k': {'dims': ['g'], 'expression': constraint}},
            objective={'sense': 'minimize', 'expression': objective},
        )
    ).program.footprint


def test_the_footprint_says_which_position_a_quadratic_stands_in():
    """A sink may take a quadratic objective and refuse a quadratic constraint.

    One flag for both would collapse the distinction `limits.md` says sinks
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
    assert footprint.domains == {'continuous'}, 'never empty — a program has variables'
    assert {type(f) for f in (footprint.sos_types, footprint.quadratic, footprint.kinds)} == {frozenset}, (
        'every field is a set, so one rule reads all of them'
    )
    assert footprint.quadratic <= set(get_args(QuadraticPosition)), (
        'and the vocabulary a consumer pins its table against'
    )
    assert {'objective', 'constraint'} == set(get_args(QuadraticPosition)), (
        'a position admitted later widens this, which is what a consumer pins against to hear about it'
    )


def test_the_footprint_is_walked_once_and_held(dispatch_program):
    """Safe to hold only because the program cannot change under it."""
    assert dispatch_program.footprint is dispatch_program.footprint


def test_a_named_expression_is_not_in_the_footprint():
    """It builds no row, so counting it would answer wrongly about what is solved."""
    program = to_spec(override(TINY, expressions={'spend': 'sum(p * cost, over=g)'})).program

    assert Parameter not in program.footprint.kinds, "the named expression's parameter reaches no row"
    assert Parameter in {type(n) for n in walk(program.expressions['spend'].expression)}, (
        'though it is in the expression'
    )


def test_a_dimension_carries_the_dtype_its_labels_are_checked_against():
    """The declared type travels with the dimension, as a parameter's does.

    A dimension is read from whatever table carries it, so nothing downstream
    can infer what the column should have been.
    """
    program = to_spec(override(TINY, **{'dimensions.t': {'dtype': 'int'}})).program

    assert program.dimensions['t'].dtype == 'int', 'a declared dtype reaches the plan'
    assert program.dimensions['g'].dtype == 'str', "and the schema's default does too, rather than nothing"


CASED = {
    'dimensions': {'t': {'dtype': 'int'}, 'g': {'dtype': 'str'}},
    'parameters': {'committable': {'dims': ['g'], 'dtype': 'bool'}, 'initial': {'dims': ['g']}},
    'variables': {'status': {'dims': ['t', 'g'], 'domain': 'binary'}},
    'expressions': {
        'previous': {
            'dims': ['t', 'g'],
            'cases': {
                'always_on': {'when': 'not committable', 'expression': 1},
                'boundary': {'when': 'committable and position(t) == 0', 'expression': 'initial'},
            },
            'otherwise': 'shift(status, along=t, offset=1)',
        }
    },
    'constraints': {'no_restart': {'dims': ['t', 'g'], 'expression': 'status - previous <= 1'}},
}


def _cases_in(program: Program) -> Cases:
    """The one cased node the fixture's constraint carries."""
    sides = [side for c in program.constraints.values() for side in (c.lhs, c.rhs)]
    found = [n for n in walk(*sides) if isinstance(n, Cases)]
    assert len(found) == 1, 'the fixture has exactly one cased expression, inlined where it is named'
    return found[0]


def test_a_cased_expression_lowers_to_one_region_per_case():
    """The regions come out in file order, values lowered like any other expression."""
    cases = _cases_in(to_spec(CASED).program)

    assert len(cases.regions) == 3, 'one region per case, the `otherwise` among them'
    assert [type(r.value).__name__ for r in cases.regions] == ['Constant', 'Parameter', 'Translate'], (
        'each region carries its own value, lowered — a number, a parameter and a shift'
    )


def test_the_fallback_region_carries_the_mask_the_file_left_unwritten():
    """`otherwise:` writes no `when:`; it arrives with the negation of the rest.

    A consumer adds regions rather than working out which one is left over, so
    the remainder is resolved once here instead of once per consumer.
    """
    remainder = _cases_in(to_spec(CASED).program).regions[-1]

    assert isinstance(remainder.when.root, And), 'two stated cases, so the remainder is a conjunction of two negations'
    assert remainder.when.root.left == ParameterDefined('committable', ('g',)), (
        'the negation of `not committable` is the term itself, not a second `not` around it'
    )


def test_a_region_s_when_is_a_mask_with_its_own_dims():
    """`Region.when` arrives in the same carrier as a declaration's `where`.

    It was the one mask left as a bare node, so a helper written over `Mask`
    branched on where a mask came from — the divergence the carrier exists to
    prevent. The synthesized remainder gets its dims like any stated case.
    """
    always_on, boundary, remainder = _cases_in(to_spec(CASED).program).regions

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
    regions = _cases_in(spec.program).regions
    named = {f'region{i}': r.when.root for i, r in enumerate(regions)}

    assert list(overlapping(named, Namespace(spec).dtypes)) == [], 'no two lowered regions can claim one coordinate'


def test_a_cased_expression_is_readable_by_the_name_the_file_wrote():
    """`Program.expressions` carries it under its name, so a consumer reads it back whole."""
    program = to_spec(CASED).program

    assert isinstance(program.expressions['previous'].expression, Cases), (
        'a cased expression reaches the program as the node, not as its fallback arm alone'
    )


@pytest.mark.parametrize(
    ('patch', 'in_math'),
    [
        pytest.param({'constraints.c.expression': 'spend >= 1'}, True, id='a-constraint-inlines-it'),
        pytest.param({'objective': {'sense': 'minimize', 'expression': 'spend'}}, True, id='the-objective-inlines-it'),
        pytest.param(
            {'expressions.twice': 'spend * 2', 'constraints.c.expression': 'twice >= 1'},
            True,
            id='inlined-through-another-entry',
        ),
        pytest.param(
            {
                'macros': {'scaled': {'args': ['x'], 'template': 'x * 2'}},
                'constraints.c.expression': 'scaled(spend) >= 1',
            },
            True,
            id='inlined-through-a-macro',
        ),
        pytest.param({}, False, id='nothing-reads-it'),
        pytest.param(
            {'expressions.ratio': 'spend / sum(p, over=g)'},
            False,
            id='only-an-entry-the-math-never-reads-inlines-it',
        ),
    ],
)
def test_an_entry_is_in_the_math_where_the_objective_or_a_constraint_inlines_it(patch, in_math):
    """`in_math` is usage, not shape: one affine body is in the math when a row inlines it, however indirectly, and a reported quantity when none does."""
    program = to_spec(override(TINY, expressions={'spend': 'sum(p * cost, over=g)'}, **patch)).program
    assert program.expressions['spend'].in_math is in_math


def test_an_entry_reached_only_through_another_is_in_the_math_with_it():
    """The whole chain is in the math, not only the entry a row names: the constraint inlines `twice`, and `twice` inlines `spend`."""
    program = to_spec(
        override(
            TINY,
            expressions={'spend': 'sum(p * cost, over=g)', 'twice': 'spend * 2'},
            **{'constraints.c.expression': 'twice >= 1'},
        )
    ).program
    reads = {name: program.expressions[name].in_math for name in ('twice', 'spend')}
    assert reads == {'twice': True, 'spend': True}, (
        'the entry the row names and the one it reaches through are both in the math'
    )


def test_a_macro_formal_named_like_an_entry_keeps_the_entry_out_of_the_math():
    """A formal shadows the entry inside the template, so the row inlines the argument, not the same-named entry."""
    program = to_spec(
        override(
            TINY,
            expressions={'spend': 'sum(p * cost, over=g)'},
            macros={'scaled': {'args': ['spend'], 'template': 'spend * 2'}},
            **{'constraints.c.expression': 'scaled(sum(p, over=g)) >= 1'},
        )
    ).program
    assert program.expressions['spend'].in_math is False, (
        'the formal shadows the entry, so the constraint inlines the argument and the math never reads spend'
    )


def test_an_entry_that_reads_a_dual_is_a_reported_quantity():
    """A dual is read after the solve, so an entry calling one is never in the math: it lowers to a Dual leaf and stays reported."""
    program = to_spec(override(TINY, expressions={'shadow_price': 'dual(c)'})).program
    declaration = program.expressions['shadow_price']
    assert declaration.in_math is False, 'the entry reading a dual is reported, never in the math'
    assert isinstance(declaration.expression, Dual), 'and it lowers to a Dual leaf'


def test_a_spec_answers_with_one_program_however_often_it_is_asked():
    """The public-API page promises one object, so a cache a reader may key on it holds."""
    spec = to_spec(DISPATCH_MODEL)
    assert spec.program is spec.program


def test_a_lowered_spec_still_pickles_and_lowers_to_the_same_program():
    """A model crosses a process the same whether or not it has been lowered.

    Lowering caches its expansion on the Spec, and a named expression's
    resolved node held its keyword arguments behind a ``MappingProxyType``,
    which pickle refuses — so a Spec that had been lowered could not cross a
    process where a fresh one could. The seal pickles now, and the copy lowers
    to the same program.
    """
    import pickle

    spec = Spec.model_validate(
        {
            'dimensions': {'t': {'dtype': 'int'}, 'g': {'dtype': 'str'}},
            'parameters': {'load': {'dims': ['t']}, 'cost': {'dims': ['g']}},
            'variables': {'p': {'dims': ['t', 'g'], 'bounds': {'lower': 0}}},
            'constraints': {'balance': {'dims': ['t'], 'expression': 'sum(p, over=g) >= load'}},
            'expressions': {'spend': 'sum(p * cost, over=g)'},
            'objective': {'sense': 'minimize', 'expression': 'sum(spend)'},
        }
    )
    program = spec.program

    copy = pickle.loads(pickle.dumps(spec))
    assert copy.model_dump() == spec.model_dump()
    assert to_spec(copy).program == program, 'the copy lowers to the program the original did'


def test_a_lowered_program_pickles_and_is_the_same_program():
    """A program crosses a process as itself, walked or not.

    Every group of declarations is sealed against writes, and the seal used
    to be a ``MappingProxyType``, which pickle refuses — so a program could
    be built by one process and never handed to another, and a consumer
    running slices in a pool re-lowered the file per slice. The seal now
    pickles, and so does what a walk caches on the program.
    """
    import pickle

    program = to_spec(
        {
            'dimensions': {'t': {'dtype': 'int'}, 'g': {'dtype': 'str'}},
            'parameters': {'load': {'dims': ['t']}, 'cost': {'dims': ['g']}},
            'variables': {'p': {'dims': ['t', 'g'], 'bounds': {'lower': 0}}},
            'constraints': {'balance': {'dims': ['t'], 'expression': 'sum(p, over=g) >= load'}},
            'expressions': {'spend': 'sum(p * cost, over=g)'},
            'objective': {'sense': 'minimize', 'expression': 'sum(spend)'},
        }
    ).program
    assert program.separability['t'].ahead == 0 and program.footprint is not None, 'the caches are filled first'

    copy = pickle.loads(pickle.dumps(program))
    assert copy == program
    assert copy.separability == program.separability
    with pytest.raises(TypeError, match='does not support item assignment'):
        copy.variables['q'] = copy.variables['p']


def test_two_groups_of_a_program_merge_with_or_as_they_did_behind_the_proxy():
    """`program.constraints | program.variables` is a dict of both, as it was
    when the groups were `MappingProxyType`s — a consumer that walks every
    declaration this way (specsolve's parity harness does) broke on alpha.78,
    where the seal answered `|` with a `TypeError`."""
    program = to_spec(
        {
            'dimensions': {'t': {'dtype': 'int'}},
            'parameters': {'load': {'dims': ['t']}},
            'variables': {'p': {'dims': ['t'], 'bounds': {'lower': 0}}},
            'constraints': {'meet': {'dims': ['t'], 'expression': 'p >= load'}},
            'objective': {'sense': 'minimize', 'expression': 'sum(p)'},
        }
    ).program
    merged = program.constraints | program.variables
    assert isinstance(merged, dict), 'a merge is a plain dict, as the proxy gave'
    assert list(merged) == ['meet', 'p'], 'both groups, the left one first'
    assert list({'q': None} | program.variables) == ['q', 'p'], 'and a dict on the left merges too'
