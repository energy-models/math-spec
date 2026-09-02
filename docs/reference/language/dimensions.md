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

_At most_ once, rather than exactly once: a coordinate with no row is how a
parameter declared `coverage: masked` masks, and an error at bind for one that
is not — which of the two is
[`coverage`](declarations.md), declared rather than inferred from the table.

## `lookups`

A lookup is what makes topology _data_: a generator sits on a bus, a line has
two endpoints, and no adjacency matrix or hand-written join appears anywhere.
Each is declared under its own name, `over:` the dimension whose members carry
it, and the second field says which of two kinds it is.

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
against it once data is bound — the check that makes `sum(by=)` safe.

**A partial lookup is legal, and `coverage:` is where the file says it was
meant.** A label the map leaves out belongs to no group — a generator on no bus,
a line with one open end — and `sum(by=)` places its terms nowhere. That is a
deliberate shape and a wiring mistake in equal measure, and they are identical in
the data, so the declaration says which:

```yaml
lookups:
  gen_bus: { over: generator, into: bus } # total: every generator is on a bus
  line_to: { over: line, into: bus, coverage: masked } # an open end is meant
```

The default is `total`, so a component library declaring its coupling map
`total` turns a port nobody wired from a term that quietly vanishes into an
error naming it. `coverage:` is for the `into:` kind only — a label space is
selected on, and a label it leaves out reads as false, which is a reading rather
than a gap. A value naming no label of the target is a typo, and an error.
"Left out" is spelled by omission: a label with no row in the map.

**Several at once**: `sum(x, by=[gen_bus, gen_tech])` groups through both maps
in one reduction, landing on `bus` _and_ `technology`. Every lookup in the list
must be `over:` the same dimension — one grouping consumes one dimension — and
must target a different one. A member either map leaves out belongs to no group
at all, the same reading one unmapped member gets.

### `dtype:` declares a label space of its own — the selection-only kind

It owns its values, targets nothing, and puts no entry under `dimensions:`,
because a label space nothing aggregates into is not part of the model's
dimensionality. _Selecting_ on it is a [`where`](expressions.md#where-strings),
which is the only thing this kind is for:

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

A lookup declares **exactly one** of `into:` and `dtype:`. Grouping into a
label space is refused — by `sum`, `at` and `shift`, each of which reaches the
target dimension, though not by `position(dim, by=)`, which only counts inside
a group ([#280](https://github.com/energy-models/math-spec/issues/280)). The rewrite is to declare the axis and target it under
a name of its own (`period: {...}` under `dimensions:`,
`period_of: {over: snapshot, into: period}`) — a promotion made the day the
model genuinely gains the axis.

### The map is supplied under the lookup's own name

`gen_bus` is a source key like any other, carrying two columns — the dimension
it runs `over`, and the space its values are labels of:

```python
sources = {
    'generator': ['g1', 'g2', 'g3'],
    'gen_bus': pl.DataFrame({'generator': ['g1', 'g2'], 'bus': ['north', 'south']}),
}
```

The value column is named after the **target dimension** for the groupable
kind, because that is what its values are labels of, and after the **lookup
itself** for a label space, which owns its values and targets nothing.

**A partial map is the rows it has.** `g3` is in no row, so `g3` sits on no
bus — absence is the absent row, and a null in the value column is refused for
saying both at once. The relation is
single-valued per label of `over`, and a key matching no label of it is a typo
rather than a new member.

Supplying it this way touches no table but its own, which is what a caller who
did not generate the index needs: a model can be extended with a lookup the
same way it can be extended with a parameter. **A column of the `over` index
named after the lookup is refused** rather than read — an index may carry any
other extra, and this one would be a map read by accident.

### Both kinds

**Every lookup name joins the flat namespace**, so a lookup may not shadow a
dimension — its own target included. `generator`'s map onto `bus` is `gen_bus`,
never a second `bus`.

Either kind is single-valued per label, and either is supplied under the
lookup's own name. Values are never inferred from the parameters that use the
dimension: inferring would let a mistyped label extend the label space instead
of being rejected.

## Dimension or lookup?

If `b` is single-valued per `a`, then **`b` is a lookup over `a`, not a
dimension**. A `foreach` product over functionally dependent dims, cut back by
a mask, is exactly the shape `lookups` exists to replace.

The block invariant follows: everything under `dimensions:` is an axis. A
dimension is never legal in a value position — it is a coordinate space, not
data — and `check` warns about a declared dimension that is never used as an
axis. To use a dimension's coordinates _as data_, declare a parameter over it.
