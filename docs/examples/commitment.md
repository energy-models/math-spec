<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Unit commitment

A dispatch model with a commitment decision and a start-up ramp — the
formulation [`cases:`](../reference/language/expressions.md#cases--one-quantity-a-value-per-region)
exists for.

Read `previous_status` and then `ramp_up`. The cases are read **in order**, and
the last one carries no `when:` — so the first arm whose condition holds is the
value, and the fallback covers every coordinate the others leave. One value at
every coordinate — never two, never none — is what lets `ramp_up` use the
quantity the way it uses a parameter.

It prints the way a paper writes it: `ramp_up` names the quantity, and the
block itself prints once below, under **Definitions**.

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
  generator: { values: [nuclear, gas, oil], description: generating units }

parameters:
  committable: { dims: [generator], dtype: bool, description: whether the unit may be switched off }
  status_initial: { dims: [generator], description: whether the unit was running before the horizon }
  p_max: { dims: [generator], description: installed capacity }
  p_min: { dims: [generator], description: output floor while running }
  ramp_limit: { dims: [generator], description: how far output may move between snapshots while running }
  start_up_limit: { dims: [generator], description: how far it may move in the snapshot it starts in }
  load: { dims: [snapshot], description: demand to be met }
  cost: { dims: [generator], description: marginal cost }

variables:
  p:
    description: output of a generator in a snapshot
    foreach: [snapshot, generator]
    bounds: { lower: 0, upper: p_max }
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
        when: "position(snapshot) == 0"
        expression: status_initial
      interior:
        expression: shift(status, over=snapshot, offset=1)

constraints:
  power_balance:
    foreach: [snapshot]
    expression: sum(p, over=generator) == load
  upper:
    description: a unit that is not running produces nothing
    foreach: [snapshot, generator]
    expression: p <= status * p_max
  lower:
    description: and one that is running produces at least its floor
    foreach: [snapshot, generator]
    expression: p >= status * p_min
  ramp_up:
    description: >-
      one inequality for both regimes — a unit already running is held to
      `ramp_limit`, a unit starting up to `start_up_limit`.
    foreach: [snapshot, generator]
    expression: >-
      p - shift(p, over=snapshot, offset=1, edge=0)
      <= ramp_limit * previous_status + start_up_limit * (1 - previous_status)

objective:
  sense: minimize
  expression: sum(p * cost)
```

Unit commitment with a start-up ramp, the formulation `cases:` exists for. The state a unit carries into a snapshot has three regimes — a unit that is never off, the first snapshot, and every later one — and writing them at the constraint would fork `ramp_up` three ways. With the regimes named once, the inequality is written once.

#### Sets

| Symbol | Meaning |
|---|---|
| $\mathcal{T}$ | index $t$ — `snapshot` — dispatch periods |
| $\mathcal{G}$ | index $g$ — `generator` — generating units |

#### Parameters

| Symbol | Meaning |
|---|---|
| $\mathrm{committable}$ | `committable` over $\mathcal{G}$ — whether the unit may be switched off |
| $\mathrm{status}^{\mathrm{initial}}$ | `status_initial` over $\mathcal{G}$ — whether the unit was running before the horizon |
| $\mathrm{p}^{\mathrm{max}}$ | `p_max` over $\mathcal{G}$ — installed capacity |
| $\mathrm{p}^{\mathrm{min}}$ | `p_min` over $\mathcal{G}$ — output floor while running |
| $\mathrm{ramp\_limit}$ | `ramp_limit` over $\mathcal{G}$ — how far output may move between snapshots while running |
| $\mathrm{start\_up\_limit}$ | `start_up_limit` over $\mathcal{G}$ — how far it may move in the snapshot it starts in |
| $\mathrm{load}$ | `load` over $\mathcal{T}$ — demand to be met |
| $\mathrm{cost}$ | `cost` over $\mathcal{G}$ — marginal cost |

#### Variables

| Symbol | Meaning |
|---|---|
| $p$ | `p` over $\mathcal{T} \times \mathcal{G}$ — output of a generator in a snapshot |
| $\mathit{status}$ | `status` over $\mathcal{T} \times \mathcal{G}$ — whether the unit is running in a snapshot |

Upright is what the model is given — a parameter such as $\mathrm{committable}$, a coordinate map, a label — and italic is what the solver chooses, such as $p$. An index is italic too, being what a quantifier chooses, and a set is script.

$t \boxminus_{v} k$ denotes translation with $v$ standing where index $t-k$ leaves the dimension (`shift(edge=v)`), so the row at that boundary is built and carries $v$ rather than being dropped.

$\mathrm{pos}(t)$ denotes where index $t$ sits along its dimension's own order — the order `shift` walks, not the order labels sort in — counted from $0$. The index itself stays the coordinate, so $t$ compares against labels and $\mathrm{pos}(t)$ against positions.

#### Objective

$$\min \sum_{t \in \mathcal{T},\enspace g \in \mathcal{G}} p_{t,g} \cdot \mathrm{cost}_{g}$$

#### Subject to

**`power_balance`**

$$\sum_{g \in \mathcal{G}} p_{t,g} = \mathrm{load}_{t} \qquad \forall\thinspace t \in \mathcal{T}$$

**`upper`**

$$p_{t,g} \le \mathit{status}_{t,g} \cdot \mathrm{p}^{\mathrm{max}}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G}$$

**`lower`**

$$p_{t,g} \ge \mathit{status}_{t,g} \cdot \mathrm{p}^{\mathrm{min}}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G}$$

**`ramp_up`**

$$p_{t,g} - p_{t \boxminus_{0} 1,g} \le \mathrm{ramp\_limit}_{g} \cdot \mathit{previous\_status}_{t,g} + \mathrm{start\_up\_limit}_{g} \cdot \left( 1 - \mathit{previous\_status}_{t,g} \right) \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G}$$

#### Definitions

**`previous_status`**

$$\mathit{previous\_status}_{t,g} = \begin{cases} 1 & \text{if } \neg \mathrm{committable}_{g} \cr \mathrm{status}^{\mathrm{initial}}_{g} & \text{if } \mathrm{pos}(t) = 0 \cr \mathit{status}_{t - 1,g} & \text{otherwise} \end{cases} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G}$$

#### Variable domains

**`p`**

$$0 \le p_{t,g} \le \mathrm{p}^{\mathrm{max}}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G}$$

**`status`**

$$\mathit{status}_{t,g} \in \{0, 1\} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G}$$
<!-- gallery:end -->

Regenerate with `pixi run python -m tools.gallery`.
