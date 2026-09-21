<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# See what a curve or a set expands to

A [`piecewise:`](../reference/language/piecewise.md) block and a `sos:` block
each stand for plain variables and constraints. Read those rows to review a
formulation, to teach one, or to hand the model to an engine that has no
concept of a set.

The model below states one of each. A `piecewise:` block ties two variables to
a curve through the breakpoints. A `sos:` block says that at most one member of
a family is nonzero.

```yaml
description: one plant whose fuel use follows a curve, and whose output picks one mode

dimensions:
  snapshot: { dtype: int }
  bp: { dtype: int }
  mode: { dtype: int }

parameters:
  demand: { dims: [snapshot] }
  bp_out: { dims: [bp] }
  bp_fuel: { dims: [bp] }

variables:
  output:
    dims: [snapshot]
    bounds: { lower: 0, upper: 100 }
  fuel:
    dims: [snapshot]
    bounds: { lower: 0 }
  level:
    dims: [snapshot, mode]
    bounds: { lower: 0, upper: 1 }

piecewise:
  fuel_curve:
    over: bp
    method: sos2
    links:
      - [output, bp_out]
      - [fuel, bp_fuel]

sos:
  mode_pick:
    variable: level
    over: mode
    type: 1

constraints:
  meet:
    dims: [snapshot]
    expression: output >= demand

objective:
  sense: minimize
  expression: sum(fuel, over=snapshot)
```

## 1. Write the formulation out

`expand()` returns the same math with its formulations stated as rows. The
command line prints the result instead of returning it.

=== "Python"

    ```python
    from math_spec import to_spec

    spec = to_spec('plant.yaml')
    written_out = spec.expand()
    ```

=== "Command line"

    ```bash
    python -m math_spec markdown plant.yaml --expand
    ```

## 2. Read the names it added

The expansion declares what the two blocks stood for, and the blocks
themselves are gone:

```python
sorted(spec.variables)  # ['fuel', 'level', 'output']
sorted(written_out.variables)
# ['fuel', 'fuel_curve_lam', 'fuel_curve_seg', 'level', 'mode_pick_seg', 'output']

sorted(written_out.constraints)
# ['fuel_curve_adjacency', 'fuel_curve_convexity', 'fuel_curve_link0',
#  'fuel_curve_link1', 'fuel_curve_pick', 'meet', 'mode_pick_nonzero',
#  'mode_pick_pick']

written_out.piecewise  # {}
written_out.sos  # {}
```

Every emitted name starts with the block that emitted it, so `fuel_curve_lam`
is the curve's weights and `mode_pick_seg` is the set's binaries. A file that
already declares one of these names is refused, which keeps the two apart.

## 3. Read the rows as math

Both readings print from the same file. The first states the construct, the
second states the rows it stands for.

=== "As the file states it"

    The curve is one line, and the set is a membership beside the variable it
    runs along:

    ```math
    \left( \mathit{output}_{t},\ \mathit{fuel}_{t} \right) \in \mathrm{pwl}_{b \in \mathcal{B}}(\mathrm{bp\_out}_{b},\ \mathrm{bp\_fuel}_{b}) \qquad \forall\, t \in \mathcal{T}
    ```

    ```math
    \left( \mathit{level}_{t,m} \right)_{m \in \mathcal{M}} \in \mathrm{SOS}1 \qquad \forall\, t \in \mathcal{T}
    ```

=== "As the rows it states"

    The curve becomes weights on the breakpoints, one link row per tied
    variable, and the binaries that keep the weights adjacent:

    ```math
    \mathit{output}_{t} = \sum_{b \in \mathcal{B}} \mathit{fuel}^{\mathrm{curve,lam}}_{t,b} \cdot \mathrm{bp\_out}_{b} \qquad \forall\, t \in \mathcal{T}
    ```

    ```math
    \mathit{fuel}^{\mathrm{curve,lam}}_{t,b} \le \mathit{fuel}^{\mathrm{curve,seg}}_{t,b} + \mathit{fuel}^{\mathrm{curve,seg}}_{t,b \boxminus_{0} 1} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B}
    ```

    The set becomes one binary per member, a row that picks at most one, and a
    row that holds an unpicked member at zero:

    ```math
    \sum_{m \in \mathcal{M}} \mathit{mode\_pick\_seg}_{t,m} \le 1 \qquad \forall\, t \in \mathcal{T}
    ```

    ```math
    \mathit{level}_{t,m} \le \mathit{mode\_pick\_seg}_{t,m} \qquad \forall\, t \in \mathcal{T},\ m \in \mathcal{M}
    ```

Name the symbols as a paper would with a symbol table, which spells an emitted
name as readily as a declared one. [Print a model as math](print.md) has the
commands for a document that compiles.

## 4. Write out one kind at a time

Pass a kind to keep the other construct. This is how to read a curve without
the binaries underneath it:

```python
spec.expand('piecewise')  # curves become weights; the sets stay
spec.expand('sos')  # sets become binaries; the curves stay
```

A `method: sos2` curve states a set, so writing the curves out adds one:

```python
sorted(spec.sos)  # ['mode_pick']
sorted(spec.expand('piecewise').sos)  # ['fuel_curve', 'mode_pick']
```

`expand()` with no argument writes the curves out first for that reason, and a
set never states a curve.

## Two things to know

**An expansion that derived parameters does not round-trip to YAML.** A curve
under a `points:` mask emits parameters filled from its own breakpoints. No
file can state those, so `to_yaml()` on that expansion is refused and names
`typeset()` instead.

**A method states what it assumes of the data.** A `method: lp` or
`method: convex` curve is exact only for breakpoints of the right shape. The
expansion writes those conditions into
[`assumptions:`](../reference/language/assumptions.md) beside the rows. The
`method: sos2` curve above assumes nothing, because it takes a curve of any
shape.

What `expand()` accepts, and what each `method:` emits, is under
[piecewise curves and SOS](../reference/language/piecewise.md#writing-a-formulation-out).
