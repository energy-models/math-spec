# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The two grammars: expression strings and where strings.

Nothing here resolves names — a parse result still holds raw
``NameNode``/``Unresolved*`` nodes.
"""

import pytest

from math_spec.errors import SchemaError
from math_spec.expression_parser import (
    BinaryOperatorNode,
    ComparisonNode,
    FunctionCallNode,
    NameNode,
    NumberNode,
    UnaryOperatorNode,
    parse_expression,
)
from math_spec.where_parser import (
    AndNode,
    BooleanLiteralNode,
    NotNode,
    OrNode,
    UnresolvedComparisonNode,
    UnresolvedNameNode,
    UnresolvedPositionNode,
    parse_where,
)


@pytest.mark.parametrize(
    ('text', 'node_type', 'attrs'),
    [
        ('42', NumberNode, {'value': 42}),
        ('3.14', NumberNode, {'value': pytest.approx(3.14)}),
        ('p_max', NameNode, {'name': 'p_max'}),
        ('a + b', BinaryOperatorNode, {'op': '+'}),
        ('-x', UnaryOperatorNode, {'op': '-'}),
        ('p <= p_max', ComparisonNode, {'op': '<='}),
        ('sum(p, over=g) == load', ComparisonNode, {'op': '=='}),
        ('sum(p, over=generator)', FunctionCallNode, {'name': 'sum'}),
    ],
)
def test_an_expression_parses_to_its_node(text, node_type, attrs):
    node = parse_expression(text)
    assert isinstance(node, node_type)
    for attr, expected in attrs.items():
        assert getattr(node, attr) == expected


def test_multiplication_binds_tighter_than_addition():
    node = parse_expression('a + b * c')
    assert node.op == '+'
    assert isinstance(node.right, BinaryOperatorNode)
    assert node.right.op == '*'


def test_parentheses_override_precedence():
    node = parse_expression('(a + b) * c')
    assert node.op == '*'
    assert isinstance(node.left, BinaryOperatorNode)
    assert node.left.op == '+'


def test_a_call_carries_its_positional_and_keyword_arguments():
    node = parse_expression('sum(p * cost, over=generator)')
    assert len(node.args) == 1
    assert isinstance(node.args[0], BinaryOperatorNode), 'the argument is an expression, not just a name'
    assert 'over' in node.kwargs


def test_an_unparseable_expression_is_an_error():
    with pytest.raises(SchemaError, match='Failed to parse'):
        parse_expression('a +')


def test_a_negation_is_over_the_power_not_under_it():
    """`-a ** 2` is `-(a ** 2)`, as in every language a modeller has met — a
    file writing `-cost ** 2` means minus the square, not the square of minus."""
    node = parse_expression('-a ** 2')
    assert isinstance(node, UnaryOperatorNode) and node.op == '-'
    assert isinstance(node.operand, BinaryOperatorNode) and node.operand.op == '**'


def test_a_negation_binds_tighter_than_a_product():
    node = parse_expression('-a * b')
    assert node.op == '*'
    assert isinstance(node.left, UnaryOperatorNode)


def test_an_exponent_may_be_negated_and_a_negation_stacked():
    assert parse_expression('2 ** -1').right == UnaryOperatorNode('-', NumberNode(1))
    assert parse_expression('--x') == UnaryOperatorNode('-', UnaryOperatorNode('-', NameNode('x')))


def test_a_keyword_given_twice_is_refused_not_overwritten():
    with pytest.raises(SchemaError, match='sum\\(over=\\) is given twice'):
        parse_expression('sum(p, over=snapshot, over=generator)')


@pytest.mark.parametrize(
    ('text', 'value'),
    [('1e5', 1e5), ('2.5E-3', 2.5e-3), ('1e+3', 1e3), ('7.e2', 700.0)],
)
def test_scientific_notation_is_a_number(text, value):
    assert parse_expression(text) == NumberNode(value)
    assert parse_where(f'p > {text}').value == value


@pytest.mark.parametrize('spelling', ['inf', '.inf'])
def test_inf_is_a_literal(spelling):
    """Both spellings, since `bounds: {upper: .inf}` is how YAML writes it."""
    assert parse_expression(f'p <= {spelling}').right == NumberNode(float('inf'))


@pytest.mark.parametrize('name', ['inflow', 'influx', 'infeed', 'infrastructure', 'inf_max'])
def test_a_name_may_begin_with_inf(name):
    """`Literal('inf')` matched a prefix, so `inflow` parsed as `inf` and then
    failed on `low` — reported as "Expected end of text", which names neither
    the literal nor the real problem. `inflow` is the archetype: hydro models
    have one, and nothing in the corpus did."""
    assert parse_expression(f'a + {name}').right == NameNode(name)


@pytest.mark.parametrize(
    ('text', 'node_type', 'attrs'),
    [
        ('True', BooleanLiteralNode, {'value': True}),
        ('p_max', UnresolvedNameNode, {'name': 'p_max'}),
        ('p_max > 0', UnresolvedComparisonNode, {'op': '>', 'value': 0}),
        ('a AND b', AndNode, {}),
        ('a OR b', OrNode, {}),
        ('NOT a', NotNode, {}),
    ],
)
def test_a_where_string_parses_to_its_node(text, node_type, attrs):
    """A bare name parses to an existence check; what it *names* is
    resolution's problem, not the parser's."""
    node = parse_where(text)
    assert isinstance(node, node_type)
    for attr, expected in attrs.items():
        assert getattr(node, attr) == expected


def test_and_binds_tighter_than_or():
    node = parse_where('a OR b AND c')
    assert isinstance(node, OrNode)
    assert isinstance(node.right, AndNode)


@pytest.mark.parametrize(
    ('text', 'value', 'quoted'),
    [
        ("g == 'wind'", 'wind', True),
        ('g == "wind"', 'wind', True),
        ("g == 'combined-cycle'", 'combined-cycle', True),
        ("g == 'CCGT 400MW'", 'CCGT 400MW', True),
        ("t > '2030-01-01'", '2030-01-01', True),
        ("g == 'it\\'s'", "it's", True),
        ('g == wind', 'wind', False),
    ],
    ids=['single', 'double', 'hyphen', 'space', 'date', 'escaped quote', 'bare'],
)
def test_a_quoted_right_hand_side_is_a_label(text, value, quoted):
    """Quoting marks a label. A bare word still parses, and still means
    "resolve me" rather than "label".

    Without quoting, any label carrying a hyphen, space or colon was
    unsayable — `combined-cycle`, `IT-north`, `CCGT 400MW` (#460).

    The flag is the whole point: a bare word may name a declaration and is
    refused for that ambiguity, so quoting is what says "label, not name".
    """
    node = parse_where(text)
    assert isinstance(node, UnresolvedComparisonNode)
    assert node.value == value
    assert node.quoted is quoted


@pytest.mark.parametrize(
    ('text', 'op', 'position', 'by'),
    [
        ('position(snapshot) == 0', '==', 0, None),
        ('position(snapshot) != 0', '!=', 0, None),
        ('position(snapshot) > 0', '>', 0, None),
        ('position(snapshot) <= -2', '<=', -2, None),
        ('position(snapshot) == -1', '==', -1, None),
        ('position(snapshot, by=period_of) == 0', '==', 0, 'period_of'),
    ],
    ids=['first', 'not first', 'after the first', 'band from the back', 'last', 'grouped'],
)
def test_position_converts_a_dimension_to_where_a_row_sits(text, op, position, by):
    """`position(dim)` is the left-hand side, so every comparator reads one way (#32)."""
    node = parse_where(text)
    assert isinstance(node, UnresolvedPositionNode)
    assert node.dimension == 'snapshot'
    assert node.op == op
    assert node.position == position
    assert node.by == by


def test_a_position_is_not_confused_with_a_name():
    """`position` leads the alternation, so it is not read as a bare name."""
    assert isinstance(parse_where('position(t) == 0 AND p_max > 0'), AndNode)


def test_a_coordinate_comparison_is_still_a_value_comparison():
    """The other half of #32: comparing the dimension itself is unchanged."""
    node = parse_where("snapshot > '2030-01-01'")
    assert isinstance(node, UnresolvedComparisonNode)
    assert node.value == '2030-01-01'


def test_the_old_index_spelling_names_its_rewrite():
    """`index(dim, i)` is what every model wrote before #32, so this failure is read most."""
    with pytest.raises(SchemaError) as excinfo:
        parse_where('snapshot == index(snapshot, 0)')
    assert 'index() is now position()' in str(excinfo.value)
    assert "write 'position(dim) == i'" in str(excinfo.value)


def test_an_unrelated_parse_failure_says_nothing_about_positions():
    with pytest.raises(SchemaError) as excinfo:
        parse_where('p_max >')
    assert 'position()' not in str(excinfo.value)
