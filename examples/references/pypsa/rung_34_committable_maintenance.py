# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 34: maintenance of committable units — a fixed, an extendable and a modular committable generator, link and process, each taken off for one event."""

from __future__ import annotations

import spine


def build():
    """The spine plus an east bus and nine maintainable committable components, with a dear peaker to cover them."""
    n = spine.build()
    n.add('Bus', 'east')
    committable = {'committable': True, 'maintainable': True}
    n.add(
        'Generator',
        'unit',
        bus='north',
        p_nom=60,
        p_min_pu=0.3,
        marginal_cost=5,
        start_up_cost=10,
        maintenance_duration=2,
        **committable,
    )
    n.add(
        'Generator',
        'unit_ext',
        bus='south',
        p_nom_extendable=True,
        p_nom_min=5,
        p_nom_max=50,
        capital_cost=10,
        p_min_pu=0.2,
        marginal_cost=4,
        maintenance_duration=3,
        maintenance_pu=0.5,
        **committable,
    )
    n.add(
        'Generator',
        'unit_mod',
        bus='south',
        p_nom_extendable=True,
        p_nom_mod=10,
        p_nom_max=30,
        capital_cost=8,
        p_min_pu=0.5,
        marginal_cost=3,
        maintenance_duration=1,
        **committable,
    )
    for component, ports in (('Link', {}), ('Process', {'rate0': -1.25})):
        n.add(
            component,
            f'{component.lower()}_unit',
            bus0='north',
            bus1='east',
            p_nom=40,
            p_min_pu=0.2,
            marginal_cost=1,
            maintenance_duration=2,
            **ports,
            **committable,
        )
        n.add(
            component,
            f'{component.lower()}_ext',
            bus0='south',
            bus1='east',
            p_nom_extendable=True,
            p_nom_min=5,
            p_nom_max=30,
            capital_cost=5,
            p_min_pu=0.2,
            maintenance_duration=3,
            maintenance_pu=0.5,
            **ports,
            **committable,
        )
        n.add(
            component,
            f'{component.lower()}_mod',
            bus0='north',
            bus1='east',
            p_nom_extendable=True,
            p_nom_mod=10,
            p_nom_max=20,
            capital_cost=3,
            p_min_pu=0.5,
            maintenance_duration=1,
            **ports,
            **committable,
        )
    n.add('Generator', 'east_peak', bus='east', p_nom=100, marginal_cost=60)
    n.add('Load', 'east_load', bus='east', p_set=[50, 60, 40, 55])
    return n
