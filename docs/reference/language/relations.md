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

The declaration fixes no direction. A call writes the direction inside its
`by=`, after the relation's name, and a key column at neither end is **joined
on**: the operand carries its dimension, and the result keeps it. A value
column at neither end is not read.

| kind      | what it does                                | written as                                     |
| --------- | ------------------------------------------- | ---------------------------------------------- |
| aggregate | many rows of the operand collapse onto one  | `sum(x, by=l(a -> b))`                         |
| read      | one row's value becomes a coordinate        | `at(x, by=l(c))`                               |
| partition | the frame stays, and its rows are grouped   | `shift`, `sum_back`, `position` with `by=l(c)` |
| test      | a row's presence keeps or cuts a coordinate | the relation's name in a `where`               |

Four rules hold for every use:

1. **`by=` is the only relational keyword.** The direction is written inside
   it, and `over=` keeps one meaning: a reduction over a dimension. A sum with
   a `by=` takes no `over=`.
2. **A call writes what the declaration does not decide, and nothing more.**
   `sum(p, by=gen_bus)` loads, because `gen_bus` has one key column and one
   value column.
3. **The key is fixed.** To change it, declare a new relation.
4. **A dimension the relation does not name passes through** to the result.

### Aggregates and reads

**A sum names both ends, since either can vary.** The left end names the
dimensions consumed and the right names the columns landed on, and either may
be a list. With `zone_of: { key: [generator, period], values: zone }` and `p`
over `[generator, period]`:

| call                                    | consumes    | joins on    | produces | result                |
| --------------------------------------- | ----------- | ----------- | -------- | --------------------- |
| `sum(p, by=zone_of(generator -> zone))` | `generator` | `period`    | `zone`   | `[zone, period]`      |
| `sum(p, by=zone_of(period -> zone))`    | `period`    | `generator` | `zone`   | `[generator, zone]`   |
| `at(price, by=zone_of(zone))`           | `zone`      | `period`    | the key  | `[generator, period]` |

- **The left end of a sum names a dimension, every other end names columns.** A
  key holds one column per dimension, so `generator` names the key column over
  it, and a renamed key column is named by its dimension. Value columns may
  share a dimension, so `bus1` is named by column.
- **A read names one end: the columns it reads.** A read lands on the whole
  key, so the landing is not written. `at(cap, by=ends(bus0))` reads the
  sending end of each line. Writing the key out as well,
  `at(cap, by=ends(bus0 -> line))`, says the same thing.
- **The result is the operand, less the consumed dimensions, plus the produced
  ones.** The operand carries every dimension consumed or joined on, and none
  that the call lands on. `sum(load * p, by=gen_bus(generator -> bus))` is
  refused; write `load * sum(p, by=gen_bus(generator -> bus))`.
- **`sum` consumes key columns, and `at` consumes value columns.** A read finds
  one row per coordinate, and a sum finds many. Each is refused in the other's
  case, and names the other.
- **Neither end names two columns over one dimension.** The operand carries
  each dimension once, so nothing would say which column its coordinate is
  read at.

### What the declaration decides

**A bare `by=` asks the declaration for the whole direction.** It has to
decide it:

| call                        | loads when                                            |
| --------------------------- | ----------------------------------------------------- |
| `sum(p, by=gen_bt)`         | the key is one column; it lands on every value column |
| `at(tech_cap, by=gen_bt)`   | it reads every value column, and lands on the key     |
| `shift(x, along=t, by=cal)` | it groups by every value column                       |

This is the rule `sum(x)` already follows for dimensions: with nothing written,
the call takes them all. A relation that decides less is refused, and the
refusal names the direction to write:

```text
sum(by=zone_of): 'zone_of' has 2 key columns (['generator', 'period']), and the
call has to say the direction: by=zone_of(<dimension> -> zone).
```

**A bare call reads a value column added later.** `sum(p, by=gen_bt)` lands on
every value column of `gen_bt`, so a column declared after it changes what it
means. Write the direction — `sum(p, by=gen_bt(generator -> [bus, technology]))`
— where that matters.

### Partitions

`shift(x, along=d, by=l(c))`, `sum_back(x, along=d, by=l(c))` and
`position(d, by=l(c))` step along the key column over `d`, join on the other
key columns, and group by the value columns the parenthesis names. The frame
does not change. **A partition names one end, its group**, because the other
end is the axis `along=` names. The parenthesis may name two columns over one
dimension, may not name a key column, and a bare relation partitions nothing.

### Tests

A `where` string uses a relation at the frame's own coordinates: it compares a
column under `values:` against a label, compares two columns of one table, or
tests that a row exists ([where strings](expressions.md#where-strings)).
