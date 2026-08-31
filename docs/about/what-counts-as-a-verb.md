<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# What counts as a verb

[What counts as language](what-counts-as-language.md) says which rules belong
here. [The ceiling](ceiling.md) says which constructs may enter at all. This
says which **functions** may — and it is the page that decides whether the API
stays small while the language gets more capable, or grows a verb per feature
until nobody can hold it.

The test:

> **A verb is admissible iff every decision it makes is one the language has
> already stated, and iff it needs nothing but the file to make it.**

Two clauses, and each refuses a different thing. The first refuses a verb that
holds a rule of its own — because a rule with a second home drifts, and a rule
only reachable by calling a function is one a second consumer cannot implement.
The second refuses a verb that takes data, a solver, a network, a plugin or a
clock — because a function whose answer depends on something outside the file
cannot be part of a contract about the file.

## Capability is measured on the far side

The temptation with an API is to measure it by what a caller can call. That is
the wrong end. This package builds nothing and solves nothing, so what it is
worth is what a **second consumer** can build on it — and a wide surface only
one program uses is narrower, in the sense that matters, than a small one a
dozen programs read.

That is why the largest single capability this API can gain is not a verb at
all. It is the `Program` becoming a value another language can read: one
serialisation, and every consumer that is not Python stops needing a second
implementation of the language to exist. Nothing else on any list multiplies
like that, and it adds no surface a caller has to learn.

## Growth happens in the schema

The normal way this package gets more capable is a **declaration**, not a
function.

| The capability                                | What it cost the API |
| --------------------------------------------- | -------------------- |
| Regimes in one quantity (`cases:`)            | nothing              |
| A curve as facts (`piecewise:`)               | nothing              |
| A set a solver branches on (`sos:`)           | nothing              |
| Whether a missing row was meant (`coverage:`) | nothing              |
| Composition (`merge`)                         | one verb             |

A capability that arrives as a declaration is inspectable, printable, diffable
and serialisable, because those are properties of the file. The same capability
as a callback, a hook or a registry entry is none of them: it cannot be
reviewed, it cannot be typeset, and it cannot cross into another language. **A
feature that can be a declaration must be one.**

## Three properties every verb keeps

**Pure.** No state, no configuration that changes what a model means, no
registry, no plugin seam. The same file gives the same answer today and in a
year. `symbols=` is the shape a legitimate option takes — it changes how a model
_prints_ and nothing about what it _says_, which is why the typesetter may have
one and the loader may not.

**Total at load.** Everything decidable without data is decided, so a verb
either returns or raises naming the rewrite. There is no third outcome, no
partially-built value and no warning a caller may ignore into a wrong answer.
`Advice` is not a fourth outcome: it is about a file the language accepts, and
it never changes what the file means.

**Closed under composition.** The verbs compose without a caller having to know
an order:

- `to_spec` and `to_program` are idempotent — a caller who does not know which
  it holds may call either and be right.
- a composition verb answers to it too: `merge` of one fragment has to be that
  fragment, and merging has to be associative, so a library may ship a prelude
  already merged and a caller may merge it with their own fragments and reach
  what merging all of them at once reaches.

The third property is the one that is easy to lose and expensive to notice — a
verb can wrap or reorder its output so the answer stays right while the
composition does not, and composing one fragment comes back differing from the
fragment, every nesting adding another pair. Nothing about a single call shows
it, which is why the property is a verb's to earn rather than a reviewer's to
catch.

## The sharp edge

The test cuts both ways, and the second cut is what keeps this page from being
a fence around a museum.

- A verb **may not** decide something the language has not stated. `merge`
  passes only because the rules it implements — a shared coordinate space, owned
  math, summed objectives — are written in
  [file shape](../reference/language/file.md) and not in its docstring.
- A verb **may not** take what a consumer owns. What a sink can ingest, how data
  binds, which solver runs: a function here that answered any of those would
  make every consumer inherit one consumer's limits.
- But the language **may not** refuse a verb merely for being new. A pure
  function of the file that states no rule of its own costs nothing to have and
  nothing to keep, and refusing one on taste is how an API becomes a lecture.

## What this refuses, and will keep refusing

| Asked for                                      | Why                                                      |
| ---------------------------------------------- | -------------------------------------------------------- |
| A Python API for constructing models           | hard rule 5 — the model is the file you review and diff  |
| A hook, a callback, a registry, a plugin       | not reviewable, not printable, not serialisable          |
| A verb that binds data or reaches a solver     | the second clause of the test; that work is a consumer's |
| A configuration that changes what a file means | two callers would then read one file two ways            |
| A verb whose answer a declaration could carry  | the table above                                          |

## It is a claim, so it can be falsified

A capability somebody genuinely needs, which this test refuses, and which cannot
be reshaped into a declaration, is a row against this page rather than an
exception to it. The ceiling carries its refusals as a ledger for the same
reason: a rule with no way to be wrong is a preference wearing a rule's clothes.
