<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Expressions

Every `expression:` in the file — a constraint's, the objective's, a named
quantity's — is written in one small arithmetic language:

```text
expression  ::= arithmetic | arithmetic COMPARATOR arithmetic
arithmetic  ::= atom | unary_op arithmetic | arithmetic binary_op arithmetic
             |  function_call | "(" arithmetic ")"
atom        ::= NUMBER | NAME
unary_op    ::= "+" | "-"       binary_op ::= "+" | "-" | "*" | "/" | "**"
COMPARATOR  ::= "<=" | ">=" | "=="
function_call ::= NAME "(" [pos_arg ("," pos_arg)*] ["," kwarg ("," kwarg)*] ")"
kwarg       ::= NAME "=" (arithmetic | QUOTED | "[" NAME ("," NAME)* "]")
NAME        ::= [a-zA-Z][a-zA-Z0-9_]*
NUMBER      ::= integer | float | "inf" | ".inf"
```

Precedence, highest first: `**`, then unary `+` `-`, then `*` `/`, then binary
`+` `-` — so `-x ** 2` is `-(x ** 2)` and `-x * y` is `(-x) * y`, as in Python.
Parentheses override. A float may carry an exponent (`1e5`, `2.5e-3`); a sign
is always the unary operator's. A keyword given twice in one call is an error
rather than the later one winning.

## Degree 2 in the math, degree 1 beside it

**The objective and constraints take `variable * variable`.** So a quadratic
cost, `sum(p * p * wear, over=g)`, and a quadratic row, `p * q >= floor`, are
both sayable and both say what they mean.

Three rules bound it:

- **At most one factor may be a sum of terms.** `sum(p, over=g) * sum(q,
over=g)` is refused: that is every term of one against every term of the
  other, and nothing in the file says how many that is. Multiply _before_
  reducing, or give the reduction a name — a variable constrained to equal it
  is one term. Factors carrying different dims are fine: `x * y * link`
  broadcasts and joins through the table that couples them.
- **Degree stops at 2.** `p * p * p` is refused where `p * p` is not.
- **Everything beside the math stays affine** — a bound, a named expression and
  a `piecewise:` link. Each is read affinely by something downstream: a bound
  is a number per column, a named expression is evaluated after a solve, and a
  link expands into declarations that must themselves be affine.

`/` needs a variable-free divisor everywhere, and a single factor rather than a
sum — both decided at load time, since neither depends on the numbers that
arrive, and a variable divisor is rational rather than polynomial, which is
outside the language at any degree.

`**` takes a base and an exponent that **carry no variable**, and nothing else.
`growth ** period` is a discount factor — one number per coordinate, folded
from a rate the model binds and a period it declares — so it is the arithmetic
`*` already does, spelled the way the maths is written. Two refusals bound it,
both at load:

- **A variable anywhere under it.** `x * x` is how a square gets written; above
  degree 2 there is no rewrite at all. A variable _exponent_ is out for a
  sharper reason — `p ** n` is affine at `n = 1` and quadratic at `n = 2`, so
  the _degree_ would be a property of the data and `load_model` could not
  answer with nothing bound.
- **An operand that adds.** Addition does not distribute over `**`, so
  `(1 + rate) ** period` is two factors wearing one and is refused where
  `growth ** period` is not. Bind the factor itself.

### What it costs is a consumer's question

Saying it is one question; solving it is another
([the ceiling](../../about/ceiling.md#capability-is-not-the-ceiling)). This
language admits degree 2 in the objective and constraints and says nothing
about which solver, lane or file format takes it — that is the consumer's
axis, and each consumer answers for itself. Two things no consumer can answer
from the model alone, because both are properties of the _data_: whether a
quadratic form is **convex**, and whether a quadratic row can be priced.

A `piecewise:` block with `method: convex` remains the way to spend a curve and
keep the LP, its duals and its warm start.

## Name resolution

**One flat namespace** covers dimensions, parameters, variables, named
expressions, macros and the built-in operators. A collision is a load error
naming both declarations — there is no shadowing, because under it declaring a
parameter named `snapshot` would silently change what an existing
`where: "snapshot > 0"` means.

**Position decides which kinds of name are legal**, and every name's kind is
fixed when the file loads:

| Position                                | Legal kinds                                                                        |
| --------------------------------------- | ---------------------------------------------------------------------------------- |
| expression (`p * cost`)                 | variable, parameter — the parameter a number ([dtype](declarations.md#parameters)) |
| dimension argument (`over=`)            | dimension                                                                          |
| lookup argument (`by=` on `sum` / `at`) | lookup — never a dimension                                                         |
| `where` string                          | parameter, variable, dimension, lookup ([where strings](#where-strings))           |
| `bounds.lower` / `bounds.upper`         | parameter name, or a number                                                        |
| the `edge` key of `shift`               | `'wrap'` **quoted**, or a bare number; never a dimension                           |

A bare word in a keyword-argument value is _a name to resolve_, which is why
`wrap` is quoted: `shift(x, over=wrap, edge='wrap')` reads unambiguously even
where a dimension is called `wrap`. `edge` is the one keyword whose _key_ is
fixed rather than naming a dimension, so a dimension called `edge` does not
change what it means.

**A dimension in a value position is an error** — it is a coordinate space, not
data. To use its coordinates as data, declare a parameter over it.

**A `str` or `bool` parameter there is an error too** — data, but not a number.
A label selects and a flag masks, which is what a `where` is for; multiplying by
either is a cast the file never wrote, so only `dtype: float` and `dtype: int`
stand as a coefficient, a term or a divisor
([dtype](declarations.md#parameters)).

**Constraints are outside the namespace**, no position resolving to one, so a
model may name a constraint after a variable. What reads a solve back keys on
the label space as well as the name for that reason. The objective carries no
name at all.

## Dim algebra

Parameter `dims` and variable `foreach` are declared, and dimension arguments
are name-checked, so **every expression's dim set is known before any data
binds**:

| Node                         | Dim set                                      | Error                                                                          |
| ---------------------------- | -------------------------------------------- | ------------------------------------------------------------------------------ |
| number                       | `{}`                                         |                                                                                |
| parameter / variable         | its `dims` / its `foreach`                   |                                                                                |
| `-x`, `+x`                   | `dims(x)`                                    |                                                                                |
| `a + b`, `a * b`, `a / b`    | `dims(a) ∪ dims(b)`                          |                                                                                |
| `sum(x)`                     | `{}`                                         | if `dims(x)` is empty already                                                  |
| `sum(x, over=d)`             | `dims(x) − {d}`                              | if `d ∉ dims(x)`                                                               |
| `sum(x, by=l)`               | `(dims(x) − {over(l)}) ∪ {into(l)}`          | if `over(l) ∉ dims(x)`, or `into(l) ∈ dims(x)` already                         |
| `sum(x, by=[l, m])`          | `(dims(x) − {over(l)}) ∪ {into(l), into(m)}` | the same, plus: if `l` and `m` are over different dims, or target the same one |
| `at(x, by=l)`                | `(dims(x) − {into(l)}) ∪ {over(l)}`          | if `into(l) ∉ dims(x)`, or `over(l) ∈ dims(x)` already                         |
| `shift(x, over=d, offset=n)` | `dims(x)`                                    | if `d ∉ dims(x)`                                                               |

Binary operators **union**: an outer product is legitimate when the frame
declares the result. What must not be silent is a _declaration_ that disagrees,
so:

- a **constraint** requires `dims(lhs) ∪ dims(rhs)` to **equal** its `foreach`.
  A stray dim multiplies rows and an unused `foreach` dim repeats one row
  across them — either way you would build a different model than the file
  reads as;
- an **objective** must carry **no dims at all** — it is one number, and the
  sums that make it one are written in the expression;
- a **`where` predicate**'s dims and a **bound parameter**'s dims must not
  _exceed_ the frame they sit in.

Get it wrong and you are told at load time, not at solve time.

## Where strings

A `where:` is a boolean mask, and true means "this coordinate exists".

```text
where_expr ::= atom | "NOT" where_expr | where_expr ("AND"|"OR") where_expr
            |  "(" where_expr ")"
atom       ::= NAME | NAME COMPARATOR value | POSITION COMPARATOR INTEGER
            |  "True" | "False"
COMPARATOR ::= "<=" | ">=" | "==" | "!=" | "<" | ">"
value      ::= NUMBER | QUOTED | NAME_OR_STRING
POSITION   ::= "position" "(" NAME [ "," "by" "=" NAME ] ")"
QUOTED     ::= "'" chars "'" | '"' chars '"'
```

| Surface                          | Names a…                         | Meaning                                                                                                                                                                                                                                     |
| -------------------------------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name` (bare)                    | parameter                        | what defined means is the **declaration's** to say: a `bool` is its own answer, a `str` is defined wherever the table has a row, and a number has to be finite as well — `0.0` counts, `inf` does not, though it is a value everywhere else |
| `name` (bare)                    | variable                         | the variable exists at this coordinate — the counterpart of the parameter row, and how you say which coordinates the row-dropping rule applies to                                                                                           |
| `name` (bare)                    | dimension                        | load error: it is true everywhere, so it reads as a condition and is not one. Compare it instead                                                                                                                                            |
| `name OP value`                  | parameter                        | element-wise; a null compares false. The right-hand side is a literal number, or a bare name read as a string coordinate                                                                                                                    |
| `name OP value`                  | dimension                        | a filter on the frame's own coordinate column                                                                                                                                                                                               |
| `name` (bare)                    | lookup                           | defined: the label maps somewhere. A lookup may be [partial](dimensions.md#lookups), and this is how a declaration asks for the labels that do map                                                                                          |
| `name OP value`                  | lookup                           | a filter on the lookup's column of its `over` dimension's index — which therefore has to be in the frame. A null value is **false**, whatever the comparator                                                                                |
| `name OP name`                   | two lookups                      | the one comparison whose both sides are structure. Legal only where both map out of the **same** dimension _and_ into the **same** one — `from != to` excludes a self-loop                                                                  |
| `position(name) OP i`            | one dimension                    | where the row sits along that dimension's own order, as an integer — `0` is first, negative counts from the end. Both sides are integers, so every comparator reads the one way                                                             |
| `position(name, by=lookup) OP i` | a dimension and a lookup over it | the same, counted **within each group** the lookup makes — every period's first snapshot, whatever each period's length                                                                                                                     |
| `AND` `OR` `NOT`                 | —                                | case-insensitive; `NOT` binds tighter than `AND`, which binds tighter than `OR`                                                                                                                                                             |
| `True` / `False`                 | —                                | literals; `True` is the same as no `where`                                                                                                                                                                                                  |

The mask's dims must not exceed the frame it sits in
([dim algebra](#dim-algebra)), and an undeclared bare name is a
load error.

**Defined is not non-zero**, and the difference is a property of the data rather
than of the model. A bare parameter name is true wherever the table _has a row_,
`0.0` included — so one `where:` masks nothing against a table padded with zeros
and deletes rows against a sparse one carrying the same information. Where the
intent is _non-zero_, compare for it: `where: "inflow != 0"` rather than
`where: inflow`, which a padded zero satisfies.

**Comparing two parameters is not in the language** — precompute a boolean
parameter in data prep — and neither is comparing two dimensions. Two
_lookups_ are the exception, and only two that share both ends: over one
dimension they are two columns of one index, so the comparison is a filter on
that table rather than a join between two, and into one dimension they draw
from one label set, so a match is possible at all. Over different dimensions no
row carries both, and into different label sets no value can ever match —
either is a load error. A label space owns its values and is therefore never
the other side of one.

The string reading of a right-hand-side name is for names the model does _not_
declare, which is how a string coordinate is compared; a **declared** name
there is a load error naming the near miss, because reading it as text would
compare a coordinate column against another declaration's name and mask
everything out.

**Quote a label that is not an identifier, and quote a date.** A bare word has
to look like a name, so `combined-cycle`, `IT-north` and `CCGT 400MW` are only
sayable in quotes — and quoting is also what says _label, not name_, so a
quoted word is never read as a declaration and never a near-miss error.

**A comparison is checked against the declared `dtype`.** This matters most for
dates: a `datetime` dimension compared to a number is compared against the
**epoch**, so `snapshot > 0` would silently mean "after 1970-01-01". That is a
load error naming the fix. A datetime boundary is a quoted ISO date —
`snapshot > '2030-01-01'`, or `'2030-01-01T06:00'` with a time. Calendar
arithmetic, resampling and timezone conversion stay data prep.

**`position(dim)` converts a dimension to where the row sits along it**, so a
boundary clause survives the index being relabelled:

```yaml
dimensions:
  snapshot: { dtype: int }
parameters:
  soc_initial: { dims: [] }
variables:
  soc: { foreach: [snapshot], bounds: { lower: 0 } }
constraints:
  soc_start:
    foreach: [snapshot]
    where: "position(snapshot) == 0" # not: snapshot == 0
    expression: soc == soc_initial
```

A recurrence needs its first position seeded, and the label that happens to be
there is a property of the data — relabel `[0, 1, 2]` to `[1, 2, 3]` and
`snapshot == 0` matches nothing, leaving the recurrence unanchored. `-1` is the
last position, `-2` the one before it. A position no coordinate occupies is
an **error at bind**, not an empty mask: the clause exists to seed a row, and
seeding none is the failure it was written to prevent.

The order counted along is the dimension's own — the one `shift` walks, and the
one the index declares — not the bytewise order a label comparison uses.

**The conversion is on the left, and that is what makes an ordering readable.**
`position(snapshot) > 0` is "not the first row", on any axis, because both
sides are integers. Naming the coordinate _at_ a position and comparing
coordinates against it would have made the same clause mean either that or "a
coordinate sorting after the first one" — two different masks wherever the
coordinates do not arrive sorted, and nothing in a file says they do
([#32](https://github.com/energy-models/math-spec/issues/32)). A comparison of
_values_ is still written against the dimension itself, where it always was:
`snapshot > '2030-01-01'`.

**`by=` counts inside each group a lookup makes**, which is the boundary a
multi-period model wants — one seeded row per period rather than one per
horizon:

```yaml
dimensions:
  snapshot: { dtype: int }
  period: { dtype: int }
lookups:
  period_of: { over: snapshot, into: period }
parameters:
  soc_initial: { dims: [period] }
variables:
  soc: { foreach: [snapshot], bounds: { lower: 0 } }
constraints:
  soc_start:
    foreach: [snapshot]
    where: "position(snapshot, by=period_of) == 0"
    expression: soc == at(soc_initial, by=period_of)
```

It is the same `by=` as [`sum(by=)` and `at(by=)`](operators.md), and takes a
lookup **over the dimension being counted** — groups a row of that dimension is
actually in. A row reads its own group's boundary, the broadcast `at(by=)`
already defines, and `-1` is each group's last however long that group is.
Periods of different lengths therefore need nothing special, which is the case
no single position along the whole axis can express.

A coordinate the lookup sends nowhere is in no group, so it is no group's
boundary — the same reading a null value gets everywhere else. A group _shorter_
than the position is an error at bind, for the reason the ungrouped form has
one: a boundary naming no coordinate leaves those rows unseeded.

**String labels order bytewise**, whatever order the dimension declared them
in. Declaration order is a different axis — it is what `shift` walks — and a
`where` never reads it: `node >= 'b'` means the same thing however the nodes
were listed. A label the dimension does not carry compares equal to nothing, so
the mask is false there rather than an error: quoting already said _label, not
name_, and a label is data.

## Named expressions

A quantity the model names once and can read back after a solve:

```yaml
dimensions:
  generator: { dtype: str }
parameters:
  rate: { dims: [generator] }
variables:
  p: { foreach: [generator] }
expressions:
  total_generation: sum(p, over=generator)
  emissions:
    expression: sum(p * rate, over=generator)
    description: CO2 released, the quantity a cap would bound
```

Written as a bare string until it carries a `description:`, which is when it
gains the mapping form.

A named expression has **fixed dims** — they fall out of its body, so there is
no `foreach` — and an **observable identity**: after a solve,
a consumer can read its value back over its own dims.
That is the point of naming a
quantity: the CO₂ a constraint bounds and the CO₂ a summary reports are one
definition, validated once.

Where a constraint or the objective references one, it is substituted before
anything consumes the model, so a reference costs nothing at build time. It is
lowered only when it is _read_, so a model with fifty named expressions that
reads none pays for none.

## Macros

A **parameterised** template. It has no dims until it is called, and each call
site may give it different ones — so it has no value a solve could report, and
is never readable:

<!-- doctest: wrap=macros -->

```yaml
weighted_sum:
  args: [array, weights] # positional formals, default []
  kwargs: [over] # keyword formals, default []
  template: sum(array * weights, over=over)
```

Both blocks hold arithmetic and no comparison. Arguments expand before
substitution (call-by-value), so they may themselves use macros and named
expressions. Formals shadow model names inside a template but may not collide
with a declared **dimension**. Arity is checked per call site, and cycles are
reported with the reference chain.

**Every template is parsed and name-checked at load time even if it is never
called** — a macro nobody uses cannot hide a typo.

Anything composable out of the [built-in operators](operators.md) belongs here.
Math that is not sayable at all is out of scope
([limits](errors.md#what-the-language-will-not-say)).
