# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""One named expression typesets to the bare definition the whole-model render prints for it."""

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
#: three shapes the definition has to read: chosen, scalar, and given.
PLAIN = override(
    DISPATCH,
    **{
        'expressions.spend': 'sum(p * cost, over=generator)',
        'expressions.total': 'sum(p)',
        'expressions.priced': 'cost * 2',
    },
)


@pytest.mark.parametrize(
    ('model', 'name', 'expected'),
    [
        pytest.param(
            PLAIN,
            'spend',
            r'\mathit{spend}_{t} = \sum_{g \in \mathcal{G}} p_{t,g} \cdot \mathrm{cost}_{g} \qquad \forall\, t \in \mathcal{T}',
            id='chosen-a-variable-reaches-it-so-the-symbol-is-italic',
        ),
        pytest.param(
            PLAIN,
            'total',
            r'\mathit{total} = \sum_{t \in \mathcal{T},\ g \in \mathcal{G}} p_{t,g}',
            id='scalar-a-reduction-over-every-dim-leaves-no-subscript-and-no-quantifier',
        ),
        pytest.param(
            PLAIN,
            'priced',
            r'\mathrm{priced}_{g} = \mathrm{cost}_{g} \cdot 2 \qquad \forall\, g \in \mathcal{G}',
            id='given-no-variable-so-the-symbol-is-upright',
        ),
        pytest.param(
            CASED,
            'headroom',
            r'\mathrm{headroom}_{t,g} = \begin{cases} \mathrm{p}^{\mathrm{max}}_{g} & '
            r'\text{if } \mathrm{pos}(t) = 0 \\ 0 & \text{otherwise} \end{cases} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}',
            id='cased-keeps-its-cases-layout-under-the-indexed-symbol',
        ),
    ],
)
def test_a_named_expression_prints_its_definition(model: dict, name: str, expected: str):
    """The frame comes from the declared `foreach` of a cased expression and the
    body's own dims of a plain one, and the given/chosen cut a variable inside
    it decides — the same line the document prints under Definitions."""
    assert typeset_expression(model, name, 'latex') == expected


@EVERY_FORMAT
def test_the_definition_is_bare_math_with_its_quantifier(name: FormatName, fmt: Format):
    """No label, no delimiters, no number: the caller lays it out."""
    line = typeset_expression(PLAIN, 'spend', name)
    assert fmt.operators['forall'] in line, 'the frame prints as the quantifier, as the document does'
    assert not line.startswith(('$', '\\begin')), 'math only, for a math context the caller controls'
    assert fmt.prose('spend') not in line, 'the label is the name the caller already holds'


def test_a_symbol_table_renames_an_expression_cased_or_plain():
    table = {'notation': 'latex', 'names': {'headroom': r'\bar h'}}
    assert typeset_expression(CASED, 'headroom', 'latex', symbols=table).startswith(r'\bar h_{t,g} =')
    table = {'notation': 'latex', 'names': {'spend': 'S'}}
    assert typeset_expression(PLAIN, 'spend', 'latex', symbols=table).startswith('S_{t} =')


def test_a_body_naming_another_expression_prints_its_symbol():
    """`spend` is named, so `double_spend` prints its symbol; the document defines both, each once."""
    model = override(PLAIN, **{'expressions.double_spend': 'spend * 2'})
    assert typeset_expression(model, 'double_spend', 'latex') == (
        r'\mathit{double\_spend}_{t} = \mathit{spend}_{t} \cdot 2 \qquad \forall\, t \in \mathcal{T}'
    )


def test_an_unknown_name_is_refused_with_the_near_miss():
    with pytest.raises(SchemaError, match=r"'spent' is not a named expression.*spend"):
        typeset_expression(PLAIN, 'spent', 'latex')


def test_an_invalid_model_is_refused_before_anything_renders():
    broken = override(PLAIN, **{'expressions.spend': 'p * nonexistent'})
    with pytest.raises(LanguageError):
        typeset_expression(broken, 'spend', 'latex')
