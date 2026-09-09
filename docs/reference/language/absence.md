<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Absence and `where`

A `where:` does not zero a variable out. It leaves the variable **unbuilt** at
the masked coordinates. There is no column there, and no value. Every rule on
this page follows from that one fact.

```yaml
dimensions:
  g: { dtype: str }
parameters:
  p_max: { dims: [g] }
variables:
  p:
    foreach: [g]
    where: "p_max > 0"
```

With `p_max = {wind: 10, gas: 5, old: 0}`, the model has `p[wind]` and
`p[gas]`. There is no `p[old]`.

The [grammar](expressions.md#where-strings) says what a `where:` may contain.
This page says what it means.

## What creates absence

| Construct                                    | What is absent                                                   |
| -------------------------------------------- | ---------------------------------------------------------------- |
| `where:` on a variable                       | the variable, at the masked coordinates                          |
| `where:` on a constraint                     | the row                                                          |
| `shift(x, over=d, offset=n)` without `edge=` | the vacated edge coordinate ([shift](operators.md#shift))        |
| a label a lookup does not map                | that label's group membership ([lookups](dimensions.md#lookups)) |

Nothing else creates absence. In particular, **a missing parameter row is not
absence.** A sparse table is a compressed dense table, and a missing row reads
as the value that contributes nothing: `0` as a coefficient, and `false` in a
`where`.

Where no such value exists, the load is refused rather than guessed. There are
four such positions: a divisor, a `bounds:` entry, the whole constant side of a
comparison, and a [`piecewise:`](piecewise.md) breakpoint.

## How absence travels

**Through arithmetic, absence spreads and takes the row with it. Out of a
summing operator, it does not.**

```yaml
variables:
  x: { foreach: [g] }
  y: { foreach: [g], where: "p_max > 0" } # no y[old]
constraints:
  each:
    foreach: [g]
    expression: x + y >= 1 # rows at wind and gas; no row at old
  total:
    foreach: []
    expression: sum(x + y, over=g) >= 1 # x[wind] + y[wind] + x[gas] + y[gas] >= 1
  split:
    foreach: []
    expression: sum(x, over=g) + sum(y, over=g) >= 1 # x[old] is back in
```

Look at what each constraint does. `each` has no row at `old` at all, so you do
not get `x[old] >= 1`. `total` sums the summand wherever the summand exists, so
`x[old]` goes away together with `y[old]`. `split` sums each operand over its
own domain, so `x[old]` counts.

These are different questions. If you rewrite one into the other, you read the
absent `y[old]` as a zero.

The same rule beside a parameter gives the asymmetry that catches people out:

```yaml
constraints:
  cap:
    foreach: [g]
    expression: x - rel_max * y <= 0
```

Where the _variable_ `y` is masked, the row is gone. Where the _parameter_
`rel_max` has no row, it reads as `0`, and the row stands as `x <= 0`. If you
want the row dropped there instead, say so with `where: rel_max` on the
constraint.

Every operator falls on one side of that line, and one question decides which
side: **does one output slot stand for several input slots, or for one?**

| Operator                        | An output slot reads            | An absent input                      |
| ------------------------------- | ------------------------------- | ------------------------------------ |
| `sum(x, over=d)`                | every position along `d`        | is one summand fewer; the row stands |
| `sum(x, by=lookup)`             | every member of the group       | is one summand fewer; the row stands |
| `sum_back(x, over=d, within=w)` | the positions the window covers | is one summand fewer; the row stands |
| `shift(x, over=d, offset=n)`    | one position, `n` back          | _is_ the output, so it spreads       |
| `at(x, by=lookup)`              | one position, through the map   | _is_ the output, so it spreads       |

The three summing operators put several slots into one. So a missing slot just
gives a shorter sum, and the row survives. A window that reaches past the start
of its axis is short for the same reason, and it is not absent.

The other two operators map one slot to one slot. There is nothing to sum over,
so absence rides straight through. That is why the vacated edge of a bare
`shift` takes its row with it.

Reading a summing operator as though it spread absence is the same mistake as
rewriting `total` into `split` above, one operator further down.

## What a missing coordinate means

By default a masked coordinate has **no value**. A store that is not there has
no state of charge, so a row that needs that state is not asserted.

But some quantities are **zero** outside their mask. A reservoir with no inflow
spills nothing, and a model like that wants its row. The variable says which of
the two readings applies:

```yaml
variables:
  spill:
    foreach: [storage]
    where: has_inflow
    absence: zero # outside the mask spill is 0 and the row stands
  soc:
    foreach: [storage]
    where: has_store # the default, absence: undefined — no row
constraints:
  balance:
    foreach: [storage]
    expression: inflow - spill - soc == 0
```

At a storage that has a store and no inflow, `balance` reads
`inflow - soc == 0`. At a storage that has inflow and no store, there is no row
at all.

Three things to know about `absence: zero`. It needs a `where:`. It is the only
fill that a variable takes. And it changes nothing inside a summing operator,
because a summing operator never propagated absence in the first place.

## A row with no variable terms is not built

A missing parameter row can leave a row with nothing to decide. An example is
`0 == load` at a bus that no generator sits on. Such a row is not built,
whatever left it in that shape.

An expression that names no variable _in the file_ is a different case. That is
refused at load, where the message can quote the line.

Every row that is not built is reported by `diagnostics().omissions` as
`(constraint, rows_not_built)`. This covers rows lost to a mask, rows lost to a
spread absence, and rows lost to this rule. The first row of a recurrence
appears in that report, and it is the boundary of the recurrence, not a bug.

## Reported values follow the rows that were built

A [reported expression](reported.md) is arithmetic over solved numbers, so it
inherits the absence of those numbers. It does so by the same fork described
[above](#how-absence-travels).

Through pointwise arithmetic, a null spreads and takes the coordinate with it.
So `cost / delivered` has **no value** wherever either operand is masked. That
is the null reading, the one a lookup gets, and not a zero.

Out of a summing operator, a null does not spread. `sum(p, over=g)` is one
summand shorter where a `p[g]` is masked, and it still stands as long as one
slot does. So a statistic is defined at exactly the coordinates where the rows
it reduces over were built, and it is absent everywhere else.

A quotient whose divisor **solved to zero** is absent in the same way. The row
was built and the numbers are in hand, but the arithmetic has no value there.
So the reported quantity reads that same null. The language has one "no value",
and an undefined quotient joins it rather than raising a separate
not-a-number.

A [`dual(c)`](reported.md#reading-a-constraints-dual) follows the same rule
from the constraint side. A constraint's `where:` leaves its row **unbuilt** at
the masked coordinates. An unbuilt row has no shadow price, so `dual(c)` has
**no value** there. That is the same null, and not a zero. The dual is defined
at exactly those coordinates of `c`'s frame where the row was built.

## Asking for the other reading

| You want                                       | You write                                                                                                                    |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| the row kept, the masked variable read as zero | `absence: zero` on the variable                                                                                              |
| the row dropped where a parameter has no data  | `where: p` on the constraint                                                                                                 |
| a vacated shift position to contribute         | `shift(x, over=d, offset=n, edge=0)`                                                                                         |
| to test whether a variable exists here         | its bare name in a `where`                                                                                                   |
| a bound only where the data has one            | supply the bound, because `inf` is a value, or mask the variable. These are different models, so the language infers neither |
