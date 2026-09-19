<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# A curve by convex combination

A generator's cost curve, tied to its dispatch through one weight per
breakpoint. This is the floor of the [`piecewise`](../reference/language/piecewise.md)
family: the three pages after it are this same model with the weights
restricted a different way.

Read the math for what the block expands to. The file declares no weight, and
`cost_curve_lam` appears below because the block emits it. One row makes the
weights sum to 1, and one row per link ties that link's expression to the
weighted breakpoints. `method: convex` adds nothing further. A convex curve
under a minimised cost settles on one segment without being held there.

<!-- gallery:begin -->
```yaml
description: >-
  Least-cost dispatch where each generator's cost curve is piecewise-linear in
  its output, expanded into a lambda formulation.

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
      cost read off the generator's curve — convex, so the weights need no
      binaries to keep them on one segment
    along: bp
    links:
      - [dispatch, bp_x]
      - [op_cost, bp_y]
    method: convex

constraints:
  balance:
    dims: [snapshot]
    expression: sum(dispatch, over=generator) == load

objective:
  sense: minimize
  description: total operating cost, taken off the curves rather than from a marginal rate
  expression: sum(op_cost)
```

Least-cost dispatch where each generator's cost curve is piecewise-linear in its output, expanded into a lambda formulation.

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
<!-- gallery:end -->
