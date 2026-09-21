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

The declaration fixes no direction. A call names the columns it reads, and a
key column named at neither end is **joined on**: the operand carries its
dimension, and the result keeps it. A value column named at neither end is not
read.

| kind      | what it does                                | written as                                            |
| --------- | ------------------------------------------- | ----------------------------------------------------- |
| aggregate | many rows of the operand collapse onto one  | `sum(x, by=l, over=a, into=b)`                        |
| read      | one row's value becomes a coordinate        | `at(x, by=l, over=a, into=b)`                         |
| partition | the frame stays, and its rows are grouped   | `shift`, `sum_back`, `position` with `by=l, within=c` |
| test      | a row's presence keeps or cuts a coordinate | the relation's name in a `where`                      |

Four rules hold for every use:

1. **A call names every column it reads.** `sum(p, by=gen_bus)` is refused.
2. **A value column the call does not name is not read.** So adding one to the
   relation changes no call.
3. **The key is fixed.** To change it, declare a new relation.
4. **A dimension the relation does not name passes through** to the result.

### Aggregates and reads

`over=` names the columns consumed and `into=` the columns produced, and either
may be a list. With `zone_of: { key: [generator, period], values: zone }`, the
bare `connection: { key: [generator, bus] }` and `p` over `[generator, period]`:

| call                                               | consumes    | joins on    | produces    | result                |
| -------------------------------------------------- | ----------- | ----------- | ----------- | --------------------- |
| `sum(p, by=zone_of, over=generator, into=zone)`    | `generator` | `period`    | `zone`      | `[zone, period]`      |
| `sum(p, by=zone_of, over=period, into=zone)`       | `period`    | `generator` | `zone`      | `[generator, zone]`   |
| `sum(p, by=connection, over=generator, into=bus)`  | `generator` | nothing     | `bus`       | `[bus, period]`       |
| `at(price, by=zone_of, over=zone, into=generator)` | `zone`      | `period`    | `generator` | `[generator, period]` |

- **The result is the operand, less the consumed dimensions, plus the produced
  ones.** The operand carries every dimension consumed or joined on, and none
  that the call lands on. `sum(load * p, by=gen_bus, over=generator, into=bus)`
  is refused; write `load * sum(p, by=gen_bus, over=generator, into=bus)`.
- **`over=` and `into=` name different columns**, and neither names two
  columns over one dimension.

#### Which call the table admits

A read needs one row per coordinate of its result, and a sum needs many. One
question decides which call the table admits: do the columns a call lands on
and joins on hold the whole key? A call that **covers** the key that way finds
one row at each coordinate. A call that leaves a key column out finds many.

|            | `sum`                                                      | `at`                                         |
| ---------- | ---------------------------------------------------------- | -------------------------------------------- |
| consumes   | at least one key column, and any value column it names too | value columns only                           |
| lands on   | any column it does not consume, key or value               | any column it does not consume, key or value |
| the key is | left uncovered, so many rows meet at one coordinate        | covered, so one row meets each coordinate    |

Both calls land where the table lets them.
`sum(p, by=connection, over=generator, into=bus)` lands on a key column,
because a bare relation has no other kind.
`at(x, by=gen_bt, over=bus, into=technology)` lands on a value column and joins
on the key. What separates the two calls is the consumed end.

- **A sum that consumes no key column is a read.** Every key column is then
  landed on or joined on, so each coordinate holds one term and nothing is
  added up. The refusal names the call to write instead:

  ```text
  Constraint 'cap': sum(by=zone_of): this sum lands on the key ['generator', 'period'], so each coordinate has one term and nothing is added up — that is a read, which is at()'s. Write at(..., by=zone_of, over=['zone'], into=['generator']), or sum toward a value column.
  ```

- **A read that consumes a key column is a sum.** The key is then uncovered,
  so the coordinate the read lands on has many rows and no one value:

  ```text
  Constraint 'cap': at(by=gen_bt): at reads one value per coordinate, and 'gen_bt' is not single-valued in ['generator'] at the columns the call lands on (['bus']) — its key is ['generator']. Key the table by the columns the call lands on, or read the other way.
  ```

### Partitions

`shift(x, along=d, by=l, within=c)`, `sum_back(x, along=d, by=l, within=c)`
and `position(d, by=l, within=c)` step along the key column over `d`, join on
the other key columns, and group by the value columns `within=` names. The
frame does not change. `within=` is written whenever `by=` is. It may name two
columns over one dimension, may not name a key column, and a bare relation
partitions nothing.

### Tests

A `where` string uses a relation at the frame's own coordinates: it compares a
column under `values:` against a label, compares two columns of one table, or
tests that a row exists ([where strings](expressions.md#where-strings)).
