<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# PyPSA, the relaxed commitment

Rung 12 of [PyPSA in one file](pypsa.md): `n.optimize(linearized_unit_commitment=True)`,
stated on rung 1's transport surface in a file of its own — the model's
description below says why. Its reference network is the shared spine,
`data/base/`, plus the folder below; `rung.json` there names the file and the
keyword.

## Rung 12 — linearized unit commitment

| PyPSA                                                        | status | note                                                |
| ------------------------------------------------------------ | ------ | --------------------------------------------------- |
| [`Generator-status`, `-start_up`, `-shut_down`](#variable-domains) | done | shares in [0, 1], not binaries                    |
| [`Generator-com-p-before`](#generator-com-p-before)          | done   | where start and stop cost the same — a data-prep bool |
| [`Generator-com-p-current`](#generator-com-p-current)        | done   |                                                     |
| [`Generator-com-partly-start-up`](#generator-com-partly-start-up) | done |                                                  |
| [`Generator-com-partly-shut-down`](#generator-com-partly-shut-down) | done |                                                |

<!-- reference:rung_12_linearized_uc:begin -->
> ✔ `pypsa 1.3.0` solves this rung's reference network at objective `7775.0`, 128 rows. `lpspec ga6a817698` binds `examples/pypsa_linearized_uc.yaml` against the same network and lands on the same objective (lpspec's parity gate). Nodal prices agree on 8 rows.

<details markdown="1">
<summary>What this rung adds, as data</summary>

`data/rung_12_linearized_uc/generators.csv`

```csv
name,bus,committable,p_nom,marginal_cost,p_min_pu,min_up_time,min_down_time,up_time_before,ramp_limit_up,ramp_limit_down,ramp_limit_start_up,ramp_limit_shut_down,start_up_cost,shut_down_cost,stand_by_cost
uc12,north,True,50.0,5.0,0.4,3,2,1,0.5,0.5,0.6,0.6,100.0,100.0,5.0
cold12,south,True,30.0,60.0,0.3,2,1,0,0.5,0.5,0.7,0.7,80.0,40.0,
```

`data/rung_12_linearized_uc/loads.csv`

```csv
name,bus
swing12,north
```

`data/rung_12_linearized_uc/timeseries.csv`

```csv
component,name,attribute,snapshot,value
Load,swing12,p_set,0,25.0
Load,swing12,p_set,1,45.0
Load,swing12,p_set,2,45.0
Load,swing12,p_set,3,10.0
```

</details>
<!-- reference:rung_12_linearized_uc:end -->

## The file

<!-- gallery:begin -->
The relaxed class of a plain `n.optimize()`: `linearized_unit_commitment`, stated on rung 1's transport surface in a file of its own. The status, its starts and its stops are shares in [0, 1] rather than binaries — a domain is the model's, not the data's — and four rows PyPSA adds only under the keyword tighten the relaxation where a unit's start and stop cost the same. `examples/pypsa.yaml` stays the integer one.

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
| $\mathrm{f}^{\mathrm{nom}}$ | `Link_p_nom` over $\mathcal{L}$ — nominal power |
| $\underline{\mathrm{f}}$ | `Link_p_min_pu` over $\mathcal{T} \times \mathcal{L}$ — least flow, per unit of nominal power — negative for a link that carries both ways |
| $\overline{\mathrm{f}}$ | `Link_p_max_pu` over $\mathcal{T} \times \mathcal{L}$ — most flow, per unit of nominal power |
| $\eta$ | `Link_efficiency` over $\mathcal{L}$ — share of the flow that arrives at the link's `Link_bus1` end |
| $\mathrm{c}^{f}$ | `Link_marginal_cost` over $\mathcal{T} \times \mathcal{L}$ — cost of one unit of flow |
| $\mathrm{load}$ | `Load_p_set` over $\mathcal{T} \times \mathcal{D}$ — demand |
| $\mathrm{com}$ | `Generator_committable` over $\mathcal{G}$ — whether output is gated by an on/off status decision |
| $\mathrm{ru}$ | `Generator_ramp_limit_up` over $\mathcal{G}$ — most a generator may raise its output between snapshots, per unit of nominal power; no value means no limit |
| $\mathrm{rd}$ | `Generator_ramp_limit_down` over $\mathcal{G}$ — most a generator may lower its output between snapshots, per unit of nominal power; no value means no limit |
| $\mathrm{ru}^{\mathrm{up}}$ | `Generator_ramp_limit_start_up` over $\mathcal{G}$ — most output in the snapshot a unit starts, per unit of nominal power |
| $\mathrm{rd}^{\mathrm{dn}}$ | `Generator_ramp_limit_shut_down` over $\mathcal{G}$ — most output in the snapshot before a unit stops, per unit of nominal power |
| $\mathrm{UT}$ | `Generator_min_up_time` over $\mathcal{G}$ — least snapshots a unit stays on once started |
| $\mathrm{DT}$ | `Generator_min_down_time` over $\mathcal{G}$ — least snapshots a unit stays off once stopped |
| $\mathrm{u}^{0}$ | `Generator_status_initial` over $\mathcal{G}$ — one where the unit was on before the first snapshot, zero where off — PyPSA's `up_time_before > 0`, data prep |
| $\mathrm{hold}$ | `Generator_must_stay_up` over $\mathcal{T} \times \mathcal{G}$ — true while the up time a unit brought into the horizon still binds — data prep, since `position()` compares against a literal rather than a parameter |
| $\mathrm{c}^{\mathrm{up}}$ | `Generator_start_up_cost` over $\mathcal{G}$ — cost of one start |
| $\mathrm{c}^{\mathrm{dn}}$ | `Generator_shut_down_cost` over $\mathcal{G}$ — cost of one stop |
| $\mathrm{c}^{\mathrm{on}}$ | `Generator_stand_by_cost` over $\mathcal{T} \times \mathcal{G}$ — cost of one snapshot spent on |
| $\mathrm{tight}$ | `Generator_partly_tightened` over $\mathcal{G}$ — whether the four tightening rows below apply — PyPSA adds them only where a unit's start-up and shut-down costs are equal; two parameters cannot be compared in a `where`, so the equality is data prep |

#### Variables

| Symbol | Meaning |
|---|---|
| $p$ | `Generator_p` over $\mathcal{T} \times \mathcal{G}$ — `Generator-p` — output of a generator in a snapshot |
| $f$ | `Link_p` over $\mathcal{T} \times \mathcal{L}$ — `Link-p` — PyPSA's `p0`, the flow measured at the `Link_bus0` end: a positive value withdraws there and injects at `Link_bus1` |
| $u$ | `Generator_status` over $\mathcal{T} \times \mathcal{G}$ — `Generator-status` — how much of a committable unit is on, a share in [0, 1] rather than a binary: the relaxation `linearized_unit_commitment` solves |
| $\mathit{up}$ | `Generator_start_up` over $\mathcal{T} \times \mathcal{G}$ — `Generator-start_up` — how much of a committable unit turns on this snapshot |
| $\mathit{dn}$ | `Generator_shut_down` over $\mathcal{T} \times \mathcal{G}$ — `Generator-shut_down` — how much of a committable unit turns off this snapshot |

$\mathrm{pos}(t)$ denotes where index $t$ sits along its dimension's own order — the order `shift` walks, not the order labels sort in — counted from $0$. The index itself stays the coordinate, so $t$ compares against labels and $\mathrm{pos}(t)$ against positions.

### Objective

```yaml
objective:
  sense: minimize
  description: operating cost by weighted snapshot, plus what starts, stops and standing by cost
  expression: >-
    sum(Generator_p * Generator_marginal_cost * snapshot_weightings_objective)
    + sum(Link_p * Link_marginal_cost * snapshot_weightings_objective)
    + sum(Generator_status * Generator_stand_by_cost * snapshot_weightings_objective)
    + sum(Generator_start_up * Generator_start_up_cost)
    + sum(Generator_shut_down * Generator_shut_down_cost)
```

$$\min \sum_{t \in \mathcal{T},\enspace g \in \mathcal{G}} p_{t,g} \cdot \mathrm{c}_{t,g} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\enspace l \in \mathcal{L}} f_{t,l} \cdot \mathrm{c}^{f}_{t,l} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\enspace g \in \mathcal{G}} u_{t,g} \cdot \mathrm{c}^{\mathrm{on}}_{t,g} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\enspace g \in \mathcal{G}} \mathit{up}_{t,g} \cdot \mathrm{c}^{\mathrm{up}}_{g} + \sum_{t \in \mathcal{T},\enspace g \in \mathcal{G}} \mathit{dn}_{t,g} \cdot \mathrm{c}^{\mathrm{dn}}_{g}$$

### `Generator-fix-p-lower`

`Generator_fix_p_lower`

```yaml
Generator_fix_p_lower:
  description: "`Generator-fix-p-lower` — a generator outputs at least its minimum"
  foreach: [snapshot, generator]
  where: not Generator_committable
  expression: Generator_p >= Generator_p_min_pu * Generator_p_nom
```

$$p_{t,g} \ge \underline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \neg \mathrm{com}_{g}$$

### `Generator-fix-p-upper`

`Generator_fix_p_upper`

```yaml
Generator_fix_p_upper:
  description: "`Generator-fix-p-upper` — a generator outputs at most what is available"
  foreach: [snapshot, generator]
  where: not Generator_committable
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom
```

$$p_{t,g} \le \overline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \neg \mathrm{com}_{g}$$

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

### `Generator-com-p-lower`

`Generator_com_p_lower`

```yaml
Generator_com_p_lower:
  description: "`Generator-com-p-lower` — a committed unit outputs at least its minimum; off, at least nothing"
  foreach: [snapshot, generator]
  where: Generator_committable
  expression: Generator_p >= Generator_p_min_pu * Generator_p_nom * Generator_status
```

$$p_{t,g} \ge \underline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot u_{t,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g}$$

### `Generator-com-p-upper`

`Generator_com_p_upper`

```yaml
Generator_com_p_upper:
  description: "`Generator-com-p-upper` — a committed unit outputs at most what is available; off, at most nothing"
  foreach: [snapshot, generator]
  where: Generator_committable
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom * Generator_status
```

$$p_{t,g} \le \overline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot u_{t,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g}$$

### `Generator-com-transition-start-up`

`Generator_com_transition_start_up`

```yaml
Generator_com_transition_start_up:
  description: >-
    `Generator-com-transition-start-up` — turning on is a start. The
    translated term vacates the first snapshot; the initial block below
    compares it against the given status instead
  foreach: [snapshot, generator]
  where: Generator_committable
  expression: Generator_start_up >= Generator_status - shift(Generator_status, over=snapshot, offset=1)
```

$$\mathit{up}_{t,g} \ge u_{t,g} - u_{t - 1,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g}$$

### `Generator-com-transition-start-up`

`Generator_com_transition_start_up_initial`

```yaml
Generator_com_transition_start_up_initial:
  description: "`Generator-com-transition-start-up` — the first snapshot turns on against the status the unit brought in"
  foreach: [snapshot, generator]
  where: Generator_committable AND position(snapshot) == 0
  expression: Generator_start_up >= Generator_status - Generator_status_initial
```

$$\mathit{up}_{t,g} \ge u_{t,g} - \mathrm{u}^{0}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{pos}(t) = 0$$

### `Generator-com-transition-shut-down`

`Generator_com_transition_shut_down`

```yaml
Generator_com_transition_shut_down:
  description: "`Generator-com-transition-shut-down` — turning off is a stop; the first snapshot is the initial block's"
  foreach: [snapshot, generator]
  where: Generator_committable
  expression: Generator_shut_down >= shift(Generator_status, over=snapshot, offset=1) - Generator_status
```

$$\mathit{dn}_{t,g} \ge u_{t - 1,g} - u_{t,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g}$$

### `Generator-com-transition-shut-down`

`Generator_com_transition_shut_down_initial`

```yaml
Generator_com_transition_shut_down_initial:
  description: "`Generator-com-transition-shut-down` — the first snapshot turns off against the status the unit brought in"
  foreach: [snapshot, generator]
  where: Generator_committable AND position(snapshot) == 0
  expression: Generator_shut_down >= Generator_status_initial - Generator_status
```

$$\mathit{dn}_{t,g} \ge \mathrm{u}^{0}_{g} - u_{t,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{pos}(t) = 0$$

### `Generator-com-up-time`

`Generator_com_up_time`

```yaml
Generator_com_up_time:
  description: >-
    `Generator-com-up-time` — a unit started within its own minimum up time
    is still on. The first snapshot's share of the window is the brought-in
    up time's, which the must-stay-up mask carries
  foreach: [snapshot, generator]
  where: Generator_committable AND Generator_min_up_time > 0 AND position(snapshot) > 0
  expression: sum_back(Generator_start_up, over=snapshot, within=Generator_min_up_time) <= Generator_status
```

$$\sum_{t' \in \mathcal{T} \thinspace:\thinspace 0 \le t - t' < \mathrm{UT}} \mathit{up}_{t',g} \le u_{t,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{UT}_{g} > 0 \wedge \mathrm{pos}(t) > 0$$

### `Generator-com-down-time`

`Generator_com_down_time`

```yaml
Generator_com_down_time:
  description: "`Generator-com-down-time` — a unit stopped within its own minimum down time is still off"
  foreach: [snapshot, generator]
  where: Generator_committable AND Generator_min_down_time > 0 AND position(snapshot) > 0
  expression: sum_back(Generator_shut_down, over=snapshot, within=Generator_min_down_time) <= 1 - Generator_status
```

$$\sum_{t' \in \mathcal{T} \thinspace:\thinspace 0 \le t - t' < \mathrm{DT}} \mathit{dn}_{t',g} \le 1 - u_{t,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{DT}_{g} > 0 \wedge \mathrm{pos}(t) > 0$$

### `Generator-com-status-min_up_time_must_stay_up`

`Generator_com_status_must_stay_up`

```yaml
Generator_com_status_must_stay_up:
  description: "`Generator-com-status-min_up_time_must_stay_up` — a unit still serving the up time it brought in stays on"
  foreach: [snapshot, generator]
  where: Generator_committable AND Generator_must_stay_up
  expression: Generator_status == 1
```

$$u_{t,g} = 1 \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{hold}_{t,g}$$

### `Generator-p-ramp_limit_up`

`Generator_p_ramp_limit_up_com`

```yaml
Generator_p_ramp_limit_up_com:
  description: >-
    `Generator-p-ramp_limit_up` — a committed unit raises output no faster
    than its limit while it was already on, and no further than its
    start-up ramp in the snapshot it turns on
  foreach: [snapshot, generator]
  where: Generator_committable AND Generator_ramp_limit_up
  expression: >-
    Generator_p - shift(Generator_p, over=snapshot, offset=1) <=
    Generator_ramp_limit_up * Generator_p_nom * shift(Generator_status, over=snapshot, offset=1)
    + Generator_ramp_limit_start_up * Generator_p_nom
    * (Generator_status - shift(Generator_status, over=snapshot, offset=1))
```

$$p_{t,g} - p_{t - 1,g} \le \mathrm{ru}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot u_{t - 1,g} + \mathrm{ru}^{\mathrm{up}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot \left( u_{t,g} - u_{t - 1,g} \right) \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{ru}_{g} \text{ is defined}$$

### `Generator-p-ramp_limit_up`

`Generator_p_ramp_limit_up_com_initial`

```yaml
Generator_p_ramp_limit_up_com_initial:
  description: >-
    `Generator-p-ramp_limit_up` — a unit that was off ramps its first
    snapshot from an output of nothing; one already on brought an unknown
    output, so it carries no row
  foreach: [snapshot, generator]
  where: >-
    Generator_committable
    AND Generator_ramp_limit_up AND position(snapshot) == 0 AND Generator_status_initial == 0
  expression: >-
    Generator_p <=
    Generator_ramp_limit_up * Generator_p_nom * Generator_status_initial
    + Generator_ramp_limit_start_up * Generator_p_nom * (Generator_status - Generator_status_initial)
```

$$p_{t,g} \le \mathrm{ru}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot \mathrm{u}^{0}_{g} + \mathrm{ru}^{\mathrm{up}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot \left( u_{t,g} - \mathrm{u}^{0}_{g} \right) \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{ru}_{g} \text{ is defined} \wedge \mathrm{pos}(t) = 0 \wedge \mathrm{u}^{0}_{g} = 0$$

### `Generator-p-ramp_limit_down`

`Generator_p_ramp_limit_down_com`

```yaml
Generator_p_ramp_limit_down_com:
  description: >-
    `Generator-p-ramp_limit_down` — a committed unit lowers output no
    faster than its limit while it stays on, and no further than its
    shut-down ramp in the snapshot it turns off
  foreach: [snapshot, generator]
  where: Generator_committable AND Generator_ramp_limit_down
  expression: >-
    shift(Generator_p, over=snapshot, offset=1) - Generator_p <=
    Generator_ramp_limit_down * Generator_p_nom * Generator_status
    + Generator_ramp_limit_shut_down * Generator_p_nom
    * (shift(Generator_status, over=snapshot, offset=1) - Generator_status)
```

$$p_{t - 1,g} - p_{t,g} \le \mathrm{rd}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot u_{t,g} + \mathrm{rd}^{\mathrm{dn}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot \left( u_{t - 1,g} - u_{t,g} \right) \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{rd}_{g} \text{ is defined}$$

### `Generator-p-ramp_limit_down`

`Generator_p_ramp_limit_down_com_initial`

```yaml
Generator_p_ramp_limit_down_com_initial:
  description: >-
    `Generator-p-ramp_limit_down` — a unit that was off ramps its first
    snapshot down from an output of nothing; one already on carries no row
  foreach: [snapshot, generator]
  where: >-
    Generator_committable
    AND Generator_ramp_limit_down AND position(snapshot) == 0 AND Generator_status_initial == 0
  expression: >-
    -Generator_p <=
    Generator_ramp_limit_down * Generator_p_nom * Generator_status
    + Generator_ramp_limit_shut_down * Generator_p_nom * (Generator_status_initial - Generator_status)
```

$$-p_{t,g} \le \mathrm{rd}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot u_{t,g} + \mathrm{rd}^{\mathrm{dn}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot \left( \mathrm{u}^{0}_{g} - u_{t,g} \right) \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{rd}_{g} \text{ is defined} \wedge \mathrm{pos}(t) = 0 \wedge \mathrm{u}^{0}_{g} = 0$$

### `Generator-com-p-before`

`Generator_com_p_before`

```yaml
Generator_com_p_before:
  description: >-
    `Generator-com-p-before` — the output a unit had entering this snapshot
    fits the share of it still on, less the share it is shutting down at
    the shut-down ramp. The translated term vacates the first snapshot, as
    PyPSA's `sns[1:]` does
  foreach: [snapshot, generator]
  where: Generator_committable AND Generator_partly_tightened
  expression: >-
    shift(Generator_p, over=snapshot, offset=1)
    - Generator_ramp_limit_shut_down * Generator_p_nom * shift(Generator_status, over=snapshot, offset=1)
    - (Generator_p_max_pu * Generator_p_nom - Generator_ramp_limit_shut_down * Generator_p_nom)
    * (Generator_status - Generator_start_up) <= 0
```

$$p_{t - 1,g} - \mathrm{rd}^{\mathrm{dn}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot u_{t - 1,g} - \left( \overline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} - \mathrm{rd}^{\mathrm{dn}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \right) \cdot \left( u_{t,g} - \mathit{up}_{t,g} \right) \le 0 \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{tight}_{g}$$

### `Generator-com-p-current`

`Generator_com_p_current`

```yaml
Generator_com_p_current:
  description: "`Generator-com-p-current` — output fits the share on, and the share starting up only up to the start-up ramp"
  foreach: [snapshot, generator]
  where: Generator_committable AND Generator_partly_tightened AND position(snapshot) > 0
  expression: >-
    Generator_p - Generator_p_max_pu * Generator_p_nom * Generator_status
    + (Generator_p_max_pu * Generator_p_nom - Generator_ramp_limit_start_up * Generator_p_nom) * Generator_start_up <= 0
```

$$p_{t,g} - \overline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot u_{t,g} + \left( \overline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} - \mathrm{ru}^{\mathrm{up}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \right) \cdot \mathit{up}_{t,g} \le 0 \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{tight}_{g} \wedge \mathrm{pos}(t) > 0$$

### `Generator-com-partly-start-up`

`Generator_com_partly_start_up`

```yaml
Generator_com_partly_start_up:
  description: "`Generator-com-partly-start-up` — raising output while a share is starting up is bounded by the ramp of the share on and the start-up ramp of the share coming on"
  foreach: [snapshot, generator]
  where: Generator_committable AND Generator_partly_tightened
  expression: >-
    Generator_p - shift(Generator_p, over=snapshot, offset=1)
    - (Generator_p_min_pu * Generator_p_nom + Generator_ramp_limit_up * Generator_p_nom) * Generator_status
    + Generator_p_min_pu * Generator_p_nom * shift(Generator_status, over=snapshot, offset=1)
    + (Generator_p_min_pu * Generator_p_nom + Generator_ramp_limit_up * Generator_p_nom - Generator_ramp_limit_start_up * Generator_p_nom)
    * Generator_start_up <= 0
```

$$p_{t,g} - p_{t - 1,g} - \left( \underline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} + \mathrm{ru}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \right) \cdot u_{t,g} + \underline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot u_{t - 1,g} + \left( \underline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} + \mathrm{ru}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} - \mathrm{ru}^{\mathrm{up}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \right) \cdot \mathit{up}_{t,g} \le 0 \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{tight}_{g}$$

### `Generator-com-partly-shut-down`

`Generator_com_partly_shut_down`

```yaml
Generator_com_partly_shut_down:
  description: "`Generator-com-partly-shut-down` — lowering output while a share is shutting down is bounded likewise, by the shut-down ramp"
  foreach: [snapshot, generator]
  where: Generator_committable AND Generator_partly_tightened
  expression: >-
    shift(Generator_p, over=snapshot, offset=1) - Generator_p
    - Generator_ramp_limit_shut_down * Generator_p_nom * shift(Generator_status, over=snapshot, offset=1)
    + (Generator_ramp_limit_shut_down * Generator_p_nom - Generator_ramp_limit_down * Generator_p_nom) * Generator_status
    - (Generator_p_min_pu * Generator_p_nom + Generator_ramp_limit_down * Generator_p_nom - Generator_ramp_limit_shut_down * Generator_p_nom)
    * Generator_start_up <= 0
```

$$p_{t - 1,g} - p_{t,g} - \mathrm{rd}^{\mathrm{dn}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot u_{t - 1,g} + \left( \mathrm{rd}^{\mathrm{dn}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} - \mathrm{rd}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \right) \cdot u_{t,g} - \left( \underline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} + \mathrm{rd}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} - \mathrm{rd}^{\mathrm{dn}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \right) \cdot \mathit{up}_{t,g} \le 0 \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{tight}_{g}$$

#### Variable domains

**`Generator_p`**

$$p_{t,g} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G}$$

**`Link_p`**

$$f_{t,l} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace l \in \mathcal{L}$$

**`Generator_status`**

$$0 \le u_{t,g} \le 1 \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g}$$

**`Generator_start_up`**

$$0 \le \mathit{up}_{t,g} \le 1 \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g}$$

**`Generator_shut_down`**

$$0 \le \mathit{dn}_{t,g} \le 1 \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g}$$
<!-- gallery:end -->

Regenerate with `pixi run python -m tools.gallery`.
