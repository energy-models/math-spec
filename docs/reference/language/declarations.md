<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Parameters, variables, constraints and the objective

These are the four blocks that carry the math. Each block takes an optional
`description:`. A description is free text, it is never parsed, and it has no
length limit.

A `#` comment is thrown away, but a description is part of the loaded model, so
it reaches everything downstream. The [typeset](../typeset.md) legend prints
the description on a dimension, a parameter or a variable.

A description is **plain prose, in no notation.** Every output format sets the
same words as text. Each format escapes whatever its own syntax would otherwise
read as markup. So an underscore stays an underscore, and `$\ell$` prints as
those five characters instead of a symbol. Write the thing itself rather than
its symbol: write "flow on a line", not "flow on line $\ell$".

## `parameters`

A parameter declares a shape and nothing more. The numbers bind by name at run
time, inside whatever consumes the syntax tree.

Three things about that binding are not the consumer's to decide: where a
dimension's members come from, what order they stand in, and the rule that a
table carries each coordinate at most once. Those three are covered in
[dimensions](dimensions.md).

```yaml
dimensions:
  snapshot: { dtype: int }
parameters:
  load:
    dims: [snapshot]
  discount_rate:
    dims: [] # a scalar
```

| Field         |                                                                |                 |
| ------------- | -------------------------------------------------------------- | --------------- |
| `dims`        | required. The dimensions it is indexed by. `[]` means a scalar |                 |
| `dtype`       | `float`, `int`, `bool`, `str`                                  | default `float` |
| `description` | free text                                                      | default `null`  |

The `dtype` is a claim about the values, and the column has to match it. It
decides four things:

- whether the name is a value in an [expression](expressions.md) at all;
- what a `where` comparison is checked against;
- what a bare `where` on the name _means_, described under
  [where strings](expressions.md#where-strings);
- whether the name may stand where an operator reads a
  [position](operators.md#an-offset-that-differs-per-entity).

So a column that disagrees with the declared `dtype` describes a model that the
data does not build. Such a column does not bind.

| declared | the column                             |                                                                 |
| -------- | -------------------------------------- | --------------------------------------------------------------- |
| `float`  | a float column — **or an integer one** | whole numbers are numbers, the one widening                     |
| `int`    | an integer column                      | which is why a fractional position cannot arrive                |
| `bool`   | a boolean column                       | `1` and `0` are not booleans. Cast the column, or declare `int` |
| `str`    | a string column                        |                                                                 |

Arithmetic works over numbers, so only `float` and `int` are values. A `str`
parameter is a label, and a `bool` parameter is a mask. Each of them names
rows rather than scaling them. So if you write either one as a coefficient, a
term or a divisor, you get a load error. The engine does not quietly cast it on
the way past.

Use each kind for what it is:

- Select with a label, as in `where: "fuel == 'gas'"`, and carry the numbers
  that the label picks out in a parameter of its own.
- Mask with a flag, as in `where: "committable"`.
- Declare the column `dtype: int` where the `0` or `1` really is meant to arrive
  as data and be multiplied by.

## `variables`

A variable is what the solver decides. There is one column per coordinate of
`foreach`.

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
| `foreach`                       | required. The dimension signature                                                                                                            |                        |
| `where`                         | which coordinates exist ([absence](absence.md))                                                                                              | default `null`         |
| `bounds.lower` / `bounds.upper` | a number, or the name of a `float` or `int` parameter. Two numbers that cross are refused at load. A named bound is checked against its data | default `-inf` / `inf` |
| `domain`                        | `continuous`, `integer` or `binary`. `binary` carries fixed 0/1 bounds                                                                       | default `continuous`   |
| `absence`                       | `undefined` or `zero`. This says what the masked-out coordinates _mean_ ([absence](absence.md#what-a-missing-coordinate-means))              | default `undefined`    |
| `description`                   | free text                                                                                                                                    | default `null`         |

!!! warning "A bound you omit leaves the variable unbounded on that side"

    You write non-negativity. The language does not assume it.

Bounds take a name or a number, and never arithmetic. `upper: p_max` is
fine. `upper: -rating` is not, and the error says exactly that instead of
reporting a parse failure. Ship the negated column as data. Allowing
expressions there is [#31](https://github.com/fluxopt/lpspec/issues/31). The
dimensions of a bound parameter must not exceed `foreach`.

Equal bounds pin a variable. This is how one declaration can cover a
quantity that is a decision in one model and data in another. Bind `lower` and
`upper` to the same value where the quantity is fixed. Then
`rate - relmax * size <= 0` is one equation, whether `size` is chosen or given.
Presolve substitutes the pinned column, so the solver receives the same linear
program that the pre-multiplied form would have produced.

There are two limits on this. A pinned variable is still a variable, so
`size * on` is refused as variable × variable, as described in
[expressions](expressions.md). And a pinned variable cannot appear in another
variable's `bounds`.

## `constraints`

One block is one rule. The name of the block _is_ the name of the constraint,
and that name is how you read a row back after a solve.

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

| Field         |                                                     |                |
| ------------- | --------------------------------------------------- | -------------- |
| `foreach`     | required. The rows this rule builds                 |                |
| `expression`  | required. It uses exactly one of `<=`, `>=` or `==` |                |
| `where`       | which rows are built ([absence](absence.md))        | default `null` |
| `description` | free text                                           | default `null` |

The dimensions of the expression must **equal** `foreach`. See
[how dimensions combine](expressions.md#how-dimensions-combine).

Either side of the comparator may carry the variables, and one side must carry
them. A comparison between numbers and parameters is settled before the solve,
so the language refuses it when the file is read. A single _row_ can also end up
with no variables, because the data left its terms nowhere to sit. Such a row is
not a constraint, and it is not built. See
[absence](absence.md#a-row-with-no-variable-terms-is-not-built).

`foreach: []` gives one scalar row. Use it for a single system-wide
budget, where the expression reduces every dimension away. There is nothing
special about it: `sum(x, over=f) <= 120` has no free dimensions, so `[]` is the
signature that matches.

An empty dimension list means the empty coordinate everywhere it appears. It is
one value for a parameter's `dims: []`, one column for a variable's
`foreach: []`, and one row for a constraint's. So you never write a scalar as a
dummy dimension of size 1.

There is one gap here. A scalar **variable** may not carry a `where`
([#340](https://github.com/fluxopt/lpspec/issues/340)). Put the condition on the
constraints that use it instead.

Two regimes of one rule are two blocks. Each block then gets a name that a
reader chose, rather than a position in a list:

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
[absent](absence.md). So that row drops out without a `where` saying so.

You could instead write `edge='wrap'` and gate it on `where: "snapshot > 0"`.
That builds the same rows in this model, but it builds a _different_ model on a
horizon that does not start at 0. The gate hardcodes the origin; the operator
does not.

## `objective`

The objective is a single block, not a mapping, and it carries no name. The
value is a scalar, so there would be nothing for a name to read back.

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

| Field         |                                          |                    |
| ------------- | ---------------------------------------- | ------------------ |
| `expression`  | required. Arithmetic, with no comparator |                    |
| `sense`       | `minimize` or `maximize`                 | default `minimize` |
| `description` | free text                                | default `null`     |

There is no `foreach` here, and **the expression must be scalar.** Anything
else is a load error, and the message names the wrapper it wants.

Nothing is summed for you. So the file says where the sum closes, and you do not
have to remember a rule about it. Suppose `x` and `a` are on `i`, and `y` and
`b` are on `j`. Then `sum(x * a) + sum(y * b)` has `|i| + |j|` summands, while
`sum(x * a + y * b)` has `|i| · |j|`. You can say both, they are different
models, and the bracket is the whole difference.

You cannot say a second objective at all, so nothing needs to check for one:
the schema holds a single block. To pursue several goals, weight them into one
expression.
