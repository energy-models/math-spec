<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# The network

One of the [24 fragments](index.md) of `examples/pypsa.yaml`: the buses and the balance at each of them. It declares `Bus_injection` as a sum with a frame and no body, which every component adds its injection to.

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

expressions:
  Bus_injection:
    dims: [scenario, snapshot, bus]
    description: >-
      what every component puts into a bus, less what it takes out of it;
      PyPSA writes each term into the balance, and a load on its right-hand
      side

constraints:
  Bus_nodal_balance:
    description: >-
      `Bus-nodal_balance` — what is generated at a bus, storage dispatch and
      stores included, less what the links take away, plus what arrives over
      them after losses and any delay at every port they deliver to, each
      process port drawing or delivering at its own rate and each passive branch
      carrying its flow, meets the load there, less half of every incident
      line's and transformer's loss — PyPSA dissipates a branch's loss half at
      either end. Each generator, storage unit, store and load term enters
      with its component's `sign` (`constraints.py:1428-1429`, `:1538`), and
      an inactive load not at all. A bus nothing is attached to has no row; PyPSA refuses one that
      carries load, and this file does not yet.
    dims: [scenario, snapshot, bus]
    expression: Bus_injection == 0
```

#### Sets

| Symbol | Meaning |
|---|---|
| $`\Xi`$ | index $`\xi`$ — `scenario` — the futures dispatch is chosen in, each with a weight |
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` — dispatch periods |
| $`\mathcal{N}`$ | index $`n`$ — `bus` — network nodes |

#### Definitions

| Symbol | Meaning |
|---|---|
| $`\mathit{Bus\_injection}`$ | `Bus_injection` over $`\Xi \times \mathcal{T} \times \mathcal{N}`$ — what every component puts into a bus, less what it takes out of it; PyPSA writes each term into the balance, and a load on its right-hand side |

#### Subject to

**`Bus_nodal_balance`**

```math
\mathit{Bus\_injection}_{\xi,t,n} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ n \in \mathcal{N}
```

#### Definitions

**`Bus_injection`**

```math
\mathit{Bus\_injection}_{\xi,t,n} = \cdots \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ n \in \mathcal{N}
```
<!-- gallery:end -->
