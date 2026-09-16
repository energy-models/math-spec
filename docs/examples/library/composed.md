<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# The composed model

What [the surface](surface.md), [generators](generator.md) and
[loads](load.md) make together:

```python
import math_spec as ms

model = ms.merge({'surface': 'surface.yaml', 'generator': 'generator.yaml', 'load': 'load.yaml'})
spec = ms.to_spec(model)
```

The file below is `spec.to_yaml()` — no fragment holds it, and nothing in the
repository commits it. `flow` is one declaration here: each template read it
under `given_variables`, and merging folded those into the surface's own.

The objective is the generator's, carried as it was written, because it is the
only fragment that priced anything. A second priced fragment would have its
term summed with this one.

<!-- gallery:begin -->
```yaml
version: 0
dimensions:
  snapshot:
    dtype: int
  port:
    dtype: str
  bus:
    dtype: str
  generator:
    dtype: str
  demand:
    dtype: str
relations:
  port_bus:
    key: port
    value: bus
  gen_port:
    key: generator
    value: port
  dem_port:
    key: demand
    value: port
parameters:
  gen_cost:
    dims:
    - generator
    dtype: float
    description: what one unit of output costs
  gen_p_max:
    dims:
    - generator
    dtype: float
    description: installed capacity
  dem_load:
    dims:
    - snapshot
    - demand
    dtype: float
    description: what a demand takes in a snapshot
variables:
  flow:
    dims:
    - snapshot
    - port
    domain: continuous
    absence: undefined
    description: what a port puts into its bus in a snapshot, negative for a withdrawal
  gen_p:
    dims:
    - snapshot
    - generator
    bounds:
      lower: 0.0
      upper: gen_p_max
    domain: continuous
    absence: undefined
    description: what a generator produces in a snapshot
constraints:
  balance:
    dims:
    - snapshot
    - bus
    expression: sum(flow, by=port_bus) == 0
    description: every bus clears in every snapshot
  gen_injects:
    dims:
    - snapshot
    - generator
    expression: at(flow, by=gen_port) == gen_p
    description: a generator's output is what its port injects
  dem_withdraws:
    dims:
    - snapshot
    - demand
    expression: at(flow, by=dem_port) == -dem_load
    description: a demand's port withdraws what the demand takes
objective:
  sense: minimize
  expression: sum(gen_p * gen_cost)
```

#### Sets

| Symbol | Meaning |
|---|---|
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` |
| $`\mathcal{P}`$ | index $`p`$ — `port` with $`\mathrm{port\_bus}: \mathcal{P} \to \mathcal{B},\ \mathrm{gen\_port}: \mathcal{G} \to \mathcal{P},\ \mathrm{dem\_port}: \mathcal{D} \to \mathcal{P}`$ |
| $`\mathcal{B}`$ | index $`b`$ — `bus` with $`\mathrm{port\_bus}: \mathcal{P} \to \mathcal{B}`$ |
| $`\mathcal{G}`$ | index $`g`$ — `generator` with $`\mathrm{gen\_port}: \mathcal{G} \to \mathcal{P}`$ |
| $`\mathcal{D}`$ | index $`d`$ — `demand` with $`\mathrm{dem\_port}: \mathcal{D} \to \mathcal{P}`$ |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{gen\_cost}`$ | `gen_cost` over $`\mathcal{G}`$ — what one unit of output costs |
| $`\mathrm{gen\_p\_max}`$ | `gen_p_max` over $`\mathcal{G}`$ — installed capacity |
| $`\mathrm{dem\_load}`$ | `dem_load` over $`\mathcal{T} \times \mathcal{D}`$ — what a demand takes in a snapshot |

#### Variables

| Symbol | Meaning |
|---|---|
| $`\mathit{flow}`$ | `flow` over $`\mathcal{T} \times \mathcal{P}`$ — what a port puts into its bus in a snapshot, negative for a withdrawal |
| $`\mathit{gen\_p}`$ | `gen_p` over $`\mathcal{T} \times \mathcal{G}`$ — what a generator produces in a snapshot |

Upright is what the model is given — a parameter such as $`\mathrm{gen\_cost}`$, a coordinate map, a label — and italic is what the solver chooses, such as $`\mathit{flow}`$. An index is italic too, being what a quantifier chooses, and a set is script.

#### Objective

```math
\min \sum_{t \in \mathcal{T},\ g \in \mathcal{G}} \mathit{gen\_p}_{t,g} \cdot \mathrm{gen\_cost}_{g}
```

#### Subject to

**`balance`**

```math
\sum_{p \in \mathcal{P} \,:\, \mathrm{port\_bus}(p) = b} \mathit{flow}_{t,p} = 0 \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B}
```

**`gen_injects`**

```math
\mathit{flow}_{t,\mathrm{gen\_port}(g)} = \mathit{gen\_p}_{t,g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

**`dem_withdraws`**

```math
\mathit{flow}_{t,\mathrm{dem\_port}(d)} = -\mathrm{dem\_load}_{t,d} \qquad \forall\, t \in \mathcal{T},\ d \in \mathcal{D}
```

#### Variable domains

**`flow`**

```math
\mathit{flow}_{t,p} \in \mathbb{R} \qquad \forall\, t \in \mathcal{T},\ p \in \mathcal{P}
```

**`gen_p`**

```math
0 \le \mathit{gen\_p}_{t,g} \le \mathrm{gen\_p\_max}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```
<!-- gallery:end -->
