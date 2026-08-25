<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# PyPSA in one file

The model a plain `n.optimize()` builds, stated as one file and grown a rung
at a time towards
[milestone 1](https://github.com/energy-models/math-spec/milestone/1). The
index below lists every row PyPSA emits (PyPSA `0d7d683`,
`pypsa/optimization/`) and links each to its block in the file once it is
there. The blocks are the file — PyPSA's name for the row, the YAML, the
equation the typesetter prints — and are generated, so a row that stops
loading or changes its math fails CI.

Three rules shape the file. Bounds are the explicit rows PyPSA writes, so
their duals are row duals. Regimes are data columns and `where:` masks, never
file variants. Names are PyPSA's, `Component_attribute`, with a symbol table
(`examples/symbols/pypsa.yaml`) making the math read as math.

## Index

A row is **done** and links once it is in the file. A blank status is a row
expected to state one-to-one; a word is the catch: **prep** needs a parameter computed in
data prep · **split** one PyPSA row is several `where:` blocks · **not** a
PyPSA workaround not reproduced · **flag** only under an `n.optimize()`
keyword · **scope** multi-period or stochastic · **open** not stateable yet.

### Rung 1 — transport

| PyPSA                                               | status | note                                                       |
| --------------------------------------------------- | ------ | ---------------------------------------------------------- |
| [`Generator-p`, `Link-p`](#variable-domains)        | done   |                                                            |
| [`Generator-fix-p-lower`](#generator-fix-p-lower)   | done   |                                                            |
| [`Generator-fix-p-upper`](#generator-fix-p-upper)   | done   |                                                            |
| [`Link-fix-p-lower`](#link-fix-p-lower)             | done   |                                                            |
| [`Link-fix-p-upper`](#link-fix-p-upper)             | done   |                                                            |
| [`Bus-nodal_balance`](#bus-nodal_balance)           | done   | a loaded bus with nothing attached: PyPSA refuses, see X2  |
| `Bus-meshed-*-nodal_balance`                        | not    | a linopy-speed split; one row here                         |
| [`marginal_cost`](#objective)                       | done   |                                                            |
| `objective_constant`                                | not    | compare objectives net of `n._objective_constant`          |

### Rung 2 — storage

| PyPSA                                                 | status | note                                                          |
| ----------------------------------------------------- | ------ | ------------------------------------------------------------- |
| [`StorageUnit-p_dispatch`, `-p_store`, `-state_of_charge`, `Store-e`, `Store-p`](#variable-domains) | done |                                 |
| [`StorageUnit-spill`](#variable-domains)              | done   | `where: inflow > 0`, `absence: zero`; bounds on the variable, as PyPSA's |
| [`StorageUnit-fix-*`](#storageunit-fix-p_dispatch-lower), [`Store-fix-e-*`](#store-fix-e-lower) | done |                                 |
| [`StorageUnit-energy_balance`](#storageunit-energy_balance) | done | three blocks: carried / initial / cyclic; `(1-loss)**eh` is prep |
| [`Store-energy_balance`](#store-energy_balance)       | done   | same                                                          |
| [`StorageUnit-p_set`](#storageunit-p_set), [`{c}-{attr}_set`](#generator-p_set) | done | `Generator-p_set`, `Link-p_set`, `StorageUnit-state_of_charge_set`, `Store-e_set` |
| [`marginal_cost_storage`, `spill_cost`](#objective)   | done   |                                                               |

### Rung 3 — expansion

| PyPSA                            | status | note                                        |
| -------------------------------- | ------ | ------------------------------------------- |
| `{c}-p_nom`, `-s_nom`, `-e_nom`  |        |                                             |
| `{c}-ext-{attr}-lower/upper`     |        |                                             |
| `{c}-ext-p_nom-lower/upper`      |        |                                             |
| `{c}-p_nom_set`                  |        |                                             |
| `Generator-e_sum_min/max`        |        |                                             |
| capital cost                     | prep   | `periodized_cost` is an annuity, data prep  |

### Rung 4 — ramps

| PyPSA                          | status | note                                                       |
| ------------------------------ | ------ | ---------------------------------------------------------- |
| `{c}-p-ramp_limit_up/down`     | split  | one block per regime, one for the first snapshot           |

### Rung 5 — global constraints

`GlobalConstraint-{name}` for all; the type and the comparator are data, so
each type is three blocks by sense.

| PyPSA type                            | status      | note                                              |
| ------------------------------------- | ----------- | ------------------------------------------------- |
| `primary_energy`                      | prep, split | carrier weights and "soc at the end" are prep     |
| `operational_limit`                   | prep, split |                                                   |
| `transmission_volume_expansion_limit` | prep, split | membership from PyPSA's carrier string is prep    |
| `transmission_expansion_cost_limit`   | prep, split |                                                   |
| `tech_capacity_expansion_limit`       | prep, split |                                                   |
| `Bus-nom_min/max_{carrier}`           | not         | deprecated in PyPSA                               |
| `Carrier-growth_limit`                | scope       | multi-period                                      |
| `effect_limit`, priced effects        | open        | `effects.py` not inventoried                      |

### Rung 6 — KVL

| PyPSA                   | status | note                              |
| ----------------------- | ------ | --------------------------------- |
| `Line-s`, `Line-fix-s-*` |       |                                   |
| `Kirchhoff-Voltage-Law` | prep   | the cycle basis is data prep      |

### Rung 7 — commitment

| PyPSA                                        | status | note                                                          |
| -------------------------------------------- | ------ | ------------------------------------------------------------- |
| `{c}-status`, `-start_up`, `-shut_down`      |        |                                                               |
| `{c}-com-p-lower/upper`                      |        |                                                               |
| `{c}-*-p-fixed-upper`                        |        |                                                               |
| `{c}-com-transition-start-up/shut-down`      | split  | first snapshot carries the initial status                     |
| `{c}-com-up-time`, `-down-time`              |        | `sum_back(within=min_up_time)`                                |
| `{c}-com-status-*-must_stay_up`              | prep   | `position()` takes a literal, not a parameter                 |
| `stand_by_cost`, `start_up_cost`, `shut_down_cost` |     |                                                             |
| `{c}-com-p-before/-current/-partly-*`        | flag   | `linearized_unit_commitment`                                  |

### Rung 8 — modular and big-M

| PyPSA                                         | status | note                                                       |
| --------------------------------------------- | ------ | ---------------------------------------------------------- |
| `{c}-n_mod`, `{c}-p_nom_modularity`           |        |                                                            |
| `{c}-*-p_nom-variable-upper`                  |        |                                                            |
| `{c}-*-p-fixed-upper`, modular                | split  | non-integer `p_nom / p_nom_mod`: PyPSA refuses, see X1     |
| `{c}-com-mod-p-lower/upper`                   |        |                                                            |
| `{c}-com-ext-p-*` (big-M)                     | prep   | `M` is a network-wide reduction                            |
| `{c}-com-ext-p-lower-nonneg`                  | prep   | `(p_min_pu >= 0).all()` is prep                            |
| `{c}-p-ramp_limit_*-bigM`                     | prep   |                                                            |

### Rung 9 — multi-link and delay

| PyPSA                        | status | note                                          |
| ---------------------------- | ------ | --------------------------------------------- |
| nodal balance, ports 2..n    |        |                                               |
| nodal balance, link delay    | open   | #75, a per-link edge kind                     |

### Not on a rung

| PyPSA                          | status | note                                 |
| ------------------------------ | ------ | ------------------------------------ |
| `{c}-loss*`                    | flag   | `transmission_losses`                |
| `marginal_cost_quadratic`      |        | degree 2 in the objective            |
| `CVaR-*`                       | scope  | stochastic                           |

## Refusals

Where PyPSA refuses to build, parity means refusing too. None is a language
gap; each is a data check not made yet, and where it should live — language,
data prep, or harness — is one open question.

| PyPSA raises                                 | on                                                | here                    | note |
| -------------------------------------------- | ------------------------------------------------- | ----------------------- | ---- |
| `ValueError`, `constraints.py:1449`          | fixed modular `p_nom` not a multiple of `p_nom_mod` | builds a smaller plant | X1   |
| `ValueError`, `constraints.py:1192`          | load on a bus with nothing attached               | row not built, unserved | X2   |
| `ValueError`, `optimize.py:430`              | no component carries a cost                       | feasibility problem     | X3   |
| `NotImplementedError`, `global_constraints.py:339` | depletion with period weightings `!= 1`     | scope                   |      |
| `ValueError`/`RuntimeError`, losses          | `s_nom_max = inf`; secant cap                     | flag                    |      |

Duals and solutions are read back by the harness on the lpspec side:
`marginal_price` is the balance dual over `w_objective`, `mu_upper` the
concatenation of the regime blocks, `p0`/`p1` derived from `Link-p`.

## The file

<!-- gallery:begin -->
The model a plain `n.optimize()` builds, stated in one file. Every declaration is named `Component_attribute` after the PyPSA statement it stands for, and each constraint's description opens with the linopy name PyPSA gives that row, so the two can be read side by side. PyPSA's regimes — extendable, committable — are data columns and become `where:` masks. Bounds are the explicit rows PyPSA writes, so their duals are row duals. Parameters no PyPSA table carries verbatim are computed in data prep and say so in their description.

#### Sets

| Symbol | Meaning |
|---|---|
| $\mathcal{T}$ | index $t$ — `snapshot` — dispatch periods |
| $\mathcal{N}$ | index $n$ — `bus` — network nodes |
| $\mathcal{G}$ | index $g$ — `generator` with $\mathrm{Generator\_bus}: \mathcal{G} \to \mathcal{N}$ — generating units, each on one bus |
| $\mathcal{L}$ | index $l$ — `link` with $\mathrm{Link\_bus0}: \mathcal{L} \to \mathcal{N},\enspace \mathrm{Link\_bus1}: \mathcal{L} \to \mathcal{N}$ — controllable connections, each from one bus to another |
| $\mathcal{D}$ | index $d$ — `load` with $\mathrm{Load\_bus}: \mathcal{D} \to \mathcal{N}$ — demands, each on one bus |
| $\mathcal{S}$ | index $s$ — `storage_unit` with $\mathrm{StorageUnit\_bus}: \mathcal{S} \to \mathcal{N}$ — storage units, dispatch and store behind one bus connection |
| $\mathcal{V}$ | index $v$ — `store` with $\mathrm{Store\_bus}: \mathcal{V} \to \mathcal{N}$ — pure energy stores, each on one bus |

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
| $\mathrm{p}^{\mathrm{set}}$ | `Generator_p_set` over $\mathcal{T} \times \mathcal{G}$ — a given output schedule; a generator without one has no row here |
| $\mathrm{f}^{\mathrm{set}}$ | `Link_p_set` over $\mathcal{T} \times \mathcal{L}$ — a given flow schedule; a link without one has no row here |
| $\mathrm{w}^{\mathrm{sto}}$ | `snapshot_weightings_stores` over $\mathcal{T}$ — PyPSA's `snapshot_weightings.stores` — hours a snapshot stands for in a storage balance |
| $\mathrm{h}^{\mathrm{nom}}$ | `StorageUnit_p_nom` over $\mathcal{S}$ — nominal power |
| $\mathrm{ext}^{h}$ | `StorageUnit_p_nom_extendable` over $\mathcal{S}$ — whether the nominal power is a decision |
| $\underline{\mathrm{h}}$ | `StorageUnit_p_min_pu` over $\mathcal{T} \times \mathcal{S}$ — most storing, per unit of nominal power and negated |
| $\overline{\mathrm{h}}$ | `StorageUnit_p_max_pu` over $\mathcal{T} \times \mathcal{S}$ — most dispatch, per unit of nominal power |
| $\mathrm{T}^{h}$ | `StorageUnit_max_hours` over $\mathcal{S}$ — energy capacity, as hours of dispatch at nominal power |
| $\eta^{-}$ | `StorageUnit_efficiency_store` over $\mathcal{S}$ — share of the power drawn from the bus that becomes charge |
| $\eta^{+}$ | `StorageUnit_efficiency_dispatch` over $\mathcal{S}$ — share of the charge drawn down that reaches the bus |
| $\rho$ | `StorageUnit_retention` over $\mathcal{T} \times \mathcal{S}$ — share of charge kept over a snapshot — PyPSA's `(1 - standing_loss) ** elapsed hours`, data prep |
| $\mathrm{inflow}$ | `StorageUnit_inflow` over $\mathcal{T} \times \mathcal{S}$ — energy arriving per hour, a river into a reservoir |
| $\mathrm{soc}^{0}$ | `StorageUnit_state_of_charge_initial` over $\mathcal{S}$ — charge held before the first snapshot |
| $\mathrm{cyc}$ | `StorageUnit_cyclic_state_of_charge` over $\mathcal{S}$ — whether the horizon closes on itself instead of opening on the initial charge |
| $\mathrm{c}^{h}$ | `StorageUnit_marginal_cost` over $\mathcal{T} \times \mathcal{S}$ — cost of one unit of dispatch |
| $\mathrm{c}^{\mathrm{soc}}$ | `StorageUnit_marginal_cost_storage` over $\mathcal{T} \times \mathcal{S}$ — cost of one unit of charge held over one snapshot |
| $\mathrm{c}^{\mathrm{spill}}$ | `StorageUnit_spill_cost` over $\mathcal{T} \times \mathcal{S}$ — cost of one unit of inflow passed on unused |
| $\mathrm{h}^{\mathrm{set}}$ | `StorageUnit_p_set` over $\mathcal{T} \times \mathcal{S}$ — a given net dispatch schedule; a unit without one has no row here |
| $\mathrm{soc}^{\mathrm{set}}$ | `StorageUnit_state_of_charge_set` over $\mathcal{T} \times \mathcal{S}$ — a given charge schedule; a unit without one has no row here |
| $\mathrm{e}^{\mathrm{nom}}$ | `Store_e_nom` over $\mathcal{V}$ — nominal energy capacity |
| $\mathrm{ext}^{e}$ | `Store_e_nom_extendable` over $\mathcal{V}$ — whether the nominal energy capacity is a decision |
| $\underline{\mathrm{e}}$ | `Store_e_min_pu` over $\mathcal{T} \times \mathcal{V}$ — least energy held, per unit of nominal capacity — negative for a store that may go short |
| $\overline{\mathrm{e}}$ | `Store_e_max_pu` over $\mathcal{T} \times \mathcal{V}$ — most energy held, per unit of nominal capacity |
| $\rho^{e}$ | `Store_retention` over $\mathcal{T} \times \mathcal{V}$ — share of energy kept over a snapshot — PyPSA's `(1 - standing_loss) ** elapsed hours`, data prep |
| $\mathrm{e}^{0}$ | `Store_e_initial` over $\mathcal{V}$ — energy held before the first snapshot |
| $\mathrm{cyc}^{e}$ | `Store_e_cyclic` over $\mathcal{V}$ — whether the horizon closes on itself instead of opening on the initial energy |
| $\mathrm{c}^{q}$ | `Store_marginal_cost` over $\mathcal{T} \times \mathcal{V}$ — cost of one unit of power delivered |
| $\mathrm{c}^{e}$ | `Store_marginal_cost_storage` over $\mathcal{T} \times \mathcal{V}$ — cost of one unit of energy held over one snapshot |
| $\mathrm{e}^{\mathrm{set}}$ | `Store_e_set` over $\mathcal{T} \times \mathcal{V}$ — a given energy schedule; a store without one has no row here |

#### Variables

| Symbol | Meaning |
|---|---|
| $p$ | `Generator_p` over $\mathcal{T} \times \mathcal{G}$ — `Generator-p` — output of a generator in a snapshot |
| $f$ | `Link_p` over $\mathcal{T} \times \mathcal{L}$ — `Link-p` — PyPSA's `p0`, the flow measured at the `Link_bus0` end: a positive value withdraws there and injects at `Link_bus1` |
| $h^{+}$ | `StorageUnit_p_dispatch` over $\mathcal{T} \times \mathcal{S}$ — `StorageUnit-p_dispatch` — power delivered to the bus |
| $h^{-}$ | `StorageUnit_p_store` over $\mathcal{T} \times \mathcal{S}$ — `StorageUnit-p_store` — power drawn from the bus into charge |
| $\mathit{soc}$ | `StorageUnit_state_of_charge` over $\mathcal{T} \times \mathcal{S}$ — `StorageUnit-state_of_charge` — energy held at the end of a snapshot |
| $\mathit{spill}$ | `StorageUnit_spill` over $\mathcal{T} \times \mathcal{S}$ — `StorageUnit-spill` — inflow passed on unused. Zero where there is no inflow, so the balance keeps its row there; the bounds are PyPSA's, on the variable rather than as rows |
| $e$ | `Store_e` over $\mathcal{T} \times \mathcal{V}$ — `Store-e` — energy held at the end of a snapshot |
| $q$ | `Store_p` over $\mathcal{T} \times \mathcal{V}$ — `Store-p` — power delivered to the bus; charging is negative |

$t \ominus k$ denotes cyclic translation: index $t-k$ taken modulo the size of the dimension (`roll`). Plain $t-k$ (`shift`) has no wraparound — terms translated past the edge are simply absent.

$\mathrm{pos}(t)$ denotes where index $t$ sits along its dimension's own order — the order `shift` walks, not the order labels sort in — counted from $0$. The index itself stays the coordinate, so $t$ compares against labels and $\mathrm{pos}(t)$ against positions.

### Objective

```yaml
objective:
  sense: minimize
  description: operating cost, each snapshot weighted by the hours it stands for
  expression: >-
    sum(Generator_p * Generator_marginal_cost * snapshot_weightings_objective)
    + sum(Link_p * Link_marginal_cost * snapshot_weightings_objective)
    + sum(StorageUnit_p_dispatch * StorageUnit_marginal_cost * snapshot_weightings_objective)
    + sum(StorageUnit_state_of_charge * StorageUnit_marginal_cost_storage * snapshot_weightings_objective)
    + sum(StorageUnit_spill * StorageUnit_spill_cost * snapshot_weightings_objective)
    + sum(Store_p * Store_marginal_cost * snapshot_weightings_objective)
    + sum(Store_e * Store_marginal_cost_storage * snapshot_weightings_objective)
```

$$\min \sum_{t \in \mathcal{T},\enspace g \in \mathcal{G}} p_{t,g} \cdot \mathrm{c}_{t,g} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\enspace l \in \mathcal{L}} f_{t,l} \cdot \mathrm{c}^{f}_{t,l} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\enspace s \in \mathcal{S}} h^{+}_{t,s} \cdot \mathrm{c}^{h}_{t,s} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\enspace s \in \mathcal{S}} \mathit{soc}_{t,s} \cdot \mathrm{c}^{\mathrm{soc}}_{t,s} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\enspace s \in \mathcal{S}} \mathit{spill}_{t,s} \cdot \mathrm{c}^{\mathrm{spill}}_{t,s} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\enspace v \in \mathcal{V}} q_{t,v} \cdot \mathrm{c}^{q}_{t,v} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\enspace v \in \mathcal{V}} e_{t,v} \cdot \mathrm{c}^{e}_{t,v} \cdot \mathrm{w}_{t}$$

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

### `StorageUnit-fix-p_dispatch-lower`

`StorageUnit_fix_p_dispatch_lower`

```yaml
StorageUnit_fix_p_dispatch_lower:
  description: "`StorageUnit-fix-p_dispatch-lower` — dispatch is non-negative"
  foreach: [snapshot, storage_unit]
  where: not StorageUnit_p_nom_extendable
  expression: StorageUnit_p_dispatch >= 0
```

$$h^{+}_{t,s} \ge 0 \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \neg \mathrm{ext}^{h}_{s}$$

### `StorageUnit-fix-p_dispatch-upper`

`StorageUnit_fix_p_dispatch_upper`

```yaml
StorageUnit_fix_p_dispatch_upper:
  description: "`StorageUnit-fix-p_dispatch-upper` — a fixed unit dispatches at most its nominal power"
  foreach: [snapshot, storage_unit]
  where: not StorageUnit_p_nom_extendable
  expression: StorageUnit_p_dispatch <= StorageUnit_p_max_pu * StorageUnit_p_nom
```

$$h^{+}_{t,s} \le \overline{\mathrm{h}}_{t,s} \cdot \mathrm{h}^{\mathrm{nom}}_{s} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \neg \mathrm{ext}^{h}_{s}$$

### `StorageUnit-fix-p_store-lower`

`StorageUnit_fix_p_store_lower`

```yaml
StorageUnit_fix_p_store_lower:
  description: "`StorageUnit-fix-p_store-lower` — storing is non-negative"
  foreach: [snapshot, storage_unit]
  where: not StorageUnit_p_nom_extendable
  expression: StorageUnit_p_store >= 0
```

$$h^{-}_{t,s} \ge 0 \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \neg \mathrm{ext}^{h}_{s}$$

### `StorageUnit-fix-p_store-upper`

`StorageUnit_fix_p_store_upper`

```yaml
StorageUnit_fix_p_store_upper:
  description: >-
    `StorageUnit-fix-p_store-upper` — a fixed unit stores at most its
    nominal power, the minimum-per-unit column carrying that cap negated
  foreach: [snapshot, storage_unit]
  where: not StorageUnit_p_nom_extendable
  expression: StorageUnit_p_store <= -StorageUnit_p_min_pu * StorageUnit_p_nom
```

$$h^{-}_{t,s} \le \left( -\underline{\mathrm{h}}_{t,s} \right) \cdot \mathrm{h}^{\mathrm{nom}}_{s} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \neg \mathrm{ext}^{h}_{s}$$

### `StorageUnit-fix-state_of_charge-lower`

`StorageUnit_fix_state_of_charge_lower`

```yaml
StorageUnit_fix_state_of_charge_lower:
  description: "`StorageUnit-fix-state_of_charge-lower` — charge is non-negative"
  foreach: [snapshot, storage_unit]
  where: not StorageUnit_p_nom_extendable
  expression: StorageUnit_state_of_charge >= 0
```

$$\mathit{soc}_{t,s} \ge 0 \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \neg \mathrm{ext}^{h}_{s}$$

### `StorageUnit-fix-state_of_charge-upper`

`StorageUnit_fix_state_of_charge_upper`

```yaml
StorageUnit_fix_state_of_charge_upper:
  description: "`StorageUnit-fix-state_of_charge-upper` — a fixed unit holds at most its hours at nominal power"
  foreach: [snapshot, storage_unit]
  where: not StorageUnit_p_nom_extendable
  expression: StorageUnit_state_of_charge <= StorageUnit_max_hours * StorageUnit_p_nom
```

$$\mathit{soc}_{t,s} \le \mathrm{T}^{h}_{s} \cdot \mathrm{h}^{\mathrm{nom}}_{s} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \neg \mathrm{ext}^{h}_{s}$$

### `StorageUnit-energy_balance`

`StorageUnit_energy_balance`

```yaml
StorageUnit_energy_balance:
  description: >-
    `StorageUnit-energy_balance` — charge carried over less standing loss,
    plus what is stored after its efficiency, less what dispatch draws down
    before its own, plus inflow not spilled. The translated term vacates the
    first snapshot, so this block builds every row but that one; the initial
    block below is the boundary
  foreach: [snapshot, storage_unit]
  where: not StorageUnit_cyclic_state_of_charge
  expression: >-
    StorageUnit_state_of_charge ==
    StorageUnit_retention * shift(StorageUnit_state_of_charge, over=snapshot, offset=1)
    + StorageUnit_efficiency_store * StorageUnit_p_store * snapshot_weightings_stores
    - StorageUnit_p_dispatch * snapshot_weightings_stores / StorageUnit_efficiency_dispatch
    + (StorageUnit_inflow - StorageUnit_spill) * snapshot_weightings_stores
```

$$\mathit{soc}_{t,s} = \rho_{t,s} \cdot \mathit{soc}_{t - 1,s} + \eta^{-}_{s} \cdot h^{-}_{t,s} \cdot \mathrm{w}^{\mathrm{sto}}_{t} - \frac{h^{+}_{t,s} \cdot \mathrm{w}^{\mathrm{sto}}_{t}}{\eta^{+}_{s}} + \left( \mathrm{inflow}_{t,s} - \mathit{spill}_{t,s} \right) \cdot \mathrm{w}^{\mathrm{sto}}_{t} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \neg \mathrm{cyc}_{s}$$

### `StorageUnit-energy_balance`

`StorageUnit_energy_balance_initial`

```yaml
StorageUnit_energy_balance_initial:
  description: "`StorageUnit-energy_balance` — the first snapshot opens on the given initial charge"
  foreach: [snapshot, storage_unit]
  where: not StorageUnit_cyclic_state_of_charge AND position(snapshot) == 0
  expression: >-
    StorageUnit_state_of_charge ==
    StorageUnit_retention * StorageUnit_state_of_charge_initial
    + StorageUnit_efficiency_store * StorageUnit_p_store * snapshot_weightings_stores
    - StorageUnit_p_dispatch * snapshot_weightings_stores / StorageUnit_efficiency_dispatch
    + (StorageUnit_inflow - StorageUnit_spill) * snapshot_weightings_stores
```

$$\mathit{soc}_{t,s} = \rho_{t,s} \cdot \mathrm{soc}^{0}_{s} + \eta^{-}_{s} \cdot h^{-}_{t,s} \cdot \mathrm{w}^{\mathrm{sto}}_{t} - \frac{h^{+}_{t,s} \cdot \mathrm{w}^{\mathrm{sto}}_{t}}{\eta^{+}_{s}} + \left( \mathrm{inflow}_{t,s} - \mathit{spill}_{t,s} \right) \cdot \mathrm{w}^{\mathrm{sto}}_{t} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \neg \mathrm{cyc}_{s} \wedge \mathrm{pos}(t) = 0$$

### `StorageUnit-energy_balance`

`StorageUnit_energy_balance_cyclic`

```yaml
StorageUnit_energy_balance_cyclic:
  description: "`StorageUnit-energy_balance` — a cyclic unit's first snapshot carries over from its last"
  foreach: [snapshot, storage_unit]
  where: StorageUnit_cyclic_state_of_charge
  expression: >-
    StorageUnit_state_of_charge ==
    StorageUnit_retention * shift(StorageUnit_state_of_charge, over=snapshot, offset=1, edge='wrap')
    + StorageUnit_efficiency_store * StorageUnit_p_store * snapshot_weightings_stores
    - StorageUnit_p_dispatch * snapshot_weightings_stores / StorageUnit_efficiency_dispatch
    + (StorageUnit_inflow - StorageUnit_spill) * snapshot_weightings_stores
```

$$\mathit{soc}_{t,s} = \rho_{t,s} \cdot \mathit{soc}_{t \ominus 1,s} + \eta^{-}_{s} \cdot h^{-}_{t,s} \cdot \mathrm{w}^{\mathrm{sto}}_{t} - \frac{h^{+}_{t,s} \cdot \mathrm{w}^{\mathrm{sto}}_{t}}{\eta^{+}_{s}} + \left( \mathrm{inflow}_{t,s} - \mathit{spill}_{t,s} \right) \cdot \mathrm{w}^{\mathrm{sto}}_{t} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \mathrm{cyc}_{s}$$

### `Store-fix-e-lower`

`Store_fix_e_lower`

```yaml
Store_fix_e_lower:
  description: "`Store-fix-e-lower` — a fixed store holds at least its floor"
  foreach: [snapshot, store]
  where: not Store_e_nom_extendable
  expression: Store_e >= Store_e_min_pu * Store_e_nom
```

$$e_{t,v} \ge \underline{\mathrm{e}}_{t,v} \cdot \mathrm{e}^{\mathrm{nom}}_{v} \qquad \forall\thinspace t \in \mathcal{T},\enspace v \in \mathcal{V} \thinspace:\thinspace \neg \mathrm{ext}^{e}_{v}$$

### `Store-fix-e-upper`

`Store_fix_e_upper`

```yaml
Store_fix_e_upper:
  description: "`Store-fix-e-upper` — a fixed store holds at most its nominal capacity"
  foreach: [snapshot, store]
  where: not Store_e_nom_extendable
  expression: Store_e <= Store_e_max_pu * Store_e_nom
```

$$e_{t,v} \le \overline{\mathrm{e}}_{t,v} \cdot \mathrm{e}^{\mathrm{nom}}_{v} \qquad \forall\thinspace t \in \mathcal{T},\enspace v \in \mathcal{V} \thinspace:\thinspace \neg \mathrm{ext}^{e}_{v}$$

### `Store-energy_balance`

`Store_energy_balance`

```yaml
Store_energy_balance:
  description: >-
    `Store-energy_balance` — energy carried over less standing loss, less
    what is delivered to the bus. The translated term vacates the first
    snapshot; the initial block below is the boundary
  foreach: [snapshot, store]
  where: not Store_e_cyclic
  expression: >-
    Store_e ==
    Store_retention * shift(Store_e, over=snapshot, offset=1)
    - Store_p * snapshot_weightings_stores
```

$$e_{t,v} = \rho^{e}_{t,v} \cdot e_{t - 1,v} - q_{t,v} \cdot \mathrm{w}^{\mathrm{sto}}_{t} \qquad \forall\thinspace t \in \mathcal{T},\enspace v \in \mathcal{V} \thinspace:\thinspace \neg \mathrm{cyc}^{e}_{v}$$

### `Store-energy_balance`

`Store_energy_balance_initial`

```yaml
Store_energy_balance_initial:
  description: "`Store-energy_balance` — the first snapshot opens on the given initial energy"
  foreach: [snapshot, store]
  where: not Store_e_cyclic AND position(snapshot) == 0
  expression: >-
    Store_e ==
    Store_retention * Store_e_initial
    - Store_p * snapshot_weightings_stores
```

$$e_{t,v} = \rho^{e}_{t,v} \cdot \mathrm{e}^{0}_{v} - q_{t,v} \cdot \mathrm{w}^{\mathrm{sto}}_{t} \qquad \forall\thinspace t \in \mathcal{T},\enspace v \in \mathcal{V} \thinspace:\thinspace \neg \mathrm{cyc}^{e}_{v} \wedge \mathrm{pos}(t) = 0$$

### `Store-energy_balance`

`Store_energy_balance_cyclic`

```yaml
Store_energy_balance_cyclic:
  description: "`Store-energy_balance` — a cyclic store's first snapshot carries over from its last"
  foreach: [snapshot, store]
  where: Store_e_cyclic
  expression: >-
    Store_e ==
    Store_retention * shift(Store_e, over=snapshot, offset=1, edge='wrap')
    - Store_p * snapshot_weightings_stores
```

$$e_{t,v} = \rho^{e}_{t,v} \cdot e_{t \ominus 1,v} - q_{t,v} \cdot \mathrm{w}^{\mathrm{sto}}_{t} \qquad \forall\thinspace t \in \mathcal{T},\enspace v \in \mathcal{V} \thinspace:\thinspace \mathrm{cyc}^{e}_{v}$$

### `Generator-p_set`

`Generator_p_set`

```yaml
Generator_p_set:
  description: "`Generator-p_set` — output pinned to the given schedule, wherever one is given"
  foreach: [snapshot, generator]
  where: Generator_p_set
  expression: Generator_p == Generator_p_set
```

$$p_{t,g} = \mathrm{p}^{\mathrm{set}}_{t,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{p}^{\mathrm{set}}_{t,g} \text{ is defined}$$

### `Link-p_set`

`Link_p_set`

```yaml
Link_p_set:
  description: "`Link-p_set` — flow pinned to the given schedule, wherever one is given"
  foreach: [snapshot, link]
  where: Link_p_set
  expression: Link_p == Link_p_set
```

$$f_{t,l} = \mathrm{f}^{\mathrm{set}}_{t,l} \qquad \forall\thinspace t \in \mathcal{T},\enspace l \in \mathcal{L} \thinspace:\thinspace \mathrm{f}^{\mathrm{set}}_{t,l} \text{ is defined}$$

### `StorageUnit-p_set`

`StorageUnit_p_set`

```yaml
StorageUnit_p_set:
  description: "`StorageUnit-p_set` — net dispatch pinned to the given schedule, wherever one is given"
  foreach: [snapshot, storage_unit]
  where: StorageUnit_p_set
  expression: StorageUnit_p_dispatch - StorageUnit_p_store == StorageUnit_p_set
```

$$h^{+}_{t,s} - h^{-}_{t,s} = \mathrm{h}^{\mathrm{set}}_{t,s} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \mathrm{h}^{\mathrm{set}}_{t,s} \text{ is defined}$$

### `StorageUnit-state_of_charge_set`

`StorageUnit_state_of_charge_set`

```yaml
StorageUnit_state_of_charge_set:
  description: "`StorageUnit-state_of_charge_set` — charge pinned to the given schedule, wherever one is given"
  foreach: [snapshot, storage_unit]
  where: StorageUnit_state_of_charge_set
  expression: StorageUnit_state_of_charge == StorageUnit_state_of_charge_set
```

$$\mathit{soc}_{t,s} = \mathrm{soc}^{\mathrm{set}}_{t,s} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \mathrm{soc}^{\mathrm{set}}_{t,s} \text{ is defined}$$

### `Store-e_set`

`Store_e_set`

```yaml
Store_e_set:
  description: "`Store-e_set` — energy pinned to the given schedule, wherever one is given"
  foreach: [snapshot, store]
  where: Store_e_set
  expression: Store_e == Store_e_set
```

$$e_{t,v} = \mathrm{e}^{\mathrm{set}}_{t,v} \qquad \forall\thinspace t \in \mathcal{T},\enspace v \in \mathcal{V} \thinspace:\thinspace \mathrm{e}^{\mathrm{set}}_{t,v} \text{ is defined}$$

### `Bus-nodal_balance`

`Bus_nodal_balance`

```yaml
Bus_nodal_balance:
  description: >-
    `Bus-nodal_balance` — what is generated at a bus, storage dispatch and
    stores included, less what the links take away, plus what arrives over
    them after losses, meets the load there. A bus nothing is attached to
    has no row; PyPSA refuses one that carries load, and this file does not
    yet.
  foreach: [snapshot, bus]
  expression: >-
    sum(Generator_p, by=Generator_bus)
    + sum(StorageUnit_p_dispatch - StorageUnit_p_store, by=StorageUnit_bus)
    + sum(Store_p, by=Store_bus)
    - sum(Link_p, by=Link_bus0)
    + sum(Link_p * Link_efficiency, by=Link_bus1)
    == sum(Load_p_set, by=Load_bus)
```

$$\sum_{g \in \mathcal{G} \thinspace:\thinspace \mathrm{Generator\_bus}(g) = n} p_{t,g} + \sum_{s \in \mathcal{S} \thinspace:\thinspace \mathrm{StorageUnit\_bus}(s) = n} \left( h^{+}_{t,s} - h^{-}_{t,s} \right) + \sum_{v \in \mathcal{V} \thinspace:\thinspace \mathrm{Store\_bus}(v) = n} q_{t,v} - \left( \sum_{l \in \mathcal{L} \thinspace:\thinspace \mathrm{Link\_bus0}(l) = n} f_{t,l} \right) + \sum_{l \in \mathcal{L} \thinspace:\thinspace \mathrm{Link\_bus1}(l) = n} f_{t,l} \cdot \eta_{l} = \sum_{d \in \mathcal{D} \thinspace:\thinspace \mathrm{Load\_bus}(d) = n} \mathrm{load}_{t,d} \qquad \forall\thinspace t \in \mathcal{T},\enspace n \in \mathcal{N}$$

#### Variable domains

**`Generator_p`**

$$p_{t,g} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G}$$

**`Link_p`**

$$f_{t,l} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace l \in \mathcal{L}$$

**`StorageUnit_p_dispatch`**

$$h^{+}_{t,s} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S}$$

**`StorageUnit_p_store`**

$$h^{-}_{t,s} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S}$$

**`StorageUnit_state_of_charge`**

$$\mathit{soc}_{t,s} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S}$$

**`StorageUnit_spill`**

$$0 \le \mathit{spill}_{t,s} \le \mathrm{inflow}_{t,s} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \mathrm{inflow}_{t,s} > 0$$

**`Store_e`**

$$e_{t,v} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace v \in \mathcal{V}$$

**`Store_p`**

$$q_{t,v} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace v \in \mathcal{V}$$
<!-- gallery:end -->

Regenerate with `pixi run python -m tools.gallery`.
