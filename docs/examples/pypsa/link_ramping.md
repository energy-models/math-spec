<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Links, the ramping

One of the [24 fragments](index.md) of `examples/pypsa.yaml`: PyPSA's `Link`, the ramping rows. It reads `Link_active`, `Link_big_m`, `Link_committable`, `Link_p`, `Link_p_nom_committed`, `Link_p_nom_effective` and 8 more under [`given`](../../reference/language/declarations.md#given).

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
  period:
    description: investment periods — PyPSA's `investment_periods`
    dtype: int

relations:
  snapshot_period:
    description: the investment period a snapshot falls in
    key: snapshot
    values: period

parameters:
  Link_ramp_limit_up:
    description: most a link may raise its flow between snapshots, per unit of nominal power; no value means no limit — read at the later of the two snapshots, so the limit may change over time
    dims: [scenario, snapshot, link]
  Link_ramp_limit_down:
    description: most a link may lower its flow between snapshots, per unit of nominal power; no value means no limit — read at the later of the two snapshots, so the limit may change over time
    dims: [scenario, snapshot, link]
  Link_ramp_limit_start_up:
    description: most flow in the snapshot a link starts, per unit of nominal power
    dims: [scenario, link]
  Link_ramp_limit_shut_down:
    description: most flow in the snapshot before a link stops, per unit of nominal power
    dims: [scenario, link]
  Link_p_init:
    description: >-
      the flow a link brought into the horizon — PyPSA's `p_init`, read
      only where the link came in running; no value means it is unknown, so
      the link carries no ramp row at the first snapshot
    dims: [scenario, link]

given:
  parameters:
    Link_p_nom_extendable: { dims: [link], dtype: bool }
    Link_committable: { dims: [link], dtype: bool }
    Link_status_initial: { dims: [scenario, link], dtype: int }
    Link_p_nom_mod: { dims: [link] }
    Link_big_m: { dims: [scenario, link] }
    Link_active: { dims: [snapshot, link], dtype: bool }
  variables:
    Link_p: { dims: [scenario, snapshot, link] }
    Link_status: { dims: [scenario, snapshot, link], domain: integer }
    Link_start_up: { dims: [scenario, snapshot, link], domain: integer }
    Link_shut_down: { dims: [scenario, snapshot, link], domain: integer }
    Link_p_nom_ext: { dims: [link] }
  expressions:
    Link_p_nom_effective: { dims: [scenario, link] }
    Link_previous_status: { dims: [scenario, snapshot, link] }
    Link_p_nom_committed: { dims: [scenario, link] }

expressions:
  Link_previous_p:
    description: >-
      the flow a link carries into a snapshot — at the first, the
      `p_init` it brought in where it came in running and nothing where it
      came in off; the previous snapshot's after that
    dims: [scenario, snapshot, link]
    cases:
      opening: { when: "position(snapshot) == 0", expression: Link_status_initial * Link_p_init }
    otherwise: shift(Link_p, along=snapshot, offset=1)
  Link_ramp_up_rate:
    description: >-
      the ramp limit a link's up row reads — PyPSA's `ramp_limit_up`, or the
      full build where it has none, since a start-up ramp alone builds the row
    dims: [scenario, snapshot, link]
    cases:
      given: { when: Link_ramp_limit_up, expression: Link_ramp_limit_up }
    otherwise: 1
  Link_ramp_down_rate:
    description: >-
      the ramp limit a link's down row reads — PyPSA's `ramp_limit_down`, or
      the full build where it has none, since a shut-down ramp alone builds the row
    dims: [scenario, snapshot, link]
    cases:
      given: { when: Link_ramp_limit_down, expression: Link_ramp_limit_down }
    otherwise: 1
  Link_start_up_rate:
    description: >-
      the start-up ramp a link's up row reads — PyPSA's `ramp_limit_start_up`,
      or the full build where it has none
    dims: [scenario, link]
    cases:
      given: { when: Link_ramp_limit_start_up, expression: Link_ramp_limit_start_up }
    otherwise: 1
  Link_shut_down_rate:
    description: >-
      the shut-down ramp a link's down row reads — PyPSA's
      `ramp_limit_shut_down`, or the full build where it has none
    dims: [scenario, link]
    cases:
      given: { when: Link_ramp_limit_shut_down, expression: Link_ramp_limit_shut_down }
    otherwise: 1
  Link_ramp_up_allowance:
    description: >-
      how far a link may raise flow between two snapshots — its ramp
      limit of the build while it stays on, plus its start-up ramp in the
      snapshot it turns on
    dims: [scenario, snapshot, link]
    cases:
      committed:
        when: Link_committable
        expression: >-
          Link_ramp_up_rate * Link_p_nom_committed * Link_previous_status
          + Link_start_up_rate * Link_p_nom_committed
          * (Link_status - Link_previous_status)
    otherwise: Link_ramp_up_rate * Link_p_nom_effective
  Link_ramp_down_allowance:
    description: >-
      how far a link may lower flow between two snapshots — its ramp
      limit of the build while it stays on, plus its shut-down ramp in the
      snapshot it turns off
    dims: [scenario, snapshot, link]
    cases:
      committed:
        when: Link_committable
        expression: >-
          Link_ramp_down_rate * Link_p_nom_committed * Link_status
          + Link_shut_down_rate * Link_p_nom_committed
          * (Link_previous_status - Link_status)
    otherwise: Link_ramp_down_rate * Link_p_nom_effective

constraints:
  Link_p_ramp_limit_up_run_big_m:
    description: >-
      `Link-p-ramp_limit_up-run-bigM` — a committed extendable link
      raises flow no faster than its limit of the chosen build; the big M
      releases the row in the snapshot it turns on
    dims: [scenario, snapshot, link]
    where: >-
      Link_committable AND Link_p_nom_extendable AND NOT (Link_p_nom_mod > 0)
      AND (Link_ramp_limit_up OR Link_ramp_limit_start_up)
      AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Link_status_initial == 0 OR Link_p_init)))
      AND Link_active
    expression: >-
      Link_p - Link_previous_p <=
      Link_ramp_up_rate * Link_p_nom_ext
      + Link_big_m - Link_big_m * Link_previous_status
  Link_p_ramp_limit_up_start_big_m:
    description: >-
      `Link-p-ramp_limit_up-start-bigM` — in the snapshot it turns on, a
      committed extendable link ramps no further than its start-up ramp of
      the chosen build; the big M releases the row everywhere else
    dims: [scenario, snapshot, link]
    where: >-
      Link_committable AND Link_p_nom_extendable AND NOT (Link_p_nom_mod > 0)
      AND (Link_ramp_limit_up OR Link_ramp_limit_start_up)
      AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Link_status_initial == 0 OR Link_p_init)))
      AND Link_active
    expression: >-
      Link_p - Link_previous_p <=
      Link_start_up_rate * Link_p_nom_ext
      + Link_big_m - Link_big_m * Link_start_up
  Link_p_ramp_limit_down_run_big_m:
    description: >-
      `Link-p-ramp_limit_down-run-bigM` — a committed extendable link
      lowers flow no faster than its limit of the chosen build; the big M
      releases the row in the snapshot it turns off
    dims: [scenario, snapshot, link]
    where: >-
      Link_committable AND Link_p_nom_extendable AND NOT (Link_p_nom_mod > 0)
      AND (Link_ramp_limit_down OR Link_ramp_limit_shut_down)
      AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Link_status_initial == 0 OR Link_p_init)))
      AND Link_active
    expression: >-
      Link_previous_p - Link_p <=
      Link_ramp_down_rate * Link_p_nom_ext
      + Link_big_m - Link_big_m * Link_status
  Link_p_ramp_limit_down_shut_big_m:
    description: >-
      `Link-p-ramp_limit_down-shut-bigM` — in the snapshot it turns off,
      a committed extendable link ramps no further than its shut-down ramp of
      the chosen build; the big M releases the row everywhere else
    dims: [scenario, snapshot, link]
    where: >-
      Link_committable AND Link_p_nom_extendable AND NOT (Link_p_nom_mod > 0)
      AND (Link_ramp_limit_down OR Link_ramp_limit_shut_down)
      AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Link_status_initial == 0 OR Link_p_init)))
      AND Link_active
    expression: >-
      Link_previous_p - Link_p <=
      Link_shut_down_rate * Link_p_nom_ext
      + Link_big_m - Link_big_m * Link_shut_down
  Link_p_ramp_limit_up:
    description: >-
      `Link-p-ramp_limit_up` — a link raises flow no faster than
      its ramp limit of the build, and a committed one no further than its
      start-up ramp in the snapshot it turns on. A link that came into the
      horizon running carries a row at the first snapshot only where its
      `p_init` gives the flow it brought in, and no link carries one at
      the start of a later investment period — nor does any link a big M releases instead
    dims: [scenario, snapshot, link]
    where: >-
      (Link_ramp_limit_up OR Link_ramp_limit_start_up)
      AND NOT (Link_committable AND Link_p_nom_extendable AND NOT (Link_p_nom_mod > 0))
      AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Link_status_initial == 0 OR Link_p_init)))
      AND Link_active
    expression: Link_p - Link_previous_p <= Link_ramp_up_allowance
  Link_p_ramp_limit_down:
    description: >-
      `Link-p-ramp_limit_down` — a link lowers flow no faster than
      its ramp limit of the build, and a committed one no further than its
      shut-down ramp in the snapshot it turns off. A link that came into the
      horizon running carries a row at the first snapshot only where its
      `p_init` gives the flow it brought in, and no link carries one at
      the start of a later investment period — nor does any link a big M releases instead
    dims: [scenario, snapshot, link]
    where: >-
      (Link_ramp_limit_down OR Link_ramp_limit_shut_down)
      AND NOT (Link_committable AND Link_p_nom_extendable AND NOT (Link_p_nom_mod > 0))
      AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Link_status_initial == 0 OR Link_p_init)))
      AND Link_active
    expression: Link_previous_p - Link_p <= Link_ramp_down_allowance

assumptions:
  Link_came_in_running_unless_committable:
    holds: "Link_status_initial == 1"
    where: "NOT Link_committable AND (Link_ramp_limit_up OR Link_ramp_limit_down)"
    description: >-
      PyPSA reads `up_time_before` of a link that is not committable in its
      ramp rows. Where it is zero, PyPSA builds a row at the first snapshot
      with nothing carried in, and caps the link there at zero, or at its
      start-up ramp where another link of the component is committable with a
      fixed build (`constraints.py:1091-1094`, `1110-1112`). PyPSA documents
      the attribute as read only for a committable link and does not check
      it. PyPSA has not decided which row is intended (PyPSA/PyPSA#1943). The
      spec does not state that row, so it refuses the data
```

#### Sets

| Symbol | Meaning |
|---|---|
| $`\Xi`$ | index $`\xi`$ — `scenario` — the futures dispatch is chosen in, each with a weight |
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` with $`\mathrm{snapshot\_period}: \mathcal{T} \to \mathcal{Y}`$ — dispatch periods |
| $`\mathcal{L}`$ | index $`l`$ — `link` — controllable connections, each from one bus to the buses it delivers to |
| $`\mathcal{Y}`$ | index $`y`$ — `period` with $`\mathrm{snapshot\_period}: \mathcal{T} \to \mathcal{Y}`$ — investment periods — PyPSA's `investment_periods` |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{ru}^{f}`$ | `Link_ramp_limit_up` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — most a link may raise its flow between snapshots, per unit of nominal power; no value means no limit — read at the later of the two snapshots, so the limit may change over time |
| $`\mathrm{rd}^{f}`$ | `Link_ramp_limit_down` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — most a link may lower its flow between snapshots, per unit of nominal power; no value means no limit — read at the later of the two snapshots, so the limit may change over time |
| $`\mathrm{ru}^{f,\mathrm{up}}`$ | `Link_ramp_limit_start_up` over $`\Xi \times \mathcal{L}`$ — most flow in the snapshot a link starts, per unit of nominal power |
| $`\mathrm{rd}^{f,\mathrm{dn}}`$ | `Link_ramp_limit_shut_down` over $`\Xi \times \mathcal{L}`$ — most flow in the snapshot before a link stops, per unit of nominal power |
| $`\mathrm{f}^{0}`$ | `Link_p_init` over $`\Xi \times \mathcal{L}`$ — the flow a link brought into the horizon — PyPSA's `p_init`, read only where the link came in running; no value means it is unknown, so the link carries no ramp row at the first snapshot |

#### Given

| Symbol | Meaning |
|---|---|
| $`\mathrm{ext}^{f}`$ | `Link_p_nom_extendable` over $`\mathcal{L}`$, data another file declares |
| $`\mathrm{com}^{f}`$ | `Link_committable` over $`\mathcal{L}`$, data another file declares |
| $`\mathrm{u}^{f,0}`$ | `Link_status_initial` over $`\Xi \times \mathcal{L}`$, data another file declares |
| $`\mathrm{f}^{\mathrm{mod}}`$ | `Link_p_nom_mod` over $`\mathcal{L}`$, data another file declares |
| $`\mathrm{M}^{f}`$ | `Link_big_m` over $`\Xi \times \mathcal{L}`$, data another file declares |
| $`\mathrm{on}^{f}`$ | `Link_active` over $`\mathcal{T} \times \mathcal{L}`$, data another file declares |
| $`f`$ | `Link_p` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ |
| $`u^{f}`$ | `Link_status` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ |
| $`\mathit{up}^{f}`$ | `Link_start_up` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ |
| $`\mathit{dn}^{f}`$ | `Link_shut_down` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ |
| $`F`$ | `Link_p_nom_ext` over $`\mathcal{L}`$ |
| $`\widetilde{\mathrm{f}}^{\mathrm{nom}}`$ | `Link_p_nom_effective` over $`\Xi \times \mathcal{L}`$, an expression another file defines |
| $`\overleftarrow{u}^{f}`$ | `Link_previous_status` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$, an expression another file defines |
| $`\widehat{\mathrm{f}}^{\mathrm{nom}}`$ | `Link_p_nom_committed` over $`\Xi \times \mathcal{L}`$, an expression another file defines |

#### Definitions

| Symbol | Meaning |
|---|---|
| $`\overleftarrow{f}`$ | `Link_previous_p` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — the flow a link carries into a snapshot — at the first, the `p_init` it brought in where it came in running and nothing where it came in off; the previous snapshot's after that |
| $`\widetilde{\mathrm{ru}}^{f}`$ | `Link_ramp_up_rate` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — the ramp limit a link's up row reads — PyPSA's `ramp_limit_up`, or the full build where it has none, since a start-up ramp alone builds the row |
| $`\widetilde{\mathrm{rd}}^{f}`$ | `Link_ramp_down_rate` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — the ramp limit a link's down row reads — PyPSA's `ramp_limit_down`, or the full build where it has none, since a shut-down ramp alone builds the row |
| $`\widetilde{\mathrm{ru}}^{f,\mathrm{up}}`$ | `Link_start_up_rate` over $`\Xi \times \mathcal{L}`$ — the start-up ramp a link's up row reads — PyPSA's `ramp_limit_start_up`, or the full build where it has none |
| $`\widetilde{\mathrm{rd}}^{f,\mathrm{dn}}`$ | `Link_shut_down_rate` over $`\Xi \times \mathcal{L}`$ — the shut-down ramp a link's down row reads — PyPSA's `ramp_limit_shut_down`, or the full build where it has none |
| $`\Delta^{f,+}`$ | `Link_ramp_up_allowance` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — how far a link may raise flow between two snapshots — its ramp limit of the build while it stays on, plus its start-up ramp in the snapshot it turns on |
| $`\Delta^{f,-}`$ | `Link_ramp_down_allowance` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — how far a link may lower flow between two snapshots — its ramp limit of the build while it stays on, plus its shut-down ramp in the snapshot it turns off |

$`\mathrm{pos}(t)`$ denotes where index $`t`$ sits along its dimension's own order — the order `shift` steps along, not the order labels sort in — counted from $`0`$. The index itself stays the coordinate, so $`t`$ compares against labels and $`\mathrm{pos}(t)`$ against positions.

$`\mathrm{pos}_{\mathrm{relation}(t)}(t)`$ counts within the group a relation puts $`t`$ in: the subscript names the map, $`\mathcal{T}_{\mathrm{relation}(t)}`$ is the group it lands in, and that group has a first position of its own.

#### Subject to

**`Link_p_ramp_limit_up_run_big_m`**

```math
f_{\xi,t,l} - \overleftarrow{f}_{\xi,t,l} \le \widetilde{\mathrm{ru}}^{f}_{\xi,t,l} \cdot F_{l} + \mathrm{M}^{f}_{\xi,l} - \mathrm{M}^{f}_{\xi,l} \cdot \overleftarrow{u}^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \left( \mathrm{ru}^{f}_{\xi,t,l} \text{ is defined} \vee \mathrm{ru}^{f,\mathrm{up}}_{\xi,l} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{f,0}_{\xi,l} = 0 \vee \mathrm{f}^{0}_{\xi,l} \text{ is defined} \right) \right) \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_p_ramp_limit_up_start_big_m`**

```math
f_{\xi,t,l} - \overleftarrow{f}_{\xi,t,l} \le \widetilde{\mathrm{ru}}^{f,\mathrm{up}}_{\xi,l} \cdot F_{l} + \mathrm{M}^{f}_{\xi,l} - \mathrm{M}^{f}_{\xi,l} \cdot \mathit{up}^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \left( \mathrm{ru}^{f}_{\xi,t,l} \text{ is defined} \vee \mathrm{ru}^{f,\mathrm{up}}_{\xi,l} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{f,0}_{\xi,l} = 0 \vee \mathrm{f}^{0}_{\xi,l} \text{ is defined} \right) \right) \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_p_ramp_limit_down_run_big_m`**

```math
\overleftarrow{f}_{\xi,t,l} - f_{\xi,t,l} \le \widetilde{\mathrm{rd}}^{f}_{\xi,t,l} \cdot F_{l} + \mathrm{M}^{f}_{\xi,l} - \mathrm{M}^{f}_{\xi,l} \cdot u^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \left( \mathrm{rd}^{f}_{\xi,t,l} \text{ is defined} \vee \mathrm{rd}^{f,\mathrm{dn}}_{\xi,l} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{f,0}_{\xi,l} = 0 \vee \mathrm{f}^{0}_{\xi,l} \text{ is defined} \right) \right) \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_p_ramp_limit_down_shut_big_m`**

```math
\overleftarrow{f}_{\xi,t,l} - f_{\xi,t,l} \le \widetilde{\mathrm{rd}}^{f,\mathrm{dn}}_{\xi,l} \cdot F_{l} + \mathrm{M}^{f}_{\xi,l} - \mathrm{M}^{f}_{\xi,l} \cdot \mathit{dn}^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \left( \mathrm{rd}^{f}_{\xi,t,l} \text{ is defined} \vee \mathrm{rd}^{f,\mathrm{dn}}_{\xi,l} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{f,0}_{\xi,l} = 0 \vee \mathrm{f}^{0}_{\xi,l} \text{ is defined} \right) \right) \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_p_ramp_limit_up`**

```math
f_{\xi,t,l} - \overleftarrow{f}_{\xi,t,l} \le \Delta^{f,+}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \left( \mathrm{ru}^{f}_{\xi,t,l} \text{ is defined} \vee \mathrm{ru}^{f,\mathrm{up}}_{\xi,l} \text{ is defined} \right) \wedge \neg \left( \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{f,0}_{\xi,l} = 0 \vee \mathrm{f}^{0}_{\xi,l} \text{ is defined} \right) \right) \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_p_ramp_limit_down`**

```math
\overleftarrow{f}_{\xi,t,l} - f_{\xi,t,l} \le \Delta^{f,-}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \left( \mathrm{rd}^{f}_{\xi,t,l} \text{ is defined} \vee \mathrm{rd}^{f,\mathrm{dn}}_{\xi,l} \text{ is defined} \right) \wedge \neg \left( \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{f,0}_{\xi,l} = 0 \vee \mathrm{f}^{0}_{\xi,l} \text{ is defined} \right) \right) \wedge \mathrm{on}^{f}_{t,l}
```

#### Definitions

**`Link_previous_p`**

```math
\overleftarrow{f}_{\xi,t,l} = \begin{cases} \mathrm{u}^{f,0}_{\xi,l} \cdot \mathrm{f}^{0}_{\xi,l} & \text{if } \mathrm{pos}(t) = 0 \\ f_{\xi,t - 1,l} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L}
```

**`Link_ramp_up_rate`**

```math
\widetilde{\mathrm{ru}}^{f}_{\xi,t,l} = \begin{cases} \mathrm{ru}^{f}_{\xi,t,l} & \text{if } \mathrm{ru}^{f}_{\xi,t,l} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L}
```

**`Link_ramp_down_rate`**

```math
\widetilde{\mathrm{rd}}^{f}_{\xi,t,l} = \begin{cases} \mathrm{rd}^{f}_{\xi,t,l} & \text{if } \mathrm{rd}^{f}_{\xi,t,l} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L}
```

**`Link_start_up_rate`**

```math
\widetilde{\mathrm{ru}}^{f,\mathrm{up}}_{\xi,l} = \begin{cases} \mathrm{ru}^{f,\mathrm{up}}_{\xi,l} & \text{if } \mathrm{ru}^{f,\mathrm{up}}_{\xi,l} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L}
```

**`Link_shut_down_rate`**

```math
\widetilde{\mathrm{rd}}^{f,\mathrm{dn}}_{\xi,l} = \begin{cases} \mathrm{rd}^{f,\mathrm{dn}}_{\xi,l} & \text{if } \mathrm{rd}^{f,\mathrm{dn}}_{\xi,l} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L}
```

**`Link_ramp_up_allowance`**

```math
\Delta^{f,+}_{\xi,t,l} = \begin{cases} \widetilde{\mathrm{ru}}^{f}_{\xi,t,l} \cdot \widehat{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} \cdot \overleftarrow{u}^{f}_{\xi,t,l} + \widetilde{\mathrm{ru}}^{f,\mathrm{up}}_{\xi,l} \cdot \widehat{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} \cdot \left( u^{f}_{\xi,t,l} - \overleftarrow{u}^{f}_{\xi,t,l} \right) & \text{if } \mathrm{com}^{f}_{l} \\ \widetilde{\mathrm{ru}}^{f}_{\xi,t,l} \cdot \widetilde{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L}
```

**`Link_ramp_down_allowance`**

```math
\Delta^{f,-}_{\xi,t,l} = \begin{cases} \widetilde{\mathrm{rd}}^{f}_{\xi,t,l} \cdot \widehat{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} \cdot u^{f}_{\xi,t,l} + \widetilde{\mathrm{rd}}^{f,\mathrm{dn}}_{\xi,l} \cdot \widehat{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} \cdot \left( \overleftarrow{u}^{f}_{\xi,t,l} - u^{f}_{\xi,t,l} \right) & \text{if } \mathrm{com}^{f}_{l} \\ \widetilde{\mathrm{rd}}^{f}_{\xi,t,l} \cdot \widetilde{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L}
```

#### Assumptions

**`Link_came_in_running_unless_committable`**

```math
\mathrm{u}^{f,0}_{\xi,l} = 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \neg \mathrm{com}^{f}_{l} \wedge \left( \mathrm{ru}^{f}_{\xi,t,l} \text{ is defined} \vee \mathrm{rd}^{f}_{\xi,t,l} \text{ is defined} \right)
```
<!-- gallery:end -->
