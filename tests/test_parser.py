# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The two grammars: expression strings and where strings.

Nothing here resolves names — a parse result still holds raw
``NameNode``/``Unresolved*`` nodes.
"""

import operator
from dataclasses import FrozenInstanceError

import pytest

import math_spec.program as program_module
from math_spec._expression_parser import (
    BinaryOperatorNode,
    ComparisonNode,
    FunctionCallNode,
    NameListNode,
    NameNode,
    NumberNode,
    UnaryOperatorNode,
    parse_expression,
)
from math_spec._where_parser import (
    UnresolvedComparisonNode,
    UnresolvedNameNode,
    UnresolvedPositionNode,
    parse_where,
)
from math_spec.errors import SchemaError
from math_spec.program import AndNode, BooleanLiteralNode, NotNode, OrNode, _conjuncts


def test_the_grammar_builds_the_program_s_own_node_classes():
    """The connectives and literals in a parse are `math_spec.program`'s classes.

    The parser constructs the resolved vocabulary's connectives directly, so a
    consumer's `isinstance` against the program's classes holds on any tree —
    two homes for `AndNode` would make it hold on neither.
    """
    tree = parse_where('a AND NOT b OR True')
    assert type(tree) is program_module.OrNode
    assert type(tree.left) is program_module.AndNode
    assert type(tree.left.right) is program_module.NotNode
    assert type(tree.right) is program_module.BooleanLiteralNode


@pytest.mark.parametrize(
    ('text', 'node_type', 'attrs'),
    [
        pytest.param('42', NumberNode, {'value': 42}, id='an-integer'),
        pytest.param('3.14', NumberNode, {'value': pytest.approx(3.14)}, id='a-decimal'),
        pytest.param('p_max', NameNode, {'name': 'p_max'}, id='a-name'),
        pytest.param('a + b', BinaryOperatorNode, {'op': '+'}, id='a-binary-operator'),
        pytest.param('-x', UnaryOperatorNode, {'op': '-'}, id='a-unary-operator'),
        pytest.param('p <= p_max', ComparisonNode, {'op': '<='}, id='a-comparison'),
        pytest.param('sum(p, over=g) == load', ComparisonNode, {'op': '=='}, id='a-comparison-over-a-call'),
        pytest.param('sum(p, over=generator)', FunctionCallNode, {'name': 'sum'}, id='a-call'),
    ],
)
def test_an_expression_parses_to_its_node(text, node_type, attrs):
    node = parse_expression(text)
    assert isinstance(node, node_type)
    for attr, expected in attrs.items():
        assert getattr(node, attr) == expected


@pytest.mark.parametrize(
    ('text', 'tree'),
    [
        pytest.param(
            'a + b * c',
            BinaryOperatorNode('+', NameNode('a'), BinaryOperatorNode('*', NameNode('b'), NameNode('c'))),
            id='multiplication-binds-tighter-than-addition',
        ),
        pytest.param(
            '(a + b) * c',
            BinaryOperatorNode('*', BinaryOperatorNode('+', NameNode('a'), NameNode('b')), NameNode('c')),
            id='parentheses-override-precedence',
        ),
        pytest.param(
            '-a ** 2',
            UnaryOperatorNode('-', BinaryOperatorNode('**', NameNode('a'), NumberNode(2))),
            id='a-negation-is-over-the-power-not-under-it',
        ),
        pytest.param(
            '-a * b',
            BinaryOperatorNode('*', UnaryOperatorNode('-', NameNode('a')), NameNode('b')),
            id='a-negation-binds-tighter-than-a-product',
        ),
    ],
)
def test_precedence(text, tree):
    assert parse_expression(text) == tree


def test_a_call_carries_its_positional_and_keyword_arguments():
    node = parse_expression('sum(p * cost, over=generator)')
    assert len(node.args) == 1, 'one positional argument; the keyword is not among them'
    assert isinstance(node.args[0], BinaryOperatorNode), 'the argument is an expression, not just a name'
    assert 'over' in node.kwargs


@pytest.mark.parametrize(
    ('rewrite', 'error', 'match'),
    [
        pytest.param(
            lambda node: setattr(node, 'op', '>='), FrozenInstanceError, 'cannot assign', id='a-comparison-sense'
        ),
        pytest.param(
            lambda node: operator.setitem(node.left.kwargs, 'over', NameNode('snapshot')),
            TypeError,
            'does not support item assignment',
            id='a-reduction-axis',
        ),
    ],
)
def test_a_parsed_expression_cannot_be_rewritten_under_another_pass(rewrite, error, match):
    """A pass handed a parsed tree could rewrite the operand another one reads.

    The expression nodes were plain dataclasses while every where and program
    node was frozen (#197): `node.op = '<='` flipped a shared comparison and
    `node.kwargs['over'] = ...` re-aimed a reduction, with no error anywhere.
    """
    node = parse_expression('sum(p * cost, over=generator) == load')
    with pytest.raises(error, match=match):
        rewrite(node)


def test_a_call_copies_the_kwargs_it_is_handed():
    """A caller's own dict is copied on the way in, so holding it is not a back door either."""
    passed = {'over': NameNode('generator')}
    built = FunctionCallNode('sum', (NameNode('p'),), passed)
    passed['over'] = NameNode('snapshot')
    assert built.kwargs == {'over': NameNode('generator')}, 'the dict handed in was copied, not aliased'
    assert isinstance(hash(built), int), 'kwargs sits outside the hash, so a call hashes like every other node'


@pytest.mark.parametrize(
    ('text', 'rewrite'),
    [
        pytest.param('p < p_max', r'the senses are <=, >= and ==\. Write the bound inclusive', id='strict-less'),
        pytest.param('p > 0', r'the senses are <=, >= and ==\. Write the bound inclusive', id='strict-greater'),
        pytest.param('status != 0', r'write the test in where:, where != is legal', id='not-equals-is-a-where-matter'),
        pytest.param('p = p_max', r'Equality between two sides is written ==', id='a-lone-equals'),
        pytest.param('p ^ 2', r"power is written '\*\*', not '\^'", id='caret-for-power'),
        pytest.param('0 <= p <= p_max', r'Split the chain into two constraints', id='a-chained-comparison'),
    ],
)
def test_a_parse_failure_names_the_rewrite(text, rewrite):
    """The predictable mistakes are refused with their rewrite, not the grammar's complaint alone."""
    with pytest.raises(SchemaError, match=rewrite):
        parse_expression(text)


@pytest.mark.parametrize(
    'fragment',
    [pytest.param('Failed to parse', id='the-refusal'), pytest.param('Expected', id='the-grammar-s-complaint')],
)
def test_a_failure_with_no_diagnosis_still_shows_the_grammar_s_complaint(fragment):
    with pytest.raises(SchemaError, match=fragment):
        parse_expression('a +')


def test_an_exponent_may_be_negated_and_a_negation_stacked():
    assert parse_expression('2 ** -1').right == UnaryOperatorNode('-', NumberNode(1))
    assert parse_expression('--x') == UnaryOperatorNode('-', UnaryOperatorNode('-', NameNode('x')))


def test_a_keyword_given_twice_is_refused_not_overwritten():
    with pytest.raises(SchemaError, match='sum\\(over=\\) is given twice'):
        parse_expression('sum(p, over=snapshot, over=generator)')


def test_a_list_of_names_is_a_kwarg_value():
    """`by=[a, b]` is one value, so the operator reads one grouping and not two."""
    node = parse_expression('sum(p, by=[a, b])')
    assert node.kwargs['by'] == NameListNode(('a', 'b'))


@pytest.mark.parametrize(
    'text',
    [
        pytest.param('sum(p, by=[a,])', id='a-trailing-comma'),
        pytest.param('sum(p, by=[])', id='no-names-at-all'),
        pytest.param('sum(p, by=[a b])', id='a-missing-comma'),
        pytest.param('sum(p, by=[a)', id='an-unclosed-bracket'),
        pytest.param('sum([p], over=g)', id='a-positional-argument'),
        pytest.param('p + [c]', id='a-term'),
        pytest.param('[a, b]', id='the-whole-expression'),
    ],
)
def test_a_list_the_grammar_cannot_read_is_refused_at_load(text):
    """A list is a kwarg value and nothing else, and the last three say so."""
    with pytest.raises(SchemaError, match='Failed to parse expression'):
        parse_expression(text)


@pytest.mark.parametrize(
    ('text', 'value'),
    [
        pytest.param('1e5', 1e5, id='a-bare-exponent'),
        pytest.param('2.5E-3', 2.5e-3, id='an-upper-case-negative-exponent'),
        pytest.param('1e+3', 1e3, id='a-signed-exponent'),
        pytest.param('7.e2', 700.0, id='a-trailing-point-mantissa'),
    ],
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
    """`Literal('inf')` matched a prefix, so `inflow` parsed as `inf` and failed on `low`."""
    assert parse_expression(f'a + {name}').right == NameNode(name)


@pytest.mark.parametrize(
    ('text', 'node_type', 'attrs'),
    [
        pytest.param('True', BooleanLiteralNode, {'value': True}, id='a-literal'),
        pytest.param('p_max', UnresolvedNameNode, {'name': 'p_max'}, id='a-bare-name'),
        pytest.param('p_max > 0', UnresolvedComparisonNode, {'op': '>', 'value': 0}, id='a-comparison'),
        pytest.param('a AND b', AndNode, {}, id='and'),
        pytest.param('a OR b', OrNode, {}, id='or'),
        pytest.param('NOT a', NotNode, {}, id='not'),
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
    assert parse_where('a OR b AND c') == OrNode(
        UnresolvedNameNode('a'), AndNode(UnresolvedNameNode('b'), UnresolvedNameNode('c'))
    )


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('a', ['a']),
        ('a AND b', ['a', 'b']),
        ('a AND b AND c', ['a', 'b', 'c']),
    ],
    ids=['single', 'pair', 'chain'],
)
def test_conjuncts_flattens_the_and_spine(text, expected):
    """A chain the grammar left-folds into nested `AndNode`s comes back flat (#312).

    `_conjuncts` is the one home of the flatten rule; `Mask.conjuncts` is the
    door a consumer asks it through."""
    assert [n.name for n in _conjuncts(parse_where(text))] == expected


@pytest.mark.parametrize(
    'text',
    ['a OR b', 'NOT a', 'a AND b OR c', 'NOT (a AND b)'],
    ids=['or', 'not', 'or-of-and', 'not-of-and'],
)
def test_conjuncts_does_not_split_or_or_not(text):
    result = _conjuncts(parse_where(text))
    assert result == (parse_where(text),), 'a non-AND top node is its own only conjunct'


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
    """Quoting says "label, not name" (#460): unquoted, `combined-cycle` or `CCGT 400MW` was
    unsayable, and a bare word may name a declaration."""
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


@pytest.mark.parametrize(
    ('text', 'rewrite'),
    [
        pytest.param('p_max > 0 & committable', r'written AND', id='ampersand'),
        pytest.param('p_max > 0 && committable', r'written AND', id='doubled-ampersand'),
        pytest.param('p_max > 0 | committable', r'written OR', id='pipe'),
        pytest.param('p_max > 0 || committable', r'written OR', id='doubled-pipe'),
        pytest.param('~committable', r'written NOT, before the predicate', id='tilde'),
        pytest.param('!committable', r'written NOT, before the predicate', id='bang'),
        pytest.param('status = 0', r'equality is written ==', id='a-lone-equals'),
    ],
)
def test_a_where_parse_failure_names_the_rewrite(text, rewrite):
    """The connective habits of pandas and C are refused with their rewrite, not the grammar's complaint alone."""
    with pytest.raises(SchemaError, match=rewrite):
        parse_where(text)


def test_a_legal_where_operator_is_never_diagnosed():
    """`!=`, `<` and `>` are predicates here, unlike on the expression side, so no diagnosis may fire on them."""
    assert parse_where('status != 0') == UnresolvedComparisonNode('status', '!=', 0.0)
    assert parse_where('p_max < 5') == UnresolvedComparisonNode('p_max', '<', 5.0)


def test_an_unrelated_parse_failure_says_nothing_about_positions():
    with pytest.raises(SchemaError) as excinfo:
        parse_where('p_max >')
    assert 'position()' not in str(excinfo.value)


def test_a_string_parses_to_one_shared_tree():
    """Drop the memo and this passes on `==` alone — `is` is the claim."""
    text = 'sum(p * cost, over=generator) == load'
    assert parse_expression(text) is parse_expression(text), 'the same expression string parses to one tree'
    assert parse_where('p_max > 0') is parse_where('p_max > 0'), 'and so does the same where string'


def test_a_parse_failure_is_raised_every_time_it_is_asked_for():
    """A memo that cached the failure would hand the second caller a traceback from the first."""
    for _ in range(2):
        with pytest.raises(SchemaError, match=r"power is written '\*\*'"):
            parse_expression('p ^ 2')
