<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Dimensions and lookups

A **dimension** is an axis of the model, such as `snapshot` or `generator`.
Declarations are indexed by it, and `sum` reduces along it.

A **lookup** is a named map out of a dimension: one value for each of its
members. A generator's bus is a lookup, and so is a snapshot's period.

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
   `p_max` for its values, never for its list of generators, and it does not
   treat `gen_bus` as the list either. If a declaration uses `generator` and
   no `generator` table arrives, the engine raises an error that names
   `generator`. It does not build an empty axis, because an empty axis would
   silently delete every row indexed by it. A declared dimension that no
   declaration uses needs no table.
2. **The members keep the order the table gives them.** The engine does not
   sort them, whether they are strings, integers or dates.
   [`shift`](operators.md#shift), `sum_back` and `position()` all count along
   this order, so an engine that sorted `snapshot` would give
   `shift(p, over=snapshot, offset=1)` a different meaning. To get a
   particular order, write the table in that order.
3. **A table has each coordinate at most once.** Two rows for `snapshot == 3`
   is an error that names `3`. The engine does not keep the last, keep the
   first, or add them. _At most_ once, not exactly once: a coordinate with no
   row is [absence](absence.md), and absence is how a model masks. A lookup's
   table obeys the same rule.

Every dimension has one list of members, and every parameter is lined up against
it when the data binds. So if `load` has 8760 snapshots and `price` has 8759, the
engine raises an error rather than build a model with one snapshot dropped.

## `lookups`

A lookup is what makes topology _data_: a generator sits on a bus, a line has
two endpoints, a snapshot falls in a period, and no adjacency matrix or
hand-written join appears anywhere. A lookup is a **relation between
dimensions** — a table with one column per dimension it relates — and `key:`
is the claim that makes it a map: one row per key tuple, so the other columns
are a function of the key. The declaration fixes no direction; the operator
that walks the table says which column it consumes and which it produces.

```yaml
dimensions:
  bus: { dtype: str }
  generator: { dtype: str }
  line: { dtype: str }
  snapshot: { dtype: int }
  period: { dtype: int }
lookups:
  gen_bus: { over: [generator, bus], key: generator } # each generator on one bus
  line_from: { over: [line, bus], key: line } # two lookups onto one dimension
  line_to: { over: [line, bus], key: line }
  period_of: { over: [snapshot, period], key: snapshot }
  connection: { over: [generator, bus] } # no key: a generator may connect to several buses
```

| Field         |                                                                                                                                      |                |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------ | -------------- |
| `over`        | required — the columns: a list of dimensions, or a mapping of column name to dimension where two columns share one ([roles](#roles)) |                |
| `into`        | not a field: a lookup declares no direction                                                                                          |                |
| `key`         | the columns a row is identified by, one name or a list; omitted, the table is a bare relation ([below](#the-key-is-the-claim))       | default none   |
| `description` | free text, never parsed                                                                                                              | default `null` |

Every column is over a declared dimension, and its values are checked against
that dimension's labels once data is bound — the check that makes `sum(by=)`
safe, and the reason a label set the model only ever _selects_ on is declared
as a dimension all the same: nothing is indexed by `period` above, and
`where: "period_of == 1"` ([where strings](expressions.md#where-strings)) is
how a declaration selects on it. A lookup has at least two columns; a label on
one dimension is a parameter over it.

### The key is the claim

`key: generator` says the table holds **one row per generator** — that the
other column is a function of it — and it is checked at bind: a generator on
two buses is refused, where a `0`/`1` membership parameter would have said so
legally and silently ([#161](https://github.com/energy-models/math-spec/issues/161)).
The columns the key determines are the lookup's **value columns**.

The key is also what decides which walks the table admits:

| the walk                        | needs                                                                      | because                                                       |
| ------------------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------- |
| `sum(x, by=l, from=a, to=b)`    | nothing                                                                    | a sum lands every row it finds; several per coordinate add up |
| `at(x, by=l, from=a, to=b)`     | a key inside the columns the operand fixes — `b` and the columns joined on | a read is one value per coordinate, or it is not a read       |
| `shift`, `sum_back`, `position` | a key column over the dimension walked                                     | a coordinate is in one group, or it has no neighbour          |
| `where: "l == 'north'"`         | a key, and the column compared a value column                              | a comparison is one value per coordinate                      |
| `where: l` (bare)               | nothing                                                                    | a row exists, or it does not                                  |

A bare relation — no `key:` — is walked by `sum` alone, with both ends named,
and tested by a bare `where`. That is what a many-to-many relation can say,
and all it can say.

### A walk names its ends

Every operator that takes `by=` walks the table between two of its columns:
`from=` the column **consumed**, `to=` the column **produced**, and every other
**key** column **joined on** — the operand carries its dimension and the
result keeps it. A value column not walked is not read: `ends` below, walked
from `line` to `bus1`, joins on nothing. A bare relation's columns are all
key, so all of them but the two walked are joined on.

```yaml
dimensions:
  generator: { dtype: str }
  zone: { dtype: str }
  period: { dtype: int }
lookups:
  zone_of: { over: [generator, period, zone], key: [generator, period] } # a generator's zone, per period
parameters:
  demand: { dims: [zone, period] }
  price: { dims: [zone, period] }
variables:
  p: { foreach: [generator, period] }
constraints:
  zone_balance: # p[generator, period] → [zone, period]
    foreach: [zone, period]
    expression: sum(p, by=zone_of, from=generator, to=zone) >= demand
  history: # p[generator, period] → [generator, zone]: the same table, walked from its other key column
    foreach: [generator, zone]
    expression: sum(p, by=zone_of, from=period, to=zone) <= 100
  capped_revenue: # price[zone, period] → [generator, period]: the price of the zone this generator sat in that period
    foreach: [generator, period]
    expression: at(price, by=zone_of, from=zone, to=generator) * p <= 1000
```

**What the declaration decides, the call may leave unsaid.** Where the key has
one column and the key determines one column, the walk is the arrow the key
draws, and `sum(p, by=gen_bus)` and `at(price, by=gen_bus)` are complete:
`sum` consumes the key and produces the value, `at` consumes the value and
produces the key. Where a side has several candidates — two key columns, two
value columns — the call names it, and the refusal lists the candidates.
`zone_of` above has two key columns, so `sum` names `from=`, while `to=zone`
could have been left out.

**A partition walks a key column and groups by the value columns.**
`shift(x, over=d, by=l)`, `sum_back(x, over=d, by=l)` and
`position(d, by=l)` take the one key column over `d`, or `from=` says which
where there are two; the other key columns are joined on, and the group is the
value tuple.

The rules, each decided at load with a refusal naming the rewrite:

- **`from=` and `to=` name two different columns of the lookup `by=` names**,
  and are refused without a `by=`.
- **The operand carries every joined column's dimension, each once.** The map
  is read at the key columns not walked, so there is no reading it at a
  coordinate that lacks them; two joined columns over one dimension have
  nothing to tell apart.
- **A produced dimension the operand already carries is joined on too.**
  `sum(load * p, by=gen_bus)` with `load[snapshot, bus]` restricts each term to
  the row where the generator's bus is the row's bus — a masked sum, which is
  what the join says.
- **`at` reads one value.** Its key lies inside `to=` and the joined columns,
  or the call is refused; a bare relation is never read by `at`.
- **A partition walks a key column over the dimension it walks.** A bare
  relation partitions nothing.
- **A `by=` list walks each lookup by its declared arrow.** `by=[a, b]` is one
  grouping, so `from=` and `to=` have nothing to name; every lookup in it
  consumes the same dimension, joins on its own other columns, and no two
  produce the same dimension.
- **A `where` comparison reads a value column of a keyed lookup at its key.**
  `zone_of == 'north'` reads the one value column; `ends.bus0 != ends.bus1`
  names the columns where there are several. The frame carries the key's
  dimensions, and two lookups compared have keys over the same dimensions and
  columns over one. A bare name — `where: gen_bus` — tests that a row exists:
  at the key for a keyed lookup, at every column for a bare relation.
- **Every column is over a declared dimension, every column name is distinct,
  the key names columns the lookup has, and does not name all of them.**

**Every lookup name joins the flat namespace**, so a lookup may not shadow a
dimension. `generator`'s map onto `bus` is `gen_bus`, never a second `bus`.

### Roles

A list under `over:` names each column after its dimension. Two columns over
one dimension need names of their own, and the mapping form gives them:

```yaml
lookups:
  ends: { over: { line: line, bus0: bus, bus1: bus }, key: line } # a line's two ends, one table
  rep_of: { over: { snapshot: snapshot, rep: snapshot }, key: snapshot } # the representative snapshot
```

`sum(f, by=ends, from=line, to=bus1) - sum(f, by=ends, from=line, to=bus0)`
is the nodal balance through one table where two lookups did it before, and
`where: "ends.bus0 != ends.bus1"` excludes a self-loop by comparing two of its
columns.

`rep_of` relates a dimension to itself, which is how a clustered year is run
on a few typical days: every snapshot names the one that stands for it.
Nothing changes in the rules — `snapshot` is consumed and `rep` produced, both
over one dimension, so the frame is unchanged through `sum(by=)` and `at(by=)`
alike:

```yaml
constraints:
  representative: # every snapshot takes its representative's value
    foreach: [snapshot]
    expression: p == at(p, by=rep_of)
  weighted: # the snapshots a representative stands for, summed onto it
    foreach: [snapshot]
    expression: sum(p, by=rep_of) <= 100
```

**A self-map is directional exactly as far as its key says.** `key: snapshot`
makes `rep` a function of `snapshot`, so the arrow runs from a snapshot to its
representative: `at` reads along it and `sum` collects against it, the inverse
of a many-to-one map being one-to-many, reachable as a grouping and never as
a function. Two steps along the arrow are two nested calls. Without a key the
same two columns are an undirected relation — a neighbour table — which `sum`
walks either way and nothing reads. Selecting the representatives themselves,
the rows where the map is the identity, is not a comparison the language has,
since a lookup is never compared to a dimension; declare a `bool` parameter
for them.

### How the map is supplied

`gen_bus` is a source key like any other, carrying one column per column
declared, named after the column:

```python
sources = {
    'generator': ['g1', 'g2', 'g3'],
    'gen_bus': pl.DataFrame({'generator': ['g1', 'g2'], 'bus': ['north', 'south']}),
}
```

**A partial map is the rows it has.** `g3` is in no row, so `g3` sits on no
bus — absence is the absent row, exactly as it is for a parameter, and a null
in any column is refused for saying both at once. A keyed table holds one row
per key tuple, and a value matching no label of its column's dimension is a
typo rather than a new member. Values are never inferred from the parameters
that use a dimension: inferring would let a mistyped label extend the label
set instead of being rejected.

Supplying it this way touches no table but its own, which is what a caller who
did not generate the index needs: a model can be extended with a lookup the
same way it can be extended with a parameter. **A column of a dimension's index
named after a lookup is refused** rather than read — an index may carry any
other extra, and this one would be a map read by accident.

## Dimension, lookup or parameter?

Every column of data is one of the three. What decides which is what the math
does with the column, not what the column holds:

| The column…                                                                                                                           | is declared as                              | because                                                                                                                   |
| ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| is an axis: something is indexed by it, or an aggregation lands terms on it                                                           | a `dimension`                               | its members are the coordinate set every table over it is reindexed onto                                                  |
| has one value per member of a dimension, or per tuple of several — a generator's bus, a line's two ends, a generator's zone by period | a `lookup` with that `key`                  | it is a map every operator walks, and its values are checked against the dimensions they name                             |
| relates members of two dimensions many-to-many, with nothing to weigh — which buses a generator may connect to                        | a `lookup` with no key                      | `sum` walks it with both ends named, and a bare `where` tests it. Nothing reads it, because there is no one value to read |
| relates members of two dimensions many-to-many, with a weight per pair — a link's efficiency to each bus, a cycle's lines             | a `parameter` over both                     | the weight is the data, its row set is the relation, and the aggregation is `sum(w * x, over=a)`                          |
| is a label set the model only selects on or counts within — a period, a season, a zone                                                | a `dimension`, and a keyed `lookup` onto it | the membership check is worth one line and one member list                                                                |
| scales terms — a coefficient, a bound, an offset                                                                                      | a `parameter` (`float` or `int`)            | arithmetic is over numbers ([dtype](declarations.md#parameters))                                                          |
| is a per-row attribute the math only selects on — a fuel, a constraint's sense                                                        | a `str` parameter                           | it names rows rather than scaling them, and no set is declared to check its values against                                |
| is a mask                                                                                                                             | a `bool` parameter                          | a bare name in a `where` is its own answer                                                                                |

Two rules follow from the table. If `b` has one value per `a`, then `b` is a
**lookup** keyed by `a`, and not a dimension: a `foreach` product over two
dimensions that depend on each other, cut back with a mask, is the shape that
`lookups` replaces.

And everything under `dimensions:` is an axis. A dimension is never legal where
a value belongs, because it is a coordinate space and not data. To use a
dimension's coordinates as data, declare a parameter over it.
`python -m math_spec check` advises on a declared dimension that nothing is
indexed by, nothing aggregates into and no lookup has a column over
([errors](errors.md#what-advice-warns-about)).
