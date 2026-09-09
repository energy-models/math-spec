<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# What counts as language

Several programs read the same model file. An engine builds the model and hands
it to a solver. A renderer prints it as equations. A checker reads it in CI with
no data. This page says which decisions the language makes for all of them, and
which each program makes for itself.

The test is one question:

> If two programs answered this differently, would the file have two meanings?

Suppose the engine sums `p` over `generator` and the renderer prints a sum over
`snapshot`. The file now means two things, and that is a bug. So the language
decides what `sum(p, over=generator)` means, and both programs read the answer
instead of working it out.

Suppose instead that the engine writes the model in one solver's file format and
the renderer sets the page width to 80 characters. They disagree, and nothing is
wrong. Each program decides those things for itself.

Four rules follow from the test:

- A name means one thing. `p` cannot be a variable in the engine and a parameter
  in the renderer.
- The set of operators is fixed. A program cannot add a `roll` that the others
  do not know.
- Each operator has one rule for the dimensions it produces. `sum(p, by=gen_bus)`
  lands on `bus` for every program.
- Degree is decided when the file loads. Whether `x * y` is allowed does not
  depend on which engine builds the model.

A `piecewise:` block expands into ordinary variables and constraints, so the
language decides that expansion too. Otherwise two engines could build two
different curves from one block.

## What each program decides for itself

A program can refuse a model for a reason of its own. One engine can only take
a literal offset in `shift`. Another has no concept of a special-ordered set. A
file format has no way to write a quadratic constraint. None of these is a
disagreement about what the file means, so none of them is the language's to
settle. If the language refused everything one program cannot build, every
other program would inherit that limit.

So the boundary runs both ways:

- A program must not invent a rule about what the file _means_. If it needs
  one, the rule goes into the language, once.
- The language must not state a rule about what one program can _build_.

A file that every program accepts can still be a file that one engine cannot
build. Accepting and building are different steps.

## How this differs from the limits

[The limits](limits.md) answer a different question: which operators and blocks
may be added to the language at all. This page answers who decides a rule once
the operator or block exists. Ask the limits first, then this page.
