# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""A cased expression is the one named expression that prints: once, as a definition, and its uses name it."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from math_spec import SchemaError, to_latex, to_spec, typeset
from math_spec.piecewise import expand_piecewise
from math_spec.typesetting.symbols import chosen_expressions, printed_expressions
from tests.fixtures import DISPATCH_MODEL as DISPATCH
from tests.fixtures import override
from tests.typesetting.fixtures import EVERY_FORMAT

if TYPE_CHECKING:
    from math_spec.typesetting.format import Format

#: One region and the default. `opening` is a column and the default a scalar,
#: so the cases alone would not give a quantity its shape — the `foreach` does.
BY_REGION = {
    'foreach': ['snapshot', 'generator'],
    'cases': {
        'opening': {'when': 'position(snapshot) == 0', 'expression': 'p_max'},
        'default': 0,
    },
}

#: The dispatch model, with a quantity defined by region and a constraint using it.
CASED = override(
    DISPATCH,
    **{
        'expressions.headroom': BY_REGION,
        'constraints.spare': {'foreach': ['snapshot', 'generator'], 'expression': 'p <= headroom'},
    },
)


def _sections(rendered: str) -> list[str]:
    """The section titles the render printed, in order."""
    return [title for title in ('Objective', 'Subject to', 'Definitions', 'Variable domains') if title in rendered]


@EVERY_FORMAT
def test_a_cased_expression_is_the_exception_that_keeps_its_name(fmt: Format):
    """It prints once, as a definition, and its uses name it.

    The other way round — the block inlined at each use — is what the AST does
    and the wrong thing to print: a block three arms tall puts whatever follows
    it beside its middle row.
    """
    rendered = typeset(CASED, fmt, legend=False)
    # counted indexed, because Typst spells a row label and an upright symbol
    # the same way and only the symbol carries the dims
    indexed = fmt.subscript(fmt.upright('headroom'), ['t', 'g'])
    assert rendered.count(indexed) == 2, 'one use and one definition, no more'
    assert _sections(rendered) == ['Objective', 'Subject to', 'Definitions', 'Variable domains']


@EVERY_FORMAT
def test_the_last_arm_prints_as_the_fallback_rather_than_a_condition(fmt: Format):
    """It has no `when` to print, and `otherwise` is how a paper writes that."""
    rendered = typeset(CASED, fmt, legend=False)
    assert fmt.prose('otherwise') in rendered
    assert rendered.count(fmt.prose('if ')) == 1, 'one arm carries a condition, and the fallback carries none'


@EVERY_FORMAT
def test_a_declared_definition_prints_whether_or_not_a_row_names_it(fmt: Format):
    """The rule a variable's domain follows: the file declared it, so it prints."""
    unused = override(CASED, **{'constraints.spare.expression': 'p <= p_max'})
    rendered = typeset(unused, fmt, legend=False)
    assert rendered.count(fmt.subscript(fmt.upright('headroom'), ['t', 'g'])) == 1, 'the definition, and no use'
    assert 'Definitions' in rendered


@EVERY_FORMAT
def test_a_case_is_given_when_its_values_are_however_its_regions_are_chosen(fmt: Format):
    """A `when` mentioning a variable does not make the quantity one.

    The mask asks whether the variable *exists* at a coordinate, which the
    model settles when it is built; only a value reaching one is a quantity the
    solver returns.
    """
    masked = override(
        CASED,
        **{
            'expressions.headroom.cases': {
                'running': {'when': 'p', 'expression': 'p_max'},
                'default': 0,
            }
        },
    )
    rendered = typeset(masked, fmt, legend=False)
    assert fmt.upright('headroom') in rendered, 'every case is a parameter, so the quantity is given'
    assert fmt.italic('headroom') not in rendered


@EVERY_FORMAT
def test_a_case_reaching_a_variable_is_chosen(fmt: Format):
    """One case holding a variable is enough: the solver decides the quantity."""
    decided = override(CASED, **{'expressions.headroom.cases.opening.expression': 'p'})
    assert fmt.italic('headroom') in typeset(decided, fmt, legend=False)


@EVERY_FORMAT
def test_a_definition_naming_another_one_prints_both(fmt: Format):
    """The cases are walked too, so the collection runs to a fixpoint."""
    rendered = typeset(_NESTED, fmt, legend=False)
    assert fmt.italic('headroom') in rendered, 'the inner definition was reached through a case'
    assert rendered.count(fmt.subscript(fmt.italic('opening_cost'), ['t', 'g'])) == 2


#: One cased expression reached only through another's case. `opening_cost` has
#: no variable of its own — its route to one runs through `headroom`.
_NESTED = override(
    CASED,
    **{
        'expressions.headroom.cases.opening.expression': 'p',
        'expressions.opening_cost.foreach': ['snapshot', 'generator'],
        'expressions.opening_cost.cases': {
            'opening': {'when': 'position(snapshot) == 0', 'expression': 'headroom * cost'},
            'default': 0,
        },
        'constraints.spare.expression': 'p <= opening_cost',
    },
)


def test_a_variable_reached_through_another_cased_expression_still_prints_chosen():
    """The given/chosen cut follows the whole chain, not one link of it.

    `opening_cost` names `headroom` and nothing else that moves; `headroom`
    holds a variable. A walk stopping at the inner block would print the outer
    one upright — a quantity the solver decides, set as one the model was handed.
    """
    schema = expand_piecewise(to_spec(_NESTED))
    assert chosen_expressions(schema) == {'headroom', 'opening_cost'}
    assert r'\mathit{opening\_cost}' in to_latex(_NESTED, legend=False)


def test_the_table_may_rename_a_cased_expression_but_not_a_plain_one():
    """It names what prints, and a cased expression is the only expression that does.

    An entry that never applies is the failure mode the table is strict about.
    """
    tex = to_latex(CASED, symbols={'notation': 'latex', 'names': {'headroom': r'\bar h'}}, legend=False)
    assert r'\bar h_{t,g}' in tex

    plain = override(DISPATCH, **{'expressions.supply': 'sum(p, over=generator)'})
    with pytest.raises(SchemaError, match='is not declared by the model'):
        to_latex(plain, symbols={'notation': 'latex', 'names': {'supply': 's'}}, legend=False)


def test_the_definitions_print_in_declaration_order():
    """The file's order, not a set's — six of them, so a shuffle cannot pass by luck.

    `printed_expressions` collected into a `frozenset`, whose iteration order
    follows string hashes and so is re-randomised every process: the section
    printed its rows in a different order on each run, and a generated page
    carrying two of them would churn on every regeneration.
    """
    declared = ['alpha', 'bravo', 'charlie', 'delta', 'echo', 'foxtrot']
    schema = expand_piecewise(to_spec(override(CASED, **{f'expressions.{n}': BY_REGION for n in declared})))
    assert list(printed_expressions(schema)) == ['headroom', *declared], "declaration order, the file's own"
