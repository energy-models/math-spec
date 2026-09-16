<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# The coupling surface

The spine every other file in the library is written against. It declares one
`flow` per port, one balance per bus, and the relation that says which bus a
port sits on. Nothing in it knows which components exist, so it is the one file
that never changes when a component type is added.

A flow is positive where the port injects into its bus. Every component reads
that convention and none of them restates it.

<!-- gallery:begin -->
```yaml
description: >-
  The coupling surface every component in this library is written against: one
  flow per port, and one balance per bus. A flow is positive where the port
  injects into its bus. A bus carries one energy carrier, so the carrier is
  which bus a port is wired to rather than a dimension of its own.
dimensions:
  snapshot: { dtype: int }
  port: { dtype: str }
  bus: { dtype: str }
relations:
  port_bus: { key: port, value: bus }
variables:
  flow:
    dims: [snapshot, port]
    description: what a port puts into its bus in a snapshot, negative for a withdrawal
constraints:
  balance:
    description: every bus clears in every snapshot
    dims: [snapshot, bus]
    expression: sum(flow, by=port_bus) == 0
```

The coupling surface every component in this library is written against: one flow per port, and one balance per bus. A flow is positive where the port injects into its bus. A bus carries one energy carrier, so the carrier is which bus a port is wired to rather than a dimension of its own.

#### Sets

| Symbol | Meaning |
|---|---|
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` |
| $`\mathcal{P}`$ | index $`p`$ — `port` with $`\mathrm{port\_bus}: \mathcal{P} \to \mathcal{B}`$ |
| $`\mathcal{B}`$ | index $`b`$ — `bus` with $`\mathrm{port\_bus}: \mathcal{P} \to \mathcal{B}`$ |

#### Variables

| Symbol | Meaning |
|---|---|
| $`\mathit{flow}`$ | `flow` over $`\mathcal{T} \times \mathcal{P}`$ — what a port puts into its bus in a snapshot, negative for a withdrawal |

#### Subject to

**`balance`**

```math
\sum_{p \in \mathcal{P} \,:\, \mathrm{port\_bus}(p) = b} \mathit{flow}_{t,p} = 0 \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B}
```

#### Variable domains

**`flow`**

```math
\mathit{flow}_{t,p} \in \mathbb{R} \qquad \forall\, t \in \mathcal{T},\ p \in \mathcal{P}
```
<!-- gallery:end -->
