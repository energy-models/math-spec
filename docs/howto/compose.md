<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Compose a model from a base and patches

Extend a model somebody else wrote, without copying it. The base is an ordinary
model file. A patch is a file that says only what it changes. `override` lays
the patches on the base and hands back one mapping, which
[`to_spec`](../reference/language/reading.md) loads like any file.

1. **Write the base as a model.** Nothing about it says it will be extended.

   ```yaml title="base.yaml"
   description: Least-cost dispatch of a generator fleet against an hourly load.
   dimensions:
     snapshot: { dtype: int }
     generator: { dtype: str }
   parameters:
     load: { dims: [snapshot] }
     cost: { dims: [generator] }
     capacity: { dims: [generator] }
   variables:
     dispatch:
       dims: [snapshot, generator]
       bounds: { lower: 0, upper: capacity }
   constraints:
     power_balance:
       dims: [snapshot]
       expression: sum(dispatch, over=generator) == load
   objective:
     sense: minimize
     expression: sum(dispatch * cost)
   ```

2. **Write each patch as the change it makes.** A declaration a patch does not
   name is left as the base wrote it. A patch is not a model on its own, so
   `to_spec` does not read one.

   ```yaml title="carbon.yaml"
   parameters:
     emission_rate: { dims: [generator] }
   constraints:
     emission_cap:
       dims: []
       expression: sum(dispatch * emission_rate) <= 100
   ```

   ```yaml title="operate.yaml"
   variables:
     dispatch: { where: "capacity > 0" }
   ```

   `operate.yaml` names one field. The dimensions and the bounds the base gave
   `dispatch` stay.

3. **Lay the patches on the base.** Each patch is given a name, and that name
   is what a refusal calls it.

   ```python
   import math_spec as ms

   model = ms.override('base.yaml', {'carbon': 'carbon.yaml', 'operate': 'operate.yaml'})
   spec = ms.to_spec(model)
   ```

   The patches must write different fields, so the order they are given in
   cannot change the model.

4. **Remove a declaration with `null`.** A patch that does not mention a
   declaration leaves it alone, so removal needs a marker of its own.

   ```yaml title="feasibility.yaml"
   constraints:
     emission_cap: null
   objective: null
   ```

   The marker is the declaration itself. Deeper down, `null` is a value the
   schema already takes: `dispatch: { where: null }` gives that variable no
   mask, and leaves the variable in place.

5. **Write the composed model out where the file is what you review.**
   `Spec.to_yaml()` is what every other page here diffs.

   ```python
   Path('composed.yaml').write_text(ms.to_spec(model).to_yaml())
   ```

## What a patch may say

| The entry                            | What happens                                               |
| ------------------------------------ | ---------------------------------------------------------- |
| some fields of a declaration         | those fields change, and the rest of the declaration stays |
| a whole declaration under a new name | it is added                                                |
| `null` under a declaration's name    | it is removed                                              |
| a dimension or a relation            | it is added, or restated exactly as the base declares it   |
| `version`, `description`             | the patch's value replaces the base's                      |

## A partial entry that lands on nothing

An entry naming some fields has to land on a declaration the base has. A
mistyped name is refused rather than read as a new declaration:

```text
patch 'project' edits the constraint 'power_balnce', which its base does not declare. Did you mean 'power_balance'? A patch creates a declaration only by writing it whole, and this one is not: a constraint needs `expression`.
```

To add a constraint, write the whole constraint. To change one, spell its name
as the base spells it.

## Two patches on one field

Two patches writing one field is refused, both named:

```text
patches 'pathway' and 'project': both write variables.dispatch.bounds.upper. Patches laid on one base are disjoint, so nothing decides which of two writes wins. Write the change in one patch, or lay one patch on the result of the other: override(override(base, {'pathway': …}), {'project': …}).
```

Where one patch is meant to refine another, nest the calls. The second call
lays its patch on the first call's result, so the order is on the page:

```python
model = ms.override(ms.override('base.yaml', {'pathway': 'pathway.yaml'}), {'project': 'project.yaml'})
```

## An axis the base already declares

A patch may add a dimension or a relation, and may restate one the base
declares. Changing one under the expressions already written over it is
refused:

```text
patch 'relabelled' declares the dimension 'snapshot' as {'dtype': 'str'}, where its base declares {'dtype': 'int'}. A patch adjusts the math, not the axes the math is already written over: restate the declaration exactly, leave it out, or give the patch an axis of its own under a name of its own.
```

## A removal of something that is not there

A removal says what the base has, so a stale one is refused with the near miss:

```text
patch 'stale' removes the constraint 'power_balnce', which its base does not declare. A removal is a claim about what is there, so a stale one is a patch that no longer describes the model it lands on. Did you mean 'power_balance'?
```
