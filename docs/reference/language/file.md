<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# File shape

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

## `description`

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

## `version`

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

## The schema is closed

An unrecognised key, at the top level or inside any declaration, is a load
error naming the near miss:

```text
unknown key 'boundz' … Did you mean 'bounds'?
```

## How the YAML is read

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
