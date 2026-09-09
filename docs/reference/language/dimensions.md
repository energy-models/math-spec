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

A lookup is how the network's wiring stays in the data. Which bus each generator
sits on, which two buses each line joins, which period a snapshot falls in: each
is a lookup table, and the file holds no adjacency matrix.

Declare each lookup under its own name. `over:` names the dimension whose
members carry the value, and `into:` names the dimension the values are labels
of. [`sum(by=)` and `at(by=)`](operators.md) land terms on that target
dimension:

```yaml
dimensions:
  bus: { dtype: str }
  generator: { dtype: str }
  line: { dtype: str }
  snapshot: { dtype: int }
  period: { dtype: int }
lookups:
  gen_bus: { over: generator, into: bus }
  line_from: { over: line, into: bus } # two lookups onto one dimension
  line_to: { over: line, into: bus }
  period_of: { over: snapshot, into: period }
```

| Field         |                                                                                                                                        |                |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------- | -------------- |
| `over`        | required — the map's key dimensions: one, or a list in the order the table carries them ([below](#keyed-by-several-dimensions))        |                |
| `into`        | required — the dimension its values are labels of; one of the keys, where the map is [into its own dimension](#into-its-own-dimension) |                |
| `description` | free text, never parsed                                                                                                                | default `null` |

The target must be a declared dimension. It may be one of the keys, where the
map goes [into its own dimension](#into-its-own-dimension). The values are
checked against the target when the data binds, which is the check that makes
`sum(by=)` safe.

That check is also why a label set the model only ever _selects_ on is declared
as a dimension all the same. Nothing above is indexed by `period`; a declaration
selects on it with `where: "period_of == 1"`
([where strings](expressions.md#where-strings)).

A partial lookup is legal. A label the map leaves out belongs to no group, so a
generator can sit on no bus and a line can have one open end. `sum(by=)` places
such a label's terms nowhere. A value that names no label of the target is an
error.

Several lookups may group at once. `sum(x, by=[gen_bus, gen_tech])` groups
through both maps in one reduction and lands on `bus` and `technology`. Every
lookup in the list must walk the same dimension, and each must target a
different one. A member that either map leaves out belongs to no group.

Every lookup name joins the flat namespace, so a lookup may not shadow a
dimension, and that includes its own target. The map from `generator` onto `bus`
is called `gen_bus`, never a second `bus`.

### Keyed by several dimensions

A map keyed by one dimension gives every generator one zone for the whole
model. A generator whose bidding zone changes by period needs a second key, and
`over:` takes a list of them:

```yaml
dimensions:
  generator: { dtype: str }
  zone: { dtype: str }
  period: { dtype: int }
lookups:
  zone_of: { over: [generator, period], into: zone }
parameters:
  demand: { dims: [zone, period] }
variables:
  p: { foreach: [generator, period] }
constraints:
  zone_balance:
    foreach: [zone, period]
    expression: sum(p, by=zone_of.generator) >= demand
```

A call walks one key and joins on the rest. The dot says which:
`by=zone_of.generator` consumes `generator`, produces `zone`, and joins on
`period`. So `sum(p, by=zone_of.generator)` takes `p[generator, period]` to
`[zone, period]`, and `at(price, by=zone_of.generator)` reads
`price[zone, period]` back at `[generator, period]`, which is the price of the
zone this generator sat in that period. The same table walked along its other
key is a different sum: `sum(p, by=zone_of.period)` takes `p` to
`[generator, zone]`, each generator's output over the periods it spent in each
zone.

Six rules follow, and the loader decides each of them before any data binds:

- **The dot names a key.** Write it wherever the lookup has more than one key.
  Without it the call is refused, because the operator cannot know which key it
  consumes. With one key the dot is redundant and legal, so `by=gen_bus` and
  `by=gen_bus.generator` are the same call.
- **The operand carries every key but the one walked.** The map is read at
  those keys, so there is no reading it at a coordinate that lacks them.
- **The walked key is the walked dimension.** `shift(x, over=d, by=l.k)`,
  `sum_back(x, over=d, by=l.k)` and `position(d, by=l.k)` need `k` to be `d`.
  Each groups the rows of `d` within one coordinate of the other keys.
- **A `by=` list walks one dimension.** `by=[a.k, b.k]` is one grouping, so
  every lookup in it names the same key dimension. Each joins on its own other
  keys.
- **A `where` reads every key.** `zone_of == 'north'`, a bare `zone_of` and
  `zone_of != area_of` are filters on the key table, so the frame carries all of
  a lookup's keys, and two lookups compared carry the same keys.
- **Each key is a declared dimension, named once.** The target is not one of
  them.

### Into its own dimension

A map may land in the dimension it is keyed by. The representative snapshot is
the case: every snapshot names the one that stands for it, which is how a
clustered year runs on a few typical days.

```yaml
dimensions:
  snapshot: { dtype: int }
lookups:
  rep_of: { over: snapshot, into: snapshot }
variables:
  p: { foreach: [snapshot] }
constraints:
  representative:
    foreach: [snapshot]
    expression: p == at(p, by=rep_of) # every snapshot takes its representative's value
  weighted:
    foreach: [snapshot]
    expression: sum(p, by=rep_of) <= 100 # the snapshots a representative stands for, summed onto it
```

No rule changes. The walked key is consumed and the target is produced, and
here they are the same dimension, so `sum(by=)` and `at(by=)` both leave the
frame as it was. A snapshot that no other snapshot names is an empty group, and
contributes nothing. `shift(by=rep_of)` walks inside each representative's
group, and `position(snapshot, by=rep_of)` counts within it. The table carries
`snapshot` and `rep_of`, under the naming rule every lookup follows.

A self-map is directional, because a lookup is a function: one value per key,
and the declaration says which way the arrow points. `rep_of` sends every
snapshot to its representative and never the other way. The two verbs are the
two walks of that one arrow, as they are for every lookup. `at` reads along it,
so each snapshot takes its representative's value. `sum` reads against it, so
each representative collects the snapshots that point at it. The inverse of a
many-to-one map is one-to-many, which is reachable as a grouping and never as a
function. For a bijection, a successor map `next_of`, the two walks are the two
directions outright. Two steps along the arrow are two nested calls,
`at(at(x, by=rep_of), by=rep_of)`, because the frame is unchanged at each. What
has no direction is not a lookup: an undirected neighbour relation between buses
is a parameter over `[bus, bus]`, as every
[many-to-many relation](#dimension-lookup-or-parameter) is.

Selecting the representatives themselves, the rows where the map is the
identity, is not a comparison the language has: a lookup is never compared to a
dimension. Declare a `bool` parameter for them.

### How the map is supplied

The map is a source key like any other, under the lookup's own name. It carries
one column per key, each named after its dimension, and the value column, named
after the lookup:

```python
sources = {
    'generator': ['g1', 'g2', 'g3'],
    'gen_bus': pl.DataFrame({'generator': ['g1', 'g2'], 'gen_bus': ['north', 'south']}),
}
```

A partial map is exactly the rows it has: `g3` appears in no row, so `g3` sits
on no bus. A null in the value column is refused, because a missing row already
says the same thing. A key that matches no label of `over` is an error rather
than a new member.

A map with several keys is single-valued per key tuple. A generator in two zones in one period is
refused, where a `0`/`1` membership parameter says it legally and silently.

Values are never inferred from the parameters that use the target. If they were,
a mistyped label would extend the label set instead of being rejected.

The map touches no table but its own, so you can add a lookup to a model the way
you add a parameter. The index of the `over` dimension may carry other columns,
but a column named after the lookup is refused rather than read.

## Dimension, lookup or parameter?

Every column of data is one of the three. What decides which is what the math
does with the column, not what the column holds:

| The column…                                                                                                                               | is declared as                        | because                                                                                                                               |
| ----------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| is an axis: something is indexed by it, or an aggregation lands terms on it                                                               | a `dimension`                         | its members are the coordinate set every table over it is reindexed onto                                                              |
| has one value per member of a dimension, or per tuple of several, and points at another — a generator's bus, a generator's zone by period | a `lookup` into that dimension        | it is a map that `sum(by=)` and `at(by=)` walk, and its values are checked against the target                                         |
| relates members of two dimensions many-to-many — a link's several buses with their efficiencies, a cycle's lines                          | a `parameter` over both               | `bool` where it only selects, numeric where it weights. The aggregation is `sum(w * x, over=a)`, and a pair the table lacks is absent |
| is a label set the model only selects on or counts within — a period, a season, a zone                                                    | a `dimension`, and a `lookup` into it | the membership check is worth one line and one member list                                                                            |
| scales terms — a coefficient, a bound, an offset                                                                                          | a `parameter` (`float` or `int`)      | arithmetic is over numbers ([dtype](declarations.md#parameters))                                                                      |
| is a per-row attribute the math only selects on — a fuel, a constraint's sense                                                            | a `str` parameter                     | it names rows rather than scaling them, and no set is declared to check its values against                                            |
| is a mask                                                                                                                                 | a `bool` parameter                    | a bare name in a `where` is its own answer                                                                                            |

**A many-to-many relation is a parameter, weighted or not.** Pairs alone are a
`bool` parameter, written `connection: {dims: [entity, bus], dtype: bool}` and
read with `where: connection`. Pairs with a weight are a numeric one, and the
aggregation needs no lookup: `sum(efficiency * p, over=entity)` lands on `bus`,
because `efficiency[entity, bus]` has a row exactly where the pair exists. A
lookup is the single-valued case, where the language checks a claim a parameter
cannot make.

Two rules follow from the table. If `b` has one value per `a`, then `b` is a
**lookup** over `a`, and not a dimension: a `foreach` product over two
dimensions that depend on each other, cut back with a mask, is the shape that
`lookups` replaces.

And everything under `dimensions:` is an axis. A dimension is never legal where
a value belongs, because it is a coordinate space and not data. To use a
dimension's coordinates as data, declare a parameter over it.
`python -m math_spec check` advises on a declared dimension that nothing is
indexed by, nothing aggregates into and no lookup targets
([errors](errors.md#what-advice-warns-about)).
