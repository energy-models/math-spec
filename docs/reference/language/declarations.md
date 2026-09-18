<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Parameters, variables, constraints and the objective

These four blocks carry the math. Each takes an optional `description:`, free
text that every tool reading the model keeps, and that the
[typeset](../typeset.md#descriptions) legend prints.

## `parameters`

A parameter declares a shape and nothing more. The engine that builds the model
supplies the numbers, by name, from its own tables. How the engine reads those
tables is fixed by [three rules](dimensions.md#where-the-members-come-from) that
every engine follows.

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

The `dtype` is a claim about the values, and the column has to match it:

| declared | the column                        |                                                                 |
| -------- | --------------------------------- | --------------------------------------------------------------- |
| `float`  | a float column, or an integer one | whole numbers are numbers, and this is the one widening allowed |
| `int`    | an integer column                 | so a fractional position or offset cannot arrive                |
| `bool`   | a boolean column                  | `1` and `0` are not booleans. Cast the column, or declare `int` |
| `str`    | a string column                   |                                                                 |

The `dtype` decides four things: whether the name is a value in an
[expression](expressions.md); what a `where` comparison is checked against; what
a bare name in a [`where`](expressions.md#where-strings) means; and whether the
name may stand where an operator reads a
[position](operators.md#an-offset-that-differs-per-entity).

Only `float` and `int` are values. A `str` parameter is a label and a `bool`
parameter is a mask: each selects rows in a [`where`](expressions.md#where-strings)
rather than scaling them, and writing either as a coefficient, a term or a
divisor is a load error. A `0` or `1` that is meant to be multiplied by is
declared `dtype: int`.

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

| Field                           |                                                                                                                                              |                        |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| `dims`                          | required. The dimensions it is indexed by                                                                                                    |                        |
| `where`                         | which coordinates exist ([absence](absence.md))                                                                                              | default `null`         |
| `bounds.lower` / `bounds.upper` | a number, or the name of a `float` or `int` parameter. Two numbers that cross are refused at load. A named bound is checked against its data | default `-inf` / `inf` |
| `domain`                        | `continuous`, `integer` or `binary`. `binary` carries fixed 0/1 bounds                                                                       | default `continuous`   |
| `absence`                       | `undefined` or `zero`: what a masked-out coordinate means ([absence](absence.md#what-a-missing-coordinate-means))                            | default `undefined`    |
| `description`                   | free text                                                                                                                                    | default `null`         |

!!! warning "A bound you omit leaves the variable unbounded on that side"

    You write non-negativity. The language does not assume it.

A bound is a name or a number, never arithmetic: `upper: capacity` is accepted,
and `upper: -rating` is refused. Ship the negated column as data. The dimensions
of a bound parameter must not exceed its `dims`.

Equal bounds pin a variable. A pinned variable is still a variable, so
`size * on` is `variable * variable`, and a pinned variable cannot stand in
another variable's `bounds`.

## `constraints`

One block is one rule. The name of the block is the name of the constraint, and
that name is how a row is read back after a solve.

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

The dimensions of the expression must **equal** its `dims`. See
[how dimensions combine](expressions.md#how-dimensions-combine).

Either side of the comparator may carry variables, and one side must. A
comparison between numbers and parameters alone is refused at load, because it
is settled before the solve. A single _row_ can still end up with no variable
terms, because the data left its terms nowhere to sit. Such a row is not built.
See [absence](absence.md#rows-with-no-variable-terms).

`dims: []` gives one scalar row, for a rule such as a system-wide budget. An
empty dimension list means one value for a parameter, one column for a variable
and one row for a constraint, so a scalar is never written as a dummy dimension
of size 1. A scalar _variable_ may not carry a `where`
([#340](https://github.com/fluxopt/lpspec/issues/340)); put the condition on the
constraints that use it.

Two regimes of one rule are two blocks, each under its own `where:`
([state a rule that differs by regime](../../howto/regimes.md)).

## `objective`

The objective is a single block with no name. Its value is a scalar, so there is
nothing for a name to read back.

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

The expression must be **scalar**. Anything else is a load error that names the
`sum` it wants. Nothing is summed for you: `sum(x * a) + sum(y * b)` and
`sum(x * a + y * b)` are both allowed, and they are different models.

There is one objective block. To pursue several goals, weight them into one
expression.
