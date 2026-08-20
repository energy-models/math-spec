"""Tests for load-time validation of expression and where strings."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pytest

from lpspec.language.validation import load_model, validate_expressions

if TYPE_CHECKING:
    from lpspec.language.model import Model


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
        with pytest.raises(ValueError) as exc:
            _schema(**overrides)
        for fragment in fragments:
            assert fragment in str(exc.value), f'the refusal has to carry {fragment!r}'

    def test_dim_name_kwarg_not_flagged(self):
        """Keyword-arg names are dimension names, not data references."""
        schema = _schema(
            objective={'expression': 'sum(p, over=g)'},
        )
        validate_expressions(schema)

    def test_multiple_errors_collected(self):
        with pytest.raises(ValueError) as exc_info:
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
        with pytest.raises(ValueError) as exc:
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
        with pytest.raises(ValueError, match=match):
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
        with pytest.raises(ValueError, match=match):
            _schema(dimensions={'g': {'dtype': dtype}}, variables={'p': {'foreach': ['g'], 'where': where}})


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
        with pytest.raises(ValueError) as exc:
            load_model(self._model(version=1))

        message = str(exc.value)
        assert 'declares version 1' in message
        assert 'understands [0]' in message, 'the error has to say what this reader can read'
        assert 'Upgrade lpspec' in message, 'and what to do about it'

    def test_the_version_gates_no_behaviour(self):
        """Reject-only. Two files differing only in a *declared* supported
        version must build the same model — the field never selects a surface.
        """
        bare = load_model(self._model())
        declared = load_model(self._model(version=0))
        assert bare.model_dump(exclude={'version'}) == declared.model_dump(exclude={'version'})
