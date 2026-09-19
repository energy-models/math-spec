<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Compose a model from several files

Build one model out of files that each say part of it. `override` lays
**patches** over a **base**: the model a framework ships, and the change a
project makes to it. It hands back one mapping, which
[`to_spec`](../reference/language/errors.md#what-to_spec-checks) loads like any
file.

## A base and its patches

1. **Write the base as a model**, and each patch as the change it makes. A
   patch names only the fields it changes. A declaration a patch does not name
   stays as the base wrote it.

   ```yaml title="base.yaml"
   dimensions:
     snapshot: { dtype: int }
     generator: { dtype: str }
   parameters:
     capacity: { dims: [generator] }
     cost: { dims: [generator] }
     load: { dims: [snapshot] }
   variables:
     dispatch: { dims: [snapshot, generator], bounds: { lower: 0, upper: capacity } }
   constraints:
     power_balance:
       dims: [snapshot]
       expression: sum(dispatch, over=generator) == load
   objective:
     sense: minimize
     expression: sum(dispatch * cost)
   ```

   ```yaml title="operate.yaml"
   variables:
     dispatch: { where: "capacity > 0" }
   ```

   ```yaml title="carbon.yaml"
   parameters:
     emission_rate: { dims: [generator] }
   constraints:
     emission_cap:
       dims: []
       expression: sum(dispatch * emission_rate) <= 1000
   ```

2. **Lay the patches on the base.** Each patch is given a name, and that name
   is what a refusal calls it. The patches must write different fields, so the
   order they are given in cannot change the model.

   ```python
   import math_spec as ms

   model = ms.override('base.yaml', {'carbon': 'carbon.yaml', 'operate': 'operate.yaml'})
   spec = ms.to_spec(model)
   ```

   `spec` declares `emission_cap` beside `power_balance`, and `dispatch` carries
   the mask `capacity > 0`.

3. **Remove a declaration with `null`.** A patch that does not mention a
   declaration leaves it alone, so removal needs a marker of its own.

   ```yaml title="feasibility.yaml"
   constraints:
     emission_cap: null
   objective: null
   ```

   The marker is the declaration itself. Deeper down, `null` is a value the
   schema takes: `dispatch: { where: null }` gives that variable no mask, and
   leaves the variable in place.

4. **Nest the calls where one patch refines another.** The second call lays
   its patch on the first call's result, so the order is on the page.

   ```python
   model = ms.override(ms.override('base.yaml', {'pathway': 'pathway.yaml'}), {'project': 'project.yaml'})
   ```

## What a patch may say

| The entry                            | What happens                                               |
| ------------------------------------ | ---------------------------------------------------------- |
| some fields of a declaration         | those fields change, and the rest of the declaration stays |
| a whole declaration under a new name | it is added                                                |
| `null` under a declaration's name    | it is removed                                              |
| a dimension or a relation            | it is added, or restated exactly as the base declares it   |
| an entry under `given: variables:` or `given: constraints:` | it is edited, added or removed like any declaration, and the other kind stays |
| `version`, `description`             | the patch's value replaces the base's                      |

## A partial entry on a missing name

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

## An axis redeclared

A patch may add a dimension or a relation, and may restate one the base
declares. Changing one under the expressions already written over it is
refused:

```text
patch 'relabelled' declares the dimension 'snapshot' as {'dtype': 'str'}, where its base declares {'dtype': 'int'}. A patch adjusts the math, not the axes the math is already written over: restate the declaration exactly, leave it out, or give the patch an axis of its own under a name of its own.
```

## A stale removal

A removal says what the base has, so a removal of a declaration the base does
not have is refused with the near miss:

```text
patch 'stale' removes the constraint 'power_balnce', which its base does not declare. A removal is a claim about what is there, so a stale one is a patch that no longer describes the model it lands on. Did you mean 'power_balance'?
```
