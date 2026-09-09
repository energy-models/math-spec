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
  p_max: { dims: [g] }
variables:
  p:
    foreach: [g]
    where: "p_max > 0"
```

With `p_max = {wind: 10, gas: 5, old: 0}`, the model has `p[wind]` and
`p[gas]`. There is no `p[old]`.

The [grammar](expressions.md#where-strings) says what a `where:` may contain.
This page says what the mask means for the rows that are built.

## What creates absence

| Construct                                    | What is absent                                                 |
| -------------------------------------------- | -------------------------------------------------------------- |
| `where:` on a variable                       | the variable, at the masked coordinates                        |
| `where:` on a constraint                     | the row                                                        |
| `shift(x, over=d, offset=n)` without `edge=` | the vacated edge coordinate ([shift](operators.md#shift))      |
| a key a `masked` lookup does not map         | that key's group membership ([lookups](dimensions.md#lookups)) |

Nothing else creates absence. **A missing parameter row is not absence.** A
sparse table is a compressed dense table, and a missing row reads as the value
that contributes nothing: `0` as a coefficient, and `false` in a `where`.

Where no such value exists, loading is refused rather than guessed. There are
four such positions: a divisor, a `bounds:` entry, the whole constant side of a
comparison, and a [`piecewise:`](piecewise.md) breakpoint.

## How absence travels

Through arithmetic, absence spreads and takes the row with it. Out of a summing
operator, it does not.

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

`each` has no row at `old`, so there is no `x[old] >= 1`. `total` sums the
summand wherever the summand exists, so `x[old]` goes away with `y[old]`.
`split` sums each operand over its own domain, so `x[old]` counts. Rewriting one
into the other reads the absent `y[old]` as a zero, and they are different
questions.

Beside a parameter, the rule reads the other way:

```yaml
constraints:
  cap:
    foreach: [g]
    expression: x - rel_max * y <= 0
```

Where the variable `y` is masked, the row is gone. Where the parameter `rel_max`
has no row, it reads as `0`, and the row stands as `x <= 0`. To drop the row
there instead, write `where: rel_max` on the constraint.

Every operator falls on one side of the line, and one question decides which:
does an output slot stand for several input slots, or for one?

| Operator                        | An output slot reads            | An absent input                      |
| ------------------------------- | ------------------------------- | ------------------------------------ |
| `sum(x, over=d)`                | every position along `d`        | is one summand fewer; the row stands |
| `sum(x, by=lookup)`             | every member of the group       | is one summand fewer; the row stands |
| `sum_back(x, over=d, within=w)` | the positions the window covers | is one summand fewer; the row stands |
| `shift(x, over=d, offset=n)`    | one position, `n` back          | _is_ the output, so it spreads       |
| `at(x, by=lookup)`              | one position, through the map   | _is_ the output, so it spreads       |

The three summing operators put several slots into one, so a missing slot gives a
shorter sum and the row survives. A window that reaches past the start of its
axis is short for the same reason. The other two map one slot to one slot, so
absence passes straight through, and the vacated edge of a bare `shift` takes its
row with it.

## What a missing coordinate means

By default a masked coordinate has **no value**. A store that is not there has no
state of charge, so a row that needs that state is not asserted.

Some quantities are **zero** outside their mask. A reservoir with no inflow spills
nothing, and a model like that wants its row. The variable says which reading
applies:

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

At a storage with a store and no inflow, `balance` reads `inflow - soc == 0`. At
a storage with inflow and no store, there is no row.

`absence: zero` needs a `where:`. It is the only fill a variable takes, and it
changes nothing inside a summing operator, because a summing operator never
spread absence.

## Rows with no variable terms

A missing parameter row can leave a row with nothing to decide, such as
`0 == load` at a bus with no generator. Such a row is not built, whatever left it
in that shape. An expression that names no variable _in the file_ is a different
case, and it is refused at load, where the message can quote the line.

The engine that builds the model is the one that knows which rows it did not
build, so it is the engine that reports them: rows lost to a mask, to a deleted
variable, and to this rule. The first row of a storage balance is always among
them, and that is the start of the recurrence rather than a bug.

## Reported values

A [reported expression](reported.md) is arithmetic over solved numbers, so it
inherits their absence by the same rule as above. Through pointwise arithmetic,
a null spreads: `cost / delivered` has no value wherever either operand is
masked. Out of a summing operator, it does not: `sum(p, over=g)` is one summand
shorter where a `p[g]` is masked, and stands as long as one slot does.

A quotient whose divisor solved to zero is absent in the same way. The language
has one "no value", and an undefined quotient joins it rather than raising a
separate not-a-number.

`dual(c)` follows the same rule from the constraint side. A row that `c`'s
`where:` leaves unbuilt has no shadow price, so `dual(c)` has no value there.

## Asking for the opposite reading

| You want                                       | You write                                                                                                                    |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| the row kept, the masked variable read as zero | `absence: zero` on the variable                                                                                              |
| the row dropped where a parameter has no data  | `where: p` on the constraint                                                                                                 |
| a vacated shift position to contribute         | `shift(x, over=d, offset=n, edge=0)`                                                                                         |
| to test whether a variable exists here         | its bare name in a `where`                                                                                                   |
| a bound only where the data has one            | supply the bound, because `inf` is a value, or mask the variable. These are different models, so the language infers neither |
