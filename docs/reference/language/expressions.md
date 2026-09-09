<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Expressions

Every `expression:` in the file is written in one small arithmetic language.
That covers a constraint's expression, the objective's expression, and a named
quantity's expression:

```text
expression  ::= arithmetic | arithmetic COMPARATOR arithmetic
arithmetic  ::= atom | unary_op arithmetic | arithmetic binary_op arithmetic
             |  function_call | "(" arithmetic ")"
atom        ::= NUMBER | NAME
unary_op    ::= "+" | "-"       binary_op ::= "+" | "-" | "*" | "/" | "**"
COMPARATOR  ::= "<=" | ">=" | "=="
function_call ::= NAME "(" [pos_arg ("," pos_arg)*] ["," kwarg ("," kwarg)*] ")"
kwarg       ::= NAME "=" (arithmetic | QUOTED | "[" NAME ("," NAME)* "]")
NAME        ::= [a-zA-Z_][a-zA-Z0-9_]*
NUMBER      ::= integer | float | "inf" | ".inf"
```

Precedence runs as follows, highest first: `**`, then unary `+` and `-`, then
`*` and `/`, then binary `+` and `-`. So `-x ** 2` means `-(x ** 2)`, and
`-x * y` means `(-x) * y`, exactly as in Python. Parentheses override
precedence.

A float may carry an exponent, as in `1e5` or `2.5e-3`. A sign is always the
unary operator, never part of the number.

If you give the same keyword twice in one call, that is an error. The later one
does not win.

An expression nests at most 100 levels deep. That is a chain of at most 100
terms written out. A chain that long is one that a single `sum()` over a
dimension replaces. `where:` strings have the same limit.

## Where a product of two variables is allowed

The objective and the constraints take `variable * variable`. A quadratic cost
is `sum(p * p * wear, over=g)`, and a quadratic row is `p * q >= floor`.

Three rules bound this:

- **At most one factor may be a sum of terms.** So `sum(p, over=g) * sum(q,
over=g)` is refused. That product pairs every term of one sum against every
  term of the other, and nothing in the file says how many terms that is.
  Instead, multiply _before_ you reduce, or give the reduction a name, because a
  variable constrained to equal a reduction is one term. Factors that carry
  different dimensions are fine: `x * y * link` broadcasts and joins through
  the table that couples the two.
- **Degree stops at 2.** `p * p * p` is refused, where `p * p` is not.
- **Everything beside the math stays affine.** This covers a bound and a
  `piecewise:` link. A bound is one number per column. A link expands into
  declarations, and those declarations must themselves be affine.

A named expression works differently. It is read at the limit of wherever the
math reads it: degree 2 in the objective or a constraint, and affine in a
piecewise link. A named expression that nothing in the math reads is held to no
degree at all. It is a **reported** quantity, described below, and that is what
lets it divide by a variable, cube one, or call `dual()`.

`/` always needs a divisor that carries no variable, and that divisor must be a
single factor rather than a sum. Both of these are decided at load time,
because neither depends on the numbers that arrive. A variable divisor is
rational rather than polynomial, and that is outside the language at any degree.

`**` takes a base and an exponent that both **carry no variable**, and nothing
else. `growth ** period` is a discount factor. It is one number per coordinate,
folded from a rate that the model binds and a period that it declares. So it is
the same arithmetic that `*` already does, spelled the way the mathematics is
written.

Two refusals bound `**`, and both happen at load:

- **A variable anywhere under it.** Write `x * x` for a square. Above degree 2
  there is no rewrite at all. A variable _exponent_ is out for a sharper
  reason: `p ** n` is affine at `n = 1` and quadratic at `n = 2`, so the
  _degree_ would become a property of the data, and `to_spec` could not answer
  with nothing bound.
- **An operand that adds.** Addition does not distribute over `**`. So
  `(1 + rate) ** period` is two factors dressed as one, and it is refused where
  `growth ** period` is not. Bind the factor itself instead.

### What it costs to solve is a consumer's question

Saying something is one question. Solving it is another. See
[the limits](../../about/limits.md#capability-is-not-the-limit).

This language admits degree 2 in the objective and in the constraints. It says
nothing about which solver, lane or file format will take it. That is the
consumer's axis, and each consumer answers for itself.

Two things no consumer can answer from the model alone, because both are
properties of the _data_: whether a quadratic form is **convex**, and whether a
quadratic row can be priced.

A `piecewise:` block with `method: convex` is still the way to spend a curve and
keep the linear program, together with its duals and its warm start.

## Name resolution

A name is a letter or an underscore, followed by letters, digits or
underscores. That is the spelling an expression uses to refer to a
declaration. A declaration keyed by anything else is a load error, because
nothing in the file could ever write that key.

One flat namespace covers dimensions, parameters, variables, named
expressions, macros and the built-in operators. A collision is a load error, and
the message names both declarations.

There is no shadowing. With shadowing, declaring a parameter named `snapshot`
would silently change what an existing `where: "snapshot > 0"` means.

Position decides which kinds of name are legal, and the kind of every name is
fixed when the file loads:

| Position                                | Legal kinds                                                                                                                                    |
| --------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| expression (`p * cost`)                 | a variable, or a parameter whose values are numbers ([dtype](declarations.md#parameters))                                                      |
| dimension argument (`over=`)            | a dimension                                                                                                                                    |
| lookup argument (`by=` on `sum` / `at`) | a lookup, and never a dimension                                                                                                                |
| `where` string                          | a parameter, variable, dimension or lookup ([where strings](#where-strings))                                                                   |
| `bounds.lower` / `bounds.upper`         | a parameter name, or a number                                                                                                                  |
| the `edge` key of `shift`               | `'wrap'` in **quotes**, or a bare number. Never a dimension                                                                                    |
| `dual` argument (`dual(c)`)             | a constraint. It resolves against the constraints alone, never against the flat namespace ([reported](reported.md#reading-a-constraints-dual)) |

A bare word in the value of a keyword argument is _a name to resolve_. That is
why `wrap` is quoted. `shift(x, over=wrap, edge='wrap')` then reads
unambiguously, even in a model where a dimension is called `wrap`. `edge` is
the one keyword whose _key_ is fixed rather than naming a dimension, so a
dimension called `edge` does not change what `edge=` means.

A dimension in a value position is an error. A dimension is a coordinate
space, not data. To use its coordinates as data, declare a parameter over it.

A `str` or `bool` parameter in a value position is also an error. Those are
data, but they are not numbers. A label selects rows and a flag masks rows, and
selecting and masking are what a `where` is for. Multiplying by either one is a
cast that the file never wrote. So only `dtype: float` and `dtype: int` may
stand as a coefficient, a term or a divisor. See
[dtype](declarations.md#parameters).

Constraints sit outside the flat namespace. The one position that names a
constraint is [`dual`'s argument](reported.md#reading-a-constraints-dual), and
that resolves against the constraints alone. So a bare name never reaches a
constraint, and a model may name a constraint after a variable. For the same
reason, whatever reads a solve back keys on the label space as well as on the
name. The objective carries no name at all.

## How dimensions combine

A parameter declares its `dims`, a variable declares its `foreach`, and every
dimension argument is name-checked. So **the dimension set of every expression
is known before any data binds**:

| Node                         | Dim set                                      | Error                                                                                                             |
| ---------------------------- | -------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| number                       | `{}`                                         |                                                                                                                   |
| parameter / variable         | its `dims` / its `foreach`                   |                                                                                                                   |
| `-x`, `+x`                   | `dims(x)`                                    |                                                                                                                   |
| `a + b`, `a * b`, `a / b`    | `dims(a) ∪ dims(b)`                          |                                                                                                                   |
| `sum(x)`                     | `{}`                                         | error if `dims(x)` is already empty                                                                               |
| `sum(x, over=d)`             | `dims(x) − {d}`                              | error if `d ∉ dims(x)`                                                                                            |
| `sum(x, by=l)`               | `(dims(x) − {over(l)}) ∪ {into(l)}`          | error if `over(l) ∉ dims(x)`, or if `into(l)` is already in `dims(x)`                                             |
| `sum(x, by=[l, m])`          | `(dims(x) − {over(l)}) ∪ {into(l), into(m)}` | the same errors, plus an error if `l` and `m` are over different dimensions, or if they target the same dimension |
| `at(x, by=l)`                | `(dims(x) − {into(l)}) ∪ {over(l)}`          | error if `into(l) ∉ dims(x)`, or if `over(l)` is already in `dims(x)`                                             |
| `shift(x, over=d, offset=n)` | `dims(x)`                                    | error if `d ∉ dims(x)`                                                                                            |

Binary operators take the **union** of the two dimension sets. An outer product
is legitimate whenever the frame declares the result. What must never be silent
is a _declaration_ that disagrees with its expression. So:

- A **constraint** requires `dims(lhs) ∪ dims(rhs)` to **equal** its `foreach`.
  A stray dimension multiplies the rows, and an unused `foreach` dimension
  repeats one row across them. Either way, you would build a different model
  from the one the file reads as.
- An **objective** must carry **no dimensions at all.** It is one number, and
  the sums that reduce it to one number are written in the expression.
- The dimensions of a **`where` predicate**, and the dimensions of a **bound
  parameter**, must not _exceed_ the frame they sit in.

If you get any of this wrong, you are told at load time, not at solve time.

## `where` strings

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

| Surface                          | Names a…                         | Meaning                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| -------------------------------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `name` (bare)                    | parameter                        | The **declaration** says what "defined" means here. A `bool` is its own answer. A `str` is defined wherever the table has a row. A number has to have a row and be finite, so `0.0` counts and `inf` does not, although `inf` is a value everywhere else                                                                                                                                                                                                                                                                             |
| `name` (bare)                    | variable                         | The variable exists at this coordinate. This is the counterpart of the parameter row, and it is how you say which coordinates the row-dropping rule applies to                                                                                                                                                                                                                                                                                                                                                                       |
| `name` (bare)                    | dimension                        | This is a load error. It is true everywhere, so it looks like a condition without being one. Compare it against something instead                                                                                                                                                                                                                                                                                                                                                                                                    |
| `name OP value`                  | parameter                        | The comparison is element-wise, and a null compares false. The right-hand side is a literal number, or a bare name that is read as a string coordinate                                                                                                                                                                                                                                                                                                                                                                               |
| `name OP value`                  | dimension                        | A filter on the frame's own coordinate column                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| `name` (bare)                    | lookup                           | Defined means that the label maps somewhere. A lookup may be [partial](dimensions.md#lookups), and this is how a declaration asks for the labels that do map                                                                                                                                                                                                                                                                                                                                                                         |
| `name OP value`                  | lookup                           | A filter on the lookup's column in the index of its `over` dimension. That dimension therefore has to be in the frame. A null value is **false**, whatever the comparator                                                                                                                                                                                                                                                                                                                                                            |
| `name OP name`                   | two lookups                      | The one comparison where both sides are structure. It is legal only where both lookups map out of the **same** dimension _and_ into the **same** dimension. For example, `from != to` excludes a self-loop                                                                                                                                                                                                                                                                                                                           |
| `position(name) OP i`            | one dimension                    | Where the row sits along that dimension's own order, as an integer. `0` is first, and a negative number counts from the end. Both sides are integers, so every comparator reads one way only                                                                                                                                                                                                                                                                                                                                         |
| `position(name, by=lookup) OP i` | a dimension and a lookup over it | The same, but counted **within each group** that the lookup makes. This picks out the first snapshot of every period, whatever the length of each period                                                                                                                                                                                                                                                                                                                                                                             |
| `AND` `OR` `NOT`                 | —                                | These are case-insensitive. `NOT` binds tighter than `AND`, and `AND` binds tighter than `OR`                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| `True` / `False`                 | —                                | These are literals, and they are decided at load wherever they stand. `True` is the same as no `where`. `False` gives a declaration with no rows. A literal under an `AND` or an `OR` settles that side, so `x AND False` also gives a declaration with no rows. A double negation folds the same way, and `NOT NOT x` is `x`. So a page prints what the mask decides, not how the mask was spelled. A case [`when:`](#the-rules-that-keep-the-cases-apart) is the one place where a mask that folds to a literal is refused instead |

The dimensions of the mask must not exceed the frame it sits in. See
[how dimensions combine](#how-dimensions-combine). A bare name that is not declared is a load
error.

!!! warning "Defined is not the same as non-zero"

    A bare parameter name is true wherever the table _has a row_, and that
    includes a row holding `0.0`. So one `where:` masks nothing against a table
    padded with zeros, and deletes rows against a sparse table that carries the
    same information. The difference is a property of the data rather than of
    the model.

    Where you mean _non-zero_, compare for it. Write `where: "inflow != 0"`
    rather than `where: inflow`, which a padded zero satisfies.

Comparing two parameters is not in the language. Precompute a boolean
parameter during data preparation instead. Comparing two dimensions is not in
the language either.

Two _lookups_ are the exception, and only two lookups that share both ends. Over
one dimension, two lookups are two columns of one index, so the comparison is a
filter on that one table rather than a join between two tables. Into one
dimension, both lookups draw from one label set, so a match is possible at all.

The two failing cases are both load errors. Over different dimensions, no row
carries both lookups. Into different label sets, no value can ever match. A
label space owns its values, so a label space is never the other side of such a
comparison.

On the right-hand side of a comparison, a name is read as a string when the
model does _not_ declare it. That is how you compare a string coordinate. A
**declared** name there is a load error that names the near miss. Reading a
declared name as text would compare a coordinate column against another
declaration's name, and mask everything out.

Quote a label that is not an identifier, and quote a date. A bare word has
to look like a name, so `combined-cycle`, `IT-north` and `CCGT 400MW` are only
written in quotes. Quoting is also what says _label, not name_. So a quoted word
is never read as a declaration, and it never gives a near-miss error.

A comparison is checked against the declared `dtype`. Write a datetime boundary
as a quoted ISO date, such as `snapshot > '2030-01-01'`, or
`'2030-01-01T06:00'` if you need a time. Calendar arithmetic, resampling and
timezone conversion all stay in data preparation.

!!! warning "A number against a `datetime` dimension is a load error"

    A `datetime` dimension compared to a number is compared against the epoch,
    so `snapshot > 0` would silently mean "after 1970-01-01". The language
    refuses it at load instead, and the message names the fix.

`position(dim)` converts a dimension into where the row sits along that
dimension. A boundary clause written that way survives a relabelling of the
index:

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

A recurrence needs its first position seeded, and the label that happens to sit
there is a property of the data. Relabel `[0, 1, 2]` to `[1, 2, 3]`, and
`snapshot == 0` matches nothing, which leaves the recurrence unanchored.

`-1` is the last position, and `-2` is the one before it. A position that no
coordinate occupies is an **error at bind**, not an empty mask. The clause
exists to seed a row, so seeding no row is the exact failure it was written to
prevent.

The order that `position` counts along is the dimension's own order. That is the
order `shift` walks, and the order the index declares. It is not the bytewise
order that a label comparison uses.

The conversion sits on the left. `position(snapshot) > 0` means "not the first
row" on any axis, because both sides are integers.

The alternative would be to name the coordinate _at_ a position, and compare
coordinates against it. Then the same clause could mean either "not the first
row" or "a coordinate that sorts after the first one". Those are two different
masks wherever the coordinates do not arrive sorted, and nothing in a file says
that they do
([#32](https://github.com/energy-models/math-spec/issues/32)).

You still write a comparison of _values_ against the dimension itself, as you
always did: `snapshot > '2030-01-01'`.

`by=` counts inside each group that a lookup makes. That is the boundary a
multi-period model wants: one seeded row per period, rather than one per
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

`by=` takes a lookup **over the dimension being counted**, so the groups are
groups that a row of that dimension is actually in.

Unlike [`sum(by=)` and `at(by=)`](operators.md), this lookup need not be a
_groupable_ one. Counting inside a group lands no terms anywhere, so a label
space partitions the rows just as well
([#280](https://github.com/energy-models/math-spec/issues/280)).

A row reads its own group's boundary, which is the broadcast that `at(by=)`
already defines. `-1` is the last position of each group, however long that
group is. So periods of different lengths need nothing special, and that is
exactly the case that no single position along the whole axis can express.

A coordinate that the lookup sends nowhere is in no group, so it is no group's
boundary. That is the same reading a null value gets everywhere else. A group
_shorter_ than the position is an error at bind, for the same reason the
ungrouped form gives an error: a boundary that names no coordinate leaves those
rows unseeded.

String labels order bytewise, whatever order the dimension declared them in. Declaration order is a different axis, and it is the one `shift` walks. A
`where` never reads declaration order, so `node >= 'b'` means the same thing
however the nodes were listed.

A label that the dimension does not carry compares equal to nothing. So the mask
is false there, rather than an error. Quoting already said _label, not name_,
and a label is data.

## Named expressions

A named expression is a quantity that the model names once and can read back
after a solve:

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

Write a named expression as a bare string. It gains the mapping form when it
needs to carry a `description:`.

A named expression has **fixed dimensions**. They fall out of its body, so there
is no `foreach`. It also has an **observable identity**: after a solve, a
consumer can read its value back over its own dimensions.

Naming a quantity is what makes that possible. The CO₂ that a constraint bounds
and the CO₂ that a summary reports are then one definition, validated once.

Where a constraint or the objective references a named expression, the
expression is substituted before anything consumes the model. So a reference
costs nothing at build time. It is lowered only when it is _read_. So a model
with fifty named expressions that reads none of them pays for none of them.

A named expression is one of **two things**, and the file never says which. The
objective and the constraints decide.

If the objective or a constraint inlines it, directly or through another entry
or a macro, then it is **in the math**. It stands inside the program that a
solver sees, and it is held to the same
[degree-2 limit](#where-a-product-of-two-variables-is-allowed) that the math is
held to everywhere else, at the place where it is read.

If nothing in the math names it, then it is **reported**. It is a statistic that
the solver never sees, and it is arithmetic over numbers that a solve has
already produced. There, those restrictions no longer apply, and that is what lets it
divide by a variable, cube one, or call
[`dual()`](reported.md#reading-a-constraints-dual). See
[Reported expressions](reported.md) for which restrictions do not apply, and for how the split is
decided.

### `cases:` — one quantity, a value per region

Some quantities have no single expression. Take the commitment state that a
unit carries into a snapshot. It has three regimes: `1` for a unit that is
never switched off, an initial condition at the first snapshot, and the
previous snapshot's status everywhere else.

If you write those regimes at the constraint, they fork the inequality three
ways. If you name them here, you write the inequality once:

```yaml
expressions:
  previous_status:
    description: the commitment state a unit carries into a snapshot
    foreach: [snapshot, generator]
    cases:
      always_on:
        when: "not committable"
        expression: 1
      boundary:
        when: "committable and position(snapshot) == 0"
        expression: status_initial
    otherwise: shift(status, over=snapshot, offset=1)
constraints:
  ramp_up:
    foreach: [snapshot, generator]
    expression: >-
      p - shift(p, over=snapshot, offset=1, edge=0)
      <= ramp_limit * previous_status + start_up_limit * (1 - previous_status)
```

Each case becomes one row of the printed definition, and `otherwise:` is the
last row:

$$\mathit{previous\_status}_{t,g} = \begin{cases} 1 & \text{if } \neg \mathrm{committable}_{g} \cr \mathrm{status}^{\mathrm{initial}}_{g} & \text{if } \mathrm{committable}_{g} \wedge \mathrm{pos}(t) = 0 \cr \mathit{status}_{t - 1,g} & \text{otherwise} \end{cases} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G}$$

A named expression carries exactly one of two things: an `expression:`, or a
`cases:` block.

A `cases:` block is a map of named cases. Each case has a `when:` and an
`expression:`. Two more keys sit beside the block. `otherwise:` carries whatever
the cases leave over. `foreach:` declares the dimensions that all of them range
over.

Those dimensions are the block's **frame**. One point of the frame is a
**coordinate**, which in the example above is one snapshot for one generator.
Every rule below is about which case owns which coordinate.

#### The rules that keep the cases apart

No two cases may claim one coordinate. One generator at one snapshot cannot
have two previous statuses. So if two `when:` masks in a file can hold at once,
the file is refused at load. The refusal comes before any data binds, and the
message names three things: the pair of cases, a coordinate that both of them
claim, and the rewrite:

> `Named expression 'previous_status'`: cases `always_on` and `boundary` both
> claim the value where committable is false, the position of snapshot is 0. A
> coordinate two cases claim has two values, so it has none — narrow one of the
> two `when:` strings by the negation of the other, or drop the wider one and
> let `otherwise:` carry that region.

That is why `boundary` above says `committable and`.

A `when:` that the data cannot decide is not a case. Some masks are settled
by the connectives alone. `True` and `False` are two, and so is anything that
folds to one of them, such as `committable OR True`. Such a mask states no
condition for the data to answer, so it names no region. Both halves are refused
at load, and the refusal names the rewrite:

> `Named expression 'previous_status', case 'always_on'`: the mask admits every
> row, so no other arm can hold anywhere and `otherwise:` covers nothing. Write
> the expression without `cases:`, or narrow the `when`.

An always-false arm is the other half of the same rule. It never applies, so
either delete it or widen it.

A **declaration's** `where:` is not held to this rule, and it cannot be. There,
`False` is how a file says that the declaration has no rows, and `True` is the
same as writing no mask at all. It is only the `when:` on an arm that has to be
a question, because the arms are kept apart by proof.

A pair that the check cannot decide is also refused, and that refusal names its
rewrite too. The pair that comes up in practice is
`position(snapshot) == 0` against `position(snapshot) == -1`. On an axis with a
single member, those two pick the same row, and how many members an axis has is
data rather than declaration. So count from one end only.

`otherwise:` is the value wherever no `when` holds, and it takes every
coordinate that the cases leave. It carries no mask of its own, so nothing
narrows the frame it is written against. It is the one value that has to hold up
at every coordinate, including those where a parameter is absent or a label is
unnamed.

Covering a coordinate is not the same as having a value there. A case that
claims a coordinate may still be empty at it. The `otherwise:` above shows how.
Its `shift` carries no `edge=`, so it produces nothing at the first snapshot.
`previous_status` is whole there only because `boundary` or `always_on` claims
every unit at that snapshot instead.

Close a hole like that in one of three ways:

- widen a `when` until it covers the coordinate the case drops out at,
- give the `shift` an `edge=`,
- or set `absence: zero` on a masked variable.

Nothing catches a hole left open at load, because whether a case has a value
there depends on the data.

`foreach:` is required with cases, and refused without them. The dimensions
of an expression with no cases fall out of its body. The dimensions of a cased
expression cannot, because a case may be a single number while the condition
that selects it ranges over dimensions. `always_on` above is exactly that. So
you declare the frame. Each `when:` is then held to that frame, in the way a
variable's or a constraint's mask is, and each case's value must sit inside it.

The dimensions of a reference are the declared `foreach`, not the union of the
cases. A case that is narrower than the frame broadcasts, exactly as a
parameter with fewer dimensions does.

`cases:` inside a `macros:` template is not supported. The `otherwise:`
would have to cover a frame that the macro does not have until it is called.

#### Why it is shaped this way

A coordinate with two values has no single value, so it is no longer a
quantity. That is why the regimes are kept apart by proof, rather than ranked by
position.

Keeping them apart by proof is what makes the cases readable in any order. Each
case says where it applies on its own terms, without you having to hold the
cases above it in mind. So a tool that re-sorts the keys of a file cannot change
what the file means.

`otherwise:` is required because it makes the quantity whole without a second
proof. It carries no condition, so there is no condition on it to fail. A
coordinate that no `when` matched would have no value at all, and absence
[spreads](absence.md), so any constraint that read the expression would lose
rows it never masked.

`otherwise:` is written beside `cases:` rather than inside it, because it is not
a region in the way the cases are. It is what is left over. And because it
carries a value and nothing else, you write it as a bare value. That is the same
shorthand that `expressions:` itself takes.

### How a named expression prints

A use of a named expression prints the symbol. The body prints once, under a
**Definitions** heading between `Subject to` and `Variable domains`, in
declaration order. That is where a paper states a quantity it names.

The symbol is italic where a variable reaches the body, and upright where none
does. That is the same cut every other name follows. A named expression joins
the symbol pool like any other quantity, so `--symbols` can rename one.

`inline_expressions`, which is `--inline-expressions` on the command line,
substitutes each plain expression where it is used instead. That is the math a
backend builds.

A cased expression is printed as a definition either way, and that is a
decision. A `cases` block is taller than the line it would sit in, and it would
print once per use even though the file writes it once. Avoiding that repetition
is the point of naming it.

[The unit commitment example](../../examples/commitment.md) is the complete
model that this section is drawn from.

## Macros

A macro is a **parameterised** template. It has no dimensions until it is
called, and each call site may give it different ones. So it has no value that a
solve could report, and you can never read it back:

<!-- doctest: wrap=macros -->

```yaml
weighted_sum:
  args: [array, weights] # positional formals, default []
  kwargs: [over] # keyword formals, default []
  template: sum(array * weights, over=over)
```

Both blocks hold arithmetic, and neither holds a comparison.

Arguments expand before substitution, which is call-by-value. So an argument may
itself use macros and named expressions.

Inside a template, the formal parameters shadow model names. But a formal
parameter may not collide with a declared **dimension**.

Arity is checked at each call site. A cycle is reported together with the
reference chain.

Every template is parsed and name-checked at load time, even if it is never
called. So a macro that nobody uses cannot hide a typo.

Anything you can compose out of the [built-in operators](operators.md) belongs
here. Math the language cannot express at all is out of scope. See
[limits](errors.md#what-the-language-will-not-say).
