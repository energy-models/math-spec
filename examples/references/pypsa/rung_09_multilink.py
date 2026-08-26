#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["pypsa==1.3.0", "linopy==0.9.1", "pandas>=2.2", "xarray==2026.7.0", "highspy==1.15.1"]
# ///
"""Reference for rung 9 of `examples/pypsa.yaml` — a multi-link delivering at two ports.

uv run --script examples/references/pypsa/rung_09_multilink.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pypsa

sys.path.insert(0, str(Path(__file__).resolve().parent))

import instances

RUNG = 'rung_09_multilink'


def build() -> pypsa.Network:
    """Rung 9's multi-link: one gas flow delivering power and heat at two ports.

    The CHP link withdraws gas at its first bus and injects at the other two
    by its two efficiencies; the heat bus has no other supply, so the link
    runs and the power bus tops up from imports.
    """
    return instances.build(RUNG)


if __name__ == '__main__':
    instances.stamp(RUNG, build())
