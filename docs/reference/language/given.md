<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Given declarations

`given:` names the variables and constraints a file reads and does not
introduce. Use it to write a **layer**: a file of math meant to be added to a
model that already exists, such as an emissions cap over a dispatch model
somebody else built.

A file with a `given:` block says all of its own math. What it does not say is
where those declarations come from. That is bound by whoever builds the model,
the same way the numbers behind a parameter are.

```yaml
dimensions:
  snapshot: { dtype: int }
  generator: { dtype: str }
parameters:
  emission_rate: { dims: [generator] }
  cap: { dims: [] }
given:
  variables:
    p:
      foreach: [snapshot, generator]
      description: dispatch, built by the model this file is added to
  constraints:
    balance:
      foreach: [snapshot]
      sense: "=="
constraints:
  co2_cap:
    foreach: []
    expression: sum(sum(p * emission_rate, over=generator), over=snapshot) <= cap
expressions:
  price: dual(balance)
```

The file loads on its own, prints on its own, and is refused on its own terms.
Nothing about it waits for the model it is laid over.

## `given.variables`

A given variable is a column the file reads. It carries every field a
load-time rule asks a variable for:

| Field         |                                                        |              |
| ------------- | ------------------------------------------------------ | ------------ |
| `foreach`     | the dimensions the column is indexed by                | required     |
| `where`       | a mask, in the [`where` grammar](expressions.md)       | optional     |
| `domain`      | `continuous`, `integer` or `binary`                    | `continuous` |
| `absence`     | what a masked coordinate means ([absence](absence.md)) | `undefined`  |
| `description` | plain prose                                            | optional     |

**There is no `bounds:` key.** Whoever owns the column owns its bounds, and a
second spelling of them here would be a second home for one fact. Writing one
is refused:

```text
given.variables.p: unknown key 'bounds' in a given variable declaration.
Valid keys: absence, description, domain, foreach, where.
```

**Everything else treats a given variable as a variable.** It resolves in an
expression, it carries dimensions into a constraint, it prints in the legend,
and its `where` is checked against its `foreach`. The one thing that differs is
who builds the column.

## `given.constraints`

A given constraint is a row family the file reads the dual of:

| Field         |                                        |          |
| ------------- | -------------------------------------- | -------- |
| `foreach`     | the dimensions the rows are indexed by | required |
| `sense`       | `<=`, `==` or `>=`                     | required |
| `description` | plain prose                            | optional |

**There is no `expression:` key.** The body belongs to whoever builds the row.
Nothing here builds one, so a given constraint never reaches the constraints a
build reads.

```text
given.constraints.balance: unknown key 'expression' in a given constraint
declaration. Valid keys: description, foreach, sense.
```

**`sense` is required because it fixes the sign of the dual.** Under
`minimize`, a `<=` row and a `>=` row carry shadow prices of opposite sign. A
dual read against the wrong sense is a wrong number rather than an error. So
the file states the sense, and a consumer checks it against what it binds.

**`dual()` is the only thing that may name a given constraint.** It is a
[reported expression](reported.md), so the same rule holds as for any dual: the
math cannot read one. Writing `dual(balance)` in a constraint or the objective
is refused:

```text
Constraint 'co2_cap': a dual exists only after a solve; the math cannot read
one — keep the entry that carries it out of constraints, the objective, bounds
and where.
```

## What is refused

| The file says                                            | Because                                                             |
| -------------------------------------------------------- | ------------------------------------------------------------------- |
| `bounds:` on a given variable                            | the owner of the column holds them                                  |
| `expression:` on a given constraint                      | the owner of the row holds it                                       |
| a given constraint with no `sense:`                      | its dual would have no sign convention                              |
| a name under both `variables:` and `given.variables`     | one flat namespace, so it is a collision naming both                |
| a name under both `constraints:` and `given.constraints` | a row family is built here or given, never both                     |
| a `foreach` naming a dimension the file does not declare | every frame is a product of declared dimensions                     |
| `absence:` with no `where:`                              | an unmasked column exists at every coordinate, so nothing is absent |

## What is advised

A given entry nothing reads asks whoever binds the file to find a column or a
row family it has no use for. That is advice rather than a refusal, since a
half-written file looks the same:

```text
given variable 'spare' is never read: this file declares it and then no
expression names it. Remove it, or name it in the math — a given block states
what a consumer must bind, so an unread entry asks for one it has no use for.
```

Read it through [`advice`](reading.md), under the kind `given-never-read`.

## What a consumer binds

A loaded model reports a given variable in `variables`, with `given` true and
both bounds open, and a given constraint in `given_constraints`, apart from the
constraints a build reads.

The language stops there. Whether the bound column has the declared dimensions,
coordinates and domain is a question about the model, not about the file. So is
whether the bound row family has the declared sense. Both are answered where
the file and the model meet.
