<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Generators, the ramping

One of the [24 fragments](index.md) of `examples/pypsa.yaml`: PyPSA's `Generator`, the ramping rows. It reads `Generator_active`, `Generator_big_m`, `Generator_committable`, `Generator_p`, `Generator_p_nom_committed`, `Generator_p_nom_effective` and 8 more under [`given`](../../reference/language/declarations.md#given).

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
  Generator_ramp_limit_up:
    description: most a generator may raise its output between snapshots, per unit of nominal power; no value means no limit — read at the later of the two snapshots, so the limit may change over time
    dims: [scenario, snapshot, generator]
  Generator_ramp_limit_down:
    description: most a generator may lower its output between snapshots, per unit of nominal power; no value means no limit — read at the later of the two snapshots, so the limit may change over time
    dims: [scenario, snapshot, generator]
  Generator_ramp_limit_start_up:
    description: most output in the snapshot a unit starts, per unit of nominal power
    dims: [scenario, generator]
  Generator_ramp_limit_shut_down:
    description: most output in the snapshot before a unit stops, per unit of nominal power
    dims: [scenario, generator]
  Generator_p_init:
    description: >-
      the output a unit brought into the horizon — PyPSA's `p_init`, read
      only where the unit came in running; no value means it is unknown, so
      the unit carries no ramp row at the first snapshot
    dims: [scenario, generator]

given:
  parameters:
    Generator_p_nom_extendable: { dims: [generator], dtype: bool }
    Generator_committable: { dims: [generator], dtype: bool }
    Generator_status_initial: { dims: [scenario, generator], dtype: int }
    Generator_p_nom_mod: { dims: [generator] }
    Generator_big_m: { dims: [scenario, generator] }
    Generator_active: { dims: [snapshot, generator], dtype: bool }
  variables:
    Generator_p: { dims: [scenario, snapshot, generator] }
    Generator_status: { dims: [scenario, snapshot, generator], domain: integer }
    Generator_start_up: { dims: [scenario, snapshot, generator], domain: integer }
    Generator_shut_down: { dims: [scenario, snapshot, generator], domain: integer }
    Generator_p_nom_ext: { dims: [generator] }
  expressions:
    Generator_previous_status: { dims: [scenario, snapshot, generator] }
    Generator_p_nom_effective: { dims: [scenario, generator] }
    Generator_p_nom_committed: { dims: [scenario, generator] }

expressions:
  Generator_previous_p:
    description: >-
      the output a generator carries into a snapshot — at the first, the
      `p_init` it brought in where it came in running and nothing where it
      came in off; the previous snapshot's after that
    dims: [scenario, snapshot, generator]
    cases:
      opening: { when: "position(snapshot) == 0", expression: Generator_status_initial * Generator_p_init }
    otherwise: shift(Generator_p, along=snapshot, offset=1)
  Generator_ramp_up_rate:
    description: >-
      the ramp limit a unit's up row reads — PyPSA's `ramp_limit_up`, or the
      full build where it has none, since a start-up ramp alone builds the row
    dims: [scenario, snapshot, generator]
    cases:
      given: { when: Generator_ramp_limit_up, expression: Generator_ramp_limit_up }
    otherwise: 1
  Generator_ramp_down_rate:
    description: >-
      the ramp limit a unit's down row reads — PyPSA's `ramp_limit_down`, or
      the full build where it has none, since a shut-down ramp alone builds the row
    dims: [scenario, snapshot, generator]
    cases:
      given: { when: Generator_ramp_limit_down, expression: Generator_ramp_limit_down }
    otherwise: 1
  Generator_start_up_rate:
    description: >-
      the start-up ramp a unit's up row reads — PyPSA's `ramp_limit_start_up`,
      or the full build where it has none
    dims: [scenario, generator]
    cases:
      given: { when: Generator_ramp_limit_start_up, expression: Generator_ramp_limit_start_up }
    otherwise: 1
  Generator_shut_down_rate:
    description: >-
      the shut-down ramp a unit's down row reads — PyPSA's
      `ramp_limit_shut_down`, or the full build where it has none
    dims: [scenario, generator]
    cases:
      given: { when: Generator_ramp_limit_shut_down, expression: Generator_ramp_limit_shut_down }
    otherwise: 1
  Generator_ramp_up_allowance:
    description: >-
      how far a generator may raise output between two snapshots — its ramp
      limit of the build while it stays on, plus its start-up ramp in the
      snapshot it turns on
    dims: [scenario, snapshot, generator]
    cases:
      committed:
        when: Generator_committable
        expression: >-
          Generator_ramp_up_rate * Generator_p_nom_committed * Generator_previous_status
          + Generator_start_up_rate * Generator_p_nom_committed
          * (Generator_status - Generator_previous_status)
    otherwise: Generator_ramp_up_rate * Generator_p_nom_effective
  Generator_ramp_down_allowance:
    description: >-
      how far a generator may lower output between two snapshots — its ramp
      limit of the build while it stays on, plus its shut-down ramp in the
      snapshot it turns off
    dims: [scenario, snapshot, generator]
    cases:
      committed:
        when: Generator_committable
        expression: >-
          Generator_ramp_down_rate * Generator_p_nom_committed * Generator_status
          + Generator_shut_down_rate * Generator_p_nom_committed
          * (Generator_previous_status - Generator_status)
    otherwise: Generator_ramp_down_rate * Generator_p_nom_effective

constraints:
  Generator_p_ramp_limit_up_run_big_m:
    description: >-
      `Generator-p-ramp_limit_up-run-bigM` — a committed extendable unit
      raises output no faster than its limit of the chosen build; the big M
      releases the row in the snapshot it turns on
    dims: [scenario, snapshot, generator]
    where: >-
      Generator_committable AND Generator_p_nom_extendable AND NOT (Generator_p_nom_mod > 0)
      AND (Generator_ramp_limit_up OR Generator_ramp_limit_start_up)
      AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Generator_status_initial == 0 OR Generator_p_init)))
      AND Generator_active
    expression: >-
      Generator_p - Generator_previous_p <=
      Generator_ramp_up_rate * Generator_p_nom_ext
      + Generator_big_m - Generator_big_m * Generator_previous_status
  Generator_p_ramp_limit_up_start_big_m:
    description: >-
      `Generator-p-ramp_limit_up-start-bigM` — in the snapshot it turns on, a
      committed extendable unit ramps no further than its start-up ramp of
      the chosen build; the big M releases the row everywhere else
    dims: [scenario, snapshot, generator]
    where: >-
      Generator_committable AND Generator_p_nom_extendable AND NOT (Generator_p_nom_mod > 0)
      AND (Generator_ramp_limit_up OR Generator_ramp_limit_start_up)
      AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Generator_status_initial == 0 OR Generator_p_init)))
      AND Generator_active
    expression: >-
      Generator_p - Generator_previous_p <=
      Generator_start_up_rate * Generator_p_nom_ext
      + Generator_big_m - Generator_big_m * Generator_start_up
  Generator_p_ramp_limit_down_run_big_m:
    description: >-
      `Generator-p-ramp_limit_down-run-bigM` — a committed extendable unit
      lowers output no faster than its limit of the chosen build; the big M
      releases the row in the snapshot it turns off
    dims: [scenario, snapshot, generator]
    where: >-
      Generator_committable AND Generator_p_nom_extendable AND NOT (Generator_p_nom_mod > 0)
      AND (Generator_ramp_limit_down OR Generator_ramp_limit_shut_down)
      AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Generator_status_initial == 0 OR Generator_p_init)))
      AND Generator_active
    expression: >-
      Generator_previous_p - Generator_p <=
      Generator_ramp_down_rate * Generator_p_nom_ext
      + Generator_big_m - Generator_big_m * Generator_status
  Generator_p_ramp_limit_down_shut_big_m:
    description: >-
      `Generator-p-ramp_limit_down-shut-bigM` — in the snapshot it turns off,
      a committed extendable unit ramps no further than its shut-down ramp of
      the chosen build; the big M releases the row everywhere else
    dims: [scenario, snapshot, generator]
    where: >-
      Generator_committable AND Generator_p_nom_extendable AND NOT (Generator_p_nom_mod > 0)
      AND (Generator_ramp_limit_down OR Generator_ramp_limit_shut_down)
      AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Generator_status_initial == 0 OR Generator_p_init)))
      AND Generator_active
    expression: >-
      Generator_previous_p - Generator_p <=
      Generator_shut_down_rate * Generator_p_nom_ext
      + Generator_big_m - Generator_big_m * Generator_shut_down
  Generator_p_ramp_limit_up:
    description: >-
      `Generator-p-ramp_limit_up` — a generator raises output no faster than
      its ramp limit of the build, and a committed one no further than its
      start-up ramp in the snapshot it turns on. A unit that came into the
      horizon running carries a row at the first snapshot only where its
      `p_init` gives the output it brought in, and no unit carries one at
      the start of a later investment period — nor does any unit a big M releases instead
    dims: [scenario, snapshot, generator]
    where: >-
      (Generator_ramp_limit_up OR Generator_ramp_limit_start_up)
      AND NOT (Generator_committable AND Generator_p_nom_extendable AND NOT (Generator_p_nom_mod > 0))
      AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Generator_status_initial == 0 OR Generator_p_init)))
      AND Generator_active
    expression: Generator_p - Generator_previous_p <= Generator_ramp_up_allowance
  Generator_p_ramp_limit_down:
    description: >-
      `Generator-p-ramp_limit_down` — a generator lowers output no faster than
      its ramp limit of the build, and a committed one no further than its
      shut-down ramp in the snapshot it turns off. A unit that came into the
      horizon running carries a row at the first snapshot only where its
      `p_init` gives the output it brought in, and no unit carries one at
      the start of a later investment period — nor does any unit a big M releases instead
    dims: [scenario, snapshot, generator]
    where: >-
      (Generator_ramp_limit_down OR Generator_ramp_limit_shut_down)
      AND NOT (Generator_committable AND Generator_p_nom_extendable AND NOT (Generator_p_nom_mod > 0))
      AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Generator_status_initial == 0 OR Generator_p_init)))
      AND Generator_active
    expression: Generator_previous_p - Generator_p <= Generator_ramp_down_allowance

assumptions:
  Generator_came_in_running_unless_committable:
    holds: "Generator_status_initial == 1"
    where: "NOT Generator_committable AND (Generator_ramp_limit_up OR Generator_ramp_limit_down)"
    description: >-
      PyPSA reads `up_time_before` of a unit that is not committable in its
      ramp rows. Where it is zero, PyPSA builds a row at the first snapshot
      with nothing carried in, and caps the unit there at zero, or at its
      start-up ramp where another unit of the component is committable with a
      fixed build (`constraints.py:1091-1094`, `1110-1112`). PyPSA documents
      the attribute as read only for a committable unit and does not check
      it. PyPSA has not decided which row is intended (PyPSA/PyPSA#1943). The
      spec does not state that row, so it refuses the data
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
| $`\mathrm{ru}`$ | `Generator_ramp_limit_up` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — most a generator may raise its output between snapshots, per unit of nominal power; no value means no limit — read at the later of the two snapshots, so the limit may change over time |
| $`\mathrm{rd}`$ | `Generator_ramp_limit_down` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — most a generator may lower its output between snapshots, per unit of nominal power; no value means no limit — read at the later of the two snapshots, so the limit may change over time |
| $`\mathrm{ru}^{\mathrm{up}}`$ | `Generator_ramp_limit_start_up` over $`\Xi \times \mathcal{G}`$ — most output in the snapshot a unit starts, per unit of nominal power |
| $`\mathrm{rd}^{\mathrm{dn}}`$ | `Generator_ramp_limit_shut_down` over $`\Xi \times \mathcal{G}`$ — most output in the snapshot before a unit stops, per unit of nominal power |
| $`\mathrm{p}^{0}`$ | `Generator_p_init` over $`\Xi \times \mathcal{G}`$ — the output a unit brought into the horizon — PyPSA's `p_init`, read only where the unit came in running; no value means it is unknown, so the unit carries no ramp row at the first snapshot |

#### Given

| Symbol | Meaning |
|---|---|
| $`\mathrm{ext}`$ | `Generator_p_nom_extendable` over $`\mathcal{G}`$, data another file declares |
| $`\mathrm{com}`$ | `Generator_committable` over $`\mathcal{G}`$, data another file declares |
| $`\mathrm{u}^{0}`$ | `Generator_status_initial` over $`\Xi \times \mathcal{G}`$, data another file declares |
| $`\mathrm{p}^{\mathrm{mod}}`$ | `Generator_p_nom_mod` over $`\mathcal{G}`$, data another file declares |
| $`\mathrm{M}`$ | `Generator_big_m` over $`\Xi \times \mathcal{G}`$, data another file declares |
| $`\mathrm{on}`$ | `Generator_active` over $`\mathcal{T} \times \mathcal{G}`$, data another file declares |
| $`p`$ | `Generator_p` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ |
| $`u`$ | `Generator_status` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ |
| $`\mathit{up}`$ | `Generator_start_up` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ |
| $`\mathit{dn}`$ | `Generator_shut_down` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ |
| $`P`$ | `Generator_p_nom_ext` over $`\mathcal{G}`$ |
| $`\overleftarrow{u}`$ | `Generator_previous_status` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$, an expression another file defines |
| $`\widetilde{\mathrm{p}}^{\mathrm{nom}}`$ | `Generator_p_nom_effective` over $`\Xi \times \mathcal{G}`$, an expression another file defines |
| $`\widehat{\mathrm{p}}^{\mathrm{nom}}`$ | `Generator_p_nom_committed` over $`\Xi \times \mathcal{G}`$, an expression another file defines |

#### Definitions

| Symbol | Meaning |
|---|---|
| $`\overleftarrow{p}`$ | `Generator_previous_p` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — the output a generator carries into a snapshot — at the first, the `p_init` it brought in where it came in running and nothing where it came in off; the previous snapshot's after that |
| $`\widetilde{\mathrm{ru}}`$ | `Generator_ramp_up_rate` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — the ramp limit a unit's up row reads — PyPSA's `ramp_limit_up`, or the full build where it has none, since a start-up ramp alone builds the row |
| $`\widetilde{\mathrm{rd}}`$ | `Generator_ramp_down_rate` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — the ramp limit a unit's down row reads — PyPSA's `ramp_limit_down`, or the full build where it has none, since a shut-down ramp alone builds the row |
| $`\widetilde{\mathrm{ru}}^{\mathrm{up}}`$ | `Generator_start_up_rate` over $`\Xi \times \mathcal{G}`$ — the start-up ramp a unit's up row reads — PyPSA's `ramp_limit_start_up`, or the full build where it has none |
| $`\widetilde{\mathrm{rd}}^{\mathrm{dn}}`$ | `Generator_shut_down_rate` over $`\Xi \times \mathcal{G}`$ — the shut-down ramp a unit's down row reads — PyPSA's `ramp_limit_shut_down`, or the full build where it has none |
| $`\Delta^{+}`$ | `Generator_ramp_up_allowance` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — how far a generator may raise output between two snapshots — its ramp limit of the build while it stays on, plus its start-up ramp in the snapshot it turns on |
| $`\Delta^{-}`$ | `Generator_ramp_down_allowance` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — how far a generator may lower output between two snapshots — its ramp limit of the build while it stays on, plus its shut-down ramp in the snapshot it turns off |

$`\mathrm{pos}(t)`$ denotes where index $`t`$ sits along its dimension's own order — the order `shift` steps along, not the order labels sort in — counted from $`0`$. The index itself stays the coordinate, so $`t`$ compares against labels and $`\mathrm{pos}(t)`$ against positions.

$`\mathrm{pos}_{\mathrm{relation}(t)}(t)`$ counts within the group a relation puts $`t`$ in: the subscript names the map, $`\mathcal{T}_{\mathrm{relation}(t)}`$ is the group it lands in, and that group has a first position of its own.

#### Subject to

**`Generator_p_ramp_limit_up_run_big_m`**

```math
p_{\xi,t,g} - \overleftarrow{p}_{\xi,t,g} \le \widetilde{\mathrm{ru}}_{\xi,t,g} \cdot P_{g} + \mathrm{M}_{\xi,g} - \mathrm{M}_{\xi,g} \cdot \overleftarrow{u}_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \left( \mathrm{ru}_{\xi,t,g} \text{ is defined} \vee \mathrm{ru}^{\mathrm{up}}_{\xi,g} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{0}_{\xi,g} = 0 \vee \mathrm{p}^{0}_{\xi,g} \text{ is defined} \right) \right) \wedge \mathrm{on}_{t,g}
```

**`Generator_p_ramp_limit_up_start_big_m`**

```math
p_{\xi,t,g} - \overleftarrow{p}_{\xi,t,g} \le \widetilde{\mathrm{ru}}^{\mathrm{up}}_{\xi,g} \cdot P_{g} + \mathrm{M}_{\xi,g} - \mathrm{M}_{\xi,g} \cdot \mathit{up}_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \left( \mathrm{ru}_{\xi,t,g} \text{ is defined} \vee \mathrm{ru}^{\mathrm{up}}_{\xi,g} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{0}_{\xi,g} = 0 \vee \mathrm{p}^{0}_{\xi,g} \text{ is defined} \right) \right) \wedge \mathrm{on}_{t,g}
```

**`Generator_p_ramp_limit_down_run_big_m`**

```math
\overleftarrow{p}_{\xi,t,g} - p_{\xi,t,g} \le \widetilde{\mathrm{rd}}_{\xi,t,g} \cdot P_{g} + \mathrm{M}_{\xi,g} - \mathrm{M}_{\xi,g} \cdot u_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \left( \mathrm{rd}_{\xi,t,g} \text{ is defined} \vee \mathrm{rd}^{\mathrm{dn}}_{\xi,g} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{0}_{\xi,g} = 0 \vee \mathrm{p}^{0}_{\xi,g} \text{ is defined} \right) \right) \wedge \mathrm{on}_{t,g}
```

**`Generator_p_ramp_limit_down_shut_big_m`**

```math
\overleftarrow{p}_{\xi,t,g} - p_{\xi,t,g} \le \widetilde{\mathrm{rd}}^{\mathrm{dn}}_{\xi,g} \cdot P_{g} + \mathrm{M}_{\xi,g} - \mathrm{M}_{\xi,g} \cdot \mathit{dn}_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \left( \mathrm{rd}_{\xi,t,g} \text{ is defined} \vee \mathrm{rd}^{\mathrm{dn}}_{\xi,g} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{0}_{\xi,g} = 0 \vee \mathrm{p}^{0}_{\xi,g} \text{ is defined} \right) \right) \wedge \mathrm{on}_{t,g}
```

**`Generator_p_ramp_limit_up`**

```math
p_{\xi,t,g} - \overleftarrow{p}_{\xi,t,g} \le \Delta^{+}_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \left( \mathrm{ru}_{\xi,t,g} \text{ is defined} \vee \mathrm{ru}^{\mathrm{up}}_{\xi,g} \text{ is defined} \right) \wedge \neg \left( \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{0}_{\xi,g} = 0 \vee \mathrm{p}^{0}_{\xi,g} \text{ is defined} \right) \right) \wedge \mathrm{on}_{t,g}
```

**`Generator_p_ramp_limit_down`**

```math
\overleftarrow{p}_{\xi,t,g} - p_{\xi,t,g} \le \Delta^{-}_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \left( \mathrm{rd}_{\xi,t,g} \text{ is defined} \vee \mathrm{rd}^{\mathrm{dn}}_{\xi,g} \text{ is defined} \right) \wedge \neg \left( \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{0}_{\xi,g} = 0 \vee \mathrm{p}^{0}_{\xi,g} \text{ is defined} \right) \right) \wedge \mathrm{on}_{t,g}
```

#### Definitions

**`Generator_previous_p`**

```math
\overleftarrow{p}_{\xi,t,g} = \begin{cases} \mathrm{u}^{0}_{\xi,g} \cdot \mathrm{p}^{0}_{\xi,g} & \text{if } \mathrm{pos}(t) = 0 \\ p_{\xi,t - 1,g} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G}
```

**`Generator_ramp_up_rate`**

```math
\widetilde{\mathrm{ru}}_{\xi,t,g} = \begin{cases} \mathrm{ru}_{\xi,t,g} & \text{if } \mathrm{ru}_{\xi,t,g} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G}
```

**`Generator_ramp_down_rate`**

```math
\widetilde{\mathrm{rd}}_{\xi,t,g} = \begin{cases} \mathrm{rd}_{\xi,t,g} & \text{if } \mathrm{rd}_{\xi,t,g} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G}
```

**`Generator_start_up_rate`**

```math
\widetilde{\mathrm{ru}}^{\mathrm{up}}_{\xi,g} = \begin{cases} \mathrm{ru}^{\mathrm{up}}_{\xi,g} & \text{if } \mathrm{ru}^{\mathrm{up}}_{\xi,g} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G}
```

**`Generator_shut_down_rate`**

```math
\widetilde{\mathrm{rd}}^{\mathrm{dn}}_{\xi,g} = \begin{cases} \mathrm{rd}^{\mathrm{dn}}_{\xi,g} & \text{if } \mathrm{rd}^{\mathrm{dn}}_{\xi,g} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G}
```

**`Generator_ramp_up_allowance`**

```math
\Delta^{+}_{\xi,t,g} = \begin{cases} \widetilde{\mathrm{ru}}_{\xi,t,g} \cdot \widehat{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} \cdot \overleftarrow{u}_{\xi,t,g} + \widetilde{\mathrm{ru}}^{\mathrm{up}}_{\xi,g} \cdot \widehat{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} \cdot \left( u_{\xi,t,g} - \overleftarrow{u}_{\xi,t,g} \right) & \text{if } \mathrm{com}_{g} \\ \widetilde{\mathrm{ru}}_{\xi,t,g} \cdot \widetilde{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G}
```

**`Generator_ramp_down_allowance`**

```math
\Delta^{-}_{\xi,t,g} = \begin{cases} \widetilde{\mathrm{rd}}_{\xi,t,g} \cdot \widehat{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} \cdot u_{\xi,t,g} + \widetilde{\mathrm{rd}}^{\mathrm{dn}}_{\xi,g} \cdot \widehat{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} \cdot \left( \overleftarrow{u}_{\xi,t,g} - u_{\xi,t,g} \right) & \text{if } \mathrm{com}_{g} \\ \widetilde{\mathrm{rd}}_{\xi,t,g} \cdot \widetilde{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Assumptions

**`Generator_came_in_running_unless_committable`**

```math
\mathrm{u}^{0}_{\xi,g} = 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \neg \mathrm{com}_{g} \wedge \left( \mathrm{ru}_{\xi,t,g} \text{ is defined} \vee \mathrm{rd}_{\xi,t,g} \text{ is defined} \right)
```
<!-- gallery:end -->
