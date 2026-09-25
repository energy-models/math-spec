# SPDX-FileCopyrightText: mathspec contributors
#
# SPDX-License-Identifier: MIT

"""The headings the release workflow reads, and the release each one asks for."""

from __future__ import annotations

import re

import pytest

from tools.changelog import LEGACY, PATH, ChangelogError, missing_entry, notes, order, pending, sections

PREAMBLE = '# Changelog\n\nProse the tool never reads.\n\n'
HISTORY = '## [0.0.0-alpha.126](https://example.org/compare) (2026-09-25)\n\n* an old line\n'
TAGS = {'v0.0.0-alpha.125', 'v0.0.0-alpha.126'}


def changelog(*blocks: str) -> str:
    return PREAMBLE + ''.join(blocks) + HISTORY


@pytest.mark.parametrize(
    ('text', 'tags', 'expected'),
    [
        pytest.param(changelog('## Upcoming version\n\n- a line\n\n'), TAGS, None, id='upcoming-only'),
        pytest.param(changelog(), TAGS, None, id='nothing-above-the-history'),
        pytest.param(changelog('## 0.1.0 (2026-10-01)\n\n- a line\n\n'), TAGS, '0.1.0', id='a-new-release'),
        pytest.param(
            changelog('## Upcoming version\n\n## 0.1.0 (2026-10-01)\n\n- a line\n\n'),
            TAGS,
            '0.1.0',
            id='a-new-release-under-an-empty-upcoming',
        ),
        pytest.param(changelog('## 0.1.0rc1 (2026-10-01)\n\n- a line\n\n'), TAGS, '0.1.0rc1', id='a-release-candidate'),
        pytest.param(
            changelog('## 0.1.0 (2026-10-01)\n\n- a line\n\n'), TAGS | {'v0.1.0'}, None, id='a-release-already-tagged'
        ),
        pytest.param(
            changelog('## 0.1.1 (2026-10-02)\n\n- b\n\n## 0.1.0 (2026-10-01)\n\n- a\n\n'),
            TAGS | {'v0.1.0'},
            '0.1.1',
            id='the-next-release-above-a-tagged-one',
        ),
    ],
)
def test_the_first_untagged_release_heading_is_the_release(text, tags, expected):
    assert pending(text, tags) == expected


@pytest.mark.parametrize(
    ('text', 'tags', 'message'),
    [
        pytest.param(
            changelog('## Unreleased\n\n- a line\n\n'), TAGS, 'neither "## Upcoming version"', id='another-name'
        ),
        pytest.param(changelog('## v0.1.0 (2026-10-01)\n\n- a\n\n'), TAGS, 'neither', id='a-v-before-the-version'),
        pytest.param(changelog('## 0.1 (2026-10-01)\n\n- a\n\n'), TAGS, 'neither', id='two-parts'),
        pytest.param(changelog('## 0.1.0-alpha.1 (2026-10-01)\n\n- a\n\n'), TAGS, 'neither', id='a-semver-pre'),
        pytest.param(changelog('## 0.1.0\n\n- a\n\n'), TAGS, 'neither', id='no-date'),
        pytest.param(changelog('## 0.1.0 (2026-13-01)\n\n- a\n\n'), TAGS, 'not a day', id='a-date-that-is-not-a-day'),
        pytest.param(changelog('## 0.1.0 (2026-10-01)\n\n'), TAGS, 'nothing under it', id='no-notes'),
        pytest.param(
            changelog('## 0.0.0a3 (2026-10-01)\n\n- a\n\n'), TAGS, 'not newer than', id='older-than-the-latest-tag'
        ),
        pytest.param(
            changelog('## 0.0.0a126 (2026-10-01)\n\n- a\n\n'),
            TAGS,
            'not newer than the latest tag, v0.0.0-alpha.126',
            id='the-latest-tag-in-the-other-spelling',
        ),
        pytest.param(
            changelog('## Upcoming version\n\n## Upcoming version\n\n'), TAGS, 'two "## Upcoming version"', id='two'
        ),
        pytest.param(PREAMBLE + '## Upcoming version\n\n- a\n', TAGS, 'no release heading', id='no-release-at-all'),
        pytest.param(changelog(), {'v0.0.0-alpha.125'}, 'release-please heading with no tag', id='untagged-history'),
    ],
)
def test_a_heading_the_workflow_cannot_release_is_refused(text, tags, message):
    with pytest.raises(ChangelogError, match=re.escape(message)):
        pending(text, tags)


@pytest.mark.parametrize(
    ('smaller', 'larger'),
    [
        pytest.param('v0.0.0-alpha.9', 'v0.0.0-alpha.10', id='the-alpha-counter-as-a-number'),
        pytest.param('v0.0.0-alpha.126', 'v0.0.0a127', id='both-spellings-of-an-alpha'),
        pytest.param('v0.1.0a1', 'v0.1.0b1', id='alpha-before-beta'),
        pytest.param('v0.1.0rc2', 'v0.1.0', id='a-candidate-before-the-release'),
        pytest.param('v0.9.0', 'v0.10.0', id='a-part-as-a-number'),
    ],
)
def test_tags_order_as_versions(smaller, larger):
    assert order(smaller) < order(larger)


def test_a_tag_that_is_not_a_version_is_ignored():
    assert order('docs-snapshot') is None, 'a stray tag neither blocks nor pins a release'


def test_the_notes_are_the_section_as_written():
    text = changelog('## 0.1.0 (2026-10-01)\n\n### Features\n\n- a line\n\n')
    assert notes(text, '0.1.0') == '### Features\n\n- a line\n', 'the release notes are the text under the heading'


def test_notes_for_a_version_with_no_heading_are_refused():
    with pytest.raises(ChangelogError, match=re.escape('no "## 0.2.0 (date)" heading')):
        notes(changelog(), '0.2.0')


def test_the_repository_changelog_releases_nothing_while_its_history_is_tagged():
    """The workflow reads this file on every push to main, so it has to parse."""
    text = PATH.read_text()
    history = {f'v{m["version"]}' for s in sections(text) if (m := LEGACY.fullmatch(s.heading))}
    assert history, 'the release-please history is still in the file'
    assert pending(text, history) is None, 'a changelog with nothing new above its tagged history releases nothing'


BASE = changelog('## Upcoming version\n\n- an earlier line\n\n')
ADDED = changelog('## Upcoming version\n\n- an earlier line\n- this PR\n\n')


@pytest.mark.parametrize(
    ('title', 'text', 'owes'),
    [
        pytest.param('feat(language): a new thing', ADDED, False, id='a-feat-that-adds-its-line'),
        pytest.param('feat(language): a new thing', BASE, True, id='a-feat-that-adds-none'),
        pytest.param('fix: a bug', BASE, True, id='a-fix-that-adds-none'),
        pytest.param('docs: a page', BASE, True, id='a-docs-pr-that-adds-none'),
        pytest.param('revert: a change', BASE, True, id='a-revert-that-adds-none'),
        pytest.param('chore: a tidy', BASE, False, id='a-chore-owes-none'),
        pytest.param('ci: a workflow', BASE, False, id='a-ci-pr-owes-none'),
        pytest.param('test: a case', BASE, False, id='a-test-pr-owes-none'),
        pytest.param(
            'feat: a new thing',
            changelog('## Upcoming version\n\n- an earlier line, reworded\n\n'),
            False,
            id='a-reworded-line-counts',
        ),
        pytest.param(
            'feat: a new thing',
            changelog('## 0.1.0 (2026-10-01)\n\n- an earlier line\n- this PR\n\n'),
            True,
            id='a-line-outside-upcoming-does-not-count',
        ),
    ],
)
def test_a_pr_a_changelog_reader_wants_to_hear_about_adds_a_line(title, text, owes):
    assert (missing_entry(title, text, BASE) is not None) == owes


def test_a_pr_that_owes_a_line_is_told_the_way_out():
    reason = missing_entry('feat: a new thing', BASE, BASE)
    assert reason is not None
    assert 'under "## Upcoming version"' in reason, 'the message says where the line goes'
    assert 'the label "no changelog"' in reason, 'and how a PR that owes none says so'
