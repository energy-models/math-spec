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
kwarg       ::= NAME "=" (arithmetic | NAME)
NAME        ::= [a-zA-Z][a-zA-Z0-9_]*
NUMBER      ::= integer | float | "inf" | ".inf"
```

Precedence, highest first: `**`, then `*` `/`, then binary `+` `-`, then unary
`+` `-`. Parentheses override.

## Degree 1, always

Every expression is **affine in the variables**:

- `*` needs at least one variable-free factor — `p * cost` is fine, `p * on` is
  not;
- `/` needs a variable-free divisor, and a single factor rather than a sum —
  both decided at load time, since neither depends on the numbers that arrive;
- `**` parses but is **not in the language**. It is rejected at load time, so
  the refusal can name the operator and its rewrite. A variable base breaks
  degree 1; over parameters alone it is data prep.

This is the ceiling the whole design sits under, not a missing feature — what
that buys, and what it costs, is [the ceiling](../../about/ceiling.md).

## Name resolution

**One flat namespace** covers dimensions, parameters, variables, named
expressions, macros and the built-in operators. A collision is a load error
naming both declarations — there is no shadowing, because under it declaring a
parameter named `snapshot` would silently change what an existing
`where: "snapshot > 0"` means.

**Position decides which kinds of name are legal**, and every name's kind is
fixed when the file loads:

| Position | Legal kinds |
|---|---|
| expression (`p * cost`) | variable, parameter |
| dimension argument (`over=`) | dimension |
| lookup argument (`by=` on `sum` / `at`) | lookup — never a dimension |
| `where` string | parameter, variable, dimension, lookup ([where strings](#where-strings)) |
| `bounds.lower` / `bounds.upper` | parameter name, or a number |
| the `edge` key of `shift` | `'wrap'` **quoted**, or a bare number; never a dimension |

A bare word in a keyword-argument value is *a name to resolve*, which is why
`wrap` is quoted: `shift(x, over=wrap, edge='wrap')` reads unambiguously even
where a dimension is called `wrap`. `edge` is the one keyword whose *key* is
fixed rather than naming a dimension, so a dimension called `edge` does not
change what it means.

**A dimension in a value position is an error** — it is a coordinate space, not
data. To use its coordinates as data, declare a parameter over it.

**Constraints are outside the namespace**, no position resolving to one, so a
model may name a constraint after a variable. What reads a solve back keys on
the label space as well as the name for that reason. The objective carries no
name at all.

## Dim algebra

Parameter `dims` and variable `foreach` are declared, and dimension arguments
are name-checked, so **every expression's dim set is known before any data
binds**:

| Node | Dim set | Error |
|---|---|---|
| number | `{}` | |
| parameter / variable | its `dims` / its `foreach` | |
| `-x`, `+x` | `dims(x)` | |
| `a + b`, `a * b`, `a / b` | `dims(a) ∪ dims(b)` | |
| `sum(x)` | `{}` | if `dims(x)` is empty already |
| `sum(x, over=d)` | `dims(x) − {d}` | if `d ∉ dims(x)` |
| `sum(x, by=l)` | `(dims(x) − {over(l)}) ∪ {into(l)}` | if `over(l) ∉ dims(x)`, or `into(l) ∈ dims(x)` already |
| `at(x, by=l)` | `(dims(x) − {into(l)}) ∪ {over(l)}` | if `into(l) ∉ dims(x)`, or `over(l) ∈ dims(x)` already |
| `shift(x, over=d, offset=n)` | `dims(x)` | if `d ∉ dims(x)` |

Binary operators **union**: an outer product is legitimate when the frame
declares the result. What must not be silent is a *declaration* that disagrees,
so:

- a **constraint** requires `dims(lhs) ∪ dims(rhs)` to **equal** its `foreach`.
  A stray dim multiplies rows and an unused `foreach` dim repeats one row
  across them — either way you would build a different model than the file
  reads as;
- a **`where` predicate**'s dims and a **bound parameter**'s dims must not
  *exceed* the frame they sit in.

Get it wrong and you are told at load time, not at solve time.

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
| `name` (bare) | parameter | what defined means is the **declaration's** to say: a `bool` is its own answer, a `str` is defined wherever the table has a row, and a number has to be finite as well — `0.0` counts, `inf` does not, though it is a value everywhere else |
| `name` (bare) | variable | the variable exists at this coordinate — the counterpart of the parameter row, and how you say which coordinates the row-dropping rule applies to |
| `name` (bare) | dimension | load error: it is true everywhere, so it reads as a condition and is not one. Compare it instead |
| `name OP value` | parameter | element-wise; a null compares false. The right-hand side is a literal number, or a bare name read as a string coordinate |
| `name OP value` | dimension | a filter on the frame's own coordinate column |
| `name` (bare) | lookup | defined: the label maps somewhere. A lookup may be [partial](dimensions.md#lookups), and this is how a declaration asks for the labels that do map |
| `name OP value` | lookup | a filter on the lookup's column of its `over` dimension's index — which therefore has to be in the frame. A null value is **false**, whatever the comparator |
| `name OP name` | two lookups | the one comparison whose both sides are structure. Legal only where both map out of the **same** dimension *and* into the **same** one — `from != to` excludes a self-loop |
| `name OP index(name, i)` | one dimension, twice | the coordinate at position `i` of that dimension's own order — negative counts from the end. Both names must be the **same** dimension |
| `name OP index(name, i, by=lookup)` | a dimension and a lookup over it | the same, counted **within each group** the lookup makes — every period's first snapshot, whatever each period's length |
| `AND` `OR` `NOT` | — | case-insensitive; `NOT` binds tighter than `AND`, which binds tighter than `OR` |
| `True` / `False` | — | literals; `True` is the same as no `where` |

The mask's dims must not exceed the frame it sits in
([dim algebra](#dim-algebra)), and an undeclared bare name is a
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

**`by=` counts inside each group a lookup makes**, which is the boundary a
multi-period model wants — one seeded row per period rather than one per
horizon:

```yaml
dimensions:
  snapshot: {dtype: int}
  period: {dtype: int}
lookups:
  period_of: {over: snapshot, into: period}
parameters:
  soc_initial: {dims: [period]}
variables:
  soc: {foreach: [snapshot], bounds: {lower: 0}}
constraints:
  soc_start:
    foreach: [snapshot]
    where: "snapshot == index(snapshot, 0, by=period_of)"
    expression: soc == at(soc_initial, by=period_of)
```

It is the same `by=` as [`sum(by=)` and `at(by=)`](operators.md), and takes a
lookup **over the dimension being counted** — groups a row of that dimension is
actually in. A row reads its own group's boundary, the broadcast `at(by=)`
already defines, and `-1` is each group's last however long that group is.
Periods of different lengths therefore need nothing special, which is the case
no single position along the whole axis can express.

A coordinate the lookup sends nowhere is in no group, so it is no group's
boundary — the same reading a null value gets everywhere else. A group *shorter*
than the position is an error at bind, for the reason the ungrouped form has
one: a boundary naming no coordinate leaves those rows unseeded.

**String labels order bytewise**, whatever order the dimension declared them
in. Declaration order is a different axis — it is what `shift` walks — and a
`where` never reads it: `node >= 'b'` means the same thing however the nodes
were listed. A label the dimension does not carry compares equal to nothing, so
the mask is false there rather than an error: quoting already said *label, not
name*, and a label is data.

## Named expressions

A quantity the model names once and can read back after a solve:

```yaml
dimensions:
  generator: {dtype: str}
parameters:
  rate: {dims: [generator]}
variables:
  p: {foreach: [generator]}
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
`result.expression('emissions')` gives its value over its own dims
([reading a result](../api.md#reading-a-result)). That is the point of naming a
quantity: the CO₂ a constraint bounds and the CO₂ a summary reports are one
definition, validated once.

Where a constraint or the objective references one, it is substituted before
anything consumes the model, so a reference costs nothing at build time. It is
lowered only when it is *read*, so a model with fifty named expressions that
reads none pays for none.

## Macros

A **parameterised** template. It has no dims until it is called, and each call
site may give it different ones — so it has no value a solve could report, and
is never readable:

<!-- doctest: wrap=macros -->
```yaml
weighted_sum:
  args: [array, weights]  # positional formals, default []
  kwargs: [over]  # keyword formals, default []
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
