<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Parameters, variables, constraints and the objective

These four blocks carry the math, and `given:` names what the math reads from
another file. Each takes an optional `description:`, free text that the
[typeset](../typeset.md#descriptions) legend prints.

## `parameters`

A parameter declares a shape and nothing more. The engine that builds the model
supplies the numbers, by name, from its own tables.

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

| Field                           |                                                                                                                   |                        |
| ------------------------------- | ----------------------------------------------------------------------------------------------------------------- | ---------------------- |
| `dims`                          | required. The dimensions it is indexed by                                                                         |                        |
| `where`                         | which coordinates exist ([absence](absence.md))                                                                   | default `null`         |
| `bounds.lower` / `bounds.upper` | a number, or the name of a `float` or `int` parameter                                                             | default `-inf` / `inf` |
| `domain`                        | `continuous`, `integer` or `binary`. `binary` carries fixed 0/1 bounds                                            | default `continuous`   |
| `absence`                       | `undefined` or `zero`: what a masked-out coordinate means ([absence](absence.md#what-a-missing-coordinate-means)) | default `undefined`    |
| `description`                   | free text                                                                                                         | default `null`         |

!!! warning "A bound you omit leaves the variable unbounded on that side"

    You write non-negativity. The language does not assume it.

A bound is a name or a number: `upper: capacity` is accepted,
and `upper: -rating` is refused. Ship the negated column as data. The dimensions of
a bound parameter are a subset of the variable's.

Equal bounds pin a variable ([fix a quantity](../../howto/pin-a-variable.md)).
A pinned variable is still a variable.

## `given`

`given:` holds what this file reads and does not build: columns under
`variables:`, row families under `constraints:`. It takes those two keys and no
other. A file with a `given:` block loads and prints on its own.

### `given: variables`

A given variable is a column this file reads and another file introduces.

```yaml
dimensions:
  snapshot: { dtype: int }
  port: { dtype: str }
  generator: { dtype: str }
relations:
  gen_port: { key: generator, values: port }
variables:
  gen_p: { dims: [snapshot, generator], bounds: { lower: 0 } }
given:
  variables:
    flow:
      dims: [snapshot, port]
      description: what a port puts into its bus
constraints:
  gen_injects:
    dims: [snapshot, generator]
    expression: at(flow, by=gen_port, over=port, into=generator) == gen_p
```

| Field         |                                                   |                      |
| ------------- | ------------------------------------------------- | -------------------- |
| `dims`        | required. The dimensions the column is indexed by |                      |
| `domain`      | `continuous`, `integer` or `binary`               | default `continuous` |
| `description` | free text                                         | default `null`       |

There is no `bounds` and no `where`. The file that introduces the column owns
both.

An expression reads a given variable as it reads any other. A name declared
under both `variables:` and `given: variables:` is refused. The typeset legend
lists a given variable under _Given_, and prints no domain line for it.

Where nothing in this language introduces the column, the program carries the
declaration for a consumer to bind
([what a program does not build](../reading.md#what-a-program-does-not-build)).

### `given: constraints`

A given constraint is a row family this file reads the dual of and another
model builds.

```yaml
dimensions:
  snapshot: { dtype: int }
  bus: { dtype: str }
given:
  constraints:
    balance:
      dims: [snapshot, bus]
      description: the host model clears each bus
expressions:
  price:
    expression: dual(balance)
```

| Field         |                                                   |                |
| ------------- | ------------------------------------------------- | -------------- |
| `dims`        | required. The dimensions the row family runs over |                |
| `description` | free text                                         | default `null` |

There is no `expression` and no `sense`.
`dual(name)` is the only place a given row family may be named, and the frame
gives the reported expression its dimensions. A name declared under both
`constraints:` and `given: constraints:` is refused.

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

`dims: []` gives one scalar row, for a rule such as a system-wide budget. A
scalar variable may not carry a `where`; put the condition on the constraints
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
are different models.

There is one objective block. To pursue several goals, weight them into one
expression.
