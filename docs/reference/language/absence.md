# Absence and `where`

A coordinate where a **variable does not exist**. Not a value, not a zero, but
a state the language tracks — and the thing to understand before writing a
sparse model, because a mask does not shrink a model by zeroing it out. It
shrinks it by not building it.

```yaml
dimensions:
  snapshot: {dtype: int}
  generator: {dtype: str}
parameters:
  p_max: {dims: [generator]}
variables:
  p:
    foreach: [snapshot, generator]
    where: "p_max > 0"
```

`p` has **no column at all** where `p_max` is zero. A retired generator costs
nothing to carry in the data, and the built model is smaller than the
coordinate product. What a `where:` may *say* is the
[grammar](expressions.md#where-strings); this page is what it means.

## What creates absence

| Construct | What is absent |
|---|---|
| `where:` on a variable | the variable, at the masked coordinates |
| `where:` on a constraint | the row |
| `shift(x, over=d, offset=n)` with no `edge=` | the vacated edge coordinate ([shift](operators.md#shift)) |
| a label a lookup does not map | that label's group membership ([lookups](dimensions.md#lookups)) |

Four constructs, and nothing else. Absence is a property of **variables**: it
is a variable that is missing, and a term carrying one takes its row with it.
The second row of the table is the one exception — a constraint's own `where:`
deletes a row directly, with nothing absent in it.

**A sparse parameter table creates none.** Missing rows are compressed
encoding, and what one reads as is the value that makes it contribute nothing —
or a refusal, where no such reading exists:

| Position | A missing parameter row | Why that reading |
|---|---|---|
| coefficient — `w * x` | zero: the term does not participate | `0` is the identity of a sum, so the term contributes nothing |
| `where` operand | false | a coordinate whose data is missing is not one the model can claim exists |
| divisor — `x / d` | **refused**, where the model divides by it | nothing contributes nothing: `0` divides by zero, `1` rescales, dropping rewrites the constraint |
| a comparison's whole constant side — `x <= cap` | **refused**, where the row is built | the fill would *be* the bound, so `x <= 0` would bind where the model said nothing |
| a [`piecewise:`](piecewise.md) curve's values | **refused**, where the block builds a weight for it — which `points:` is how you say | the fill would be a breakpoint at the origin, and the weights would mix onto it |
| `bounds:` | an error | unbounded is not bounded-at-zero |

The row a zeroed coefficient sits in normally survives; where the missing rows
cover *every* term of it, it reaches the shape
[below](#a-row-with-no-variable-terms-is-not-built) and is not built.

The refusals are keyed to **the rows a declaration actually builds**, never to
the coordinate product: a coordinate a `where` already removed asks no
question, so supplying data only where the model uses it stays the ordinary
idiom. That is also what makes masking a real remedy rather than a workaround:

<!-- doctest: wrap=constraints -->
```yaml
c:
  foreach: [g]
  where: cap  # no row where `cap` has none, instead of a row reading `x <= 0`
  expression: x <= cap
```

Three answers — supply the rows, mask them out, drop the declaration — and the
language picks none of them for you.

**The asymmetry is the one that bites.** `x - rel_max * size <= 0` **loses the
row** where the *variable* `size` is masked, and **keeps** it as `x <= 0` where
the *parameter* `rel_max` has no row — feasible, plausible, no error. A missing
correction term tightens in the safe direction and is a legitimate idiom; a
missing coefficient that *is* the bound rewrites what the constraint says.

## How absence travels

**Through arithmetic it spreads, taking the row with it.** `x + y >= 10` is *no
constraint* where `y` is masked — not `x >= 10`.

**Out of a reduction it does not.** `sum(x, over=d)` is defined when only some
of `d` exists, or one masked component would delete a system-wide accounting
row. So these two spellings ask different questions:

| Spelling | Sums over | With `y` absent at `f=b` |
|---|---|---|
| `sum(x + y, over=f)` | where the **summand** exists | `x[a] + y[a]` — `x[b]` goes with the absent `y[b]` |
| `sum(x, over=f) + sum(y, over=f)` | each operand over **its own** domain | `x[a] + x[b] + y[a]` |

*The total of the net where the net is defined*, against *the total in minus
the total out*. Rewriting one into the other reads the absent `y[b]` as a zero.

## What a missing coordinate means

The default is a *reading*: the coordinate holds a quantity with **no value**,
so an expression needing it is undefined and its row is not asserted — there is
no state of charge for a store that is not there. For other quantities the
missing coordinate is **zero**: a reservoir with no inflow spills nothing, and
that model wants its row. Which one it is belongs to the quantity, so it is said
at the declaration:

<!-- doctest: wrap=variables -->
```yaml
spill:
  foreach: [snapshot, storage]
  where: inflow
  absence: zero      # outside the mask this quantity is zero
soc:
  foreach: [snapshot, storage]
  where: has_storage
  absence: undefined # the default — outside the mask it has no value
```

| Where the variable appears | `undefined` | `zero` |
|---|---|---|
| a bare term — `x + y >= 5` | no row | `x >= 5` |
| a summand — `sum(x + y, over=f)` | the element goes, and its `x` with it | the element stays, `y` worth `0` |
| a reduction — `sum(y, over=f)` | the total over the `y` that exist | the same total, plus zeros |

Only the first two differ: a reduction never propagated absence, so the third
row is the same under either reading.

**`absence: zero` needs a `where:`.** A variable's only source of absence is its
own mask, `foreach` being a product of declared dimensions that holds every
coordinate of it, so the key on an unmasked variable would choose between two
readings of a case that cannot arise. Refused at load, naming the fix.

**There is no third value, and no number.** Over a variable the only
representable fill is zero — a nonzero one would stand a constant where a term
was, the same rule that limits `shift`'s numeric `edge=` over a variable
([operators](operators.md)). A *parameter* wanting `1` says so at the use site,
its missing row being a zero coefficient already rather than an absence.

## A row with no variable terms is not built

Three ways to reach one shape — *a row asserting something about constants
only*: a reduction over an absent set contributed `0`, a missing parameter row
was a zero coefficient, or `sum(x, by=l)` landed on a group with **no
members**, which is the one a topology model meets first — a bus no generator
sits on gets `0 == load`, not a row a solver can act on. The shape decides, not
the provenance.

All three are the **data** leaving a row with nothing to decide. An expression
that names no variable at all is a different matter and is refused when the file
is read, where the whole question is answerable and the message can quote the
line: `p_max <= 1` is true or false before any solve, and no data could make it
otherwise.

A row that a **masked variable** took with it never reaches that shape and is a
different event: absence travels out of the term and deletes the row while its
other terms are still live. `x + y >= 5` is no constraint where `y` is masked —
including where `x` is a variable with a bound of its own.

**All of them are reported, by the same line.** `diagnostics().omissions` gives
`(constraint, rows_not_built)` ([diagnostics](../api.md#diagnostics)), counted
against the constraint that declared them, and empty for a model whose every
declared row reached the solver — which is a reason to `build` a model you mean
to inspect rather than to `solve` it, an answer being the one thing that cannot
report an unenforced constraint.

A recurrence's first row is in there and is the boundary rather than a bug:
`soc == shift(soc, over=t, offset=1) + …` has no row at the first coordinate, the
initial condition being the block written under the complementary `where`. What
the report is *for* is the other case — rows lost to a mask the constraint never
mentions.

## Asking for the other reading

Each rule has a spelling for the opposite intent:

| You want | You write |
|---|---|
| the row kept, the missing term read as zero | `absence: zero` on the variable — or, where only one constraint wants it, two constraints under complementary `where` clauses |
| a vacated shift position to contribute | `shift(x, over=d, offset=n, edge=0)` — the identity of *its* position |
| to test whether a variable exists here | its bare name in a `where` |
| a [`piecewise:`](piecewise.md#piecewise) curve pinned off where its gate does not exist | `absence: zero` on the gate variable — the default leaves the curve *ungated* there, the block emitting its convexity row under complementary masks so absence never deletes it |
| a sparse coefficient to remove the row rather than zero the term | mask on it — `where: "rel_max"` |
| to divide by a parameter you only have some of | mask the row or the variable — `where: "d"`. The divisor is required where the division survives, not everywhere it is indexed |
| a bound only where the data has one | supply the missing value (`inf` is a value), or mask the variable — the two build **different models**, so neither is inferred |

Only one of those is a fill: the coordinate `shift` vacates is *created by the
operator*, so there is no row you could have supplied. Everywhere else the
value is expressible in the data, and that is where it stays.
