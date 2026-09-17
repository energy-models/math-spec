<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Compose a model from several files

Build one model out of files that each say part of it. `merge` composes
**peers** — the files of a component library, where a name two of them declare
is a collision. `override` lays **patches** over a base — what a
framework ships and a project extends. Both hand back one mapping, which
[`to_spec`](../reference/language/reading.md) loads like any file, and they
compose: `override(merge({…}), {…})`.

## A library of components

1. **Write the coupling surface as a model.** One flow per port, one balance
   per bus. Nothing in it knows which components exist.

   ```yaml title="surface.yaml"
   dimensions:
     snapshot: { dtype: datetime }
     bus: { dtype: str }
     port: { dtype: str }
   relations:
     Port_bus: { key: port, value: bus }
   variables:
     Port_p:
       dims: [snapshot, port]
       description: what a port puts into its bus in a snapshot
   constraints:
     Bus_nodal_balance:
       dims: [snapshot, bus]
       expression: sum(Port_p, by=Port_bus) == 0
   ```

2. **Write each component file against that surface.** It declares its own
   entities, its own math, and one relation into `port`. It names `Port_p`
   under
   [`given_variables`](../reference/language/declarations.md#given_variables),
   because the surface introduces that column and this file only reads it.

   ```yaml title="generator.yaml"
   dimensions:
     snapshot: { dtype: datetime }
     port: { dtype: str }
     generator: { dtype: str }
   relations:
     Generator_port: { key: generator, value: port }
   given_variables:
     Port_p: { dims: [snapshot, port] }
   parameters:
     Generator_p_nom: { dims: [generator] }
     Generator_marginal_cost: { dims: [generator] }
   variables:
     Generator_p: { dims: [snapshot, generator], bounds: { lower: 0, upper: Generator_p_nom } }
   constraints:
     Generator_injection:
       dims: [snapshot, generator]
       expression: at(Port_p, by=Generator_port) == Generator_p
   objective:
     sense: minimize
     expression: sum(Generator_p * Generator_marginal_cost)
   ```

   The file loads on its own, and it prints as math on its own. Lowering it
   gives a program that names `Port_p` as a column to bind rather than build,
   which is what a layer over another model wants; a library merges instead.

3. **Merge the files you need.** Each fragment is given a name, and that name
   is what a refusal calls it.

   ```python
   import math_spec as ms

   model = ms.merge({'surface': 'surface.yaml', 'generator': 'generator.yaml', 'load': 'load.yaml'})
   spec = ms.to_spec(model)
   ```

   `merge` folds each given declaration into the one that introduces it, so the
   composed model declares `Port_p` once and carries no `given_variables`. It
   lowers and solves like any model.

4. **Add a component type without touching the balance.** A component file pins
   the flow at its own port rather than adding a term, so `Bus_nodal_balance`
   is written once and stays as it is however many files are merged. What grows
   is the data: which ports exist, and which bus each one sits on.

## A base and its patches

1. **Write the base as a model**, and each patch as the change it makes. A
   declaration a patch does not name is left as the base wrote it.

   ```yaml title="operate.yaml"
   variables:
     gen_p: { where: "gen_p_max > 0" }
   ```

2. **Lay the patches on the base.** The patches must write different fields, so
   the order they are given in cannot change the model.

   ```python
   model = ms.override('base.yaml', {'carbon': 'carbon.yaml', 'operate': 'operate.yaml'})
   ```

3. **Remove a declaration with `null`.** A patch that does not mention a
   declaration leaves it alone, so removal needs a marker of its own.

   ```yaml title="feasibility.yaml"
   constraints:
     emission_cap: null
   objective: null
   ```

   The marker is the declaration itself. Deeper down, `null` is a value the
   schema already takes: `gen_p: { where: null }` gives that variable no mask,
   and leaves the variable in place.

## From the shell

```bash
python -m math_spec compose surface.yaml generator.yaml load.yaml -o library.yaml
python -m math_spec compose base.yaml -p carbon.yaml -p operate.yaml -o composed.yaml
```

Several models are merged as peers. `-p` lays a patch over what they compose
to. The model goes to the file, and the account of how it got there goes to
stderr:

```text
merged 3 fragments
  added  parameters.emission_rate  (carbon)
 edited  variables.gen_p  (operate)
1 added, 1 edited
```

Without `-o` the model goes to stdout. Diff it against the base to read what
the patches did to the math.

## What a patch may say

| The entry                            | What happens                                               |
| ------------------------------------ | ---------------------------------------------------------- |
| some fields of a declaration         | those fields change, and the rest of the declaration stays |
| a whole declaration under a new name | it is added                                                |
| `null` under a declaration's name    | it is removed                                              |
| a dimension or a relation            | it is added, or restated exactly as the base declares it   |
| `version`, `description`             | the patch's value replaces the base's                      |

## A name two fragments declare

Fragments own their math, so a name two of them declare is refused, both named. Here two files each say what a generator fleet is:

```text
fragments 'gas' and 'coal' both declare the parameter 'Generator_p_nom'. Two of the same kind of thing are two rows of a dimension rather than two fragments: merge the fragment once, and let the data carry both. Different math under one spelling is a rename — call one of them something else.
```

## A column read one way and introduced another

What a fragment states about a column it reads has to agree with the file that
owns it:

```text
fragment 'generator' reads given variable 'Port_p' as {'dims': ['snapshot', 'generator']}, where 'surface' introduces it as {'dims': ['snapshot', 'port'], 'description': 'what a port puts into its bus in a snapshot'}. A given declaration is what the file expects of a column somebody else owns, so it says the same as the declaration it is folded into, or less.
```

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

## An axis the other file already declares

A fragment may add a dimension or a relation, and two fragments may declare one
the same way. Saying different things about one is refused, and so is changing
one under the expressions already written over it:

```text
patch 'relabelled' declares the dimension 'snapshot' as {'dtype': 'str'}, where its base declares {'dtype': 'int'}. A patch adjusts the math, not the axes the math is already written over: restate the declaration exactly, leave it out, or give the patch an axis of its own under a name of its own.
```

## A removal of something that is not there

A removal says what the base has, so a stale one is refused with the near miss:

```text
patch 'stale' removes the constraint 'power_balnce', which its base does not declare. A removal is a claim about what is there, so a stale one is a patch that no longer describes the model it lands on. Did you mean 'power_balance'?
```
