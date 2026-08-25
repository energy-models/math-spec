# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The PyPSA tier ladder states the model PyPSA states, and answers where it reads.

Ported as proof-of-concept groundwork from lpspec's ``compat/pypsa/`` — see
``compat/pypsa/README.md`` for the ladder and what each rung claims. mathspec
states the math only and has no build/solve engine yet, so the tests below
that need one (a bound model, a linopy model, a populated HiGHS instance, a
solved answer) are ported but skipped; they name the shape a future build
layer would have to fill. Only the language-level gates run today: a model
that loads needs no data and no optional dependency.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from math_spec import load_model

if TYPE_CHECKING:
    from collections.abc import Callable

    from compat.pypsa.tiers import Tier

MODELS = Path(__file__).resolve().parent.parent / 'compat' / 'pypsa' / 'models'

INF = float('inf')


def _models() -> list[Path]:
    return sorted(MODELS.glob('*.yaml'))


#: Tier names are the model stems, so this needs no import from `bench`, which
#: is what lets the load gate below run on the bare install.
TIER_NAMES = [p.stem for p in _models()]


@pytest.mark.parametrize('model', _models(), ids=lambda p: p.stem)
def test_a_pypsa_tier_model_loads(model: Path):
    """Compiles with no data bound — holds even on the bare install."""
    load_model(model)


def test_the_ladder_is_not_empty():
    """A guard on the guard: the parametrised test above passes vacuously if
    the glob stops matching, e.g. a rename of ``compat/pypsa/models/``."""
    assert len(_models()) >= 1, f'expected at least the T1 model; found {_models()}'


@pytest.fixture(scope='module')
def tiers():
    return pytest.importorskip('compat.pypsa.tiers', reason='needs pandas; the bare install has none')


@pytest.mark.skip(reason='mathspec has no build engine yet — nothing to bind sources to')
@pytest.mark.parametrize('tier_name', TIER_NAMES)
def test_a_pypsa_tier_builds_on_the_base_shape(tier_name: str, tmp_path: Path, tiers):
    pytest.importorskip('pyarrow', reason='needs pyarrow; the bare install has none')
    from compat.pypsa.network import Shape

    tier: Tier = tiers.TIERS[tier_name]
    sources = tiers.bind(tier, Shape('base'), tmp_path)
    with lps.build(tier.model, sources) as bound:  # noqa: F821 -- pending mathspec build API
        assert bound is not None


def test_a_component_with_no_pypsa_lane_is_refused(tiers):
    """A rung naming a component ``build_network`` cannot build is a rung whose
    two lanes solve different problems, and it says so instead of quietly
    building the one it knows."""
    pytest.importorskip('pypsa', reason='needs pypsa; the bare install has none')
    from compat.pypsa.network import Shape, build_network

    with pytest.raises(ValueError, match='Store'):
        build_network(Shape('base'), frozenset({'Generator', 'Store'}))


@pytest.mark.skip(reason='mathspec has no build/solve engine yet')
@pytest.mark.parametrize('tier_name', TIER_NAMES)
def test_a_pypsa_tier_agrees_with_pypsa(tier_name: str, tmp_path: Path, tiers):
    """A live oracle: this recomputes PyPSA's objective on every run rather
    than pinning a recorded number, unlike ``tests/test_ports.py``.

    The comparable figure is ``objective + objective_constant``, not
    ``objective``. It is the same number on every tier up to T4, where
    extendable capacity makes PyPSA credit the capital already standing in
    ``p_nom`` and report the change against it, while lpspec states the system
    cost outright — so the sum is what a later tier needs and what is written
    here now rather than after T4 fails mysteriously.

    Columns are compared as well as the optimum, because an objective is one
    number and two different models reach it: an lpspec rung that declared
    fewer variables than its PyPSA twin still hits it wherever the missing ones
    sit at zero, and would pass a comparison of optima alone. Rows
    are deliberately *not* compared — see ``compat/pypsa/README.md``.
    """
    pytest.importorskip('pypsa', reason='needs pypsa; the bare install has none')
    from compat.pypsa.network import Shape, build_network

    tier: Tier = tiers.TIERS[tier_name]
    shape = Shape('base')

    logging.getLogger('pypsa').setLevel(logging.ERROR)
    logging.getLogger('linopy').setLevel(logging.ERROR)

    n = build_network(shape, tier.components)
    status, condition = n.optimize(solver_name='highs', include_objective_constant=False)
    assert (status, condition) == ('ok', 'optimal'), f'pypsa lane did not solve: {status}, {condition}'
    expected = float(n.objective) + float(n.objective_constant)

    sources = tiers.bind(tier, shape, tmp_path)
    with lps.build(tier.model, sources) as bound:  # noqa: F821 -- pending mathspec build API
        solution = bound.solve()
        assert solution.is_ok, f'lpspec lane did not solve: {solution.status}'
        assert solution.objective == pytest.approx(expected, rel=1e-9), (
            f'{tier.name}: lpspec and pypsa must describe the same model'
        )
        assert bound.diagnostics().columns == n.model.nvars, (
            f'{tier.name}: the two lanes must decide the same variables — '
            f'lpspec {bound.diagnostics().columns}, pypsa {n.model.nvars}'
        )


def _as_pypsa(name: str) -> str:
    """A declaration's name as PyPSA's linopy model spells it.

    PyPSA joins the component to the attribute with ``-``; lpspec cannot, its
    expression parser reading a hyphen as subtraction. So a rung writes
    ``Component_attribute`` and the first underscore is the join — which leaves
    ``Bus_nodal_balance`` mapping to ``Bus-nodal_balance`` and not to
    ``Bus-nodal-balance``, the reason this replaces one and not all.
    """
    return name.replace('_', '-', 1)


#: A linopy sign as the ``[lower, upper]`` span HiGHS states the same row with,
#: so one fold serves both extractors.
SPAN: dict[str, Callable[[float], tuple[float, float]]] = {
    '=': lambda rhs: (rhs, rhs),
    '<=': lambda rhs: (-INF, rhs),
    '>=': lambda rhs: (rhs, INF),
}


def _fold(columns: dict[Any, list[float]], gathered: dict[Any, list]) -> dict[Any, tuple]:
    """Rewrite every single-variable row as the bound it is, in place.

    The one normalisation both comparisons in this module need, and the only
    reason two lanes stating one LP can be compared at all: PyPSA states a
    bound as a row and leaves the column at ``+-inf``, lpspec states it on the
    column and builds no row. A row is folded into its column's bounds by
    tightening them, which is what makes `a <= x <= b` and two rows the same
    model.

    *columns* is mutated; the rows worth comparing as rows are returned. A
    coefficient of zero is not a term — a row left with one live term after
    that is a bound however many entries linopy stored for it.

    Args:
        columns: Mutable ``[lower, upper]`` by column key.
        gathered: ``[terms, lower, upper]`` by row key, *terms* mapping a
            column key to its coefficient.
    """
    rows = {}
    for key, (terms, lower, upper) in gathered.items():
        live = {column: coefficient for column, coefficient in terms.items() if coefficient != 0.0}
        if len(live) != 1:
            rows[key] = (tuple(sorted(live.items())), lower, upper)
            continue
        ((column, coefficient),) = live.items()
        low, high = sorted((lower / coefficient, upper / coefficient))
        columns[column][0] = max(columns[column][0], low)
        columns[column][1] = min(columns[column][1], high)
    return rows


def _at_coordinate(labels: Any) -> dict[int, tuple[Any, ...]]:
    """linopy's integer labels, by the coordinate each one sits at.

    Labels are assigned in build order and mean nothing across two models, so
    every comparison here keys on the coordinate instead. ``-1`` is linopy's
    mask for a slot no variable or row was built at.
    """
    series = labels.to_series()
    return {int(v): (k if isinstance(k, tuple) else (k,)) for k, v in series.items() if int(v) >= 0}


def _canonical(model: Any, spell: Callable[[str], str]) -> tuple[dict, dict, dict]:
    """One linopy model as three label-free dicts: columns, objective, rows.

    Keys are ``(declaration name, coordinate)`` with the name put through
    *spell*, so the same LP built by two libraries canonicalises to the same
    thing. Two normalisations make that true:

    **A single-variable row is a bound** — `_fold`.

    **Repeated terms are collapsed.** linopy stores ``x + 2 * x`` as two
    entries where a coefficient comparison needs one — the same trap
    ``tests/test_corpus_parity.py`` documents.

    Returns:
        ``(columns, cost, rows)`` — bounds by column, objective coefficient by
        column, and ``(terms, lower, upper)`` by row.
    """
    where: dict[int, tuple[str, tuple[Any, ...]]] = {}
    columns: dict[tuple[str, tuple[Any, ...]], list[float]] = {}
    for name, variable in model.variables.items():
        labels = variable.labels.to_series()
        lowers, uppers = variable.lower.to_series(), variable.upper.to_series()
        for (coordinate, label), lower, upper in zip(labels.items(), lowers, uppers, strict=True):
            if int(label) < 0:
                continue
            key = (spell(name), coordinate if isinstance(coordinate, tuple) else (coordinate,))
            where[int(label)] = key
            columns[key] = [float(lower), float(upper)]

    cost: dict[tuple[str, tuple[Any, ...]], float] = {}
    for term in model.objective.to_polars().iter_rows(named=True):
        if term['vars'] >= 0:
            cost[where[term['vars']]] = cost.get(where[term['vars']], 0.0) + term['coeffs']

    gathered: dict[tuple[str, tuple[Any, ...]], list] = {}
    for name, constraint in model.constraints.items():
        at = _at_coordinate(constraint.labels)
        for term in constraint.to_polars().iter_rows(named=True):
            if term['labels'] < 0 or term['vars'] < 0:
                continue
            key = (spell(name), at[term['labels']])
            entry = gathered.setdefault(key, [{}, *SPAN[str(term['sign'])](float(term['rhs']))])
            column = where[term['vars']]
            entry[0][column] = entry[0].get(column, 0.0) + term['coeffs']

    rows = _fold(columns, gathered)
    return {key: tuple(value) for key, value in columns.items()}, cost, rows


def _values(canonical: dict) -> list[Any]:
    return [canonical[key] for key in sorted(canonical, key=repr)]


@pytest.mark.skip(reason='mathspec has no build/solve engine yet')
@pytest.mark.parametrize('tier_name', TIER_NAMES)
def test_a_pypsa_tier_builds_the_linopy_model_pypsa_builds(tier_name: str, tmp_path: Path, tiers):
    """The two linopy models are the same model — the ladder's strongest gate.

    Objective parity says the lanes reach one number and column parity says
    they count the same variables; neither says they wrote the same LP. This
    compares it: every column with its bounds, every objective coefficient,
    every row with its terms, sign and right-hand side, keyed by coordinate
    because linopy's labels mean nothing across two models.

    The one normalisation is ``_canonical``'s: PyPSA states bounds as rows and
    lpspec states them as bounds, so a single-variable row is read as the bound
    it is. Nothing else is forgiven — a coefficient, a sign, a right-hand side
    or a coordinate that differs fails here.
    """
    pytest.importorskip('pypsa', reason='needs pypsa; the bare install has none')
    from lpspec import linopy as lpspec_linopy

    from compat.pypsa.network import Shape, build_network

    logging.getLogger('pypsa').setLevel(logging.ERROR)
    logging.getLogger('linopy').setLevel(logging.ERROR)

    tier: Tier = tiers.TIERS[tier_name]
    shape = Shape('base')

    network = build_network(shape, tier.components)
    theirs = _canonical(network.optimize.create_model(include_objective_constant=False), str)
    ours = _canonical(lpspec_linopy.build(tier.model, tiers.bind(tier, shape, tmp_path)), _as_pypsa)

    for part, mine, yours in zip(('columns', 'objective', 'rows'), ours, theirs, strict=True):
        assert set(mine) == set(yours), (
            f'{tier.name}: the two lanes state different {part} — '
            f'only lpspec {sorted(set(mine) - set(yours), key=repr)[:5]}, '
            f'only pypsa {sorted(set(yours) - set(mine), key=repr)[:5]}'
        )
        assert _values(mine) == pytest.approx(_values(yours), rel=1e-9, abs=1e-12), (
            f'{tier.name}: the two lanes agree on which {part} exist and not on what they say'
        )


def _numbers(item: Any) -> list[float]:
    """Every float in a nested canonical form, in order, for one approx compare."""
    if isinstance(item, tuple | list):
        return [number for part in item for number in _numbers(part)]
    return [float(item)]


def _canonical_highs(handle: Any) -> tuple[list[tuple], list[tuple]]:
    """One populated ``highspy.Highs`` as columns and rows, identified by what they say.

    Neither lane names anything it loads — ``build_highs`` sets no names and
    ``to_highspy(set_names=False)`` asks for none — so nothing here can key on a
    coordinate the way `_canonical` does. A column is therefore identified
    by its own content, ``(cost, lower, upper, integrality)``, and a row by its
    coefficients each paired with the signature of the column it multiplies.
    Both are sorted, so the comparison survives the two lanes loading the same
    model in different orders, which they do.

    That is weaker than `_canonical` exactly where two columns share a
    signature: such columns are interchangeable here and a row could name
    either. It is also the only gate on the object a solver is handed, which is
    why both exist.

    Returns:
        ``(columns, rows)`` — signatures, and ``(terms, lower, upper)`` with
        *terms* a sorted tuple of ``(coefficient, signature)``.
    """
    lp = handle.getLp()
    matrix = lp.a_matrix_
    assert 'kRowwise' in str(matrix.format_), f'a column-wise matrix needs transposing first, got {matrix.format_}'

    integrality = [int(kind) for kind in lp.integrality_] or [0] * lp.num_col_
    columns = {c: [float(lp.col_lower_[c]), float(lp.col_upper_[c])] for c in range(lp.num_col_)}

    gathered: dict[int, list] = {}
    for r in range(lp.num_row_):
        terms: dict[int, float] = {}
        for k in range(matrix.start_[r], matrix.start_[r + 1]):
            column = int(matrix.index_[k])
            terms[column] = terms.get(column, 0.0) + float(matrix.value_[k])
        gathered[r] = [terms, float(lp.row_lower_[r]), float(lp.row_upper_[r])]

    rows = _fold(columns, gathered)
    signature = {c: (float(lp.col_cost_[c]), *bounds, integrality[c]) for c, bounds in columns.items()}
    return (
        sorted(signature.values()),
        sorted(
            (tuple(sorted((coefficient, signature[c]) for c, coefficient in terms)), lower, upper)
            for terms, lower, upper in rows.values()
        ),
    )


@pytest.mark.skip(reason='mathspec has no build/solve engine yet')
@pytest.mark.parametrize('tier_name', TIER_NAMES)
def test_a_pypsa_tier_hands_highs_the_model_pypsa_hands_it(tier_name: str, tmp_path: Path, tiers):
    """The two lanes load one LP into HiGHS — the gate on the streaming core.

    The test above compares two *linopy* models, which asks whether lpspec can
    state PyPSA's model through PyPSA's own backend. This asks the question an
    integration turns on: whether the streaming core, which is what would go
    underneath PyPSA, hands a solver the same LP. `lps.build` reaches the sink
    without linopy in the path at all, so no gate above this one reads the
    matrix it writes.

    Both lanes end holding a populated ``highspy.Highs`` with ``run()`` never
    called — lpspec through ``build_highs``, PyPSA through
    ``create_model().to_highspy()`` — and this compares those two objects,
    cost, bounds, integrality, coefficients and both row bounds.

    Post-fold the row *counts* are compared here, unlike everywhere else in
    this module: once each lane's bounds sit on its columns there is nothing
    left to excuse a row the other does not have.
    """
    pytest.importorskip('pypsa', reason='needs pypsa; the bare install has none')
    from lpspec.relational.sinks.solvers.highs import build_highs

    from compat.pypsa.network import Shape, build_network

    logging.getLogger('pypsa').setLevel(logging.ERROR)
    logging.getLogger('linopy').setLevel(logging.ERROR)

    tier: Tier = tiers.TIERS[tier_name]
    shape = Shape('base')

    network = build_network(shape, tier.components)
    model = network.optimize.create_model(include_objective_constant=False)
    theirs = _canonical_highs(model.to_highspy(set_names=False))
    with lps.build(tier.model, tiers.bind(tier, shape, tmp_path)) as bound:  # noqa: F821 -- pending mathspec build API
        ours = _canonical_highs(build_highs(bound._engine._tables()))

    columns, rows = ours
    their_columns, their_rows = theirs
    assert len(columns) == len(their_columns), (
        f'{tier.name}: the two lanes load a different number of columns — '
        f'lpspec {len(columns)}, pypsa {len(their_columns)}'
    )
    assert [len(terms) for terms, _, _ in rows] == [len(terms) for terms, _, _ in their_rows], (
        f'{tier.name}: the two lanes load different rows, once every bound sits on its column — '
        f'lpspec {len(rows)} rows, pypsa {len(their_rows)}'
    )
    for part, mine, yours in (('columns', columns, their_columns), ('rows', rows, their_rows)):
        assert _numbers(mine) == pytest.approx(_numbers(yours), rel=1e-9, abs=1e-12), (
            f'{tier.name}: the two lanes hand HiGHS the same {part} and say different things in them'
        )


#: A declaration whose answer PyPSA does not keep under its own attribute: a
#: link's flow is reported at its ``bus0`` end as ``p0``, and a nodal balance's
#: shadow price as ``marginal_price``. Keyed by ``(component, attribute)`` so
#: one table serves both spellings — ``assign_solution`` and ``assign_duals``
#: are the source.
ELSEWHERE = {('Link', 'p'): 'p0', ('Bus', 'nodal_balance'): 'marginal_price'}


def _slot(name: str, join: str) -> tuple[str, str]:
    """Where PyPSA keeps *name*'s answer — its component and dynamic attribute.

    The naming rule read a third way. ``_as_pypsa`` turns a declaration into a
    linopy name; this turns either spelling into the place PyPSA's readers, its
    statistics module and its plots take the answer from, so *join* is ``_`` for
    a declaration and ``-`` for a linopy name and the same table of exceptions
    covers both directions.
    """
    component, attribute = name.split(join, 1)
    return component, ELSEWHERE.get((component, attribute), attribute)


def _priced(names: Any) -> set[str]:
    """The constraints PyPSA has a dynamic dual home for, in either spelling.

    ``assign_duals`` writes a nodal balance's dual to ``marginal_price`` and
    leaves every other row of this ladder unassigned unless a caller asks for
    ``assign_all_duals=True`` — where lpspec has nothing to put anyway, its
    bounds sitting on columns (``compat/pypsa/README.md``). ``nodal_balance``
    keeps its underscore in both spellings, so one predicate reads both.
    """
    return {name for name in names if name.endswith('nodal_balance')}


def _tidy(frame: Any) -> set[tuple]:
    """A tidy lpspec answer as the set of coordinates it carries a value at."""
    return set(frame.drop('value').rows())


def _dense(frame: Any) -> set[tuple]:
    """A PyPSA dynamic frame as the set of coordinates it has a slot at."""
    return {(snapshot, column) for snapshot in frame.index for column in frame.columns}


@pytest.mark.skip(reason='mathspec has no build/solve engine yet')
@pytest.mark.parametrize('tier_name', TIER_NAMES)
def test_a_pypsa_tier_answers_where_pypsa_reads(tier_name: str, tmp_path: Path, tiers):
    """The return trip: an answer PyPSA can read is where an integration ends.

    Every gate above this one checks the model going *in*. This one checks that
    what comes back out has a place: PyPSA fills ``n.generators_t.p``,
    ``n.links_t.p0``, ``n.storage_units_t.state_of_charge`` and
    ``n.buses_t.marginal_price`` from its own variable and row names, and an
    integration putting lpspec underneath has to land in those same frames.

    What is compared is the **mapping, both ways** — every slot PyPSA fills has
    an lpspec declaration answering it, every declaration has a slot, and the
    two agree coordinate for coordinate — and never the values. An LP with
    alternative optima has many optimal primal solutions, so the two lanes may
    legitimately sit on different vertices and a value comparison would be
    flaky about the wrong thing; ``tests/test_corpus_parity.py`` is where
    values are pinned, against recordings rather than across lanes.

    Duals reach only as far as ``marginal_price``, which is a real row in both
    lanes. ``mu_upper`` and ``mu_lower`` are out of reach by construction and
    stay a stated gap — see ``compat/pypsa/README.md``.
    """
    pytest.importorskip('pypsa', reason='needs pypsa; the bare install has none')
    from compat.pypsa.network import Shape, build_network

    logging.getLogger('pypsa').setLevel(logging.ERROR)
    logging.getLogger('linopy').setLevel(logging.ERROR)

    tier: Tier = tiers.TIERS[tier_name]
    shape = Shape('base')

    n = build_network(shape, tier.components)
    status, condition = n.optimize(solver_name='highs', include_objective_constant=False)
    assert (status, condition) == ('ok', 'optimal'), f'pypsa lane did not solve: {status}, {condition}'

    model = lps.check(tier.model)  # noqa: F821 -- pending mathspec build API
    answered = {**dict.fromkeys(model.variables, 'primal'), **dict.fromkeys(_priced(model.constraints), 'dual')}
    assert 'dual' in answered.values(), f'{tier.name}: no row matched _priced, so this gate would check no dual'

    mine = {_slot(name, '_') for name in answered}
    theirs = {_slot(name, '-') for name in (*n.model.variables, *_priced(n.model.constraints))}
    assert mine == theirs, (
        f'{tier.name}: the two lanes answer in different places — '
        f'only lpspec {sorted(mine - theirs)}, only pypsa {sorted(theirs - mine)}'
    )

    with lps.build(tier.model, tiers.bind(tier, shape, tmp_path)) as bound:  # noqa: F821 -- pending mathspec build API
        result = bound.solve()
        assert result.has_primal, f'lpspec lane left nothing to read back: {result.status}'
        readers = {'primal': result.primal, 'dual': result.dual}
        for name, quantity in answered.items():
            component, attribute = _slot(name, '_')
            dynamic = n.c[component].dynamic
            assert attribute in dynamic, (
                f'{tier.name}: pypsa keeps no {component} answer called {attribute!r}; it has {sorted(dynamic)}'
            )
            ours, slots = _tidy(readers[quantity](name)), _dense(dynamic[attribute])
            assert ours == slots, (
                f"{tier.name}: {name}'s {quantity} does not lay out over n.{component}.{attribute} — "
                f'only lpspec {sorted(ours - slots, key=repr)[:5]}, only pypsa {sorted(slots - ours, key=repr)[:5]}'
            )
