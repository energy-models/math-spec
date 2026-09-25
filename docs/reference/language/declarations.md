<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Parameters, variables, constraints and the objective

These four blocks carry the math. Each takes an optional `description:`, free
text that the [typeset](../typeset.md#descriptions) legend prints.

## `parameters`

A parameter declares a shape. The numbers arrive by name with the data.

```yaml
dimensions:
  snapshot: { dtype: int }
parameters:
  load:
    dims: [snapshot]
  discount_rate:
    dims: [] # a scalar
```

| Field         |                                                                |                 |
| ------------- | -------------------------------------------------------------- | --------------- |
| `dims`        | required. The dimensions it is indexed by. `[]` means a scalar |                 |
| `dtype`       | `float`, `int`, `bool`, `str`                                  | default `float` |
| `description` | free text                                                      | default `null`  |

The column has to match the `dtype`:

| declared | the column                        |                                               |
| -------- | --------------------------------- | --------------------------------------------- |
| `float`  | a float column, or an integer one |                                               |
| `int`    | an integer column                 |                                               |
| `bool`   | a boolean column                  | `1` and `0` are not booleans. Cast the column |
| `str`    | a string column                   |                                               |

Only `float` and `int` are values. A `str` parameter is a label and a `bool`
parameter is a mask: each selects rows in a
[`where`](expressions.md#where-strings), and writing either as a coefficient,
a term or a divisor is a load error. A `0` or `1` that is meant to be
multiplied by is declared `dtype: int`.

## `variables`

A variable is what the solver decides. There is one column per coordinate of
`dims`.

```yaml
dimensions:
  snapshot: { dtype: int }
  generator: { dtype: str }
parameters:
  capacity: { dims: [generator] }
variables:
  dispatch:
    dims: [snapshot, generator]
    where: "capacity > 0"
    bounds:
      lower: 0
      upper: capacity
```

| Field                           |                                                                                                                   |                      |
| ------------------------------- | ----------------------------------------------------------------------------------------------------------------- | -------------------- |
| `dims`                          | required. The dimensions it is indexed by                                                                         |                      |
| `where`                         | which coordinates exist ([absence](absence.md))                                                                   | default `null`       |
| `bounds.lower` / `bounds.upper` | a finite number, or the name of a `float` or `int` parameter. `null` leaves that side open                        | default `null`       |
| `domain`                        | `continuous`, `integer` or `binary`. `binary` carries fixed 0/1 bounds                                            | default `continuous` |
| `absence`                       | `undefined` or `zero`: what a masked-out coordinate means ([absence](absence.md#what-a-missing-coordinate-means)) | default `undefined`  |
| `description`                   | free text                                                                                                         | default `null`       |

An open side is `null`. A bound is never infinite: `.inf` and `-.inf` are
refused, with `null` named as the rewrite.

A bound is a name or a number: `upper: capacity` is accepted,
and `upper: -rating` is refused. Ship the negated column as data.

Equal bounds pin a variable ([fix a quantity](../../howto/pin-a-variable.md)).
A pinned variable is still a variable.

## `constraints`

One block is one rule. The name of the block is the name of the constraint.

```yaml
dimensions:
  snapshot: { dtype: int }
  generator: { dtype: str }
parameters:
  load: { dims: [snapshot] }
variables:
  dispatch: { dims: [snapshot, generator] }
constraints:
  power_balance:
    dims: [snapshot]
    expression: sum(dispatch, over=generator) == load
```

| Field         |                                                     |                |
| ------------- | --------------------------------------------------- | -------------- |
| `dims`        | required. The rows this rule builds                 |                |
| `expression`  | required. It uses exactly one of `<=`, `>=` or `==` |                |
| `where`       | which rows are built ([absence](absence.md))        | default `null` |
| `description` | free text                                           | default `null` |

The dimensions of the expression must **equal** its `dims`
([how dimensions combine](expressions.md#how-dimensions-combine)).

At least one side of the comparator carries a variable. A comparison between
numbers and parameters alone is refused at load.

`dims: []` gives one scalar row. A scalar variable may not carry a `where`; put the condition on the constraints
that use it.

Two regimes of one rule are two blocks, each under its own `where:`
([state a rule that differs by regime](../../howto/regimes.md)).

## `objective`

The objective is a single block with no name.

```yaml
dimensions:
  generator: { dtype: str }
parameters:
  cost: { dims: [generator] }
variables:
  dispatch: { dims: [generator] }
objective:
  sense: minimize
  expression: sum(dispatch * cost)
```

| Field         |                                          |                    |
| ------------- | ---------------------------------------- | ------------------ |
| `expression`  | required. Arithmetic, with no comparator |                    |
| `sense`       | `minimize` or `maximize`                 | default `minimize` |
| `description` | free text                                | default `null`     |

The expression must be **scalar**. Nothing is summed for you:
`sum(x * a) + sum(y * b)` and `sum(x * a + y * b)` are both allowed, and they
state different objectives.

There is one objective block. To pursue several goals, weight them into one
expression.
