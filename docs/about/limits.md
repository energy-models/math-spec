<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# The limits of the language

A model can only say what the language has words for. This page says which words
can be added, and which cannot. Read it before you ask for a new operator, block
or keyword. For the rules a model itself has to obey, read
[the ten rules](../reference/language/index.md#the-ten-rules).

## How a new construct enters

A request for something new is one of four kinds, and the kind decides what it
costs to add.

- **A macro** is a template with arguments, written in the file under `macros:`,
  that is substituted into an expression before anything reads it. Adding one
  costs nothing: it uses only operators that exist, so no engine has to change.
  Most requests turn out to be a macro. See
  [macros](../reference/language/expressions.md#macros).
- **A primitive** is an operator built into the language: `sum`, `sum_back`,
  `at`, `shift`, and the `where` comparisons. A file cannot add one. Adding one
  here is the expensive kind: every engine that builds models has to implement
  it, and the typesetter has to print it in LaTeX, Typst and Markdown.
- **A formulation** is a block that expands into ordinary variables and
  constraints before the model is built. `piecewise:` is the only one. It costs
  as much as a primitive to build, but composes as freely as a macro, because
  the rest of the model only sees the variables and constraints it emitted.
- **An `escape:`** is a block of Python, named in the file, that emits the rows
  the language cannot write. It is planned as
  [#38](https://github.com/fluxopt/lpspec/issues/38) and has not shipped.

### What a new primitive has to satisfy

**A macro must be able to call it.** Everything a modeller might pass in goes in
the value of a keyword argument, such as `over=snapshot`, never in the key. A
macro can write `over=d` and let the caller supply `d`. It could not do that if
the dimension were the keyword itself.

**Each output row reads a bounded number of input rows.** `sum(p, over=g)` reads
one row per generator. `shift(p, over=t, offset=1)` reads one row, the one
before it. `x * y * a` reads the rows of `a` that pair an `x` with a `y`. An
operator that reads the whole table to produce one row, or that calls itself, is
refused, because an engine cannot then build the model one chunk of rows at a
time. Reading only the coordinate labels does not count: "the last snapshot"
looks at the list of snapshots, not at the data, and is allowed.

| The operator                                         | Allowed?                                                          |
| ---------------------------------------------------- | ----------------------------------------------------------------- |
| filters rows on a column they already carry          | yes                                                               |
| joins each row against a parameter or a lookup table | yes                                                               |
| reads a fixed number of neighbouring rows            | yes                                                               |
| reads only the coordinate labels                     | yes                                                               |
| reads every row, or calls itself                     | no, and the message names the macro or `escape:` to write instead |

**Degree is not a third test.** `p * q` at one coordinate is a join of a table
with itself, so the objective and the constraints take it. Two things limit the
quadratic case:

- **Where it stands.** More solvers and file formats take a quadratic objective
  than a quadratic constraint. Which ones is the
  [separate question below](#what-a-solver-can-take-is-a-separate-question).
- **A product of two sums.** `sum(x, over=i) * sum(y, over=j)` multiplies every
  term of the first sum by every term of the second, and the file does not say
  how many terms either sum has. It is refused. `x[i] * y[j] * a[i, j]` is
  allowed, because the table `a` says which pairs exist.

A new primitive is finished when `to_program` lowers it, the typesetter prints
it in all three formats, and an engine's build of a model that uses it matches
the same model written out by hand.

### Three kinds of refusal

| The language refuses it because…                                                   | Examples                                                                                                                                                            | Can it change?                             |
| ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| **one solver cannot take it**                                                      | indicator constraints (#220); a quadratic constraint. `sos:` was in this group, and entered: a solver with sets takes it as one, and a solver without gets binaries | yes, solver by solver                      |
| **it exceeds the label budget**, the cap on rows and columns an `escape:` may emit | an operator that reads a whole table; arbitrary Python                                                                                                              | into an `escape:`, once one ships          |
| **this project puts the work elsewhere**                                           | data preparation such as resampling; helpers for one domain; Python that decides which declarations exist                                                           | it could; this project does not want it to |

Three things never appear inside one model: an `if`, a loop, and a set of
declarations that depends on the data. `foreach: [snapshot]` does not know how
many snapshots there are, and it does not need to. A dimension computed before
the model loads is fine: a cycle basis for Kirchhoff's voltage law is a graph
algorithm run in data preparation, and its result arrives as a parameter. What no
model can hold is work that needs the solver's answer before it can write the
next row, such as cuts added during a solve. A program can still loop over
models: a rolling horizon, Benders decomposition and successive substitution
each build a model, solve it, and build the next
([Track 2](https://github.com/fluxopt/lpspec/issues/471)).

### What a solver can take is a separate question

The test above asks whether an engine can build the operator. Whether a given
solver then accepts the result is a second question, and the language does not
answer it. If it did, one solver's limits would be written into the language,
and every other solver would inherit them.

Two examples show why the questions stay apart:

- HiGHS has no special-ordered sets. Gurobi does. An engine handing a model to
  HiGHS rewrites each set as binaries and big-M rows; one handing it to Gurobi
  passes the set through.
- A quadratic constraint is accepted by some solvers only when it is convex,
  and convexity depends on the numbers, which the file does not have.

So `sos:` entered the language on the first question alone: a set only names
columns a variable has already declared. Each engine then decides how to hand it
to its solver. A set rewritten as binaries returns no duals, where the native set
does, so the engine reports which it did, and you choose the solver
([#925](https://github.com/fluxopt/lpspec/pull/925),
[#928](https://github.com/fluxopt/lpspec/pull/928)).

A set is a declaration under `sos:`, not an `expression:`, because no expression
can write it: `x_i * x_j == 0` for every pair is degree 2, and "at most two of
these are non-zero" is not arithmetic at all.

## What counts as data preparation

The table below refuses data preparation as a language feature. But from inside a
model, a column you computed in pandas and a column the language could have
derived look the same: a parameter arrives, and a constraint reads it. One
sentence tells them apart:

> Data preparation computes what the model cannot know. The language derives what
> it can from data the model already has.

A cycle basis is the first kind. It needs the network's topology, which only the
data has, so `cycle_incidence` arrives as a parameter. A minimum up time is the
second kind. `min_up_time` is a column the model already binds, and the window
"the last `min_up_time` hours" follows from it, so `sum_back(within=min_up_time)`
reads the width off the column and you ship no window mask
([#849](https://github.com/fluxopt/lpspec/issues/849)).

Calliope made this trade-off the other way. A Calliope component carries several
`where`-guarded versions of one equation, so a cyclic and a non-cyclic store are
one block. Here they are two constraints, and which applies is a column in the
data ([#711](https://github.com/fluxopt/lpspec/issues/711)). What this buys is
that the list of declarations is fixed before any data is read, which is what
lets an engine build the model one chunk of rows at a time.

## Deliberate non-primitives

What has been asked for and refused, with the reason and what to write instead.
That another tool has a feature is not by itself a reason to add it.

| Request                                                                  | Why refused                                                                                                                                                                                                                                                                               | Instead                                                                                                                                                                                                                   |
| ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Resampling, clustering, file IO, unit conversion                         | not math                                                                                                                                                                                                                                                                                  | do it in data preparation, and pass a parameter                                                                                                                                                                           |
| Unit checking at load                                                    | a `unit: MW` on a parameter is a claim that nothing checks against the column. A clean pass would only mean that no two annotated operands disagreed. It would also need a grammar of units that the language then has to maintain ([#125](https://github.com/fluxopt/lpspec/issues/125)) | convert to one unit system in data preparation, and name it in the `description:`                                                                                                                                         |
| Array operations such as `merge` and `reindex`                           | there is no end to them                                                                                                                                                                                                                                                                   | data preparation                                                                                                                                                                                                          |
| Helpers for one domain, such as `reduce_carrier_dim`                     | writes one field's vocabulary into the language                                                                                                                                                                                                                                           | a component library of macros over the operators that exist                                                                                                                                                               |
| A vocabulary for tracked metrics: `impacts:`, `effects:`, a `costs` axis | a named expression already does this                                                                                                                                                                                                                                                      | an `impact` dimension and one named expression. Cap it with a constraint, whose dual is the shadow price; weight it in the objective; read it back after the solve ([#124](https://github.com/fluxopt/lpspec/issues/124)) |
| `**` with a variable in the base or the exponent                         | the exponent would decide the degree, and `to_spec` reads no data. `p ** n` is linear at `n = 1`, quadratic at `n = 2`, and refused at `n = 3`                                                                                                                                            | `x * x` for a square. `**` over parameters and numbers is allowed ([#1175](https://github.com/fluxopt/lpspec/issues/1175))                                                                                                |
| Normalisation, `x / sum(x)`                                              | dividing by a variable is not a polynomial, and no solver takes it                                                                                                                                                                                                                        | write the ratio as a constraint, or fix the denominator                                                                                                                                                                   |
| An `if`, a loop, or declarations that depend on the data                 | `to_spec` could no longer read the file without the data                                                                                                                                                                                                                                  | `where:` masks and `foreach:` dimensions. A program may loop over models                                                                                                                                                  |
| A Python API for building models                                         | the model is the file you review and diff                                                                                                                                                                                                                                                 | YAML, or a `dict` with the same keys ([below](#composition-component-libraries))                                                                                                                                          |

## Composition (component libraries)

A component library is a set of templates, such as a boiler, a battery and a
line, that agree on how ports and flows are named. You merge the templates you
need into one file, wire the components together with a connectivity table in
the data, and close the system with one `sum(by=)` balance.

The topology is data. Adding a second battery is a row in a table, not a second
block of YAML, so the file grows with the number of component _types_ and not
with the number of components.

Merging happens before `to_spec`. Every function here takes a `dict` as well as
a path, so a model assembled in Python is checked exactly as a file is, and
`Spec.to_yaml()` writes the file a reviewer reads. A `dict` may hold only what a
file may hold. There is no Python API that builds models any other way.

Two requests were closed against this design. A built-in merge (#30) and
namespaces so that two templates can each declare a `p` (#29) are both things a
library does before it hands over a `dict`. Arithmetic in `bounds:`, which signed
and bidirectional flows need, is still open as #31. A component whose number of
ports is only known at run time belongs in the library, which emits more rows or
more templates, and never one block of YAML per component.
