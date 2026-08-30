<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# File shape

A model file is a YAML mapping with **ten declaration keys**, plus `version`
and `description`:

| Key           |                                                                                                              |
| ------------- | ------------------------------------------------------------------------------------------------------------ |
| `dimensions`  | the axes ([dimensions](dimensions.md))                                                                       |
| `lookups`     | named maps out of a dimension ([lookups](dimensions.md#lookups))                                             |
| `parameters`  | the data the model expects ([declarations](declarations.md))                                                 |
| `variables`   | what the solver decides                                                                                      |
| `constraints` | the rules those decisions obey                                                                               |
| `objective`   | what is minimised or maximised                                                                               |
| `expressions` | named quantities, reusable and readable back after a solve ([expressions](expressions.md#named-expressions)) |
| `macros`      | parameterised templates ([macros](expressions.md#macros))                                                    |
| `piecewise`   | piecewise-linear curves ([piecewise](piecewise.md))                                                          |
| `sos`         | special-ordered sets ([sos](piecewise.md#sos))                                                               |

Any subset is accepted, `objective` included: a file with none is a
**feasibility problem**, and the answer is whether the constraints can be met
at all. It solves, its variables read back, and `result.objective` is the zero
the solver was handed.

## More than one file

A component library is a set of templates agreeing on a port and flow
convention, and wiring a system is rows in a connectivity table rather than
generated YAML. `merge` is what that needs of the language: the templates in,
**one model** out, validated and lowered exactly once.

```python
import math_spec as ms

model = ms.merge({'generator': 'generator.yaml', 'demand': 'demand.yaml'}, description='a fleet')
spec = ms.to_spec(model)  # one flat namespace, checked here and nowhere else
```

**A fragment is not a model.** It is merged before it is validated, so a
template may name what a sibling declares — a shared `bus`, the flow every
component writes into — without being loadable on its own. Nothing is resolved
or name-checked until the composition is whole, and then everything is, exactly
as for a file somebody typed.

Two kinds of declaration, and the split is what merging means:

- `dimensions` and `lookups` are the coordinate space, which templates share on
  purpose. Declared twice and agreeing they are one declaration; declared twice
  and disagreeing, the disagreement is the error.
- Everything else is the math, which a template owns, so a name two fragments
  both declare is a collision naming both — the composition being wrong rather
  than the file.

Objectives are summed, each term parenthesised, and a fragment running the
other way is refused rather than negated: a composed model has one sense and
nothing in the files says which.

**Names are not rewritten.** Until qualified names are in the language, a
library keeps its templates apart by naming them apart, and the collision error
is what holds it to that. Two of the same kind of thing — a battery and a
pumped hydro — are not two fragments to keep apart but two **rows** of one
dimension: merge the template once, and let the data carry both.

### A base and its patches

`merge` composes peers. `override` layers a base and the patches over it — what
a framework ships and a project extends:

```python
model = ms.override('base.yaml', {'pathway': 'pathway.yaml', 'project': 'project.yaml'})
```

The two obey opposite laws and neither is a mode of the other: a name two peers
declare is a collision, a name a patch declares is the point, and erroring on
one cannot also mean winning with it.

A patch says only what it changes. Declarations are laid over **field by
field**, so naming one field keeps the rest of the declaration under it:

```yaml
constraints:
  flow_out_max: { foreach: [node, tech, carrier, snapshot, investstep] }
```

**A declaration the patch sets to `null` is removed.** That is the one thing an
ordered list of files cannot say for itself — a declaration a patch does not
mention is left alone, so without a marker a deletion has no spelling:

```yaml
constraints:
  no_longer_relevant: null
variables:
  cap: null # a decision becomes a number the next block declares
parameters:
  cap: { dims: [generator] }
```

The marker is **positional** and reaches no deeper: `constraints: {ramp: null}`
removes the constraint, where `variables: {p: {where: null}}` sets that
variable's mask to none, which is a value the schema already takes. Removing a
declaration the base does not have is an error naming the near miss — a removal
is a claim about what is there, and a stale one is a patch that no longer
describes what it lands on.

**A patch is not a model**, for the same reason a fragment is not: it is read
before validation, so `null` never appears in a file anyone loads as a model
and the schema gains no key. What a reviewer reads is the composed result —
`Spec.to_yaml` on it is the artifact to diff against the base, which is the
answer to a verb designed to collide.

**Order is the instruction**, so this is the one verb here where the same
arguments given differently mean a different model. Both take and return what
the other does, so `override(merge({...}), patches)` is ordinary.

## `description`

What the file as a whole is: the same plain prose a declaration's
`description:` takes, and the first thing a
[typeset document](../typeset.md) prints. Optional, never parsed, default
`null`.

<!-- doctest: skip -->

```yaml
description: Least-cost dispatch of a generator fleet against an hourly load.
dimensions: ...
```

A `#` comment above the file says this too, and the parser throws it away. A
`description:` is the version a reader who never opens the YAML still gets.

## `version`

Which language surface the file is written against. Optional; absent means `0`:

<!-- doctest: skip -->

```yaml
version: 0
dimensions: ...
```

**`0` means unstable, and that is the promise being made.** The surface may
change in any release, and saying so in the file is more honest than silence.
`0` does not become `1` without a changelog entry naming what moved.

A version this release does not know is a load error, and nothing else — the
field gates no behaviour and never selects an alternative surface:

```text
model declares version 1, and math_spec 0.0.1a75 understands [0].
Upgrade math_spec, or write the version this file actually targets.
```

It is a **language** version, not a package one: it moves when the accepted
YAML surface moves, which most releases do not.

## The schema is closed

An unrecognised key — top level or inside any declaration — is a load error
naming the near miss:

```text
unknown key 'boundz' … Did you mean 'bounds'?
```

Ignoring it would let a typo change the model: a dropped `bounds:` leaves a
variable unbounded, a dropped `where:` leaves it unmasked.

## How the YAML is read

- **Booleans are YAML 1.2** (`true` / `false` only); everything else is read as
  1.1. Under 1.1 `on` / `off` / `yes` / `no` / `y` / `n` become booleans and a
  declaration named after a country code stops being one, so `no: {dtype: str}`
  is a dimension called `no` here.
- **Implicit timestamps** (`2024-01-01`) and sexagesimal integers (`12:30` →
  `750`) survive. Neither reaches a coordinate, which is data; a literal in a
  `where` string is where one is read as a label, and there the `dtype` of the
  name it is compared against catches it
  ([expressions](expressions.md#where-strings)).
- **A duplicate key is a load error** naming both lines.
- **`<<:` merge keys are honoured**, and a key the mapping declares itself
  overrides the merged value.
- The document must be a mapping.
