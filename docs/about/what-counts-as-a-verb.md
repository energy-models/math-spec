<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# What counts as a verb

This page decides which **functions** the API may gain.
[What counts as language](what-counts-as-language.md) says which rules belong
here; [the ceiling](ceiling.md) says which constructs may enter at all.

The test:

> **A verb is admissible iff every decision it makes is one the language has
> already stated, and iff it needs nothing but the file to make it.**

The first clause refuses a verb that holds a rule of its own. A rule with a
second home drifts, and a rule reachable only by calling a function is one a
second consumer cannot implement. The second clause refuses a verb that takes
data, a solver, a network, a plugin or a clock. A function whose answer depends
on something outside the file cannot be part of a contract about the file.

## Capability is measured on the far side

This package builds nothing and solves nothing, so its worth is what a
**second consumer** can build on it. A wide surface only one program uses is
narrower than a small one a dozen programs read.

So the largest single capability this API can gain is not a verb. It is the
`Program` becoming a value another language can read: one serialisation, and a
consumer that is not Python no longer needs a second implementation of the
language. It adds no surface a caller has to learn.

## Growth happens in the schema

This package gets more capable through a **declaration**, not a function.

| The capability                                | What it cost the API |
| --------------------------------------------- | -------------------- |
| Regimes in one quantity (`cases:`)            | nothing              |
| A curve as facts (`piecewise:`)               | nothing              |
| A set a solver branches on (`sos:`)           | nothing              |
| Whether a missing row was meant (`coverage:`) | nothing              |
| Composition (`merge`)                         | one verb             |

A capability that arrives as a declaration is inspectable, printable, diffable
and serialisable, because those are properties of the file. The same capability
as a callback, a hook or a registry entry cannot be reviewed, typeset or read
from another language. **A feature that can be a declaration must be one.**

## Three properties every verb keeps

**Pure.** No state, no configuration that changes what a model means, no
registry, no plugin seam. The same file gives the same answer today and in a
year. `symbols=` is the shape a legitimate option takes: it changes how a model
_prints_ and nothing about what it _says_. So the typesetter may have one and
the loader may not.

**Total at load.** Everything decidable without data is decided, so a verb
either returns or raises naming the rewrite. There is no third outcome, no
partially built value and no warning a caller may ignore into a wrong answer.
`Advice` is not a third outcome either: it is about a file the language
accepts, and it never changes what the file means.

**Closed under composition.** The verbs compose without a caller having to know
an order:

- `to_spec` and `to_program` are idempotent: a caller who does not know which
  it holds may call either and be right.
- `merge` of one fragment is that fragment, and merging is associative. So a
  library may ship a prelude already merged, and a caller who merges it with
  their own fragments reaches what merging all of them at once reaches.

The third property is easy to lose and expensive to notice. A verb can wrap or
reorder its output so the answer stays right while the composition does not,
and nothing about a single call shows it. So the property is a verb's to earn
rather than a reviewer's to catch.

## The sharp edge

The test cuts both ways.

- A verb **may not** decide something the language has not stated. `merge`
  passes only because the rules it implements (a shared coordinate space, owned
  math, summed objectives) are written in
  [the file](../reference/language/index.md#the-file) and not in its docstring.
- A verb **may not** take what a consumer owns. What a sink can ingest, how data
  binds, which solver runs: a function here that answered any of those would
  make every consumer inherit one consumer's limits.
- The language **may not** refuse a verb merely for being new. A pure function
  of the file that states no rule of its own costs nothing to have and nothing
  to keep.

## What this refuses, and will keep refusing

| Asked for                                      | Why                                                      |
| ---------------------------------------------- | -------------------------------------------------------- |
| A Python API for constructing models           | hard rule 5 — the model is the file you review and diff  |
| A hook, a callback, a registry, a plugin       | not reviewable, not printable, not serialisable          |
| A verb that binds data or reaches a solver     | the second clause of the test; that work is a consumer's |
| A configuration that changes what a file means | two callers would then read one file two ways            |
| A verb whose answer a declaration could carry  | the table above                                          |

## It is a claim, so it can be falsified

A capability somebody needs, which this test refuses, and which cannot be
reshaped into a declaration, is a row against this page rather than an
exception to it. The ceiling carries its refusals as a ledger for the same
reason: a rule with no way to be wrong is a preference wearing a rule's
clothes.
