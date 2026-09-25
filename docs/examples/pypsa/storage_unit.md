<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Storage units

One of the [24 fragments](index.md) of `examples/pypsa.yaml`: PyPSA's `StorageUnit`. It adds a term to `primary_energy`, `operational_limit`, `tech_capacity_expansion`, `scenario_opex`, `Carrier_additions`, `Bus_injection`. It reads `CVaR_omega`, `GlobalConstraint_counts_snapshot`, `GlobalConstraint_snapshot_closes`, `period_weight_objective`, `period_weight_years`, `scenario_weight` and 2 more under [`given`](../../reference/language/declarations.md#given).

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
  storage_unit:
    description: storage units, dispatch and store behind one bus connection
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
  StorageUnit_carrier:
    description: the carrier a storage unit converts from
    key: storage_unit
    values: carrier
  StorageUnit_bus:
    description: the bus a storage unit sits on
    key: storage_unit
    values: bus

parameters:
  StorageUnit_active:
    description: whether a storage unit stands in a snapshot's period — PyPSA's `active`, data prep
    dims: [snapshot, storage_unit]
    dtype: bool
  StorageUnit_capital_weight:
    description: the sum of period weights a storage unit stands in — PyPSA's `active * period_weighting`, summed, data prep
    dims: [storage_unit]
  StorageUnit_first_active:
    description: >-
      one in the first period a storage unit stands in, zero elsewhere, data prep.
      PyPSA `1.3.0` takes `active.cumsum() == 1`, which also counts a storage unit
      that has retired in every later period (`global_constraints.py:276`,
      PyPSA/PyPSA#1938)
    dims: [period, storage_unit]
  StorageUnit_p_nom_min:
    description: least nominal power an extendable storage unit may be built at
    dims: [scenario, storage_unit]
  StorageUnit_p_nom_max:
    description: most nominal power an extendable storage unit may be built at
    dims: [scenario, storage_unit]
  StorageUnit_capital_cost:
    description: cost of one unit of nominal power — PyPSA's `capital_cost`, periodized as an annuity in data prep
    dims: [scenario, storage_unit]
  StorageUnit_p_nom_set:
    description: a given nominal power for an extendable storage unit; one without a value has no row here
    dims: [scenario, storage_unit]
  StorageUnit_p_nom:
    description: nominal power
    dims: [scenario, storage_unit]
  StorageUnit_p_nom_extendable:
    description: whether the nominal power is a decision
    dims: [storage_unit]
    dtype: bool
  StorageUnit_p_min_pu:
    description: most storing, per unit of nominal power and negated
    dims: [scenario, snapshot, storage_unit]
  StorageUnit_p_max_pu:
    description: most dispatch, per unit of nominal power
    dims: [scenario, snapshot, storage_unit]
  StorageUnit_max_hours:
    description: energy capacity, as hours of dispatch at nominal power
    dims: [scenario, storage_unit]
  StorageUnit_efficiency_store:
    description: share of the power drawn from the bus that becomes charge
    dims: [scenario, storage_unit]
  StorageUnit_efficiency_dispatch:
    description: share of the charge drawn down that reaches the bus
    dims: [scenario, storage_unit]
  StorageUnit_sign:
    description: >-
      the sign net dispatch enters its bus's balance with — PyPSA's `sign`,
      `1` unless given. PyPSA refuses one that differs by scenario
      (`consistency.py:1187`)
    dims: [storage_unit]
  StorageUnit_retention:
    description: share of charge kept over a snapshot — PyPSA's `(1 - standing_loss) ** elapsed hours`, data prep
    dims: [scenario, snapshot, storage_unit]
  StorageUnit_inflow:
    description: energy arriving per hour, a river into a reservoir
    dims: [scenario, snapshot, storage_unit]
  StorageUnit_state_of_charge_initial:
    description: charge held before the first snapshot
    dims: [scenario, storage_unit]
  StorageUnit_cyclic_state_of_charge:
    description: whether the horizon closes on itself instead of opening on the initial charge
    dims: [scenario, storage_unit]
    dtype: bool
  StorageUnit_cyclic_state_of_charge_per_period:
    description: >-
      whether each investment period closes on itself instead of carrying its
      charge on to the next; it overrides `cyclic_state_of_charge` and
      `state_of_charge_initial_per_period`. PyPSA reads it only under
      `multi_investment_periods`, so data prep feeds false otherwise
    dims: [scenario, storage_unit]
    dtype: bool
  StorageUnit_state_of_charge_initial_per_period:
    description: >-
      whether each investment period opens on the initial charge instead of
      carrying the previous period's; PyPSA reads it only under
      `multi_investment_periods`, so data prep feeds false otherwise
    dims: [scenario, storage_unit]
    dtype: bool
  StorageUnit_opens_late:
    description: >-
      whether a snapshot is the first a storage unit stands in, where that is
      not the first of the horizon — PyPSA's `active.cumsum() == 1` over the
      snapshots it stands in, past the first snapshot, data prep; false in a
      run where every unit stands throughout
    dims: [snapshot, storage_unit]
    dtype: bool
  StorageUnit_inactive_snapshots:
    description: >-
      how many snapshots a storage unit does not stand in — PyPSA's
      `(~active).sum()`, data prep. A cyclic unit reaches back this many
      snapshots further, so it closes on the last snapshot it stands in
    dims: [storage_unit]
    dtype: int
  StorageUnit_marginal_cost:
    description: cost of one unit of dispatch
    dims: [scenario, snapshot, storage_unit]
  StorageUnit_marginal_cost_quadratic:
    description: cost of the square of one unit of dispatch; storing is not charged
    dims: [scenario, snapshot, storage_unit]
  StorageUnit_marginal_cost_storage:
    description: cost of one unit of charge held over one snapshot
    dims: [scenario, snapshot, storage_unit]
  StorageUnit_spill_cost:
    description: cost of one unit of inflow passed on unused
    dims: [scenario, snapshot, storage_unit]
  StorageUnit_p_set:
    description: a given net dispatch schedule; a unit without one has no row here
    dims: [scenario, snapshot, storage_unit]
  StorageUnit_p_dispatch_set:
    description: a given dispatch schedule; a unit without one has no row here
    dims: [scenario, snapshot, storage_unit]
  StorageUnit_p_store_set:
    description: a given charging schedule; a unit without one has no row here
    dims: [scenario, snapshot, storage_unit]
  StorageUnit_state_of_charge_set:
    description: a given charge schedule; a unit without one has no row here
    dims: [scenario, snapshot, storage_unit]
  StorageUnit_primary_energy_weight:
    description: the constrained attribute per unit of charge depleted — data prep; an unweighted unit has no row
    dims: [scenario, global_constraint, storage_unit]
  StorageUnit_operational_limit_weight:
    description: one where the storage unit is in the row's set — data prep; one outside it has no row
    dims: [scenario, global_constraint, storage_unit]
  StorageUnit_tech_capacity_weight:
    description: >-
      one where the storage unit is in the row's carrier-and-bus set — data prep; one
      outside it, or one that does not stand in the row's `investment_period`,
      has no row
    dims: [global_constraint, storage_unit]

variables:
  StorageUnit_p_dispatch:
    description: "`StorageUnit-p_dispatch` — power delivered to the bus"
    dims: [scenario, snapshot, storage_unit]
    where: StorageUnit_active
  StorageUnit_p_store:
    description: "`StorageUnit-p_store` — power drawn from the bus into charge"
    dims: [scenario, snapshot, storage_unit]
    where: StorageUnit_active
  StorageUnit_state_of_charge:
    description: "`StorageUnit-state_of_charge` — energy held at the end of a snapshot"
    dims: [scenario, snapshot, storage_unit]
    where: StorageUnit_active
  StorageUnit_spill:
    description: >-
      `StorageUnit-spill` — inflow passed on unused. Zero where there is no
      inflow, so the balance keeps its row there; the bounds are PyPSA's, on
      the variable rather than as rows
    dims: [scenario, snapshot, storage_unit]
    where: "StorageUnit_inflow > 0 AND StorageUnit_active"
    absence: zero
    bounds:
      lower: 0
      upper: StorageUnit_inflow
  StorageUnit_p_nom_ext:
    description: >-
      `StorageUnit-p_nom` — nominal power where it is a decision; the
      parameter of the same PyPSA name carries the fixed regime
    dims: [storage_unit]
    where: StorageUnit_p_nom_extendable

given:
  parameters:
    snapshot_weightings_objective: { dims: [snapshot] }
    scenario_weight: { dims: [scenario] }
    CVaR_omega: { dims: [] }
    period_weight_objective: { dims: [period] }
    period_weight_years: { dims: [period] }
    snapshot_weightings_stores: { dims: [snapshot] }
    GlobalConstraint_counts_snapshot: { dims: [scenario, global_constraint, snapshot], dtype: bool }
  expressions:
    GlobalConstraint_snapshot_closes: { dims: [scenario, global_constraint, snapshot] }
    primary_energy: { dims: [scenario, global_constraint], term: StorageUnit_primary_energy }
    operational_limit: { dims: [scenario, global_constraint], term: StorageUnit_operational_limit }
    tech_capacity_expansion: { dims: [global_constraint], term: StorageUnit_tech_capacity_expansion }
    scenario_opex: { dims: [scenario], term: StorageUnit_opex }
    Carrier_additions: { dims: [period, carrier], term: StorageUnit_additions }
    Bus_injection: { dims: [scenario, snapshot, bus], term: StorageUnit_injection }

expressions:
  StorageUnit_charge_carried_in:
    description: >-
      the charge a unit opens a snapshot with — at the first snapshot it
      stands in, its last such snapshot's less standing loss where it is
      cyclic and the given initial charge, which no standing loss has touched
      yet, where it is not; the previous snapshot's less standing loss
      otherwise. A unit built in a later period opens in that period, and a
      cyclic one that retires closes on its own last snapshot. Per period, the
      same holds with each investment period as the horizon
    dims: [scenario, snapshot, storage_unit]
    cases:
      cyclic:
        when: >-
          StorageUnit_cyclic_state_of_charge AND NOT StorageUnit_cyclic_state_of_charge_per_period
          AND NOT StorageUnit_state_of_charge_initial_per_period
          AND (position(snapshot) == 0 OR StorageUnit_opens_late)
        expression: >-
          StorageUnit_retention
          * shift(shift(StorageUnit_state_of_charge, along=snapshot, offset=1, edge='wrap'), along=snapshot, offset=StorageUnit_inactive_snapshots, edge='wrap')
      opening:
        when: >-
          NOT StorageUnit_cyclic_state_of_charge AND NOT StorageUnit_cyclic_state_of_charge_per_period
          AND NOT StorageUnit_state_of_charge_initial_per_period
          AND (position(snapshot) == 0 OR StorageUnit_opens_late)
        expression: StorageUnit_state_of_charge_initial
      period_cyclic:
        when: StorageUnit_cyclic_state_of_charge_per_period
        expression: >-
          StorageUnit_retention
          * shift(StorageUnit_state_of_charge, along=snapshot, offset=1, edge='wrap', by=snapshot_period, within=period)
      period_opening:
        when: >-
          StorageUnit_state_of_charge_initial_per_period AND NOT StorageUnit_cyclic_state_of_charge_per_period
          AND position(snapshot, by=snapshot_period, within=period) == 0
        expression: StorageUnit_state_of_charge_initial
    otherwise: StorageUnit_retention * shift(StorageUnit_state_of_charge, along=snapshot, offset=1)
  StorageUnit_closing_weight:
    description: >-
      what the charge a unit holds at a snapshot counts for in a row as its
      closing level — the years of the period at the last snapshot of each
      counted period where the unit reopens per period, one at the last
      counted snapshot where it does not, and nothing elsewhere
    dims: [scenario, global_constraint, snapshot, storage_unit]
    cases:
      per_period:
        when: StorageUnit_state_of_charge_initial_per_period AND GlobalConstraint_counts_snapshot AND position(snapshot, by=snapshot_period, within=period) == -1
        expression: at(period_weight_years, by=snapshot_period, over=period, into=snapshot)
      carried_over:
        when: NOT StorageUnit_state_of_charge_initial_per_period
        expression: GlobalConstraint_snapshot_closes
    otherwise: 0
  StorageUnit_primary_energy:
    expression: >-
      -sum(sum((StorageUnit_state_of_charge * StorageUnit_closing_weight) * StorageUnit_primary_energy_weight, over=snapshot), over=storage_unit)
  StorageUnit_operational_limit:
    expression: >-
      -sum(sum((StorageUnit_state_of_charge * StorageUnit_closing_weight) * StorageUnit_operational_limit_weight, over=snapshot), over=storage_unit)
  StorageUnit_tech_capacity_expansion:
    expression: sum(StorageUnit_p_nom_ext * StorageUnit_tech_capacity_weight, over=storage_unit)
  StorageUnit_opex:
    expression: >-
      sum(sum(((StorageUnit_p_dispatch * StorageUnit_marginal_cost) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=storage_unit), over=snapshot)
      + sum(sum((((StorageUnit_p_dispatch * StorageUnit_p_dispatch) * StorageUnit_marginal_cost_quadratic) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=storage_unit), over=snapshot)
      + sum(sum(((StorageUnit_state_of_charge * StorageUnit_marginal_cost_storage) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=storage_unit), over=snapshot)
      + sum(sum(((StorageUnit_spill * StorageUnit_spill_cost) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=storage_unit), over=snapshot)
  StorageUnit_additions:
    expression: >-
      sum(StorageUnit_p_nom_ext * StorageUnit_first_active, by=StorageUnit_carrier, over=storage_unit, into=carrier)
  StorageUnit_injection:
    expression: >-
      sum(StorageUnit_sign * (StorageUnit_p_dispatch - StorageUnit_p_store), by=StorageUnit_bus, over=storage_unit, into=bus)

constraints:
  StorageUnit_fix_p_dispatch_lower:
    description: "`StorageUnit-fix-p_dispatch-lower` — dispatch is non-negative"
    dims: [scenario, snapshot, storage_unit]
    where: not StorageUnit_p_nom_extendable AND StorageUnit_active
    expression: StorageUnit_p_dispatch >= 0
  StorageUnit_fix_p_dispatch_upper:
    description: "`StorageUnit-fix-p_dispatch-upper` — a fixed unit dispatches at most its nominal power"
    dims: [scenario, snapshot, storage_unit]
    where: not StorageUnit_p_nom_extendable AND StorageUnit_active
    expression: StorageUnit_p_dispatch <= StorageUnit_p_max_pu * StorageUnit_p_nom
  StorageUnit_fix_p_store_lower:
    description: "`StorageUnit-fix-p_store-lower` — storing is non-negative"
    dims: [scenario, snapshot, storage_unit]
    where: not StorageUnit_p_nom_extendable AND StorageUnit_active
    expression: StorageUnit_p_store >= 0
  StorageUnit_fix_p_store_upper:
    description: >-
      `StorageUnit-fix-p_store-upper` — a fixed unit stores at most its
      nominal power, the minimum-per-unit column carrying that cap negated
    dims: [scenario, snapshot, storage_unit]
    where: not StorageUnit_p_nom_extendable AND StorageUnit_active
    expression: StorageUnit_p_store <= -StorageUnit_p_min_pu * StorageUnit_p_nom
  StorageUnit_fix_state_of_charge_lower:
    description: "`StorageUnit-fix-state_of_charge-lower` — charge is non-negative"
    dims: [scenario, snapshot, storage_unit]
    where: not StorageUnit_p_nom_extendable AND StorageUnit_active
    expression: StorageUnit_state_of_charge >= 0
  StorageUnit_fix_state_of_charge_upper:
    description: "`StorageUnit-fix-state_of_charge-upper` — a fixed unit holds at most its hours at nominal power"
    dims: [scenario, snapshot, storage_unit]
    where: not StorageUnit_p_nom_extendable AND StorageUnit_active
    expression: StorageUnit_state_of_charge <= StorageUnit_max_hours * StorageUnit_p_nom
  StorageUnit_ext_p_dispatch_lower:
    description: "`StorageUnit-ext-p_dispatch-lower` — dispatch is non-negative"
    dims: [scenario, snapshot, storage_unit]
    where: StorageUnit_p_nom_extendable AND StorageUnit_active
    expression: StorageUnit_p_dispatch >= 0
  StorageUnit_ext_p_dispatch_upper:
    description: "`StorageUnit-ext-p_dispatch-upper` — an extendable unit dispatches at most the chosen build"
    dims: [scenario, snapshot, storage_unit]
    where: StorageUnit_p_nom_extendable AND StorageUnit_active
    expression: StorageUnit_p_dispatch <= StorageUnit_p_max_pu * StorageUnit_p_nom_ext
  StorageUnit_ext_p_store_lower:
    description: "`StorageUnit-ext-p_store-lower` — storing is non-negative"
    dims: [scenario, snapshot, storage_unit]
    where: StorageUnit_p_nom_extendable AND StorageUnit_active
    expression: StorageUnit_p_store >= 0
  StorageUnit_ext_p_store_upper:
    description: >-
      `StorageUnit-ext-p_store-upper` — an extendable unit stores at most the
      chosen build, the minimum-per-unit column carrying that cap negated
    dims: [scenario, snapshot, storage_unit]
    where: StorageUnit_p_nom_extendable AND StorageUnit_active
    expression: StorageUnit_p_store <= -StorageUnit_p_min_pu * StorageUnit_p_nom_ext
  StorageUnit_ext_state_of_charge_lower:
    description: "`StorageUnit-ext-state_of_charge-lower` — charge is non-negative"
    dims: [scenario, snapshot, storage_unit]
    where: StorageUnit_p_nom_extendable AND StorageUnit_active
    expression: StorageUnit_state_of_charge >= 0
  StorageUnit_ext_state_of_charge_upper:
    description: "`StorageUnit-ext-state_of_charge-upper` — an extendable unit holds at most its hours at the chosen build"
    dims: [scenario, snapshot, storage_unit]
    where: StorageUnit_p_nom_extendable AND StorageUnit_active
    expression: StorageUnit_state_of_charge <= StorageUnit_max_hours * StorageUnit_p_nom_ext
  StorageUnit_ext_p_nom_lower:
    description: "`StorageUnit-ext-p_nom-lower` — the chosen build is at least its floor in every scenario"
    dims: [scenario, storage_unit]
    where: StorageUnit_p_nom_extendable
    expression: StorageUnit_p_nom_ext >= StorageUnit_p_nom_min
  StorageUnit_ext_p_nom_upper:
    description: "`StorageUnit-ext-p_nom-upper` — the chosen build is at most its cap in every scenario; a cap of infinity is no row"
    dims: [scenario, storage_unit]
    where: StorageUnit_p_nom_extendable AND StorageUnit_p_nom_max
    expression: StorageUnit_p_nom_ext <= StorageUnit_p_nom_max
  StorageUnit_p_nom_set:
    description: "`StorageUnit-p_nom_set` — the chosen build pinned, wherever a value is given"
    dims: [scenario, storage_unit]
    where: StorageUnit_p_nom_extendable AND StorageUnit_p_nom_set
    expression: StorageUnit_p_nom_ext == StorageUnit_p_nom_set
  StorageUnit_energy_balance:
    description: >-
      `StorageUnit-energy_balance` — the charge carried in, plus what is
      stored after its efficiency, less what dispatch draws down before its
      own, plus inflow not spilled
    dims: [scenario, snapshot, storage_unit]
    where: StorageUnit_active
    expression: >-
      StorageUnit_state_of_charge ==
      StorageUnit_charge_carried_in
      + StorageUnit_efficiency_store * StorageUnit_p_store * snapshot_weightings_stores
      - StorageUnit_p_dispatch * snapshot_weightings_stores / StorageUnit_efficiency_dispatch
      + (StorageUnit_inflow - StorageUnit_spill) * snapshot_weightings_stores
  StorageUnit_p_set:
    description: "`StorageUnit-p_set` — net dispatch pinned to the given schedule, wherever one is given"
    dims: [scenario, snapshot, storage_unit]
    where: StorageUnit_p_set AND StorageUnit_active
    expression: StorageUnit_p_dispatch - StorageUnit_p_store == StorageUnit_p_set
  StorageUnit_p_dispatch_set:
    description: "`StorageUnit-p_dispatch_set` — dispatch pinned to the given schedule, wherever one is given"
    dims: [scenario, snapshot, storage_unit]
    where: StorageUnit_p_dispatch_set AND StorageUnit_active
    expression: StorageUnit_p_dispatch == StorageUnit_p_dispatch_set
  StorageUnit_p_store_set:
    description: "`StorageUnit-p_store_set` — charging pinned to the given schedule, wherever one is given"
    dims: [scenario, snapshot, storage_unit]
    where: StorageUnit_p_store_set AND StorageUnit_active
    expression: StorageUnit_p_store == StorageUnit_p_store_set
  StorageUnit_state_of_charge_set:
    description: "`StorageUnit-state_of_charge_set` — charge pinned to the given schedule, wherever one is given"
    dims: [scenario, snapshot, storage_unit]
    where: StorageUnit_state_of_charge_set AND StorageUnit_active
    expression: StorageUnit_state_of_charge == StorageUnit_state_of_charge_set

assumptions:
  StorageUnit_stands_in_one_run:
    holds: "count(StorageUnit_active AND NOT shift(StorageUnit_active, along=snapshot, offset=1), over=snapshot) <= 1"
    description: >-
      the snapshots a storage unit stands in are one unbroken run, as a build
      year and a lifetime make them. The opening row holds at the first
      of them only, and a cyclic storage unit reaches back
      `StorageUnit_inactive_snapshots` further to the last of them
  StorageUnit_opens_late_only_where_it_opens:
    holds: "StorageUnit_active AND NOT shift(StorageUnit_active, along=snapshot, offset=1) AND position(snapshot) > 0"
    where: "StorageUnit_opens_late"
    description: >-
      `StorageUnit_opens_late` marks the first snapshot the storage unit stands in, past
      the first of the horizon, and no other
  StorageUnit_opens_late_where_it_opens:
    holds: "StorageUnit_opens_late"
    where: "StorageUnit_active AND NOT shift(StorageUnit_active, along=snapshot, offset=1) AND position(snapshot) > 0"
    description: >-
      a storage unit that opens past the first snapshot of the horizon opens on
      its initial level, or its last level where it is cyclic, only where
      `StorageUnit_opens_late` marks the snapshot
  StorageUnit_primary_energy_per_period_closes_over_the_horizon:
    holds: "count(NOT GlobalConstraint_counts_snapshot, over=snapshot) == 0"
    where: "StorageUnit_primary_energy_weight AND StorageUnit_state_of_charge_initial_per_period"
    description: >-
      PyPSA reads the closing charge of a unit that reopens per period at
      the last snapshot of every period, and fails on a `primary_energy` row
      that names an `investment_period` (`global_constraints.py:474`)
  StorageUnit_primary_energy_carried_over_has_unit_years:
    holds: "period_weight_years == 1"
    where: "StorageUnit_primary_energy_weight AND NOT StorageUnit_state_of_charge_initial_per_period"
    description: >-
      a unit that carries its charge from one period to the next closes
      once, at the last counted snapshot, and no period's years weighs that
      level — PyPSA refuses it where any period's years is not one
      (`global_constraints.py:448`)
  StorageUnit_operational_limit_carried_over_has_unit_years:
    holds: "at(period_weight_years == 1, by=snapshot_period, over=period, into=snapshot)"
    where: "StorageUnit_operational_limit_weight AND NOT StorageUnit_state_of_charge_initial_per_period AND GlobalConstraint_counts_snapshot"
    description: >-
      the same for an `operational_limit` row, over the periods it counts —
      PyPSA refuses it (`global_constraints.py:647`)
  StorageUnit_marginal_cost_quadratic_without_risk_preference:
    holds: "StorageUnit_marginal_cost_quadratic == 0"
    where: "CVaR_omega > 0"
    description: >-
      a quadratic cost puts a square into every `CVaR-excess` row, and PyPSA
      refuses quadratic costs under any risk preference
      (`optimize.py:467-474`). The spec cannot tell no risk preference from
      one with `omega = 0`, so it refuses only where `omega` is positive

objective:
  sense: minimize
  expression: >-
    sum(((scenario_weight * StorageUnit_p_nom_ext) * StorageUnit_capital_cost) * StorageUnit_capital_weight)
```

#### Sets

| Symbol | Meaning |
|---|---|
| $`\Xi`$ | index $`\xi`$ — `scenario` — the futures dispatch is chosen in, each with a weight |
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` with $`\mathrm{snapshot\_period}: \mathcal{T} \to \mathcal{Y}`$ — dispatch periods |
| $`\mathcal{N}`$ | index $`n`$ — `bus` with $`\mathrm{StorageUnit\_bus}: \mathcal{S} \to \mathcal{N}`$ — network nodes |
| $`\mathcal{S}`$ | index $`s`$ — `storage_unit` with $`\mathrm{StorageUnit\_carrier}: \mathcal{S} \to \mathcal{I},\ \mathrm{StorageUnit\_bus}: \mathcal{S} \to \mathcal{N}`$ — storage units, dispatch and store behind one bus connection |
| $`\mathcal{G}`$ | index $`g`$ — `global_constraint` — PyPSA's `GlobalConstraint` rows, one label per declared limit |
| $`\mathcal{Y}`$ | index $`y`$ — `period` with $`\mathrm{snapshot\_period}: \mathcal{T} \to \mathcal{Y}`$ — investment periods — PyPSA's `investment_periods` |
| $`\mathcal{I}`$ | index $`i`$ — `carrier` with $`\mathrm{StorageUnit\_carrier}: \mathcal{S} \to \mathcal{I}`$ — energy carriers, what a growth limit is set per |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{on}^{h}`$ | `StorageUnit_active` over $`\mathcal{T} \times \mathcal{S}`$ — whether a storage unit stands in a snapshot's period — PyPSA's `active`, data prep |
| $`\mathrm{W}^{h}`$ | `StorageUnit_capital_weight` over $`\mathcal{S}`$ — the sum of period weights a storage unit stands in — PyPSA's `active * period_weighting`, summed, data prep |
| $`\mathrm{new}^{h}`$ | `StorageUnit_first_active` over $`\mathcal{Y} \times \mathcal{S}`$ — one in the first period a storage unit stands in, zero elsewhere, data prep. PyPSA `1.3.0` takes `active.cumsum() == 1`, which also counts a storage unit that has retired in every later period (`global_constraints.py:276`, PyPSA/PyPSA\#1938) |
| $`\underline{\mathrm{h}}^{\mathrm{nom}}`$ | `StorageUnit_p_nom_min` over $`\Xi \times \mathcal{S}`$ — least nominal power an extendable storage unit may be built at |
| $`\overline{\mathrm{h}}^{\mathrm{nom}}`$ | `StorageUnit_p_nom_max` over $`\Xi \times \mathcal{S}`$ — most nominal power an extendable storage unit may be built at |
| $`\mathrm{c}^{\mathrm{cap},h}`$ | `StorageUnit_capital_cost` over $`\Xi \times \mathcal{S}`$ — cost of one unit of nominal power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $`\mathrm{h}^{\mathrm{nom,set}}`$ | `StorageUnit_p_nom_set` over $`\Xi \times \mathcal{S}`$ — a given nominal power for an extendable storage unit; one without a value has no row here |
| $`\mathrm{h}^{\mathrm{nom}}`$ | `StorageUnit_p_nom` over $`\Xi \times \mathcal{S}`$ — nominal power |
| $`\mathrm{ext}^{h}`$ | `StorageUnit_p_nom_extendable` over $`\mathcal{S}`$ — whether the nominal power is a decision |
| $`\underline{\mathrm{h}}`$ | `StorageUnit_p_min_pu` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — most storing, per unit of nominal power and negated |
| $`\overline{\mathrm{h}}`$ | `StorageUnit_p_max_pu` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — most dispatch, per unit of nominal power |
| $`\mathrm{T}^{h}`$ | `StorageUnit_max_hours` over $`\Xi \times \mathcal{S}`$ — energy capacity, as hours of dispatch at nominal power |
| $`\eta^{-}`$ | `StorageUnit_efficiency_store` over $`\Xi \times \mathcal{S}`$ — share of the power drawn from the bus that becomes charge |
| $`\eta^{+}`$ | `StorageUnit_efficiency_dispatch` over $`\Xi \times \mathcal{S}`$ — share of the charge drawn down that reaches the bus |
| $`\mathrm{sgn}^{h}`$ | `StorageUnit_sign` over $`\mathcal{S}`$ — the sign net dispatch enters its bus's balance with — PyPSA's `sign`, `1` unless given. PyPSA refuses one that differs by scenario (`consistency.py:1187`) |
| $`\rho`$ | `StorageUnit_retention` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — share of charge kept over a snapshot — PyPSA's `(1 - standing_loss) ** elapsed hours`, data prep |
| $`\mathrm{inflow}`$ | `StorageUnit_inflow` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — energy arriving per hour, a river into a reservoir |
| $`\mathrm{soc}^{0}`$ | `StorageUnit_state_of_charge_initial` over $`\Xi \times \mathcal{S}`$ — charge held before the first snapshot |
| $`\mathrm{cyc}`$ | `StorageUnit_cyclic_state_of_charge` over $`\Xi \times \mathcal{S}`$ — whether the horizon closes on itself instead of opening on the initial charge |
| $`\mathrm{cyc}^{y}`$ | `StorageUnit_cyclic_state_of_charge_per_period` over $`\Xi \times \mathcal{S}`$ — whether each investment period closes on itself instead of carrying its charge on to the next; it overrides `cyclic_state_of_charge` and `state_of_charge_initial_per_period`. PyPSA reads it only under `multi_investment_periods`, so data prep feeds false otherwise |
| $`\mathrm{reset}`$ | `StorageUnit_state_of_charge_initial_per_period` over $`\Xi \times \mathcal{S}`$ — whether each investment period opens on the initial charge instead of carrying the previous period's; PyPSA reads it only under `multi_investment_periods`, so data prep feeds false otherwise |
| $`\mathrm{open}`$ | `StorageUnit_opens_late` over $`\mathcal{T} \times \mathcal{S}`$ — whether a snapshot is the first a storage unit stands in, where that is not the first of the horizon — PyPSA's `active.cumsum() == 1` over the snapshots it stands in, past the first snapshot, data prep; false in a run where every unit stands throughout |
| $`\mathrm{idle}`$ | `StorageUnit_inactive_snapshots` over $`\mathcal{S}`$ — how many snapshots a storage unit does not stand in — PyPSA's `(~active).sum()`, data prep. A cyclic unit reaches back this many snapshots further, so it closes on the last snapshot it stands in |
| $`\mathrm{c}^{h}`$ | `StorageUnit_marginal_cost` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — cost of one unit of dispatch |
| $`\mathrm{c}^{h,(2)}`$ | `StorageUnit_marginal_cost_quadratic` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — cost of the square of one unit of dispatch; storing is not charged |
| $`\mathrm{c}^{\mathrm{soc}}`$ | `StorageUnit_marginal_cost_storage` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — cost of one unit of charge held over one snapshot |
| $`\mathrm{c}^{\mathrm{spill}}`$ | `StorageUnit_spill_cost` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — cost of one unit of inflow passed on unused |
| $`\mathrm{h}^{\mathrm{set}}`$ | `StorageUnit_p_set` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — a given net dispatch schedule; a unit without one has no row here |
| $`\mathrm{h}^{+,\mathrm{set}}`$ | `StorageUnit_p_dispatch_set` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — a given dispatch schedule; a unit without one has no row here |
| $`\mathrm{h}^{-,\mathrm{set}}`$ | `StorageUnit_p_store_set` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — a given charging schedule; a unit without one has no row here |
| $`\mathrm{soc}^{\mathrm{set}}`$ | `StorageUnit_state_of_charge_set` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — a given charge schedule; a unit without one has no row here |
| $`\mathrm{a}^{h}`$ | `StorageUnit_primary_energy_weight` over $`\Xi \times \mathcal{G} \times \mathcal{S}`$ — the constrained attribute per unit of charge depleted — data prep; an unweighted unit has no row |
| $`\mathrm{b}^{h}`$ | `StorageUnit_operational_limit_weight` over $`\Xi \times \mathcal{G} \times \mathcal{S}`$ — one where the storage unit is in the row's set — data prep; one outside it has no row |
| $`\mathrm{m}^{h}`$ | `StorageUnit_tech_capacity_weight` over $`\mathcal{G} \times \mathcal{S}`$ — one where the storage unit is in the row's carrier-and-bus set — data prep; one outside it, or one that does not stand in the row's `investment_period`, has no row |

#### Variables

| Symbol | Meaning |
|---|---|
| $`h^{+}`$ | `StorageUnit_p_dispatch` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — `StorageUnit-p_dispatch` — power delivered to the bus |
| $`h^{-}`$ | `StorageUnit_p_store` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — `StorageUnit-p_store` — power drawn from the bus into charge |
| $`\mathit{soc}`$ | `StorageUnit_state_of_charge` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — `StorageUnit-state_of_charge` — energy held at the end of a snapshot |
| $`\mathit{spill}`$ | `StorageUnit_spill` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — `StorageUnit-spill` — inflow passed on unused. Zero where there is no inflow, so the balance keeps its row there; the bounds are PyPSA's, on the variable rather than as rows |
| $`H`$ | `StorageUnit_p_nom_ext` over $`\mathcal{S}`$ — `StorageUnit-p_nom` — nominal power where it is a decision; the parameter of the same PyPSA name carries the fixed regime |

#### Given

| Symbol | Meaning |
|---|---|
| $`\mathrm{w}`$ | `snapshot_weightings_objective` over $`\mathcal{T}`$, data another file declares |
| $`\pi`$ | `scenario_weight` over $`\Xi`$, data another file declares |
| $`\omega`$ | `CVaR_omega` (scalar), data another file declares |
| $`\mathrm{w}^{y}`$ | `period_weight_objective` over $`\mathcal{Y}`$, data another file declares |
| $`\mathrm{w}^{\mathrm{yr}}`$ | `period_weight_years` over $`\mathcal{Y}`$, data another file declares |
| $`\mathrm{w}^{\mathrm{sto}}`$ | `snapshot_weightings_stores` over $`\mathcal{T}`$, data another file declares |
| $`\mathrm{in}`$ | `GlobalConstraint_counts_snapshot` over $`\Xi \times \mathcal{G} \times \mathcal{T}`$, data another file declares |
| $`\mathit{last}`$ | `GlobalConstraint_snapshot_closes` over $`\Xi \times \mathcal{G} \times \mathcal{T}`$, an expression another file defines |
| $`\mathit{primary\_energy}`$ | `primary_energy` over $`\Xi \times \mathcal{G}`$, an expression this file adds `StorageUnit_primary_energy` to |
| $`\mathit{operational\_limit}`$ | `operational_limit` over $`\Xi \times \mathcal{G}`$, an expression this file adds `StorageUnit_operational_limit` to |
| $`\mathit{tech\_capacity\_expansion}`$ | `tech_capacity_expansion` over $`\mathcal{G}`$, an expression this file adds `StorageUnit_tech_capacity_expansion` to |
| $`\mathit{scenario\_opex}`$ | `scenario_opex` over $`\Xi`$, an expression this file adds `StorageUnit_opex` to |
| $`\mathit{Carrier\_additions}`$ | `Carrier_additions` over $`\mathcal{Y} \times \mathcal{I}`$, an expression this file adds `StorageUnit_additions` to |
| $`\mathit{Bus\_injection}`$ | `Bus_injection` over $`\Xi \times \mathcal{T} \times \mathcal{N}`$, an expression this file adds `StorageUnit_injection` to |

#### Definitions

| Symbol | Meaning |
|---|---|
| $`\overleftarrow{\mathit{soc}}`$ | `StorageUnit_charge_carried_in` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — the charge a unit opens a snapshot with — at the first snapshot it stands in, its last such snapshot's less standing loss where it is cyclic and the given initial charge, which no standing loss has touched yet, where it is not; the previous snapshot's less standing loss otherwise. A unit built in a later period opens in that period, and a cyclic one that retires closes on its own last snapshot. Per period, the same holds with each investment period as the horizon |
| $`\mathit{w}^{h}`$ | `StorageUnit_closing_weight` over $`\Xi \times \mathcal{G} \times \mathcal{T} \times \mathcal{S}`$ — what the charge a unit holds at a snapshot counts for in a row as its closing level — the years of the period at the last snapshot of each counted period where the unit reopens per period, one at the last counted snapshot where it does not, and nothing elsewhere |
| $`\mathit{StorageUnit\_primary\_energy}`$ | `StorageUnit_primary_energy` over $`\Xi \times \mathcal{G}`$ |
| $`\mathit{StorageUnit\_operational\_limit}`$ | `StorageUnit_operational_limit` over $`\Xi \times \mathcal{G}`$ |
| $`\mathit{StorageUnit\_tech\_capacity\_expansion}`$ | `StorageUnit_tech_capacity_expansion` over $`\mathcal{G}`$ |
| $`\mathit{StorageUnit\_opex}`$ | `StorageUnit_opex` over $`\Xi`$ |
| $`\mathit{StorageUnit\_additions}`$ | `StorageUnit_additions` over $`\mathcal{Y} \times \mathcal{I}`$ |
| $`\mathit{StorageUnit\_injection}`$ | `StorageUnit_injection` over $`\Xi \times \mathcal{T} \times \mathcal{N}`$ |

$`t \ominus k`$ denotes cyclic translation: index $`t-k`$ taken modulo the size of the dimension (`roll`). Plain $`t-k`$ (`shift`) has no wraparound — terms translated past the edge are simply absent.

$`t \ominus^{\mathrm{relation}(t)} k`$ denotes a translation counted inside the group a relation puts $`t`$ in (`shift(by=relation)`), so a term never crosses out of its own group.

$`\mathrm{pos}(t)`$ denotes where index $`t`$ sits along its dimension's own order — the order `shift` steps along, not the order labels sort in — counted from $`0`$. The index itself stays the coordinate, so $`t`$ compares against labels and $`\mathrm{pos}(t)`$ against positions.

$`\mathrm{pos}_{\mathrm{relation}(t)}(t)`$ counts within the group a relation puts $`t`$ in: the subscript names the map, $`\mathcal{T}_{\mathrm{relation}(t)}`$ is the group it lands in, and that group has a first position of its own.

$`\lvert \mathcal{T} \rvert`$ denotes the size of the set being counted along, and a position counted from the end prints against it — $`\lvert \mathcal{T} \rvert - 1`$ is the last position, one less than the size because the first is $`0`$.

#### Objective

```math
\min \sum_{\xi \in \Xi,\ s \in \mathcal{S}} \pi_{\xi} \cdot H_{s} \cdot \mathrm{c}^{\mathrm{cap},h}_{\xi,s} \cdot \mathrm{W}^{h}_{s}
```

#### Subject to

**`StorageUnit_fix_p_dispatch_lower`**

```math
h^{+}_{\xi,t,s} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \neg \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

**`StorageUnit_fix_p_dispatch_upper`**

```math
h^{+}_{\xi,t,s} \le \overline{\mathrm{h}}_{\xi,t,s} \cdot \mathrm{h}^{\mathrm{nom}}_{\xi,s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \neg \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

**`StorageUnit_fix_p_store_lower`**

```math
h^{-}_{\xi,t,s} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \neg \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

**`StorageUnit_fix_p_store_upper`**

```math
h^{-}_{\xi,t,s} \le -\underline{\mathrm{h}}_{\xi,t,s} \cdot \mathrm{h}^{\mathrm{nom}}_{\xi,s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \neg \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

**`StorageUnit_fix_state_of_charge_lower`**

```math
\mathit{soc}_{\xi,t,s} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \neg \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

**`StorageUnit_fix_state_of_charge_upper`**

```math
\mathit{soc}_{\xi,t,s} \le \mathrm{T}^{h}_{\xi,s} \cdot \mathrm{h}^{\mathrm{nom}}_{\xi,s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \neg \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

**`StorageUnit_ext_p_dispatch_lower`**

```math
h^{+}_{\xi,t,s} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

**`StorageUnit_ext_p_dispatch_upper`**

```math
h^{+}_{\xi,t,s} \le \overline{\mathrm{h}}_{\xi,t,s} \cdot H_{s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

**`StorageUnit_ext_p_store_lower`**

```math
h^{-}_{\xi,t,s} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

**`StorageUnit_ext_p_store_upper`**

```math
h^{-}_{\xi,t,s} \le -\underline{\mathrm{h}}_{\xi,t,s} \cdot H_{s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

**`StorageUnit_ext_state_of_charge_lower`**

```math
\mathit{soc}_{\xi,t,s} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

**`StorageUnit_ext_state_of_charge_upper`**

```math
\mathit{soc}_{\xi,t,s} \le \mathrm{T}^{h}_{\xi,s} \cdot H_{s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

**`StorageUnit_ext_p_nom_lower`**

```math
H_{s} \ge \underline{\mathrm{h}}^{\mathrm{nom}}_{\xi,s} \qquad \forall\, \xi \in \Xi,\ s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s}
```

**`StorageUnit_ext_p_nom_upper`**

```math
H_{s} \le \overline{\mathrm{h}}^{\mathrm{nom}}_{\xi,s} \qquad \forall\, \xi \in \Xi,\ s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s} \wedge \overline{\mathrm{h}}^{\mathrm{nom}}_{\xi,s} \text{ is defined}
```

**`StorageUnit_p_nom_set`**

```math
H_{s} = \mathrm{h}^{\mathrm{nom,set}}_{\xi,s} \qquad \forall\, \xi \in \Xi,\ s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s} \wedge \mathrm{h}^{\mathrm{nom,set}}_{\xi,s} \text{ is defined}
```

**`StorageUnit_energy_balance`**

```math
\mathit{soc}_{\xi,t,s} = \overleftarrow{\mathit{soc}}_{\xi,t,s} + \eta^{-}_{\xi,s} \cdot h^{-}_{\xi,t,s} \cdot \mathrm{w}^{\mathrm{sto}}_{t} - \frac{h^{+}_{\xi,t,s} \cdot \mathrm{w}^{\mathrm{sto}}_{t}}{\eta^{+}_{\xi,s}} + \left( \mathrm{inflow}_{\xi,t,s} - \mathit{spill}_{\xi,t,s} \right) \cdot \mathrm{w}^{\mathrm{sto}}_{t} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{on}^{h}_{t,s}
```

**`StorageUnit_p_set`**

```math
h^{+}_{\xi,t,s} - h^{-}_{\xi,t,s} = \mathrm{h}^{\mathrm{set}}_{\xi,t,s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{h}^{\mathrm{set}}_{\xi,t,s} \text{ is defined} \wedge \mathrm{on}^{h}_{t,s}
```

**`StorageUnit_p_dispatch_set`**

```math
h^{+}_{\xi,t,s} = \mathrm{h}^{+,\mathrm{set}}_{\xi,t,s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{h}^{+,\mathrm{set}}_{\xi,t,s} \text{ is defined} \wedge \mathrm{on}^{h}_{t,s}
```

**`StorageUnit_p_store_set`**

```math
h^{-}_{\xi,t,s} = \mathrm{h}^{-,\mathrm{set}}_{\xi,t,s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{h}^{-,\mathrm{set}}_{\xi,t,s} \text{ is defined} \wedge \mathrm{on}^{h}_{t,s}
```

**`StorageUnit_state_of_charge_set`**

```math
\mathit{soc}_{\xi,t,s} = \mathrm{soc}^{\mathrm{set}}_{\xi,t,s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{soc}^{\mathrm{set}}_{\xi,t,s} \text{ is defined} \wedge \mathrm{on}^{h}_{t,s}
```

#### Definitions

**`StorageUnit_charge_carried_in`**

```math
\overleftarrow{\mathit{soc}}_{\xi,t,s} = \begin{cases} \rho_{\xi,t,s} \cdot \mathit{soc}_{\xi,\left( t \ominus \mathrm{idle} \right) \ominus 1,s} & \text{if } \mathrm{cyc}_{\xi,s} \wedge \neg \mathrm{cyc}^{y}_{\xi,s} \wedge \neg \mathrm{reset}_{\xi,s} \wedge \left( \mathrm{pos}(t) = 0 \vee \mathrm{open}_{t,s} \right) \\ \mathrm{soc}^{0}_{\xi,s} & \text{if } \neg \mathrm{cyc}_{\xi,s} \wedge \neg \mathrm{cyc}^{y}_{\xi,s} \wedge \neg \mathrm{reset}_{\xi,s} \wedge \left( \mathrm{pos}(t) = 0 \vee \mathrm{open}_{t,s} \right) \\ \rho_{\xi,t,s} \cdot \mathit{soc}_{\xi,t \ominus^{\mathrm{snapshot\_period}(t)} 1,s} & \text{if } \mathrm{cyc}^{y}_{\xi,s} \\ \mathrm{soc}^{0}_{\xi,s} & \text{if } \mathrm{reset}_{\xi,s} \wedge \neg \mathrm{cyc}^{y}_{\xi,s} \wedge \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) = 0 \\ \rho_{\xi,t,s} \cdot \mathit{soc}_{\xi,t - 1,s} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S}
```

**`StorageUnit_closing_weight`**

```math
\mathit{w}^{h}_{\xi,g,t,s} = \begin{cases} \mathrm{w}^{\mathrm{yr}}_{\mathrm{snapshot\_period}(t)} & \text{if } \mathrm{reset}_{\xi,s} \wedge \mathrm{in}_{\xi,g,t} \wedge \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) = \lvert \mathcal{T}_{\mathrm{snapshot\_period}(t)} \rvert - 1 \\ \mathit{last}_{\xi,g,t} & \text{if } \neg \mathrm{reset}_{\xi,s} \\ 0 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G},\ t \in \mathcal{T},\ s \in \mathcal{S}
```

**`StorageUnit_primary_energy`**

```math
\mathit{StorageUnit\_primary\_energy}_{\xi,g} = -\left( \sum_{s \in \mathcal{S}} \sum_{t \in \mathcal{T}} \mathit{soc}_{\xi,t,s} \cdot \mathit{w}^{h}_{\xi,g,t,s} \cdot \mathrm{a}^{h}_{\xi,g,s} \right) \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G}
```

**`StorageUnit_operational_limit`**

```math
\mathit{StorageUnit\_operational\_limit}_{\xi,g} = -\left( \sum_{s \in \mathcal{S}} \sum_{t \in \mathcal{T}} \mathit{soc}_{\xi,t,s} \cdot \mathit{w}^{h}_{\xi,g,t,s} \cdot \mathrm{b}^{h}_{\xi,g,s} \right) \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G}
```

**`StorageUnit_tech_capacity_expansion`**

```math
\mathit{StorageUnit\_tech\_capacity\_expansion}_{g} = \sum_{s \in \mathcal{S}} H_{s} \cdot \mathrm{m}^{h}_{g,s} \qquad \forall\, g \in \mathcal{G}
```

**`StorageUnit_opex`**

```math
\mathit{StorageUnit\_opex}_{\xi} = \sum_{t \in \mathcal{T}} \sum_{s \in \mathcal{S}} h^{+}_{\xi,t,s} \cdot \mathrm{c}^{h}_{\xi,t,s} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{s \in \mathcal{S}} h^{+}_{\xi,t,s} \cdot h^{+}_{\xi,t,s} \cdot \mathrm{c}^{h,(2)}_{\xi,t,s} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{s \in \mathcal{S}} \mathit{soc}_{\xi,t,s} \cdot \mathrm{c}^{\mathrm{soc}}_{\xi,t,s} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{s \in \mathcal{S}} \mathit{spill}_{\xi,t,s} \cdot \mathrm{c}^{\mathrm{spill}}_{\xi,t,s} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} \qquad \forall\, \xi \in \Xi
```

**`StorageUnit_additions`**

```math
\mathit{StorageUnit\_additions}_{y,i} = \sum_{s \in \mathcal{S} \,:\, \mathrm{StorageUnit\_carrier}(s) = i} H_{s} \cdot \mathrm{new}^{h}_{y,s} \qquad \forall\, y \in \mathcal{Y},\ i \in \mathcal{I}
```

**`StorageUnit_injection`**

```math
\mathit{StorageUnit\_injection}_{\xi,t,n} = \sum_{s \in \mathcal{S} \,:\, \mathrm{StorageUnit\_bus}(s) = n} \mathrm{sgn}^{h}_{s} \cdot \left( h^{+}_{\xi,t,s} - h^{-}_{\xi,t,s} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ n \in \mathcal{N}
```

#### Variable domains

**`StorageUnit_p_dispatch`**

```math
h^{+}_{\xi,t,s} \in \mathbb{R} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{on}^{h}_{t,s}
```

**`StorageUnit_p_store`**

```math
h^{-}_{\xi,t,s} \in \mathbb{R} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{on}^{h}_{t,s}
```

**`StorageUnit_state_of_charge`**

```math
\mathit{soc}_{\xi,t,s} \in \mathbb{R} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{on}^{h}_{t,s}
```

**`StorageUnit_spill`**

```math
0 \le \mathit{spill}_{\xi,t,s} \le \mathrm{inflow}_{\xi,t,s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{inflow}_{\xi,t,s} > 0 \wedge \mathrm{on}^{h}_{t,s}
```

**`StorageUnit_p_nom_ext`**

```math
H_{s} \in \mathbb{R} \qquad \forall\, s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s}
```

#### Assumptions

**`StorageUnit_stands_in_one_run`**

```math
\lvert \{ t \in \mathcal{T} \,:\, \mathrm{on}^{h}_{t,s} \wedge \neg \mathrm{on}^{h}_{t - 1,s} \} \rvert \le 1 \qquad \forall\, s \in \mathcal{S}
```

**`StorageUnit_opens_late_only_where_it_opens`**

```math
\mathrm{on}^{h}_{t,s} \wedge \neg \mathrm{on}^{h}_{t - 1,s} \wedge \mathrm{pos}(t) > 0 \qquad \forall\, t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{open}_{t,s}
```

**`StorageUnit_opens_late_where_it_opens`**

```math
\mathrm{open}_{t,s} \qquad \forall\, t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{on}^{h}_{t,s} \wedge \neg \mathrm{on}^{h}_{t - 1,s} \wedge \mathrm{pos}(t) > 0
```

**`StorageUnit_primary_energy_per_period_closes_over_the_horizon`**

```math
\lvert \{ t \in \mathcal{T} \,:\, \neg \mathrm{in}_{\xi,g,t} \} \rvert = 0 \qquad \forall\, \xi \in \Xi,\ s \in \mathcal{S},\ g \in \mathcal{G} \,:\, \mathrm{a}^{h}_{\xi,g,s} \text{ is defined} \wedge \mathrm{reset}_{\xi,s}
```

**`StorageUnit_primary_energy_carried_over_has_unit_years`**

```math
\mathrm{w}^{\mathrm{yr}}_{y} = 1 \qquad \forall\, \xi \in \Xi,\ s \in \mathcal{S},\ g \in \mathcal{G},\ y \in \mathcal{Y} \,:\, \mathrm{a}^{h}_{\xi,g,s} \text{ is defined} \wedge \neg \mathrm{reset}_{\xi,s}
```

**`StorageUnit_operational_limit_carried_over_has_unit_years`**

```math
\mathrm{w}^{\mathrm{yr}}_{\mathrm{snapshot\_period}(t)} = 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S},\ g \in \mathcal{G} \,:\, \mathrm{b}^{h}_{\xi,g,s} \text{ is defined} \wedge \neg \mathrm{reset}_{\xi,s} \wedge \mathrm{in}_{\xi,g,t}
```

**`StorageUnit_marginal_cost_quadratic_without_risk_preference`**

```math
\mathrm{c}^{h,(2)}_{\xi,t,s} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \omega > 0
```
<!-- gallery:end -->
