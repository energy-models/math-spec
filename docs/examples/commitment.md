<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Unit commitment

This model adds a commitment decision and a start-up ramp to least-cost
dispatch. It is the model that
[`cases:`](../reference/language/expressions.md#cases--one-quantity-a-value-per-region)
exists for. Read `previous_status` first, then `ramp_up`.

The cases carry no order. No two of them can claim one coordinate, and that is
proved at load, before any data binds. `otherwise:` carries every coordinate the
cases leave. So every coordinate has exactly one value, and `ramp_up` uses the
quantity the way it uses a parameter. `ramp_up` prints the quantity's symbol,
and the block itself prints once below, under **Definitions**.

<!-- gallery:begin -->
```yaml
description: >-
  Unit commitment with a start-up ramp, the formulation `cases:` exists for.
  The state a unit carries into a snapshot has three regimes — a unit that is
  never off, the first snapshot, and every later one — and writing them at the
  constraint would fork `ramp_up` three ways. With the regimes named once, the
  inequality is written once.

dimensions:
  snapshot: { dtype: int, description: dispatch periods }
  generator: { description: generating units }

parameters:
  committable: { dims: [generator], dtype: bool, description: whether the unit may be switched off }
  status_initial: { dims: [generator], description: whether the unit was running before the horizon }
  capacity: { dims: [generator], description: installed capacity }
  min_output: { dims: [generator], description: output floor while running }
  ramp_limit: { dims: [generator], description: how far output may move between snapshots while running }
  start_up_limit: { dims: [generator], description: how far it may move in the snapshot it starts in }
  load: { dims: [snapshot], description: demand to be met }
  cost: { dims: [generator], description: marginal cost }

variables:
  dispatch:
    description: output of a generator in a snapshot
    foreach: [snapshot, generator]
    bounds: { lower: 0, upper: capacity }
  status:
    description: whether the unit is running in a snapshot
    foreach: [snapshot, generator]
    domain: binary

expressions:
  previous_status:
    description: the commitment state a unit carries into a snapshot
    foreach: [snapshot, generator]
    cases:
      always_on:
        when: "not committable"
        expression: 1
      boundary:
        when: "committable and position(snapshot) == 0"
        expression: status_initial
    otherwise: shift(status, over=snapshot, offset=1)

constraints:
  power_balance:
    foreach: [snapshot]
    expression: sum(dispatch, over=generator) == load
  upper:
    description: a unit that is not running produces nothing
    foreach: [snapshot, generator]
    expression: dispatch <= status * capacity
  lower:
    description: and one that is running produces at least its floor
    foreach: [snapshot, generator]
    expression: dispatch >= status * min_output
  ramp_up:
    description: >-
      one inequality for both regimes — a unit already running is held to
      `ramp_limit`, a unit starting up to `start_up_limit`.
    foreach: [snapshot, generator]
    expression: >-
      dispatch - shift(dispatch, over=snapshot, offset=1, edge=0)
      <= ramp_limit * previous_status + start_up_limit * (1 - previous_status)

objective:
  sense: minimize
  expression: sum(dispatch * cost)
```

Unit commitment with a start-up ramp, the formulation `cases:` exists for. The state a unit carries into a snapshot has three regimes — a unit that is never off, the first snapshot, and every later one — and writing them at the constraint would fork `ramp_up` three ways. With the regimes named once, the inequality is written once.

#### Sets

| Symbol | Meaning |
|---|---|
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` — dispatch periods |
| $`\mathcal{G}`$ | index $`g`$ — `generator` — generating units |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{committable}`$ | `committable` over $`\mathcal{G}`$ — whether the unit may be switched off |
| $`\mathrm{status}^{\mathrm{initial}}`$ | `status_initial` over $`\mathcal{G}`$ — whether the unit was running before the horizon |
| $`\mathrm{capacity}`$ | `capacity` over $`\mathcal{G}`$ — installed capacity |
| $`\mathrm{min\_output}`$ | `min_output` over $`\mathcal{G}`$ — output floor while running |
| $`\mathrm{ramp\_limit}`$ | `ramp_limit` over $`\mathcal{G}`$ — how far output may move between snapshots while running |
| $`\mathrm{start\_up\_limit}`$ | `start_up_limit` over $`\mathcal{G}`$ — how far it may move in the snapshot it starts in |
| $`\mathrm{load}`$ | `load` over $`\mathcal{T}`$ — demand to be met |
| $`\mathrm{cost}`$ | `cost` over $`\mathcal{G}`$ — marginal cost |

#### Variables

| Symbol | Meaning |
|---|---|
| $`\mathit{dispatch}`$ | `dispatch` over $`\mathcal{T} \times \mathcal{G}`$ — output of a generator in a snapshot |
| $`\mathit{status}`$ | `status` over $`\mathcal{T} \times \mathcal{G}`$ — whether the unit is running in a snapshot |

#### Definitions

| Symbol | Meaning |
|---|---|
| $`\mathit{previous\_status}`$ | `previous_status` over $`\mathcal{T} \times \mathcal{G}`$ — the commitment state a unit carries into a snapshot |

Upright is what the model is given — a parameter such as $`\mathrm{committable}`$, a coordinate map, a label — and italic is what the solver chooses, such as $`\mathit{dispatch}`$. An index is italic too, being what a quantifier chooses, and a set is script.

$`t \boxminus_{v} k`$ denotes translation with $`v`$ standing where index $`t-k`$ leaves the dimension (`shift(edge=v)`), so the row at that boundary is built and carries $`v`$ rather than being dropped.

$`\mathrm{pos}(t)`$ denotes where index $`t`$ sits along its dimension's own order — the order `shift` walks, not the order labels sort in — counted from $`0`$. The index itself stays the coordinate, so $`t`$ compares against labels and $`\mathrm{pos}(t)`$ against positions.

#### Objective

```math
\min \sum_{t \in \mathcal{T},\ g \in \mathcal{G}} \mathit{dispatch}_{t,g} \cdot \mathrm{cost}_{g}
```

#### Subject to

**`power_balance`**

```math
\sum_{g \in \mathcal{G}} \mathit{dispatch}_{t,g} = \mathrm{load}_{t} \qquad \forall\, t \in \mathcal{T}
```

**`upper`**

```math
\mathit{dispatch}_{t,g} \le \mathit{status}_{t,g} \cdot \mathrm{capacity}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

**`lower`**

```math
\mathit{dispatch}_{t,g} \ge \mathit{status}_{t,g} \cdot \mathrm{min\_output}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

**`ramp_up`**

```math
\mathit{dispatch}_{t,g} - \mathit{dispatch}_{t \boxminus_{0} 1,g} \le \mathrm{ramp\_limit}_{g} \cdot \mathit{previous\_status}_{t,g} + \mathrm{start\_up\_limit}_{g} \cdot \left( 1 - \mathit{previous\_status}_{t,g} \right) \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Definitions

**`previous_status`**

```math
\mathit{previous\_status}_{t,g} = \begin{cases} 1 & \text{if } \neg \mathrm{committable}_{g} \\ \mathrm{status}^{\mathrm{initial}}_{g} & \text{if } \mathrm{committable}_{g} \wedge \mathrm{pos}(t) = 0 \\ \mathit{status}_{t - 1,g} & \text{otherwise} \end{cases} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Variable domains

**`dispatch`**

```math
0 \le \mathit{dispatch}_{t,g} \le \mathrm{capacity}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

**`status`**

```math
\mathit{status}_{t,g} \in \{0, 1\} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```
<!-- gallery:end -->

Regenerate with `pixi run python -m tools.gallery`.
