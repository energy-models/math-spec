<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Post-solve expressions

A [named expression](expressions.md#named-expressions) can be one of two
things, and the file never says which — the entry's own body decides:

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
```

`system_cost` and `delivered` are **math-grade**: each is an affine sum, so
either can stand in the objective or a constraint, substituted before anything
consumes the model. `lcoe` divides one by the other — a variable divisor — so
it is **post-solve grade**: arithmetic over numbers a solve has already
produced, not a term any solver sees. Nothing about the YAML marks it; the
grade is read off the expanded body against the same degree rules a
constraint holds to (`ceiling=1`), and decided at load, no data.

## What lifts and why

A math-grade entry is read affinely: the objective, a constraint or a bound may
reference one, substituted before anything consumes the model, so it stays
inside the [degree-2 ceiling](expressions.md#degree-2-in-the-math-degree-1-beside-it)
the math holds to. A post-solve-grade entry breaks one of those rules —
that is the whole test — because **nothing in the model reads it**: it is
arithmetic over numbers a solve has already produced, and the restrictions the
math carries because a sink must build it all lift for a body nothing ingests:

- **No degree cap.** `system_cost / delivered` above divides one variable
  quantity by another. `p * p * p` is sayable. A quotient, a cube, a ratio of
  two sums — each is a number once the solve is done.
- **The divisor may carry variables**, and so may an exponent. `/` and `**`
  drop the variable-free operand they require in the math, because there is no
  degree left for a variable operand to change. Where such a divisor solves to
  zero the quotient is absent there, the null a masked row leaves
  ([absence](absence.md#post-solve-values-follow-the-rows-that-were-built)).
- **A divisor, a base or an exponent may be a sum.** The math refuses `x / (a +
b)` and `(1 + rate) ** period` even with no variable in sight, because a
  quotient compiles to one reciprocal factor and neither operator distributes
  over `+`. A post-solve-grade body compiles to nothing, so the precompute a
  math-grade entry needs — `(1 + rate) ** period` bound as a parameter — is no
  longer needed.
- **A factor may be a sum of terms with no ceiling on the other.**
  [The one-sum-factor rule](expressions.md#degree-2-in-the-math-degree-1-beside-it)
  is about how many rows a product builds; a post-solve-grade body builds none.

Without this lift, LCOE — cost over delivered energy — is unsayable, because
its divisor is a variable.

**Comparisons stay out**, exactly as for a math-grade entry: an
`expressions:` body is arithmetic, and `>=` belongs to a constraint.

## How the grade is decided

The grade is asked of the entry's **resolved, expanded** body: every
reference it makes — to a variable, a parameter, another named expression, a
macro call — is inlined first, so the question is body-local and answered once,
at load, with no data. An entry is post-solve grade when its expanded body
fails `check_expression` at the ceiling a bound or a `where` is held to
(`ceiling=1`); otherwise it is math grade. Because expansion runs first, a
macro cannot smuggle a post-solve-grade shape past the check by hiding it
behind a call.

## The math never reads one — checked where the math reads

An entry's declaration is not degree-checked at all — there is nothing to
check it _against_ until something reads it. Degree is a rule about the
position doing the reading, so it fires again, unconditionally, on the
expanded tree of **every** constraint, the objective, each bound, `where`
string and piecewise link — the same rules and the same messages that would
refuse a variable divisor or a degree-3 product written out by hand. A
constraint that references `lcoe` inlines its post-solve-grade body and hits
the divisor rule at that position:

```text
Constraint 'cap': the divisor contains variables, which is not affine. Divide
by a parameter, or precompute the reciprocal as one.
```

The message names the constraint and the operation the inlined body performs,
not the entry `lcoe` the author wrote — expansion has already substituted it
away by the time the ceiling is checked. Move the quantity a constraint needs
into a math-grade entry instead; a post-solve-grade one is for reading back
after the solve, never for feeding one.

## What a consumer does with it

A post-solve-grade entry is **observable**, like a math-grade one: after a
solve, a consumer reads its value back over its own dims, which fall out of
its body exactly as a math-grade entry's do — no `foreach`, no `where`. The
difference is _what the math may read_: a math-grade entry is a linear form a
sink ingests, so the objective, a constraint or a bound can name it; a
post-solve-grade entry is a shape the math cannot read that way, so nothing in
the model does. That is about the shape, not about when the value exists: `(1 + rate) ** period`, with no variable in it, is a number before any solve and post-solve grade all the same, because `**` over a sum is not a form the math reads. Where a masked row leaves a solved quantity absent, the post-solve value is absent there too — the null reading a lookup gets ([absence](absence.md#post-solve-values-follow-the-rows-that-were-built)).

Nothing in this repository evaluates a post-solve-grade body; computing the
number is a consumer's business
([what counts as language](../../about/what-counts-as-language.md)). The
language's job is to say, once and unambiguously, what the number _is_ — and
[typeset](../typeset.md) prints it that way too, as `lcoe = system_cost /
delivered`, whatever names it inlines from.
