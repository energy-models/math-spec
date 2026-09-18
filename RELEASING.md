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
                                       and publishes it to PyPI
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

The config is in sticky `prerelease` mode, so every release is
`0.0.1-alpha.N`, which is the distribution version `0.0.1aN`. The manifest
carries the base, and one thing moves it: a breaking change.

The base was `0.0.0` while the stream was pinned there. Under
`versioning: prerelease` a bump lands on the counter whenever the digits below
it are already zero, so at `0.0.0` a minor bump was absorbed and a breaking
marker changed nothing at all. At `0.0.1` the patch is not zero, so the minor
bump bites and one `feat!:` gives `0.1.0-alpha.N`.

None of these versions carries a semantic promise. The point of them is that an
early user always has a number to quote in a bug report, instead of a commit
SHA.

**Nothing is on PyPI yet.** The publish job in `build.yml` runs on every tag,
and waits on the trusted publisher in the PyPI note below. Until that exists,
the alpha stream produces tags, changelog entries and GitHub releases, and
nothing more.

Two consequences worth knowing:

- **`main` releases on every merge.** The last step of `release.yml` enables
  auto-merge on the release PR. That step is explicitly temporary, and it
  expires by itself. It reads the version off the PR title and refuses anything
  that is not a prerelease. So the first official version stops the automation,
  and nobody has to remember to do it. To pause it earlier, set the repository
  variable `AUTO_RELEASE` to `false`, and merge the release PRs by hand.
- **A breaking marker bumps the minor.** A `!` in the subject, or a
  `BREAKING CHANGE:` footer, moves the base from `0.0.1` to `0.1.0`, and the
  counter carries on rather than restarting. That is the one compatibility
  signal the stream has: the minor says a consumer has to change something, and
  the counter says nothing at all. `pr-title.yml` used to refuse the marker,
  because the base was pinned to `0.0.0` and a marker would have moved it off
  the stream unannounced. The base is no longer pinned, so the check no longer
  looks.

## Leaving the alpha stream

When the project is ready for a real version:

1. Delete the auto-merge step from `release.yml` (it is fenced by a comment
   banner).
2. Remove `versioning`, `prerelease` and `prerelease-type` from
   `.release-please-config.json`.
3. Set the manifest to the last version you want release-please to bump _from_.
4. Merge the next release PR by hand.

## One-time setup

The app is in place: release PRs are authored by
`energy-models-release-please[bot]`, so CI runs on them and a tag it pushes
builds. What is left is the branch rules and PyPI, below.

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

**PyPI.** The publish job in `build.yml` runs on every tag. What it needs on
PyPI's side is a project named `math-spec` and a trusted publisher pointing at
`build.yml` and the `pypi` environment, plus that environment on the
repository. **Do this before the next tag.** A tag reaches the job either way,
and without the publisher the upload fails on a rejected OIDC token.

The switch is deliberately not a repository variable. Anyone with write access
can set a repository variable, with no review, and this switch publishes under
the project's name. Turning it on, or off again, should cost a pull request.

`build.yml` also produces the wheel as an artifact, which needs the
release-please app above: a tag pushed by `GITHUB_TOKEN` starts no workflow, so
without the app a release has no artifact attached to it.

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
