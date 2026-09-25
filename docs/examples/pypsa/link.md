<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Links

One of the [24 fragments](index.md) of `examples/pypsa.yaml`: PyPSA's `Link`. It adds a term to `transmission_volume_expansion`, `transmission_expansion_cost`, `tech_capacity_expansion`, `scenario_opex`, `Carrier_additions`, `Bus_injection`. It reads `CVaR_omega`, `Link_committable`, `Link_maintenance`, `Link_maintenance_capacity`, `Link_maintenance_pu`, `period_weight_objective` and 2 more under [`given`](../../reference/language/declarations.md#given).

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
  link:
    description: controllable connections, each from one bus to the buses it delivers to
  link_output:
    description: >-
      a link's output ports, one label per port a link declares — PyPSA's
      `bus1`, `bus2`, … columns read long, so a link of any number of output
      ports is one term in the balance, data prep
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
  Link_carrier:
    description: the carrier a link converts from
    key: link
    values: carrier
  Link_bus0:
    description: the bus a link leaves
    key: link
    values: bus
  Link_output_link:
    description: the link an output port belongs to
    key: link_output
    values: link
  Link_output_bus:
    description: >-
      the bus an output port delivers to — PyPSA's `bus1`, `bus2`, … columns.
      A link of three output ports is three labels here rather than a third
      relation, so the file states any number of them
    key: link_output
    values: bus

parameters:
  Link_p_nom:
    description: nominal power
    dims: [scenario, link]
  Link_p_nom_extendable:
    description: whether the nominal power is a decision
    dims: [link]
    dtype: bool
  Link_p_min_pu:
    description: least flow, per unit of nominal power — negative for a link that carries both ways
    dims: [scenario, snapshot, link]
  Link_p_max_pu:
    description: most flow, per unit of nominal power
    dims: [scenario, snapshot, link]
  Link_efficiency:
    description: >-
      share of the flow that arrives at an output port, PyPSA's `efficiency`,
      `efficiency2`, … read long — negative where that port consumes rather
      than delivers
    dims: [scenario, link_output]
  Link_output_delay:
    description: >-
      snapshots a port's delivery lags its link's flow — PyPSA's `delay`,
      `delay2`, … read long, in `snapshot_weightings.generators` units, which
      the file states as whole snapshots; zero for a port that delivers at once.
      Each scenario takes its own. PyPSA `1.3.0` groups the ports by delay over
      all scenarios and shifts each group in every one, so a delay that differs
      by scenario delivers the flow twice (`constraints.py:1269-1276`,
      PyPSA/PyPSA#1941)
    dims: [scenario, link_output]
    dtype: int
  Link_output_cyclic_delay:
    description: >-
      whether a delayed port's flow wraps from the end of its investment
      period — PyPSA's `cyclic_delay`, `cyclic_delay2`, …; where it does not,
      the flow still in transit at each period's first snapshots is lost. Each
      scenario takes its own, as the delay
    dims: [scenario, link_output]
    dtype: bool
  Link_marginal_cost:
    description: cost of one unit of flow
    dims: [scenario, snapshot, link]
  Link_marginal_cost_quadratic:
    description: cost of the square of one unit of flow
    dims: [scenario, snapshot, link]
  Link_p_nom_mod:
    description: the module size a build comes in whole numbers of; no value means the build is continuous
    dims: [link]
  Link_modules_installed:
    description: >-
      how many whole modules a committable build has in place: `Link_p_nom
      / Link_p_nom_mod` where a fixed build is modular, one where it is
      not, data prep. PyPSA refuses a fixed modular build whose nominal power
      is not a whole number of modules
    dims: [scenario, link]
  Link_p_min_pu_nonneg:
    description: >-
      true where none of the link's own minimums-per-unit is negative —
      PyPSA's per-unit `(p_min_pu >= 0).all()` over every snapshot and scenario, data prep
    dims: [link]
    dtype: bool
  Link_active:
    description: whether a link stands in a snapshot's period — PyPSA's `active`, data prep
    dims: [snapshot, link]
    dtype: bool
  Link_capital_weight:
    description: the sum of period weights a link stands in — PyPSA's `active * period_weighting`, summed, data prep
    dims: [link]
  Link_first_active:
    description: >-
      one in the first period a link stands in, zero elsewhere, data prep.
      PyPSA `1.3.0` takes `active.cumsum() == 1`, which also counts a link
      that has retired in every later period (`global_constraints.py:276`,
      PyPSA/PyPSA#1938)
    dims: [period, link]
  Link_p_set:
    description: a given flow schedule; a link without one has no row here
    dims: [scenario, snapshot, link]
  Link_p_nom_min:
    description: least nominal power an extendable link may be built at
    dims: [scenario, link]
  Link_p_nom_max:
    description: most nominal power an extendable link may be built at
    dims: [scenario, link]
  Link_capital_cost:
    description: cost of one unit of nominal power — PyPSA's `capital_cost`, periodized as an annuity in data prep
    dims: [scenario, link]
  Link_p_nom_set:
    description: a given nominal power for an extendable link; one without a value has no row here
    dims: [scenario, link]
  Link_volume_weight:
    description: >-
      the link's length where its carrier is in the row's set, the first
      scenario's length as PyPSA reads it (`global_constraints.py:835-836`) —
      data prep; a
      link outside it, or one that does not stand in the row's
      `investment_period`, has no row
    dims: [scenario, global_constraint, link]
  Link_expansion_cost_weight:
    description: >-
      the link's capital cost where its carrier is in the row's set, times
      the objective weights of the periods it stands in where the row names
      no `investment_period` under `multi_investment_periods` — data prep; a
      link outside the set, or one that does not stand in the row's period,
      has no row
    dims: [scenario, global_constraint, link]
  Link_tech_capacity_weight:
    description: >-
      one where the link is in the row's carrier-and-bus set — data prep; one
      outside it, or one that does not stand in the row's `investment_period`,
      has no row
    dims: [global_constraint, link]

variables:
  Link_p:
    description: >-
      `Link-p` — PyPSA's `p0`, the flow measured at the `Link_bus0` end: a
      positive value withdraws there and injects at every bus the link's
      output ports deliver to
    dims: [scenario, snapshot, link]
    where: Link_active
  Link_n_mod:
    description: "`Link-n_mod` — how many modules of an extendable modular build"
    dims: [link]
    where: Link_p_nom_extendable AND Link_p_nom_mod > 0
    domain: integer
    bounds:
      lower: 0
  Link_p_nom_ext:
    description: >-
      `Link-p_nom` — nominal power where it is a decision; the parameter of
      the same PyPSA name carries the fixed regime
    dims: [link]
    where: Link_p_nom_extendable

given:
  parameters:
    snapshot_weightings_objective: { dims: [snapshot] }
    Link_committable: { dims: [link], dtype: bool }
    Link_maintenance_pu: { dims: [scenario, link] }
    scenario_weight: { dims: [scenario] }
    CVaR_omega: { dims: [] }
    period_weight_objective: { dims: [period] }
  variables:
    Link_maintenance: { dims: [scenario, snapshot, link] }
    Link_maintenance_capacity: { dims: [scenario, snapshot, link] }
  expressions:
    transmission_volume_expansion: { dims: [scenario, global_constraint], term: Link_transmission_volume_expansion }
    transmission_expansion_cost: { dims: [scenario, global_constraint], term: Link_transmission_expansion_cost }
    tech_capacity_expansion: { dims: [global_constraint], term: Link_tech_capacity_expansion }
    scenario_opex: { dims: [scenario], term: Link_opex }
    Carrier_additions: { dims: [period, carrier], term: Link_additions }
    Bus_injection: { dims: [scenario, snapshot, bus], term: Link_injection }

expressions:
  Link_p_nom_effective:
    description: the build a link's limits are taken against — the chosen one where it is extendable, the given one otherwise
    dims: [scenario, link]
    cases:
      extendable: { when: Link_p_nom_extendable, expression: Link_p_nom_ext }
    otherwise: Link_p_nom
  Link_p_nom_committed:
    description: >-
      the build a committed link's ramp rows are taken against — one module
      where the build is extendable and modular, the given build otherwise
    dims: [scenario, link]
    cases:
      modular_build: { when: Link_p_nom_extendable AND Link_p_nom_mod > 0, expression: Link_p_nom_mod }
    otherwise: Link_p_nom
  Link_output_arrival:
    description: >-
      what a link delivers to an output port at a snapshot — its flow after the
      port's efficiency, delayed by the port's `delay` within its investment
      period; where the port is `cyclic_delay` the delayed flow wraps from the
      period's end, and where it is not the flow still in transit at the
      period's first snapshots is lost. A port that does not delay (`delay`
      zero) delivers its flow unshifted, cyclic or not
    dims: [scenario, snapshot, link_output]
    cases:
      wrapping:
        when: Link_output_cyclic_delay
        expression: shift(at(Link_p, by=Link_output_link, over=link, into=link_output) * Link_efficiency, along=snapshot, offset=Link_output_delay, edge='wrap', by=snapshot_period, within=period)
    otherwise: shift(at(Link_p, by=Link_output_link, over=link, into=link_output) * Link_efficiency, along=snapshot, offset=Link_output_delay, edge=0, by=snapshot_period, within=period)
  Link_transmission_volume_expansion:
    expression: sum(Link_p_nom_ext * Link_volume_weight, over=link)
  Link_transmission_expansion_cost:
    expression: sum(Link_p_nom_ext * Link_expansion_cost_weight, over=link)
  Link_tech_capacity_expansion:
    expression: sum(Link_p_nom_ext * Link_tech_capacity_weight, over=link)
  Link_opex:
    expression: >-
      sum(sum(((Link_p * Link_marginal_cost) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=link), over=snapshot)
      + sum(sum((((Link_p * Link_p) * Link_marginal_cost_quadratic) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=link), over=snapshot)
  Link_additions:
    expression: >-
      sum(Link_p_nom_ext * Link_first_active, by=Link_carrier, over=link, into=carrier)
  Link_injection:
    expression: >-
      -sum(Link_p, by=Link_bus0, over=link, into=bus)
      + sum(Link_output_arrival, by=Link_output_bus, over=link_output, into=bus)

constraints:
  Link_fix_p_lower:
    description: "`Link-fix-p-lower` — a fixed link carries at least its minimum, negative for the other way"
    dims: [scenario, snapshot, link]
    where: not Link_p_nom_extendable AND not Link_committable AND Link_active
    expression: Link_p >= Link_p_min_pu * Link_p_nom * (1 - Link_maintenance_pu * Link_maintenance)
  Link_fix_p_upper:
    description: "`Link-fix-p-upper` — a fixed link carries at most its nominal power"
    dims: [scenario, snapshot, link]
    where: not Link_p_nom_extendable AND not Link_committable AND Link_active
    expression: Link_p <= Link_p_max_pu * Link_p_nom * (1 - Link_maintenance_pu * Link_maintenance)
  Link_ext_p_lower:
    description: "`Link-ext-p-lower` — an extendable link carries at least its minimum of the chosen build, negative for the other way"
    dims: [scenario, snapshot, link]
    where: Link_p_nom_extendable AND not Link_committable AND Link_active
    expression: Link_p >= Link_p_min_pu * (Link_p_nom_ext - Link_maintenance_pu * Link_maintenance_capacity)
  Link_ext_p_upper:
    description: "`Link-ext-p-upper` — an extendable link carries at most the chosen build"
    dims: [scenario, snapshot, link]
    where: Link_p_nom_extendable AND not Link_committable AND Link_active
    expression: Link_p <= Link_p_max_pu * (Link_p_nom_ext - Link_maintenance_pu * Link_maintenance_capacity)
  Link_ext_p_nom_lower:
    description: "`Link-ext-p_nom-lower` — the chosen build is at least its floor in every scenario"
    dims: [scenario, link]
    where: Link_p_nom_extendable
    expression: Link_p_nom_ext >= Link_p_nom_min
  Link_ext_p_nom_upper:
    description: "`Link-ext-p_nom-upper` — the chosen build is at most its cap in every scenario; a cap of infinity is no row"
    dims: [scenario, link]
    where: Link_p_nom_extendable AND Link_p_nom_max
    expression: Link_p_nom_ext <= Link_p_nom_max
  Link_p_nom_set:
    description: "`Link-p_nom_set` — the chosen build pinned, wherever a value is given"
    dims: [scenario, link]
    where: Link_p_nom_extendable AND Link_p_nom_set
    expression: Link_p_nom_ext == Link_p_nom_set
  Link_p_nom_modularity:
    description: "`Link-p_nom_modularity` — the chosen build is a whole number of modules"
    dims: [link]
    where: Link_p_nom_extendable AND Link_p_nom_mod > 0
    expression: Link_p_nom_ext == Link_p_nom_mod * Link_n_mod
  Link_p_set:
    description: "`Link-p_set` — flow pinned to the given schedule, wherever one is given"
    dims: [scenario, snapshot, link]
    where: Link_p_set AND Link_active
    expression: Link_p == Link_p_set

assumptions:
  Link_marginal_cost_quadratic_without_risk_preference:
    holds: "Link_marginal_cost_quadratic == 0"
    where: "CVaR_omega > 0"
    description: >-
      a quadratic cost puts a square into every `CVaR-excess` row, and PyPSA
      refuses quadratic costs under any risk preference
      (`optimize.py:467-474`). The spec cannot tell no risk preference from
      one with `omega = 0`, so it refuses only where `omega` is positive

objective:
  sense: minimize
  expression: >-
    sum(((scenario_weight * Link_p_nom_ext) * Link_capital_cost) * Link_capital_weight)
```

#### Sets

| Symbol | Meaning |
|---|---|
| $`\Xi`$ | index $`\xi`$ — `scenario` — the futures dispatch is chosen in, each with a weight |
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` with $`\mathrm{snapshot\_period}: \mathcal{T} \to \mathcal{Y}`$ — dispatch periods |
| $`\mathcal{N}`$ | index $`n`$ — `bus` with $`\mathrm{Link\_bus0}: \mathcal{L} \to \mathcal{N},\ \mathrm{Link\_output\_bus}: \mathcal{O} \to \mathcal{N}`$ — network nodes |
| $`\mathcal{L}`$ | index $`l`$ — `link` with $`\mathrm{Link\_carrier}: \mathcal{L} \to \mathcal{I},\ \mathrm{Link\_bus0}: \mathcal{L} \to \mathcal{N},\ \mathrm{Link\_output\_link}: \mathcal{O} \to \mathcal{L}`$ — controllable connections, each from one bus to the buses it delivers to |
| $`\mathcal{O}`$ | index $`o`$ — `link_output` with $`\mathrm{Link\_output\_link}: \mathcal{O} \to \mathcal{L},\ \mathrm{Link\_output\_bus}: \mathcal{O} \to \mathcal{N}`$ — a link's output ports, one label per port a link declares — PyPSA's `bus1`, `bus2`, … columns read long, so a link of any number of output ports is one term in the balance, data prep |
| $`\mathcal{G}`$ | index $`g`$ — `global_constraint` — PyPSA's `GlobalConstraint` rows, one label per declared limit |
| $`\mathcal{Y}`$ | index $`y`$ — `period` with $`\mathrm{snapshot\_period}: \mathcal{T} \to \mathcal{Y}`$ — investment periods — PyPSA's `investment_periods` |
| $`\mathcal{I}`$ | index $`i`$ — `carrier` with $`\mathrm{Link\_carrier}: \mathcal{L} \to \mathcal{I}`$ — energy carriers, what a growth limit is set per |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{f}^{\mathrm{nom}}`$ | `Link_p_nom` over $`\Xi \times \mathcal{L}`$ — nominal power |
| $`\mathrm{ext}^{f}`$ | `Link_p_nom_extendable` over $`\mathcal{L}`$ — whether the nominal power is a decision |
| $`\underline{\mathrm{f}}`$ | `Link_p_min_pu` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — least flow, per unit of nominal power — negative for a link that carries both ways |
| $`\overline{\mathrm{f}}`$ | `Link_p_max_pu` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — most flow, per unit of nominal power |
| $`\eta`$ | `Link_efficiency` over $`\Xi \times \mathcal{O}`$ — share of the flow that arrives at an output port, PyPSA's `efficiency`, `efficiency2`, … read long — negative where that port consumes rather than delivers |
| $`\mathrm{d}^{f}`$ | `Link_output_delay` over $`\Xi \times \mathcal{O}`$ — snapshots a port's delivery lags its link's flow — PyPSA's `delay`, `delay2`, … read long, in `snapshot_weightings.generators` units, which the file states as whole snapshots; zero for a port that delivers at once. Each scenario takes its own. PyPSA `1.3.0` groups the ports by delay over all scenarios and shifts each group in every one, so a delay that differs by scenario delivers the flow twice (`constraints.py:1269-1276`, PyPSA/PyPSA\#1941) |
| $`\mathrm{cyc}^{f}`$ | `Link_output_cyclic_delay` over $`\Xi \times \mathcal{O}`$ — whether a delayed port's flow wraps from the end of its investment period — PyPSA's `cyclic_delay`, `cyclic_delay2`, …; where it does not, the flow still in transit at each period's first snapshots is lost. Each scenario takes its own, as the delay |
| $`\mathrm{c}^{f}`$ | `Link_marginal_cost` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — cost of one unit of flow |
| $`\mathrm{c}^{f,(2)}`$ | `Link_marginal_cost_quadratic` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — cost of the square of one unit of flow |
| $`\mathrm{f}^{\mathrm{mod}}`$ | `Link_p_nom_mod` over $`\mathcal{L}`$ — the module size a build comes in whole numbers of; no value means the build is continuous |
| $`\mathrm{N}^{f,\mathrm{fix}}`$ | `Link_modules_installed` over $`\Xi \times \mathcal{L}`$ — how many whole modules a committable build has in place: `Link_p_nom / Link_p_nom_mod` where a fixed build is modular, one where it is not, data prep. PyPSA refuses a fixed modular build whose nominal power is not a whole number of modules |
| $`\mathrm{nonneg}^{f}`$ | `Link_p_min_pu_nonneg` over $`\mathcal{L}`$ — true where none of the link's own minimums-per-unit is negative — PyPSA's per-unit `(p_min_pu >= 0).all()` over every snapshot and scenario, data prep |
| $`\mathrm{on}^{f}`$ | `Link_active` over $`\mathcal{T} \times \mathcal{L}`$ — whether a link stands in a snapshot's period — PyPSA's `active`, data prep |
| $`\mathrm{W}^{f}`$ | `Link_capital_weight` over $`\mathcal{L}`$ — the sum of period weights a link stands in — PyPSA's `active * period_weighting`, summed, data prep |
| $`\mathrm{new}^{f}`$ | `Link_first_active` over $`\mathcal{Y} \times \mathcal{L}`$ — one in the first period a link stands in, zero elsewhere, data prep. PyPSA `1.3.0` takes `active.cumsum() == 1`, which also counts a link that has retired in every later period (`global_constraints.py:276`, PyPSA/PyPSA\#1938) |
| $`\mathrm{f}^{\mathrm{set}}`$ | `Link_p_set` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — a given flow schedule; a link without one has no row here |
| $`\underline{\mathrm{f}}^{\mathrm{nom}}`$ | `Link_p_nom_min` over $`\Xi \times \mathcal{L}`$ — least nominal power an extendable link may be built at |
| $`\overline{\mathrm{f}}^{\mathrm{nom}}`$ | `Link_p_nom_max` over $`\Xi \times \mathcal{L}`$ — most nominal power an extendable link may be built at |
| $`\mathrm{c}^{\mathrm{cap},f}`$ | `Link_capital_cost` over $`\Xi \times \mathcal{L}`$ — cost of one unit of nominal power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $`\mathrm{f}^{\mathrm{nom,set}}`$ | `Link_p_nom_set` over $`\Xi \times \mathcal{L}`$ — a given nominal power for an extendable link; one without a value has no row here |
| $`\mathrm{len}^{f}`$ | `Link_volume_weight` over $`\Xi \times \mathcal{G} \times \mathcal{L}`$ — the link's length where its carrier is in the row's set, the first scenario's length as PyPSA reads it (`global_constraints.py:835-836`) — data prep; a link outside it, or one that does not stand in the row's `investment_period`, has no row |
| $`\mathrm{cc}^{f}`$ | `Link_expansion_cost_weight` over $`\Xi \times \mathcal{G} \times \mathcal{L}`$ — the link's capital cost where its carrier is in the row's set, times the objective weights of the periods it stands in where the row names no `investment_period` under `multi_investment_periods` — data prep; a link outside the set, or one that does not stand in the row's period, has no row |
| $`\mathrm{m}^{f}`$ | `Link_tech_capacity_weight` over $`\mathcal{G} \times \mathcal{L}`$ — one where the link is in the row's carrier-and-bus set — data prep; one outside it, or one that does not stand in the row's `investment_period`, has no row |

#### Variables

| Symbol | Meaning |
|---|---|
| $`f`$ | `Link_p` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — `Link-p` — PyPSA's `p0`, the flow measured at the `Link_bus0` end: a positive value withdraws there and injects at every bus the link's output ports deliver to |
| $`N^{f}`$ | `Link_n_mod` over $`\mathcal{L}`$ — `Link-n_mod` — how many modules of an extendable modular build |
| $`F`$ | `Link_p_nom_ext` over $`\mathcal{L}`$ — `Link-p_nom` — nominal power where it is a decision; the parameter of the same PyPSA name carries the fixed regime |

#### Given

| Symbol | Meaning |
|---|---|
| $`\mathrm{w}`$ | `snapshot_weightings_objective` over $`\mathcal{T}`$, data another file declares |
| $`\mathrm{com}^{f}`$ | `Link_committable` over $`\mathcal{L}`$, data another file declares |
| $`\gamma^{f}`$ | `Link_maintenance_pu` over $`\Xi \times \mathcal{L}`$, data another file declares |
| $`\pi`$ | `scenario_weight` over $`\Xi`$, data another file declares |
| $`\omega`$ | `CVaR_omega` (scalar), data another file declares |
| $`\mathrm{w}^{y}`$ | `period_weight_objective` over $`\mathcal{Y}`$, data another file declares |
| $`\mu^{f}`$ | `Link_maintenance` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ |
| $`\mu^{f,\mathrm{nom}}`$ | `Link_maintenance_capacity` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ |
| $`\mathit{transmission\_volume\_expansion}`$ | `transmission_volume_expansion` over $`\Xi \times \mathcal{G}`$, an expression this file adds `Link_transmission_volume_expansion` to |
| $`\mathit{transmission\_expansion\_cost}`$ | `transmission_expansion_cost` over $`\Xi \times \mathcal{G}`$, an expression this file adds `Link_transmission_expansion_cost` to |
| $`\mathit{tech\_capacity\_expansion}`$ | `tech_capacity_expansion` over $`\mathcal{G}`$, an expression this file adds `Link_tech_capacity_expansion` to |
| $`\mathit{scenario\_opex}`$ | `scenario_opex` over $`\Xi`$, an expression this file adds `Link_opex` to |
| $`\mathit{Carrier\_additions}`$ | `Carrier_additions` over $`\mathcal{Y} \times \mathcal{I}`$, an expression this file adds `Link_additions` to |
| $`\mathit{Bus\_injection}`$ | `Bus_injection` over $`\Xi \times \mathcal{T} \times \mathcal{N}`$, an expression this file adds `Link_injection` to |

#### Definitions

| Symbol | Meaning |
|---|---|
| $`\widetilde{\mathrm{f}}^{\mathrm{nom}}`$ | `Link_p_nom_effective` over $`\Xi \times \mathcal{L}`$ — the build a link's limits are taken against — the chosen one where it is extendable, the given one otherwise |
| $`\widehat{\mathrm{f}}^{\mathrm{nom}}`$ | `Link_p_nom_committed` over $`\Xi \times \mathcal{L}`$ — the build a committed link's ramp rows are taken against — one module where the build is extendable and modular, the given build otherwise |
| $`\overrightarrow{f}`$ | `Link_output_arrival` over $`\Xi \times \mathcal{T} \times \mathcal{O}`$ — what a link delivers to an output port at a snapshot — its flow after the port's efficiency, delayed by the port's `delay` within its investment period; where the port is `cyclic_delay` the delayed flow wraps from the period's end, and where it is not the flow still in transit at the period's first snapshots is lost. A port that does not delay (`delay` zero) delivers its flow unshifted, cyclic or not |
| $`\mathit{Link\_transmission\_volume\_expansion}`$ | `Link_transmission_volume_expansion` over $`\Xi \times \mathcal{G}`$ |
| $`\mathit{Link\_transmission\_expansion\_cost}`$ | `Link_transmission_expansion_cost` over $`\Xi \times \mathcal{G}`$ |
| $`\mathit{Link\_tech\_capacity\_expansion}`$ | `Link_tech_capacity_expansion` over $`\mathcal{G}`$ |
| $`\mathit{Link\_opex}`$ | `Link_opex` over $`\Xi`$ |
| $`\mathit{Link\_additions}`$ | `Link_additions` over $`\mathcal{Y} \times \mathcal{I}`$ |
| $`\mathit{Link\_injection}`$ | `Link_injection` over $`\Xi \times \mathcal{T} \times \mathcal{N}`$ |

$`t \ominus k`$ denotes cyclic translation: index $`t-k`$ taken modulo the size of the dimension (`roll`). Plain $`t-k`$ (`shift`) has no wraparound — terms translated past the edge are simply absent.

$`t \boxminus_{v} k`$ denotes translation with $`v`$ standing where index $`t-k`$ leaves the dimension (`shift(edge=v)`), so the row at that boundary is built and carries $`v`$ rather than being dropped.

$`t \ominus^{\mathrm{relation}(t)} k`$ denotes a translation counted inside the group a relation puts $`t`$ in (`shift(by=relation)`), so a term never crosses out of its own group. The two modifiers take different slots — the group above, the fill below — so $`t \boxminus_{v}^{\mathrm{relation}(t)} k`$ is both at once.

#### Objective

```math
\min \sum_{\xi \in \Xi,\ l \in \mathcal{L}} \pi_{\xi} \cdot F_{l} \cdot \mathrm{c}^{\mathrm{cap},f}_{\xi,l} \cdot \mathrm{W}^{f}_{l}
```

#### Subject to

**`Link_fix_p_lower`**

```math
f_{\xi,t,l} \ge \underline{\mathrm{f}}_{\xi,t,l} \cdot \mathrm{f}^{\mathrm{nom}}_{\xi,l} \cdot \left( 1 - \gamma^{f}_{\xi,l} \cdot \mu^{f}_{\xi,t,l} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \neg \mathrm{ext}^{f}_{l} \wedge \neg \mathrm{com}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_fix_p_upper`**

```math
f_{\xi,t,l} \le \overline{\mathrm{f}}_{\xi,t,l} \cdot \mathrm{f}^{\mathrm{nom}}_{\xi,l} \cdot \left( 1 - \gamma^{f}_{\xi,l} \cdot \mu^{f}_{\xi,t,l} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \neg \mathrm{ext}^{f}_{l} \wedge \neg \mathrm{com}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_ext_p_lower`**

```math
f_{\xi,t,l} \ge \underline{\mathrm{f}}_{\xi,t,l} \cdot \left( F_{l} - \gamma^{f}_{\xi,l} \cdot \mu^{f,\mathrm{nom}}_{\xi,t,l} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{ext}^{f}_{l} \wedge \neg \mathrm{com}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_ext_p_upper`**

```math
f_{\xi,t,l} \le \overline{\mathrm{f}}_{\xi,t,l} \cdot \left( F_{l} - \gamma^{f}_{\xi,l} \cdot \mu^{f,\mathrm{nom}}_{\xi,t,l} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{ext}^{f}_{l} \wedge \neg \mathrm{com}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_ext_p_nom_lower`**

```math
F_{l} \ge \underline{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L} \,:\, \mathrm{ext}^{f}_{l}
```

**`Link_ext_p_nom_upper`**

```math
F_{l} \le \overline{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L} \,:\, \mathrm{ext}^{f}_{l} \wedge \overline{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} \text{ is defined}
```

**`Link_p_nom_set`**

```math
F_{l} = \mathrm{f}^{\mathrm{nom,set}}_{\xi,l} \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L} \,:\, \mathrm{ext}^{f}_{l} \wedge \mathrm{f}^{\mathrm{nom,set}}_{\xi,l} \text{ is defined}
```

**`Link_p_nom_modularity`**

```math
F_{l} = \mathrm{f}^{\mathrm{mod}}_{l} \cdot N^{f}_{l} \qquad \forall\, l \in \mathcal{L} \,:\, \mathrm{ext}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0
```

**`Link_p_set`**

```math
f_{\xi,t,l} = \mathrm{f}^{\mathrm{set}}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{f}^{\mathrm{set}}_{\xi,t,l} \text{ is defined} \wedge \mathrm{on}^{f}_{t,l}
```

#### Definitions

**`Link_p_nom_effective`**

```math
\widetilde{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} = \begin{cases} F_{l} & \text{if } \mathrm{ext}^{f}_{l} \\ \mathrm{f}^{\mathrm{nom}}_{\xi,l} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L}
```

**`Link_p_nom_committed`**

```math
\widehat{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} = \begin{cases} \mathrm{f}^{\mathrm{mod}}_{l} & \text{if } \mathrm{ext}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \\ \mathrm{f}^{\mathrm{nom}}_{\xi,l} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L}
```

**`Link_output_arrival`**

```math
\overrightarrow{f}_{\xi,t,o} = \begin{cases} f_{\xi,t \ominus^{\mathrm{snapshot\_period}(t)} \mathrm{d}^{f},\mathrm{Link\_output\_link}(o)} \cdot \eta_{\xi,o} & \text{if } \mathrm{cyc}^{f}_{\xi,o} \\ f_{\xi,t \boxminus_{0}^{\mathrm{snapshot\_period}(t)} \mathrm{d}^{f},\mathrm{Link\_output\_link}(o)} \cdot \eta_{\xi,o} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ o \in \mathcal{O}
```

**`Link_transmission_volume_expansion`**

```math
\mathit{Link\_transmission\_volume\_expansion}_{\xi,g} = \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{len}^{f}_{\xi,g,l} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G}
```

**`Link_transmission_expansion_cost`**

```math
\mathit{Link\_transmission\_expansion\_cost}_{\xi,g} = \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{cc}^{f}_{\xi,g,l} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G}
```

**`Link_tech_capacity_expansion`**

```math
\mathit{Link\_tech\_capacity\_expansion}_{g} = \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{m}^{f}_{g,l} \qquad \forall\, g \in \mathcal{G}
```

**`Link_opex`**

```math
\mathit{Link\_opex}_{\xi} = \sum_{t \in \mathcal{T}} \sum_{l \in \mathcal{L}} f_{\xi,t,l} \cdot \mathrm{c}^{f}_{\xi,t,l} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{l \in \mathcal{L}} f_{\xi,t,l} \cdot f_{\xi,t,l} \cdot \mathrm{c}^{f,(2)}_{\xi,t,l} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} \qquad \forall\, \xi \in \Xi
```

**`Link_additions`**

```math
\mathit{Link\_additions}_{y,i} = \sum_{l \in \mathcal{L} \,:\, \mathrm{Link\_carrier}(l) = i} F_{l} \cdot \mathrm{new}^{f}_{y,l} \qquad \forall\, y \in \mathcal{Y},\ i \in \mathcal{I}
```

**`Link_injection`**

```math
\mathit{Link\_injection}_{\xi,t,n} = -\left( \sum_{l \in \mathcal{L} \,:\, \mathrm{Link\_bus0}(l) = n} f_{\xi,t,l} \right) + \sum_{o \in \mathcal{O} \,:\, \mathrm{Link\_output\_bus}(o) = n} \overrightarrow{f}_{\xi,t,o} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ n \in \mathcal{N}
```

#### Variable domains

**`Link_p`**

```math
f_{\xi,t,l} \in \mathbb{R} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{on}^{f}_{t,l}
```

**`Link_n_mod`**

```math
N^{f}_{l} \ge 0, N^{f}_{l} \in \mathbb{Z} \qquad \forall\, l \in \mathcal{L} \,:\, \mathrm{ext}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0
```

**`Link_p_nom_ext`**

```math
F_{l} \in \mathbb{R} \qquad \forall\, l \in \mathcal{L} \,:\, \mathrm{ext}^{f}_{l}
```

#### Assumptions

**`Link_marginal_cost_quadratic_without_risk_preference`**

```math
\mathrm{c}^{f,(2)}_{\xi,t,l} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \omega > 0
```
<!-- gallery:end -->
