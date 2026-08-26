"""Rung 6: KVL — passive lines under Kirchhoff's voltage law."""

from __future__ import annotations

from math import nan

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', 'a')
    n.add('Bus', 'b')
    n.add('Bus', 'c')
    n.add('Generator', 'hydro', bus='a', p_nom=80, marginal_cost=10)
    n.add('Generator', 'diesel6', bus='b', p_nom=80, marginal_cost=50)
    n.add('Load', 'town', bus='c', p_set=45)
    n.add('Line', 'ab', bus0='a', bus1='b', carrier='AC', length=30, x=0.1, r=0.01, s_nom=60)
    n.add('Line', 'bc', bus0='b', bus1='c', carrier='AC', length=40, x=0.2, r=0.01, s_nom=60, s_set=[16, nan, nan, nan])
    n.add('Line', 'ca', bus0='c', bus1='a', carrier='AC', length=35, x=0.1, r=0.01, s_nom=60)
    n.add(
        'Line',
        'ca2',
        bus0='c',
        bus1='a',
        carrier='AC',
        length=50,
        x=0.15,
        r=0.01,
        s_nom_extendable=True,
        capital_cost=10,
        s_nom_max=40,
        s_nom_set=30,
    )
    n.add(
        'Line',
        'ca3',
        bus0='c',
        bus1='a',
        carrier='AC',
        length=80,
        x=0.12,
        r=0.01,
        s_nom_extendable=True,
        capital_cost=8,
        s_nom_max=40,
    )
    n.add(
        'GlobalConstraint',
        'vol_ac',
        type='transmission_volume_expansion_limit',
        carrier_attribute='AC',
        sense='==',
        constant=2300,
    )
    n.add(
        'GlobalConstraint',
        'vol_ac_floor',
        type='transmission_volume_expansion_limit',
        carrier_attribute='AC',
        sense='>=',
        constant=1000,
    )
    n.add(
        'GlobalConstraint',
        'cost_ac',
        type='transmission_expansion_cost_limit',
        carrier_attribute='AC',
        sense='<=',
        constant=500,
    )
    n.add(
        'GlobalConstraint',
        'cost_ac_floor',
        type='transmission_expansion_cost_limit',
        carrier_attribute='AC',
        sense='>=',
        constant=100,
    )
    n.add(
        'GlobalConstraint',
        'tech_ac',
        type='tech_capacity_expansion_limit',
        carrier_attribute='AC',
        sense='<=',
        constant=60,
    )
    return n
