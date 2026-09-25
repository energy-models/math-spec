<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Named expressions and macros

An `expressions:` entry names a quantity once, for the math to read or for a
solve to report. A `macros:` entry is a template with arguments, substituted
before anything reads it.

## `expressions`

A constraint or the objective may use a named expression, and a solve may
report its value:

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

It is a bare string, or a mapping with a `description:`. Its body decides its
dimensions, and there is no `dims:`.

Where the objective or a constraint names it, the body is substituted there,
and the [degree limit](expressions.md#where-a-product-of-two-variables-is-allowed)
applies where it is read. Where nothing in the math names it, the entry is
[reported](#reported-expressions).

## `cases`

A quantity with several regimes is written as cases, and the rule that reads it
is written once. The commitment state a unit carries into a snapshot is `1`
for a unit that is never switched off, an initial condition at the first
snapshot, and the previous snapshot's status everywhere else:

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

A named expression carries **exactly one** of `expression:` and `cases:`.

| Key         |                                                                                                   |
| ----------- | ------------------------------------------------------------------------------------------------- |
| `dims`      | required with `cases:`, and refused without. The **frame**: the dimensions every case ranges over |
| `cases`     | a map of named cases, each with a `when:` mask and an `expression:`                               |
| `otherwise` | required. The value at every coordinate the cases leave                                           |

### The rules that keep the cases apart

- **No two cases may claim one coordinate.** If two `when:` masks can hold at
  once, the file is refused at load:

  > `Named expression 'previous_status'`: cases `always_on` and `boundary` both
  > claim the value where committable is false, the position of snapshot is 0. A
  > coordinate two cases claim has two values, so it has none — narrow one of the
  > two `when:` strings by the negation of the other, or drop the wider one and
  > let `otherwise:` carry that region.

  The cases carry no order.

- **A `when:` must be a question the data answers.** `True`, `False`, and a mask
  that folds to one of them, such as `committable OR True`, are refused.

- **A pair the check cannot decide is refused.** `position(snapshot) == 0`
  against `position(snapshot) == -1` pick the same row on an axis with one
  member. Count from one end only.

- **A `when:` may not compare expressions**, such as `c > 2 * k`, even in a
  block with one case. Precompute the test as a boolean parameter.

- **Each `when:` and each value sits inside the frame.** A narrower case
  broadcasts as a parameter with fewer dimensions does.

A claimed coordinate can still have no value: the `otherwise:` above has none
at the first snapshot, where a case claims every unit. To close such a hole,
widen a `when`, give the `shift` an `edge=`, or set `absence: zero` on the
masked variable.

`cases:` is not accepted inside a `macros:` template.

## Reported expressions

A named expression is either **in the math** or **reported**. The objective
and the constraints decide which:

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

`system_cost` is in the math. `delivered` and `lcoe` are reported.

An entry is in the math when the objective, a constraint or a `piecewise:`
link reaches it, directly or through another entry or a macro. A bound and a
`where` name no entry.

**No degree limit applies to a reported entry**: it may divide by a variable,
raise one to a power, and multiply two sums. A comparison stays out. A
constraint that names such an entry is refused under the constraint's own name.

### Reading a constraint's dual

`dual(c)` reads the **row dual** of the constraint `c`: the shadow price a solve
puts on that row, over `c`'s own `dims`. Only a reported entry may call it. In a
constraint, the objective, a piecewise link, or an entry one of those inlines,
it is refused:

```text
Constraint 'd': a dual exists only after a solve; the math cannot read one —
keep the entry that carries it out of constraints, the objective, bounds and where.
```

`dual(c)` is the rate at which the optimal objective improves as `c` is relaxed
in the direction its comparator points, under the model's own `minimize` or
`maximize`.

A row that `c`'s `where:` deletes has no dual.

## `macros`

A macro is a template that takes arguments and is substituted into an expression
before anything reads it:

```yaml
macros:
  weighted_sum:
    args: [array, weights] # positional formals, default []
    kwargs: [over] # keyword formals, default []
    template: sum(array * weights, over=over)
```

- A template holds arithmetic, and no comparison.
- An argument may itself use macros and named expressions.
- Inside a template, the formal parameters shadow model names. A formal may not
  collide with a declared dimension.
- The number of arguments is checked at each call site. A cycle is reported with
  its reference chain.
- Every template is held at load to every rule a call site is, whether or not it
  is called. A formal is left for the call site to bind.

A composition of the [built-in operators](operators.md) belongs here. What
the language will not express is in
[the limits](../../about/limits.md#deliberate-non-primitives).
