<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Reported expressions

A [named expression](expressions.md#named-expressions) is one of two things,
and the file never says which — the objective and the constraints do:

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
inside the program a solver sees, held to the
[degree-2 ceiling](expressions.md#degree-2-in-the-math-degree-1-beside-it)
where it is read. `delivered` and `lcoe` are **reported**: nothing in the
objective or a constraint names them, so no solver sees them — each is a
quantity read back after a solve. `lcoe` could be nothing else, since a
variable divisor is a shape the math refuses; `delivered` could have stood in
the math and simply does not. Nothing about the YAML marks either. Which is
which is decided at load, no data, by expanding the objective and every
constraint and noting each entry they inline.

## What lifts and why

An entry the math reads is substituted before anything consumes the model, so
it stays inside the ceiling the math holds to. A reported entry is read by
**nothing in the model**: it is arithmetic over numbers a solve has already
produced, and the restrictions the math carries because a sink must build it
all lift for a body nothing ingests:

- **No degree cap.** `system_cost / delivered` above divides one variable
  quantity by another. `p * p * p` is sayable. A quotient, a cube, a ratio of
  two sums — each is a number once the solve is done.
- **The divisor may carry variables**, and so may an exponent. `/` and `**`
  drop the variable-free operand they require in the math, because there is no
  degree left for a variable operand to change. Where such a divisor solves to
  zero the quotient is absent there, the null a masked row leaves
  ([absence](absence.md#reported-values-follow-the-rows-that-were-built)).
- **A divisor, a base or an exponent may be a sum.** The math refuses `x / (a +
b)` and `(1 + rate) ** period` even with no variable in sight, because a
  quotient compiles to one reciprocal factor and neither operator distributes
  over `+`. A reported body compiles to nothing, so the precompute an entry in
  the math needs — `(1 + rate) ** period` bound as a parameter — is no longer
  needed.
- **A factor may be a sum of terms with no ceiling on the other.**
  [The one-sum-factor rule](expressions.md#degree-2-in-the-math-degree-1-beside-it)
  is about how many rows a product builds; a reported body builds none.

Without this lift, LCOE — cost over delivered energy — is unsayable, because
its divisor is a variable.

**Comparisons stay out**, exactly as for an entry in the math: an
`expressions:` body is arithmetic, and `>=` belongs to a constraint.

## Which is which

An entry is in the math when the objective or a constraint inlines it.
Expansion substitutes every reference before anything reads an expression, so
the question is answered on the expanded tree, and an entry reached through
another entry or through a macro call counts the same as one named in place. A
bound and a `where` name no entry; a `piecewise:` link may, and reaches the
math through the constraints its expansion emits. A cased entry is in the math
on the same terms as a plain one.

Reported is about what the math reads, not about the body's shape or when its
value exists. `delivered` above is affine and reported, because nothing reads
it. A quantity such as `(1 + rate) ** period`, with no variable in it, needs no
solve at all, and is reported all the same. The one cost of deciding by use
rather than by shape is a typo: an entry meant for a constraint and never
named there loads as a reported quantity instead of failing.

A consumer reads the answer off the program —
`Program.named_expressions[name].in_math` — and
[typeset](../typeset.md) prints every entry that is not under its own name in
a "Reported quantities" section, its body expanded to the leaves — `lcoe`
prints as the quotient of the two sums it names, since an entry the math reads
has no symbol of its own. The two cannot disagree: one function decides both.

## The math reads at its own ceiling

An entry's declaration is not degree-checked at all — there is nothing to
check it _against_ until something reads it. Degree is a rule about the
position doing the reading, so it fires, unconditionally, on the expanded tree
of **every** constraint, the objective and each piecewise link — the same
rules and the same messages that would refuse a variable divisor or a degree-3
product written out by hand. A constraint that references `lcoe` inlines its
body and hits the divisor rule at that position:

```text
Constraint 'cap': the divisor contains variables, which is not affine. Divide
by a parameter, or precompute the reciprocal as one.
```

The message names the constraint and the operation the inlined body performs,
not the entry `lcoe` the author wrote — expansion has already substituted it
away by the time the ceiling is checked. Move the quantity a constraint needs
into an entry whose shape the math can read; a reported one is for reading back
after the solve, never for feeding one.

## Reading a constraint's dual

`dual(c)` is the one builtin only a reported entry may call: it reads the
**row dual** of constraint `c` — the shadow price a solve puts on it — over
`c`'s own `foreach` frame. `c` names a constraint, and only a constraint: it
[resolves against constraints alone](expressions.md#name-resolution), never the
flat namespace, so a variable or parameter sharing the name is not what `dual`
reads.

A dual exists only after a solve, so it may stand only in an entry the math
never reads. Written anywhere the solver ingests — a constraint, the objective,
a piecewise link, or an entry one of those inlines — it is a load error naming
the rewrite:

```text
Constraint 'd': a dual exists only after a solve; the math cannot read one —
keep the entry that carries it out of constraints, the objective, bounds and where.
```

The check runs on the **expanded** tree, so a macro or an inlined named
expression cannot smuggle a `dual` into the math.

Where a constraint's `where:` deletes a row, that row has no dual, so `dual(c)`
is absent there too — the null reading a lookup gets
([absence](absence.md#reported-values-follow-the-rows-that-were-built)).

**A solve does not always return one.** A model with integer or binary
variables, a quadratic constraint, or a set reformulated into binaries may come
back with no dual for a row that carries one in a pure linear model — and
solvers legitimately differ on which. The language refuses none of these at
load: capability is not the ceiling
([ceiling](../../about/ceiling.md#capability-is-not-the-ceiling)), where a set
reformulated into binaries "returns no duals where the native form does". So
`dual(c)` where a solve reports none is a **documented absence a consumer
names**, the same null — not a value the language promises is there.

**The sign is fixed by the constraint as written and the declared sense.**
`dual(c)` is the rate the optimal objective improves as `c` is relaxed in the
direction its `sense` points, under the model's own `minimize` or `maximize`.
The orientation the file wrote — which side is `lhs`, which is `rhs`, which way
the `sense` faces — is kept verbatim, so the sign is a function of two facts the
file states. A solver that normalises signs its own way is reconciling its
representation, not the language's; two consumers reading the same model still
agree on the sign.

## What a consumer does with it

A reported entry is **observable**, like one in the math: after a solve, a
consumer reads its value back over its own dims, which fall out of its body
exactly as any entry's do — no `foreach`, no `where`. The difference is _what
the math reads_: an entry in the math is a form a sink ingests, inlined
wherever the objective or a constraint names it; a reported entry is read by
nothing in the model. Where a masked row leaves a solved quantity absent, the
reported value is absent there too — the null reading a lookup gets
([absence](absence.md#reported-values-follow-the-rows-that-were-built)).

Nothing in this repository evaluates a reported body; computing the number is
a consumer's business
([what counts as language](../../about/what-counts-as-language.md)). The
language's job is to say, once and unambiguously, what the number _is_, and
which entries the math reads.
