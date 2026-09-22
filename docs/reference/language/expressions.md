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
  then `*` and `/`, then binary `+` and `-`. So `-x ** 2` is `-(x ** 2)`, as in
  Python. Parentheses override precedence.
- A float may carry an exponent, as in `1e5` or `2.5e-3`.
- The same keyword twice in one call is an error.
- An expression nests at most 100 levels deep, and so does a `where:` string.

## Where a product of two variables is allowed

The objective and the constraints take `variable * variable`. A quadratic cost is
`sum(p * p * wear, over=g)`, and a quadratic row is `p * q >= floor`. Three rules
bound it:

- **At most one factor may be a sum of terms.** `sum(p, over=g) * sum(q, over=g)`
  is refused. Multiply before you reduce, or constrain a variable to equal the
  reduction. Factors on different dimensions are allowed: `x * y * link`
  broadcasts, and the table `link` says which pairs exist.
- **Degree stops at 2.** `p * p * p` is refused.
- **Everything beside the math stays affine.** A bound is one number per
  column, and a `piecewise:` link is affine.

A [named expression](named.md) is held to the limit of the place that reads
it. One that nothing in the math reads is [reported](named.md#reported-expressions),
and no degree limit applies to it.

`/` needs a divisor that carries no variable and is a single factor.

`**` needs a base and an exponent that both carry no variable and neither of
which adds. `growth ** period` is allowed, and `(1 + rate) ** period` is
refused: bind the factor itself as a parameter. Write `x * x` for a square.

## Name resolution

A name is a letter or an underscore, followed by letters, digits or underscores.

One flat namespace covers dimensions, relations, parameters, variables, named
expressions, macros and the built-in operators. A collision is a load error that
names both declarations, and nothing shadows anything.

Position decides which kinds of name are legal:

| Position                               | Legal kinds                                                                                                        |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| expression (`p * cost`)                | a variable, or a parameter whose values are numbers ([dtype](declarations.md#parameters))                          |
| dimension argument (`over=`, `along=`) | a dimension                                                                                                        |
| relation argument (`by=`)              | a relation. `over=`, `into=` and `within=` name its columns                                                        |
| `where` string                         | a parameter, variable, dimension or relation ([where strings](#where-strings))                                     |
| `bounds.lower` / `bounds.upper`        | a parameter name, or a number                                                                                      |
| the `edge` key of `shift`              | `'wrap'` in quotes, or a bare number                                                                               |
| `dual` argument (`dual(c)`)            | a constraint. It resolves against the constraints alone ([named expressions](named.md#reading-a-constraints-dual)) |

A bare word in the value of a keyword argument is a name to resolve, which is
why `wrap` is quoted. A keyword's key is never a name.

Constraints sit outside the flat namespace, so a model may name a constraint
after a variable. The objective has no name at all.

## How dimensions combine

The dimension set of every expression is known before any data binds:

| Node                             | Dim set                        | Error                                                                            |
| -------------------------------- | ------------------------------ | -------------------------------------------------------------------------------- |
| number                           | `{}`                           |                                                                                  |
| parameter / variable             | its `dims`                     |                                                                                  |
| `-x`, `+x`                       | `dims(x)`                      |                                                                                  |
| `a + b`, `a * b`, `a / b`        | `dims(a) ∪ dims(b)`            |                                                                                  |
| `sum(x)`                         | `{}`                           | error if `dims(x)` is already empty                                              |
| `sum(x, over=d)`                 | `dims(x) − {d}`                | error if `d ∉ dims(x)`                                                           |
| `sum(x, by=l, over=a, into=b)`   | `(dims(x) − joined) ∪ grouped` | the refusals under [how a relation is used](relations.md#how-a-relation-is-used) |
| `at(x, by=l, over=a, into=b)`    | `(dims(x) − joined) ∪ grouped` | the same                                                                         |
| `shift(x, along=d, offset=n)`    | `dims(x)`                      | error if `d ∉ dims(x)`                                                           |
| `sum_back(x, along=d, window=n)` | `dims(x)`                      | error if `d ∉ dims(x)`                                                           |

A binary operator takes the **union** of the two dimension sets, so an outer
product is allowed. The declaration's own dimensions are its **frame**, and a
declaration may not disagree with its expression:

- A constraint requires `dims(lhs) ∪ dims(rhs)` to **equal** its `dims`.
- An objective must carry **no dimensions**. Write the sums that reduce it.
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
POSITION   ::= "position" "(" NAME [ "," "by" "=" NAME "," "within" "=" COLUMNS ] ")"
COLUMNS    ::= NAME | "[" NAME { "," NAME } "]"
QUOTED     ::= "'" chars "'" | '"' chars '"'
```

| Written as                              | Names a…             | Meaning                                                                                                                                                           |
| --------------------------------------- | -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name` (bare)                           | parameter            | The value is defined here. A `bool` is its own answer. A `str` is defined wherever the table has a row. A number has to have a row and be finite                  |
| `name` (bare)                           | variable             | The variable exists at this coordinate                                                                                                                            |
| `name` (bare)                           | relation             | A row exists, read at the relation's key. A relation may be [partial](relations.md#the-data-contract), and this selects the labels that do map                    |
| `name` (bare)                           | dimension            | A load error. It would be true everywhere                                                                                                                         |
| `name OP value`                         | parameter            | Element-wise, and a null compares false                                                                                                                           |
| `name OP value`                         | dimension            | A filter on the frame's own coordinate column                                                                                                                     |
| `name OP value`, `name.col OP value`    | relation             | A filter on a value column, read at the relation's key. Name the column where the key determines several                                                          |
| `name OP name`, `name.a OP name.b`      | two relation columns | Legal where both relations are keyed over the same dimensions and both columns are over one dimension. `ends.bus0 != ends.bus1` excludes a self-loop              |
| `position(name) OP i`                   | dimension            | Where the row sits along the dimension's own order. `0` is first, and a negative number counts from the end                                                       |
| `position(name, by=relation, within=c)` | dimension            | The same, counted within each group the relation makes                                                                                                            |
| `AND` `OR` `NOT`                        | —                    | Case-insensitive. `NOT` binds tighter than `AND`, and `AND` tighter than `OR`                                                                                     |
| `True` / `False`                        | —                    | `True` is the same as no `where`; `False` gives a declaration with no rows. A [case `when:`](named.md#the-rules-that-keep-the-cases-apart) may not fold to either |

The dimensions of the mask must not exceed the frame it sits in. A bare name
that is not declared is a load error.

!!! warning "Defined is not the same as non-zero"

    A bare parameter name is true wherever the table has a row, and a row
    holding `0.0` is a row. Where you mean non-zero, write `where: "inflow != 0"`.

### The right-hand side of a comparison

A bare name on the right is read as a string label when the model does not
declare it. A declared name there is a load error.

Quote a label that is not an identifier, and quote a date: `'combined-cycle'`,
`'IT-north'`, `'2030-01-01'`. A quoted word is never read as a declaration.

A comparison is checked against the declared `dtype`. A `datetime` dimension is
compared against a quoted ISO date such as `snapshot > '2030-01-01'` or
`'2030-01-01T06:00'`, and a number against it is a load error.

String labels compare bytewise, whatever order the dimension declared them in.
A label the dimension does not carry compares equal to nothing, so the mask is
false there.

Comparing two parameters, or two dimensions, is not in the language. Precompute
a boolean parameter instead.

### `position()`

`position(dim)` is where the row sits along the dimension's own order, which is
the order `shift` steps along. A boundary written with it survives a relabelling of
the index:

```yaml
dimensions:
  snapshot: { dtype: int }
parameters:
  soc_initial: { dims: [] }
variables:
  soc: { dims: [snapshot], bounds: { lower: 0 } }
constraints:
  soc_start:
    dims: [snapshot]
    where: "position(snapshot) == 0" # not: snapshot == 0
    expression: soc == soc_initial
```

`-1` is the last position, and `-2` the one before it. A position that no
coordinate occupies is an error when the data binds.

`by=` counts inside each group that a relation makes. That gives one seeded row
per period, however long each period is:

```yaml
dimensions:
  snapshot: { dtype: int }
  period: { dtype: int }
relations:
  period_of: { key: snapshot, values: period }
parameters:
  soc_initial: { dims: [period] }
variables:
  soc: { dims: [snapshot], bounds: { lower: 0 } }
constraints:
  soc_start:
    dims: [snapshot]
    where: "position(snapshot, by=period_of, within=period) == 0"
    expression: soc == at(soc_initial, by=period_of, over=period, into=snapshot)
```

The relation must have a key column over the dimension being counted, and
`within=` names the value columns the groups are made of
([partitions](relations.md#partitions)). A coordinate the relation sends
nowhere is in no group.
