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
changelog and the GitHub release, and `build.yml` produces a
wheel as a build artifact. Only the upload is skipped.

## What CI proves, and what it does not

`ci.yml` runs on the declared floor, Python 3.12, and only there. If the package
works on the oldest supported interpreter it almost certainly works on the newer
ones, and the common real breakage — reaching for a stdlib feature newer than the
floor — is exactly what a floor-pinned job catches. The cost is that the 3.13 and
3.14 classifiers in `pyproject.toml` are untested claims. That is an acceptable
trade while the project is pre-1.0; raise it if a user reports a version-specific
break, not on principle.

## Cutting a release by hand

Push a tag. `build.yml` reacts to any tag, so
`git tag v0.1.0 && git push origin v0.1.0` builds and (if enabled) publishes it.
Nothing has to be kept in step by hand: `[tool.hatch.version] source = "vcs"`
reads the version from `git describe`, so the tag *is* what the wheel is built
as, and the two cannot disagree.

Nothing else happens: no changelog entry, no GitHub release, and
`.release-please-manifest.json` still says whatever it said before. The next
release-please run will bump from the manifest, not from your tag, so a
hand-pushed tag ahead of the stream produces a version that already exists.
Prefer letting the pipeline cut it.
