# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 11: PyPSA's own `ac_dc_meshed` example, whole — meshed AC and DC, extendable lines, links and generators, carriers, a CO2 budget."""

from __future__ import annotations


def build():
    """The example network as PyPSA ships it — not the spine: every statement above, composed."""
    import pypsa

    return pypsa.examples.ac_dc_meshed()
