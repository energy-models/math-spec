<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# A spec in several files

In this lesson you build a dispatch spec out of files that each hold one part
of it, merge them into one spec, and then add a component without changing the
other files. Do [your first spec](first-spec.md) first.

## The network

Make a file `network.yaml`. It balances every bus, and it reads the injection
at a bus under [`given:`](reference/language/declarations.md#given) rather
than defining it. `additive: true` says that other files add terms to it:

```yaml title="network.yaml"
description: Every bus is balanced in every snapshot.

dimensions:
  snapshot: { dtype: int, description: dispatch periods }
  bus: { description: network nodes }

given:
  expressions:
    injection:
      dims: [snapshot, bus]
      additive: true
      description: what the components put into a bus, less what they take out

constraints:
  balance:
    dims: [snapshot, bus]
    expression: injection == 0
```

Check the file:

```bash
python -m mathspec check network.yaml
```

The check accepts it, and notes that no file has added a term yet:

```text
expression 'injection' is a sum other files add terms to, and this file adds none: merge() sums the term every fragment declares under the name. Until one does, the program reads it and does not build it.
```

## The generators

Make a file `generators.yaml`. Its term of the injection is an ordinary named
expression under the same name:

```yaml title="generators.yaml"
description: A generator fleet, each unit on one bus.

dimensions:
  snapshot: { dtype: int, description: dispatch periods }
  bus: { description: network nodes }
  generator: { description: generating units }

relations:
  gen_bus: { key: generator, values: bus, description: the bus a generator sits on }

parameters:
  capacity: { dims: [generator], description: installed capacity }
  cost: { dims: [generator], description: marginal cost }

variables:
  dispatch:
    description: output of a generator in a snapshot
    dims: [snapshot, generator]
    bounds: { lower: 0, upper: capacity }

expressions:
  injection: sum(dispatch, by=gen_bus, over=generator, into=bus)

objective:
  sense: minimize
  expression: sum(dispatch * cost)
```

Check the file. The check prints nothing and exits with status 0:

```bash
python -m mathspec check generators.yaml
```

## The loads

Make a file `loads.yaml`. Its term takes the demand out of the bus:

```yaml title="loads.yaml"
description: The demand at every bus.

dimensions:
  snapshot: { dtype: int, description: dispatch periods }
  bus: { description: network nodes }

parameters:
  demand: { dims: [snapshot, bus], description: demand to be met }

expressions:
  injection: -demand
```

Check the file. The check prints nothing and exits with status 0:

```bash
python -m mathspec check loads.yaml
```

## Merge the files

Merge the three files in Python. Each name is what an error calls that file:

```python
import mathspec as ms

spec = ms.merge({'network': 'network.yaml', 'generators': 'generators.yaml', 'loads': 'loads.yaml'})
print(spec.expressions['injection'].expression)
```

The injection is the sum of the two terms, in the order of the file names:

```text
(sum(dispatch, by=gen_bus, over=generator, into=bus)) + (-demand)
```

Print the math of the merged spec:

```python
print(ms.to_markdown(spec, legend=False))
```

!!! example "Rendered output"

    #### Objective

    ```math
    \min \sum_{t \in \mathcal{T},\ g \in \mathcal{G}} \mathit{dispatch}_{t,g} \cdot \mathrm{cost}_{g}
    ```

    #### Subject to

    **`balance`**

    ```math
    \mathit{injection}_{t,b} = 0 \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B}
    ```

    #### Definitions

    **`injection`**

    ```math
    \mathit{injection}_{t,b} = \sum_{g \in \mathcal{G} \,:\, \mathrm{gen\_bus}(g) = b} \mathit{dispatch}_{t,g} - \mathrm{demand}_{t,b} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B}
    ```

    #### Variable domains

    **`dispatch`**

    ```math
    0 \le \mathit{dispatch}_{t,g} \le \mathrm{capacity}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
    ```

## Add a component

Make a file `imports.yaml`. It adds a term to the injection and a term to the
objective:

```yaml title="imports.yaml"
description: Power bought from outside the network, at a price.

dimensions:
  snapshot: { dtype: int, description: dispatch periods }
  bus: { description: network nodes }

parameters:
  import_limit: { dims: [bus], description: most a bus can import }
  import_price: { dims: [snapshot], description: price of imported power }

variables:
  imported:
    description: power a bus imports in a snapshot
    dims: [snapshot, bus]
    bounds: { lower: 0, upper: import_limit }

expressions:
  injection: imported

objective:
  sense: minimize
  expression: sum(imported * import_price)
```

Merge the four files:

```python
spec = ms.merge(
    {'network': 'network.yaml', 'generators': 'generators.yaml', 'loads': 'loads.yaml', 'imports': 'imports.yaml'}
)
print(spec.expressions['injection'].expression)
print(spec.objective.expression)
```

The injection has a third term, and the objective sums the two objectives.
`network.yaml` did not change:

```text
(sum(dispatch, by=gen_bus, over=generator, into=bus)) + (imported) + (-demand)
(sum(dispatch * cost)) + (sum(imported * import_price))
```

## Read what another file declares

Make a file `emissions.yaml`. It caps what the fleet emits, and it reads
`dispatch` under `given:` rather than declaring it:

```yaml title="emissions.yaml"
description: A cap on what the fleet emits over the horizon.

dimensions:
  snapshot: { dtype: int, description: dispatch periods }
  generator: { description: generating units }

given:
  variables:
    dispatch: { dims: [snapshot, generator] }

parameters:
  emission_rate: { dims: [generator], description: emissions per unit of output }
  emission_cap: { dims: [], description: most the fleet may emit }

constraints:
  emission_limit:
    dims: []
    expression: sum(dispatch * emission_rate) <= emission_cap
```

Check the file:

```bash
python -m mathspec check emissions.yaml
```

The check accepts it, and notes the variable it reads:

```text
variable 'dispatch' is read here and declared elsewhere: the model this one is layered onto provides it. A consumer checks that it does, on the same frame, and refuses the program where it does not. A fragment is composed instead: merge() folds this declaration into the one a sibling introduces.
```

Merge all five files:

```python
spec = ms.merge(
    {
        'network': 'network.yaml',
        'generators': 'generators.yaml',
        'loads': 'loads.yaml',
        'imports': 'imports.yaml',
        'emissions': 'emissions.yaml',
    }
)
print(sorted(spec.constraints))
print(bool(spec.program.given))
```

The cap reads the generators' `dispatch`, and nothing is left for anything
outside the files to provide:

```text
['balance', 'emission_limit']
False
```

## Leave the network out

Merge the generators and the loads without the network:

```python
ms.merge({'generators': 'generators.yaml', 'loads': 'loads.yaml'})
```

`merge` refuses it. Without the file that marks `injection` as a sum, the two
terms are two definitions of one name:

```text
fragments 'generators' and 'loads' both declare the expression 'injection'. Two of the same kind of thing are two rows of a dimension rather than two fragments: merge the fragment once, and let the data carry both. Different math under one spelling is a rename: call one of them something else. If each fragment adds a term to one sum, mark the name `additive: true` on a `given: expressions:` entry in the file that reads it.
```

## Where to next

- [Compose a spec from several files](howto/compose.md) covers `merge` and
  `override`, which lays a patch over a spec.
- [`given`](reference/language/declarations.md#given) gives every rule a file
  that reads another file obeys.
- [A component library](examples/library/index.md) shows larger fragments
  beside the math they print.
