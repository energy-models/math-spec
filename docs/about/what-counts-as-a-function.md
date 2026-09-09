<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# What counts as a function

Three pages divide up the question of what this project accepts.
[What counts as language](what-counts-as-language.md) says which rules belong
here. [The limits](limits.md) say which constructs are allowed to enter at
all. This page says which **functions** are allowed to enter.

The answer keeps the API small while the language becomes more capable. Without
it, the API grows one function per feature, until nobody can hold the whole API
in mind.

A function is admissible when both of these are true:

> Every decision the function makes is a decision the language has already
> stated. And the function needs nothing but the file to make that decision.

Each of the two clauses refuses something different.

The first clause refuses a function that holds a rule of its own. A rule with a
second home drifts away from the first home. A rule you can only reach by
calling a function is also a rule that a second consumer — another program that
reads a model, in any language — cannot implement.

The second clause refuses a function that needs data, a solver, a network, a
plugin or a clock. If the answer depends on something outside the file, the
function cannot be part of a contract about the file.

## What makes this API more capable

This package builds nothing and solves nothing. So its value is not what a
caller can call. It is what a **second consumer** can build on top of it.

A wide API that only one program uses is therefore worth less than a small API
that a dozen programs read.

So the largest capability this API can gain is not a function at all. It is the
`Program` becoming a value that another language can read. One serialisation
format, and every consumer outside Python stops needing its own implementation
of the language. Nothing else reaches as many consumers, and it adds nothing for
a caller to learn.

## Where the API grows

The usual way this package becomes more capable is a new **declaration**, not a
new function.

| The capability                                | What it cost the API |
| --------------------------------------------- | -------------------- |
| Regimes in one quantity (`cases:`)            | nothing              |
| A curve as facts (`piecewise:`)               | nothing              |
| A set a solver branches on (`sos:`)           | nothing              |
| Whether a missing row was meant (`coverage:`) | nothing              |
| Composition (`merge`)                         | one function         |

A capability that arrives as a declaration can be inspected, printed, diffed and
serialised. It gets those properties because they are properties of the file.
The same capability as a callback, a hook or a registry entry has none of them.
You cannot review it, you cannot typeset it, and it cannot cross into another
language. So a feature that can be a declaration is one.

## Three properties every function keeps

**Pure.** No state. No configuration that changes what a model means. No
registry, and no plugin system. The same file gives the same answer today and in a
year.

`symbols=` shows the shape a legitimate option takes. It changes how a model
_prints_ and changes nothing about what the model _says_. That is why the
typesetter is allowed such an option and the loader is not.

**Total at load.** Everything that can be decided without data is decided at
load. So a function either returns a value or raises an error that names the
rewrite. There is no third outcome, no half-built value, and no warning that a
caller can ignore into a wrong answer.

`Advice` is not a fourth outcome. It talks about a file that the language
accepts, and it never changes what the file means.

**Closed under composition.** The functions compose without the caller having to
know a correct order:

- Calling `to_spec` or `to_program` again returns the same object unchanged. If a caller does not know which of
  the two values they hold, they can call either one and get the right result.
- A composition function must also satisfy this. `merge` of a single fragment has
  to give back that fragment, and merging has to be associative. Because of
  those two properties, a library can ship a prelude that is already merged, a
  caller can merge it with their own fragments, and the result is the same as
  merging everything at once.

The third property is the easy one to lose, and one call shows nothing about it.
A function can wrap or reorder its output so that the answer is still correct
while the composition is not. Then merging a single fragment gives back
something slightly different from that fragment, and each level of nesting adds
another wrapper. So the function has to earn the property, rather than a
reviewer having to catch the failure.

## What a function must and must not decide

The test above runs both ways, and the second direction is what stops this page
from refusing every function that is new.

- A function must not decide something the language has not stated. `merge` is
  admissible only because the rules it implements are written down in
  [file shape](../reference/language/file.md) and not in its docstring. Those
  rules are a shared coordinate space, owned math, and summed objectives.
- A function must not take over what a consumer owns. Three questions are the
  consumer's: what its sink can take, how data binds, and which solver runs. A
  sink here is whatever a built model is handed to, such as a solver's API. A
  function that answered any of the three would make every consumer inherit the
  limits of one of them.
- The language must not refuse a function only because it is new. A pure
  function of the file that states no rule of its own costs nothing to add and
  nothing to keep. Refusing such a function on taste keeps a capability out for
  no stated reason.

## What this refuses, and will keep refusing

| Asked for                                         | Why                                                      |
| ------------------------------------------------- | -------------------------------------------------------- |
| A Python API for constructing models              | the model is the file you review and diff                |
| A hook, a callback, a registry, a plugin          | not reviewable, not printable, not serialisable          |
| A function that binds data or reaches a solver    | the second clause of the test; that work is a consumer's |
| A configuration that changes what a file means    | two callers would then read one file two ways            |
| A function whose answer a declaration could carry | the table above                                          |

## How this page could be shown wrong

Suppose somebody genuinely needs a capability, this test refuses it, and it
cannot be reshaped into a declaration. That is evidence against this page, not
an exception to it.

The limits keep their refusals as a ledger for the same reason. A rule that
nothing could show wrong is a preference, and not a rule.
