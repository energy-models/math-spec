<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Compose a model from several files

Build one model out of files that each say part of it. `merge` composes
**fragments**: the files of a component library, each owning part of the math.
`override` lays **patches** over a **base**: the model a framework ships, and
the change a project makes to it. Each loads every fragment and the base with
[`to_spec`](../reference/language/errors.md#what-to_spec-checks) before it
composes them, and hands back the composed model loaded the same way. The two
compose as `override(merge({…}), {…})`.

## A library of components

1. **Write the coupling surface as a model.** One flow per port, one balance
   per bus. Nothing in it names a component class.

   ```yaml title="surface.yaml"
   dimensions:
     snapshot: { dtype: int }
     bus: { dtype: str }
     port: { dtype: str }
   relations:
     Port_bus: { key: port, values: bus }
   variables:
     Port_p:
       dims: [snapshot, port]
       description: what a port puts into its bus
   constraints:
     Bus_balance:
       dims: [snapshot, bus]
       expression: sum(Port_p, by=Port_bus, over=port, into=bus) == 0
   ```

2. **Write each component file against that surface.** It declares its own
   dimension, its own math, and one relation into `port`. It names `Port_p`
   under [`given`](../reference/language/declarations.md#given), because the
   surface introduces that column and this file only reads it.

   ```yaml title="generator.yaml"
   dimensions:
     snapshot: { dtype: int }
     port: { dtype: str }
     generator: { dtype: str }
   relations:
     Generator_port: { key: generator, values: port }
   given:
     variables:
       Port_p: { dims: [snapshot, port] }
   parameters:
     Generator_p_nom: { dims: [generator] }
     Generator_marginal_cost: { dims: [generator] }
   variables:
     Generator_p: { dims: [snapshot, generator], bounds: { lower: 0, upper: Generator_p_nom } }
   constraints:
     Generator_injection:
       dims: [snapshot, generator]
       expression: at(Port_p, by=Generator_port, over=port, into=generator) == Generator_p
   objective:
     sense: minimize
     expression: sum(Generator_p * Generator_marginal_cost)
   ```

   ```yaml title="load.yaml"
   dimensions:
     snapshot: { dtype: int }
     port: { dtype: str }
     load: { dtype: str }
   relations:
     Load_port: { key: load, values: port }
   given:
     variables:
       Port_p: { dims: [snapshot, port] }
   parameters:
     Load_p_set: { dims: [snapshot, load] }
   constraints:
     Load_withdrawal:
       dims: [snapshot, load]
       expression: at(Port_p, by=Load_port, over=port, into=load) == -Load_p_set
   ```

   Each file loads on its own and prints as math on its own.

3. **Merge the files you need.** Each fragment is given a name, and that name
   is what a refusal calls it. The order the fragments are given in does not
   change the model.

   ```python
   import math_spec as ms

   model = ms.merge({'surface': 'surface.yaml', 'generator': 'generator.yaml', 'load': 'load.yaml'})
   ```

   `merge` folds each given declaration into the declaration that introduces
   it, so `model` declares `Port_p` once and carries no `given:`. The objectives
   of the fragments are summed, each term in parentheses, in the order the
   fragment names sort in.

4. **Add a component class without touching the balance.** A component file
   pins the flow at its own port rather than adding a term to the balance, so
   `Bus_balance` is written once and stays as it is however many files are
   merged. What grows is the data: which ports exist, and which bus each one
   sits on.

## What a fragment may share

| The entry                                         | What happens                                                                             |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| a dimension or a relation                         | every fragment may declare it, and the ones that do say the same thing about it          |
| a `description` on a shared dimension or relation | it is prose rather than a claim, and the first fragment's wording is carried             |
| any other declaration                             | one fragment declares it, and a second is refused                                        |
| an entry under `given:`                           | it is checked against the fragment that introduces the name, then folded into it         |
| a given expression                                | the definition's body carries no dimension the reader's `dims` do not name               |
| a given entry no fragment introduces              | it stays under `given:` until a host model provides it                                   |
| `objective`                                       | the terms are summed in fragment-name order, each in parentheses, and the senses agree   |
| `version`                                         | every fragment is written against the same one                                           |
| `description` at the top of a fragment            | it is about the fragment and is not carried. Pass the composed model's as `description=` |

## A name two fragments declare

Fragments own their math, so a name two of them declare is refused, both
named. Here two files each say what a generator fleet is:

```text
fragments 'gas' and 'coal' both declare the parameter 'Generator_p_nom'. Two of the same kind of thing are two rows of a dimension rather than two fragments: merge the fragment once, and let the data carry both. Different math under one spelling is a rename: call one of them something else.
```

## A column read one way and introduced another

What a fragment states about a column it reads has to agree with the fragment
that introduces the column. The reader may say less, such as the frame with no
`domain`, and may not say something else. Here the generator reads `Port_p` as
binary:

```text
fragment 'generator' reads the given variable 'Port_p' as {'dims': ['snapshot', 'port'], 'domain': 'binary'}, where 'surface' introduces it as {'dims': ['snapshot', 'port'], 'domain': 'continuous', 'absence': 'undefined', 'description': 'what a port puts into its bus'}. A given declaration says the same as the declaration it is folded into, or less: restate the frame as the introducer declares it, or leave the field out.
```

Two fragments that both only read a column have to read it the same way, and
a difference is refused as it is for a dimension.

## A fragment that does not load on its own

A fragment is a whole model, so `merge` loads each one before it composes
them. A fragment `to_spec` refuses is refused under its own name, with the
refusal `to_spec` gives. A sibling cannot make it load. Here the generator
declares `Generator_p` and reads it under `given:` as well:

```text
fragment 'generator' does not load on its own. A fragment is a whole model: it declares what it builds, and reads what a sibling builds under 'given:'.
Given variable 'Generator_p' collides with the variable of the same name. Names share one flat namespace — rename one of them.
```

## A base and its patches

1. **Write the base as a model**, and each patch as the change it makes. A
   patch names only the fields it changes. A declaration a patch does not name
   stays as the base wrote it. The base loads on its own, and `override` loads
   it first. A patch is not a model, so it is laid over as written, and the
   patched model is loaded after.

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
   ```

   `model` declares `emission_cap` beside `power_balance`, and `dispatch` carries
   the mask `capacity > 0`.

3. **Remove a declaration with `null`.** A patch that does not mention a
   declaration leaves it alone, so removal needs a marker of its own.

   ```yaml title="feasibility.yaml"
   constraints:
     emission_cap: null
   objective: null
   ```

   A `null` makes what it names absent. On a declaration, the declaration is
   removed. On a field, the field takes its default and the declaration stays:
   `dispatch: { where: null }` gives that variable no mask, and
   `dispatch: { bounds: { upper: null } }` leaves it open above. Higher up,
   `constraints: null` is refused, because a section is not a declaration and
   nulling it removes nothing.

4. **Nest the calls where one patch refines another.** The second call lays
   its patch on the first call's result, so the order is on the page.

   ```python
   model = ms.override(ms.override('base.yaml', {'pathway': 'pathway.yaml'}), {'project': 'project.yaml'})
   ```

## What a patch may say

| The entry                            | What happens                                                                  |
| ------------------------------------ | ----------------------------------------------------------------------------- |
| some fields of a declaration         | those fields change, and the rest of the declaration stays                    |
| a whole declaration under a new name | it is added                                                                   |
| `null` under a declaration's name    | it is removed                                                                 |
| `null` on a field of a declaration   | the field takes its default, and the rest of the declaration stays            |
| `null` under a section's name        | it is refused                                                                 |
| a dimension or a relation            | it is added, or restated word for word as the base declares it                |
| an entry under one kind of `given:`  | it is edited, added or removed like any declaration, and the other kinds stay |
| `version`, `description`             | the patch's value replaces the base's                                         |

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

## A dimension redeclared

A patch may add a dimension or a relation, and may restate one the base
declares. The restatement is word for word: half a declaration is a second
reading of the same name. Changing one under the expressions already written
over it is refused, and so is removing one:

```text
patch 'relabelled' declares the dimension 'snapshot' as {'dtype': 'str'}, where its base declares {'dtype': 'int'}. A patch adjusts the math, not the coordinate space the math is already written over: restate the declaration word for word, leave it out, or give the patch a dimension of its own under a name of its own.
```

## A section set to `null`

A `null` removes the declaration it names. A section holds declarations rather
than being one, so nulling a section is refused rather than read as emptying
it:

```text
patch 'project' sets 'constraints' to null, which removes nothing: the removal marker names one declaration, and a section is not one. Remove the declarations one at a time, each under its own name, or leave the section out of the patch.
```

## A stale removal

A removal says what the base has, so a removal of a declaration the base does
not have is refused with the near miss:

```text
patch 'stale' removes the constraint 'power_balnce', which its base does not declare. A removal is a claim about what is there, so a stale one is a patch that no longer describes the model it lands on. Did you mean 'power_balance'?
```
