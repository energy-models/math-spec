<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Dimensions and lookups

A **dimension** is an axis of the model. Something is indexed by it, or an
aggregation lands terms on it.

A **lookup** is a named map out of a dimension that gives one value per label.
A generator's bus and a snapshot's period are both lookups.

The two are different things, and the file keeps them apart.

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

**A declaration says that the axis exists, and how its coordinates are typed.
It never says which coordinates there are.** The members are data, and they
arrive with the data. If the file named them, that would be a second place to
look. In a real model the generators, the buses and the snapshots are a table,
not a list that somebody keeps in step by hand.

**Each dimension has one master coordinate set, resolved before any data
binds.** Every parameter is reindexed onto that set. So if two tables disagree
about which snapshots exist, you get an error at load time instead of a model
that was quietly truncated.

Which coordinates there are, and what order they stand in, is for the data to
say. The three rules below say how the data says it.

### Binding belongs to the language, even though the data does not

The file declares an axis. The data supplies its members. Between those two
sentences sit three facts that together decide **which model a file and a table
make**. If a consumer answered any of the three differently, it would build a
different model from the same two inputs. So these facts belong to the
language. A consumer implements them; it does not choose them.

**The members come from the dimension's own source.** They are read from the
key named after the dimension, and from nowhere else. A parameter's table is
read for values, never for labels. A lookup's map is not a claim about which
members exist.

If a declaration reaches a dimension and nothing supplies it, that is an error
that names the dimension. It is not an empty axis. An axis with no members
would quietly delete every row indexed by it. A declared dimension that no
declaration reaches asks nothing of the data, so it needs no source.

**The order of the members is the order that the source gives them**, first row
first. They are not sorted, and the type of a label changes nothing. An axis of
strings, an axis of integers and an axis of timestamps are all read in the
order they arrive.

The order is observable, because [`shift`](operators.md#shift), `sum_back` and
`position()` all walk it. A consumer that sorted the axis would answer
`shift(p, over=snapshot, offset=1)` with a different row, and the file could
not tell you which answer it meant. If a model wants a particular order, it
states that order in the source it hands over.

**One row per coordinate.** A parameter's table carries each coordinate of its
`dims` at most once. A second row for one coordinate is an error that names the
coordinate. It is never a last-wins, a first-wins, or a sum. Each of those
three readings is defensible, and that is exactly why the file may not leave
the choice open. A lookup's map obeys the same rule one axis over, and says so
under `lookups` below: it gives one value per label of `over`.

Note that this is _at most_ once, not exactly once. A coordinate with no row is
[absence](absence.md), and absence is how a model masks.

## `lookups`

A lookup is what makes topology into _data_. A generator sits on a bus, and a
line has two endpoints, and no adjacency matrix or hand-written join appears
anywhere.

Declare each lookup under its own name. Give `over:` the dimension whose
members carry the lookup. The second field says which of the two kinds of
lookup it is.

### `into:` names a target dimension — the groupable kind

With `into:`, the lookup's values are labels of another dimension. That target
dimension is what [`sum(by=)` and `at(by=)`](operators.md) land terms on:

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

The target must be a declared dimension, and it must not be the same dimension
as `over`. The values are checked against the target once the data is bound,
and that check is what makes `sum(by=)` safe.

**A partial lookup is legal.** A label that the map leaves out belongs to no
group. A generator can sit on no bus, and a line can have one open end. For
such a label, `sum(by=)` places its terms nowhere. A value that names no label
of the target is a typo, and it is an error. You spell "left out" by omission,
which means a label with no row in the map.

**You can use several lookups at once.** `sum(x, by=[gen_bus, gen_tech])`
groups through both maps in one reduction, and lands on `bus` _and_
`technology`. Every lookup in the list must be `over:` the same dimension,
because one grouping consumes one dimension. Each must also target a different
dimension. A member that either map leaves out belongs to no group at all,
which is the same reading that one unmapped member gets.

### `dtype:` declares a label space of its own — the selection-only kind

This kind of lookup owns its values and targets nothing. It puts no entry
under `dimensions:`, because a label space that nothing aggregates into is not
part of the model's dimensionality. The only thing you can do with this kind is
_select_ on it, using a [`where`](expressions.md#where-strings):

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

A lookup declares **exactly one** of `into:` and `dtype:`.

Grouping into a label space is refused. The refusal comes from `sum`, `at` and
`shift`, because each of those reaches the target dimension. It does not come
from `position(dim, by=)`, which only counts inside a group
([#280](https://github.com/energy-models/math-spec/issues/280)).

The rewrite is to declare the axis, and to target it under a name of its own.
Put `period: {...}` under `dimensions:`, then declare
`period_of: {over: snapshot, into: period}`. Make that promotion on the day the
model genuinely gains the axis.

### The map is supplied under the lookup's own name

`gen_bus` is a source key like any other. It carries two columns: the dimension
it runs `over`, and the space that its values are labels of:

```python
sources = {
    'generator': ['g1', 'g2', 'g3'],
    'gen_bus': pl.DataFrame({'generator': ['g1', 'g2'], 'bus': ['north', 'south']}),
}
```

How you name the value column depends on the kind of lookup. For the groupable
kind, name it after the **target dimension**, because that is what its values
are labels of. For a label space, name it after the **lookup itself**, because
a label space owns its values and targets nothing.

**A partial map is exactly the rows it has.** `g3` appears in no row, so `g3`
sits on no bus. Absence is the absent row, exactly as it is for a parameter. A
null in the value column is refused, because it says both things at once. The
relation gives one value per label of `over`, and a key that matches no label
of `over` is a typo rather than a new member.

Supplying a lookup this way touches no table except its own. That is what a
caller who did not generate the index needs, because it means you can extend a
model with a lookup in the same way you extend it with a parameter. **A column
of the `over` index named after the lookup is refused** rather than read. An
index may carry any other extra column, but that one would be a map read by
accident.

### Both kinds

**Every lookup name joins the flat namespace.** So a lookup may not shadow a
dimension, and that includes its own target. The map from `generator` onto
`bus` is called `gen_bus`, and never a second `bus`.

Both kinds give one value per label, and you supply both kinds under the
lookup's own name. Values are never inferred from the parameters that use the
dimension. If they were inferred, a mistyped label would extend the label space
instead of being rejected.

## Dimension or lookup?

If `b` has one value per `a`, then **`b` is a lookup over `a`, and not a
dimension**. Take a `foreach` product over dimensions that are functionally
dependent, then cut it back with a mask. That shape is exactly what `lookups`
exists to replace.

The invariant for the block follows from this: everything under `dimensions:`
is an axis. A dimension is never legal in a value position, because it is a
coordinate space and not data. `check` warns you about a declared dimension
that is never used as an axis. To use a dimension's coordinates _as data_,
declare a parameter over that dimension.
