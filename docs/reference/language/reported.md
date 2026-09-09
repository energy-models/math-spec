<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Reported expressions

A [named expression](expressions.md#named-expressions) is either **in the
math** or **reported**. The file never says which. The objective and the
constraints decide:

```yaml
dimensions:
  generator: { dtype: str }
  snapshot: { dtype: int }
parameters:
  marginal_cost: { dims: [generator] }
variables:
  p: { foreach: [snapshot, generator] }
expressions:
  system_cost: sum(sum(p * marginal_cost, over=generator), over=snapshot)
  delivered: sum(sum(p, over=generator), over=snapshot)
  lcoe: system_cost / delivered
objective: { sense: minimize, expression: system_cost }
```

`system_cost` is in the math: the objective inlines it, so its body stands inside
the program a solver sees. `delivered` and `lcoe` are reported: nothing in the
objective or a constraint names them, so no solver sees them, and a consumer
reads their values back after a solve.

## Which entries are in the math

An entry is in the math when the objective or a constraint inlines it. The
question is answered at load, on the expanded tree, so an entry reached through
another entry or a macro call counts the same as one named in place. A bound and
a `where` name no entry. A `piecewise:` link may name one, and it reaches the
math through the constraints the link expands into.

"Reported" is about what the math reads, not about the shape of the body.
`delivered` is affine and reported, because nothing reads it. An entry with no
variable in it, such as `(1 + rate) ** period`, is reported all the same.

Deciding by use costs one thing: an entry meant for a constraint, and never named
there, loads as a reported quantity instead of failing.

A consumer reads the answer at `Program.named_expressions[name].in_math`.

## Which restrictions do not apply

The math carries its restrictions because a solver has to build it. A reported
body is built by nothing, so:

- **There is no degree limit.** `system_cost / delivered` divides one variable
  quantity by another, and `p * p * p` is allowed.
- **A divisor, a base or an exponent may carry variables, and may be a sum.**
  In the math, `/` and `**` need a variable-free single factor. Here
  `x / (a + b)` and `(1 + rate) ** period` need no precomputed parameter.
- **Both factors of a product may be sums.** The
  [one-sum-factor rule](expressions.md#where-a-product-of-two-variables-is-allowed)
  is about how many rows a product builds, and a reported body builds none.

Without this, LCOE, which is cost over delivered energy, could not be written.

A comparison stays out: an `expressions:` body is arithmetic, and `>=` belongs
to a constraint.

## An entry is checked where it is read

The declaration of an entry is not degree-checked. Degree is a rule about the
position that reads, so it applies to the expanded tree of every constraint, the
objective and each piecewise link. A constraint that references `lcoe` inlines
its body and hits the divisor rule there:

```text
Constraint 'cap': the divisor contains variables, which is not affine. Divide
by a parameter, or precompute the reciprocal as one.
```

The message names the constraint and the operation, not the entry `lcoe`,
because expansion has already substituted `lcoe` away. If a constraint needs a
quantity, move that quantity into an entry whose shape the math can read.

## Reading a constraint's dual

`dual(c)` reads the **row dual** of the constraint `c`: the shadow price a solve
puts on that row, over `c`'s own `foreach`. It is the one built-in that only a
reported entry may call.

`c` [resolves against the constraints alone](expressions.md#name-resolution),
so a variable or parameter sharing the name is not what `dual` reads.

A dual exists only after a solve, so `dual` is refused anywhere the solver
ingests: a constraint, the objective, a piecewise link, and any entry one of
those inlines. The check runs on the expanded tree, so a macro cannot carry a
`dual` into the math:

```text
Constraint 'd': a dual exists only after a solve; the math cannot read one —
keep the entry that carries it out of constraints, the objective, bounds and where.
```

The sign is fixed by the file. `dual(c)` is the rate at which the optimal
objective improves as `c` is relaxed in the direction its comparator points,
under the model's own `minimize` or `maximize`. A solver that normalises signs
its own way reconciles its representation, not the language's.

A row that a constraint's `where:` deletes has no dual, so `dual(c)` has no
value there. A solve may also return no dual for a row that would carry one in a
pure linear model, such as a row in a model with integer variables or a
reformulated set. The language refuses none of these at load, because what a
solver returns is [not the language's limit](../../about/limits.md#what-a-solver-can-take-is-a-separate-question).
A missing dual is an absence the consumer names, not a value the language
promises.

## How a consumer reads a reported entry

A reported entry's value is read back over its own dimensions, which fall out of
its body, so there is no `foreach` and no `where`. Where a masked row leaves a
solved quantity absent, the reported value is absent there too. See
[absence](absence.md#reported-values-follow-the-rows-that-were-built).

Nothing in this package evaluates a reported body. The language says what the
number is and which entries the math reads. Computing the number is a
[consumer's](../../about/what-counts-as-language.md) work.
