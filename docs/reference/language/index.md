<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# The language

A model is one YAML file. The file declares four things: the axes the model runs
over, the data it expects, the decisions the solver makes, and the rules those
decisions obey. It declares nothing else. No Python state changes what a file
means, and the same file means the same model whichever solver reads it.

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

That file is a complete model. The pages here give the exact rules.

## Ten rules the language reduces to

**Nothing is guessed.** If a file does not determine the answer, loading fails,
and the error message names the rewrite you need. Each rule below is that one
principle applied in a different place. Each rule links to the page that gives
the detail.

| #   | Rule                                                                                                                                                                                                                                                                                                                                                             |                                                        |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| 1   | There are ten declaration keys, plus `version` and `description`. The schema is **closed at every level**, so an unknown key is an error that names the near miss. Booleans follow YAML 1.2, so `no`, `on` and `off` stay names.                                                                                                                                 | [File shape](file.md)                                  |
| 2   | Everything that can be decided without data is **decided without data**.                                                                                                                                                                                                                                                                                         | [Errors](errors.md)                                    |
| 3   | **One flat namespace, and no shadowing.** A collision is a load error that names both declarations.                                                                                                                                                                                                                                                              | [Names](expressions.md#name-resolution)                |
| 4   | **Position decides which kinds of name are legal**, and the kind of a name is fixed at load time. A dimension is never legal in a value position, because it is a coordinate space and not data.                                                                                                                                                                 | [Names](expressions.md#name-resolution)                |
| 5   | **Dimension sets compose by union.** A constraint must _equal_ its `foreach`. An objective must carry **no** dimensions. A `where` or a bound must not _exceed_ its frame.                                                                                                                                                                                       | [Dim algebra](expressions.md#dim-algebra)              |
| 6   | **Four constructs create absence**, and nothing else does. Absence is a state of a _variable_. A constraint's own `where:` deletes its row directly.                                                                                                                                                                                                             | [Absence](absence.md)                                  |
| 7   | Through arithmetic, absence **spreads and takes the row with it**. Out of a reduction it does not spread. So `sum(x + y)` and `sum(x) + sum(y)` ask different questions.                                                                                                                                                                                         | [Absence](absence.md#how-absence-travels)              |
| 8   | **Identity of the position.** A missing value reads as whatever makes it contribute nothing: zero as a coefficient, and false in a `where`. Where no such reading exists, the language refuses it. A divisor and a bound are the two cases.                                                                                                                      | [Absence](absence.md), [Operators](operators.md#shift) |
| 9   | **Degree 2 in the math, degree 1 beside it.** The objective and the constraints take `variable * variable`. A bound, a named expression and a `piecewise:` link do not. `/` always needs a divisor that carries no variable, and `**` needs a base and an exponent that carry none. Where a quadratic model can _land_ is a consumer's axis, not the language's. | [Expressions](expressions.md)                          |
| 10  | **The operator set is closed.** Compositions go in `macros:`.                                                                                                                                                                                                                                                                                                    | [Operators](operators.md)                              |

## The pages

|                                                       |                                                                                                       |
| ----------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| [File shape](file.md)                                 | the ten keys, `version`, `description`, and how the YAML is read                                      |
| [Dimensions and lookups](dimensions.md)               | the axes, and the maps that their members carry                                                       |
| [Parameters, variables, constraints](declarations.md) | the four blocks that make up the math                                                                 |
| [Expressions](expressions.md)                         | the two grammars, arithmetic and `where`: what a name may mean where, and how dimensions compose      |
| [Reported expressions](reported.md)                   | the entries that the math never reads. You read them off a solve, and the math-only restrictions lift |
| [Operators](operators.md)                             | `sum`, `at` and `shift`: the closed set                                                               |
| [Absence and `where`](absence.md)                     | what a mask _means_: which rows are built, and which are not                                          |
| [Piecewise curves and SOS](piecewise.md)              | `piecewise:` and `sos:`                                                                               |
| [Errors and limits](errors.md)                        | what fails when, and what the language will not say                                                   |

Running a model means building it, solving it, and reading an answer back. That
work belongs to a consumer of the syntax tree, not to this package. Nothing a
consumer does changes what a file means.
