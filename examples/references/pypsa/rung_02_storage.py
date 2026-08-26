#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["pypsa==1.3.0", "linopy==0.9.1", "pandas>=2.2", "xarray==2026.7.0", "highspy==1.15.1"]
# ///
"""Reference for rung 2 of `examples/pypsa.yaml` — storage units and stores.

uv run --script examples/references/pypsa/rung_02_storage.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pypsa

sys.path.insert(0, str(Path(__file__).resolve().parent))

import instances

RUNG = 'rung_02_storage'


def build() -> pypsa.Network:
    """Rung 2's storage: a cyclic battery, a reservoir that can spill, a cavern store.

    The generator is cheap for two snapshots and dear for two, so the battery
    buys low and sells high and its horizon closes on itself; the reservoir
    opens on a given charge and spills the inflow it cannot hold; the cavern
    drains from its initial fill.
    """
    return instances.build(RUNG)


if __name__ == '__main__':
    instances.stamp(RUNG, build())
