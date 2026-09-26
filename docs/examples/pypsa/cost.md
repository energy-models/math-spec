<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# The cost

One of the [24 fragments](index.md) of `examples/pypsa.yaml`: the objective: the expected operating cost and its tail, weighted by scenario. It reads `CVaR_omega`, `scenario_opex`, `scenario_weight` under [`given`](../../reference/language/declarations.md#given).

<!-- gallery:begin -->
```yaml
dimensions:
  scenario:
    description: the futures dispatch is chosen in, each with a weight

parameters:
  CVaR_inv_tail:
    description: PyPSA's `1 / (1 - alpha)` — the tail's own probability, inverted in data prep because a divisor is one factor
    dims: []

variables:
  CVaR_a:
    description: "`CVaR-a` — how far a scenario's operating cost exceeds the tail's start; nothing where it does not"
    dims: [scenario]
    bounds:
      lower: 0
  CVaR_theta:
    description: "`CVaR-theta` — where the tail starts, the value at risk"
    dims: []
  CVaR:
    description: "`CVaR` — the tail's average cost, what the objective prices at `omega`"
    dims: []

given:
  parameters:
    scenario_weight: { dims: [scenario] }
    CVaR_omega: { dims: [] }
  expressions:
    scenario_opex: { dims: [scenario] }

constraints:
  CVaR_excess:
    description: "`CVaR-excess-{s}` — a scenario's operating cost beyond the tail's start is its excess; PyPSA names one row per scenario"
    dims: [scenario]
    where: CVaR_omega > 0
    expression: CVaR_a - scenario_opex + CVaR_theta >= 0
  CVaR_def:
    description: "`CVaR-def` — the tail's average is at least where it starts plus the expected excess over the tail's probability"
    dims: []
    where: CVaR_omega > 0
    expression: CVaR_theta + CVaR_inv_tail * sum(scenario_weight * CVaR_a, over=scenario) <= CVaR

objective:
  sense: minimize
  description: >-
    capacity once per active period at its expected cost over the scenarios, operation in expectation over the scenarios, and a share of it at the tail
  expression: >-
    (1 - CVaR_omega) * sum(scenario_weight * scenario_opex, over=scenario)
    + CVaR_omega * CVaR
```

#### Sets

| Symbol | Meaning |
|---|---|
| $`\Xi`$ | index $`\xi`$ — `scenario` — the futures dispatch is chosen in, each with a weight |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{v}`$ | `CVaR_inv_tail` (scalar) — PyPSA's `1 / (1 - alpha)` — the tail's own probability, inverted in data prep because a divisor is one factor |

#### Variables

| Symbol | Meaning |
|---|---|
| $`a`$ | `CVaR_a` over $`\Xi`$ — `CVaR-a` — how far a scenario's operating cost exceeds the tail's start; nothing where it does not |
| $`\theta`$ | `CVaR_theta` (scalar) — `CVaR-theta` — where the tail starts, the value at risk |
| $`CVaR`$ | `CVaR` (scalar) — `CVaR` — the tail's average cost, what the objective prices at `omega` |

#### Given

| Symbol | Meaning |
|---|---|
| $`\pi`$ | `scenario_weight` over $`\Xi`$, data another file declares |
| $`\omega`$ | `CVaR_omega` (scalar), data another file declares |
| $`\mathit{scenario\_opex}`$ | `scenario_opex` over $`\Xi`$, an expression another file defines |

#### Objective

```math
\min \left( 1 - \omega \right) \cdot \left( \sum_{\xi \in \Xi} \pi_{\xi} \cdot \mathit{scenario\_opex}_{\xi} \right) + \omega \cdot CVaR
```

#### Subject to

**`CVaR_excess`**

```math
a_{\xi} - \mathit{scenario\_opex}_{\xi} + \theta \ge 0 \qquad \forall\, \xi \in \Xi \,:\, \omega > 0
```

**`CVaR_def`**

```math
\theta + \mathrm{v} \cdot \left( \sum_{\xi \in \Xi} \pi_{\xi} \cdot a_{\xi} \right) \le CVaR \qquad \text{where } \omega > 0
```

#### Variable domains

**`CVaR_a`**

```math
a_{\xi} \ge 0 \qquad \forall\, \xi \in \Xi
```

**`CVaR_theta`**

```math
\theta \in \mathbb{R}
```

**`CVaR`**

```math
CVaR \in \mathbb{R}
```
<!-- gallery:end -->
