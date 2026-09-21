<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Absence and `where`

A `where:` does not set a variable to zero. It leaves the variable **unbuilt**
at the masked coordinates: no column, and no value. Every rule on this page
follows from that.

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

The [grammar](expressions.md#where-strings) says what a `where:` may contain.
This page says what the mask means for the rows that are built.

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
[`piecewise:`](piecewise.md) breakpoint.

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

`each` has no row at `old`. `total` sums the summand wherever the summand
exists, so `x[old]` goes away with `y[old]`. `split` sums each operand over its
own domain, so `x[old]` counts. The two are different constraints.

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

| Operator                         | An output slot reads            | An absent input                      |
| -------------------------------- | ------------------------------- | ------------------------------------ |
| `sum(x, over=d)`                 | every position along `d`        | is one summand fewer; the row stands |
| `sum(x, by=relation(a -> b))`    | every member of the group       | is one summand fewer; the row stands |
| `sum_back(x, along=d, window=w)` | the positions the window covers | is one summand fewer; the row stands |
| `shift(x, along=d, offset=n)`    | one position, `n` back          | _is_ the output, so it spreads       |
| `at(x, by=relation(c))`          | one position, through the map   | _is_ the output, so it spreads       |

## What a missing coordinate means

By default a masked coordinate has **no value**. A store that is not there has no
state of charge, so a row that needs that state is not built.

Some quantities are **zero** outside their mask. A reservoir with no inflow spills
nothing, and a model like that wants its row. The variable says which reading
applies:

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
`0 == load` at a bus with no generator. Such a row is not built, and the engine
reports it. An expression that names no variable _in the file_ is refused at
load.

## Reported values

A [reported expression](named.md#reported-expressions) is arithmetic over
solved numbers, and it inherits their absence by the rule above. Through
arithmetic, a null spreads: `cost / delivered` has no value wherever either
operand is masked. Out of a summing operator, it does not.

A quotient whose divisor solved to zero is absent in the same way. `dual(c)` has
no value at a row that `c`'s `where:` leaves unbuilt.

## Asking for the opposite reading

| You want                                       | You write                                                                                    |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------- |
| the row kept, the masked variable read as zero | `absence: zero` on the variable                                                              |
| the row dropped where a parameter has no data  | `where: capacity` on the constraint                                                          |
| a vacated shift position to contribute         | `shift(x, along=d, offset=n, edge=0)`                                                        |
| to test whether a variable exists here         | its bare name in a `where`                                                                   |
| a bound only where the data has one            | supply the bound, because `inf` is a value, or mask the variable. These are different models |
