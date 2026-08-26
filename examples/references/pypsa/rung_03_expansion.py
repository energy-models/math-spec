#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["pypsa==1.3.0", "linopy==0.9.1", "pandas>=2.2", "xarray==2026.7.0", "highspy==1.15.1"]
# ///
"""Reference for rung 3 of `examples/pypsa.yaml` — capacity expansion.

uv run --script examples/references/pypsa/rung_03_expansion.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pypsa

sys.path.insert(0, str(Path(__file__).resolve().parent))

import instances

RUNG = 'rung_03_expansion'


def build() -> pypsa.Network:
    """Rung 3's expansion: a wind build decided by the solver against a fixed gas fleet.

    Wind is free to run but costs capacity, its availability varies, and its
    build is floored and capped; gas is fixed, dear, and budgeted in energy
    over the horizon, so the optimum has to buy some wind — at least the
    energy floor it also carries. The cable to the island is the extendable
    link, and the pump and tank are the extendable storage.
    """
    return instances.build(RUNG)


if __name__ == '__main__':
    instances.stamp(RUNG, build())
