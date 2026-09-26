<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Processes, the ramping

One of the [24 fragments](index.md) of `examples/pypsa.yaml`: PyPSA's `Process`, the ramping rows. It reads `Process_active`, `Process_big_m`, `Process_committable`, `Process_p`, `Process_p_nom_committed`, `Process_p_nom_effective` and 8 more under [`given`](../../reference/language/declarations.md#given).

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
  Process_ramp_limit_up:
    description: most a process may raise its internal power between snapshots, per unit of nominal power; no value means no limit — read at the later of the two snapshots, so the limit may change over time
    dims: [scenario, snapshot, process]
  Process_ramp_limit_down:
    description: most a process may lower its internal power between snapshots, per unit of nominal power; no value means no limit — read at the later of the two snapshots, so the limit may change over time
    dims: [scenario, snapshot, process]
  Process_ramp_limit_start_up:
    description: most internal power in the snapshot a process starts, per unit of nominal power
    dims: [scenario, process]
  Process_ramp_limit_shut_down:
    description: most internal power in the snapshot before a process stops, per unit of nominal power
    dims: [scenario, process]
  Process_p_init:
    description: >-
      the internal power a process brought into the horizon — PyPSA's `p_init`, read
      only where the process came in running; no value means it is unknown, so
      the process carries no ramp row at the first snapshot
    dims: [scenario, process]

given:
  parameters:
    Process_p_nom_extendable: { dims: [process], dtype: bool }
    Process_committable: { dims: [process], dtype: bool }
    Process_status_initial: { dims: [scenario, process], dtype: int }
    Process_p_nom_mod: { dims: [process] }
    Process_big_m: { dims: [scenario, process] }
    Process_active: { dims: [snapshot, process], dtype: bool }
  variables:
    Process_p: { dims: [scenario, snapshot, process] }
    Process_status: { dims: [scenario, snapshot, process], domain: integer }
    Process_start_up: { dims: [scenario, snapshot, process], domain: integer }
    Process_shut_down: { dims: [scenario, snapshot, process], domain: integer }
    Process_p_nom_ext: { dims: [process] }
  expressions:
    Process_p_nom_effective: { dims: [scenario, process] }
    Process_previous_status: { dims: [scenario, snapshot, process] }
    Process_p_nom_committed: { dims: [scenario, process] }

expressions:
  Process_previous_p:
    description: >-
      the internal power a process carries into a snapshot — at the first, the
      `p_init` it brought in where it came in running and nothing where it
      came in off; the previous snapshot's after that
    dims: [scenario, snapshot, process]
    cases:
      opening: { when: "position(snapshot) == 0", expression: Process_status_initial * Process_p_init }
    otherwise: shift(Process_p, along=snapshot, offset=1)
  Process_ramp_up_rate:
    description: >-
      the ramp limit a process's up row reads — PyPSA's `ramp_limit_up`, or the
      full build where it has none, since a start-up ramp alone builds the row
    dims: [scenario, snapshot, process]
    cases:
      given: { when: Process_ramp_limit_up, expression: Process_ramp_limit_up }
    otherwise: 1
  Process_ramp_down_rate:
    description: >-
      the ramp limit a process's down row reads — PyPSA's `ramp_limit_down`, or
      the full build where it has none, since a shut-down ramp alone builds the row
    dims: [scenario, snapshot, process]
    cases:
      given: { when: Process_ramp_limit_down, expression: Process_ramp_limit_down }
    otherwise: 1
  Process_start_up_rate:
    description: >-
      the start-up ramp a process's up row reads — PyPSA's `ramp_limit_start_up`,
      or the full build where it has none
    dims: [scenario, process]
    cases:
      given: { when: Process_ramp_limit_start_up, expression: Process_ramp_limit_start_up }
    otherwise: 1
  Process_shut_down_rate:
    description: >-
      the shut-down ramp a process's down row reads — PyPSA's
      `ramp_limit_shut_down`, or the full build where it has none
    dims: [scenario, process]
    cases:
      given: { when: Process_ramp_limit_shut_down, expression: Process_ramp_limit_shut_down }
    otherwise: 1
  Process_ramp_up_allowance:
    description: >-
      how far a process may raise internal power between two snapshots — its ramp
      limit of the build while it stays on, plus its start-up ramp in the
      snapshot it turns on
    dims: [scenario, snapshot, process]
    cases:
      committed:
        when: Process_committable
        expression: >-
          Process_ramp_up_rate * Process_p_nom_committed * Process_previous_status
          + Process_start_up_rate * Process_p_nom_committed
          * (Process_status - Process_previous_status)
    otherwise: Process_ramp_up_rate * Process_p_nom_effective
  Process_ramp_down_allowance:
    description: >-
      how far a process may lower internal power between two snapshots — its ramp
      limit of the build while it stays on, plus its shut-down ramp in the
      snapshot it turns off
    dims: [scenario, snapshot, process]
    cases:
      committed:
        when: Process_committable
        expression: >-
          Process_ramp_down_rate * Process_p_nom_committed * Process_status
          + Process_shut_down_rate * Process_p_nom_committed
          * (Process_previous_status - Process_status)
    otherwise: Process_ramp_down_rate * Process_p_nom_effective

constraints:
  Process_p_ramp_limit_up_run_big_m:
    description: >-
      `Process-p-ramp_limit_up-run-bigM` — a committed extendable process
      raises internal power no faster than its limit of the chosen build; the big M
      releases the row in the snapshot it turns on
    dims: [scenario, snapshot, process]
    where: >-
      Process_committable AND Process_p_nom_extendable AND NOT (Process_p_nom_mod > 0)
      AND (Process_ramp_limit_up OR Process_ramp_limit_start_up)
      AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Process_status_initial == 0 OR Process_p_init)))
      AND Process_active
    expression: >-
      Process_p - Process_previous_p <=
      Process_ramp_up_rate * Process_p_nom_ext
      + Process_big_m - Process_big_m * Process_previous_status
  Process_p_ramp_limit_up_start_big_m:
    description: >-
      `Process-p-ramp_limit_up-start-bigM` — in the snapshot it turns on, a
      committed extendable process ramps no further than its start-up ramp of
      the chosen build; the big M releases the row everywhere else
    dims: [scenario, snapshot, process]
    where: >-
      Process_committable AND Process_p_nom_extendable AND NOT (Process_p_nom_mod > 0)
      AND (Process_ramp_limit_up OR Process_ramp_limit_start_up)
      AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Process_status_initial == 0 OR Process_p_init)))
      AND Process_active
    expression: >-
      Process_p - Process_previous_p <=
      Process_start_up_rate * Process_p_nom_ext
      + Process_big_m - Process_big_m * Process_start_up
  Process_p_ramp_limit_down_run_big_m:
    description: >-
      `Process-p-ramp_limit_down-run-bigM` — a committed extendable process
      lowers internal power no faster than its limit of the chosen build; the big M
      releases the row in the snapshot it turns off
    dims: [scenario, snapshot, process]
    where: >-
      Process_committable AND Process_p_nom_extendable AND NOT (Process_p_nom_mod > 0)
      AND (Process_ramp_limit_down OR Process_ramp_limit_shut_down)
      AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Process_status_initial == 0 OR Process_p_init)))
      AND Process_active
    expression: >-
      Process_previous_p - Process_p <=
      Process_ramp_down_rate * Process_p_nom_ext
      + Process_big_m - Process_big_m * Process_status
  Process_p_ramp_limit_down_shut_big_m:
    description: >-
      `Process-p-ramp_limit_down-shut-bigM` — in the snapshot it turns off,
      a committed extendable process ramps no further than its shut-down ramp of
      the chosen build; the big M releases the row everywhere else
    dims: [scenario, snapshot, process]
    where: >-
      Process_committable AND Process_p_nom_extendable AND NOT (Process_p_nom_mod > 0)
      AND (Process_ramp_limit_down OR Process_ramp_limit_shut_down)
      AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Process_status_initial == 0 OR Process_p_init)))
      AND Process_active
    expression: >-
      Process_previous_p - Process_p <=
      Process_shut_down_rate * Process_p_nom_ext
      + Process_big_m - Process_big_m * Process_shut_down
  Process_p_ramp_limit_up:
    description: >-
      `Process-p-ramp_limit_up` — a process raises internal power no faster than
      its ramp limit of the build, and a committed one no further than its
      start-up ramp in the snapshot it turns on. A process that came into the
      horizon running carries a row at the first snapshot only where its
      `p_init` gives the internal power it brought in, and no process carries one at
      the start of a later investment period — nor does any process a big M releases instead
    dims: [scenario, snapshot, process]
    where: >-
      (Process_ramp_limit_up OR Process_ramp_limit_start_up)
      AND NOT (Process_committable AND Process_p_nom_extendable AND NOT (Process_p_nom_mod > 0))
      AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Process_status_initial == 0 OR Process_p_init)))
      AND Process_active
    expression: Process_p - Process_previous_p <= Process_ramp_up_allowance
  Process_p_ramp_limit_down:
    description: >-
      `Process-p-ramp_limit_down` — a process lowers internal power no faster than
      its ramp limit of the build, and a committed one no further than its
      shut-down ramp in the snapshot it turns off. A process that came into the
      horizon running carries a row at the first snapshot only where its
      `p_init` gives the internal power it brought in, and no process carries one at
      the start of a later investment period — nor does any process a big M releases instead
    dims: [scenario, snapshot, process]
    where: >-
      (Process_ramp_limit_down OR Process_ramp_limit_shut_down)
      AND NOT (Process_committable AND Process_p_nom_extendable AND NOT (Process_p_nom_mod > 0))
      AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Process_status_initial == 0 OR Process_p_init)))
      AND Process_active
    expression: Process_previous_p - Process_p <= Process_ramp_down_allowance

assumptions:
  Process_came_in_running_unless_committable:
    holds: "Process_status_initial == 1"
    where: "NOT Process_committable AND (Process_ramp_limit_up OR Process_ramp_limit_down)"
    description: >-
      PyPSA reads `up_time_before` of a process that is not committable in its
      ramp rows. Where it is zero, PyPSA builds a row at the first snapshot
      with nothing carried in, and caps the process there at zero, or at its
      start-up ramp where another process of the component is committable with a
      fixed build (`constraints.py:1091-1094`, `1110-1112`). PyPSA documents
      the attribute as read only for a committable process and does not check
      it. PyPSA has not decided which row is intended (PyPSA/PyPSA#1943). The
      spec does not state that row, so it refuses the data
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
| $`\mathrm{ru}^{z}`$ | `Process_ramp_limit_up` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — most a process may raise its internal power between snapshots, per unit of nominal power; no value means no limit — read at the later of the two snapshots, so the limit may change over time |
| $`\mathrm{rd}^{z}`$ | `Process_ramp_limit_down` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — most a process may lower its internal power between snapshots, per unit of nominal power; no value means no limit — read at the later of the two snapshots, so the limit may change over time |
| $`\mathrm{ru}^{z,\mathrm{up}}`$ | `Process_ramp_limit_start_up` over $`\Xi \times \mathcal{J}`$ — most internal power in the snapshot a process starts, per unit of nominal power |
| $`\mathrm{rd}^{z,\mathrm{dn}}`$ | `Process_ramp_limit_shut_down` over $`\Xi \times \mathcal{J}`$ — most internal power in the snapshot before a process stops, per unit of nominal power |
| $`\mathrm{z}^{0}`$ | `Process_p_init` over $`\Xi \times \mathcal{J}`$ — the internal power a process brought into the horizon — PyPSA's `p_init`, read only where the process came in running; no value means it is unknown, so the process carries no ramp row at the first snapshot |

#### Given

| Symbol | Meaning |
|---|---|
| $`\mathrm{ext}^{z}`$ | `Process_p_nom_extendable` over $`\mathcal{J}`$, data another file declares |
| $`\mathrm{com}^{z}`$ | `Process_committable` over $`\mathcal{J}`$, data another file declares |
| $`\mathrm{u}^{z,0}`$ | `Process_status_initial` over $`\Xi \times \mathcal{J}`$, data another file declares |
| $`\mathrm{z}^{\mathrm{mod}}`$ | `Process_p_nom_mod` over $`\mathcal{J}`$, data another file declares |
| $`\mathrm{M}^{z}`$ | `Process_big_m` over $`\Xi \times \mathcal{J}`$, data another file declares |
| $`\mathrm{on}^{z}`$ | `Process_active` over $`\mathcal{T} \times \mathcal{J}`$, data another file declares |
| $`z`$ | `Process_p` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ |
| $`u^{z}`$ | `Process_status` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ |
| $`\mathit{up}^{z}`$ | `Process_start_up` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ |
| $`\mathit{dn}^{z}`$ | `Process_shut_down` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ |
| $`Z`$ | `Process_p_nom_ext` over $`\mathcal{J}`$ |
| $`\widetilde{\mathrm{z}}^{\mathrm{nom}}`$ | `Process_p_nom_effective` over $`\Xi \times \mathcal{J}`$, an expression another file defines |
| $`\overleftarrow{u}^{z}`$ | `Process_previous_status` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$, an expression another file defines |
| $`\widehat{\mathrm{z}}^{\mathrm{nom}}`$ | `Process_p_nom_committed` over $`\Xi \times \mathcal{J}`$, an expression another file defines |

#### Definitions

| Symbol | Meaning |
|---|---|
| $`\overleftarrow{z}`$ | `Process_previous_p` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — the internal power a process carries into a snapshot — at the first, the `p_init` it brought in where it came in running and nothing where it came in off; the previous snapshot's after that |
| $`\widetilde{\mathrm{ru}}^{z}`$ | `Process_ramp_up_rate` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — the ramp limit a process's up row reads — PyPSA's `ramp_limit_up`, or the full build where it has none, since a start-up ramp alone builds the row |
| $`\widetilde{\mathrm{rd}}^{z}`$ | `Process_ramp_down_rate` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — the ramp limit a process's down row reads — PyPSA's `ramp_limit_down`, or the full build where it has none, since a shut-down ramp alone builds the row |
| $`\widetilde{\mathrm{ru}}^{z,\mathrm{up}}`$ | `Process_start_up_rate` over $`\Xi \times \mathcal{J}`$ — the start-up ramp a process's up row reads — PyPSA's `ramp_limit_start_up`, or the full build where it has none |
| $`\widetilde{\mathrm{rd}}^{z,\mathrm{dn}}`$ | `Process_shut_down_rate` over $`\Xi \times \mathcal{J}`$ — the shut-down ramp a process's down row reads — PyPSA's `ramp_limit_shut_down`, or the full build where it has none |
| $`\Delta^{z,+}`$ | `Process_ramp_up_allowance` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — how far a process may raise internal power between two snapshots — its ramp limit of the build while it stays on, plus its start-up ramp in the snapshot it turns on |
| $`\Delta^{z,-}`$ | `Process_ramp_down_allowance` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — how far a process may lower internal power between two snapshots — its ramp limit of the build while it stays on, plus its shut-down ramp in the snapshot it turns off |

$`\mathrm{pos}(t)`$ denotes where index $`t`$ sits along its dimension's own order — the order `shift` steps along, not the order labels sort in — counted from $`0`$. The index itself stays the coordinate, so $`t`$ compares against labels and $`\mathrm{pos}(t)`$ against positions.

$`\mathrm{pos}_{\mathrm{relation}(t)}(t)`$ counts within the group a relation puts $`t`$ in: the subscript names the map, $`\mathcal{T}_{\mathrm{relation}(t)}`$ is the group it lands in, and that group has a first position of its own.

#### Subject to

**`Process_p_ramp_limit_up_run_big_m`**

```math
z_{\xi,t,j} - \overleftarrow{z}_{\xi,t,j} \le \widetilde{\mathrm{ru}}^{z}_{\xi,t,j} \cdot Z_{j} + \mathrm{M}^{z}_{\xi,j} - \mathrm{M}^{z}_{\xi,j} \cdot \overleftarrow{u}^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \left( \mathrm{ru}^{z}_{\xi,t,j} \text{ is defined} \vee \mathrm{ru}^{z,\mathrm{up}}_{\xi,j} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{z,0}_{\xi,j} = 0 \vee \mathrm{z}^{0}_{\xi,j} \text{ is defined} \right) \right) \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_p_ramp_limit_up_start_big_m`**

```math
z_{\xi,t,j} - \overleftarrow{z}_{\xi,t,j} \le \widetilde{\mathrm{ru}}^{z,\mathrm{up}}_{\xi,j} \cdot Z_{j} + \mathrm{M}^{z}_{\xi,j} - \mathrm{M}^{z}_{\xi,j} \cdot \mathit{up}^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \left( \mathrm{ru}^{z}_{\xi,t,j} \text{ is defined} \vee \mathrm{ru}^{z,\mathrm{up}}_{\xi,j} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{z,0}_{\xi,j} = 0 \vee \mathrm{z}^{0}_{\xi,j} \text{ is defined} \right) \right) \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_p_ramp_limit_down_run_big_m`**

```math
\overleftarrow{z}_{\xi,t,j} - z_{\xi,t,j} \le \widetilde{\mathrm{rd}}^{z}_{\xi,t,j} \cdot Z_{j} + \mathrm{M}^{z}_{\xi,j} - \mathrm{M}^{z}_{\xi,j} \cdot u^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \left( \mathrm{rd}^{z}_{\xi,t,j} \text{ is defined} \vee \mathrm{rd}^{z,\mathrm{dn}}_{\xi,j} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{z,0}_{\xi,j} = 0 \vee \mathrm{z}^{0}_{\xi,j} \text{ is defined} \right) \right) \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_p_ramp_limit_down_shut_big_m`**

```math
\overleftarrow{z}_{\xi,t,j} - z_{\xi,t,j} \le \widetilde{\mathrm{rd}}^{z,\mathrm{dn}}_{\xi,j} \cdot Z_{j} + \mathrm{M}^{z}_{\xi,j} - \mathrm{M}^{z}_{\xi,j} \cdot \mathit{dn}^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \left( \mathrm{rd}^{z}_{\xi,t,j} \text{ is defined} \vee \mathrm{rd}^{z,\mathrm{dn}}_{\xi,j} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{z,0}_{\xi,j} = 0 \vee \mathrm{z}^{0}_{\xi,j} \text{ is defined} \right) \right) \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_p_ramp_limit_up`**

```math
z_{\xi,t,j} - \overleftarrow{z}_{\xi,t,j} \le \Delta^{z,+}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \left( \mathrm{ru}^{z}_{\xi,t,j} \text{ is defined} \vee \mathrm{ru}^{z,\mathrm{up}}_{\xi,j} \text{ is defined} \right) \wedge \neg \left( \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{z,0}_{\xi,j} = 0 \vee \mathrm{z}^{0}_{\xi,j} \text{ is defined} \right) \right) \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_p_ramp_limit_down`**

```math
\overleftarrow{z}_{\xi,t,j} - z_{\xi,t,j} \le \Delta^{z,-}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \left( \mathrm{rd}^{z}_{\xi,t,j} \text{ is defined} \vee \mathrm{rd}^{z,\mathrm{dn}}_{\xi,j} \text{ is defined} \right) \wedge \neg \left( \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{z,0}_{\xi,j} = 0 \vee \mathrm{z}^{0}_{\xi,j} \text{ is defined} \right) \right) \wedge \mathrm{on}^{z}_{t,j}
```

#### Definitions

**`Process_previous_p`**

```math
\overleftarrow{z}_{\xi,t,j} = \begin{cases} \mathrm{u}^{z,0}_{\xi,j} \cdot \mathrm{z}^{0}_{\xi,j} & \text{if } \mathrm{pos}(t) = 0 \\ z_{\xi,t - 1,j} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J}
```

**`Process_ramp_up_rate`**

```math
\widetilde{\mathrm{ru}}^{z}_{\xi,t,j} = \begin{cases} \mathrm{ru}^{z}_{\xi,t,j} & \text{if } \mathrm{ru}^{z}_{\xi,t,j} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J}
```

**`Process_ramp_down_rate`**

```math
\widetilde{\mathrm{rd}}^{z}_{\xi,t,j} = \begin{cases} \mathrm{rd}^{z}_{\xi,t,j} & \text{if } \mathrm{rd}^{z}_{\xi,t,j} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J}
```

**`Process_start_up_rate`**

```math
\widetilde{\mathrm{ru}}^{z,\mathrm{up}}_{\xi,j} = \begin{cases} \mathrm{ru}^{z,\mathrm{up}}_{\xi,j} & \text{if } \mathrm{ru}^{z,\mathrm{up}}_{\xi,j} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ j \in \mathcal{J}
```

**`Process_shut_down_rate`**

```math
\widetilde{\mathrm{rd}}^{z,\mathrm{dn}}_{\xi,j} = \begin{cases} \mathrm{rd}^{z,\mathrm{dn}}_{\xi,j} & \text{if } \mathrm{rd}^{z,\mathrm{dn}}_{\xi,j} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ j \in \mathcal{J}
```

**`Process_ramp_up_allowance`**

```math
\Delta^{z,+}_{\xi,t,j} = \begin{cases} \widetilde{\mathrm{ru}}^{z}_{\xi,t,j} \cdot \widehat{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} \cdot \overleftarrow{u}^{z}_{\xi,t,j} + \widetilde{\mathrm{ru}}^{z,\mathrm{up}}_{\xi,j} \cdot \widehat{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} \cdot \left( u^{z}_{\xi,t,j} - \overleftarrow{u}^{z}_{\xi,t,j} \right) & \text{if } \mathrm{com}^{z}_{j} \\ \widetilde{\mathrm{ru}}^{z}_{\xi,t,j} \cdot \widetilde{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J}
```

**`Process_ramp_down_allowance`**

```math
\Delta^{z,-}_{\xi,t,j} = \begin{cases} \widetilde{\mathrm{rd}}^{z}_{\xi,t,j} \cdot \widehat{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} \cdot u^{z}_{\xi,t,j} + \widetilde{\mathrm{rd}}^{z,\mathrm{dn}}_{\xi,j} \cdot \widehat{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} \cdot \left( \overleftarrow{u}^{z}_{\xi,t,j} - u^{z}_{\xi,t,j} \right) & \text{if } \mathrm{com}^{z}_{j} \\ \widetilde{\mathrm{rd}}^{z}_{\xi,t,j} \cdot \widetilde{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J}
```

#### Assumptions

**`Process_came_in_running_unless_committable`**

```math
\mathrm{u}^{z,0}_{\xi,j} = 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \neg \mathrm{com}^{z}_{j} \wedge \left( \mathrm{ru}^{z}_{\xi,t,j} \text{ is defined} \vee \mathrm{rd}^{z}_{\xi,t,j} \text{ is defined} \right)
```
<!-- gallery:end -->
