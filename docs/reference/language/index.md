# The language

A model is one YAML file. It declares the axes the model runs over, the data it
expects, the decisions the solver makes, and the rules those decisions obey —
and nothing else: no Python state changes what a file means, and the same file
means the same model whichever solver takes it.

```yaml title="dispatch.yaml"
description: Least-cost dispatch of a generator fleet against an hourly load.

dimensions:
  snapshot: { dtype: int }
  generator: { values: [wind, solar, gas] }

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

That file is a complete model; the pages here are the exact rules.

## Ten rules the language reduces to

**Nothing is guessed.** Where a file does not determine the answer, loading
fails and the message names the rewrite. Every rule below is that one principle
in a different position, and each links to the page that spells it out.

| #   | Rule                                                                                                                                                                                                                                                                                                                                                      |                                                        |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| 1   | Ten declaration keys plus `version` and `description`, and the schema is **closed at every level** — an unknown key is an error naming the near miss. Booleans are YAML 1.2, so `no` / `on` / `off` stay labels.                                                                                                                                          | [File shape](file.md)                                  |
| 2   | Everything decidable without data is **decided without data**.                                                                                                                                                                                                                                                                                            | [Errors](errors.md)                                    |
| 3   | **One flat namespace, no shadowing** — a collision is a load error naming both declarations.                                                                                                                                                                                                                                                              | [Names](expressions.md#name-resolution)                |
| 4   | **Position decides which kinds of name are legal**, and a name's kind is fixed at load time. A dimension is never legal in a value position: it is a coordinate space, not data.                                                                                                                                                                          | [Names](expressions.md#name-resolution)                |
| 5   | **Dim sets compose by union.** A constraint must _equal_ its `foreach`; an objective must carry **none**; a `where` or a bound must not _exceed_ its frame.                                                                                                                                                                                               | [Dim algebra](expressions.md#dim-algebra)              |
| 6   | **Four constructs create absence**, and nothing else does. It is a state of a _variable_; a constraint's own `where:` deletes its row directly.                                                                                                                                                                                                           | [Absence](absence.md)                                  |
| 7   | Through arithmetic absence **spreads, taking the row with it**. Out of a reduction it does not — so `sum(x + y)` and `sum(x) + sum(y)` are different questions.                                                                                                                                                                                           | [Absence](absence.md#how-absence-travels)              |
| 8   | **Identity of the position.** A missing value reads as whatever makes it contribute nothing — zero as a coefficient, false in a `where`. Where no such reading exists it is refused: a divisor, a bound.                                                                                                                                                  | [Absence](absence.md), [Operators](operators.md#shift) |
| 9   | **Degree 2 in the math, degree 1 beside it**: the objective and constraints take `variable * variable`; a bound, a named expression and a `piecewise:` link do not. `/` always needs a variable-free divisor, and `**` a base and an exponent that carry no variable. Where a quadratic model can _land_ is a separate axis — ask `check(model, sink=…)`. | [Expressions](expressions.md)                          |
| 10  | **The operator set is closed.** Compositions go in `macros:`.                                                                                                                                                                                                                                                                                             | [Operators](operators.md)                              |

## The pages

|                                                       |                                                                                              |
| ----------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| [File shape](file.md)                                 | the ten keys, `version`, `description`, and how the YAML is read                             |
| [Dimensions and lookups](dimensions.md)               | the axes, and the maps their members carry                                                   |
| [Parameters, variables, constraints](declarations.md) | the four blocks that make up the math                                                        |
| [Expressions](expressions.md)                         | the two grammars — arithmetic and `where` — what a name may mean where, and how dims compose |
| [Operators](operators.md)                             | `sum`, `at`, `shift` — the closed set                                                        |
| [Absence and `where`](absence.md)                     | what a mask _means_: which rows are built, and which are not                                 |
| [Piecewise curves and SOS](piecewise.md)              | `piecewise:` and `sos:`                                                                      |
| [Errors and limits](errors.md)                        | what fails when, and what the language will not say                                          |

Running a model — building, solving, reading an answer back — belongs to a
consumer of the AST, not to this package. Nothing a consumer does changes what
a file means.
