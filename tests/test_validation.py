# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Tests for load-time validation of expression and where strings."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pytest

from math_spec._yaml import parse_yaml
from math_spec.errors import LanguageError
from math_spec.resolution import Namespace, where_of
from math_spec.validation import load_model, validate_expressions
from math_spec.where_parser import DimensionPositionNode
from tests.fixtures import DISPATCH_MODEL, OPERATOR_PROBES, override

if TYPE_CHECKING:
    from math_spec.model import Model


def _schema(**overrides) -> Model:
    base = {
        'dimensions': {'g': {'values': ['wind', 'solar']}},
        'parameters': {'p_max': {'dims': ['g']}},
        'variables': {'p': {'foreach': ['g']}},
    }
    base.update(overrides)
    return load_model(base)


class TestValidateExpressions:
    def test_valid_schema_passes(self):
        schema = _schema(
            constraints={'cap': {'foreach': ['g'], 'expression': 'p <= p_max'}},
            objective={'expression': 'sum(p, over=g)'},
        )
        validate_expressions(schema)

    @pytest.mark.parametrize(
        ('overrides', 'fragments'),
        [
            pytest.param(
                {'constraints': {'cap': {'foreach': ['g'], 'expression': 'q <= p_max'}}},
                ("'q' not found", "Constraint 'cap'", 'p_max'),
                id='an-unknown-name-in-a-constraint',
            ),
            pytest.param(
                {'constraints': {'cap': {'foreach': ['g'], 'expression': 'p + p_max'}}},
                ('exactly one comparison',),
                id='a-constraint-without-a-comparison',
            ),
            pytest.param(
                {'objective': {'expression': 'sum(p, over=g) <= 5'}},
                ('must not contain a comparison',),
                id='an-objective-with-a-comparison',
            ),
            pytest.param(
                {'constraints': {'cap': {'foreach': ['g'], 'expression': 'p_max <= 1'}}},
                ('decides nothing', "Constraint 'cap'", "'p_max <= 1'"),
                id='a-comparison-with-no-variable-in-it',
            ),
            pytest.param(
                {'objective': {'expression': 'frobnicate(p, over=g)'}},
                ("Unknown operator 'frobnicate'",),
                id='an-unknown-operator',
            ),
            pytest.param(
                {'constraints': {'cap': {'foreach': ['g'], 'expression': 'p * p * p <= p_max'}}},
                ("Constraint 'cap'", 'this product is degree 3'),
                id='a-cubic-constraint',
            ),
            pytest.param(
                {'objective': {'expression': 'sum(p ** 2, over=g)'}},
                ('The objective', '`**` is not in the language over variables'),
                id='a-variable-under-a-power',
            ),
            pytest.param(
                {'expressions': {'sq': 'p * p'}},
                ("Named expression 'sq'", 'which is degree 2'),
                id='a-quadratic-named-expression',
            ),
            pytest.param(
                {'constraints': {'cap': {'foreach': ['g'], 'where': 'p_max >', 'expression': 'p <= p_max'}}},
                ('Failed to parse where string',),
                id='a-malformed-where-string',
            ),
            # Used to evaluate to False, which built an empty model in the eager
            # lane and raised in the relational one — one language, two answers.
            # Resolution makes it a load error for both.
            pytest.param(
                {'constraints': {'cap': {'foreach': ['g'], 'where': 'not_a_param > 0', 'expression': 'p <= p_max'}}},
                ("'not_a_param' not found",),
                id='an-unknown-name-in-a-where',
            ),
        ],
    )
    def test_a_bad_declaration_is_refused_at_load(self, overrides, fragments):
        with pytest.raises(LanguageError) as exc:
            _schema(**overrides)
        for fragment in fragments:
            assert fragment in str(exc.value), f'the refusal has to carry {fragment!r}'

    def test_the_objective_and_a_constraint_take_degree_two(self):
        _schema(
            constraints={'floor': {'foreach': ['g'], 'expression': 'p * p >= 1'}},
            objective={'expression': 'sum(p * p * p_max, over=g)'},
        )

    def test_dim_name_kwarg_not_flagged(self):
        """Keyword-arg names are dimension names, not data references."""
        schema = _schema(
            objective={'expression': 'sum(p, over=g)'},
        )
        validate_expressions(schema)

    def test_multiple_errors_collected(self):
        with pytest.raises(LanguageError) as exc_info:
            _schema(
                constraints={
                    'a': {'foreach': ['g'], 'expression': 'q <= 1'},
                    'b': {'foreach': ['g'], 'expression': 'p + 1'},
                },
            )
        msg = str(exc_info.value)
        assert "'q' not found" in msg
        assert 'exactly one comparison' in msg


class TestDimensionKwargs:
    """A dim kwarg that names nothing is a silent no-op, not an error.

    ``sum(p, over=snapshto)`` used to build a model that solved and was wrong —
    both lanes agree on the no-op, so nothing downstream caught it.
    """

    @staticmethod
    def _schema(expression: str, foreach: list[str] | None = None) -> Model:
        """A model over (snapshot, generator), with `zone` a lookup into `bus`.

        `zone` deliberately targets a dim `p` does *not* carry: grouping into
        one it already has needs that dim twice, which is its own error.
        """
        foreach = ['snapshot'] if foreach is None else foreach  # an explicit [] is a scalar constraint
        return load_model(
            {
                'dimensions': {
                    'snapshot': {'dtype': 'int'},
                    'bus': {'values': ['n']},
                    'generator': {'values': ['wind']},
                },
                'lookups': {'zone': {'over': 'generator', 'into': 'bus'}},
                'parameters': {'load': {'dims': ['snapshot']}},
                'variables': {'p': {'foreach': ['snapshot', 'generator']}},
                'constraints': {'c': {'foreach': foreach, 'expression': expression}},
            }
        )

    @pytest.mark.parametrize(
        ('expression', 'fragments'),
        [
            pytest.param('sum(p, over=snapshto) == load', ('silent no-op', 'sum(over=snapshto)'), id='sum-over-typo'),
            pytest.param(
                'sum(p, by=bus) == load',
                ("'bus' is a dimension, and by= takes a lookup",),
                id='by-names-a-dimension',
            ),
            pytest.param(
                'sum(p, by=zne) == load',
                ('does not name a lookup', "Lookups: ['zone']"),
                id='by-lookup-typo',
            ),
            pytest.param(
                'shift(p, over=snapshto, offset=1) == load',
                ('does not name a declared dimension',),
                id='shift-over-typo',
            ),
        ],
    )
    def test_a_dim_kwarg_typo_is_rejected(self, expression, fragments):
        with pytest.raises(LanguageError) as exc:
            validate_expressions(self._schema(expression))
        for fragment in fragments:
            assert fragment in str(exc.value), f'the refusal has to carry {fragment!r}'

    @pytest.mark.parametrize(
        ('expression', 'foreach'),
        [
            pytest.param('sum(p, over=generator) == load', ['snapshot'], id='a-sum'),
            pytest.param('sum(p, by=zone) == load', ['snapshot', 'bus'], id='a-grouped-sum'),
            pytest.param(
                "shift(p, over=snapshot, offset=1, edge='wrap') == load",
                ['snapshot', 'generator'],
                id='a-wrapping-shift',
            ),
            pytest.param('shift(p, over=snapshot, offset=1) == load', ['snapshot', 'generator'], id='a-bare-shift'),
        ],
    )
    def test_declared_dimensions_still_pass(self, expression, foreach):
        validate_expressions(self._schema(expression, foreach))

    def test_macro_formals_are_not_mistaken_for_dimensions(self):
        """A formal in a dim position is legal inside the template body."""
        schema = load_model(
            {
                'dimensions': {'generator': {'values': ['wind']}},
                'parameters': {'cost': {'dims': ['generator']}},
                'variables': {'p': {'foreach': ['generator']}},
                'macros': {
                    'ws': {
                        'args': ['array', 'weights'],
                        'kwargs': ['over'],
                        'template': 'sum(array * weights, over=over)',
                    }
                },
                'objective': {'sense': 'minimize', 'expression': 'ws(p, cost, over=generator)'},
            }
        )
        validate_expressions(schema)

    @pytest.mark.parametrize(
        ('dtype', 'values', 'match'),
        [
            ('str', [datetime.date(2024, 1, 1)], 'has type date'),
            ('str', [750], 'has type int'),
            ('int', ['alpha'], 'has type str'),
            ('int', [True], 'has type bool'),
        ],
    )
    def test_a_coordinate_must_be_its_declared_dtype(self, dtype, values, match):
        """Nothing checked `values` against `dtype`, so a coordinate YAML had
        resolved to another type failed to join the user's data — and row
        absence is the structural zero, so the model solved a smaller problem.
        """
        with pytest.raises(LanguageError, match=match):
            _schema(dimensions={'g': {'dtype': dtype, 'values': values}})

    @pytest.mark.parametrize(
        ('dtype', 'values'),
        [
            ('str', ['no', 'se']),
            ('datetime', [datetime.date(2024, 1, 1)]),
            ('float', [1, 2.5]),
            ('int', [0, 1]),
        ],
    )
    def test_a_coordinate_of_the_declared_dtype_passes(self, dtype, values):
        validate_expressions(_schema(dimensions={'g': {'dtype': dtype, 'values': values}}))

    @pytest.mark.parametrize(
        ('dtype', 'where', 'match'),
        [
            ('datetime', 'g > 0', 'compares against the epoch'),
            ('str', 'g > 3', 'matches no label'),
            ('int', "g > 'x'", 'matches nothing'),
            ('datetime', "g > 'not-a-date'", 'is not an ISO date'),
        ],
    )
    def test_a_where_comparison_must_match_the_declared_dtype(self, dtype, where, match):
        """The same guard as above, one construct over — and this one was
        silent (#460).

        `_check_dimension_values` guarded a dimension's declared `values:`
        against its dtype; a `where` comparison against that same dimension had
        no such guard. polars compares a datetime column to an integer as an
        offset from the epoch, so `snapshot > 0` quietly meant "after
        1970-01-01" and dropped every earlier coordinate — and row absence is
        the structural zero, so the model solved a smaller problem with no
        error anywhere.
        """
        with pytest.raises(LanguageError, match=match):
            _schema(dimensions={'g': {'dtype': dtype}}, variables={'p': {'foreach': ['g'], 'where': where}})


class TestArithmeticDtype:
    """A name in an expression has to be a number, which its `dtype` says.

    The dtype rules reached three positions — what a `where` comparison is
    checked against, what a bare `where` on a name means, and whether a named
    offset counts positions — and an ordinary *value* position was not among
    them. So a label stood as a coefficient and as a divisor, and the file
    declared a model no column could build: whether the engine multiplied a
    string, cast it, or raised something out of its own exception tree was left
    to the lane, this far from the declaration that was wrong.
    """

    @staticmethod
    def _schema(dtype: str, expression: str) -> Model:
        return load_model(
            {
                'dimensions': {'g': {'values': ['wind', 'solar']}},
                'parameters': {'p_max': {'dims': ['g']}, 'a': {'dims': ['g'], 'dtype': dtype}},
                'variables': {'p': {'foreach': ['g']}},
                'constraints': {'cap': {'foreach': ['g'], 'expression': expression}},
            }
        )

    @pytest.mark.parametrize('dtype', ['str', 'bool'])
    @pytest.mark.parametrize(
        'expression',
        [
            pytest.param('a * p <= p_max', id='a-coefficient'),
            pytest.param('p / a <= p_max', id='a-divisor'),
            pytest.param('p + a <= p_max', id='a-term'),
            pytest.param('-a * p <= p_max', id='a-negated-factor'),
            pytest.param('sum(a * p, over=g) <= 1', id='under-an-operator'),
        ],
    )
    def test_a_label_or_a_flag_is_not_a_value(self, dtype, expression):
        with pytest.raises(LanguageError, match=f'declared dtype: {dtype}'):
            self._schema(dtype, expression)

    @pytest.mark.parametrize('dtype', ['float', 'int'])
    def test_a_number_is(self, dtype):
        self._schema(dtype, 'a * p <= p_max')

    @pytest.mark.parametrize(
        ('dtype', 'where'),
        [
            ('str', "a == 'wind'"),
            ('bool', 'a'),
            ('bool', 'NOT a'),
        ],
    )
    def test_the_position_it_is_declared_for_still_takes_it(self, dtype, where):
        """The refusal is about arithmetic, not about the dtype: selecting with
        a label and masking with a flag are what those two columns are for."""
        load_model(
            {
                'dimensions': {'g': {'values': ['wind', 'solar']}},
                'parameters': {'p_max': {'dims': ['g']}, 'a': {'dims': ['g'], 'dtype': dtype}},
                'variables': {'p': {'foreach': ['g'], 'where': where}},
                'constraints': {'cap': {'foreach': ['g'], 'expression': 'p <= p_max'}},
            }
        )

    def test_a_named_amount_keeps_its_own_sentence(self):
        """An `offset=` is a value position with a *stricter* rule of its own —
        a count of positions is integral, not merely numeric — and one that can
        name the axis being walked. This pass leaves that position to it, so
        the better sentence is still the one that arrives.
        """
        with pytest.raises(LanguageError, match='counts positions along'):
            load_model(
                {
                    'dimensions': {'t': {'dtype': 'int', 'values': [0, 1]}},
                    'parameters': {'cap': {'dims': ['t']}, 'lag': {'dims': [], 'dtype': 'str'}},
                    'variables': {'p': {'foreach': ['t']}},
                    'constraints': {
                        'c': {'foreach': ['t'], 'expression': "shift(p, over=t, offset=lag, edge='wrap') <= cap"}
                    },
                }
            )


class TestVersion:
    """`version:` — the field, and the policy that gives it meaning (#67).

    The field alone would be cargo cult: what makes it worth carrying is that
    an unknown version is *refused* rather than interpreted. Everything else
    here follows from that.
    """

    def _model(self, **top):
        return {
            **top,
            'dimensions': {'t': {'dtype': 'int', 'values': [0, 1]}},
            'parameters': {'c': {'dims': ['t']}},
            'variables': {'x': {'foreach': ['t'], 'bounds': {'lower': 0, 'upper': 1}}},
            'constraints': {'r': {'foreach': ['t'], 'expression': 'x <= 1'}},
            'objective': {'sense': 'maximize', 'expression': 'sum(x * c)'},
        }

    def test_absent_means_zero(self):
        """Additive by design: every file written before the field stays valid,
        so adding it needed no migration of examples, ports or fixtures."""
        assert load_model(self._model()).version == 0

    def test_zero_is_the_unstable_surface(self):
        assert load_model(self._model(version=0)).version == 0

    def test_an_unknown_version_is_refused_not_interpreted(self):
        """A file from the future must not be read by an older reader — that is
        the whole reason the field exists, and the only thing it does."""
        with pytest.raises(LanguageError) as exc:
            load_model(self._model(version=1))

        message = str(exc.value)
        assert 'declares version 1' in message
        assert 'understands [0]' in message, 'the error has to say what this reader can read'
        assert 'Upgrade math_spec' in message, 'and what to do about it'

    def test_the_version_gates_no_behaviour(self):
        """Reject-only. Two files differing only in a *declared* supported
        version must build the same model — the field never selects a surface.
        """
        bare = load_model(self._model())
        declared = load_model(self._model(version=0))
        assert bare.model_dump(exclude={'version'}) == declared.model_dump(exclude={'version'})


class TestPositionResolves:
    """`position(dim)` — the conversion #32 put on the left-hand side.

    The dimension has to be one, and a `by=` has to be a lookup over *that*
    dimension: the groups are its target's labels, and a lookup over anything
    else carries no row for a position to be a position in.
    """

    @staticmethod
    def _schema() -> Model:
        return load_model(
            {
                'dimensions': {'snapshot': {'dtype': 'int'}, 'period': {'dtype': 'int', 'values': [2030, 2040]}},
                'lookups': {
                    'period_of': {'over': 'snapshot', 'into': 'period'},
                    'starts_at': {'over': 'period', 'into': 'snapshot'},
                },
                'parameters': {'load': {'dims': ['snapshot']}},
                'variables': {'p': {'foreach': ['snapshot']}},
            }
        )

    @pytest.mark.parametrize(
        ('mask', 'position', 'by'),
        [
            ('position(snapshot) == 0', 0, None),
            ('position(snapshot) > 0', 0, None),
            ('position(snapshot) == -1', -1, None),
            ('position(snapshot) < -2', -2, None),
            ('position(snapshot, by=period_of) == 0', 0, 'period_of'),
        ],
        ids=['first', 'after the first', 'last', 'before the final two', 'first of each period'],
    )
    def test_it_resolves(self, mask: str, position: int, by: str | None):
        schema = self._schema()
        node = where_of(mask, Namespace.of(schema), 'the mask')
        assert isinstance(node, DimensionPositionNode)
        assert node.name == 'snapshot'
        assert node.position == position
        assert node.by == by

    @pytest.mark.parametrize(
        ('mask', 'fragments'),
        [
            ('position(load) == 0', ["counts along a dimension's coordinates", "'load' is a parameter"]),
            ('position(nope) == 0', ["'nope' is not declared"]),
            ('position(snapshot, by=load) == 0', ['groups by', '``by=`` takes a lookup']),
            ('position(snapshot, by=starts_at) == 0', ["along 'snapshot'", "lookup over 'period'"]),
        ],
        ids=['a parameter', 'undeclared', 'by= is not a lookup', 'by= is over another dim'],
    )
    def test_it_refuses(self, mask: str, fragments: list[str]):
        schema = self._schema()
        with pytest.raises(LanguageError) as excinfo:
            where_of(mask, Namespace.of(schema), 'the mask')
        for fragment in fragments:
            assert fragment in str(excinfo.value)


#: Two dimensions, a groupable and a label-space lookup, a numeric and a boolean
#: parameter, a variable on each frame — one declaration of every kind a rule
#: below can name.
RULES_BASE = {
    'dimensions': {'g': {'values': ['a', 'b']}, 'h': {'values': ['x', 'y']}},
    'lookups': {'lk': {'over': 'g', 'into': 'h'}, 'tag': {'over': 'g', 'dtype': 'str'}},
    'parameters': {'c': {'dims': ['g']}, 'flag': {'dims': ['g'], 'dtype': 'bool'}},
    'variables': {'p': {'foreach': ['g']}, 'q': {'foreach': ['g', 'h']}},
}


class TestDeclarationRules:
    """Every cross-declaration rule the schema decides, one row each."""

    @pytest.mark.parametrize(
        ('patch', 'fragments'),
        [
            pytest.param(
                {'sos': {'s': {'variable': 'p', 'over': 'z', 'type': 1}}},
                ("undeclared dimension 'z'",),
                id='sos-over-undeclared',
            ),
            pytest.param(
                {'sos': {'s': {'variable': 'c', 'over': 'g', 'type': 1}}},
                ("'c' is not a declared variable",),
                id='sos-over-a-parameter',
            ),
            pytest.param(
                {'sos': {'s': {'variable': 'p', 'over': 'h', 'type': 1}}},
                ("over 'h' is not a dim of variable 'p'",),
                id='sos-along-a-dim-the-variable-lacks',
            ),
            pytest.param(
                {
                    'sos': {
                        's': {'variable': 'p', 'over': 'g', 'type': 1},
                        't': {'variable': 'p', 'over': 'g', 'type': 2},
                    }
                },
                ("already carries the set declared by 's'",),
                id='two-sets-on-one-variable',
            ),
            pytest.param(
                {'sos': {'s': {'variable': 'p', 'over': 'g', 'type': 3}}},
                ('sos type must be 1 or 2, got 3',),
                id='sos-of-order-three',
            ),
            pytest.param(
                {'sos': {'s': {'variable': 'p', 'over': 'g', 'type': 1, 'big_m': 0}}},
                ('big_m must be a positive, finite number',),
                id='sos-big-m-zero',
            ),
            pytest.param(
                {'sos': {'s': {'variable': 'p', 'over': 'g', 'type': 1, 'big_m': float('inf')}}},
                ('big_m must be a positive, finite number',),
                id='sos-big-m-infinite',
            ),
            pytest.param(
                {'lookups.both': {'over': 'g', 'into': 'h', 'dtype': 'int'}},
                ('exactly one of',),
                id='lookup-both-kinds',
            ),
            pytest.param({'lookups.neither': {'over': 'g'}}, ('exactly one of',), id='lookup-neither-kind'),
            pytest.param({'lookups.lk.over': 'z'}, ("over undeclared dimension 'z'",), id='lookup-over-undeclared'),
            pytest.param({'lookups.lk.into': 'z'}, ("targets undeclared dimension 'z'",), id='lookup-into-undeclared'),
            pytest.param({'lookups.lk.into': 'g'}, ("maps 'g' into itself",), id='lookup-into-itself'),
            pytest.param(
                {'lookups.g': {'over': 'h', 'into': 'g'}},
                ("Lookup 'g' collides with the dimension",),
                id='lookup-named-after-a-dimension',
            ),
            pytest.param(
                {'lookups.lk.values': {'zz': 'x'}},
                ("declares values for ['zz'], which are not labels of 'g'",),
                id='lookup-map-from-a-stranger',
            ),
            pytest.param(
                {'lookups.lk.values': {'a': 'zz'}},
                ("maps to 'zz', which are not labels of 'h'",),
                id='lookup-map-to-a-stranger',
            ),
            pytest.param(
                {'lookups.tag.values': {'a': 7}},
                ("Lookup 'tag': value 7 has type int, but dtype is 'str'",),
                id='lookup-map-to-the-wrong-dtype',
            ),
            pytest.param(
                {'variables.p.absence': 'zero'}, ('absence: zero needs a `where:`',), id='absence-without-a-mask'
            ),
            pytest.param(
                {'variables.p.bounds.upper': 'c * 2'},
                ('not an expression', 'Precompute it as a parameter'),
                id='a-bound-that-is-an-expression',
            ),
            pytest.param(
                {'variables.p.bounds.upper': 'nope'},
                ("'nope' is not a declared parameter",),
                id='a-bound-naming-nothing',
            ),
            pytest.param(
                {'variables.p.bounds.upper': 'flag'},
                ("bounds.upper: 'flag' is a bool parameter, and a bound is a number",),
                id='a-bound-naming-a-flag',
            ),
            pytest.param({'variables.p.bounds.lower': float('nan')}, ('bounds.lower is nan',), id='a-nan-bound'),
            pytest.param({'variables.p.bounds.lower': True}, ('bounds.lower is a boolean',), id='a-boolean-bound'),
            pytest.param(
                {'variables.p.foreach': ['g', 'g']},
                ("Variable 'p' names dimension 'g' twice",),
                id='foreach-repeats-a-dim',
            ),
            pytest.param(
                {'parameters.c.dims': ['g', 'g']}, ("Parameter 'c' names dimension 'g' twice",), id='dims-repeat-a-dim'
            ),
            pytest.param(
                {'dimensions.g.values': ['a', 'b', 'a']},
                ("Dimension 'g' declares label 'a' twice",),
                id='values-repeat-a-label',
            ),
            pytest.param(
                {'variables.p.where': 'p'},
                ('asks whether it exists in its own where',),
                id='a-mask-naming-its-own-variable',
            ),
            pytest.param(
                {'dimensions.g.values': [['a'], 'b'], 'lookups.lk.values': {'b': 'x'}},
                ("Dimension 'g': value ['a'] has type list",),
                id='an-unhashable-label-under-a-declared-map',
            ),
            pytest.param(
                {'sos': {'s': {'variable': 'p', 'over': 'g', 'type': [1]}}},
                ('sos type must be 1 or 2, got [1]',),
                id='sos-type-a-list',
            ),
            pytest.param(
                {'sos': {'s': {'variable': 'p', 'over': 'g', 'type': True}}},
                ('sos type must be 1 or 2, got True',),
                id='sos-type-a-boolean',
            ),
            pytest.param(
                {'sos': {'s': {'variable': 'p', 'over': 'g', 'type': 1.0}}},
                ('sos type must be 1 or 2, got 1.0',),
                id='sos-type-a-float',
            ),
            pytest.param(
                {
                    'dimensions.bp': {'dtype': 'int'},
                    'parameters.bx': {'dims': ['bp']},
                    'parameters.by': {'dims': ['bp']},
                    'piecewise': {'cv': {'over': 'bp', 'links': [['p', 'bx'], ['q', 'by']], 'method': ['lp']}},
                },
                ("unknown piecewise method ['lp']",),
                id='piecewise-method-a-list',
            ),
            pytest.param(
                {'variables.p.boundz': {'lower': 0}},
                ("unknown key 'boundz'", 'bounds'),
                id='a-misspelt-key-names-the-near-miss',
            ),
            pytest.param(
                {'variables.p.foreach': ['g', 'z']}, ("references undeclared dimension 'z'",), id='foreach-undeclared'
            ),
            pytest.param({'parameters.c.dims': ['z']}, ("references undeclared dimension 'z'",), id='dims-undeclared'),
            pytest.param(
                {'parameters.p': {'dims': ['g']}},
                ("Variable 'p' collides with the parameter",),
                id='one-name-two-kinds',
            ),
        ],
    )
    def test_a_declaration_the_schema_refuses(self, patch, fragments):
        with pytest.raises(LanguageError) as exc:
            load_model(override(RULES_BASE, **patch))
        for fragment in fragments:
            assert fragment in str(exc.value), f'the refusal has to carry {fragment!r}'

    @pytest.mark.parametrize(
        ('patch', 'fragments'),
        [
            pytest.param(
                {'objective': {'expression': 'sum(g + p, over=g)'}},
                ("'g' is a dimension, and a dimension is not a value",),
                id='a-dimension-as-a-value',
            ),
            pytest.param(
                {'objective': {'expression': 'sum(lk + p, over=g)'}},
                ("'lk' is a lookup, and a lookup is structure",),
                id='a-lookup-as-a-value',
            ),
            pytest.param(
                {'objective': {'expression': 'sum(shift(p, over=g, offset=1, edge=wrap), over=g)'}},
                ('is a bare name where a keyword belongs',),
                id='a-bare-edge-keyword',
            ),
            pytest.param(
                {'objective': {'expression': "sum(shift(p, over=g, offset=1, edge='foo'), over=g)"}},
                ("edge='foo') is not an edge policy",),
                id='an-edge-policy-that-is-not-one',
            ),
            pytest.param(
                {'objective': {'expression': 'sum(p, over=g, by=lk)'}}, ('at most one of',), id='over-and-by-together'
            ),
            pytest.param(
                {
                    'parameters.off': {'dims': [], 'dtype': 'int'},
                    'objective': {'expression': 'sum(shift(p, over=g, offset=off + 0), over=g)'},
                },
                ('shift(offset=) takes a number or the name of an integer parameter, not an expression',),
                id='an-amount-that-is-an-expression',
            ),
            pytest.param(
                {'objective': {'expression': 'sum(sum_back(p, over=g, within=2 * 1), over=g)'}},
                ('sum_back(within=) takes a number or the name of an integer parameter',),
                id='a-width-that-is-an-expression',
            ),
            pytest.param(
                {'objective': {'expression': 'sum(shift(p, over=g, offset=1, edge=1 + 1), over=g)'}},
                ('shift(edge=) is an expression, and an edge is the keyword',),
                id='an-edge-that-is-an-expression',
            ),
            pytest.param(
                {'lookups.hk': {'over': 'h', 'into': 'g'}, 'objective': {'expression': 'sum(sum(q, by=[lk, hk]))'}},
                ('groups through lookups over different dimensions',),
                id='by-lookups-over-different-dimensions',
            ),
            pytest.param(
                {'objective': {'expression': 'sum(sum(p, by=[lk, lk]))'}},
                ("targets ['h'] more than once",),
                id='by-the-same-target-twice',
            ),
        ],
    )
    def test_a_value_position_the_resolver_refuses(self, patch, fragments):
        with pytest.raises(LanguageError) as exc:
            load_model(override(RULES_BASE, **patch))
        for fragment in fragments:
            assert fragment in str(exc.value), f'the refusal has to carry {fragment!r}'

    @pytest.mark.parametrize(
        ('where', 'fragments'),
        [
            pytest.param('c > flag', ('compares two parameters',), id='against-a-parameter'),
            pytest.param(
                'c > q', ('compares against variable', 'built before variables exist'), id='against-a-variable'
            ),
            pytest.param('c > lk', ('against lookup', 'structure rather than data'), id='against-a-lookup'),
            pytest.param('c > h', ("compares against dimension 'h'", 'masks everything out'), id='against-a-dimension'),
            pytest.param('g', ('a bare dimension name is true at every coordinate',), id='a-bare-dimension'),
        ],
    )
    def test_a_where_the_resolver_refuses(self, where, fragments):
        with pytest.raises(LanguageError) as exc:
            load_model(override(RULES_BASE, **{'variables.p.where': where}))
        for fragment in fragments:
            assert fragment in str(exc.value), f'the refusal has to carry {fragment!r}'


class TestTheFrontDoor:
    def test_a_list_of_models_is_not_a_model(self):
        with pytest.raises(TypeError, match='one file, one dict or one Model, never a list'):
            load_model([DISPATCH_MODEL, DISPATCH_MODEL])

    def test_a_loaded_model_passes_through_as_itself(self):
        model = load_model(DISPATCH_MODEL)
        assert load_model(model) is model

    def test_a_path_as_a_string_is_read_as_a_file(self, tmp_path):
        path = tmp_path / 'm.yaml'
        path.write_text(load_model(DISPATCH_MODEL).to_yaml())
        assert load_model(str(path)).to_dict() == load_model(path).to_dict()

    @pytest.mark.parametrize('probe', OPERATOR_PROBES, ids=[p.stem for p in OPERATOR_PROBES])
    def test_to_dict_reproduces_the_model(self, probe):
        model = load_model(probe)
        assert load_model(model.to_dict()).to_dict() == model.to_dict()
        assert load_model(model.to_dict()) == model

    def test_to_yaml_reproduces_the_model(self):
        model = load_model(DISPATCH_MODEL)
        assert load_model(parse_yaml(model.to_yaml())) == model

    def test_a_declared_empty_map_survives_the_round_trip(self):
        """`values: {}` is a map the file declares with nothing in it; `None` is a map supplied at bind time."""
        model = load_model(override(RULES_BASE, **{'lookups.lk.values': {}}))
        assert model.lookups['lk'].values == {}
        assert load_model(model.to_dict()).lookups['lk'].values == {}, 'the two mean different things'
        assert 'values: {}' in model.to_yaml()

    def test_an_empty_section_is_not_written(self):
        written = load_model(DISPATCH_MODEL).to_yaml()
        assert 'lookups' not in written and 'macros' not in written, 'a section declaring nothing says nothing'

    def test_a_default_is_written_out_and_an_absence_is_not(self):
        written = load_model(DISPATCH_MODEL).to_dict()
        assert written['variables']['p']['domain'] == 'continuous', 'a default is a fact the reviewer reads'
        assert 'upper' in written['variables']['p']['bounds'] and 'where' not in written['variables']['p'], (
            'a null and an infinite bound say nothing, so they are not written'
        )
