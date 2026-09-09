<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Dimensions and lookups

A **dimension** is an axis of the model — something is indexed by it, or an
aggregation lands terms on it. A **lookup** is a named single-valued map out of
a dimension: a generator's bus, a snapshot's period. The two are different
things and the file keeps them apart.

```yaml
dimensions:
  snapshot: { dtype: int }
  generator: { dtype: str }
```

Every dimension named anywhere in the file must be declared here.

| Field         |                                   |                |
| ------------- | --------------------------------- | -------------- |
| `dtype`       | `float`, `int`, `str`, `datetime` | default `str`  |
| `description` | free text, never parsed           | default `null` |

**A declaration says the axis exists and what its coordinates are typed as,
never which coordinates there are.** The members are data and arrive with it —
a file naming them would be a second place to look, and a real model's
generators, buses and snapshots are a table rather than a list somebody keeps
in step by hand.

**One master coordinate set per dimension, resolved before any data binds.**
Every parameter is reindexed onto it, so two tables that disagree about which
snapshots exist is an error at load time rather than a silently truncated
model. Which coordinates those are, and in what order they stand, is data's to
say — and the three rules below say how it says it.

### Binding is the language's, even though the data is not

The file declares an axis; the data supplies its members. Between those two
sentences sit three facts that decide **which model a file and a table make
together** — and a consumer answering any of them differently would build a
different model from the same two inputs. So they are the language's, and a
consumer implements them rather than choosing them.

**The dimension's own source supplies its members.** They are read from the key
named after the dimension, and from nothing else: a parameter's table is read
for values, never for labels, and a lookup's map is not a claim about which
members exist. A dimension a declaration reaches and nothing supplies is an
error naming it, not an empty axis — an axis with no members would delete every
row indexed by it, silently. A declared dimension no declaration reaches asks
nothing of the data, and needs no source.

**Their order is the order that source gives them**, first row first. It is not
sorted, and nothing about a label's type changes that: an axis of strings, of
integers and of timestamps are all read in the order they arrive. The order is
observable — [`shift`](operators.md#shift), `sum_back` and `position()` all walk
it — so a consumer that sorted would answer `shift(p, over=snapshot, offset=1)`
with a different row, and the file could not tell you which it meant. A model
wanting a particular order states it in the source it hands over.

**One row per coordinate.** A parameter's table carries each coordinate of its
`dims` at most once, and a second row for one coordinate is an error naming the
coordinate — never a last-wins, a first-wins or a sum, each of which is a
defensible reading, which is exactly why the file may not leave the choice
open. A lookup's map obeys the same rule one axis over, and says so under
`lookups` below: it is single-valued per label of `over`.

_At most_ once, rather than exactly once: a coordinate with no row is
[absence](absence.md), which is how a model masks.

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
one dimension is a parameter over it. A column named like a dimension is over
that dimension, so `over: {bus: line}` is refused.

### The key is the claim

`key:` names the columns that are unique together. `key: generator` says the
generator column holds each label once: the table has **one row per
generator**, so the other column is a function of it. `key: [generator, period]`
says the pair holds each combination once. Neither column need be unique on its
own: a generator appears once per period, and a period once per generator.
The claim is checked at bind: a generator on two buses is refused, where a
`0`/`1` membership parameter would have said so legally and silently
([#161](https://github.com/energy-models/math-spec/issues/161)). The columns
the key determines are the lookup's **value columns**. A key has one column per
dimension: it is read at its dimensions, and no frame carries a dimension
twice, so `key: [bus0, bus1]` is refused where both are over `bus`.

Each cardinality is one declaration, and the key is the side that is one:

| to say                                     | write                                                                                                             | checked at bind                       |
| ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- | ------------------------------------- |
| many-to-one, each generator on one bus     | `{over: [generator, bus], key: generator}`                                                                        | one row per generator                 |
| one-to-many, a bus and its generators      | the same table: `sum(p, by=gen_bus)` collects a bus's generators, `at(price, by=gen_bus)` reads a generator's bus | the same                              |
| many-to-many, a generator on several buses | `{over: [generator, bus]}`, no key                                                                                | nothing: a row exists, or it does not |
| one-to-one                                 | not a claim the language has: a key is one set of columns, so the other side stays many                           |                                       |

The key is also what decides which walks the table admits:

| the walk                        | needs                                                                                     | because                                                       |
| ------------------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| `sum(x, by=l, from=a, into=b)`  | nothing                                                                                   | a sum lands every row it finds; several per coordinate add up |
| `at(x, by=l, from=a, into=b)`   | a key inside the columns the operand fixes — the `into` columns and the columns joined on | a read is one value per coordinate, or it is not a read       |
| `shift`, `sum_back`, `position` | a key column over the dimension walked                                                    | a coordinate is in one group, or it has no neighbour          |
| `where: "l == 'north'"`         | a key, and the column compared a value column                                             | a comparison is one value per coordinate                      |
| `where: l` (bare)               | nothing                                                                                   | a row exists, or it does not                                  |

A bare relation — no `key:` — is walked by `sum` alone, with both ends named,
and tested by a bare `where`. That is what a many-to-many relation can say,
and all it can say.

### A walk names its ends

Every operator that takes `by=` walks the table between two of its columns:
`from=` the column **consumed**, `into=` the column **produced**, and every other
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
    expression: sum(p, by=zone_of, from=generator, into=zone) >= demand
  history: # p[generator, period] → [generator, zone]: the same table, walked from its other key column
    foreach: [generator, zone]
    expression: sum(p, by=zone_of, from=period, into=zone) <= 100
  capped_revenue: # price[zone, period] → [generator, period]: the price of the zone this generator sat in that period
    foreach: [generator, period]
    expression: at(price, by=zone_of, from=zone, into=generator) * p <= 1000
```

**What the declaration decides, the call may leave unsaid.** Where the key has
one column and the key determines one column, the walk is the arrow the key
draws, and `sum(p, by=gen_bus)` and `at(price, by=gen_bus)` are complete:
`sum` consumes the key and produces the value, `at` consumes the value and
produces the key. Where a side has several candidates — two key columns, two
value columns — the call names it, and the refusal lists the candidates.
`zone_of` above has two key columns, so `sum` names `from=`, while `into=zone`
could have been left out.

**A partition walks a key column and groups by the value columns.**
`shift(x, over=d, by=l)`, `sum_back(x, over=d, by=l)` and
`position(d, by=l)` take the one key column over `d`; the other key columns
are joined on, and the group is the value tuple. `into=` names the value columns the group is made of
where the table has several: `shift(x, over=snapshot, by=cal, into=week)`
walks within weeks of a calendar declared once over `[snapshot, day, week]`,
and a value column not named is not read.

The rules, each decided at load with a refusal naming the rewrite:

- **`from=` and `into=` name columns of the lookup `by=` names**, one each or a
  list each, no column on both sides, and are refused without a `by=`.
  `sum(p, by=gen_bt, into=[bus, technology])` lands one table with two value
  columns on the product `bus × technology` in one join;
  `sum(p, by=zone_of, from=[generator, period])` consumes both key columns
  at once, which is `sum(sum(p, by=zone_of, from=generator), over=period)`
  said once; `at(tech_cap, by=gen_bt, from=[bus, technology])` reads a
  two-column slot at each generator.
- **The operand carries every joined column's dimension, each once.** The map
  is read at the key columns not walked, so there is no reading it at a
  coordinate that lacks them; two joined columns over one dimension have
  nothing to tell apart.
- **A produced dimension the operand already carries is joined on too.**
  `sum(load * p, by=gen_bus)` with `load[snapshot, bus]` restricts each term to
  the row where the generator's bus is the row's bus — a masked sum, which is
  what the join says.
- **`at` reads one value.** Its key lies inside `into=` and the joined columns,
  or the call is refused; a bare relation is never read by `at`.
- **A partition walks the one key column over the dimension it walks, and
  groups by the value columns `into=` names** — all of them where it names
  none. `into=` naming a key column is refused, and a bare relation
  partitions nothing. The group may hold two columns over one dimension, a
  pair of buses say: a partition lands nothing, so nothing needs the
  dimension twice.
- **A `by=` list walks each lookup by its declared arrow.** `by=[a, b]` is one
  grouping, so `from=` and `into=` have nothing to name; every lookup in it
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

`sum(f, by=ends, from=line, into=bus1) - sum(f, by=ends, from=line, into=bus0)`
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

### The map is supplied under the lookup's own name

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

Every column of data is one of the three, and the block it goes under is
decided by what the math does with it rather than by what it holds:

| The column…                                                                                                                              | is declared as                              | because                                                                                                                       |
| ---------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| is an axis: something is indexed by it, or an aggregation lands terms on it                                                              | a `dimension`                               | its members are the coordinate set every table over it is reindexed onto                                                      |
| is single-valued per member of a dimension, or per tuple of several — a generator's bus, a line's two ends, a generator's zone by period | a `lookup` with that `key`                  | it is a map every operator walks, whose values are checked against the set they name and whose cardinality is checked at bind |
| relates members of dimensions many-to-many, with nothing to weigh — which buses a generator may connect to                               | a `lookup` with no key                      | `sum` walks it with both ends named, a bare `where` tests it, and nothing reads it, since there is no one value to read       |
| relates members of dimensions many-to-many, with a weight per pair — a link's efficiency to each bus, a cycle's lines                    | a `parameter` over both                     | the weight is the data, its row set is the relation, and the aggregation is `sum(w * x, over=a)`                              |
| is a label set the model selects on or counts within, and nothing is indexed by it — a period, a season, a zone                          | a `dimension`, and a keyed `lookup` onto it | a set worth a `where` or a `position(by=)` is worth the membership check; the dimension costs one line and one member list    |
| scales terms — a coefficient, a bound, an offset                                                                                         | a `parameter` (`float` or `int`)            | arithmetic is over numbers ([dtype](declarations.md#parameters))                                                              |
| is a per-row attribute the math only ever selects on — a fuel, a constraint's sense                                                      | a `str` parameter                           | it names rows rather than scaling them, and no set is declared for its values to be checked against                           |
| is a mask                                                                                                                                | a `bool` parameter                          | a bare name in a `where` is its own answer                                                                                    |

Two rules the table follows from. **If `b` is single-valued per `a`, then `b`
is a lookup keyed by `a`, not a dimension**: a `foreach` product over
functionally dependent dims, cut back by a mask, is exactly the shape
`lookups` exists to replace. And **everything under `dimensions:` is a set** —
a dimension is never legal in a value position, it is a coordinate space
rather than data, and `check` warns about a declared dimension that nothing is
indexed by, nothing aggregates into and no lookup has a column over. To use a
dimension's coordinates _as data_, declare a parameter over it.
