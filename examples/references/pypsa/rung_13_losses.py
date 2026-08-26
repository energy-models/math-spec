# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 13: transmission losses in tangent form — a loss per line, stated by `pypsa_losses.yaml`."""

from __future__ import annotations

import spine

MODEL = 'pypsa_losses.yaml'
OPTIMIZE = {'transmission_losses': {'mode': 'tangents', 'segments': 2}}


def build():
    """The spine plus a lossy triangle of lines, one of them extendable; resistances small enough at 1 kV to keep the loss below the flow."""
    n = spine.build()
    n.add('Bus', ['a', 'b', 'c'])
    n.add('Generator', 'hydro13', bus='a', p_nom=80, marginal_cost=10)
    n.add('Generator', 'diesel13', bus='b', p_nom=80, marginal_cost=50)
    n.add('Line', 'ab13', bus0='a', bus1='b', carrier='AC', x=0.1, r=0.0005, s_nom=60)
    n.add('Line', 'bc13', bus0='b', bus1='c', carrier='AC', x=0.2, r=0.0008, s_nom=60)
    n.add(
        'Line',
        'ca13',
        bus0='c',
        bus1='a',
        carrier='AC',
        x=0.15,
        r=0.0005,
        s_nom=40,
        s_nom_extendable=True,
        s_nom_max=90,
        capital_cost=4,
    )
    n.add('Load', 'town13', bus='c', p_set=[35, 55, 15, 45])
    return n
