"""Rung 3: expansion — extendable capacity, energy-sum bounds, fixed and set nominal capacities."""

from __future__ import annotations

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', 'island')
    n.add('Carrier', 'onwind')
    n.add('Carrier', 'solarpv')
    n.add('Carrier', 'dc')
    n.add('Carrier', 'phs')
    n.add('Carrier', 'h2')
    n.add(
        'Generator',
        'wind',
        bus='north',
        carrier='onwind',
        p_nom_extendable=True,
        capital_cost=50,
        p_nom_min=5,
        p_nom_max=80,
        marginal_cost=0,
        e_sum_min=40,
        ramp_limit_up=0.4,
        ramp_limit_down=0.4,
        p_max_pu=[0.3, 0.8, 0.5, 0.9],
    )
    n.add(
        'Generator',
        'solar',
        bus='north',
        carrier='solarpv',
        p_nom_extendable=True,
        capital_cost=60,
        p_nom_max=40,
        marginal_cost=0,
        p_nom_set=15,
        p_max_pu=[0.5, 0.6, 0.4, 0.2],
    )
    n.add('Generator', 'diesel', bus='island', marginal_cost=40, p_nom=60, e_sum_max=70)
    n.add(
        'Link',
        'cable',
        bus0='north',
        bus1='island',
        carrier='dc',
        length=120,
        p_nom_extendable=True,
        capital_cost=20,
        p_nom_max=30,
        efficiency=0.95,
        p_nom_set=25,
        ramp_limit_up=0.3,
        ramp_limit_down=0.3,
    )
    n.add('Load', 'island_load', bus='island', p_set=10)
    n.add(
        'StorageUnit',
        'pump',
        bus='north',
        carrier='phs',
        p_nom_extendable=True,
        capital_cost=15,
        p_nom_max=30,
        max_hours=4,
        efficiency_store=0.9,
        efficiency_dispatch=0.9,
        cyclic_state_of_charge=True,
        p_nom_set=20,
    )
    n.add('StorageUnit', 'ice', bus='island', max_hours=2, p_nom=8, state_of_charge_initial=6)
    n.add(
        'Store',
        'tank',
        bus='north',
        carrier='h2',
        e_nom_extendable=True,
        capital_cost=2,
        e_nom_max=80,
        e_cyclic=True,
        e_nom_set=50,
    )
    n.add('Store', 'keg', bus='island', e_nom=15, e_initial=5)
    n.add(
        'GlobalConstraint',
        'tech_wind',
        type='tech_capacity_expansion_limit',
        carrier_attribute='onwind',
        sense='==',
        constant=50,
    )
    n.add(
        'GlobalConstraint',
        'tech_solar',
        type='tech_capacity_expansion_limit',
        carrier_attribute='solarpv',
        sense='>=',
        constant=10,
    )
    n.add(
        'GlobalConstraint',
        'tech_dc',
        type='tech_capacity_expansion_limit',
        carrier_attribute='dc',
        sense='<=',
        constant=28,
    )
    n.add(
        'GlobalConstraint',
        'tech_phs',
        type='tech_capacity_expansion_limit',
        carrier_attribute='phs',
        sense='<=',
        constant=25,
    )
    n.add(
        'GlobalConstraint',
        'tech_h2',
        type='tech_capacity_expansion_limit',
        carrier_attribute='h2',
        sense='>=',
        constant=30,
    )
    n.add(
        'GlobalConstraint',
        'vol_dc',
        type='transmission_volume_expansion_limit',
        carrier_attribute='dc',
        sense='<=',
        constant=3500,
    )
    n.add(
        'GlobalConstraint',
        'cost_dc',
        type='transmission_expansion_cost_limit',
        carrier_attribute='dc',
        sense='>=',
        constant=400,
    )
    n.add(
        'GlobalConstraint',
        'cost_dc_exact',
        type='transmission_expansion_cost_limit',
        carrier_attribute='dc',
        sense='==',
        constant=500,
    )
    return n
