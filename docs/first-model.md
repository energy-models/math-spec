<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Your first model

In this lesson you write a least-cost dispatch model one block at a time, check
it, and print it as math. You finish with the model on the
[home page](index.md) in a file of your own.

## Installation

Install math-spec as [installation](howto/installation.md) says. Then run the
command-line interface:

```bash
python -m math_spec --help
```

It prints its four commands:

```text
usage: python -m math_spec [-h] {check,latex,markdown,typst} ...

positional arguments:
  {check,latex,markdown,typst}
    check               load a model, and print what the language advises
    latex               render a model as latex
    markdown            render a model as markdown
    typst               render a model as typst

options:
  -h, --help            show this help message and exit
```

## Dimensions

Make a file `dispatch.yaml` with a description and two
[dimensions](reference/language/dimensions.md). A dimension is an axis the
model runs over. Here `snapshot` holds the dispatch periods and `generator`
holds the generating units.

```yaml title="dispatch.yaml"
description: Least-cost dispatch of a generator fleet against an hourly load.

dimensions:
  snapshot: { dtype: int, description: dispatch periods }
  generator: { description: generating units }
```

Check the file:

```bash
python -m math_spec check dispatch.yaml
```

The check accepts the file and prints two lines of advice. Nothing uses the
dimensions yet:

```text
dimension 'snapshot' is never used: nothing is indexed by it, nothing aggregates into it, and no relation has a column over it. Remove it — or keep it knowingly, if the declarations that use it are still to be written.
dimension 'generator' is never used: nothing is indexed by it, nothing aggregates into it, and no relation has a column over it. Remove it — or keep it knowingly, if the declarations that use it are still to be written.
```

## Parameters

Add three [parameters](reference/language/declarations.md#parameters). A
parameter is data the model expects. The file gives its name and its
dimensions, and no values.

```yaml title="dispatch.yaml" hl_lines="7-10"
description: Least-cost dispatch of a generator fleet against an hourly load.

dimensions:
  snapshot: { dtype: int, description: dispatch periods }
  generator: { description: generating units }

parameters:
  capacity: { dims: [generator], description: installed capacity }
  load: { dims: [snapshot], description: demand to be met }
  cost: { dims: [generator], description: marginal cost }
```

Print the file as Markdown:

```bash
python -m math_spec markdown dispatch.yaml
```

It prints Markdown: a table of sets and a table of parameters. Rendered, the
output reads:

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

## Variable

Add one [variable](reference/language/declarations.md#variables). A variable is
a decision the solver makes. The [`where:`](reference/language/absence.md) line
leaves out every generator with no capacity.

```yaml title="dispatch.yaml" hl_lines="12-17"
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
```

Print the file again. `--no-legend` leaves out the tables, so only the math
prints:

```bash
python -m math_spec markdown --no-legend dispatch.yaml
```

The variable prints as its bounds:

!!! example "Rendered output"

    Least-cost dispatch of a generator fleet against an hourly load.

    #### Variable domains

    **`dispatch`**

    ```math
    0 \le \mathit{dispatch}_{t,g} \le \mathrm{capacity}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{capacity}_{g} > 0
    ```

## Constraint

Add one [constraint](reference/language/declarations.md#constraints). A
constraint is a rule the variables obey. This one makes the generators meet the
load in every snapshot.

```yaml title="dispatch.yaml" hl_lines="19-22"
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
```

Print the math again:

```bash
python -m math_spec markdown --no-legend dispatch.yaml
```

The constraint prints above the bounds:

!!! example "Rendered output"

    Least-cost dispatch of a generator fleet against an hourly load.

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

## Objective

Add the [objective](reference/language/declarations.md#objective). The
objective is the one number the solver minimises.

```yaml title="dispatch.yaml" hl_lines="24-26"
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

The model is complete. Check it:

```bash
python -m math_spec check dispatch.yaml
```

The check prints nothing and exits with status 0. The language accepts the
model.

## An undeclared name

Change `load` to `loads` in the constraint:

```yaml title="dispatch.yaml" hl_lines="22"
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
    expression: sum(dispatch, over=generator) == loads

objective:
  sense: minimize
  expression: sum(dispatch * cost)
```

Check the file:

```bash
python -m math_spec check dispatch.yaml
```

The check refuses the file. It prints this message and exits with status 1:

```text
Constraint 'power_balance': 'loads' not found.
  Variables: ['dispatch']
  Parameters: ['capacity', 'cost', 'load']
Check for typos, or ensure 'loads' is declared.
```

Change `loads` back to `load`. The check prints nothing again.

## The math

Print the whole model:

```bash
python -m math_spec markdown dispatch.yaml
```

It prints the description, the tables, the objective, the constraint and the
bounds:

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
- [The glossary](reference/glossary.md) defines each word the pages use in a
  fixed sense.
- [Examples](examples/index.md) shows larger models beside the math they print.
- [Print a model as math](howto/print.md) prints LaTeX and Typst, and gives
  each name its own symbol.
- [Check a model without data](howto/check.md) runs the check over every model
  in CI.
