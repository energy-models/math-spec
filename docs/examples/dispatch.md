<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Least-cost dispatch

The smallest file that is a whole model: generators with a capacity, an hourly
load to meet, and a cost to minimise. It is the model on the
[home page](../index.md) and in the README, and the one the language reference
varies when it needs a base to change one thing in.

Two things worth reading for. The `where:` on `p` deletes the rows where a
generator has no capacity — [absence](../reference/language/absence.md) is a
declaration, not a runtime check. And `sum(p, over=generator)` names the
dimension it reduces, so the constraint's frame is what remains.

<!-- gallery:begin -->
```yaml
description: Least-cost dispatch of a generator fleet against an hourly load.

dimensions:
  snapshot: { dtype: int, description: dispatch periods }
  generator: { values: [wind, solar, gas], description: generating units }

parameters:
  p_max: { dims: [generator], description: installed capacity }
  load: { dims: [snapshot], description: demand to be met }
  cost: { dims: [generator], description: marginal cost }

variables:
  p:
    description: output of a generator in a snapshot
    foreach: [snapshot, generator]
    where: "p_max > 0"
    bounds: { lower: 0, upper: p_max }

constraints:
  power_balance:
    foreach: [snapshot]
    expression: sum(p, over=generator) == load

objective:
  sense: minimize
  expression: sum(p * cost)
```

Least-cost dispatch of a generator fleet against an hourly load.

#### Sets

| Symbol | Meaning |
|---|---|
| $\mathcal{T}$ | index $t$ — `snapshot` — dispatch periods |
| $\mathcal{G}$ | index $g$ — `generator` — generating units |

#### Parameters

| Symbol | Meaning |
|---|---|
| $\mathrm{p}^{\mathrm{max}}$ | `p_max` over $\mathcal{G}$ — installed capacity |
| $\mathrm{load}$ | `load` over $\mathcal{T}$ — demand to be met |
| $\mathrm{cost}$ | `cost` over $\mathcal{G}$ — marginal cost |

#### Variables

| Symbol | Meaning |
|---|---|
| $p$ | `p` over $\mathcal{T} \times \mathcal{G}$ — output of a generator in a snapshot |

Upright is what the model is given — a parameter such as $\mathrm{p}^{\mathrm{max}}$, a coordinate map, a label — and italic is what the solver chooses, such as $p$. An index is italic too, being what a quantifier chooses, and a set is script.

#### Objective

$$\min \sum_{t \in \mathcal{T},\enspace g \in \mathcal{G}} p_{t,g} \cdot \mathrm{cost}_{g}$$

#### Subject to

**`power_balance`**

$$\sum_{g \in \mathcal{G}} p_{t,g} = \mathrm{load}_{t} \qquad \forall\thinspace t \in \mathcal{T}$$

#### Variable domains

**`p`**

$$0 \le p_{t,g} \le \mathrm{p}^{\mathrm{max}}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{p}^{\mathrm{max}}_{g} > 0$$
<!-- gallery:end -->

Regenerate with `pixi run python -m tools.gallery`.
