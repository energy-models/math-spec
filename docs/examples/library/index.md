<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# A component library

A set of files that each say part of a model, and compose into one. The
surface declares what components share, each component template declares its
own math against it, and [`merge`](../../howto/compose.md) makes the model.
Every file here loads and prints on its own, so the unit you pick from is the
unit you can read.

## The layout

```text
examples/library/
  surface.yaml               one flow per port, one balance per bus
  generator.yaml             a component type
  load.yaml                  a component type
  variants/
    commitment.yaml          a patch over generator.yaml, not a peer
```

| Page                               | What it shows                                                  |
| ---------------------------------- | -------------------------------------------------------------- |
| [The coupling surface](surface.md) | the spine, and the sign convention                             |
| [Generators](generator.md)         | a template that reads `flow` and prices its output             |
| [Loads](load.md)                   | a template with no variable of its own                         |
| [The composed model](composed.md)  | what `merge` returns, and the math it prints with each variant |

## Four rules the layout follows

- **One file per thing you would pick on its own.** `merge` takes a whole
  fragment or none of it, so a model with no storage never mentions storage.
  Splitting further is possible and pointless: take the relation out of
  `generator.yaml` and neither half means anything.
- **One spine.** Two surface files would be two conventions, and nothing could
  say which one a template meant.
- **Every name carries its fragment's prefix.** `merge` does not rename, so
  `gen_`, `dem_` and the rest keep the templates apart. The surface owns the
  unprefixed shared names: `flow`, `port`, `bus`.
- **A fragment is what a system has. A patch is how a component is
  formulated.** A second kind of thing is a peer, composed with `merge`. A
  different formulation of one thing edits declarations that already exist, so
  it is laid over with `override`.

## A variant is a patch

`variants/commitment.yaml` makes the generator a committed unit. It adds a
binary, relaxes the bound the capacity used to give, and caps output with a
constraint instead.

It names `gen_p_max`, which `generator.yaml` declares, and edits `gen_p`, which
`generator.yaml` introduced. So it is not a model and does not load on its own.
It is laid over the composition:

```python
ms.override(ms.merge(fragments), {'commitment': 'variants/commitment.yaml'})
```

The [composed model](composed.md) carries the file and the math it makes, in a
tab of its own. A patch has no math until it lands on something, so that is the
only place it can be read as math.
