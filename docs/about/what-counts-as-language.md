<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# What counts as language

More than one program reads a model file. This page decides which rules belong
to the language, and which belong to the programs that read it. Those programs
are the model's **consumers**: an engine that builds it, a renderer that prints
it, a checker that judges it without any data.

One question decides:

> A rule belongs to the language when it would be a bug for two consumers to
> answer it separately.

Ask whether a second opinion could be wrong. Whether the rule is about syntax
does not decide it, and neither does whether it applies before the model runs.

Sometimes two consumers give different answers and both are reasonable. In that
case the question belongs to each of them. Sometimes two different answers would
mean the file itself says two different things. In that case the question
belongs to the language, and only one answer is allowed.

Four of the language's rules follow from that:

- A name resolves once.
- The set of operators is closed.
- The dimension rule for an operator has one home. Consumers ask for the answer
  instead of working it out again.
- Degree is decided when the file loads. Whether `x * y` is allowed does not
  depend on what builds the model.

A block that expands into declarations, such as `piecewise:`, is part of the
language too, because the declarations it emits are.

## Which rules belong to one consumer

The question above also runs the other way, and that is what stops it from
pulling in everything.

A consumer can refuse a model for its own good reasons. Its representation may
not be able to hold what the model asks for. Examples are an offset that must
be a literal value, a grouping that must name a lookup that is already
declared, or a set that the solver has no concept of. A second opinion about
these limits is not a bug. The limit belongs to that one consumer. If you moved
the limit into the language, every consumer would inherit the limits of the most
restricted one.

So two rules follow, one for each side:

- A consumer must not state a rule about the _language_ that another consumer
  then has to state again.
- The language must not state a rule about what a _consumer_ can represent.

A refusal that breaks the first rule is a language error. A refusal that breaks
the second is one consumer speaking for itself. So accepting a model is not the
same as building it: a model that every reader accepts can still be more than
one of them can build.

## How this differs from the limits

[The limits](limits.md) answer a different question, and the two questions are
easy to confuse.

That page says what is allowed to enter the language at all. It sorts each new
construct into a macro, an operator built into the language, or an `escape:`
block of Python, and it says what a built-in operator must stay inside.

This page says who owns a rule once the construct is in: the language, or one
consumer.

The two answers are independent. A construct can pass the limits and still not
be the business of the language. A rule can belong to the language while the
construct it governs is refused. When you place something new, ask both
questions, in that order.
