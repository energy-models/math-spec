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

The declaration fixes no direction. A call **joins** the operand to the
relation on the columns they share, and **groups** what the join produces. The
call names the columns that decide both.

| kind              | what it does                                                                 | written as                                            |
| ----------------- | ---------------------------------------------------------------------------- | ----------------------------------------------------- |
| join and group by | rows of the operand match rows of the relation, and each group is added up   | `sum(x, by=l, over=a, into=b)`                        |
| join              | each row of the operand matches one row of the relation, and reads its value | `at(x, by=l, over=a, into=b)`                         |
| partition         | the frame stays, and its rows are grouped                                    | `shift`, `sum_back`, `position` with `by=l, within=c` |
| test              | a row's presence keeps or cuts a coordinate                                  | the relation's name in a `where`                      |

Four rules hold for every use:

1. **A call names every column it reads.** `sum(p, by=gen_bus)` is refused.
2. **A value column the call does not name is not read.** So adding one to the
   relation changes no call.
3. **The key is fixed.** To change it, declare a new relation.
4. **A dimension the relation does not name passes through** to the result.

### Joins and group-bys

Each column of the relation is either **joined on** or not, and either
**grouped by** or not. `by=` names the relation, and not the columns grouped
by. `over=` names the columns joined on and not grouped by, which leave the
result. `into=` names the columns grouped by and not joined on, which the
result lands on. Either may be a list. So in every call `over=` names what
leaves and `into=` names what arrives, as `over=` does in `sum(p, over=d)`.

| column of the relation        | joined on | grouped by | in the result |
| ----------------------------- | --------- | ---------- | ------------- |
| `over=`                       | yes       | no         | leaves        |
| `into=`                       | no        | yes        | arrives       |
| a key column the call omits   | yes       | yes        | stays         |
| a value column the call omits | no        | no         | is not read   |

With `zone_of: { key: [generator, period], values: zone }`, the bare
`connection: { key: [generator, bus] }` and `p` over `[generator, period]`:

| call                                               | joins on            | groups by           | result                |
| -------------------------------------------------- | ------------------- | ------------------- | --------------------- |
| `sum(p, by=zone_of, over=generator, into=zone)`    | `generator, period` | `zone, period`      | `[zone, period]`      |
| `sum(p, by=zone_of, over=period, into=zone)`       | `period, generator` | `zone, generator`   | `[generator, zone]`   |
| `sum(p, by=connection, over=generator, into=bus)`  | `generator`         | `bus`               | `[bus, period]`       |
| `at(price, by=zone_of, over=zone, into=generator)` | `zone, period`      | `generator, period` | `[generator, period]` |

- **The result is the operand, less the columns joined on, plus the columns
  grouped by.** The operand carries every column joined on, and none that the
  call groups by: a column the operand carries would be joined on, not grouped
  by. `sum(load * p, by=gen_bus, over=generator, into=bus)` is refused; write
  `load * sum(p, by=gen_bus, over=generator, into=bus)`.
- **A sum adds up several rows per group, and a read finds one.** Where the
  columns grouped by hold the whole key, every group is one row. That is a join
  with no group-by, which is `at`. A `sum` there is refused toward `at`, and an
  `at` whose groups hold several rows is refused toward `sum`:

  ```text
  Constraint 'cap': sum(by=zone_of): the columns this sum groups by, ['generator', 'period'], hold the whole key ['generator', 'period'], so every group is one row and nothing is added up — that is a join with no group-by, which is at()'s. Write at(..., by=zone_of, over=['zone'], into=['generator']), or sum toward a value column.
  ```

- **A sum joins on at least one key column, and groups by any column it does
  not join on.** Either end may name a value column beside a key one.
  `connection` has only key columns, and the sum above joins on one and groups
  by the other.
- **A read joins on value columns, and groups by the key.** Its result carries
  every key column, named in `into=` or left unnamed, and whatever else the
  operand carries that the read does not join on.
- **`over=` and `into=` name different columns**, and neither names two
  columns over one dimension.

### Partitions

`shift(x, along=d, by=l, within=c)`, `sum_back(x, along=d, by=l, within=c)`
and `position(d, by=l, within=c)` step along the key column over `d`, join on
the other key columns, and partition the rows by the value columns `within=`
names. The
frame does not change. `within=` is written whenever `by=` is. It may name two
columns over one dimension, may not name a key column, and a bare relation
partitions nothing.

### Tests

A `where` string uses a relation at the frame's own coordinates: it compares a
column under `values:` against a label, compares two columns of one table, or
tests that a row exists ([where strings](expressions.md#where-strings)).
