<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Absence and `where`

A `where:` does not set a variable to zero. It leaves the variable **unbuilt**
at the masked coordinates: no column, and no value.

```yaml
dimensions:
  g: { dtype: str }
parameters:
  capacity: { dims: [g] }
variables:
  dispatch:
    dims: [g]
    where: "capacity > 0"
```

With `capacity = {wind: 10, gas: 5, old: 0}`, the model has `dispatch[wind]` and
`dispatch[gas]`. There is no `dispatch[old]`.

The [grammar](expressions.md#where-strings) says what a `where:` may hold.

## What creates absence

| Construct                                     | What is absent                                                              |
| --------------------------------------------- | --------------------------------------------------------------------------- |
| `where:` on a variable                        | the variable, at the masked coordinates                                     |
| `where:` on a constraint                      | the row                                                                     |
| `shift(x, along=d, offset=n)` without `edge=` | the vacated edge coordinate ([shift](operators.md#shift))                   |
| a label a relation does not map               | that label's group membership ([relations](relations.md#the-data-contract)) |

Nothing else creates absence. **A missing parameter row is not absence.** It
reads as the value that contributes nothing: `0` as a coefficient, and `false`
in a `where`.

Where no such value exists, loading is refused. There are four such positions:
a divisor, a `bounds:` entry, the whole constant side of a comparison, and a
[`piecewise:`](piecewise.md) breakpoint. For a bound only where the data has
one, supply `inf` elsewhere or mask the variable.

## How absence travels

Through arithmetic, absence spreads and takes the row with it. Out of a summing
operator, it does not.

```yaml
variables:
  x: { dims: [g] }
  y: { dims: [g], where: "capacity > 0" } # no y[old]
constraints:
  each:
    dims: [g]
    expression: x + y >= 1 # rows at wind and gas; no row at old
  total:
    dims: []
    expression: sum(x + y, over=g) >= 1 # x[wind] + y[wind] + x[gas] + y[gas] >= 1
  split:
    dims: []
    expression: sum(x, over=g) + sum(y, over=g) >= 1 # x[old] is back in
```

`total` sums the summand wherever the summand exists. `split` sums each
operand over its own domain. The two are different constraints.

Beside a parameter, the rule reads the other way:

```yaml
constraints:
  cap:
    dims: [g]
    expression: x - rel_max * y <= 0
```

Where the variable `y` is masked, the row is gone. Where the parameter `rel_max`
has no row, it reads as `0`, and the row stands as `x <= 0`. To drop the row
there instead, write `where: rel_max` on the constraint.

| Operator                              | An output slot reads            | An absent input                      |
| ------------------------------------- | ------------------------------- | ------------------------------------ |
| `sum(x, over=d)`                      | every position along `d`        | is one summand fewer; the row stands |
| `sum(x, by=relation, over=a, into=b)` | every member of the group       | is one summand fewer; the row stands |
| `sum_back(x, along=d, window=w)`      | the positions the window covers | is one summand fewer; the row stands |
| `shift(x, along=d, offset=n)`         | one position, `n` back          | _is_ the output, so it spreads       |
| `at(x, by=relation, over=a, into=b)`  | one position, through the map   | _is_ the output, so it spreads       |

## What a missing coordinate means

By default a masked coordinate has **no value**, and a row that needs it is not
built. Some quantities are **zero** outside their mask, and the variable says
which reading applies:

```yaml
variables:
  spill:
    dims: [storage]
    where: has_inflow
    absence: zero # outside the mask spill is 0 and the row stands
  soc:
    dims: [storage]
    where: has_store # the default, absence: undefined — no row
constraints:
  balance:
    dims: [storage]
    expression: inflow - spill - soc == 0
```

At a storage with a store and no inflow, `balance` reads `inflow - soc == 0`. At
a storage with inflow and no store, there is no row.

`absence: zero` needs a `where:`. It changes nothing inside a summing operator.

## Rows with no variable terms

A missing parameter row can leave a row with nothing to decide, such as
`0 == load` at a bus with no generator. Such a row is not built. An expression that names no variable _in the file_ is refused at
load.

## Reported values

A [reported expression](named.md#reported-expressions) inherits the absence of
the solved numbers it reads, by the rules above. A quotient whose divisor solved
to zero is absent too. A deleted row has
[no dual](named.md#reading-a-constraints-dual).
