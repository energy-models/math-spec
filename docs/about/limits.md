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

A request for something new is one of three kinds, and the kind decides what it
costs to add.

- **A macro** is a template with arguments, written in the file under `macros:`.
  Adding one costs nothing: it uses only operators that exist, so no engine has
  to change. Most requests turn out to be a macro
  ([macros](../reference/language/named.md#macros)).
- **A primitive** is an operator built into the language: `sum`, `sum_back`,
  `at`, `shift`, and the `where` comparisons. A file cannot add one. Adding one
  here is the expensive kind: every engine that builds models has to implement
  it, and the typesetter has to print it in LaTeX, Typst and Markdown.
- **A formulation** is a block that states ordinary variables and constraints
  rather than being one. `piecewise:` and `sos:` are the two. It costs as much as
  a primitive to build, but composes as freely as a macro. A formulation emits
  variables and constraints, states what it assumes of the data as ordinary
  assumptions, and emits no parameter — so the same data binds a model and its
  expansion, and
  [`spec.expand()`](../reference/language/piecewise.md#writing-a-formulation-out)
  needs no source a reader has to supply.

A request that is none of the three is refused, and the
[table of refusals](#deliberate-non-primitives) records it with what to write
instead.

### What a new primitive has to satisfy

**A macro must be able to call it.** Everything a modeller might pass in goes in
the value of a keyword argument, such as `over=snapshot`.

**An operator may read the whole table. It pays one full pass over the data.**
`sum(p, over=g)` reads one row per generator, and `shift(p, along=t, offset=1)`
reads the row before. Each reads a bounded number of rows per output row, so an
engine builds the model one chunk of rows at a time. An operator that reads
every row to produce one row costs one full pass before any chunk builds, and a
request for such an operator names that price.

**An operator that calls itself is refused.** Nothing bounds how far it expands.

| The operator                                     | Allowed?                                        |
| ------------------------------------------------ | ----------------------------------------------- |
| filters rows on a column they already carry      | yes                                             |
| joins each row against a parameter or a relation | yes                                             |
| reads a fixed number of neighbouring rows        | yes                                             |
| reads only the coordinate labels                 | yes                                             |
| reads every row                                  | yes, at one full pass before any chunk builds   |
| calls itself                                     | no, and the message names what to write instead |

**Degree is not a third test.** `p * q` at one coordinate is a join of a table
with itself, so the objective and the constraints take it. A product of two
sums, `sum(x, over=i) * sum(y, over=j)`, is refused, because the file does not
say how many terms either sum has. `x[i] * y[j] * a[i, j]` is allowed, because
the table `a` says which pairs exist.

A new primitive is finished when `to_program` lowers it, the typesetter prints
it in all three formats, and an engine's build of a model that uses it matches
the same model written out by hand.

### Three kinds of refusal

| The language refuses it because…           | Examples                                                                                                                                                                        | Can it change?                             |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| **one solver cannot take it**              | indicator constraints; a quadratic constraint. `sos:` was in this group, and entered: a solver with sets takes it as one, and a model for a solver without is written out first | yes, solver by solver                      |
| **the file would stop being the artifact** | arbitrary Python, whose content no loader can check and no typesetter can print                                                                                                 | no                                         |
| **this project puts the work elsewhere**   | data preparation such as resampling; helpers for one domain; Python that decides which declarations exist                                                                       | it could; this project does not want it to |

Three things never appear inside one model: an `if`, a loop, and a set of
declarations that depends on the data. A dimension computed before the model
loads is fine: a cycle basis for Kirchhoff's voltage law is a graph algorithm
run in data preparation, and its result arrives as a parameter. What no model
can hold is work that needs the solver's answer before it can write the next
row, such as cuts added during a solve. A tool can still loop over models: a
rolling horizon and Benders decomposition each build a model, solve it, and
build the next.

### Solver capability

Whether an engine can build the operator is one question. Whether a given
solver then accepts the result is a second one, and the language does not
answer it. If it did, one solver's limits would be written into the language,
and every other solver would inherit them.

- HiGHS has no special-ordered sets. Gurobi does. An engine handing a model to
  Gurobi passes the set through; one handing it to HiGHS refuses it, and the
  author writes the set out with `spec.expand('sos')` first.
- A quadratic constraint is accepted by some solvers only when it is convex,
  and convexity depends on the numbers, which the file does not have.

So `sos:` entered the language on the first question alone. Each engine then
decides whether it takes a set, and the language decides what a set is written
out as.

## What counts as data preparation

From inside a model, a column you computed in pandas and a column the language
could have derived look the same: a parameter arrives, and a constraint reads
it. One sentence tells them apart:

> Data preparation computes what the model cannot know. The language derives what
> it can from data the model already has.

A cycle basis is the first kind. It needs the network's topology, which only the
data has, so `cycle_incidence` arrives as a parameter. A minimum up time is the
second kind. `min_up_time` is a column the model already binds, so
`sum_back(window=min_up_time)` reads the width off the column and you ship no
window mask.

Checking a column is neither. `p_min <= p_max` is a rule two consumers must not
answer differently, so the rule is
[language](../reference/language/assumptions.md) and the check is the
consumer's. The file states the predicate, and whoever binds the numbers runs
it.

## Deliberate non-primitives

What has been asked for and refused, with the reason and what to write instead.
That another tool has a feature is not by itself a reason to add it.

| Request                                                                  | Why refused                                                                                                                                | Instead                                                                                                                                                                            |
| ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Resampling, clustering, file IO, unit conversion                         | not math                                                                                                                                   | do it in data preparation, and pass a parameter                                                                                                                                    |
| Unit checking at load                                                    | a `unit: MW` on a parameter is a claim that nothing checks against the column, and it needs a grammar of units the language then maintains | convert to one unit system in data preparation, and name it in the `description:`. A range the data has to meet is an [`assumptions:`](../reference/language/assumptions.md) entry |
| Array operations such as `merge` and `reindex`                           | there is no end to them                                                                                                                    | data preparation                                                                                                                                                                   |
| Helpers for one domain, such as `reduce_carrier_dim`                     | writes one field's vocabulary into the language                                                                                            | a component library of macros over the operators that exist                                                                                                                        |
| A vocabulary for tracked metrics: `impacts:`, `effects:`, a `costs` axis | a named expression already does this                                                                                                       | an `impact` dimension and one named expression. Cap it with a constraint, weight it in the objective, read it back after the solve                                                 |
| `**` with a variable in the base or the exponent                         | the exponent would decide the degree, and `to_spec` reads no data                                                                          | `x * x` for a square. `**` over parameters and numbers is allowed                                                                                                                  |
| Normalisation, `x / sum(x)`                                              | dividing by a variable is not a polynomial, and no solver takes it                                                                         | write the ratio as a constraint, or fix the denominator                                                                                                                            |
| An `if`, a loop, or declarations that depend on the data                 | `to_spec` could no longer read the file without the data                                                                                   | `where:` masks and `dims:` dimensions. A tool may loop over models                                                                                                                 |
| A Python API for building models                                         | the model is the file you review and diff                                                                                                  | YAML, or a `dict` with the same keys ([below](#composition-component-libraries))                                                                                                   |
| A `where` comparing a relation column against the dimension it maps into | the relation already pairs the two, and a mask over the pair is the same fact in a bigger shape                                            | place the quantity with `sum(by=)`, or read it with `at(by=)` ([operators](../reference/language/operators.md#sum))                                                                |

## Composition (component libraries)

A component library is a set of templates, such as a boiler, a battery and a
line, that agree on how ports and flows are named. You merge the templates you
need into one file, wire the components together with a connectivity table in
the data, and close the system with one `sum(by=)` balance.

The topology is data. Adding a second battery is a row in a table, so the file
grows with the number of component _types_.

Merging happens before `to_spec`. Every function here takes a `dict` as well as
a path, so a model assembled in Python is checked exactly as a file is, and
`Spec.to_yaml()` writes the file a reviewer reads. A `dict` may hold only what a
file may hold, so the file itself states no composition. A template names no
sibling, and no key says which fragment wins where two declare a `p`.
