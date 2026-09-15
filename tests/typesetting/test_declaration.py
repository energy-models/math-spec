# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""One declaration typesets to the bare line the whole-model render prints for it."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from math_spec import LanguageError, SchemaError, typeset_declaration
from tests.fixtures import DISPATCH_MODEL as DISPATCH
from tests.fixtures import override
from tests.typesetting.fixtures import EVERY_FORMAT
from tests.typesetting.test_cases import CASED

if TYPE_CHECKING:
    from math_spec.typesetting import FormatName
    from math_spec.typesetting.format import Format

#: A variable-carrying reduction, a scalar reduction, a data-only body, and a
#: constraint reading the first — the shapes a line has to read.
PLAIN = override(
    DISPATCH,
    **{
        'expressions.spend': 'sum(p * cost, over=generator)',
        'expressions.total': 'sum(p)',
        'expressions.priced': 'cost * 2',
        'constraints.budgeted': {'dims': ['snapshot'], 'where': 'load > 0', 'expression': 'spend <= 10'},
    },
)


@pytest.mark.parametrize(
    ('model', 'name', 'expected'),
    [
        pytest.param(
            PLAIN,
            'spend',
            r'\mathit{spend}_{t} = \sum_{g \in \mathcal{G}} p_{t,g} \cdot \mathrm{cost}_{g} \qquad \forall\, t \in \mathcal{T}',
            id='a-plain-expression-a-variable-reaches-so-the-symbol-is-italic',
        ),
        pytest.param(
            PLAIN,
            'total',
            r'\mathit{total} = \sum_{t \in \mathcal{T},\ g \in \mathcal{G}} p_{t,g}',
            id='a-scalar-expression-no-subscript-no-quantifier',
        ),
        pytest.param(
            PLAIN,
            'priced',
            r'\mathrm{priced}_{g} = \mathrm{cost}_{g} \cdot 2 \qquad \forall\, g \in \mathcal{G}',
            id='a-data-only-expression-so-the-symbol-is-upright',
        ),
        pytest.param(
            CASED,
            'headroom',
            r'\mathrm{headroom}_{t,g} = \begin{cases} \mathrm{p}^{\mathrm{max}}_{g} & '
            r'\text{if } \mathrm{pos}(t) = 0 \\ 0 & \text{otherwise} \end{cases} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}',
            id='a-cased-expression-keeps-its-cases-layout',
        ),
        pytest.param(
            PLAIN,
            'budgeted',
            r'\sum_{g \in \mathcal{G}} p_{t,g} \cdot \mathrm{cost}_{g} \le 10 \qquad '
            r'\forall\, t \in \mathcal{T} \,:\, \mathrm{load}_{t} > 0',
            id='a-constraint-with-its-mask-on-the-quantifier-and-its-expression-inlined',
        ),
        pytest.param(
            PLAIN,
            'p',
            r'0 \le p_{t,g} \le \mathrm{p}^{\mathrm{max}}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}',
            id='a-variable-prints-its-domain',
        ),
    ],
)
def test_a_declaration_prints_the_line_the_whole_model_render_prints(model: dict, name: str, expected: str):
    """The frame comes from the declared `dims` of a cased expression, a
    constraint or a variable, and from the body's own dims of a plain
    expression; the given/chosen cut a variable inside it decides."""
    assert typeset_declaration(model, name, 'latex') == expected


@EVERY_FORMAT
def test_the_line_is_bare_math_with_its_quantifier(name: FormatName, fmt: Format):
    """No label, no delimiters, no number: the caller lays it out. The
    quantifier stays, since without it a constraint's mask is lost."""
    line = typeset_declaration(PLAIN, 'budgeted', name)
    assert fmt.operators['forall'] in line and fmt.operators['such_that'] in line, 'quantifier and mask'
    assert 'budgeted' not in line, 'the label is the name the caller already holds'
    assert not line.startswith(('$', '\\begin')), 'math only, for a math context the caller controls'


def test_a_line_on_its_own_inlines_the_expressions_it_uses_unless_told_otherwise():
    """No Definitions section stands beside one line, so `budgeted` reads `spend` by body by default and by symbol on request."""
    by_symbol = typeset_declaration(PLAIN, 'budgeted', 'latex', inline_expressions=False)
    by_body = typeset_declaration(PLAIN, 'budgeted', 'latex')
    assert by_symbol.startswith(r'\mathit{spend}_{t} \le 10')
    assert by_body.startswith(r'\sum_{g \in \mathcal{G}} p_{t,g} \cdot \mathrm{cost}_{g} \le 10')
    assert typeset_declaration(PLAIN, 'spend', 'latex', inline_expressions=True).startswith(r'\mathit{spend}_{t} ='), (
        'asked for by name, a plain expression prints its definition whether or not its uses inline it'
    )


def test_a_symbol_table_renames_an_expression_either_way():
    table = {'notation': 'latex', 'names': {'headroom': r'\bar h'}}
    assert typeset_declaration(CASED, 'headroom', 'latex', symbols=table).startswith(r'\bar h_{t,g} =')
    table = {'notation': 'latex', 'names': {'spend': 'S'}}
    assert typeset_declaration(PLAIN, 'spend', 'latex', symbols=table).startswith('S_{t} =')


def test_a_body_naming_another_expression_inlines_it_on_its_own_and_names_it_in_the_document():
    """On its own, `double_spend` is complete only with `spend` substituted; in
    the document both are defined, each once, so a use prints the symbol."""
    model = override(PLAIN, **{'expressions.double_spend': 'spend * 2'})
    assert typeset_declaration(model, 'double_spend', 'latex') == (
        r'\mathit{double\_spend}_{t} = \left( \sum_{g \in \mathcal{G}} p_{t,g} \cdot \mathrm{cost}_{g} \right) '
        r'\cdot 2 \qquad \forall\, t \in \mathcal{T}'
    )
    assert typeset_declaration(model, 'double_spend', 'latex', inline_expressions=False) == (
        r'\mathit{double\_spend}_{t} = \mathit{spend}_{t} \cdot 2 \qquad \forall\, t \in \mathcal{T}'
    )


@pytest.mark.parametrize(
    ('name', 'match'),
    [
        pytest.param('spent', r"'spent' is not a named expression, constraint or variable.*spend", id='a-near-miss'),
        pytest.param('objective', r"'objective' is not a named expression", id='the-objective-has-no-name'),
    ],
)
def test_a_name_declared_as_none_of_the_three_is_refused(name: str, match: str):
    with pytest.raises(SchemaError, match=match):
        typeset_declaration(PLAIN, name, 'latex')


def test_a_name_shared_by_a_constraint_and_a_variable_is_refused_rather_than_guessed():
    """Constraints sit outside the flat namespace, so the model admits the pair; one line prints one of them."""
    model = override(PLAIN, **{'constraints.p': {'dims': ['snapshot', 'generator'], 'expression': 'p <= 1'}})
    with pytest.raises(SchemaError, match="'p' is both a constraint and a variable"):
        typeset_declaration(model, 'p', 'latex')


def test_a_format_nobody_spells_is_refused():
    with pytest.raises(ValueError, match="'docx' is not a format this package prints"):
        typeset_declaration(PLAIN, 'spend', 'docx')  # pyrefly: ignore[bad-argument-type]  # the refusal under test


def test_an_invalid_model_is_refused_before_anything_renders():
    broken = override(PLAIN, **{'expressions.spend': 'p * nonexistent'})
    with pytest.raises(LanguageError):
        typeset_declaration(broken, 'spend', 'latex')
