<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Errors and limits

## Everything decidable without data is decided without data

Anything detectable before building is detected before building. The worst
error this language could hand you is an opaque solver or array exception with
no pointer back to a YAML declaration, so a model is parsed, expanded, resolved
and dim-checked — including _uncalled_ macro templates and every `where` string
— before a single source is read.

`lps.check('model.yaml')` runs exactly that and binds nothing, which is why it
is the CI verb: a model repository can be validated on every commit without
shipping the data.

Every message names what went wrong, what to do about it, and where it helps,
the valid options:

```text
Constraint 'balance', equation 0: 'p_charge' not found.
  Variables: ['p', 'soc']
  Parameters: ['p_max', 'load', 'efficiency']
Check for typos, or ensure 'p_charge' is declared.
```

A construct outside the language names the construct and its rewrite, never a
silent fallback.

## One answer is decidable without data too

A variable that no constraint names, and whose bounds leave open the side its
objective term improves toward, runs to infinity for every dataset there is. A
solver says that with a bare `unbounded` naming nothing; `check` says it with
the variable and the side, as advice:

```text
Variable 'slack' makes this model unbounded: no constraint names it, and
bounds.lower is -inf, which is the direction a +slack term improves a minimize
objective in. No data can change that, so the solve would answer `unbounded`
and name nothing.
Give it a finite bounds.lower, or the constraint that was meant to define it.
```

Advice and not a refusal, because the same shape is what a half-written model
looks like — a variable declared before the constraint that will hold it — and
`build` and `solve` stay open to one. The price is that only `check` says it:
go straight to `solve` and the solver's bare answer is still the first word.

Both halves of the conjunction are needed, and neither alone is wrong: a
variable held by nothing but its own `bounds:` is ordinary, and so is an
unbounded one that a constraint names. Where the sign a variable enters the
objective with is _data_ — a parameter coefficient, which may be zero or either
sign — nothing is said, because a note against a model that solves is the worse
error. The per-coordinate case, where a `where:` mask leaves one slice of a
variable with no constraint row, still reaches you from the solver
([#229](https://github.com/fluxopt/lpspec/issues/229)).

## Which error you get

|                           |                                                                                                       |
| ------------------------- | ----------------------------------------------------------------------------------------------------- |
| `MathSpecError`           | the root of the tree; everything below is an instance of it                                           |
| `LanguageError`           | the model: a construct outside the language, a dim set that does not compose, a name nothing declares |
| `SchemaError`             | the file: an unknown key, a malformed declaration, a bad symbol table                                 |
| `DimensionError`          | dims that disagree — a constraint whose expression does not equal its `foreach`                       |
| `PiecewiseExpansionError` | a `piecewise:` block that cannot be expanded                                                          |

Every one of them is the _file_ being wrong, and every one is reproducible from
the YAML alone — no data, no solver. That is the whole tree this package
raises: a consumer that binds numbers or calls a solver adds its own errors
below `MathSpecError`, and says so in its own documentation.

## What the language will not say

Refusals, and what to reach for instead. None of them is an unimplemented
feature list: each is a boundary the design keeps on purpose, and
[the ceiling](../../about/ceiling.md) is the argument for where it sits.

| Not here                                                                       | Instead                                                                                                                                                                                                                 |
| ------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| variable × variable in a **bound, a named expression or a `piecewise:` link**  | the objective and constraints take it; elsewhere, a parameter coefficient ([expressions](expressions.md#degree-2-in-the-math-degree-1-beside-it))                                                                       |
| `sum(x, over=d) * sum(y, over=d)`                                              | multiply before reducing, or name the reduction with a variable — a product of two sums is a cross join                                                                                                                 |
| degree 3 (`x * y * z`)                                                         | a variable constrained to equal one product, then multiplied by the third                                                                                                                                               |
| `**`                                                                           | `x * x` ([expressions](expressions.md#degree-2-in-the-math-degree-1-beside-it))                                                                                                                                         |
| a quadratic constraint on the **linopy lane**, or on `highs`                   | neither builds one; `lps.solve(..., solver_name='gurobi')`, or write an `.lp` file. `check(model, sink=…)` says so before you build                                                                                     |
| arithmetic in `bounds:`                                                        | a name or a number; ship the derived column as data ([#31](https://github.com/fluxopt/lpspec/issues/31))                                                                                                                |
| time-series processing (resample, cluster, interpolate, align), file IO, units | data prep; pass a parameter                                                                                                                                                                                             |
| solver breadth                                                                 | three solvers — HiGHS, which ships, plus Gurobi and Xpress via their own extras — chosen at the call and never in the file; LP and MPS files for everything else ([#106](https://github.com/fluxopt/lpspec/issues/106)) |
| indicator constraints                                                          | planned as a _solver capability_ rather than a language question, the same axis `sos:` landed on ([#220](https://github.com/fluxopt/lpspec/issues/220))                                                                 |
| multi-objective                                                                | one `objective:` block — a second is unsayable; weight them into one expression                                                                                                                                         |
| arbitrary array ops (`merge`, `reindex`, `apply_ufunc`)                        | data prep — the closed operator set is what makes streaming possible                                                                                                                                                    |
| filling a missing value (`.fillna`)                                            | data prep, or a `where` if you meant the coordinate not to exist. In the language only where the data cannot reach: `shift(..., edge=)` ([absence](absence.md))                                                         |
| schema migrations                                                              | —                                                                                                                                                                                                                       |

A model built partly in Python has no readable `.yaml` representation and will
not get one: the _math_ side is feasible, but expression and `where` strings
come back as anonymous arrays, so the round trip would be functional and not
reviewable — which is the whole point of the file. A framework that wants to
_emit_ declarations passes a dict, and gets `to_yaml()` back.

Where the language genuinely cannot say the math, the escape hatch is a
declared `escape:` island — named in the file, bounded by the preceding `where`
mask, terminal, and billed against a label budget before any Python runs. It is
[#38](https://github.com/fluxopt/lpspec/issues/38) and not shipped.
