<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# PyPSA, the quadratic class

Rung 10 of [PyPSA in one file](pypsa.md): PyPSA's `marginal_cost_quadratic`,
stated on rung 1's transport surface in a file of its own — the model's
description below says why. Its reference network starts from the same shared
spine, `data/base/`, shown once on [the rung ladder's page](pypsa.md#index).

## Rung 10 — quadratic costs

| PyPSA                                   | status | note                                                                       |
| --------------------------------------- | ------ | -------------------------------------------------------------------------- |
| [`marginal_cost_quadratic`](#objective) | done   | degree 2 in the objective; Generator and Link here — PyPSA also carries it on storage units and stores, one more term each of the same shape |

<!-- reference:rung_10_quadratic_costs:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `12587.437500000098`, 60 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_10_quadratic_costs.py`

```python
"""Rung 10: quadratic costs — a marginal cost quadratic in output, stated by `pypsa_quadratic.yaml`."""

from __future__ import annotations

import spine

#: This rung binds a file of its own.
MODEL = 'pypsa_quadratic.yaml'


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', 'village')
    n.add('Generator', 'steam', bus='north', p_nom=80, marginal_cost=5, marginal_cost_quadratic=0.08)
    n.add('Generator', 'engine', bus='north', p_nom=80, marginal_cost=20, marginal_cost_quadratic=0.01)
    n.add(
        'Link',
        'wire2',
        bus0='north',
        bus1='village',
        p_nom=40,
        p_min_pu=-1,
        efficiency=0.9,
        marginal_cost=1,
        marginal_cost_quadratic=0.02,
    )
    n.add('Load', 'village_load', bus='village', p_set=15)
    n.add('Load', 'extra10', bus='north', p_set=[30, 50, 40, 60])
    return n
```

</details>
<!-- reference:rung_10_quadratic_costs:end -->

## The file

<!-- gallery:begin -->
The quadratic class of a plain `n.optimize()`: PyPSA's `marginal_cost_quadratic`, stated on rung 1's transport surface in a file of its own. One model cannot carry a quadratic objective beside commitment's integer variables and keep a HiGHS lane — degree is the model's property, not the data's — so the class a free solver takes as a QP lives here, and `examples/pypsa.yaml` stays the mixed-integer one. PyPSA also carries the attribute on storage units and stores; each is one more term of the same shape.

#### Sets

| Symbol | Meaning |
|---|---|
| $\mathcal{T}$ | index $t$ — `snapshot` — dispatch periods |
| $\mathcal{N}$ | index $n$ — `bus` — network nodes |
| $\mathcal{G}$ | index $g$ — `generator` with $\mathrm{Generator\_bus}: \mathcal{G} \to \mathcal{N}$ — generating units, each on one bus |
| $\mathcal{L}$ | index $l$ — `link` with $\mathrm{Link\_bus0}: \mathcal{L} \to \mathcal{N}$ — controllable connections, each from one bus to the buses it delivers to |
| $\mathcal{O}$ | index $o$ — `link_output` with $\mathrm{Link\_output\_link}: \mathcal{O} \to \mathcal{L},\enspace \mathrm{Link\_output\_bus}: \mathcal{O} \to \mathcal{N}$ — a link's output ports, one label per port a link declares — PyPSA's `bus1`, `bus2`, … columns read long, so a link of any number of output ports is one term in the balance, data prep |
| $\mathcal{D}$ | index $d$ — `load` with $\mathrm{Load\_bus}: \mathcal{D} \to \mathcal{N}$ — demands, each on one bus |

#### Parameters

| Symbol | Meaning |
|---|---|
| $\mathrm{w}$ | `snapshot_weightings_objective` over $\mathcal{T}$ — PyPSA's `snapshot_weightings.objective` — hours a snapshot stands for in the cost |
| $\mathrm{p}^{\mathrm{nom}}$ | `Generator_p_nom` over $\mathcal{G}$ — nominal power |
| $\underline{\mathrm{p}}$ | `Generator_p_min_pu` over $\mathcal{T} \times \mathcal{G}$ — least output, per unit of nominal power |
| $\overline{\mathrm{p}}$ | `Generator_p_max_pu` over $\mathcal{T} \times \mathcal{G}$ — most output, per unit of nominal power — an availability profile |
| $\mathrm{c}$ | `Generator_marginal_cost` over $\mathcal{T} \times \mathcal{G}$ — cost of one unit of output |
| $\mathrm{c}^{(2)}$ | `Generator_marginal_cost_quadratic` over $\mathcal{T} \times \mathcal{G}$ — cost of the square of one unit of output |
| $\mathrm{f}^{\mathrm{nom}}$ | `Link_p_nom` over $\mathcal{L}$ — nominal power |
| $\underline{\mathrm{f}}$ | `Link_p_min_pu` over $\mathcal{T} \times \mathcal{L}$ — least flow, per unit of nominal power — negative for a link that carries both ways |
| $\overline{\mathrm{f}}$ | `Link_p_max_pu` over $\mathcal{T} \times \mathcal{L}$ — most flow, per unit of nominal power |
| $\eta$ | `Link_efficiency` over $\mathcal{O}$ — share of the flow that arrives at an output port, PyPSA's `efficiency`, `efficiency2`, … read long — negative where that port consumes rather than delivers |
| $\mathrm{c}^{f}$ | `Link_marginal_cost` over $\mathcal{T} \times \mathcal{L}$ — cost of one unit of flow |
| $\mathrm{c}^{f,(2)}$ | `Link_marginal_cost_quadratic` over $\mathcal{T} \times \mathcal{L}$ — cost of the square of one unit of flow |
| $\mathrm{load}$ | `Load_p_set` over $\mathcal{T} \times \mathcal{D}$ — demand |

#### Variables

| Symbol | Meaning |
|---|---|
| $p$ | `Generator_p` over $\mathcal{T} \times \mathcal{G}$ — `Generator-p` — output of a generator in a snapshot |
| $f$ | `Link_p` over $\mathcal{T} \times \mathcal{L}$ — `Link-p` — PyPSA's `p0`, the flow measured at the `Link_bus0` end: a positive value withdraws there and injects at every bus the link's output ports deliver to |

### Objective

```yaml
objective:
  sense: minimize
  description: operating cost, linear and quadratic, each snapshot weighted by the hours it stands for
  expression: >-
    sum(Generator_p * Generator_marginal_cost * snapshot_weightings_objective)
    + sum(Generator_p * Generator_p * Generator_marginal_cost_quadratic * snapshot_weightings_objective)
    + sum(Link_p * Link_marginal_cost * snapshot_weightings_objective)
    + sum(Link_p * Link_p * Link_marginal_cost_quadratic * snapshot_weightings_objective)
```

$$\min \sum_{t \in \mathcal{T},\enspace g \in \mathcal{G}} p_{t,g} \cdot \mathrm{c}_{t,g} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\enspace g \in \mathcal{G}} p_{t,g} \cdot p_{t,g} \cdot \mathrm{c}^{(2)}_{t,g} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\enspace l \in \mathcal{L}} f_{t,l} \cdot \mathrm{c}^{f}_{t,l} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\enspace l \in \mathcal{L}} f_{t,l} \cdot f_{t,l} \cdot \mathrm{c}^{f,(2)}_{t,l} \cdot \mathrm{w}_{t}$$

### `Generator-fix-p-lower`

`Generator_fix_p_lower`

```yaml
Generator_fix_p_lower:
  description: "`Generator-fix-p-lower` — a generator outputs at least its minimum"
  foreach: [snapshot, generator]
  expression: Generator_p >= Generator_p_min_pu * Generator_p_nom
```

$$p_{t,g} \ge \underline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G}$$

### `Generator-fix-p-upper`

`Generator_fix_p_upper`

```yaml
Generator_fix_p_upper:
  description: "`Generator-fix-p-upper` — a generator outputs at most what is available"
  foreach: [snapshot, generator]
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom
```

$$p_{t,g} \le \overline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G}$$

### `Link-fix-p-lower`

`Link_fix_p_lower`

```yaml
Link_fix_p_lower:
  description: "`Link-fix-p-lower` — a link carries at least its minimum, negative for the other way"
  foreach: [snapshot, link]
  expression: Link_p >= Link_p_min_pu * Link_p_nom
```

$$f_{t,l} \ge \underline{\mathrm{f}}_{t,l} \cdot \mathrm{f}^{\mathrm{nom}}_{l} \qquad \forall\thinspace t \in \mathcal{T},\enspace l \in \mathcal{L}$$

### `Link-fix-p-upper`

`Link_fix_p_upper`

```yaml
Link_fix_p_upper:
  description: "`Link-fix-p-upper` — a link carries at most its nominal power"
  foreach: [snapshot, link]
  expression: Link_p <= Link_p_max_pu * Link_p_nom
```

$$f_{t,l} \le \overline{\mathrm{f}}_{t,l} \cdot \mathrm{f}^{\mathrm{nom}}_{l} \qquad \forall\thinspace t \in \mathcal{T},\enspace l \in \mathcal{L}$$

### `Bus-nodal_balance`

`Bus_nodal_balance`

```yaml
Bus_nodal_balance:
  description: >-
    `Bus-nodal_balance` — what is generated at a bus, less what the links
    take away, plus what arrives over them after losses, meets the load
    there
  foreach: [snapshot, bus]
  expression: >-
    sum(Generator_p, by=Generator_bus)
    - sum(Link_p, by=Link_bus0)
    + sum(at(Link_p, by=Link_output_link) * Link_efficiency, by=Link_output_bus)
    == sum(Load_p_set, by=Load_bus)
```

$$\sum_{g \in \mathcal{G} \thinspace:\thinspace \mathrm{Generator\_bus}(g) = n} p_{t,g} - \left( \sum_{l \in \mathcal{L} \thinspace:\thinspace \mathrm{Link\_bus0}(l) = n} f_{t,l} \right) + \sum_{o \in \mathcal{O} \thinspace:\thinspace \mathrm{Link\_output\_bus}(o) = n} f_{t,\mathrm{Link\_output\_link}(o)} \cdot \eta_{o} = \sum_{d \in \mathcal{D} \thinspace:\thinspace \mathrm{Load\_bus}(d) = n} \mathrm{load}_{t,d} \qquad \forall\thinspace t \in \mathcal{T},\enspace n \in \mathcal{N}$$

#### Variable domains

**`Generator_p`**

$$p_{t,g} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G}$$

**`Link_p`**

$$f_{t,l} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace l \in \mathcal{L}$$
<!-- gallery:end -->

Regenerate with `pixi run python -m tools.gallery`.
