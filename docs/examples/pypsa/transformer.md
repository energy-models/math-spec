<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Transformers

One of the [24 fragments](index.md) of `examples/pypsa.yaml`: PyPSA's `Transformer`. It adds a term to `Bus_injection`, `Cycle_angle_sum`. It reads `scenario_weight`, `transmission_losses` under [`given`](../../reference/language/declarations.md#given).

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
  transformer:
    description: passive branches between two buses, their flow set by impedance and tap ratio, with a phase shift fixed or optimised
  cycle:
    description: independent cycles of the passive network graph — the cycle basis, data prep
  segment:
    description: >-
      the cuts a passive branch's loss curve is held above — PyPSA's tangents,
      as many as its `segments` count, or its secants, as many as its tolerance
      loop places; none in a lossless run
    dtype: int

relations:
  Transformer_bus0:
    description: the bus a transformer's flow is measured at
    key: transformer
    values: bus
  Transformer_bus1:
    description: the bus at a transformer's other end
    key: transformer
    values: bus

parameters:
  Transformer_active:
    description: whether a transformer stands in a snapshot's period — PyPSA's `active`, data prep
    dims: [snapshot, transformer]
    dtype: bool
  Transformer_capital_weight:
    description: the sum of period weights a transformer stands in — PyPSA's `active * period_weighting`, summed, data prep
    dims: [transformer]
  Transformer_s_nom:
    description: nominal apparent power
    dims: [scenario, transformer]
  Transformer_s_nom_extendable:
    description: whether the nominal apparent power is a decision
    dims: [transformer]
    dtype: bool
  Transformer_s_max_pu:
    description: most flow either way, per unit of nominal apparent power
    dims: [scenario, snapshot, transformer]
  Transformer_s_nom_min:
    description: least nominal apparent power an extendable transformer may be built at
    dims: [scenario, transformer]
  Transformer_s_nom_max:
    description: most nominal apparent power an extendable transformer may be built at
    dims: [scenario, transformer]
  Transformer_capital_cost:
    description: cost of one unit of nominal apparent power — PyPSA's `capital_cost`, periodized as an annuity in data prep
    dims: [scenario, transformer]
  Transformer_s_nom_set:
    description: a given nominal apparent power for an extendable transformer; one without a value has no row here
    dims: [scenario, transformer]
  Transformer_s_set:
    description: a given flow schedule; a transformer without one has no row here
    dims: [scenario, snapshot, transformer]
  Transformer_cycle_weight:
    description: >-
      the transformer's effective series reactance, `x` times its tap ratio,
      signed by its orientation in the cycle — PyPSA's `x_pu_eff`, the cycle
      basis, data prep; a transformer in no cycle has no row. From the first
      scenario only, as a line's
    dims: [transformer, cycle]
  Transformer_phase_shift_weight:
    description: >-
      a fixed transformer's phase shift in radians, signed by its orientation
      in the cycle — a constant added to the cycle sum, data prep; zero for a
      varying transformer, whose shift is a decision instead, so the constant and
      the variable term never both count a shift. A transformer with no shift or
      in no cycle has no row
    dims: [transformer, cycle]
  Transformer_phase_shift_varying:
    description: >-
      whether a transformer's phase shift is a decision — PyPSA's
      `phase_shift_min < phase_shift_max`, read as a flag in data prep; false is a
      fixed shift carried by `phase_shift`. The shift parameters carry no
      scenario: only a cycle row reads them, and PyPSA fails on a transformer in
      a cycle on a network with scenarios (`constraints.py:1654`)
    dims: [transformer]
    dtype: bool
  Transformer_phase_shift_min:
    description: >-
      the least a varying transformer's phase shift may take, in degrees —
      PyPSA's `phase_shift_min`; where it is below `phase_shift_max` the shift is
      a decision, otherwise the transformer keeps its fixed `phase_shift`
    dims: [transformer]
  Transformer_phase_shift_max:
    description: >-
      the most a varying transformer's phase shift may take, in degrees —
      PyPSA's `phase_shift_max`; equal to `phase_shift_min` for a fixed transformer
    dims: [transformer]
  Transformer_phase_shift_cycle_weight:
    description: >-
      the cycle sign for a varying transformer's phase shift, times π/180 so a
      shift in degrees enters the cycle sum in radians — data prep; zero for a
      fixed transformer or one in no cycle
    dims: [transformer, cycle]
  Transformer_loss_max:
    description: >-
      the loss at a transformer's rating — PyPSA's `r_pu_eff * (s_max_pu *
      s_nom_max)**2`, its `r_pu_eff` the resistance over the given `s_nom` times
      the tap ratio, data prep
    dims: [scenario, snapshot, transformer]
  Transformer_loss_slope:
    description: >-
      the slope of a cut to a transformer's loss curve — a tangent's
      `2 * r_pu_eff * p_k`, a secant's `r_pu_eff * (p_k + p_k+1)`, as a line's,
      over the transformer's own `r_pu_eff` and rating, data prep
    dims: [scenario, snapshot, transformer, segment]
  Transformer_loss_offset:
    description: >-
      where that cut meets the loss axis — a tangent's `loss_k - slope_k * p_k`,
      a secant's `-r_pu_eff * p_k * p_k+1`, negative, data prep
    dims: [scenario, snapshot, transformer, segment]

variables:
  Transformer_s:
    description: >-
      `Transformer-s` — PyPSA's `p0`, the flow measured at the
      `Transformer_bus0` end: a positive value withdraws there and injects at
      `Transformer_bus1`, lossless
    dims: [scenario, snapshot, transformer]
    where: Transformer_active
  Transformer_loss:
    description: >-
      `Transformer-loss` — what a transformer dissipates carrying its flow, as
      a line does; absent, and zero in the balance, where the network is
      lossless
    dims: [scenario, snapshot, transformer]
    where: transmission_losses AND Transformer_active
    absence: zero
    bounds:
      lower: 0
  Transformer_phase_shift:
    description: >-
      `Transformer-phase_shift` — a phase-shifting transformer's voltage angle
      shift in degrees, chosen per snapshot to redistribute the flows around its
      cycles without moving active power; absent, and zero in the cycle sum,
      where the shift is fixed
    dims: [scenario, snapshot, transformer]
    where: Transformer_phase_shift_varying AND Transformer_active
    absence: zero
    bounds:
      lower: Transformer_phase_shift_min
      upper: Transformer_phase_shift_max
  Transformer_s_nom_ext:
    description: >-
      `Transformer-s_nom` — nominal apparent power where it is a decision; the
      parameter of the same PyPSA name carries the fixed regime
    dims: [transformer]
    where: Transformer_s_nom_extendable

given:
  parameters:
    scenario_weight: { dims: [scenario] }
    transmission_losses: { dims: [], dtype: bool }
  expressions:
    Bus_injection: { dims: [scenario, snapshot, bus], term: Transformer_injection }
    Cycle_angle_sum: { dims: [scenario, snapshot, cycle], term: Transformer_angle_sum }

expressions:
  Transformer_s_monitored:
    description: the flow a transformer's post-contingency rows read, as a line's
    dims: [scenario, snapshot, transformer]
    cases:
      standing: { when: Transformer_active, expression: Transformer_s }
    otherwise: 0
  Transformer_injection:
    expression: >-
      -sum(Transformer_s, by=Transformer_bus0, over=transformer, into=bus)
      + sum(Transformer_s, by=Transformer_bus1, over=transformer, into=bus)
      - (0.5 * sum(Transformer_loss, by=Transformer_bus0, over=transformer, into=bus))
      - (0.5 * sum(Transformer_loss, by=Transformer_bus1, over=transformer, into=bus))
  Transformer_angle_sum:
    expression: >-
      sum(Transformer_s * Transformer_cycle_weight, over=transformer)
      + sum(Transformer_phase_shift_weight, over=transformer)
      + sum(Transformer_phase_shift * Transformer_phase_shift_cycle_weight, over=transformer)

constraints:
  Transformer_fix_s_lower:
    description: "`Transformer-fix-s-lower` — a fixed transformer carries at least the negative of its rating, the loss counted against it"
    dims: [scenario, snapshot, transformer]
    where: not Transformer_s_nom_extendable AND Transformer_active
    expression: Transformer_s - Transformer_loss >= -Transformer_s_max_pu * Transformer_s_nom
  Transformer_fix_s_upper:
    description: "`Transformer-fix-s-upper` — a fixed transformer carries at most its rating, the loss included"
    dims: [scenario, snapshot, transformer]
    where: not Transformer_s_nom_extendable AND Transformer_active
    expression: Transformer_s + Transformer_loss <= Transformer_s_max_pu * Transformer_s_nom
  Transformer_ext_s_lower:
    description: "`Transformer-ext-s-lower` — an extendable transformer carries at least the negative of its rating of the chosen build, the loss counted against it"
    dims: [scenario, snapshot, transformer]
    where: Transformer_s_nom_extendable AND Transformer_active
    expression: Transformer_s - Transformer_loss >= -Transformer_s_max_pu * Transformer_s_nom_ext
  Transformer_ext_s_upper:
    description: "`Transformer-ext-s-upper` — an extendable transformer carries at most its rating of the chosen build, the loss included"
    dims: [scenario, snapshot, transformer]
    where: Transformer_s_nom_extendable AND Transformer_active
    expression: Transformer_s + Transformer_loss <= Transformer_s_max_pu * Transformer_s_nom_ext
  Transformer_ext_s_nom_lower:
    description: "`Transformer-ext-s_nom-lower` — the chosen build is at least its floor in every scenario"
    dims: [scenario, transformer]
    where: Transformer_s_nom_extendable
    expression: Transformer_s_nom_ext >= Transformer_s_nom_min
  Transformer_ext_s_nom_upper:
    description: "`Transformer-ext-s_nom-upper` — the chosen build is at most its cap in every scenario; a cap of infinity is no row"
    dims: [scenario, transformer]
    where: Transformer_s_nom_extendable AND Transformer_s_nom_max
    expression: Transformer_s_nom_ext <= Transformer_s_nom_max
  Transformer_s_nom_set:
    description: "`Transformer-s_nom_set` — the chosen build pinned, wherever a value is given"
    dims: [scenario, transformer]
    where: Transformer_s_nom_extendable AND Transformer_s_nom_set
    expression: Transformer_s_nom_ext == Transformer_s_nom_set
  Transformer_s_set:
    description: "`Transformer-s_set` — flow pinned to the given schedule, wherever one is given"
    dims: [scenario, snapshot, transformer]
    where: Transformer_s_set AND Transformer_active
    expression: Transformer_s == Transformer_s_set
  Transformer_loss_upper:
    description: "`Transformer-loss_upper` — a transformer dissipates at most the loss at its rating"
    dims: [scenario, snapshot, transformer]
    where: transmission_losses AND Transformer_active
    expression: Transformer_loss <= Transformer_loss_max
  Transformer_loss_tangents_forward:
    description: >-
      `Transformer-loss_tangents-{k}-1`, `Transformer-loss_secants-pos` — the
      loss sits above every cut to its curve for flow one way, as a line's
      does, over the segment dimension
    dims: [scenario, snapshot, transformer, segment]
    where: transmission_losses AND Transformer_active
    expression: Transformer_loss + Transformer_loss_slope * Transformer_s >= Transformer_loss_offset
  Transformer_loss_tangents_reverse:
    description: >-
      `Transformer-loss_tangents-{k}--1`, `Transformer-loss_secants-neg` — the
      same fan mirrored, the loss depending on the flow's magnitude
    dims: [scenario, snapshot, transformer, segment]
    where: transmission_losses AND Transformer_active
    expression: Transformer_loss - Transformer_loss_slope * Transformer_s >= Transformer_loss_offset

objective:
  sense: minimize
  expression: >-
    sum(((scenario_weight * Transformer_s_nom_ext) * Transformer_capital_cost) * Transformer_capital_weight)
```

#### Sets

| Symbol | Meaning |
|---|---|
| $`\Xi`$ | index $`\xi`$ — `scenario` — the futures dispatch is chosen in, each with a weight |
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` — dispatch periods |
| $`\mathcal{N}`$ | index $`n`$ — `bus` with $`\mathrm{Transformer\_bus0}: \mathcal{M} \to \mathcal{N},\ \mathrm{Transformer\_bus1}: \mathcal{M} \to \mathcal{N}`$ — network nodes |
| $`\mathcal{M}`$ | index $`m`$ — `transformer` with $`\mathrm{Transformer\_bus0}: \mathcal{M} \to \mathcal{N},\ \mathrm{Transformer\_bus1}: \mathcal{M} \to \mathcal{N}`$ — passive branches between two buses, their flow set by impedance and tap ratio, with a phase shift fixed or optimised |
| $`\mathcal{C}`$ | index $`c`$ — `cycle` — independent cycles of the passive network graph — the cycle basis, data prep |
| $`\mathcal{S}`$ | index $`s`$ — `segment` — the cuts a passive branch's loss curve is held above — PyPSA's tangents, as many as its `segments` count, or its secants, as many as its tolerance loop places; none in a lossless run |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{on}^{\sigma}`$ | `Transformer_active` over $`\mathcal{T} \times \mathcal{M}`$ — whether a transformer stands in a snapshot's period — PyPSA's `active`, data prep |
| $`\mathrm{W}^{\sigma}`$ | `Transformer_capital_weight` over $`\mathcal{M}`$ — the sum of period weights a transformer stands in — PyPSA's `active * period_weighting`, summed, data prep |
| $`\sigma^{\mathrm{nom}}`$ | `Transformer_s_nom` over $`\Xi \times \mathcal{M}`$ — nominal apparent power |
| $`\mathrm{ext}^{\sigma}`$ | `Transformer_s_nom_extendable` over $`\mathcal{M}`$ — whether the nominal apparent power is a decision |
| $`\overline{\sigma}`$ | `Transformer_s_max_pu` over $`\Xi \times \mathcal{T} \times \mathcal{M}`$ — most flow either way, per unit of nominal apparent power |
| $`\underline{\sigma}^{\mathrm{nom}}`$ | `Transformer_s_nom_min` over $`\Xi \times \mathcal{M}`$ — least nominal apparent power an extendable transformer may be built at |
| $`\overline{\sigma}^{\mathrm{nom}}`$ | `Transformer_s_nom_max` over $`\Xi \times \mathcal{M}`$ — most nominal apparent power an extendable transformer may be built at |
| $`\mathrm{c}^{\mathrm{cap},\sigma}`$ | `Transformer_capital_cost` over $`\Xi \times \mathcal{M}`$ — cost of one unit of nominal apparent power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $`\sigma^{\mathrm{nom,set}}`$ | `Transformer_s_nom_set` over $`\Xi \times \mathcal{M}`$ — a given nominal apparent power for an extendable transformer; one without a value has no row here |
| $`\sigma^{\mathrm{set}}`$ | `Transformer_s_set` over $`\Xi \times \mathcal{T} \times \mathcal{M}`$ — a given flow schedule; a transformer without one has no row here |
| $`\mathrm{x}^{\sigma}`$ | `Transformer_cycle_weight` over $`\mathcal{M} \times \mathcal{C}`$ — the transformer's effective series reactance, `x` times its tap ratio, signed by its orientation in the cycle — PyPSA's `x_pu_eff`, the cycle basis, data prep; a transformer in no cycle has no row. From the first scenario only, as a line's |
| $`\vartheta`$ | `Transformer_phase_shift_weight` over $`\mathcal{M} \times \mathcal{C}`$ — a fixed transformer's phase shift in radians, signed by its orientation in the cycle — a constant added to the cycle sum, data prep; zero for a varying transformer, whose shift is a decision instead, so the constant and the variable term never both count a shift. A transformer with no shift or in no cycle has no row |
| $`\mathrm{Transformer\_phase\_shift\_varying}`$ | `Transformer_phase_shift_varying` over $`\mathcal{M}`$ — whether a transformer's phase shift is a decision — PyPSA's `phase_shift_min < phase_shift_max`, read as a flag in data prep; false is a fixed shift carried by `phase_shift`. The shift parameters carry no scenario: only a cycle row reads them, and PyPSA fails on a transformer in a cycle on a network with scenarios (`constraints.py:1654`) |
| $`\mathrm{Transformer\_phase\_shift\_min}`$ | `Transformer_phase_shift_min` over $`\mathcal{M}`$ — the least a varying transformer's phase shift may take, in degrees — PyPSA's `phase_shift_min`; where it is below `phase_shift_max` the shift is a decision, otherwise the transformer keeps its fixed `phase_shift` |
| $`\mathrm{Transformer\_phase\_shift\_max}`$ | `Transformer_phase_shift_max` over $`\mathcal{M}`$ — the most a varying transformer's phase shift may take, in degrees — PyPSA's `phase_shift_max`; equal to `phase_shift_min` for a fixed transformer |
| $`\mathrm{Transformer\_phase\_shift\_cycle\_weight}`$ | `Transformer_phase_shift_cycle_weight` over $`\mathcal{M} \times \mathcal{C}`$ — the cycle sign for a varying transformer's phase shift, times π/180 so a shift in degrees enters the cycle sum in radians — data prep; zero for a fixed transformer or one in no cycle |
| $`\overline{\ell}^{\sigma}`$ | `Transformer_loss_max` over $`\Xi \times \mathcal{T} \times \mathcal{M}`$ — the loss at a transformer's rating — PyPSA's `r_pu_eff * (s_max_pu * s_nom_max)**2`, its `r_pu_eff` the resistance over the given `s_nom` times the tap ratio, data prep |
| $`\mathrm{a}^{\sigma}`$ | `Transformer_loss_slope` over $`\Xi \times \mathcal{T} \times \mathcal{M} \times \mathcal{S}`$ — the slope of a cut to a transformer's loss curve — a tangent's `2 * r_pu_eff * p_k`, a secant's `r_pu_eff * (p_k + p_k+1)`, as a line's, over the transformer's own `r_pu_eff` and rating, data prep |
| $`\mathrm{b}^{\sigma}`$ | `Transformer_loss_offset` over $`\Xi \times \mathcal{T} \times \mathcal{M} \times \mathcal{S}`$ — where that cut meets the loss axis — a tangent's `loss_k - slope_k * p_k`, a secant's `-r_pu_eff * p_k * p_k+1`, negative, data prep |

#### Variables

| Symbol | Meaning |
|---|---|
| $`\sigma`$ | `Transformer_s` over $`\Xi \times \mathcal{T} \times \mathcal{M}`$ — `Transformer-s` — PyPSA's `p0`, the flow measured at the `Transformer_bus0` end: a positive value withdraws there and injects at `Transformer_bus1`, lossless |
| $`\ell^{\sigma}`$ | `Transformer_loss` over $`\Xi \times \mathcal{T} \times \mathcal{M}`$ — `Transformer-loss` — what a transformer dissipates carrying its flow, as a line does; absent, and zero in the balance, where the network is lossless |
| $`\mathit{Transformer\_phase\_shift}`$ | `Transformer_phase_shift` over $`\Xi \times \mathcal{T} \times \mathcal{M}`$ — `Transformer-phase_shift` — a phase-shifting transformer's voltage angle shift in degrees, chosen per snapshot to redistribute the flows around its cycles without moving active power; absent, and zero in the cycle sum, where the shift is fixed |
| $`\Sigma`$ | `Transformer_s_nom_ext` over $`\mathcal{M}`$ — `Transformer-s_nom` — nominal apparent power where it is a decision; the parameter of the same PyPSA name carries the fixed regime |

#### Given

| Symbol | Meaning |
|---|---|
| $`\pi`$ | `scenario_weight` over $`\Xi`$, data another file declares |
| $`\mathrm{lossy}`$ | `transmission_losses` (scalar), data another file declares |
| $`\mathit{Bus\_injection}`$ | `Bus_injection` over $`\Xi \times \mathcal{T} \times \mathcal{N}`$, an expression this file adds `Transformer_injection` to |
| $`\mathit{Cycle\_angle\_sum}`$ | `Cycle_angle_sum` over $`\Xi \times \mathcal{T} \times \mathcal{C}`$, an expression this file adds `Transformer_angle_sum` to |

#### Definitions

| Symbol | Meaning |
|---|---|
| $`\check{\sigma}`$ | `Transformer_s_monitored` over $`\Xi \times \mathcal{T} \times \mathcal{M}`$ — the flow a transformer's post-contingency rows read, as a line's |
| $`\mathit{Transformer\_injection}`$ | `Transformer_injection` over $`\Xi \times \mathcal{T} \times \mathcal{N}`$ |
| $`\mathit{Transformer\_angle\_sum}`$ | `Transformer_angle_sum` over $`\Xi \times \mathcal{T} \times \mathcal{C}`$ |

Upright is what the data supplies — a parameter such as $`\mathrm{Transformer\_phase\_shift\_varying}`$, a coordinate map, a label — and italic is what the solver chooses, such as $`\mathit{Transformer\_phase\_shift}`$. An index is italic too, being what a quantifier chooses, and a set is script.

#### Objective

```math
\min \sum_{\xi \in \Xi,\ m \in \mathcal{M}} \pi_{\xi} \cdot \Sigma_{m} \cdot \mathrm{c}^{\mathrm{cap},\sigma}_{\xi,m} \cdot \mathrm{W}^{\sigma}_{m}
```

#### Subject to

**`Transformer_fix_s_lower`**

```math
\sigma_{\xi,t,m} - \ell^{\sigma}_{\xi,t,m} \ge -\overline{\sigma}_{\xi,t,m} \cdot \sigma^{\mathrm{nom}}_{\xi,m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M} \,:\, \neg \mathrm{ext}^{\sigma}_{m} \wedge \mathrm{on}^{\sigma}_{t,m}
```

**`Transformer_fix_s_upper`**

```math
\sigma_{\xi,t,m} + \ell^{\sigma}_{\xi,t,m} \le \overline{\sigma}_{\xi,t,m} \cdot \sigma^{\mathrm{nom}}_{\xi,m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M} \,:\, \neg \mathrm{ext}^{\sigma}_{m} \wedge \mathrm{on}^{\sigma}_{t,m}
```

**`Transformer_ext_s_lower`**

```math
\sigma_{\xi,t,m} - \ell^{\sigma}_{\xi,t,m} \ge -\overline{\sigma}_{\xi,t,m} \cdot \Sigma_{m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M} \,:\, \mathrm{ext}^{\sigma}_{m} \wedge \mathrm{on}^{\sigma}_{t,m}
```

**`Transformer_ext_s_upper`**

```math
\sigma_{\xi,t,m} + \ell^{\sigma}_{\xi,t,m} \le \overline{\sigma}_{\xi,t,m} \cdot \Sigma_{m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M} \,:\, \mathrm{ext}^{\sigma}_{m} \wedge \mathrm{on}^{\sigma}_{t,m}
```

**`Transformer_ext_s_nom_lower`**

```math
\Sigma_{m} \ge \underline{\sigma}^{\mathrm{nom}}_{\xi,m} \qquad \forall\, \xi \in \Xi,\ m \in \mathcal{M} \,:\, \mathrm{ext}^{\sigma}_{m}
```

**`Transformer_ext_s_nom_upper`**

```math
\Sigma_{m} \le \overline{\sigma}^{\mathrm{nom}}_{\xi,m} \qquad \forall\, \xi \in \Xi,\ m \in \mathcal{M} \,:\, \mathrm{ext}^{\sigma}_{m} \wedge \overline{\sigma}^{\mathrm{nom}}_{\xi,m} \text{ is defined}
```

**`Transformer_s_nom_set`**

```math
\Sigma_{m} = \sigma^{\mathrm{nom,set}}_{\xi,m} \qquad \forall\, \xi \in \Xi,\ m \in \mathcal{M} \,:\, \mathrm{ext}^{\sigma}_{m} \wedge \sigma^{\mathrm{nom,set}}_{\xi,m} \text{ is defined}
```

**`Transformer_s_set`**

```math
\sigma_{\xi,t,m} = \sigma^{\mathrm{set}}_{\xi,t,m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M} \,:\, \sigma^{\mathrm{set}}_{\xi,t,m} \text{ is defined} \wedge \mathrm{on}^{\sigma}_{t,m}
```

**`Transformer_loss_upper`**

```math
\ell^{\sigma}_{\xi,t,m} \le \overline{\ell}^{\sigma}_{\xi,t,m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M} \,:\, \mathrm{lossy} \wedge \mathrm{on}^{\sigma}_{t,m}
```

**`Transformer_loss_tangents_forward`**

```math
\ell^{\sigma}_{\xi,t,m} + \mathrm{a}^{\sigma}_{\xi,t,m,s} \cdot \sigma_{\xi,t,m} \ge \mathrm{b}^{\sigma}_{\xi,t,m,s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M},\ s \in \mathcal{S} \,:\, \mathrm{lossy} \wedge \mathrm{on}^{\sigma}_{t,m}
```

**`Transformer_loss_tangents_reverse`**

```math
\ell^{\sigma}_{\xi,t,m} - \mathrm{a}^{\sigma}_{\xi,t,m,s} \cdot \sigma_{\xi,t,m} \ge \mathrm{b}^{\sigma}_{\xi,t,m,s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M},\ s \in \mathcal{S} \,:\, \mathrm{lossy} \wedge \mathrm{on}^{\sigma}_{t,m}
```

#### Definitions

**`Transformer_s_monitored`**

```math
\check{\sigma}_{\xi,t,m} = \begin{cases} \sigma_{\xi,t,m} & \text{if } \mathrm{on}^{\sigma}_{t,m} \\ 0 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M}
```

**`Transformer_injection`**

```math
\mathit{Transformer\_injection}_{\xi,t,n} = -\left( \sum_{m \in \mathcal{M} \,:\, \mathrm{Transformer\_bus0}(m) = n} \sigma_{\xi,t,m} \right) + \sum_{m \in \mathcal{M} \,:\, \mathrm{Transformer\_bus1}(m) = n} \sigma_{\xi,t,m} - 0.5 \cdot \left( \sum_{m \in \mathcal{M} \,:\, \mathrm{Transformer\_bus0}(m) = n} \ell^{\sigma}_{\xi,t,m} \right) - 0.5 \cdot \left( \sum_{m \in \mathcal{M} \,:\, \mathrm{Transformer\_bus1}(m) = n} \ell^{\sigma}_{\xi,t,m} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ n \in \mathcal{N}
```

**`Transformer_angle_sum`**

```math
\mathit{Transformer\_angle\_sum}_{\xi,t,c} = \sum_{m \in \mathcal{M}} \sigma_{\xi,t,m} \cdot \mathrm{x}^{\sigma}_{m,c} + \sum_{m \in \mathcal{M}} \vartheta_{m,c} + \sum_{m \in \mathcal{M}} \mathit{Transformer\_phase\_shift}_{\xi,t,m} \cdot \mathrm{Transformer\_phase\_shift\_cycle\_weight}_{m,c} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ c \in \mathcal{C}
```

#### Variable domains

**`Transformer_s`**

```math
\sigma_{\xi,t,m} \in \mathbb{R} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M} \,:\, \mathrm{on}^{\sigma}_{t,m}
```

**`Transformer_loss`**

```math
\ell^{\sigma}_{\xi,t,m} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M} \,:\, \mathrm{lossy} \wedge \mathrm{on}^{\sigma}_{t,m}
```

**`Transformer_phase_shift`**

```math
\mathrm{Transformer\_phase\_shift\_min}_{m} \le \mathit{Transformer\_phase\_shift}_{\xi,t,m} \le \mathrm{Transformer\_phase\_shift\_max}_{m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M} \,:\, \mathrm{Transformer\_phase\_shift\_varying}_{m} \wedge \mathrm{on}^{\sigma}_{t,m}
```

**`Transformer_s_nom_ext`**

```math
\Sigma_{m} \in \mathbb{R} \qquad \forall\, m \in \mathcal{M} \,:\, \mathrm{ext}^{\sigma}_{m}
```
<!-- gallery:end -->
