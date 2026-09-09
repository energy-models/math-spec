<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# What counts as a verb

Three pages divide up the question of what this project accepts.
[What counts as language](what-counts-as-language.md) says which rules belong
here. [The ceiling](ceiling.md) says which constructs are allowed to enter at
all. This page says which **functions** are allowed to enter.

This page decides whether the API stays small while the language becomes more
capable, or whether it grows one verb per feature until nobody can hold the
whole surface in mind.

The test:

> **A verb is admissible if and only if two things are true. Every decision it
> makes is a decision the language has already stated. And it needs nothing but
> the file to make that decision.**

Each of the two clauses refuses something different.

The first clause refuses a verb that holds a rule of its own. A rule with a
second home will drift away from the first home. Worse, a rule you can only
reach by calling a function is a rule that a second consumer cannot implement.

The second clause refuses a verb that needs data, a solver, a network, a plugin
or a clock. If the answer depends on something outside the file, the function
cannot be part of a contract about the file.

## Capability is measured on the far side

It is tempting to measure an API by what a caller can call. That is the wrong
end to measure from. This package builds nothing and solves nothing. Its value
is what a **second consumer** can build on top of it.

So a wide surface that only one program uses is narrower, in the way that
matters, than a small surface that a dozen programs read.

This is why the largest capability this API can gain is not a verb at all. It is
the `Program` becoming a value that another language can read. One
serialisation format, and every consumer outside Python stops needing its own
implementation of the language. Nothing else has that multiplier, and it adds
nothing for a caller to learn.

## Growth happens in the schema

The usual way this package becomes more capable is a new **declaration**, not a
new function.

| The capability                                | What it cost the API |
| --------------------------------------------- | -------------------- |
| Regimes in one quantity (`cases:`)            | nothing              |
| A curve as facts (`piecewise:`)               | nothing              |
| A set a solver branches on (`sos:`)           | nothing              |
| Whether a missing row was meant (`coverage:`) | nothing              |
| Composition (`merge`)                         | one verb             |

A capability that arrives as a declaration can be inspected, printed, diffed and
serialised. It gets those properties because they are properties of the file.
The same capability as a callback, a hook or a registry entry has none of them.
You cannot review it, you cannot typeset it, and it cannot cross into another
language. **If a feature can be a declaration, it must be one.**

## Three properties every verb keeps

**Pure.** No state. No configuration that changes what a model means. No
registry, and no plugin seam. The same file gives the same answer today and in a
year.

`symbols=` shows the shape a legitimate option takes. It changes how a model
_prints_ and changes nothing about what the model _says_. That is why the
typesetter is allowed such an option and the loader is not.

**Total at load.** Everything that can be decided without data is decided at
load. So a verb either returns a value or raises an error that names the
rewrite. There is no third outcome, no half-built value, and no warning that a
caller can ignore into a wrong answer.

`Advice` is not a fourth outcome. It talks about a file that the language
accepts, and it never changes what the file means.

**Closed under composition.** The verbs compose without the caller having to
know a correct order:

- `to_spec` and `to_program` are idempotent. If a caller does not know which of
  the two values they hold, they can call either one and get the right result.
- A composition verb must also satisfy this. `merge` of a single fragment has
  to give back that fragment, and merging has to be associative. Because of
  those two properties, a library can ship a prelude that is already merged, a
  caller can merge it with their own fragments, and the result is the same as
  merging everything at once.

The third property is the easy one to lose and the expensive one to notice. A
verb can wrap or reorder its output so that the answer is still correct while
the composition is not. Then merging a single fragment gives back something
slightly different from that fragment, and each level of nesting adds another
wrapper. Nothing about one call shows this. That is why the verb has to earn the
property, rather than a reviewer having to catch the failure.

## The test also works in reverse

The test cuts both ways. The second cut is what stops this page from being a
fence around a museum.

- A verb **must not** decide something the language has not stated. `merge` is
  admissible only because the rules it implements are written down in
  [file shape](../reference/language/file.md) and not in its docstring. Those
  rules are a shared coordinate space, owned math, and summed objectives.
- A verb **must not** take over what a consumer owns. What a sink can ingest,
  how data binds, and which solver runs all belong to the consumer. A function
  here that answered any of those questions would make every consumer inherit
  the limits of one consumer.
- But the language **must not** refuse a verb only because it is new. A pure
  function of the file that states no rule of its own costs nothing to add and
  nothing to keep. Refusing such a verb on taste is how an API turns into a
  lecture.

## What this refuses, and will keep refusing

| Asked for                                      | Why                                                      |
| ---------------------------------------------- | -------------------------------------------------------- |
| A Python API for constructing models           | hard rule 5 — the model is the file you review and diff  |
| A hook, a callback, a registry, a plugin       | not reviewable, not printable, not serialisable          |
| A verb that binds data or reaches a solver     | the second clause of the test; that work is a consumer's |
| A configuration that changes what a file means | two callers would then read one file two ways            |
| A verb whose answer a declaration could carry  | the table above                                          |

## It is a claim, so it can be falsified

Suppose somebody genuinely needs a capability, this test refuses it, and it
cannot be reshaped into a declaration. That is evidence against this page, not
an exception to it.

The ceiling keeps its refusals as a ledger for the same reason. A rule with no
way to be wrong is a preference in a rule's clothing.
