# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""The normal form: one text for every file that means the same thing.

A reviewer diffs two specs in an editor, and a text diff reports key order,
spacing and the order of terms in a sum — none of which is a difference in the
spec. What is left after this form is applied is what the two files mean
differently, which is the question `to_yaml(canonical=True)` exists to answer.
"""

from __future__ import annotations

import itertools
import random
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml

import mathspec as ms
from mathspec.__main__ import main
from mathspec._expression_parser import (
    BinaryOperatorNode,
    ComparisonNode,
    FunctionCallNode,
    NameNode,
    NumberNode,
    UnaryOperatorNode,
    operand,
    parse_expression,
)
from mathspec.canonical import _factors, _signed_terms, canonical_text, laid_out, normalised
from tests.fixtures import DISPATCH_MODEL, EXAMPLES, raw_of, varied

if TYPE_CHECKING:
    from mathspec._expression_parser import ArithmeticNode, ParsedNode

#: Every spec in the repository, the operator probes included. The symbol
#: tables under `examples/symbols/` and the patches under a `variants/` folder
#: are not specs and do not load as one.
SPECS = [path for path in sorted(EXAMPLES.rglob('*.yaml')) if not {'symbols', 'variants'} & set(path.parts)]
FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'every_program_node.yaml'


def _dumped(**patch: object) -> str:
    return ms.to_spec(varied(DISPATCH_MODEL, **patch)).to_yaml(canonical=True)


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
    assert one.to_yaml(canonical=True) == other.to_yaml(canonical=True), 'the two files state one spec'
    assert one.to_yaml() != other.to_yaml(), 'and the dump that keeps the file as written still tells them apart'


@pytest.mark.parametrize('path', [*SPECS, FIXTURE], ids=lambda path: path.stem)
def test_the_form_loads_and_is_already_in_the_form(path):
    """Every spec in the tree, dumped, re-read and dumped again.

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
        varied(DISPATCH_MODEL, **{'constraints.a_cap.dims': [], 'constraints.a_cap.expression': 'sum(p) >= 0'})
    ).to_yaml(canonical=True)
    assert dumped.index('a_cap:') < dumped.index('balance:'), 'a section reads in name order, not file order'


#: The order the form writes the sections in, whatever order the file wrote
#: them in. It is the order of the fields on `Spec`, pinned here so that a
#: reordered field is a failing test rather than a quiet change to every diff.
SECTIONS = [
    'version',
    'description',
    'dimensions',
    'relations',
    'parameters',
    'variables',
    'given',
    'constraints',
    'objective',
    'expressions',
    'macros',
    'piecewise',
    'sos',
    'assumptions',
]


def _written_backwards(raw: object, depth: int = 3) -> object:
    """*raw* with every mapping down to *depth* levels written in reverse order.

    Three levels reach the sections, the declarations of each section and the
    keys of each declaration. They stop above a `cases:` block, whose regions
    are a mapping that the form keeps in the file's order.
    """
    if depth == 0 or not isinstance(raw, dict):
        return raw
    return {key: _written_backwards(value, depth - 1) for key, value in reversed(raw.items())}


@pytest.mark.parametrize('path', SPECS, ids=lambda path: path.stem)
def test_a_file_written_backwards_writes_the_same_text(path):
    """The section order, the declaration order in each section and the key
    order in each declaration are spelling. A file that writes all three in
    reverse is the same spec, so it writes the same text."""
    raw = raw_of(path)
    backwards = ms.to_spec(_written_backwards(raw)).to_yaml(canonical=True)
    assert backwards == ms.to_spec(raw).to_yaml(canonical=True), 'three orders reversed, one text'


@pytest.mark.parametrize('path', SPECS, ids=lambda path: path.stem)
def test_the_sections_come_in_one_order(path):
    written = list(yaml.safe_load(ms.to_spec(path).to_yaml(canonical=True)))
    assert written == [section for section in SECTIONS if section in written], (
        f'the sections of {path.name} follow SECTIONS, not the file'
    )


@pytest.mark.parametrize('path', SPECS, ids=lambda path: path.stem)
def test_every_section_is_sorted_by_name(path):
    data = yaml.safe_load(ms.to_spec(path).to_yaml(canonical=True))
    for section, declarations in data.items():
        if isinstance(declarations, dict) and section != 'objective':
            assert list(declarations) == sorted(declarations), f'{path.name}: `{section}` reads in name order'


def _commitment_with_its_cases_reversed() -> dict[str, object]:
    raw = raw_of(EXAMPLES / 'commitment.yaml')
    cases = raw['expressions']['previous_status']['cases']
    return varied(raw, **{'expressions.previous_status.cases': dict(reversed(cases.items()))})


def _piecewise_with_its_links_reversed() -> dict[str, object]:
    raw = raw_of(EXAMPLES / 'piecewise.yaml')
    return varied(raw, **{'piecewise.cost_curve.links': raw['piecewise']['cost_curve']['links'][::-1]})


@pytest.mark.parametrize(
    ('written', 'reordered'),
    [
        pytest.param(
            DISPATCH_MODEL,
            varied(DISPATCH_MODEL, **{'variables.p.dims': ['generator', 'snapshot']}),
            id='a-declarations-dims',
        ),
        pytest.param(
            raw_of(EXAMPLES / 'commitment.yaml'),
            _commitment_with_its_cases_reversed(),
            id='the-regions-of-a-cases-block',
        ),
        pytest.param(
            raw_of(EXAMPLES / 'piecewise.yaml'),
            _piecewise_with_its_links_reversed(),
            id='the-links-of-a-piecewise-block',
        ),
        pytest.param(
            varied(DISPATCH_MODEL, **{'variables.p.where': 'p_max > 0 and cost > 0'}),
            varied(DISPATCH_MODEL, **{'variables.p.where': 'cost > 0 and p_max > 0'}),
            id='the-predicates-of-a-where',
        ),
    ],
)
def test_an_order_the_form_keeps_is_a_difference_in_the_text(written, reordered):
    """The orders the form does not sort, each reversed alone. A change here
    changes what a reviewer sees as a difference, so it is a decision."""
    assert ms.to_spec(written).to_yaml(canonical=True) != ms.to_spec(reordered).to_yaml(canonical=True), (
        'the form keeps this order as the file wrote it'
    )


def test_the_dump_that_keeps_the_file_as_written_is_unchanged():
    """The default is the round trip `reading.md` documents, and the form is an
    argument away rather than a change to it."""
    spec = ms.to_spec(DISPATCH_MODEL)
    assert ms.to_spec(spec.to_yaml()) == spec, 'the file as written still reproduces the spec it came from'


def test_the_shell_writes_the_form_a_reviewer_diffs(tmp_path, capsys):
    """The verb is the whole point of the form: a reviewer works in a shell and
    a version control diff, not in Python."""
    model = tmp_path / 'spec.yaml'
    model.write_text(ms.to_spec(DISPATCH_MODEL).to_yaml())
    assert main(['canonical', str(model)]) == 0, 'a spec the language accepts exits 0'
    assert capsys.readouterr().out == ms.to_spec(model).to_yaml(canonical=True), 'stdout is the form, whole'


def test_the_shell_refuses_a_spec_the_language_refuses(tmp_path, capsys):
    model = tmp_path / 'broken.yaml'
    model.write_text('constraints: {k: {dims: [], expression: "p >= "}}\n')
    assert main(['canonical', str(model)]) == 1, 'a refused file is exit status 1'
    assert capsys.readouterr().err, 'and its message on stderr'


def test_the_check_passes_a_file_in_the_form_and_writes_nothing(tmp_path, capsys):
    model = tmp_path / 'spec.yaml'
    model.write_text(ms.to_spec(DISPATCH_MODEL).to_yaml(canonical=True))
    assert main(['canonical', '--check', str(model)]) == 0, 'a file in the form passes'
    assert capsys.readouterr() == ('', ''), 'a check that passes prints nothing on either stream'


def test_the_check_fails_a_file_out_of_the_form_and_names_the_rewrite(tmp_path, capsys):
    """What a CI job runs: the spec loads, so the language accepts it, and the
    job still fails, because the file is not the text the form writes."""
    model = tmp_path / 'spec.yaml'
    written = ms.to_spec(DISPATCH_MODEL).to_yaml()
    model.write_text(written)
    assert main(['canonical', '--check', str(model)]) == 1, 'a file out of the form is exit status 1'
    assert capsys.readouterr().err == (
        f'{model} is not in the canonical form. Run `python -m mathspec canonical --write {model}` to rewrite it.\n'
    )
    assert model.read_text() == written, 'the check leaves the file as it found it'


def test_the_rewrite_leaves_a_file_the_check_passes(tmp_path, capsys):
    model = tmp_path / 'spec.yaml'
    model.write_text(ms.to_spec(DISPATCH_MODEL).to_yaml())
    assert main(['canonical', '--write', str(model)]) == 0, 'the rewrite of a spec the language accepts exits 0'
    assert model.read_text() == ms.to_spec(DISPATCH_MODEL).to_yaml(canonical=True), 'the file now holds the form'
    assert capsys.readouterr().out == '', 'the form goes into the file, not to stdout'
    assert main(['canonical', '--check', str(model)]) == 0, 'and the check passes the file it wrote'


@pytest.mark.parametrize('flag', ['--check', '--write'])
def test_a_refused_file_is_neither_checked_nor_rewritten(tmp_path, capsys, flag):
    model = tmp_path / 'broken.yaml'
    written = 'constraints: {k: {dims: [], expression: "p >= "}}\n'
    model.write_text(written)
    assert main(['canonical', flag, str(model)]) == 1, 'a refused file is exit status 1'
    assert capsys.readouterr().err, 'and its message on stderr'
    assert model.read_text() == written, 'the file is left as the author wrote it'


@pytest.mark.parametrize(
    'flags',
    [
        pytest.param(['--check', '--write'], id='check-and-write'),
        pytest.param(['--check', '-o', 'out.yaml'], id='check-and-out'),
        pytest.param(['--write', '-o', 'out.yaml'], id='write-and-out'),
    ],
)
def test_the_form_goes_to_one_place(tmp_path, flags):
    """Each flag names where the form goes, so two of them name two places."""
    model = tmp_path / 'spec.yaml'
    model.write_text(ms.to_spec(DISPATCH_MODEL).to_yaml())
    with pytest.raises(SystemExit) as refused:
        main(['canonical', *flags, str(model)])
    assert refused.value.code == 2, 'argparse refuses the pair before the file is read'


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
    """2000 generated trees, where the specs in the tree carry a few hundred
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


@pytest.mark.parametrize('path', SPECS, ids=lambda path: path.stem)
def test_the_form_declares_the_same_spec(path):
    """The form is not only stable, it is the same spec: every declaration is
    there, under its own name, on its own frame. What the form is allowed to
    change is the text of an expression and the order two declarations sit in.

    A frame is compared as the set it is. Sorting `variables:` changes the
    order a `piecewise:` expansion meets them in, so a constraint the expansion
    emits can carry the same dims in another order — the same frame, laid out
    differently by a consumer that reads that order.
    """
    original, rewritten = (
        ms.to_spec(source).expand('piecewise').program for source in (path, ms.to_spec(path).to_yaml(canonical=True))
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


def test_a_named_expression_written_on_one_line_is_normalised_too():
    """`name: a + b` serialises back as a bare string, which the form passed through as written."""
    frame = {'dimensions': {'t': {'dtype': 'int'}}, 'variables': {'a': {'dims': ['t']}, 'b': {'dims': ['t']}}}
    one, other = ({**frame, 'expressions': {'total': text}} for text in ('a + b', 'b + a'))
    assert ms.to_spec(one).to_yaml(canonical=True) == ms.to_spec(other).to_yaml(canonical=True)


def test_the_names_a_file_reads_are_sorted_like_the_names_it_declares():
    """`given:` nests its kinds one level below a section, so sorting the sections alone left them in file order."""
    frame = {'dimensions': {'t': {'dtype': 'int'}}, 'constraints': {'c': {'dims': ['t'], 'expression': 'a + b >= 0'}}}
    one, other = (
        {**frame, 'given': {'variables': dict(entries)}}
        for entries in (
            [('a', {'dims': ['t']}), ('b', {'dims': ['t']})],
            [('b', {'dims': ['t']}), ('a', {'dims': ['t']})],
        )
    )
    assert ms.to_spec(one).to_yaml(canonical=True) == ms.to_spec(other).to_yaml(canonical=True)
