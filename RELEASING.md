<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Releasing

[release-please](https://github.com/googleapis/release-please) cuts the
releases. It works from the conventional-commit subjects that land on `main`.
While the project is on the alpha stream, no part of a release is done by
hand.

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

| File                            | Role                                                           |
| ------------------------------- | -------------------------------------------------------------- |
| `.release-please-config.json`   | the release type, the changelog sections, and the alpha stream |
| `.release-please-manifest.json` | the last released version. release-please rewrites this file   |
| `.github/workflows/release.yml` | runs release-please on every push to `main`                    |

`.github/workflows/pr-title.yml` guards the input.
`.github/workflows/build.yml` consumes the output.

## Why release-please and `pyproject.toml` need no glue

`release-type` is `simple`, and `simple` never touches `pyproject.toml`.
release-please maintains `CHANGELOG.md`, the manifest and the tag, and nothing
else.

It does not need to touch `pyproject.toml`, because `pyproject.toml` declares
`dynamic = ["version"]` and `[tool.hatch.version] source = "vcs"`. So hatch-vcs
reads the tag at build time. The tag is the whole interface between the two
halves, and neither workflow needs to know that the other exists.

Note that `simple` also declares a `version.txt` updater, but with
`createIfMissing: false`. There is no `version.txt` in this repository, and none
will be created.

## The alpha stream

The manifest is seeded at `0.0.0-alpha.0`, and the config is in sticky
`prerelease` mode. So every release is `0.0.0-alpha.N`, which is the
distribution version `0.0.0aN`.

The seed is what pins the `0.0.0`. release-please increments the counter only
when the version it starts from already carries a prerelease. From a plain
`0.0.0` it would bump the patch first, and the stream would be
`0.0.1-alpha.N`.

None of these versions carries a semantic promise. The point of them is that an
early user always has a number to quote in a bug report, instead of a commit
SHA.

**Nothing is published.** The publish job in `build.yml` is `if: false`. See the
PyPI note below. The alpha stream produces tags, changelog entries and GitHub
releases, and nothing more.

Two consequences worth knowing:

- **`main` releases on every merge.** The last step of `release.yml` enables
  auto-merge on the release PR. That step is explicitly temporary, and it
  expires by itself. It reads the version off the PR title and refuses anything
  that is not a prerelease. So the first official version stops the automation,
  and nobody has to remember to do it. To pause it earlier, set the repository
  variable `AUTO_RELEASE` to `false`, and merge the release PRs by hand.
- **Breaking markers are refused.** A `!` in the subject, or a
  `BREAKING CHANGE:` footer, moves the _base_ version rather than the counter.
  Under `versioning: prerelease`, a zero patch is an absorbing state. So at
  `0.0.0` a breaking marker is currently harmless. But that immunity disappears
  the moment the stream moves, and then one `feat!:` turns `0.0.1-alpha.12`
  into `0.1.0-alpha.12`. So `pr-title.yml` refuses the marker. Describe the
  break in the PR body instead. The alpha stream carries no compatibility
  promise, so there is nothing for the version to announce.

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

These steps are not done yet. Until they are, the workflows are either inert or
degraded.

**Do them in this order.** The app has to exist before `main` requires any
status check, and the two are not independent.

release-please opens its release PR with whatever token it was given, and a PR
authored by `GITHUB_TOKEN` triggers no workflows at all. So if you require `CI`
first, the release PR waits on a check that never starts, auto-merge waits with
it, and the alpha stream stops dead. With the app in place, the app authors the
PR, and it runs CI like any other PR.

`scripts/setup-release-app.sh` walks through the app half, and stops
deliberately short of the branch rules.

**A GitHub App for release-please.** A PR authored by `GITHUB_TOKEN` does not
trigger CI, and a tag pushed by `GITHUB_TOKEN` does not trigger `build.yml`.
With no app, the release PR is opened but never built, and `release.yml` emits a
warning that says so.

Create an app with `contents: write` and `pull_requests: write`. That is exactly
what `release.yml` asks the token for, and the action can only narrow those
permissions, never widen them.

The app is installed across the whole `energy-models` organisation, and its two
secrets live at organisation level. Writing those secrets needs `admin:org` on
your token. Owning the organisation does not give you that scope, because the
scopes a default `gh auth login` asks for stop at `read:org`:

```bash
gh auth refresh -h github.com -s admin:org

gh secret set APP_CLIENT_ID   --org energy-models --visibility all --body 'Iv23li...'
gh secret set APP_PRIVATE_KEY --org energy-models --visibility all < ~/Downloads/*.private-key.pem
```

So the second repository to adopt release-please needs no new app and no new
key.

That convenience has two costs. The first is blast radius: one key can write
contents and pull requests anywhere in the organisation. The second is that a
_repository_ secret of the same name silently wins over the organisation one. So
do not set these secrets on `math-spec` as well. You would then have two copies
to rotate, and only one of them would be in use.

**"Allow auto-merge" on the repository.** The temporary alpha step requires
this. Without it, that step fails.

**Branch protection on `main`.** Use squash-only merges, and require the `CI`
and `Conventional commit subject` checks. Auto-merge is what makes the release
PR wait for them.

Do this last, and only once you have seen a release PR run CI under the app. See
the ordering note above. The `main` ruleset already exists with everything
except the checks, so this command adds them to it:

```bash
ID=$(gh api repos/energy-models/math-spec/rulesets --jq '.[]|select(.name=="main")|.id')
gh api "repos/energy-models/math-spec/rulesets/$ID" --jq '.rules' | python3 -c '
import json, sys
rules = json.load(sys.stdin)
rules.append({"type": "required_status_checks", "parameters": {
    "required_status_checks": [
        {"context": "CI", "integration_id": 15368},
        {"context": "Conventional commit subject", "integration_id": 15368},
    ],
    "strict_required_status_checks_policy": False,
    "do_not_enforce_on_create": False}})
json.dump({"rules": rules}, sys.stdout)' > /tmp/ruleset.json
gh api -X PATCH "repos/energy-models/math-spec/rulesets/$ID" --input /tmp/ruleset.json
```

Note that `15368` is the app id of GitHub Actions. It makes each context
resolve to a workflow in this repository, rather than to any check that happens
to share the name.

**PyPI.** The publish job in `build.yml` is `if: false`. To enable publishing,
register `math-spec` on PyPI, configure a trusted publisher that points at
`build.yml` and the `pypi` environment, then restore the tag condition,
`startsWith(github.ref, 'refs/tags/')`, in the same pull request that explains
why.

This is deliberately not a repository variable. Anyone with write access can set
a repository variable, with no review, and this switch publishes under the
project's name. Turning it on should cost a pull request.

Until then, nothing reaches PyPI. The rest of the pipeline still runs, so
release-please cuts the tag, the changelog and the GitHub release.

`build.yml` also produces the wheel as an artifact, but only once the
release-please app above exists. A tag pushed by `GITHUB_TOKEN` starts no
workflow, so until the app exists, a release has no artifact attached to it.

## What CI proves, and what it does not

`ci.yml` runs on the declared floor, Python 3.12, and only there.

If the package works on the oldest supported interpreter, it almost certainly
works on the newer ones. And the breakage that really happens is reaching for a
standard-library feature newer than the floor, which is exactly what a
floor-pinned job catches.

The cost is that the 3.13 and 3.14 classifiers in `pyproject.toml` are untested
claims. That is an acceptable trade while the project is before 1.0. Raise the
question if a user reports a version-specific break, and not on principle.

## Cutting a release by hand

Push a tag. `build.yml` reacts to any tag, so
`git tag v0.1.0 && git push origin v0.1.0` builds the wheel and, if publishing
is enabled, publishes it.

You do not have to keep anything in step by hand.
`[tool.hatch.version] source = "vcs"` reads the version from `git describe`. So
the tag _is_ what the wheel is built as, and the two cannot disagree.

Nothing else happens. There is no changelog entry, no GitHub release, and
`.release-please-manifest.json` still says whatever it said before.

The next release-please run bumps from the manifest, not from your tag. So a
hand-pushed tag that is ahead of the stream produces a version that already
exists. Prefer to let the pipeline cut the release.
