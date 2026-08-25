<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# PyPSA in one file

The model a plain `n.optimize()` builds, stated as one file and grown a rung
at a time towards
[milestone 1](https://github.com/energy-models/math-spec/milestone/1). This is
rung 1, transport: generator dispatch, controllable links, a nodal balance and
a linear cost.

The page is the file a declaration at a time. Each constraint is headed by the
name PyPSA's own linopy model gives that row — `Generator-fix-p-upper`,
`Bus-nodal_balance` — then the YAML that states it here, then the equation the
typesetter prints from that YAML. Nothing on this page is typed: a constraint
that stops loading, or starts printing different math, fails CI.

Three decisions shape the file, and they are visible in every block:

- **Bounds are rows.** PyPSA writes a generator's limits as explicit
  constraints, `Generator-fix-p-lower` and `-upper`, and reads `mu_lower` and
  `mu_upper` off them. So does this file — a `bounds:` on the variable would
  fold them onto the column, and the dual would have nowhere to come from.
- **Regimes are data.** Whether a generator is extendable is a column,
  `Generator_p_nom_extendable`, and the fixed-capacity rows carry
  `where: not Generator_p_nom_extendable`. The extendable rows join the file on
  a later rung under the complementary mask; the file never forks.
- **Names are PyPSA's.** Every declaration is `Component_attribute` after the
  statement it stands for, so the file reads beside `n.model` — and a symbol
  table, `examples/pypsa.symbols.yaml`, is what makes the math read as math.

## Rungs

One file, grown in this order; each rung keeps the rows above it green. A row
links to its block below once it is in the file.

| rung                  | adds                                                        | rows                                                                                                                                                                                   |
| --------------------- | ----------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1 transport           | generator dispatch, controllable links, nodal balance, cost | [`Generator-fix-p-lower`](#generator-fix-p-lower) · [`Generator-fix-p-upper`](#generator-fix-p-upper) · [`Link-fix-p-lower`](#link-fix-p-lower) · [`Link-fix-p-upper`](#link-fix-p-upper) · [`Bus-nodal_balance`](#bus-nodal_balance) |
| 2 storage             | stores carrying energy between snapshots, cyclic and not    | next                                                                                                                                                                                   |
| 3 expansion           | nominal power as a decision                                 |                                                                                                                                                                                        |
| 4 ramps               | limits on how far output moves between snapshots            |                                                                                                                                                                                        |
| 5 global constraints  | emission and expansion budgets                              |                                                                                                                                                                                        |
| 6 KVL                 | flows around cycles of lines with reactance                 |                                                                                                                                                                                        |
| 7 commitment          | binary status, minimum up and down times — a MILP           |                                                                                                                                                                                        |
| 8 modular and big-M   | integer module counts; committable and extendable at once   |                                                                                                                                                                                        |
| 9 multi-link and delay | links with more than two ports; flow that arrives later     |                                                                                                                                                                                        |

<!-- gallery:begin -->
The model a plain `n.optimize()` builds, stated in one file. Every declaration is named `Component_attribute` after the PyPSA statement it stands for, and each constraint's description opens with the linopy name PyPSA gives that row, so the two can be read side by side. PyPSA's regimes — extendable, committable — are data columns and become `where:` masks. Rung 1, transport: generator dispatch, controllable links, a nodal balance, a linear cost. Bounds are the explicit rows PyPSA writes, so their duals are row duals.

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
| $\mathrm{ext}$ | `Generator_p_nom_extendable` over $\mathcal{G}$ — whether the nominal power is a decision; false on this rung |
| $\underline{\mathrm{p}}$ | `Generator_p_min_pu` over $\mathcal{T} \times \mathcal{G}$ — least output, per unit of nominal power |
| $\overline{\mathrm{p}}$ | `Generator_p_max_pu` over $\mathcal{T} \times \mathcal{G}$ — most output, per unit of nominal power — an availability profile |
| $\mathrm{c}$ | `Generator_marginal_cost` over $\mathcal{T} \times \mathcal{G}$ — cost of one unit of output |
| $\mathrm{f}^{\mathrm{nom}}$ | `Link_p_nom` over $\mathcal{L}$ — nominal power |
| $\mathrm{ext}^{f}$ | `Link_p_nom_extendable` over $\mathcal{L}$ — whether the nominal power is a decision; false on this rung |
| $\underline{\mathrm{f}}$ | `Link_p_min_pu` over $\mathcal{T} \times \mathcal{L}$ — least flow, per unit of nominal power — negative for a link that carries both ways |
| $\overline{\mathrm{f}}$ | `Link_p_max_pu` over $\mathcal{T} \times \mathcal{L}$ — most flow, per unit of nominal power |
| $\eta$ | `Link_efficiency` over $\mathcal{L}$ — share of the flow that arrives at the link's `Link_bus1` end |
| $\mathrm{c}^{f}$ | `Link_marginal_cost` over $\mathcal{T} \times \mathcal{L}$ — cost of one unit of flow |
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
  description: operating cost, each snapshot weighted by the hours it stands for
  expression: >-
    sum(Generator_p * Generator_marginal_cost * snapshot_weightings_objective)
    + sum(Link_p * Link_marginal_cost * snapshot_weightings_objective)
```

$$\min \sum_{t \in \mathcal{T},\enspace g \in \mathcal{G}} p_{t,g} \cdot \mathrm{c}_{t,g} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\enspace l \in \mathcal{L}} f_{t,l} \cdot \mathrm{c}^{f}_{t,l} \cdot \mathrm{w}_{t}$$

### `Generator-fix-p-lower`

`Generator_fix_p_lower`

```yaml
Generator_fix_p_lower:
  description: "`Generator-fix-p-lower` — a fixed generator outputs at least its minimum"
  foreach: [snapshot, generator]
  where: not Generator_p_nom_extendable
  expression: Generator_p >= Generator_p_min_pu * Generator_p_nom
```

$$p_{t,g} \ge \underline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \neg \mathrm{ext}_{g}$$

### `Generator-fix-p-upper`

`Generator_fix_p_upper`

```yaml
Generator_fix_p_upper:
  description: "`Generator-fix-p-upper` — a fixed generator outputs at most what is available"
  foreach: [snapshot, generator]
  where: not Generator_p_nom_extendable
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom
```

$$p_{t,g} \le \overline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \neg \mathrm{ext}_{g}$$

### `Link-fix-p-lower`

`Link_fix_p_lower`

```yaml
Link_fix_p_lower:
  description: "`Link-fix-p-lower` — a fixed link carries at least its minimum, negative for the other way"
  foreach: [snapshot, link]
  where: not Link_p_nom_extendable
  expression: Link_p >= Link_p_min_pu * Link_p_nom
```

$$f_{t,l} \ge \underline{\mathrm{f}}_{t,l} \cdot \mathrm{f}^{\mathrm{nom}}_{l} \qquad \forall\thinspace t \in \mathcal{T},\enspace l \in \mathcal{L} \thinspace:\thinspace \neg \mathrm{ext}^{f}_{l}$$

### `Link-fix-p-upper`

`Link_fix_p_upper`

```yaml
Link_fix_p_upper:
  description: "`Link-fix-p-upper` — a fixed link carries at most its nominal power"
  foreach: [snapshot, link]
  where: not Link_p_nom_extendable
  expression: Link_p <= Link_p_max_pu * Link_p_nom
```

$$f_{t,l} \le \overline{\mathrm{f}}_{t,l} \cdot \mathrm{f}^{\mathrm{nom}}_{l} \qquad \forall\thinspace t \in \mathcal{T},\enspace l \in \mathcal{L} \thinspace:\thinspace \neg \mathrm{ext}^{f}_{l}$$

### `Bus-nodal_balance`

`Bus_nodal_balance`

```yaml
Bus_nodal_balance:
  description: >-
    `Bus-nodal_balance` — what is generated at a bus, less what the links
    take away, plus what arrives over them after losses, meets the load
    there. A bus nothing is attached to has no row; PyPSA refuses one that
    carries load, and this file does not yet.
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
