<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# A curve as segment lines

The same curve again, stated as the lines its segments lie on rather than as
breakpoints to interpolate between. The `>=` on the second link says which side
of the lines the cost sits on.

This is the one method that declares no auxiliary variable. No weights appear in
the math below, so nothing has to be restricted and the model stays a linear
program. `cost_curve_chord` is one inequality per segment, and the two domain
rows hold dispatch between the curve's ends. The form reads correctly only where
the curvature matches the sign. Lines that envelope a convex curve would cut a
concave one, and the solve comes back optimal either way.

<!-- gallery:begin -->
```yaml
description: >-
  The same least-cost dispatch as `piecewise.yaml`, with each generator's cost
  curve stated as the lines its segments lie on rather than interpolated
  between its breakpoints. The curve is convex and the objective pushes the
  cost down, so a cost above every segment line settles on the curve — which
  needs no interpolation weights, and so declares no auxiliary variable at all.

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
    description: operating cost, held above every segment of the generator's curve
    dims: [snapshot, generator]
    bounds:
      lower: 0

piecewise:
  cost_curve:
    description: >-
      cost bounded below by the curve — the `>=` is what says which side of the
      lines the cost sits on, and the curvature has to match it: lines that
      envelope a convex curve would cut a concave one, and the solve comes back
      optimal either way
    along: bp
    links:
      - [dispatch, bp_x]
      - [op_cost, bp_y, ">="]
    method: lp

constraints:
  balance:
    dims: [snapshot]
    expression: sum(dispatch, over=generator) == load

objective:
  sense: minimize
  description: total operating cost, taken off the curves rather than from a marginal rate
  expression: sum(op_cost)
```

The same least-cost dispatch as `piecewise.yaml`, with each generator's cost curve stated as the lines its segments lie on rather than interpolated between its breakpoints. The curve is convex and the objective pushes the cost down, so a cost above every segment line settles on the curve — which needs no interpolation weights, and so declares no auxiliary variable at all.

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
| $`\mathit{op\_cost}`$ | `op_cost` over $`\mathcal{T} \times \mathcal{G}`$ — operating cost, held above every segment of the generator's curve |

Upright is what the model is given — a parameter such as $`\mathrm{capacity}`$, a coordinate map, a label — and italic is what the solver chooses, such as $`\mathit{dispatch}`$. An index is italic too, being what a quantifier chooses, and a set is script.

$`t \boxminus_{v} k`$ denotes translation with $`v`$ standing where index $`t-k`$ leaves the dimension (`shift(edge=v)`), so the row at that boundary is built and carries $`v`$ rather than being dropped.

$`\mathrm{pos}(t)`$ denotes where index $`t`$ sits along its dimension's own order — the order `shift` steps along, not the order labels sort in — counted from $`0`$. The index itself stays the coordinate, so $`t`$ compares against labels and $`\mathrm{pos}(t)`$ against positions.

$`\lvert \mathcal{T} \rvert`$ denotes the size of the set being counted along, and a position counted from the end prints against it — $`\lvert \mathcal{T} \rvert - 1`$ is the last position, one less than the size because the first is $`0`$.

#### Objective

```math
\min \sum_{t \in \mathcal{T},\ g \in \mathcal{G}} \mathit{op\_cost}_{t,g}
```

#### Subject to

**`balance`**

```math
\sum_{g \in \mathcal{G}} \mathit{dispatch}_{t,g} = \mathrm{load}_{t} \qquad \forall\, t \in \mathcal{T}
```

**`cost_curve_chord`**

```math
\mathit{op\_cost}_{t,g} \cdot \left( \mathrm{bp\_x}_{g,b} - \mathrm{bp\_x}_{g,b \boxminus_{0} 1} \right) \ge \left( \mathrm{bp\_y}_{g,b} - \mathrm{bp\_y}_{g,b \boxminus_{0} 1} \right) \cdot \left( \mathit{dispatch}_{t,g} - \mathrm{bp\_x}_{g,b} \right) + \mathrm{bp\_y}_{g,b} \cdot \left( \mathrm{bp\_x}_{g,b} - \mathrm{bp\_x}_{g,b \boxminus_{0} 1} \right) \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G},\ b \in \mathcal{B} \,:\, \mathrm{pos}(b) \neq 0
```

**`cost_curve_domain_lo`**

```math
\mathit{dispatch}_{t,g} \ge \mathrm{bp\_x}_{g,b} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G},\ b \in \mathcal{B} \,:\, \mathrm{pos}(b) = 0
```

**`cost_curve_domain_hi`**

```math
\mathit{dispatch}_{t,g} \le \mathrm{bp\_x}_{g,b} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G},\ b \in \mathcal{B} \,:\, \mathrm{pos}(b) = \lvert \mathcal{B} \rvert - 1
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
<!-- gallery:end -->
