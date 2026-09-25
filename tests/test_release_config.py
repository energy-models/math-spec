# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""The two lists that decide whether a merged subject reaches the changelog."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / '.release-please-config.json'
PR_TITLE = ROOT / '.github' / 'workflows' / 'pr-title.yml'


def test_every_accepted_type_has_a_changelog_section():
    """What 0.0.0-alpha.91 cost: `revert:` passed the title check and had no changelog section.

    release-please keeps a commit only where its type has a section, so the
    revert was dropped, the feature #481 had cancelled was announced alone, and
    the release tags no change at all.
    """
    accepted = re.search(r"^\s*TYPES='([^']+)'", PR_TITLE.read_text(), re.MULTILINE)
    assert accepted, f"{PR_TITLE.name} no longer defines TYPES='a|b|c', so what the check accepts cannot be read here"
    sections = json.loads(CONFIG.read_text())['packages']['.']['changelog-sections']
    assert set(accepted[1].split('|')) == {section['type'] for section in sections}, (
        f'{PR_TITLE.name} and {CONFIG.name} disagree on the commit types: a type with no section is dropped from '
        f'the changelog and nothing fails — give the type a section, or take it out of TYPES'
    )
