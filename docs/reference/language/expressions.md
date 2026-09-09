<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Expressions

Every `expression:` in the file is written in one arithmetic grammar. That
covers a constraint, the objective, a named expression and a macro template:

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

- Operators bind in this order, highest first: `**`, then unary `+` and `-`,
  then `*` and `/`, then binary `+` and `-`. So `-x ** 2` is `-(x ** 2)`, and `-x * y` is
  `(-x) * y`, as in Python. Parentheses override precedence.
- A float may carry an exponent, as in `1e5` or `2.5e-3`. A sign is always the
  unary operator, never part of the number.
- The same keyword twice in one call is an error.
- An expression nests at most 100 levels deep, and so does a `where:` string.
  A chain of 100 terms is one that a `sum()` over a dimension replaces.

## Where a product of two variables is allowed

The objective and the constraints take `variable * variable`. A quadratic cost is
`sum(p * p * wear, over=g)`, and a quadratic row is `p * q >= floor`. Three rules
bound it:

- **At most one factor may be a sum of terms.** `sum(p, over=g) * sum(q, over=g)`
  is refused: it pairs every term of one sum against every term of the other,
  and nothing in the file says how many terms that is. Multiply before you
  reduce, or constrain a variable to equal the reduction, because a variable is
  one term. Factors on different dimensions are allowed: `x * y * link`
  broadcasts, and the table `link` says which pairs exist.
- **Degree stops at 2.** `p * p * p` is refused.
- **Everything beside the math stays affine.** A bound is one number per
  column. A `piecewise:` link expands into declarations, and those must be
  affine.

A named expression is held to the limit of the place that reads it: degree 2 in
the objective or a constraint, affine in a `piecewise:` link. A named expression
that nothing in the math reads is a [reported](reported.md) quantity, and no
degree limit applies to it.

`/` needs a divisor that carries no variable and is a single factor, not a sum.
A variable divisor is rational rather than polynomial, which is outside the
language at any degree.

`**` needs a base and an exponent that both carry no variable and neither of
which adds. `growth ** period` is one number per coordinate, so it is the same
arithmetic that `*` already does. `(1 + rate) ** period` is refused, because
addition does not distribute over `**`; bind the factor itself as a parameter.
A variable under `**` is refused because the exponent would decide the degree:
`p ** n` is affine at `n = 1` and quadratic at `n = 2`, and `to_spec` reads no
data. Write `x * x` for a square.

### Solver support

The language admits degree 2 in the objective and the constraints. Which solver
or file format takes the result is decided by the tool that builds the model.
See [the limits](../../about/limits.md#solver-capability).
Whether a quadratic form is convex is a property of the data, so no tool can
answer it from the file alone. A `piecewise:` block with `method: convex` spends
a curve and keeps the linear program, with its duals.

## Name resolution

A name is a letter or an underscore, followed by letters, digits or underscores.
A declaration keyed by anything else is a load error, because no expression
could write that key.

One flat namespace covers dimensions, lookups, parameters, variables, named
expressions, macros and the built-in operators. A collision is a load error that
names both declarations. There is no shadowing: with shadowing, a new parameter
named `snapshot` would silently change what `where: "snapshot > 0"` means.

Position decides which kinds of name are legal, and the kind of every name is
fixed at load:

| Position                                | Legal kinds                                                                                                  |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| expression (`p * cost`)                 | a variable, or a parameter whose values are numbers ([dtype](declarations.md#parameters))                    |
| dimension argument (`over=`)            | a dimension                                                                                                  |
| lookup argument (`by=` on `sum` / `at`) | a lookup, and never a dimension. `from=` and `to=` name its columns                                          |
| `where` string                          | a parameter, variable, dimension or lookup ([where strings](#where-strings))                                 |
| `bounds.lower` / `bounds.upper`         | a parameter name, or a number                                                                                |
| the `edge` key of `shift`               | `'wrap'` in quotes, or a bare number. Never a dimension                                                      |
| `dual` argument (`dual(c)`)             | a constraint. It resolves against the constraints alone ([reported](reported.md#reading-a-constraints-dual)) |

A bare word in the value of a keyword argument is a name to resolve. That is why
`wrap` is quoted: `shift(x, over=wrap, edge='wrap')` reads one way, even in a
model with a dimension called `wrap`. `edge` is the one keyword whose _key_ is
fixed rather than naming a dimension, so a dimension called `edge` changes
nothing.

A dimension where a value belongs is an error. A dimension is a coordinate
space, not data; to use its coordinates as data, declare a parameter over it. A
`str` or `bool` parameter where a value belongs is also an error: a label
selects rows and a flag masks rows, and both belong in a `where`. Only
`dtype: float` and `dtype: int` stand as a coefficient, a term or a divisor.

Constraints sit outside the flat namespace. The one position that names a
constraint is [`dual`'s argument](reported.md#reading-a-constraints-dual), so a
bare name never reaches a constraint, and a model may name a constraint after a
variable. The objective has no name at all.

## How dimensions combine

A parameter declares `dims`, a variable declares `foreach`, and every dimension
argument is name-checked. So **the dimension set of every expression is known
before any data binds**:

| Node                            | Dim set                                  | Error                                                                                                                    |
| ------------------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| number                          | `{}`                                     |                                                                                                                          |
| parameter / variable            | its `dims` / its `foreach`               |                                                                                                                          |
| `-x`, `+x`                      | `dims(x)`                                |                                                                                                                          |
| `a + b`, `a * b`, `a / b`       | `dims(a) ∪ dims(b)`                      |                                                                                                                          |
| `sum(x)`                        | `{}`                                     | error if `dims(x)` is already empty                                                                                      |
| `sum(x, over=d)`                | `dims(x) − {d}`                          | error if `d ∉ dims(x)`                                                                                                   |
| `sum(x, by=l)`                  | `(dims(x) − {from(l)}) ∪ {to(l)}`        | error if `from(l) ∉ dims(x)`, or if a joined column's dimension is not in `dims(x)`                                      |
| `sum(x, by=[l, m])`             | `(dims(x) − {from(l)}) ∪ {to(l), to(m)}` | the same errors, plus an error if `l` and `m` consume different dimensions, or if they produce the same one              |
| `at(x, by=l)`                   | `(dims(x) − {from(l)}) ∪ {to(l)}`        | error if `from(l) ∉ dims(x)`, if a joined column's dimension is not, or if `l` has no key inside the columns `to=` names |
| `shift(x, over=d, offset=n)`    | `dims(x)`                                | error if `d ∉ dims(x)`                                                                                                   |
| `sum_back(x, over=d, within=n)` | `dims(x)`                                | error if `d ∉ dims(x)`                                                                                                   |

A binary operator takes the **union** of the two dimension sets, so an outer
product is allowed wherever the declaration's own dimensions cover the result.
Those dimensions are the declaration's **frame**. What is never allowed is a
declaration that disagrees with its expression:

- A constraint requires `dims(lhs) ∪ dims(rhs)` to **equal** its `foreach`. A
  stray dimension multiplies the rows, and an unused `foreach` dimension repeats
  one row across them.
- An objective must carry **no dimensions**. It is one number, and the sums that
  reduce it to one number are written in the expression.
- A `where` predicate and a bound parameter must not **exceed** the frame they
  sit in.

Each of these is a load error.

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

| Written as                              | Names a…                               | Meaning                                                                                                                                                                                                                                                                                             |
| --------------------------------------- | -------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name` (bare)                           | parameter                              | The value is defined here. A `bool` is its own answer. A `str` is defined wherever the table has a row. A number has to have a row and be finite, so `0.0` counts and `inf` does not                                                                                                                |
| `name` (bare)                           | variable                               | The variable exists at this coordinate                                                                                                                                                                                                                                                              |
| `name` (bare)                           | lookup                                 | A row exists: at the key for a keyed lookup, at every column for a bare relation. A lookup may be [partial](dimensions.md#lookups), and this selects the labels that do map                                                                                                                         |
| `name` (bare)                           | dimension                              | A load error. It would be true everywhere. Compare it against something instead                                                                                                                                                                                                                     |
| `name OP value`                         | parameter                              | Element-wise, and a null compares false. The right-hand side is a literal, or a bare name read as a string label                                                                                                                                                                                    |
| `name OP value`                         | dimension                              | A filter on the frame's own coordinate column                                                                                                                                                                                                                                                       |
| `name OP value`, `name.col OP value`    | lookup                                 | A filter on a value column of a keyed lookup, read at its key, so the key's dimensions have to be in the frame. Name the column where the key determines several. A null compares false                                                                                                             |
| `name OP name`, `name.a OP name.b`      | two lookup columns                     | Legal only where both lookups are keyed over the same dimensions and both columns are over one dimension. `ends.bus0 != ends.bus1` excludes a self-loop                                                                                                                                             |
| `position(name) OP i`                   | dimension                              | Where the row sits along the dimension's own order. `0` is first, and a negative number counts from the end                                                                                                                                                                                         |
| `position(name, by=lookup[, from=col])` | a dimension and a lookup keyed over it | The same, counted within each group the lookup's value columns make                                                                                                                                                                                                                                 |
| `AND` `OR` `NOT`                        | —                                      | Case-insensitive. `NOT` binds tighter than `AND`, and `AND` tighter than `OR`                                                                                                                                                                                                                       |
| `True` / `False`                        | —                                      | Literals, folded at load wherever they stand. `True` is the same as no `where`; `False` gives a declaration with no rows. `x AND False` folds to `False`, and `NOT NOT x` to `x`. A [case `when:`](#the-rules-that-keep-the-cases-apart) is the one place a mask that folds to a literal is refused |

The dimensions of the mask must not exceed the frame it sits in. A bare name
that is not declared is a load error.

!!! warning "Defined is not the same as non-zero"

    A bare parameter name is true wherever the table has a row, and a row holding
    `0.0` is a row. So one `where:` masks nothing against a table padded with
    zeros, and deletes rows against a sparse table carrying the same information.
    Where you mean non-zero, write `where: "inflow != 0"`.

### The right-hand side of a comparison

A bare name on the right is read as a string label when the model does not
declare it. A declared name there is a load error that names the near miss,
because reading it as text would compare a column against another declaration's
name and mask everything out.

Quote a label that is not an identifier, and quote a date: `'combined-cycle'`,
`'IT-north'`, `'2030-01-01'`. A quoted word is never read as a declaration.

A comparison is checked against the declared `dtype`. A `datetime` dimension is
compared against a quoted ISO date such as `snapshot > '2030-01-01'` or
`'2030-01-01T06:00'`. A number against a `datetime` dimension is a load error,
because it would silently mean "after 1970-01-01". Calendar arithmetic and
resampling stay in data preparation.

String labels compare bytewise, whatever order the dimension declared them in,
so `node >= 'b'` means the same however the nodes were listed. A label the
dimension does not carry compares equal to nothing, so the mask is false there
rather than an error.

Comparing two parameters, or two dimensions, is not in the language. Precompute a
boolean parameter instead. Two lookup columns are the exception, where the two
lookups are keyed over the same dimensions and the two columns are over one
dimension. Keyed alike, they are two columns of one key table, so the comparison
filters that table rather than joining two. Over one dimension they draw from one
label set, so a match is possible at all.

### `position()`

`position(dim)` is where the row sits along the dimension's own order, which is
the order `shift` walks. A boundary written with it survives a relabelling of the
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

Relabel `[0, 1, 2]` to `[1, 2, 3]`, and `snapshot == 0` matches nothing, which
leaves the recurrence unanchored. `position(snapshot) == 0` still names the first
row.

`-1` is the last position, and `-2` the one before it. A position that no
coordinate occupies is an error when the data binds, not an empty mask, because
seeding no row is the failure the clause was written to prevent.

`by=` counts inside each group that a lookup makes. That gives one seeded row per
period, however long each period is:

```yaml
dimensions:
  snapshot: { dtype: int }
  period: { dtype: int }
lookups:
  period_of: { over: [snapshot, period], key: snapshot }
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

The lookup must have a key column over the dimension being counted, and its
value columns are the groups. A coordinate the lookup sends nowhere is in no
group. A group shorter than the position is an error when
the data binds, for the same reason as above.

## Named expressions

A named expression is a quantity the model names once. A constraint or the
objective may use it, and the engine can report its value after a solve:

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

Write it as a bare string, or as a mapping when it carries a `description:`. Its
dimensions fall out of its body, so there is no `foreach`. The CO₂ that a
constraint bounds and the CO₂ that a summary reports are then one definition,
validated once.

Where the objective or a constraint names it, the body is substituted before
anything reads the model. So a named expression is one of two things, and the
file never says which:

- **In the math**, when the objective or a constraint inlines it, directly or
  through another expression or a macro. It is held to the
  [degree limit](#where-a-product-of-two-variables-is-allowed) at the place that
  reads it.
- **Reported**, when nothing in the math names it. It is arithmetic over numbers
  a solve has produced, and the math's restrictions no longer apply. See
  [reported expressions](reported.md).

### `cases:` — one quantity, a value per region

Some quantities have no single expression. The commitment state a unit carries
into a snapshot has three regimes: `1` for a unit that is never switched off, an
initial condition at the first snapshot, and the previous snapshot's status
everywhere else. Written at the constraint, those regimes fork the inequality
three ways. Named here, the inequality is written once:

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

Each case prints as one row of the definition, and `otherwise:` as the last:

$$\mathit{previous\_status}_{t,g} = \begin{cases} 1 & \text{if } \neg \mathrm{committable}_{g} \cr \mathrm{status}^{\mathrm{initial}}_{g} & \text{if } \mathrm{committable}_{g} \wedge \mathrm{pos}(t) = 0 \cr \mathit{status}_{t - 1,g} & \text{otherwise} \end{cases} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G}$$

A named expression carries **exactly one** of `expression:` and `cases:`. A
`cases:` block is a map of named cases, each with a `when:` mask and an
`expression:`. Beside it, `otherwise:` carries every coordinate the cases leave,
and `foreach:` declares the **frame**: the dimensions every case ranges over. A
point of the frame is a **coordinate**, here one snapshot for one generator.

#### The rules that keep the cases apart

- **No two cases may claim one coordinate.** If two `when:` masks can hold at
  once, the file is refused at load, and the message names the pair, a
  coordinate both claim, and the rewrite:

  > `Named expression 'previous_status'`: cases `always_on` and `boundary` both
  > claim the value where committable is false, the position of snapshot is 0. A
  > coordinate two cases claim has two values, so it has none — narrow one of the
  > two `when:` strings by the negation of the other, or drop the wider one and
  > let `otherwise:` carry that region.

  That is why `boundary` above says `committable and`. The cases carry no order,
  so a tool that re-sorts the keys of a file cannot change what it means.

- **A `when:` must be a question the data answers.** `True`, `False`, and a mask
  that folds to one of them, such as `committable OR True`, are refused. A mask
  that admits every row leaves `otherwise:` nothing, and one that admits none
  never applies. A declaration's `where:` is not held to this rule, because
  there `False` means no rows and `True` means no mask.

- **A pair the check cannot decide is refused.** `position(snapshot) == 0`
  against `position(snapshot) == -1` pick the same row on an axis with one
  member, and how many members an axis has is data. Count from one end only.

- **`otherwise:` is required.** It carries no mask, so it has to hold at every
  coordinate the cases leave. Without it a coordinate no `when` matched would
  have no value, and absence [spreads](absence.md), so a constraint reading the
  expression would lose rows it never masked.

- **`foreach:` is required with cases, and refused without them.** A case may be
  a single number while its `when:` ranges over dimensions, as `always_on` does,
  so the frame cannot fall out of the body. Each `when:` and each value must sit
  inside the frame. The dimensions of a reference are the declared `foreach`,
  and a narrower case broadcasts as a parameter with fewer dimensions does.

Claiming a coordinate is not the same as having a value there. The `otherwise:`
above carries no `edge=`, so its `shift` has no value at the first snapshot, and
`previous_status` is whole there only because `boundary` or `always_on` claims
every unit at that snapshot. To close such a hole, widen a `when`, give the
`shift` an `edge=`, or set `absence: zero` on the masked variable. Nothing
catches a hole at load, because whether a case has a value depends on the data.

`cases:` inside a `macros:` template is not supported, because `otherwise:`
would have to cover a frame the macro does not have until it is called.

### How a named expression prints

A use prints the symbol. The body prints once, under a **Definitions** heading
between _Subject to_ and _Variable domains_, in declaration order. The symbol is
italic where a variable reaches the body and upright where none does, as every
other name is. A named expression joins the symbol pool, so a
[symbol table](../typeset.md#symbol-tables) can rename it.

`inline_expressions`, which is `--inline-expressions` on the command line,
substitutes each plain expression where it is used. A cased expression always
prints as a definition, because a `cases` block is taller than the line it would
sit in and would otherwise print once per use.

[The unit commitment example](../../examples/commitment.md) is the model this
section is drawn from.

## Macros

A macro is a template that takes arguments and is substituted into an expression
before anything reads it. It has no dimensions until it is called, so it has no
value that a solve could report:

<!-- doctest: wrap=macros -->

```yaml
weighted_sum:
  args: [array, weights] # positional formals, default []
  kwargs: [over] # keyword formals, default []
  template: sum(array * weights, over=over)
```

- A template holds arithmetic, and no comparison.
- Arguments expand before substitution, so an argument may itself use macros and
  named expressions.
- Inside a template, the formal parameters shadow model names. A formal may not
  collide with a declared dimension.
- The number of arguments is checked at each call site. A cycle is reported with
  its reference chain.
- Every template is parsed and name-checked at load, whether or not it is called.

Anything composed out of the [built-in operators](operators.md) belongs here.
Math the language cannot express is out of scope; see
[what the language will not express](errors.md#what-the-language-will-not-express).
