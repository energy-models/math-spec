<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# What counts as language

A fence tells you what must not happen. It does not tell you what belongs
inside. This page gives the test that does:

> **A rule belongs to the language if and only if it would be a bug for two
> consumers to answer it separately.**

The question is not whether the rule is about syntax. It is not whether the
rule applies before the model runs. The question is simpler: **would a second
opinion be wrong?**

More than one program reads a model file. An engine builds the model. A
renderer prints it. A checker judges it without any data. Sometimes two of
these programs can give different answers and both answers are reasonable. In
that case the question belongs to each program. Sometimes two different answers
would mean the file itself says two different things. In that case the question
belongs to the language, and only one implementation of the answer is allowed.

This is why the language works the way it does:

- A name resolves once.
- The set of operators is closed.
- The dimension rule for an operator has one home. Consumers **ask** for the
  answer instead of working it out again.
- Degree is decided before any plan exists. Nothing about `x * y` depends on a
  relational engine.

A formulation that emits declarations is also part of the language, because
declarations are part of the language.

## The test also works in reverse

The reverse direction is what stops the test from pulling in everything.

A consumer can refuse a model for its own good reasons. Its representation may
not be able to hold what the model asks for. Examples are an offset that must
be a literal value, a grouping that must name a lookup that is already
declared, or a set that the solver has no concept of. A second opinion about
these limits is not a bug. The limit belongs to that one consumer. If you moved
the limit into the language, every consumer would inherit the limits of the most
restricted one.

So the test has a sharp edge on both sides:

- A consumer must not state a rule about the **language** that another consumer
  then has to state again.
- The language must not state a rule about what a **consumer** can represent.

A refusal that fails the first test is a language error. A refusal that fails
the second test is one consumer speaking for itself. This is why **acceptance is
not construction**: a model that every reader accepts can still hit a wall
inside one of them.

## How this differs from the ceiling

[The ceiling](ceiling.md) answers a different question, and the two questions
are easy to confuse.

The ceiling says **what is allowed to enter the language at all**. It sorts each
new construct into a macro, a primitive or an escape, and it sets the limits a
primitive must stay inside.

This page says **who owns a rule once the construct is in**: the language, or
one consumer.

The two answers are independent. A construct can pass the ceiling and still not
be the business of the language. A rule can clearly belong to the language while
the construct it governs is refused. When you place something new, ask both
questions, in that order.
