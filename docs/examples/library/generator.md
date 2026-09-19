<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Generators

PyPSA's `Generator`, as one fragment. It owns its dimension, its relation into
`port`, its parameters, its column and its cost. It reads `Port_p` from
[the surface](surface.md) under
[`given`](../../reference/language/declarations.md#given). `Generator_port`
stands where PyPSA writes `Generator_bus`.

The constraint is what makes the library composable.
`at(Port_p, by=Generator_port, over=port, into=generator)` pins the flow at
this component's own port rather than adding a term to the balance, so the
balance does not grow.

The file is cut to what a dispatch model needs. A fixed build, no availability
profile and no ramp limits are three declarations PyPSA carries and this file
does not. [The PyPSA rungs](../pypsa.md) state them in full.

The math below is what this file prints on its own, with `Port_p` under
*Given* in the legend. When it merges with the surface, `Port_p` is one
declaration again.

<!-- gallery:begin -->
```yaml
description: >-
  PyPSA's `Generator`, wired to a port rather than straight to a bus, and cut
  to what a dispatch model needs: a fixed build, no availability profile, no
  ramp limits.
dimensions:
  snapshot: { dtype: datetime, description: dispatch periods }
  port: { dtype: str, description: "the connections components make, one label per connection" }
  generator: { dtype: str, description: "generating units, each on one port" }
relations:
  Generator_port: { key: generator, values: port }
given:
  variables:
    Port_p:
      dims: [snapshot, port]
      description: the surface introduces this flow, and this file pins it at its own ports
parameters:
  Generator_p_nom: { dims: [generator], description: nominal power }
  Generator_marginal_cost: { dims: [generator], description: cost of one unit of output }
variables:
  Generator_p:
    dims: [snapshot, generator]
    bounds: { lower: 0, upper: Generator_p_nom }
    description: "`Generator-p` — what a generator produces in a snapshot"
constraints:
  Generator_injection:
    description: >-
      what a generator produces is what its port injects. No PyPSA row stands
      for this: PyPSA writes the generator into the balance instead
    dims: [snapshot, generator]
    expression: at(Port_p, by=Generator_port, over=port, into=generator) == Generator_p
objective:
  sense: minimize
  expression: sum(Generator_p * Generator_marginal_cost)
```

PyPSA's `Generator`, wired to a port rather than straight to a bus, and cut to what a dispatch model needs: a fixed build, no availability profile, no ramp limits.

#### Sets

| Symbol | Meaning |
|---|---|
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` — dispatch periods |
| $`\mathcal{J}`$ | index $`j`$ — `port` with $`\mathrm{Generator\_port}: \mathcal{G} \to \mathcal{J}`$ — the connections components make, one label per connection |
| $`\mathcal{G}`$ | index $`g`$ — `generator` with $`\mathrm{Generator\_port}: \mathcal{G} \to \mathcal{J}`$ — generating units, each on one port |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{p}^{\mathrm{nom}}`$ | `Generator_p_nom` over $`\mathcal{G}`$ — nominal power |
| $`\mathrm{c}`$ | `Generator_marginal_cost` over $`\mathcal{G}`$ — cost of one unit of output |

#### Variables

| Symbol | Meaning |
|---|---|
| $`p`$ | `Generator_p` over $`\mathcal{T} \times \mathcal{G}`$ — `Generator-p` — what a generator produces in a snapshot |

#### Given

| Symbol | Meaning |
|---|---|
| $`f`$ | `Port_p` over $`\mathcal{T} \times \mathcal{J}`$ — the surface introduces this flow, and this file pins it at its own ports |

#### Objective

```math
\min \sum_{t \in \mathcal{T},\ g \in \mathcal{G}} p_{t,g} \cdot \mathrm{c}_{g}
```

#### Subject to

**`Generator_injection`**

```math
f_{t,\mathrm{Generator\_port}(g)} = p_{t,g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Variable domains

**`Generator_p`**

```math
0 \le p_{t,g} \le \mathrm{p}^{\mathrm{nom}}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```
<!-- gallery:end -->
