<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Loads

PyPSA's `Load`, and the fragment that shows what a file may leave out. It
declares no variable and no objective. `Load_p_set` is data, and the only thing
the file says is what the load's port withdraws.

The minus sign is the whole of its relation to the sign convention. A
withdrawal is a negative injection.

<!-- gallery:begin -->
```yaml
description: PyPSA's `Load`, wired to a port rather than straight to a bus. What it takes is data, so it decides nothing.
dimensions:
  snapshot: { dtype: datetime, description: dispatch periods }
  port: { dtype: str, description: "the connections components make, one label per connection" }
  load: { dtype: str, description: "demands, each on one port" }
relations:
  Load_port: { key: load, values: port }
given:
  variables:
    Port_p:
      dims: [snapshot, port]
      description: the surface introduces this flow, and this file pins it at its own ports
parameters:
  Load_p_set: { dims: [snapshot, load], description: "`Load-p_set` — what a load takes in a snapshot" }
constraints:
  Load_withdrawal:
    description: >-
      what a load takes is what its port withdraws. No PyPSA row stands for
      this: PyPSA writes the load into the balance instead
    dims: [snapshot, load]
    expression: at(Port_p, by=Load_port, over=port, into=load) == -Load_p_set
```

PyPSA's `Load`, wired to a port rather than straight to a bus. What it takes is data, so it decides nothing.

#### Sets

| Symbol | Meaning |
|---|---|
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` — dispatch periods |
| $`\mathcal{J}`$ | index $`j`$ — `port` with $`\mathrm{Load\_port}: \mathcal{D} \to \mathcal{J}`$ — the connections components make, one label per connection |
| $`\mathcal{D}`$ | index $`d`$ — `load` with $`\mathrm{Load\_port}: \mathcal{D} \to \mathcal{J}`$ — demands, each on one port |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{load}`$ | `Load_p_set` over $`\mathcal{T} \times \mathcal{D}`$ — `Load-p_set` — what a load takes in a snapshot |

#### Given

| Symbol | Meaning |
|---|---|
| $`f`$ | `Port_p` over $`\mathcal{T} \times \mathcal{J}`$ — the surface introduces this flow, and this file pins it at its own ports |

#### Subject to

**`Load_withdrawal`**

```math
f_{t,\mathrm{Load\_port}(d)} = -\mathrm{load}_{t,d} \qquad \forall\, t \in \mathcal{T},\ d \in \mathcal{D}
```
<!-- gallery:end -->
