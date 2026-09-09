<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Parameters, variables, constraints

The four blocks that carry the math, and the fields each takes. Every block
takes an optional `description:`: free text, never parsed, no length limit.
Unlike a `#` comment it is part of the loaded model, and the
[typeset](../typeset.md) legend prints the one on a dimension, parameter or
variable.

A description is **plain prose, with one piece of notation**. A name in
backticks sets in monospace in every output format: `` `capital_cost` ``,
`` `Generator-p_nom` ``. Everything else is text, and every format escapes what
its own syntax would read as markup: an underscore stays an underscore, and
`$\ell$` prints as those five characters.

## `parameters`

A parameter declares a shape only. The numbers bind by name at run time, in
whatever consumes the loaded model, and the three rules that binding obeys are
under [dimensions](dimensions.md).

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

**`dtype` is a claim about the values, and the bound column must match it.**
It decides whether the name is a value in an [expression](expressions.md) at
all, what a `where` comparison is checked against, what a bare `where` on the
name means ([where strings](expressions.md#where-strings)), and whether the
name may stand where an operator reads a
[position](operators.md#an-offset-that-differs-per-entity). A column that
disagrees does not bind.

| declared | the column                             |                                                  |
| -------- | -------------------------------------- | ------------------------------------------------ |
| `float`  | a float column — **or an integer one** | whole numbers are numbers, the one widening      |
| `int`    | an integer column                      | which is why a fractional position cannot arrive |
| `bool`   | a boolean column                       | `1`/`0` is not one; cast it, or declare `int`    |
| `str`    | a string column                        |                                                  |

**Only `float` and `int` are values.** A `str` parameter is a label and a
`bool` one is a mask; either one as a coefficient, a term or a divisor is a
load error. Select with the label (`where: "fuel == 'gas'"`) and carry the
numbers it picks out in a parameter of its own. Mask with the flag
(`where: "committable"`), or declare `dtype: int` where the `0`/`1` is data to
multiply by.

## `variables`

What the solver decides: one column per coordinate of `foreach`.

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

| Field                           |                                                                                                                                              |                        |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| `foreach`                       | required — the dim signature                                                                                                                 |                        |
| `where`                         | which coordinates exist ([absence](absence.md))                                                                                              | default `null`         |
| `bounds.lower` / `bounds.upper` | a number, or the name of a `float` or `int` parameter; two numbers that cross are refused at load, a named bound is checked against its data | default `-inf` / `inf` |
| `domain`                        | `continuous`, `integer` or `binary` — which carries fixed 0/1 bounds                                                                         | default `continuous`   |
| `absence`                       | `undefined` or `zero` — what the masked-out coordinates _mean_ ([absence](absence.md#what-a-missing-coordinate-means))                       | default `undefined`    |
| `description`                   | free text                                                                                                                                    | default `null`         |

**Omitting a bound means unbounded on that side.** Non-negativity is written,
not assumed.

**Bounds take a name or a number, never arithmetic.** `upper: p_max` loads;
`upper: -rating` is refused, and the message says so rather than reporting a
parse failure ([#31](https://github.com/fluxopt/lpspec/issues/31)). Ship the
negated column as data. A bound parameter's dims must not exceed `foreach`.

**Equal bounds pin a variable.** Bind `lower` and `upper` to the same value
where a quantity is given, and `rate - relmax * size <= 0` is one equation
whether `size` is chosen or data. Presolve substitutes the pinned column, so
the solver receives the LP the pre-multiplied form would have produced. A
pinned variable is still a variable: `size * on` is refused as variable ×
variable ([expressions](expressions.md)), and it cannot appear in another
variable's `bounds`.

## `constraints`

**One rule per block.** The block's name _is_ the constraint's name, and a row
is read back by it after a solve.

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
([dim algebra](expressions.md#dim-algebra)). Either side may carry variables,
and one side must: a comparison of numbers and parameters alone is refused at
load. A row the data leaves with no variable terms is
[not built](absence.md#a-row-with-no-variable-terms-is-not-built).

**`foreach: []` is one scalar row.** `sum(x, over=f) <= 120` has no free dims,
so `[]` is the signature that matches it. An empty dim list is one value for a
parameter's `dims: []`, one column for a variable's `foreach: []`, and one row
for a constraint's; a dummy dimension of size 1 is never how a scalar is
written. A scalar **variable** may not carry a `where`
([#340](https://github.com/fluxopt/lpspec/issues/340)); put the condition on
the constraints that use it.

**Two regimes of one rule are two blocks**, each under its own name:

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

`shift` vacates the first snapshot, and a vacated position is
[absent](absence.md), so that row drops without a `where`. `edge='wrap'` gated
on `where: "snapshot > 0"` builds the same rows on this horizon and a
_different_ model on one that does not start at 0: the gate hardcodes the
origin.

## `objective`

A single block, not a mapping, and it carries no name: the value is scalar, so
nothing reads back by name.

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

There is no `foreach`, and **the expression must be scalar**; otherwise a load
error names the wrapper it wants. Nothing is summed for you, so the file says
where each sum closes. With `x, a` on `i` and `y, b` on `j`,
`sum(x * a) + sum(y * b)` is `|i| + |j|` summands and `sum(x * a + y * b)` is
`|i| · |j|`: two models, and the bracket is the difference.

The schema holds one `objective` block, so a second objective is unsayable.
Weight several goals into one expression.
