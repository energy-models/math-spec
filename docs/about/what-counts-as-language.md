# What counts as language

A fence says what may not happen; it does not say what belongs. The test is:

> **A rule is language iff two consumers answering it separately would be a
> bug.**

Not "is it about syntax", not "does it run early" — _would a second opinion be
wrong?_ A model file is read by more than one thing: an engine that builds it, a
renderer that prints it, a checker that judges it without data. Wherever two of
them could reach different answers and both be defensible, the question is
theirs. Wherever two different answers would mean the file meant two things, the
question is the language's, and exactly one implementation of it may exist.

That is why names resolve once, the operator set is closed, an operator's dim
rule has a single home that consumers **ask** rather than re-derive, and degree
is decided before any plan exists. Nothing about `x * y` is relational. A
formulation that emits declarations is language too, because declarations are.

## The test cuts the other way

This is what keeps it from swallowing everything. A consumer legitimately
refuses what its own representation cannot hold — an offset that must be a
literal, a grouping that must name a declared lookup, a set a solver has no
concept of. A second opinion about those is not a bug; it is the other
consumer's own business, and forcing them into the language would make every
consumer inherit the narrowest one's limits.

So the rule has a sharp edge on both sides:

- A consumer may not state a rule about the **language** that another consumer
  then has to restate.
- The language may not state a rule about what a **consumer** can represent.

A refusal that fails the first test is a language error. One that fails the
second is the consumer saying so in its own words — which is why _accepting is
not building_, and why a model every reader accepts may still meet a wall inside
one of them.

## Beside the ceiling

[The ceiling](ceiling.md) answers a different question and they are easy to
confuse. The ceiling says **what may enter the language at all** — the triage
into macro, primitive or escape, and the intersection a primitive has to sit
inside. This says **who owns a rule once it is in**: the language, or one
consumer.

A construct can pass the ceiling and still not be the language's business, and a
rule can be plainly the language's while the construct it governs is refused
outright. Asked to place something new, both questions get asked, in that order.
