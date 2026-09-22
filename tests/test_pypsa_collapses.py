# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""`examples/pypsa.yaml` is the superset that collapses to the standard PyPSA model.

The file always declares a `scenario` axis, a mask-only `period` axis, a `carrier`
axis and the CVaR rows. Fed one scenario, one period, all-active masks and unit
weights, every addition is a no-op and the standard model returns. The repository
runs no solver, so the reduction is guarded structurally: `tests/fixtures/
pypsa_standard_shape.yaml` freezes the standard model's names and frames, and the
only frame change a standard row may carry is a leading `scenario`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from math_spec import to_spec
from math_spec._yaml import read_yaml
from tests.fixtures import EXAMPLES

STANDARD = read_yaml(Path(__file__).resolve().parent / 'fixtures' / 'pypsa_standard_shape.yaml')
ALL = to_spec(str(EXAMPLES / 'pypsa.yaml'))

#: capacity is chosen once, before the future is known, so it spans no scenario
SCENARIO_FREE_VARIABLES = {
    'Generator_n_mod',
    'Generator_p_nom_ext',
    'Link_p_nom_ext',
    'StorageUnit_p_nom_ext',
    'Store_e_nom_ext',
    'Line_s_nom_ext',
}


def _dims(block: Any) -> list[str]:
    return list(block.dims or [])


def test_every_standard_name_survives():
    sections = {
        'parameters': ALL.parameters,
        'relations': ALL.relations,
        'variables': ALL.variables,
        'expressions': ALL.expressions,
        'constraints': ALL.constraints,
    }
    dropped = {
        f'{section}.{name}' for section, present in sections.items() for name in set(STANDARD[section]) - set(present)
    }
    assert not dropped, f'the unified file lost {sorted(dropped)} — it must keep every standard name'


def test_a_variable_gains_scenario_only_when_it_is_second_stage():
    wrong = {
        name: _dims(ALL.variables[name])
        for name, dims in STANDARD['variables'].items()
        if _dims(ALL.variables[name]) != (dims if name in SCENARIO_FREE_VARIABLES else ['scenario', *dims])
    }
    assert not wrong, f'these variables carry the wrong frame: {wrong}'


def test_a_standard_constraint_changes_frame_only_by_a_leading_scenario():
    wrong = {
        name: _dims(ALL.constraints[name])
        for name, dims in STANDARD['constraints'].items()
        if _dims(ALL.constraints[name]) not in (dims, ['scenario', *dims])
    }
    assert not wrong, f'a standard row may gain only a leading scenario; these differ: {wrong}'


def test_only_load_carries_scenario_among_standard_parameters():
    wrong = {
        name: _dims(ALL.parameters[name])
        for name, dims in STANDARD['parameters'].items()
        if _dims(ALL.parameters[name]) != (['scenario', *dims] if name == 'Load_p_set' else dims)
    }
    assert not wrong, f'only Load_p_set gains scenario; these differ: {wrong}'


def test_the_extra_axes_and_rows_are_declared():
    assert {'scenario', 'period', 'carrier'} <= set(ALL.dimensions), 'the three extra axes are declared'
    assert {'CVaR_a', 'CVaR_theta', 'CVaR'} <= set(ALL.variables), 'the CVaR variables are declared'
    assert {'CVaR_excess', 'CVaR_def', 'Carrier_growth_limit'} <= set(ALL.constraints), (
        'the CVaR rows and the carrier growth limit are declared'
    )
    assert 'scenario_opex' in ALL.expressions, 'the per-scenario operating cost is a named expression'


def test_omega_blends_expectation_and_tail_in_the_objective():
    expr = ALL.objective.expression
    assert all(term in expr for term in ('CVaR_omega', 'scenario_weight', 'scenario_opex', 'CVaR')), (
        'the objective prices expected opex by scenario weight and blends the tail by omega'
    )
