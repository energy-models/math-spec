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

## A row with no variable terms is not built

Whatever emptied it: a masked variable took the row with it, a reduction over
an absent set contributed `0`, or a missing parameter row was a zero
coefficient. Three ways to reach one shape — *a row asserting something about
constants only* — and the shape decides, not the provenance. Such a row
constrains nothing a solver can act on.

It is **reported**, never silent: `diagnostics().omissions` on a built model
gives `(constraint, rows_not_built)`, and is empty for a model whose every
declared row was built ([diagnostics](../api.md#diagnostics)). A declared
constraint that goes unenforced is a thing you have to be able to see — which
is a reason to `build` a model you mean to inspect rather than to `solve` it,
an answer being the one thing that cannot report it.

## Asking for the other reading

Each rule has a spelling for the opposite intent:

| You want | You write |
|---|---|
| the row kept, the missing term read as zero | two constraints under complementary `where` clauses |
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
value      ::= NUMBER | QUOTED | NAME_OR_STRING
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
| `AND` `OR` `NOT` | — | case-insensitive; `NOT` binds tighter than `AND`, which binds tighter than `OR` |
| `True` / `False` | — | literals; `True` is the same as no `where` |

The mask's dims must not exceed the frame it sits in
([dim algebra](expressions.md#dim-algebra)), and an undeclared bare name is a
load error.

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

**String labels order bytewise**, whatever order the dimension declared them
in. Declaration order is a different axis — it is what `shift` walks — and a
`where` never reads it: `node >= 'b'` means the same thing however the nodes
were listed. A label the dimension does not carry compares equal to nothing, so
the mask is false there rather than an error: quoting already said *label, not
name*, and a label is data.
