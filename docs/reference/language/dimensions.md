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
sits on, and which two buses each line joins, are lookup tables, and the file
holds no adjacency matrix.

Declare each lookup under its own name. `over:` names the dimension whose
members carry the value. **Exactly one** of `into:` and `dtype:` says which
kind of lookup it is.

### `into:` maps onto another dimension

The values are labels of the target dimension, and
[`sum(by=)` and `at(by=)`](operators.md) land terms on that dimension:

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

The target must be a declared dimension, and it must differ from `over`. The
values are checked against the target when the data binds.

A partial lookup is legal. A label the map leaves out belongs to no group, so a
generator can sit on no bus and a line can have one open end. `sum(by=)` places
such a label's terms nowhere. A value that names no label of the target is an
error.

Several lookups may group at once. `sum(x, by=[gen_bus, gen_tech])` groups
through both maps in one reduction and lands on `bus` and `technology`. Every
lookup in the list must be `over:` the same dimension, and each must target a
different one. A member that either map leaves out belongs to no group.

### `dtype:` declares a label space of its own

The values belong to the lookup and target nothing. Nothing aggregates into a
label space, so it takes no entry under `dimensions:`. The one thing you can do
with it is select on it in a [`where`](expressions.md#where-strings):

```yaml
dimensions:
  snapshot: { dtype: int }
lookups:
  period: { over: snapshot, dtype: int } # a label on snapshot, and nothing else
variables:
  build:
    foreach: [snapshot]
    where: "period == 1"
```

`sum`, `sum_back`, `at` and `shift` refuse a label space in `by=`, because each
of them reaches the target dimension. `position(dim, by=)` accepts one, because it only
counts inside a group
([#280](https://github.com/energy-models/math-spec/issues/280)).

To aggregate into a label space, promote it: declare `period` under
`dimensions:`, and declare `period_of: {over: snapshot, into: period}`.

### How the map is supplied

The map is a source key like any other, under the lookup's own name. It carries
two columns: the `over` dimension, and the values:

```python
sources = {
    'generator': ['g1', 'g2', 'g3'],
    'gen_bus': pl.DataFrame({'generator': ['g1', 'g2'], 'bus': ['north', 'south']}),
}
```

The value column is named after the **target dimension** for an `into:` lookup,
and after the **lookup itself** for a `dtype:` lookup.

A partial map is exactly the rows it has: `g3` appears in no row, so `g3` sits
on no bus. A null in the value column is refused, because a missing row already
says the same thing. A key that matches no label of `over` is an error rather
than a new member.

The map touches no table but its own, so you can add a lookup to a model the way
you add a parameter. The index of the `over` dimension may carry other columns,
but a column named after the lookup is refused rather than read.

### Rules both kinds share

Every lookup name joins the flat namespace, so a lookup may not shadow a
dimension, and that includes its own target. The map from `generator` onto `bus`
is called `gen_bus`, never a second `bus`.

Values are never inferred from the parameters that use the dimension. If they
were, a mistyped label would extend the label space instead of being rejected.

## Dimension or lookup?

If `b` has one value per `a`, then `b` is a **lookup** over `a`, and not a
dimension. A `foreach` product over two dimensions that depend on each other,
cut back with a mask, is the shape that `lookups` replaces.

Everything under `dimensions:` is an axis. A dimension is never legal where a
value belongs, because it is a coordinate space and not data. To use a
dimension's coordinates as data, declare a parameter over it.
`python -m math_spec check` advises on a declared dimension that is never used
as an axis ([errors](errors.md#advice-warns-about-two-things-that-load)).
