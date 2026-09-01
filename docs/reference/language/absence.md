<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Absence and `where`

A `where:` does not zero a variable out. It leaves the variable **unbuilt** at
the masked coordinates — no column, no value — and every rule on this page
follows from that one fact.

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

With `p_max = {wind: 10, gas: 5, old: 0}` the model has `p[wind]` and `p[gas]`.
There is no `p[old]`. What a `where:` may say is the
[grammar](expressions.md#where-strings); this page is what it means.

## What creates absence

| Construct                                    | What is absent                                                   |
| -------------------------------------------- | ---------------------------------------------------------------- |
| `where:` on a variable                       | the variable, at the masked coordinates                          |
| `where:` on a constraint                     | the row                                                          |
| `shift(x, over=d, offset=n)` without `edge=` | the vacated edge coordinate ([shift](operators.md#shift))        |
| a label a lookup does not map                | that label's group membership ([lookups](dimensions.md#lookups)) |

Nothing else does. In particular **a missing parameter row is not absence**: a
sparse table is a compressed dense one, and the missing row reads as the value
that contributes nothing — `0` as a coefficient, `false` in a `where`. Where no
such value exists the load is refused rather than guessed: a divisor, a
`bounds:` entry, the whole constant side of a comparison, a
[`piecewise:`](piecewise.md) breakpoint.

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

`each` has no row at `old` — not `x[old] >= 1`. `total` sums the summand where
the summand exists, so `x[old]` goes with `y[old]`. `split` sums each operand
over its own domain, so `x[old]` counts. Different questions; rewriting one into
the other reads the absent `y[old]` as a zero.

The same rule next to a parameter is the asymmetry that bites:

```yaml
constraints:
  cap:
    foreach: [g]
    expression: x - rel_max * y <= 0
```

Where the _variable_ `y` is masked the row is gone. Where the _parameter_
`rel_max` has no row it is `0`, and the row stands as `x <= 0`. To drop the row
there instead, say so: `where: rel_max` on the constraint.

Every operator falls on one side of that line, and one question puts it there:
**does an output slot stand for several input slots, or for one?**

| Operator                        | An output slot reads            | An absent input                      |
| ------------------------------- | ------------------------------- | ------------------------------------ |
| `sum(x, over=d)`                | every position along `d`        | is one summand fewer; the row stands |
| `sum(x, by=lookup)`             | every member of the group       | is one summand fewer; the row stands |
| `sum_back(x, over=d, within=w)` | the positions the window covers | is one summand fewer; the row stands |
| `shift(x, over=d, offset=n)`    | one position, `n` back          | _is_ the output, so it spreads       |
| `at(x, by=lookup)`              | one position, through the map   | _is_ the output, so it spreads       |

The three summing operators put several slots into one, so a missing slot is a
shorter sum and the row survives — a window that reaches past the start of its
axis is short for the same reason, not absent. The other two are one slot for
one, so there is nothing to sum over and absence rides straight through, which
is why a bare `shift`'s vacated edge takes its row with it.

Reading a summing operator as though it spread absence is the same error as
rewriting `total` into `split` above, one operator down.

## What a missing coordinate means

By default the masked coordinate has **no value**: a store that is not there
has no state of charge, so a row needing it is not asserted. Some quantities
are **zero** outside their mask — a reservoir with no inflow spills nothing —
and that model wants its row. The variable says which:

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
nothing inside a summing operator, which never propagated absence in the first
place.

## A row with no variable terms is not built

A missing parameter row can leave a row with nothing to decide — `0 == load` at
a bus no generator sits on. Such a row is not built, whatever left it that
shape. An expression that names no variable _in the file_ is different, and is
refused at load where the message can quote the line.

Every row not built — by a mask, by a spread absence, by this rule — is reported
by `diagnostics().omissions` as `(constraint, rows_not_built)`. A recurrence's
first row is in there and is the boundary, not a bug.

## Post-solve values follow the rows that were built

A [post-solve expression](postsolve.md) is arithmetic over solved numbers, so it
inherits their absence — by the same fork as [above](#how-absence-travels).
Through pointwise arithmetic a null spreads and takes the coordinate with it:
`cost / delivered` has **no value** wherever either operand is masked, the null
reading a lookup gets rather than a zero. Out of a summing operator it does not:
`sum(p, over=g)` is one summand shorter where a `p[g]` is masked, and stands so
long as one slot does. A statistic is defined exactly where the rows it reduces
over were built, and absent everywhere they were not.

A quotient whose divisor **solved to zero** is absent the same way. The row was
built and the numbers are in hand, but the arithmetic has no value there, so the
post-solve quantity reads that same null — the language has one "no value", and
an undefined quotient joins it rather than raising a separate not-a-number.

## Asking for the other reading

| You want                                       | You write                                                                                     |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------- |
| the row kept, the masked variable read as zero | `absence: zero` on the variable                                                               |
| the row dropped where a parameter has no data  | `where: p` on the constraint                                                                  |
| a vacated shift position to contribute         | `shift(x, over=d, offset=n, edge=0)`                                                          |
| to test whether a variable exists here         | its bare name in a `where`                                                                    |
| a bound only where the data has one            | supply it (`inf` is a value), or mask the variable — different models, so neither is inferred |
