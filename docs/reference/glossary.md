<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Glossary

This page defines the words these docs use in a fixed sense and that no single
reference page owns. A construct, such as a parameter or a macro, is defined on
its [language page](language/index.md).

## The file and what reads it

**Spec**
: The optimisation problem a file states: its dimensions, the data it expects,
its decisions and its rules. A spec holds no data. In Python it is a `Spec`,
the file as written and checked, which `to_spec` returns
([reading a spec and its program](reading.md#spec-and-program)).

**Model**
: A spec with data attached, which an engine builds and a solver takes.
mathspec never holds one. The docs say "model" only in this sense.

**Program**
: What the file means, `spec.program`: every name typed, every macro expanded,
every operator a node.

**Load**
: What `to_spec` does. "Refused at load" means `to_spec` raises, before any
data exists.

**Attach**
: What a consumer does when it puts data on a program. A rule about numbers can
be checked only then, and the language checks none itself. The docs never say
"bind" for it, so that **bound** means one thing: a lower or upper limit on a
variable ([variables](language/declarations.md#variables)).

**Consumer**
: A tool that reads a spec: an **engine** that attaches data and builds the rows a
solver takes, a **renderer** such as the typesetter, or a **checker**
([what counts as language](../about/what-counts-as-language.md)).

**Declaration**
: One named entry under one of the top-level keys: one dimension, one
parameter, one constraint ([file shape](language/file.md)).

## Coordinates

**Label**
: One member of a dimension, `wind` say. The labels arrive with the data, in
the order that `shift`, `sum_back` and `position()` count along.

**Coordinate**
: One point of a declaration's dimensions: one generator in one snapshot. A
variable has one column at each coordinate it is built at, and a constraint
has one row.

**Frame**
: A declaration's own dimensions. An expression, a mask and a bound parameter
must fit inside the frame they sit in
([how dimensions combine](language/expressions.md#how-dimensions-combine)).

**Group**
: The labels that one value of a relation column collects. `within=` keeps a
`shift`, a `sum_back` or a `position()` inside each group.

## Masks and absence

**Mask** · **predicate**
: A predicate is a true-or-false expression in the
[where grammar](language/expressions.md#where-strings). A mask is a predicate
on a declaration, and the coordinates it admits.

**Absence**
: No value at a coordinate. A masked-out variable has no column there, and a
row that reads it is not built ([absence](language/absence.md)).

**Missing row**
: A coordinate that a parameter's table has no row for. It is not absence: it
reads as `0` in arithmetic and as false in a `where`
([what creates absence](language/absence.md#what-creates-absence)).

## Kinds of construct

**Primitive**
: A construct built into the language, which every engine implements and the
typesetter prints: the operators and the `where` comparisons.

**Formulation**
: A block that states ordinary variables and constraints rather than being
one: `piecewise:` and `sos:` ([piecewise curves and SOS](language/piecewise.md)).

A request for a new construct is a macro, a primitive or a formulation, or it
is refused ([how a new construct enters](../about/limits.md#how-a-new-construct-enters)).

## Words with two senses

These words mean two things in these docs. The sentence around each one says
which.

| Word     | One sense                                               | The other sense                                               |
| -------- | ------------------------------------------------------- | ------------------------------------------------------------- |
| row      | a constraint at one coordinate                          | one line of a parameter's or a relation's table               |
| column   | a variable at one coordinate                            | one column of a data table or a relation                      |
| set      | an `sos:` entry                                         | the set symbol of a dimension, $\mathcal{G}$, in the legend   |
| regime   | one case of a [`cases:`](language/named.md#cases) block | one of two constraints, each under its own `where:`           |
| domain   | a variable's `continuous`, `integer` or `binary`        | the rows that hold a curve's link inside its breakpoint range |
| program  | `spec.program`, the typed spec                          | a linear or quadratic program, the problem a solver takes     |
| the rows | the constraint rows of a spec                           | the expanded spec: the spec a formulation is written out as   |
