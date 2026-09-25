<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# A spec in several files

In this lesson you build a dispatch spec out of files that each hold one part
of it, merge them into one spec, and then add a component without changing the
other files. Do [your first spec](first-spec.md) first.

## The network

Make a file `network.yaml`. It balances every bus, and it declares the
injection at a bus as a sum with a frame and no body: what the components
put in is theirs to say, in
[a term](reference/language/declarations.md#a-term-a-file-adds) each.

```yaml title="network.yaml"
description: Every bus is balanced in every snapshot.

dimensions:
  snapshot: { dtype: int, description: dispatch periods }
  bus: { description: network nodes }

expressions:
  injection:
    dims: [snapshot, bus]
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

The check accepts it, and notes the sum with no body yet:

```text
expression 'injection' is a sum this file declares and other files add terms to: merge() writes its body from their terms. Until then, the program reads it and does not build it.
```

## The generators

Make a file `generators.yaml`. It says what the fleet puts into a bus as a
named expression, `generation`. It reads the injection too, and a
[`term:`](reference/language/declarations.md#a-term-a-file-adds) on the entry
names `generation` as what this file adds to it.

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
  generation:
    description: what the fleet puts into a bus
    expression: sum(dispatch, by=gen_bus, over=generator, into=bus)

given:
  expressions:
    injection:
      dims: [snapshot, bus]
      term: generation

objective:
  sense: minimize
  expression: sum(dispatch * cost)
```

Check the file:

```bash
python -m mathspec check generators.yaml
```

The check accepts it, and notes the term:

```text
expression 'injection' is read here and declared elsewhere, and this file adds a term to it: merge() sums the term with what the other files declare under the name. Until then, the program reads it and does not build it.
```

Print the math of the file on its own:

```python
import mathspec as ms

print(ms.to_markdown('generators.yaml', legend=False))
```

The term prints as its own definition, and the legend, left out here, says
what it adds to:

!!! example "Rendered output"

    A generator fleet, each unit on one bus.

    #### Objective

    ```math
    \min \sum_{t \in \mathcal{T},\ g \in \mathcal{G}} \mathit{dispatch}_{t,g} \cdot \mathrm{cost}_{g}
    ```

    #### Definitions

    **`generation`**

    ```math
    \mathit{generation}_{t,b} = \sum_{g \in \mathcal{G} \,:\, \mathrm{gen\_bus}(g) = b} \mathit{dispatch}_{t,g} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B}
    ```

    #### Variable domains

    **`dispatch`**

    ```math
    0 \le \mathit{dispatch}_{t,g} \le \mathrm{capacity}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
    ```

## The loads

Make a file `loads.yaml`. Its term, `consumption`, takes the demand out of the
bus:

```yaml title="loads.yaml"
description: The demand at every bus.

dimensions:
  snapshot: { dtype: int, description: dispatch periods }
  bus: { description: network nodes }

parameters:
  demand: { dims: [snapshot, bus], description: demand to be met }

expressions:
  consumption:
    description: what the loads take out of a bus
    expression: -demand

given:
  expressions:
    injection:
      dims: [snapshot, bus]
      term: consumption
```

Check the file:

```bash
python -m mathspec check loads.yaml
```

The check accepts it, with the same note:

```text
expression 'injection' is read here and declared elsewhere, and this file adds a term to it: merge() sums the term with what the other files declare under the name. Until then, the program reads it and does not build it.
```

## Merge the files

Merge the three files in Python. Each name is what an error calls that file:

```python
spec = ms.merge({'network': 'network.yaml', 'generators': 'generators.yaml', 'loads': 'loads.yaml'})
print(spec.expressions['injection'].expression)
```

The injection is the sum of the two terms by name, in the order of the file
names. Each term stays a named expression of the merged spec:

```text
generation + consumption
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
    \mathit{injection}_{t,b} = \mathit{generation}_{t,b} + \mathrm{consumption}_{t,b} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B}
    ```

    **`generation`**

    ```math
    \mathit{generation}_{t,b} = \sum_{g \in \mathcal{G} \,:\, \mathrm{gen\_bus}(g) = b} \mathit{dispatch}_{t,g} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B}
    ```

    **`consumption`**

    ```math
    \mathrm{consumption}_{t,b} = -\mathrm{demand}_{t,b} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B}
    ```

    #### Variable domains

    **`dispatch`**

    ```math
    0 \le \mathit{dispatch}_{t,g} \le \mathrm{capacity}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
    ```

## Add a component

Make a file `imports.yaml`. It adds a term, `purchase`, to the injection and a
term to the objective:

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
  purchase:
    description: what the imports put into a bus
    expression: imported

given:
  expressions:
    injection:
      dims: [snapshot, bus]
      term: purchase

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
generation + purchase + consumption
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

`merge` refuses it. A term adds to a name another file declares, and without
the network no file declares `injection`:

```text
fragments 'generators' and 'loads' add a term to 'injection', which no fragment declares. A term adds to a name another file declares under 'expressions:': declare it there, with a `dims:` and no body where the files add every term, or fix the spelling.
```

## Where to next

- [Compose a spec from several files](howto/compose.md) covers `merge` and
  `override`, which lays a patch over a spec.
- [`given`](reference/language/declarations.md#given) gives every rule a file
  that reads another file obeys.
- [A component library](examples/library/index.md) shows larger fragments
  beside the math they print.
