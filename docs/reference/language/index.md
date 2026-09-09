<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# The language

These pages are the exact rules: what a file may contain, what it means, and
what the loader refuses. A model is one YAML file. It declares the axes the
model runs over, the data it expects, the decisions the solver makes, and the
rules those decisions obey. Nothing else changes what a file means: not Python
state, and not the solver that takes it.

```yaml title="dispatch.yaml"
description: Least-cost dispatch of a generator fleet against an hourly load.

dimensions:
  snapshot: { dtype: int }
  generator: { dtype: str }

parameters:
  load: { dims: [snapshot] }
  cost: { dims: [generator] }
  p_max: { dims: [generator] }

variables:
  p:
    foreach: [snapshot, generator]
    where: "p_max > 0"
    bounds: { lower: 0, upper: p_max }

constraints:
  power_balance:
    foreach: [snapshot]
    expression: sum(p, over=generator) == load

objective:
  sense: minimize
  expression: sum(p * cost) # an objective is one number, so the sum is written
```

That file is a complete model.

## The file

A model file is one YAML mapping. It takes **ten declaration keys**, plus
`version` and `description`, and nothing else:

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

Any subset is accepted, `objective` included. A file with no objective is a
**feasibility problem**: the answer is whether the constraints can be met at
all. It solves, its variables read back, and `result.objective` is the zero the
solver was handed.

### `description`

What the file as a whole is: the same plain prose a declaration's
`description:` takes ([declarations](declarations.md)), and the first thing a
[typeset document](../typeset.md) prints. Optional, never parsed, default
`null`.

<!-- doctest: skip -->

```yaml
description: Least-cost dispatch of a generator fleet against an hourly load.
dimensions: ...
```

The parser discards a `#` comment; a `description:` is part of the loaded
model.

### `version`

Which language surface the file is written against. Optional; absent means `0`:

<!-- doctest: skip -->

```yaml
version: 0
dimensions: ...
```

**`0` means unstable**: the surface may change in any release. `0` becomes `1`
only with a changelog entry naming what moved.

A version this release does not know is a load error. The field gates no
behaviour and selects no alternative surface:

```text
model declares version 1, and math_spec 0.0.1a75 understands [0].
Upgrade math_spec, or write the version this file actually targets.
```

`version` is a **language** version, not a package one. It moves when the
accepted YAML surface moves, which most releases do not.

### The schema is closed

An unrecognised key, at the top level or inside any declaration, is a load
error naming the near miss:

```text
unknown key 'boundz' … Did you mean 'bounds'?
```

### How the YAML is read

- **Booleans are YAML 1.2**: `true` / `false` only. `on` / `off` / `yes` /
  `no` / `y` / `n` stay names, so `no: {dtype: str}` declares a dimension
  called `no`. Everything else is read as YAML 1.1.
- **Implicit timestamps** (`2024-01-01`) and sexagesimal integers (`12:30` →
  `750`) survive. Neither reaches a coordinate, which is data. A literal in a
  `where` string is checked against the `dtype` of the name it is compared
  with ([expressions](expressions.md#where-strings)).
- **A duplicate key is a load error** naming both lines.
- **`<<:` merge keys are honoured.** A key the mapping declares itself
  overrides the merged value.
- **The document must be a mapping.**

## Ten rules the language reduces to

**Nothing is guessed.** Where a file does not determine the answer, loading
fails and the message names the rewrite. Each rule below is that principle in
one position, and links to the page that owns it.

| #   | Rule                                                                                                                                                                                                                                                                                                                                                                                                        |                                                        |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| 1   | Ten declaration keys plus `version` and `description`, and the schema is **closed at every level** — an unknown key is an error naming the near miss. Booleans are YAML 1.2, so `no` / `on` / `off` stay names.                                                                                                                                                                                             | [The file](#the-file)                                  |
| 2   | Everything decidable without data is **decided without data**.                                                                                                                                                                                                                                                                                                                                              | [Reading](reading.md#what-the-loader-refuses)          |
| 3   | **One flat namespace, no shadowing** — a collision is a load error naming both declarations.                                                                                                                                                                                                                                                                                                                | [Names](expressions.md#name-resolution)                |
| 4   | **Position decides which kinds of name are legal**, and a name's kind is fixed at load time. A dimension is never legal in a value position: it is a coordinate space, not data.                                                                                                                                                                                                                            | [Names](expressions.md#name-resolution)                |
| 5   | **Dim sets compose by union.** A constraint must _equal_ its `foreach`; an objective must carry **none**; a `where` or a bound must not _exceed_ its frame.                                                                                                                                                                                                                                                 | [Dim algebra](expressions.md#dim-algebra)              |
| 6   | **Four constructs create absence**, and nothing else does. It is a state of a _variable_; a constraint's own `where:` deletes its row directly.                                                                                                                                                                                                                                                             | [Absence](absence.md)                                  |
| 7   | Through arithmetic absence **spreads, taking the row with it**. Out of a reduction it does not — so `sum(x + y)` and `sum(x) + sum(y)` are different questions.                                                                                                                                                                                                                                             | [Absence](absence.md#how-absence-travels)              |
| 8   | **Identity of the position.** A missing value reads as whatever makes it contribute nothing — zero as a coefficient, false in a `where`. Where no such reading exists it is refused: a divisor, a bound.                                                                                                                                                                                                    | [Absence](absence.md), [Operators](operators.md#shift) |
| 9   | **Degree 2 in the math, degree 1 beside it**: the objective and constraints take `variable * variable`; a bound and a `piecewise:` link do not, and a named expression is read at the ceiling of the position that reads it. `/` always needs a variable-free divisor, and `**` a base and an exponent that carry no variable. Where a quadratic model can _land_ is a consumer's axis, not the language's. | [Expressions](expressions.md)                          |
| 10  | **The operator set is closed.** Compositions go in `macros:`.                                                                                                                                                                                                                                                                                                                                               | [Operators](operators.md)                              |

Building, solving and reading an answer back belong to a consumer of the
loaded model, not to this package.
