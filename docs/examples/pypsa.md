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
| `StorageUnit-p_dispatch`, `-p_store`, `-state_of_charge`, `Store-e`, `Store-p` |     |                                             |
| `StorageUnit-spill`                                   |        | `where: inflow > 0`, `absence: zero`                          |
| `StorageUnit-fix-*`, `Store-fix-e-*`                  |        |                                                               |
| `StorageUnit-energy_balance`                          | split  | cyclic / non-cyclic / first snapshot; `(1-loss)**eh` is prep   |
| `Store-energy_balance`                                | split  | same                                                          |
| `StorageUnit-p_set`, `{c}-{attr}_set`                 |        |                                                               |
| `marginal_cost_storage`, `spill_cost`                 |        |                                                               |

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
