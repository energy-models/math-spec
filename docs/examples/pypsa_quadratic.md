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
> ✔ `pypsa 1.3.0` solves this rung's reference network at objective `12587.437500000098`, 60 rows. `lpspec gaf9a9b913` binds `examples/pypsa_quadratic.yaml` against the same network and lands on the same objective (lpspec's parity gate). Nodal prices agree on 12 rows. **Model-for-model**: the two lanes build one linopy model, label for label.

<details markdown="1">
<summary>What this rung adds, as data</summary>

`data/rung_10_quadratic_costs/buses.csv`

```csv
name
village
```

`data/rung_10_quadratic_costs/generators.csv`

```csv
name,bus,p_nom,marginal_cost,marginal_cost_quadratic
steam,north,80.0,5.0,0.08
engine,north,80.0,20.0,0.01
```

`data/rung_10_quadratic_costs/links.csv`

```csv
name,bus0,bus1,p_nom,p_min_pu,efficiency,marginal_cost,marginal_cost_quadratic
wire2,north,village,40.0,-1.0,0.9,1.0,0.02
```

`data/rung_10_quadratic_costs/loads.csv`

```csv
name,bus,p_set
village_load,village,15.0
extra10,north,
```

`data/rung_10_quadratic_costs/timeseries.csv`

```csv
component,name,attribute,snapshot,value
Load,extra10,p_set,0,30.0
Load,extra10,p_set,1,50.0
Load,extra10,p_set,2,40.0
Load,extra10,p_set,3,60.0
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
| $\mathcal{L}$ | index $l$ — `link` with $\mathrm{Link\_bus0}: \mathcal{L} \to \mathcal{N},\enspace \mathrm{Link\_bus1}: \mathcal{L} \to \mathcal{N}$ — controllable connections, each from one bus to another |
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
| $\eta$ | `Link_efficiency` over $\mathcal{L}$ — share of the flow that arrives at the link's `Link_bus1` end |
| $\mathrm{c}^{f}$ | `Link_marginal_cost` over $\mathcal{T} \times \mathcal{L}$ — cost of one unit of flow |
| $\mathrm{c}^{f,(2)}$ | `Link_marginal_cost_quadratic` over $\mathcal{T} \times \mathcal{L}$ — cost of the square of one unit of flow |
| $\mathrm{load}$ | `Load_p_set` over $\mathcal{T} \times \mathcal{D}$ — demand |

#### Variables

| Symbol | Meaning |
|---|---|
| $p$ | `Generator_p` over $\mathcal{T} \times \mathcal{G}$ — `Generator-p` — output of a generator in a snapshot |
| $f$ | `Link_p` over $\mathcal{T} \times \mathcal{L}$ — `Link-p` — PyPSA's `p0`, the flow measured at the `Link_bus0` end: a positive value withdraws there and injects at `Link_bus1` |

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
    + sum(Link_p * Link_efficiency, by=Link_bus1)
    == sum(Load_p_set, by=Load_bus)
```

$$\sum_{g \in \mathcal{G} \thinspace:\thinspace \mathrm{Generator\_bus}(g) = n} p_{t,g} - \left( \sum_{l \in \mathcal{L} \thinspace:\thinspace \mathrm{Link\_bus0}(l) = n} f_{t,l} \right) + \sum_{l \in \mathcal{L} \thinspace:\thinspace \mathrm{Link\_bus1}(l) = n} f_{t,l} \cdot \eta_{l} = \sum_{d \in \mathcal{D} \thinspace:\thinspace \mathrm{Load\_bus}(d) = n} \mathrm{load}_{t,d} \qquad \forall\thinspace t \in \mathcal{T},\enspace n \in \mathcal{N}$$

#### Variable domains

**`Generator_p`**

$$p_{t,g} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G}$$

**`Link_p`**

$$f_{t,l} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace l \in \mathcal{L}$$
<!-- gallery:end -->

Regenerate with `pixi run python -m tools.gallery`.
