<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Glossary

This page gives the one meaning of each word these docs use in a fixed sense,
and links the page that owns it. The rest hang off one distinction:

> A **spec** is the file as written. A **program** is what the file means.
> Neither holds a number: the data arrives later, in the tool that builds the
> model.

```text
model.yaml ── to_spec ──▶ Spec ── .program ──▶ Program ──▶ typesetter, advice, an engine
                           │
                           └── .expand() ──▶ Spec of the rows
```

## The file and what reads it

**Spec**
: The file as written, checked: what `to_spec` returns. It keeps the file's own
spelling, its macros and its descriptions, and writes itself back out with
`to_yaml()` ([the file and the program](../about/file-and-program.md#two-states)).

**Program**
: What the file means: `spec.program`. Every name is typed, every macro is
expanded, and every operator is a node. The typesetter and `advice` read it
([reading a loaded model](reading.md#spec-and-program)).

**Load**
: What `to_spec` does: parse the file and check every rule that needs no data.
"Refused at load" means `to_spec` raises, before any data exists.

**Bind**
: What a consumer does when it puts data on a program. "When the data binds" is
the first moment a rule about numbers can be checked, and the language checks
none of them itself.

**Consumer**
: A tool that reads a spec: an **engine** that binds data and builds the rows a
solver takes, a **renderer** such as the typesetter, or a **checker** in CI.
A consumer may refuse a model for a reason of its own, and may not give the
file a second meaning
([what counts as language](../about/what-counts-as-language.md)).

**Typesetter**
: The part of this package that prints a program as math: `to_latex`,
`to_typst` and `to_markdown` ([typeset the math](typeset.md)).

**Symbol table**
: A mapping from each name and dimension in the file to the symbol it prints
as. With none, the symbols are **derived** from the names
([symbol tables](typeset.md#symbol-tables)).

**Legend**
: The table of sets, parameters, variables and definitions that the typesetter
prints above the math ([options](typeset.md#options)).

## Declarations

**Declaration**
: One named entry under one of the eleven top-level keys: one dimension, one
parameter, one constraint. The objective is the one declaration with no name
([file shape](language/file.md)).

**Dimension**
: An axis of the model, such as `snapshot` or `generator`. Declarations are
indexed by it, and `sum` reduces over it. The docs also say _axis_ for it,
and `dims` is the key that lists them ([dimensions](language/dimensions.md)).

**Label**
: One member of a dimension, `wind` say. The labels arrive with the data, in
the order that `shift`, `sum_back` and `position()` count along.

**Relation**
: A table that maps one dimension onto another: a generator's bus, a
snapshot's period. Its **key** is the columns unique per row, and its
**values** are what the key determines. A **bare relation** has no values,
so it may be many-to-many ([relations](language/relations.md)).

**Parameter**
: A name for data the model reads, with its dimensions and its `dtype`. It
declares a shape and nothing more. A `bool` parameter is a mask, and a `str`
parameter is a label; neither may stand in arithmetic
([parameters](language/declarations.md#parameters)).

**Variable**
: What the solver decides: one column per coordinate of its `dims`. Its
`domain` is `continuous`, `integer` or `binary`. It is unbounded on each side
the file does not bound ([variables](language/declarations.md#variables)).

**Constraint**
: One rule, built as one row per coordinate of its `dims`
([constraints](language/declarations.md#constraints)).

**Named expression**
: A quantity the file names once, under `expressions:`. The math may read it,
and a solve may report it ([named expressions](language/named.md)).

**Cases**
: A named expression that takes a different body in each region of its frame.
Each **case** has a `when:` mask that claims coordinates, and `otherwise:`
holds the value at the rest. No two cases may claim one coordinate
([cases](language/named.md#cases)).

**Macro**
: A template with arguments, under `macros:`. It is substituted into each
expression that calls it before anything reads the expression. Its arguments
are its **formals** ([macros](language/named.md#macros)).

**Assumption**
: A fact the data has to meet, written as a predicate under `assumptions:`. The
language types it and prints it; a consumer that has the data checks it
([assumptions](language/assumptions.md)).

## Coordinates and rows

**Coordinate**
: One point of a declaration's dimensions: one generator in one snapshot. A
variable has one column at each coordinate it is built at, and a constraint
has one row.

**Frame**
: A declaration's own dimensions. An expression, a mask and a bound parameter
must fit inside the frame they sit in
([how dimensions combine](language/expressions.md#how-dimensions-combine)).

**Dimension set**
: The dimensions an expression carries. `a + b` carries those of `a` and `b`
together, and `sum(x, over=d)` carries those of `x` less `d`.

**Scalar**
: A declaration or an expression with no dimensions, `dims: []`. The objective
is scalar.

**Degree**
: How many variables multiply together in one term. The objective and the
constraints stop at 2, and everything beside them stays at 1
([where a product of two variables is allowed](language/expressions.md#where-a-product-of-two-variables-is-allowed)).

**Group**
: The labels that one value of a relation column collects. `within=` keeps a
`shift`, a `sum_back` or a `position()` inside each group.

## Masks and absence

**Where**
: A predicate on a declaration that says which of its coordinates exist. Its
grammar is the [where grammar](language/expressions.md#where-strings).

**Mask**
: A `where` once the program holds it, and the coordinates it admits. A `bool`
parameter is a mask on its own ([nodes and masks](reading.md#nodes-and-masks)).

**Predicate**
: A true-or-false expression in the where grammar: the body of a `where:`, a
case's `when:`, or an assumption's `holds:`.

**Absence**
: No value at a coordinate: a variable masked out has no column there, and a
row that reads it is not built. Inside a `sum` an absent term is one term fewer
([absence](language/absence.md)). The `absence:` key on a variable chooses
between this reading, `undefined`, and `zero`
([what a missing coordinate means](language/absence.md#what-a-missing-coordinate-means)).

**Missing row**
: A coordinate that a parameter's table has no row for. It is not absence: it
reads as `0` in arithmetic and as false in a `where`
([what creates absence](language/absence.md#what-creates-absence)).

**Edge**
: The coordinates that a `shift` or a `sum_back` reaches past the start of its
dimension. Without `edge=`, a `shift` leaves the vacated coordinate absent,
and a `sum_back` window stops short ([`shift`](language/operators.md#shift)).

## Operators

**Operator**
: One of `sum`, `sum_back`, `at` and `shift`, plus `dual` in a reported
expression. The set is closed: a file cannot add one
([operators](language/operators.md)).

**Primitive**
: A construct built into the language, which every engine has to implement and
the typesetter has to print: the operators and the `where` comparisons. A
request for a new construct is a macro, a primitive or a formulation, or it is
refused ([how a new construct enters](../about/limits.md#how-a-new-construct-enters)).

**Consumed** · **produced**
: The relation columns that `sum(by=)` and `at(by=)` take away (`over=`) and put
in their place (`into=`)
([how a relation is used](language/relations.md#how-a-relation-is-used)).

**In the math** · **reported**
: A named expression is in the math when the objective, a constraint or a
`piecewise:` link reaches it. Otherwise it is reported: a solve computes it
from the solution, and no degree limit applies
([reported expressions](language/named.md#reported-expressions)).

**Row dual**
: `dual(c)`: the shadow price a solve puts on each row of constraint `c`. Only
a reported expression may read one
([reading a constraint's dual](language/named.md#reading-a-constraints-dual)).

## Formulations

**Formulation**
: A block that states ordinary variables and constraints rather than being one.
`piecewise:` and `sos:` are the two
([piecewise curves and SOS](language/piecewise.md)).

**Curve**
: A `piecewise:` entry: two or more expressions tied to one piecewise-linear
curve. Its **breakpoints** are the corners, one per label of the dimension
named by `over:`. Each **link** pairs an expression with the parameter that
holds its breakpoint values. `method:` says how the curve is written out
([`piecewise`](language/piecewise.md#piecewise)).

**Set**
: An `sos:` entry, a special-ordered set: of the members of a variable along
one dimension, at most one (`type: 1`) or two neighbours (`type: 2`) may be
non-zero ([`sos`](language/piecewise.md#sos)).

**Expand**
: Write each formulation out as the variables and constraints it states.
`spec.expand('piecewise')` writes the curves out and `spec.expand()` writes
the sets out too. Each returns a new spec, and nothing expands a model unasked
([writing a formulation out](language/piecewise.md#writing-a-formulation-out)).

## Checks and refusals

**Load error**
: An exception `to_spec` raises. Each is a `MathSpecError`, and the message
names the rewrite ([which error you get](language/errors.md#which-error-you-get)).

**Advice**
: A warning about a file that loads: a dimension nothing uses, or a variable
the objective pushes towards a bound it does not have
([what `advice` warns about](language/errors.md#what-advice-warns-about)).

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
| program  | `spec.program`, the typed model                         | a linear or quadratic program, the problem a solver takes     |
| the rows | the constraint rows of a model                          | the expanded model: the spec a formulation is written out as  |
