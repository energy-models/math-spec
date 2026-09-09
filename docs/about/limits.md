<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# The limits of the language

A model can only express what the language has words for. This page says which
words may be added, and which may not. Read it before you ask for a new operator,
a new block or a new keyword. For the rules a model itself must obey, read
[the ten rules](../reference/language/index.md#the-ten-rules).

## How a new construct enters

A request is one of four kinds, and the kind decides what it costs.

- **A macro** is a template that takes arguments and is substituted into an
  expression before anything reads it. It costs nothing, because it only
  composes operators that exist, and no consumer has to learn it. See
  [macros](../reference/language/expressions.md#macros). Most requests are a
  macro.
- **A primitive** is an operator built into the language, which no file can add
  to. `sum`, `sum_back`, `at`, `shift` and the `where` predicates are the
  primitives, and they set the limit of what the language can express. A new one
  is the expensive kind: every consumer that builds models has to implement it,
  and the typesetter has to print it in all three formats.
- **A formulation** is a block that expands into ordinary declarations before
  the model is built. `piecewise:` is the only one. It costs as much as a
  primitive to build, and composes as freely as a macro, because the rest of the
  model sees plain variables and constraints.
- **An `escape:`** is a block of Python, named in the file, that emits the rows
  the language cannot state. It is
  [#38](https://github.com/fluxopt/lpspec/issues/38), and it has not shipped.

### What a primitive must satisfy

A new primitive is **macro-friendly**: anything a modeller might pass in sits in
the value of a keyword argument, such as `over=` or `by=`, and never in its key.
`shift(x, over=snapshot, offset=1)` names its dimension in a value, so a macro
can pass its own argument there.

A candidate primitive is admissible when it is both **relational** and
**local**:

- Relational means one filter, one join, or one group-by aggregation over
  tables.
- Local means each output row reads its own input row, which is **pointwise**,
  or a fixed number of neighbouring rows, which is **bounded-halo**. Both can be
  built one chunk of rows at a time. An operator that reads the whole table at
  once cannot.

Locality is judged over the data, not over the coordinates. "The last snapshot"
reads only the table of coordinate labels, which is in memory already, so it
stays admissible.

Written as a query over the stream of terms, the shape of the query gives the
verdict:

| Shape of the query                                     | Locality     | Admissible?                |
| ------------------------------------------------------ | ------------ | -------------------------- |
| filters on a column the rows already carry             | pointwise    | admissible                 |
| joins against a parameter or a lookup table            | pointwise    | admissible                 |
| joins the coordinate table a fixed number of rows away | bounded-halo | admissible                 |
| reads the coordinate table only, and joins no data     | coordinates  | admissible, and free       |
| reads every row, or calls itself                       | whole table  | rejected, with the rewrite |

Degree is not a third rule. `variable * variable` at one coordinate is a join of
a table with itself, so it is relational and local, and the objective and the
constraints take degree 2. Two things bound the quadratic case:

- **Where it stands.** A quadratic objective has more sinks to land in than a
  quadratic constraint. A **sink** is whatever a built model is handed to, such as
  a solver's API or a file format, and what each sink takes is the
  [separate question below](#what-a-solver-can-take-is-a-separate-question).
- **A product of two sums.** `sum(x, over=i) * sum(y, over=j)` pairs every term
  of one sum against every term of the other, and nothing in the file says how
  many terms that is. A product of two single terms is a join whatever
  dimensions they carry, so `x[i] * y[j] * a[i, j]` is admissible: the table `a`
  says which pairs exist.

A new primitive is finished when `to_program` lowers it, the typesetter prints
it, and a consumer's build of a model using it agrees with the same model written
by hand. Porting a real model catches the bug no other test reaches: two
consumers read the same resolved tree, so a misreading they share passes every
test in this repository.

### Three groups of refusal

A request the language refuses falls into one of three groups, and the group
decides whether it can ever be allowed:

| Group                  | What bounds it                                                                 | Members                                                                                                                                                                                      | Can it move?                                    |
| ---------------------- | ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| **Capability-bounded** | what one sink can take                                                         | indicator constraints (#220); quadratic, whose verdict moves with convexity and with what stands beside it. `sos:` entered here: native where a sink has the concept, reformulated where not | per sink                                        |
| **Budget-bounded**     | the **label budget**: a cap on how many rows and columns an `escape:` may emit | operators that read a whole table, arbitrary Python, work that is not relational                                                                                                             | into an `escape:`, once one ships               |
| **Design-bounded**     | where this project has decided the work belongs                                | data preparation, domain helpers, Python that declares structure                                                                                                                             | movable any time; this project does not want to |

Three things never appear inside one model: a conditional, a loop, and structure
that the data decides. That fixes the **shape** of the model, which is which
declarations exist and which dimensions each spans, before any data is read. How
many members a dimension has is always the data's to supply.

The test is _when_ the Python runs, not what it does. A dimension computed during
data preparation is ordinary: a cycle basis for Kirchhoff's voltage law, or the
subsets of a subtour-elimination family. What no model can hold is work that
needs the solver's answer before it can decide the next row, such as cuts
generated during a solve. That work is open to the program around the model: one
model cannot loop, but a program may loop over models. A rolling horizon, Benders
decomposition and successive substitution are all in scope
([Track 2](https://github.com/fluxopt/lpspec/issues/471)).

An `escape:` is exempt from the relational and local rules, because its label
budget is declared in the file and checked before any Python runs. It is never
exempt from degree, because rows of coefficients are all it can emit.

### What a solver can take is a separate question

The test above asks how a model is built. Which solver takes the result is a
second question, kept apart from the first. Answered together, one solver's
limits would be written into the language, and every other solver would inherit
them.

Two facts keep the questions apart:

- What a solver does with an SOS varies. One sink has no concept of a set, and
  others take one as it stands.
- A quadratic form is bounded twice on one sink: once by whether it is convex,
  and again by what stands beside it in the model.

So one construct does not get one verdict. `sos:` is that reasoning applied. It
entered on the first question alone, because a set only names columns that a
variable has already made. Each sink then answers `native` or `reformulated`,
and a gap costs a weaker relaxation instead of a refusal. A set is a
**declaration** rather than a constraint, because neither way of writing it as
math is in the language: `x_i * x_j == 0` for `|i - j| >= k` is degree 2, and
bounding how many members are non-zero is not affine. A set reformulated into
binaries returns no duals where the native form does, so the difference is
declared, and the caller chooses
([#925](https://github.com/fluxopt/lpspec/pull/925),
[#928](https://github.com/fluxopt/lpspec/pull/928)).

## What counts as data preparation

The table below refuses data preparation as a language feature. From inside a
model, a precomputed column and a column the compiler could have derived look the
same. One sentence tells them apart:

> Data preparation computes what the model cannot know. The compiler builds what
> it can derive from data the model already has.

A cycle basis is the first kind: a graph algorithm over a topology that only data
supplies, so `cycle_incidence` arrives as a parameter. A minimum up time is the
second kind: `min_up_time` is a column the model already binds, and the window
over it follows from the column, so `sum_back(within=)` reads the width off the
column and the modeller ships no mask
([#849](https://github.com/fluxopt/lpspec/issues/849)).

Calliope made this trade-off differently. Its components take a list of
`where`-guarded equations, so alternatives that differ by regime live in the
file. Here they are data columns and `where:` masks, and a cyclic and a
non-cyclic store are two constraints
([#711](https://github.com/fluxopt/lpspec/issues/711)). What the difference buys
is a shape fixed before any data is read, which is what makes a streaming engine
and a second independent consumer possible.

## Deliberate non-primitives

What has been asked for and refused, with the reason and the rewrite. Parity with
another tool is not by itself a reason to add anything.

| Request                                                                  | Why                                                                                                                                                                                                                                                                                                                                   | Instead                                                                                                                                                                                                                  |
| ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Data preparation: resampling, clustering, file IO, unit conversion       | not math                                                                                                                                                                                                                                                                                                                              | preprocess, and pass a parameter                                                                                                                                                                                         |
| Unit checking at load                                                    | a `unit:` says something about the data that nothing checks against the data. A clean pass would mean only that no two annotated operands disagreed, never that the columns are in the units they claim. It would also open a unit grammar that the language then has to close ([#125](https://github.com/fluxopt/lpspec/issues/125)) | preprocess to one unit system, and name it in the declaration's `description:`                                                                                                                                           |
| Arbitrary array operations (`merge`, `reindex`)                          | there is no end to them                                                                                                                                                                                                                                                                                                               | data preparation                                                                                                                                                                                                         |
| Domain helpers (`reduce_carrier_dim`)                                    | writes one domain's vocabulary into the language                                                                                                                                                                                                                                                                                      | component libraries over generic primitives                                                                                                                                                                              |
| A tracked-metric vocabulary: `impacts:`, `effects:`, a `costs` dimension | a named expression already covers it, whether the math reads it or a solve reports it                                                                                                                                                                                                                                                 | an `impact` dimension and one named expression: cap it with a constraint whose dual is the shadow price, weight it in the objective, read it back after the solve ([#124](https://github.com/fluxopt/lpspec/issues/124)) |
| `**` with a variable base or exponent                                    | the exponent would decide the degree, and no data is read at load. `p ** n` is affine at 1, quadratic at 2 and over the limit at 3                                                                                                                                                                                                    | `x * x` for a square; above degree 2 there is no rewrite. Over variable-free operands `**` is in the language ([#1175](https://github.com/fluxopt/lpspec/issues/1175))                                                   |
| Normalisation (`x / sum(x)`)                                             | dividing by a variable is not polynomial at any degree, and no sink takes it                                                                                                                                                                                                                                                          | state the ratio as a constraint, or fix the denominator                                                                                                                                                                  |
| Conditionals, iteration, structure the data decides, inside one model    | the syntax tree could no longer be read without the data                                                                                                                                                                                                                                                                              | `where` masks and `foreach` dimensions. A program may loop over models                                                                                                                                                   |
| A Python API for constructing models                                     | the model is the file you review and diff                                                                                                                                                                                                                                                                                             | YAML, or a dict with the same keys ([composition](#composition-component-libraries))                                                                                                                                     |

## Composition (component libraries)

A component library is a fixed set of templates that take parameters, such as a
boiler, a battery and a line, which agree on one way of naming ports and flows.
Merging them gives one model, wired together by a connectivity table in the data
and closed by one `sum(by=)` balance.

Topology is data, not structure. Wiring up one system means rows in a
connectivity table, never YAML written by a program, so the file grows with the
number of component _types_ and never with the number of components.

Merging happens before building, and produces one `Spec`. Every function takes
`str | Path | dict | Spec`, so a model built as a dict is validated, expanded,
resolved and dimension-checked exactly as a file is, and `Spec.to_yaml()` prints
the copy a reviewer reads. A dict declares what a file declares, and nothing
more. It is not a Python API for building models, which stays refused.

A native schema merge (#30) and qualified names, so that two templates may each
declare a `p` (#29), were both closed against this contract: a library that
composes optional features varies its declarations by data, and a dict is already
how you say that. Signs and bidirectional flows need arithmetic in `bounds:`,
which is #31. A component whose number of ports is only known at run time belongs
in a thin layer above the language, which emits more rows or more templates, and
never one block of YAML per component.
