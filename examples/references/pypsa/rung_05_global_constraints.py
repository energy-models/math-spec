#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["pypsa==1.3.0", "linopy==0.9.1", "pandas>=2.2", "xarray==2026.7.0", "highspy==1.15.1"]
# ///
"""Reference for rung 5 of `examples/pypsa.yaml` — a CO2 cap priced through the carrier map.

uv run --script examples/references/pypsa/rung_05_global_constraints.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pypsa

sys.path.insert(0, str(Path(__file__).resolve().parent))

import instances

RUNG = 'rung_05_global_constraints'


def build() -> pypsa.Network:
    """Rung 5's global constraint: a primary-energy CO2 cap over three carriers.

    Coal is cheap and dirty, gas dearer and cleaner, wind clean and dearest to
    run here; the cap decides the mix, and its shadow price is the carbon
    price.
    """
    return instances.build(RUNG)


if __name__ == '__main__':
    instances.stamp(RUNG, build())
