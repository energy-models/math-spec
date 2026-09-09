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
carry it, and a second field says which of two kinds it is. Topology is a
lookup: a generator sits on a bus, a line has two endpoints, and no adjacency
matrix or hand-written join appears anywhere.

### `into:` names a target dimension — the groupable kind

The lookup's values are labels of another dimension, which is what
[`sum(by=)` and `at(by=)`](operators.md) land terms on:

```yaml
dimensions:
  bus: { dtype: str }
  generator: { dtype: str }
  line: { dtype: str }
lookups:
  gen_bus: { over: generator, into: bus }
  line_from: { over: line, into: bus } # two lookups onto one dimension
  line_to: { over: line, into: bus }
```

The target must be a declared dimension other than `over`. Values are checked
against it once data is bound.

**A partial lookup is legal.** A label with no row in the map belongs to no
group (a generator on no bus, a line with one open end), and `sum(by=)` places
its terms nowhere. A value naming no label of the target is an error.

**Several at once**: `sum(x, by=[gen_bus, gen_tech])` groups through both maps
in one reduction, landing on `bus` _and_ `technology`. Every lookup in the list
must be `over:` the same dimension and target a different one. A member either
map leaves out belongs to no group.

### `dtype:` declares a label space of its own — the selection-only kind

It owns its values, targets nothing, and puts no entry under `dimensions:`. A
[`where`](expressions.md#where-strings) selects on it, and nothing else reads
it:

```yaml
dimensions:
  snapshot: { dtype: int }
lookups:
  period: { over: snapshot, dtype: int } # a label on snapshot — nothing else
variables:
  build:
    foreach: [snapshot]
    where: "period == 1" # …and this is what selects on it
```

A lookup declares **exactly one** of `into:` and `dtype:`. `sum`, `at` and
`shift` refuse to group into a label space, since each reaches the target
dimension; `position(dim, by=)` accepts one, since it only counts inside a
group ([#280](https://github.com/energy-models/math-spec/issues/280)). The
rewrite is an axis of its own: `period: {...}` under `dimensions:` and
`period_of: {over: snapshot, into: period}`.

### The map is supplied under the lookup's own name

`gen_bus` is a source key like any other, carrying two columns: the dimension
it runs `over`, and the space its values are labels of:

```python
sources = {
    'generator': ['g1', 'g2', 'g3'],
    'gen_bus': pl.DataFrame({'generator': ['g1', 'g2'], 'bus': ['north', 'south']}),
}
```

The value column is named after the **target dimension** for the groupable
kind, and after the **lookup itself** for a label space.

**A partial map is the rows it has.** `g3` is in no row, so `g3` sits on no
bus. A null in the value column is refused. A key matching no label of `over`
is an error rather than a new member.

**A column of the `over` index named after the lookup is refused** rather than
read. The index may carry any other extra column.

### Both kinds

**Every lookup name joins the flat namespace**, so a lookup may not shadow a
dimension, its own target included. `generator`'s map onto `bus` is `gen_bus`,
never a second `bus`.

Either kind is single-valued per label of `over`, and supplied under the
lookup's own name. Values are never inferred from the parameters that use the
dimension.

## Dimension or lookup?

If `b` is single-valued per `a`, **`b` is a lookup over `a`, not a
dimension**. A `foreach` product over dependent dims, cut back by a mask, is
the shape a lookup replaces.

Everything under `dimensions:` is an axis. A dimension is never legal in a
value position, and `check` warns about a declared dimension that is never
used as an axis. To use a dimension's coordinates _as data_, declare a
parameter over it.
