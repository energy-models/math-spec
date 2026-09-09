<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Dimensions and lookups

A **dimension** is an axis of the model: something is indexed by it, or an
aggregation lands terms on it. A **lookup** is a named single-valued map out of
a dimension: a generator's bus, a snapshot's period. This page is what each
declares, and the three rules by which data supplies a dimension's members.

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

**A declaration says the axis exists and how its coordinates are typed, never
which coordinates there are.** The members are data and arrive with it.

**One master coordinate set per dimension, resolved before any data binds.**
Every parameter is reindexed onto it, so two tables that disagree about which
snapshots exist is a load error rather than a truncated model. The three rules
below say how data supplies that set and its order.

### Binding is the language's, even though the data is not

Three facts decide which model a file and a table make together. A consumer
implements them; it does not choose them.

**The dimension's own source supplies its members.** They are read from the
key named after the dimension, and from nothing else: a parameter's table is
read for values, never for labels, and a lookup's map is not a claim about
which members exist. A dimension a declaration reaches and nothing supplies is
an error naming it, never an empty axis. A declared dimension no declaration
reaches needs no source.

**Their order is the order the source gives them**, first row first. Nothing
sorts them, whatever the label type: strings, integers and timestamps all
stand in the order they arrive. [`shift`](operators.md#shift), `sum_back` and
`position()` all walk that order. A model wanting a particular order states it
in the source it hands over.

**One row per coordinate.** A parameter's table carries each coordinate of its
`dims` at most once. A second row for one coordinate is an error naming the
coordinate: never last-wins, first-wins or a sum. A lookup's map obeys the same
rule: it is single-valued per label of `over`.

_At most_ once, rather than exactly once: a coordinate with no row reads as the
value that contributes nothing ([absence](absence.md)).

## `lookups`

A lookup is declared under its own name, `over:` the dimension whose members
carry it and `into:` the dimension its values are labels of — which is what
[`sum(by=)` and `at(by=)`](operators.md) land terms on. Topology is a lookup: a
generator sits on a bus, a line has two endpoints, a snapshot falls in a
period, and no adjacency matrix or hand-written join appears anywhere:

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

| Field         |                                                                      |                |
| ------------- | -------------------------------------------------------------------- | -------------- |
| `over`        | required — the dimension whose members carry the map                 |                |
| `into`        | required — the dimension its values are labels of, other than `over` |                |
| `description` | free text, never parsed                                              | default `null` |

The target must be a declared dimension other than `over`. Values are checked
against it once data is bound — the check that makes `sum(by=)` safe, and the
reason a label set the model only ever _selects_ on is declared as a dimension
all the same: nothing is indexed by `period` above, and
`where: "period_of == 1"` ([where strings](expressions.md#where-strings)) is
how a declaration selects on it.

**A partial lookup is legal.** A label with no row in the map belongs to no
group (a generator on no bus, a line with one open end), and `sum(by=)` places
its terms nowhere. A value naming no label of the target is an error.

**Several at once**: `sum(x, by=[gen_bus, gen_tech])` groups through both maps
in one reduction, landing on `bus` _and_ `technology`. Every lookup in the list
must be `over:` the same dimension and target a different one. A member either
map leaves out belongs to no group.

**Every lookup name joins the flat namespace**, so a lookup may not shadow a
dimension — its own target included. `generator`'s map onto `bus` is `gen_bus`,
never a second `bus`.

### The map is supplied under the lookup's own name

`gen_bus` is a source key like any other, carrying two columns — the dimension
it runs `over`, and the dimension its values are labels of, each named after
that dimension:

```python
sources = {
    'generator': ['g1', 'g2', 'g3'],
    'gen_bus': pl.DataFrame({'generator': ['g1', 'g2'], 'bus': ['north', 'south']}),
}
```

**A partial map is the rows it has.** `g3` is in no row, so `g3` sits on no
bus — absence is the absent row, exactly as it is for a parameter, and a null
in the value column is refused for saying both at once. The relation is
single-valued per label of `over`, and a key matching no label of it is a typo
rather than a new member. Values are never inferred from the parameters that
use the target: inferring would let a mistyped label extend the label set
instead of being rejected.

**A column of the `over` index named after the lookup is refused** rather than
read. The index may carry any other extra column.

## Dimension, lookup or parameter?

Every column of data is one of the three, and the block it goes under is
decided by what the math does with it rather than by what it holds:

| The column…                                                                                                                  | is declared as                        | because                                                                                                                    |
| ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| is an axis: something is indexed by it, or an aggregation lands terms on it                                                  | a `dimension`                         | its members are the coordinate set every table over it is reindexed onto                                                   |
| is single-valued per member of a dimension and points at another — a generator's bus, a snapshot's period, a line's two ends | a `lookup` into that dimension        | it is a map `sum(by=)` and `at(by=)` walk, whose values are checked against the set they name                              |
| is a label set the model selects on or counts within, and nothing is indexed by it — a period, a season, a zone              | a `dimension`, and a `lookup` into it | a set worth a `where` or a `position(by=)` is worth the membership check; the dimension costs one line and one member list |
| scales terms — a coefficient, a bound, an offset                                                                             | a `parameter` (`float` or `int`)      | arithmetic is over numbers ([dtype](declarations.md#parameters))                                                           |
| is a per-row attribute the math only ever selects on — a fuel, a constraint's sense                                          | a `str` parameter                     | it names rows rather than scaling them, and no set is declared for its values to be checked against                        |
| is a mask                                                                                                                    | a `bool` parameter                    | a bare name in a `where` is its own answer                                                                                 |

Two rules the table follows from. **If `b` is single-valued per `a`, then `b`
is a lookup over `a`, not a dimension**: a `foreach` product over functionally
dependent dims, cut back by a mask, is exactly the shape `lookups` exists to
replace. And **everything under `dimensions:` is a set** — a dimension is never
legal in a value position, it is a coordinate space rather than data, and
`check` warns about a declared dimension that nothing is indexed by, nothing
aggregates into and no lookup targets. To use a dimension's coordinates _as
data_, declare a parameter over it.
