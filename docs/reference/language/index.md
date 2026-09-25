<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# The language

A spec is one YAML file. It declares the axes the spec runs over, the data it
expects, the decisions the solver makes, and the rules those decisions obey.

```yaml title="dispatch.yaml"
description: Least-cost dispatch of a generator fleet against an hourly load.

dimensions:
  snapshot: { dtype: int }
  generator: { dtype: str }

parameters:
  load: { dims: [snapshot] }
  cost: { dims: [generator] }
  capacity: { dims: [generator] }

variables:
  dispatch:
    dims: [snapshot, generator]
    where: "capacity > 0"
    bounds: { lower: 0, upper: capacity }

constraints:
  power_balance:
    dims: [snapshot]
    expression: sum(dispatch, over=generator) == load

objective:
  sense: minimize
  expression: sum(dispatch * cost) # an objective is one number, so the sum is written
```

That file is a complete spec. The pages of this section give the exact rules,
and the [glossary](../glossary.md) defines each word they use in a fixed sense.

## The ten rules

`to_spec` refuses a file that breaks one of these rules, with a message that
names the fix.

| #   | Rule                                                                                                                                                                  |                                                                 |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| 1   | A file has twelve declaration keys, plus `version` and `description`. An unknown key is refused, with the nearest valid key named.                                    | [File shape](file.md)                                           |
| 2   | Everything that can be checked without data is checked when the file loads.                                                                                           | [Errors](errors.md)                                             |
| 3   | Every name is declared once. A parameter and a dimension both called `snapshot` is refused.                                                                           | [Names](expressions.md#name-resolution)                         |
| 4   | Where a name may stand depends on what it is. A dimension follows `over=` or `along=`, and is never multiplied.                                                       | [Names](expressions.md#name-resolution)                         |
| 5   | `a + b` carries the dimensions of `a` and of `b` together. A constraint's expression carries exactly its `dims`, and the objective carries none.                      | [How dimensions combine](expressions.md#how-dimensions-combine) |
| 6   | A variable's `where:` deletes the variable at the masked coordinates. A constraint's `where:` deletes the row.                                                        | [Absence](absence.md)                                           |
| 7   | A deleted variable takes its row with it. Inside a `sum` it is one term fewer, and the row stays.                                                                     | [Absence](absence.md#how-absence-travels)                       |
| 8   | A parameter row missing from the table reads as `0` in arithmetic and as false in a `where`. Where `0` would change the meaning, the row is refused.                  | [Absence](absence.md#what-creates-absence)                      |
| 9   | Two variables may be multiplied in the objective and in a constraint, and nowhere else. `x / y` and `a ** b` need their divisor, base and exponent free of variables. | [Expressions](expressions.md)                                   |
| 10  | The operators are `sum`, `sum_back`, `at` and `shift`, plus `dual` in a reported expression. A file cannot add one.                                                   | [Operators](operators.md)                                       |
