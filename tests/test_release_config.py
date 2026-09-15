# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""The three lists that decide whether a merged subject reaches the changelog."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / '.release-please-config.json'
PR_TITLE = ROOT / '.github' / 'workflows' / 'pr-title.yml'


def _spelled_out(pattern: str, what: str) -> str:
    """The one capture of `pattern` in pr-title.yml, or an assertion naming the line that went missing.

    Both lists below are read out of the workflow rather than restated here, so
    this file cannot become the fourth copy of the same list.
    """
    match = re.search(pattern, PR_TITLE.read_text(), re.MULTILINE)
    assert match, f'{PR_TITLE.name} no longer spells out {what}, so this test cannot read what the check accepts'
    return match[1]


def accepted_types() -> set[str]:
    """Every type the `Conventional commit subject` check lets onto `main`."""
    return set(_spelled_out(r"^\s*TYPES='([^']+)'", "TYPES='a|b|c'").split('|'))


def advertised_types() -> set[str]:
    """Every type that check names in the help text it prints when it refuses a subject."""
    return set(_spelled_out(r'^\s+types\s{2,}(.+?)\s*$', 'the `types` line of its help text').split(', '))


def sectioned_types() -> set[str]:
    """Every type release-please gives a changelog section, and so the only types it keeps."""
    sections = json.loads(CONFIG.read_text())['packages']['.']['changelog-sections']
    return {section['type'] for section in sections}


def test_every_accepted_type_has_a_changelog_section():
    """What 0.0.0-alpha.91 cost: `revert:` passed the title check and had no changelog section.

    release-please keeps a commit only where its type is in a visible section,
    or is breaking and in a hidden one. So the revert was dropped, the feature
    #481 had cancelled was announced alone, and the release tags no change.
    """
    assert accepted_types() == sectioned_types(), (
        f'{PR_TITLE.name} and {CONFIG.name} disagree on the commit types: a type with no section is dropped from '
        f'the changelog and nothing fails, and a section no subject can reach prints nothing — give the type a '
        f'section, or take it out of TYPES'
    )


def test_the_help_text_names_the_types_the_check_accepts():
    """The third copy of the list, and the one a contributor reads only once the check has refused them."""
    assert advertised_types() == accepted_types(), (
        f"{PR_TITLE.name} prints a `types` help line that its own TYPES='…' does not match, so a refused subject "
        f'is told to use a type the check rejects, or is never told about one it would take'
    )
