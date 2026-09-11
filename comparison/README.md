<!--
SPDX-FileCopyrightText: math-spec Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Comparing the three lookup proposals

[Issue #275](https://github.com/energy-models/math-spec/issues/275) has three
open pull requests answering it, and exactly one of them is merged. This
directory holds the evidence for choosing, and the page that shows it:

| Proposal            | PR                                                          | Branch                             |
| ------------------- | ----------------------------------------------------------- | ---------------------------------- |
| `per:` conditioning | [#428](https://github.com/energy-models/math-spec/pull/428) | `claude/lookup-per-keyword-vhvfjd` |
| keys and a dot      | [#433](https://github.com/energy-models/math-spec/pull/433) | `claude/lookup-keys-vhvfjd`        |
| relations           | [#437](https://github.com/energy-models/math-spec/pull/437) | `claude/lookup-relations-vhvfjd`   |

Five modelling problems are written three times, once per proposal, and each
file is loaded on the branch that proposes it. Two of the fifteen are refused,
and the refusal is the evidence.

- `models/p1` — a generator's zone changes by period.
- `models/p2` — the same map, walked from its other key.
- `models/p3` — nodal balance, where a line has two ends.
- `models/p4` — a capacity cap per bus and technology.
- `models/p5` — which regions are neighbours: a relation between two members of
  one dimension, which only #437 can declare.
- `probes/` — single files loaded on every branch: the refusals the page prints,
  and the one file every proposal takes unchanged.

## Reading it

`comparison/index.html` is a standalone page. It needs no build step and no
server: download it and open it in a browser, or open your checkout's copy
directly.

```bash
git switch claude/mathspec-proposals-comparison-ebn7dv
open comparison/index.html      # xdg-open on Linux, start on Windows
```

GitHub shows the file as source rather than rendering it. A raw-HTML viewer
renders it from the branch without a checkout, for example
[raw.githack.com](https://raw.githack.com/energy-models/math-spec/claude/mathspec-proposals-comparison-ebn7dv/comparison/index.html).

Such a viewer caches a branch URL, so it can serve a page older than the branch
head. The page stamps the time it was built in its header and its footer, so
compare that with the last commit before you read it. To force a fresh copy,
add any query string to the URL, such as `?v=2`, which the cache reads as a
different page. A commit hash in place of the branch name never goes stale, and
never updates either.

The page fetches MathJax and two typefaces from public CDNs. Without a network
the equations stay as TeX source and the type falls back, and everything else
reads as it should.

## Rebuilding

```bash
python comparison/verify.py   # fetches all three branches, loads every file, writes evidence.json
python comparison/build.py    # writes index.html from evidence.json and template.html
```

`verify.py` makes a worktree per branch and loads each model in a child
interpreter, because the three branches define incompatible `lookups:` schemas
and cannot share one. It needs an interpreter with this package's runtime
dependencies installed, and it removes the worktrees again unless you pass
`--keep`.

`index.html` and `evidence.json` are written by those two scripts. Edit
`template.html` or the models, never the output.

## Not for `main`

This directory is a decision aid for one issue. Its pull request is a review
surface, so the models and the prose can take line comments. It is not a
proposal to merge. Two of the three proposals close as not planned once the
choice is made, and this comparison closes with them.
