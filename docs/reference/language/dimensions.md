<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Dimensions

A **dimension** is an axis of the model, such as `snapshot` or `generator`.
Declarations are indexed by it, and `sum` reduces over it. A map from one axis
onto another is a [relation](relations.md).

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
   `capacity` for its values, never for its list of generators, and it does not
   treat `gen_bus` as the list either. If a declaration uses `generator` and
   no `generator` table arrives, the engine raises an error that names
   `generator`. It does not build an empty axis, because an empty axis would
   silently delete every row indexed by it. A declared dimension that no
   declaration uses needs no table.
2. **The members keep the order the table gives them.** The engine does not
   sort them, whether they are strings, integers or dates.
   [`shift`](operators.md#shift), `sum_back` and `position()` all count along
   this order, so an engine that sorted `snapshot` would give
   `shift(dispatch, along=snapshot, offset=1)` a different meaning. To get a
   particular order, write the table in that order.
3. **A table has each coordinate at most once.** Two rows for `snapshot == 3`
   is an error that names `3`. The engine does not keep the last, keep the
   first, or add them. _At most_ once, not exactly once: a coordinate with no
   row is [absence](absence.md), and absence is how a model masks. A relation's
   table obeys the same rule.

Every dimension has one list of members, and every parameter is lined up against
it when the data binds. So if `load` has 8760 snapshots and `price` has 8759, the
engine raises an error rather than build a model with one snapshot dropped.

## Dimension, relation or parameter?

Every column of data is one of the three. What decides which is what the math
does with the column, not what the column holds:

| The column…                                                                                                                           | is declared as                          | because                                                                                                                   |
| ------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| is an axis: something is indexed by it, or an aggregation lands terms on it                                                           | a `dimension`                           | its members are the coordinate set every table over it is reindexed onto                                                  |
| has one value per member of a dimension, or per tuple of several — a generator's bus, a line's two ends, a generator's zone by period | a `relation` with that `key`            | it is a map every operator walks, and its values are checked against the dimensions they name                             |
| relates members of two dimensions many-to-many, with nothing to weigh — which buses a generator may connect to                        | a bare `relation`, with no `values:`    | `sum` walks it with both ends named, and a bare `where` tests it. Nothing reads it, because there is no one value to read |
| relates members of two dimensions many-to-many, with a weight per pair — a link's efficiency to each bus, a cycle's lines             | a `parameter` over both                 | the weight is the data, its row set is the relation, and the aggregation is `sum(w * x, over=a)`                          |
| is a label set the model only selects on or counts within — a period, a season, a zone                                                | a `dimension`, and a `relation` onto it | its labels are checked, at the cost of one line and one table                                                             |
| scales terms — a coefficient, a bound, an offset                                                                                      | a `parameter` (`float` or `int`)        | arithmetic is over numbers ([dtype](declarations.md#parameters))                                                          |
| is a per-row attribute the math only selects on — a fuel, a constraint's sense                                                        | a `str` parameter                       | it names rows rather than scaling them, and no set is declared to check its values against                                |
| is a mask                                                                                                                             | a `bool` parameter                      | a bare name in a `where` is its own answer                                                                                |

Two rules follow. If `b` has one value per `a`, declare `b` as a **relation**
keyed by `a`, not as a dimension. Two dimensions that depend on each other,
declared as a `dims` product and cut back with a mask, are one relation.

Everything under `dimensions:` is an axis. A dimension is never legal where a
value belongs, because it is a coordinate space and not data. To use a
dimension's labels as data, declare a parameter over it.
`python -m math_spec check` advises on a declared dimension that nothing is
indexed by, nothing aggregates into and no relation has a column over
([errors](errors.md#what-advice-warns-about)).
