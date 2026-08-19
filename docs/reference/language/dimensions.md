# Dimensions and lookups

A **dimension** is an axis of the model — something is indexed by it, or an
aggregation lands terms on it. A **lookup** is a named single-valued map out of
a dimension: a generator's bus, a snapshot's period. The two are different
things and the file keeps them apart.

```yaml
dimensions:
  snapshot: {dtype: int}  # coordinates come from the data
  generator: {values: [wind, solar, gas]}  # coordinates are given here
```

Every dimension named anywhere in the file must be declared here.

| Field | | |
|---|---|---|
| `dtype` | `float`, `int`, `str`, `datetime` | default `str` |
| `values` | the coordinates, as a list | default `null` — they must then arrive from data ([data binding](data.md)) |
| `description` | free text, never parsed | default `null` |

Every declared value must be of the declared `dtype`. `values: [2024-01-01]`
under the default `dtype: str` is a load error: YAML resolved it to a date, and
a date does not join `'2024-01-01'` in the data.

**One master coordinate set per dimension, resolved before any data binds.**
Every parameter is reindexed onto it, so two tables that disagree about which
snapshots exist is an error at load time rather than a silently truncated
model. Where the coordinates come from, and in what order, is
[data binding](data.md).

## `lookups`

A lookup is what makes topology *data*: a generator sits on a bus, a line has
two endpoints, and no adjacency matrix or hand-written join appears anywhere.
Each is declared under its own name, `over:` the dimension whose members carry
it, and the second field says which of two kinds it is.

### `into:` names a target dimension — the groupable kind

The lookup's values are labels of another dimension, which is what
[`sum(by=)` and `at(by=)`](operators.md) land terms on:

```yaml
dimensions:
  bus: {dtype: str}
  generator: {dtype: str}
  line: {dtype: str}
lookups:
  gen_bus: {over: generator, into: bus}
  line_from: {over: line, into: bus}  # two lookups onto one dimension
  line_to: {over: line, into: bus}
```

The target must be a declared dimension other than `over`. Non-null values are
checked against it once data is bound — the check that makes `sum(by=)` safe.

**A partial lookup is legal**: `null` says the label belongs to no group — a
generator on no bus, a line with one open end — and `sum(by=)` places its terms
nowhere. An unknown *non-null* value is a typo, and an error.

**Several at once**: `sum(x, by=[gen_bus, gen_tech])` groups through both maps
in one reduction, landing on `bus` *and* `technology`. Every lookup in the list
must be `over:` the same dimension — one grouping consumes one dimension — and
must target a different one. A member missing any of them belongs to no group
at all, the same reading a single null gets.

### `dtype:` declares an inline label space — the selection-only kind

It owns its values, targets nothing, and puts no entry under `dimensions:`,
because a label space nothing aggregates into is not part of the model's
dimensionality. *Selecting* on it is a [`where`](expressions.md#where-strings),
which is the only thing this kind is for:

```yaml
dimensions:
  snapshot: {dtype: int}
lookups:
  period: {over: snapshot, dtype: int}  # a label on snapshot — nothing else
variables:
  build:
    foreach: [snapshot]
    where: "period == 1"  # …and this is what selects on it
```

A lookup declares **exactly one** of `into:` and `dtype:`. Grouping into a
label space is refused, with the rewrite: declare the axis and target it under
a name of its own (`period: {...}` under `dimensions:`,
`period_of: {over: snapshot, into: period}`) — a promotion made the day the
model genuinely gains the axis.

### `values:` puts a small map in the file

Keyed by the labels of `over` — what a dimension's own `values:` does for its
labels, for a relation small enough to read:

```yaml
dimensions:
  generator: {values: [g1, g2]}
  bus: {values: [north, south]}
lookups:
  gen_bus: {over: generator, into: bus, values: {g1: north, g2: south}}
```

A label it omits maps to null, which is the partial case above. Both sides are
labels, so both carry the dtype rule a dimension's own `values:` carries: a key
is of `over`'s dtype, and a value of the target's — or of the lookup's own,
where it is a label space.

**Where the target declares its values too, the containment check runs at
load** rather than at bind, which is the reason to prefer declaring a small map
over supplying it.

**Labels from the caller, maps from the file** is the shape this is for: a
relation small enough to read stays beside the equation that traverses it,
while the members it is about stay in the data. A map declares no labels of its
own, and neither fact may be claimed twice. Which of the two homes each has,
what a label no map mentions gets, and why a key no label matches is a typo
rather than a new member, is [data binding](data.md#where-coordinates-come-from).

### Both kinds

**Every lookup name joins the flat namespace**, so a lookup may not shadow a
dimension — its own target included. `generator`'s map onto `bus` is `gen_bus`,
never a second `bus`.

Either kind is single-valued per label, and a dimension carrying lookups whose
maps the file does not declare needs an index source with one column per
lookup, named after it ([data binding](data.md)). Values are never inferred
from the parameters that use the dimension: inferring would let a mistyped
label extend the label space instead of being rejected.

## Dimension or lookup?

If `b` is single-valued per `a`, then **`b` is a lookup over `a`, not a
dimension**. A `foreach` product over functionally dependent dims, cut back by
a mask, is exactly the shape `lookups` exists to replace.

The block invariant follows: everything under `dimensions:` is an axis. A
dimension is never legal in a value position — it is a coordinate space, not
data — and `check` warns about a declared dimension that is never used as an
axis. To use a dimension's coordinates *as data*, declare a parameter over it.
