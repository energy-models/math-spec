<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Parameters, variables, constraints and the objective

These four blocks carry the math. Each takes an optional `description:`.

A description is free text with no length limit. The parser throws a `#` comment
away, but keeps a description, so a renderer or a checker can print it. The
[typeset](../typeset.md) legend prints the description of every dimension,
parameter and variable.

A description is **plain prose, with one piece of notation**. A name in
backticks, such as `` `capital_cost` ``, sets in monospace in every output
format. Everything else is text, and each format escapes whatever its own
syntax would read as markup: an underscore stays an underscore, and `$\ell$`
prints as those five characters. Write the thing rather than its symbol: "flow
on a line", not "flow on line $\ell$".

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
parameter is a mask: each names rows rather than scaling them. Writing either
one as a coefficient, a term or a divisor is a load error, and nothing casts it
on the way past.

- Select with a label: `where: "fuel == 'gas'"`. Carry the numbers that the label
  picks out in a parameter of their own.
- Mask with a flag: `where: "committable"`.
- Declare `dtype: int` where a `0` or `1` is meant to arrive as data and be
  multiplied by.

## `variables`

A variable is what the solver decides. There is one column per coordinate of
`dims`.

```yaml
dimensions:
  snapshot: { dtype: int }
  generator: { dtype: str }
parameters:
  p_max: { dims: [generator] }
variables:
  p:
    dims: [snapshot, generator]
    where: "p_max > 0"
    bounds:
      lower: 0
      upper: p_max
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

A bound is a name or a number, never arithmetic. `upper: p_max` is accepted, and
`upper: -rating` is refused with a message that says so. Ship the negated column
as data. Arithmetic in a bound is
[#31](https://github.com/fluxopt/lpspec/issues/31). The dimensions of a bound
parameter must not exceed its `dims`.

Equal bounds pin a variable. That is how one declaration covers a quantity that
is a decision in one model and data in another: bind `lower` and `upper` to the
same value where the quantity is fixed, and `rate - relmax * size <= 0` is one
equation whether `size` is chosen or given. A pinned variable is still a
variable, so `size * on` is `variable * variable`, and a pinned variable cannot
stand in another variable's `bounds`.

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
  p: { dims: [snapshot, generator] }
constraints:
  power_balance:
    dims: [snapshot]
    expression: sum(p, over=generator) == load
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

Two regimes of one rule are two blocks, each with a name a reader chose:

<!-- doctest: wrap=constraints -->

```yaml
storage_balance:
  dims: [snapshot, storage]
  expression: soc == shift(soc, over=snapshot, offset=1) * (1 - loss) + charge - discharge

storage_balance_initial:
  dims: [snapshot, storage]
  where: "position(snapshot) == 0"
  expression: soc == soc_initial
```

`shift` vacates the first snapshot, and a vacated position is
[absent](absence.md), so the first row of `storage_balance` drops without a
`where` saying so. Writing `edge='wrap'` and gating on `where: "snapshot > 0"`
builds the same rows here, but a different model on a horizon that does not start
at 0, because the gate hardcodes the origin.

## `objective`

The objective is a single block with no name. Its value is a scalar, so there is
nothing for a name to read back.

```yaml
dimensions:
  generator: { dtype: str }
parameters:
  cost: { dims: [generator] }
variables:
  p: { dims: [generator] }
objective:
  sense: minimize
  expression: sum(p * cost)
```

| Field         |                                          |                    |
| ------------- | ---------------------------------------- | ------------------ |
| `expression`  | required. Arithmetic, with no comparator |                    |
| `sense`       | `minimize` or `maximize`                 | default `minimize` |
| `description` | free text                                | default `null`     |

The expression must be **scalar**. Anything else is a load error that names the
`sum` it wants.

Nothing is summed for you, so the file says where each sum closes. With `x` and
`a` on `i`, and `y` and `b` on `j`, `sum(x * a) + sum(y * b)` has `|i| + |j|`
terms and `sum(x * a + y * b)` has `|i| · |j|`. Both are allowed, and they are
different models.

A second objective cannot be written, because the schema holds one block. To
pursue several goals, weight them into one expression.
