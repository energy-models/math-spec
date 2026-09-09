<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# What counts as a function

[What counts as language](what-counts-as-language.md) says which rules belong
here. [The limits](limits.md) say which constructs may enter. This page says
which **functions** may enter the public API, and it keeps the API small while
the language becomes more capable.

A function is admissible when both of these are true:

> Every decision the function makes is a decision the language has already
> stated. And the function needs nothing but the file to make that decision.

The first clause refuses a function that holds a rule of its own. A rule with a
second home drifts from the first, and a rule reachable only by calling a function
is one that a second consumer, in any language, cannot implement. The second
clause refuses a function that needs data, a solver, a network, a plugin or a
clock. If the answer depends on something outside the file, the function cannot
be part of a contract about the file.

## What makes this API more capable

This package builds nothing and solves nothing. Its value is what a **second
consumer** can build on top of it, so a small API that a dozen programs read is
worth more than a wide one that one program uses.

The largest capability this API can gain is not a function. It is the `Program`
becoming a value that another language can read: one serialisation format, and
every consumer outside Python stops needing its own implementation of the
language.

## Where the API grows

The usual way this package becomes more capable is a new **declaration**, not a
new function. `cases:`, `piecewise:` and `sos:` each cost the API nothing. A
capability that arrives as a declaration can be inspected, printed, diffed and
serialised, because those are properties of the file. The same capability as a
callback, a hook or a registry entry has none of them. So a feature that can be a
declaration is one.

## Three properties every function keeps

- **Pure.** No state, no registry, no plugin system, and no configuration that
  changes what a model means. `symbols=` shows the shape a legitimate option
  takes: it changes how a model prints and nothing about what it says, which is
  why the typesetter takes such an option and the loader does not.
- **Total at load.** A function either returns a value or raises an error that
  names the rewrite. There is no half-built value, and no warning a caller can
  ignore into a wrong answer. `Advice` is not a third outcome: it talks about a
  file the language accepts, and never changes what the file means.
- **Closed under composition.** Calling `to_spec` or `to_program` on its own
  result returns the same object unchanged, so a caller that does not know which
  value it holds can call either one. A function that combines fragments would
  have to give a single fragment back unchanged and combine associatively, and
  one call shows nothing about that property, so the function has to earn it in
  its tests.

## What a function must and must not decide

- A function must not decide something the language has not stated.
- A function must not take over what a consumer owns. Three questions are the
  consumer's: what its **sink** can take, which is the solver API or file format
  a built model is handed to; how data binds; and which solver runs. A function
  that answered any of them would make every consumer inherit one consumer's
  limits.
- The language must not refuse a function only because it is new. A pure
  function of the file that states no rule of its own costs nothing to add and
  nothing to keep.

## What this refuses

| Asked for                                         | Why                                                            |
| ------------------------------------------------- | -------------------------------------------------------------- |
| A Python API for constructing models              | the model is the file you review and diff                      |
| A hook, a callback, a registry, a plugin          | not reviewable, not printable, not serialisable                |
| A function that binds data or reaches a solver    | the second clause of the test; that work is a consumer's       |
| A configuration that changes what a file means    | two callers would then read one file two ways                  |
| A function whose answer a declaration could carry | a declaration can be inspected, printed, diffed and serialised |

A capability that somebody needs, that this test refuses, and that cannot be
reshaped into a declaration is evidence against this page, not an exception to
it. A rule that nothing could show wrong is a preference.
