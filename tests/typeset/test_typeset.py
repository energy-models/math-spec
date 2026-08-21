# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The typesetter (spike).

Three kinds of test, and the split is the point:

* **Shared** — run against every entry in ``FORMATS``. These are properties of
  the *walk*, so a new format inherits them and cannot quietly drop one.
* **Per format** — the spelling. Fragments, not golden documents: a golden
  file for a generator this young is rewritten by every cosmetic change and
  stops being read.
* **Compiled** — the only check that the output is real. Typst is a pip wheel
  so it runs here; LaTeX needs a toolchain and is compiled in CI instead.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator, Mapping
from dataclasses import is_dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, get_args

import pytest

from math_spec.errors import MathSpecError, SchemaError
from math_spec.expression_parser import ArithmeticNode, ComparisonNode, FunctionCallNode
from math_spec.operators import BUILTIN_NAMES
from math_spec.resolution import Namespace, expression_of, where_of
from math_spec.typeset import FORMATS, SymbolTable, to_latex, to_markdown, to_typst, typeset, walk
from math_spec.typeset.format import OPERATOR_NAMES
from math_spec.typeset.symbols import _derive_name_symbol
from math_spec.validation import load_model
from math_spec.where_parser import WhereNode
from tests.fixtures import OPERATOR_PROBES, override
from tests.typeset import golden

if TYPE_CHECKING:
    from math_spec.typeset.format import Format


LATEX, TYPST = FORMATS['latex'], FORMATS['typst']
EVERY_FORMAT = pytest.mark.parametrize('fmt', list(FORMATS.values()), ids=list(FORMATS))

DISPATCH = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'generator': {'dtype': 'str'}},
    'parameters': {
        'p_max': {'dims': ['generator']},
        'cost': {'dims': ['generator']},
        'load': {'dims': ['snapshot']},
    },
    'variables': {'p': {'foreach': ['snapshot', 'generator'], 'bounds': {'lower': 0, 'upper': 'p_max'}}},
    'constraints': {
        'power_balance': {
            'foreach': ['snapshot'],
            'expression': 'sum(p, over=generator) == load',
        }
    },
    'objective': {'sense': 'minimize', 'expression': 'sum(p * cost)'},
}


#: An objective whose two terms carry different dims — dispatch over (t, g)
#: and a capital cost over (g) alone. No constraints, so every summation in the
#: rendered document is one the objective asked for.
MIXED = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'generator': {'dtype': 'str'}},
    'parameters': {'cost': {'dims': ['generator']}, 'capex': {'dims': ['generator']}},
    'variables': {
        'p': {'foreach': ['snapshot', 'generator'], 'bounds': {'lower': 0}},
        'p_nom': {'foreach': ['generator'], 'bounds': {'lower': 0}},
    },
    'objective': {'sense': 'minimize', 'expression': 'sum(p * cost) + sum(p_nom * capex)'},
}


def _summations(text: str, fmt: Format) -> int:
    """How many summations *text* opens, derived from the format's own spelling."""
    return text.count(fmt.summation('DOMAIN', 'BODY').split('DOMAIN')[0])


def _over_generators(fmt: Format) -> str:
    """``sum over g in G``, opened but not filled — what the capital term is under."""
    return fmt.summation(f'g {fmt.operators["in"]} {fmt.script("G")}', '').rstrip()


# ---------------------------------------------------------------------------
# shared: properties of the walk, asserted for every format
# ---------------------------------------------------------------------------


@EVERY_FORMAT
def test_a_format_spells_every_operator_the_walk_can_emit(fmt: Format):
    """A missing spelling is a KeyError deep in a walk, on whichever model
    first happens to use that operator. Checking the table instead makes it a
    failure the format's own author sees."""
    assert set(fmt.operators) == OPERATOR_NAMES


@EVERY_FORMAT
def test_a_dimension_index_never_steals_a_letter_a_variable_owns(fmt: Format):
    """With `plant` -> `p` and a variable `p`, the output was `p_{t,p}` and no
    reader could tell which `p` was which."""
    model = {
        'dimensions': {'plant': {'dtype': 'str'}, 'snapshot': {'dtype': 'int'}},
        'parameters': {'cost': {'dims': ['plant']}},
        'variables': {'p': {'foreach': ['snapshot', 'plant'], 'bounds': {'lower': 0}}},
        'objective': {'expression': 'sum(p * cost)'},
    }
    text = typeset(model, fmt)
    assert fmt.subscript('p', ['t', 'p']) not in text
    assert fmt.subscript('p', ['t', 'l']) in text


@EVERY_FORMAT
def test_a_where_lands_on_the_quantifier_not_in_the_equation(fmt: Format):
    """A mask is row absence, so it belongs to the ∀ that names the rows."""
    model = override(DISPATCH, **{'variables.p.where': 'p_max > 0'})
    text = typeset(model, fmt, legend=False)
    assert fmt.operators['forall'] in text
    assert fmt.operators['such_that'] in text


def _masked(dtype: str) -> dict[str, object]:
    """One model per mask dtype: a bare parameter atom is the whole `where`."""
    return {
        'dimensions': {'g': {'values': ['a', 'b']}},
        'parameters': {'flag': {'dims': ['g'], 'dtype': dtype}},
        'variables': {
            'keep': {'foreach': ['g'], 'where': 'flag', 'bounds': {'lower': 0, 'upper': 1}},
            'drop': {'foreach': ['g'], 'where': 'NOT flag', 'bounds': {'lower': 0, 'upper': 1}},
        },
        'objective': {'sense': 'minimize', 'expression': 'sum(keep, over=g)'},
    }


@EVERY_FORMAT
def test_a_boolean_mask_renders_as_the_predicate_not_as_definedness(fmt: Format):
    """`where: flag` on a bool keeps the true rows, not the present ones (#834).

    A bool that is present and false is excluded, so "is defined" describes a
    different model than the one that solves, and a reader deriving from the
    page cannot tell. Absence reads as false here anyway (law 8), so the
    predicate alone is the whole condition.
    """
    text = typeset(_masked('bool'), fmt, legend=False)
    assert fmt.prose(' is defined') not in text, 'a boolean mask filters on truth, not on presence'


@EVERY_FORMAT
def test_a_non_boolean_mask_still_reads_as_definedness(fmt: Format):
    """The wording is right for every other dtype — `tsp_mtz`'s `where: distance`
    genuinely does mean "wherever a distance exists"."""
    text = typeset(_masked('float'), fmt, legend=False)
    assert fmt.prose(' is defined') in text


@EVERY_FORMAT
def test_a_negated_boolean_mask_negates_the_predicate_alone(fmt: Format):
    """`NOT flag` means false, and must not read as "not defined".

    `¬` takes no bracket here, so before #834 the prose sat outside it and the
    line printed `¬ flag is defined` — read as "flag is missing", the opposite
    grouping to the one the model builds.
    """
    text = typeset(_masked('bool'), fmt, legend=False)
    negated = f'{fmt.operators["not"]} {fmt.subscript(fmt.italic("flag"), ["g"])}'
    assert negated in text, 'the negation has to land on the predicate itself'
    assert f'{negated} {fmt.prose(" is defined")}' not in text, (
        'the negation must not scope over prose it cannot bracket'
    )


@EVERY_FORMAT
def test_translation_distinguishes_a_wrapping_edge_from_a_dropping_one(fmt: Format):
    """``edge='wrap'`` wraps and a bare shift does not — one symbol each, since a
    reader who cannot tell them apart cannot tell the two models apart either."""

    def storage(edge: str) -> dict[str, object]:
        return {
            'dimensions': {'snapshot': {'dtype': 'int'}},
            'parameters': {'load': {'dims': ['snapshot']}},
            'variables': {'soc': {'foreach': ['snapshot'], 'bounds': {'lower': 0, 'upper': 100}}},
            'constraints': {
                'balance': {
                    'foreach': ['snapshot'],
                    'expression': f'soc == shift(soc, over=snapshot, offset=1{edge}) + load',
                }
            },
        }

    cyclic = fmt.operators['cyclic_minus']
    assert cyclic in typeset(storage(", edge='wrap'"), fmt, legend=False)
    assert cyclic not in typeset(storage(''), fmt, legend=False)


@EVERY_FORMAT
def test_a_numeric_edge_is_a_third_translation_and_shows_its_fill(fmt: Format):
    """The three edge policies are three models, so they are three renderings.

    A bare shift drops the row the translation vacates; ``edge=v`` keeps the
    row and puts *v* there. Rendering both as `t - 1` said the first thing
    about a model doing the second — and the legend, which calls plain
    translation "simply absent", said it in words as well.

    The fill rides on the operator because it is per call site: one model may
    pad a sum with `0` and a product with `1`, and a legend naming both cannot
    say which term is which.
    """

    def storage(edge: str) -> dict[str, object]:
        return {
            'dimensions': {'snapshot': {'dtype': 'int'}},
            'parameters': {'load': {'dims': ['snapshot']}},
            'variables': {'soc': {'foreach': ['snapshot'], 'bounds': {'lower': 0, 'upper': 100}}},
            'constraints': {
                'balance': {
                    'foreach': ['snapshot'],
                    'expression': f'soc == shift(soc, over=snapshot, offset=1{edge}) + load',
                }
            },
        }

    padded = typeset(storage(', edge=0'), fmt, legend=False)
    assert fmt.operators['edge_minus'] in padded, 'a numeric edge renders as neither a plain nor a cyclic translation'
    assert fmt.subscript(fmt.operators['edge_minus'], ['0']) in padded, 'the substituted value is not on the operator'
    for other in (storage(''), storage(", edge='wrap'")):
        assert fmt.operators['edge_minus'] not in typeset(other, fmt, legend=False), (
            'a shift with no numeric edge borrowed the padded spelling'
        )


@EVERY_FORMAT
def test_a_fill_and_a_group_share_the_operators_one_subscript(fmt: Format):
    """Both policies subscript the operator, so a call carrying both writes one
    subscript group rather than two.

    Not a matter of taste: `\\boxminus_{0}_{season_of(t)}` is a *Double
    subscript* error, so the page stopped compiling at the equation — and the
    two policies are independent, so nothing else in the model has to be
    wrong for a model to reach it.
    """
    model = {
        'dimensions': {'snapshot': {'dtype': 'int'}, 'season': {'dtype': 'str'}},
        'lookups': {'season_of': {'over': 'snapshot', 'into': 'season'}},
        'variables': {'p': {'foreach': ['snapshot'], 'bounds': {'lower': 0}}},
        'constraints': {
            'held': {
                'foreach': ['snapshot'],
                'expression': 'p <= shift(p, over=snapshot, offset=1, edge=0, by=season_of)',
            }
        },
        'objective': {'sense': 'minimize', 'expression': 'sum(p)'},
    }
    text = typeset(model, fmt, legend=False)
    opened = fmt.subscript(fmt.operators['edge_minus'], ['0', 'GROUP']).split('GROUP')[0]
    assert opened in text, 'the fill and the group do not share the one subscript the operator has'
    assert fmt.subscript(fmt.operators['edge_minus'], ['0']) not in text, (
        'the fill closed its own subscript and the group opened a second one'
    )


@EVERY_FORMAT
def test_a_translation_under_a_pullback_survives_it(fmt: Format):
    """``at`` and ``shift`` both re-index at the leaf, and the leaf has one subscript.

    Whoever wrote it last used to win: ``at(shift(cap, over=period, offset=1,
    edge=0), by=period_of)`` printed `cap_{period_of(t)}`, dropping a
    translation the plan builds. The subscript is a composition, so it renders
    as one.
    """
    model = {
        'dimensions': {
            'snapshot': {'dtype': 'int'},
            'period': {'dtype': 'int'},
        },
        'lookups': {'period_of': {'over': 'snapshot', 'into': 'period'}},
        'parameters': {'cap': {'dims': ['period']}},
        'variables': {'p': {'foreach': ['snapshot'], 'bounds': {'lower': 0}}},
        'constraints': {
            'within': {
                'foreach': ['snapshot'],
                'expression': 'p <= at(shift(cap, over=period, offset=1, edge=0), by=period_of)',
            }
        },
    }
    text = typeset(model, fmt, legend=False)
    assert fmt.operators['edge_minus'] in text, 'the shift under the at was dropped from the subscript'
    assert fmt.apply(fmt.upright('period_of'), 't') in text, 'the pullback itself was dropped'


@EVERY_FORMAT
def test_a_shift_forward_renders_and_does_not_crash(fmt: Format):
    """``by=-1`` is a model the language accepts and the walk used to abort on.

    The parser reads a negated literal as a unary minus over a number, and the
    walk asserted a bare ``NumberNode`` — so every format raised
    ``AssertionError`` on a legal model, and the forward halves of the three
    translation operators were unreachable code that had never been printed.
    """
    model = {
        'dimensions': {'snapshot': {'dtype': 'int'}},
        'variables': {'p': {'foreach': ['snapshot'], 'bounds': {'lower': 0}}},
        'constraints': {
            'later': {'foreach': ['snapshot'], 'expression': 'p <= shift(p, over=snapshot, offset=-1, edge=0)'}
        },
        'objective': {'sense': 'minimize', 'expression': 'sum(p)'},
    }
    text = typeset(model, fmt, legend=False)
    assert fmt.subscript(fmt.operators['edge_plus'], ['0']) in text, (
        'a forward shift should translate the index the other way, with its fill'
    )
    assert fmt.operators['edge_minus'] not in text, 'a forward shift printed as a backward one'


@EVERY_FORMAT
def test_translations_that_disagree_at_the_edge_do_not_merge(fmt: Format):
    """Two shifts on one dim collapse to one offset only when they are the same shift.

    ``shift(shift(x, offset=1, edge='wrap'), offset=1)`` used to print `t ⊖ 2`, which
    the legend defines as *both* steps taken modulo the dimension — while the
    outer one drops its vacated row instead. Composition renders as
    composition; only identical policies add.
    """
    model = {
        'dimensions': {'snapshot': {'dtype': 'int'}},
        'variables': {'soc': {'foreach': ['snapshot'], 'bounds': {'lower': 0}}},
        'constraints': {
            'b': {
                'foreach': ['snapshot'],
                'expression': "soc <= shift(shift(soc, over=snapshot, offset=1, edge='wrap'), over=snapshot, offset=1)",
            }
        },
    }
    text = typeset(model, fmt, legend=False)
    assert f'{fmt.operators["cyclic_minus"]} 2' not in text, 'an acyclic step was absorbed into a cyclic offset'
    assert fmt.operators['cyclic_minus'] in text and fmt.operators['minus'] in text, (
        'both translations should still be visible'
    )


@EVERY_FORMAT
def test_the_legend_explains_wraparound_only_when_it_is_used(fmt: Format):
    rolled = {
        'dimensions': {'snapshot': {'dtype': 'int'}},
        'variables': {'soc': {'foreach': ['snapshot'], 'bounds': {'lower': 0}}},
        'constraints': {
            'b': {'foreach': ['snapshot'], 'expression': "soc == shift(soc, over=snapshot, offset=1, edge='wrap')"}
        },
    }
    assert 'cyclic translation' in typeset(rolled, fmt)
    assert 'cyclic translation' not in typeset(DISPATCH, fmt)


@EVERY_FORMAT
def test_macros_and_named_expressions_are_expanded_away(fmt: Format):
    """What prints is the math a backend builds, not the sugar it was spelled with."""
    model = override(
        DISPATCH,
        **{'expressions.supply': 'sum(p, over=generator)', 'constraints.power_balance.expression': 'supply == load'},
    )
    assert 'supply' not in typeset(model, fmt, legend=False)


@EVERY_FORMAT
def test_an_invalid_model_fails_the_same_way_check_does(fmt: Format):
    broken = override(DISPATCH, **{'objective.expression': 'p * nonexistent'})
    with pytest.raises(MathSpecError):
        typeset(broken, fmt)


# ---------------------------------------------------------------------------
# derivation: unambiguous by default
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('name', 'expected'),
    [
        pytest.param('p_max', r'p^{\mathrm{max}}', id='single-letter-head-so-the-tail-is-a-qualifier'),
        pytest.param('soc_max', r'\mathit{soc}^{\mathrm{max}}', id='declared-head-so-the-tail-is-a-qualifier'),
        pytest.param('marginal_cost', r'\mathit{marginal\_cost}', id='neither-so-it-stays-one-word'),
        pytest.param('shut_down', r'\mathit{shut\_down}', id='neither-even-when-the-tail-reads-like-a-qualifier'),
    ],
)
def test_an_underscore_is_only_a_qualifier_when_its_head_is_a_symbol(name: str, expected: str):
    """`marginal_cost` is not *marginal* raised to *cost*. Splitting every
    underscore turned about a third of real names into nonsense."""
    assert _derive_name_symbol(name, frozenset({'p', 'soc'}), LATEX) == expected


@EVERY_FORMAT
def test_the_objective_shows_the_summations_the_file_wrote(fmt: Format):
    """One summation per ``sum`` in the expression, over the dims it took.

    The objective is scalar, so nothing is implied and nothing is grouped: the
    capital term below is summed over generators alone because that is what its
    own bracket closes over. A walk that reduced the objective itself would
    have to decide where each summation begins, and #1046 is what that cost.
    """
    text = typeset(MIXED, fmt, legend=False)
    assert _summations(text, fmt) == 2, 'each written sum is one summation'
    assert _over_generators(fmt) in text, 'the capital term is summed over generators alone'


@EVERY_FORMAT
def test_two_sums_of_the_same_dims_stay_two_summations(fmt: Format):
    """The file's structure survives to the page, even where it repeats itself.

    Merging the pair would read better and say something the file does not:
    that one bracket covers both terms. The walk renders what is written.
    """
    text = typeset(override(MIXED, **{'objective.expression': 'sum(p * cost) + sum(p * cost)'}), fmt, legend=False)
    assert _summations(text, fmt) == 2, 'two written sums are two summations'


@EVERY_FORMAT
def test_a_subtracted_summation_keeps_the_sign_outside_it(fmt: Format):
    """The sign is applied to the whole reduction, and the bracket says so."""
    text = typeset(override(MIXED, **{'objective.expression': 'sum(p * cost) - sum(p_nom * capex)'}), fmt, legend=False)
    opener = fmt.parenthesise('BODY').split('BODY')[0] + _over_generators(fmt)
    assert f'{fmt.operators["minus"]} {opener}' in text


# ---------------------------------------------------------------------------
# LaTeX
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    'fragment',
    [
        pytest.param('p_{t,g}', id='symbols-follow-the-names-variable'),
        pytest.param(r'\mathit{load}_{t}', id='symbols-follow-the-names-parameter'),
        pytest.param(r'p^{\mathrm{max}}_{g}', id='symbols-follow-the-names-qualifier'),
        pytest.param(
            r'\sum_{g \in \mathcal{G}} p_{t,g} & = \mathit{load}_{t}',
            id='sum-binds-the-dimension-it-reduces',
        ),
        pytest.param(
            r'\sum_{t \in \mathcal{T},\ g \in \mathcal{G}} p_{t,g} \cdot \mathit{cost}_{g}',
            id='a-sum-naming-no-dim-puts-them-all-in-its-domain',
        ),
        pytest.param(r'0 \le p_{t,g} & \le p^{\mathrm{max}}_{g}', id='bounds-become-a-domain-line'),
        pytest.param(r'\text{power\_balance}', id='names-are-escaped-in-text-mode'),
    ],
)
def test_latex_spells_the_dispatch_model(fragment: str):
    assert fragment in to_latex(DISPATCH)


@pytest.mark.parametrize(
    ('bounds', 'expected'),
    [
        ({}, r'p_{t,g} & \in \mathbb{R}'),
        ({'lower': 0}, r'p_{t,g} & \ge 0'),
        ({'upper': 10}, r'p_{t,g} & \le 10'),
    ],
)
def test_latex_a_missing_bound_is_not_silently_zero(bounds: dict[str, object], expected: str):
    model = override(DISPATCH, **{'variables.p.bounds': bounds})
    assert expected in to_latex(model)


@pytest.mark.parametrize(
    ('declaration', 'expected'),
    [
        pytest.param(
            {'foreach': ['snapshot', 'generator'], 'domain': 'binary'},
            r'n_{t,g} & \in \{0, 1\}',
            id='binary',
        ),
        pytest.param(
            {'foreach': ['generator'], 'domain': 'integer', 'bounds': {'lower': 0, 'upper': 5}},
            r'0 \le n_{g} & \le 5, n_{g} \in \mathbb{Z}',
            id='integer-with-bounds',
        ),
        pytest.param({'foreach': ['generator'], 'domain': 'integer'}, r'n_{g} & \in \mathbb{Z}', id='integer-free'),
    ],
)
def test_latex_a_variable_states_its_domain(declaration: dict[str, object], expected: str):
    """An integer with bounds says both; one without says only where it lives.

    The free integer is here because it shares every line of the walk with the
    other two — the ternary picking the set is one statement — so nothing but
    an assertion on the output can tell that arm from its neighbour.
    """
    assert expected in to_latex(override(DISPATCH, **{'variables.n': declaration}))


def test_latex_sum_renders_the_coordinate_map_as_a_set_condition():
    """Read off the operator probe rather than a gallery model.

    `sum(by=)` is what the probe exists to show, and the probe travels with the
    renderer where the gallery does not — so this asserts the construct on the
    corpus that will still be beside it. Two maps rather than one: the
    conjunction is the part a single lookup cannot show.
    """
    tex = to_latex('examples/operators/sum_by_lookups.yaml', legend=False)
    assert r'\sum_{g \in \mathcal{G} \,:\, \mathrm{gen\_bus}(g) = b \wedge \mathrm{gen\_tech}(g) = e} p_{t,g}' in tex


def test_latex_a_sum_used_as_a_factor_is_bracketed():
    """Unbracketed, `\\sum_g x_g \\cdot 2` reads as the sum capturing the 2."""
    model = override(DISPATCH, **{'constraints.power_balance.expression': 'sum(p, over=generator) * 2 == load'})
    assert r'\left( \sum_{g \in \mathcal{G}} p_{t,g} \right) \cdot 2' in to_latex(model, legend=False)


def test_latex_standalone_is_a_whole_document():
    tex = to_latex(DISPATCH, standalone=True)
    assert tex.startswith(r'\documentclass')
    assert r'\usepackage{amsmath}' in tex
    assert tex.rstrip().endswith(r'\end{document}')


def test_latex_numbering_can_be_turned_off():
    assert r'\begin{align*}' in to_latex(DISPATCH, numbered=False)
    assert r'\begin{align}' in to_latex(DISPATCH, numbered=True)


# ---------------------------------------------------------------------------
# Typst
# ---------------------------------------------------------------------------


def test_typst_uses_its_own_grouping_and_set_notation():
    typ = to_typst(DISPATCH, legend=False)
    assert 'p_(t,g)' in typ
    assert 'sum_(g in cal(G))' in typ
    assert 'italic("load")_(t)' in typ


def test_typst_sum_renders_the_coordinate_map():
    """The same map in the other notation, off the same travelling probe."""
    typ = to_typst('examples/operators/sum_by_lookups.yaml', legend=False)
    assert 'sum_(g in cal(G) colon upright("gen_bus")(g) = b and upright("gen_tech")(g) = e) p_(t,g)' in typ


# ---------------------------------------------------------------------------
# Markdown — the one that renders where the docs already live
# ---------------------------------------------------------------------------


def test_markdown_is_latex_math_in_a_markdown_wrapper():
    """The math is byte-identical to the LaTeX lane's; only the wrapper differs.
    That is the claim the module makes, so it is the one asserted."""
    md = to_markdown(DISPATCH, legend=False)
    assert r'\sum_{g \in \mathcal{G}} p_{t,g}' in md, 'the math is spelled exactly as LaTeX spells it'
    assert '#### Subject to' in md, 'the document layer is the whole difference'
    assert r'\begin{align}' not in md
    assert r'\paragraph' not in md


def test_markdown_keeps_names_out_of_the_math():
    """`\\text{total\\_cost}` is correct in a LaTeX document and wrong in a
    browser: MathJax renders the `\\_` escape literally, backslash and all. A
    name is not math, so it goes outside the `$$` as a code span."""
    md = to_markdown(DISPATCH, legend=False)
    assert '**`power_balance`**' in md
    for block in md.split('$$')[1::2]:
        assert '\\_' not in block, f'escaped underscore reached the math: {block!r}'


def test_markdown_gives_each_equation_its_own_block():
    """`aligned` columns line up *across rows*. A page shows one equation at a
    time under its own heading, so the separators aligned against nothing and
    rendered as stretches of empty space."""
    md = to_markdown(DISPATCH, legend=False)
    assert md.count('$$') % 2 == 0
    assert 'aligned' not in md
    assert '&' not in md.replace('&&', ''), 'no alignment separators at all'


def test_markdown_renders_the_legend_as_a_table():
    md = to_markdown(DISPATCH)
    assert '| Symbol | Meaning |' in md
    assert '| `p_max` over' in md.replace('$p^{\\mathrm{max}}$ ', '')


#: Reduction operators carry a subscript without being a symbol.


def test_typst_standalone_adds_page_setup():
    assert to_typst(DISPATCH, standalone=True).startswith('#set page')
    assert not to_typst(DISPATCH).startswith('#set page')


@pytest.fixture(scope='module')
def typst():
    return pytest.importorskip('typst', reason='typst is a dev dependency; the bare install skips it')


def test_typst_output_with_a_symbol_table_compiles(typst, tmp_path: Path):
    """The gap that let #321 through: the compile test never ran with `symbols=`."""
    source = tmp_path / 'symbols.typ'
    source.write_text(to_typst(DISPATCH, symbols=TYPST_SYMBOLS, standalone=True))
    typst.compile(str(source), output=str(tmp_path / 'symbols.pdf'))


def test_a_description_of_every_special_compiles(typst, tmp_path: Path):
    """Escapes that are *present* are not necessarily *right*, and only a
    compiler says which.

    The golden model's description carries every character the notations
    escape; this is the Typst half of that claim, and CI's `pdflatex` run over
    the same file is the LaTeX half.
    """
    source = tmp_path / 'specials.typ'
    source.write_text(to_typst(golden.MODEL, standalone=True))
    typst.compile(str(source), output=str(tmp_path / 'specials.pdf'))


def test_every_typst_operator_compiles(typst, tmp_path: Path):
    """Only a handful of operators appear in `examples/`; the rest would
    otherwise first fail on somebody's own model."""
    probe = tmp_path / 'operators.typ'
    probe.write_text('\n'.join(f'$ a {TYPST.operators[name]} b $' for name in sorted(OPERATOR_NAMES)))
    typst.compile(str(probe), output=str(tmp_path / 'operators.pdf'))


# ---------------------------------------------------------------------------
# golden output — the only test that notices a change nobody pinned
# ---------------------------------------------------------------------------


@pytest.mark.parametrize('name', list(FORMATS), ids=list(FORMATS))
def test_the_output_matches_the_committed_golden_file(name: str):
    """One model, every format, byte for byte.

    Fragment assertions pin the constructs someone thought to pin, and survive
    anything leaving those substrings intact — a stray prefix, a lost space, a
    changed separator. Perturbing `TypstFormat.summation` to emit `~sum_(...)`
    failed *no test* before this existed, because every Typst assertion was a
    substring check and a `~` compiles fine.

    The same trade `examples/walkthrough.out` makes: the committed file is the
    output, so a format that starts saying something different shows up as a
    diff instead of as nothing at all.
    """
    expected = golden.path_for(name)
    actual = typeset(golden.MODEL, FORMATS[name], standalone=True)
    assert actual == expected.read_text(), (
        f'{expected.relative_to(Path.cwd())} is stale.\n'
        f'If the change was intended: `pixi run python -m tests.typeset.golden`, then read the diff.'
    )


class _Recorded:
    """*fmt*, spelling exactly as it does, remembering what it was asked to spell.

    The walk reaches every operator through ``format.operators[name]``, so a
    recording mapping in that one place is the whole census — and it is a
    census of what the *walk asked for*, not of what appears in the output,
    where ``min`` is a substring of a parameter called ``min_up`` and a symbol
    that never rendered would pass.
    """

    def __init__(self, fmt: Format) -> None:
        self._fmt = fmt
        self.asked: set[str] = set()
        self.operators = _Asked(fmt.operators, self.asked)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._fmt, name)


class _Asked(Mapping):
    def __init__(self, operators: Mapping[str, str], asked: set[str]) -> None:
        self._operators, self._asked = operators, asked

    def __getitem__(self, key: str) -> str:
        self._asked.add(key)
        return self._operators[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._operators)

    def __len__(self) -> int:
        return len(self._operators)


def test_the_golden_model_asks_for_every_operator_the_vocabulary_spells():
    """The fixture reaches every symbol, so the committed output shows them all.

    Without this the fixture is only exhaustive on the day someone read it:
    ``sum_back``, the three ``where`` predicates over lookups and both
    constant masks were all in the language and in none of the golden output,
    and nothing failed. A symbol a format spells and no model prints is either
    a construct the fixture is missing or vocabulary nothing needs, and both
    are worth being told about.

    The one exemption is derived rather than listed: a model declares one
    objective sense, so the other one cannot be asked for from here.
    """
    recorder = _Recorded(LATEX)
    typeset(golden.MODEL, recorder, standalone=True)
    sense = load_model(golden.MODEL).objective.sense
    unreachable = {'minimize', 'maximize'} - {sense}
    assert recorder.asked == OPERATOR_NAMES - unreachable, (
        f'tests/typeset/golden/model.yaml no longer prints every operator: '
        f'{sorted(OPERATOR_NAMES - unreachable - recorder.asked)} unrendered, '
        f'{sorted(recorder.asked - OPERATOR_NAMES)} unspelled. '
        f'Add the construct that prints it, or drop the spelling.'
    )


def _kinds(node: object, found: set[str]) -> set[str]:
    """Every node type in *node*'s tree, by class name, including the leaves."""
    found.add(type(node).__name__)
    for value in vars(node).values():
        for child in value.values() if isinstance(value, dict) else value if isinstance(value, list) else [value]:
            if is_dataclass(child):
                _kinds(child, found)
    return found


def _rendered_trees() -> Iterator[object]:
    """Every resolved tree the walk is handed for the golden model."""
    schema = load_model(golden.MODEL)
    namespace = Namespace.of(schema)
    yield expression_of(schema.objective.expression, schema, namespace, 'the objective')
    for name, block in schema.constraints.items():
        yield expression_of(block.expression, schema, namespace, f'constraint {name!r}')
        if (mask := where_of(block.where, namespace, f'constraint {name!r}')) is not None:
            yield mask
    for name, block in schema.variables.items():
        if (mask := where_of(block.where, namespace, f'variable {name!r}', self_variable=name)) is not None:
            yield mask


#: What resolution never hands the walk: the three nodes it types away, and the
#: three an expression only carries before names are resolved. The walk raises on
#: each rather than rendering it, so a fixture reaching one would be a bug in
#: resolution rather than a case worth committing output for.
UNRESOLVED = {
    'UnresolvedNameNode',
    'UnresolvedComparisonNode',
    'UnresolvedPositionNode',
    'NameNode',
    'NameListNode',
    'KeywordNode',
}


def test_the_golden_model_carries_every_node_kind_the_walk_renders():
    """A construct added to the language is a case this fixture owes output for.

    The operator census above is about the *symbols*; this is about the
    *branches*. Two constructs can share every symbol and still render
    differently — ``at`` and ``sum(by=)`` both print a coordinate map — so a
    walk arm no fixture reaches is one whose output nobody has ever read.
    """
    kinds: set[str] = set()
    for tree in _rendered_trees():
        _kinds(tree, kinds)
    declared = {node.__name__ for node in (*get_args(WhereNode), *get_args(ArithmeticNode), ComparisonNode)}
    assert kinds == declared - UNRESOLVED, (
        f'tests/typeset/golden/model.yaml reaches {sorted(kinds - declared)} and misses '
        f'{sorted(declared - UNRESOLVED - kinds)}. Every node the walk renders needs a case here, '
        f'or its arm ships output nobody has read.'
    )


def test_the_golden_model_calls_every_operator_in_the_language():
    """``BUILTINS`` is the closed set, so a new operator lands with its case here."""
    calls = {call.name for tree in _rendered_trees() for call in _calls(tree)}
    assert calls == BUILTIN_NAMES, (
        f'tests/typeset/golden/model.yaml never calls {sorted(BUILTIN_NAMES - calls)}. '
        f'An operator with no case here renders untested.'
    )


def _calls(node: object) -> Iterator[FunctionCallNode]:
    if isinstance(node, FunctionCallNode):
        yield node
    for value in vars(node).values():
        for child in value.values() if isinstance(value, dict) else value if isinstance(value, list) else [value]:
            if is_dataclass(child):
                yield from _calls(child)


#: What the fixture cannot reach, by the source text of the line, in two
#: groups. The **guards** — every line of the two ``resolve … first`` arms and
#: the one asserting a constraint is a comparison — are what the walk raises
#: when resolution hands it something it types away, so a model reaching one is
#: a bug upstream rather than a case worth committing output for. The
#: **absent objective** is the arm a *different* model takes: a file declares
#: at most one, so a fixture that has one cannot also be a fixture that has
#: none, and `test_a_model_with_no_objective_prints_the_rest` covers it instead.
UNREACHABLE = {
    'if isinstance(node, (NameNode, NameListNode, KeywordNode, DimensionNode, LookupNode, EdgeNode)):',
    "msg = f'{type(node).__name__} reached the typesetter; resolve the expression first.'",
    'if isinstance(node, (UnresolvedNameNode, UnresolvedComparisonNode, UnresolvedPositionNode)):',
    "msg = f'{type(node).__name__} reached the typesetter; resolve the where string first.'",
    'if not isinstance(node, ComparisonNode):',
    "msg = f'{context}: expected a comparison, got {type(node).__name__}'",
    'raise AssertionError(msg)',
    'assert_never(node)',
    'if block is None:',
    'return []',
}


def test_the_golden_model_reaches_every_line_of_the_walk(tmp_path: Path):
    """The strongest form of what the fixture claims about itself.

    The two censuses above are about *symbols* and *node kinds*; nine of the
    fixture's cases differ from each other in neither. A width taken from a
    parameter rather than a number, a translation partitioned by a lookup, an
    integer variable with no bounds, a declaration with an empty ``foreach`` —
    each is an arm of the walk, each renders differently, and deleting any of
    them left both censuses green.

    So the arm itself is what gets counted. A branch added to the walk with no
    case here fails this the moment it lands, which is the point: output nobody
    has read is what a golden file is supposed to prevent.

    The render runs in a subprocess because the walk is imported long before
    any test starts, and a measurement that begins after the import counts
    every ``def`` and ``import`` line as unreached.
    """
    coverage = pytest.importorskip(
        'coverage', reason='the bare-install job has no dev tools; the guard runs wherever they are'
    )
    data = tmp_path / 'walk.coverage'
    render = tmp_path / 'render.py'
    render.write_text(f'from math_spec import to_latex\nto_latex({str(golden.MODEL)!r})\n')
    subprocess.run(
        [sys.executable, '-m', 'coverage', 'run', f'--data-file={data}', '--include=*/typeset/walk.py', str(render)],
        check=True,
    )
    measured = coverage.Coverage(data_file=str(data))
    measured.load()
    _, _, missing, _ = measured.analysis(walk.__file__)
    source = Path(walk.__file__).read_text().splitlines()
    unread = {line: source[line - 1].strip() for line in missing if source[line - 1].strip() not in UNREACHABLE}
    assert not unread, (
        f'tests/typeset/golden/model.yaml never renders {len(unread)} line(s) of the walk:\n'
        + '\n'.join(f'  {walk.__name__}:{line}  {text}' for line, text in sorted(unread.items()))
        + '\nAdd the case that reaches it, or say in UNREACHABLE why no model can.'
    )


def test_a_model_with_no_objective_prints_the_rest():
    """The one arm the fixture structurally cannot take. See :data:`UNREACHABLE`."""
    model = {
        'dimensions': {'t': {'dtype': 'int'}},
        'variables': {'x': {'foreach': ['t'], 'bounds': {'lower': 0}}},
        'constraints': {'cap': {'foreach': ['t'], 'expression': 'x <= 1'}},
    }
    rendered = to_latex(model)
    assert 'Objective' not in rendered, 'a model with no objective prints no objective section'
    assert 'Subject to' in rendered, 'the rest of a model with no objective still prints'


# ---------------------------------------------------------------------------
# structural well-formedness (no toolchain needed)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# the symbol table
# ---------------------------------------------------------------------------

SYMBOLS = {
    'notation': 'latex',
    'dimensions': {'generator': {'index': 'u', 'set': r'\mathcal{U}'}},
    'names': {'p': r'\pi', 'marginal_cost': r'c^{\mathrm{marg}}'},
}

TYPST_SYMBOLS = {
    'notation': 'typst',
    'dimensions': {'generator': {'index': 'u', 'set': 'cal(U)'}},
    'names': {'p': 'pi', 'p_max': 'bar(p)'},
}


WITH_MARGINAL_COST = override(
    DISPATCH,
    **{'parameters.marginal_cost': {'dims': ['generator']}, 'objective.expression': 'sum(p * marginal_cost)'},
)


def test_the_table_overrides_and_the_rest_is_still_derived():
    tex = to_latex(WITH_MARGINAL_COST, symbols=SYMBOLS, legend=False)
    assert r'\pi_{t,u}' in tex, 'both the symbol and its subscripts were overridden'
    assert r'c^{\mathrm{marg}}_{u}' in tex
    assert r'\mathit{load}_{t}' in tex, 'untouched, so still derived'
    assert r'u \in \mathcal{U}' in tex


DESCRIBED = override(
    DISPATCH,
    **{
        'dimensions.generator.description': 'dispatchable units',
        'parameters.p_max.description': 'installed capacity',
        'variables.p.description': 'output of a generator in a snapshot',
    },
)


@EVERY_FORMAT
def test_a_description_reaches_the_legend_without_hiding_the_name(fmt: Format):
    """The declaration's own `description:` is what the legend reads — no
    sidecar involved, so a model carries its prose wherever it goes."""
    out = typeset(DESCRIBED, fmt)
    for text in ('dispatchable units', 'installed capacity', 'output of a generator in a snapshot'):
        assert text in out, f'{text!r} never reached the legend'
    assert 'generator' in out, 'the description sits beside the name, it does not replace it'


@pytest.mark.parametrize(
    ('symbols', 'match'),
    [
        pytest.param({'names': {'p_maxx': 'x'}}, "Did you mean 'p_max'", id='a-misspelled-name'),
        pytest.param(
            {'dimensions': {'generatr': {'index': 'g'}}},
            "Did you mean 'generator'",
            id='a-misspelled-dimension',
        ),
        pytest.param({'symbols': {'p': 'x'}}, 'unknown section', id='an-unknown-section'),
        pytest.param(
            {'descriptions': {'p': 'the output'}},
            r"unknown section\(s\) \['descriptions'\]",
            id='a-table-still-carrying-descriptions',
        ),
        pytest.param({'dimensions': {'generator': {'letter': 'g'}}}, 'unknown key', id='an-unknown-key'),
    ],
)
def test_an_entry_naming_nothing_is_an_error_with_the_near_miss(symbols, match):
    """A silent typo means a symbol that never applies and a reader who never
    finds out — so it fails, and says what it probably meant."""
    with pytest.raises(SchemaError, match=match):
        to_latex(DISPATCH, symbols={'notation': 'latex', **symbols})


def test_a_table_prints_its_own_notation_verbatim():
    typ = to_typst(DISPATCH, symbols=TYPST_SYMBOLS)
    assert 'pi_(t,u)' in typ
    assert 'bar(p)_(u)' in typ
    assert 'u in cal(U)' in typ


@pytest.mark.parametrize(
    ('render', 'symbols', 'match'),
    [
        pytest.param(
            to_typst,
            {'notation': 'latex', 'names': {'p_max': r'\bar p'}},
            'written in latex, but this is a typst render',
            id='a-latex-table-into-typst',
        ),
        pytest.param(to_latex, TYPST_SYMBOLS, 'written in typst, but this is a latex render', id='typst-table-latex'),
        pytest.param(
            to_markdown, TYPST_SYMBOLS, 'written in typst, but this is a latex render', id='typst-table-markdown'
        ),
        pytest.param(to_latex, {'names': {'p': 'x'}}, "'notation:' is required", id='a-table-that-does-not-say'),
        pytest.param(
            to_latex,
            {'notation': 'latx', 'names': {'p': 'x'}},
            "unknown notation 'latx'. Valid notations",
            id='a-notation-outside-the-vocabulary',
        ),
    ],
)
def test_a_table_in_the_wrong_notation_refuses(render, symbols, match):
    """#321 was this failing silently — LaTeX passed into a Typst document,
    breaking three tools later; now it stops at the call, naming both notations."""
    with pytest.raises(SchemaError, match=match):
        render(DISPATCH, symbols=symbols)


def test_notation_is_case_insensitive():
    assert to_latex(DISPATCH, symbols={'notation': 'LaTeX', 'names': {'p': r'\pi'}}) == to_latex(
        DISPATCH, symbols={'notation': 'latex', 'names': {'p': r'\pi'}}
    ), 'load lower-cases the notation, so casing never changes the render'


def test_an_empty_override_is_used_not_fallen_through():
    tex = to_latex(DISPATCH, symbols={'notation': 'latex', 'names': {'p_max': ''}})
    assert r'p^{\mathrm{max}}' not in tex, 'an entry in the table is used verbatim, even empty — never re-derived'


def test_a_model_renders_identically_with_an_empty_table():
    assert to_latex(DISPATCH) == to_latex(DISPATCH, symbols=SymbolTable('latex'))


def test_exported_from_the_package():
    assert to_latex is to_latex
    assert to_typst is to_typst


@EVERY_FORMAT
def test_the_model_description_opens_the_document(fmt: Format):
    """What the file says it is, printed before anything it declares — and
    printed with `legend=False` too, since it is not a symbol table."""
    described = override(DISPATCH, description='least-cost dispatch of a generator fleet')
    for options in ({}, {'legend': False}):
        out = typeset(described, fmt, **options)
        assert 'least-cost dispatch of a generator fleet' in out, f'missing with {options}'
        assert out.index('least-cost dispatch') < out.index(fmt.operators['minimize']), 'it opens the document'
    assert 'least-cost dispatch' not in typeset(DISPATCH, fmt), 'a model without one prints no empty paragraph'


#: Every character the two typeset notations have to escape, in prose a
#: modeller would plausibly write: the underscore in a coordinate's name is
#: what #827 hit, on a description `examples/ports/pypsa_ac_dc.yaml` carried.
SPECIALS = r'flow to link_to, 100% & #1 costs $5 {net} ~ ^ \ *star* @ref <label>'

ESCAPED = {
    'latex': (r'link\_to', r'100\% \& \#1', r'\$5 \{net\}', r'\textasciitilde{}', r'\textbackslash{}'),
    'typst': (r'link\_to', r'\#1', r'\$5', r'\*star\*', r'\@ref', r'\<label\>'),
}


@pytest.mark.parametrize('notation', sorted(ESCAPED), ids=sorted(ESCAPED))
@pytest.mark.parametrize('position', ['file', 'declaration'], ids=['file-description', 'declaration-description'])
def test_a_description_sets_as_text_rather_than_as_markup(notation: str, position: str):
    """A `description:` is prose in no notation, so a special in it is a
    character rather than an instruction.

    Both places author prose reaches the page: the file's own description,
    which opens the document, and a declaration's, which is the `Meaning` half
    of its legend row. Left raw, `link_to` was a fatal `pdflatex` error instead
    of a document (#827), and the corpus could only avoid that by never writing
    one.
    """
    where = 'description' if position == 'file' else 'parameters.load.description'
    out = typeset(override(DISPATCH, **{where: SPECIALS}), FORMATS[notation])
    for expected in ESCAPED[notation]:
        assert expected in out, f'{notation}: {expected!r} is set as text'
    assert SPECIALS not in out, 'the raw prose reached the document unescaped'


#: What the renderer is swept over on this side of the cut: the operator probes
#: and the golden model, both of which travel with it. The same claim over this
#: repository's gallery is `tests/test_typeset_gallery.py`.
TRAVELLING_MODELS = [*OPERATOR_PROBES, golden.MODEL]


@pytest.mark.parametrize('path', TRAVELLING_MODELS, ids=lambda p: p.stem)
@EVERY_FORMAT
def test_every_travelling_model_renders(path, fmt):
    """The walk consumes the same AST the language produces, so anything
    `load_model` accepts it must print — a node it forgot is an exception, not
    a blank."""
    assert typeset(path, fmt).strip(), f'{path.name} rendered empty as {fmt}'
