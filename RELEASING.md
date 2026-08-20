<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Releasing

Releases are cut by [release-please](https://github.com/googleapis/release-please)
from the conventional-commit subjects that land on `main`. Nothing about a
release is done by hand while the project is on the alpha stream.

## The pipeline

```text
PR title (conventional)  ──►  squash onto main
                                   │
                       release.yml │ release-please opens/updates a release PR
                                   ▼
                         "chore(main): release 0.0.0-alpha.N"
                                   │  auto-merged while on the alpha stream
                                   ▼
                              tag v0.0.0-alpha.N   +   GitHub release
                                   │
                        build.yml  ▼  builds the wheel, checks it against the tag
                                       and (when enabled) publishes to PyPI
```

Three files own it:

| File                            | Role                                                   |
| ------------------------------- | ------------------------------------------------------ |
| `.release-please-config.json`   | release type, changelog sections, the alpha stream     |
| `.release-please-manifest.json` | the last released version — release-please rewrites it |
| `.github/workflows/release.yml` | runs release-please on every push to `main`            |

`.github/workflows/pr-title.yml` guards the input; `.github/workflows/build.yml`
consumes the output.

## Why the two halves fit without a bridge

`release-type` is `simple`, which never touches `pyproject.toml` — release-please
maintains `CHANGELOG.md`, the manifest, and the tag, and nothing else. `build.yml`
already triggers on a tag push, derives the version with
`git describe --tags --abbrev=0`, and substitutes it for the `0.0.0` literal in
`pyproject.toml`. So the tag is the whole interface between them, and neither
workflow needs to know the other exists.

(`simple` also declares a `version.txt` updater, but with `createIfMissing:
false`. There is no `version.txt` in this repo and none will be created.)

## The alpha stream

The manifest is pinned at `0.0.0` and the config is in sticky `prerelease` mode,
so every release is `0.0.0-alpha.N` — dist version `0.0.0aN`. There is no
semantic promise attached to any of them; the point is that an early user always
has a number to quote in a bug report instead of a commit sha.

Two consequences worth knowing:

- **`main` releases on every merge.** The last step of `release.yml` enables
  auto-merge on the release PR. It is explicitly temporary and expires by
  itself: the step reads the version off the PR title and refuses anything that
  is not a prerelease, so the first official version stops the automation
  without anyone remembering to. To pause it earlier, set the repository
  variable `AUTO_RELEASE` to `false` and merge release PRs by hand.
- **Breaking markers are refused.** A `!` in the subject, or a
  `BREAKING CHANGE:` footer, moves the _base_ version rather than the counter.
  A zero patch happens to be an absorbing state under `versioning: prerelease`,
  so at `0.0.0` this is currently harmless — but the immunity disappears the
  moment the stream moves, and then one `feat!:` turns `0.0.1-alpha.12` into
  `0.1.0-alpha.12`. `pr-title.yml` refuses the marker instead. Describe the
  break in the PR body; the alpha stream carries no compatibility promise, so
  there is nothing for the version to announce.

## Leaving the alpha stream

When the project is ready for a real version:

1. Delete the auto-merge step from `release.yml` (it is fenced by a comment
   banner).
2. Remove `versioning`, `prerelease` and `prerelease-type` from
   `.release-please-config.json`.
3. Set the manifest to the last version you want release-please to bump _from_.
4. Drop the base-version guard from `pr-title.yml`, so `!` works again.
5. Merge the next release PR by hand.

## One-time setup

Not yet done — the workflows are inert or degraded until these are.

**A GitHub App for release-please.** A `GITHUB_TOKEN`-authored PR does not
trigger CI, and a `GITHUB_TOKEN`-pushed tag does not trigger `build.yml`. With
no app the release PR is opened but never built, and `release.yml` emits a
warning saying so. Create an app with `contents: write` and `pull_requests:
write`, install it on the repository, and set the secrets `APP_CLIENT_ID` and
`APP_PRIVATE_KEY`.

**"Allow auto-merge" on the repository.** Required by the temporary alpha step;
without it that step fails.

**Branch protection on `main`.** Squash-only merges, and require the `CI` and
`Conventional commit subject` checks. Auto-merge is what makes the release PR
wait for them.

**PyPI.** The publish job is gated on the repository variable
`PUBLISH_TO_PYPI`. Configure a trusted publisher for `math-spec` pointing at
`build.yml` and the `pypi` environment, then set the variable to `true`. Until
then the rest of the pipeline still runs: release-please cuts the tag, the
changelog and the GitHub release, and `build.yml` produces a version-checked
wheel as a build artifact. Only the upload is skipped.

## Local deviations from the template

This repository is generated from
[`energy-models/copier-template-python-open-source`](https://github.com/energy-models/copier-template-python-open-source)
(currently `v1.0.0`) and `pixi run template-update` re-applies it. Copier
three-way merges, so files the template does not know about are never touched
and files it owns can conflict.

**Additive — the template has no such file, nothing to conflict with:**
`.release-please-config.json`, `.release-please-manifest.json`,
`.github/workflows/release.yml`, `.github/workflows/pr-title.yml`,
`RELEASING.md`, `.github/pull_request_template.md`.

(That last one the template _annotates_ in `REUSE.toml` but never ships — a
dangling reference in the template itself. Adding the file resolves it.)

**Template-owned and edited — these can conflict on update:**

| File                          | What changed and why                                                                                                                                                                                                                                                                                       |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `.github/workflows/build.yml` | Two edits, both marked `LOCAL DEVIATION` in place: the wheel-version-versus-tag check, and the `PUBLISH_TO_PYPI` gate on the publish job.                                                                                                                                                                  |
| `CHANGELOG.md`                | The template ships a Keep a Changelog skeleton with a hand-maintained `## Unreleased` block. release-please owns this file now and writes a different shape, so the skeleton is gone.                                                                                                                      |
| `CONTRIBUTING.md`             | The template's "Release checklist" describes the manual process it assumes — bump a version number in `src/math_spec/__init__.py`, tag by hand, write the changelog entry yourself. All three are now wrong. Replaced, along with the commit-message section, which did not ask for conventional subjects. |
| `REUSE.toml`                  | Annotations added for the two release-please JSON files (JSON takes no comment header) and for `CHANGELOG.md`.                                                                                                                                                                                             |

On a template update, expect conflicts in `CONTRIBUTING.md` and `CHANGELOG.md`
if the template touched them, and resolve in favour of this repository — the
template cannot know the project is on release-please. `build.yml` is the one
to read carefully, since the template does maintain it (its
`scripts/update_actions.py` bumps pinned action SHAs).

## Cutting a release by hand

Push a tag. `build.yml` reacts to any tag, so
`git tag v0.1.0 && git push origin v0.1.0` builds and (if enabled) publishes it.
The version check in `build.yml` is the safety net for this path — it is the one
route that bypasses release-please entirely, and therefore the one where the tag
and the built wheel can disagree.

Nothing else happens: no changelog entry, no GitHub release, and
`.release-please-manifest.json` still says whatever it said before. The next
release-please run will bump from the manifest, not from your tag, so a
hand-pushed tag ahead of the stream produces a version that already exists.
Prefer letting the pipeline cut it.
