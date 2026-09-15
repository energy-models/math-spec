# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The two lists of commit types in the release pipeline, held to each other."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / '.release-please-config.json'
GATE = ROOT / '.github' / 'workflows' / 'pr-title.yml'


def _gate_types() -> set[str]:
    """Every type the `Conventional commit subject` check lets onto `main`.

    Reads the alternation out of the workflow rather than restating it, so the
    test cannot drift in the same way the two files it compares can.
    """
    alternation = re.search(r"^\s*TYPES='([^']+)'", GATE.read_text(), re.MULTILINE)
    assert alternation, f"{GATE.relative_to(ROOT)} has no TYPES='…' line to read the accepted types from"
    return set(alternation[1].split('|'))


def _changelog_types() -> set[str]:
    """Every type release-please has a section for. It silently drops a commit with any other type."""
    sections = json.loads(CONFIG.read_text())['packages']['.']['changelog-sections']
    return {section['type'] for section in sections}


def test_the_gate_accepts_exactly_the_types_the_changelog_knows():
    """`revert:` passed the gate into a config that had never heard of it, and 0.0.0-alpha.91 paid for it.

    That release is #474 and the revert of #474, so it carries no change at
    all. release-please has no section for `revert`, so it printed the feature
    and dropped the revert, and the changelog announces a feature no tag holds.
    """
    gate, changelog = _gate_types(), _changelog_types()
    assert gate == changelog, (
        f'{sorted(gate ^ changelog)}: a type the gate accepts has no section in {CONFIG.name}, so '
        f'release-please drops the subject from the changelog without failing — give the type a '
        f'section there, or take it out of TYPES in {GATE.name}'
    )
