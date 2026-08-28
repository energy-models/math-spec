# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""What `to_spec` refuses with no data bound, and how it says so."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from math_spec._yaml import parse_yaml
from math_spec.errors import LanguageError
from math_spec.resolution import Namespace, where_of
from math_spec.validation import to_spec
from math_spec.where_parser import DimensionPositionNode
from tests.fixtures import DISPATCH_MODEL, OPERATOR_PROBES, SMALL_MODEL, override

if TYPE_CHECKING:
    from math_spec.model import Spec


def _schema(**patch) -> Spec:
    return to_spec(override(SMALL_MODEL, **patch))


class TestValidateExpressions:
    @pytest.mark.parametrize(
        ('patch', 'fragments'),
        [
            pytest.param(
                {'constraints': {'cap': {'foreach': ['g'], 'expression': 'nope <= c'}}},
                ("'nope' not found", "Constraint 'cap'", 'c'),
                id='an-unknown-name-in-a-constraint',
            ),
            pytest.param(
                {'constraints': {'cap': {'foreach': ['g'], 'expression': 'p + c'}}},
                ('exactly one comparison',),
                id='a-constraint-without-a-comparison',
            ),
            pytest.param(
                {'objective': {'expression': 'sum(p, over=g) <= 5'}},
                ('must not contain a comparison',),
                id='an-objective-with-a-comparison',
            ),
            pytest.param(
                {'constraints': {'cap': {'foreach': ['g'], 'expression': 'c <= 1'}}},
                ('decides nothing', "Constraint 'cap'", "'c <= 1'"),
                id='a-comparison-with-no-variable-in-it',
            ),
            pytest.param(
                {'constraints': {'cap': {'foreach': ['g'], 'expression': 'p * p * p <= c'}}},
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
                {'constraints': {'cap': {'foreach': ['g'], 'where': 'c >', 'expression': 'p <= c'}}},
                ('Failed to parse where string',),
                id='a-malformed-where-string',
            ),
            pytest.param(
                {'constraints': {'cap': {'foreach': ['g'], 'where': 'not_a_param > 0', 'expression': 'p <= c'}}},
                ("'not_a_param' not found",),
                id='an-unknown-name-in-a-where-used-to-evaluate-to-false',
            ),
        ],
    )
    def test_a_bad_declaration_is_refused_at_load(self, patch, fragments):
        with pytest.raises(LanguageError) as exc:
            _schema(**patch)
        for fragment in fragments:
            assert fragment in str(exc.value)

    def test_the_objective_and_a_constraint_take_degree_two(self):
        _schema(
            constraints={'floor': {'foreach': ['g'], 'expression': 'p * p >= 1'}},
            objective={'expression': 'sum(p * p * c, over=g)'},
        )

    def test_multiple_errors_collected(self):
        with pytest.raises(LanguageError) as exc_info:
            _schema(
                constraints={
                    'a': {'foreach': ['g'], 'expression': 'nope <= 1'},
                    'b': {'foreach': ['g'], 'expression': 'p + 1'},
                },
            )
        msg = str(exc_info.value)
        assert "'nope' not found" in msg
        assert 'exactly one comparison' in msg


class TestDimensionKwargs:
    """A dim kwarg that names nothing is a silent no-op, not an error — `sum(p, over=snapshto)` used to load."""

    @staticmethod
    def _schema(expression: str, foreach: list[str] | None = None) -> Spec:
        """A model over (snapshot, generator), with `zone` a lookup into `bus`.

        `zone` deliberately targets a dim `p` does *not* carry: grouping into
        one it already has needs that dim twice, which is its own error.
        """
        foreach = ['snapshot'] if foreach is None else foreach  # an explicit [] is a scalar constraint
        return to_spec(
            {
                'dimensions': {
                    'snapshot': {'dtype': 'int'},
                    'bus': {'dtype': 'str'},
                    'generator': {'dtype': 'str'},
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
            self._schema(expression)
        for fragment in fragments:
            assert fragment in str(exc.value)

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
        self._schema(expression, foreach)

    def test_macro_formals_are_not_mistaken_for_dimensions(self):
        """A formal in a dim position is legal inside the template body."""
        _schema(
            macros={
                'ws': {'args': ['array', 'weights'], 'kwargs': ['over'], 'template': 'sum(array * weights, over=over)'}
            },
            objective={'sense': 'minimize', 'expression': 'ws(p, c, over=g)'},
        )

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
        """The same guard one construct over (#460): polars reads `snapshot > 0` on a
        datetime as "after the epoch" and silently drops every earlier coordinate."""
        with pytest.raises(LanguageError, match=match):
            _schema(**{'dimensions.g': {'dtype': dtype}, 'variables.p.where': where})


class TestArithmeticDtype:
    """A name in a value position has to be a number, which its `dtype` says.

    The dtype rules reached the `where` and `offset=` positions and not an
    ordinary value, so a label stood as a coefficient and the file declared a
    model no consumer could build.
    """

    @staticmethod
    def _schema(dtype: str, expression: str) -> Spec:
        return _schema(
            **{
                'parameters.a': {'dims': ['g'], 'dtype': dtype},
                'constraints': {'cap': {'foreach': ['g'], 'expression': expression}},
            }
        )

    @pytest.mark.parametrize('dtype', ['str', 'bool'])
    @pytest.mark.parametrize(
        'expression',
        [
            pytest.param('a * p <= c', id='a-coefficient'),
            pytest.param('p / a <= c', id='a-divisor'),
            pytest.param('p + a <= c', id='a-term'),
            pytest.param('-a * p <= c', id='a-negated-factor'),
            pytest.param('sum(a * p, over=g) <= 1', id='under-an-operator'),
        ],
    )
    def test_a_label_or_a_flag_is_not_a_value(self, dtype, expression):
        with pytest.raises(LanguageError, match=f'declared dtype: {dtype}'):
            self._schema(dtype, expression)

    @pytest.mark.parametrize('dtype', ['float', 'int'])
    def test_a_number_is(self, dtype):
        self._schema(dtype, 'a * p <= c')

    @pytest.mark.parametrize(
        ('dtype', 'where'),
        [
            ('str', "a == 'wind'"),
            ('bool', 'a'),
            ('bool', 'NOT a'),
        ],
    )
    def test_the_position_it_is_declared_for_still_takes_it(self, dtype, where):
        """The refusal is about arithmetic, not the dtype: selecting with a label and masking with a flag stay."""
        _schema(**{'parameters.a': {'dims': ['g'], 'dtype': dtype}, 'variables.p.where': where})

    def test_a_named_amount_keeps_its_own_sentence(self):
        """`offset=` has a stricter rule of its own — a count of positions is integral — and that sentence arrives."""
        with pytest.raises(LanguageError, match='counts positions along'):
            _schema(
                **{
                    'parameters.lag': {'dims': [], 'dtype': 'str'},
                    'objective': {'expression': "sum(shift(p, over=g, offset=lag, edge='wrap'))"},
                }
            )


class TestVersion:
    """`version:` is refused when unknown, and does nothing else (#67)."""

    @pytest.mark.parametrize('top', [pytest.param({}, id='absent'), pytest.param({'version': 0}, id='zero')])
    def test_absent_and_zero_are_the_unstable_surface(self, top):
        assert _schema(**top).version == 0

    def test_an_unknown_version_is_refused_not_interpreted(self):
        with pytest.raises(LanguageError) as exc:
            _schema(version=1)

        message = str(exc.value)
        assert 'declares version 1' in message
        assert 'understands [0]' in message, 'the error has to say what this reader can read'
        assert 'Upgrade math_spec' in message, 'and what to do about it'

    def test_the_version_gates_no_behaviour(self):
        """Two files differing only in a declared supported version build the same model."""
        assert _schema().model_dump(exclude={'version'}) == _schema(version=0).model_dump(exclude={'version'})


#: `position(dim)` needs a lookup over *that* dimension, so one over it and one into it.
POSITION_SCHEMA = to_spec(
    {
        'dimensions': {'snapshot': {'dtype': 'int'}, 'period': {'dtype': 'int'}},
        'lookups': {
            'period_of': {'over': 'snapshot', 'into': 'period'},
            'starts_at': {'over': 'period', 'into': 'snapshot'},
        },
        'parameters': {'load': {'dims': ['snapshot']}},
        'variables': {'p': {'foreach': ['snapshot']}},
    }
)


class TestPositionResolves:
    """`position(dim)` — the conversion #32 put on the left-hand side.

    A `by=` has to be a lookup over *that* dimension: the groups are its
    target's labels, and a lookup over anything else carries no row for a
    position to be a position in.
    """

    @pytest.mark.parametrize(
        ('mask', 'position', 'by'),
        [
            ('position(snapshot) == 0', 0, None),
            ('position(snapshot, by=period_of) == 0', 0, 'period_of'),
        ],
        ids=['first', 'first of each period'],
    )
    def test_it_resolves(self, mask: str, position: int, by: str | None):
        node = where_of(mask, Namespace.of(POSITION_SCHEMA), 'the mask')
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
        with pytest.raises(LanguageError) as excinfo:
            where_of(mask, Namespace.of(POSITION_SCHEMA), 'the mask')
        for fragment in fragments:
            assert fragment in str(excinfo.value)


class TestRulesDecidedWithoutData:
    """Every refusal the schema or the resolver makes with no data bound, one row each."""

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
            pytest.param(
                {'lookups.lk.over': 'z'}, ("references undeclared dimension 'z'",), id='lookup-over-undeclared'
            ),
            pytest.param({'lookups.lk.into': 'z'}, ("targets undeclared dimension 'z'",), id='lookup-into-undeclared'),
            pytest.param({'lookups.lk.into': 'g'}, ("maps 'g' into itself",), id='lookup-into-itself'),
            pytest.param(
                {'lookups.g': {'over': 'h', 'into': 'g'}},
                ("Lookup 'g' collides with the dimension",),
                id='lookup-named-after-a-dimension',
            ),
            pytest.param(
                {'lookups.lk.values': {'a': 'x'}},
                ("unknown key 'values' in a lookup declaration", 'Valid keys'),
                id='a-lookup-declaring-its-map',
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
                {'variables.p.bounds': {'lower': 5, 'upper': 1}},
                ('bounds.lower 5.0 is above bounds.upper 1.0, so no value satisfies them',),
                id='literal-bounds-that-cross',
            ),
            pytest.param(
                {'variables.p.bounds': {'lower': float('inf'), 'upper': float('-inf')}},
                ('bounds.lower inf is above bounds.upper -inf',),
                id='infinite-bounds-that-cross',
            ),
            pytest.param(
                {'variables.p.foreach': ['g', 'g']},
                ("Variable 'p' names dimension 'g' twice",),
                id='foreach-repeats-a-dim',
            ),
            pytest.param(
                {'parameters.c.dims': ['g', 'g']}, ("Parameter 'c' names dimension 'g' twice",), id='dims-repeat-a-dim'
            ),
            pytest.param(
                {'dimensions.g.values': ['a', 'b']},
                ("unknown key 'values' in a dimension declaration", 'Valid keys'),
                id='a-dimension-declaring-its-members',
            ),
            pytest.param(
                {'variables.p.where': 'p'},
                ('asks whether it exists in its own where',),
                id='a-mask-naming-its-own-variable',
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
                ('shift(offset=) takes a number or the name of an integer parameter', 'Precompute it as a parameter'),
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
            pytest.param(
                {'variables.p.where': 'c > flag'}, ('compares two parameters',), id='where-against-a-parameter'
            ),
            pytest.param(
                {'variables.p.where': 'c > q'},
                ('compares against variable', 'built before variables exist'),
                id='where-against-a-variable',
            ),
            pytest.param(
                {'variables.p.where': 'c > lk'},
                ('against lookup', 'structure rather than data'),
                id='where-against-a-lookup',
            ),
            pytest.param(
                {'variables.p.where': 'c > h'},
                ("compares against dimension 'h'", 'masks everything out'),
                id='where-against-a-dimension',
            ),
            pytest.param(
                {'variables.p.where': 'g'},
                ('a bare dimension name is true at every coordinate',),
                id='where-a-bare-dimension',
            ),
        ],
    )
    def test_a_rule_decided_without_data(self, patch, fragments):
        with pytest.raises(LanguageError) as exc:
            _schema(**patch)
        for fragment in fragments:
            assert fragment in str(exc.value)


class TestTheFrontDoor:
    def test_a_list_of_models_is_not_a_model(self):
        with pytest.raises(TypeError, match='one file, one dict or one Spec, never a list'):
            to_spec([DISPATCH_MODEL, DISPATCH_MODEL])

    def test_a_loaded_model_passes_through_as_itself(self):
        model = to_spec(DISPATCH_MODEL)
        assert to_spec(model) is model

    def test_a_path_as_a_string_is_read_as_a_file(self, tmp_path):
        path = tmp_path / 'm.yaml'
        path.write_text(to_spec(DISPATCH_MODEL).to_yaml())
        assert to_spec(str(path)).to_dict() == to_spec(path).to_dict()

    @pytest.mark.parametrize('probe', OPERATOR_PROBES, ids=[p.stem for p in OPERATOR_PROBES])
    def test_to_dict_reproduces_the_model(self, probe):
        model = to_spec(probe)
        assert to_spec(model.to_dict()) == model

    def test_to_yaml_reproduces_the_model(self):
        model = to_spec(DISPATCH_MODEL)
        assert to_spec(parse_yaml(model.to_yaml())) == model

    def test_an_empty_list_survives_the_round_trip(self):
        """`foreach: []` is a scalar declaration, not an absence — stripping it would put the variable on every dim it names."""
        model = _schema(**{'variables.p.foreach': []})
        assert model.to_dict()['variables']['p']['foreach'] == []
        assert to_spec(model.to_dict()).variables['p'].foreach == []

    def test_an_empty_section_is_not_written(self):
        written = to_spec(DISPATCH_MODEL).to_yaml()
        assert 'lookups' not in written and 'macros' not in written, 'a section declaring nothing says nothing'

    def test_a_default_is_written_out_and_an_absence_is_not(self):
        written = to_spec(DISPATCH_MODEL).to_dict()
        assert written['variables']['p']['domain'] == 'continuous', 'a default is a fact the reviewer reads'
        assert 'upper' in written['variables']['p']['bounds'] and 'where' not in written['variables']['p'], (
            'a null and an infinite bound say nothing, so they are not written'
        )
