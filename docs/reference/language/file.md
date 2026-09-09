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

Any subset of these keys is accepted, and that includes `objective`. A file
with no objective is a **feasibility problem**. The answer it gives you is
whether the constraints can be met at all. Such a file solves, its variables
read back, and `result.objective` is the zero that the solver was handed.

## `description`

This says what the file as a whole is. It takes the same plain prose that a
declaration's `description:` takes, and it is the first thing that a
[typeset document](../typeset.md) prints. It is optional, it is never parsed,
and it defaults to `null`.

<!-- doctest: skip -->

```yaml
description: Least-cost dispatch of a generator fleet against an hourly load.
dimensions: ...
```

A `#` comment at the top of the file says the same thing, but the parser
throws a comment away. Use `description:` instead, so that a reader who never
opens the YAML still gets the text.

## `version`

This says which language surface the file is written against. It is optional,
and if you leave it out the value is `0`:

<!-- doctest: skip -->

```yaml
version: 0
dimensions: ...
```

`0` means unstable. The surface may change in any release, and saying so in the
file is more honest than saying nothing.
`0` will not become `1` without a changelog entry that names what moved.

If this release does not know the version you give, that is a load error and
nothing more. The field gates no behaviour, and it never selects a different
language surface:

```text
model declares version 1, and math_spec 0.0.1a75 understands [0].
Upgrade math_spec, or write the version this file actually targets.
```

This is a **language** version, not a package version. It moves when the
accepted YAML surface moves, and most releases do not move it.

## An unrecognised key is refused

An unrecognised key is a load error that names the near miss. This applies at
the top level and inside any declaration:

```text
unknown key 'boundz' … Did you mean 'bounds'?
```

If the language ignored an unknown key, a typo could change the model. A
dropped `bounds:` leaves a variable unbounded, and a dropped `where:` leaves it
unmasked.

## How the YAML is read

- **Booleans follow YAML 1.2**, so only `true` and `false` are booleans.
  Everything else is read as YAML 1.1. Under 1.1, the values `on`, `off`, `yes`,
  `no`, `y` and `n` all become booleans, and a declaration named after a country
  code stops being a name. Because booleans are 1.2 here, `no: {dtype: str}` is
  a dimension called `no`.
- **Implicit timestamps** such as `2024-01-01`, and sexagesimal integers such as
  `12:30`, which becomes `750`, both survive. Neither of them reaches a
  coordinate, because a coordinate is data. The one place you read such a value
  as a label is a literal in a `where` string. There, the `dtype` of the name it
  is compared against catches the problem. See
  [expressions](expressions.md#where-strings).
- **A duplicate key is a load error**, and the message names both lines.
- **`<<:` merge keys are honoured.** If the mapping declares a key itself, that
  key overrides the merged value.
- The document must be a mapping.
