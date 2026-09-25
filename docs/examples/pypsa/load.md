<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Loads

One of the [24 fragments](index.md) of `examples/pypsa.yaml`: PyPSA's `Load`. It adds a term to `Bus_injection`.

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
  load:
    description: demands, each on one bus

relations:
  Load_bus:
    description: the bus a load sits on
    key: load
    values: bus

parameters:
  Load_p_set:
    description: demand
    dims: [scenario, snapshot, load]
  Load_sign:
    description: >-
      the sign a load's demand enters its bus's balance with — PyPSA's
      `sign`, `-1` unless given, `1` for a load that feeds its bus. PyPSA
      refuses one that differs by scenario (`consistency.py:1187`)
    dims: [load]
  Load_active:
    description: >-
      whether a load stands in the model — PyPSA's `active`. A load has no
      build year and no lifetime, so the flag holds in every snapshot. PyPSA
      refuses one that differs by scenario (`consistency.py:1195`)
    dims: [load]
    dtype: bool

given:
  expressions:
    Bus_injection: { dims: [scenario, snapshot, bus], term: Load_injection }

expressions:
  Load_demand:
    description: >-
      what a load draws from its bus's balance — its demand times its sign
      where it is active, nothing where it is not, since PyPSA drops an
      inactive load from the balance (`constraints.py:1537-1538`)
    dims: [scenario, snapshot, load]
    cases:
      active: { when: Load_active, expression: Load_sign * Load_p_set }
    otherwise: 0
  Load_injection: sum(Load_demand, by=Load_bus, over=load, into=bus)
```

#### Sets

| Symbol | Meaning |
|---|---|
| $`\Xi`$ | index $`\xi`$ — `scenario` — the futures dispatch is chosen in, each with a weight |
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` — dispatch periods |
| $`\mathcal{N}`$ | index $`n`$ — `bus` with $`\mathrm{Load\_bus}: \mathcal{D} \to \mathcal{N}`$ — network nodes |
| $`\mathcal{D}`$ | index $`d`$ — `load` with $`\mathrm{Load\_bus}: \mathcal{D} \to \mathcal{N}`$ — demands, each on one bus |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{load}`$ | `Load_p_set` over $`\Xi \times \mathcal{T} \times \mathcal{D}`$ — demand |
| $`\mathrm{sgn}^{\mathrm{load}}`$ | `Load_sign` over $`\mathcal{D}`$ — the sign a load's demand enters its bus's balance with — PyPSA's `sign`, `-1` unless given, `1` for a load that feeds its bus. PyPSA refuses one that differs by scenario (`consistency.py:1187`) |
| $`\mathrm{on}^{\mathrm{load}}`$ | `Load_active` over $`\mathcal{D}`$ — whether a load stands in the model — PyPSA's `active`. A load has no build year and no lifetime, so the flag holds in every snapshot. PyPSA refuses one that differs by scenario (`consistency.py:1195`) |

#### Given

| Symbol | Meaning |
|---|---|
| $`\mathit{Bus\_injection}`$ | `Bus_injection` over $`\Xi \times \mathcal{T} \times \mathcal{N}`$, an expression this file adds `Load_injection` to |

#### Definitions

| Symbol | Meaning |
|---|---|
| $`\check{\mathrm{load}}`$ | `Load_demand` over $`\Xi \times \mathcal{T} \times \mathcal{D}`$ — what a load draws from its bus's balance — its demand times its sign where it is active, nothing where it is not, since PyPSA drops an inactive load from the balance (`constraints.py:1537-1538`) |
| $`\mathrm{Load\_injection}`$ | `Load_injection` over $`\Xi \times \mathcal{T} \times \mathcal{N}`$ |

#### Definitions

**`Load_demand`**

```math
\check{\mathrm{load}}_{\xi,t,d} = \begin{cases} \mathrm{sgn}^{\mathrm{load}}_{d} \cdot \mathrm{load}_{\xi,t,d} & \text{if } \mathrm{on}^{\mathrm{load}}_{d} \\ 0 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ d \in \mathcal{D}
```

**`Load_injection`**

```math
\mathrm{Load\_injection}_{\xi,t,n} = \sum_{d \in \mathcal{D} \,:\, \mathrm{Load\_bus}(d) = n} \check{\mathrm{load}}_{\xi,t,d} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ n \in \mathcal{N}
```
<!-- gallery:end -->
