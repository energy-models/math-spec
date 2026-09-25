<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Carriers

One of the [24 fragments](index.md) of `examples/pypsa.yaml`: the growth limits per carrier, which read `Carrier_additions`. It reads `Carrier_additions` under [`given`](../../reference/language/declarations.md#given).

<!-- gallery:begin -->
```yaml
dimensions:
  period:
    description: investment periods — PyPSA's `investment_periods`
    dtype: int
  carrier:
    description: energy carriers, what a growth limit is set per

parameters:
  Carrier_max_growth:
    description: >-
      most capacity of a carrier that may be added in a period; no value means
      no limit. The least over the scenarios, as PyPSA takes it
      (`global_constraints.py:226-230`), data prep. PyPSA reads it only under
      `multi_investment_periods` (`global_constraints.py:219-220`), so data
      prep feeds no value otherwise
    dims: [carrier]
  Carrier_max_relative_growth:
    description: >-
      share of the previous period's additions that may be added on top — the
      least over the scenarios, as PyPSA takes it, data prep
    dims: [carrier]

given:
  expressions:
    Carrier_additions: { dims: [period, carrier] }

expressions:
  Carrier_relative_growth:
    description: >-
      the share of the previous period's additions a carrier's growth limit
      reads — PyPSA's `max_relative_growth` clipped at zero, so a negative
      share adds nothing and never tightens the limit
    dims: [carrier]
    cases:
      positive: { when: Carrier_max_relative_growth > 0, expression: Carrier_max_relative_growth }
    otherwise: 0

constraints:
  Carrier_growth_limit:
    description: >-
      `Carrier-growth_limit` — what a carrier adds across its extendable components in a period,
      counting each build in the first period it stands in, is at most its allowance plus a share of
      what it added the period before; the first period has no predecessor, so `edge=0` leaves it the
      bare allowance
    dims: [carrier, period]
    where: Carrier_max_growth
    expression: >-
      Carrier_additions
      - shift(Carrier_additions, along=period, offset=1, edge=0) * Carrier_relative_growth
      <= Carrier_max_growth
```

#### Sets

| Symbol | Meaning |
|---|---|
| $`\mathcal{Y}`$ | index $`y`$ — `period` — investment periods — PyPSA's `investment_periods` |
| $`\mathcal{I}`$ | index $`i`$ — `carrier` — energy carriers, what a growth limit is set per |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\overline{\Delta}`$ | `Carrier_max_growth` over $`\mathcal{I}`$ — most capacity of a carrier that may be added in a period; no value means no limit. The least over the scenarios, as PyPSA takes it (`global_constraints.py:226-230`), data prep. PyPSA reads it only under `multi_investment_periods` (`global_constraints.py:219-220`), so data prep feeds no value otherwise |
| $`\mathrm{r}`$ | `Carrier_max_relative_growth` over $`\mathcal{I}`$ — share of the previous period's additions that may be added on top — the least over the scenarios, as PyPSA takes it, data prep |

#### Given

| Symbol | Meaning |
|---|---|
| $`\mathit{Carrier\_additions}`$ | `Carrier_additions` over $`\mathcal{Y} \times \mathcal{I}`$, an expression another file defines |

#### Definitions

| Symbol | Meaning |
|---|---|
| $`\mathrm{r}^{+}`$ | `Carrier_relative_growth` over $`\mathcal{I}`$ — the share of the previous period's additions a carrier's growth limit reads — PyPSA's `max_relative_growth` clipped at zero, so a negative share adds nothing and never tightens the limit |

$`t \boxminus_{v} k`$ denotes translation with $`v`$ standing where index $`t-k`$ leaves the dimension (`shift(edge=v)`), so the row at that boundary is built and carries $`v`$ rather than being dropped.

#### Subject to

**`Carrier_growth_limit`**

```math
\mathit{Carrier\_additions}_{y,i} - \mathit{Carrier\_additions}_{y \boxminus_{0} 1,i} \cdot \mathrm{r}^{+}_{i} \le \overline{\Delta}_{i} \qquad \forall\, i \in \mathcal{I},\ y \in \mathcal{Y} \,:\, \overline{\Delta}_{i} \text{ is defined}
```

#### Definitions

**`Carrier_relative_growth`**

```math
\mathrm{r}^{+}_{i} = \begin{cases} \mathrm{r}_{i} & \text{if } \mathrm{r}_{i} > 0 \\ 0 & \text{otherwise} \end{cases} \qquad \forall\, i \in \mathcal{I}
```
<!-- gallery:end -->
