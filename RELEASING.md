<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Releasing

A release is a pull request that edits `CHANGELOG.md`. Merging it tags the
commit, opens the GitHub release and publishes the package to PyPI.

## Between releases

Each pull request adds one line under `## Upcoming version` at the top of
`CHANGELOG.md`: its title and a link to it. A `feat`, `fix`, `perf`,
`refactor`, `docs` or `revert` pull request adds a line. A `chore`, `test`,
`ci`, `build` or `style` pull request adds none. The `Changelog line` check
fails a pull request that owes a line and adds none. The label `no changelog`
opts it out, for a change no reader of the changelog needs to hear about.

```markdown
## Upcoming version

- feat(language): a coordinate may declare its own label space ([#123](https://github.com/energy-models/mathspec/pull/123))
```

## Cutting a release

1. Open a pull request that renames `## Upcoming version` to the version and
   the day, and edit the section into the release notes: group the lines, merge
   related ones, and add a paragraph on top if the release needs one.

   ```markdown
   ## 0.1.0 (2026-10-01)
   ```

   A version is `X.Y.Z`, with an optional `aN`, `bN` or `rcN` for a
   pre-release. The `CI` check refuses a heading the release workflow cannot
   act on: a version that is not newer than the latest tag, a date that is not a
   day, or a section with nothing under it. You can also put a new, empty
   `## Upcoming version` above the release.

2. Merge it. `.github/workflows/release.yml` then:
   - tags the merge commit `v0.1.0` and opens the GitHub release, with the
     section as its notes. A pre-release version is marked as one.
   - builds the wheel and the sdist from the tag, through `build.yml`.
   - publishes both to PyPI, after a reviewer approves the `pypi` environment.

Every other push to `main` finds no untagged version heading and does nothing.

`python -m tools.changelog check` runs the same check locally, and
`python -m tools.changelog notes 0.1.0` prints the notes the release will get.

## The version

The version comes from the git tag. `pyproject.toml` declares
`dynamic = ["version"]`, and hatch-vcs reads the tag at build time, so the
changelog heading, the tag and the wheel carry one number. The release workflow
checks that the wheel it publishes has that number.

The language version, the `version:` key of a spec file, is a separate
number ([versions](https://mathspec.readthedocs.io/en/latest/about/versions/)).
`SUPPORTED_VERSIONS` in `src/mathspec/spec.py` is the set a release reads. A
pull request that changes that set says so in its changelog line, so that the
release notes name the language versions the release starts or stops reading.

Do not push a version tag by hand. The release workflow only acts on a heading
with no tag, so a hand-made tag makes its heading history before anything is
published.

## When a step fails

- **The tag or the GitHub release was not made.** Fix the cause and re-run the
  workflow. It acts on the first version heading that has no tag.
- **The build or the upload failed after the tag was made.** Re-run the failed
  jobs of that run from the Actions tab. PyPI never takes a version twice, so a
  version that reached PyPI is final. Fix a wrong release with the next
  version.

## One-time setup

- **PyPI.** Add a trusted publisher for the project `mathspec`: owner
  `energy-models`, repository `mathspec`, workflow `release.yml`, environment
  `pypi`. Before the first upload it is a _pending_ publisher.
- **The `pypi` environment.** Create it under the repository's
  Settings → Environments, and add the people who may approve a release as
  required reviewers.
- **Branch protection on `main`.** Require the `CI`,
  `Conventional commit subject` and `Changelog line` checks.
- **The label `no changelog`.** Create it under Issues → Labels.

## What CI proves, and what it does not

`ci.yml` runs on the declared floor, Python 3.12, and only there. Code that
works on the oldest supported interpreter almost always works on the newer
ones, and the breakage that does happen is a standard-library feature newer
than the floor, which is what a floor-pinned job catches. The 3.13 and 3.14
classifiers in `pyproject.toml` are claims no job tests.
