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
maintains `CHANGELOG.md`, the manifest, and the tag, and nothing else. It does
not have to: `pyproject.toml` declares `dynamic = ["version"]` and
`[tool.hatch.version] source = "vcs"`, so hatch-vcs reads the tag at build time.
The tag is the whole interface between them, and neither workflow needs to know
the other exists.

(`simple` also declares a `version.txt` updater, but with `createIfMissing:
false`. There is no `version.txt` in this repo and none will be created.)

## The alpha stream

The manifest is seeded at `0.0.0-alpha.0` and the config is in sticky
`prerelease` mode, so every release is `0.0.0-alpha.N` — dist version `0.0.0aN`.
The seed is what pins the `0.0.0`: release-please only increments the counter
when the version it starts from already carries a prerelease. From a plain
`0.0.0` it would bump the patch first and the stream would be `0.0.1-alpha.N`.

There is no semantic promise attached to any of them; the point is that an early
user always has a number to quote in a bug report instead of a commit sha.

**Nothing is published.** `PUBLISH_TO_PYPI` is unset, so `build.yml`'s publish
job cannot run — see the PyPI note below. The alpha stream produces tags,
changelog entries and GitHub releases only.

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

**Do them in this order.** The app has to exist before `main` requires any
status check, and the two are not independent: release-please opens its release
PR with whatever token it was given, and a `GITHUB_TOKEN`-authored PR triggers
no workflows at all. Require `CI` first and the release PR waits on a check that
never starts, auto-merge waits with it, and the alpha stream stops dead. With
the app, the PR is authored by the app and runs CI like any other.

`scripts/setup-release-app.sh` walks the app half and stops deliberately short
of the branch rules.

**A GitHub App for release-please.** A `GITHUB_TOKEN`-authored PR does not
trigger CI, and a `GITHUB_TOKEN`-pushed tag does not trigger `build.yml`. With
no app the release PR is opened but never built, and `release.yml` emits a
warning saying so. Create an app with `contents: write` and `pull_requests:
write` — exactly what `release.yml` asks the token for, and the action can only
narrow that, never widen it.

It is installed across the whole `energy-models` organisation and its two
secrets live at organisation level. Writing those needs `admin:org` on the
token, which owning the organisation does not give you — the scopes a default
`gh auth login` asks for stop at `read:org`:

```bash
gh auth refresh -h github.com -s admin:org

gh secret set APP_CLIENT_ID   --org energy-models --visibility all --body 'Iv23li...'
gh secret set APP_PRIVATE_KEY --org energy-models --visibility all < ~/Downloads/*.private-key.pem
```

So the second repository to adopt release-please needs no new app and no new
key. The cost is blast radius — one key that can write contents and pull
requests anywhere in the organisation — and the rule that a _repository_ secret
of the same name silently wins over the organisation one. Do not set these on
`math-spec` as well; there would be two copies to rotate and only one of them
would be in use.

**"Allow auto-merge" on the repository.** Required by the temporary alpha step;
without it that step fails.

**Branch protection on `main`.** Squash-only merges, and require the `CI` and
`Conventional commit subject` checks. Auto-merge is what makes the release PR
wait for them.

Last, and only once a release PR has been seen running CI under the app — see
the ordering note above. The `main` ruleset already exists with everything but
the checks, so this adds them to it:

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

(`15368` is the GitHub Actions app id, so each context resolves to a workflow in
this repository rather than any check that happens to share the name.)

**PyPI.** The publish job is gated on the repository variable
`PUBLISH_TO_PYPI`. Configure a trusted publisher for `math-spec` pointing at
`build.yml` and the `pypi` environment, then set the variable to `true`.

Until then nothing reaches PyPI, and the gate fails closed: the variable is
unset, so the job's `if` cannot be true. The rest of the pipeline still runs —
release-please cuts the tag, the changelog and the GitHub release. `build.yml`
produces the wheel as an artifact too, but only once the release-please app
above exists; a `GITHUB_TOKEN`-pushed tag starts no workflow, so until then a
release has no artifact attached to it.

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
reads the version from `git describe`, so the tag _is_ what the wheel is built
as, and the two cannot disagree.

Nothing else happens: no changelog entry, no GitHub release, and
`.release-please-manifest.json` still says whatever it said before. The next
release-please run will bump from the manifest, not from your tag, so a
hand-pushed tag ahead of the stream produces a version that already exists.
Prefer letting the pipeline cut it.
