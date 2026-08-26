# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Properties of the walk, asserted for every format; and the symbol derivation."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import pytest

from math_spec.errors import LanguageError
from math_spec.piecewise import expand_piecewise
from math_spec.typesetting import FORMATS, SymbolTable, to_latex, typeset
from math_spec.typesetting.format import OPERATOR_NAMES
from math_spec.typesetting.symbols import Symbols, _derive_name_symbol
from math_spec.validation import load_model
from tests.fixtures import DISPATCH_MODEL, OPERATOR_PROBES, override
from tests.typesetting import golden
from tests.typesetting.fixtures import EVERY_FORMAT, LATEX

if TYPE_CHECKING:
    from collections.abc import Callable

    from math_spec.typesetting.format import Format


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
    model = override(DISPATCH_MODEL, **{'variables.p.where': 'p_max > 0'})
    text = typeset(model, fmt, legend=False)
    forall, such_that = fmt.operators['forall'], fmt.operators['such_that']
    masked = [line for line in text.splitlines() if such_that in line]
    assert len(masked) == 1, 'one declaration carries a mask, so exactly one line says so'
    assert masked[0].index(forall) < masked[0].index(such_that), 'the mask follows the quantifier, not the equation'


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
    negated = f'{fmt.operators["not"]} {fmt.subscript(fmt.upright("flag"), ["g"])}'
    assert negated in text
    assert f'{negated} {fmt.prose(" is defined")}' not in text, (
        'the negation must not scope over prose it cannot bracket'
    )


def _storage(shift: str) -> dict[str, object]:
    """A state-of-charge balance, `soc == shift(soc, over=snapshot, <shift>)`: one model per translation policy.

    No parameter, so it is also the model the "given" convention has nothing to say about.
    """
    return {
        'dimensions': {'snapshot': {'dtype': 'int'}},
        'variables': {'soc': {'foreach': ['snapshot'], 'bounds': {'lower': 0, 'upper': 100}}},
        'constraints': {
            'balance': {'foreach': ['snapshot'], 'expression': f'soc == shift(soc, over=snapshot, {shift})'}
        },
    }


def _operator(name: str) -> Callable[[Format], str]:
    return lambda fmt: fmt.operators[name]


def _filled(name: str) -> Callable[[Format], str]:
    """The operator with its fill, `0`, in its subscript slot."""
    return lambda fmt: fmt.subscript(fmt.operators[name], ['0'])


@EVERY_FORMAT
@pytest.mark.parametrize(
    ('shift', 'present', 'absent'),
    [
        pytest.param('offset=1', [_operator('minus')], [_operator('cyclic_minus'), _operator('edge_minus')], id='bare'),
        pytest.param("offset=1, edge='wrap'", [_operator('cyclic_minus')], [_operator('edge_minus')], id='wrap'),
        pytest.param('offset=1, edge=0', [_filled('edge_minus')], [_operator('cyclic_minus')], id='fill'),
        pytest.param('offset=-1, edge=0', [_filled('edge_plus')], [_operator('edge_minus')], id='forwards'),
    ],
)
def test_each_edge_policy_is_its_own_translation_symbol(fmt: Format, shift: str, present, absent):
    """The edge policies are different models, so they are different renderings.

    A bare shift drops the row the translation vacates; ``edge='wrap'`` wraps;
    ``edge=v`` keeps the row and puts *v* there. Rendering the last as `t - 1`
    said the first thing about a model doing the third — and the fill rides on
    the operator because it is per call site: one model may pad a sum with `0`
    and a product with `1`, and a legend naming both cannot say which term is
    which. The forward half is here because the walk used to abort on
    ``offset=-1`` — the parser reads it as a unary minus over a number — so
    every format raised on a legal model and the forward spellings had never
    been printed.
    """
    text = typeset(_storage(shift), fmt, legend=False)
    for spelling in present:
        assert spelling(fmt) in text
    for spelling in absent:
        assert spelling(fmt) not in text, 'a shift under one edge policy borrowed the spelling of another'


@EVERY_FORMAT
def test_a_fill_and_a_group_take_the_operators_two_slots(fmt: Format):
    """The fill subscripts the operator; the group superscripts it.

    One slot each, so neither `\\boxminus_{0}_{season_of(t)}` — a *Double
    subscript* error that stopped the page compiling — nor
    `\\boxminus_{0,season_of(t)}`, which compiles and leaves a reader to guess
    which of the two is the value standing at the boundary and which is the
    group the translation stays inside. The two policies are independent, so
    nothing else has to be wrong for a model to reach this.
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
    group = fmt.apply(fmt.upright('season_of'), 't')
    filled = fmt.subscript(fmt.operators['edge_minus'], ['0'])
    assert fmt.superscript(filled, group) in text, 'the fill and the group are not in their own slots'
    assert fmt.subscript(fmt.operators['edge_minus'], ['0', group]) not in text, (
        'the fill and the group are sharing one subscript again'
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
    assert fmt.operators['cyclic_minus'] in text and fmt.operators['minus'] in text


@EVERY_FORMAT
def test_a_negation_under_a_plus_is_the_subtraction_it_means(fmt: Format):
    """`a + -b` is a spelling nobody uses, and the walk was printing it."""
    model = override(DISPATCH_MODEL, **{'objective.expression': 'sum(p) + -sum(p)'})
    text = typeset(model, fmt)
    assert f'{fmt.operators["plus"]} {fmt.operators["minus"]}' not in text
    assert fmt.operators['minus'] in text, 'the subtraction it folded into should still print'


@EVERY_FORMAT
def test_a_mask_that_is_only_true_prints_no_condition(fmt: Format):
    """The language says `True` is the same as no `where`, so a `\\top` on the
    quantifier would put a condition on the page that reads as one and is not.

    Nested it still prints: `\\top \\wedge x` is what the file says, and simplifying a
    mask belongs to resolution rather than to the typesetter.
    """
    always = override(DISPATCH_MODEL, **{'constraints.balance.where': 'True'})
    assert fmt.operators['true'] not in typeset(always, fmt)
    nested = override(DISPATCH_MODEL, **{'constraints.balance.where': 'True AND load > 0'})
    assert fmt.operators['true'] in typeset(nested, fmt)


@EVERY_FORMAT
def test_the_legend_explains_wraparound_only_when_it_is_used(fmt: Format):
    assert 'cyclic translation' in typeset(_storage("offset=1, edge='wrap'"), fmt)
    assert 'cyclic translation' not in typeset(DISPATCH_MODEL, fmt)


def _selected(mask: str) -> dict[str, Any]:
    """One constraint carrying *mask*, over a dimension a lookup groups."""
    return {
        'dimensions': {'snapshot': {'dtype': 'int'}, 'season': {'dtype': 'str'}},
        'lookups': {'season_of': {'over': 'snapshot', 'into': 'season'}},
        'variables': {'soc': {'foreach': ['snapshot'], 'bounds': {'lower': 0}}},
        'constraints': {'seed': {'foreach': ['snapshot'], 'where': mask, 'expression': 'soc == 0'}},
    }


@EVERY_FORMAT
def test_a_position_from_the_end_prints_against_the_size(fmt: Format):
    """``-1`` is not a position, and the page has already said so.

    The legend gives the order ``0`` to one end and the size less one to the
    other, so an equation asserting a position *is* ``-1`` has no solution
    under the only reading offered for it — Python's index sugar, read as
    math. The sign is known where it prints, so the page can say what the file
    means instead.
    """
    text = typeset(_selected('position(snapshot) == -1'), fmt)
    assert f'{fmt.cardinality(fmt.script("T"))} {fmt.operators["minus"]} 1' in text
    assert f'{fmt.operators["equal"]} -1' not in text


@EVERY_FORMAT
def test_a_grouped_position_rides_a_subscript_rather_than_a_second_argument(fmt: Format):
    """The group is a modifier — which order is counted — not another position.

    As ``pos(t, season_of(t))`` the second argument sits where a reader of the
    first one expects an integer, and nothing says it means "within".
    """
    text = typeset(_selected('position(snapshot, by=season_of) == 0'), fmt)
    applied = fmt.apply(fmt.upright('season_of'), 't')
    assert fmt.apply(fmt.subscript(fmt.operators['position'], [applied]), 't') in text


@EVERY_FORMAT
def test_the_legend_explains_a_position_only_where_one_prints(fmt: Format):
    """Each positional symbol is introduced where it is used, and nowhere else.

    The first note is the one the page cannot go without: a reader arrives
    from papers whose index *is* the ordinal, so a page printing both
    ``pos(t) = 0`` and ``t >= 3`` has to say once which of the two is the
    coordinate.
    """
    plain = typeset(_selected('position(snapshot) == 0'), fmt)
    assert 'against positions' in plain
    assert 'against positions' not in typeset(DISPATCH_MODEL, fmt)
    assert 'counts within the group' not in plain, 'no grouped position printed'
    assert 'counted from the end' not in plain, 'no position counted from the end printed'
    assert 'counts within the group' in typeset(_selected('position(snapshot, by=season_of) == 0'), fmt)
    assert 'counted from the end' in typeset(_selected('position(snapshot) == -1'), fmt)


@EVERY_FORMAT
def test_a_dimension_compared_against_a_number_says_what_its_coordinates_are(fmt: Format):
    """``t >= 3`` is the line the convention this notation inverts reads wrong.

    A comparison against a label that is a *number* is the one that can be
    taken for a position, so the legend places it: every other coordinate
    prints as prose and could not be read as one.
    """
    text = typeset(_selected('snapshot >= 3'), fmt)
    assert f'({fmt.mono("int")} coordinates)' in text
    assert f'({fmt.mono("str")} coordinates)' not in text, 'season is compared against nothing'
    assert 'coordinates)' not in typeset(_selected('position(snapshot) == 0'), fmt)


@EVERY_FORMAT
def test_a_description_is_joined_to_its_name_by_a_dash_the_format_renders(fmt: Format):
    """``---`` is TeX's em-dash ligature and Typst's, and nothing in Markdown.

    So the legend row that reads "`cost` over G --- marginal cost" set as a
    dash in two of the three outputs and as three hyphens in the one whose
    whole promise is that it renders where it lands. The dash is an atom of the
    format now; this is what stops it going back to a literal in the walk,
    where it cannot be spelled two ways.
    """
    described = override(DISPATCH_MODEL, **{'parameters.cost.description': 'marginal cost'})
    text = typeset(described, fmt)
    assert f'{fmt.dash} marginal cost' in text
    if fmt is FORMATS['markdown']:
        assert '---' not in text.replace('|---|---|', ''), 'markdown renders the ligature literally'


@EVERY_FORMAT
def test_macros_and_named_expressions_are_expanded_away(fmt: Format):
    """What prints is the math a backend builds, not the sugar it was spelled with."""
    model = override(
        DISPATCH_MODEL,
        **{'expressions.supply': 'sum(p, over=generator)', 'constraints.balance.expression': 'supply == load'},
    )
    assert 'supply' not in typeset(model, fmt, legend=False)


@EVERY_FORMAT
def test_an_invalid_model_is_refused_before_anything_renders(fmt: Format):
    broken = override(DISPATCH_MODEL, **{'objective.expression': 'p * nonexistent'})
    with pytest.raises(LanguageError):
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
        pytest.param('theta', r'\theta', id='a-name-that-is-a-greek-letter-is-the-letter'),
        pytest.param('theta_max', r'\theta^{\mathrm{max}}', id='and-is-a-head-a-qualifier-may-hang-off'),
        pytest.param('thetas', r'\mathit{thetas}', id='but-only-when-the-whole-name-is-the-letter'),
    ],
)
def test_an_underscore_is_only_a_qualifier_when_its_head_is_a_symbol(name: str, expected: str):
    """`marginal_cost` is not *marginal* raised to *cost*. Splitting every
    underscore turned about a third of real names into nonsense."""
    assert _derive_name_symbol(name, frozenset({'p', 'soc'}), LATEX) == expected


@pytest.mark.parametrize(
    ('name', 'expected'),
    [
        pytest.param('cost', r'\mathrm{cost}', id='a-word'),
        pytest.param('p', r'\mathrm{p}', id='and-a-single-letter-too'),
        pytest.param('p_max', r'\mathrm{p}^{\mathrm{max}}', id='the-head-of-a-qualifier-with-it'),
        pytest.param('eta', r'\mathrm{eta}', id='and-a-greek-name-the-rule-beating-the-letter'),
    ],
)
def test_a_given_quantity_is_upright(name: str, expected: str):
    r"""Upright is what the data supplies, and it admits no exception.

    Not for single letters — `p^max` beside a variable `p` is exactly the pair
    a reader has to be able to tell apart — and not for a Greek name, where
    LaTeX has no upright lower-case form without `upgreek`, and taking that
    dependency would cost both a two-package preamble and markdown that
    renders the same on GitHub as on the docs site. An italic `\eta` that
    might be either is worse than an upright `\mathrm{eta}` that is one.
    """
    assert _derive_name_symbol(name, frozenset({'p', 'soc'}), LATEX, given=True) == expected


@EVERY_FORMAT
def test_a_name_that_is_a_greek_letter_prints_as_the_letter(fmt: Format):
    """A variable called `theta` set as the italic word *theta* is the one
    derived symbol no paper would accept."""
    model = override(DISPATCH_MODEL, **{'variables.theta': {'foreach': ['snapshot']}})
    assert fmt.greek('theta') in typeset(model, fmt)


@EVERY_FORMAT
def test_a_parameter_is_upright_and_a_variable_is_italic(fmt: Format):
    """The one distinction a reader of a linear model cannot afford to guess.

    A nomenclature table already splits the legend, and that is the convention
    the field uses — but it is a lookup rather than a reading, and an equation
    quoted on its own takes the legend with it. So the symbols carry it:
    upright is what the model is given, italic is what the solver chooses.
    """
    text = typeset(DISPATCH_MODEL, fmt, legend=False)
    assert fmt.subscript(fmt.upright('load'), ['t']) in text, 'a parameter is given, so it is upright'
    assert fmt.subscript(fmt.italic('load'), ['t']) not in text
    assert fmt.subscript('p', ['t', 'g']) in text, 'a variable is chosen, so it stays italic'


@EVERY_FORMAT
def test_the_legend_states_the_convention_only_where_it_draws_it(fmt: Format):
    """A note explaining a contrast the page does not draw is a dead end, the
    same reason the translation notes are gated on their symbol printing."""
    assert 'Upright is what the model is given' in typeset(DISPATCH_MODEL, fmt)
    assert 'Upright is what the model is given' not in typeset(_storage('offset=1'), fmt)


def test_nothing_the_model_is_given_prints_italic():
    r"""The convention as a property of the whole document, not of a fragment.

    The per-name tests pin the derivation and the goldens pin the bytes, but
    neither says *nothing else* prints a given quantity italic: a rendering
    path added later reaches the page through its own call, and the first to
    notice would be a reader rather than the suite. So this asks the finished
    document, over the fixture that carries every construct.

    ``\mathit`` is what a multi-letter name prints as, and a single-letter
    given quantity is upright too (``\mathrm{p}``), so a leak of either kind
    lands in one of these two nets.
    """
    schema = expand_piecewise(load_model(golden.MODEL))
    italic = {m.replace(r'\_', '_') for m in re.findall(r'\\mathit\{([^}]*)\}', to_latex(golden.MODEL))}
    assert italic <= set(schema.variables), (
        f'{sorted(italic - set(schema.variables))} print italic and are not variables — '
        f'upright is what the model is given'
    )

    symbols = Symbols(schema, LATEX, SymbolTable('latex'))
    given = {name: symbols.name[name] for name in schema.parameters}
    assert all(symbol.startswith(r'\mathrm{') for symbol in given.values()), (
        f'derived upright for every parameter, but got {sorted(s for s in given.values() if "mathrm" not in s)}'
    )


@EVERY_FORMAT
def test_the_convention_note_quotes_only_what_the_derivation_chose(fmt: Format):
    """A table is printed verbatim and is the author's to write, so a symbol it
    supplies is not one the note governs.

    `examples/symbols/dispatch.yaml` maps three parameters to italic symbols,
    and the homepage renders through it — so the note quoting one of those said
    "a parameter such as $\\bar p$" under a sentence claiming a parameter is
    upright, contradicting itself on the page a reader arrives at first.
    """
    table = {'notation': fmt.notation, 'names': {'load': 'x', 'cost': 'c', 'p_max': 'm'}}
    assert 'Upright is what the model is given' not in typeset(DISPATCH_MODEL, fmt, symbols=table)
    assert 'Upright is what the model is given' in typeset(DISPATCH_MODEL, fmt), 'derived, so the note applies'


@EVERY_FORMAT
def test_a_dimension_is_not_a_head_a_qualifier_hangs_off(fmt: Format):
    """`zone_cap` is a capacity *indexed by* zone, not a zone qualified by cap.

    Reading the axis as the head also made a parameter's symbol depend on
    whether some unrelated dimension happened to share its prefix: declare a
    dimension named `tech` and `tech_cap` silently re-rendered.
    """
    model = override(
        DISPATCH_MODEL,
        **{'dimensions.zone': {'dtype': 'str'}, 'parameters.zone_cap': {'dims': ['zone']}},
    )
    text = typeset(model, fmt)
    assert fmt.upright('zone_cap') in text
    assert fmt.superscript(fmt.upright('zone'), fmt.upright('cap')) not in text


# ---------------------------------------------------------------------------
# the objective's summations — what the file wrote, and no more
# ---------------------------------------------------------------------------


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


def summations(text: str, fmt: Format) -> int:
    """How many summations *text* opens, derived from the format's own spelling."""
    return text.count(fmt.summation('DOMAIN', 'BODY').split('DOMAIN')[0])


def over_generators(fmt: Format) -> str:
    """``sum over g in G``, opened but not filled — what the capital term is under."""
    return fmt.summation(f'g {fmt.operators["in"]} {fmt.script("G")}', '').rstrip()


@EVERY_FORMAT
def test_the_objective_shows_the_summations_the_file_wrote(fmt: Format):
    """One summation per ``sum`` in the expression, over the dims it took.

    The objective is scalar, so nothing is implied and nothing is grouped: the
    capital term below is summed over generators alone because that is what its
    own bracket closes over. A walk that reduced the objective itself would
    have to decide where each summation begins, and #1046 is what that cost.
    """
    text = typeset(MIXED, fmt, legend=False)
    assert summations(text, fmt) == 2, 'each written sum is one summation'
    assert over_generators(fmt) in text, 'the capital term is summed over generators alone'


@EVERY_FORMAT
def test_two_sums_of_the_same_dims_stay_two_summations(fmt: Format):
    """The file's structure survives to the page, even where it repeats itself.

    Merging the pair would read better and say something the file does not:
    that one bracket covers both terms. The walk renders what is written.
    """
    text = typeset(override(MIXED, **{'objective.expression': 'sum(p * cost) + sum(p * cost)'}), fmt, legend=False)
    assert summations(text, fmt) == 2, 'two written sums are two summations'


@EVERY_FORMAT
def test_a_subtracted_summation_keeps_the_sign_outside_it(fmt: Format):
    """The sign is applied to the whole reduction, and the bracket says so."""
    text = typeset(override(MIXED, **{'objective.expression': 'sum(p * cost) - sum(p_nom * capex)'}), fmt, legend=False)
    opener = fmt.parenthesise('BODY').split('BODY')[0] + over_generators(fmt)
    assert f'{fmt.operators["minus"]} {opener}' in text


TRAVELLING_MODELS = [*OPERATOR_PROBES, golden.MODEL]


@pytest.mark.parametrize('path', TRAVELLING_MODELS, ids=lambda p: p.stem)
@EVERY_FORMAT
def test_every_travelling_model_renders(path, fmt):
    """The walk consumes the same AST the language produces, so anything
    `load_model` accepts it must print — a node it forgot is an exception, not
    a blank."""
    assert typeset(path, fmt).strip(), f'{path.name} rendered empty as {fmt}'


# ---------------------------------------------------------------------------
# scope and brackets — where a rendering can read as different math
# ---------------------------------------------------------------------------


#: Two frames over generators, a lookup onto buses and a boolean mask — what the
#: scope and bracketing cases are written against.
BUSES = {
    'dimensions': {'snapshot': {'dtype': 'int'}, 'generator': {'dtype': 'str'}, 'bus': {'dtype': 'str'}},
    'lookups': {'bus_of': {'over': 'generator', 'into': 'bus'}},
    'parameters': {'load': {'dims': ['snapshot']}, 'k': {'dims': []}, 'flag': {'dims': ['snapshot'], 'dtype': 'bool'}},
    'variables': {'p': {'foreach': ['snapshot', 'generator']}, 'q': {'foreach': ['snapshot', 'generator']}},
}


def _row(expression: str, where: str | None = None, **patch: object) -> str:
    model = override(
        BUSES,
        **{'constraints.k': {'foreach': ['snapshot', 'generator'], 'expression': expression, 'where': where}},
        **patch,
    )
    return next(line for line in to_latex(model, legend=False).splitlines() if line.startswith(r'\text{k}'))


def test_a_reduction_under_its_own_dimension_takes_a_fresh_dummy():
    """Reusing `g` makes `bus_of(g) = bus_of(g)` a tautology — the sum of everything."""
    tex = _row('p == at(sum(q, by=bus_of), by=bus_of)')
    assert r"\sum_{g' \in \mathcal{G} \,:\, \mathrm{bus\_of}(g') = \mathrm{bus\_of}(g)} q_{t,g'}" in tex, tex
    tex = _row('p == q - sum(q, over=generator)')
    assert r"\sum_{g' \in \mathcal{G}} q_{t,g'}" in tex, tex


@pytest.mark.parametrize(
    ('where', 'expected'),
    [
        pytest.param('not (load >= 3)', r'\neg \left( \mathrm{load}_{t} \ge 3 \right)', id='a-comparison'),
        pytest.param('not load', r'\neg \left( \mathrm{load}_{t} \text{ is defined} \right)', id='definedness'),
        pytest.param('not flag', r'\neg \mathrm{flag}_{t}', id='a-boolean-is-the-predicate'),
    ],
)
def test_a_negated_predicate_is_bracketed_where_it_could_read_otherwise(where, expected):
    tex = _row('p <= q', where=where)
    assert expected in tex, tex


def test_a_chain_of_ors_is_flat():
    tex = _row('p <= q', where='flag or flag or flag')
    assert r'\mathrm{flag}_{t} \vee \mathrm{flag}_{t} \vee \mathrm{flag}_{t}' in tex, tex
    assert r'\left(' not in tex.split(r'\,:\,')[1], tex


def test_an_or_under_an_and_keeps_its_brackets():
    tex = _row('p <= q', where='flag and (flag or load > 0)')
    assert r'\mathrm{flag}_{t} \wedge \left( \mathrm{flag}_{t} \vee \mathrm{load}_{t} > 0 \right)' in tex, tex


@pytest.mark.parametrize(
    ('expression', 'expected', 'forbidden'),
    [
        pytest.param('p == q - -(q + k)', r'q_{t,g} + q_{t,g} + \mathrm{k}', '- -', id='minus-minus-folds-to-plus'),
        pytest.param(
            'p == q - -2 * k', r'q_{t,g} + 2 \cdot \mathrm{k}', '- -', id='a-sign-on-the-first-factor-folds-too'
        ),
        pytest.param('p == q + -k / 2', r'q_{t,g} - \frac{\mathrm{k}}{2}', '+ -', id='a-sign-on-a-dividend-folds-too'),
        pytest.param(
            'p == q * -(q + k)',
            r'q_{t,g} \cdot \left( -\left( q_{t,g} + \mathrm{k} \right) \right)',
            r'\cdot -',
            id='a-negation-as-a-factor',
        ),
        pytest.param(
            'p == 2 * +(q + k)',
            r'2 \cdot \left( q_{t,g} + \mathrm{k} \right)',
            r'\left( \left(',
            id='a-unary-plus-says-nothing',
        ),
        pytest.param('p == -q * 2', r'-q_{t,g} \cdot 2', r'\left(', id='a-negated-first-factor'),
    ],
)
def test_a_sign_beside_an_operator_is_bracketed_or_folded(expression, expected, forbidden):
    tex = _row(expression)
    assert expected in tex and forbidden not in tex, tex


@pytest.mark.parametrize(
    ('literal', 'expected'),
    [
        pytest.param('1e-5', r'10^{-5} \cdot q_{t,g}', id='a-power-of-ten'),
        pytest.param('2.5e-7', r'2.5 \times 10^{-7} \cdot q_{t,g}', id='a-mantissa'),
        pytest.param('1e6', r'1000000 \cdot q_{t,g}', id='a-whole-number-prints-whole'),
        pytest.param('0.5', r'0.5 \cdot q_{t,g}', id='a-plain-decimal'),
    ],
)
def test_a_float_prints_as_a_number_not_as_python(literal, expected):
    assert expected in _row(f'p == {literal} * q')


@EVERY_FORMAT
def test_a_string_value_in_a_where_prints_as_a_quoted_label(fmt: Format):
    """`fuel == 'gas_ccgt'` rendered the label in text mode, where MathJax
    prints the underscore's escape as a literal backslash — and an
    operator-valued label such as `'>='` read as `= >=`, an equals against a
    bare glyph. Quoted, with the word upright in math mode, both read as the
    file spells them."""
    model = {
        'dimensions': {'plant': {'dtype': 'str'}},
        'parameters': {'fuel': {'dims': ['plant'], 'dtype': 'str'}, 'cost': {'dims': ['plant']}},
        'variables': {'p': {'foreach': ['plant'], 'where': "fuel == 'gas_ccgt'"}},
        'objective': {'expression': 'sum(p * cost)'},
    }
    text = typeset(model, fmt, legend=False)
    assert fmt.quoted('gas_ccgt') in text, 'a string value prints through the quoted seam'
    assert fmt.prose('gas_ccgt') not in text, 'a string value is data, never words inside math'
