<!--
SPDX-FileCopyrightText: mathspec contributors
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
| `description` | free text                         | default `null` |

The members of a dimension arrive with the data, in the order the table gives
them. [`shift`](operators.md#shift), `sum_back` and `position()` count along
that order, and everything indexed by the dimension is matched to its members
by label.

Whether to declare a column of data as a dimension, a relation or a parameter
is decided in [declare a column of data](../../howto/declare-a-column.md).
