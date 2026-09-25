<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Links, the maintenance

One of the [24 fragments](index.md) of `examples/pypsa.yaml`: PyPSA's `Link`, the maintenance rows. It reads `Link_active`, `Link_committable`, `Link_p_nom_ext`, `Link_p_nom_extendable`, `Link_p_nom_max`, `Link_p_nom_min` and 3 more under [`given`](../../reference/language/declarations.md#given).

<!-- gallery:begin -->
```yaml
dimensions:
  scenario:
    description: the futures dispatch is chosen in, each with a weight
  snapshot:
    description: dispatch periods
    dtype: datetime
  link:
    description: controllable connections, each from one bus to the buses it delivers to

relations:
  Link_maintenance_cover:
    description: >-
      the snapshots a maintenance event covers, by the snapshot it starts in —
      in a scenario, the start and the snapshots after it, until their
      generator weightings reach that scenario's `maintenance_duration`, data prep; no
      rows for a link that is
      not maintainable
    key: { scenario: scenario, link: link, start: snapshot, covered: snapshot }

parameters:
  Link_maintainable:
    description: >-
      whether a link must be taken off for maintenance within the horizon — in
      any scenario, as PyPSA takes the union over them (`components.py:1016-1019`)
    dims: [link]
    dtype: bool
  Link_maintenance_pu:
    description: the share of the build a maintenance event takes off
    dims: [scenario, link]
  Link_maintenance_events:
    description: how many maintenance events the horizon holds
    dims: [scenario, link]
    dtype: int
  Link_maintenance_duration:
    description: >-
      the hours of generator weightings one maintenance event covers —
      PyPSA's `maintenance_duration`; no value where the link is not
      maintainable. No row reads it: data prep turns it into
      `Link_maintenance_cover` and `Link_maintenance_start_blocked`, and the
      assumptions hold it to the horizon
    dims: [scenario, link]
  Link_maintenance_start_blocked:
    description: >-
      true where no maintenance event may start, because the snapshots it
      would cover run past the end of the horizon or into one the link does
      not stand in — PyPSA's `active & ~valid`, from `maintenance_duration`
      and the generator weightings, data prep
    dims: [scenario, snapshot, link]
    dtype: bool

variables:
  Link_maintenance:
    description: >-
      `Link-maintenance` — whether a maintainable link is in maintenance:
      continuous, and one exactly where an event covers the snapshot
    dims: [scenario, snapshot, link]
    where: Link_maintainable AND Link_active
    absence: zero
    bounds:
      lower: 0
      upper: 1
  Link_maintenance_start:
    description: "`Link-maintenance_start` — whether a maintenance event starts in this snapshot"
    dims: [scenario, snapshot, link]
    where: Link_maintainable AND Link_active
    absence: zero
    domain: binary
  Link_maintenance_capacity:
    description: >-
      `Link-maintenance_capacity` — the chosen build while in maintenance, zero
      otherwise: the product the `maintcap` rows linearize
    dims: [scenario, snapshot, link]
    where: >-
      Link_maintainable AND Link_p_nom_extendable
      AND NOT (Link_committable AND Link_p_nom_mod > 0) AND Link_active
    absence: zero
    bounds:
      lower: 0
  Link_maintenance_status:
    description: >-
      `Link-maintenance_status` — the status while in maintenance, zero
      otherwise: the product the `maint-status` rows linearize, so a unit in
      maintenance may also be off
    dims: [scenario, snapshot, link]
    where: >-
      Link_maintainable AND Link_committable
      AND NOT (Link_p_nom_extendable AND NOT (Link_p_nom_mod > 0)) AND Link_active
    absence: zero
    bounds:
      lower: 0

given:
  parameters:
    Link_p_nom_extendable: { dims: [link], dtype: bool }
    Link_committable: { dims: [link], dtype: bool }
    Link_p_nom_mod: { dims: [link] }
    Link_active: { dims: [snapshot, link], dtype: bool }
    snapshot_weightings_generators: { dims: [snapshot] }
    Link_p_nom_min: { dims: [scenario, link] }
    Link_p_nom_max: { dims: [scenario, link] }
  variables:
    Link_status: { dims: [scenario, snapshot, link], domain: integer }
    Link_p_nom_ext: { dims: [link] }

constraints:
  Link_maint_event_count:
    description: "`Link-maint-event-count` — a maintainable link holds its number of maintenance events over the horizon"
    dims: [scenario, link]
    where: Link_maintainable
    expression: sum(Link_maintenance_start, over=snapshot) == Link_maintenance_events
  Link_maint_window:
    description: >-
      `Link-maint-window` — a link is in maintenance exactly where an event it
      started covers the snapshot; two events do not overlap, since the
      maintenance status is at most one
    dims: [scenario, snapshot, link]
    where: Link_maintainable AND Link_active
    expression: Link_maintenance == sum(Link_maintenance_start, by=Link_maintenance_cover, over=start, into=covered)
  Link_maint_start_horizon:
    description: "`Link-maint-start-horizon` — no event starts where it could not run its whole duration"
    dims: [scenario, snapshot, link]
    where: Link_maintainable AND Link_active AND Link_maintenance_start_blocked
    expression: Link_maintenance_start == 0
  Link_maintcap_upper:
    description: >-
      `Link-maintcap_upper` — the build taken off is at most the chosen build in
      maintenance, and at most the build less its floor out of it
    dims: [scenario, snapshot, link]
    where: Link_maintainable AND Link_p_nom_extendable AND NOT (Link_committable AND Link_p_nom_mod > 0) AND Link_active
    expression: Link_maintenance_capacity <= Link_p_nom_ext - Link_p_nom_min * (1 - Link_maintenance)
  Link_maintcap_upper_nommax:
    description: "`Link-maintcap_upper_nommax` — out of maintenance, no build is taken off"
    dims: [scenario, snapshot, link]
    where: Link_maintainable AND Link_p_nom_extendable AND NOT (Link_committable AND Link_p_nom_mod > 0) AND Link_active
    expression: Link_maintenance_capacity <= Link_p_nom_max * Link_maintenance
  Link_maintcap_lower_nommax:
    description: "`Link-maintcap_lower_nommax` — in maintenance, the whole chosen build is taken off"
    dims: [scenario, snapshot, link]
    where: Link_maintainable AND Link_p_nom_extendable AND NOT (Link_committable AND Link_p_nom_mod > 0) AND Link_active
    expression: Link_maintenance_capacity >= Link_p_nom_ext - Link_p_nom_max * (1 - Link_maintenance)
  Link_maintcap_lower_nommin:
    description: "`Link-maintcap_lower_nommin` — in maintenance, at least the floor of the build is taken off"
    dims: [scenario, snapshot, link]
    where: Link_maintainable AND Link_p_nom_extendable AND NOT (Link_committable AND Link_p_nom_mod > 0) AND Link_active AND Link_p_nom_min > 0
    expression: Link_maintenance_capacity >= Link_p_nom_min * Link_maintenance
  Link_maint_status_le_status:
    description: "`Link-maint-status-le-status` — the status in maintenance is at most the status"
    dims: [scenario, snapshot, link]
    where: Link_maintainable AND Link_committable AND NOT Link_p_nom_extendable AND Link_active
    expression: Link_maintenance_status <= Link_status
  Link_maint_status_le_maint:
    description: "`Link-maint-status-le-maint` — out of maintenance, the status in maintenance is zero"
    dims: [scenario, snapshot, link]
    where: Link_maintainable AND Link_committable AND NOT Link_p_nom_extendable AND Link_active
    expression: Link_maintenance_status <= Link_maintenance
  Link_maint_status_lb:
    description: "`Link-maint-status-lb` — on and in maintenance, the status in maintenance is one"
    dims: [scenario, snapshot, link]
    where: Link_maintainable AND Link_committable AND NOT Link_p_nom_extendable AND Link_active
    expression: Link_maintenance_status >= Link_status + Link_maintenance - 1
  Link_maint_modstatus_le_status:
    description: "`Link-maint-modstatus-le-status` — the modules on in maintenance are at most the modules on"
    dims: [scenario, snapshot, link]
    where: Link_maintainable AND Link_committable AND Link_p_nom_mod > 0 AND Link_active
    expression: Link_maintenance_status <= Link_status
  Link_maint_modstatus_le_maint:
    description: >-
      `Link-maint-modstatus-le-maint` — out of maintenance, no module is on in
      maintenance; in it, at most the modules the build cap holds
    dims: [scenario, snapshot, link]
    where: Link_maintainable AND Link_committable AND Link_p_nom_mod > 0 AND Link_active
    expression: Link_maintenance_status <= Link_p_nom_max / Link_p_nom_mod * Link_maintenance
  Link_maint_modstatus_lb:
    description: "`Link-maint-modstatus-lb` — in maintenance, every module on is on in maintenance"
    dims: [scenario, snapshot, link]
    where: Link_maintainable AND Link_committable AND Link_p_nom_mod > 0 AND Link_active
    expression: Link_maintenance_status >= Link_status - Link_p_nom_max / Link_p_nom_mod * (1 - Link_maintenance)

assumptions:
  Link_maintenance_events_positive:
    holds: "Link_maintenance_events > 0"
    where: "Link_maintainable"
    description: >-
      a maintainable link with no event schedules no maintenance —
      PyPSA refuses it (`consistency.py:1516`)
  Link_maintenance_duration_positive:
    holds: "Link_maintenance_duration > 0"
    where: "Link_maintainable"
    description: >-
      an event that covers no hours is no maintenance window — PyPSA
      refuses it (`consistency.py:1506`)
  Link_maintenance_duration_fits_the_horizon:
    holds: "Link_maintenance_duration <= sum(snapshot_weightings_generators, over=snapshot)"
    where: "Link_maintainable"
    description: >-
      one event longer than the horizon, in generator weightings, blocks
      every start and makes the event count infeasible — PyPSA refuses it
      (`consistency.py:1527`)
  Link_maintenance_events_fit_the_horizon:
    holds: "Link_maintenance_duration * Link_maintenance_events <= sum(snapshot_weightings_generators, over=snapshot)"
    where: "Link_maintainable"
    description: >-
      the events together longer than the horizon, in generator
      weightings, cannot all be scheduled — PyPSA refuses it
      (`consistency.py:1539`)
  Link_maintenance_build_cap_is_finite:
    holds: "Link_p_nom_max < inf"
    where: "Link_maintainable AND Link_p_nom_extendable"
    description: >-
      the `maintcap` rows hold the chosen build in maintenance against
      `p_nom_max`, so an infinite cap is an infinite coefficient — PyPSA
      refuses it (`consistency.py:1551`)
  Link_maintenance_module_count_is_finite:
    holds: "Link_p_nom_max < inf"
    where: "Link_maintainable AND Link_committable AND NOT Link_p_nom_extendable AND Link_p_nom_mod > 0"
    description: >-
      the `maint-modstatus` rows bound the modules on in maintenance by
      `p_nom_max / p_nom_mod`, so an infinite cap is an infinite
      coefficient. PyPSA does not check it, and HiGHS refuses the model
      (`constraints.py:500-503`)
```

#### Sets

| Symbol | Meaning |
|---|---|
| $`\Xi`$ | index $`\xi`$ — `scenario` with $`\mathrm{Link\_maintenance\_cover} \subseteq \Xi \times \mathcal{L} \times \mathcal{T} \times \mathcal{T}`$ — the futures dispatch is chosen in, each with a weight |
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` with $`\mathrm{Link\_maintenance\_cover} \subseteq \Xi \times \mathcal{L} \times \mathcal{T} \times \mathcal{T}`$ — dispatch periods |
| $`\mathcal{L}`$ | index $`l`$ — `link` with $`\mathrm{Link\_maintenance\_cover} \subseteq \Xi \times \mathcal{L} \times \mathcal{T} \times \mathcal{T}`$ — controllable connections, each from one bus to the buses it delivers to |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{mnt}^{f}`$ | `Link_maintainable` over $`\mathcal{L}`$ — whether a link must be taken off for maintenance within the horizon — in any scenario, as PyPSA takes the union over them (`components.py:1016-1019`) |
| $`\gamma^{f}`$ | `Link_maintenance_pu` over $`\Xi \times \mathcal{L}`$ — the share of the build a maintenance event takes off |
| $`\mathrm{n}^{f,\mathrm{mnt}}`$ | `Link_maintenance_events` over $`\Xi \times \mathcal{L}`$ — how many maintenance events the horizon holds |
| $`\tau^{f,\mathrm{mnt}}`$ | `Link_maintenance_duration` over $`\Xi \times \mathcal{L}`$ — the hours of generator weightings one maintenance event covers — PyPSA's `maintenance_duration`; no value where the link is not maintainable. No row reads it: data prep turns it into `Link_maintenance_cover` and `Link_maintenance_start_blocked`, and the assumptions hold it to the horizon |
| $`\mathrm{blk}^{f}`$ | `Link_maintenance_start_blocked` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — true where no maintenance event may start, because the snapshots it would cover run past the end of the horizon or into one the link does not stand in — PyPSA's `active & ~valid`, from `maintenance_duration` and the generator weightings, data prep |

#### Variables

| Symbol | Meaning |
|---|---|
| $`\mu^{f}`$ | `Link_maintenance` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — `Link-maintenance` — whether a maintainable link is in maintenance: continuous, and one exactly where an event covers the snapshot |
| $`\mu^{f,\mathrm{up}}`$ | `Link_maintenance_start` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — `Link-maintenance_start` — whether a maintenance event starts in this snapshot |
| $`\mu^{f,\mathrm{nom}}`$ | `Link_maintenance_capacity` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — `Link-maintenance_capacity` — the chosen build while in maintenance, zero otherwise: the product the `maintcap` rows linearize |
| $`\mu^{f,u}`$ | `Link_maintenance_status` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — `Link-maintenance_status` — the status while in maintenance, zero otherwise: the product the `maint-status` rows linearize, so a unit in maintenance may also be off |

#### Given

| Symbol | Meaning |
|---|---|
| $`\mathrm{ext}^{f}`$ | `Link_p_nom_extendable` over $`\mathcal{L}`$, data another file declares |
| $`\mathrm{com}^{f}`$ | `Link_committable` over $`\mathcal{L}`$, data another file declares |
| $`\mathrm{f}^{\mathrm{mod}}`$ | `Link_p_nom_mod` over $`\mathcal{L}`$, data another file declares |
| $`\mathrm{on}^{f}`$ | `Link_active` over $`\mathcal{T} \times \mathcal{L}`$, data another file declares |
| $`\mathrm{w}^{\mathrm{gen}}`$ | `snapshot_weightings_generators` over $`\mathcal{T}`$, data another file declares |
| $`\underline{\mathrm{f}}^{\mathrm{nom}}`$ | `Link_p_nom_min` over $`\Xi \times \mathcal{L}`$, data another file declares |
| $`\overline{\mathrm{f}}^{\mathrm{nom}}`$ | `Link_p_nom_max` over $`\Xi \times \mathcal{L}`$, data another file declares |
| $`u^{f}`$ | `Link_status` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ |
| $`F`$ | `Link_p_nom_ext` over $`\mathcal{L}`$ |

#### Subject to

**`Link_maint_event_count`**

```math
\sum_{t \in \mathcal{T}} \mu^{f,\mathrm{up}}_{\xi,t,l} = \mathrm{n}^{f,\mathrm{mnt}}_{\xi,l} \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l}
```

**`Link_maint_window`**

```math
\mu^{f}_{\xi,t,l} = \sum_{t' \in \mathcal{T} \,:\, \left( \xi,\ l,\ t',\ t \right) \in \mathrm{Link\_maintenance\_cover}} \mu^{f,\mathrm{up}}_{\xi,t',l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_maint_start_horizon`**

```math
\mu^{f,\mathrm{up}}_{\xi,t,l} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l} \wedge \mathrm{blk}^{f}_{\xi,t,l}
```

**`Link_maintcap_upper`**

```math
\mu^{f,\mathrm{nom}}_{\xi,t,l} \le F_{l} - \underline{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} \cdot \left( 1 - \mu^{f}_{\xi,t,l} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{com}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_maintcap_upper_nommax`**

```math
\mu^{f,\mathrm{nom}}_{\xi,t,l} \le \overline{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} \cdot \mu^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{com}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_maintcap_lower_nommax`**

```math
\mu^{f,\mathrm{nom}}_{\xi,t,l} \ge F_{l} - \overline{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} \cdot \left( 1 - \mu^{f}_{\xi,t,l} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{com}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_maintcap_lower_nommin`**

```math
\mu^{f,\mathrm{nom}}_{\xi,t,l} \ge \underline{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} \cdot \mu^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{com}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \mathrm{on}^{f}_{t,l} \wedge \underline{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} > 0
```

**`Link_maint_status_le_status`**

```math
\mu^{f,u}_{\xi,t,l} \le u^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{com}^{f}_{l} \wedge \neg \mathrm{ext}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_maint_status_le_maint`**

```math
\mu^{f,u}_{\xi,t,l} \le \mu^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{com}^{f}_{l} \wedge \neg \mathrm{ext}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_maint_status_lb`**

```math
\mu^{f,u}_{\xi,t,l} \ge u^{f}_{\xi,t,l} + \mu^{f}_{\xi,t,l} - 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{com}^{f}_{l} \wedge \neg \mathrm{ext}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_maint_modstatus_le_status`**

```math
\mu^{f,u}_{\xi,t,l} \le u^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{com}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_maint_modstatus_le_maint`**

```math
\mu^{f,u}_{\xi,t,l} \le \frac{\overline{\mathrm{f}}^{\mathrm{nom}}_{\xi,l}}{\mathrm{f}^{\mathrm{mod}}_{l}} \cdot \mu^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{com}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_maint_modstatus_lb`**

```math
\mu^{f,u}_{\xi,t,l} \ge u^{f}_{\xi,t,l} - \frac{\overline{\mathrm{f}}^{\mathrm{nom}}_{\xi,l}}{\mathrm{f}^{\mathrm{mod}}_{l}} \cdot \left( 1 - \mu^{f}_{\xi,t,l} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{com}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \wedge \mathrm{on}^{f}_{t,l}
```

#### Variable domains

**`Link_maintenance`**

```math
0 \le \mu^{f}_{\xi,t,l} \le 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_maintenance_start`**

```math
\mu^{f,\mathrm{up}}_{\xi,t,l} \in \{0, 1\} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_maintenance_capacity`**

```math
\mu^{f,\mathrm{nom}}_{\xi,t,l} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{com}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_maintenance_status`**

```math
\mu^{f,u}_{\xi,t,l} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{com}^{f}_{l} \wedge \neg \left( \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \right) \wedge \mathrm{on}^{f}_{t,l}
```

#### Assumptions

**`Link_maintenance_events_positive`**

```math
\mathrm{n}^{f,\mathrm{mnt}}_{\xi,l} > 0 \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l}
```

**`Link_maintenance_duration_positive`**

```math
\tau^{f,\mathrm{mnt}}_{\xi,l} > 0 \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l}
```

**`Link_maintenance_duration_fits_the_horizon`**

```math
\tau^{f,\mathrm{mnt}}_{\xi,l} \le \sum_{t \in \mathcal{T}} \mathrm{w}^{\mathrm{gen}}_{t} \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l}
```

**`Link_maintenance_events_fit_the_horizon`**

```math
\tau^{f,\mathrm{mnt}}_{\xi,l} \cdot \mathrm{n}^{f,\mathrm{mnt}}_{\xi,l} \le \sum_{t \in \mathcal{T}} \mathrm{w}^{\mathrm{gen}}_{t} \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l}
```

**`Link_maintenance_build_cap_is_finite`**

```math
\overline{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} < \infty \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{ext}^{f}_{l}
```

**`Link_maintenance_module_count_is_finite`**

```math
\overline{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} < \infty \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{com}^{f}_{l} \wedge \neg \mathrm{ext}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0
```
<!-- gallery:end -->
