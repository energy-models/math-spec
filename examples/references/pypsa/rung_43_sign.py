# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 43: a component's `sign` turns its term in the bus balance around."""

from __future__ import annotations

import spine

#: the sign each component enters the bus balance with, against PyPSA's default
SIGNS = {'generators': ('flex43', -1), 'loads': ('feed43', 1), 'storage_units': ('su43', -1), 'stores': ('e43', -1)}


def build():
    """The spine with a unit that draws power, a load that feeds it, and a storage unit and a store drawn the other way round."""
    n = spine.build()
    n.add('Generator', 'flex43', bus='south', p_nom=20, marginal_cost=-50, sign=-1)
    n.add('Load', 'feed43', bus='north', p_set=10, sign=1)
    n.add('StorageUnit', 'su43', bus='south', p_nom=10, max_hours=2, state_of_charge_initial=20, sign=-1)
    n.add('Store', 'e43', bus='north', e_nom=30, e_initial=30, sign=-1)
    return n
