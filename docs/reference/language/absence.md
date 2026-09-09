<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Absence and `where`

This page is what a `where:` means. It does not zero a variable out; it leaves
the variable **unbuilt** at the masked coordinates: no column, no value. Every
rule here follows from that.

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

With `p_max = {wind: 10, gas: 5, old: 0}` the model has `p[wind]` and `p[gas]`,
and no `p[old]`. What a `where:` may say is the
[grammar](expressions.md#where-strings).

## What creates absence

| Construct                                    | What is absent                                                   |
| -------------------------------------------- | ---------------------------------------------------------------- |
| `where:` on a variable                       | the variable, at the masked coordinates                          |
| `where:` on a constraint                     | the row                                                          |
| `shift(x, over=d, offset=n)` without `edge=` | the vacated edge coordinate ([shift](operators.md#shift))        |
| a label a lookup does not map                | that label's group membership ([lookups](dimensions.md#lookups)) |

Nothing else does. **A missing parameter row is not absence.** It reads as the
value that contributes nothing: `0` as a coefficient, `false` in a `where`.
Where no such value exists the load is refused: a divisor, a `bounds:` entry,
the whole constant side of a comparison, a [`piecewise:`](piecewise.md)
breakpoint.

## How absence travels

**Through arithmetic it spreads and takes the row with it. Out of a summing
operator it does not.**

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

`each` has no row at `old`, not `x[old] >= 1`. `total` sums the summand where
the summand exists, so `x[old]` goes with `y[old]`. `split` sums each operand
over its own domain, so `x[old]` counts. Rewriting one into the other reads the
absent `y[old]` as a zero.

Next to a parameter the same rule is asymmetric:

```yaml
constraints:
  cap:
    foreach: [g]
    expression: x - rel_max * y <= 0
```

Where the _variable_ `y` is masked the row is gone. Where the _parameter_
`rel_max` has no row it is `0`, and the row stands as `x <= 0`. To drop the row
there too, write `where: rel_max` on the constraint.

Every operator falls on one side of that line, and one question puts it there:
**does an output slot stand for several input slots, or for one?**

| Operator                        | An output slot reads            | An absent input                      |
| ------------------------------- | ------------------------------- | ------------------------------------ |
| `sum(x, over=d)`                | every position along `d`        | is one summand fewer; the row stands |
| `sum(x, by=lookup)`             | every member of the group       | is one summand fewer; the row stands |
| `sum_back(x, over=d, within=w)` | the positions the window covers | is one summand fewer; the row stands |
| `shift(x, over=d, offset=n)`    | one position, `n` back          | _is_ the output, so it spreads       |
| `at(x, by=lookup)`              | one position, through the map   | _is_ the output, so it spreads       |

A window that reaches past the start of its axis is short, not absent. A bare
`shift`'s vacated edge takes its row with it.

## What a missing coordinate means

By default a masked coordinate has **no value**: a store that is not there has
no state of charge, so a row needing it is not built. Some quantities are
**zero** outside their mask, and that model keeps the row: a reservoir with no
inflow spills nothing. The variable says which:

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

At a storage with a store and no inflow, `balance` reads `inflow - soc == 0`.
At one with inflow and no store, there is no row.

`absence: zero` needs a `where:`, is the only fill a variable takes, and changes
nothing inside a summing operator.

## A row with no variable terms is not built

A missing parameter row can leave a row with nothing to decide: `0 == load` at
a bus no generator sits on. Such a row is not built, whatever left it that
shape. An expression that names no variable _in the file_ is refused at load,
where the message quotes the line.

Every row not built, by a mask, a spread absence or this rule, is reported by
`diagnostics().omissions` as `(constraint, rows_not_built)`. A recurrence's
first row is in there, and is the boundary.

## Reported values follow the rows that were built

A [reported expression](reported.md) is arithmetic over solved numbers, so it
inherits their absence by the same fork as [above](#how-absence-travels).
Through pointwise arithmetic a null spreads and takes the coordinate with it:
`cost / delivered` has **no value** wherever either operand is masked. Out of a
summing operator it does not: `sum(p, over=g)` is one summand shorter where a
`p[g]` is masked, and stands so long as one slot does.

A quotient whose divisor **solved to zero** reads the same null. The language
has one "no value", and an undefined quotient joins it rather than raising a
separate not-a-number.

A [`dual(c)`](reported.md#reading-a-constraints-dual) has **no value** where
`c`'s row was not built: an unbuilt row has no shadow price, and the null is
the same one, not a zero.

## Asking for the other reading

| You want                                       | You write                                                                                     |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------- |
| the row kept, the masked variable read as zero | `absence: zero` on the variable                                                               |
| the row dropped where a parameter has no data  | `where: p` on the constraint                                                                  |
| a vacated shift position to contribute         | `shift(x, over=d, offset=n, edge=0)`                                                          |
| to test whether a variable exists here         | its bare name in a `where`                                                                    |
| a bound only where the data has one            | supply it (`inf` is a value), or mask the variable — different models, so neither is inferred |
