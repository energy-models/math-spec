<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Parameters, variables, constraints

The four blocks that carry the math. Each block takes an optional
`description:` — free text, never parsed, no length limit. Unlike a `#` comment
it is part of the loaded model, so it reaches everything downstream: the
[typeset](../typeset.md) legend prints the one on a dimension, parameter or
variable.

A description is **plain prose, in no notation**. Every output format sets the
same words as text, escaping whatever its own syntax would otherwise read as
markup — an underscore stays an underscore, and a `$\ell$` prints as those five
characters rather than as a symbol. Write the thing rather than its symbol —
"flow on a line", not "flow on line $\ell$".

## `parameters`

Declared shape only; the numbers bind by name at run time, in whatever
consumes the AST.

```yaml
dimensions:
  snapshot: { dtype: int }
parameters:
  load:
    dims: [snapshot]
  discount_rate:
    dims: [] # a scalar
```

| Field         |                                                              |                 |
| ------------- | ------------------------------------------------------------ | --------------- |
| `dims`        | required — the dimensions it is indexed by; `[]` is a scalar |                 |
| `dtype`       | `float`, `int`, `bool`, `str`                                | default `float` |
| `description` | free text                                                    | default `null`  |

**`dtype` is a claim about the values, and the column has to be it.** It
decides four things — whether the name is a value in an
[expression](expressions.md) at all, what a `where` comparison is checked
against, what a bare `where` on the name _means_
([where strings](expressions.md#where-strings)), and whether the name may stand
where an operator reads a
[position](operators.md#an-offset-that-differs-per-entity) — so a column that
disagrees describes a model the data does not build, and does not bind.

| declared | the column                             |                                                  |
| -------- | -------------------------------------- | ------------------------------------------------ |
| `float`  | a float column — **or an integer one** | whole numbers are numbers, the one widening      |
| `int`    | an integer column                      | which is why a fractional position cannot arrive |
| `bool`   | a boolean column                       | `1`/`0` is not one; cast it, or declare `int`    |
| `str`    | a string column                        |                                                  |

**Arithmetic is over numbers, so only `float` and `int` are values.** A `str`
parameter is a label and a `bool` one is a mask — each of them names rows
rather than scaling them — so writing either as a coefficient, a term or a
divisor is a load error, not a cast the engine performs on the way past.
Select with the label (`where: "fuel == 'gas'"`) and carry the numbers it picks
out in a parameter of its own; mask with the flag (`where: "committable"`), or
declare it `dtype: int` where the `0`/`1` is meant to arrive as data and be
multiplied by.

## `variables`

What the solver decides — one column per coordinate of `foreach`.

```yaml
dimensions:
  snapshot: { dtype: int }
  generator: { dtype: str }
parameters:
  p_max: { dims: [generator] }
variables:
  p:
    foreach: [snapshot, generator]
    where: "p_max > 0"
    bounds:
      lower: 0
      upper: p_max
```

| Field                           |                                                                                                                        |                        |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| `foreach`                       | required — the dim signature                                                                                           |                        |
| `where`                         | which coordinates exist ([absence](absence.md))                                                                        | default `null`         |
| `bounds.lower` / `bounds.upper` | a number, or the name of a `float` or `int` parameter                                                                  | default `-inf` / `inf` |
| `domain`                        | `continuous`, `integer` or `binary` — which carries fixed 0/1 bounds                                                   | default `continuous`   |
| `absence`                       | `undefined` or `zero` — what the masked-out coordinates _mean_ ([absence](absence.md#what-a-missing-coordinate-means)) | default `undefined`    |
| `description`                   | free text                                                                                                              | default `null`         |

**Omitting a bound means unbounded on that side** — non-negativity is written,
not assumed.

**Bounds take a name or a number, never arithmetic.** `upper: p_max` is fine;
`upper: -rating` is not, and the error says so rather than reporting a parse
failure. Ship the negated column as data. (Expressions there are
[#31](https://github.com/fluxopt/lpspec/issues/31).) A bound parameter's dims
must not exceed `foreach`.

**Equal bounds pin a variable**, which is how one declaration covers a quantity
that is a decision in one model and data in another: bind `lower` and `upper`
to the same value where it is fixed, and `rate - relmax * size <= 0` is one
equation whether `size` is chosen or given. Presolve substitutes the pinned
column, so the solver receives the LP the pre-multiplied form would have
produced. Two limits: a pinned variable is still a variable, so `size * on` is
refused as variable × variable ([expressions](expressions.md)), and it cannot
appear in another variable's `bounds`.

## `constraints`

**One rule per block.** The block's name _is_ the constraint's name, which is
what a row is read back by after a solve.

```yaml
dimensions:
  snapshot: { dtype: int }
  generator: { dtype: str }
parameters:
  load: { dims: [snapshot] }
variables:
  p: { foreach: [snapshot, generator] }
constraints:
  power_balance:
    foreach: [snapshot]
    expression: sum(p, over=generator) == load
```

| Field         |                                              |                |
| ------------- | -------------------------------------------- | -------------- |
| `foreach`     | required — the rows this rule builds         |                |
| `expression`  | required — exactly one of `<=`, `>=`, `==`   |                |
| `where`       | which rows are built ([absence](absence.md)) | default `null` |
| `description` | free text                                    | default `null` |

The expression's dims must **equal** `foreach`
([dim algebra](expressions.md#dim-algebra)). Either side may carry the
variables, and one of them must: a comparison of numbers and parameters is
settled before the solve, so it is refused when the file is read. A _row_ that
ends up with none, because the data left its terms nowhere to sit, is not a
constraint and is not built
([absence](absence.md#a-row-with-no-variable-terms-is-not-built)).

**`foreach: []` is one scalar row** — a single system-wide budget, where the
expression reduces every dim away. Nothing special: `sum(x, over=f) <= 120` has
no free dims, so `[]` is the signature that matches it. An empty dim list is
the empty coordinate everywhere it appears — one value for a parameter's
`dims: []`, one column for a variable's `foreach: []`, one row for a
constraint's — so a dummy dimension of size 1 is never how a scalar is written.
One gap: a scalar **variable** may not carry a `where`
([#340](https://github.com/fluxopt/lpspec/issues/340)); put the condition on
the constraints that use it.

**Two regimes of one rule are two blocks**, and each gets a name a reader chose
rather than a position in a list:

<!-- doctest: wrap=constraints -->

```yaml
storage_balance:
  foreach: [snapshot, storage]
  expression: soc == shift(soc, over=snapshot, offset=1) * (1 - loss) + charge - discharge

storage_balance_initial:
  foreach: [snapshot, storage]
  where: "position(snapshot) == 0"
  expression: soc == soc_initial
```

`shift` vacates the first snapshot and a vacated position is
[absent](absence.md), so that row drops without a `where` saying so. Spelling
it `edge='wrap'` gated on `where: "snapshot > 0"` builds the same rows here and
a _different_ model on a horizon that does not start at 0 — the gate hardcodes
the origin, the operator does not.

## `objective`

A single block, not a mapping, and it carries no name — there is nothing a name
would read back, the value being scalar.

```yaml
dimensions:
  generator: { dtype: str }
parameters:
  cost: { dims: [generator] }
variables:
  p: { foreach: [generator] }
objective:
  sense: minimize
  expression: sum(p * cost)
```

| Field         |                                      |                    |
| ------------- | ------------------------------------ | ------------------ |
| `expression`  | required — arithmetic, no comparator |                    |
| `sense`       | `minimize` or `maximize`             | default `minimize` |
| `description` | free text                            | default `null`     |

There is no `foreach`, and **the expression must be scalar**: a load error
otherwise, naming the wrapper it wants. Nothing is summed for you, so where the
sum closes is a thing the file says rather than a rule to remember —
`sum(x * a) + sum(y * b)` with `x, a` on `i` and `y, b` on `j` is `|i| + |j|`
summands, and `sum(x * a + y * b)` is `|i| · |j|`. Both are sayable, they are
different models, and the bracket is the difference.

A second objective is unsayable rather than checked — the schema holds one
block. Weight several goals into one expression.
