<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# A system composed from templates

Four files, none of them a model. `base.yaml` declares the coupling surface —
one `flow` per port, and one balance per bus — and the other three name `flow`
without declaring it, which is why each is a load error on its own and the
composition is not.

```python
import math_spec as ms

model = ms.merge(
    {
        'base': 'examples/composed/base.yaml',
        'generator': 'examples/composed/generator.yaml',
        'demand': 'examples/composed/demand.yaml',
        'storage': 'examples/composed/storage.yaml',
    },
    description='A power system composed from four templates',
)
```

**The balance does not grow when a component type is added.** A fourth
component adds its own declarations and its own cost, and
`sum(flow, by=port_bus) == 0` is the same row it was with three — which is the
whole reason each component pins its port's flow with
[`at`](../reference/language/operators.md) rather than owning a flow variable of
its own. Drop `storage.yaml` from the call above and every other line of the
composed model is unchanged.

**Topology is data.** No file here says which bus a generator sits on: `gen_port`
and `port_bus` are [lookups](../reference/language/dimensions.md), and wiring a
specific system is rows in those two tables. Structure is bounded by the four
component _types_; how many generators there are is a question only the data
answers.

**One name is one declaration.** Merging refuses a name two fragments both
declare, so the templates here are spelled apart — `gen_p`, `st_soc`,
`dem_load`. If two of these were the same kind of thing with different numbers,
they would be two _rows_ in one dimension rather than two fragments.

<!-- gallery:begin -->
#### `examples/composed/base.yaml`

```yaml
description: >-
  The coupling surface every component agrees on: one flow per port, and one
  balance per bus. Every other fragment names `flow` and declares none of it.
dimensions:
  snapshot: {dtype: int}
  bus: {dtype: str}
  port: {dtype: str}
lookups:
  port_bus: {over: port, into: bus}
variables:
  flow:
    description: what a port puts into its bus in a snapshot, negative for a withdrawal
    foreach: [snapshot, port]
constraints:
  balance:
    description: every bus clears
    foreach: [snapshot, bus]
    expression: sum(flow, by=port_bus) == 0
```

#### `examples/composed/generator.yaml`

```yaml
description: A fleet of generators, each on one port.
dimensions:
  snapshot: {dtype: int}
  port: {dtype: str}
  generator: {dtype: str}
lookups:
  gen_port: {over: generator, into: port}
parameters:
  gen_cost: {dims: [generator]}
  gen_p_max: {dims: [generator]}
variables:
  gen_p:
    foreach: [snapshot, generator]
    bounds: {lower: 0, upper: gen_p_max}
constraints:
  gen_injects:
    foreach: [snapshot, generator]
    expression: at(flow, by=gen_port) == gen_p
objective:
  sense: minimize
  expression: sum(gen_p * gen_cost)
```

#### `examples/composed/demand.yaml`

```yaml
description: Fixed demands, each on one port.
dimensions:
  snapshot: {dtype: int}
  port: {dtype: str}
  demand: {dtype: str}
lookups:
  dem_port: {over: demand, into: port}
parameters:
  dem_load: {dims: [snapshot, demand]}
constraints:
  dem_withdraws:
    foreach: [snapshot, demand]
    expression: at(flow, by=dem_port) == -dem_load
```

#### `examples/composed/storage.yaml`

```yaml
description: Stores, each on one port, charging and discharging against a state of charge.
dimensions:
  snapshot: {dtype: int}
  port: {dtype: str}
  store: {dtype: str}
lookups:
  st_port: {over: store, into: port}
parameters:
  st_capacity: {dims: [store]}
  st_holding: {dims: []}
variables:
  st_charge: {foreach: [snapshot, store], bounds: {lower: 0}}
  st_discharge: {foreach: [snapshot, store], bounds: {lower: 0}}
  st_soc: {foreach: [snapshot, store], bounds: {lower: 0, upper: st_capacity}}
constraints:
  st_injects:
    foreach: [snapshot, store]
    expression: at(flow, by=st_port) == st_discharge - st_charge
  st_soc_balance:
    foreach: [snapshot, store]
    expression: st_soc == shift(st_soc, over=snapshot, offset=1, edge=0) + st_charge - st_discharge
objective:
  sense: minimize
  expression: sum(st_soc) * st_holding
```

#### The one model they make

A power system composed from four templates

#### Sets

| Symbol | Meaning |
|---|---|
| $\mathcal{T}$ | index $t$ — `snapshot` |
| $\mathcal{B}$ | index $b$ — `bus` |
| $\mathcal{P}$ | index $p$ — `port` with $\mathrm{port\_bus}: \mathcal{P} \to \mathcal{B}$ |
| $\mathcal{G}$ | index $g$ — `generator` with $\mathrm{gen\_port}: \mathcal{G} \to \mathcal{P}$ |
| $\mathcal{D}$ | index $d$ — `demand` with $\mathrm{dem\_port}: \mathcal{D} \to \mathcal{P}$ |
| $\mathcal{S}$ | index $s$ — `store` with $\mathrm{st\_port}: \mathcal{S} \to \mathcal{P}$ |

#### Parameters

| Symbol | Meaning |
|---|---|
| $\mathrm{gen\_cost}$ | `gen_cost` over $\mathcal{G}$ |
| $\mathrm{gen\_p\_max}$ | `gen_p_max` over $\mathcal{G}$ |
| $\mathrm{dem\_load}$ | `dem_load` over $\mathcal{T} \times \mathcal{D}$ |
| $\mathrm{st\_capacity}$ | `st_capacity` over $\mathcal{S}$ |
| $\mathrm{st\_holding}$ | `st_holding` (scalar) |

#### Variables

| Symbol | Meaning |
|---|---|
| $\mathit{flow}$ | `flow` over $\mathcal{T} \times \mathcal{P}$ — what a port puts into its bus in a snapshot, negative for a withdrawal |
| $\mathit{gen\_p}$ | `gen_p` over $\mathcal{T} \times \mathcal{G}$ |
| $\mathit{st\_charge}$ | `st_charge` over $\mathcal{T} \times \mathcal{S}$ |
| $\mathit{st\_discharge}$ | `st_discharge` over $\mathcal{T} \times \mathcal{S}$ |
| $\mathit{st\_soc}$ | `st_soc` over $\mathcal{T} \times \mathcal{S}$ |

Upright is what the model is given — a parameter such as $\mathrm{gen\_cost}$, a coordinate map, a label — and italic is what the solver chooses, such as $\mathit{flow}$. An index is italic too, being what a quantifier chooses, and a set is script.

$t \boxminus_{v} k$ denotes translation with $v$ standing where index $t-k$ leaves the dimension (`shift(edge=v)`), so the row at that boundary is built and carries $v$ rather than being dropped.

#### Objective

$$\min \sum_{t \in \mathcal{T},\enspace g \in \mathcal{G}} \mathit{gen\_p}_{t,g} \cdot \mathrm{gen\_cost}_{g} + \left( \sum_{t \in \mathcal{T},\enspace s \in \mathcal{S}} \mathit{st\_soc}_{t,s} \right) \cdot \mathrm{st\_holding}$$

#### Subject to

**`balance`**

$$\sum_{p \in \mathcal{P} \thinspace:\thinspace \mathrm{port\_bus}(p) = b} \mathit{flow}_{t,p} = 0 \qquad \forall\thinspace t \in \mathcal{T},\enspace b \in \mathcal{B}$$

**`gen_injects`**

$$\mathit{flow}_{t,\mathrm{gen\_port}(g)} = \mathit{gen\_p}_{t,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G}$$

**`dem_withdraws`**

$$\mathit{flow}_{t,\mathrm{dem\_port}(d)} = -\mathrm{dem\_load}_{t,d} \qquad \forall\thinspace t \in \mathcal{T},\enspace d \in \mathcal{D}$$

**`st_injects`**

$$\mathit{flow}_{t,\mathrm{st\_port}(s)} = \mathit{st\_discharge}_{t,s} - \mathit{st\_charge}_{t,s} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S}$$

**`st_soc_balance`**

$$\mathit{st\_soc}_{t,s} = \mathit{st\_soc}_{t \boxminus_{0} 1,s} + \mathit{st\_charge}_{t,s} - \mathit{st\_discharge}_{t,s} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S}$$

#### Variable domains

**`flow`**

$$\mathit{flow}_{t,p} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace p \in \mathcal{P}$$

**`gen_p`**

$$0 \le \mathit{gen\_p}_{t,g} \le \mathrm{gen\_p\_max}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G}$$

**`st_charge`**

$$\mathit{st\_charge}_{t,s} \ge 0 \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S}$$

**`st_discharge`**

$$\mathit{st\_discharge}_{t,s} \ge 0 \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S}$$

**`st_soc`**

$$0 \le \mathit{st\_soc}_{t,s} \le \mathrm{st\_capacity}_{s} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S}$$
<!-- gallery:end -->
