<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Errors and limits

## `to_spec` is the check

`to_spec` is the one entry point, and it binds no data. Before
`ms.to_spec('model.yaml')` returns a `Spec`, it parses the file, expands every
`piecewise:` block, resolves every name, checks every dimension rule and every
degree, and reads every `where` string and every macro template, including the
templates that nothing calls.

Anything the language refuses is refused there. So a repository of models
validates in CI with no data and no solver. Errors that come later, such as an
array that does not bind or a solver exception, come from the tool that
builds and solves the model, not from this package.

Every message names what went wrong and what to do about it. Where it helps, the
message lists the valid options:

```text
Constraint 'balance', equation 0: 'p_charge' not found.
  Variables: ['p', 'soc']
  Parameters: ['p_max', 'load', 'efficiency']
Check for typos, or ensure 'p_charge' is declared.
```

A construct outside the language is refused with its rewrite. Nothing falls back
silently.

## `advice` reports what is decidable but not an error

Two more things can be decided without data, and each is advice rather than a
refusal. `ms.advice(model)` returns them as a tuple of `ms.Advice`. Each carries a
`kind`, which is `never-an-axis` or `unbounded`, the `subject` declaration it is
about, and its `text`. `str()` on one gives the sentence, and every tool that
shows advice shows this same sentence.

From a shell, `python -m math_spec check model.yaml` runs both. A refusal prints
to stderr and exits with status 1. Advice prints, and the status is 0.

**`never-an-axis`.** A dimension that nothing is indexed by, and that nothing
aggregates into, is never an axis. If a lookup targets it, it is a label space
wearing a dimension's declaration, and the note says how to declare it as one. If
nothing reaches it, it is unused.

**`unbounded`.** A variable that no constraint names, and whose bounds leave open
the side its objective term improves toward, runs to infinity for every dataset.
A solver reports this as a bare `unbounded` that names nothing. The note names
the variable and the side:

```text
Variable 'slack' makes this model unbounded: no constraint names it, and
bounds.lower is -inf, which is the direction a +slack term improves a minimize
objective in. No data can change that, so the solve would answer `unbounded`
and name nothing.
Give it a finite bounds.lower, or the constraint that was meant to define it.
```

This is advice rather than an error because a half-written model has the same
shape, and `to_spec` stays open to a half-written model. Both halves of the
condition are needed: a variable held only by its `bounds:` is ordinary, and so
is an unbounded variable that a constraint names. Nothing is said where the sign
a variable enters the objective with is data, because a parameter coefficient
may be zero or either sign. A slice of a variable that a `where:` leaves with no
constraint row cannot be decided from the file
([#229](https://github.com/fluxopt/lpspec/issues/229)).

## Which error you get

|                           |                                                                                                                                  |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `MathSpecError`           | The root. Everything below is an instance of it                                                                                  |
| `LanguageError`           | Something in the model: a construct outside the language, a dimension set that does not compose, or a name that nothing declares |
| `SchemaError`             | Something in the file: an unknown key, a malformed declaration, or a bad symbol table                                            |
| `DimensionError`          | Dimensions that disagree, such as a constraint whose expression does not equal its `foreach`                                     |
| `PiecewiseExpansionError` | A `piecewise:` block that cannot be expanded                                                                                     |

Every one of these means the file is wrong, and every one is reproducible from
the YAML alone. An engine that binds numbers or calls a solver adds its own
errors below `MathSpecError`, and documents them itself.

## What the language will not express

None of these is a feature waiting to be written. Each was asked for and refused,
and [the limits](../../about/limits.md) gives the reasons.

| Not in the language                                                            | Instead                                                                                                                                                             |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `variable * variable` in a bound or a `piecewise:` link                        | The objective and the constraints take it. Everywhere else, use a parameter coefficient ([expressions](expressions.md#where-a-product-of-two-variables-is-allowed)) |
| `sum(x, over=d) * sum(y, over=d)`                                              | Multiply before you reduce, or constrain a variable to equal the reduction. A product of two sums pairs every term against every term                               |
| degree 3 (`x * y * z`)                                                         | A variable constrained to equal one product, multiplied by the third                                                                                                |
| `**` with a variable in it                                                     | `x * x` for a square. Over variable-free operands `**` is in the language ([expressions](expressions.md#where-a-product-of-two-variables-is-allowed))               |
| arithmetic in `bounds:`                                                        | A name or a number. Ship the derived column as data ([#31](https://github.com/fluxopt/lpspec/issues/31))                                                            |
| time-series processing (resample, cluster, interpolate, align), file IO, units | Data preparation. Pass a parameter                                                                                                                                  |
| indicator constraints                                                          | What a solver can take is a question of its own, and `sos:` is where it landed ([#220](https://github.com/fluxopt/lpspec/issues/220))                               |
| multi-objective                                                                | There is one `objective:` block. Weight the goals into one expression                                                                                               |
| arbitrary array operations (`merge`, `reindex`, `apply_ufunc`)                 | Data preparation. The closed operator set is what lets a build stream its terms                                                                                     |
| filling a missing value (`.fillna`)                                            | Data preparation, or a `where` if the coordinate should not exist. Inside the language, only `shift(..., edge=)` fills ([absence](absence.md))                      |
| schema migrations                                                              | —                                                                                                                                                                   |

A model built with linopy or Pyomo calls cannot be turned into a `.yaml` file.
The arrays it holds would build the same model, but an `expression:` string and a
`where:` string cannot be recovered from them, so the result would be nothing a
reviewer could read. A library that wants a file passes a `dict` with the file's
keys to `to_spec`, and calls `to_yaml()`.

For math the language cannot express, an `escape:` block is planned: Python,
named in the file, that emits the rows the language cannot write, with a cap on
how many rows and columns it may emit checked before it runs. It is
[#38](https://github.com/fluxopt/lpspec/issues/38), and it has not shipped.
