<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Generators

One component template. It owns its dimension, its relation into `port`, its
parameters, its column and its cost, and it reads `flow` from
[the surface](surface.md) under
[`given_variables`](../../reference/language/declarations.md#given_variables).

The last line is what makes the library composable: `at(flow, by=gen_port)`
pins the flow at this component's own port rather than adding a term to the
balance, so the balance never grows.

This file loads and prints on its own, which is why the math below it is here.
What it cannot do is name a column nothing introduces: merged with the surface,
`flow` is one declaration again.

<!-- gallery:begin -->
```yaml
description: A fleet of generators, each wired to one port, priced by what it produces.
dimensions:
  snapshot: { dtype: int }
  port: { dtype: str }
  generator: { dtype: str }
relations:
  gen_port: { key: generator, value: port }
given_variables:
  flow:
    dims: [snapshot, port]
    description: the surface introduces this column, and this file only writes into it
parameters:
  gen_cost: { dims: [generator], description: what one unit of output costs }
  gen_p_max: { dims: [generator], description: installed capacity }
variables:
  gen_p:
    dims: [snapshot, generator]
    bounds: { lower: 0, upper: gen_p_max }
    description: what a generator produces in a snapshot
constraints:
  gen_injects:
    description: a generator's output is what its port injects
    dims: [snapshot, generator]
    expression: at(flow, by=gen_port) == gen_p
objective:
  sense: minimize
  expression: sum(gen_p * gen_cost)
```

A fleet of generators, each wired to one port, priced by what it produces.

#### Sets

| Symbol | Meaning |
|---|---|
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` |
| $`\mathcal{P}`$ | index $`p`$ — `port` with $`\mathrm{gen\_port}: \mathcal{G} \to \mathcal{P}`$ |
| $`\mathcal{G}`$ | index $`g`$ — `generator` with $`\mathrm{gen\_port}: \mathcal{G} \to \mathcal{P}`$ |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{gen\_cost}`$ | `gen_cost` over $`\mathcal{G}`$ — what one unit of output costs |
| $`\mathrm{gen\_p\_max}`$ | `gen_p_max` over $`\mathcal{G}`$ — installed capacity |

#### Variables

| Symbol | Meaning |
|---|---|
| $`\mathit{gen\_p}`$ | `gen_p` over $`\mathcal{T} \times \mathcal{G}`$ — what a generator produces in a snapshot |

#### Given

| Symbol | Meaning |
|---|---|
| $`\mathit{flow}`$ | `flow` over $`\mathcal{T} \times \mathcal{P}`$ — the surface introduces this column, and this file only writes into it |

Upright is what the model is given — a parameter such as $`\mathrm{gen\_cost}`$, a coordinate map, a label — and italic is what the solver chooses, such as $`\mathit{gen\_p}`$. An index is italic too, being what a quantifier chooses, and a set is script.

#### Objective

```math
\min \sum_{t \in \mathcal{T},\ g \in \mathcal{G}} \mathit{gen\_p}_{t,g} \cdot \mathrm{gen\_cost}_{g}
```

#### Subject to

**`gen_injects`**

```math
\mathit{flow}_{t,\mathrm{gen\_port}(g)} = \mathit{gen\_p}_{t,g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Variable domains

**`gen_p`**

```math
0 \le \mathit{gen\_p}_{t,g} \le \mathrm{gen\_p\_max}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```
<!-- gallery:end -->
