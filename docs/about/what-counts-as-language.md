<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# What counts as language

This page decides which rules belong to the language and which to a consumer.
The test:

> **A rule is language iff two consumers answering it separately would be a
> bug.**

Not "is it about syntax", not "does it run early": _would a second opinion be
wrong?_ A model file is read by more than one thing. An engine builds it, a
renderer prints it, a checker judges it without data. Where two of
them could reach different answers and both be defensible, the question is
theirs. Where two different answers would mean the file meant two things, the
question is the language's, and exactly one implementation of it may exist.

So names resolve once, the operator set is closed, an operator's dim rule has
a single home that consumers **ask** rather than re-derive, and degree is
decided before any plan exists. Nothing about `x * y` is relational. A
formulation that emits declarations is language too, because declarations are.

## The test cuts the other way

A consumer may refuse what its own representation cannot hold: an offset that
must be a literal, a grouping that must name a declared lookup, a set a solver
has no concept of. A second opinion about those is not a bug. Forcing them into
the language would make every consumer inherit the narrowest one's limits.

So the rule has a sharp edge on both sides:

- A consumer may not state a rule about the **language** that another consumer
  then has to restate.
- The language may not state a rule about what a **consumer** can represent.

A refusal that fails the first test is a language error. One that fails the
second is the consumer saying so in its own words. So _accepting is not
building_: a model every reader accepts may still meet a wall inside one of
them.

## Beside the ceiling

[The ceiling](ceiling.md) says **what may enter the language at all**: the
triage into macro, primitive or escape, and the intersection a primitive has to
sit inside. This page says **who owns a rule once it is in**: the language, or
one consumer.

A construct can pass the ceiling and still not be the language's business, and
a rule can be the language's while the construct it governs is refused
outright. Asked to place something new, ask both questions, in that order.
