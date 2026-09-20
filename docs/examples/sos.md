<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# A curve as a special-ordered set

The same restriction as [the adjacency page](piecewise_adjacency.md), handed to
the solver instead of built. `method: sos2` says that at most two weights may
be non-zero and they must be neighbours, which is the definition of a type-2
set.

Read the two pages together. The binaries are gone here, and so are the two
rows that constrained them. What replaces them is a declaration rather than a
row, because a special-ordered set is something a solver enforces directly.
Whether a given solver does is that solver's business, not the file's.

<!-- gallery:begin -->
```yaml
description: >-
  A piecewise-linear cost curve stated as a special-ordered set, so the solver
  is handed the adjacency restriction rather than binaries that encode it.

dimensions:
  snapshot:
    description: dispatch periods
    dtype: int
  generator:
    description: dispatchable units
    dtype: str
  bp:
    description: breakpoints of the cost curve
    dtype: int

parameters:
  capacity:
    description: maximum dispatch
    dims: [generator]
  load:
    description: demand to be met
    dims: [snapshot]
  bp_x:
    description: breakpoint dispatch levels, one curve per generator
    dims: [generator, bp]
  bp_y:
    description: cost at each breakpoint, one curve per generator
    dims: [generator, bp]

variables:
  dispatch:
    description: dispatched power
    dims: [snapshot, generator]
    bounds:
      lower: 0
      upper: capacity
  op_cost:
    description: operating cost, piecewise-linear in dispatch
    dims: [snapshot, generator]
    bounds:
      lower: 0

piecewise:
  cost_curve:
    description: >-
      cost read off the generator's curve, with at most two adjacent weights
      non-zero — the restriction the default method builds out of binaries,
      declared as a set instead
    along: bp
    links:
      - [dispatch, bp_x]
      - [op_cost, bp_y]
    method: sos2

constraints:
  balance:
    dims: [snapshot]
    expression: sum(dispatch, over=generator) == load

objective:
  sense: minimize
  description: total operating cost, taken off the curves rather than from a marginal rate
  expression: sum(op_cost)
```

A piecewise-linear cost curve stated as a special-ordered set, so the solver is handed the adjacency restriction rather than binaries that encode it.

#### Sets

| Symbol | Meaning |
|---|---|
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` — dispatch periods |
| $`\mathcal{G}`$ | index $`g`$ — `generator` — dispatchable units |
| $`\mathcal{B}`$ | index $`b`$ — `bp` — breakpoints of the cost curve |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{capacity}`$ | `capacity` over $`\mathcal{G}`$ — maximum dispatch |
| $`\mathrm{load}`$ | `load` over $`\mathcal{T}`$ — demand to be met |
| $`\mathrm{x}`$ | `bp_x` over $`\mathcal{G} \times \mathcal{B}`$ — breakpoint dispatch levels, one curve per generator |
| $`\mathrm{y}`$ | `bp_y` over $`\mathcal{G} \times \mathcal{B}`$ — cost at each breakpoint, one curve per generator |

#### Variables

| Symbol | Meaning |
|---|---|
| $`\mathit{dispatch}`$ | `dispatch` over $`\mathcal{T} \times \mathcal{G}`$ — dispatched power |
| $`\mathit{op\_cost}`$ | `op_cost` over $`\mathcal{T} \times \mathcal{G}`$ — operating cost, piecewise-linear in dispatch |
| $`\lambda`$ | `cost_curve_lam` over $`\mathcal{T} \times \mathcal{G} \times \mathcal{B}`$ — convex-combination weight on a breakpoint |

Upright is what the model is given — a parameter such as $`\mathrm{capacity}`$, a coordinate map, a label — and italic is what the solver chooses, such as $`\mathit{dispatch}`$. An index is italic too, being what a quantifier chooses, and a set is script.

#### Objective

```math
\min \sum_{t \in \mathcal{T},\ g \in \mathcal{G}} \mathit{op\_cost}_{t,g}
```

#### Subject to

**`balance`**

```math
\sum_{g \in \mathcal{G}} \mathit{dispatch}_{t,g} = \mathrm{load}_{t} \qquad \forall\, t \in \mathcal{T}
```

**`cost_curve_convexity`**

```math
\sum_{b \in \mathcal{B}} \lambda_{t,g,b} = 1 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

**`cost_curve_link0`**

```math
\mathit{dispatch}_{t,g} = \sum_{b \in \mathcal{B}} \lambda_{t,g,b} \cdot \mathrm{x}_{g,b} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

**`cost_curve_link1`**

```math
\mathit{op\_cost}_{t,g} = \sum_{b \in \mathcal{B}} \lambda_{t,g,b} \cdot \mathrm{y}_{g,b} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Variable domains

**`dispatch`**

```math
0 \le \mathit{dispatch}_{t,g} \le \mathrm{capacity}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

**`op_cost`**

```math
\mathit{op\_cost}_{t,g} \ge 0 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

**`cost_curve_lam`**

```math
0 \le \lambda_{t,g,b} \le 1 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G},\ b \in \mathcal{B}
```

**`cost_curve_lam sos`**

```math
\left( \lambda_{t,g,b} \right)_{b \in \mathcal{B}} \in \mathrm{SOS}2 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```
<!-- gallery:end -->
