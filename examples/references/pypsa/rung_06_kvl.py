#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["pypsa==1.3.0", "linopy==0.9.1", "pandas>=2.2", "xarray==2026.7.0", "highspy==1.15.1"]
# ///
"""Reference for rung 6 of `examples/pypsa.yaml` — passive lines and the voltage law.

uv run --script examples/references/pypsa/rung_06_kvl.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pypsa

sys.path.insert(0, str(Path(__file__).resolve().parent))

import instances

RUNG = 'rung_06_kvl'


def build() -> pypsa.Network:
    """Rung 6's voltage law: three buses in a triangle of lines.

    Two generators and one load; with a cycle in the graph the flows split by
    impedance rather than by cost, which is what the KVL row enforces; one
    line is extendable, so its rating is a decision.
    """
    return instances.build(RUNG)


if __name__ == '__main__':
    instances.stamp(RUNG, build())
