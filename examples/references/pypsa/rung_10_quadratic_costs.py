#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["pypsa==1.3.0", "linopy==0.9.1", "pandas>=2.2", "xarray==2026.7.0", "highspy==1.15.1"]
# ///
"""Reference for rung 10 of `examples/pypsa_quadratic.yaml` — quadratic costs.

uv run --script examples/references/pypsa/rung_10_quadratic_costs.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pypsa

sys.path.insert(0, str(Path(__file__).resolve().parent))

import instances

RUNG = 'rung_10_quadratic_costs'


def build() -> pypsa.Network:
    """Rung 10's quadratic costs: two generators splitting a load by their marginal slopes.

    Steam is cheap to start and steepens fast, the engine is dear but flat, so
    the optimum is an interior split only a quadratic objective produces; the
    lossy link carries its own quadratic cost.
    """
    return instances.build(RUNG)


if __name__ == '__main__':
    instances.stamp(RUNG, build())
