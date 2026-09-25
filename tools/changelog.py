# SPDX-FileCopyrightText: mathspec contributors
#
# SPDX-License-Identifier: MIT

"""The release a changelog asks for, read off its headings.

    python -m tools.changelog check           # fail if the headings are not a release this repo can cut
    python -m tools.changelog pending         # print the version to release, or nothing
    python -m tools.changelog notes 0.1.0     # print that version's section
    python -m tools.changelog entry "<PR title>" base.md   # fail if the PR adds no line it owes

``CHANGELOG.md`` is edited by hand. Above the first release sits at most one
``## Upcoming version``. A release PR renames it to ``## 0.1.0 (2026-10-01)``,
and the merge to ``main`` releases the first version heading that has no tag.
Only the heading lines are read; the prose under them is the release notes as
written. Standard library only, because the release workflow runs it on the
runner's own Python.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / 'CHANGELOG.md'
UPCOMING = 'Upcoming version'

#: A release heading as a release PR writes it: a PEP 440 release with an
#: optional pre-release, then the date in parentheses.
RELEASE = re.compile(r'(?P<version>\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?) \((?P<date>\d{4}-\d{2}-\d{2})\)')
#: A heading release-please wrote, kept as history: ``[0.0.0-alpha.126](url) (date)``.
LEGACY = re.compile(r'\[(?P<version>[^\]]+)\]\(\S+\) \(\d{4}-\d{2}-\d{2}\)')
#: A tag this repository has cut, in either spelling.
TAG = re.compile(r'v(?P<release>\d+\.\d+\.\d+)(?:(?:-(?P<legacy>alpha)\.|(?P<pre>a|b|rc))(?P<number>\d+))?')
PRE_RANK = {'alpha': 0, 'a': 0, 'b': 1, 'rc': 2}
#: The PR types a changelog reader wants to hear about, each of which adds a line.
NEEDS_LINE = frozenset({'feat', 'fix', 'perf', 'refactor', 'docs', 'revert'})
#: The label that lets a PR of one of those types add no line.
OPT_OUT = 'no changelog'


class ChangelogError(ValueError):
    """The headings do not describe a release this repository can cut."""


@dataclass(frozen=True)
class Section:
    """One ``##`` section: its heading text and the lines under it."""

    heading: str
    body: str


def sections(text: str) -> list[Section]:
    """Split the changelog at its ``##`` headings, dropping the preamble."""
    parts = re.split(r'^## (.+)$', text, flags=re.MULTILINE)
    return [Section(heading.strip(), body.strip('\n')) for heading, body in zip(parts[1::2], parts[2::2], strict=True)]


def order(tag: str) -> tuple[int, ...] | None:
    """The sort key of a version tag, or None for a tag that is not a version."""
    match = TAG.fullmatch(tag)
    if match is None:
        return None
    release = tuple(int(part) for part in match['release'].split('.'))
    pre = match['legacy'] or match['pre']
    if pre is None:
        return (*release, len(PRE_RANK), 0)
    return (*release, PRE_RANK[pre], int(match['number']))


def pending(text: str, tags: set[str]) -> str | None:
    """The version the changelog asks to release, or None when it asks for none.

    Raises:
        ChangelogError: If a heading above the first release is not
            ``Upcoming version``, if there are two of those, if no release
            heading exists, or if the first release heading is new but its
            version, date or section is not one this repository can release.
    """
    found = sections(text)
    upcoming = 0
    for section in found:
        if section.heading == UPCOMING:
            upcoming += 1
            if upcoming > 1:
                raise ChangelogError(f'there are two "## {UPCOMING}" headings. Keep one, above every release.')
            continue
        legacy = LEGACY.fullmatch(section.heading)
        if legacy is not None:
            if f'v{legacy["version"]}' not in tags:
                raise ChangelogError(
                    f'"## {section.heading}" is a release-please heading with no tag. Write a new release as '
                    f'"## 0.1.0 (2026-10-01)".'
                )
            return None
        release = RELEASE.fullmatch(section.heading)
        if release is None:
            raise ChangelogError(
                f'"## {section.heading}" is neither "## {UPCOMING}" nor a release such as "## 0.1.0 (2026-10-01)". '
                f'A version is X.Y.Z, with an optional a, b or rc number: 0.1.0rc1.'
            )
        return _new_release(release['version'], release['date'], section, tags)
    raise ChangelogError(f'the changelog has no release heading below "## {UPCOMING}".')


def _new_release(version: str, day: str, section: Section, tags: set[str]) -> str | None:
    """Check the first release heading, and return its version if it has no tag yet.

    A tagged version is history, whatever else is true of it. An untagged one is
    released on the merge, so everything a release needs is checked here, in the
    pull request that writes it, rather than by the workflow after the merge.
    """
    tag = f'v{version}'
    if tag in tags:
        return None
    try:
        date.fromisoformat(day)
    except ValueError:
        raise ChangelogError(
            f'"## {section.heading}" has the date {day}, which is not a day. Write YYYY-MM-DD.'
        ) from None
    if not section.body.strip():
        raise ChangelogError(f'"## {section.heading}" has nothing under it, and its text is the release notes.')
    newest = max((key for key in map(order, tags) if key is not None), default=None)
    key = order(tag)
    if newest is not None and key is not None and key <= newest:
        latest = max(t for t in tags if order(t) == newest)
        raise ChangelogError(f'{version} is not newer than the latest tag, {latest}. Pick a higher version.')
    return version


def notes(text: str, version: str) -> str:
    """The section under the release heading of *version*, as the release notes.

    Raises:
        ChangelogError: If no release heading names *version*.
    """
    for section in sections(text):
        release = RELEASE.fullmatch(section.heading)
        if release is not None and release['version'] == version:
            return section.body.strip() + '\n'
    raise ChangelogError(f'no "## {version} (date)" heading in the changelog.')


def upcoming(text: str) -> list[str]:
    """The non-empty lines under ``## Upcoming version``, or none when it is absent."""
    for section in sections(text):
        if section.heading == UPCOMING:
            return [line for line in section.body.splitlines() if line.strip()]
    return []


def missing_entry(title: str, text: str, base: str) -> str | None:
    """Why a pull request titled *title* owes the changelog a line, or None when it does not.

    *text* is the changelog on the pull request and *base* the one on its base
    branch. A line counts when it is under ``## Upcoming version`` and was not
    there on the base.
    """
    kind = re.match(r'[a-z]+', title)
    if kind is None or kind[0] not in NEEDS_LINE:
        return None
    if set(upcoming(text)) - set(upcoming(base)):
        return None
    return (
        f'a {kind[0]} PR adds its title, with a link to the PR, under "## {UPCOMING}". '
        f'If readers of the changelog do not need to hear about it, add the label "{OPT_OUT}".'
    )


def _tags() -> set[str]:
    """The tags of the repository this runs in."""
    return set(subprocess.run(['git', 'tag', '--list'], capture_output=True, text=True, check=True).stdout.split())


def main(argv: list[str]) -> int:
    """Run one verb, printing a refusal as a GitHub annotation."""
    text = PATH.read_text()
    try:
        match argv:
            case ['check']:
                version = pending(text, _tags())
                print(f'releases {version} on merge' if version else 'releases nothing on merge')
            case ['pending']:
                print(pending(text, _tags()) or '')
            case ['notes', version]:
                sys.stdout.write(notes(text, version))
            case ['entry', title, base]:
                if (reason := missing_entry(title, text, Path(base).read_text())) is not None:
                    raise ChangelogError(reason)
                print('the changelog line is there, or this PR owes none')
            case _:
                print(__doc__, file=sys.stderr)
                return 2
    except ChangelogError as error:
        print(f'::error file=CHANGELOG.md::{error}')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
