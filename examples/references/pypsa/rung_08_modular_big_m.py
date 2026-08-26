#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["pypsa==1.3.0", "linopy==0.9.1", "pandas>=2.2", "xarray==2026.7.0", "highspy==1.15.1"]
# ///
"""Reference for rung 8 of `examples/pypsa.yaml` — modular builds and big M.

uv run --script examples/references/pypsa/rung_08_modular_big_m.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pypsa

sys.path.insert(0, str(Path(__file__).resolve().parent))

import instances

RUNG = 'rung_08_modular_big_m'


def build() -> pypsa.Network:
    """Rung 8's modular and big-M builds: whole modules, and a build gated by a status.

    The block plant is bought twenty-five megawatts at a time and gated by a
    status, so its bounds are one module's share; the flexible plant is
    extendable and committable with ramps, which is the pairing PyPSA's big-M
    rows linearize.
    """
    return instances.build(RUNG)


if __name__ == '__main__':
    instances.stamp(RUNG, build())
