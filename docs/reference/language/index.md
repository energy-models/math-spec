<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# The language

A model is one YAML file. It declares the axes the model runs over, the data it
expects, the decisions the solver makes, and the rules those decisions obey.
Nothing outside the file changes what it means, so the same file is the same
model under every program that reads it.

```yaml title="dispatch.yaml"
description: Least-cost dispatch of a generator fleet against an hourly load.

dimensions:
  snapshot: { dtype: int }
  generator: { dtype: str }

parameters:
  load: { dims: [snapshot] }
  cost: { dims: [generator] }
  p_max: { dims: [generator] }

variables:
  p:
    foreach: [snapshot, generator]
    where: "p_max > 0"
    bounds: { lower: 0, upper: p_max }

constraints:
  power_balance:
    foreach: [snapshot]
    expression: sum(p, over=generator) == load

objective:
  sense: minimize
  expression: sum(p * cost) # an objective is one number, so the sum is written
```

That file is a complete model. The pages below give the exact rules.

## The ten rules

Nothing is guessed. Where a file does not decide the answer, loading fails, and
the message names the rewrite. Each rule below applies that principle in one
place, and links to the page that gives the detail.

| #   | Rule                                                                                                                                                                                                                                                                                           |                                                                 |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| 1   | A file has ten declaration keys, plus `version` and `description`. The schema is closed at every level, so an unknown key is an error that names the near miss.                                                                                                                                | [File shape](file.md)                                           |
| 2   | Everything that can be decided without data is decided at load.                                                                                                                                                                                                                                | [Errors](errors.md)                                             |
| 3   | One flat namespace, and no shadowing. A collision is a load error that names both declarations.                                                                                                                                                                                                | [Names](expressions.md#name-resolution)                         |
| 4   | Position decides which kinds of name are legal, and the kind of a name is fixed at load. A dimension is never legal where a value belongs, because it is a coordinate space and not data.                                                                                                      | [Names](expressions.md#name-resolution)                         |
| 5   | Dimension sets combine by union. A constraint's expression must **equal** its `foreach`. An objective carries no dimensions. A `where` or a bound must not **exceed** the frame it sits in.                                                                                                    | [How dimensions combine](expressions.md#how-dimensions-combine) |
| 6   | Four constructs create absence, and nothing else does. Absence is a state of a _variable_. A constraint's own `where:` deletes its row directly.                                                                                                                                               | [Absence](absence.md)                                           |
| 7   | Through arithmetic, absence spreads and takes the row with it. Out of a reduction it does not spread. So `sum(x + y)` and `sum(x) + sum(y)` ask different questions.                                                                                                                           | [Absence](absence.md#how-absence-travels)                       |
| 8   | A missing parameter row reads as whatever contributes nothing: zero as a coefficient, and false in a `where`. Where no such reading exists, loading is refused rather than guessed.                                                                                                            | [Absence](absence.md#what-creates-absence)                      |
| 9   | The objective and the constraints take degree 2, which is `variable * variable`. A bound and a `piecewise:` link stay affine. A named expression is held to the limit of the place that reads it. `/` needs a divisor with no variable in it, and `**` needs a base and an exponent with none. | [Expressions](expressions.md)                                   |
| 10  | The operator set is closed: `sum`, `sum_back`, `at`, `shift`, and `dual` in a reported expression. A composition of them goes in `macros:`.                                                                                                                                                    | [Operators](operators.md)                                       |

## The pages

|                                                                         |                                                                                                        |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| [File shape](file.md)                                                   | the ten keys, `version`, `description`, and how the YAML is read                                       |
| [Dimensions and lookups](dimensions.md)                                 | the axes, and the maps out of them                                                                     |
| [Parameters, variables, constraints and the objective](declarations.md) | the four blocks that carry the math                                                                    |
| [Expressions](expressions.md)                                           | the arithmetic grammar and the `where` grammar, what a name may mean where, and how dimensions combine |
| [Reported expressions](reported.md)                                     | named quantities that the math never reads, and which restrictions no longer apply to them             |
| [Operators](operators.md)                                               | `sum`, `sum_back`, `at` and `shift`                                                                    |
| [Absence and `where`](absence.md)                                       | which rows are built, and which are not                                                                |
| [Piecewise curves and SOS](piecewise.md)                                | `piecewise:` and `sos:`                                                                                |
| [Reading a loaded model](reading.md)                                    | what a program gets when it loads a model                                                              |
| [Errors and limits](errors.md)                                          | what fails when, and what the language will not express                                                |

Building a model, solving it and reading the answer back belong to a
**consumer**: a program that reads a loaded model, such as an engine, a
renderer or a checker. Nothing a consumer does changes what a file means.
