<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Declare a column of data

Decide whether a column of your data is a
[dimension](../reference/language/dimensions.md), a
[relation](../reference/language/relations.md) or a
[parameter](../reference/language/declarations.md#parameters). What decides is
what the math does with the column.

| The column…                                                                                                                           | is declared as                          |
| ------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| is an axis: something is indexed by it, or an aggregation lands terms on it                                                           | a `dimension`                           |
| has one value per member of a dimension, or per tuple of several — a generator's bus, a line's two ends, a generator's zone by period | a `relation` with that `key`            |
| relates members of two dimensions many-to-many, with nothing to weigh — which buses a generator may connect to                        | a bare `relation`, with no `values:`    |
| relates members of two dimensions many-to-many, with a weight per pair — a link's efficiency to each bus, a cycle's lines             | a `parameter` over both                 |
| is a label set the model only selects on or counts within — a period, a season, a zone                                                | a `dimension`, and a `relation` onto it |
| scales terms — a coefficient, a bound, an offset                                                                                      | a `parameter` (`float` or `int`)        |
| is a per-row attribute the math only selects on — a fuel, a constraint's sense                                                        | a `str` parameter                       |
| is a mask                                                                                                                             | a `bool` parameter                      |

Two rules decide the cases the table does not list:

1. **If `b` has one value per `a`, declare `b` as a relation keyed by `a`.**
2. **Two dimensions that depend on each other are one relation.**
