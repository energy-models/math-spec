#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["pypsa==1.3.0", "linopy==0.9.1", "pandas>=2.2", "xarray==2026.7.0", "highspy==1.15.1"]
# ///
"""Reference for rung 1 of `examples/pypsa.yaml` — transport.

uv run --script examples/references/pypsa/rung_01_transport.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pypsa

sys.path.insert(0, str(Path(__file__).resolve().parent))

import instances

RUNG = 'rung_01_transport'


def build() -> pypsa.Network:
    """Rung 1's transport: the spine as it stands, plus a must-run its schedule pins.

    Coal in the north is cheap and the wire loses a tenth on the way south, so
    the south's load splits between imports, a small must-run pinned by its
    given schedule, and its own gas at the link's rating.
    """
    return instances.build(RUNG)


if __name__ == '__main__':
    instances.stamp(RUNG, build())
