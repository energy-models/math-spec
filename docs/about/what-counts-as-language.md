<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# What counts as language

More than one program reads a model file. Those programs are the model's
**consumers**: an engine that builds it, a renderer that prints it, a checker
that judges it without data. One question decides which rules belong to the
language and which belong to a consumer:

> A rule belongs to the language when it would be a bug for two consumers to
> answer it separately.

Whether the rule is about syntax does not decide it, and neither does whether it
applies before the model runs. Where two consumers can reasonably give different
answers, the question belongs to each of them. Where two different answers would
mean the file says two different things, the question belongs to the language,
and one answer is allowed.

Four rules follow from that:

- A name resolves once.
- The set of operators is closed.
- The dimension rule for an operator has one home. A consumer asks for the
  answer instead of working it out again.
- Degree is decided when the file loads. Whether `x * y` is allowed does not
  depend on what builds the model.

A block that expands into declarations, such as `piecewise:`, is part of the
language too, because the declarations it emits are.

## Which rules belong to one consumer

The question runs the other way as well, and that stops it from pulling in
everything. A consumer can refuse a model because its own representation cannot
hold what the model asks for: an offset that must be a literal, a grouping that
must name a lookup declared already, a set that the solver has no concept of. A
second opinion about such a limit is not a bug. If the limit moved into the
language, every consumer would inherit the limits of the most restricted one.

So two rules follow, one for each side:

- A consumer must not state a rule about the _language_ that another consumer
  then has to state again.
- The language must not state a rule about what a _consumer_ can represent.

Accepting a model is therefore not the same as building it. A model that every
consumer accepts can still be one that not every consumer can build.

## How this differs from the limits

[The limits](limits.md) answer which constructs may enter the language at all,
and sort each new construct into a macro, a primitive, a formulation or an
`escape:`. This page
answers who owns a rule once the construct is in. A construct can pass the limits
and still not be the language's business, and a rule can belong to the language
while the construct it governs is refused. Ask both questions, in that order.
