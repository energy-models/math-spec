# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Dim sets are a type system, checked before any data is attached."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

import pytest

from math_spec.dimensions import DimensionError, _check_where_dims, dims_of
from math_spec.errors import SchemaError
from math_spec.program import Join, Mask, RelationPairComparison, Sum
from math_spec.resolution import Namespace
from math_spec.validation import to_spec
from tests.fixtures import expression_of, override, schema_of, where_of

if TYPE_CHECKING:
    from math_spec.model import Spec

#: `fixtures.DISPATCH_MODEL` plus buses: a dim rule is mostly about an
#: expression carrying a dim its frame does not, which needs three dims to
#: state. `snap_bus` is over `snapshot` so it can partition the axis the
#: translations step along; `spinup` and `horizon` are the named amount that
#: obeys the position rules and the one that spans that axis; `bus_lead` is
#: over a dim `p` does not carry, so it is readable only through a `by=`.
BASE = {
    'dimensions': {
        'snapshot': {'dtype': 'int'},
        'generator': {'dtype': 'str'},
        'bus': {'dtype': 'str'},
        'zone': {'dtype': 'str'},
    },
    'relations': {
        'gen_bus': {'key': 'generator', 'values': 'bus'},
        'snap_bus': {'key': 'snapshot', 'values': 'bus'},
        'gen_zone': {'key': ['generator', 'snapshot'], 'values': 'zone'},
        'rep_of': {'key': 'snapshot', 'values': {'rep': 'snapshot'}},
        'gen_bz': {'key': 'generator', 'values': ['bus', 'zone']},
        'pair': {'key': {'g': 'generator'}, 'values': {'b0': 'bus', 'b1': 'bus'}},
    },
    'parameters': {
        'p_max': {'dims': ['generator']},
        'cost': {'dims': ['generator']},
        'load': {'dims': ['snapshot', 'bus']},
        'zone_cap': {'dims': ['zone']},
        'zone_load': {'dims': ['snapshot', 'zone']},
        'bz': {'dims': ['bus', 'zone']},
        'spinup': {'dims': ['generator'], 'dtype': 'int'},
        'horizon': {'dims': ['snapshot'], 'dtype': 'int'},
        'bus_lead': {'dims': ['bus'], 'dtype': 'int'},
    },
    'variables': {'p': {'dims': ['snapshot', 'generator'], 'bounds': {'lower': 0, 'upper': 'p_max'}}},
    'constraints': {
        'balance': {
            'dims': ['snapshot', 'bus'],
            'expression': 'sum(p, over=generator, by=gen_bus[bus]) == load',
        }
    },
    'objective': {'sense': 'minimize', 'expression': 'sum(p * cost)'},
}


def _schema(**overrides) -> Spec:
    return schema_of(BASE, **overrides)


def _dims(expr: str) -> frozenset[str]:
    s = _schema()
    return dims_of(expression_of(expr, Namespace(s), 't'), s, 't')


@pytest.fixture
def namespace() -> Namespace:
    return Namespace(_schema())


# ---------------------------------------------------------------------------
# the rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('expr', 'expected'),
    [
        ('7', set()),
        ('cost', {'generator'}),
        ('p', {'snapshot', 'generator'}),
        ('-p', {'snapshot', 'generator'}),
        ('p * cost', {'snapshot', 'generator'}),
        ('sum(p)', set()),
        ('sum(p * cost)', set()),
        ('sum(p, over=generator)', {'snapshot'}),
        ('sum(p * cost, over=generator)', {'snapshot'}),
        ('sum(p, over=generator, by=gen_bus[bus])', {'snapshot', 'bus'}),
        ("shift(p, along=snapshot, offset=1, edge='wrap')", {'snapshot', 'generator'}),
        ("shift(p, along=snapshot, offset=spinup, edge='wrap')", {'snapshot', 'generator'}),
        ('sum_back(p, along=snapshot, window=spinup)', {'snapshot', 'generator'}),
        pytest.param(
            "shift(p, along=snapshot, offset=bus_lead, edge='wrap', within=snap_bus[bus])",
            {'snapshot', 'generator'},
            id='a-by-makes-an-offset-over-another-dim-readable-one-lag-per-group',
        ),
        pytest.param(
            'sum_back(p, along=snapshot, window=bus_lead, within=snap_bus[bus])',
            {'snapshot', 'generator'},
            id='a-by-makes-a-width-over-another-dim-readable-one-window-per-group',
        ),
        pytest.param('p + 1', {'snapshot', 'generator'}, id='a-scalar-broadcasts'),
        pytest.param(
            'sum(p, over=generator, by=gen_zone[zone])',
            {'snapshot', 'zone'},
            id='a-two-key-relation-sums-away-the-key-it-names-and-keeps-the-other',
        ),
        pytest.param(
            'sum(p, over=snapshot, by=gen_zone[zone])',
            {'generator', 'zone'},
            id='the-same-table-read-along-its-other-key',
        ),
        pytest.param(
            'at(zone_load, by=gen_zone[zone])',
            {'snapshot', 'generator'},
            id='its-lookup-keeps-the-joined-key-too',
        ),
        pytest.param(
            "shift(p, along=generator, offset=1, edge='wrap', within=gen_zone[zone])",
            {'snapshot', 'generator'},
            id='a-partition-along-one-key-joined-on-the-other',
        ),
        pytest.param(
            "shift(p, along=generator, offset=1, edge='wrap', within=gen_bz[bus])",
            {'snapshot', 'generator'},
            id='a-partition-grouped-by-one-value-column-of-a-two-value-table',
        ),
        pytest.param(
            'sum_back(p, along=generator, window=2, within=gen_bz[bus, zone])',
            {'snapshot', 'generator'},
            id='a-window-grouped-by-both-value-columns-named',
        ),
        pytest.param(
            "shift(p, along=generator, offset=1, edge='wrap', within=pair[b0, b1])",
            {'snapshot', 'generator'},
            id='a-partition-grouped-by-two-columns-over-one-dimension-adds-nothing',
        ),
        pytest.param(
            'sum(p, over=generator, by=gen_bus[bus])',
            {'snapshot', 'bus'},
            id='the-dot-is-legal-on-a-one-key-relation',
        ),
        pytest.param(
            'sum(p, over=generator, by=gen_bz[bus, zone])',
            {'snapshot', 'bus', 'zone'},
            id='a-to-list-lands-on-a-product-from-one-table',
        ),
        pytest.param(
            'at(bz, by=gen_bz[bus, zone])',
            {'generator'},
            id='a-from-list-reads-two-value-columns-at-once',
        ),
        pytest.param(
            'sum(p, over=[generator, snapshot], by=gen_zone[zone])',
            {'zone'},
            id='an-over-list-joins-on-two-key-columns-at-once',
        ),
        pytest.param(
            'sum(p, over=generator, by=gen_bz[bus])',
            {'snapshot', 'bus'},
            id='a-value-column-not-named-is-not-read',
        ),
        pytest.param(
            'sum(p, over=generator, by=gen_bz[bus])',
            {'snapshot', 'bus'},
            id='by-and-over-compose',
        ),
        pytest.param(
            'sum(p, over=snapshot, by=rep_of[rep])',
            {'snapshot', 'generator'},
            id='a-map-into-its-own-dimension-keeps-the-frame',
        ),
        pytest.param('at(p, by=rep_of[rep])', {'snapshot', 'generator'}, id='and-so-does-its-lookup'),
        pytest.param('sum(p, over=[generator, snapshot])', set(), id='a-plain-sum-over-a-list'),
        pytest.param(
            'sum(p, over=[generator, snapshot], by=gen_bus[bus])',
            {'bus'},
            id='a-dim-the-relation-has-no-column-over-is-summed-after-the-group-by',
        ),
        pytest.param(
            "shift(p, along=snapshot, offset=1, edge='wrap', within=rep_of[rep])",
            {'snapshot', 'generator'},
            id='a-partition-into-its-own-dimension',
        ),
    ],
)
def test_dim_inference(expr, expected):
    assert _dims(expr) == expected


def _dims_with(expr: str, **overrides) -> frozenset[str]:
    s = _schema(**overrides)
    return dims_of(expression_of(expr, Namespace(s), 't'), s, 't')


@pytest.mark.parametrize(
    ('expr', 'expected'),
    [
        pytest.param(
            'sum(p, over=generator, by=connection[bus])',
            {'snapshot', 'bus'},
            id='a-sum-through-a-bare-relation-groups-by-a-key-column',
        ),
        pytest.param(
            'sum(load, over=bus, by=connection[generator])',
            {'snapshot', 'generator'},
            id='and-the-same-table-summed-the-other-way',
        ),
    ],
)
def test_a_bare_relation_is_summed_between_its_key_columns(expr, expected):
    """A bare relation holds no value column, so the column a sum groups by is a key column."""
    assert _dims_with(expr, **{'relations.connection': {'key': ['generator', 'bus']}}) == expected


def test_a_lookup_carries_the_whole_key_and_what_the_operand_brings_beside_it():
    """A lookup groups by the key however the call splits it, and a dim the operand carries and the lookup does not join on rides along.

    `gen_bz` is keyed by `generator` alone, so the whole key is grouped by; the
    operand's `snapshot` is neither joined on nor part of the key, and the
    result keeps it.
    """
    assert _dims('at(zone_load, by=gen_bz[zone])') == {'generator', 'snapshot'}


def test_a_join_opens_an_axis_for_the_column_it_drops_and_the_sum_over_it_closes_it():
    """A map into its own dimension drops and adds one dimension, so the join names the dropped column for the relation.

    Named for its dimension, the column the join drops and the column it
    groups by are one name, and the sum over the join takes away the dim the
    row keeps.
    """
    s = _schema()
    node = expression_of('sum(p, over=snapshot, by=rep_of[rep])', Namespace(s), 't')
    assert isinstance(node, Sum) and isinstance(node.operand, Join)
    assert node.over == ('rep_of.snapshot',), 'the sum stands over the axis the join opens'
    assert dims_of(node.operand, s, 't') == {'generator', 'snapshot', 'rep_of.snapshot'}, (
        'the join keeps the dropped column beside the dimension it groups by'
    )
    assert dims_of(node, s, 't') == {'generator', 'snapshot'}, 'and the sum over it leaves the frame the row keeps'


def test_a_sum_joins_on_a_key_column_and_a_value_column_together():
    """The columns a sum joins on and sums away are not one kind: it needs one key column, and may name a value column beside it."""
    assert _dims('sum(p * load, over=[generator, bus], by=gen_bz[zone])') == {'snapshot', 'zone'}


def test_a_dual_carries_the_constraints_own_frame():
    """`dual(c)` is a row dual at every coordinate of the constraint's declared `dims`."""
    s = _schema()
    assert _dims_with('dual(balance)') == frozenset(s.constraints['balance'].dims) == {'snapshot', 'bus'}


def test_a_bare_name_reaches_the_variable_a_dual_the_same_named_constraint():
    """Constraints sit outside the flat namespace, so only `dual()` reads the constraint store — a bare name never does, even one a constraint shares (#74)."""
    shadowing = {'variables.balance': {'dims': ['snapshot'], 'bounds': {'lower': 0}}}
    assert _dims_with('balance', **shadowing) == {'snapshot'}, 'a bare name resolves to the variable of that name'
    assert _dims_with('dual(balance)', **shadowing) == {'snapshot', 'bus'}, 'dual() alone reaches the constraint'


@pytest.mark.parametrize(
    ('expr', 'error', 'match'),
    [
        pytest.param(
            'sum(p, over=bus)',
            DimensionError,
            r'sum\(over=bus\) but the expression has dims',
            id='sum-over-an-absent-dim-is-an-error-not-a-noop',
        ),
        pytest.param(
            'sum(sum(p))',
            SchemaError,
            r'the expression is already a scalar',
            id='a-bare-sum-of-a-scalar-is-an-error-not-a-noop',
        ),
        pytest.param(
            'sum(sum(p, over=bus))',
            SchemaError,
            r'sum\(over=bus\) but the expression has dims',
            id='a-dim-fault-under-a-bare-sum-is-met-while-the-sum-is-built',
        ),
        pytest.param(
            'sum(sum(p, over=bus), over=generator)',
            DimensionError,
            r'sum\(over=bus\) but the expression has dims',
            id='and-the-same-fault-under-a-sum-over-a-named-dim-is-the-dim-rules',
        ),
        pytest.param(
            'sum(load, over=generator, by=gen_bus[bus])',
            DimensionError,
            r"sum\(by=gen_bus\[bus\]\) joins on \['generator'\] to sum it away",
            id='sum-requires-the-grouped-dim',
        ),
        pytest.param(
            "shift(cost, along=snapshot, offset=1, edge='wrap')",
            DimensionError,
            r'shift\(along=snapshot\) but the expression has dims',
            id='shift-requires-the-dim',
        ),
        pytest.param(
            "shift(p, along=snapshot, offset=cost, edge='wrap')",
            SchemaError,
            r'declared dtype: float',
            id='a-named-offset-is-integral-58',
        ),
        pytest.param(
            "shift(p, along=snapshot, offset=horizon, edge='wrap')",
            DimensionError,
            r'varies over the axis it steps along is a permutation rather than a lag',
            id='a-named-offset-does-not-span-the-axis-it-steps-along',
        ),
        pytest.param(
            'sum_back(p, along=snapshot, window=cost)',
            SchemaError,
            r'declared dtype: float',
            id='a-named-width-is-integral',
        ),
        pytest.param(
            'sum_back(p, along=snapshot, window=horizon)',
            DimensionError,
            r'no longer "the last n"',
            id='a-named-width-does-not-span-the-summed-axis',
        ),
        pytest.param(
            "shift(p, along=snapshot, offset=-spinup, edge='wrap')",
            SchemaError,
            r'negates a named offset',
            id='a-named-offset-is-not-negated-at-the-call-62',
        ),
        pytest.param(
            'sum_back(p, along=snapshot, window=-spinup)',
            SchemaError,
            r'which way a window reaches is the operator',
            id='a-named-width-has-no-direction-to-negate',
        ),
        pytest.param(
            "shift(p, along=snapshot, offset=bus_lead, edge='wrap')",
            DimensionError,
            r"varies over \['bus'\], which that coordinate does not carry",
            id='a-named-offset-is-read-where-the-expression-has-a-coordinate',
        ),
        pytest.param(
            'sum(cost, over=generator, by=gen_zone[zone])',
            DimensionError,
            r"sum\(by=gen_zone\[zone\]\) joins on \['snapshot'\]",
            id='a-grouped-sum-needs-the-keys-it-joins-on',
        ),
        pytest.param(
            "shift(cost, along=generator, offset=1, edge='wrap', within=gen_zone[zone])",
            DimensionError,
            r"within=gen_zone\[zone\]\) joins on \['snapshot'\]",
            id='a-partition-needs-the-keys-it-joins-on',
        ),
    ],
)
def test_an_ill_dimensioned_expression_is_rejected(expr, error, match):
    """The class says which pass refused: what resolution needs to build a node is a `SchemaError`, and a rule on a built tree's dims a `DimensionError`.

    A dim fault under a bare `sum()` is met while the sum is built, since the
    dims it reduces are the operand's, and the same fault under a sum over a
    named dim is met by the dim rules.
    """
    with pytest.raises(error, match=match):
        _dims(expr)


@pytest.mark.parametrize(
    ('expr', 'diag'),
    [
        pytest.param(
            'sum(p, over=diag[k], by=diag[z])',
            {'key': {'k': 'generator', 'j': 'generator', 'z': 'zone'}},
            id='a-sum-summing-away-a-column-over-a-dimension-it-also-joins-on',
        ),
    ],
)
def test_two_joined_columns_do_not_share_a_dimension(expr, diag):
    """The operand carries one coordinate per dimension, so the `over=` column and an unnamed key column cannot share one."""
    with pytest.raises(DimensionError, match=r"joins 'diag' on \[.*\] through more than one column"):
        _dims_with(expr, **{'relations.diag': diag})


@pytest.mark.parametrize(
    ('expr', 'relation', 'expected'),
    [
        pytest.param(
            'at(zone_cap, by=gen_zone[zone])',
            {'key': ['generator', 'snapshot'], 'values': 'zone'},
            {'generator', 'snapshot'},
            id='a-key-column-the-operand-lacks-arrives',
        ),
        pytest.param(
            'at(load, by=gen_zone[rep])',
            {'key': ['snapshot', 'generator'], 'values': {'rep': 'snapshot'}},
            {'bus', 'snapshot', 'generator'},
            id='a-key-column-over-the-dimension-the-read-column-matches-arrives',
        ),
    ],
)
def test_a_lookup_joins_on_the_key_columns_the_operand_carries_and_the_read_does_not_match(expr, relation, expected):
    """`at` joins on each key column over a dim the operand carries, unless the column it reads already matches that dim.

    `at(load, by=diag, over=rep, into=generator)` once joined on the key's
    `snapshot` beside `rep`, at the operand's one snapshot coordinate. The
    call names only the column it reads now, so the key's `snapshot` arrives
    and the result is `load` read at `rep(t, g)` for every `(t, g)`.
    """
    assert _dims_with(expr, **{'relations.gen_zone': relation}) == frozenset(expected), (
        'the frame is the operand less the dim read, plus the key'
    )


def test_an_outer_product_is_legal_and_carries_both_dim_sets():
    """Binary ops union. Requiring subset instead would reject the convex
    piecewise epigraph, which multiplies a per-segment slope by a per-snapshot
    variable on purpose. The guard is the constraint rule below: the *frame*
    has to declare the result."""
    assert _dims('cost + load') == {'generator', 'snapshot', 'bus'}, (
        'a binary operator unions its two sides rather than requiring one to contain the other'
    )


# ---------------------------------------------------------------------------
# declaration-level rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('patch', 'match'),
    [
        pytest.param(
            {'constraints.stray': {'dims': ['snapshot'], 'expression': 'p <= p_max'}},
            r"carries dims \['generator'\] that are not in its dims:",
            id='stray-dim-in-a-constraint',
        ),
        pytest.param(
            {'constraints.unused': {'dims': ['snapshot', 'generator', 'bus'], 'expression': 'p <= p_max'}},
            r"does not carry \['bus'\]",
            id='dims-dim-the-equation-never-uses',
        ),
        pytest.param(
            {'variables.cap': {'dims': ['generator'], 'where': 'load > 0'}},
            r"where-parameter 'load' reads dims \['bus', 'snapshot'\]",
            id='where-dim-outside-the-frame',
        ),
        pytest.param(
            {'variables.cap': {'dims': ['generator'], 'where': 'snapshot > 0'}},
            "where-dimension 'snapshot'",
            id='where-comparison-on-a-dim-outside-the-frame',
        ),
        pytest.param(
            {'variables.cap': {'dims': ['generator'], 'bounds': {'lower': 0, 'upper': 'load'}}},
            r"bounds.upper parameter 'load' has dims \['bus', 'snapshot'\]",
            id='bound-parameter-dim-outside-dims',
        ),
    ],
)
def test_an_ill_dimensioned_declaration_is_rejected(patch, match):
    with pytest.raises(DimensionError, match=match):
        _schema(**patch)


class TestTheEdgeRulesAreDecidedAtLoad:
    """A file accepted by one door and refused by the next is the bug these close (#193).

    Every rule here is decidable from the file: whether the operand carries a
    variable, whether the offset is named, what the edge is written as.
    """

    BASE: ClassVar[dict[str, Any]] = {
        'dimensions': {'t': {'dtype': 'int'}, 'g': {'dtype': 'str'}},
        'parameters': {'cap': {'dims': ['g']}, 'lead': {'dims': ['g'], 'dtype': 'int'}},
        'variables': {'p': {'dims': ['t', 'g'], 'bounds': {'lower': 0, 'upper': 1}}},
        'constraints': {'k': {'dims': ['t', 'g'], 'expression': 'p <= 1'}},
    }

    def _refused(self, expression: str) -> str:
        """The message `to_spec` refuses *expression* with — a `SchemaError`, since every rule here is resolution's."""
        raw = override(self.BASE, **{'constraints.k.expression': expression})
        with pytest.raises(SchemaError) as caught:
            to_spec(raw)
        return str(caught.value)

    @pytest.mark.parametrize(
        ('expression', 'fragment'),
        [
            pytest.param(
                'p <= shift(cap, along=g, offset=1)',
                'leaves vacated positions with no value',
                id='a-shift-over-data-with-no-edge',
            ),
            pytest.param(
                'p <= shift(p, along=t, offset=lead)',
                'per-entity offset cannot say yet',
                id='a-named-offset-with-no-edge',
            ),
            pytest.param(
                'p <= shift(p, along=t, offset=1, edge=2)',
                'only fill=0 is representable',
                id='a-nonzero-edge-over-a-variable',
            ),
            pytest.param(
                'p <= sum_back(p, along=t, window=2, edge=0)',
                "takes 'wrap' or nothing",
                id='a-numeric-edge-on-a-window',
            ),
            pytest.param(
                "p <= shift(p, along=t, offset=1.5, edge='wrap')",
                'must be a whole number',
                id='a-fractional-amount',
            ),
        ],
    )
    def test_an_edge_rule_is_refused_by_to_spec(self, expression, fragment):
        assert fragment in self._refused(expression)

    @pytest.mark.parametrize('width', ['0', '1.5', '-2'], ids=['zero', 'fractional', 'negative'])
    def test_a_literal_width_below_one_is_refused_by_to_spec(self, width):
        """A negative literal once slipped past the load-time test.

        The sign was stripped before the `at least 1` comparison, so `-2` was
        tested as `2` and reached lowering, which asserted (#222).
        """
        assert 'at least 1' in self._refused(f'p <= sum_back(p, along=t, window={width})')

    def test_a_zero_step_vacates_nothing_and_needs_no_edge(self):
        """`shift(x, offset=0)` reaches every coordinate from itself.

        The refusal above exists because vacated positions have no value; a
        literal zero vacates none, so there is nothing for an `edge=` to answer
        for. A *named* offset may be zero in the data and is not known here.
        """
        to_spec(override(self.BASE, **{'constraints.k.expression': 'p <= shift(cap, along=g, offset=0)'}))


# ---------------------------------------------------------------------------
# what a predicate reads
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('predicate', 'expected'),
    [
        pytest.param('p_max > 0', {'generator'}, id='a-parameter-through-its-own-dims'),
        pytest.param('snapshot == 0', {'snapshot'}, id='a-dimension-through-itself'),
        pytest.param('position(snapshot) == 0', {'snapshot'}, id='a-position-through-the-axis-it-counts'),
        pytest.param('snap_bus == "b1"', {'snapshot'}, id='a-relation-through-the-dim-it-maps-out-of'),
        pytest.param('gen_zone == "z1"', {'generator', 'snapshot'}, id='a-two-key-relation-through-both-keys'),
        pytest.param('gen_zone', {'generator', 'snapshot'}, id='a-bare-two-key-relation-the-same'),
        pytest.param('rep_of == 3', {'snapshot'}, id='a-map-into-its-own-dimension-through-its-key'),
        pytest.param(
            'position(snapshot, within=rep_of[rep]) == 0', {'snapshot'}, id='a-position-within-a-representative'
        ),
        pytest.param(
            'position(generator, within=gen_zone[zone]) == 0',
            {'generator', 'snapshot'},
            id='a-position-within-a-group-of-a-two-key-relation-reads-both-keys',
        ),
        pytest.param(
            'position(generator, within=gen_bz[zone]) == 0',
            {'generator'},
            id='a-position-within-one-named-value-column-reads-the-key',
        ),
        pytest.param('p_max > 0 AND snapshot == 0', {'generator', 'snapshot'}, id='a-conjunction-reads-both-sides'),
        pytest.param('NOT p_max > 0', {'generator'}, id='a-negation-reads-what-it-negates'),
        pytest.param('False', set(), id='a-literal-reads-nothing'),
    ],
)
def test_a_predicate_is_read_at_the_coordinates_its_leaves_are_read_at(namespace, predicate, expected):
    """The dim rule for the predicate side."""
    where = where_of(predicate, namespace, 'test')

    assert where is not None, 'a predicate the connectives cannot settle survives the fold'
    assert where.dims == expected


def test_a_predicate_that_admits_every_row_has_no_leaves_left_to_read(namespace):
    """`where_of` folds an always-true mask to `None`, so there is no node to ask."""
    assert where_of('True', namespace, 'test') is None, 'folded away, not a predicate over nothing'


def test_the_frame_check_and_the_reading_walk_the_same_leaves(namespace):
    """One rule, two readers — the check reports per leaf and so cannot take the union.

    A predicate outside the frame is refused by the *name* of the leaf that
    left it, and that leaf is one `Mask.dims` counted: a check passing a mask
    the builder then reads wider would be the divergence this shares a walk to
    prevent.
    """
    where = where_of('p_max > 0', namespace, 'test')
    assert where is not None

    assert where.dims == {'generator'}, 'read at the generator axis'
    with pytest.raises(DimensionError, match=r"where-parameter 'p_max' reads dims \['generator'\]"):
        _check_where_dims(where, frozenset({'snapshot'}), 'test')


@pytest.mark.parametrize(
    ('predicate', 'expected'),
    [
        pytest.param('p_max > 0', {'p_max'}, id='a-parameter-comparison-names-the-parameter'),
        pytest.param('spinup', {'spinup'}, id='a-parameter-bare-names-the-parameter'),
        pytest.param('p', {'p'}, id='a-variable-bare-names-the-variable'),
        pytest.param('snap_bus == "b1"', {'snap_bus'}, id='a-relation-comparison-names-the-relation'),
        pytest.param('gen_bus', {'gen_bus'}, id='a-relation-bare-names-the-relation'),
        pytest.param('snapshot == 0', set(), id='a-dimension-names-nothing-it-is-a-coordinate'),
        pytest.param('position(snapshot) == 0', set(), id='a-position-names-nothing'),
        pytest.param('p_max > 0 AND snapshot == 0', {'p_max'}, id='a-conjunction-drops-the-dimension-side'),
        pytest.param('p_max > 0 AND snap_bus == "b1"', {'p_max', 'snap_bus'}, id='a-conjunction-unions-both-names'),
        pytest.param('NOT p_max > 0', {'p_max'}, id='a-negation-names-what-it-negates'),
        pytest.param('False', set(), id='a-literal-names-nothing'),
    ],
)
def test_a_predicate_names_the_declarations_its_leaves_test(namespace, predicate, expected):
    """A dimension names no declaration — it is a coordinate — so `names_read` drops it where `dims` keeps it."""
    where = where_of(predicate, namespace, 'test')

    assert where is not None, 'a predicate the connectives cannot settle survives the fold'
    assert where.names_read == expected


def test_names_read_takes_both_sides_of_a_relation_pair():
    """The one leaf that names two declarations — two maps compared on the dimension they share.

    BASE has one relation per dimension, so the pair is built directly rather than
    resolved from a predicate string.
    """
    where = RelationPairComparison('from_bus', 'bus', 'to_bus', 'bus', '!=', ('line',))

    assert Mask(where).names_read == {'from_bus', 'to_bus'}, 'a relation pair names both maps it compares'
