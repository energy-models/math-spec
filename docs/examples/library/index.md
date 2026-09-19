<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# A component library

Several files each say part of a model and compose into one. The surface
declares what the components share. Each component file declares its own math
against the surface, and [`merge`](../../howto/compose.md) makes the model.
Every file here loads and prints on its own, so the unit you pick from is the
unit you can read.

The names are PyPSA's, spelled `Component_attribute` as
[the PyPSA rungs](../pypsa.md) spell them, and the math prints in the symbols
those pages use. The model is cut to dispatch: one build, no availability
profile, no ramp limits.

## The layout

```text
examples/library/
  surface.yaml               one flow per port, one balance per bus
  generator.yaml             PyPSA's Generator
  load.yaml                  PyPSA's Load
  variants/
    commitment.yaml          a patch over the composition, not a peer
```

| Page                               | What it shows                                                  |
| ---------------------------------- | -------------------------------------------------------------- |
| [The coupling surface](surface.md) | the surface, and the sign convention                           |
| [Generators](generator.md)         | a file that reads `Port_p` and prices its output               |
| [Loads](load.md)                   | a file with no variable of its own                             |
| [The composed model](composed.md)  | what `merge` returns, and the math it prints with each variant |

## Rules of the layout

- **One file per thing you would pick on its own.** `merge` takes a whole
  fragment or none of it, so a model with no storage never mentions storage.
- **Every component file is written against one surface.**
- **Every name carries the component class it belongs to.** `merge` does not
  rename. `Generator_` and `Load_` keep the files apart, and the surface owns
  `Port_`, `port` and `bus`.
- **A fragment is what a system has. A patch is how a component is
  formulated.** A second kind of component is a peer, and `merge` composes it.
  A different formulation of one component edits declarations that already
  exist, and `override` lays it over the composition.

## The variant

`variants/commitment.yaml` makes the generator a committed unit. It adds a
binary, lifts the upper bound the capacity gave `Generator_p`, and caps output
with a constraint instead.

It edits `Generator_p`, which `generator.yaml` introduces, and names
`Generator_p_nom`, which `generator.yaml` declares. So it is not a model, and
`to_spec` refuses it on its own. It is laid over the composition:

```python
ms.override(ms.merge(fragments), {'commitment': 'variants/commitment.yaml'})
```

The [composed model](composed.md) carries the patch and the math it makes, in a
tab of its own. That tab is the only place the patch can be read as math.
