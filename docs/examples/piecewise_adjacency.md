<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# A curve that is not convex

The same dispatch model, with a curve that bends both ways. Nothing about the
objective now keeps the weights on one segment, so the method builds the
restriction out of binaries. `adjacency` is the default, and this is what it
costs.

Compare the math with [the convex page](piecewise.md). A second variable
appears, `cost_curve_seg`, one binary per segment. Two rows come with it:
`cost_curve_pick` picks exactly one segment, and `cost_curve_adjacency` holds
each weight under the segments it borders. The link rows and the convexity row
are unchanged.

<!-- gallery:begin -->
```yaml
description: >-
  The same least-cost dispatch as `piecewise.yaml`, with a cost curve that is
  not convex. The weights need binaries to hold them on one segment, which is
  what the default method builds.

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
      cost read off the generator's curve. The curve bends both ways, so
      nothing but the restriction keeps the weights on one segment: a binary
      per segment picks the one they may sit on
    along: bp
    links:
      - [dispatch, bp_x]
      - [op_cost, bp_y]
    method: adjacency

constraints:
  balance:
    dims: [snapshot]
    expression: sum(dispatch, over=generator) == load

objective:
  sense: minimize
  description: total operating cost, taken off the curves rather than from a marginal rate
  expression: sum(op_cost)
```

The same least-cost dispatch as `piecewise.yaml`, with a cost curve that is not convex. The weights need binaries to hold them on one segment, which is what the default method builds.

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
| $`\mathrm{bp\_x}`$ | `bp_x` over $`\mathcal{G} \times \mathcal{B}`$ — breakpoint dispatch levels, one curve per generator |
| $`\mathrm{bp\_y}`$ | `bp_y` over $`\mathcal{G} \times \mathcal{B}`$ — cost at each breakpoint, one curve per generator |

#### Variables

| Symbol | Meaning |
|---|---|
| $`\mathit{dispatch}`$ | `dispatch` over $`\mathcal{T} \times \mathcal{G}`$ — dispatched power |
| $`\mathit{op\_cost}`$ | `op_cost` over $`\mathcal{T} \times \mathcal{G}`$ — operating cost, piecewise-linear in dispatch |
| $`\mathit{cost\_curve\_lam}`$ | `cost_curve_lam` over $`\mathcal{T} \times \mathcal{G} \times \mathcal{B}`$ — convex-combination weight on a breakpoint |
| $`\mathit{cost\_curve\_seg}`$ | `cost_curve_seg` over $`\mathcal{T} \times \mathcal{G} \times \mathcal{B}`$ |

Upright is what the model is given — a parameter such as $`\mathrm{capacity}`$, a coordinate map, a label — and italic is what the solver chooses, such as $`\mathit{dispatch}`$. An index is italic too, being what a quantifier chooses, and a set is script.

$`t \boxminus_{v} k`$ denotes translation with $`v`$ standing where index $`t-k`$ leaves the dimension (`shift(edge=v)`), so the row at that boundary is built and carries $`v`$ rather than being dropped.

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
\sum_{b \in \mathcal{B}} \mathit{cost\_curve\_lam}_{t,g,b} = 1 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

**`cost_curve_link0`**

```math
\mathit{dispatch}_{t,g} = \sum_{b \in \mathcal{B}} \mathit{cost\_curve\_lam}_{t,g,b} \cdot \mathrm{bp\_x}_{g,b} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

**`cost_curve_link1`**

```math
\mathit{op\_cost}_{t,g} = \sum_{b \in \mathcal{B}} \mathit{cost\_curve\_lam}_{t,g,b} \cdot \mathrm{bp\_y}_{g,b} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

**`cost_curve_pick`**

```math
\sum_{b \in \mathcal{B}} \mathit{cost\_curve\_seg}_{t,g,b} = 1 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

**`cost_curve_adjacency`**

```math
\mathit{cost\_curve\_lam}_{t,g,b} \le \mathit{cost\_curve\_seg}_{t,g,b} + \mathit{cost\_curve\_seg}_{t,g,b \boxminus_{0} 1} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G},\ b \in \mathcal{B}
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
0 \le \mathit{cost\_curve\_lam}_{t,g,b} \le 1 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G},\ b \in \mathcal{B}
```

**`cost_curve_seg`**

```math
\mathit{cost\_curve\_seg}_{t,g,b} \in \{0, 1\} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G},\ b \in \mathcal{B}
```
<!-- gallery:end -->
