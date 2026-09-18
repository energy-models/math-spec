<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Named expressions and macros

An `expressions:` entry names a quantity once, for the math to read or for a
solve to report. A `macros:` entry is a template with arguments, substituted
before anything reads it. This page says what each may contain, which
restrictions reach it, and how a solve reports one.

## `expressions`

A named expression is a quantity the model names once. A constraint or the
objective may use it, and the engine can report its value after a solve:

```yaml
dimensions:
  generator: { dtype: str }
parameters:
  rate: { dims: [generator] }
variables:
  p: { dims: [generator] }
expressions:
  total_generation: sum(p, over=generator)
  emissions:
    expression: sum(p * rate, over=generator)
    description: CO2 released, the quantity a cap would bound
```

Write it as a bare string, or as a mapping when it carries a `description:`. Its
dimensions fall out of its body, so there is no `dims:`. The CO₂ that a
constraint bounds and the CO₂ that a summary reports are then one definition,
validated once.

Where the objective or a constraint names it, the body is substituted before
anything reads the model, and the
[degree limit](expressions.md#where-a-product-of-two-variables-is-allowed)
applies where it is read. Where nothing in the math names it, the entry is
[reported](#reported-expressions).

## `cases`

Some quantities have no single expression. The commitment state a unit carries
into a snapshot has three regimes: `1` for a unit that is never switched off, an
initial condition at the first snapshot, and the previous snapshot's status
everywhere else. Written at the constraint, those regimes fork the inequality
three ways. Named here, the inequality is written once:

```yaml
expressions:
  previous_status:
    description: the commitment state a unit carries into a snapshot
    dims: [snapshot, generator]
    cases:
      always_on:
        when: "not committable"
        expression: 1
      boundary:
        when: "committable and position(snapshot) == 0"
        expression: status_initial
    otherwise: shift(status, along=snapshot, offset=1)
constraints:
  ramp_up:
    dims: [snapshot, generator]
    expression: >-
      p - shift(p, along=snapshot, offset=1, edge=0)
      <= ramp_limit * previous_status + start_up_limit * (1 - previous_status)
```

Each case prints as one row of the definition, and `otherwise:` as the last:

$$\mathit{previous\_status}_{t,g} = \begin{cases} 1 & \text{if } \neg \mathrm{committable}_{g} \cr \mathrm{status}^{\mathrm{initial}}_{g} & \text{if } \mathrm{committable}_{g} \wedge \mathrm{pos}(t) = 0 \cr \mathit{status}_{t - 1,g} & \text{otherwise} \end{cases} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G}$$

A named expression carries **exactly one** of `expression:` and `cases:`. A
`cases:` block is a map of named cases, each with a `when:` mask and an
`expression:`. Beside it, `otherwise:` carries every coordinate the cases leave,
and `dims:` declares the **frame**: the dimensions every case ranges over. A
point of the frame is a **coordinate**, here one snapshot for one generator.

### The rules that keep the cases apart

- **No two cases may claim one coordinate.** If two `when:` masks can hold at
  once, the file is refused at load:

  > `Named expression 'previous_status'`: cases `always_on` and `boundary` both
  > claim the value where committable is false, the position of snapshot is 0. A
  > coordinate two cases claim has two values, so it has none — narrow one of the
  > two `when:` strings by the negation of the other, or drop the wider one and
  > let `otherwise:` carry that region.

  That is why `boundary` above says `committable and`. The cases carry no order.

- **A `when:` must be a question the data answers.** `True`, `False`, and a mask
  that folds to one of them, such as `committable OR True`, are refused. A
  declaration's `where:` is not held to this rule.

- **A pair the check cannot decide is refused.** `position(snapshot) == 0`
  against `position(snapshot) == -1` pick the same row on an axis with one
  member, and how many members an axis has is data. Count from one end only.

- **`otherwise:` is required.** It carries no mask, and it holds at every
  coordinate the cases leave.

- **`dims:` is required with cases, and refused without them.** A case may be
  a single number while its `when:` ranges over dimensions, as `always_on` does.
  Each `when:` and each value must sit inside the frame, and a narrower case
  broadcasts as a parameter with fewer dimensions does.

Claiming a coordinate is not the same as having a value there. The `otherwise:`
above carries no `edge=`, so its `shift` has no value at the first snapshot, and
`previous_status` is whole there only because `boundary` or `always_on` claims
every unit at that snapshot. To close such a hole, widen a `when`, give the
`shift` an `edge=`, or set `absence: zero` on the masked variable. Nothing
catches a hole at load, because whether a case has a value depends on the data.

`cases:` inside a `macros:` template is not supported, because `otherwise:`
would have to cover a frame the macro does not have until it is called.

## Reported expressions

A named expression is either **in the math** or **reported**. The file never
says which. The objective and the constraints decide:

```yaml
dimensions:
  generator: { dtype: str }
  snapshot: { dtype: int }
parameters:
  marginal_cost: { dims: [generator] }
variables:
  p: { dims: [snapshot, generator] }
expressions:
  system_cost: sum(sum(p * marginal_cost, over=generator), over=snapshot)
  delivered: sum(sum(p, over=generator), over=snapshot)
  lcoe: system_cost / delivered
objective: { sense: minimize, expression: system_cost }
```

`system_cost` is in the math: the objective uses it, so the solver sees its body.
`delivered` and `lcoe` are reported: no constraint and no objective uses them, so
the solver never sees them, and the engine computes them from the solution
afterwards.

### Which entries are in the math

An entry is in the math when the objective or a constraint inlines it. The
question is answered at load, on the expanded tree, so an entry reached through
another entry or a macro call counts the same as one named in place. A bound and
a `where` name no entry. A `piecewise:` link may name one, and it reaches the
math through the constraints the link expands into.

"Reported" is about what the math reads, not about the shape of the body.
`delivered` is affine and reported, because nothing reads it. An entry with no
variable in it, such as `(1 + rate) ** period`, is reported all the same.

### Which restrictions do not apply

A reported body is built by no solver, so:

- **There is no degree limit.** `system_cost / delivered` divides one variable
  quantity by another, and `p * p * p` is allowed.
- **A divisor, a base or an exponent may carry variables, and may be a sum.**
  In the math, `/` and `**` need a variable-free single factor. Here
  `x / (a + b)` and `(1 + rate) ** period` need no precomputed parameter.
- **Both factors of a product may be sums.**

A comparison stays out: an `expressions:` body is arithmetic, and `>=` belongs
to a constraint.

### Where an entry is checked

The declaration of an entry is not degree-checked. Degree is a rule about the
position that reads, so it applies to the expanded tree of every constraint, the
objective and each piecewise link. A constraint that references `lcoe` inlines
its body and hits the divisor rule there:

```text
Constraint 'cap': the divisor contains variables, which is not affine. Divide
by a parameter, or precompute the reciprocal as one.
```

The message names the constraint and the operation, not the entry `lcoe`,
because expansion has already substituted `lcoe` away.

### Reading a constraint's dual

`dual(c)` reads the **row dual** of the constraint `c`: the shadow price a solve
puts on that row, over `c`'s own `dims`. It is the one built-in that only a
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
under the model's own `minimize` or `maximize`.

A row that a constraint's `where:` deletes has no dual, so `dual(c)` has no
value there. A solver may also return no dual for a row that would have one in a
pure linear program: a model with integer variables, or a set rewritten as
binaries. `to_spec` refuses none of these, because
[what a solver returns is not the language's limit](../../about/limits.md#solver-capability).
Where the solver returns no dual, the engine reports no value.

A reported entry has the dimensions of its body, so there is no `dims:` and no
`where`. Where a masked row leaves a solved quantity absent, the reported value
is absent there too ([absence](absence.md#reported-values)). Nothing in this
package computes a reported value: the language says what the number is and
which entries the math uses, and the engine computes it from the solution.

## `macros`

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
