<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Generators

One of the [24 fragments](index.md) of `examples/pypsa.yaml`: PyPSA's `Generator`. It adds a term to `primary_energy`, `operational_limit`, `tech_capacity_expansion`, `scenario_opex`, `Carrier_additions`, `Bus_injection`. It reads `CVaR_omega`, `Generator_committable`, `Generator_maintenance`, `Generator_maintenance_capacity`, `Generator_maintenance_pu`, `GlobalConstraint_energy_weight` and 4 more under [`given`](../../reference/language/declarations.md#given).

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
  generator:
    description: generating units, each on one bus
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
  Generator_carrier:
    description: the carrier a generator converts from
    key: generator
    values: carrier
  Generator_bus:
    description: the bus a generator sits on
    key: generator
    values: bus

parameters:
  Generator_p_nom:
    description: nominal power
    dims: [scenario, generator]
  Generator_p_nom_extendable:
    description: whether the nominal power is a decision
    dims: [generator]
    dtype: bool
  Generator_p_min_pu:
    description: least output, per unit of nominal power
    dims: [scenario, snapshot, generator]
  Generator_p_max_pu:
    description: most output, per unit of nominal power — an availability profile
    dims: [scenario, snapshot, generator]
  Generator_marginal_cost:
    description: cost of one unit of output
    dims: [scenario, snapshot, generator]
  Generator_marginal_cost_quadratic:
    description: cost of the square of one unit of output
    dims: [scenario, snapshot, generator]
  Generator_sign:
    description: >-
      the sign output enters its bus's balance with — PyPSA's `sign`, `1`
      unless given, `-1` for a unit that draws power. PyPSA refuses one that
      differs by scenario (`consistency.py:1187`)
    dims: [generator]
  Generator_p_nom_mod:
    description: the module size a build comes in whole numbers of; no value means the build is continuous
    dims: [generator]
  Generator_modules_installed:
    description: >-
      how many whole modules a committable build has in place: `Generator_p_nom
      / Generator_p_nom_mod` where a fixed build is modular, one where it is
      not, data prep. PyPSA refuses a fixed modular build whose nominal power
      is not a whole number of modules
    dims: [scenario, generator]
  Generator_p_min_pu_nonneg:
    description: >-
      true where none of the generator's own minimums-per-unit is negative —
      PyPSA's per-unit `(p_min_pu >= 0).all()` over every snapshot and scenario, data prep
    dims: [generator]
    dtype: bool
  Generator_active:
    description: whether a generator stands in a snapshot's period — PyPSA's `active`, from build year and lifetime, data prep
    dims: [snapshot, generator]
    dtype: bool
  Generator_capital_weight:
    description: the sum of period weights a generator stands in — PyPSA's `active * period_weighting`, summed, data prep
    dims: [generator]
  Generator_first_active:
    description: >-
      one in the first period a generator stands in, zero elsewhere, data prep.
      PyPSA `1.3.0` takes `active.cumsum() == 1`, which also counts a generator
      that has retired in every later period (`global_constraints.py:276`,
      PyPSA/PyPSA#1938)
    dims: [period, generator]
  Generator_p_set:
    description: a given output schedule; a generator without one has no row here
    dims: [scenario, snapshot, generator]
  Generator_p_nom_min:
    description: least nominal power an extendable generator may be built at
    dims: [scenario, generator]
  Generator_p_nom_max:
    description: most nominal power an extendable generator may be built at
    dims: [scenario, generator]
  Generator_capital_cost:
    description: cost of one unit of nominal power — PyPSA's `capital_cost`, periodized as an annuity in data prep
    dims: [scenario, generator]
  Generator_p_nom_set:
    description: a given nominal power for an extendable generator; one without a value has no row here
    dims: [scenario, generator]
  Generator_e_sum_min:
    description: least energy over the horizon; minus infinity where no floor is meant
    dims: [scenario, generator]
  Generator_e_sum_max:
    description: most energy over the horizon — a fuel or emission budget in energy terms; infinity where no cap is meant
    dims: [scenario, generator]
  Generator_primary_energy_weight:
    description: >-
      the constrained attribute per unit of energy at the bus — the carrier's
      `co2_emissions` over the generator's efficiency, data prep; a generator
      of an unweighted carrier has no row
    dims: [scenario, global_constraint, generator]
  Generator_operational_limit_weight:
    description: one where the generator is in the row's set — data prep; one outside it has no row
    dims: [scenario, global_constraint, generator]
  Generator_tech_capacity_weight:
    description: >-
      one where the generator is in the row's carrier-and-bus set — data
      prep; one outside it, or one that does not stand in the row's
      `investment_period`, has no row
    dims: [global_constraint, generator]

variables:
  Generator_p:
    description: "`Generator-p` — output of a generator in a snapshot"
    dims: [scenario, snapshot, generator]
    where: Generator_active
  Generator_n_mod:
    description: "`Generator-n_mod` — how many modules of an extendable modular build"
    dims: [generator]
    where: Generator_p_nom_extendable AND Generator_p_nom_mod > 0
    domain: integer
    bounds:
      lower: 0
  Generator_p_nom_ext:
    description: >-
      `Generator-p_nom` — nominal power where it is a decision; the parameter
      of the same PyPSA name carries the fixed regime
    dims: [generator]
    where: Generator_p_nom_extendable

given:
  parameters:
    snapshot_weightings_objective: { dims: [snapshot] }
    Generator_committable: { dims: [generator], dtype: bool }
    Generator_maintenance_pu: { dims: [scenario, generator] }
    scenario_weight: { dims: [scenario] }
    CVaR_omega: { dims: [] }
    period_weight_objective: { dims: [period] }
    snapshot_weightings_generators: { dims: [snapshot] }
  variables:
    Generator_maintenance: { dims: [scenario, snapshot, generator] }
    Generator_maintenance_capacity: { dims: [scenario, snapshot, generator] }
  expressions:
    GlobalConstraint_energy_weight: { dims: [scenario, global_constraint, snapshot] }
    primary_energy: { dims: [scenario, global_constraint], term: Generator_primary_energy }
    operational_limit: { dims: [scenario, global_constraint], term: Generator_operational_limit }
    tech_capacity_expansion: { dims: [global_constraint], term: Generator_tech_capacity_expansion }
    scenario_opex: { dims: [scenario], term: Generator_opex }
    Carrier_additions: { dims: [period, carrier], term: Generator_additions }
    Bus_injection: { dims: [scenario, snapshot, bus], term: Generator_injection }

expressions:
  Generator_p_nom_effective:
    description: the build a generator's limits are taken against — the chosen one where it is extendable, the given one otherwise
    dims: [scenario, generator]
    cases:
      extendable: { when: Generator_p_nom_extendable, expression: Generator_p_nom_ext }
    otherwise: Generator_p_nom
  Generator_p_nom_committed:
    description: >-
      the build a committed unit's ramp rows are taken against — one module
      where the build is extendable and modular, the given build otherwise
    dims: [scenario, generator]
    cases:
      modular_build: { when: Generator_p_nom_extendable AND Generator_p_nom_mod > 0, expression: Generator_p_nom_mod }
    otherwise: Generator_p_nom
  Generator_primary_energy:
    expression: >-
      sum(sum((Generator_p * GlobalConstraint_energy_weight) * Generator_primary_energy_weight, over=snapshot), over=generator)
  Generator_operational_limit:
    expression: >-
      sum(sum((Generator_p * GlobalConstraint_energy_weight) * Generator_operational_limit_weight, over=snapshot), over=generator)
  Generator_tech_capacity_expansion:
    expression: sum(Generator_p_nom_ext * Generator_tech_capacity_weight, over=generator)
  Generator_opex:
    expression: >-
      sum(sum(((Generator_p * Generator_marginal_cost) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=generator), over=snapshot)
      + sum(sum((((Generator_p * Generator_p) * Generator_marginal_cost_quadratic) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=generator), over=snapshot)
  Generator_additions:
    expression: >-
      sum(Generator_p_nom_ext * Generator_first_active, by=Generator_carrier, over=generator, into=carrier)
  Generator_injection:
    expression: sum(Generator_sign * Generator_p, by=Generator_bus, over=generator, into=bus)

constraints:
  Generator_fix_p_lower:
    description: "`Generator-fix-p-lower` — a fixed generator outputs at least its minimum"
    dims: [scenario, snapshot, generator]
    where: not Generator_p_nom_extendable AND not Generator_committable AND Generator_active
    expression: Generator_p >= Generator_p_min_pu * Generator_p_nom * (1 - Generator_maintenance_pu * Generator_maintenance)
  Generator_fix_p_upper:
    description: "`Generator-fix-p-upper` — a fixed generator outputs at most what is available"
    dims: [scenario, snapshot, generator]
    where: not Generator_p_nom_extendable AND not Generator_committable AND Generator_active
    expression: Generator_p <= Generator_p_max_pu * Generator_p_nom * (1 - Generator_maintenance_pu * Generator_maintenance)
  Generator_ext_p_lower:
    description: "`Generator-ext-p-lower` — an extendable generator outputs at least its minimum of the chosen build"
    dims: [scenario, snapshot, generator]
    where: Generator_p_nom_extendable AND not Generator_committable AND Generator_active
    expression: Generator_p >= Generator_p_min_pu * (Generator_p_nom_ext - Generator_maintenance_pu * Generator_maintenance_capacity)
  Generator_ext_p_upper:
    description: "`Generator-ext-p-upper` — an extendable generator outputs at most what is available of the chosen build"
    dims: [scenario, snapshot, generator]
    where: Generator_p_nom_extendable AND not Generator_committable AND Generator_active
    expression: Generator_p <= Generator_p_max_pu * (Generator_p_nom_ext - Generator_maintenance_pu * Generator_maintenance_capacity)
  Generator_ext_p_nom_lower:
    description: "`Generator-ext-p_nom-lower` — the chosen build is at least its floor in every scenario"
    dims: [scenario, generator]
    where: Generator_p_nom_extendable
    expression: Generator_p_nom_ext >= Generator_p_nom_min
  Generator_ext_p_nom_upper:
    description: "`Generator-ext-p_nom-upper` — the chosen build is at most its cap in every scenario; a cap of infinity is no row"
    dims: [scenario, generator]
    where: Generator_p_nom_extendable AND Generator_p_nom_max
    expression: Generator_p_nom_ext <= Generator_p_nom_max
  Generator_p_nom_set:
    description: "`Generator-p_nom_set` — the chosen build pinned, wherever a value is given"
    dims: [scenario, generator]
    where: Generator_p_nom_extendable AND Generator_p_nom_set
    expression: Generator_p_nom_ext == Generator_p_nom_set
  Generator_e_sum_min:
    description: "`Generator-e_sum_min` — energy over the horizon is at least its floor; a floor of minus infinity is no row"
    dims: [scenario, generator]
    where: Generator_e_sum_min
    expression: sum(Generator_p * snapshot_weightings_generators, over=snapshot) >= Generator_e_sum_min
  Generator_e_sum_max:
    description: "`Generator-e_sum_max` — energy over the horizon is at most its budget; a budget of infinity is no row"
    dims: [scenario, generator]
    where: Generator_e_sum_max
    expression: sum(Generator_p * snapshot_weightings_generators, over=snapshot) <= Generator_e_sum_max
  Generator_p_nom_modularity:
    description: "`Generator-p_nom_modularity` — the chosen build is a whole number of modules"
    dims: [generator]
    where: Generator_p_nom_extendable AND Generator_p_nom_mod > 0
    expression: Generator_p_nom_ext == Generator_p_nom_mod * Generator_n_mod
  Generator_p_set:
    description: "`Generator-p_set` — output pinned to the given schedule, wherever one is given"
    dims: [scenario, snapshot, generator]
    where: Generator_p_set AND Generator_active
    expression: Generator_p == Generator_p_set

assumptions:
  Generator_marginal_cost_quadratic_without_risk_preference:
    holds: "Generator_marginal_cost_quadratic == 0"
    where: "CVaR_omega > 0"
    description: >-
      a quadratic cost puts a square into every `CVaR-excess` row, and PyPSA
      refuses quadratic costs under any risk preference
      (`optimize.py:467-474`). The spec cannot tell no risk preference from
      one with `omega = 0`, so it refuses only where `omega` is positive

objective:
  sense: minimize
  expression: >-
    sum(((scenario_weight * Generator_p_nom_ext) * Generator_capital_cost) * Generator_capital_weight)
```

#### Sets

| Symbol | Meaning |
|---|---|
| $`\Xi`$ | index $`\xi`$ — `scenario` — the futures dispatch is chosen in, each with a weight |
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` with $`\mathrm{snapshot\_period}: \mathcal{T} \to \mathcal{Y}`$ — dispatch periods |
| $`\mathcal{N}`$ | index $`n`$ — `bus` with $`\mathrm{Generator\_bus}: \mathcal{G} \to \mathcal{N}`$ — network nodes |
| $`\mathcal{G}`$ | index $`g`$ — `generator` with $`\mathrm{Generator\_carrier}: \mathcal{G} \to \mathcal{I},\ \mathrm{Generator\_bus}: \mathcal{G} \to \mathcal{N}`$ — generating units, each on one bus |
| $`\mathcal{L}`$ | index $`l`$ — `global_constraint` — PyPSA's `GlobalConstraint` rows, one label per declared limit |
| $`\mathcal{Y}`$ | index $`y`$ — `period` with $`\mathrm{snapshot\_period}: \mathcal{T} \to \mathcal{Y}`$ — investment periods — PyPSA's `investment_periods` |
| $`\mathcal{I}`$ | index $`i`$ — `carrier` with $`\mathrm{Generator\_carrier}: \mathcal{G} \to \mathcal{I}`$ — energy carriers, what a growth limit is set per |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{p}^{\mathrm{nom}}`$ | `Generator_p_nom` over $`\Xi \times \mathcal{G}`$ — nominal power |
| $`\mathrm{ext}`$ | `Generator_p_nom_extendable` over $`\mathcal{G}`$ — whether the nominal power is a decision |
| $`\underline{\mathrm{p}}`$ | `Generator_p_min_pu` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — least output, per unit of nominal power |
| $`\overline{\mathrm{p}}`$ | `Generator_p_max_pu` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — most output, per unit of nominal power — an availability profile |
| $`\mathrm{c}`$ | `Generator_marginal_cost` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — cost of one unit of output |
| $`\mathrm{c}^{(2)}`$ | `Generator_marginal_cost_quadratic` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — cost of the square of one unit of output |
| $`\mathrm{sgn}`$ | `Generator_sign` over $`\mathcal{G}`$ — the sign output enters its bus's balance with — PyPSA's `sign`, `1` unless given, `-1` for a unit that draws power. PyPSA refuses one that differs by scenario (`consistency.py:1187`) |
| $`\mathrm{p}^{\mathrm{mod}}`$ | `Generator_p_nom_mod` over $`\mathcal{G}`$ — the module size a build comes in whole numbers of; no value means the build is continuous |
| $`\mathrm{N}^{\mathrm{fix}}`$ | `Generator_modules_installed` over $`\Xi \times \mathcal{G}`$ — how many whole modules a committable build has in place: `Generator_p_nom / Generator_p_nom_mod` where a fixed build is modular, one where it is not, data prep. PyPSA refuses a fixed modular build whose nominal power is not a whole number of modules |
| $`\mathrm{nonneg}`$ | `Generator_p_min_pu_nonneg` over $`\mathcal{G}`$ — true where none of the generator's own minimums-per-unit is negative — PyPSA's per-unit `(p_min_pu >= 0).all()` over every snapshot and scenario, data prep |
| $`\mathrm{on}`$ | `Generator_active` over $`\mathcal{T} \times \mathcal{G}`$ — whether a generator stands in a snapshot's period — PyPSA's `active`, from build year and lifetime, data prep |
| $`\mathrm{W}`$ | `Generator_capital_weight` over $`\mathcal{G}`$ — the sum of period weights a generator stands in — PyPSA's `active * period_weighting`, summed, data prep |
| $`\mathrm{new}`$ | `Generator_first_active` over $`\mathcal{Y} \times \mathcal{G}`$ — one in the first period a generator stands in, zero elsewhere, data prep. PyPSA `1.3.0` takes `active.cumsum() == 1`, which also counts a generator that has retired in every later period (`global_constraints.py:276`, PyPSA/PyPSA\#1938) |
| $`\mathrm{p}^{\mathrm{set}}`$ | `Generator_p_set` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — a given output schedule; a generator without one has no row here |
| $`\underline{\mathrm{p}}^{\mathrm{nom}}`$ | `Generator_p_nom_min` over $`\Xi \times \mathcal{G}`$ — least nominal power an extendable generator may be built at |
| $`\overline{\mathrm{p}}^{\mathrm{nom}}`$ | `Generator_p_nom_max` over $`\Xi \times \mathcal{G}`$ — most nominal power an extendable generator may be built at |
| $`\mathrm{c}^{\mathrm{cap}}`$ | `Generator_capital_cost` over $`\Xi \times \mathcal{G}`$ — cost of one unit of nominal power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $`\mathrm{p}^{\mathrm{nom,set}}`$ | `Generator_p_nom_set` over $`\Xi \times \mathcal{G}`$ — a given nominal power for an extendable generator; one without a value has no row here |
| $`\underline{\mathrm{E}}`$ | `Generator_e_sum_min` over $`\Xi \times \mathcal{G}`$ — least energy over the horizon; minus infinity where no floor is meant |
| $`\overline{\mathrm{E}}`$ | `Generator_e_sum_max` over $`\Xi \times \mathcal{G}`$ — most energy over the horizon — a fuel or emission budget in energy terms; infinity where no cap is meant |
| $`\mathrm{a}`$ | `Generator_primary_energy_weight` over $`\Xi \times \mathcal{L} \times \mathcal{G}`$ — the constrained attribute per unit of energy at the bus — the carrier's `co2_emissions` over the generator's efficiency, data prep; a generator of an unweighted carrier has no row |
| $`\mathrm{b}`$ | `Generator_operational_limit_weight` over $`\Xi \times \mathcal{L} \times \mathcal{G}`$ — one where the generator is in the row's set — data prep; one outside it has no row |
| $`\mathrm{m}`$ | `Generator_tech_capacity_weight` over $`\mathcal{L} \times \mathcal{G}`$ — one where the generator is in the row's carrier-and-bus set — data prep; one outside it, or one that does not stand in the row's `investment_period`, has no row |

#### Variables

| Symbol | Meaning |
|---|---|
| $`p`$ | `Generator_p` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — `Generator-p` — output of a generator in a snapshot |
| $`N`$ | `Generator_n_mod` over $`\mathcal{G}`$ — `Generator-n_mod` — how many modules of an extendable modular build |
| $`P`$ | `Generator_p_nom_ext` over $`\mathcal{G}`$ — `Generator-p_nom` — nominal power where it is a decision; the parameter of the same PyPSA name carries the fixed regime |

#### Given

| Symbol | Meaning |
|---|---|
| $`\mathrm{w}`$ | `snapshot_weightings_objective` over $`\mathcal{T}`$, data another file declares |
| $`\mathrm{com}`$ | `Generator_committable` over $`\mathcal{G}`$, data another file declares |
| $`\gamma`$ | `Generator_maintenance_pu` over $`\Xi \times \mathcal{G}`$, data another file declares |
| $`\pi`$ | `scenario_weight` over $`\Xi`$, data another file declares |
| $`\omega`$ | `CVaR_omega` (scalar), data another file declares |
| $`\mathrm{w}^{y}`$ | `period_weight_objective` over $`\mathcal{Y}`$, data another file declares |
| $`\mathrm{w}^{\mathrm{gen}}`$ | `snapshot_weightings_generators` over $`\mathcal{T}`$, data another file declares |
| $`\mu`$ | `Generator_maintenance` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ |
| $`\mu^{\mathrm{nom}}`$ | `Generator_maintenance_capacity` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ |
| $`\mathit{w}^{\mathrm{gc}}`$ | `GlobalConstraint_energy_weight` over $`\Xi \times \mathcal{L} \times \mathcal{T}`$, an expression another file defines |
| $`\mathit{primary\_energy}`$ | `primary_energy` over $`\Xi \times \mathcal{L}`$, an expression this file adds `Generator_primary_energy` to |
| $`\mathit{operational\_limit}`$ | `operational_limit` over $`\Xi \times \mathcal{L}`$, an expression this file adds `Generator_operational_limit` to |
| $`\mathit{tech\_capacity\_expansion}`$ | `tech_capacity_expansion` over $`\mathcal{L}`$, an expression this file adds `Generator_tech_capacity_expansion` to |
| $`\mathit{scenario\_opex}`$ | `scenario_opex` over $`\Xi`$, an expression this file adds `Generator_opex` to |
| $`\mathit{Carrier\_additions}`$ | `Carrier_additions` over $`\mathcal{Y} \times \mathcal{I}`$, an expression this file adds `Generator_additions` to |
| $`\mathit{Bus\_injection}`$ | `Bus_injection` over $`\Xi \times \mathcal{T} \times \mathcal{N}`$, an expression this file adds `Generator_injection` to |

#### Definitions

| Symbol | Meaning |
|---|---|
| $`\widetilde{\mathrm{p}}^{\mathrm{nom}}`$ | `Generator_p_nom_effective` over $`\Xi \times \mathcal{G}`$ — the build a generator's limits are taken against — the chosen one where it is extendable, the given one otherwise |
| $`\widehat{\mathrm{p}}^{\mathrm{nom}}`$ | `Generator_p_nom_committed` over $`\Xi \times \mathcal{G}`$ — the build a committed unit's ramp rows are taken against — one module where the build is extendable and modular, the given build otherwise |
| $`\mathit{Generator\_primary\_energy}`$ | `Generator_primary_energy` over $`\Xi \times \mathcal{L}`$ |
| $`\mathit{Generator\_operational\_limit}`$ | `Generator_operational_limit` over $`\Xi \times \mathcal{L}`$ |
| $`\mathit{Generator\_tech\_capacity\_expansion}`$ | `Generator_tech_capacity_expansion` over $`\mathcal{L}`$ |
| $`\mathit{Generator\_opex}`$ | `Generator_opex` over $`\Xi`$ |
| $`\mathit{Generator\_additions}`$ | `Generator_additions` over $`\mathcal{Y} \times \mathcal{I}`$ |
| $`\mathit{Generator\_injection}`$ | `Generator_injection` over $`\Xi \times \mathcal{T} \times \mathcal{N}`$ |

#### Objective

```math
\min \sum_{\xi \in \Xi,\ g \in \mathcal{G}} \pi_{\xi} \cdot P_{g} \cdot \mathrm{c}^{\mathrm{cap}}_{\xi,g} \cdot \mathrm{W}_{g}
```

#### Subject to

**`Generator_fix_p_lower`**

```math
p_{\xi,t,g} \ge \underline{\mathrm{p}}_{\xi,t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{\xi,g} \cdot \left( 1 - \gamma_{\xi,g} \cdot \mu_{\xi,t,g} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \neg \mathrm{ext}_{g} \wedge \neg \mathrm{com}_{g} \wedge \mathrm{on}_{t,g}
```

**`Generator_fix_p_upper`**

```math
p_{\xi,t,g} \le \overline{\mathrm{p}}_{\xi,t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{\xi,g} \cdot \left( 1 - \gamma_{\xi,g} \cdot \mu_{\xi,t,g} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \neg \mathrm{ext}_{g} \wedge \neg \mathrm{com}_{g} \wedge \mathrm{on}_{t,g}
```

**`Generator_ext_p_lower`**

```math
p_{\xi,t,g} \ge \underline{\mathrm{p}}_{\xi,t,g} \cdot \left( P_{g} - \gamma_{\xi,g} \cdot \mu^{\mathrm{nom}}_{\xi,t,g} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{ext}_{g} \wedge \neg \mathrm{com}_{g} \wedge \mathrm{on}_{t,g}
```

**`Generator_ext_p_upper`**

```math
p_{\xi,t,g} \le \overline{\mathrm{p}}_{\xi,t,g} \cdot \left( P_{g} - \gamma_{\xi,g} \cdot \mu^{\mathrm{nom}}_{\xi,t,g} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{ext}_{g} \wedge \neg \mathrm{com}_{g} \wedge \mathrm{on}_{t,g}
```

**`Generator_ext_p_nom_lower`**

```math
P_{g} \ge \underline{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{ext}_{g}
```

**`Generator_ext_p_nom_upper`**

```math
P_{g} \le \overline{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{ext}_{g} \wedge \overline{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} \text{ is defined}
```

**`Generator_p_nom_set`**

```math
P_{g} = \mathrm{p}^{\mathrm{nom,set}}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{nom,set}}_{\xi,g} \text{ is defined}
```

**`Generator_e_sum_min`**

```math
\sum_{t \in \mathcal{T}} p_{\xi,t,g} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \ge \underline{\mathrm{E}}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \underline{\mathrm{E}}_{\xi,g} \text{ is defined}
```

**`Generator_e_sum_max`**

```math
\sum_{t \in \mathcal{T}} p_{\xi,t,g} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \le \overline{\mathrm{E}}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \overline{\mathrm{E}}_{\xi,g} \text{ is defined}
```

**`Generator_p_nom_modularity`**

```math
P_{g} = \mathrm{p}^{\mathrm{mod}}_{g} \cdot N_{g} \qquad \forall\, g \in \mathcal{G} \,:\, \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0
```

**`Generator_p_set`**

```math
p_{\xi,t,g} = \mathrm{p}^{\mathrm{set}}_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{p}^{\mathrm{set}}_{\xi,t,g} \text{ is defined} \wedge \mathrm{on}_{t,g}
```

#### Definitions

**`Generator_p_nom_effective`**

```math
\widetilde{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} = \begin{cases} P_{g} & \text{if } \mathrm{ext}_{g} \\ \mathrm{p}^{\mathrm{nom}}_{\xi,g} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G}
```

**`Generator_p_nom_committed`**

```math
\widehat{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} = \begin{cases} \mathrm{p}^{\mathrm{mod}}_{g} & \text{if } \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \\ \mathrm{p}^{\mathrm{nom}}_{\xi,g} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G}
```

**`Generator_primary_energy`**

```math
\mathit{Generator\_primary\_energy}_{\xi,l} = \sum_{g \in \mathcal{G}} \sum_{t \in \mathcal{T}} p_{\xi,t,g} \cdot \mathit{w}^{\mathrm{gc}}_{\xi,l,t} \cdot \mathrm{a}_{\xi,l,g} \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L}
```

**`Generator_operational_limit`**

```math
\mathit{Generator\_operational\_limit}_{\xi,l} = \sum_{g \in \mathcal{G}} \sum_{t \in \mathcal{T}} p_{\xi,t,g} \cdot \mathit{w}^{\mathrm{gc}}_{\xi,l,t} \cdot \mathrm{b}_{\xi,l,g} \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L}
```

**`Generator_tech_capacity_expansion`**

```math
\mathit{Generator\_tech\_capacity\_expansion}_{l} = \sum_{g \in \mathcal{G}} P_{g} \cdot \mathrm{m}_{l,g} \qquad \forall\, l \in \mathcal{L}
```

**`Generator_opex`**

```math
\mathit{Generator\_opex}_{\xi} = \sum_{t \in \mathcal{T}} \sum_{g \in \mathcal{G}} p_{\xi,t,g} \cdot \mathrm{c}_{\xi,t,g} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{g \in \mathcal{G}} p_{\xi,t,g} \cdot p_{\xi,t,g} \cdot \mathrm{c}^{(2)}_{\xi,t,g} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} \qquad \forall\, \xi \in \Xi
```

**`Generator_additions`**

```math
\mathit{Generator\_additions}_{y,i} = \sum_{g \in \mathcal{G} \,:\, \mathrm{Generator\_carrier}(g) = i} P_{g} \cdot \mathrm{new}_{y,g} \qquad \forall\, y \in \mathcal{Y},\ i \in \mathcal{I}
```

**`Generator_injection`**

```math
\mathit{Generator\_injection}_{\xi,t,n} = \sum_{g \in \mathcal{G} \,:\, \mathrm{Generator\_bus}(g) = n} \mathrm{sgn}_{g} \cdot p_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ n \in \mathcal{N}
```

#### Variable domains

**`Generator_p`**

```math
p_{\xi,t,g} \in \mathbb{R} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{on}_{t,g}
```

**`Generator_n_mod`**

```math
N_{g} \ge 0, N_{g} \in \mathbb{Z} \qquad \forall\, g \in \mathcal{G} \,:\, \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0
```

**`Generator_p_nom_ext`**

```math
P_{g} \in \mathbb{R} \qquad \forall\, g \in \mathcal{G} \,:\, \mathrm{ext}_{g}
```

#### Assumptions

**`Generator_marginal_cost_quadratic_without_risk_preference`**

```math
\mathrm{c}^{(2)}_{\xi,t,g} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \omega > 0
```
<!-- gallery:end -->
