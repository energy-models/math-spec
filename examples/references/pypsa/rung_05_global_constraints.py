"""Rung 5: global constraints — one row per limit type and sense."""

from __future__ import annotations

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Carrier', 'coalc', co2_emissions=0.9)
    n.add('Carrier', 'gasc', co2_emissions=0.4)
    n.add('Carrier', 'windc')
    n.add('Generator', 'coal5', bus='north', carrier='coalc', p_nom=60, marginal_cost=9, efficiency=0.35)
    n.add('Generator', 'gas5', bus='north', carrier='gasc', p_nom=60, marginal_cost=25, efficiency=0.5)
    n.add('Generator', 'wind5', bus='north', carrier='windc', p_nom=60, marginal_cost=40)
    n.add('Load', 'extra5', bus='north', p_set=50)
    n.add('StorageUnit', 'res5', bus='north', carrier='gasc', p_nom=20, max_hours=4, state_of_charge_initial=30)
    n.add('Store', 'tank5', bus='north', carrier='coalc', e_nom=40, e_initial=25)
    n.add(
        'GlobalConstraint',
        'co2_cap',
        type='primary_energy',
        carrier_attribute='co2_emissions',
        sense='<=',
        constant=150,
    )
    n.add(
        'GlobalConstraint',
        'co2_floor',
        type='primary_energy',
        carrier_attribute='co2_emissions',
        sense='>=',
        constant=20,
    )
    n.add(
        'GlobalConstraint',
        'co2_exact',
        type='primary_energy',
        carrier_attribute='co2_emissions',
        sense='==',
        constant=120,
    )
    n.add('GlobalConstraint', 'op_wind', type='operational_limit', carrier_attribute='windc', sense='==', constant=30)
    n.add('GlobalConstraint', 'op_coal', type='operational_limit', carrier_attribute='coalc', sense='<=', constant=200)
    n.add('GlobalConstraint', 'op_gas', type='operational_limit', carrier_attribute='gasc', sense='>=', constant=10)
    return n
