# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The normal form: one text for every file that means the same thing.

A reviewer diffs two models in an editor, and a text diff reports key order,
spacing and the order of terms in a sum — none of which is a difference in the
model. What is left after this form is applied is what the two files mean
differently, which is the question `to_yaml(canonical=True)` exists to answer.
"""

from __future__ import annotations

import itertools
import random
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import math_spec as ms
from math_spec.__main__ import main
from math_spec._expression_parser import (
    BinaryOperatorNode,
    ComparisonNode,
    FunctionCallNode,
    NameNode,
    NumberNode,
    UnaryOperatorNode,
    operand,
    parse_expression,
)
from math_spec.canonical import _factors, _signed_terms, canonical_text, laid_out, normalised
from tests.fixtures import DISPATCH_MODEL, EXAMPLES, override

if TYPE_CHECKING:
    from math_spec._expression_parser import ArithmeticNode, ParsedNode

#: Every model in the repository, the operator probes included. The symbol
#: tables under `examples/symbols/` are not models and do not load as one.
MODELS = [path for path in sorted(EXAMPLES.rglob('*.yaml')) if 'symbols' not in path.parts]
FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'every_program_node.yaml'


def _dumped(**patch: object) -> str:
    return ms.to_spec(override(DISPATCH_MODEL, **patch)).to_yaml(canonical=True)


def test_two_files_that_mean_the_same_thing_write_the_same_text():
    """The claim the form makes, over the three ambiguities a file carries: the
    order two declarations are written in, the order of the terms of a sum, and
    the order of the factors of a product."""
    one = ms.to_spec(
        {
            'dimensions': {'h': {'dtype': 'int'}, 'u': {'dtype': 'str'}},
            'parameters': {'cost': {'dims': ['u']}, 'cap': {'dims': ['u']}},
            'variables': {'p': {'dims': ['h', 'u'], 'bounds': {'lower': 0}}},
            'constraints': {'k': {'dims': ['h', 'u'], 'expression': 'p * cost + p - cap <= 10'}},
            'objective': {'sense': 'minimize', 'expression': 'sum(p * cost)'},
        }
    )
    other = ms.to_spec(
        {
            'parameters': {'cap': {'dims': ['u']}, 'cost': {'dims': ['u']}},
            'dimensions': {'u': {'dtype': 'str'}, 'h': {'dtype': 'int'}},
            'variables': {'p': {'dims': ['h', 'u'], 'bounds': {'lower': 0}}},
            'constraints': {'k': {'dims': ['h', 'u'], 'expression': '-cap + p + cost * p <= 10'}},
            'objective': {'sense': 'minimize', 'expression': 'sum(cost * p)'},
        }
    )
    assert one.to_yaml(canonical=True) == other.to_yaml(canonical=True), 'the two files say one model'
    assert one.to_yaml() != other.to_yaml(), 'and the dump that keeps the file as written still tells them apart'


@pytest.mark.parametrize('path', [*MODELS, FIXTURE], ids=lambda path: path.stem)
def test_the_form_loads_and_is_already_in_the_form(path):
    """Every model in the tree, dumped, re-read and dumped again.

    Idempotence is the property that makes the text a *normal* form rather than
    a rewriting: a second pass that moved anything would mean two files in the
    form could still differ. It is also what catches a print the grammar reads
    back as a different tree, which a leading negative term did.
    """
    text = ms.to_spec(path).to_yaml(canonical=True)
    assert ms.to_spec(text).to_yaml(canonical=True) == text, 'the form is a fixed point of itself'


@pytest.mark.parametrize(
    ('written', 'canonical'),
    [
        pytest.param('a + c + b', 'a\n+ b\n+ c', id='the-terms-of-a-sum-are-sorted'),
        pytest.param('c * a * b', '(a * b) * c', id='and-the-factors-of-a-product'),
        pytest.param('b - a', '-a\n+ b', id='a-term-carries-its-sign-as-it-moves'),
        pytest.param('a + -b', 'a\n- b', id='and-a-sign-written-twice-is-folded-once'),
        pytest.param('a - (b - c)', 'a\n- (b - c)', id='a-bracketed-group-stays-one-term'),
        pytest.param('b - a - c', '-a\n+ b\n- c', id='terms-sort-under-the-signs-they-keep'),
        pytest.param('2 * 3 * a', '(2 * 3) * a', id='a-constant-is-never-folded-into-another'),
        pytest.param('b / a', 'b / a', id='a-division-is-not-reordered'),
        pytest.param('b ** a', 'b ** a', id='nor-is-an-exponent'),
        pytest.param('shift(p, edge=0, along=t)', 'shift(p, along=t, edge=0)', id='a-calls-kwargs-are-sorted'),
        pytest.param('at(q, by=r) - p', 'at(q, by=r)\n- p', id='a-call-sorts-as-the-text-it-prints'),
    ],
)
def test_an_expression_is_written_one_way(written, canonical):
    assert canonical_text(written) == canonical, 'the normal form of the expression, whole'


def test_a_positional_argument_keeps_the_place_the_file_gave_it():
    """`sum(a, b)` is not `sum(b, a)` for any operator that takes two operands,
    so position is meaning and only keywords are sorted."""
    assert canonical_text('max(b, a)') == 'max(b, a)', 'the arguments stand where they were written'


def test_an_expression_of_one_term_stays_on_one_line():
    dumped = _dumped(**{'constraints.balance.expression': 'sum(p, over=generator) == load'})
    assert 'expression: sum(p, over=generator) == load' in dumped, 'nothing to break across lines'


def test_a_sum_is_broken_one_term_to_a_line():
    """What a term-per-line layout buys: a changed term is one line of a diff
    rather than a rewritten expression."""
    dumped = _dumped(**{'constraints.balance.expression': 'sum(p, over=generator) - load + 1 == 0'})
    assert '\n      1\n      - load\n      + sum(p, over=generator)\n      == 0\n' in dumped, (
        'the block scalar holds one term per line, each under its own sign, and the comparison closes it'
    )


def test_the_declarations_of_a_section_are_sorted_by_name():
    dumped = ms.to_spec(
        override(DISPATCH_MODEL, **{'constraints.a_cap.dims': [], 'constraints.a_cap.expression': 'sum(p) >= 0'})
    ).to_yaml(canonical=True)
    assert dumped.index('a_cap:') < dumped.index('balance:'), 'a section reads in name order, not file order'


def test_the_dump_that_keeps_the_file_as_written_is_unchanged():
    """The default is the round trip `reading.md` documents, and the form is an
    argument away rather than a change to it."""
    spec = ms.to_spec(DISPATCH_MODEL)
    assert ms.to_spec(spec.to_yaml()) == spec, 'the file as written still reproduces the spec it came from'


def test_the_shell_writes_the_form_a_reviewer_diffs(tmp_path, capsys):
    """The verb is the whole point of the form: a reviewer works in a shell and
    a version control diff, not in Python."""
    model = tmp_path / 'model.yaml'
    model.write_text(ms.to_spec(DISPATCH_MODEL).to_yaml())
    assert main(['canonical', str(model)]) == 0, 'a model the language accepts exits 0'
    assert capsys.readouterr().out == ms.to_spec(model).to_yaml(canonical=True), 'stdout is the form, whole'


def test_the_shell_refuses_a_model_the_language_refuses(tmp_path, capsys):
    model = tmp_path / 'broken.yaml'
    model.write_text('constraints: {k: {dims: [], expression: "p >= "}}\n')
    assert main(['canonical', str(model)]) == 1, 'a refused file is exit status 1'
    assert capsys.readouterr().err, 'and its message on stderr'


# ---------------------------------------------------------------------------
# What the form promises, over trees nobody wrote by hand
# ---------------------------------------------------------------------------

#: The leaves a generated tree draws from. Two names that share a prefix and one
#: that sorts last make an ordering mistake visible.
LEAVES = ['a', 'b', 'c', 'd', 'long_name']


def _tree(rng: random.Random, depth: int = 0) -> ArithmeticNode:
    """One random expression tree, every node kind an expression can carry."""
    if depth >= 4 or rng.random() < 0.28:
        return rng.choice([NameNode(rng.choice(LEAVES)), NumberNode(float(rng.randint(1, 5)))])
    roll = rng.random()
    if roll < 0.12:
        return UnaryOperatorNode(rng.choice(['-', '+']), _tree(rng, depth + 1))
    if roll < 0.24:
        args = tuple(_tree(rng, depth + 2) for _ in range(rng.randint(1, 2)))
        keywords = rng.sample(['over', 'by', 'along', 'within'], rng.randint(0, 3))
        return FunctionCallNode(
            rng.choice(['sum', 'at', 'shift']), args, {key: NameNode(rng.choice(LEAVES)) for key in keywords}
        )
    return BinaryOperatorNode(rng.choice(['+', '-', '*', '/', '**']), _tree(rng, depth + 1), _tree(rng, depth + 1))


def _top(rng: random.Random) -> ParsedNode:
    node = _tree(rng)
    return ComparisonNode(rng.choice(['<=', '>=', '==']), node, _tree(rng, 2)) if rng.random() < 0.3 else node


def _value(node: ArithmeticNode, env: dict[str, float]) -> float:
    """What the tree computes, for the one question a normal form must answer the same.

    A call is read as the sum of its arguments and its keywords are ignored,
    because what is under test is the arithmetic around it: the form normalises
    each argument in place and sorts the keywords, and both leave this reading
    alone.
    """
    if isinstance(node, NumberNode):
        return node.value
    if isinstance(node, NameNode):
        return env[node.name]
    if isinstance(node, UnaryOperatorNode):
        return -_value(node.operand, env) if node.op == '-' else _value(node.operand, env)
    if isinstance(node, FunctionCallNode):
        return sum(_value(argument, env) for argument in node.args)
    assert isinstance(node, BinaryOperatorNode), f'{node} is not a kind this evaluator was given'
    left, right = _value(node.left, env), _value(node.right, env)
    return {'+': left + right, '-': left - right, '*': left * right, '/': left / right, '**': left**right}[node.op]


@pytest.mark.parametrize(
    ('written', 'terms'),
    [
        pytest.param('a + (b + c)', ['+ a', '+ b', '+ c'], id='a-sum-under-a-plus-is-spliced'),
        pytest.param('a + (b - c)', ['+ a', '+ b', '- c'], id='signs-and-all'),
        pytest.param('(a + b) + c', ['+ a', '+ b', '+ c'], id='on-the-left-as-well-as-the-right'),
        pytest.param('a - (b - c)', ['+ a', '- (b - c)'], id='and-one-under-a-minus-is-left-whole'),
        pytest.param('- -(a + b)', ['+ a', '+ b'], id='a-sign-written-twice-cancels-and-splices'),
    ],
)
def test_a_sum_flattens_into_the_terms_its_text_shows(written, terms):
    """What the flatten owes the layout: the terms it yields are the lines that
    get printed, so a group it leaves whole must be one the text brackets. A
    group under a plus is not, which is why it is spliced."""
    found = [f'{sign} {operand(node)}' for sign, node in _signed_terms(parse_expression(written))]
    assert found == terms, 'every term of the sum, in the order the spine holds them, and no group left flat'


@pytest.mark.parametrize(
    ('written', 'factors'),
    [
        pytest.param('a * (b * c)', ['a', 'b', 'c'], id='a-product-on-the-right-is-spliced'),
        pytest.param('(a * b) * c', ['a', 'b', 'c'], id='and-on-the-left'),
        pytest.param('a * (b / c)', ['a', 'b / c'], id='a-division-stays-one-factor'),
    ],
)
def test_a_product_flattens_from_either_side(written, factors):
    """Both sides, for the sum's reason: `(a * b) * c` and `a * (b * c)` print
    the same flat text, so a group left whole here would not survive it."""
    assert [str(node) for node in _factors(parse_expression(written))] == factors, (
        'every factor of the product, and no group left flat'
    )


def test_the_form_is_a_fixed_point_on_any_tree_at_all():
    """2000 generated trees, where the models in the tree carry a few hundred
    shapes between them. Three bugs were found here and nowhere else, all of one
    kind: text that the grammar reads back as a *different* tree, because a
    group the form kept as one term prints into flat text that is several."""
    for seed in range(2000):
        node = _top(random.Random(seed))
        printed = laid_out(normalised(node))
        assert normalised(parse_expression(printed)) == normalised(node), (
            f'seed {seed}: `{node}` printed as `{printed}`, which reads back as another tree'
        )


def test_the_form_computes_what_the_expression_it_came_from_computes():
    """The property under every other one. Sorting terms, folding signs and
    splicing groups are all rewrites, and a rewrite that changed a value would
    be a wrong answer rather than an untidy file."""
    for seed in range(500):
        node = _tree(random.Random(seed))
        rewritten = parse_expression(laid_out(normalised(node)))
        env = {name: 1.5 + index for index, name in enumerate(LEAVES)}
        try:
            before, after = _value(node, env), _value(rewritten, env)
        except (ZeroDivisionError, OverflowError):
            continue
        assert abs(before - after) <= 1e-9 * max(1.0, abs(before)), (
            f'seed {seed}: `{node}` is {before} and `{rewritten}` is {after}'
        )


def test_every_spelling_of_one_sum_writes_one_text():
    """Written in any order, with any term negated, one sum writes one text —
    which is the whole claim the form makes, over every permutation rather than
    the one a test author would have picked."""
    for seed in range(150):
        rng = random.Random(seed)
        terms = [str(_tree(rng, 2)) for _ in range(rng.randint(3, 4))]
        signs = [rng.choice(['+', '-']) for _ in terms]
        written = set()
        for order in itertools.permutations(range(len(terms))):
            head, *rest = order
            text = f'-({terms[head]})' if signs[head] == '-' else f'({terms[head]})'
            text += ''.join(f' {signs[i]} ({terms[i]})' for i in rest)
            written.add(canonical_text(text))
        assert len(written) == 1, f'seed {seed}: one sum wrote {len(written)} texts: {sorted(written)}'


@pytest.mark.parametrize('path', MODELS, ids=lambda path: path.stem)
def test_the_form_declares_the_same_model(path):
    """The form is not only stable, it is the same model: every declaration is
    there, under its own name, on its own frame. What the form is allowed to
    change is the text of an expression and the order two declarations sit in.

    A frame is compared as the set it is. Sorting `variables:` changes the
    order a `piecewise:` expansion meets them in, so a constraint the expansion
    emits can carry the same dims in another order — the same frame, laid out
    differently by a consumer that reads that order.
    """
    original, rewritten = (
        ms.to_program(ms.to_spec(source).expand('piecewise'))
        for source in (path, ms.to_spec(path).to_yaml(canonical=True))
    )
    groups = (
        'parameters',
        'variables',
        'constraints',
        'expressions',
        'piecewise',
        'sos',
        'dimensions',
        'relations',
        'assumptions',
    )
    for group in groups:
        assert sorted(getattr(original, group)) == sorted(getattr(rewritten, group)), (
            f'{group}: the form declares a different set of names'
        )
    assert [(name, frozenset(block.dims), block.sense) for name, block in sorted(rewritten.constraints.items())] == [
        (name, frozenset(block.dims), block.sense) for name, block in sorted(original.constraints.items())
    ], 'every constraint keeps its frame and its sense'
    assert [(name, frozenset(block.dims), block.domain) for name, block in sorted(rewritten.variables.items())] == [
        (name, frozenset(block.dims), block.domain) for name, block in sorted(original.variables.items())
    ], 'and every variable its frame and its domain'
    assert (rewritten.objective is None) == (original.objective is None), 'an objective is kept, or its absence is'
    if original.objective is not None and rewritten.objective is not None:
        assert rewritten.objective.sense == original.objective.sense, 'and its sense with it'
