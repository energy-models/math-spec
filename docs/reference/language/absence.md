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
coordinate product.

## What creates absence

| Construct | What is absent |
|---|---|
| `where:` on a variable | the variable, at the masked coordinates |
| `where:` on a constraint | the row |
| `shift(x, over=d, by=n)` with no `edge=` | the vacated edge coordinate ([shift](operators.md#shift)) |
| a null value in a lookup | that label's group membership ([lookups](dimensions.md#lookups)) |

Four constructs, and nothing else. In particular:

**A sparse parameter table is not one of them.** Missing rows are compressed
encoding, and what one reads as is the value that makes it contribute nothing —
or a refusal, where no such reading exists:

| Position | A missing parameter row | Why that reading |
|---|---|---|
| coefficient — `w * x` | zero: the term does not participate, the row survives | `0` is the identity of a sum, so the term contributes nothing |
| `where` operand | false | a coordinate whose data is missing is not one the model can claim exists |
| divisor — `x / d` | **refused**, where the model divides by it | nothing contributes nothing: `0` divides by zero, `1` rescales, dropping rewrites the constraint |
| a comparison's whole constant side — `x <= cap` | **refused**, where the row is built | the fill would *be* the bound, so `x <= 0` would bind where the model said nothing |
| `bounds:` | an error | unbounded is not bounded-at-zero |

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

Three answers, and the language picks between them for you in none of the
cases: **supply the rows** if the value is what was meant, **mask them out** if
the row should not exist, or **drop the declaration** if the model has no such
quantity.

## Variables and parameters are not symmetrical

Worth learning early, because it is the one asymmetry that bites:

- a **variable** the mask removed is *absent*, and a term carrying it takes its
  whole row with it;
- a **parameter** row that is simply missing is a zero coefficient, and the row
  survives without it.

In one example: `x - rel_max * size <= 0` **loses the row** where the
*variable* `size` is masked, and **keeps** it as `x <= 0` where the *parameter*
`rel_max` has no row — feasible, plausible, no error. A missing correction term
tightens in the safe direction and is a legitimate idiom; a missing coefficient
that *is* the bound rewrites what the constraint says.

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

Everything above is the default, and the default is a *reading*: a coordinate
the mask removed holds a quantity with **no value**, so an expression needing
that value is undefined and its row is not asserted. For many quantities that is
right — there is no state of charge for a store that is not there.

For others the missing coordinate is not undefined at all, it is **zero**. A
reservoir with no inflow spills nothing; a line with no losses loses nothing.
Those models want the row, with the term contributing nothing. Which one it is
belongs to the quantity, so it is said at the declaration:

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

The behaviour follows from the meaning rather than being the thing declared:

| Where the variable appears | `undefined` | `zero` |
|---|---|---|
| a bare term — `x + y >= 5` | no row | `x >= 5` |
| a summand — `sum(x + y, over=f)` | the element goes, and its `x` with it | the element stays, `y` worth `0` |
| a reduction — `sum(y, over=f)` | the total over the `y` that exist | the same total, plus zeros |

Only the first two differ. A reduction never propagated absence — *the total
over the set that exists* is defined under either reading — which is why the
third row is the same in both columns.

**`absence: zero` needs a `where:`.** A variable's only source of absence is its
own mask, `foreach` being a product of declared dimensions that holds every
coordinate of it, so the key on an unmasked variable would choose between two
readings of a case that cannot arise. Refused at load, naming the fix.

**There is no third value, and no number.** Over a variable the only
representable fill is zero: a nonzero one would stand a constant where a term
was, which is the rule that already limits `shift`'s numeric `edge=` over a
variable ([operators](operators.md)). Where a *parameter* wants `1` rather than
`0` the identity is positional and the model says so at the use site — and a
missing parameter row is a zero coefficient already, not an absence.

## A row with no variable terms is not built

Two ways to reach one shape — *a row asserting something about constants only*:
a reduction over an absent set contributed `0`, or a missing parameter row was
a zero coefficient. The shape decides, not the provenance. Such a row
constrains nothing a solver can act on.

A row that a **masked variable** took with it never reaches that shape and is a
different event: absence travels out of the term and deletes the row while its
other terms are still live. `x + y >= 5` is no constraint where `y` is masked —
including where `x` is a variable with a bound of its own.

**Both are reported, by the same line.** `diagnostics().omissions` on a built
model gives `(constraint, rows_not_built)`
([diagnostics](../api.md#diagnostics)) — a row emptied of its terms and a row a
propagated absence deleted both land there, counted against the constraint that
declared them, and it is empty for a model whose every declared row reached the
solver. A declared constraint that goes unenforced is a thing you have to be
able to see, which is a reason to `build` a model you mean to inspect rather
than to `solve` it, an answer being the one thing that cannot report it.

**A recurrence's first row appears here, and is the boundary rather than a bug.**
`soc == shift(soc, over=t, by=1) + …` has no row at the first coordinate, so it
reports one omission per store — the initial condition being the block written
under the complementary `where`. What the report is *for* is the other case: rows
lost to a mask the constraint never mentions, where the number is the difference
between what a declaration asked for and what it was given.

## Asking for the other reading

Each rule has a spelling for the opposite intent:

| You want | You write |
|---|---|
| the row kept, the missing term read as zero | `absence: zero` on the variable — or, where only one constraint wants it, two constraints under complementary `where` clauses |
| a vacated shift position to contribute | `shift(x, over=d, by=n, edge=0)` — the identity of *its* position |
| to test whether a variable exists here | its bare name in a `where` |
| a sparse coefficient to remove the row rather than zero the term | mask on it — `where: "rel_max"` |
| to divide by a parameter you only have some of | mask the row or the variable — `where: "d"`. The divisor is required where the division survives, not everywhere it is indexed |
| a bound only where the data has one | supply the missing value (`inf` is a value), or mask the variable — the two build **different models**, so neither is inferred |

Only one of those is a fill: the coordinate `shift` vacates is *created by the
operator*, so there is no row you could have supplied. Everywhere else the
value is expressible in the data, and that is where it stays.

## Where strings

A `where:` is a boolean mask, and true means "this coordinate exists".

```text
where_expr ::= atom | "NOT" where_expr | where_expr ("AND"|"OR") where_expr
            |  "(" where_expr ")"
atom       ::= NAME | NAME COMPARATOR value | "True" | "False"
COMPARATOR ::= "<=" | ">=" | "==" | "!=" | "<" | ">"
value      ::= NUMBER | QUOTED | NAME_OR_STRING | POSITION
POSITION   ::= "index" "(" NAME "," INTEGER ")"
QUOTED     ::= "'" chars "'" | '"' chars '"'
```

| Surface | Names a… | Meaning |
|---|---|---|
| `name` (bare) | parameter | defined: non-null **and** finite |
| `name` (bare) | variable | the variable exists at this coordinate — the counterpart of the parameter row, and how you say which coordinates the row-dropping rule applies to |
| `name` (bare) | dimension | load error: it is true everywhere, so it reads as a condition and is not one. Compare it instead |
| `name OP value` | parameter | element-wise; a null compares false. The right-hand side is a literal number, or a bare name read as a string coordinate |
| `name OP value` | dimension | a filter on the frame's own coordinate column |
| `name` (bare) | lookup | defined: the label maps somewhere. A lookup may be [partial](dimensions.md#lookups), and this is how a declaration asks for the labels that do map |
| `name OP value` | lookup | a filter on the lookup's column of its `over` dimension's index — which therefore has to be in the frame. A null value is **false**, whatever the comparator |
| `name OP name` | two lookups | the one comparison whose both sides are structure. Legal only where both map out of the **same** dimension *and* into the **same** one — `from != to` excludes a self-loop |
| `name OP index(name, i)` | one dimension, twice | the coordinate at position `i` of that dimension's own order — negative counts from the end. Both names must be the **same** dimension |
| `AND` `OR` `NOT` | — | case-insensitive; `NOT` binds tighter than `AND`, which binds tighter than `OR` |
| `True` / `False` | — | literals; `True` is the same as no `where` |

The mask's dims must not exceed the frame it sits in
([dim algebra](expressions.md#dim-algebra)), and an undeclared bare name is a
load error.

**Defined is not non-zero**, and the difference is a property of the data rather
than of the model. A bare parameter name is true wherever the table *has a row*,
`0.0` included — so one `where:` masks nothing against a table padded with zeros
and deletes rows against a sparse one carrying the same information. Where the
intent is *non-zero*, compare for it: `where: "inflow != 0"` rather than
`where: inflow`, which a padded zero satisfies.

**Comparing two parameters is not in the language** — precompute a boolean
parameter in data prep — and neither is comparing two dimensions. Two
*lookups* are the exception, and only two that share both ends: over one
dimension they are two columns of one index, so the comparison is a filter on
that table rather than a join between two, and into one dimension they draw
from one label set, so a match is possible at all. Over different dimensions no
row carries both, and into different label sets no value can ever match —
either is a load error. A label space owns its values and is therefore never
the other side of one.

The string reading of a right-hand-side name is for names the model does *not*
declare, which is how a string coordinate is compared; a **declared** name
there is a load error naming the near miss, because reading it as text would
compare a coordinate column against another declaration's name and mask
everything out.

**Quote a label that is not an identifier, and quote a date.** A bare word has
to look like a name, so `combined-cycle`, `IT-north` and `CCGT 400MW` are only
sayable in quotes — and quoting is also what says *label, not name*, so a
quoted word is never read as a declaration and never a near-miss error.

**A comparison is checked against the declared `dtype`.** This matters most for
dates: a `datetime` dimension compared to a number is compared against the
**epoch**, so `snapshot > 0` would silently mean "after 1970-01-01". That is a
load error naming the fix. A datetime boundary is a quoted ISO date —
`snapshot > '2030-01-01'`, or `'2030-01-01T06:00'` with a time. Calendar
arithmetic, resampling and timezone conversion stay data prep.

**`index(dim, i)` names a coordinate by where it sits**, so a boundary clause
survives the index being relabelled:

```yaml
dimensions:
  snapshot: {dtype: int}
parameters:
  soc_initial: {dims: []}
variables:
  soc: {foreach: [snapshot], bounds: {lower: 0}}
constraints:
  soc_start:
    foreach: [snapshot]
    where: "snapshot == index(snapshot, 0)"   # not: snapshot == 0
    expression: soc == soc_initial
```

A recurrence needs its first position seeded, and the label that happens to be
there is a property of the data — relabel `[0, 1, 2]` to `[1, 2, 3]` and
`snapshot == 0` matches nothing, leaving the recurrence unanchored. `-1` is the
last coordinate, `-2` the one before it. A position no coordinate occupies is
an **error at bind**, not an empty mask: the clause exists to seed a row, and
seeding none is the failure it was written to prevent.

The order counted along is the dimension's own — the one `shift` walks, and the
one the index declares — not the bytewise order a label comparison uses.

**String labels order bytewise**, whatever order the dimension declared them
in. Declaration order is a different axis — it is what `shift` walks — and a
`where` never reads it: `node >= 'b'` means the same thing however the nodes
were listed. A label the dimension does not carry compares equal to nothing, so
the mask is false there rather than an error: quoting already said *label, not
name*, and a label is data.
