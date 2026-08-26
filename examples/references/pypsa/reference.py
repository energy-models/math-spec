#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["pypsa==1.3.0", "linopy==0.9.1", "pandas>=2.2", "xarray==2026.7.0", "highspy==1.15.1"]
# ///
"""Solve every rung's reference network through PyPSA and record what it saw.

    uv run --script examples/references/pypsa/reference.py            # every rung
    uv run --script examples/references/pypsa/reference.py rung_04_ramps

The rungs are the folders under `data/` other than `base`: a rung is added by
adding a folder, and its story is the folder's `README.md`. `instances.build`
reads the spine plus the folder, `instances.stamp` writes the record.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import instances


def rungs() -> list[str]:
    """Every rung there is, in ladder order — the folders beside the spine."""
    return sorted(path.name for path in instances.DATA.iterdir() if path.is_dir() and path.name != 'base')


if __name__ == '__main__':
    for rung in sys.argv[1:] or rungs():
        instances.stamp(rung, instances.build(rung))
