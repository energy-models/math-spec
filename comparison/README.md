<!--
SPDX-FileCopyrightText: math-spec Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Comparing the three lookup proposals

[Issue #275](https://github.com/energy-models/math-spec/issues/275) has three
open pull requests answering it, and exactly one of them is merged. This
directory holds the evidence for choosing, and the page that shows it:

| Proposal              | PR                                                        | Branch                            |
| --------------------- | --------------------------------------------------------- | --------------------------------- |
| `per:` conditioning   | [#428](https://github.com/energy-models/math-spec/pull/428) | `claude/lookup-per-keyword-vhvfjd` |
| keys and a dot        | [#433](https://github.com/energy-models/math-spec/pull/433) | `claude/lookup-keys-vhvfjd`        |
| relations             | [#437](https://github.com/energy-models/math-spec/pull/437) | `claude/lookup-relations-vhvfjd`   |

Five modelling problems are written three times, once per proposal, and each
file is loaded on the branch that proposes it. Two of the fifteen are refused,
and the refusal is the evidence.

- `models/p1` — a generator's zone changes by period.
- `models/p2` — the same map, walked from its other key.
- `models/p3` — nodal balance, where a line has two ends.
- `models/p4` — a capacity cap per bus and technology.
- `models/p5` — which regions are neighbours: a relation between two members of
  one dimension, which only #437 can declare.
- `probes/` — files that are refused, so the page can print the message.

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

This directory is a decision aid for one issue. Two of the three proposals close
as not planned once the choice is made, and this comparison closes with them.
Nothing here is proposed for `main`.
