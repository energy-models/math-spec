# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""A cased expression is the one named expression that prints: once, as a definition, and its uses name it."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from math_spec import SchemaError, to_latex, to_spec, typeset
from math_spec.piecewise import expand_piecewise
from math_spec.resolution import Namespace
from math_spec.typesetting.symbols import chosen_expressions, printed_expressions
from tests.fixtures import DISPATCH_MODEL as DISPATCH
from tests.fixtures import override
from tests.typesetting.fixtures import EVERY_FORMAT

if TYPE_CHECKING:
    from math_spec.typesetting.format import Format

#: One region and the fallback. `opening` is a column and `otherwise` a scalar,
#: so the cases alone would not give a quantity its shape — the `foreach` does.
BY_REGION = {
    'foreach': ['snapshot', 'generator'],
    'cases': {'opening': {'when': 'position(snapshot) == 0', 'expression': 'p_max'}},
    'otherwise': 0,
}

#: The dispatch model, with a quantity defined by region and a constraint using it.
CASED = override(
    DISPATCH,
    **{
        'expressions.headroom': BY_REGION,
        'constraints.spare': {'foreach': ['snapshot', 'generator'], 'expression': 'p <= headroom'},
    },
)

#: One cased expression reached only through another's case. `opening_cost` has
#: no variable of its own — its route to one runs through `headroom`.
_NESTED = override(
    CASED,
    **{
        'expressions.headroom.cases.opening.expression': 'p',
        'expressions.opening_cost.foreach': ['snapshot', 'generator'],
        'expressions.opening_cost.cases': {
            'opening': {'when': 'position(snapshot) == 0', 'expression': 'headroom * cost'},
        },
        'expressions.opening_cost.otherwise': 0,
        'constraints.spare.expression': 'p <= opening_cost',
    },
)


@EVERY_FORMAT
def test_a_cased_expression_is_the_exception_that_keeps_its_name(fmt: Format):
    """The other way round — the block inlined at each use — is what the AST does
    and the wrong thing to print: a block three arms tall puts whatever follows
    it beside its middle row."""
    rendered = typeset(CASED, fmt, legend=False)
    indexed = fmt.subscript(fmt.upright('headroom'), ['t', 'g'])
    assert rendered.count(indexed) == 2, (
        'one use and one definition, no more — counted indexed, because Typst spells a row label and an upright '
        'symbol the same way and only the symbol carries the dims'
    )
    sections = [title for title in ('Objective', 'Subject to', 'Definitions', 'Variable domains') if title in rendered]
    assert sections == ['Objective', 'Subject to', 'Definitions', 'Variable domains'], (
        'the definition has a section of its own, after the constraints and before the domains'
    )


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
@pytest.mark.parametrize(
    ('patch', 'chosen'),
    [
        pytest.param(
            {'expressions.headroom.cases': {'running': {'when': 'p', 'expression': 'p_max'}}},
            False,
            id='a-when-naming-a-variable-leaves-it-given',
        ),
        pytest.param({'expressions.headroom.cases.opening.expression': 'p'}, True, id='a-case-reaching-a-variable'),
        pytest.param({'expressions.headroom.otherwise': 'p'}, True, id='the-fallback-reaching-a-variable'),
    ],
)
def test_a_cased_expression_is_chosen_when_a_value_reaching_it_is(fmt: Format, patch: dict, chosen: bool):
    """A `when` mentioning a variable does not make the quantity one: the mask
    asks whether the variable *exists* at a coordinate, which the model settles
    when it is built. Only a value reaching one is a quantity the solver
    returns, and one case holding a variable is enough. The `otherwise:` is a
    value of the quantity like any case's, so a walk reading only the cases
    prints a solved quantity upright."""
    rendered = typeset(override(CASED, **patch), fmt, legend=False)
    italic, upright = (fmt.subscript(face('headroom'), ['t', 'g']) for face in (fmt.italic, fmt.upright))
    assert (italic in rendered) is chosen, 'the quantity is chosen exactly when a value reaching it holds a variable'
    assert (upright in rendered) is not chosen, 'and given otherwise, however its regions are chosen'


@EVERY_FORMAT
def test_a_definition_naming_another_one_prints_both(fmt: Format):
    """The cases are walked too, so the collection runs to a fixpoint."""
    rendered = typeset(_NESTED, fmt, legend=False)
    assert fmt.italic('headroom') in rendered, 'the inner definition was reached through a case'
    assert rendered.count(fmt.subscript(fmt.italic('opening_cost'), ['t', 'g'])) == 2, (
        'the outer definition and its one use'
    )


def test_a_variable_reached_through_another_cased_expression_still_prints_chosen():
    """The given/chosen cut follows the whole chain, not one link of it.

    `opening_cost` names `headroom` and nothing else that moves; `headroom`
    holds a variable. A walk stopping at the inner block would print the outer
    one upright — a quantity the solver decides, set as one the model was handed.
    """
    schema = expand_piecewise(to_spec(_NESTED))
    assert chosen_expressions(schema, Namespace.of(schema)) == {'headroom', 'opening_cost'}, (
        'the chain is followed to its end, so both are chosen'
    )


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
