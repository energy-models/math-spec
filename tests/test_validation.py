# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""What `to_spec` refuses with no data bound, and how it says so."""

from __future__ import annotations

import copy
import re
from typing import TYPE_CHECKING, Any

import pytest

from math_spec._yaml import parse_yaml
from math_spec.errors import DimensionError, LanguageError, SchemaError
from math_spec.lowering import to_program
from math_spec.program import DimensionPositionNode
from math_spec.resolution import Namespace, where_of
from math_spec.typesetting import to_markdown
from math_spec.validation import to_spec
from tests.fixtures import DISPATCH_MODEL, OPERATOR_PROBES, SMALL_MODEL, override

if TYPE_CHECKING:
    from math_spec.model import Spec


def _schema(**patch) -> Spec:
    return to_spec(override(SMALL_MODEL, **patch))


def _refusal(model: dict[str, Any] = SMALL_MODEL, **patch: Any) -> str:
    """The message `to_spec` refuses *model* patched with — and it has to refuse."""
    with pytest.raises(LanguageError) as caught:
        to_spec(override(model, **patch))
    return str(caught.value)


_NONLINEAR_ENTRY = {'expressions': {'bad': 'c / sum(p)'}}


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
        message = _refusal(
            constraints={
                'a': {'foreach': ['g'], 'expression': 'nope <= 1'},
                'b': {'foreach': ['g'], 'expression': 'p + 1'},
            },
        )
        assert "'nope' not found" in message
        assert 'exactly one comparison' in message, 'the second fault is reported beside the first, not behind it'

    @pytest.mark.parametrize(
        ('patch', 'fragments'),
        [
            pytest.param(
                {'constraints': {'cap': {'foreach': ['g'], 'expression': 'p <= bad'}}},
                ("Constraint 'cap'", 'the divisor contains variables, which is not affine'),
                id='constraint',
            ),
            pytest.param(
                {'objective': {'expression': 'sum(bad)'}},
                ('The objective', 'the divisor contains variables, which is not affine'),
                id='objective',
            ),
        ],
    )
    def test_a_nonlinear_entry_is_refused_where_the_math_reads_it(self, patch, fragments):
        """The refusal a nonlinear body once earned at its own declaration now fires where the math reads it.

        `bad` (a variable divisor) loads on its own — its grade is decided, not
        refused (see `TestExpressionGrade`). The constraint and the objective
        read it and hit the divisor ban at their own ceiling, which is the whole
        point of grading rather than banning at declaration. The piecewise-link
        position is `test_a_link_reading_a_nonlinear_entry_is_refused`; a bound
        and a where, which reference no expression at all, are
        `test_a_bound_or_where_cannot_name_an_expression`.
        """
        with pytest.raises(LanguageError) as exc:
            _schema(**_NONLINEAR_ENTRY, **patch)
        for fragment in fragments:
            assert fragment in str(exc.value)

    @pytest.mark.parametrize(
        ('patch', 'fragment'),
        [
            pytest.param(
                {'variables.p.bounds': {'lower': 'bad'}},
                "'bad' is not a declared parameter",
                id='bound',
            ),
            pytest.param(
                {'constraints': {'cap': {'foreach': ['g'], 'where': 'bad > 0', 'expression': 'p <= c'}}},
                "'bad' not found",
                id='where',
            ),
        ],
    )
    def test_a_bound_or_where_cannot_name_an_expression(self, patch, fragment):
        """A bound and a where reference parameters/variables, never a named expression, so the name fails to resolve regardless of the entry's grade."""
        with pytest.raises(LanguageError) as exc:
            _schema(**_NONLINEAR_ENTRY, **patch)
        assert fragment in str(exc.value)

    def test_an_unreferenced_nonlinear_entry_loads_typesets_and_grades_postsolve(self):
        """A nonlinear entry nothing reads is accepted, printed, and graded post-solve — the deliberate cost of grading over banning.

        This is the C1 silent-typo case made visible instead of denied: a body
        the math would refuse (here a variable divisor) is legal on its own
        because it is arithmetic over solved numbers, so a typo that leaves it
        unread is not caught by the loader. The language pays that cost openly —
        the entry loads, appears in the typeset Post-solve section, and reports
        its grade — rather than degree-checking a declaration nothing consumes.
        """
        model = override(SMALL_MODEL, expressions={'lcoe': 'c / sum(p)'})
        assert 'lcoe' in to_program(model).named_expressions, (
            'the unread nonlinear body loads rather than being refused'
        )
        rendered = to_markdown(model)
        assert 'Post-solve' in rendered and 'lcoe' in rendered, (
            'and its grade shows: it prints in the Post-solve section'
        )


def _kwarg_model(expression: str, foreach: list[str] | None = None) -> dict[str, Any]:
    """A model over (snapshot, generator), with `zone` a lookup into `bus`.

    `zone` deliberately targets a dim `p` does *not* carry: grouping into
    one it already has needs that dim twice, which is its own error.
    `season` is a label space over the same dim, for the refusals below.
    An explicit ``foreach=[]`` is a scalar constraint; ``None`` is the
    default frame over `snapshot`.
    """
    return {
        'dimensions': {
            'snapshot': {'dtype': 'int'},
            'bus': {'dtype': 'str'},
            'generator': {'dtype': 'str'},
        },
        'lookups': {
            'zone': {'over': 'generator', 'into': 'bus'},
            'season': {'over': 'generator', 'dtype': 'str'},
        },
        'parameters': {'load': {'dims': ['snapshot']}},
        'variables': {'p': {'foreach': ['snapshot', 'generator']}},
        'constraints': {'c': {'foreach': ['snapshot'] if foreach is None else foreach, 'expression': expression}},
    }


class TestDual:
    """`dual(c)`: a primitive whose call grades its entry post-solve, its argument a constraint name resolved against constraints alone."""

    BASE = override(SMALL_MODEL, **{'constraints.lim': {'foreach': ['g'], 'expression': 'p <= c'}})

    @pytest.mark.parametrize(
        ('patch', 'fragments'),
        [
            pytest.param(
                {'expressions': {'price': 'dual(nope)'}},
                ("dual(nope): 'nope' is not a declared constraint", 'Constraints:', 'lim'),
                id='an-unknown-constraint',
            ),
            pytest.param(
                {'expressions': {'price': 'dual(p)'}},
                ("dual(p): 'p' is not a declared constraint",),
                id='a-variable-name-is-not-a-constraint',
            ),
            pytest.param(
                {'expressions': {'price': 'dual(1 + 1)'}},
                ('dual() takes the name of a declared constraint, written bare', 'dual(<constraint>)'),
                id='a-non-name-argument-is-not-a-constraint-reference',
            ),
            pytest.param(
                {'expressions': {'price': 'dual(c)'}},
                ("dual(c): 'c' is not a declared constraint",),
                id='a-parameter-name-is-not-a-constraint',
            ),
            pytest.param(
                {'constraints': {'lim': {'foreach': ['g'], 'expression': 'dual(lim) <= c'}}},
                ('a dual exists only after a solve', 'the math cannot read one'),
                id='a-dual-written-inside-a-constraint',
            ),
            pytest.param(
                {'objective': {'sense': 'minimize', 'expression': 'sum(p) + dual(lim)'}},
                ('a dual exists only after a solve', 'the math cannot read one'),
                id='a-dual-written-inside-the-objective',
            ),
            pytest.param(
                {
                    'macros': {'shadow': {'args': ['x'], 'template': 'dual(x)'}},
                    'constraints': {'lim': {'foreach': ['g'], 'expression': 'shadow(lim) <= c'}},
                },
                ('a dual exists only after a solve', 'the math cannot read one'),
                id='a-dual-smuggled-through-a-macro-into-a-constraint',
            ),
            pytest.param(
                {
                    'expressions': {'price': 'dual(lim)'},
                    'constraints': {'lim': {'foreach': ['g'], 'expression': 'price <= c'}},
                },
                ('a dual exists only after a solve', 'keep the entry that carries it out of constraints'),
                id='a-dual-smuggled-through-an-entry-into-a-constraint',
            ),
        ],
    )
    def test_a_dual_out_of_place_is_refused(self, patch, fragments):
        with pytest.raises(LanguageError) as exc:
            to_spec(override(self.BASE, **patch))
        for fragment in fragments:
            assert fragment in str(exc.value)

    def test_a_dual_loads_in_an_expressions_entry(self):
        """The one place it is legal: an ``expressions:`` entry naming a declared constraint — the call grades the entry post-solve."""
        assert to_spec(override(self.BASE, expressions={'price': 'dual(lim)'})).expressions['price']


class TestDimensionKwargs:
    """A dim kwarg that names nothing is a silent no-op, not an error — `sum(p, over=snapshto)` used to load."""

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
                ('does not name a lookup', "Did you mean 'zone'?"),
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
        message = _refusal(_kwarg_model(expression))
        for fragment in fragments:
            assert fragment in message

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
        to_spec(_kwarg_model(expression, foreach))

    @pytest.mark.parametrize(
        'expression',
        [
            pytest.param('sum(p, by=season) == load', id='sum'),
            pytest.param('at(p, by=season) == load', id='at'),
            pytest.param('shift(p, over=generator, offset=1, by=season) == load', id='shift'),
        ],
    )
    def test_a_label_space_is_refused_wherever_by_needs_a_target(self, expression):
        """Every `by=` but `position`'s reaches a target dimension: `sum` and `at` to
        place terms on it, `shift` so a named `offset=` may vary per group. A label
        space targets nothing, so all three refuse it and name the promotion (#280)."""
        message = _refusal(_kwarg_model(expression, ['snapshot', 'bus']))
        assert 'is a label space' in message, 'the refusal names the kind, not just the name'
        assert 'season_of' in message, 'and it spells the promotion out'

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
    def _schema_with_typed_a(dtype: str, expression: str) -> Spec:
        """`SMALL_MODEL` plus a parameter `a` of *dtype*, standing in the constraint *expression*."""
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
            self._schema_with_typed_a(dtype, expression)

    @pytest.mark.parametrize('dtype', ['float', 'int'])
    def test_a_number_is(self, dtype):
        self._schema_with_typed_a(dtype, 'a * p <= c')

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
        message = _refusal(version=1)
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
            'season': {'over': 'snapshot', 'dtype': 'str'},
        },
        'parameters': {'load': {'dims': ['snapshot']}},
        'variables': {'p': {'foreach': ['snapshot']}},
    }
)


class TestPositionResolves:
    """`position(dim)` — the conversion #32 put on the left-hand side.

    A `by=` has to be a lookup over *that* dimension, and that is the whole
    test: a lookup over anything else carries no row for a position to be a
    position in. Unlike `sum`, `at` and `shift`, it does not have to be a
    *groupable* one — counting inside a group lands no terms, so a label
    space partitions the rows perfectly well (#280).
    """

    @pytest.mark.parametrize(
        ('mask', 'position', 'by'),
        [
            ('position(snapshot) == 0', 0, None),
            ('position(snapshot, by=period_of) == 0', 0, 'period_of'),
            ('position(snapshot, by=season) == 0', 0, 'season'),
        ],
        ids=['first', 'first of each period', 'first of each season, by a label space'],
    )
    def test_it_resolves(self, mask: str, position: int, by: str | None):
        resolved = where_of(mask, Namespace.of(POSITION_SCHEMA), 'the mask')
        assert resolved is not None
        node = resolved.root
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
                {'constraints': {'cap': {'foreach': ['g'], 'where': 'c >', 'expression': 'p <= c'}}},
                ('Failed to parse where string',),
                id='a-malformed-where-string',
            ),
            pytest.param(
                {'constraints': {'cap': {'foreach': ['g'], 'where': 'not_a_param > 0', 'expression': 'p <= c'}}},
                ("'not_a_param' not found",),
                id='an-unknown-name-in-a-where',
            ),
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
        message = _refusal(**patch)
        for fragment in fragments:
            assert fragment in message


class TestTheFrontDoor:
    def test_a_list_of_models_is_not_a_model(self):
        """Composition is Python's, not the file's (#30) — and the refusal is the package's own, so the CLI's one except catches it."""
        with pytest.raises(SchemaError, match='one file, one dict or one Spec, never a list'):
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
        assert model.to_dict()['variables']['p']['foreach'] == [], 'the empty frame is written out, not dropped'
        assert to_spec(model.to_dict()).variables['p'].foreach == [], 'and reads back as the scalar it declares'

    def test_an_empty_section_is_not_written(self):
        written = to_spec(DISPATCH_MODEL).to_yaml()
        assert 'lookups' not in written and 'macros' not in written, 'a section declaring nothing says nothing'

    def test_a_default_is_written_out_and_an_absence_is_not(self):
        written = to_spec(DISPATCH_MODEL).to_dict()
        assert written['variables']['p']['domain'] == 'continuous', 'a default is a fact the reviewer reads'
        assert 'upper' in written['variables']['p']['bounds'] and 'where' not in written['variables']['p'], (
            'a null and an infinite bound say nothing, so they are not written'
        )


#: A model with room for a cased expression: two dimensions, so an arm can be
#: narrower than the frame, and a variable, so an arm can reach one.
CASED_BASE = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'generator': {}},
    'parameters': {'p_max': {'dims': ['generator']}, 'load': {'dims': ['snapshot']}},
    'variables': {'p': {'foreach': ['snapshot', 'generator']}},
}

#: The one region of a quantity whose `otherwise` carries everything else.
OPENING = {'opening': {'when': 'position(snapshot) == 0', 'expression': 'p_max'}}


def _headroom(block: dict[str, Any]) -> dict[str, Any]:
    """`CASED_BASE` with *block* as its one named expression, `headroom`."""
    return {**copy.deepcopy(CASED_BASE), 'expressions': {'headroom': block}}


def _cased(cases: dict[str, Any] | None = None, **block: Any) -> dict[str, Any]:
    """`_headroom` over a cased block: `OPENING` or *cases*, an `otherwise:` of 0, and *block* on top."""
    return _headroom(
        {
            'foreach': ['snapshot', 'generator'],
            'cases': OPENING if cases is None else cases,
            'otherwise': 0,
            **block,
        }
    )


class TestExpressionCases:
    """`cases:` on a named expression — the declaration, and the shape it must have."""

    def test_a_cased_expression_loads(self):
        block = to_spec(_cased()).expressions['headroom']
        assert list(block.cases) == ['opening'], 'the one case, under the name the file gave it'
        assert block.otherwise == '0'

    @pytest.mark.parametrize(
        ('when', 'fragment'),
        [
            pytest.param(
                'position(snapshot) == 0 OR True',
                'no other arm can hold anywhere',
                id='folds-to-every-row',
            ),
            pytest.param('False', 'this arm never applies', id='admits-no-row'),
        ],
    )
    def test_an_arm_the_data_cannot_decide_is_refused(self, when: str, fragment: str):
        """A mask that folds to a literal is not a case, and the refusal names the rewrite."""
        model = _cased(cases={'opening': {'when': when, 'expression': 'p_max'}})
        with pytest.raises(SchemaError, match=fragment):
            to_spec(model)

    def test_it_round_trips(self):
        """The mapping form goes back out as it came in, `otherwise:` and all."""
        schema = to_spec(_cased(description='what is spare'))
        assert to_spec(schema.to_dict()).to_yaml() == schema.to_yaml()

    def test_the_fallback_is_written_as_the_bare_value(self):
        """`otherwise:` carries nothing but its value, so a mapping around it would be ceremony."""
        written = to_spec(_cased()).to_dict()['expressions']['headroom']
        assert written['cases'] == {'opening': {'when': 'position(snapshot) == 0', 'expression': 'p_max'}}, (
            'a case goes back out as the mapping it came in as'
        )
        assert written['otherwise'] == '0'

    @pytest.mark.parametrize(
        ('block', 'fragment'),
        [
            pytest.param(
                {'expression': 'load', 'foreach': ['snapshot'], 'cases': OPENING, 'otherwise': 0},
                'this has both',
                id='both',
            ),
            pytest.param({'description': 'nothing at all'}, 'this has neither', id='neither'),
            pytest.param({'cases': OPENING, 'otherwise': 0}, '`cases:` needs a `foreach:`', id='no-foreach'),
            pytest.param(
                {'expression': 'load', 'foreach': ['snapshot']},
                '`foreach:` is only for a named expression with `cases:`',
                id='foreach-alone',
            ),
            pytest.param(
                {'foreach': ['snapshot', 'generator'], 'cases': OPENING},
                'a `cases:` block needs an `otherwise:`',
                id='no-otherwise',
            ),
            pytest.param(
                {'expression': 'load', 'otherwise': 0},
                '`otherwise:` is what is left once the `cases:` have taken their regions',
                id='otherwise-alone',
            ),
        ],
    )
    def test_the_two_forms_do_not_mix(self, block: dict[str, Any], fragment: str):
        with pytest.raises(SchemaError, match=re.escape(fragment)):
            to_spec(_headroom(block))

    @pytest.mark.parametrize(
        ('cases', 'message'),
        [
            pytest.param(
                {'opening': {'expression': 'p_max'}},
                'expressions.headroom.cases.opening.when: Field required',
                id='case-without-when',
            ),
            pytest.param(
                {},
                'expressions.headroom.cases: Dictionary should have at least 1 item after validation, not 0',
                id='no-cases',
            ),
        ],
    )
    def test_the_schema_itself_states_the_shape_of_a_case(self, cases: dict[str, Any], message: str):
        """Every case says where it applies, and a block carries one — both the closed schema's own error."""
        with pytest.raises(SchemaError, match=re.escape(message)):
            to_spec(_cased(cases))

    def test_two_cases_may_not_claim_one_coordinate(self):
        """Proved before any data binds, so the arms are read apart rather than in order."""
        cases = {
            'gas': {'when': "generator == 'gas'", 'expression': 'p_max'},
            'opening': {'when': 'position(snapshot) == 0', 'expression': 'p_max * 2'},
        }
        with pytest.raises(SchemaError, match="cases 'gas' and 'opening' both claim the value where"):
            to_spec(_cased(cases))

    def test_cases_spelled_apart_load(self):
        """The same three regions, with the second narrowed by the negation of the first."""
        cases = {
            'gas': {'when': "generator == 'gas'", 'expression': 'p_max'},
            'opening': {'when': "generator != 'gas' and position(snapshot) == 0", 'expression': 'p_max * 2'},
        }
        assert list(to_spec(_cased(cases)).expressions['headroom'].cases) == ['gas', 'opening'], (
            'both cases load, in the order the file wrote them'
        )

    def test_a_pair_that_cannot_be_decided_is_refused_as_an_overlap_is(self):
        """`snapshot` declares no `values:`, so 0 and -1 are one row on a one-member axis."""
        cases = {
            'opening': {'when': 'position(snapshot) == 0', 'expression': 'p_max'},
            'closing': {'when': 'position(snapshot) == -1', 'expression': 'p_max * 2'},
        }
        with pytest.raises(SchemaError, match='cannot be told apart before the data arrives'):
            to_spec(_cased(cases))

    def test_the_frame_must_name_declared_dimensions(self):
        with pytest.raises(SchemaError, match="references undeclared dimension 'region'"):
            to_spec(_cased(foreach=['snapshot', 'region']))

    def test_a_case_may_not_widen_the_frame(self):
        """A case is a value within the frame, and `load` carries a dim it lacks."""
        cases = {'gas': {'when': "generator == 'gas'", 'expression': 'p_max'}}
        with pytest.raises(DimensionError, match="otherwise: the value carries dims \\['snapshot'\\]"):
            to_spec(_cased(cases, foreach=['generator'], otherwise='load'))

    def test_a_when_may_not_test_a_dim_outside_the_frame(self):
        """The same rule a variable's or a constraint's mask is held to."""
        with pytest.raises(
            DimensionError, match=r"where-dimension 'snapshot' reads dims \['snapshot'\] outside the frame"
        ):
            to_spec(_cased(foreach=['generator']))

    def test_an_unknown_name_in_a_case_is_a_load_error(self):
        with pytest.raises(SchemaError, match="case 'opening'"):
            to_spec(_cased({'opening': {'when': 'position(snapshot) == 0', 'expression': 'nonexistent'}}))

    def test_a_case_may_not_compare(self):
        cases = {'opening': {'when': 'position(snapshot) == 0', 'expression': 'p_max >= 0'}}
        with pytest.raises(SchemaError, match='must not contain a comparison operator'):
            to_spec(_cased(cases))

    def test_a_constraint_naming_it_carries_the_declared_frame(self):
        """Not the union of the cases: one narrower than the frame broadcasts."""
        model = _cased()
        model['constraints'] = {'spare': {'foreach': ['snapshot', 'generator'], 'expression': 'p <= headroom'}}
        to_spec(model)

        model['constraints'] = {'spare': {'foreach': ['generator'], 'expression': 'p <= headroom'}}
        with pytest.raises(DimensionError, match='snapshot'):
            to_spec(model)

    def test_a_fault_in_an_arm_names_the_declaration_and_is_reported_once(self):
        """The block is expanded at every use, and the fault is in one place.

        Naming the use site would report a case on a constraint that has none,
        and one sentence per constraint reading the expression is the same
        fault as many.
        """
        model = _cased({'opening': {'when': 'position(snapshot) == 0', 'expression': 'nope'}})
        model['constraints'] = {
            name: {'foreach': ['snapshot', 'generator'], 'expression': f'p <= headroom + {n}'}
            for n, name in enumerate(('cap', 'floor'))
        }
        message = _refusal(model)
        assert message.count("'nope' not found") == 1, 'two constraints read it; the fault is reported once'
        assert "Named expression 'headroom', case 'opening'" in message
        assert 'Constraint' not in message, "the arm is the declaration's, not the use site's"

    def test_the_fallback_is_not_named_as_a_case(self):
        """`otherwise:` is what is left, not a region like the cases are.

        Reached through a constraint, which is where the arms are walked a
        second time and where the label was read off the arm.
        """
        model = _cased(otherwise='nope')
        model['constraints'] = {'cap': {'foreach': ['snapshot', 'generator'], 'expression': 'p <= headroom'}}
        message = _refusal(model)
        assert "Named expression 'headroom', otherwise: 'nope' not found" in message
        assert "case 'otherwise'" not in message, 'the fallback is not one of the cases'

    def test_a_case_may_name_another_expression(self):
        model = _cased({'opening': {'when': 'position(snapshot) == 0', 'expression': 'spare'}})
        model['expressions']['spare'] = 'p_max * 2'
        model['constraints'] = {'cap': {'foreach': ['snapshot', 'generator'], 'expression': 'p <= headroom'}}
        to_spec(model)

    def test_a_macro_may_name_one(self):
        model = _cased()
        model['macros'] = {'twice': {'args': ['x'], 'template': 'x * 2'}}
        model['constraints'] = {'cap': {'foreach': ['snapshot', 'generator'], 'expression': 'p <= twice(headroom)'}}
        to_spec(model)


class TestANumberIsAnExpression:
    """`expression: 0` is a constant, and YAML reads it as an int rather than a string."""

    def test_a_number_is_read_as_the_expression_it_writes(self):
        assert _schema(**{'expressions.always': {'expression': 1}}).expressions['always'].expression == '1'

    def test_it_survives_the_round_trip_as_the_string_it_became(self):
        model = _schema(**{'expressions.always': {'expression': 1.5}})
        assert to_spec(model.to_dict()).expressions['always'].expression == '1.5'

    def test_a_boolean_is_still_not_an_expression(self):
        """`true` is not arithmetic, and an error naming the type reads better than one naming `'True'`."""
        with pytest.raises(SchemaError, match='valid string'):
            _schema(**{'expressions.always': {'expression': True}})


class TestADeclarationIsNamed:
    """A declaration's key must be a name the expression grammar could write.

    Nothing checked it, so `parameters: {'': {...}}` loaded, and a piecewise
    block naming it under `points:` had its mask silently dropped —
    `if mask:` in the expansion read a declared parameter as "this block
    masks nothing", and the weights came out unmasked. Every unwritable name
    has the same shape: a declaration no expression can reach, in a language
    whose promise is that the file decides.
    """

    @pytest.mark.parametrize(
        'name',
        [
            pytest.param('', id='empty'),
            pytest.param(' ', id='a-space'),
            pytest.param('a b', id='two-words'),
            pytest.param('1x', id='leading-digit'),
            pytest.param('a-b', id='a-hyphen'),
            pytest.param('a.b', id='a-dot'),
        ],
    )
    @pytest.mark.parametrize(
        'section',
        [
            'dimensions',
            'lookups',
            'parameters',
            'variables',
            'expressions',
            'macros',
            'constraints',
            'piecewise',
            'sos',
        ],
    )
    def test_a_name_no_expression_could_write_is_refused(self, section: str, name: str):
        declarations: dict[str, Any] = {
            'dimensions': {'dtype': 'str'},
            'lookups': {'over': 'g', 'into': 'h'},
            'parameters': {'dims': ['g']},
            'variables': {'foreach': ['g']},
            'expressions': {'expression': 'c'},
            'macros': {'args': ['x'], 'template': 'x * 2'},
            'constraints': {'foreach': ['g'], 'expression': 'p <= c'},
            'piecewise': {'over': 'g', 'links': [['p', 'c'], ['q', 'c']], 'method': 'convex'},
            'sos': {'variable': 'p', 'over': 'g', 'type': 1},
        }
        model = copy.deepcopy(SMALL_MODEL)
        model.setdefault(section, {})[name] = declarations[section]
        with pytest.raises(LanguageError, match='is not a name'):
            to_spec(model)

    def test_the_message_names_the_rewrite(self):
        model = copy.deepcopy(SMALL_MODEL)
        model['parameters']['a b'] = {'dims': ['g']}
        message = _refusal(model)
        assert "'a b'" in message, 'the offending name is quoted'
        assert 'letter or an underscore' in message, (
            'the message says what a name may be, not only that this is not one'
        )

    def test_an_ordinary_name_still_loads(self):
        assert 'headroom_2' in _schema(**{'parameters.headroom_2': {'dims': ['g']}}).parameters
