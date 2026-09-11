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

| Field         |                                                                                                                 |                |
| ------------- | --------------------------------------------------------------------------------------------------------------- | -------------- |
| `over`        | required — the dimension whose members carry the map                                                            |                |
| `into`        | required — the dimension its values are labels of, other than `over`                                            |                |
| `per`         | the dimensions the map is conditioned on, besides those two ([below](#maps-that-vary-along-a-second-dimension)) | default `[]`   |
| `description` | free text, never parsed                                                                                         | default `null` |

The target must be a declared dimension, and it must differ from `over`. The
values are checked against it when the data binds, which is the check that makes
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
lookup in the list must be `over:` the same dimension, and each must target a
different one. A member that either map leaves out belongs to no group.

Every lookup name joins the flat namespace, so a lookup may not shadow a
dimension, and that includes its own target. The map from `generator` onto `bus`
is called `gen_bus`, never a second `bus`.

### Maps that vary along a second dimension

`over:` alone gives every generator one zone for the whole model. A generator
whose bidding zone changes by period needs a second key, and `per:` names it:

```yaml
dimensions:
  generator: { dtype: str }
  zone: { dtype: str }
  period: { dtype: int }
lookups:
  zone_of: { over: generator, into: zone, per: [period] }
parameters:
  demand: { dims: [zone, period] }
variables:
  p: { foreach: [generator, period] }
constraints:
  zone_balance:
    foreach: [zone, period]
    expression: sum(p, by=zone_of) >= demand
```

`over:` is consumed, `into:` is produced, and each `per` dimension is joined on
and kept. So `sum(p, by=zone_of)` takes `p[generator, period]` to
`[zone, period]`, and `at(price, by=zone_of)` reads `price[zone, period]` back
at `[generator, period]`, which is the price of the zone this generator sat in
that period. Nothing changes at the call site. Every operator that takes a
lookup takes a conditioned one: `shift(by=)` and `position(by=)` group within
each `per` coordinate, and a `where` naming the lookup is read at them.

Four rules follow, and the loader decides each of them before any data binds:

- **Each `per` dimension is declared, and is neither `over` nor `into`.** A
  dimension named twice is refused as well.
- **The operand carries every `per` dimension.** The map varies along them, so
  there is no reading it at a coordinate that lacks them.
- **A `by=` list shares its `per` as it shares its `over`.** One grouping is one
  join.
- **Two lookups compared in a `where` share it.** Otherwise no row carries both.

### How the map is supplied

The map is a source key like any other, under the lookup's own name. It carries
two columns, each named after the dimension it holds: the `over` dimension, and
the target:

```python
sources = {
    'generator': ['g1', 'g2', 'g3'],
    'gen_bus': pl.DataFrame({'generator': ['g1', 'g2'], 'bus': ['north', 'south']}),
}
```

A partial map is exactly the rows it has: `g3` appears in no row, so `g3` sits
on no bus. A null in the value column is refused, because a missing row already
says the same thing. A key that matches no label of `over` is an error rather
than a new member.

A conditioned map carries one further key column per `per` dimension, named
after it, and is single-valued per `(over, *per)`. A generator in two zones in
one period is refused, where a `0`/`1` membership parameter says it legally and
silently.

Values are never inferred from the parameters that use the target. If they were,
a mistyped label would extend the label set instead of being rejected.

The map touches no table but its own, so you can add a lookup to a model the way
you add a parameter. The index of the `over` dimension may carry other columns,
but a column named after the lookup is refused rather than read.

## Dimension, lookup or parameter?

Every column of data is one of the three. What decides which is what the math
does with the column, not what the column holds:

| The column…                                                                            | is declared as                        | because                                                                                       |
| -------------------------------------------------------------------------------------- | ------------------------------------- | --------------------------------------------------------------------------------------------- |
| is an axis: something is indexed by it, or an aggregation lands terms on it            | a `dimension`                         | its members are the coordinate set every table over it is reindexed onto                      |
| has one value per member of a dimension and points at another — a generator's bus      | a `lookup` into that dimension        | it is a map that `sum(by=)` and `at(by=)` walk, and its values are checked against the target |
| is a label set the model only selects on or counts within — a period, a season, a zone | a `dimension`, and a `lookup` into it | the membership check is worth one line and one member list                                    |
| scales terms — a coefficient, a bound, an offset                                       | a `parameter` (`float` or `int`)      | arithmetic is over numbers ([dtype](declarations.md#parameters))                              |
| is a per-row attribute the math only selects on — a fuel, a constraint's sense         | a `str` parameter                     | it names rows rather than scaling them, and no set is declared to check its values against    |
| is a mask                                                                              | a `bool` parameter                    | a bare name in a `where` is its own answer                                                    |

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
