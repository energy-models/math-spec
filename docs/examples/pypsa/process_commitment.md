<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Processes, the commitment

One of the [24 fragments](index.md) of `examples/pypsa.yaml`: PyPSA's `Process`, the commitment rows. It adds a term to `scenario_opex`. It reads `Process_active`, `Process_maintenance_capacity`, `Process_maintenance_pu`, `Process_maintenance_status`, `Process_modules_installed`, `Process_n_mod` and 10 more under [`given`](../../reference/language/declarations.md#given).

<!-- gallery:begin -->
```yaml
dimensions:
  scenario:
    description: the futures dispatch is chosen in, each with a weight
  snapshot:
    description: dispatch periods
    dtype: datetime
  process:
    description: generalized multi-port converters, each with an internal power that every port draws or delivers at its own rate
  period:
    description: investment periods — PyPSA's `investment_periods`
    dtype: int

relations:
  snapshot_period:
    description: the investment period a snapshot falls in
    key: snapshot
    values: period

parameters:
  Process_committable:
    description: whether internal power is gated by an on/off status decision
    dims: [process]
    dtype: bool
  Process_min_up_time:
    description: least snapshots a process stays on once started
    dims: [scenario, process]
    dtype: int
  Process_min_down_time:
    description: least snapshots a process stays off once stopped
    dims: [scenario, process]
    dtype: int
  Process_status_initial:
    description: one where the process was on before the first snapshot, zero where off — PyPSA's `up_time_before > 0`, data prep
    dims: [scenario, process]
    dtype: int
  Process_must_stay_up:
    description: >-
      true while the up time a process brought into the horizon still binds —
      data prep, since `position()` compares against a literal rather than a
      parameter
    dims: [scenario, snapshot, process]
    dtype: bool
  Process_must_stay_down:
    description: >-
      true while the down time a process brought into the horizon still binds —
      PyPSA's `min_down_time - down_time_before` snapshots, where
      `down_time_before > 0`, data prep for the same reason
    dims: [scenario, snapshot, process]
    dtype: bool
  Process_start_up_cost:
    description: cost of one start
    dims: [scenario, process]
  Process_shut_down_cost:
    description: cost of one stop
    dims: [scenario, process]
  Process_stand_by_cost:
    description: cost of one snapshot spent on
    dims: [scenario, snapshot, process]
  Process_big_m:
    description: a bound safely above any feasible internal power — the build cap at full availability, data prep
    dims: [scenario, process]

variables:
  Process_status:
    description: >-
      `Process-status` — how much of a committable process is on: an integer
      the rows below cap at one, or at the module count where the build is
      modular
    dims: [scenario, snapshot, process]
    where: Process_committable AND Process_active
    domain: integer
    bounds:
      lower: 0
  Process_start_up:
    description: "`Process-start_up` — how much of a committable process turns on this snapshot, capped as the status is"
    dims: [scenario, snapshot, process]
    where: Process_committable AND Process_active
    domain: integer
    bounds:
      lower: 0
  Process_shut_down:
    description: "`Process-shut_down` — how much of a committable process turns off this snapshot, capped as the status is"
    dims: [scenario, snapshot, process]
    where: Process_committable AND Process_active
    domain: integer
    bounds:
      lower: 0

given:
  parameters:
    snapshot_weightings_objective: { dims: [snapshot] }
    Process_p_nom: { dims: [scenario, process] }
    Process_p_nom_extendable: { dims: [process], dtype: bool }
    Process_p_min_pu: { dims: [scenario, snapshot, process] }
    Process_p_max_pu: { dims: [scenario, snapshot, process] }
    Process_p_nom_mod: { dims: [process] }
    Process_modules_installed: { dims: [scenario, process] }
    Process_p_min_pu_nonneg: { dims: [process], dtype: bool }
    Process_maintenance_pu: { dims: [scenario, process] }
    period_weight_objective: { dims: [period] }
    Process_active: { dims: [snapshot, process], dtype: bool }
  variables:
    Process_p: { dims: [scenario, snapshot, process] }
    Process_n_mod: { dims: [process], domain: integer }
    Process_maintenance_capacity: { dims: [scenario, snapshot, process] }
    Process_maintenance_status: { dims: [scenario, snapshot, process] }
    Process_p_nom_ext: { dims: [process] }
  expressions:
    scenario_opex: { dims: [scenario], term: Process_commitment_opex }

expressions:
  Process_previous_status:
    description: >-
      the commitment state a process carries into a snapshot — the state it
      brought into the horizon at the first, the previous snapshot's after that
    dims: [scenario, snapshot, process]
    cases:
      opening: { when: "position(snapshot) == 0", expression: Process_status_initial }
    otherwise: shift(Process_status, along=snapshot, offset=1)
  Process_commitment_opex:
    expression: >-
      sum(sum(((Process_status * Process_stand_by_cost) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=process), over=snapshot)
      + sum(sum(Process_start_up * Process_start_up_cost, over=process), over=snapshot)
      + sum(sum(Process_shut_down * Process_shut_down_cost, over=process), over=snapshot)

constraints:
  Process_com_p_lower:
    description: "`Process-com-p-lower` — a committed process runs at least its minimum; off, at least nothing"
    dims: [scenario, snapshot, process]
    where: Process_committable AND not Process_p_nom_extendable AND Process_active
    expression: Process_p >= Process_p_min_pu * Process_p_nom * (Process_status - Process_maintenance_pu * Process_maintenance_status)
  Process_com_p_upper:
    description: "`Process-com-p-upper` — a committed process runs at most what is available; off, at most nothing"
    dims: [scenario, snapshot, process]
    where: Process_committable AND not Process_p_nom_extendable AND Process_active
    expression: Process_p <= Process_p_max_pu * Process_p_nom * (Process_status - Process_maintenance_pu * Process_maintenance_status)
  Process_com_transition_start_up:
    description: "`Process-com-transition-start-up` — turning on is a start, counted against the state the process carried into the snapshot"
    dims: [scenario, snapshot, process]
    where: Process_committable AND Process_active
    expression: Process_start_up >= Process_status - Process_previous_status
  Process_com_transition_shut_down:
    description: "`Process-com-transition-shut-down` — turning off is a stop, counted against the state the process carried into the snapshot"
    dims: [scenario, snapshot, process]
    where: Process_committable AND Process_active
    expression: Process_shut_down >= Process_previous_status - Process_status
  Process_com_up_time:
    description: >-
      `Process-com-up-time` — a process started within its own minimum up time
      is still on. The first snapshot's share of the window is the brought-in
      up time's, which the must-stay-up mask carries
    dims: [scenario, snapshot, process]
    where: Process_committable AND Process_min_up_time > 0 AND position(snapshot) > 0 AND Process_active
    expression: sum_back(Process_start_up, along=snapshot, window=Process_min_up_time) <= Process_status
  Process_com_down_time:
    description: >-
      `Process-com-down-time` — a process stopped within its own minimum down
      time is still off. The first snapshot's share of the window is the
      brought-in down time's, which the must-stay-down mask carries
    dims: [scenario, snapshot, process]
    where: Process_committable AND Process_min_down_time > 0 AND position(snapshot) > 0 AND Process_active
    expression: sum_back(Process_shut_down, along=snapshot, window=Process_min_down_time) <= 1 - Process_status
  Process_com_status_must_stay_up:
    description: "`Process-com-status-min_up_time_must_stay_up` — a process still serving the up time it brought in stays on"
    dims: [scenario, snapshot, process]
    where: Process_committable AND Process_must_stay_up AND Process_active
    expression: Process_status == 1
  Process_com_status_must_stay_down:
    description: >-
      `Process-com-status-min_down_time_must_stay_up` — a process still serving
      the down time it brought in stays off; PyPSA names the row `_must_stay_up`
    dims: [scenario, snapshot, process]
    where: Process_committable AND Process_must_stay_down AND Process_active
    expression: Process_status == 0
  Process_com_ext_p_upper_cap:
    description: >-
      `Process-com-ext-p-upper-cap` — a committed extendable process runs
      at most what is available of the chosen build, whatever its status
    dims: [scenario, snapshot, process]
    where: Process_committable AND Process_p_nom_extendable AND NOT (Process_p_nom_mod > 0) AND Process_active
    expression: Process_p <= Process_p_max_pu * (Process_p_nom_ext - Process_maintenance_pu * Process_maintenance_capacity)
  Process_com_ext_p_upper_big_m:
    description: "`Process-com-ext-p-upper-bigM` — off, a process does not run; on, the big M is no bound"
    dims: [scenario, snapshot, process]
    where: Process_committable AND Process_p_nom_extendable AND NOT (Process_p_nom_mod > 0) AND Process_active
    expression: Process_p <= Process_big_m * Process_status
  Process_com_ext_p_lower:
    description: >-
      `Process-com-ext-p-lower` — a committed extendable process runs at
      least its minimum of the chosen build; off, the big M releases the row
    dims: [scenario, snapshot, process]
    where: Process_committable AND Process_p_nom_extendable AND NOT (Process_p_nom_mod > 0) AND Process_active
    expression: >-
      Process_p >=
      Process_p_min_pu * (Process_p_nom_ext - Process_maintenance_pu * Process_maintenance_capacity)
      + Process_big_m * Process_status - Process_big_m
  Process_com_ext_p_lower_nonneg:
    description: >-
      `Process-com-ext-p-lower-nonneg` — where no minimum-per-unit is
      negative, internal power is also plainly non-negative, a row the big-M lower
      cannot assert while the process is off
    dims: [scenario, snapshot, process]
    where: >-
      Process_committable AND Process_p_nom_extendable
      AND Process_p_min_pu_nonneg AND NOT (Process_p_nom_mod > 0) AND Process_active
    expression: Process_p >= 0
  Process_com_mod_p_lower:
    description: >-
      `Process-com-mod-p-lower` — a committed modular process runs at least
      its minimum of one module, whether the build is fixed or a decision
    dims: [scenario, snapshot, process]
    where: Process_committable AND Process_p_nom_mod > 0 AND Process_active
    expression: Process_p >= Process_p_min_pu * Process_p_nom_mod * (Process_status - Process_maintenance_pu * Process_maintenance_status)
  Process_com_mod_p_upper:
    description: >-
      `Process-com-mod-p-upper` — a committed modular process runs at most
      one module's share, whether the build is fixed or a decision
    dims: [scenario, snapshot, process]
    where: Process_committable AND Process_p_nom_mod > 0 AND Process_active
    expression: Process_p <= Process_p_max_pu * Process_p_nom_mod * (Process_status - Process_maintenance_pu * Process_maintenance_status)
  Process_status_p_fixed_upper:
    description: >-
      `Process-status-p-fixed-upper` — a status is at most the modules in
      place, an explicit row as PyPSA writes it: one where the build is not
      modular, and the fixed build's whole count of modules where it is
    dims: [scenario, snapshot, process]
    where: Process_committable AND NOT (Process_p_nom_extendable AND Process_p_nom_mod > 0) AND Process_active
    expression: Process_status <= Process_modules_installed
  Process_start_up_p_fixed_upper:
    description: >-
      `Process-start_up-p-fixed-upper` — a start is at most the modules in
      place, an explicit row as PyPSA writes it: one where the build is not
      modular, and the fixed build's whole count of modules where it is
    dims: [scenario, snapshot, process]
    where: Process_committable AND NOT (Process_p_nom_extendable AND Process_p_nom_mod > 0) AND Process_active
    expression: Process_start_up <= Process_modules_installed
  Process_shut_down_p_fixed_upper:
    description: >-
      `Process-shut_down-p-fixed-upper` — a stop is at most the modules in
      place, an explicit row as PyPSA writes it: one where the build is not
      modular, and the fixed build's whole count of modules where it is
    dims: [scenario, snapshot, process]
    where: Process_committable AND NOT (Process_p_nom_extendable AND Process_p_nom_mod > 0) AND Process_active
    expression: Process_shut_down <= Process_modules_installed
  Process_status_p_nom_variable_upper:
    description: "`Process-status-p_nom-variable-upper` — a modular process is on only where a module is built"
    dims: [scenario, snapshot, process]
    where: Process_committable AND Process_p_nom_extendable AND Process_p_nom_mod > 0 AND Process_active
    expression: Process_status <= Process_n_mod
  Process_start_up_p_nom_variable_upper:
    description: "`Process-start_up-p_nom-variable-upper` — a modular process starts only where a module is built"
    dims: [scenario, snapshot, process]
    where: Process_committable AND Process_p_nom_extendable AND Process_p_nom_mod > 0 AND Process_active
    expression: Process_start_up <= Process_n_mod
  Process_shut_down_p_nom_variable_upper:
    description: "`Process-shut_down-p_nom-variable-upper` — a modular process stops only where a module is built"
    dims: [scenario, snapshot, process]
    where: Process_committable AND Process_p_nom_extendable AND Process_p_nom_mod > 0 AND Process_active
    expression: Process_shut_down <= Process_n_mod
```

#### Sets

| Symbol | Meaning |
|---|---|
| $`\Xi`$ | index $`\xi`$ — `scenario` — the futures dispatch is chosen in, each with a weight |
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` with $`\mathrm{snapshot\_period}: \mathcal{T} \to \mathcal{Y}`$ — dispatch periods |
| $`\mathcal{J}`$ | index $`j`$ — `process` — generalized multi-port converters, each with an internal power that every port draws or delivers at its own rate |
| $`\mathcal{Y}`$ | index $`y`$ — `period` with $`\mathrm{snapshot\_period}: \mathcal{T} \to \mathcal{Y}`$ — investment periods — PyPSA's `investment_periods` |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{com}^{z}`$ | `Process_committable` over $`\mathcal{J}`$ — whether internal power is gated by an on/off status decision |
| $`\mathrm{UT}^{z}`$ | `Process_min_up_time` over $`\Xi \times \mathcal{J}`$ — least snapshots a process stays on once started |
| $`\mathrm{DT}^{z}`$ | `Process_min_down_time` over $`\Xi \times \mathcal{J}`$ — least snapshots a process stays off once stopped |
| $`\mathrm{u}^{z,0}`$ | `Process_status_initial` over $`\Xi \times \mathcal{J}`$ — one where the process was on before the first snapshot, zero where off — PyPSA's `up_time_before > 0`, data prep |
| $`\mathrm{hold}^{z}`$ | `Process_must_stay_up` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — true while the up time a process brought into the horizon still binds — data prep, since `position()` compares against a literal rather than a parameter |
| $`\mathrm{rest}^{z}`$ | `Process_must_stay_down` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — true while the down time a process brought into the horizon still binds — PyPSA's `min_down_time - down_time_before` snapshots, where `down_time_before > 0`, data prep for the same reason |
| $`\mathrm{c}^{z,\mathrm{up}}`$ | `Process_start_up_cost` over $`\Xi \times \mathcal{J}`$ — cost of one start |
| $`\mathrm{c}^{z,\mathrm{dn}}`$ | `Process_shut_down_cost` over $`\Xi \times \mathcal{J}`$ — cost of one stop |
| $`\mathrm{c}^{z,\mathrm{on}}`$ | `Process_stand_by_cost` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — cost of one snapshot spent on |
| $`\mathrm{M}^{z}`$ | `Process_big_m` over $`\Xi \times \mathcal{J}`$ — a bound safely above any feasible internal power — the build cap at full availability, data prep |

#### Variables

| Symbol | Meaning |
|---|---|
| $`u^{z}`$ | `Process_status` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — `Process-status` — how much of a committable process is on: an integer the rows below cap at one, or at the module count where the build is modular |
| $`\mathit{up}^{z}`$ | `Process_start_up` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — `Process-start_up` — how much of a committable process turns on this snapshot, capped as the status is |
| $`\mathit{dn}^{z}`$ | `Process_shut_down` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — `Process-shut_down` — how much of a committable process turns off this snapshot, capped as the status is |

#### Given

| Symbol | Meaning |
|---|---|
| $`\mathrm{w}`$ | `snapshot_weightings_objective` over $`\mathcal{T}`$, data another file declares |
| $`\mathrm{z}^{\mathrm{nom}}`$ | `Process_p_nom` over $`\Xi \times \mathcal{J}`$, data another file declares |
| $`\mathrm{ext}^{z}`$ | `Process_p_nom_extendable` over $`\mathcal{J}`$, data another file declares |
| $`\underline{\mathrm{z}}`$ | `Process_p_min_pu` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$, data another file declares |
| $`\overline{\mathrm{z}}`$ | `Process_p_max_pu` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$, data another file declares |
| $`\mathrm{z}^{\mathrm{mod}}`$ | `Process_p_nom_mod` over $`\mathcal{J}`$, data another file declares |
| $`\mathrm{N}^{z,\mathrm{fix}}`$ | `Process_modules_installed` over $`\Xi \times \mathcal{J}`$, data another file declares |
| $`\mathrm{nonneg}^{z}`$ | `Process_p_min_pu_nonneg` over $`\mathcal{J}`$, data another file declares |
| $`\gamma^{z}`$ | `Process_maintenance_pu` over $`\Xi \times \mathcal{J}`$, data another file declares |
| $`\mathrm{w}^{y}`$ | `period_weight_objective` over $`\mathcal{Y}`$, data another file declares |
| $`\mathrm{on}^{z}`$ | `Process_active` over $`\mathcal{T} \times \mathcal{J}`$, data another file declares |
| $`z`$ | `Process_p` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ |
| $`N^{z}`$ | `Process_n_mod` over $`\mathcal{J}`$ |
| $`\mu^{z,\mathrm{nom}}`$ | `Process_maintenance_capacity` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ |
| $`\mu^{z,u}`$ | `Process_maintenance_status` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ |
| $`Z`$ | `Process_p_nom_ext` over $`\mathcal{J}`$ |
| $`\mathit{scenario\_opex}`$ | `scenario_opex` over $`\Xi`$, an expression this file adds `Process_commitment_opex` to |

#### Definitions

| Symbol | Meaning |
|---|---|
| $`\overleftarrow{u}^{z}`$ | `Process_previous_status` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — the commitment state a process carries into a snapshot — the state it brought into the horizon at the first, the previous snapshot's after that |
| $`\mathit{Process\_commitment\_opex}`$ | `Process_commitment_opex` over $`\Xi`$ |

$`\mathrm{pos}(t)`$ denotes where index $`t`$ sits along its dimension's own order — the order `shift` steps along, not the order labels sort in — counted from $`0`$. The index itself stays the coordinate, so $`t`$ compares against labels and $`\mathrm{pos}(t)`$ against positions.

#### Subject to

**`Process_com_p_lower`**

```math
z_{\xi,t,j} \ge \underline{\mathrm{z}}_{\xi,t,j} \cdot \mathrm{z}^{\mathrm{nom}}_{\xi,j} \cdot \left( u^{z}_{\xi,t,j} - \gamma^{z}_{\xi,j} \cdot \mu^{z,u}_{\xi,t,j} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \neg \mathrm{ext}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_com_p_upper`**

```math
z_{\xi,t,j} \le \overline{\mathrm{z}}_{\xi,t,j} \cdot \mathrm{z}^{\mathrm{nom}}_{\xi,j} \cdot \left( u^{z}_{\xi,t,j} - \gamma^{z}_{\xi,j} \cdot \mu^{z,u}_{\xi,t,j} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \neg \mathrm{ext}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_com_transition_start_up`**

```math
\mathit{up}^{z}_{\xi,t,j} \ge u^{z}_{\xi,t,j} - \overleftarrow{u}^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_com_transition_shut_down`**

```math
\mathit{dn}^{z}_{\xi,t,j} \ge \overleftarrow{u}^{z}_{\xi,t,j} - u^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_com_up_time`**

```math
\sum_{t' \in \mathcal{T} \,:\, 0 \le t - t' < \mathrm{UT}^{z}} \mathit{up}^{z}_{\xi,t',j} \le u^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{UT}^{z}_{\xi,j} > 0 \wedge \mathrm{pos}(t) > 0 \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_com_down_time`**

```math
\sum_{t' \in \mathcal{T} \,:\, 0 \le t - t' < \mathrm{DT}^{z}} \mathit{dn}^{z}_{\xi,t',j} \le 1 - u^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{DT}^{z}_{\xi,j} > 0 \wedge \mathrm{pos}(t) > 0 \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_com_status_must_stay_up`**

```math
u^{z}_{\xi,t,j} = 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{hold}^{z}_{\xi,t,j} \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_com_status_must_stay_down`**

```math
u^{z}_{\xi,t,j} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{rest}^{z}_{\xi,t,j} \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_com_ext_p_upper_cap`**

```math
z_{\xi,t,j} \le \overline{\mathrm{z}}_{\xi,t,j} \cdot \left( Z_{j} - \gamma^{z}_{\xi,j} \cdot \mu^{z,\mathrm{nom}}_{\xi,t,j} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_com_ext_p_upper_big_m`**

```math
z_{\xi,t,j} \le \mathrm{M}^{z}_{\xi,j} \cdot u^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_com_ext_p_lower`**

```math
z_{\xi,t,j} \ge \underline{\mathrm{z}}_{\xi,t,j} \cdot \left( Z_{j} - \gamma^{z}_{\xi,j} \cdot \mu^{z,\mathrm{nom}}_{\xi,t,j} \right) + \mathrm{M}^{z}_{\xi,j} \cdot u^{z}_{\xi,t,j} - \mathrm{M}^{z}_{\xi,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_com_ext_p_lower_nonneg`**

```math
z_{\xi,t,j} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \mathrm{nonneg}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_com_mod_p_lower`**

```math
z_{\xi,t,j} \ge \underline{\mathrm{z}}_{\xi,t,j} \cdot \mathrm{z}^{\mathrm{mod}}_{j} \cdot \left( u^{z}_{\xi,t,j} - \gamma^{z}_{\xi,j} \cdot \mu^{z,u}_{\xi,t,j} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_com_mod_p_upper`**

```math
z_{\xi,t,j} \le \overline{\mathrm{z}}_{\xi,t,j} \cdot \mathrm{z}^{\mathrm{mod}}_{j} \cdot \left( u^{z}_{\xi,t,j} - \gamma^{z}_{\xi,j} \cdot \mu^{z,u}_{\xi,t,j} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_status_p_fixed_upper`**

```math
u^{z}_{\xi,t,j} \le \mathrm{N}^{z,\mathrm{fix}}_{\xi,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \neg \left( \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_start_up_p_fixed_upper`**

```math
\mathit{up}^{z}_{\xi,t,j} \le \mathrm{N}^{z,\mathrm{fix}}_{\xi,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \neg \left( \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_shut_down_p_fixed_upper`**

```math
\mathit{dn}^{z}_{\xi,t,j} \le \mathrm{N}^{z,\mathrm{fix}}_{\xi,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \neg \left( \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_status_p_nom_variable_upper`**

```math
u^{z}_{\xi,t,j} \le N^{z}_{j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_start_up_p_nom_variable_upper`**

```math
\mathit{up}^{z}_{\xi,t,j} \le N^{z}_{j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_shut_down_p_nom_variable_upper`**

```math
\mathit{dn}^{z}_{\xi,t,j} \le N^{z}_{j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \wedge \mathrm{on}^{z}_{t,j}
```

#### Definitions

**`Process_previous_status`**

```math
\overleftarrow{u}^{z}_{\xi,t,j} = \begin{cases} \mathrm{u}^{z,0}_{\xi,j} & \text{if } \mathrm{pos}(t) = 0 \\ u^{z}_{\xi,t - 1,j} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J}
```

**`Process_commitment_opex`**

```math
\mathit{Process\_commitment\_opex}_{\xi} = \sum_{t \in \mathcal{T}} \sum_{j \in \mathcal{J}} u^{z}_{\xi,t,j} \cdot \mathrm{c}^{z,\mathrm{on}}_{\xi,t,j} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{j \in \mathcal{J}} \mathit{up}^{z}_{\xi,t,j} \cdot \mathrm{c}^{z,\mathrm{up}}_{\xi,j} + \sum_{t \in \mathcal{T}} \sum_{j \in \mathcal{J}} \mathit{dn}^{z}_{\xi,t,j} \cdot \mathrm{c}^{z,\mathrm{dn}}_{\xi,j} \qquad \forall\, \xi \in \Xi
```

#### Variable domains

**`Process_status`**

```math
u^{z}_{\xi,t,j} \ge 0, u^{z}_{\xi,t,j} \in \mathbb{Z} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_start_up`**

```math
\mathit{up}^{z}_{\xi,t,j} \ge 0, \mathit{up}^{z}_{\xi,t,j} \in \mathbb{Z} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_shut_down`**

```math
\mathit{dn}^{z}_{\xi,t,j} \ge 0, \mathit{dn}^{z}_{\xi,t,j} \in \mathbb{Z} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```
<!-- gallery:end -->
