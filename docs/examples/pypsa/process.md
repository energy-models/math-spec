<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Processes

One of the [24 fragments](index.md) of `examples/pypsa.yaml`: PyPSA's `Process`. It adds a term to `tech_capacity_expansion`, `scenario_opex`, `Carrier_additions`, `Bus_injection`. It reads `CVaR_omega`, `Process_committable`, `Process_maintenance`, `Process_maintenance_capacity`, `Process_maintenance_pu`, `period_weight_objective` and 2 more under [`given`](../../reference/language/declarations.md#given).

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
  process:
    description: generalized multi-port converters, each with an internal power that every port draws or delivers at its own rate
  process_output:
    description: >-
      a process's ports, one label per port a process declares — PyPSA's
      `bus0`, `bus1`, … each carry a signed `rate`, so a process of any number
      of ports is one term in the balance, data prep
  global_constraint:
    description: PyPSA's `GlobalConstraint` rows, one label per declared limit
  period:
    description: investment periods — PyPSA's `investment_periods`
    dtype: int
  carrier:
    description: energy carriers, what a growth limit is set per

relations:
  snapshot_period:
    description: the investment period a snapshot falls in
    key: snapshot
    values: period
  Process_carrier:
    description: the carrier a process converts from
    key: process
    values: carrier
  Process_output_process:
    description: the process a port belongs to
    key: process_output
    values: process
  Process_output_bus:
    description: >-
      the bus a port draws from or delivers to — PyPSA's `bus0`, `bus1`, …
      columns. A process of three ports is three labels here rather than a
      third relation, so the file states any number of them
    key: process_output
    values: bus

parameters:
  Process_p_nom:
    description: nominal internal power
    dims: [scenario, process]
  Process_p_nom_extendable:
    description: whether the nominal internal power is a decision
    dims: [process]
    dtype: bool
  Process_p_min_pu:
    description: least internal power, per unit of nominal power — negative for a process that runs both ways
    dims: [scenario, snapshot, process]
  Process_p_max_pu:
    description: most internal power, per unit of nominal power
    dims: [scenario, snapshot, process]
  Process_rate:
    description: >-
      the energy a port draws or delivers per unit of internal power, PyPSA's
      `rate0`, `rate1`, … read long — negative where the port withdraws,
      positive where it injects; a link is a process whose `bus0` rate is minus
      one and whose output rates are its efficiencies
    dims: [scenario, process_output]
  Process_output_delay:
    description: >-
      snapshots a port's transfer lags its process's internal power — PyPSA's
      `delay0`, `delay1`, … read long, in `snapshot_weightings.generators`
      units, which the file states as whole snapshots; zero for a port that
      transfers at once. Each scenario takes its own, as a link's
    dims: [scenario, process_output]
    dtype: int
  Process_output_cyclic_delay:
    description: >-
      whether a delayed port's transfer wraps from the end of its investment
      period — PyPSA's `cyclic_delay0`, `cyclic_delay1`, …; where it does not,
      the energy still in transit at each period's first snapshots is lost.
      Each scenario takes its own, as the delay
    dims: [scenario, process_output]
    dtype: bool
  Process_marginal_cost:
    description: cost of one unit of internal power
    dims: [scenario, snapshot, process]
  Process_marginal_cost_quadratic:
    description: cost of the square of one unit of internal power
    dims: [scenario, snapshot, process]
  Process_p_set:
    description: a given internal power schedule; a process without one has no row here
    dims: [scenario, snapshot, process]
  Process_p_nom_min:
    description: least nominal power an extendable process may be built at
    dims: [scenario, process]
  Process_p_nom_max:
    description: most nominal power an extendable process may be built at
    dims: [scenario, process]
  Process_capital_cost:
    description: cost of one unit of nominal power — PyPSA's `capital_cost`, periodized as an annuity in data prep
    dims: [scenario, process]
  Process_p_nom_set:
    description: a given nominal power for an extendable process; one without a value has no row here
    dims: [scenario, process]
  Process_p_nom_mod:
    description: the module size a build comes in whole numbers of; no value means the build is continuous
    dims: [process]
  Process_modules_installed:
    description: >-
      how many whole modules a committable build has in place: `Process_p_nom
      / Process_p_nom_mod` where a fixed build is modular, one where it is
      not, data prep. PyPSA refuses a fixed modular build whose nominal power
      is not a whole number of modules
    dims: [scenario, process]
  Process_p_min_pu_nonneg:
    description: >-
      true where none of the process's own minimums-per-unit is negative —
      PyPSA's per-unit `(p_min_pu >= 0).all()` over every snapshot and scenario, data prep
    dims: [process]
    dtype: bool
  Process_active:
    description: whether a process stands in a snapshot's period — PyPSA's `active`, data prep
    dims: [snapshot, process]
    dtype: bool
  Process_capital_weight:
    description: the sum of period weights a process stands in — PyPSA's `active * period_weighting`, summed, data prep
    dims: [process]
  Process_first_active:
    description: >-
      one in the first period a process stands in, zero elsewhere, data prep.
      PyPSA `1.3.0` takes `active.cumsum() == 1`, which also counts a process
      that has retired in every later period (`global_constraints.py:276`,
      PyPSA/PyPSA#1938)
    dims: [period, process]
  Process_tech_capacity_weight:
    description: >-
      one where the process is in the row's carrier-and-bus set — data prep; one
      outside it, or one that does not stand in the row's `investment_period`,
      has no row
    dims: [global_constraint, process]

variables:
  Process_p:
    description: >-
      `Process-p` — PyPSA's internal power `p`: a positive value drives every
      port at its own rate, withdrawing where the rate is negative and injecting
      where it is positive
    dims: [scenario, snapshot, process]
    where: Process_active
  Process_n_mod:
    description: "`Process-n_mod` — how many modules of an extendable modular build"
    dims: [process]
    where: Process_p_nom_extendable AND Process_p_nom_mod > 0
    domain: integer
    bounds:
      lower: 0
  Process_p_nom_ext:
    description: >-
      `Process-p_nom` — nominal internal power where it is a decision; the
      parameter of the same PyPSA name carries the fixed regime
    dims: [process]
    where: Process_p_nom_extendable

given:
  parameters:
    snapshot_weightings_objective: { dims: [snapshot] }
    Process_committable: { dims: [process], dtype: bool }
    Process_maintenance_pu: { dims: [scenario, process] }
    scenario_weight: { dims: [scenario] }
    CVaR_omega: { dims: [] }
    period_weight_objective: { dims: [period] }
  variables:
    Process_maintenance: { dims: [scenario, snapshot, process] }
    Process_maintenance_capacity: { dims: [scenario, snapshot, process] }
  expressions:
    tech_capacity_expansion: { dims: [global_constraint], term: Process_tech_capacity_expansion }
    scenario_opex: { dims: [scenario], term: Process_opex }
    Carrier_additions: { dims: [period, carrier], term: Process_additions }
    Bus_injection: { dims: [scenario, snapshot, bus], term: Process_injection }

expressions:
  Process_p_nom_effective:
    description: the build a process's limits are taken against — the chosen one where it is extendable, the given one otherwise
    dims: [scenario, process]
    cases:
      extendable: { when: Process_p_nom_extendable, expression: Process_p_nom_ext }
    otherwise: Process_p_nom
  Process_p_nom_committed:
    description: >-
      the build a committed process's ramp rows are taken against — one module
      where the build is extendable and modular, the given build otherwise
    dims: [scenario, process]
    cases:
      modular_build: { when: Process_p_nom_extendable AND Process_p_nom_mod > 0, expression: Process_p_nom_mod }
    otherwise: Process_p_nom
  Process_output_arrival:
    description: >-
      what a process transfers at a port at a snapshot — its internal power
      times the port's rate, delayed by the port's `delay` within its
      investment period; where the port is `cyclic_delay` the delayed transfer
      wraps from the period's end, and where it is not the energy still in
      transit at the period's first snapshots is lost. A port that does not
      delay (`delay` zero) transfers at once, cyclic or not
    dims: [scenario, snapshot, process_output]
    cases:
      wrapping:
        when: Process_output_cyclic_delay
        expression: shift(at(Process_p, by=Process_output_process, over=process, into=process_output) * Process_rate, along=snapshot, offset=Process_output_delay, edge='wrap', by=snapshot_period, within=period)
    otherwise: shift(at(Process_p, by=Process_output_process, over=process, into=process_output) * Process_rate, along=snapshot, offset=Process_output_delay, edge=0, by=snapshot_period, within=period)
  Process_tech_capacity_expansion:
    expression: sum(Process_p_nom_ext * Process_tech_capacity_weight, over=process)
  Process_opex:
    expression: >-
      sum(sum(((Process_p * Process_marginal_cost) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=process), over=snapshot)
      + sum(sum((((Process_p * Process_p) * Process_marginal_cost_quadratic) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=process), over=snapshot)
  Process_additions:
    expression: >-
      sum(Process_p_nom_ext * Process_first_active, by=Process_carrier, over=process, into=carrier)
  Process_injection:
    expression: >-
      sum(Process_output_arrival, by=Process_output_bus, over=process_output, into=bus)

constraints:
  Process_fix_p_lower:
    description: "`Process-fix-p-lower` — a fixed process runs at least its minimum, negative for the other way"
    dims: [scenario, snapshot, process]
    where: not Process_p_nom_extendable AND not Process_committable AND Process_active
    expression: Process_p >= Process_p_min_pu * Process_p_nom * (1 - Process_maintenance_pu * Process_maintenance)
  Process_fix_p_upper:
    description: "`Process-fix-p-upper` — a fixed process runs at most its nominal power"
    dims: [scenario, snapshot, process]
    where: not Process_p_nom_extendable AND not Process_committable AND Process_active
    expression: Process_p <= Process_p_max_pu * Process_p_nom * (1 - Process_maintenance_pu * Process_maintenance)
  Process_ext_p_lower:
    description: "`Process-ext-p-lower` — an extendable process runs at least its minimum of the chosen build, negative for the other way"
    dims: [scenario, snapshot, process]
    where: Process_p_nom_extendable AND not Process_committable AND Process_active
    expression: Process_p >= Process_p_min_pu * (Process_p_nom_ext - Process_maintenance_pu * Process_maintenance_capacity)
  Process_ext_p_upper:
    description: "`Process-ext-p-upper` — an extendable process runs at most the chosen build"
    dims: [scenario, snapshot, process]
    where: Process_p_nom_extendable AND not Process_committable AND Process_active
    expression: Process_p <= Process_p_max_pu * (Process_p_nom_ext - Process_maintenance_pu * Process_maintenance_capacity)
  Process_ext_p_nom_lower:
    description: "`Process-ext-p_nom-lower` — the chosen build is at least its floor in every scenario"
    dims: [scenario, process]
    where: Process_p_nom_extendable
    expression: Process_p_nom_ext >= Process_p_nom_min
  Process_ext_p_nom_upper:
    description: "`Process-ext-p_nom-upper` — the chosen build is at most its cap in every scenario; a cap of infinity is no row"
    dims: [scenario, process]
    where: Process_p_nom_extendable AND Process_p_nom_max
    expression: Process_p_nom_ext <= Process_p_nom_max
  Process_p_nom_set:
    description: "`Process-p_nom_set` — the chosen build pinned, wherever a value is given"
    dims: [scenario, process]
    where: Process_p_nom_extendable AND Process_p_nom_set
    expression: Process_p_nom_ext == Process_p_nom_set
  Process_p_nom_modularity:
    description: "`Process-p_nom_modularity` — the chosen build is a whole number of modules"
    dims: [process]
    where: Process_p_nom_extendable AND Process_p_nom_mod > 0
    expression: Process_p_nom_ext == Process_p_nom_mod * Process_n_mod
  Process_p_set:
    description: "`Process-p_set` — internal power pinned to the given schedule, wherever one is given"
    dims: [scenario, snapshot, process]
    where: Process_p_set AND Process_active
    expression: Process_p == Process_p_set

assumptions:
  Process_marginal_cost_quadratic_without_risk_preference:
    holds: "Process_marginal_cost_quadratic == 0"
    where: "CVaR_omega > 0"
    description: >-
      a quadratic cost puts a square into every `CVaR-excess` row, and PyPSA
      refuses quadratic costs under any risk preference
      (`optimize.py:467-474`). The spec cannot tell no risk preference from
      one with `omega = 0`, so it refuses only where `omega` is positive

objective:
  sense: minimize
  expression: >-
    sum(((scenario_weight * Process_p_nom_ext) * Process_capital_cost) * Process_capital_weight)
```

#### Sets

| Symbol | Meaning |
|---|---|
| $`\Xi`$ | index $`\xi`$ — `scenario` — the futures dispatch is chosen in, each with a weight |
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` with $`\mathrm{snapshot\_period}: \mathcal{T} \to \mathcal{Y}`$ — dispatch periods |
| $`\mathcal{N}`$ | index $`n`$ — `bus` with $`\mathrm{Process\_output\_bus}: \mathcal{R} \to \mathcal{N}`$ — network nodes |
| $`\mathcal{J}`$ | index $`j`$ — `process` with $`\mathrm{Process\_carrier}: \mathcal{J} \to \mathcal{I},\ \mathrm{Process\_output\_process}: \mathcal{R} \to \mathcal{J}`$ — generalized multi-port converters, each with an internal power that every port draws or delivers at its own rate |
| $`\mathcal{R}`$ | index $`r`$ — `process_output` with $`\mathrm{Process\_output\_process}: \mathcal{R} \to \mathcal{J},\ \mathrm{Process\_output\_bus}: \mathcal{R} \to \mathcal{N}`$ — a process's ports, one label per port a process declares — PyPSA's `bus0`, `bus1`, … each carry a signed `rate`, so a process of any number of ports is one term in the balance, data prep |
| $`\mathcal{G}`$ | index $`g`$ — `global_constraint` — PyPSA's `GlobalConstraint` rows, one label per declared limit |
| $`\mathcal{Y}`$ | index $`y`$ — `period` with $`\mathrm{snapshot\_period}: \mathcal{T} \to \mathcal{Y}`$ — investment periods — PyPSA's `investment_periods` |
| $`\mathcal{I}`$ | index $`i`$ — `carrier` with $`\mathrm{Process\_carrier}: \mathcal{J} \to \mathcal{I}`$ — energy carriers, what a growth limit is set per |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{z}^{\mathrm{nom}}`$ | `Process_p_nom` over $`\Xi \times \mathcal{J}`$ — nominal internal power |
| $`\mathrm{ext}^{z}`$ | `Process_p_nom_extendable` over $`\mathcal{J}`$ — whether the nominal internal power is a decision |
| $`\underline{\mathrm{z}}`$ | `Process_p_min_pu` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — least internal power, per unit of nominal power — negative for a process that runs both ways |
| $`\overline{\mathrm{z}}`$ | `Process_p_max_pu` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — most internal power, per unit of nominal power |
| $`\alpha`$ | `Process_rate` over $`\Xi \times \mathcal{R}`$ — the energy a port draws or delivers per unit of internal power, PyPSA's `rate0`, `rate1`, … read long — negative where the port withdraws, positive where it injects; a link is a process whose `bus0` rate is minus one and whose output rates are its efficiencies |
| $`\mathrm{d}^{z}`$ | `Process_output_delay` over $`\Xi \times \mathcal{R}`$ — snapshots a port's transfer lags its process's internal power — PyPSA's `delay0`, `delay1`, … read long, in `snapshot_weightings.generators` units, which the file states as whole snapshots; zero for a port that transfers at once. Each scenario takes its own, as a link's |
| $`\mathrm{cyc}^{z}`$ | `Process_output_cyclic_delay` over $`\Xi \times \mathcal{R}`$ — whether a delayed port's transfer wraps from the end of its investment period — PyPSA's `cyclic_delay0`, `cyclic_delay1`, …; where it does not, the energy still in transit at each period's first snapshots is lost. Each scenario takes its own, as the delay |
| $`\mathrm{c}^{z}`$ | `Process_marginal_cost` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — cost of one unit of internal power |
| $`\mathrm{c}^{z,(2)}`$ | `Process_marginal_cost_quadratic` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — cost of the square of one unit of internal power |
| $`\mathrm{z}^{\mathrm{set}}`$ | `Process_p_set` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — a given internal power schedule; a process without one has no row here |
| $`\underline{\mathrm{z}}^{\mathrm{nom}}`$ | `Process_p_nom_min` over $`\Xi \times \mathcal{J}`$ — least nominal power an extendable process may be built at |
| $`\overline{\mathrm{z}}^{\mathrm{nom}}`$ | `Process_p_nom_max` over $`\Xi \times \mathcal{J}`$ — most nominal power an extendable process may be built at |
| $`\mathrm{c}^{\mathrm{cap},z}`$ | `Process_capital_cost` over $`\Xi \times \mathcal{J}`$ — cost of one unit of nominal power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $`\mathrm{z}^{\mathrm{nom,set}}`$ | `Process_p_nom_set` over $`\Xi \times \mathcal{J}`$ — a given nominal power for an extendable process; one without a value has no row here |
| $`\mathrm{z}^{\mathrm{mod}}`$ | `Process_p_nom_mod` over $`\mathcal{J}`$ — the module size a build comes in whole numbers of; no value means the build is continuous |
| $`\mathrm{N}^{z,\mathrm{fix}}`$ | `Process_modules_installed` over $`\Xi \times \mathcal{J}`$ — how many whole modules a committable build has in place: `Process_p_nom / Process_p_nom_mod` where a fixed build is modular, one where it is not, data prep. PyPSA refuses a fixed modular build whose nominal power is not a whole number of modules |
| $`\mathrm{nonneg}^{z}`$ | `Process_p_min_pu_nonneg` over $`\mathcal{J}`$ — true where none of the process's own minimums-per-unit is negative — PyPSA's per-unit `(p_min_pu >= 0).all()` over every snapshot and scenario, data prep |
| $`\mathrm{on}^{z}`$ | `Process_active` over $`\mathcal{T} \times \mathcal{J}`$ — whether a process stands in a snapshot's period — PyPSA's `active`, data prep |
| $`\mathrm{W}^{z}`$ | `Process_capital_weight` over $`\mathcal{J}`$ — the sum of period weights a process stands in — PyPSA's `active * period_weighting`, summed, data prep |
| $`\mathrm{new}^{z}`$ | `Process_first_active` over $`\mathcal{Y} \times \mathcal{J}`$ — one in the first period a process stands in, zero elsewhere, data prep. PyPSA `1.3.0` takes `active.cumsum() == 1`, which also counts a process that has retired in every later period (`global_constraints.py:276`, PyPSA/PyPSA\#1938) |
| $`\mathrm{m}^{z}`$ | `Process_tech_capacity_weight` over $`\mathcal{G} \times \mathcal{J}`$ — one where the process is in the row's carrier-and-bus set — data prep; one outside it, or one that does not stand in the row's `investment_period`, has no row |

#### Variables

| Symbol | Meaning |
|---|---|
| $`z`$ | `Process_p` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — `Process-p` — PyPSA's internal power `p`: a positive value drives every port at its own rate, withdrawing where the rate is negative and injecting where it is positive |
| $`N^{z}`$ | `Process_n_mod` over $`\mathcal{J}`$ — `Process-n_mod` — how many modules of an extendable modular build |
| $`Z`$ | `Process_p_nom_ext` over $`\mathcal{J}`$ — `Process-p_nom` — nominal internal power where it is a decision; the parameter of the same PyPSA name carries the fixed regime |

#### Given

| Symbol | Meaning |
|---|---|
| $`\mathrm{w}`$ | `snapshot_weightings_objective` over $`\mathcal{T}`$, data another file declares |
| $`\mathrm{com}^{z}`$ | `Process_committable` over $`\mathcal{J}`$, data another file declares |
| $`\gamma^{z}`$ | `Process_maintenance_pu` over $`\Xi \times \mathcal{J}`$, data another file declares |
| $`\pi`$ | `scenario_weight` over $`\Xi`$, data another file declares |
| $`\omega`$ | `CVaR_omega` (scalar), data another file declares |
| $`\mathrm{w}^{y}`$ | `period_weight_objective` over $`\mathcal{Y}`$, data another file declares |
| $`\mu^{z}`$ | `Process_maintenance` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ |
| $`\mu^{z,\mathrm{nom}}`$ | `Process_maintenance_capacity` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ |
| $`\mathit{tech\_capacity\_expansion}`$ | `tech_capacity_expansion` over $`\mathcal{G}`$, an expression this file adds `Process_tech_capacity_expansion` to |
| $`\mathit{scenario\_opex}`$ | `scenario_opex` over $`\Xi`$, an expression this file adds `Process_opex` to |
| $`\mathit{Carrier\_additions}`$ | `Carrier_additions` over $`\mathcal{Y} \times \mathcal{I}`$, an expression this file adds `Process_additions` to |
| $`\mathit{Bus\_injection}`$ | `Bus_injection` over $`\Xi \times \mathcal{T} \times \mathcal{N}`$, an expression this file adds `Process_injection` to |

#### Definitions

| Symbol | Meaning |
|---|---|
| $`\widetilde{\mathrm{z}}^{\mathrm{nom}}`$ | `Process_p_nom_effective` over $`\Xi \times \mathcal{J}`$ — the build a process's limits are taken against — the chosen one where it is extendable, the given one otherwise |
| $`\widehat{\mathrm{z}}^{\mathrm{nom}}`$ | `Process_p_nom_committed` over $`\Xi \times \mathcal{J}`$ — the build a committed process's ramp rows are taken against — one module where the build is extendable and modular, the given build otherwise |
| $`\overrightarrow{z}`$ | `Process_output_arrival` over $`\Xi \times \mathcal{T} \times \mathcal{R}`$ — what a process transfers at a port at a snapshot — its internal power times the port's rate, delayed by the port's `delay` within its investment period; where the port is `cyclic_delay` the delayed transfer wraps from the period's end, and where it is not the energy still in transit at the period's first snapshots is lost. A port that does not delay (`delay` zero) transfers at once, cyclic or not |
| $`\mathit{Process\_tech\_capacity\_expansion}`$ | `Process_tech_capacity_expansion` over $`\mathcal{G}`$ |
| $`\mathit{Process\_opex}`$ | `Process_opex` over $`\Xi`$ |
| $`\mathit{Process\_additions}`$ | `Process_additions` over $`\mathcal{Y} \times \mathcal{I}`$ |
| $`\mathit{Process\_injection}`$ | `Process_injection` over $`\Xi \times \mathcal{T} \times \mathcal{N}`$ |

$`t \ominus k`$ denotes cyclic translation: index $`t-k`$ taken modulo the size of the dimension (`roll`). Plain $`t-k`$ (`shift`) has no wraparound — terms translated past the edge are simply absent.

$`t \boxminus_{v} k`$ denotes translation with $`v`$ standing where index $`t-k`$ leaves the dimension (`shift(edge=v)`), so the row at that boundary is built and carries $`v`$ rather than being dropped.

$`t \ominus^{\mathrm{relation}(t)} k`$ denotes a translation counted inside the group a relation puts $`t`$ in (`shift(by=relation)`), so a term never crosses out of its own group. The two modifiers take different slots — the group above, the fill below — so $`t \boxminus_{v}^{\mathrm{relation}(t)} k`$ is both at once.

#### Objective

```math
\min \sum_{\xi \in \Xi,\ j \in \mathcal{J}} \pi_{\xi} \cdot Z_{j} \cdot \mathrm{c}^{\mathrm{cap},z}_{\xi,j} \cdot \mathrm{W}^{z}_{j}
```

#### Subject to

**`Process_fix_p_lower`**

```math
z_{\xi,t,j} \ge \underline{\mathrm{z}}_{\xi,t,j} \cdot \mathrm{z}^{\mathrm{nom}}_{\xi,j} \cdot \left( 1 - \gamma^{z}_{\xi,j} \cdot \mu^{z}_{\xi,t,j} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \neg \mathrm{ext}^{z}_{j} \wedge \neg \mathrm{com}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_fix_p_upper`**

```math
z_{\xi,t,j} \le \overline{\mathrm{z}}_{\xi,t,j} \cdot \mathrm{z}^{\mathrm{nom}}_{\xi,j} \cdot \left( 1 - \gamma^{z}_{\xi,j} \cdot \mu^{z}_{\xi,t,j} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \neg \mathrm{ext}^{z}_{j} \wedge \neg \mathrm{com}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_ext_p_lower`**

```math
z_{\xi,t,j} \ge \underline{\mathrm{z}}_{\xi,t,j} \cdot \left( Z_{j} - \gamma^{z}_{\xi,j} \cdot \mu^{z,\mathrm{nom}}_{\xi,t,j} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{ext}^{z}_{j} \wedge \neg \mathrm{com}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_ext_p_upper`**

```math
z_{\xi,t,j} \le \overline{\mathrm{z}}_{\xi,t,j} \cdot \left( Z_{j} - \gamma^{z}_{\xi,j} \cdot \mu^{z,\mathrm{nom}}_{\xi,t,j} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{ext}^{z}_{j} \wedge \neg \mathrm{com}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_ext_p_nom_lower`**

```math
Z_{j} \ge \underline{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} \qquad \forall\, \xi \in \Xi,\ j \in \mathcal{J} \,:\, \mathrm{ext}^{z}_{j}
```

**`Process_ext_p_nom_upper`**

```math
Z_{j} \le \overline{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} \qquad \forall\, \xi \in \Xi,\ j \in \mathcal{J} \,:\, \mathrm{ext}^{z}_{j} \wedge \overline{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} \text{ is defined}
```

**`Process_p_nom_set`**

```math
Z_{j} = \mathrm{z}^{\mathrm{nom,set}}_{\xi,j} \qquad \forall\, \xi \in \Xi,\ j \in \mathcal{J} \,:\, \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{nom,set}}_{\xi,j} \text{ is defined}
```

**`Process_p_nom_modularity`**

```math
Z_{j} = \mathrm{z}^{\mathrm{mod}}_{j} \cdot N^{z}_{j} \qquad \forall\, j \in \mathcal{J} \,:\, \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0
```

**`Process_p_set`**

```math
z_{\xi,t,j} = \mathrm{z}^{\mathrm{set}}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{z}^{\mathrm{set}}_{\xi,t,j} \text{ is defined} \wedge \mathrm{on}^{z}_{t,j}
```

#### Definitions

**`Process_p_nom_effective`**

```math
\widetilde{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} = \begin{cases} Z_{j} & \text{if } \mathrm{ext}^{z}_{j} \\ \mathrm{z}^{\mathrm{nom}}_{\xi,j} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ j \in \mathcal{J}
```

**`Process_p_nom_committed`**

```math
\widehat{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} = \begin{cases} \mathrm{z}^{\mathrm{mod}}_{j} & \text{if } \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \\ \mathrm{z}^{\mathrm{nom}}_{\xi,j} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ j \in \mathcal{J}
```

**`Process_output_arrival`**

```math
\overrightarrow{z}_{\xi,t,r} = \begin{cases} z_{\xi,t \ominus^{\mathrm{snapshot\_period}(t)} \mathrm{d}^{z},\mathrm{Process\_output\_process}(r)} \cdot \alpha_{\xi,r} & \text{if } \mathrm{cyc}^{z}_{\xi,r} \\ z_{\xi,t \boxminus_{0}^{\mathrm{snapshot\_period}(t)} \mathrm{d}^{z},\mathrm{Process\_output\_process}(r)} \cdot \alpha_{\xi,r} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ r \in \mathcal{R}
```

**`Process_tech_capacity_expansion`**

```math
\mathit{Process\_tech\_capacity\_expansion}_{g} = \sum_{j \in \mathcal{J}} Z_{j} \cdot \mathrm{m}^{z}_{g,j} \qquad \forall\, g \in \mathcal{G}
```

**`Process_opex`**

```math
\mathit{Process\_opex}_{\xi} = \sum_{t \in \mathcal{T}} \sum_{j \in \mathcal{J}} z_{\xi,t,j} \cdot \mathrm{c}^{z}_{\xi,t,j} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{j \in \mathcal{J}} z_{\xi,t,j} \cdot z_{\xi,t,j} \cdot \mathrm{c}^{z,(2)}_{\xi,t,j} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} \qquad \forall\, \xi \in \Xi
```

**`Process_additions`**

```math
\mathit{Process\_additions}_{y,i} = \sum_{j \in \mathcal{J} \,:\, \mathrm{Process\_carrier}(j) = i} Z_{j} \cdot \mathrm{new}^{z}_{y,j} \qquad \forall\, y \in \mathcal{Y},\ i \in \mathcal{I}
```

**`Process_injection`**

```math
\mathit{Process\_injection}_{\xi,t,n} = \sum_{r \in \mathcal{R} \,:\, \mathrm{Process\_output\_bus}(r) = n} \overrightarrow{z}_{\xi,t,r} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ n \in \mathcal{N}
```

#### Variable domains

**`Process_p`**

```math
z_{\xi,t,j} \in \mathbb{R} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{on}^{z}_{t,j}
```

**`Process_n_mod`**

```math
N^{z}_{j} \ge 0, N^{z}_{j} \in \mathbb{Z} \qquad \forall\, j \in \mathcal{J} \,:\, \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0
```

**`Process_p_nom_ext`**

```math
Z_{j} \in \mathbb{R} \qquad \forall\, j \in \mathcal{J} \,:\, \mathrm{ext}^{z}_{j}
```

#### Assumptions

**`Process_marginal_cost_quadratic_without_risk_preference`**

```math
\mathrm{c}^{z,(2)}_{\xi,t,j} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \omega > 0
```
<!-- gallery:end -->
