<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Reported expressions

A [named expression](expressions.md#named-expressions) is one of two things.
The file never says which one it is. The objective and the constraints decide:

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

`system_cost` is **in the math**. The objective inlines it, so its body stands
inside the program that a solver sees. It is held to the
[degree-2 limit](expressions.md#where-a-product-of-two-variables-is-allowed) at
the place where it is read.

`delivered` and `lcoe` are **reported**. Nothing in the objective or in a
constraint names them, so no solver sees them. Each one is a quantity that you
read back after a solve.

`lcoe` could not be anything else, because a variable divisor is a shape that
the math refuses. `delivered` could have stood in the math, and it simply does
not. Nothing in the YAML marks either one.

Which entry is which is decided at load, with no data. The loader expands the
objective and every constraint, and notes each entry that they inline.

## Which restrictions do not apply, and why

An entry that the math reads is substituted into the math before anything reads
the model. So it is held to the same limits as the math around it.

A reported entry is read by nothing in the model. It is arithmetic over numbers
that a solve has already produced. The math carries its restrictions because a
solver has to build it, and none of those restrictions applies to a body that no
solver ever sees:

- There is no degree cap. `system_cost / delivered` above divides one
  variable quantity by another. `p * p * p` is allowed. A quotient, a cube and a
  ratio of two sums are each just a number once the solve is done.
- The divisor may carry variables, and so may an exponent. In the math, `/`
  and `**` require an operand free of variables. Here they drop that
  requirement, because there is no degree left for a variable operand to change.
  Where such a divisor solves to zero, the quotient is absent at that
  coordinate. That is the same null a masked row leaves. See
  [absence](absence.md#reported-values-follow-the-rows-that-were-built).
- A divisor, a base or an exponent may be a sum. The math refuses
  `x / (a + b)` and `(1 + rate) ** period` even when there is no variable in
  sight. It refuses them because a quotient compiles to one reciprocal factor,
  and neither operator distributes over `+`. A reported body compiles to
  nothing, so you no longer need the precompute that an entry in the math would
  need, which is `(1 + rate) ** period` bound as a parameter.
- A factor may be a sum of terms, with no limit on the other factor.
  [The one-sum-factor rule](expressions.md#where-a-product-of-two-variables-is-allowed)
  is about how many rows a product builds, and a reported body builds none.

Without this exception you could not write LCOE, which is cost over delivered energy,
because its divisor is a variable.

Comparisons stay out, exactly as they do for an entry in the math. An
`expressions:` body is arithmetic, and `>=` belongs to a constraint.

## Which entries are in the math

An entry is in the math when the objective or a constraint inlines it.

Expansion substitutes every reference before anything reads an expression. So
the question is answered on the expanded tree. An entry that is reached through
another entry, or through a macro call, counts exactly the same as one named in
place.

A bound and a `where` name no entry. A `piecewise:` link may name one, and it
reaches the math through the constraints that its expansion emits. A cased entry
is in the math on the same terms as a plain one.

"Reported" is about what the math reads. It is not about the shape of the body,
and it is not about when the value exists. `delivered` above is affine and
reported, because nothing reads it. A quantity such as `(1 + rate) ** period`
has no variable in it and needs no solve at all, and it is reported all the
same.

Deciding this by use rather than by shape costs one thing: a typo. An entry that
was meant for a constraint, and is never named there, loads as a reported
quantity instead of failing.

A consumer reads the answer off the program, at
`Program.named_expressions[name].in_math`.

On the page, every named expression prints its body once under a **Definitions** heading,
and prints its symbol where it is used. So a reported entry reads no differently
from one in the math. What `in_math` decides on the page is what
[`inline_expressions=`](../typeset.md) may substitute away. An entry that the
math reads is substituted into the equations that read it. A reported entry has
nowhere to be substituted into, so its definition stands either way. The two
cannot disagree, because one function decides both.

## An entry is checked at the limit of whatever reads it

The declaration of an entry is not degree-checked at all. There is nothing to
check it _against_ until something reads it.

Degree is a rule about the position that does the reading. So it fires
unconditionally on the expanded tree of every constraint, of the objective, and
of each piecewise link. Those are the same rules and the same messages that
would refuse a variable divisor, or a degree-3 product, written out by hand.

A constraint that references `lcoe` inlines its body, and hits the divisor rule
at that position:

```text
Constraint 'cap': the divisor contains variables, which is not affine. Divide
by a parameter, or precompute the reciprocal as one.
```

The message names the constraint, and the operation that the inlined body
performs. It does not name the entry `lcoe` that the author wrote, because
expansion has already substituted `lcoe` away by the time the limit is
checked.

If a constraint needs a quantity, move that quantity into an entry whose shape
the math can read. A reported entry is for reading back after a solve, and never
for feeding one.

## Reading a constraint's dual

`dual(c)` is the one built-in that only a reported entry may call. It reads the
**row dual** of the constraint `c`, which is the shadow price that a solve puts
on that constraint, over `c`'s own `foreach` frame.

`c` names a constraint, and only a constraint. It
[resolves against the constraints alone](expressions.md#name-resolution) and
never against the flat namespace. So a variable or parameter that shares the
name is not what `dual` reads.

A dual exists only after a solve, so it may stand only in an entry that the math
never reads. If you write it anywhere the solver ingests, you get a load error
that names the rewrite. Those places are a constraint, the objective, a
piecewise link, and any entry that one of those inlines:

```text
Constraint 'd': a dual exists only after a solve; the math cannot read one —
keep the entry that carries it out of constraints, the objective, bounds and where.
```

The check runs on the expanded tree. So a macro, or an inlined named
expression, cannot smuggle a `dual` into the math.

Where a constraint's `where:` deletes a row, that row has no dual. So `dual(c)`
is absent there too, and that is the same null reading a lookup gets. See
[absence](absence.md#reported-values-follow-the-rows-that-were-built).

A solve does not always return a dual. A model with integer or binary
variables, a quadratic constraint, or a set reformulated into binaries may come
back with no dual for a row that would carry one in a pure linear model. Solvers
also differ, legitimately, on which rows those are.

The language refuses none of these at load, because capability is not the
limit. See
[limits](../../about/limits.md#what-a-solver-can-take-is-a-separate-question), where a set
reformulated into binaries "returns no duals where the native form does".

So `dual(c)` where a solve reports no dual is an absence that the consumer
names. It is the same null. It is not a value that the language
promises is there.

The sign is fixed by the constraint as written, together with the declared
sense. `dual(c)` is the rate at which the optimal objective improves as `c` is
relaxed in the direction its `sense` points, under the model's own `minimize` or
`maximize`.

The orientation that the file wrote is kept exactly: which side is `lhs`, which
side is `rhs`, and which way the `sense` faces. So the sign is a function of two
facts that the file states. A solver that normalises signs in its own way is
reconciling its own representation, not the language's, and two consumers
reading the same model still agree on the sign.

## How a consumer reads a reported entry

A reported entry can be read back, just like an entry in the math. After a
solve, a consumer reads its value back over its own dimensions. Those dimensions
fall out of its body, exactly as any entry's do, so there is no `foreach` and no
`where`.

The difference between the two is _what the math reads_. An entry in the math is
a form that a solver takes, and it is inlined wherever the objective or a
constraint names it. A reported entry is read by nothing in the model.

Where a masked row leaves a solved quantity absent, the reported value is absent
there too. That is the same null reading a lookup gets. See
[absence](absence.md#reported-values-follow-the-rows-that-were-built).

Nothing in this repository evaluates a reported body. Computing the number is a
consumer's business. See
[what counts as language](../../about/what-counts-as-language.md).

The job of the language is to say two things, once and without ambiguity: what
the number _is_, and which entries the math reads.
