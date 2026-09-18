<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Relations

A **relation** is a mapping between [dimensions](dimensions.md): a generator's
bus, a snapshot's period, or the buses a generator may connect to. It is
declared as a table, and the data supplies its rows.

## `relations`

```yaml
dimensions:
  bus: { dtype: str }
  generator: { dtype: str }
  snapshot: { dtype: int }
  period: { dtype: int }
relations:
  gen_bus: { key: generator, values: bus } # each generator on one bus
  period_of: { key: snapshot, values: period }
  connection: { key: [generator, bus] } # no values: a generator may connect to several buses
```

`key:` and `values:` each name one dimension or a list of them. The **key** is
the combination of dimensions that is unique per row: `key: generator` says
the table has one row per generator. The **values** are what that row
determines: its bus. With no `values:`, the key is every column, and the table
is a **bare relation**.

| Field         |                                                                  |                |
| ------------- | ---------------------------------------------------------------- | -------------- |
| `key`         | required. The columns that identify a row                        |                |
| `values`      | the columns the key determines. Omitted, the key is every column | default none   |
| `description` | free text, never parsed                                          | default `null` |

A column is named after its dimension. Where two columns share a dimension, or
a column maps a dimension onto itself, the mapping form names them:
`{bus0: bus, bus1: bus}`.

### Cardinalities

| to say                                                        | write                                                                                                               |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| many-to-one, each generator on one bus                        | `{key: generator, values: bus}`                                                                                     |
| one-to-many, a bus and its generators                         | the same table, read the other way                                                                                  |
| many-to-many, a generator on several buses                    | `{key: [generator, bus]}`, no `values:`                                                                             |
| one value per pair, a generator's zone in each period         | `{key: [generator, period], values: zone}`                                                                          |
| two columns over one dimension, a line's two ends             | `{key: line, values: {bus0: bus, bus1: bus}}`                                                                       |
| a dimension onto itself, a snapshot's representative          | `{key: snapshot, values: {rep: snapshot}}`                                                                          |
| pairs of one dimension, a snapshot and each of its neighbours | `{key: {from: snapshot, to: snapshot}}`, no `values:`. `sum` walks it either way, and nothing reads a value from it |
| one-to-one                                                    | not a claim the language has: a key is one set of columns                                                           |

A key that determines a value holds one column per dimension, so
`{key: {bus0: bus, bus1: bus}, values: line}` is refused. A bare relation may
key two columns over one dimension, because nothing reads it.

### The data contract

The data for `gen_bus` arrives under the key `gen_bus`, as a table with one
column per declared column, named after it.

- **One row per key tuple.** A generator on two buses is refused when the data
  binds.
- **Every value is a label of its dimension.** A value that matches none is
  refused as a typo, never added as a member.
- **A partial map is the rows it has.** A generator in no row sits on no bus,
  which is [absence](absence.md), as for a parameter.
- **A null in any column is refused.**
- **The members keep the order the table gives them.** A partition steps along
  that order.

## How a relation is read

The declaration fixes no direction. A call names the columns it reads, and a
key column named at neither end is **joined on**: the operand carries its
dimension, and the result keeps it. A value column named at neither end is not
read. A relation is read in four ways:

| reading   | in ten words                                | by                                                    |
| --------- | ------------------------------------------- | ----------------------------------------------------- |
| aggregate | many rows of the operand collapse onto one  | `sum(x, by=l, over=a, into=b)`                        |
| read      | one row's value becomes a coordinate        | `at(x, by=l, over=a, into=b)`                         |
| partition | the frame stays, and its rows are grouped   | `shift`, `sum_back`, `position` with `by=l, within=c` |
| test      | a row's presence keeps or cuts a coordinate | the relation's name in a `where`                      |

### Walks

An aggregate and a read are **walks**: `over=` names the columns consumed, and
`into=` the columns produced. Either may be a list. With
`zone_of: { key: [generator, period], values: zone }` and `p` over
`[generator, period]`:

| call                                               | consumes    | joins on    | produces    | result                |
| -------------------------------------------------- | ----------- | ----------- | ----------- | --------------------- |
| `sum(p, by=zone_of, over=generator, into=zone)`    | `generator` | `period`    | `zone`      | `[zone, period]`      |
| `sum(p, by=zone_of, over=period, into=zone)`       | `period`    | `generator` | `zone`      | `[generator, zone]`   |
| `at(price, by=zone_of, over=zone, into=generator)` | `zone`      | `period`    | `generator` | `[generator, period]` |

#### The six rules

1. **The result is the operand, less the consumed dimensions, plus the
   produced ones.** The operand carries every dimension consumed or joined on.
2. **Both ends are written on every call.** `sum(p, by=gen_bus)` is refused,
   so that an edit to the relation never changes a result.
3. **Adding a value column is safe.** A value column the call does not name is
   not read.
4. **The key is fixed.** A key that gains or loses a column re-aims every call
   that joins on it. Declare a new relation instead.
5. **An operand may grow.** A dimension the relation does not name passes
   through to the result. Growing into a dimension the call lands on is
   refused: write `load * sum(p, by=gen_bus, over=generator, into=bus)`, not
   `sum(load * p, ...)`. A relation onto its own dimension is not this case.
6. **`sum` consumes a key column, and `at` consumes none.** Consume none and
   each coordinate finds one row, which is a read. Consume one and it finds
   many, which is a sum. Each is refused in the other's case.

Rule 6 is all that tells the two ends apart:

| operator | `over=`, consumed                      | `into=`, produced |
| -------- | -------------------------------------- | ----------------- |
| `sum`    | any columns, at least one a key column | any columns       |
| `at`     | value columns only                     | any columns       |

An end may not name a column twice, name a column the other end names, or
name two columns over one dimension.

### Partitions

`shift(x, along=d, by=l, within=c)`, `sum_back(x, along=d, by=l, within=c)`
and `position(d, by=l, within=c)` step along the key column over `d`, join on
the other key columns, and group by the value columns `within=` names. The
frame does not change. `within=` is written whenever `by=` is, so rules 3 and
4 hold. `within=` may name two columns over one dimension, may not name a key
column, and a bare relation partitions nothing.

### Tests

A `where` string reads a relation at the frame's own coordinates: a value
column at its key, two columns of one table compared, or a bare name that
tests a row exists ([where strings](expressions.md#where-strings)).
