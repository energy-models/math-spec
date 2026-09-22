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

The **key** is the combination of dimensions that is unique per row:
`key: generator` says the table has one row per generator. The **values** are
what that row determines: its bus. With no `values:`, the key is every column,
and the table is a **bare relation**.

| Field         |                                                                  |                |
| ------------- | ---------------------------------------------------------------- | -------------- |
| `key`         | required. The columns that identify a row                        |                |
| `values`      | the columns the key determines. Omitted, the key is every column | default none   |
| `description` | free text                                                        | default `null` |

A column is named after its dimension. Where two columns share a dimension, the
mapping form names them: `{bus0: bus, bus1: bus}`.

### Cardinalities

| intention                                              | written                                               | cardinality                                 |
| ------------------------------------------------------ | ----------------------------------------------------- | ------------------------------------------- |
| each generator has one bus                             | `{key: generator, values: bus}`                       | many-to-one                                 |
| a bus has several generators                           | the same table, read the other way                    | one-to-many                                 |
| a generator may connect to several buses               | `{key: [generator, bus]}`, no `values:`               | many-to-many                                |
| a generator has one zone in each period                | `{key: [generator, period], values: zone}`            | many-to-one, keyed by a pair                |
| a snapshot has a month, a week and a weekday           | `{key: snapshot, values: [month, week, weekday]}`     | many-to-one, several values                 |
| a line has two ends, both buses                        | `{key: line, values: {bus0: bus, bus1: bus}}`         | many-to-one, two columns over one dimension |
| a snapshot has a representative snapshot               | `{key: snapshot, values: {rep: snapshot}}`            | many-to-one, onto itself                    |
| a snapshot has neighbours                              | `{key: {from: snapshot, to: snapshot}}`, no `values:` | many-to-many, onto itself                   |
| each generator has one bus, and each bus one generator | not a claim the language has                          | one-to-one                                  |

A key that determines a value holds one column per dimension, so
`{key: {bus0: bus, bus1: bus}, values: line}` is refused. A bare relation may
key two columns over one dimension.

### The data contract

The data for `gen_bus` arrives under the key `gen_bus`, as a table with one
column per declared column, named after it.

- **One row per key tuple.** A generator on two buses is refused when the data
  binds.
- **Every value is a label of its dimension.** A value that matches none is
  refused.
- **A partial map is the rows it has.** A generator in no row sits on no bus,
  which is [absence](absence.md).
- **A null in any column is refused.**
- **Row order carries nothing.** The order is the
  [dimension's](dimensions.md).

## How a relation is used

The declaration fixes no direction. A call names the relation and its columns
with a dot, and a key column it does not name is **joined on** where the call
reads from the rest of the key, and summed away where it lands on it.

| kind      | what it does                                | written as                                              |
| --------- | ------------------------------------------- | ------------------------------------------------------- |
| aggregate | many rows of the operand collapse onto one  | `sum(x, over=l.a)` or `sum(x, by=l.b)`                  |
| read      | one row's value becomes a coordinate        | `at(x, by=l, over=a, into=b)`                           |
| partition | the frame stays, and its rows are grouped   | `shift`, `sum_back`, `position` with `l.a` and `within=c` |
| test      | a row's presence keeps or cuts a coordinate | the relation's name in a `where`                        |

Four rules hold for every use:

1. **A call names every column it reads.** `sum(p, by=gen_bus)`, with no column
   after the dot, is refused.
2. **A value column the call does not name is not read.** So adding one to the
   relation changes no call.
3. **The key is fixed.** To change it, declare a new relation.
4. **A dimension the relation does not name passes through** to the result.

### Aggregates and reads

A sum names one end after the dot and the relation supplies the other:
`over=` names the columns consumed, and `by=` the columns landed on. A read
names both ends beside a bare relation, with `over=` and `into=`. Every one of
them may be a list, written `l.[a, b]` after the dot. With
`zone_of: { key: [generator, period], values: zone }`, the bare
`connection: { key: [generator, bus] }` and `p` over `[generator, period]`:

| call                                               | consumes    | joins on    | produces    | result                |
| -------------------------------------------------- | ----------- | ----------- | ----------- | --------------------- |
| `sum(p, over=zone_of.generator)`                   | `generator` | `period`    | `zone`      | `[zone, period]`      |
| `sum(p, over=zone_of.period)`                      | `period`    | `generator` | `zone`      | `[generator, zone]`   |
| `sum(p, by=zone_of.zone)`                          | `generator`, `period` | nothing | `zone`   | `[zone]`              |
| `sum(p, by=connection.bus)`                        | `generator` | nothing     | `bus`       | `[bus, period]`       |
| `at(price, by=zone_of, over=zone, into=generator)` | `zone`      | `period`    | `generator` | `[generator, period]` |

- **The result is the operand, less the consumed dimensions, plus the produced
  ones.** The operand carries every dimension consumed or joined on, and none
  that the call lands on. `sum(load * p, over=gen_bus.generator)` is refused;
  write `load * sum(p, over=gen_bus.generator)`.
- **A read finds one row per coordinate, and a sum finds many.** The columns a
  read lands on and joins on hold the whole key. A sum leaves a key column out,
  and each call is refused in the other's case:

  ```text
  Constraint 'cap': sum(by=zone_of.[generator, period]): this sum lands on the key ['generator', 'period'], so each coordinate has one term and nothing is added up — that is a read, which is at()'s. Write at(..., by=zone_of, over=['zone'], into=['generator', 'period']), or sum toward a value column.
  ```

- **A sum consumes at least one key column, and lands on any column it does not
  consume.** `over=` may name a value column beside a key one, and the sum then
  lands on the value column left over. `connection` has only key columns, and
  `by=connection.bus` lands on one and sums the other away.
- **A read consumes value columns, and lands on the key.** Its result carries
  every key column — named in `into=`, or joined on — and whatever else the
  operand carries that the read does not consume.
- **A read's `over=` and `into=` name different columns**, and no end of any
  call names two columns over one dimension.

### Partitions

`shift(x, along=l.a, within=c)`, `sum_back(x, along=l.a, within=c)` and
`position(l.a, within=c)` step along key column `a`, join on the other key
columns, and group by the value columns `within=` names. The frame does not
change. The dot names one key column, and `within=` is written whenever the
dot is. `within=` may name two columns over one dimension, may not name a key
column, and a bare relation partitions nothing.

### Tests

A `where` string uses a relation at the frame's own coordinates: it compares a
column under `values:` against a label, compares two columns of one table, or
tests that a row exists ([where strings](expressions.md#where-strings)).
