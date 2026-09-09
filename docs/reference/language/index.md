<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# The language

A model is one YAML file. It declares the axes the model runs over, the data it
expects, the decisions the solver makes, and the rules those decisions obey.
Every program that reads the file reads the same model.

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

`to_spec` checks everything it can without data, and refuses the file with a
message that names the fix. These ten rules are what it checks.

| #   | Rule                                                                                                                                                                                                                                        |                                                                 |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| 1   | A file has ten declaration keys, plus `version` and `description`. A key the schema does not know is refused, with the nearest valid key named: `boundz` → `bounds`.                                                                        | [File shape](file.md)                                           |
| 2   | Everything that can be checked without data is checked when the file loads.                                                                                                                                                                 | [Errors](errors.md)                                             |
| 3   | Every name is declared once. A parameter and a dimension both called `snapshot` is refused, and the message names both lines.                                                                                                               | [Names](expressions.md#name-resolution)                         |
| 4   | Where a name may stand depends on what it is. A dimension may follow `over=`, and may not be multiplied: `p * snapshot` is refused, because `snapshot` is an axis and not a column of numbers.                                              | [Names](expressions.md#name-resolution)                         |
| 5   | `a + b` carries the dimensions of `a` and of `b` together. A constraint's expression must carry **exactly** its `foreach`. The objective must carry none. A `where` or a bound may carry fewer dimensions than its declaration, never more. | [How dimensions combine](expressions.md#how-dimensions-combine) |
| 6   | A variable's `where:` deletes the variable at the masked coordinates. There is no column there, not a column fixed at zero. A constraint's `where:` deletes the row.                                                                        | [Absence](absence.md)                                           |
| 7   | A deleted variable takes its row with it: `x + y >= 1` has no row where `y` is deleted. Inside a `sum` it is one term fewer, and the row stays. So `sum(x + y)` and `sum(x) + sum(y)` are different constraints.                            | [Absence](absence.md#how-absence-travels)                       |
| 8   | A parameter row that is missing from the table reads as `0` in arithmetic and as false in a `where`. Where `0` would change the model, as in a divisor or a bound, the missing row is refused instead.                                      | [Absence](absence.md#what-creates-absence)                      |
| 9   | The objective and the constraints may multiply two variables: `p * p * wear`. A bound and a `piecewise:` link may not. `x / y` needs `y` free of variables, and `a ** b` needs both `a` and `b` free of them.                               | [Expressions](expressions.md)                                   |
| 10  | The operators are `sum`, `sum_back`, `at`, `shift`, and `dual` in a reported expression. There are no others, and a file cannot add one. Write a composition of them as a macro.                                                            | [Operators](operators.md)                                       |

## The pages

|                                                                         |                                                                                                               |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| [File shape](file.md)                                                   | the ten keys, `version`, `description`, and how the YAML is read                                              |
| [Dimensions and lookups](dimensions.md)                                 | the axes, and the maps from one axis onto another                                                             |
| [Parameters, variables, constraints and the objective](declarations.md) | the four blocks that carry the math                                                                           |
| [Expressions](expressions.md)                                           | the arithmetic grammar and the `where` grammar, where each kind of name may stand, and how dimensions combine |
| [Reported expressions](reported.md)                                     | named quantities that no constraint or objective uses, which you read back after a solve                      |
| [Operators](operators.md)                                               | `sum`, `sum_back`, `at` and `shift`                                                                           |
| [Absence and `where`](absence.md)                                       | which rows are built, and which are not                                                                       |
| [Piecewise curves and SOS](piecewise.md)                                | `piecewise:` and `sos:`                                                                                       |
| [Reading a loaded model](reading.md)                                    | what a program gets when it loads a model                                                                     |
| [Errors and limits](errors.md)                                          | what fails when, and what the language will not express                                                       |

Building the model, solving it and reading the answer back are the work of the
program that reads the file, such as an engine or a renderer. Nothing that
program does changes what the file means.
