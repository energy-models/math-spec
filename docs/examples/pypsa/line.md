<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Lines

One of the [24 fragments](index.md) of `examples/pypsa.yaml`: PyPSA's `Line`. It adds a term to `transmission_volume_expansion`, `transmission_expansion_cost`, `tech_capacity_expansion`, `Carrier_additions`, `Bus_injection`, `Cycle_angle_sum`. It reads `scenario_weight`, `transmission_losses` under [`given`](../../reference/language/declarations.md#given).

<!-- gallery:begin -->
```yaml
dimensions:
  scenario:
    description: the futures dispatch is chosen in, each with a weight
  snapshot:
    description: dispatch periods
    dtype: datetime
  bus:
    description: network nodes
  line:
    description: passive branches, each between two buses, their flow set by impedance
  cycle:
    description: independent cycles of the passive network graph — the cycle basis, data prep
  segment:
    description: >-
      the cuts a passive branch's loss curve is held above — PyPSA's tangents,
      as many as its `segments` count, or its secants, as many as its tolerance
      loop places; none in a lossless run
    dtype: int
  global_constraint:
    description: PyPSA's `GlobalConstraint` rows, one label per declared limit
  period:
    description: investment periods — PyPSA's `investment_periods`
    dtype: int
  carrier:
    description: energy carriers, what a growth limit is set per

relations:
  Line_carrier:
    description: the carrier a line carries
    key: line
    values: carrier
  Line_bus0:
    description: the bus a line's flow is measured at
    key: line
    values: bus
  Line_bus1:
    description: the bus at a line's other end
    key: line
    values: bus

parameters:
  Line_active:
    description: whether a line stands in a snapshot's period — PyPSA's `active`, data prep
    dims: [snapshot, line]
    dtype: bool
  Line_capital_weight:
    description: the sum of period weights a line stands in — PyPSA's `active * period_weighting`, summed, data prep
    dims: [line]
  Line_first_active:
    description: >-
      one in the first period a line stands in, zero elsewhere, data prep.
      PyPSA `1.3.0` takes `active.cumsum() == 1`, which also counts a line
      that has retired in every later period (`global_constraints.py:276`,
      PyPSA/PyPSA#1938)
    dims: [period, line]
  Line_s_nom:
    description: nominal apparent power
    dims: [scenario, line]
  Line_s_nom_extendable:
    description: whether the nominal apparent power is a decision
    dims: [line]
    dtype: bool
  Line_s_max_pu:
    description: most flow either way, per unit of nominal apparent power
    dims: [scenario, snapshot, line]
  Line_s_nom_min:
    description: least nominal apparent power an extendable line may be built at
    dims: [scenario, line]
  Line_s_nom_max:
    description: most nominal apparent power an extendable line may be built at
    dims: [scenario, line]
  Line_capital_cost:
    description: cost of one unit of nominal apparent power — PyPSA's `capital_cost`, periodized as an annuity in data prep
    dims: [scenario, line]
  Line_s_nom_set:
    description: a given nominal apparent power for an extendable line; one without a value has no row here
    dims: [scenario, line]
  Line_s_set:
    description: a given flow schedule; a line without one has no row here
    dims: [scenario, snapshot, line]
  Line_cycle_weight:
    description: >-
      the line's series impedance, signed by its orientation in the cycle —
      the cycle basis, data prep; a line in no cycle has no row. PyPSA builds
      the cycle basis from the first scenario only (`networks.py:1354-1361`)
    dims: [line, cycle]
  Line_loss_max:
    description: the loss at a line's rating — PyPSA's `r_pu_eff * (s_max_pu * s_nom_max)**2`, data prep
    dims: [scenario, snapshot, line]
  Line_loss_slope:
    description: >-
      the slope of a cut to the loss curve — a tangent's `2 * r_pu_eff * p_k`
      at its segment's flow, a secant's `r_pu_eff * (p_k + p_k+1)` between
      consecutive breakpoints, data prep
    dims: [scenario, snapshot, line, segment]
  Line_loss_offset:
    description: >-
      where that cut meets the loss axis — a tangent's `loss_k - slope_k * p_k`,
      a secant's `-r_pu_eff * p_k * p_k+1`, negative, data prep
    dims: [scenario, snapshot, line, segment]
  Line_volume_weight:
    description: >-
      the line's length where its carrier is in the row's set, the first
      scenario's length as PyPSA reads it (`global_constraints.py:835-836`) —
      data prep; a
      line outside it, or one that does not stand in the row's
      `investment_period`, has no row
    dims: [scenario, global_constraint, line]
  Line_expansion_cost_weight:
    description: >-
      the line's capital cost where its carrier is in the row's set, times
      the objective weights of the periods it stands in where the row names
      no `investment_period` under `multi_investment_periods` — data prep; a
      line outside the set, or one that does not stand in the row's period,
      has no row
    dims: [scenario, global_constraint, line]
  Line_tech_capacity_weight:
    description: >-
      one where the line is in the row's carrier-and-bus set — data prep; one
      outside it, or one that does not stand in the row's `investment_period`,
      has no row
    dims: [global_constraint, line]

variables:
  Line_s:
    description: >-
      `Line-s` — PyPSA's `p0`, the flow measured at the `Line_bus0` end: a
      positive value withdraws there and injects at `Line_bus1`, lossless
    dims: [scenario, snapshot, line]
    where: Line_active
  Line_loss:
    description: >-
      `Line-loss` — what a line dissipates carrying its flow, pushed down by the
      cost and held up by the cuts; absent, and zero in the balance, where
      the network is lossless
    dims: [scenario, snapshot, line]
    where: transmission_losses AND Line_active
    absence: zero
    bounds:
      lower: 0
  Line_s_nom_ext:
    description: >-
      `Line-s_nom` — nominal apparent power where it is a decision; the
      parameter of the same PyPSA name carries the fixed regime
    dims: [line]
    where: Line_s_nom_extendable

given:
  parameters:
    scenario_weight: { dims: [scenario] }
    transmission_losses: { dims: [], dtype: bool }
  expressions:
    transmission_volume_expansion: { dims: [scenario, global_constraint], term: Line_transmission_volume_expansion }
    transmission_expansion_cost: { dims: [scenario, global_constraint], term: Line_transmission_expansion_cost }
    tech_capacity_expansion: { dims: [global_constraint], term: Line_tech_capacity_expansion }
    Carrier_additions: { dims: [period, carrier], term: Line_additions }
    Bus_injection: { dims: [scenario, snapshot, bus], term: Line_injection }
    Cycle_angle_sum: { dims: [scenario, snapshot, cycle], term: Line_angle_sum }

expressions:
  Line_transmission_volume_expansion:
    expression: sum(Line_s_nom_ext * Line_volume_weight, over=line)
  Line_transmission_expansion_cost:
    expression: sum(Line_s_nom_ext * Line_expansion_cost_weight, over=line)
  Line_tech_capacity_expansion:
    expression: sum(Line_s_nom_ext * Line_tech_capacity_weight, over=line)
  Line_additions:
    expression: >-
      sum(Line_s_nom_ext * Line_first_active, by=Line_carrier, over=line, into=carrier)
  Line_s_monitored:
    description: >-
      the flow a line's post-contingency rows read — its flow where it stands,
      nothing where it does not, since PyPSA builds those rows for every
      branch of the sub-network in every snapshot
    dims: [scenario, snapshot, line]
    cases:
      standing: { when: Line_active, expression: Line_s }
    otherwise: 0
  Line_injection:
    expression: >-
      -sum(Line_s, by=Line_bus0, over=line, into=bus)
      + sum(Line_s, by=Line_bus1, over=line, into=bus)
      - (0.5 * sum(Line_loss, by=Line_bus0, over=line, into=bus))
      - (0.5 * sum(Line_loss, by=Line_bus1, over=line, into=bus))
  Line_angle_sum: sum(Line_s * Line_cycle_weight, over=line)

constraints:
  Line_fix_s_lower:
    description: "`Line-fix-s-lower` — a fixed line carries at least the negative of its rating, the loss counted against it"
    dims: [scenario, snapshot, line]
    where: not Line_s_nom_extendable AND Line_active
    expression: Line_s - Line_loss >= -Line_s_max_pu * Line_s_nom
  Line_fix_s_upper:
    description: "`Line-fix-s-upper` — a fixed line carries at most its rating, the loss included"
    dims: [scenario, snapshot, line]
    where: not Line_s_nom_extendable AND Line_active
    expression: Line_s + Line_loss <= Line_s_max_pu * Line_s_nom
  Line_ext_s_lower:
    description: "`Line-ext-s-lower` — an extendable line carries at least the negative of its rating of the chosen build, the loss counted against it"
    dims: [scenario, snapshot, line]
    where: Line_s_nom_extendable AND Line_active
    expression: Line_s - Line_loss >= -Line_s_max_pu * Line_s_nom_ext
  Line_ext_s_upper:
    description: "`Line-ext-s-upper` — an extendable line carries at most its rating of the chosen build, the loss included"
    dims: [scenario, snapshot, line]
    where: Line_s_nom_extendable AND Line_active
    expression: Line_s + Line_loss <= Line_s_max_pu * Line_s_nom_ext
  Line_ext_s_nom_lower:
    description: "`Line-ext-s_nom-lower` — the chosen build is at least its floor in every scenario"
    dims: [scenario, line]
    where: Line_s_nom_extendable
    expression: Line_s_nom_ext >= Line_s_nom_min
  Line_ext_s_nom_upper:
    description: "`Line-ext-s_nom-upper` — the chosen build is at most its cap in every scenario; a cap of infinity is no row"
    dims: [scenario, line]
    where: Line_s_nom_extendable AND Line_s_nom_max
    expression: Line_s_nom_ext <= Line_s_nom_max
  Line_s_nom_set:
    description: "`Line-s_nom_set` — the chosen build pinned, wherever a value is given"
    dims: [scenario, line]
    where: Line_s_nom_extendable AND Line_s_nom_set
    expression: Line_s_nom_ext == Line_s_nom_set
  Line_s_set:
    description: "`Line-s_set` — flow pinned to the given schedule, wherever one is given"
    dims: [scenario, snapshot, line]
    where: Line_s_set AND Line_active
    expression: Line_s == Line_s_set
  Line_loss_upper:
    description: "`Line-loss_upper` — a line dissipates at most the loss at its rating"
    dims: [scenario, snapshot, line]
    where: transmission_losses AND Line_active
    expression: Line_loss <= Line_loss_max
  Line_loss_tangents_forward:
    description: >-
      `Line-loss_tangents-{k}-1`, `Line-loss_secants-pos` — the loss sits above
      every cut to its curve for flow one way; PyPSA names one row per tangent
      `k`, or one row stacked over its `secant` axis, and this block states them
      all over the segment dimension
    dims: [scenario, snapshot, line, segment]
    where: transmission_losses AND Line_active
    expression: Line_loss + Line_loss_slope * Line_s >= Line_loss_offset
  Line_loss_tangents_reverse:
    description: >-
      `Line-loss_tangents-{k}--1`, `Line-loss_secants-neg` — the same fan
      mirrored, the loss depending on the flow's magnitude
    dims: [scenario, snapshot, line, segment]
    where: transmission_losses AND Line_active
    expression: Line_loss - Line_loss_slope * Line_s >= Line_loss_offset

objective:
  sense: minimize
  expression: >-
    sum(((scenario_weight * Line_s_nom_ext) * Line_capital_cost) * Line_capital_weight)
```

#### Sets

| Symbol | Meaning |
|---|---|
| $`\Xi`$ | index $`\xi`$ — `scenario` — the futures dispatch is chosen in, each with a weight |
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` — dispatch periods |
| $`\mathcal{N}`$ | index $`n`$ — `bus` with $`\mathrm{Line\_bus0}: \mathcal{K} \to \mathcal{N},\ \mathrm{Line\_bus1}: \mathcal{K} \to \mathcal{N}`$ — network nodes |
| $`\mathcal{K}`$ | index $`k`$ — `line` with $`\mathrm{Line\_carrier}: \mathcal{K} \to \mathcal{I},\ \mathrm{Line\_bus0}: \mathcal{K} \to \mathcal{N},\ \mathrm{Line\_bus1}: \mathcal{K} \to \mathcal{N}`$ — passive branches, each between two buses, their flow set by impedance |
| $`\mathcal{C}`$ | index $`c`$ — `cycle` — independent cycles of the passive network graph — the cycle basis, data prep |
| $`\mathcal{E}`$ | index $`e`$ — `segment` — the cuts a passive branch's loss curve is held above — PyPSA's tangents, as many as its `segments` count, or its secants, as many as its tolerance loop places; none in a lossless run |
| $`\mathcal{G}`$ | index $`g`$ — `global_constraint` — PyPSA's `GlobalConstraint` rows, one label per declared limit |
| $`\mathcal{Y}`$ | index $`y`$ — `period` — investment periods — PyPSA's `investment_periods` |
| $`\mathcal{I}`$ | index $`i`$ — `carrier` with $`\mathrm{Line\_carrier}: \mathcal{K} \to \mathcal{I}`$ — energy carriers, what a growth limit is set per |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{on}^{s}`$ | `Line_active` over $`\mathcal{T} \times \mathcal{K}`$ — whether a line stands in a snapshot's period — PyPSA's `active`, data prep |
| $`\mathrm{W}^{s}`$ | `Line_capital_weight` over $`\mathcal{K}`$ — the sum of period weights a line stands in — PyPSA's `active * period_weighting`, summed, data prep |
| $`\mathrm{new}^{s}`$ | `Line_first_active` over $`\mathcal{Y} \times \mathcal{K}`$ — one in the first period a line stands in, zero elsewhere, data prep. PyPSA `1.3.0` takes `active.cumsum() == 1`, which also counts a line that has retired in every later period (`global_constraints.py:276`, PyPSA/PyPSA\#1938) |
| $`\mathrm{s}^{\mathrm{nom}}`$ | `Line_s_nom` over $`\Xi \times \mathcal{K}`$ — nominal apparent power |
| $`\mathrm{ext}^{s}`$ | `Line_s_nom_extendable` over $`\mathcal{K}`$ — whether the nominal apparent power is a decision |
| $`\overline{\mathrm{s}}`$ | `Line_s_max_pu` over $`\Xi \times \mathcal{T} \times \mathcal{K}`$ — most flow either way, per unit of nominal apparent power |
| $`\underline{\mathrm{s}}^{\mathrm{nom}}`$ | `Line_s_nom_min` over $`\Xi \times \mathcal{K}`$ — least nominal apparent power an extendable line may be built at |
| $`\overline{\mathrm{s}}^{\mathrm{nom}}`$ | `Line_s_nom_max` over $`\Xi \times \mathcal{K}`$ — most nominal apparent power an extendable line may be built at |
| $`\mathrm{c}^{\mathrm{cap},s}`$ | `Line_capital_cost` over $`\Xi \times \mathcal{K}`$ — cost of one unit of nominal apparent power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $`\mathrm{s}^{\mathrm{nom,set}}`$ | `Line_s_nom_set` over $`\Xi \times \mathcal{K}`$ — a given nominal apparent power for an extendable line; one without a value has no row here |
| $`\mathrm{s}^{\mathrm{set}}`$ | `Line_s_set` over $`\Xi \times \mathcal{T} \times \mathcal{K}`$ — a given flow schedule; a line without one has no row here |
| $`\mathrm{x}`$ | `Line_cycle_weight` over $`\mathcal{K} \times \mathcal{C}`$ — the line's series impedance, signed by its orientation in the cycle — the cycle basis, data prep; a line in no cycle has no row. PyPSA builds the cycle basis from the first scenario only (`networks.py:1354-1361`) |
| $`\overline{\ell}`$ | `Line_loss_max` over $`\Xi \times \mathcal{T} \times \mathcal{K}`$ — the loss at a line's rating — PyPSA's `r_pu_eff * (s_max_pu * s_nom_max)**2`, data prep |
| $`\mathrm{a}`$ | `Line_loss_slope` over $`\Xi \times \mathcal{T} \times \mathcal{K} \times \mathcal{E}`$ — the slope of a cut to the loss curve — a tangent's `2 * r_pu_eff * p_k` at its segment's flow, a secant's `r_pu_eff * (p_k + p_k+1)` between consecutive breakpoints, data prep |
| $`\mathrm{b}`$ | `Line_loss_offset` over $`\Xi \times \mathcal{T} \times \mathcal{K} \times \mathcal{E}`$ — where that cut meets the loss axis — a tangent's `loss_k - slope_k * p_k`, a secant's `-r_pu_eff * p_k * p_k+1`, negative, data prep |
| $`\mathrm{len}`$ | `Line_volume_weight` over $`\Xi \times \mathcal{G} \times \mathcal{K}`$ — the line's length where its carrier is in the row's set, the first scenario's length as PyPSA reads it (`global_constraints.py:835-836`) — data prep; a line outside it, or one that does not stand in the row's `investment_period`, has no row |
| $`\mathrm{cc}`$ | `Line_expansion_cost_weight` over $`\Xi \times \mathcal{G} \times \mathcal{K}`$ — the line's capital cost where its carrier is in the row's set, times the objective weights of the periods it stands in where the row names no `investment_period` under `multi_investment_periods` — data prep; a line outside the set, or one that does not stand in the row's period, has no row |
| $`\mathrm{m}^{l}`$ | `Line_tech_capacity_weight` over $`\mathcal{G} \times \mathcal{K}`$ — one where the line is in the row's carrier-and-bus set — data prep; one outside it, or one that does not stand in the row's `investment_period`, has no row |

#### Variables

| Symbol | Meaning |
|---|---|
| $`s`$ | `Line_s` over $`\Xi \times \mathcal{T} \times \mathcal{K}`$ — `Line-s` — PyPSA's `p0`, the flow measured at the `Line_bus0` end: a positive value withdraws there and injects at `Line_bus1`, lossless |
| $`\ell`$ | `Line_loss` over $`\Xi \times \mathcal{T} \times \mathcal{K}`$ — `Line-loss` — what a line dissipates carrying its flow, pushed down by the cost and held up by the cuts; absent, and zero in the balance, where the network is lossless |
| $`S`$ | `Line_s_nom_ext` over $`\mathcal{K}`$ — `Line-s_nom` — nominal apparent power where it is a decision; the parameter of the same PyPSA name carries the fixed regime |

#### Given

| Symbol | Meaning |
|---|---|
| $`\pi`$ | `scenario_weight` over $`\Xi`$, data another file declares |
| $`\mathrm{lossy}`$ | `transmission_losses` (scalar), data another file declares |
| $`\mathit{transmission\_volume\_expansion}`$ | `transmission_volume_expansion` over $`\Xi \times \mathcal{G}`$, an expression this file adds `Line_transmission_volume_expansion` to |
| $`\mathit{transmission\_expansion\_cost}`$ | `transmission_expansion_cost` over $`\Xi \times \mathcal{G}`$, an expression this file adds `Line_transmission_expansion_cost` to |
| $`\mathit{tech\_capacity\_expansion}`$ | `tech_capacity_expansion` over $`\mathcal{G}`$, an expression this file adds `Line_tech_capacity_expansion` to |
| $`\mathit{Carrier\_additions}`$ | `Carrier_additions` over $`\mathcal{Y} \times \mathcal{I}`$, an expression this file adds `Line_additions` to |
| $`\mathit{Bus\_injection}`$ | `Bus_injection` over $`\Xi \times \mathcal{T} \times \mathcal{N}`$, an expression this file adds `Line_injection` to |
| $`\mathit{Cycle\_angle\_sum}`$ | `Cycle_angle_sum` over $`\Xi \times \mathcal{T} \times \mathcal{C}`$, an expression this file adds `Line_angle_sum` to |

#### Definitions

| Symbol | Meaning |
|---|---|
| $`\mathit{Line\_transmission\_volume\_expansion}`$ | `Line_transmission_volume_expansion` over $`\Xi \times \mathcal{G}`$ |
| $`\mathit{Line\_transmission\_expansion\_cost}`$ | `Line_transmission_expansion_cost` over $`\Xi \times \mathcal{G}`$ |
| $`\mathit{Line\_tech\_capacity\_expansion}`$ | `Line_tech_capacity_expansion` over $`\mathcal{G}`$ |
| $`\mathit{Line\_additions}`$ | `Line_additions` over $`\mathcal{Y} \times \mathcal{I}`$ |
| $`\check{s}`$ | `Line_s_monitored` over $`\Xi \times \mathcal{T} \times \mathcal{K}`$ — the flow a line's post-contingency rows read — its flow where it stands, nothing where it does not, since PyPSA builds those rows for every branch of the sub-network in every snapshot |
| $`\mathit{Line\_injection}`$ | `Line_injection` over $`\Xi \times \mathcal{T} \times \mathcal{N}`$ |
| $`\mathit{Line\_angle\_sum}`$ | `Line_angle_sum` over $`\Xi \times \mathcal{T} \times \mathcal{C}`$ |

#### Objective

```math
\min \sum_{\xi \in \Xi,\ k \in \mathcal{K}} \pi_{\xi} \cdot S_{k} \cdot \mathrm{c}^{\mathrm{cap},s}_{\xi,k} \cdot \mathrm{W}^{s}_{k}
```

#### Subject to

**`Line_fix_s_lower`**

```math
s_{\xi,t,k} - \ell_{\xi,t,k} \ge -\overline{\mathrm{s}}_{\xi,t,k} \cdot \mathrm{s}^{\mathrm{nom}}_{\xi,k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K} \,:\, \neg \mathrm{ext}^{s}_{k} \wedge \mathrm{on}^{s}_{t,k}
```

**`Line_fix_s_upper`**

```math
s_{\xi,t,k} + \ell_{\xi,t,k} \le \overline{\mathrm{s}}_{\xi,t,k} \cdot \mathrm{s}^{\mathrm{nom}}_{\xi,k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K} \,:\, \neg \mathrm{ext}^{s}_{k} \wedge \mathrm{on}^{s}_{t,k}
```

**`Line_ext_s_lower`**

```math
s_{\xi,t,k} - \ell_{\xi,t,k} \ge -\overline{\mathrm{s}}_{\xi,t,k} \cdot S_{k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K} \,:\, \mathrm{ext}^{s}_{k} \wedge \mathrm{on}^{s}_{t,k}
```

**`Line_ext_s_upper`**

```math
s_{\xi,t,k} + \ell_{\xi,t,k} \le \overline{\mathrm{s}}_{\xi,t,k} \cdot S_{k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K} \,:\, \mathrm{ext}^{s}_{k} \wedge \mathrm{on}^{s}_{t,k}
```

**`Line_ext_s_nom_lower`**

```math
S_{k} \ge \underline{\mathrm{s}}^{\mathrm{nom}}_{\xi,k} \qquad \forall\, \xi \in \Xi,\ k \in \mathcal{K} \,:\, \mathrm{ext}^{s}_{k}
```

**`Line_ext_s_nom_upper`**

```math
S_{k} \le \overline{\mathrm{s}}^{\mathrm{nom}}_{\xi,k} \qquad \forall\, \xi \in \Xi,\ k \in \mathcal{K} \,:\, \mathrm{ext}^{s}_{k} \wedge \overline{\mathrm{s}}^{\mathrm{nom}}_{\xi,k} \text{ is defined}
```

**`Line_s_nom_set`**

```math
S_{k} = \mathrm{s}^{\mathrm{nom,set}}_{\xi,k} \qquad \forall\, \xi \in \Xi,\ k \in \mathcal{K} \,:\, \mathrm{ext}^{s}_{k} \wedge \mathrm{s}^{\mathrm{nom,set}}_{\xi,k} \text{ is defined}
```

**`Line_s_set`**

```math
s_{\xi,t,k} = \mathrm{s}^{\mathrm{set}}_{\xi,t,k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K} \,:\, \mathrm{s}^{\mathrm{set}}_{\xi,t,k} \text{ is defined} \wedge \mathrm{on}^{s}_{t,k}
```

**`Line_loss_upper`**

```math
\ell_{\xi,t,k} \le \overline{\ell}_{\xi,t,k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K} \,:\, \mathrm{lossy} \wedge \mathrm{on}^{s}_{t,k}
```

**`Line_loss_tangents_forward`**

```math
\ell_{\xi,t,k} + \mathrm{a}_{\xi,t,k,e} \cdot s_{\xi,t,k} \ge \mathrm{b}_{\xi,t,k,e} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K},\ e \in \mathcal{E} \,:\, \mathrm{lossy} \wedge \mathrm{on}^{s}_{t,k}
```

**`Line_loss_tangents_reverse`**

```math
\ell_{\xi,t,k} - \mathrm{a}_{\xi,t,k,e} \cdot s_{\xi,t,k} \ge \mathrm{b}_{\xi,t,k,e} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K},\ e \in \mathcal{E} \,:\, \mathrm{lossy} \wedge \mathrm{on}^{s}_{t,k}
```

#### Definitions

**`Line_transmission_volume_expansion`**

```math
\mathit{Line\_transmission\_volume\_expansion}_{\xi,g} = \sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{len}_{\xi,g,k} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G}
```

**`Line_transmission_expansion_cost`**

```math
\mathit{Line\_transmission\_expansion\_cost}_{\xi,g} = \sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{cc}_{\xi,g,k} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G}
```

**`Line_tech_capacity_expansion`**

```math
\mathit{Line\_tech\_capacity\_expansion}_{g} = \sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{m}^{l}_{g,k} \qquad \forall\, g \in \mathcal{G}
```

**`Line_additions`**

```math
\mathit{Line\_additions}_{y,i} = \sum_{k \in \mathcal{K} \,:\, \mathrm{Line\_carrier}(k) = i} S_{k} \cdot \mathrm{new}^{s}_{y,k} \qquad \forall\, y \in \mathcal{Y},\ i \in \mathcal{I}
```

**`Line_s_monitored`**

```math
\check{s}_{\xi,t,k} = \begin{cases} s_{\xi,t,k} & \text{if } \mathrm{on}^{s}_{t,k} \\ 0 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K}
```

**`Line_injection`**

```math
\mathit{Line\_injection}_{\xi,t,n} = -\left( \sum_{k \in \mathcal{K} \,:\, \mathrm{Line\_bus0}(k) = n} s_{\xi,t,k} \right) + \sum_{k \in \mathcal{K} \,:\, \mathrm{Line\_bus1}(k) = n} s_{\xi,t,k} - 0.5 \cdot \left( \sum_{k \in \mathcal{K} \,:\, \mathrm{Line\_bus0}(k) = n} \ell_{\xi,t,k} \right) - 0.5 \cdot \left( \sum_{k \in \mathcal{K} \,:\, \mathrm{Line\_bus1}(k) = n} \ell_{\xi,t,k} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ n \in \mathcal{N}
```

**`Line_angle_sum`**

```math
\mathit{Line\_angle\_sum}_{\xi,t,c} = \sum_{k \in \mathcal{K}} s_{\xi,t,k} \cdot \mathrm{x}_{k,c} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ c \in \mathcal{C}
```

#### Variable domains

**`Line_s`**

```math
s_{\xi,t,k} \in \mathbb{R} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K} \,:\, \mathrm{on}^{s}_{t,k}
```

**`Line_loss`**

```math
\ell_{\xi,t,k} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K} \,:\, \mathrm{lossy} \wedge \mathrm{on}^{s}_{t,k}
```

**`Line_s_nom_ext`**

```math
S_{k} \in \mathbb{R} \qquad \forall\, k \in \mathcal{K} \,:\, \mathrm{ext}^{s}_{k}
```
<!-- gallery:end -->
