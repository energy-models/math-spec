# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 49: a carrier's growth limit without `multi_investment_periods` — PyPSA builds no row, so the build passes the cap."""

from __future__ import annotations

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Carrier', 'wind', max_growth=10)
    n.add('Generator', 'wind49', bus='south', carrier='wind', p_nom_extendable=True, p_nom_max=100, capital_cost=5)
    return n
