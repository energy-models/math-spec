<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Dimensions and relations

A **dimension** is an axis of the model, such as `snapshot` or `generator`.
Declarations are indexed by it, and `sum` reduces over it.

A **relation** is a named table between dimensions: a generator's bus, a
snapshot's period, or the buses a generator may connect to.

## `dimensions`

```yaml
dimensions:
  snapshot: { dtype: int }
  generator: { dtype: str }
```

Every dimension named anywhere in the file is declared here.

| Field         |                                   |                |
| ------------- | --------------------------------- | -------------- |
| `dtype`       | `float`, `int`, `str`, `datetime` | default `str`  |
| `description` | free text, never parsed           | default `null` |

A declaration says that the axis exists and what type its labels have. It never
lists the labels. The generators, buses and snapshots arrive with the data, as a
table, not as a list somebody keeps in step by hand.

### Where the members come from

The engine that binds the data follows three rules, and every engine follows the
same three. So two engines given the same file and the same tables build the
same model.

1. **The members come from the key named after the dimension.** An engine reads
   `generator` from the `generator` table, and from nowhere else. It reads
   `capacity` for its values, never for its list of generators, and it does not
   treat `gen_bus` as the list either. If a declaration uses `generator` and
   no `generator` table arrives, the engine raises an error that names
   `generator`. It does not build an empty axis, because an empty axis would
   silently delete every row indexed by it. A declared dimension that no
   declaration uses needs no table.
2. **The members keep the order the table gives them.** The engine does not
   sort them, whether they are strings, integers or dates.
   [`shift`](operators.md#shift), `sum_back` and `position()` all count along
   this order, so an engine that sorted `snapshot` would give
   `shift(dispatch, along=snapshot, offset=1)` a different meaning. To get a
   particular order, write the table in that order.
3. **A table has each coordinate at most once.** Two rows for `snapshot == 3`
   is an error that names `3`. The engine does not keep the last, keep the
   first, or add them. _At most_ once, not exactly once: a coordinate with no
   row is [absence](absence.md), and absence is how a model masks. A relation's
   table obeys the same rule.

Every dimension has one list of members, and every parameter is lined up against
it when the data binds. So if `load` has 8760 snapshots and `price` has 8759, the
engine raises an error rather than build a model with one snapshot dropped.

## `relations`

A relation is a **table with one column per dimension it relates**: a
generator's bus, a snapshot's period, or the buses a generator may connect to.
It is what makes topology data, so no adjacency matrix and no hand-written join
appears anywhere. `key:` names the columns that identify a row, and `values:`
the columns that key determines. Every relation is keyed: with no `values:`, the
key is every column. The declaration fixes no direction. The operator that
walks the table says which column it consumes and which it produces.

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

### The key is the claim

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

| to say                                     | write                                                                                                             | checked at bind       |
| ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- | --------------------- |
| many-to-one, each generator on one bus     | `{key: generator, values: bus}`                                                                                   | one row per generator |
| one-to-many, a bus and its generators      | the same table: `sum(p, by=gen_bus)` collects a bus's generators, `at(price, by=gen_bus)` reads a generator's bus | the same              |
| many-to-many, a generator on several buses | `{key: [generator, bus]}`, no `values:`                                                                           | no row twice          |
| one-to-one                                 | not a claim the language has: a key is one set of columns, and nothing checks the other side                      |                       |

A bare relation is a set of rows: no row twice, and nothing else claimed.
`sum` walks it with both ends named, and a bare `where` tests it. That is what
a many-to-many relation can say, and all it can say.

### Walks

A walk consumes one or more columns of a relation, produces one or more, and
joins on every other key column. The operand carries each joined dimension. The
result keeps it, and keeps every dimension the relation does not name.

`sum` consumes key columns and produces value columns. `at` consumes value
columns and produces the key.

`over=` names the column consumed and `into=` the column produced. Name a column
only where the relation offers two.

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
  zone_balance: # consumes generator, joins on period, produces zone: [generator, period] → [zone, period]
    dims: [zone, period]
    expression: sum(p, by=zone_of, over=generator) >= demand
  history: # consumes period, joins on generator, produces zone: [generator, period] → [generator, zone]
    dims: [generator, zone]
    expression: sum(p, by=zone_of, over=period) <= 100
  capped_revenue: # consumes zone, joins on period, produces generator: [zone, period] → [generator, period]
    dims: [generator, period]
    expression: at(price, by=zone_of, over=zone, into=generator) * p <= 1000
```

`zone_of` has one value column, `zone`. It is the only column `sum` can produce,
so `sum` leaves `into=zone` unsaid. It is the only column `at` can consume, so
`at` may leave `over=zone` unsaid too. `zone_of` has two key columns, and there
the call chooses: `sum` names the one it consumes, because `over=generator` and
`over=period` are different constraints, and `at` names the one it produces.
`period` is joined on either way. With one key column and one value column,
`sum(p, by=gen_bus)` and `at(price, by=gen_bus)` need neither keyword. A column
left out where the relation offers two is refused, and the message lists the
candidates:

```
sum(by=zone_of): 'zone_of' has 2 key columns (['generator', 'period']), and the call has to say which over= names.
```

`capped_revenue` reads the price of the zone this generator sat in that period.
The typesetter prints it as $`\mathrm{price}_{\mathrm{zone\_of}(g,\ e),e}`$,
and the joined `period` is the second subscript.

- **Either keyword takes a list.** `sum(p, by=gen_bt, into=[bus, technology])`
  lands on the product `bus × technology` in one join.
  `sum(p, by=zone_of, over=[generator, period])` consumes both key columns at
  once. `at(tech_cap, by=gen_bt, over=[bus, technology])` reads `tech_cap` at
  each generator's bus and technology together.
- **A produced dimension the operand already carries is joined on.** In
  `sum(load * p, by=gen_bus)` with `load[snapshot, bus]`, the walk produces
  `bus` and `load` already carries it. So each generator's term is read at the
  bus the generator sits on, and the sum lands there.
- **A value column that is not walked is not read.**
  `sum(f, by=ends, over=line, into=bus1)` reads `bus1` and ignores `bus0`
  ([roles](#roles)).
- **`by=[a, b]` is one grouping onto what `a` and `b` produce together.** Each
  relation is walked from its key to its value, so `over=` and `into=` have
  nothing to name. The relations consume the same dimension, and no two produce
  the same one.
- **`into=` needs a `by=`**, because a column belongs to a table. `over=`
  without a `by=` names a dimension, as in `sum(p, over=period)`.

Three refusals draw the line, and each message names the rewrite:

| refused                               | message                                                                                                                                                                                                                                                             |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `at` on a bare relation               | `at(by=connection): at reads one value per coordinate, and 'connection' is not single-valued in ['bus'] at the columns the operand fixes (['generator']) — its key is ['generator', 'bus']. Key the table by columns the read fixes, or read the other way.`        |
| a `sum` that consumes no key column   | `sum(by=zone_of): this sum walks to the key ['generator', 'period'], so each coordinate has one term and nothing is added up — that is a read, which is at()'s. Write at(..., by=zone_of, over=['zone'], into=['generator']), or sum toward a value column.`        |
| an operand missing a joined dimension | `at(by=zone_of) joins on ['period'] (columns ['period'] of 'zone_of'), which the expression does not carry (dims ['zone']). A relation is walked between two of its columns and read at the others — index the operand by them, or walk between different columns.` |

### Partitions

`shift(x, along=d, by=l)`, `sum_back(x, along=d, by=l)` and `position(d, by=l)`
walk the one key column over `d`, join on the other key columns, and group by
the value columns. The frame does not change: the group says which rows are
neighbours, and nothing lands anywhere.

`within=` names the value columns the group is made of where the table has
several. `shift(x, along=snapshot, by=cal, within=week)` walks within weeks of a
calendar declared once over `[snapshot, day, week]`, and a value column not
named is not read. The group may be two columns over one dimension, such as a
line's two buses, because a partition produces no dimension. `within=` naming a
key column is refused, and a bare relation partitions nothing.

A `where` string reads a relation too: a value column at its key, two columns
of one table compared, or a bare name that tests a row exists
([where strings](expressions.md#where-strings)).

### Roles

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
    expression: p == at(p, by=rep_of)
  weighted: # the snapshots a representative stands for, summed onto it
    dims: [snapshot]
    expression: sum(p, by=rep_of) <= 100
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

### How the map is supplied

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

## Dimension, relation or parameter?

Every column of data is one of the three. What decides which is what the math
does with the column, not what the column holds:

| The column…                                                                                                                           | is declared as                          | because                                                                                                                   |
| ------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| is an axis: something is indexed by it, or an aggregation lands terms on it                                                           | a `dimension`                           | its members are the coordinate set every table over it is reindexed onto                                                  |
| has one value per member of a dimension, or per tuple of several — a generator's bus, a line's two ends, a generator's zone by period | a `relation` with that `key`            | it is a map every operator walks, and its values are checked against the dimensions they name                             |
| relates members of two dimensions many-to-many, with nothing to weigh — which buses a generator may connect to                        | a bare `relation`, with no `values:`    | `sum` walks it with both ends named, and a bare `where` tests it. Nothing reads it, because there is no one value to read |
| relates members of two dimensions many-to-many, with a weight per pair — a link's efficiency to each bus, a cycle's lines             | a `parameter` over both                 | the weight is the data, its row set is the relation, and the aggregation is `sum(w * x, over=a)`                          |
| is a label set the model only selects on or counts within — a period, a season, a zone                                                | a `dimension`, and a `relation` onto it | its labels are checked, at the cost of one line and one table                                                             |
| scales terms — a coefficient, a bound, an offset                                                                                      | a `parameter` (`float` or `int`)        | arithmetic is over numbers ([dtype](declarations.md#parameters))                                                          |
| is a per-row attribute the math only selects on — a fuel, a constraint's sense                                                        | a `str` parameter                       | it names rows rather than scaling them, and no set is declared to check its values against                                |
| is a mask                                                                                                                             | a `bool` parameter                      | a bare name in a `where` is its own answer                                                                                |

Two rules follow. If `b` has one value per `a`, declare `b` as a **relation**
keyed by `a`, not as a dimension. Two dimensions that depend on each other,
declared as a `dims` product and cut back with a mask, are one relation.

Everything under `dimensions:` is an axis. A dimension is never legal where a
value belongs, because it is a coordinate space and not data. To use a
dimension's labels as data, declare a parameter over it.
`python -m math_spec check` advises on a declared dimension that nothing is
indexed by, nothing aggregates into and no relation has a column over
([errors](errors.md#what-advice-warns-about)).
