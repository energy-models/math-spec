<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Generators, the maintenance

One of the [24 fragments](index.md) of `examples/pypsa.yaml`: PyPSA's `Generator`, the maintenance rows. It reads `Generator_active`, `Generator_committable`, `Generator_p_nom_ext`, `Generator_p_nom_extendable`, `Generator_p_nom_max`, `Generator_p_nom_min` and 3 more under [`given`](../../reference/language/declarations.md#given).

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

relations:
  Generator_maintenance_cover:
    description: >-
      the snapshots a maintenance event covers, by the snapshot it starts in —
      in a scenario, the start and the snapshots after it, until their
      generator weightings reach that scenario's `maintenance_duration`, data prep; no
      rows for a generator that is
      not maintainable
    key: { scenario: scenario, generator: generator, start: snapshot, covered: snapshot }

parameters:
  Generator_maintainable:
    description: >-
      whether a generator must be taken off for maintenance within the horizon — in
      any scenario, as PyPSA takes the union over them (`components.py:1016-1019`)
    dims: [generator]
    dtype: bool
  Generator_maintenance_pu:
    description: the share of the build a maintenance event takes off
    dims: [scenario, generator]
  Generator_maintenance_events:
    description: how many maintenance events the horizon holds
    dims: [scenario, generator]
    dtype: int
  Generator_maintenance_duration:
    description: >-
      the hours of generator weightings one maintenance event covers —
      PyPSA's `maintenance_duration`; no value where the generator is not
      maintainable. No row reads it: data prep turns it into
      `Generator_maintenance_cover` and `Generator_maintenance_start_blocked`, and the
      assumptions hold it to the horizon
    dims: [scenario, generator]
  Generator_maintenance_start_blocked:
    description: >-
      true where no maintenance event may start, because the snapshots it
      would cover run past the end of the horizon or into one the generator does
      not stand in — PyPSA's `active & ~valid`, from `maintenance_duration`
      and the generator weightings, data prep
    dims: [scenario, snapshot, generator]
    dtype: bool

variables:
  Generator_maintenance:
    description: >-
      `Generator-maintenance` — whether a maintainable generator is in maintenance:
      continuous, and one exactly where an event covers the snapshot
    dims: [scenario, snapshot, generator]
    where: Generator_maintainable AND Generator_active
    absence: zero
    bounds:
      lower: 0
      upper: 1
  Generator_maintenance_start:
    description: "`Generator-maintenance_start` — whether a maintenance event starts in this snapshot"
    dims: [scenario, snapshot, generator]
    where: Generator_maintainable AND Generator_active
    absence: zero
    domain: binary
  Generator_maintenance_capacity:
    description: >-
      `Generator-maintenance_capacity` — the chosen build while in maintenance, zero
      otherwise: the product the `maintcap` rows linearize
    dims: [scenario, snapshot, generator]
    where: >-
      Generator_maintainable AND Generator_p_nom_extendable
      AND NOT (Generator_committable AND Generator_p_nom_mod > 0) AND Generator_active
    absence: zero
    bounds:
      lower: 0
  Generator_maintenance_status:
    description: >-
      `Generator-maintenance_status` — the status while in maintenance, zero
      otherwise: the product the `maint-status` rows linearize, so a unit in
      maintenance may also be off
    dims: [scenario, snapshot, generator]
    where: >-
      Generator_maintainable AND Generator_committable
      AND NOT (Generator_p_nom_extendable AND NOT (Generator_p_nom_mod > 0)) AND Generator_active
    absence: zero
    bounds:
      lower: 0

given:
  parameters:
    Generator_p_nom_extendable: { dims: [generator], dtype: bool }
    Generator_committable: { dims: [generator], dtype: bool }
    Generator_p_nom_mod: { dims: [generator] }
    Generator_active: { dims: [snapshot, generator], dtype: bool }
    snapshot_weightings_generators: { dims: [snapshot] }
    Generator_p_nom_min: { dims: [scenario, generator] }
    Generator_p_nom_max: { dims: [scenario, generator] }
  variables:
    Generator_status: { dims: [scenario, snapshot, generator], domain: integer }
    Generator_p_nom_ext: { dims: [generator] }

constraints:
  Generator_maint_event_count:
    description: "`Generator-maint-event-count` — a maintainable generator holds its number of maintenance events over the horizon"
    dims: [scenario, generator]
    where: Generator_maintainable
    expression: sum(Generator_maintenance_start, over=snapshot) == Generator_maintenance_events
  Generator_maint_window:
    description: >-
      `Generator-maint-window` — a generator is in maintenance exactly where an event it
      started covers the snapshot; two events do not overlap, since the
      maintenance status is at most one
    dims: [scenario, snapshot, generator]
    where: Generator_maintainable AND Generator_active
    expression: Generator_maintenance == sum(Generator_maintenance_start, by=Generator_maintenance_cover, over=start, into=covered)
  Generator_maint_start_horizon:
    description: "`Generator-maint-start-horizon` — no event starts where it could not run its whole duration"
    dims: [scenario, snapshot, generator]
    where: Generator_maintainable AND Generator_active AND Generator_maintenance_start_blocked
    expression: Generator_maintenance_start == 0
  Generator_maintcap_upper:
    description: >-
      `Generator-maintcap_upper` — the build taken off is at most the chosen build in
      maintenance, and at most the build less its floor out of it
    dims: [scenario, snapshot, generator]
    where: Generator_maintainable AND Generator_p_nom_extendable AND NOT (Generator_committable AND Generator_p_nom_mod > 0) AND Generator_active
    expression: Generator_maintenance_capacity <= Generator_p_nom_ext - Generator_p_nom_min * (1 - Generator_maintenance)
  Generator_maintcap_upper_nommax:
    description: "`Generator-maintcap_upper_nommax` — out of maintenance, no build is taken off"
    dims: [scenario, snapshot, generator]
    where: Generator_maintainable AND Generator_p_nom_extendable AND NOT (Generator_committable AND Generator_p_nom_mod > 0) AND Generator_active
    expression: Generator_maintenance_capacity <= Generator_p_nom_max * Generator_maintenance
  Generator_maintcap_lower_nommax:
    description: "`Generator-maintcap_lower_nommax` — in maintenance, the whole chosen build is taken off"
    dims: [scenario, snapshot, generator]
    where: Generator_maintainable AND Generator_p_nom_extendable AND NOT (Generator_committable AND Generator_p_nom_mod > 0) AND Generator_active
    expression: Generator_maintenance_capacity >= Generator_p_nom_ext - Generator_p_nom_max * (1 - Generator_maintenance)
  Generator_maintcap_lower_nommin:
    description: "`Generator-maintcap_lower_nommin` — in maintenance, at least the floor of the build is taken off"
    dims: [scenario, snapshot, generator]
    where: Generator_maintainable AND Generator_p_nom_extendable AND NOT (Generator_committable AND Generator_p_nom_mod > 0) AND Generator_active AND Generator_p_nom_min > 0
    expression: Generator_maintenance_capacity >= Generator_p_nom_min * Generator_maintenance
  Generator_maint_status_le_status:
    description: "`Generator-maint-status-le-status` — the status in maintenance is at most the status"
    dims: [scenario, snapshot, generator]
    where: Generator_maintainable AND Generator_committable AND NOT Generator_p_nom_extendable AND Generator_active
    expression: Generator_maintenance_status <= Generator_status
  Generator_maint_status_le_maint:
    description: "`Generator-maint-status-le-maint` — out of maintenance, the status in maintenance is zero"
    dims: [scenario, snapshot, generator]
    where: Generator_maintainable AND Generator_committable AND NOT Generator_p_nom_extendable AND Generator_active
    expression: Generator_maintenance_status <= Generator_maintenance
  Generator_maint_status_lb:
    description: "`Generator-maint-status-lb` — on and in maintenance, the status in maintenance is one"
    dims: [scenario, snapshot, generator]
    where: Generator_maintainable AND Generator_committable AND NOT Generator_p_nom_extendable AND Generator_active
    expression: Generator_maintenance_status >= Generator_status + Generator_maintenance - 1
  Generator_maint_modstatus_le_status:
    description: "`Generator-maint-modstatus-le-status` — the modules on in maintenance are at most the modules on"
    dims: [scenario, snapshot, generator]
    where: Generator_maintainable AND Generator_committable AND Generator_p_nom_mod > 0 AND Generator_active
    expression: Generator_maintenance_status <= Generator_status
  Generator_maint_modstatus_le_maint:
    description: >-
      `Generator-maint-modstatus-le-maint` — out of maintenance, no module is on in
      maintenance; in it, at most the modules the build cap holds
    dims: [scenario, snapshot, generator]
    where: Generator_maintainable AND Generator_committable AND Generator_p_nom_mod > 0 AND Generator_active
    expression: Generator_maintenance_status <= Generator_p_nom_max / Generator_p_nom_mod * Generator_maintenance
  Generator_maint_modstatus_lb:
    description: "`Generator-maint-modstatus-lb` — in maintenance, every module on is on in maintenance"
    dims: [scenario, snapshot, generator]
    where: Generator_maintainable AND Generator_committable AND Generator_p_nom_mod > 0 AND Generator_active
    expression: Generator_maintenance_status >= Generator_status - Generator_p_nom_max / Generator_p_nom_mod * (1 - Generator_maintenance)

assumptions:
  Generator_maintenance_events_positive:
    holds: "Generator_maintenance_events > 0"
    where: "Generator_maintainable"
    description: >-
      a maintainable generator with no event schedules no maintenance —
      PyPSA refuses it (`consistency.py:1516`)
  Generator_maintenance_duration_positive:
    holds: "Generator_maintenance_duration > 0"
    where: "Generator_maintainable"
    description: >-
      an event that covers no hours is no maintenance window — PyPSA
      refuses it (`consistency.py:1506`)
  Generator_maintenance_duration_fits_the_horizon:
    holds: "Generator_maintenance_duration <= sum(snapshot_weightings_generators, over=snapshot)"
    where: "Generator_maintainable"
    description: >-
      one event longer than the horizon, in generator weightings, blocks
      every start and makes the event count infeasible — PyPSA refuses it
      (`consistency.py:1527`)
  Generator_maintenance_events_fit_the_horizon:
    holds: "Generator_maintenance_duration * Generator_maintenance_events <= sum(snapshot_weightings_generators, over=snapshot)"
    where: "Generator_maintainable"
    description: >-
      the events together longer than the horizon, in generator
      weightings, cannot all be scheduled — PyPSA refuses it
      (`consistency.py:1539`)
  Generator_maintenance_build_cap_is_finite:
    holds: "Generator_p_nom_max < inf"
    where: "Generator_maintainable AND Generator_p_nom_extendable"
    description: >-
      the `maintcap` rows hold the chosen build in maintenance against
      `p_nom_max`, so an infinite cap is an infinite coefficient — PyPSA
      refuses it (`consistency.py:1551`)
  Generator_maintenance_module_count_is_finite:
    holds: "Generator_p_nom_max < inf"
    where: "Generator_maintainable AND Generator_committable AND NOT Generator_p_nom_extendable AND Generator_p_nom_mod > 0"
    description: >-
      the `maint-modstatus` rows bound the modules on in maintenance by
      `p_nom_max / p_nom_mod`, so an infinite cap is an infinite
      coefficient. PyPSA does not check it, and HiGHS refuses the model
      (`constraints.py:500-503`)
```

#### Sets

| Symbol | Meaning |
|---|---|
| $`\Xi`$ | index $`\xi`$ — `scenario` with $`\mathrm{Generator\_maintenance\_cover} \subseteq \Xi \times \mathcal{G} \times \mathcal{T} \times \mathcal{T}`$ — the futures dispatch is chosen in, each with a weight |
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` with $`\mathrm{Generator\_maintenance\_cover} \subseteq \Xi \times \mathcal{G} \times \mathcal{T} \times \mathcal{T}`$ — dispatch periods |
| $`\mathcal{G}`$ | index $`g`$ — `generator` with $`\mathrm{Generator\_maintenance\_cover} \subseteq \Xi \times \mathcal{G} \times \mathcal{T} \times \mathcal{T}`$ — generating units, each on one bus |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{mnt}`$ | `Generator_maintainable` over $`\mathcal{G}`$ — whether a generator must be taken off for maintenance within the horizon — in any scenario, as PyPSA takes the union over them (`components.py:1016-1019`) |
| $`\gamma`$ | `Generator_maintenance_pu` over $`\Xi \times \mathcal{G}`$ — the share of the build a maintenance event takes off |
| $`\mathrm{n}^{\mathrm{mnt}}`$ | `Generator_maintenance_events` over $`\Xi \times \mathcal{G}`$ — how many maintenance events the horizon holds |
| $`\tau^{\mathrm{mnt}}`$ | `Generator_maintenance_duration` over $`\Xi \times \mathcal{G}`$ — the hours of generator weightings one maintenance event covers — PyPSA's `maintenance_duration`; no value where the generator is not maintainable. No row reads it: data prep turns it into `Generator_maintenance_cover` and `Generator_maintenance_start_blocked`, and the assumptions hold it to the horizon |
| $`\mathrm{blk}`$ | `Generator_maintenance_start_blocked` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — true where no maintenance event may start, because the snapshots it would cover run past the end of the horizon or into one the generator does not stand in — PyPSA's `active & ~valid`, from `maintenance_duration` and the generator weightings, data prep |

#### Variables

| Symbol | Meaning |
|---|---|
| $`\mu`$ | `Generator_maintenance` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — `Generator-maintenance` — whether a maintainable generator is in maintenance: continuous, and one exactly where an event covers the snapshot |
| $`\mu^{\mathrm{up}}`$ | `Generator_maintenance_start` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — `Generator-maintenance_start` — whether a maintenance event starts in this snapshot |
| $`\mu^{\mathrm{nom}}`$ | `Generator_maintenance_capacity` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — `Generator-maintenance_capacity` — the chosen build while in maintenance, zero otherwise: the product the `maintcap` rows linearize |
| $`\mu^{u}`$ | `Generator_maintenance_status` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — `Generator-maintenance_status` — the status while in maintenance, zero otherwise: the product the `maint-status` rows linearize, so a unit in maintenance may also be off |

#### Given

| Symbol | Meaning |
|---|---|
| $`\mathrm{ext}`$ | `Generator_p_nom_extendable` over $`\mathcal{G}`$, data another file declares |
| $`\mathrm{com}`$ | `Generator_committable` over $`\mathcal{G}`$, data another file declares |
| $`\mathrm{p}^{\mathrm{mod}}`$ | `Generator_p_nom_mod` over $`\mathcal{G}`$, data another file declares |
| $`\mathrm{on}`$ | `Generator_active` over $`\mathcal{T} \times \mathcal{G}`$, data another file declares |
| $`\mathrm{w}^{\mathrm{gen}}`$ | `snapshot_weightings_generators` over $`\mathcal{T}`$, data another file declares |
| $`\underline{\mathrm{p}}^{\mathrm{nom}}`$ | `Generator_p_nom_min` over $`\Xi \times \mathcal{G}`$, data another file declares |
| $`\overline{\mathrm{p}}^{\mathrm{nom}}`$ | `Generator_p_nom_max` over $`\Xi \times \mathcal{G}`$, data another file declares |
| $`u`$ | `Generator_status` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ |
| $`P`$ | `Generator_p_nom_ext` over $`\mathcal{G}`$ |

#### Subject to

**`Generator_maint_event_count`**

```math
\sum_{t \in \mathcal{T}} \mu^{\mathrm{up}}_{\xi,t,g} = \mathrm{n}^{\mathrm{mnt}}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g}
```

**`Generator_maint_window`**

```math
\mu_{\xi,t,g} = \sum_{t' \in \mathcal{T} \,:\, \left( \xi,\ g,\ t',\ t \right) \in \mathrm{Generator\_maintenance\_cover}} \mu^{\mathrm{up}}_{\xi,t',g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{on}_{t,g}
```

**`Generator_maint_start_horizon`**

```math
\mu^{\mathrm{up}}_{\xi,t,g} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{on}_{t,g} \wedge \mathrm{blk}_{\xi,t,g}
```

**`Generator_maintcap_upper`**

```math
\mu^{\mathrm{nom}}_{\xi,t,g} \le P_{g} - \underline{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} \cdot \left( 1 - \mu_{\xi,t,g} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{com}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
```

**`Generator_maintcap_upper_nommax`**

```math
\mu^{\mathrm{nom}}_{\xi,t,g} \le \overline{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} \cdot \mu_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{com}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
```

**`Generator_maintcap_lower_nommax`**

```math
\mu^{\mathrm{nom}}_{\xi,t,g} \ge P_{g} - \overline{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} \cdot \left( 1 - \mu_{\xi,t,g} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{com}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
```

**`Generator_maintcap_lower_nommin`**

```math
\mu^{\mathrm{nom}}_{\xi,t,g} \ge \underline{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} \cdot \mu_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{com}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g} \wedge \underline{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} > 0
```

**`Generator_maint_status_le_status`**

```math
\mu^{u}_{\xi,t,g} \le u_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{com}_{g} \wedge \neg \mathrm{ext}_{g} \wedge \mathrm{on}_{t,g}
```

**`Generator_maint_status_le_maint`**

```math
\mu^{u}_{\xi,t,g} \le \mu_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{com}_{g} \wedge \neg \mathrm{ext}_{g} \wedge \mathrm{on}_{t,g}
```

**`Generator_maint_status_lb`**

```math
\mu^{u}_{\xi,t,g} \ge u_{\xi,t,g} + \mu_{\xi,t,g} - 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{com}_{g} \wedge \neg \mathrm{ext}_{g} \wedge \mathrm{on}_{t,g}
```

**`Generator_maint_modstatus_le_status`**

```math
\mu^{u}_{\xi,t,g} \le u_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{com}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \wedge \mathrm{on}_{t,g}
```

**`Generator_maint_modstatus_le_maint`**

```math
\mu^{u}_{\xi,t,g} \le \frac{\overline{\mathrm{p}}^{\mathrm{nom}}_{\xi,g}}{\mathrm{p}^{\mathrm{mod}}_{g}} \cdot \mu_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{com}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \wedge \mathrm{on}_{t,g}
```

**`Generator_maint_modstatus_lb`**

```math
\mu^{u}_{\xi,t,g} \ge u_{\xi,t,g} - \frac{\overline{\mathrm{p}}^{\mathrm{nom}}_{\xi,g}}{\mathrm{p}^{\mathrm{mod}}_{g}} \cdot \left( 1 - \mu_{\xi,t,g} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{com}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \wedge \mathrm{on}_{t,g}
```

#### Variable domains

**`Generator_maintenance`**

```math
0 \le \mu_{\xi,t,g} \le 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{on}_{t,g}
```

**`Generator_maintenance_start`**

```math
\mu^{\mathrm{up}}_{\xi,t,g} \in \{0, 1\} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{on}_{t,g}
```

**`Generator_maintenance_capacity`**

```math
\mu^{\mathrm{nom}}_{\xi,t,g} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{com}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
```

**`Generator_maintenance_status`**

```math
\mu^{u}_{\xi,t,g} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{com}_{g} \wedge \neg \left( \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \right) \wedge \mathrm{on}_{t,g}
```

#### Assumptions

**`Generator_maintenance_events_positive`**

```math
\mathrm{n}^{\mathrm{mnt}}_{\xi,g} > 0 \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g}
```

**`Generator_maintenance_duration_positive`**

```math
\tau^{\mathrm{mnt}}_{\xi,g} > 0 \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g}
```

**`Generator_maintenance_duration_fits_the_horizon`**

```math
\tau^{\mathrm{mnt}}_{\xi,g} \le \sum_{t \in \mathcal{T}} \mathrm{w}^{\mathrm{gen}}_{t} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g}
```

**`Generator_maintenance_events_fit_the_horizon`**

```math
\tau^{\mathrm{mnt}}_{\xi,g} \cdot \mathrm{n}^{\mathrm{mnt}}_{\xi,g} \le \sum_{t \in \mathcal{T}} \mathrm{w}^{\mathrm{gen}}_{t} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g}
```

**`Generator_maintenance_build_cap_is_finite`**

```math
\overline{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} < \infty \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{ext}_{g}
```

**`Generator_maintenance_module_count_is_finite`**

```math
\overline{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} < \infty \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{com}_{g} \wedge \neg \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0
```
<!-- gallery:end -->
