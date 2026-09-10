<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# File shape

A model file is a YAML mapping with **eleven declaration keys**, plus
`version` and `description`. Any subset of the eleven is accepted.

| Key           |                                                                                                                     |
| ------------- | ------------------------------------------------------------------------------------------------------------------- |
| `dimensions`  | the axes ([dimensions](dimensions.md))                                                                              |
| `lookups`     | named maps out of a dimension ([lookups](dimensions.md#lookups))                                                    |
| `parameters`  | the data the model expects ([declarations](declarations.md))                                                        |
| `variables`   | what the solver decides                                                                                             |
| `constraints` | the rules those decisions obey                                                                                      |
| `objective`   | what is minimised or maximised                                                                                      |
| `expressions` | named quantities, reusable in the math and readable after a solve ([expressions](expressions.md#named-expressions)) |
| `macros`      | templates that take arguments ([macros](expressions.md#macros))                                                     |
| `piecewise`   | piecewise-linear curves ([piecewise](piecewise.md))                                                                 |
| `sos`         | special-ordered sets ([sos](piecewise.md#sos))                                                                      |
| `given`       | what the file reads and does not introduce ([given](given.md))                                                      |

A file with no `objective` is a **feasibility problem**: it asks whether the
constraints can all be met. It loads and solves like any other model, and the
solver reports an objective of zero.

## `description`

Plain prose that says what the file as a whole is. It is optional, it is never
parsed, and it defaults to `null`. A [typeset document](../typeset.md) prints
it first.

<!-- doctest: skip -->

```yaml
description: Least-cost dispatch of a generator fleet against an hourly load.
dimensions: ...
```

A `#` comment can say the same thing, but the parser throws a comment away.
A `description:` reaches every tool that reads the model.

## `version`

The language version the file is written against. It is optional, and it
defaults to `0`:

<!-- doctest: skip -->

```yaml
version: 0
dimensions: ...
```

`0` means that the accepted YAML may change in any release. It becomes `1` only
with a changelog entry that names what moved. This is a language version, not
the package version, and most releases do not move it.

A version this release does not know is a load error. The field selects
nothing else:

```text
model declares version 1, and math_spec 0.0.1a75 understands [0].
Upgrade math_spec, or write the version this file actually targets.
```

## Unknown keys

An unknown key is a load error that names the near miss, at the top level and
inside every declaration:

```text
unknown key 'boundz' … Did you mean 'bounds'?
```

An ignored key would change the model silently. A dropped `bounds:` leaves a
variable unbounded, and a dropped `where:` leaves it unmasked.

## How the YAML is read

- **Booleans follow YAML 1.2**, so only `true` and `false` are booleans.
  Everything else follows YAML 1.1. Under 1.1, `on`, `off`, `yes`, `no`, `y`
  and `n` are booleans, and a declaration named after a country code stops
  being a name. Here, `no: {dtype: str}` is a dimension called `no`.
- Implicit timestamps such as `2024-01-01`, and sexagesimal integers such as
  `12:30`, which reads as `750`, survive. Neither reaches a coordinate, because
  coordinates are data. The one place such a value is read as a label is a
  literal in a `where` string, where the `dtype` of the name it is compared
  against catches it. See [where strings](expressions.md#where-strings).
- A duplicate key is a load error, and the message names both lines.
- `<<:` merge keys are honoured. A key the mapping declares itself overrides
  the merged value.
- The document must be a mapping.
