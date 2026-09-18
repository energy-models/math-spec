<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Relations

A **relation** is a named table between [dimensions](dimensions.md): a
generator's bus, a snapshot's period, or the buses a generator may connect to.
This page says how one is declared, what its key claims, and how an operator
or a `where` reads it.

## `relations`

A relation is a **table with one column per dimension it relates**. It is what
makes topology data, so no adjacency matrix and no hand-written join appears
anywhere. `key:` names the columns that identify a row, and `values:` the
columns that key determines. Every relation is keyed: with no `values:`, the
key is every column. The declaration fixes no direction. The call that reads
the table says which columns it reads ([below](#how-a-relation-is-read)).

```yaml
dimensions:
  bus: { dtype: str }
  generator: { dtype: str }
  line: { dtype: str }
  snapshot: { dtype: int }
  period: { dtype: int }
relations:
  gen_bus: { key: generator, values: bus } # each generator on one bus
  line_from: { key: line, values: bus } # two relations onto one dimension
  line_to: { key: line, values: bus }
  period_of: { key: snapshot, values: period }
  connection: { key: [generator, bus] } # no values: a generator may connect to several buses
```

| Field         |                                                                                                        |                |
| ------------- | ------------------------------------------------------------------------------------------------------ | -------------- |
| `key`         | required — the columns that identify a row ([below](#the-key-is-the-claim))                            |                |
| `values`      | the columns the key determines; omitted, the table is a bare relation ([below](#the-key-is-the-claim)) | default none   |
| `description` | free text, never parsed                                                                                | default `null` |

Each side is one dimension, a list of them, or a mapping of column name to
dimension where two columns share one ([roles](#roles)).

A relation has at least two columns between the two sides, each over a declared
dimension, and each column name is distinct. A column named like a dimension is
over that dimension, so `values: {bus: line}` is refused. A relation name may not
shadow a dimension: `generator`'s map onto `bus` is `gen_bus`, never a second
`bus`.

A column's values are checked against its dimension's labels when data is
bound, so a mistyped bus is refused rather than summed into a group of its own.
That is why a label set the model only selects on is still declared as a
dimension. Nothing above is indexed by `period`, but `period` is declared, so
`where: "period_of == 1"` ([where strings](expressions.md#where-strings))
compares against a checked label.

## The key is the claim

`key:` names the columns that are unique together. `key: generator` says the
generator column holds each label once: the table has **one row per
generator**, so every column under `values:` is a function of it. `key: [generator, period]`
says the pair holds each combination once. Neither column need be unique on its
own: a generator appears once per period, and a period once per generator. The
claim is checked at bind, so a generator on two buses is refused
([#161](https://github.com/energy-models/math-spec/issues/161)). The columns
under `values:` are the relation's **value columns**. A key that determines a
value is read at its dimensions, and no frame carries a dimension twice, so
`{key: {bus0: bus, bus1: bus}, values: line}` is refused. A bare relation may
key two columns over one dimension, because nothing reads it.

Each cardinality is one declaration:

| to say                                     | write                                                                                                                                                                 | checked at bind       |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------- |
| many-to-one, each generator on one bus     | `{key: generator, values: bus}`                                                                                                                                       | one row per generator |
| one-to-many, a bus and its generators      | the same table: `sum(p, by=gen_bus, over=generator, into=bus)` collects a bus's generators, `at(price, by=gen_bus, over=bus, into=generator)` reads a generator's bus | the same              |
| many-to-many, a generator on several buses | `{key: [generator, bus]}`, no `values:`                                                                                                                               | no row twice          |
| one-to-one                                 | not a claim the language has: a key is one set of columns, and nothing checks the other side                                                                          |                       |

A bare relation is a set of rows: no row twice, and nothing else claimed.
`sum` walks it with both ends named, and a bare `where` tests it. That is what
a many-to-many relation can say, and all it can say.

## Roles

A bare name or a list names each column after its dimension. Two columns over
one dimension need names of their own, and the mapping form gives them:

```yaml
relations:
  ends: { key: line, values: { bus0: bus, bus1: bus } } # a line's two ends, one table
  rep_of: { key: snapshot, values: { rep: snapshot } } # the representative snapshot
```

`sum(f, by=ends, over=line, into=bus1) - sum(f, by=ends, over=line, into=bus0)`
is a nodal balance through one table: flow arriving at `bus1` less flow leaving
`bus0`. `where: "ends.bus0 != ends.bus1"` excludes a line whose two ends are
one bus.

`rep_of` relates a dimension to itself. That is how a clustered year runs on a
few typical days: every snapshot names the snapshot that stands for it. The
rules are the same. `sum` consumes `snapshot` and produces `rep`, both over
`snapshot`, so the frame is `[snapshot]` before the walk and after it:

```yaml
constraints:
  representative: # every snapshot takes its representative's value
    dims: [snapshot]
    expression: p == at(p, by=rep_of, over=rep, into=snapshot)
  weighted: # the snapshots a representative stands for, summed onto it
    dims: [snapshot]
    expression: sum(p, by=rep_of, over=snapshot, into=rep) <= 100
```

**The key directs a self-map.** `key: snapshot` makes `rep` a function of
`snapshot`. `at` reads each snapshot's representative, and `sum` collects onto
a representative the snapshots it stands for. Two steps along the map are two
nested calls. Put both columns under `key:`, as
`{key: {from: snapshot, to: snapshot}}`, and the table is a neighbour table
instead, which `sum` walks either way and nothing reads. The rows where a
snapshot is its own
representative cannot be selected with a `where`, because a value column is
never compared to the frame's own coordinate. Declare a `bool` parameter for
them.

## How the map is supplied

The data for `gen_bus` arrives under the key `gen_bus`, as a table with one
column per declared column, named after it:

```python
sources = {
    'generator': ['g1', 'g2', 'g3'],
    'gen_bus': pl.DataFrame({'generator': ['g1', 'g2'], 'bus': ['north', 'south']}),
}
```

**A partial map is the rows it has.** `g3` is in no row, so `g3` sits on no
bus. Absence is the missing row, as it is for a parameter. A null in any column
is refused, because a row that is present and empty says both at once. The
table holds one row per key tuple. A value that matches no label of its
dimension is refused as a typo, never added as a member.

A relation's table stands on its own, so a model gains a relation the way it
gains a parameter: one more table, and no change to the others. **A column named
after a relation inside a dimension's table is refused.** That table may carry
other extra columns, but this one would be a map read by accident.

## How a relation is read

A relation is read in three ways. A **walk** moves the frame: `sum` and `at`
consume columns and produce others. A **partition** keeps the frame and groups
it: `shift`, `sum_back` and `position` step inside the groups a relation makes.
A **`where`** tests it at the frame's own coordinates. The declaration fixes no
direction, and the call says which columns it reads.

### Walks

A walk reads a relation from one set of its columns to another. `over=` names
the columns the call **consumes**, and `into=` names the columns it
**produces**. Every key column named at neither end is **joined on**: the
operand carries its dimension, and the result keeps it. A value column named
at neither end is not read.

`sum` consumes key columns and produces value columns. `at` consumes value
columns and produces the key.

```yaml
dimensions:
  generator: { dtype: str }
  zone: { dtype: str }
  period: { dtype: int }
relations:
  zone_of: { key: [generator, period], values: zone } # a generator's zone, per period
parameters:
  demand: { dims: [zone, period] }
  price: { dims: [zone, period] }
variables:
  p: { dims: [generator, period] }
constraints:
  zone_balance: # consumes generator, joins on period, produces zone: [generator, period] -> [zone, period]
    dims: [zone, period]
    expression: sum(p, by=zone_of, over=generator, into=zone) >= demand
  history: # consumes period, joins on generator, produces zone: [generator, period] -> [generator, zone]
    dims: [generator, zone]
    expression: sum(p, by=zone_of, over=period, into=zone) <= 100
  capped_revenue: # consumes zone, joins on period, produces generator: [zone, period] -> [generator, period]
    dims: [generator, period]
    expression: at(price, by=zone_of, over=zone, into=generator) * p <= 1000
```

The three calls read one table three ways:

| call                                               | consumes    | joins on    | produces    | operand               | result                |
| -------------------------------------------------- | ----------- | ----------- | ----------- | --------------------- | --------------------- |
| `sum(p, by=zone_of, over=generator, into=zone)`    | `generator` | `period`    | `zone`      | `[generator, period]` | `[zone, period]`      |
| `sum(p, by=zone_of, over=period, into=zone)`       | `period`    | `generator` | `zone`      | `[generator, period]` | `[generator, zone]`   |
| `at(price, by=zone_of, over=zone, into=generator)` | `zone`      | `period`    | `generator` | `[zone, period]`      | `[generator, period]` |

`capped_revenue` reads the price of the zone this generator sat in that period.
The typesetter prints it as $`\mathrm{price}_{\mathrm{zone\_of}(g,\ e),e}`$,
and the joined `period` is the second subscript.

Three things hold for the shape of the call:

- **Either keyword takes a list.** With
  `gen_bt: { key: generator, values: [bus, technology] }`,
  `sum(p, by=gen_bt, over=generator, into=[bus, technology])` lands on the
  product `bus x technology` in one join.
  `sum(p, by=zone_of, over=[generator, period], into=zone)` consumes both key
  columns at once, so nothing is joined on and `period` leaves with `generator`.
- **`into=` needs a `by=`**, because a column belongs to a table. `over=`
  without a `by=` names a dimension, as in `sum(p, over=period)`.
- **One call walks one table.** `by=` names a single relation. To land on
  columns of two tables at once, declare one relation holding the columns of
  both; to walk them in turn, write one call each.

### The six rules

Six rules hold for every `sum` and every `at` through a relation. They say what
a call computes, which of the two operators is legal, and what an edit to the
file changes. A change to the notation has to keep all six.

1. **The result is the operand, less the consumed dimensions, plus the produced
   ones.** The operand carries every dimension the call consumes and every one
   it joins on. In symbols, `result = (operand − consumed) ∪ produced`, where
   the joined columns are the key columns named at neither end. The table above
   is this rule three times.
2. **The result gains a dimension only from the operand, never from an edit to
   the relation.** That is why both ends are written on every call.
   `sum(p, by=gen_bus)` is refused, even where `gen_bus` has one key column and
   one value column. What a call leaves unsaid, an edit to the relation could
   change: a table that gained a value column would silently start producing
   it.
3. **Adding a value column is safe.** A relation that gains one changes no
   existing call, because a value column the call does not name is not read.
   `sum(f, by=ends, over=line, into=bus1)` reads `bus1` and ignores `bus0`, and
   goes on reading `bus1` alone when `ends` gains a third column.
4. **The key is fixed.** Every call through a relation joins on the key columns
   it names at neither end. So a key that gains or loses a column re-aims every
   call at once, and that is a different table. Declare a new relation rather
   than edit the key. Calls through the old one keep their meaning, because the
   old one still says what it said.
5. **An operand may grow.** A call means the same when its operand gains a
   dimension the relation does not name, and that dimension passes through to
   the result. Give `p` a `scenario` dimension, and `zone_balance` carries
   `scenario` too, with the same call. An operand may not grow into a dimension
   the call lands on. `sum(load * p, by=gen_bus, over=generator, into=bus)` is
   refused where `load` carries `bus`. The walk would tie the operand's `bus` to
   the one it produces rather than add it, and the call reads the same either
   way. Write `load * sum(p, by=gen_bus, over=generator, into=bus)`. A relation
   into its own dimension is not this case, because there the dimension landed
   on is the one just consumed ([roles](#roles)).
6. **`sum` consumes a key column, and `at` consumes none.** Consume no key
   column and each coordinate finds one row, so nothing is added up. That is a
   read, and it is `at`'s. Consume one and a coordinate finds many rows, which
   is `sum`'s. Each operator is refused in the other's case.

What each end may name follows from rule 6, and from nothing else:

| operator | `over=`, consumed                      | `into=`, produced |
| -------- | -------------------------------------- | ----------------- |
| `sum`    | any columns, at least one a key column | any columns       |
| `at`     | value columns only                     | any columns       |

An end may not name a column twice, name a column the other end names, or name
two columns over one dimension. The operand has one axis per dimension, so
nothing would say which column its coordinate is read at.

Five refusals draw the line, and each message names the rewrite:

| refused                                | message                                                                                                                                                                                                                                                                  |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| a walk with an end unsaid              | `sum() through a relation leaves into= unsaid. A walk names both of its ends, so that a relation may gain a value column without changing what this call means. Write: sum(<expr>), sum(<expr>, over=<dim>) or sum(<expr>, by=<relation>, over=<column>, into=<column>)` |
| landing on a dimension already carried | `sum(by=gen_bus) lands on ['bus'], which the expression already carries. A walk brings the dims it lands on, so that reading the call tells you what it adds. Move the factor carrying ['bus'] outside the operator, or walk to a column over another dimension.`        |
| `at` on a bare relation                | `at(by=connection): at reads one value per coordinate, and 'connection' is not single-valued in ['bus'] at the columns the operand fixes (['generator']) — its key is ['generator', 'bus']. Key the table by columns the read fixes, or read the other way.`             |
| a `sum` that consumes no key column    | `sum(by=zone_of): this sum walks to the key ['generator', 'period'], so each coordinate has one term and nothing is added up — that is a read, which is at()'s. Write at(..., by=zone_of, over=['generator'], into=['zone']), or sum toward a value column.`             |
| an operand missing a joined dimension  | `at(by=zone_of) joins on ['period'] (columns ['period'] of 'zone_of'), which the expression does not carry (dims ['zone']). A relation is walked between two of its columns and read at the others — index the operand by them, or walk between different columns.`      |

### Partitions

`shift(x, along=d, by=l, within=c)`, `sum_back(x, along=d, by=l, within=c)` and
`position(d, by=l, within=c)` walk the one key column over `d`, join on the
other key columns, and group by the value columns `within=` names. The frame
does not change: the group says which rows are neighbours, and nothing lands
anywhere.

A partition writes `within=` whenever it writes `by=`, for the reason a walk
writes both of its ends. `shift(x, along=snapshot, by=cal, within=week)` walks
within weeks of a calendar declared once over `[snapshot, day, week]`, and a
value column not named is not read. So a table that gains a column changes no
call through it. The group may be two columns over one dimension, such as a
line's two buses, because a partition produces no dimension. `within=` naming a
key column is refused, and a bare relation partitions nothing. The refusal for
a group left unsaid names the rewrite:

```text
shift() through a relation leaves within= unsaid.
A partition names the value columns it groups by, so that a relation may gain a value column without changing what this call means.
Write: shift(<expr>, along=<dim>, offset=<n>[, edge='wrap'|<number>][, by=<relation>, within=<column>])
```

Of the [six rules](#the-six-rules), a partition keeps rules 3 and 4. A key
column added to the relation is one more column every call joins on, so declare
a new relation.

### In a `where`

A `where` string reads a relation at the frame's own coordinates: a value
column at its key, two columns of one table compared, or a bare name that tests
a row exists ([where strings](expressions.md#where-strings)). Nothing is
consumed, produced or joined on, so the frame carries the key's dimensions.
