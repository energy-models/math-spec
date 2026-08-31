# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Dim sets are a type system, checked before any data is bound.

Every case here used to build a model and solve it — wrongly, or larger than
the file reads as. None of them needs data to be caught.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

import pytest

from math_spec.dimensions import DimensionError, _check_where_dims, check_schema, dims_of
from math_spec.program import LookupPairComparisonNode, Mask
from math_spec.resolution import Namespace, expression_of, where_of
from math_spec.validation import to_spec
from tests.fixtures import OPERATOR_PROBES, override, schema_of

if TYPE_CHECKING:
    from math_spec.model import Spec

#: `fixtures.DISPATCH_MODEL` plus buses: a dim rule is mostly about an
#: expression carrying a dim its frame does not, which needs three dims to
#: state. `snap_bus` is over `snapshot` so it can partition the axis the
#: translations walk; `spinup` and `horizon` are the named amount that obeys
#: the position rules and the one that spans the axis walked; `bus_lead` is
#: over a dim `p` does not carry, so it is readable only through a `by=`.
BASE = {
    'dimensions': {
        'snapshot': {'dtype': 'int'},
        'generator': {'dtype': 'str'},
        'bus': {'dtype': 'str'},
    },
    'lookups': {
        'gen_bus': {'over': 'generator', 'into': 'bus'},
        'snap_bus': {'over': 'snapshot', 'into': 'bus'},
    },
    'parameters': {
        'p_max': {'dims': ['generator']},
        'cost': {'dims': ['generator']},
        'load': {'dims': ['snapshot', 'bus']},
        'spinup': {'dims': ['generator'], 'dtype': 'int'},
        'horizon': {'dims': ['snapshot'], 'dtype': 'int'},
        'bus_lead': {'dims': ['bus'], 'dtype': 'int'},
    },
    'variables': {'p': {'foreach': ['snapshot', 'generator'], 'bounds': {'lower': 0, 'upper': 'p_max'}}},
    'constraints': {
        'balance': {
            'foreach': ['snapshot', 'bus'],
            'expression': 'sum(p, by=gen_bus) == load',
        }
    },
    'objective': {'sense': 'minimize', 'expression': 'sum(p * cost)'},
}


def _schema(**overrides) -> Spec:
    return schema_of(BASE, **overrides)


def _dims(expr: str) -> frozenset[str]:
    s = _schema()
    return dims_of(expression_of(expr, s, Namespace.of(s), 't'), s, 't')


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
        ('sum(p, by=gen_bus)', {'snapshot', 'bus'}),
        ("shift(p, over=snapshot, offset=1, edge='wrap')", {'snapshot', 'generator'}),
        ("shift(p, over=snapshot, offset=spinup, edge='wrap')", {'snapshot', 'generator'}),
        ('sum_back(p, over=snapshot, within=spinup)', {'snapshot', 'generator'}),
        # the same offset a `by=` makes readable: one lag per group it maps into
        ("shift(p, over=snapshot, offset=bus_lead, edge='wrap', by=snap_bus)", {'snapshot', 'generator'}),
        ('sum_back(p, over=snapshot, within=bus_lead, by=snap_bus)', {'snapshot', 'generator'}),
        pytest.param('p + 1', {'snapshot', 'generator'}, id='a-scalar-broadcasts'),
    ],
)
def test_dim_inference(expr, expected):
    assert _dims(expr) == expected


def _dims_with(expr: str, **overrides) -> frozenset[str]:
    s = _schema(**overrides)
    return dims_of(expression_of(expr, s, Namespace.of(s), 't'), s, 't')


def test_a_dual_carries_the_constraints_own_frame():
    """`dual(c)` is a row dual at every coordinate of the constraint's declared `foreach`."""
    s = _schema()
    assert _dims_with('dual(balance)') == frozenset(s.constraints['balance'].foreach) == {'snapshot', 'bus'}


def test_a_bare_name_reaches_the_variable_a_dual_the_same_named_constraint():
    """Constraints sit outside the flat namespace, so only `dual()` reads the constraint store — a bare name never does, even one a constraint shares (#74)."""
    shadowing = {'variables.balance': {'foreach': ['snapshot'], 'bounds': {'lower': 0}}}
    assert _dims_with('balance', **shadowing) == {'snapshot'}, 'a bare name resolves to the variable of that name'
    assert _dims_with('dual(balance)', **shadowing) == {'snapshot', 'bus'}, 'dual() alone reaches the constraint'


@pytest.mark.parametrize(
    ('expr', 'match'),
    [
        pytest.param(
            'sum(p, over=bus)',
            r'sum\(over=bus\) but the expression has dims',
            id='sum-over-an-absent-dim-is-an-error-not-a-noop',
        ),
        pytest.param(
            'sum(sum(p))',
            r'the expression is already a scalar',
            id='a-bare-sum-of-a-scalar-is-an-error-not-a-noop',
        ),
        pytest.param(
            'sum(load, by=gen_bus)',
            r"sum\(by=gen_bus\) consumes 'generator', the dim it maps out of",
            id='sum-requires-the-grouped-dim',
        ),
        pytest.param(
            'sum(load * p, by=gen_bus)',
            'already carries',
            id='sum-into-a-dim-the-operand-already-carries',
        ),
        pytest.param(
            "shift(cost, over=snapshot, offset=1, edge='wrap')",
            r'shift\(over=snapshot\) but the expression has dims',
            id='shift-requires-the-dim',
        ),
        pytest.param(
            "shift(p, over=snapshot, offset=cost, edge='wrap')",
            r'declared dtype: float',
            id='a-named-offset-is-integral-58',
        ),
        pytest.param(
            "shift(p, over=snapshot, offset=horizon, edge='wrap')",
            r'varies along the axis it walks is a permutation rather than a lag',
            id='a-named-offset-does-not-span-the-axis-it-walks',
        ),
        pytest.param(
            'sum_back(p, over=snapshot, within=cost)',
            r'declared dtype: float',
            id='a-named-width-is-integral',
        ),
        pytest.param(
            'sum_back(p, over=snapshot, within=horizon)',
            r'no longer "the last n"',
            id='a-named-width-does-not-span-the-summed-axis',
        ),
        pytest.param(
            "shift(p, over=snapshot, offset=-spinup, edge='wrap')",
            r'negates a named offset',
            id='a-named-offset-is-not-negated-at-the-call-62',
        ),
        pytest.param(
            'sum_back(p, over=snapshot, within=-spinup)',
            r'which way a window reaches is the operator',
            id='a-named-width-has-no-direction-to-negate',
        ),
        pytest.param(
            "shift(p, over=snapshot, offset=bus_lead, edge='wrap')",
            r"varies over \['bus'\], which that coordinate does not carry",
            id='a-named-offset-is-read-where-the-expression-has-a-coordinate',
        ),
    ],
)
def test_an_ill_dimensioned_expression_is_rejected(expr, match):
    with pytest.raises(DimensionError, match=match):
        _dims(expr)


def test_an_outer_product_is_legal_and_carries_both_dim_sets():
    """Binary ops union. Requiring subset instead would reject the convex
    piecewise epigraph, which multiplies a per-segment slope by a per-snapshot
    variable on purpose. The guard is the constraint rule below: the *frame*
    has to declare the result."""
    assert _dims('cost + load') == {'generator', 'snapshot', 'bus'}


# ---------------------------------------------------------------------------
# declaration-level rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('patch', 'match'),
    [
        pytest.param(
            {'constraints.stray': {'foreach': ['snapshot'], 'expression': 'p <= p_max'}},
            r"carries dims \['generator'\] that are not in foreach",
            id='stray-dim-in-a-constraint',
        ),
        pytest.param(
            {'constraints.unused': {'foreach': ['snapshot', 'generator', 'bus'], 'expression': 'p <= p_max'}},
            r"does not carry \['bus'\]",
            id='foreach-dim-the-equation-never-uses',
        ),
        pytest.param(
            {'variables.cap': {'foreach': ['generator'], 'where': 'load > 0'}},
            r"where-parameter 'load' has dims \['bus', 'snapshot'\]",
            id='where-dim-outside-the-frame',
        ),
        pytest.param(
            {'variables.cap': {'foreach': ['generator'], 'where': 'snapshot > 0'}},
            "where-comparison on dimension 'snapshot'",
            id='where-comparison-on-a-dim-outside-the-frame',
        ),
        pytest.param(
            {'variables.cap': {'foreach': ['generator'], 'bounds': {'lower': 0, 'upper': 'load'}}},
            r"bounds.upper parameter 'load' has dims \['bus', 'snapshot'\]",
            id='bound-parameter-dim-outside-foreach',
        ),
    ],
)
def test_an_ill_dimensioned_declaration_is_rejected(patch, match):
    with pytest.raises(DimensionError, match=match):
        _schema(**patch)


@pytest.mark.parametrize('path', OPERATOR_PROBES, ids=lambda p: p.name)
def test_every_operator_probe_typechecks(path):
    check_schema(schema_of(path))


class TestTheEdgeRulesAreDecidedAtLoad:
    """`to_spec` refuses what `to_program` used to, so the two cannot disagree.

    Every rule here is decidable from the file — whether the operand carries a
    variable, whether the offset is named, what the edge is written as. A file
    accepted by one door and refused by the next is the bug these close (#193):
    a repository of models compiled in CI would pass, and only a consumer that
    built them would find out.
    """

    BASE: ClassVar[dict[str, Any]] = {
        'dimensions': {'t': {'dtype': 'int'}, 'g': {'dtype': 'str'}},
        'parameters': {'cap': {'dims': ['g']}, 'lead': {'dims': ['g'], 'dtype': 'int'}},
        'variables': {'p': {'foreach': ['t', 'g'], 'bounds': {'lower': 0, 'upper': 1}}},
        'constraints': {'k': {'foreach': ['t', 'g'], 'expression': 'p <= 1'}},
    }

    def _refused(self, expression: str) -> str:
        raw = override(self.BASE, **{'constraints.k.expression': expression})
        with pytest.raises(DimensionError) as caught:
            to_spec(raw)
        return str(caught.value)

    def test_a_shift_over_data_with_no_edge_is_refused_by_to_spec(self):
        assert 'leaves vacated positions with no value' in self._refused('p <= shift(cap, over=g, offset=1)')

    def test_a_named_offset_with_no_edge_is_refused_by_to_spec(self):
        assert 'per-entity offset cannot say yet' in self._refused('p <= shift(p, over=t, offset=lead)')

    def test_a_nonzero_edge_over_a_variable_is_refused_by_to_spec(self):
        assert 'only fill=0 is representable' in self._refused('p <= shift(p, over=t, offset=1, edge=2)')

    def test_a_numeric_edge_on_a_window_is_refused_by_to_spec(self):
        assert "takes 'wrap' or nothing" in self._refused('p <= sum_back(p, over=t, within=2, edge=0)')

    def test_a_fractional_amount_is_refused_by_to_spec(self):
        assert 'must be a whole number' in self._refused("p <= shift(p, over=t, offset=1.5, edge='wrap')")

    @pytest.mark.parametrize('width', ['0', '1.5', '-2'], ids=['zero', 'fractional', 'negative'])
    def test_a_literal_width_below_one_is_refused_by_to_spec(self, width):
        """A negative literal once slipped past the load-time test.

        The sign was stripped before the `at least 1` comparison, so `-2` was
        tested as `2` and reached lowering, which asserted (#222).
        """
        assert 'at least 1' in self._refused(f'p <= sum_back(p, over=t, within={width})')

    def test_a_zero_step_vacates_nothing_and_needs_no_edge(self):
        """`shift(x, offset=0)` reaches every coordinate from itself.

        The refusal above exists because vacated positions have no value; a
        literal zero vacates none, so there is nothing for an `edge=` to answer
        for. A *named* offset may be zero in the data and is not known here.
        """
        raw = override(self.BASE, **{'constraints.k.expression': 'p <= shift(cap, over=g, offset=0)'})
        assert to_spec(raw) is not None, 'a zero step is none at all, so no edge policy is owed'


# ---------------------------------------------------------------------------
# what a predicate reads
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('predicate', 'expected'),
    [
        pytest.param('p_max > 0', {'generator'}, id='a-parameter-through-its-own-dims'),
        pytest.param('snapshot == 0', {'snapshot'}, id='a-dimension-through-itself'),
        pytest.param('position(snapshot) == 0', {'snapshot'}, id='a-position-through-the-axis-it-counts'),
        pytest.param('snap_bus == "b1"', {'snapshot'}, id='a-lookup-through-the-dim-it-maps-out-of'),
        pytest.param('p_max > 0 AND snapshot == 0', {'generator', 'snapshot'}, id='a-conjunction-reads-both-sides'),
        pytest.param('NOT p_max > 0', {'generator'}, id='a-negation-reads-what-it-negates'),
        pytest.param('False', set(), id='a-literal-reads-nothing'),
    ],
)
def test_a_predicate_is_read_at_the_coordinates_its_leaves_are_read_at(predicate, expected):
    """The dim rule for the predicate side, which a consumer masking rows needs.

    Stated here rather than in whichever engine builds the mask: two consumers
    answering it differently would restrict the same model differently, with no
    error anywhere to say which was meant.
    """
    schema = to_spec(BASE)
    ns = Namespace.of(schema)

    where = where_of(predicate, ns, 'test')

    assert where is not None, 'a predicate the connectives cannot settle survives the fold'
    assert where.dims == expected, f'{predicate!r} reads {expected}'


def test_a_predicate_that_admits_every_row_has_no_leaves_left_to_read():
    """`where_of` folds an always-true mask to `None`, so there is no node to ask."""
    schema = to_spec(BASE)

    assert where_of('True', Namespace.of(schema), 'test') is None, 'folded away, not a predicate over nothing'


def test_the_frame_check_and_the_reading_walk_the_same_leaves():
    """One rule, two readers — the check reports per leaf and so cannot take the union.

    A predicate outside the frame is refused by the *name* of the leaf that
    left it, and that leaf is one `Mask.dims` counted: a check passing a mask
    the builder then reads wider would be the divergence this shares a walk to
    prevent.
    """
    schema = to_spec(BASE)
    ns = Namespace.of(schema)

    where = where_of('p_max > 0', ns, 'test')
    assert where is not None

    assert where.dims == {'generator'}, 'read at the generator axis'
    with pytest.raises(DimensionError, match=r"where-parameter 'p_max' has dims \['generator'\]"):
        _check_where_dims(where, frozenset({'snapshot'}), 'test')


@pytest.mark.parametrize(
    ('predicate', 'expected'),
    [
        pytest.param('p_max > 0', {'p_max'}, id='a-parameter-comparison-names-the-parameter'),
        pytest.param('spinup', {'spinup'}, id='a-parameter-bare-names-the-parameter'),
        pytest.param('p', {'p'}, id='a-variable-bare-names-the-variable'),
        pytest.param('snap_bus == "b1"', {'snap_bus'}, id='a-lookup-comparison-names-the-lookup'),
        pytest.param('gen_bus', {'gen_bus'}, id='a-lookup-bare-names-the-lookup'),
        pytest.param('snapshot == 0', set(), id='a-dimension-names-nothing-it-is-a-coordinate'),
        pytest.param('position(snapshot) == 0', set(), id='a-position-names-nothing'),
        pytest.param('p_max > 0 AND snapshot == 0', {'p_max'}, id='a-conjunction-drops-the-dimension-side'),
        pytest.param('p_max > 0 AND snap_bus == "b1"', {'p_max', 'snap_bus'}, id='a-conjunction-unions-both-names'),
        pytest.param('NOT p_max > 0', {'p_max'}, id='a-negation-names-what-it-negates'),
        pytest.param('False', set(), id='a-literal-names-nothing'),
    ],
)
def test_a_predicate_names_the_declarations_its_leaves_test(predicate, expected):
    """The name rule for the predicate side, the complement of `Mask.dims`'s dim rule.

    A dimension names no declaration — it is a coordinate, not data to feed —
    so `names_read` drops it where `dims` keeps it, and the two together
    say of a leaf both where it is read and what it reads.
    """
    schema = to_spec(BASE)
    where = where_of(predicate, Namespace.of(schema), 'test')

    assert where is not None, 'a predicate the connectives cannot settle survives the fold'
    assert where.names_read == expected, f'{predicate!r} names {expected}'


def test_names_read_takes_both_sides_of_a_lookup_pair():
    """The one leaf that names two declarations — two maps compared on the dimension they share.

    BASE has one lookup per dimension, so the pair is built directly rather than
    resolved from a predicate string.
    """
    where = LookupPairComparisonNode('from_bus', 'to_bus', 'line', '!=')

    assert Mask(where).names_read == {'from_bus', 'to_bus'}, 'a lookup pair names both maps it compares'
