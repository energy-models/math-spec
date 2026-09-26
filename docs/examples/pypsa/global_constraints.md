<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Global constraints

One of the [24 fragments](index.md) of `examples/pypsa.yaml`: the five system totals PyPSA caps, each a sum the components add to. It reads `operational_limit`, `primary_energy`, `scenario_weight`, `tech_capacity_expansion`, `transmission_expansion_cost`, `transmission_volume_expansion` under [`given`](../../reference/language/declarations.md#given).

<!-- gallery:begin -->
```yaml
dimensions:
  scenario:
    description: the futures dispatch is chosen in, each with a weight
  global_constraint:
    description: PyPSA's `GlobalConstraint` rows, one label per declared limit

parameters:
  GlobalConstraint_type:
    description: >-
      which formula the row takes — `primary_energy`, `operational_limit`,
      `transmission_volume_expansion_limit`,
      `transmission_expansion_cost_limit` or
      `tech_capacity_expansion_limit`
    dims: [global_constraint]
    dtype: str
  GlobalConstraint_sense:
    description: >-
      which way the row binds in each scenario — `<=`, `>=` or `==`; PyPSA
      reads a row's sense per scenario (`global_constraints.py:556`, `:748`,
      `:860`)
    dims: [scenario, global_constraint]
    dtype: str
  GlobalConstraint_constant:
    description: >-
      the constant the total is held against; what a variable cannot carry —
      an initial charge, times its period's years for each counted period
      where the storage reopens per period, or a non-extendable build — is
      folded in here by data prep. PyPSA reads it per scenario
      (`global_constraints.py:557`, `:749`, `:861`)
    dims: [scenario, global_constraint]

given:
  parameters:
    scenario_weight: { dims: [scenario] }
  expressions:
    primary_energy: { dims: [scenario, global_constraint] }
    operational_limit: { dims: [scenario, global_constraint] }
    transmission_volume_expansion: { dims: [scenario, global_constraint] }
    transmission_expansion_cost: { dims: [scenario, global_constraint] }
    tech_capacity_expansion: { dims: [global_constraint] }

constraints:
  GlobalConstraint_primary_energy_ub:
    description: "`primary_energy` — its total, at most its constant"
    dims: [scenario, global_constraint]
    where: GlobalConstraint_type == 'primary_energy' AND GlobalConstraint_sense == '<='
    expression: primary_energy <= GlobalConstraint_constant
  GlobalConstraint_primary_energy_lb:
    description: "`primary_energy` — its total, at least its constant"
    dims: [scenario, global_constraint]
    where: GlobalConstraint_type == 'primary_energy' AND GlobalConstraint_sense == '>='
    expression: primary_energy >= GlobalConstraint_constant
  GlobalConstraint_primary_energy_eq:
    description: "`primary_energy` — its total, at its constant"
    dims: [scenario, global_constraint]
    where: GlobalConstraint_type == 'primary_energy' AND GlobalConstraint_sense == '=='
    expression: primary_energy == GlobalConstraint_constant
  GlobalConstraint_operational_limit_ub:
    description: "`operational_limit` — its total, at most its constant"
    dims: [scenario, global_constraint]
    where: GlobalConstraint_type == 'operational_limit' AND GlobalConstraint_sense == '<='
    expression: operational_limit <= GlobalConstraint_constant
  GlobalConstraint_operational_limit_lb:
    description: "`operational_limit` — its total, at least its constant"
    dims: [scenario, global_constraint]
    where: GlobalConstraint_type == 'operational_limit' AND GlobalConstraint_sense == '>='
    expression: operational_limit >= GlobalConstraint_constant
  GlobalConstraint_operational_limit_eq:
    description: "`operational_limit` — its total, at its constant"
    dims: [scenario, global_constraint]
    where: GlobalConstraint_type == 'operational_limit' AND GlobalConstraint_sense == '=='
    expression: operational_limit == GlobalConstraint_constant
  GlobalConstraint_transmission_volume_expansion_limit_ub:
    description: "`transmission_volume_expansion_limit` — its total, at most its constant"
    dims: [scenario, global_constraint]
    where: GlobalConstraint_type == 'transmission_volume_expansion_limit' AND GlobalConstraint_sense == '<='
    expression: transmission_volume_expansion <= GlobalConstraint_constant
  GlobalConstraint_transmission_volume_expansion_limit_lb:
    description: "`transmission_volume_expansion_limit` — its total, at least its constant"
    dims: [scenario, global_constraint]
    where: GlobalConstraint_type == 'transmission_volume_expansion_limit' AND GlobalConstraint_sense == '>='
    expression: transmission_volume_expansion >= GlobalConstraint_constant
  GlobalConstraint_transmission_volume_expansion_limit_eq:
    description: "`transmission_volume_expansion_limit` — its total, at its constant"
    dims: [scenario, global_constraint]
    where: GlobalConstraint_type == 'transmission_volume_expansion_limit' AND GlobalConstraint_sense == '=='
    expression: transmission_volume_expansion == GlobalConstraint_constant
  GlobalConstraint_transmission_expansion_cost_limit_ub:
    description: "`transmission_expansion_cost_limit` — its total, at most its constant"
    dims: [scenario, global_constraint]
    where: GlobalConstraint_type == 'transmission_expansion_cost_limit' AND GlobalConstraint_sense == '<='
    expression: transmission_expansion_cost <= GlobalConstraint_constant
  GlobalConstraint_transmission_expansion_cost_limit_lb:
    description: "`transmission_expansion_cost_limit` — its total, at least its constant"
    dims: [scenario, global_constraint]
    where: GlobalConstraint_type == 'transmission_expansion_cost_limit' AND GlobalConstraint_sense == '>='
    expression: transmission_expansion_cost >= GlobalConstraint_constant
  GlobalConstraint_transmission_expansion_cost_limit_eq:
    description: "`transmission_expansion_cost_limit` — its total, at its constant"
    dims: [scenario, global_constraint]
    where: GlobalConstraint_type == 'transmission_expansion_cost_limit' AND GlobalConstraint_sense == '=='
    expression: transmission_expansion_cost == GlobalConstraint_constant
  GlobalConstraint_tech_capacity_expansion_limit_ub:
    description: "`tech_capacity_expansion_limit` — its total, at most its constant"
    dims: [scenario, global_constraint]
    where: GlobalConstraint_type == 'tech_capacity_expansion_limit' AND GlobalConstraint_sense == '<='
    expression: tech_capacity_expansion <= GlobalConstraint_constant
  GlobalConstraint_tech_capacity_expansion_limit_lb:
    description: "`tech_capacity_expansion_limit` — its total, at least its constant"
    dims: [scenario, global_constraint]
    where: GlobalConstraint_type == 'tech_capacity_expansion_limit' AND GlobalConstraint_sense == '>='
    expression: tech_capacity_expansion >= GlobalConstraint_constant
  GlobalConstraint_tech_capacity_expansion_limit_eq:
    description: "`tech_capacity_expansion_limit` — its total, at its constant"
    dims: [scenario, global_constraint]
    where: GlobalConstraint_type == 'tech_capacity_expansion_limit' AND GlobalConstraint_sense == '=='
    expression: tech_capacity_expansion == GlobalConstraint_constant

assumptions:
  GlobalConstraint_tech_capacity_expansion_limit_without_scenarios:
    holds: "GlobalConstraint_type != 'tech_capacity_expansion_limit'"
    where: "count(scenario_weight, over=scenario) > 1"
    description: >-
      PyPSA does not build a `tech_capacity_expansion_limit` row on a
      network with scenarios and refuses it
      (`global_constraints.py:66-68`). The spec cannot tell a network with
      one scenario from one with none, so it refuses only where there is
      more than one scenario
```

#### Sets

| Symbol | Meaning |
|---|---|
| $`\Xi`$ | index $`\xi`$ — `scenario` — the futures dispatch is chosen in, each with a weight |
| $`\mathcal{G}`$ | index $`g`$ — `global_constraint` — PyPSA's `GlobalConstraint` rows, one label per declared limit |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{type}`$ | `GlobalConstraint_type` over $`\mathcal{G}`$ — which formula the row takes — `primary_energy`, `operational_limit`, `transmission_volume_expansion_limit`, `transmission_expansion_cost_limit` or `tech_capacity_expansion_limit` |
| $`\mathrm{sense}`$ | `GlobalConstraint_sense` over $`\Xi \times \mathcal{G}`$ — which way the row binds in each scenario — `<=`, `>=` or `==`; PyPSA reads a row's sense per scenario (`global_constraints.py:556`, `:748`, `:860`) |
| $`\mathrm{K}`$ | `GlobalConstraint_constant` over $`\Xi \times \mathcal{G}`$ — the constant the total is held against; what a variable cannot carry — an initial charge, times its period's years for each counted period where the storage reopens per period, or a non-extendable build — is folded in here by data prep. PyPSA reads it per scenario (`global_constraints.py:557`, `:749`, `:861`) |

#### Given

| Symbol | Meaning |
|---|---|
| $`\pi`$ | `scenario_weight` over $`\Xi`$, data another file declares |
| $`\mathit{primary\_energy}`$ | `primary_energy` over $`\Xi \times \mathcal{G}`$, an expression another file defines |
| $`\mathit{operational\_limit}`$ | `operational_limit` over $`\Xi \times \mathcal{G}`$, an expression another file defines |
| $`\mathit{transmission\_volume\_expansion}`$ | `transmission_volume_expansion` over $`\Xi \times \mathcal{G}`$, an expression another file defines |
| $`\mathit{transmission\_expansion\_cost}`$ | `transmission_expansion_cost` over $`\Xi \times \mathcal{G}`$, an expression another file defines |
| $`\mathit{tech\_capacity\_expansion}`$ | `tech_capacity_expansion` over $`\mathcal{G}`$, an expression another file defines |

#### Subject to

**`GlobalConstraint_primary_energy_ub`**

```math
\mathit{primary\_energy}_{\xi,g} \le \mathrm{K}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{type}_{g} = \text{'}\mathrm{primary\_energy}\text{'} \wedge \mathrm{sense}_{\xi,g} = \text{'}\mathrm{<=}\text{'}
```

**`GlobalConstraint_primary_energy_lb`**

```math
\mathit{primary\_energy}_{\xi,g} \ge \mathrm{K}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{type}_{g} = \text{'}\mathrm{primary\_energy}\text{'} \wedge \mathrm{sense}_{\xi,g} = \text{'}\mathrm{>=}\text{'}
```

**`GlobalConstraint_primary_energy_eq`**

```math
\mathit{primary\_energy}_{\xi,g} = \mathrm{K}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{type}_{g} = \text{'}\mathrm{primary\_energy}\text{'} \wedge \mathrm{sense}_{\xi,g} = \text{'}\mathrm{==}\text{'}
```

**`GlobalConstraint_operational_limit_ub`**

```math
\mathit{operational\_limit}_{\xi,g} \le \mathrm{K}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{type}_{g} = \text{'}\mathrm{operational\_limit}\text{'} \wedge \mathrm{sense}_{\xi,g} = \text{'}\mathrm{<=}\text{'}
```

**`GlobalConstraint_operational_limit_lb`**

```math
\mathit{operational\_limit}_{\xi,g} \ge \mathrm{K}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{type}_{g} = \text{'}\mathrm{operational\_limit}\text{'} \wedge \mathrm{sense}_{\xi,g} = \text{'}\mathrm{>=}\text{'}
```

**`GlobalConstraint_operational_limit_eq`**

```math
\mathit{operational\_limit}_{\xi,g} = \mathrm{K}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{type}_{g} = \text{'}\mathrm{operational\_limit}\text{'} \wedge \mathrm{sense}_{\xi,g} = \text{'}\mathrm{==}\text{'}
```

**`GlobalConstraint_transmission_volume_expansion_limit_ub`**

```math
\mathit{transmission\_volume\_expansion}_{\xi,g} \le \mathrm{K}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{type}_{g} = \text{'}\mathrm{transmission\_volume\_expansion\_limit}\text{'} \wedge \mathrm{sense}_{\xi,g} = \text{'}\mathrm{<=}\text{'}
```

**`GlobalConstraint_transmission_volume_expansion_limit_lb`**

```math
\mathit{transmission\_volume\_expansion}_{\xi,g} \ge \mathrm{K}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{type}_{g} = \text{'}\mathrm{transmission\_volume\_expansion\_limit}\text{'} \wedge \mathrm{sense}_{\xi,g} = \text{'}\mathrm{>=}\text{'}
```

**`GlobalConstraint_transmission_volume_expansion_limit_eq`**

```math
\mathit{transmission\_volume\_expansion}_{\xi,g} = \mathrm{K}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{type}_{g} = \text{'}\mathrm{transmission\_volume\_expansion\_limit}\text{'} \wedge \mathrm{sense}_{\xi,g} = \text{'}\mathrm{==}\text{'}
```

**`GlobalConstraint_transmission_expansion_cost_limit_ub`**

```math
\mathit{transmission\_expansion\_cost}_{\xi,g} \le \mathrm{K}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{type}_{g} = \text{'}\mathrm{transmission\_expansion\_cost\_limit}\text{'} \wedge \mathrm{sense}_{\xi,g} = \text{'}\mathrm{<=}\text{'}
```

**`GlobalConstraint_transmission_expansion_cost_limit_lb`**

```math
\mathit{transmission\_expansion\_cost}_{\xi,g} \ge \mathrm{K}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{type}_{g} = \text{'}\mathrm{transmission\_expansion\_cost\_limit}\text{'} \wedge \mathrm{sense}_{\xi,g} = \text{'}\mathrm{>=}\text{'}
```

**`GlobalConstraint_transmission_expansion_cost_limit_eq`**

```math
\mathit{transmission\_expansion\_cost}_{\xi,g} = \mathrm{K}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{type}_{g} = \text{'}\mathrm{transmission\_expansion\_cost\_limit}\text{'} \wedge \mathrm{sense}_{\xi,g} = \text{'}\mathrm{==}\text{'}
```

**`GlobalConstraint_tech_capacity_expansion_limit_ub`**

```math
\mathit{tech\_capacity\_expansion}_{g} \le \mathrm{K}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{type}_{g} = \text{'}\mathrm{tech\_capacity\_expansion\_limit}\text{'} \wedge \mathrm{sense}_{\xi,g} = \text{'}\mathrm{<=}\text{'}
```

**`GlobalConstraint_tech_capacity_expansion_limit_lb`**

```math
\mathit{tech\_capacity\_expansion}_{g} \ge \mathrm{K}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{type}_{g} = \text{'}\mathrm{tech\_capacity\_expansion\_limit}\text{'} \wedge \mathrm{sense}_{\xi,g} = \text{'}\mathrm{>=}\text{'}
```

**`GlobalConstraint_tech_capacity_expansion_limit_eq`**

```math
\mathit{tech\_capacity\_expansion}_{g} = \mathrm{K}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{type}_{g} = \text{'}\mathrm{tech\_capacity\_expansion\_limit}\text{'} \wedge \mathrm{sense}_{\xi,g} = \text{'}\mathrm{==}\text{'}
```

#### Assumptions

**`GlobalConstraint_tech_capacity_expansion_limit_without_scenarios`**

```math
\mathrm{type}_{g} \neq \text{'}\mathrm{tech\_capacity\_expansion\_limit}\text{'} \qquad \forall\, g \in \mathcal{G} \,:\, \lvert \{ \xi \in \Xi \,:\, \pi_{\xi} \text{ is defined} \} \rvert > 1
```
<!-- gallery:end -->
