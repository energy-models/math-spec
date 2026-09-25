<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Your first model

In this lesson you write a least-cost dispatch model one block at a time, check
it, and print it as math. [Install mathspec](howto/installation.md) first.

## Dimensions

Make a file `dispatch.yaml` with a description and two
[dimensions](reference/language/dimensions.md), the axes the model runs over:

```yaml title="dispatch.yaml"
description: Least-cost dispatch of a generator fleet against an hourly load.

dimensions:
  snapshot: { dtype: int, description: dispatch periods }
  generator: { description: generating units }
```

Check the file:

```bash
python -m mathspec check dispatch.yaml
```

The check accepts the file, and advises that nothing uses the dimensions yet:

```text
dimension 'snapshot' is never used: nothing is indexed by it, nothing aggregates into it, and no relation has a column over it. Remove it — or keep it knowingly, if the declarations that use it are still to be written.
dimension 'generator' is never used: nothing is indexed by it, nothing aggregates into it, and no relation has a column over it. Remove it — or keep it knowingly, if the declarations that use it are still to be written.
```

## Parameters and a variable

Add three [parameters](reference/language/declarations.md#parameters), the data
the model expects, and one [variable](reference/language/declarations.md#variables),
the decision the solver makes. The `where:` line leaves out every generator with
no capacity.

```yaml
parameters:
  capacity: { dims: [generator], description: installed capacity }
  load: { dims: [snapshot], description: demand to be met }
  cost: { dims: [generator], description: marginal cost }

variables:
  dispatch:
    description: output of a generator in a snapshot
    dims: [snapshot, generator]
    where: "capacity > 0"
    bounds: { lower: 0, upper: capacity }
```

Print the math. `--no-legend` leaves out the tables of symbols:

```bash
python -m mathspec markdown --no-legend dispatch.yaml
```

!!! example "Rendered output"

    Least-cost dispatch of a generator fleet against an hourly load.

    #### Variable domains

    **`dispatch`**

    ```math
    0 \le \mathit{dispatch}_{t,g} \le \mathrm{capacity}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{capacity}_{g} > 0
    ```

## Constraint and objective

Add one [constraint](reference/language/declarations.md#constraints), which
meets the load in every snapshot, and the
[objective](reference/language/declarations.md#objective):

```yaml
constraints:
  power_balance:
    dims: [snapshot]
    expression: sum(dispatch, over=generator) == load

objective:
  sense: minimize
  expression: sum(dispatch * cost)
```

Check the file again. The check prints nothing and exits with status 0.

??? note "The whole file"

    ```yaml title="dispatch.yaml"
    description: Least-cost dispatch of a generator fleet against an hourly load.

    dimensions:
      snapshot: { dtype: int, description: dispatch periods }
      generator: { description: generating units }

    parameters:
      capacity: { dims: [generator], description: installed capacity }
      load: { dims: [snapshot], description: demand to be met }
      cost: { dims: [generator], description: marginal cost }

    variables:
      dispatch:
        description: output of a generator in a snapshot
        dims: [snapshot, generator]
        where: "capacity > 0"
        bounds: { lower: 0, upper: capacity }

    constraints:
      power_balance:
        dims: [snapshot]
        expression: sum(dispatch, over=generator) == load

    objective:
      sense: minimize
      expression: sum(dispatch * cost)
    ```

## An undeclared name

Change `load` to `loads` in the constraint, and check the file. The check
refuses it and exits with status 1:

```text
Constraint 'power_balance': 'loads' not found.
  Variables: ['dispatch']
  Parameters: ['capacity', 'cost', 'load']
Check for typos, or ensure 'loads' is declared.
```

Change `loads` back to `load`.

## The math

Print the whole model:

```bash
python -m mathspec markdown dispatch.yaml
```

!!! example "Rendered output"

    Least-cost dispatch of a generator fleet against an hourly load.

    #### Sets

    | Symbol | Meaning |
    |---|---|
    | $`\mathcal{T}`$ | index $`t`$ — `snapshot` — dispatch periods |
    | $`\mathcal{G}`$ | index $`g`$ — `generator` — generating units |

    #### Parameters

    | Symbol | Meaning |
    |---|---|
    | $`\mathrm{capacity}`$ | `capacity` over $`\mathcal{G}`$ — installed capacity |
    | $`\mathrm{load}`$ | `load` over $`\mathcal{T}`$ — demand to be met |
    | $`\mathrm{cost}`$ | `cost` over $`\mathcal{G}`$ — marginal cost |

    #### Variables

    | Symbol | Meaning |
    |---|---|
    | $`\mathit{dispatch}`$ | `dispatch` over $`\mathcal{T} \times \mathcal{G}`$ — output of a generator in a snapshot |

    Upright is what the model is given — a parameter such as $`\mathrm{capacity}`$, a coordinate map, a label — and italic is what the solver chooses, such as $`\mathit{dispatch}`$. An index is italic too, being what a quantifier chooses, and a set is script.

    #### Objective

    ```math
    \min \sum_{t \in \mathcal{T},\ g \in \mathcal{G}} \mathit{dispatch}_{t,g} \cdot \mathrm{cost}_{g}
    ```

    #### Subject to

    **`power_balance`**

    ```math
    \sum_{g \in \mathcal{G}} \mathit{dispatch}_{t,g} = \mathrm{load}_{t} \qquad \forall\, t \in \mathcal{T}
    ```

    #### Variable domains

    **`dispatch`**

    ```math
    0 \le \mathit{dispatch}_{t,g} \le \mathrm{capacity}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{capacity}_{g} > 0
    ```

## Where to next

- [The language](reference/language/index.md) gives every rule a file obeys.
- [Examples](examples/index.md) shows larger models beside the math they print.
- [Print a model as math](howto/print.md) prints LaTeX and Typst.
