# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 60: efficiencies per snapshot — a link, a process, a storage unit, a fuel unit under a primary-energy cap and a transformer with a fixed phase shift, each reading its coefficient per snapshot."""

from __future__ import annotations

from datetime import datetime

#: Four hourly stamps. The `generators` weighting is uniform, as rung 16's, so a
#: `delay` of one is a shift of one snapshot position. The `objective` and
#: `stores` columns stay non-uniform, so no cost or storage factor passes as identity.
SNAPSHOTS = [datetime(2015, 1, 1, hour) for hour in range(4)]
WEIGHTINGS = {'objective': [2.0, 1.5, 2.5, 3.0], 'stores': [0.5, 2.0, 1.5, 2.5], 'generators': [1.0, 1.0, 1.0, 1.0]}

LINK_EFFICIENCY = [2.0, 3.5, 2.5, 3.0]
PROCESS_RATE = [0.9, 0.5, 0.8, 0.6]
EFFICIENCY_STORE = [0.9, 0.5, 0.9, 0.5]
EFFICIENCY_DISPATCH = [0.6, 0.9, 0.7, 0.95]
FUEL_EFFICIENCY = [0.3, 0.6, 0.4, 0.5]
PHASE_SHIFT = [0.0, 0.5, -0.3, 1.0]


def build():
    """A source feeding a sink over a delayed link and a delayed process, a storage unit and a capped fuel unit at the sink, and a triangle with a fixed phase shift per snapshot."""
    import pypsa

    n = pypsa.Network()
    n.set_snapshots(SNAPSHOTS)
    for column, values in WEIGHTINGS.items():
        n.snapshot_weightings[column] = values
    n.add('Carrier', 'fuel60', co2_emissions=1.0)
    n.add('Bus', ['source', 'sink'])
    n.add('Generator', 'spring60', bus='source', p_nom=200, marginal_cost=5)
    n.add('Generator', 'backup60', bus='sink', p_nom=200, marginal_cost=100)
    n.add(
        'Generator', 'fuel_unit60', bus='sink', carrier='fuel60', p_nom=40, marginal_cost=20, efficiency=FUEL_EFFICIENCY
    )
    n.add('Link', 'heat_pump60', bus0='source', bus1='sink', p_nom=10, efficiency=LINK_EFFICIENCY, delay=1)
    n.add('Process', 'boiler60', bus0='source', bus1='sink', p_nom=20, rate1=PROCESS_RATE, delay1=1)
    n.add(
        'StorageUnit',
        'battery60',
        bus='sink',
        p_nom=20,
        max_hours=2,
        cyclic_state_of_charge=True,
        efficiency_store=EFFICIENCY_STORE,
        efficiency_dispatch=EFFICIENCY_DISPATCH,
    )
    n.add('Load', 'sink_load60', bus='sink', p_set=[60.0, 90.0, 50.0, 100.0])
    n.add(
        'GlobalConstraint',
        'fuel_cap60',
        type='primary_energy',
        carrier_attribute='co2_emissions',
        sense='<=',
        constant=150,
    )
    n.add('Bus', ['a', 'b', 'c'])
    n.add('Generator', 'hydro60', bus='a', p_nom=300, marginal_cost=10)
    n.add('Generator', 'diesel60', bus='c', p_nom=300, marginal_cost=200)
    n.add('Load', 'town60', bus='c', p_set=[90.0, 75.0, 120.0, 105.0])
    n.add('Line', 'ab60', bus0='a', bus1='b', carrier='AC', x=0.002, r=0.0002, s_nom=120)
    n.add('Line', 'bc60', bus0='b', bus1='c', carrier='AC', x=0.002, r=0.0002, s_nom=120)
    n.add('Transformer', 'ca60', bus0='c', bus1='a', x=0.002, r=0.0002, s_nom=40, phase_shift=PHASE_SHIFT)
    return n
