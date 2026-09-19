<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Errors and limits

## What `to_spec` checks

`to_spec` binds no data. Before it returns a `Spec`, it parses the file,
resolves every name, checks every dimension rule and every degree, and reads
every `where` string and every macro template, including the templates that
nothing calls. A `piecewise:` block is checked as written, against every rule
its expansion would be held to, and stays a block.

Anything the language refuses is refused there, so a repository of models
validates in CI with no data and no solver. An array that does not bind, or a
solver exception, comes from the tool that builds and solves the model.

Every message names what went wrong and what to do about it:

```text
Constraint 'balance', equation 0: 'p_charge' not found.
  Variables: ['dispatch', 'soc']
  Parameters: ['capacity', 'load', 'efficiency']
Check for typos, or ensure 'p_charge' is declared.
```

## What `advice` warns about

`ms.advice(model)` returns a tuple of `ms.Advice`, one per warning, and
`python -m math_spec check model.yaml` prints them. Advice is a warning: the file
loads.

| `kind`          | The file has…                                                                                                     | The advice says…                                                      |
| --------------- | ----------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `never-an-axis` | a dimension nothing is indexed by, nothing aggregates into and no relation targets                                | remove it, or keep it knowingly if its declarations are still to come |
| `given`         | a column or a row family it reads and does not build ([given](declarations.md#given))                             | a consumer binds it to the model this one is layered onto             |
| `unbounded`     | a variable that no constraint, set or curve uses, whose objective term pushes it towards a bound it does not have | give it a finite bound, or the constraint that was meant to define it |

```text
Variable 'slack' makes this model unbounded: no constraint names it, and
bounds.lower is -inf, which is the direction a +slack term improves a minimize
objective in. No data can change that, so the solve would answer `unbounded`
and name nothing.
Give it a finite bounds.lower, or the constraint that was meant to define it.
```

`advice` is silent where the answer depends on the data: an objective
coefficient that is a parameter, or a `where:` that leaves one slice of a
variable with no constraint row.

## Which error you get

|                  |                                                                                                                                  |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `MathSpecError`  | The root. Everything below is an instance of it                                                                                  |
| `LanguageError`  | Something in the model: a construct outside the language, a dimension set that does not compose, or a name that nothing declares |
| `SchemaError`    | Something in the file: an unknown key, a malformed declaration, or a bad symbol table                                            |
| `DimensionError` | Dimensions that disagree, such as a constraint whose expression does not equal its `dims`                                        |

Every one of these is reproducible from the YAML alone. An engine that binds
numbers or calls a solver adds its own errors below `MathSpecError`.

## What the language will not express

Each of these was asked for and refused, and [the limits](../../about/limits.md)
gives the reasons.

| Not in the language                                                            | Instead                                                                                                                                                             |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `variable * variable` in a bound or a `piecewise:` link                        | The objective and the constraints take it. Everywhere else, use a parameter coefficient ([expressions](expressions.md#where-a-product-of-two-variables-is-allowed)) |
| `sum(x, over=d) * sum(y, over=d)`                                              | Multiply before you reduce, or constrain a variable to equal the reduction                                                                                          |
| degree 3 (`x * y * z`)                                                         | A variable constrained to equal one product, multiplied by the third                                                                                                |
| `**` with a variable in it                                                     | `x * x` for a square. Over variable-free operands `**` is in the language                                                                                           |
| arithmetic in `bounds:`                                                        | A name or a number. Ship the derived column as data                                                                                                                 |
| time-series processing (resample, cluster, interpolate, align), file IO, units | Data preparation. Pass a parameter                                                                                                                                  |
| indicator constraints                                                          | `sos:` is where that landed ([piecewise](piecewise.md#sos))                                                                                                         |
| multi-objective                                                                | There is one `objective:` block. Weight the goals into one expression                                                                                               |
| arbitrary array operations (`merge`, `reindex`, `apply_ufunc`)                 | Data preparation                                                                                                                                                    |
| filling a missing value (`.fillna`)                                            | Data preparation, or a `where` if the coordinate should not exist. Inside the language, only `shift(..., edge=)` fills ([absence](absence.md))                      |

The language has no escape hatch. Math it cannot express is a gap in the
language, and a gap closes as a macro, a primitive or a formulation
([the limits](../../about/limits.md)).
