# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The prep layer: a PyPSA network as the tables the example models bind.

Every parameter the files mark "data prep" is computed here, beside the plain
renames. `parity.py` is the caller and cuts the tables to what each model
declares; nothing here imports math_spec or lpspec — the mapping is pure
PyPSA-and-pandas, handed over as polars frames.

Sparseness is meaning: a table row left out is an absent value on the other
side, so the sparse tables here (`*_set` pins, ramp limits, weights) drop
their empty rows instead of shipping fills.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
import polars as pl
from pypsa.descriptors import get_switchable_as_dense

if TYPE_CHECKING:
    import pypsa


def _static(component: pd.DataFrame, attr: str, dim: str, *, sparse: bool = False) -> pd.DataFrame:
    table = pd.DataFrame({dim: component.index.astype(str), 'value': component[attr].to_numpy()})
    return table.dropna() if sparse else table


def _melt(dense: pd.DataFrame, dim: str) -> pd.DataFrame:
    table = dense.melt(ignore_index=False, var_name=dim).reset_index(names='snapshot')
    return table.astype({dim: str, 'value': float})


def _varying(n: pypsa.Network, component: str, attr: str, dim: str, *, sparse: bool = False) -> pd.DataFrame:
    table = _melt(get_switchable_as_dense(n, component, attr), dim)
    return table.dropna() if sparse else table


def _lookup(component: pd.DataFrame, attr: str, over: str, into: str) -> pd.DataFrame:
    table = pd.DataFrame({over: component.index.astype(str), into: component[attr].astype(str)})
    return table[table[into] != '']


def _weighting(n: pypsa.Network, column: str) -> pd.DataFrame:
    return pd.DataFrame({'snapshot': n.snapshots, 'value': n.snapshot_weightings[column].to_numpy()})


def _retention(n: pypsa.Network, component: str, dim: str) -> pd.DataFrame:
    losses = n.static(component)['standing_loss']
    hours = n.snapshot_weightings['stores']
    return _melt(pd.DataFrame({name: (1.0 - loss) ** hours for name, loss in losses.items()}, index=n.snapshots), dim)


def _cycle_weights(n: pypsa.Network) -> pd.DataFrame:
    """The KVL basis PyPSA itself solves with: ``sub_network.C``, scaled by effective reactance."""
    n.determine_network_topology()
    n.calculate_dependent_values()
    rows = []
    for sub in n.sub_networks.obj:
        cycles = sub.C.todense()
        branches = sub.branches()
        for c in range(cycles.shape[1]):
            for b, (kind, name) in enumerate(branches.index):
                if kind == 'Line' and cycles[b, c]:
                    weight = float(cycles[b, c]) * float(n.lines.at[name, 'x_pu_eff'])
                    rows.append({'line': str(name), 'cycle': f'{sub.name}-c{c}', 'value': weight})
    return pd.DataFrame(rows, columns=['line', 'cycle', 'value']).astype({'value': float})


def _primary_energy_weights(n: pypsa.Network) -> pd.DataFrame:
    """Tonnes of the constrained attribute per unit of bus energy, per row and generator."""
    rows = []
    for label, gc in n.global_constraints.iterrows():
        if gc['type'] != 'primary_energy':
            continue
        emissions = n.carriers[gc['carrier_attribute']]
        for name, generator in n.generators.iterrows():
            weight = emissions.get(generator['carrier'], 0.0)
            if weight:
                rows.append(
                    {'global_constraint': str(label), 'generator': str(name), 'value': weight / generator['efficiency']}
                )
    return pd.DataFrame(rows, columns=['global_constraint', 'generator', 'value']).astype({'value': float})


def _must_stay_up(n: pypsa.Network) -> pd.DataFrame:
    """True while the up time a unit brought into the horizon still binds."""
    rows = []
    for name, g in n.generators.iterrows():
        if not g['committable'] or g['up_time_before'] <= 0:
            continue
        remaining = int(min(g['min_up_time'] - g['up_time_before'], len(n.snapshots)))
        rows.extend({'snapshot': t, 'generator': str(name), 'value': True} for t in n.snapshots[: max(remaining, 0)])
    table = pd.DataFrame(rows, columns=['snapshot', 'generator', 'value'])
    return table.astype({'value': bool})


def sources(n: pypsa.Network) -> dict[str, object]:
    """Every table the example models bind, from one PyPSA network."""
    generators, links, loads = n.generators, n.links, n.loads
    storage_units, stores, lines = n.storage_units, n.stores, n.lines
    committable_ext = generators['committable'] & generators['p_nom_extendable']
    big_m = generators['p_nom_max'] * get_switchable_as_dense(n, 'Generator', 'p_max_pu').max().clip(lower=1.0)

    tables: dict[str, object] = {
        'snapshot': pl.Series('snapshot', list(n.snapshots), dtype=pl.Int64),
        'bus': pl.Series('bus', list(n.buses.index.astype(str)), dtype=pl.String),
        'generator': pl.Series('generator', list(generators.index.astype(str)), dtype=pl.String),
        'link': pl.Series('link', list(links.index.astype(str)), dtype=pl.String),
        'load': pl.Series('load', list(loads.index.astype(str)), dtype=pl.String),
        'storage_unit': pl.Series('storage_unit', list(storage_units.index.astype(str)), dtype=pl.String),
        'store': pl.Series('store', list(stores.index.astype(str)), dtype=pl.String),
        'line': pl.Series('line', list(lines.index.astype(str)), dtype=pl.String),
        'global_constraint': pl.Series(
            'global_constraint', list(n.global_constraints.index.astype(str)), dtype=pl.String
        ),
        'Generator_bus': _lookup(generators, 'bus', 'generator', 'bus'),
        'Link_bus0': _lookup(links, 'bus0', 'link', 'bus'),
        'Link_bus1': _lookup(links, 'bus1', 'link', 'bus'),
        'Load_bus': _lookup(loads, 'bus', 'load', 'bus'),
        'StorageUnit_bus': _lookup(storage_units, 'bus', 'storage_unit', 'bus'),
        'Store_bus': _lookup(stores, 'bus', 'store', 'bus'),
        'Line_bus0': _lookup(lines, 'bus0', 'line', 'bus'),
        'Line_bus1': _lookup(lines, 'bus1', 'line', 'bus'),
        'snapshot_weightings_objective': _weighting(n, 'objective'),
        'snapshot_weightings_stores': _weighting(n, 'stores'),
        'snapshot_weightings_generators': _weighting(n, 'generators'),
        'Load_p_set': _varying(n, 'Load', 'p_set', 'load'),
        'Generator_p_nom': _static(generators, 'p_nom', 'generator'),
        'Generator_p_nom_extendable': _static(generators, 'p_nom_extendable', 'generator'),
        'Generator_p_min_pu': _varying(n, 'Generator', 'p_min_pu', 'generator'),
        'Generator_p_max_pu': _varying(n, 'Generator', 'p_max_pu', 'generator'),
        'Generator_marginal_cost': _varying(n, 'Generator', 'marginal_cost', 'generator'),
        'Generator_p_set': _varying(n, 'Generator', 'p_set', 'generator', sparse=True),
        'Generator_p_nom_min': _static(generators, 'p_nom_min', 'generator'),
        'Generator_p_nom_max': _static(generators, 'p_nom_max', 'generator'),
        'Generator_capital_cost': _static(generators, 'capital_cost', 'generator'),
        'Generator_p_nom_set': _static(generators, 'p_nom_set', 'generator', sparse=True),
        'Generator_e_sum_min': _static(generators, 'e_sum_min', 'generator'),
        'Generator_e_sum_max': _static(generators, 'e_sum_max', 'generator'),
        'Generator_committable': _static(generators, 'committable', 'generator'),
        'Generator_ramp_limit_up': _static(generators, 'ramp_limit_up', 'generator', sparse=True),
        'Generator_ramp_limit_down': _static(generators, 'ramp_limit_down', 'generator', sparse=True),
        'Generator_ramp_limit_start_up': _static(
            generators.fillna({'ramp_limit_start_up': 1.0}), 'ramp_limit_start_up', 'generator'
        ),
        'Generator_ramp_limit_shut_down': _static(
            generators.fillna({'ramp_limit_shut_down': 1.0}), 'ramp_limit_shut_down', 'generator'
        ),
        'Generator_min_up_time': _static(generators, 'min_up_time', 'generator'),
        'Generator_min_down_time': _static(generators, 'min_down_time', 'generator'),
        'Generator_status_initial': pd.DataFrame(
            {
                'generator': generators.index.astype(str),
                'value': (generators['up_time_before'] > 0).astype(int).to_numpy(),
            }
        ),
        'Generator_must_stay_up': _must_stay_up(n),
        'Generator_start_up_cost': _static(generators, 'start_up_cost', 'generator'),
        'Generator_shut_down_cost': _static(generators, 'shut_down_cost', 'generator'),
        'Generator_stand_by_cost': _varying(n, 'Generator', 'stand_by_cost', 'generator'),
        'Generator_p_nom_mod': _static(generators[generators['p_nom_mod'] > 0], 'p_nom_mod', 'generator'),
        'Generator_big_m': pd.DataFrame({'generator': generators.index.astype(str), 'value': big_m.to_numpy()}),
        'Generator_p_min_pu_nonneg': bool(
            (get_switchable_as_dense(n, 'Generator', 'p_min_pu').loc[:, committable_ext] >= 0).all().all()
        ),
        'Link_p_nom': _static(links, 'p_nom', 'link'),
        'Link_p_nom_extendable': _static(links, 'p_nom_extendable', 'link'),
        'Link_p_min_pu': _varying(n, 'Link', 'p_min_pu', 'link'),
        'Link_p_max_pu': _varying(n, 'Link', 'p_max_pu', 'link'),
        'Link_efficiency': _static(links, 'efficiency', 'link'),
        'Link_marginal_cost': _varying(n, 'Link', 'marginal_cost', 'link'),
        'Link_p_set': _varying(n, 'Link', 'p_set', 'link', sparse=True),
        'Link_p_nom_min': _static(links, 'p_nom_min', 'link'),
        'Link_p_nom_max': _static(links, 'p_nom_max', 'link'),
        'Link_capital_cost': _static(links, 'capital_cost', 'link'),
        'Link_p_nom_set': _static(links, 'p_nom_set', 'link', sparse=True),
        'Link_ramp_limit_up': _static(links, 'ramp_limit_up', 'link', sparse=True),
        'Link_ramp_limit_down': _static(links, 'ramp_limit_down', 'link', sparse=True),
        'StorageUnit_p_nom': _static(storage_units, 'p_nom', 'storage_unit'),
        'StorageUnit_p_nom_extendable': _static(storage_units, 'p_nom_extendable', 'storage_unit'),
        'StorageUnit_p_min_pu': _varying(n, 'StorageUnit', 'p_min_pu', 'storage_unit'),
        'StorageUnit_p_max_pu': _varying(n, 'StorageUnit', 'p_max_pu', 'storage_unit'),
        'StorageUnit_max_hours': _static(storage_units, 'max_hours', 'storage_unit'),
        'StorageUnit_efficiency_store': _static(storage_units, 'efficiency_store', 'storage_unit'),
        'StorageUnit_efficiency_dispatch': _static(storage_units, 'efficiency_dispatch', 'storage_unit'),
        'StorageUnit_retention': _retention(n, 'StorageUnit', 'storage_unit'),
        'StorageUnit_inflow': _varying(n, 'StorageUnit', 'inflow', 'storage_unit'),
        'StorageUnit_state_of_charge_initial': _static(storage_units, 'state_of_charge_initial', 'storage_unit'),
        'StorageUnit_cyclic_state_of_charge': _static(storage_units, 'cyclic_state_of_charge', 'storage_unit'),
        'StorageUnit_marginal_cost': _varying(n, 'StorageUnit', 'marginal_cost', 'storage_unit'),
        'StorageUnit_marginal_cost_storage': _varying(n, 'StorageUnit', 'marginal_cost_storage', 'storage_unit'),
        'StorageUnit_spill_cost': _varying(n, 'StorageUnit', 'spill_cost', 'storage_unit'),
        'StorageUnit_p_set': _varying(n, 'StorageUnit', 'p_set', 'storage_unit', sparse=True),
        'StorageUnit_state_of_charge_set': _varying(
            n, 'StorageUnit', 'state_of_charge_set', 'storage_unit', sparse=True
        ),
        'StorageUnit_p_nom_min': _static(storage_units, 'p_nom_min', 'storage_unit'),
        'StorageUnit_p_nom_max': _static(storage_units, 'p_nom_max', 'storage_unit'),
        'StorageUnit_capital_cost': _static(storage_units, 'capital_cost', 'storage_unit'),
        'StorageUnit_p_nom_set': _static(storage_units, 'p_nom_set', 'storage_unit', sparse=True),
        'Store_e_nom': _static(stores, 'e_nom', 'store'),
        'Store_e_nom_extendable': _static(stores, 'e_nom_extendable', 'store'),
        'Store_e_min_pu': _varying(n, 'Store', 'e_min_pu', 'store'),
        'Store_e_max_pu': _varying(n, 'Store', 'e_max_pu', 'store'),
        'Store_retention': _retention(n, 'Store', 'store'),
        'Store_e_initial': _static(stores, 'e_initial', 'store'),
        'Store_e_cyclic': _static(stores, 'e_cyclic', 'store'),
        'Store_marginal_cost': _varying(n, 'Store', 'marginal_cost', 'store'),
        'Store_marginal_cost_storage': _varying(n, 'Store', 'marginal_cost_storage', 'store'),
        'Store_e_set': _varying(n, 'Store', 'e_set', 'store', sparse=True),
        'Store_e_nom_min': _static(stores, 'e_nom_min', 'store'),
        'Store_e_nom_max': _static(stores, 'e_nom_max', 'store'),
        'Store_capital_cost': _static(stores, 'capital_cost', 'store'),
        'Store_e_nom_set': _static(stores, 'e_nom_set', 'store', sparse=True),
        'Line_s_nom': _static(lines, 's_nom', 'line'),
        'Line_s_nom_extendable': _static(lines, 's_nom_extendable', 'line'),
        'Line_s_max_pu': _varying(n, 'Line', 's_max_pu', 'line'),
        'Line_s_nom_min': _static(lines, 's_nom_min', 'line'),
        'Line_s_nom_max': _static(lines, 's_nom_max', 'line'),
        'Line_capital_cost': _static(lines, 'capital_cost', 'line'),
        'Line_s_nom_set': _static(lines, 's_nom_set', 'line', sparse=True),
        'Line_s_set': _varying(n, 'Line', 's_set', 'line', sparse=True),
        'Line_cycle_weight': _cycle_weights(n),
        'GlobalConstraint_type': _static(n.global_constraints, 'type', 'global_constraint').astype({'value': str}),
        'GlobalConstraint_sense': _static(n.global_constraints, 'sense', 'global_constraint').astype({'value': str}),
        'GlobalConstraint_constant': _static(n.global_constraints, 'constant', 'global_constraint').astype(
            {'value': float}
        ),
        'snapshot_is_last': pd.DataFrame(
            {'snapshot': n.snapshots, 'value': [0] * (len(n.snapshots) - 1) + [1] if len(n.snapshots) else []}
        ),
        'Generator_primary_energy_weight': _primary_energy_weights(n),
        'Generator_marginal_cost_quadratic': _varying(n, 'Generator', 'marginal_cost_quadratic', 'generator'),
        'Link_marginal_cost_quadratic': _varying(n, 'Link', 'marginal_cost_quadratic', 'link'),
    }

    tables['cycle'] = pl.Series('cycle', list(pd.unique(tables['Line_cycle_weight']['cycle'])), dtype=pl.String)
    if 'bus2' not in links.columns:
        links = links.assign(bus2='', efficiency2=1.0)
    tables['Link_bus2'] = _lookup(links, 'bus2', 'link', 'bus')
    tables['Link_efficiency2'] = _static(links[links['bus2'] != ''], 'efficiency2', 'link')

    for name, dim in [
        ('StorageUnit_primary_energy_weight', 'storage_unit'),
        ('Store_primary_energy_weight', 'store'),
        ('Generator_operational_limit_weight', 'generator'),
        ('StorageUnit_operational_limit_weight', 'storage_unit'),
        ('Store_operational_limit_weight', 'store'),
        ('Line_volume_weight', 'line'),
        ('Link_volume_weight', 'link'),
        ('Line_expansion_cost_weight', 'line'),
        ('Link_expansion_cost_weight', 'link'),
        ('Generator_tech_capacity_weight', 'generator'),
        ('Link_tech_capacity_weight', 'link'),
        ('StorageUnit_tech_capacity_weight', 'storage_unit'),
        ('Store_tech_capacity_weight', 'store'),
    ]:
        tables[name] = pl.DataFrame(schema={'global_constraint': pl.String, dim: pl.String, 'value': pl.Float64})

    for name, table in tables.items():
        if isinstance(table, pd.DataFrame):
            lost = {
                column: 'int64' if column == 'snapshot' else 'string'
                for column in table.columns
                if table[column].dtype == object
            }
            tables[name] = pl.from_pandas(table.astype(lost))
    return tables
