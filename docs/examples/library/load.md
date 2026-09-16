<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Loads

The second component template, and the one that shows what a fragment may
leave out. It declares no variable and no objective: a fixed demand is a
parameter, and the only thing it says is what its port withdraws.

The minus sign is the whole of its relationship to the convention — a
withdrawal is a negative injection.

<!-- gallery:begin -->
```yaml
description: Fixed demands, each wired to one port, withdrawing what the data says.
dimensions:
  snapshot: { dtype: int }
  port: { dtype: str }
  demand: { dtype: str }
relations:
  dem_port: { key: demand, value: port }
given_variables:
  flow:
    dims: [snapshot, port]
    description: the surface introduces this column, and this file only writes into it
parameters:
  dem_load: { dims: [snapshot, demand], description: what a demand takes in a snapshot }
constraints:
  dem_withdraws:
    description: a demand's port withdraws what the demand takes
    dims: [snapshot, demand]
    expression: at(flow, by=dem_port) == -dem_load
```

Fixed demands, each wired to one port, withdrawing what the data says.

#### Sets

| Symbol | Meaning |
|---|---|
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` |
| $`\mathcal{P}`$ | index $`p`$ — `port` with $`\mathrm{dem\_port}: \mathcal{D} \to \mathcal{P}`$ |
| $`\mathcal{D}`$ | index $`d`$ — `demand` with $`\mathrm{dem\_port}: \mathcal{D} \to \mathcal{P}`$ |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{dem\_load}`$ | `dem_load` over $`\mathcal{T} \times \mathcal{D}`$ — what a demand takes in a snapshot |

#### Given

| Symbol | Meaning |
|---|---|
| $`\mathit{flow}`$ | `flow` over $`\mathcal{T} \times \mathcal{P}`$ — the surface introduces this column, and this file only writes into it |

#### Subject to

**`dem_withdraws`**

```math
\mathit{flow}_{t,\mathrm{dem\_port}(d)} = -\mathrm{dem\_load}_{t,d} \qquad \forall\, t \in \mathcal{T},\ d \in \mathcal{D}
```
<!-- gallery:end -->
