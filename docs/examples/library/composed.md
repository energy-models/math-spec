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

The file below is `model`, the mapping `merge` returns, written as YAML. No
fragment holds it, and nothing in the repository commits it. `Port_p` is one
declaration here. Each component fragment read it under `given:`, and merging
folded those readings into the surface's own declaration.

The objective is the generator's, carried as it was written, since no other
fragment prices anything. A second priced fragment would add its term to this
one, each term in parentheses.

The math under the file has a tab per formulation. **As composed** is the model
above. **With commitment** lays `variants/commitment.yaml` over it with
[`override`](../../howto/compose.md#a-base-and-its-patches), which makes the
generator a committed unit:

```python
spec = ms.to_spec(ms.override(model, {'commitment': 'variants/commitment.yaml'}))
```

A patch is refused on its own, since it edits declarations it does not
declare. So the model it lands on is the only place its math exists, and the
tab prints the patch beside that math.

<!-- gallery:begin -->
```yaml
dimensions:
  snapshot: {dtype: datetime, description: dispatch periods}
  bus: {dtype: str, description: network nodes}
  port: {dtype: str, description: 'the connections components make, one label per connection'}
  generator: {dtype: str, description: 'generating units, each on one port'}
  load: {dtype: str, description: 'demands, each on one port'}
relations:
  Port_bus: {key: port, values: bus}
  Generator_port: {key: generator, values: port}
  Load_port: {key: load, values: port}
parameters:
  Generator_p_nom:
    dims: [generator]
    description: nominal power
  Generator_marginal_cost:
    dims: [generator]
    description: cost of one unit of output
  Load_p_set:
    dims: [snapshot, load]
    description: '`Load-p_set` — what a load takes in a snapshot'
variables:
  Port_p:
    dims: [snapshot, port]
    description: what a port puts into its bus in a snapshot, negative for a withdrawal
  Generator_p:
    dims: [snapshot, generator]
    bounds: {lower: 0, upper: Generator_p_nom}
    description: '`Generator-p` — what a generator produces in a snapshot'
constraints:
  Bus_nodal_balance:
    description: '`Bus-nodal_balance` — what the ports on a bus put in nets to nothing'
    dims: [snapshot, bus]
    expression: sum(Port_p, by=Port_bus, over=port, into=bus) == 0
  Generator_injection:
    description: 'what a generator produces is what its port injects. No PyPSA row stands for this: PyPSA
      writes the generator into the balance instead'
    dims: [snapshot, generator]
    expression: at(Port_p, by=Generator_port, over=port, into=generator) == Generator_p
  Load_withdrawal:
    description: 'what a load takes is what its port withdraws. No PyPSA row stands for this: PyPSA writes
      the load into the balance instead'
    dims: [snapshot, load]
    expression: at(Port_p, by=Load_port, over=port, into=load) == -Load_p_set
objective: {sense: minimize, expression: sum(Generator_p * Generator_marginal_cost)}
```

=== "As composed"

    #### Sets

    | Symbol | Meaning |
    |---|---|
    | $`\mathcal{T}`$ | index $`t`$ — `snapshot` — dispatch periods |
    | $`\mathcal{N}`$ | index $`n`$ — `bus` with $`\mathrm{Port\_bus}: \mathcal{J} \to \mathcal{N}`$ — network nodes |
    | $`\mathcal{J}`$ | index $`j`$ — `port` with $`\mathrm{Port\_bus}: \mathcal{J} \to \mathcal{N},\ \mathrm{Generator\_port}: \mathcal{G} \to \mathcal{J},\ \mathrm{Load\_port}: \mathcal{D} \to \mathcal{J}`$ — the connections components make, one label per connection |
    | $`\mathcal{G}`$ | index $`g`$ — `generator` with $`\mathrm{Generator\_port}: \mathcal{G} \to \mathcal{J}`$ — generating units, each on one port |
    | $`\mathcal{D}`$ | index $`d`$ — `load` with $`\mathrm{Load\_port}: \mathcal{D} \to \mathcal{J}`$ — demands, each on one port |

    #### Parameters

    | Symbol | Meaning |
    |---|---|
    | $`\mathrm{p}^{\mathrm{nom}}`$ | `Generator_p_nom` over $`\mathcal{G}`$ — nominal power |
    | $`\mathrm{c}`$ | `Generator_marginal_cost` over $`\mathcal{G}`$ — cost of one unit of output |
    | $`\mathrm{load}`$ | `Load_p_set` over $`\mathcal{T} \times \mathcal{D}`$ — `Load-p_set` — what a load takes in a snapshot |

    #### Variables

    | Symbol | Meaning |
    |---|---|
    | $`f`$ | `Port_p` over $`\mathcal{T} \times \mathcal{J}`$ — what a port puts into its bus in a snapshot, negative for a withdrawal |
    | $`p`$ | `Generator_p` over $`\mathcal{T} \times \mathcal{G}`$ — `Generator-p` — what a generator produces in a snapshot |

    #### Objective

    ```math
    \min \sum_{t \in \mathcal{T},\ g \in \mathcal{G}} p_{t,g} \cdot \mathrm{c}_{g}
    ```

    #### Subject to

    **`Bus_nodal_balance`**

    ```math
    \sum_{j \in \mathcal{J} \,:\, \mathrm{Port\_bus}(j) = n} f_{t,j} = 0 \qquad \forall\, t \in \mathcal{T},\ n \in \mathcal{N}
    ```

    **`Generator_injection`**

    ```math
    f_{t,\mathrm{Generator\_port}(g)} = p_{t,g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
    ```

    **`Load_withdrawal`**

    ```math
    f_{t,\mathrm{Load\_port}(d)} = -\mathrm{load}_{t,d} \qquad \forall\, t \in \mathcal{T},\ d \in \mathcal{D}
    ```

    #### Variable domains

    **`Port_p`**

    ```math
    f_{t,j} \in \mathbb{R} \qquad \forall\, t \in \mathcal{T},\ j \in \mathcal{J}
    ```

    **`Generator_p`**

    ```math
    0 \le p_{t,g} \le \mathrm{p}^{\mathrm{nom}}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
    ```

=== "With commitment"

    ```yaml title="variants/commitment.yaml"
    parameters:
      Generator_p_min_pu: { dims: [generator], description: "least output, per unit of nominal power" }
    variables:
      Generator_status:
        dims: [snapshot, generator]
        domain: binary
        description: "`Generator-status` — whether a unit is on in a snapshot"
      Generator_p: { bounds: { upper: .inf } }
    constraints:
      Generator_com_p_upper:
        description: "`Generator-com-p-upper` — a committed unit outputs at most its nominal power; off, at most nothing"
        dims: [snapshot, generator]
        expression: Generator_p <= Generator_p_nom * Generator_status
      Generator_com_p_lower:
        description: "`Generator-com-p-lower` — a committed unit outputs at least its minimum; off, at least nothing"
        dims: [snapshot, generator]
        expression: Generator_p >= Generator_p_min_pu * Generator_p_nom * Generator_status
    ```

    #### Sets

    | Symbol | Meaning |
    |---|---|
    | $`\mathcal{T}`$ | index $`t`$ — `snapshot` — dispatch periods |
    | $`\mathcal{N}`$ | index $`n`$ — `bus` with $`\mathrm{Port\_bus}: \mathcal{J} \to \mathcal{N}`$ — network nodes |
    | $`\mathcal{J}`$ | index $`j`$ — `port` with $`\mathrm{Port\_bus}: \mathcal{J} \to \mathcal{N},\ \mathrm{Generator\_port}: \mathcal{G} \to \mathcal{J},\ \mathrm{Load\_port}: \mathcal{D} \to \mathcal{J}`$ — the connections components make, one label per connection |
    | $`\mathcal{G}`$ | index $`g`$ — `generator` with $`\mathrm{Generator\_port}: \mathcal{G} \to \mathcal{J}`$ — generating units, each on one port |
    | $`\mathcal{D}`$ | index $`d`$ — `load` with $`\mathrm{Load\_port}: \mathcal{D} \to \mathcal{J}`$ — demands, each on one port |

    #### Parameters

    | Symbol | Meaning |
    |---|---|
    | $`\mathrm{p}^{\mathrm{nom}}`$ | `Generator_p_nom` over $`\mathcal{G}`$ — nominal power |
    | $`\mathrm{c}`$ | `Generator_marginal_cost` over $`\mathcal{G}`$ — cost of one unit of output |
    | $`\mathrm{load}`$ | `Load_p_set` over $`\mathcal{T} \times \mathcal{D}`$ — `Load-p_set` — what a load takes in a snapshot |
    | $`\underline{\mathrm{p}}`$ | `Generator_p_min_pu` over $`\mathcal{G}`$ — least output, per unit of nominal power |

    #### Variables

    | Symbol | Meaning |
    |---|---|
    | $`f`$ | `Port_p` over $`\mathcal{T} \times \mathcal{J}`$ — what a port puts into its bus in a snapshot, negative for a withdrawal |
    | $`p`$ | `Generator_p` over $`\mathcal{T} \times \mathcal{G}`$ — `Generator-p` — what a generator produces in a snapshot |
    | $`u`$ | `Generator_status` over $`\mathcal{T} \times \mathcal{G}`$ — `Generator-status` — whether a unit is on in a snapshot |

    #### Objective

    ```math
    \min \sum_{t \in \mathcal{T},\ g \in \mathcal{G}} p_{t,g} \cdot \mathrm{c}_{g}
    ```

    #### Subject to

    **`Bus_nodal_balance`**

    ```math
    \sum_{j \in \mathcal{J} \,:\, \mathrm{Port\_bus}(j) = n} f_{t,j} = 0 \qquad \forall\, t \in \mathcal{T},\ n \in \mathcal{N}
    ```

    **`Generator_injection`**

    ```math
    f_{t,\mathrm{Generator\_port}(g)} = p_{t,g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
    ```

    **`Load_withdrawal`**

    ```math
    f_{t,\mathrm{Load\_port}(d)} = -\mathrm{load}_{t,d} \qquad \forall\, t \in \mathcal{T},\ d \in \mathcal{D}
    ```

    **`Generator_com_p_upper`**

    ```math
    p_{t,g} \le \mathrm{p}^{\mathrm{nom}}_{g} \cdot u_{t,g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
    ```

    **`Generator_com_p_lower`**

    ```math
    p_{t,g} \ge \underline{\mathrm{p}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot u_{t,g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
    ```

    #### Variable domains

    **`Port_p`**

    ```math
    f_{t,j} \in \mathbb{R} \qquad \forall\, t \in \mathcal{T},\ j \in \mathcal{J}
    ```

    **`Generator_p`**

    ```math
    p_{t,g} \ge 0 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
    ```

    **`Generator_status`**

    ```math
    u_{t,g} \in \{0, 1\} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
    ```
<!-- gallery:end -->
