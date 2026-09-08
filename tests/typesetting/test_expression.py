# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""One named expression typesets to a bare `symbol = body` fragment, plain or cased."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from math_spec import LanguageError, SchemaError, typeset_expression
from tests.fixtures import DISPATCH_MODEL as DISPATCH
from tests.fixtures import override
from tests.typesetting.fixtures import EVERY_FORMAT
from tests.typesetting.test_cases import CASED

if TYPE_CHECKING:
    from math_spec.typesetting import FormatName
    from math_spec.typesetting.format import Format

#: A variable-carrying reduction, a scalar reduction, and a data-only body — the
#: three shapes the fragment has to read: chosen, scalar, and given.
PLAIN = override(
    DISPATCH,
    **{
        'expressions.spend': 'sum(p * cost, over=generator)',
        'expressions.total': 'sum(p)',
        'expressions.priced': 'cost * 2',
    },
)


@pytest.mark.parametrize(
    ('name', 'expected'),
    [
        pytest.param(
            'spend',
            r'\mathit{spend}_{t} = \sum_{g \in \mathcal{G}} p_{t,g} \cdot \mathrm{cost}_{g}',
            id='chosen-a-variable-reaches-it-so-the-symbol-is-italic',
        ),
        pytest.param(
            'total',
            r'\mathit{total} = \sum_{t \in \mathcal{T},\ g \in \mathcal{G}} p_{t,g}',
            id='scalar-a-reduction-over-every-dim-leaves-no-subscript',
        ),
        pytest.param(
            'priced',
            r'\mathrm{priced}_{g} = \mathrm{cost}_{g} \cdot 2',
            id='given-no-variable-so-the-symbol-is-upright',
        ),
        pytest.param(
            'headroom',
            r'\mathrm{headroom}_{t,g} = \begin{cases} \mathrm{p}^{\mathrm{max}}_{g} & '
            r'\text{if } \mathrm{pos}(t) = 0 \\ 0 & \text{otherwise} \end{cases}',
            id='cased-keeps-its-cases-layout-under-the-indexed-symbol',
        ),
    ],
)
def test_a_named_expression_prints_its_defining_equation(name: str, expected: str):
    """The frame comes from the declared `foreach` of a cased expression and the
    substituted body's own dims of a plain one, and the given/chosen cut a
    variable inside it decides. `headroom` lives in CASED, the others in PLAIN."""
    model = CASED if name == 'headroom' else PLAIN
    assert typeset_expression(model, name, 'latex') == expected


@EVERY_FORMAT
def test_a_scalar_body_prints_a_bare_symbol_with_no_subscript(name: FormatName, fmt: Format):
    """A reduction over every dim leaves an empty frame, so the symbol carries no index."""
    assert typeset_expression(PLAIN, 'total', name).startswith(f'{fmt.italic("total")} {fmt.operators["equal"]} ')


@EVERY_FORMAT
def test_a_cased_expression_keeps_its_cases_layout(name: FormatName, fmt: Format):
    frag = typeset_expression(CASED, 'headroom', name)
    assert frag.startswith(f'{fmt.subscript(fmt.upright("headroom"), ["t", "g"])} {fmt.operators["equal"]} ')
    assert fmt.prose('otherwise') in frag, 'the fallback arm, printed as the cases block does everywhere'


def test_a_symbol_table_renames_a_cased_expression_but_never_a_plain_one():
    """The same cut the whole-model render draws: a table names only what prints there.

    A cased expression prints under its own name and may be renamed; a plain one
    is substituted away in the whole-model render, so an entry naming it is the
    dead entry the table is strict about, even though this fragment does print it.
    The refusal names why rather than offering a near miss: it is declared, just
    unrenamable.
    """
    table = {'notation': 'latex', 'names': {'headroom': r'\bar h'}}
    assert typeset_expression(CASED, 'headroom', 'latex', symbols=table).startswith(r'\bar h_{t,g} =')

    with pytest.raises(SchemaError, match='is a plain expression'):
        typeset_expression(PLAIN, 'spend', 'latex', symbols={'notation': 'latex', 'names': {'spend': 's'}})


def test_a_body_referencing_another_named_expression_inlines_it():
    """`spend` is substituted where it is named, so `double_spend` renders its
    body, never its name — the same expansion the whole-model render does."""
    model = override(PLAIN, **{'expressions.double_spend': 'spend * 2'})
    frag = typeset_expression(model, 'double_spend', 'latex')
    assert (
        frag
        == r'\mathit{double\_spend}_{t} = \left( \sum_{g \in \mathcal{G}} p_{t,g} \cdot \mathrm{cost}_{g} \right) \cdot 2'
    )


def test_an_unknown_name_is_refused_with_the_near_miss():
    with pytest.raises(SchemaError, match=r"'spent' is not a named expression.*spend"):
        typeset_expression(PLAIN, 'spent', 'latex')


def test_an_invalid_model_is_refused_before_anything_renders():
    broken = override(PLAIN, **{'expressions.spend': 'p * nonexistent'})
    with pytest.raises(LanguageError):
        typeset_expression(broken, 'spend', 'latex')
