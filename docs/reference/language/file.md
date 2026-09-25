<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# File shape

A model file is a YAML mapping with **twelve declaration keys**, plus
`version` and `description`. Any subset of the twelve is accepted.

| Key           |                                                                                                   |
| ------------- | ------------------------------------------------------------------------------------------------- |
| `dimensions`  | the axes ([dimensions](dimensions.md))                                                            |
| `relations`   | named relations between dimensions ([relations](relations.md))                                    |
| `parameters`  | the data the model expects ([declarations](declarations.md))                                      |
| `variables`   | what the solver decides                                                                           |
| `given`       | what this file reads but does not build ([given](declarations.md#given))                          |
| `constraints` | the rules those decisions obey                                                                    |
| `objective`   | what is minimised or maximised                                                                    |
| `expressions` | named quantities, reusable in the math and readable after a solve ([named expressions](named.md)) |
| `macros`      | templates that take arguments ([macros](named.md#macros))                                         |
| `piecewise`   | piecewise-linear curves ([piecewise](piecewise.md))                                               |
| `sos`         | special-ordered sets ([sos](piecewise.md#sos))                                                    |
| `assumptions` | what the model expects of its data ([assumptions](assumptions.md))                                |

A file with no `objective` is a **feasibility problem**: it asks whether the
constraints can all be met.

## `description`

Free text that says what the model is. It is optional, and a
[typeset document](../typeset.md) prints it first.

```yaml
description: Least-cost dispatch of a generator fleet against an hourly load.
```

## `version`

The language version the file is written against. It is optional, and it
defaults to `0`, the one version this release knows. It is not the package
version ([versions](../../about/versions.md)).

```yaml
version: 0
```

A version this release does not know is a load error:

```text
version: model declares version 1, and mathspec 0.0.0a127 understands [0].
Upgrade mathspec, or write the version this file actually targets.
```

## Unknown keys

An unknown key is a load error that names the near miss, at the top level and
inside every declaration:

```text
unknown key 'boundz' … Did you mean 'bounds'?
```

## How the YAML is read

- The document is a mapping.
- Only `true` and `false` are booleans, so `no: {dtype: str}` is a dimension
  called `no`.
- A duplicate key is a load error, and the message names both lines.
- `<<:` merge keys are honoured. A key the mapping declares itself overrides
  the merged value.
