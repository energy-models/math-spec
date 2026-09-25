<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Assumptions

`assumptions:` states what the model expects of the data attached to it. The
language types each predicate and prints it in the
[typeset document](../typeset.md). The consumer that attaches the numbers runs it.

```yaml
dimensions:
  generator: { dtype: str }
parameters:
  p_min: { dims: [generator] }
  p_max: { dims: [generator] }
variables:
  p:
    dims: [generator]
    bounds: { lower: p_min, upper: p_max }
constraints:
  cap:
    dims: [generator]
    expression: p <= p_max
objective:
  sense: minimize
  expression: sum(p, over=generator)
assumptions:
  bounds_do_not_cross: "p_min <= p_max"
```

$$\mathrm{p}^{\mathrm{min}}_{g} \le \mathrm{p}^{\mathrm{max}}_{g} \qquad \forall\thinspace g \in \mathcal{G}$$

## The entry

An entry is one where string, or a mapping once it carries more than the
predicate.

| Field         |                                                                               |                |
| ------------- | ----------------------------------------------------------------------------- | -------------- |
| `holds`       | required. The predicate, in the [where grammar](expressions.md#where-strings) |                |
| `where`       | which coordinates it is checked at, in the same grammar                       | default `null` |
| `description` | why the rule is there. A refusal quotes it                                    | default `null` |

`bounds_do_not_cross: "p_min <= p_max"` above is the short form of
`bounds_do_not_cross: { holds: "p_min <= p_max" }`.

There is no `dims:`. The predicate holds at every coordinate of the product of
the dimensions its two masks name. A predicate narrower than that broadcasts,
as it does in any `where`.

## What a predicate may say

Everything the [where grammar](expressions.md#where-strings) admits, which
includes arithmetic on either side:

```yaml
dimensions:
  snapshot: { dtype: int }
  generator: { dtype: str }
parameters:
  eta: { dims: [generator] }
  p_max: { dims: [generator] }
  peak: { dims: [] }
  load: { dims: [snapshot] }
  ramp_limit: { dims: [] }
variables:
  p:
    dims: [snapshot, generator]
    bounds: { lower: 0, upper: p_max }
constraints:
  meet_load:
    dims: [snapshot]
    expression: sum(p, over=generator) == load
objective:
  sense: minimize
  expression: sum(p)
assumptions:
  efficiency_is_a_fraction: "eta > 0 AND eta <= 1"
  peak_is_reachable: "sum(p_max, over=generator) >= peak"
  ramps_are_gentle:
    holds: "load - shift(load, along=snapshot, offset=1, edge=0) <= ramp_limit"
    where: "position(snapshot) > 0"
    description: the first snapshot has no predecessor to ramp from
```

A parameter supplied only where it applies takes a `where:`, so the rows it has
no value at are not checked.

## What the loader refuses

**A predicate the connectives already decide:**

> `Assumption 'sound'`: the predicate `'c > 0 OR true'` folds to true, so it
> assumes nothing of the data. Delete it, or name a parameter it constrains.

A `where:` the connectives decide is refused the same way: one that folds to
true narrows nothing, and one that folds to false checks the entry on no row.

**A variable:**

> `Assumption 'sound'`: variable `'p'` stands in what the assumption assumes,
> and an assumption is about the data — a variable is what the solver decides
> from it. Name a parameter, or state the rule as a constraint.

A constraint whose sides carry no variable is refused, and its message names
this section.

## What a curve assumes

A [`piecewise:`](piecewise.md) block `curve` adds its own assumptions, derived
from its `method:`, its `points:` and the sign on its links. They print under
the same _Assumptions_ heading as the written ones.

| Entry               | Added for         | Holds                                                                                                 |
| ------------------- | ----------------- | ----------------------------------------------------------------------------------------------------- |
| `curve_complete`    | every block       | every values parameter has a row at every breakpoint the curve runs through                           |
| `curve_increasing`  | `convex`, `lp`    | the pinned link's breakpoints (the first link's, when both are pinned) strictly increase along `over` |
| `curve_curvature`   | `convex`, `lp`    | with a `>=` link the curve is convex, with `<=` concave; with both links pinned it bends one way only |
| `curve_breakpoints` | `lp`              | each curve has at least two breakpoints                                                               |
| `curve_contiguous`  | a block `points:` | the marked breakpoints are one consecutive run of at least one                                        |

[Reading a spec and its program](../reading.md#what-the-data-has-to-satisfy) says how
a consumer runs them.
