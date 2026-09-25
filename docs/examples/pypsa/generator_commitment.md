<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Generators, the commitment

One of the [24 fragments](index.md) of `examples/pypsa.yaml`: PyPSA's `Generator`, the commitment rows. It adds a term to `scenario_opex`. It reads `Generator_active`, `Generator_maintenance_capacity`, `Generator_maintenance_pu`, `Generator_maintenance_status`, `Generator_modules_installed`, `Generator_n_mod` and 10 more under [`given`](../../reference/language/declarations.md#given).

<!-- gallery:begin -->
```yaml
dimensions:
  scenario:
    description: the futures dispatch is chosen in, each with a weight
  snapshot:
    description: dispatch periods
    dtype: datetime
  generator:
    description: generating units, each on one bus
  period:
    description: investment periods — PyPSA's `investment_periods`
    dtype: int

relations:
  snapshot_period:
    description: the investment period a snapshot falls in
    key: snapshot
    values: period

parameters:
  Generator_committable:
    description: whether output is gated by an on/off status decision
    dims: [generator]
    dtype: bool
  Generator_min_up_time:
    description: least snapshots a unit stays on once started
    dims: [scenario, generator]
    dtype: int
  Generator_min_down_time:
    description: least snapshots a unit stays off once stopped
    dims: [scenario, generator]
    dtype: int
  Generator_status_initial:
    description: one where the unit was on before the first snapshot, zero where off — PyPSA's `up_time_before > 0`, data prep
    dims: [scenario, generator]
    dtype: int
  Generator_must_stay_up:
    description: >-
      true while the up time a unit brought into the horizon still binds —
      data prep, since `position()` compares against a literal rather than a
      parameter
    dims: [scenario, snapshot, generator]
    dtype: bool
  Generator_must_stay_down:
    description: >-
      true while the down time a unit brought into the horizon still binds —
      PyPSA's `min_down_time - down_time_before` snapshots, where
      `down_time_before > 0`, data prep for the same reason
    dims: [scenario, snapshot, generator]
    dtype: bool
  Generator_start_up_cost:
    description: cost of one start
    dims: [scenario, generator]
  Generator_shut_down_cost:
    description: cost of one stop
    dims: [scenario, generator]
  Generator_stand_by_cost:
    description: cost of one snapshot spent on
    dims: [scenario, snapshot, generator]
  Generator_big_m:
    description: a bound safely above any feasible output — the build cap at full availability, data prep
    dims: [scenario, generator]

variables:
  Generator_status:
    description: >-
      `Generator-status` — how much of a committable unit is on: an integer
      the rows below cap at one, or at the module count where the build is
      modular
    dims: [scenario, snapshot, generator]
    where: Generator_committable AND Generator_active
    domain: integer
    bounds:
      lower: 0
  Generator_start_up:
    description: "`Generator-start_up` — how much of a committable unit turns on this snapshot, capped as the status is"
    dims: [scenario, snapshot, generator]
    where: Generator_committable AND Generator_active
    domain: integer
    bounds:
      lower: 0
  Generator_shut_down:
    description: "`Generator-shut_down` — how much of a committable unit turns off this snapshot, capped as the status is"
    dims: [scenario, snapshot, generator]
    where: Generator_committable AND Generator_active
    domain: integer
    bounds:
      lower: 0

given:
  parameters:
    snapshot_weightings_objective: { dims: [snapshot] }
    Generator_p_nom: { dims: [scenario, generator] }
    Generator_p_nom_extendable: { dims: [generator], dtype: bool }
    Generator_p_min_pu: { dims: [scenario, snapshot, generator] }
    Generator_p_max_pu: { dims: [scenario, snapshot, generator] }
    Generator_p_nom_mod: { dims: [generator] }
    Generator_modules_installed: { dims: [scenario, generator] }
    Generator_p_min_pu_nonneg: { dims: [generator], dtype: bool }
    Generator_maintenance_pu: { dims: [scenario, generator] }
    period_weight_objective: { dims: [period] }
    Generator_active: { dims: [snapshot, generator], dtype: bool }
  variables:
    Generator_p: { dims: [scenario, snapshot, generator] }
    Generator_n_mod: { dims: [generator], domain: integer }
    Generator_maintenance_capacity: { dims: [scenario, snapshot, generator] }
    Generator_maintenance_status: { dims: [scenario, snapshot, generator] }
    Generator_p_nom_ext: { dims: [generator] }
  expressions:
    scenario_opex: { dims: [scenario], term: Generator_commitment_opex }

expressions:
  Generator_previous_status:
    description: >-
      the commitment state a generator carries into a snapshot — the state it
      brought into the horizon at the first, the previous snapshot's after that
    dims: [scenario, snapshot, generator]
    cases:
      opening: { when: "position(snapshot) == 0", expression: Generator_status_initial }
    otherwise: shift(Generator_status, along=snapshot, offset=1)
  Generator_commitment_opex:
    expression: >-
      sum(sum(((Generator_status * Generator_stand_by_cost) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=generator), over=snapshot)
      + sum(sum(Generator_start_up * Generator_start_up_cost, over=generator), over=snapshot)
      + sum(sum(Generator_shut_down * Generator_shut_down_cost, over=generator), over=snapshot)

constraints:
  Generator_com_p_lower:
    description: "`Generator-com-p-lower` — a committed unit outputs at least its minimum; off, at least nothing"
    dims: [scenario, snapshot, generator]
    where: Generator_committable AND not Generator_p_nom_extendable AND Generator_active
    expression: Generator_p >= Generator_p_min_pu * Generator_p_nom * (Generator_status - Generator_maintenance_pu * Generator_maintenance_status)
  Generator_com_p_upper:
    description: "`Generator-com-p-upper` — a committed unit outputs at most what is available; off, at most nothing"
    dims: [scenario, snapshot, generator]
    where: Generator_committable AND not Generator_p_nom_extendable AND Generator_active
    expression: Generator_p <= Generator_p_max_pu * Generator_p_nom * (Generator_status - Generator_maintenance_pu * Generator_maintenance_status)
  Generator_com_transition_start_up:
    description: "`Generator-com-transition-start-up` — turning on is a start, counted against the state the unit carried into the snapshot"
    dims: [scenario, snapshot, generator]
    where: Generator_committable AND Generator_active
    expression: Generator_start_up >= Generator_status - Generator_previous_status
  Generator_com_transition_shut_down:
    description: "`Generator-com-transition-shut-down` — turning off is a stop, counted against the state the unit carried into the snapshot"
    dims: [scenario, snapshot, generator]
    where: Generator_committable AND Generator_active
    expression: Generator_shut_down >= Generator_previous_status - Generator_status
  Generator_com_up_time:
    description: >-
      `Generator-com-up-time` — a unit started within its own minimum up time
      is still on. The first snapshot's share of the window is the brought-in
      up time's, which the must-stay-up mask carries
    dims: [scenario, snapshot, generator]
    where: Generator_committable AND Generator_min_up_time > 0 AND position(snapshot) > 0 AND Generator_active
    expression: sum_back(Generator_start_up, along=snapshot, window=Generator_min_up_time) <= Generator_status
  Generator_com_down_time:
    description: >-
      `Generator-com-down-time` — a unit stopped within its own minimum down
      time is still off. The first snapshot's share of the window is the
      brought-in down time's, which the must-stay-down mask carries
    dims: [scenario, snapshot, generator]
    where: Generator_committable AND Generator_min_down_time > 0 AND position(snapshot) > 0 AND Generator_active
    expression: sum_back(Generator_shut_down, along=snapshot, window=Generator_min_down_time) <= 1 - Generator_status
  Generator_com_status_must_stay_up:
    description: "`Generator-com-status-min_up_time_must_stay_up` — a unit still serving the up time it brought in stays on"
    dims: [scenario, snapshot, generator]
    where: Generator_committable AND Generator_must_stay_up AND Generator_active
    expression: Generator_status == 1
  Generator_com_status_must_stay_down:
    description: >-
      `Generator-com-status-min_down_time_must_stay_up` — a unit still serving
      the down time it brought in stays off; PyPSA names the row `_must_stay_up`
    dims: [scenario, snapshot, generator]
    where: Generator_committable AND Generator_must_stay_down AND Generator_active
    expression: Generator_status == 0
  Generator_com_ext_p_upper_cap:
    description: >-
      `Generator-com-ext-p-upper-cap` — a committed extendable unit outputs
      at most what is available of the chosen build, whatever its status
    dims: [scenario, snapshot, generator]
    where: Generator_committable AND Generator_p_nom_extendable AND NOT (Generator_p_nom_mod > 0) AND Generator_active
    expression: Generator_p <= Generator_p_max_pu * (Generator_p_nom_ext - Generator_maintenance_pu * Generator_maintenance_capacity)
  Generator_com_ext_p_upper_big_m:
    description: "`Generator-com-ext-p-upper-bigM` — off, a unit outputs nothing; on, the big M is no bound"
    dims: [scenario, snapshot, generator]
    where: Generator_committable AND Generator_p_nom_extendable AND NOT (Generator_p_nom_mod > 0) AND Generator_active
    expression: Generator_p <= Generator_big_m * Generator_status
  Generator_com_ext_p_lower:
    description: >-
      `Generator-com-ext-p-lower` — a committed extendable unit outputs at
      least its minimum of the chosen build; off, the big M releases the row
    dims: [scenario, snapshot, generator]
    where: Generator_committable AND Generator_p_nom_extendable AND NOT (Generator_p_nom_mod > 0) AND Generator_active
    expression: >-
      Generator_p >=
      Generator_p_min_pu * (Generator_p_nom_ext - Generator_maintenance_pu * Generator_maintenance_capacity)
      + Generator_big_m * Generator_status - Generator_big_m
  Generator_com_ext_p_lower_nonneg:
    description: >-
      `Generator-com-ext-p-lower-nonneg` — where no minimum-per-unit is
      negative, output is also plainly non-negative, a row the big-M lower
      cannot assert while the unit is off
    dims: [scenario, snapshot, generator]
    where: >-
      Generator_committable AND Generator_p_nom_extendable
      AND Generator_p_min_pu_nonneg AND NOT (Generator_p_nom_mod > 0) AND Generator_active
    expression: Generator_p >= 0
  Generator_com_mod_p_lower:
    description: >-
      `Generator-com-mod-p-lower` — a committed modular unit outputs at least
      its minimum of one module, whether the build is fixed or a decision
    dims: [scenario, snapshot, generator]
    where: Generator_committable AND Generator_p_nom_mod > 0 AND Generator_active
    expression: Generator_p >= Generator_p_min_pu * Generator_p_nom_mod * (Generator_status - Generator_maintenance_pu * Generator_maintenance_status)
  Generator_com_mod_p_upper:
    description: >-
      `Generator-com-mod-p-upper` — a committed modular unit outputs at most
      one module's share, whether the build is fixed or a decision
    dims: [scenario, snapshot, generator]
    where: Generator_committable AND Generator_p_nom_mod > 0 AND Generator_active
    expression: Generator_p <= Generator_p_max_pu * Generator_p_nom_mod * (Generator_status - Generator_maintenance_pu * Generator_maintenance_status)
  Generator_status_p_fixed_upper:
    description: >-
      `Generator-status-p-fixed-upper` — a status is at most the modules in
      place, an explicit row as PyPSA writes it: one where the build is not
      modular, and the fixed build's whole count of modules where it is
    dims: [scenario, snapshot, generator]
    where: Generator_committable AND NOT (Generator_p_nom_extendable AND Generator_p_nom_mod > 0) AND Generator_active
    expression: Generator_status <= Generator_modules_installed
  Generator_start_up_p_fixed_upper:
    description: >-
      `Generator-start_up-p-fixed-upper` — a start is at most the modules in
      place, an explicit row as PyPSA writes it: one where the build is not
      modular, and the fixed build's whole count of modules where it is
    dims: [scenario, snapshot, generator]
    where: Generator_committable AND NOT (Generator_p_nom_extendable AND Generator_p_nom_mod > 0) AND Generator_active
    expression: Generator_start_up <= Generator_modules_installed
  Generator_shut_down_p_fixed_upper:
    description: >-
      `Generator-shut_down-p-fixed-upper` — a stop is at most the modules in
      place, an explicit row as PyPSA writes it: one where the build is not
      modular, and the fixed build's whole count of modules where it is
    dims: [scenario, snapshot, generator]
    where: Generator_committable AND NOT (Generator_p_nom_extendable AND Generator_p_nom_mod > 0) AND Generator_active
    expression: Generator_shut_down <= Generator_modules_installed
  Generator_status_p_nom_variable_upper:
    description: "`Generator-status-p_nom-variable-upper` — a modular unit is on only where a module is built"
    dims: [scenario, snapshot, generator]
    where: Generator_committable AND Generator_p_nom_extendable AND Generator_p_nom_mod > 0 AND Generator_active
    expression: Generator_status <= Generator_n_mod
  Generator_start_up_p_nom_variable_upper:
    description: "`Generator-start_up-p_nom-variable-upper` — a modular unit starts only where a module is built"
    dims: [scenario, snapshot, generator]
    where: Generator_committable AND Generator_p_nom_extendable AND Generator_p_nom_mod > 0 AND Generator_active
    expression: Generator_start_up <= Generator_n_mod
  Generator_shut_down_p_nom_variable_upper:
    description: "`Generator-shut_down-p_nom-variable-upper` — a modular unit stops only where a module is built"
    dims: [scenario, snapshot, generator]
    where: Generator_committable AND Generator_p_nom_extendable AND Generator_p_nom_mod > 0 AND Generator_active
    expression: Generator_shut_down <= Generator_n_mod
```

#### Sets

| Symbol | Meaning |
|---|---|
| $`\Xi`$ | index $`\xi`$ — `scenario` — the futures dispatch is chosen in, each with a weight |
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` with $`\mathrm{snapshot\_period}: \mathcal{T} \to \mathcal{Y}`$ — dispatch periods |
| $`\mathcal{G}`$ | index $`g`$ — `generator` — generating units, each on one bus |
| $`\mathcal{Y}`$ | index $`y`$ — `period` with $`\mathrm{snapshot\_period}: \mathcal{T} \to \mathcal{Y}`$ — investment periods — PyPSA's `investment_periods` |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{com}`$ | `Generator_committable` over $`\mathcal{G}`$ — whether output is gated by an on/off status decision |
| $`\mathrm{UT}`$ | `Generator_min_up_time` over $`\Xi \times \mathcal{G}`$ — least snapshots a unit stays on once started |
| $`\mathrm{DT}`$ | `Generator_min_down_time` over $`\Xi \times \mathcal{G}`$ — least snapshots a unit stays off once stopped |
| $`\mathrm{u}^{0}`$ | `Generator_status_initial` over $`\Xi \times \mathcal{G}`$ — one where the unit was on before the first snapshot, zero where off — PyPSA's `up_time_before > 0`, data prep |
| $`\mathrm{hold}`$ | `Generator_must_stay_up` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — true while the up time a unit brought into the horizon still binds — data prep, since `position()` compares against a literal rather than a parameter |
| $`\mathrm{rest}`$ | `Generator_must_stay_down` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — true while the down time a unit brought into the horizon still binds — PyPSA's `min_down_time - down_time_before` snapshots, where `down_time_before > 0`, data prep for the same reason |
| $`\mathrm{c}^{\mathrm{up}}`$ | `Generator_start_up_cost` over $`\Xi \times \mathcal{G}`$ — cost of one start |
| $`\mathrm{c}^{\mathrm{dn}}`$ | `Generator_shut_down_cost` over $`\Xi \times \mathcal{G}`$ — cost of one stop |
| $`\mathrm{c}^{\mathrm{on}}`$ | `Generator_stand_by_cost` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — cost of one snapshot spent on |
| $`\mathrm{M}`$ | `Generator_big_m` over $`\Xi \times \mathcal{G}`$ — a bound safely above any feasible output — the build cap at full availability, data prep |

#### Variables

| Symbol | Meaning |
|---|---|
| $`u`$ | `Generator_status` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — `Generator-status` — how much of a committable unit is on: an integer the rows below cap at one, or at the module count where the build is modular |
| $`\mathit{up}`$ | `Generator_start_up` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — `Generator-start_up` — how much of a committable unit turns on this snapshot, capped as the status is |
| $`\mathit{dn}`$ | `Generator_shut_down` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — `Generator-shut_down` — how much of a committable unit turns off this snapshot, capped as the status is |

#### Given

| Symbol | Meaning |
|---|---|
| $`\mathrm{w}`$ | `snapshot_weightings_objective` over $`\mathcal{T}`$, data another file declares |
| $`\mathrm{p}^{\mathrm{nom}}`$ | `Generator_p_nom` over $`\Xi \times \mathcal{G}`$, data another file declares |
| $`\mathrm{ext}`$ | `Generator_p_nom_extendable` over $`\mathcal{G}`$, data another file declares |
| $`\underline{\mathrm{p}}`$ | `Generator_p_min_pu` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$, data another file declares |
| $`\overline{\mathrm{p}}`$ | `Generator_p_max_pu` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$, data another file declares |
| $`\mathrm{p}^{\mathrm{mod}}`$ | `Generator_p_nom_mod` over $`\mathcal{G}`$, data another file declares |
| $`\mathrm{N}^{\mathrm{fix}}`$ | `Generator_modules_installed` over $`\Xi \times \mathcal{G}`$, data another file declares |
| $`\mathrm{nonneg}`$ | `Generator_p_min_pu_nonneg` over $`\mathcal{G}`$, data another file declares |
| $`\gamma`$ | `Generator_maintenance_pu` over $`\Xi \times \mathcal{G}`$, data another file declares |
| $`\mathrm{w}^{y}`$ | `period_weight_objective` over $`\mathcal{Y}`$, data another file declares |
| $`\mathrm{on}`$ | `Generator_active` over $`\mathcal{T} \times \mathcal{G}`$, data another file declares |
| $`p`$ | `Generator_p` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ |
| $`N`$ | `Generator_n_mod` over $`\mathcal{G}`$ |
| $`\mu^{\mathrm{nom}}`$ | `Generator_maintenance_capacity` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ |
| $`\mu^{u}`$ | `Generator_maintenance_status` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ |
| $`P`$ | `Generator_p_nom_ext` over $`\mathcal{G}`$ |
| $`\mathit{scenario\_opex}`$ | `scenario_opex` over $`\Xi`$, an expression this file adds `Generator_commitment_opex` to |

#### Definitions

| Symbol | Meaning |
|---|---|
| $`\overleftarrow{u}`$ | `Generator_previous_status` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — the commitment state a generator carries into a snapshot — the state it brought into the horizon at the first, the previous snapshot's after that |
| $`\mathit{Generator\_commitment\_opex}`$ | `Generator_commitment_opex` over $`\Xi`$ |

$`\mathrm{pos}(t)`$ denotes where index $`t`$ sits along its dimension's own order — the order `shift` steps along, not the order labels sort in — counted from $`0`$. The index itself stays the coordinate, so $`t`$ compares against labels and $`\mathrm{pos}(t)`$ against positions.

#### Subject to

**`Generator_com_p_lower`**

```math
p_{\xi,t,g} \ge \underline{\mathrm{p}}_{\xi,t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{\xi,g} \cdot \left( u_{\xi,t,g} - \gamma_{\xi,g} \cdot \mu^{u}_{\xi,t,g} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \neg \mathrm{ext}_{g} \wedge \mathrm{on}_{t,g}
```

**`Generator_com_p_upper`**

```math
p_{\xi,t,g} \le \overline{\mathrm{p}}_{\xi,t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{\xi,g} \cdot \left( u_{\xi,t,g} - \gamma_{\xi,g} \cdot \mu^{u}_{\xi,t,g} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \neg \mathrm{ext}_{g} \wedge \mathrm{on}_{t,g}
```

**`Generator_com_transition_start_up`**

```math
\mathit{up}_{\xi,t,g} \ge u_{\xi,t,g} - \overleftarrow{u}_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{on}_{t,g}
```

**`Generator_com_transition_shut_down`**

```math
\mathit{dn}_{\xi,t,g} \ge \overleftarrow{u}_{\xi,t,g} - u_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{on}_{t,g}
```

**`Generator_com_up_time`**

```math
\sum_{t' \in \mathcal{T} \,:\, 0 \le t - t' < \mathrm{UT}} \mathit{up}_{\xi,t',g} \le u_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{UT}_{\xi,g} > 0 \wedge \mathrm{pos}(t) > 0 \wedge \mathrm{on}_{t,g}
```

**`Generator_com_down_time`**

```math
\sum_{t' \in \mathcal{T} \,:\, 0 \le t - t' < \mathrm{DT}} \mathit{dn}_{\xi,t',g} \le 1 - u_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{DT}_{\xi,g} > 0 \wedge \mathrm{pos}(t) > 0 \wedge \mathrm{on}_{t,g}
```

**`Generator_com_status_must_stay_up`**

```math
u_{\xi,t,g} = 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{hold}_{\xi,t,g} \wedge \mathrm{on}_{t,g}
```

**`Generator_com_status_must_stay_down`**

```math
u_{\xi,t,g} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{rest}_{\xi,t,g} \wedge \mathrm{on}_{t,g}
```

**`Generator_com_ext_p_upper_cap`**

```math
p_{\xi,t,g} \le \overline{\mathrm{p}}_{\xi,t,g} \cdot \left( P_{g} - \gamma_{\xi,g} \cdot \mu^{\mathrm{nom}}_{\xi,t,g} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
```

**`Generator_com_ext_p_upper_big_m`**

```math
p_{\xi,t,g} \le \mathrm{M}_{\xi,g} \cdot u_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
```

**`Generator_com_ext_p_lower`**

```math
p_{\xi,t,g} \ge \underline{\mathrm{p}}_{\xi,t,g} \cdot \left( P_{g} - \gamma_{\xi,g} \cdot \mu^{\mathrm{nom}}_{\xi,t,g} \right) + \mathrm{M}_{\xi,g} \cdot u_{\xi,t,g} - \mathrm{M}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
```

**`Generator_com_ext_p_lower_nonneg`**

```math
p_{\xi,t,g} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \mathrm{nonneg}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
```

**`Generator_com_mod_p_lower`**

```math
p_{\xi,t,g} \ge \underline{\mathrm{p}}_{\xi,t,g} \cdot \mathrm{p}^{\mathrm{mod}}_{g} \cdot \left( u_{\xi,t,g} - \gamma_{\xi,g} \cdot \mu^{u}_{\xi,t,g} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \wedge \mathrm{on}_{t,g}
```

**`Generator_com_mod_p_upper`**

```math
p_{\xi,t,g} \le \overline{\mathrm{p}}_{\xi,t,g} \cdot \mathrm{p}^{\mathrm{mod}}_{g} \cdot \left( u_{\xi,t,g} - \gamma_{\xi,g} \cdot \mu^{u}_{\xi,t,g} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \wedge \mathrm{on}_{t,g}
```

**`Generator_status_p_fixed_upper`**

```math
u_{\xi,t,g} \le \mathrm{N}^{\mathrm{fix}}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \neg \left( \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
```

**`Generator_start_up_p_fixed_upper`**

```math
\mathit{up}_{\xi,t,g} \le \mathrm{N}^{\mathrm{fix}}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \neg \left( \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
```

**`Generator_shut_down_p_fixed_upper`**

```math
\mathit{dn}_{\xi,t,g} \le \mathrm{N}^{\mathrm{fix}}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \neg \left( \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
```

**`Generator_status_p_nom_variable_upper`**

```math
u_{\xi,t,g} \le N_{g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \wedge \mathrm{on}_{t,g}
```

**`Generator_start_up_p_nom_variable_upper`**

```math
\mathit{up}_{\xi,t,g} \le N_{g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \wedge \mathrm{on}_{t,g}
```

**`Generator_shut_down_p_nom_variable_upper`**

```math
\mathit{dn}_{\xi,t,g} \le N_{g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \wedge \mathrm{on}_{t,g}
```

#### Definitions

**`Generator_previous_status`**

```math
\overleftarrow{u}_{\xi,t,g} = \begin{cases} \mathrm{u}^{0}_{\xi,g} & \text{if } \mathrm{pos}(t) = 0 \\ u_{\xi,t - 1,g} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G}
```

**`Generator_commitment_opex`**

```math
\mathit{Generator\_commitment\_opex}_{\xi} = \sum_{t \in \mathcal{T}} \sum_{g \in \mathcal{G}} u_{\xi,t,g} \cdot \mathrm{c}^{\mathrm{on}}_{\xi,t,g} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{g \in \mathcal{G}} \mathit{up}_{\xi,t,g} \cdot \mathrm{c}^{\mathrm{up}}_{\xi,g} + \sum_{t \in \mathcal{T}} \sum_{g \in \mathcal{G}} \mathit{dn}_{\xi,t,g} \cdot \mathrm{c}^{\mathrm{dn}}_{\xi,g} \qquad \forall\, \xi \in \Xi
```

#### Variable domains

**`Generator_status`**

```math
u_{\xi,t,g} \ge 0, u_{\xi,t,g} \in \mathbb{Z} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{on}_{t,g}
```

**`Generator_start_up`**

```math
\mathit{up}_{\xi,t,g} \ge 0, \mathit{up}_{\xi,t,g} \in \mathbb{Z} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{on}_{t,g}
```

**`Generator_shut_down`**

```math
\mathit{dn}_{\xi,t,g} \ge 0, \mathit{dn}_{\xi,t,g} \in \mathbb{Z} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{on}_{t,g}
```
<!-- gallery:end -->
