<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Releasing

[release-please](https://github.com/googleapis/release-please) cuts the
releases. It works from the conventional-commit subjects that land on `main`.
Merging the release PR is the one part done by hand.

## The pipeline

```text
PR title (conventional)  ──►  squash onto main
                                   │
                       release.yml │ release-please opens/updates a release PR
                                   ▼
                            "chore(main): release 0.0.1"
                                   │  you merge it
                                   ▼
                                tag v0.0.1   +   GitHub release
                                   │
                        build.yml  ▼  builds the wheel, checks it against the tag
                                       and publishes it to PyPI
```

Three files own it:

| File                            | Role                                                            |
| ------------------------------- | --------------------------------------------------------------- |
| `.release-please-config.json`   | the release type, the changelog sections and the version scheme |
| `.release-please-manifest.json` | the last released version. release-please rewrites this file    |
| `.github/workflows/release.yml` | runs release-please on every push to `main`                     |

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

## The version scheme

The version is below 1.0.0, and two keys in the config keep it there:

- `bump-minor-pre-major` — a breaking change bumps the **minor**, so a `feat!:`
  on `0.1.4` gives `0.2.0` and not `1.0.0`.
- `bump-patch-for-minor-pre-major` — a feature bumps the **patch**, so a
  feature and a fix both give `0.1.5`.

So below 1.0.0 the minor means _a consumer has to change something_, and the
patch means everything else. A breaking marker is how you ask for it: a `!` in
the subject, or a `BREAKING CHANGE:` footer.

The releases before this scheme are the `0.0.0-alpha.N` stream, which the
config pinned with `versioning: prerelease`. Those numbers promised nothing at
all, and they stay in the changelog as they are. The manifest names `0.0.0` as
the version to bump from, so the first release under the scheme is `0.0.1`, or
`0.1.0` if a breaking marker lands first.

**Nothing is on PyPI yet.** The publish job in `build.yml` runs on every tag,
and waits on the trusted publisher in the PyPI note below.

**`main` does not release on its own.** release-please opens the release PR and
it waits for you. The alpha stream auto-merged those PRs, and that step is gone
with the stream.

## Reaching 1.0.0

Remove `bump-minor-pre-major` and `bump-patch-for-minor-pre-major` from
`.release-please-config.json`. A breaking change then bumps the major and a
feature the minor, which is ordinary semver. Do it in the pull request that
argues the API is stable, because the promise cannot be withdrawn afterwards.

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
