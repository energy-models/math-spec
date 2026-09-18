<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Declare a column of data

Decide whether a column of your data is a
[dimension](../reference/language/dimensions.md), a
[relation](../reference/language/relations.md) or a
[parameter](../reference/language/declarations.md#parameters). What decides is
what the math does with the column, not what the column holds.

| The column…                                                                                                                           | is declared as                          | because                                                                                                                   |
| ------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| is an axis: something is indexed by it, or an aggregation lands terms on it                                                           | a `dimension`                           | its members are the coordinate set every table over it is reindexed onto                                                  |
| has one value per member of a dimension, or per tuple of several — a generator's bus, a line's two ends, a generator's zone by period | a `relation` with that `key`            | it is a map every operator walks, and its values are checked against the dimensions they name                             |
| relates members of two dimensions many-to-many, with nothing to weigh — which buses a generator may connect to                        | a bare `relation`, with no `values:`    | `sum` walks it with both ends named, and a bare `where` tests it. Nothing reads it, because there is no one value to read |
| relates members of two dimensions many-to-many, with a weight per pair — a link's efficiency to each bus, a cycle's lines             | a `parameter` over both                 | the weight is the data, its row set is the relation, and the aggregation is `sum(w * x, over=a)`                          |
| is a label set the model only selects on or counts within — a period, a season, a zone                                                | a `dimension`, and a `relation` onto it | its labels are checked, at the cost of one line and one table                                                             |
| scales terms — a coefficient, a bound, an offset                                                                                      | a `parameter` (`float` or `int`)        | arithmetic is over numbers ([dtype](../reference/language/declarations.md#parameters))                                    |
| is a per-row attribute the math only selects on — a fuel, a constraint's sense                                                        | a `str` parameter                       | it names rows rather than scaling them, and no set is declared to check its values against                                |
| is a mask                                                                                                                             | a `bool` parameter                      | a bare name in a `where` is its own answer                                                                                |

Two rules decide the cases the table does not list:

1. **If `b` has one value per `a`, declare `b` as a relation keyed by `a`**,
   not as a dimension. A dimension is an axis, and `b` is a column along `a`.
2. **Two dimensions that depend on each other are one relation.** Declared as
   a `dims` product and cut back with a mask, they cost a dense frame and a
   `where` for what one keyed table says outright.
