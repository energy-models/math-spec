<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Reported expressions

This page says which [named expressions](expressions.md#named-expressions) the
math never reads, what such an entry may say that the math refuses, and what
`dual()` reads. The file never marks an entry as one or the other; the
objective and the constraints decide:

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

`system_cost` is **in the math**: the objective inlines it, so its body stands
inside the program a solver sees. There it is held to the
[degree-2 ceiling](expressions.md#degree-2-in-the-math-degree-1-beside-it).
`delivered` and `lcoe` are **reported**: nothing in the objective or a
constraint names them, so no solver sees them. Each is a quantity read back
after a solve.

## What lifts and why

A reported body is arithmetic over numbers a solve has already produced, and
nothing in the model ingests it. So the restrictions the math carries lift:

- **No degree cap.** `system_cost / delivered` above divides one variable
  quantity by another, and `p * p * p` is sayable.
- **The divisor may carry variables, and so may an exponent.** Where such a
  divisor solves to zero, the quotient is absent there, the null a masked row
  leaves
  ([absence](absence.md#reported-values-follow-the-rows-that-were-built)).
- **A divisor, a base or an exponent may be a sum.** `x / (a + b)` and
  `(1 + rate) ** period` are accepted here and refused in the math.
- **A factor may be a sum of terms with no ceiling on the other.**
  [The one-sum-factor rule](expressions.md#degree-2-in-the-math-degree-1-beside-it)
  counts the rows a product builds, and a reported body builds none.

**Comparisons stay out**, as for an entry in the math: an `expressions:` body
is arithmetic, and `>=` belongs to a constraint.

## Which is which

An entry is in the math when the objective or a constraint inlines it. The
question is decided at load, with no data, on the expanded tree. So an entry
reached through another entry or a macro call counts the same as one named in
place. A bound and a `where` name no entry. A `piecewise:` link may,
and reaches the math through the constraints its expansion emits. A cased entry
is in the math on the same terms as a plain one.

Use decides, not the body's shape or when its value exists. `delivered` above
is affine and reported, because nothing reads it. `(1 + rate) ** period`, with
no variable in it, needs no solve and is reported all the same. The cost of
deciding by use is a typo: an entry meant for a constraint and never named
there loads as a reported quantity instead of failing.

A consumer reads the answer off the program, as
`Program.named_expressions[name].in_math`. On the page every named expression
prints its body once under **Definitions** and its symbol where it is used. A
reported entry reads no differently from one in the math. `in_math` decides
what [`inline_expressions=`](../typeset.md) may substitute away: an entry the
math reads is substituted into the equations that read it. A reported one has
nowhere to go, so its definition stands either way. One function decides both,
so the two cannot disagree.

## The math reads at its own ceiling

An entry's declaration is not degree-checked. Degree is a rule about the
position doing the reading. It fires on the expanded tree of **every**
constraint, the objective and each piecewise link, with the messages that
refuse a variable divisor or a degree-3 product written out by hand. A
constraint that references `lcoe` inlines its body and hits the divisor
rule at that position:

```text
Constraint 'cap': the divisor contains variables, which is not affine. Divide
by a parameter, or precompute the reciprocal as one.
```

The message names the constraint and the operation the inlined body performs,
not the entry `lcoe`: expansion has substituted it away before the ceiling is
checked. Move the quantity the constraint needs into an entry whose shape the
math can read.

## Reading a constraint's dual

`dual(c)` is the one builtin only a reported entry may call. It reads the
**row dual** of constraint `c`, the shadow price a solve puts on it, over `c`'s
own `foreach` frame. `c`
[resolves against constraints alone](expressions.md#name-resolution), never the
flat namespace. A variable or parameter sharing the name is not what `dual`
reads.

A dual exists only after a solve, so `dual` may stand only in an entry the math
never reads. Written in a constraint, the objective, a piecewise link, or an
entry one of those inlines, it is a load error naming the rewrite:

```text
Constraint 'd': a dual exists only after a solve; the math cannot read one —
keep the entry that carries it out of constraints, the objective, bounds and where.
```

The check runs on the **expanded** tree, so a macro or an inlined named
expression cannot carry a `dual` into the math.

Where a constraint's `where:` deletes a row, that row has no dual, so `dual(c)`
is absent there too, the null reading a lookup gets.

**A solve does not always return one.** A model with integer or binary
variables, a quadratic constraint, or a set reformulated into binaries may come
back with no dual for a row that carries one in a pure linear model. Solvers
differ on which. The language refuses none of these at load
([capability is not the ceiling](../../about/ceiling.md#capability-is-not-the-ceiling)).
`dual(c)` where a solve reports none is the same absence, which the consumer
names; the language does not promise the value is there.

**The sign is fixed by the constraint as written and the declared sense.**
`dual(c)` is the rate the optimal objective improves as `c` is relaxed in the
direction its `sense` points, under the model's own `minimize` or `maximize`.
Which side is `lhs`, which is `rhs` and which way `sense` faces are kept
verbatim. So two consumers reading the same model agree on the sign. A solver
that normalises signs its own way is reconciling its representation, not the
language's.

## What a consumer does with it

A reported entry is **observable**, like one in the math: after a solve, a
consumer reads its value back over its own dims. Those fall out of its body;
there is no `foreach` and no `where`. Where a masked row leaves a solved quantity
absent, the reported value is absent there too.

Nothing in this repository evaluates a reported body; computing the number is
a consumer's business
([what counts as language](../../about/what-counts-as-language.md)). The
language says what the number _is_, and which entries the math reads.
