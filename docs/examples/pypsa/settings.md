<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Settings

One of the [24 fragments](index.md) of `examples/pypsa.yaml`: the weightings, the risk preference and the flags every topic reads, and the readings of the totals whose readers may be left out. It reads `Carrier_additions`, `operational_limit`, `primary_energy`, `scenario_opex`, `tech_capacity_expansion`, `transmission_expansion_cost` and 1 more under [`given`](../../reference/language/declarations.md#given).

<!-- gallery:begin -->
```yaml
dimensions:
  scenario:
    description: the futures dispatch is chosen in, each with a weight
  snapshot:
    description: dispatch periods
    dtype: datetime
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

parameters:
  snapshot_weightings_objective:
    description: PyPSA's `snapshot_weightings.objective` — hours a snapshot stands for in the cost
    dims: [snapshot]
  scenario_weight:
    description: PyPSA's `scenario_weightings.weight` — the probability of a future
    dims: [scenario]
  CVaR_omega:
    description: PyPSA's `risk_preference['omega']` — the share of operating cost priced at the tail rather than in expectation; zero recovers the risk-neutral model
    dims: []
  period_weight_objective:
    description: PyPSA's `investment_period_weightings.objective` — what a period's cost weighs
    dims: [period]
  period_weight_years:
    description: >-
      PyPSA's `investment_period_weightings.years` — what a period's energy
      weighs in a `primary_energy` or `operational_limit` row; PyPSA reads it
      only under `multi_investment_periods`, so data prep feeds one otherwise
    dims: [period]
  snapshot_weightings_stores:
    description: PyPSA's `snapshot_weightings.stores` — hours a snapshot stands for in a storage balance
    dims: [snapshot]
  snapshot_weightings_generators:
    description: PyPSA's `snapshot_weightings.generators` — hours a snapshot stands for in an energy total
    dims: [snapshot]
  transmission_losses:
    description: >-
      whether the network dissipates transmission losses — PyPSA's
      `transmission_losses` read as a flag; its mode, tangents or secants,
      only decides how data prep fills the `segment` axis, the rows are the
      same; false with no segments is a lossless run. A security-constrained
      run over a network with passive branches builds no loss: PyPSA does not
      hand the keyword to `create_model` (`abstract.py:437-441`) but to the
      solver (`:491`), so data prep feeds false there
    dims: []
    dtype: bool
  GlobalConstraint_counts_snapshot:
    description: >-
      whether a row counts a snapshot in a scenario — PyPSA's `investment_period`: every
      snapshot where the row names none, and only that period's where it
      names one, data prep. A row that names a period the run does not model
      has no label here, as PyPSA skips it (`global_constraints.py:377`);
      PyPSA reads the column only under `multi_investment_periods`, and fails
      on a row that names a period without it (`global_constraints.py:375`)
    dims: [scenario, global_constraint, snapshot]
    dtype: bool

given:
  expressions:
    primary_energy:
      dims: [scenario, global_constraint]
      description: >-
        what a `primary_energy` row totals — weighted generator energy over the
        snapshots it counts, less the charge left in weighted storage at the
        close; the initial charge it is compared against is folded into the
        row's constant
    operational_limit:
      dims: [scenario, global_constraint]
      description: >-
        what an `operational_limit` row totals — the weighted energy its
        generators deliver over the snapshots it counts, plus what its
        non-cyclic storage draws down; the initial charge it draws from is
        folded into the row's constant
    transmission_volume_expansion:
      dims: [scenario, global_constraint]
      description: >-
        what a `transmission_volume_expansion_limit` row totals — length times
        the chosen build of the row's branches
    transmission_expansion_cost:
      dims: [scenario, global_constraint]
      description: >-
        what a `transmission_expansion_cost_limit` row totals — capital cost
        times the chosen build of the row's branches
    tech_capacity_expansion:
      dims: [global_constraint]
      description: >-
        what a `tech_capacity_expansion_limit` row totals — the chosen build of
        the row's carrier-and-bus set
    scenario_opex:
      dims: [scenario]
      description: >-
        what a future costs to run — every operating term, weighted by the
        snapshot's hours and its period, before the scenario's own weight; a
        start and a stop cost what they cost, unweighted, as PyPSA adds them
        (`optimize.py:414-429`)
    Carrier_additions:
      dims: [period, carrier]
      description: >-
        what a carrier adds in a period — every extendable component of that
        carrier, counting each build in the first period it stands in. Like
        PyPSA, it sums only the components that carry a carrier attribute, so a
        transformer, which has none, counts in no carrier

expressions:
  GlobalConstraint_energy_weight:
    description: >-
      what one unit of power at a snapshot counts for in a row — the
      generator weighting times the years of the snapshot's period, where the
      row counts the snapshot, and nothing where it does not
    dims: [scenario, global_constraint, snapshot]
    cases:
      counted:
        when: GlobalConstraint_counts_snapshot
        expression: snapshot_weightings_generators * at(period_weight_years, by=snapshot_period, over=period, into=snapshot)
    otherwise: 0
  GlobalConstraint_snapshot_closes:
    description: one at the last snapshot a row counts, and zero elsewhere
    dims: [scenario, global_constraint, snapshot]
    cases:
      last_counted:
        when: GlobalConstraint_counts_snapshot AND NOT shift(GlobalConstraint_counts_snapshot, along=snapshot, offset=-1)
        expression: 1
    otherwise: 0
```

#### Sets

| Symbol | Meaning |
|---|---|
| $`\Xi`$ | index $`\xi`$ — `scenario` — the futures dispatch is chosen in, each with a weight |
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` with $`\mathrm{snapshot\_period}: \mathcal{T} \to \mathcal{Y}`$ — dispatch periods |
| $`\mathcal{G}`$ | index $`g`$ — `global_constraint` — PyPSA's `GlobalConstraint` rows, one label per declared limit |
| $`\mathcal{Y}`$ | index $`y`$ — `period` with $`\mathrm{snapshot\_period}: \mathcal{T} \to \mathcal{Y}`$ — investment periods — PyPSA's `investment_periods` |
| $`\mathcal{I}`$ | index $`i`$ — `carrier` — energy carriers, what a growth limit is set per |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{w}`$ | `snapshot_weightings_objective` over $`\mathcal{T}`$ — PyPSA's `snapshot_weightings.objective` — hours a snapshot stands for in the cost |
| $`\pi`$ | `scenario_weight` over $`\Xi`$ — PyPSA's `scenario_weightings.weight` — the probability of a future |
| $`\omega`$ | `CVaR_omega` (scalar) — PyPSA's `risk_preference['omega']` — the share of operating cost priced at the tail rather than in expectation; zero recovers the risk-neutral model |
| $`\mathrm{w}^{y}`$ | `period_weight_objective` over $`\mathcal{Y}`$ — PyPSA's `investment_period_weightings.objective` — what a period's cost weighs |
| $`\mathrm{w}^{\mathrm{yr}}`$ | `period_weight_years` over $`\mathcal{Y}`$ — PyPSA's `investment_period_weightings.years` — what a period's energy weighs in a `primary_energy` or `operational_limit` row; PyPSA reads it only under `multi_investment_periods`, so data prep feeds one otherwise |
| $`\mathrm{w}^{\mathrm{sto}}`$ | `snapshot_weightings_stores` over $`\mathcal{T}`$ — PyPSA's `snapshot_weightings.stores` — hours a snapshot stands for in a storage balance |
| $`\mathrm{w}^{\mathrm{gen}}`$ | `snapshot_weightings_generators` over $`\mathcal{T}`$ — PyPSA's `snapshot_weightings.generators` — hours a snapshot stands for in an energy total |
| $`\mathrm{lossy}`$ | `transmission_losses` (scalar) — whether the network dissipates transmission losses — PyPSA's `transmission_losses` read as a flag; its mode, tangents or secants, only decides how data prep fills the `segment` axis, the rows are the same; false with no segments is a lossless run. A security-constrained run over a network with passive branches builds no loss: PyPSA does not hand the keyword to `create_model` (`abstract.py:437-441`) but to the solver (`:491`), so data prep feeds false there |
| $`\mathrm{in}`$ | `GlobalConstraint_counts_snapshot` over $`\Xi \times \mathcal{G} \times \mathcal{T}`$ — whether a row counts a snapshot in a scenario — PyPSA's `investment_period`: every snapshot where the row names none, and only that period's where it names one, data prep. A row that names a period the run does not model has no label here, as PyPSA skips it (`global_constraints.py:377`); PyPSA reads the column only under `multi_investment_periods`, and fails on a row that names a period without it (`global_constraints.py:375`) |

#### Given

| Symbol | Meaning |
|---|---|
| $`\mathit{primary\_energy}`$ | `primary_energy` over $`\Xi \times \mathcal{G}`$, an expression another file defines — what a `primary_energy` row totals — weighted generator energy over the snapshots it counts, less the charge left in weighted storage at the close; the initial charge it is compared against is folded into the row's constant |
| $`\mathit{operational\_limit}`$ | `operational_limit` over $`\Xi \times \mathcal{G}`$, an expression another file defines — what an `operational_limit` row totals — the weighted energy its generators deliver over the snapshots it counts, plus what its non-cyclic storage draws down; the initial charge it draws from is folded into the row's constant |
| $`\mathit{transmission\_volume\_expansion}`$ | `transmission_volume_expansion` over $`\Xi \times \mathcal{G}`$, an expression another file defines — what a `transmission_volume_expansion_limit` row totals — length times the chosen build of the row's branches |
| $`\mathit{transmission\_expansion\_cost}`$ | `transmission_expansion_cost` over $`\Xi \times \mathcal{G}`$, an expression another file defines — what a `transmission_expansion_cost_limit` row totals — capital cost times the chosen build of the row's branches |
| $`\mathit{tech\_capacity\_expansion}`$ | `tech_capacity_expansion` over $`\mathcal{G}`$, an expression another file defines — what a `tech_capacity_expansion_limit` row totals — the chosen build of the row's carrier-and-bus set |
| $`\mathit{scenario\_opex}`$ | `scenario_opex` over $`\Xi`$, an expression another file defines — what a future costs to run — every operating term, weighted by the snapshot's hours and its period, before the scenario's own weight; a start and a stop cost what they cost, unweighted, as PyPSA adds them (`optimize.py:414-429`) |
| $`\mathit{Carrier\_additions}`$ | `Carrier_additions` over $`\mathcal{Y} \times \mathcal{I}`$, an expression another file defines — what a carrier adds in a period — every extendable component of that carrier, counting each build in the first period it stands in. Like PyPSA, it sums only the components that carry a carrier attribute, so a transformer, which has none, counts in no carrier |

#### Definitions

| Symbol | Meaning |
|---|---|
| $`\mathit{w}^{\mathrm{gc}}`$ | `GlobalConstraint_energy_weight` over $`\Xi \times \mathcal{G} \times \mathcal{T}`$ — what one unit of power at a snapshot counts for in a row — the generator weighting times the years of the snapshot's period, where the row counts the snapshot, and nothing where it does not |
| $`\mathit{last}`$ | `GlobalConstraint_snapshot_closes` over $`\Xi \times \mathcal{G} \times \mathcal{T}`$ — one at the last snapshot a row counts, and zero elsewhere |

#### Definitions

**`GlobalConstraint_energy_weight`**

```math
\mathit{w}^{\mathrm{gc}}_{\xi,g,t} = \begin{cases} \mathrm{w}^{\mathrm{gen}}_{t} \cdot \mathrm{w}^{\mathrm{yr}}_{\mathrm{snapshot\_period}(t)} & \text{if } \mathrm{in}_{\xi,g,t} \\ 0 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G},\ t \in \mathcal{T}
```

**`GlobalConstraint_snapshot_closes`**

```math
\mathit{last}_{\xi,g,t} = \begin{cases} 1 & \text{if } \mathrm{in}_{\xi,g,t} \wedge \neg \mathrm{in}_{\xi,g,t + 1} \\ 0 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G},\ t \in \mathcal{T}
```
<!-- gallery:end -->
