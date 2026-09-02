# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Where the golden output lives, and what the two halves agree to call it."""

from __future__ import annotations

from pathlib import Path

DIRECTORY = Path(__file__).resolve().parent
MODEL = DIRECTORY / 'model.yaml'


def path_for(format_name: str) -> Path:
    """The committed output for one format."""
    return DIRECTORY / f'{format_name}.out'
