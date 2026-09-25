# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 50: a load that is not `active` — PyPSA drops it from its bus's balance."""

from __future__ import annotations

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Load', 'idle50', bus='south', p_set=[30, 10, 20, 40], active=False)
    return n
