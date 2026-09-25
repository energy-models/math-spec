<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# The limits of the language

A spec can only say what the language has words for. This page says which words
can be added, and which cannot. Read it before you ask for a new operator, block
or keyword. For the rules a spec itself has to obey, read
[the ten rules](../reference/language/index.md#the-ten-rules).

## How a new construct enters

A request for something new is one of four kinds, and the kind decides what it
costs to add.

- **A macro** is a template with arguments, written in the file under `macros:`.
  Adding one costs nothing: it uses only operators that exist, so no engine has
  to change ([macros](../reference/language/named.md#macros)).
- **A primitive** is an operator built into the language: `sum`, `sum_back`,
  `at`, `shift`, and the `where` comparisons. Adding one is the expensive kind:
  every engine that builds models has to implement it, and the typesetter has
  to print it in LaTeX, Typst and Markdown.
- **A formulation** is a block that states ordinary variables and constraints
  rather than being one. `piecewise:` and `sos:` are the two. It costs as much as
  a primitive to build, but composes as freely as a macro. It emits variables,
  constraints and assumptions, and no parameter, so
  [`spec.expand()`](../reference/language/piecewise.md#writing-a-formulation-out)
  writes it out with the data the spec already expects.
- **A declaration section** is a block of declarations of one kind, such as
  `variables:` or `given:`. One enters where it states something no section
  states, where a file decides it without data, and where the typesetter prints
  it. `given:` entered on all three. No other section says that a parameter,
  a column, a named expression or a row family belongs to another file, and
  that is what lets a component file load and print on its own.

A request that is none of the four is refused, and the
[table of refusals](#deliberate-non-primitives) records it with what to write
instead.

### What a new primitive has to satisfy

**A macro must be able to call it.** Everything a modeller might pass in goes in
the value of a keyword argument, such as `over=snapshot`.

**An operator names its price in rows read.** `sum(p, over=g)` reads one row
per generator, and `shift(p, along=t, offset=1)` reads the row before. Each
reads a bounded number of rows per output row, so an engine builds the model
one chunk of rows at a time. An operator that calls itself is refused, because
nothing bounds how far it expands.

| The operator                                     | Allowed?                                        |
| ------------------------------------------------ | ----------------------------------------------- |
| filters rows on a column they already carry      | yes                                             |
| joins each row against a parameter or a relation | yes                                             |
| reads a fixed number of neighbouring rows        | yes                                             |
| reads only the coordinate labels                 | yes                                             |
| reads every row                                  | yes, at one full pass before any chunk builds   |
| calls itself                                     | no, and the message names what to write instead |

Degree is not a test for a new primitive. The
[product rule](../reference/language/expressions.md#where-a-product-of-two-variables-is-allowed)
holds for every operator.

A new primitive is finished when lowering builds it, the typesetter prints
it in all three formats, and an engine's build of a spec that uses it matches
its build of the same spec written out by hand.

### Three kinds of refusal

| The language refuses it because…           | Examples                                                                                                                          | Can it change?                             |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| **one solver cannot take it**              | indicator constraints; a quadratic constraint ([solver capability](what-counts-as-language.md#what-each-tool-decides-for-itself)) | yes, solver by solver                      |
| **the file would stop being the artifact** | arbitrary Python, whose content no loader can check and no typesetter can print                                                   | no                                         |
| **this project puts the work elsewhere**   | data preparation such as resampling; helpers for one domain; Python that decides which declarations exist                         | it could; this project does not want it to |

## What counts as data preparation

A column computed in pandas and a column the language could derive look the
same once attached. One sentence tells them apart:

> Data preparation computes what the spec cannot state. The language derives
> what it can from the data the spec already expects.

A cycle basis is the first kind. It needs the network's topology, which only the
data has, so `cycle_incidence` arrives as a parameter. A minimum up time is the
second kind. `min_up_time` is a column the spec already expects, so
`sum_back(window=min_up_time)` reads the width off the column and you ship no
window mask.

Checking a column is neither. `p_min <= p_max` is a rule two consumers must not
answer differently, so the rule is
[language](../reference/language/assumptions.md) and the check is the
consumer's. The file states the predicate, and whoever attaches the numbers runs
it.

## Deliberate non-primitives

Each row is a request the language refuses, with the reason and what to write
instead.

| Request                                                                  | Why refused                                                                                                                                | Instead                                                                                                                                                                            |
| ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Resampling, clustering, file IO, unit conversion                         | not math                                                                                                                                   | do it in data preparation, and pass a parameter                                                                                                                                    |
| Unit checking at load                                                    | a `unit: MW` on a parameter is a claim that nothing checks against the column, and it needs a grammar of units the language then maintains | convert to one unit system in data preparation, and name it in the `description:`. A range the data has to meet is an [`assumptions:`](../reference/language/assumptions.md) entry |
| Array operations such as `merge` and `reindex`                           | there is no end to them                                                                                                                    | data preparation                                                                                                                                                                   |
| Helpers for one domain, such as `reduce_carrier_dim`                     | writes one field's vocabulary into the language                                                                                            | a component library of macros over the operators that exist                                                                                                                        |
| A vocabulary for tracked metrics: `impacts:`, `effects:`, a `costs` axis | a named expression already does this                                                                                                       | an `impact` dimension and one named expression. Cap it with a constraint, weight it in the objective, read it back after the solve                                                 |
| `**` with a variable in the base or the exponent                         | the exponent would decide the degree, and `to_spec` reads no data                                                                          | `x * x` for a square. `**` over parameters and numbers is allowed                                                                                                                  |
| Normalisation, `x / sum(x)`                                              | dividing by a variable is not a polynomial, and no solver takes it                                                                         | write the ratio as a constraint, or fix the denominator                                                                                                                            |
| An `if`, a loop, or declarations that depend on the data                 | `to_spec` could no longer read the file without the data                                                                                   | `where:` masks and `dims:` dimensions. A tool may loop over specs                                                                                                                  |
| A Python API for building specs                                          | the spec is the file you review and diff                                                                                                   | YAML, or a `dict` with the same keys, merged before `to_spec`                                                                                                                      |
| A `where` comparing a relation column against the dimension it maps into | the relation already pairs the two, and a mask over the pair is the same fact in a bigger shape                                            | place the quantity with `sum(by=)`, or read it with `at(by=)` ([operators](../reference/language/operators.md#sum))                                                                |
