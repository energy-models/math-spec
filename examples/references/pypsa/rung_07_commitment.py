#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["pypsa==1.3.0", "linopy==0.9.1", "pandas>=2.2", "xarray==2026.7.0", "highspy==1.15.1"]
# ///
"""Reference for rung 7 of `examples/pypsa.yaml` — unit commitment.

uv run --script examples/references/pypsa/rung_07_commitment.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pypsa

sys.path.insert(0, str(Path(__file__).resolve().parent))

import instances

RUNG = 'rung_07_commitment'


def build() -> pypsa.Network:
    """Rung 7's commitment: a unit that pays to start, to stop, and to idle.

    The base unit may not run below forty percent, was already on with two
    snapshots of its minimum up time left to serve, pays for each start, and
    ramps against its previous status — so the swing between it and the
    peaker is a schedule, not a dispatch.
    """
    return instances.build(RUNG)


if __name__ == '__main__':
    instances.stamp(RUNG, build())
