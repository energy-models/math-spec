<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# PyPSA, the two-stage class

Rung 14 of [PyPSA in one file](pypsa.md): a network with scenarios and a risk
preference, `n.set_scenarios(...)` and `n.set_risk_preference(alpha, omega)`,
stated on rungs 1 and 3 in a file of its own — the model's description below
says why. Its reference network is the shared spine, `data/base/`, plus the
folder below; `rung.json` there names the scenarios, their weights and the
risk preference, and `timeseries.csv` carries a `scenario` column.

## Rung 14 — two-stage stochastic, with CVaR

| PyPSA                                                | status | note                                                       |
| ---------------------------------------------------- | ------ | ---------------------------------------------------------- |
| [`Generator-p`, `Link-p`](#variable-domains)         | done   | over `scenario`; `Generator-p_nom` is not — chosen once    |
| [`Generator-fix-p-*`, `-ext-p-*`, `Link-fix-p-*`, `Bus-nodal_balance`](#generator-fix-p-lower) | done | rungs 1 and 3, over `scenario` |
| [`CVaR-a`, `CVaR-theta`, `CVaR`](#variable-domains)  | done   |                                                            |
| [`CVaR-excess-{s}`](#cvar-excess-s)                  | split  | PyPSA names a row per scenario; one block over the dimension |
| [`CVaR-def`](#cvar-def)                              | done   | `1 / (1 - alpha)` is data prep                             |
| objective                                            | done   | capacity once; operation `(1 - omega)` in expectation, `omega` at the tail |

<!-- reference:rung_14_stochastic:begin -->
> ✔ `pypsa 1.3.0` solves this rung's reference network at objective `9267.386666666665`, 87 rows. `lpspec ga6a817698` binds `examples/pypsa_stochastic.yaml` against the same network and lands on the same objective (lpspec's parity gate). Nodal prices agree on 16 rows.

<details markdown="1">
<summary>What this rung adds, as data</summary>

`data/rung_14_stochastic/generators.csv`

```csv
name,bus,p_nom,p_nom_extendable,p_nom_max,marginal_cost,capital_cost
wind14,south,0.0,True,100.0,1.0,20.0
```

`data/rung_14_stochastic/loads.csv`

```csv
name,bus
port14,south
```

`data/rung_14_stochastic/timeseries.csv`

```csv
component,name,attribute,snapshot,value,scenario
Load,port14,p_set,0,10,calm
Load,port14,p_set,1,20,calm
Load,port14,p_set,2,15,calm
Load,port14,p_set,3,10,calm
Generator,wind14,p_max_pu,0,0.9,calm
Generator,wind14,p_max_pu,1,0.7,calm
Generator,wind14,p_max_pu,2,0.8,calm
Generator,wind14,p_max_pu,3,0.6,calm
Load,port14,p_set,0,40,stormy
Load,port14,p_set,1,60,stormy
Load,port14,p_set,2,50,stormy
Load,port14,p_set,3,30,stormy
Generator,wind14,p_max_pu,0,0.3,stormy
Generator,wind14,p_max_pu,1,0.2,stormy
Generator,wind14,p_max_pu,2,0.4,stormy
Generator,wind14,p_max_pu,3,0.1,stormy
```

</details>
<!-- reference:rung_14_stochastic:end -->

## The file

<!-- gallery:begin -->
The two-stage class of a plain `n.optimize()`: a network with scenarios, stated on rung 1's transport and rung 3's expansion in a file of its own. Everything over a snapshot spans a scenario as well; capacity does not — it is chosen once, before the future is known — and the cost is the expectation over the scenarios' weights. With a risk preference PyPSA adds the CVaR rows: an excess per scenario and the tail's average, blended into the objective. A dimension a run may not have cannot ride on `examples/pypsa.yaml`, so this class lives here.

#### Sets

| Symbol | Meaning |
|---|---|
| $\mathcal{S}$ | index $s$ — `scenario` — the futures dispatch is chosen in, each with a weight |
| $\mathcal{T}$ | index $t$ — `snapshot` — dispatch periods |
| $\mathcal{N}$ | index $n$ — `bus` — network nodes |
| $\mathcal{G}$ | index $g$ — `generator` with $\mathrm{Generator\_bus}: \mathcal{G} \to \mathcal{N}$ — generating units, each on one bus |
| $\mathcal{L}$ | index $l$ — `link` with $\mathrm{Link\_bus0}: \mathcal{L} \to \mathcal{N},\enspace \mathrm{Link\_bus1}: \mathcal{L} \to \mathcal{N}$ — controllable connections, each from one bus to another |
| $\mathcal{D}$ | index $d$ — `load` with $\mathrm{Load\_bus}: \mathcal{D} \to \mathcal{N}$ — demands, each on one bus |

#### Parameters

| Symbol | Meaning |
|---|---|
| $\pi$ | `scenario_weight` over $\mathcal{S}$ — PyPSA's `scenario_weightings.weight` — the probability of a future |
| $\omega$ | `CVaR_omega` (scalar) — PyPSA's `risk_preference['omega']` — the share of the operating cost priced at the tail rather than in expectation |
| $\mathrm{v}$ | `CVaR_inv_tail` (scalar) — PyPSA's `1 / (1 - alpha)` — the tail's own probability, inverted in data prep because a divisor is one factor |
| $\mathrm{w}$ | `snapshot_weightings_objective` over $\mathcal{T}$ — PyPSA's `snapshot_weightings.objective` — hours a snapshot stands for in the cost |
| $\mathrm{p}^{\mathrm{nom}}$ | `Generator_p_nom` over $\mathcal{G}$ — nominal power |
| $\mathrm{ext}$ | `Generator_p_nom_extendable` over $\mathcal{G}$ — whether the nominal power is a decision |
| $\underline{\mathrm{p}}^{\mathrm{nom}}$ | `Generator_p_nom_min` over $\mathcal{G}$ — least nominal power an extendable generator may be built at |
| $\overline{\mathrm{p}}^{\mathrm{nom}}$ | `Generator_p_nom_max` over $\mathcal{G}$ — most nominal power an extendable generator may be built at |
| $\mathrm{c}^{\mathrm{cap}}$ | `Generator_capital_cost` over $\mathcal{G}$ — cost of one unit of nominal power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $\underline{\mathrm{p}}$ | `Generator_p_min_pu` over $\mathcal{T} \times \mathcal{G}$ — least output, per unit of nominal power |
| $\overline{\mathrm{p}}$ | `Generator_p_max_pu` over $\mathcal{S} \times \mathcal{T} \times \mathcal{G}$ — most output, per unit of nominal power — an availability profile |
| $\mathrm{c}$ | `Generator_marginal_cost` over $\mathcal{T} \times \mathcal{G}$ — cost of one unit of output |
| $\mathrm{f}^{\mathrm{nom}}$ | `Link_p_nom` over $\mathcal{L}$ — nominal power |
| $\underline{\mathrm{f}}$ | `Link_p_min_pu` over $\mathcal{T} \times \mathcal{L}$ — least flow, per unit of nominal power — negative for a link that carries both ways |
| $\overline{\mathrm{f}}$ | `Link_p_max_pu` over $\mathcal{T} \times \mathcal{L}$ — most flow, per unit of nominal power |
| $\eta$ | `Link_efficiency` over $\mathcal{L}$ — share of the flow that arrives at the link's `Link_bus1` end |
| $\mathrm{c}^{f}$ | `Link_marginal_cost` over $\mathcal{T} \times \mathcal{L}$ — cost of one unit of flow |
| $\mathrm{load}$ | `Load_p_set` over $\mathcal{S} \times \mathcal{T} \times \mathcal{D}$ — demand |

#### Variables

| Symbol | Meaning |
|---|---|
| $p$ | `Generator_p` over $\mathcal{S} \times \mathcal{T} \times \mathcal{G}$ — `Generator-p` — output of a generator in a snapshot |
| $f$ | `Link_p` over $\mathcal{S} \times \mathcal{T} \times \mathcal{L}$ — `Link-p` — PyPSA's `p0`, the flow measured at the `Link_bus0` end: a positive value withdraws there and injects at `Link_bus1` |
| $P$ | `Generator_p_nom_ext` over $\mathcal{G}$ — `Generator-p_nom` — nominal power where it is a decision; the parameter of the same PyPSA name carries the fixed regime |
| $a$ | `CVaR_a` over $\mathcal{S}$ — `CVaR-a` — how far a scenario's operating cost exceeds the tail's start; nothing where it does not |
| $\theta$ | `CVaR_theta` (scalar) — `CVaR-theta` — where the tail starts, the value at risk |
| $CVaR$ | `CVaR` (scalar) — `CVaR` — the tail's average cost, what the objective prices at `omega` |

### Objective

```yaml
objective:
  sense: minimize
  description: capacity once, operation in expectation, and a share of it at the tail
  expression: >-
    sum(Generator_p_nom_ext * Generator_capital_cost)
    + (1 - CVaR_omega) * sum(scenario_weight * scenario_opex, over=scenario)
    + CVaR_omega * CVaR
```

$$\min \sum_{g \in \mathcal{G}} P_{g} \cdot \mathrm{c}^{\mathrm{cap}}_{g} + \left( 1 - \omega \right) \cdot \left( \sum_{s \in \mathcal{S}} \pi_{s} \cdot \left( \sum_{t \in \mathcal{T}} \sum_{g \in \mathcal{G}} p_{s,t,g} \cdot \mathrm{c}_{t,g} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T}} \sum_{l \in \mathcal{L}} f_{s,t,l} \cdot \mathrm{c}^{f}_{t,l} \cdot \mathrm{w}_{t} \right) \right) + \omega \cdot CVaR$$

### `Generator-fix-p-lower`

`Generator_fix_p_lower`

```yaml
Generator_fix_p_lower:
  description: "`Generator-fix-p-lower` — a generator outputs at least its minimum"
  foreach: [scenario, snapshot, generator]
  where: not Generator_p_nom_extendable
  expression: Generator_p >= Generator_p_min_pu * Generator_p_nom
```

$$p_{s,t,g} \ge \underline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \qquad \forall\thinspace s \in \mathcal{S},\enspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \neg \mathrm{ext}_{g}$$

### `Generator-fix-p-upper`

`Generator_fix_p_upper`

```yaml
Generator_fix_p_upper:
  description: "`Generator-fix-p-upper` — a generator outputs at most what is available"
  foreach: [scenario, snapshot, generator]
  where: not Generator_p_nom_extendable
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom
```

$$p_{s,t,g} \le \overline{\mathrm{p}}_{s,t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \qquad \forall\thinspace s \in \mathcal{S},\enspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \neg \mathrm{ext}_{g}$$

### `Generator-ext-p-lower`

`Generator_ext_p_lower`

```yaml
Generator_ext_p_lower:
  description: "`Generator-ext-p-lower` — an extendable generator outputs at least its minimum of the chosen build"
  foreach: [scenario, snapshot, generator]
  where: Generator_p_nom_extendable
  expression: Generator_p >= Generator_p_min_pu * Generator_p_nom_ext
```

$$p_{s,t,g} \ge \underline{\mathrm{p}}_{t,g} \cdot P_{g} \qquad \forall\thinspace s \in \mathcal{S},\enspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{ext}_{g}$$

### `Generator-ext-p-upper`

`Generator_ext_p_upper`

```yaml
Generator_ext_p_upper:
  description: "`Generator-ext-p-upper` — an extendable generator outputs at most what is available of the chosen build"
  foreach: [scenario, snapshot, generator]
  where: Generator_p_nom_extendable
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom_ext
```

$$p_{s,t,g} \le \overline{\mathrm{p}}_{s,t,g} \cdot P_{g} \qquad \forall\thinspace s \in \mathcal{S},\enspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{ext}_{g}$$

### `Generator-ext-p_nom-lower`

`Generator_ext_p_nom_lower`

```yaml
Generator_ext_p_nom_lower:
  description: "`Generator-ext-p_nom-lower` — the chosen build is at least its floor"
  foreach: [generator]
  where: Generator_p_nom_extendable
  expression: Generator_p_nom_ext >= Generator_p_nom_min
```

$$P_{g} \ge \underline{\mathrm{p}}^{\mathrm{nom}}_{g} \qquad \forall\thinspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{ext}_{g}$$

### `Generator-ext-p_nom-upper`

`Generator_ext_p_nom_upper`

```yaml
Generator_ext_p_nom_upper:
  description: "`Generator-ext-p_nom-upper` — the chosen build is at most its cap; a cap of infinity is no row"
  foreach: [generator]
  where: Generator_p_nom_extendable AND Generator_p_nom_max
  expression: Generator_p_nom_ext <= Generator_p_nom_max
```

$$P_{g} \le \overline{\mathrm{p}}^{\mathrm{nom}}_{g} \qquad \forall\thinspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{ext}_{g} \wedge \overline{\mathrm{p}}^{\mathrm{nom}}_{g} \text{ is defined}$$

### `Link-fix-p-lower`

`Link_fix_p_lower`

```yaml
Link_fix_p_lower:
  description: "`Link-fix-p-lower` — a link carries at least its minimum, negative for the other way"
  foreach: [scenario, snapshot, link]
  expression: Link_p >= Link_p_min_pu * Link_p_nom
```

$$f_{s,t,l} \ge \underline{\mathrm{f}}_{t,l} \cdot \mathrm{f}^{\mathrm{nom}}_{l} \qquad \forall\thinspace s \in \mathcal{S},\enspace t \in \mathcal{T},\enspace l \in \mathcal{L}$$

### `Link-fix-p-upper`

`Link_fix_p_upper`

```yaml
Link_fix_p_upper:
  description: "`Link-fix-p-upper` — a link carries at most its nominal power"
  foreach: [scenario, snapshot, link]
  expression: Link_p <= Link_p_max_pu * Link_p_nom
```

$$f_{s,t,l} \le \overline{\mathrm{f}}_{t,l} \cdot \mathrm{f}^{\mathrm{nom}}_{l} \qquad \forall\thinspace s \in \mathcal{S},\enspace t \in \mathcal{T},\enspace l \in \mathcal{L}$$

### `Bus-nodal_balance`

`Bus_nodal_balance`

```yaml
Bus_nodal_balance:
  description: >-
    `Bus-nodal_balance` — what is generated at a bus, less what the links
    take away, plus what arrives over them after losses, meets the load
    there
  foreach: [scenario, snapshot, bus]
  expression: >-
    sum(Generator_p, by=Generator_bus)
    - sum(Link_p, by=Link_bus0)
    + sum(Link_p * Link_efficiency, by=Link_bus1)
    == sum(Load_p_set, by=Load_bus)
```

$$\sum_{g \in \mathcal{G} \thinspace:\thinspace \mathrm{Generator\_bus}(g) = n} p_{s,t,g} - \left( \sum_{l \in \mathcal{L} \thinspace:\thinspace \mathrm{Link\_bus0}(l) = n} f_{s,t,l} \right) + \sum_{l \in \mathcal{L} \thinspace:\thinspace \mathrm{Link\_bus1}(l) = n} f_{s,t,l} \cdot \eta_{l} = \sum_{d \in \mathcal{D} \thinspace:\thinspace \mathrm{Load\_bus}(d) = n} \mathrm{load}_{s,t,d} \qquad \forall\thinspace s \in \mathcal{S},\enspace t \in \mathcal{T},\enspace n \in \mathcal{N}$$

### `CVaR-excess-{s}`

`CVaR_excess`

```yaml
CVaR_excess:
  description: "`CVaR-excess-{s}` — a scenario's operating cost beyond the tail's start is its excess; PyPSA names one row per scenario"
  foreach: [scenario]
  expression: CVaR_a - scenario_opex + CVaR_theta >= 0
```

$$a_{s} - \left( \sum_{t \in \mathcal{T}} \sum_{g \in \mathcal{G}} p_{s,t,g} \cdot \mathrm{c}_{t,g} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T}} \sum_{l \in \mathcal{L}} f_{s,t,l} \cdot \mathrm{c}^{f}_{t,l} \cdot \mathrm{w}_{t} \right) + \theta \ge 0 \qquad \forall\thinspace s \in \mathcal{S}$$

### `CVaR-def`

`CVaR_def`

```yaml
CVaR_def:
  description: "`CVaR-def` — the tail's average is at least where it starts plus the expected excess over the tail's probability"
  foreach: []
  expression: CVaR_theta + CVaR_inv_tail * sum(scenario_weight * CVaR_a, over=scenario) <= CVaR
```

$$\theta + \mathrm{v} \cdot \left( \sum_{s \in \mathcal{S}} \pi_{s} \cdot a_{s} \right) \le CVaR$$

#### Variable domains

**`Generator_p`**

$$p_{s,t,g} \in \mathbb{R} \qquad \forall\thinspace s \in \mathcal{S},\enspace t \in \mathcal{T},\enspace g \in \mathcal{G}$$

**`Link_p`**

$$f_{s,t,l} \in \mathbb{R} \qquad \forall\thinspace s \in \mathcal{S},\enspace t \in \mathcal{T},\enspace l \in \mathcal{L}$$

**`Generator_p_nom_ext`**

$$P_{g} \in \mathbb{R} \qquad \forall\thinspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{ext}_{g}$$

**`CVaR_a`**

$$a_{s} \ge 0 \qquad \forall\thinspace s \in \mathcal{S}$$

**`CVaR_theta`**

$$\theta \in \mathbb{R}$$

**`CVaR`**

$$CVaR \in \mathbb{R}$$
<!-- gallery:end -->

Regenerate with `pixi run python -m tools.gallery`.
