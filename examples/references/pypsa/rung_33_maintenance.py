# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 33: maintenance — a fixed and an extendable generator, link and process, each taken off for events that the generator weightings time."""

from __future__ import annotations

import spine


def build():
    """The spine plus an east bus and six maintainable components, fixed and extendable, with a dear peaker to cover them."""
    n = spine.build()
    n.add('Bus', 'east')
    n.add('Generator', 'hydro', bus='north', p_nom=50, marginal_cost=2, maintainable=True, maintenance_duration=3)
    n.add(
        'Generator',
        'wind_ext',
        bus='south',
        p_nom_extendable=True,
        p_nom_min=10,
        p_nom_max=60,
        capital_cost=20,
        marginal_cost=1,
        p_max_pu=[0.9, 0.6, 0.8, 0.7],
        maintainable=True,
        maintenance_duration=2,
        maintenance_pu=0.5,
    )
    n.add(
        'Link',
        'tie_fix',
        bus0='north',
        bus1='east',
        p_nom=30,
        efficiency=0.95,
        maintainable=True,
        maintenance_duration=1,
        maintenance_events=2,
    )
    n.add(
        'Link',
        'tie_ext',
        bus0='south',
        bus1='east',
        p_nom_extendable=True,
        p_nom_min=5,
        p_nom_max=40,
        capital_cost=4,
        efficiency=0.9,
        p_min_pu=-1,
        maintainable=True,
        maintenance_duration=3,
    )
    n.add(
        'Process',
        'conv_fix',
        bus0='north',
        bus1='east',
        rate0=-1.25,
        p_nom=25,
        maintainable=True,
        maintenance_duration=3,
        maintenance_pu=0.6,
    )
    n.add(
        'Process',
        'conv_ext',
        bus0='south',
        bus1='east',
        rate0=-1.25,
        p_nom_extendable=True,
        p_nom_min=5,
        p_nom_max=30,
        capital_cost=3,
        maintainable=True,
        maintenance_duration=1,
    )
    n.add('Generator', 'east_peak', bus='east', p_nom=100, marginal_cost=60)
    n.add('Load', 'east_load', bus='east', p_set=[50, 60, 40, 55])
    return n
