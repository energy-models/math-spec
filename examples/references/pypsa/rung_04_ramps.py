#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["pypsa==1.3.0", "linopy==0.9.1", "pandas>=2.2", "xarray==2026.7.0", "highspy==1.15.1"]
# ///
"""Reference for rung 4 of `examples/pypsa.yaml` — ramp limits.

uv run --script examples/references/pypsa/rung_04_ramps.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pypsa

sys.path.insert(0, str(Path(__file__).resolve().parent))

import instances

RUNG = 'rung_04_ramps'


def build() -> pypsa.Network:
    """Rung 4's ramps: a slow cheap unit against a fast dear one, chasing a swinging load.

    Coal may move a fifth of its capacity per snapshot, so the swings belong
    to the peaker however dear it is; the tie line east ramps too.
    """
    return instances.build(RUNG)


if __name__ == '__main__':
    instances.stamp(RUNG, build())
