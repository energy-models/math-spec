<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# One construct per model

For each built-in [operator](../reference/language/operators.md), the smallest
model that declares it, beside the equation it prints. The reference page shows
the same equations as one table. This page shows the **file** that produced each
one.

Each is a whole model rather than a fragment, so a model whose operator changed
shape stops loading in CI, in the run that would otherwise have shipped the old
math.

<!-- gallery:begin -->
### `sum(array)`

`examples/operators/sum_all.yaml`

```yaml
description: Every dimension at once — `sum(array)` names none of them and takes them all.

dimensions:
  snapshot: { dtype: int }
  generator: { dtype: str }

parameters:
  budget: { dims: [] }

variables:
  p:
    dims: [snapshot, generator]
    bounds: { lower: 0 }

constraints:
  fleet_budget:
    dims: []
    expression: sum(p) <= budget

objective: { sense: minimize, expression: sum(p) }
```

$`\sum_{t \in \mathcal{T},\ g \in \mathcal{G}} p_{t,g} \le \mathrm{budget}`$

### `sum(array, over=dim)`

`examples/operators/sum.yaml`

```yaml
description: The plain reduction — `sum(array, over=dim)` collapses one dimension.

dimensions:
  snapshot: { dtype: int }
  generator: { dtype: str }

parameters:
  limit: { dims: [snapshot] }

variables:
  p:
    dims: [snapshot, generator]
    bounds: { lower: 0 }

constraints:
  fleet_total:
    dims: [snapshot]
    expression: sum(p, over=generator) <= limit

objective: { sense: minimize, expression: sum(p) }
```

$`\sum_{g \in \mathcal{G}} p_{t,g} \le \mathrm{limit}_{t} \qquad \forall\, t \in \mathcal{T}`$

### `sum(array, by=relation)`

`examples/operators/sum_by.yaml`

```yaml
description: >-
  The membership reduction — `sum(array, by=relation)` lands the result on the
  column the relation is walked to, which is what makes topology data rather than
  structure.

dimensions:
  snapshot: { dtype: int }
  generator: { dtype: str }
  bus: { dtype: str }

relations:
  gen_bus: { columns: [generator, bus], key: generator }

parameters:
  limit: { dims: [snapshot, bus] }

variables:
  p:
    dims: [snapshot, generator]
    bounds: { lower: 0 }

constraints:
  bus_total:
    dims: [snapshot, bus]
    expression: sum(p, by=gen_bus) <= limit

objective: { sense: minimize, expression: sum(p) }
```

$`\sum_{g \in \mathcal{G} \,:\, \mathrm{gen\_bus}(g) = b} p_{t,g} \le \mathrm{limit}_{t,b} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B}`$

### `sum(array, by=[relation, …])`

`examples/operators/sum_by_relations.yaml`

```yaml
description: >-
  Grouping through several maps at once — `sum(array, by=[relation, …])` lands
  the result on every dimension the relations map into, which is one grouping
  rather than a composition of two: the generator dimension is consumed once.

dimensions:
  snapshot: { dtype: int }
  generator: { dtype: str }
  bus: { dtype: str }
  technology: { dtype: str }

relations:
  gen_bus: { columns: [generator, bus], key: generator }
  gen_tech: { columns: [generator, technology], key: generator }

parameters:
  limit: { dims: [snapshot, bus, technology] }

variables:
  p:
    dims: [snapshot, generator]
    bounds: { lower: 0 }

constraints:
  bus_technology_total:
    dims: [snapshot, bus, technology]
    expression: sum(p, by=[gen_bus, gen_tech]) <= limit

objective: { sense: minimize, expression: sum(p) }
```

$`\sum_{g \in \mathcal{G} \,:\, \mathrm{gen\_bus}(g) = b \wedge \mathrm{gen\_tech}(g) = e} p_{t,g} \le \mathrm{limit}_{t,b,e} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B},\ e \in \mathcal{E}`$

### `sum(array, by=relation, direction=a -> b)`

`examples/operators/sum_by_columns.yaml`

```yaml
description: >-
  A walk that names its direction — `sum(array, by=relation, direction=a -> b)`
  consumes the key column over dimension `a` and lands on column `b`, and the
  other key column is joined on, so each zone's total is taken per period.

dimensions:
  generator: { dtype: str }
  period: { dtype: int }
  zone: { dtype: str }

relations:
  zone_of: { columns: [generator, period, zone], key: [generator, period] }

parameters:
  demand: { dims: [zone, period] }

variables:
  p:
    dims: [generator, period]
    bounds: { lower: 0 }

constraints:
  zone_balance:
    dims: [zone, period]
    expression: sum(p, by=zone_of, direction=generator -> zone) >= demand

objective: { sense: minimize, expression: sum(p) }
```

$`\sum_{g \in \mathcal{G} \,:\, \mathrm{zone\_of}(g,\ e) = z} p_{g,e} \ge \mathrm{demand}_{z,e} \qquad \forall\, z \in \mathcal{Z},\ e \in \mathcal{E}`$

### `sum(array, by=relation, direction=[a, …] -> [b, …])`

`examples/operators/sum_by_column_lists.yaml`

```yaml
description: >-
  A walk with several columns at each end — `sum(array, by=relation, direction=[a, …] -> [b, …])`
  consumes both key columns at once and lands on the product of both value
  columns in one join.

dimensions:
  generator: { dtype: str }
  period: { dtype: int }
  bus: { dtype: str }
  technology: { dtype: str }

relations:
  slot_of: { columns: [generator, period, bus, technology], key: [generator, period] }

parameters:
  cap: { dims: [bus, technology] }

variables:
  p:
    dims: [generator, period]
    bounds: { lower: 0 }

constraints:
  slot_cap:
    dims: [bus, technology]
    expression: sum(p, by=slot_of, direction=[generator, period] -> [bus, technology]) <= cap

objective: { sense: minimize, expression: sum(p) }
```

$`\sum_{g \in \mathcal{G},\ e \in \mathcal{E} \,:\, \mathrm{slot\_of.bus}(g,\ e) = b \wedge \mathrm{slot\_of.technology}(g,\ e) = t} p_{g,e} \le \mathrm{cap}_{b,t} \qquad \forall\, b \in \mathcal{B},\ t \in \mathcal{T}`$

### `at(array, by=relation)`

`examples/operators/at.yaml`

```yaml
description: >-
  The adjoint of the membership reduction — `at(array, by=relation)` reads one
  coarse value once per fine label pointing at it.

dimensions:
  snapshot: { dtype: int }
  period: { dtype: int }

relations:
  period_of: { columns: [snapshot, period], key: snapshot }

parameters:
  cap: { dims: [period] }

variables:
  p:
    dims: [snapshot]
    bounds: { lower: 0 }

constraints:
  within_cap:
    dims: [snapshot]
    expression: p <= at(cap, by=period_of)

objective: { sense: minimize, expression: sum(p) }
```

$`p_{t} \le \mathrm{cap}_{\mathrm{period\_of}(t)} \qquad \forall\, t \in \mathcal{T}`$

### `at(array, by=relation, over=a)`

`examples/operators/at_columns.yaml`

```yaml
description: >-
  A read that names the column it consumes — `at(array, by=relation, over=a)`
  reads column `a` where a table has two columns over one dimension, here the
  sending end of a line.

dimensions:
  line: { dtype: str }
  bus: { dtype: str }

relations:
  ends: { columns: { line: line, bus0: bus, bus1: bus }, key: line }

parameters:
  cap: { dims: [bus] }

variables:
  f:
    dims: [line]
    bounds: { lower: 0 }

constraints:
  sending_cap:
    dims: [line]
    expression: f <= at(cap, by=ends, over=bus0)

objective: { sense: minimize, expression: sum(f) }
```

$`f_{l} \le \mathrm{cap}_{\mathrm{ends.bus0}(l)} \qquad \forall\, l \in \mathcal{L}`$

### `shift(array, along=dim, offset=n)`

`examples/operators/shift.yaml`

```yaml
description: >-
  Translation with no edge policy — the vacated position is absent, so the row
  it would have fed is not built.

dimensions:
  snapshot: { dtype: int }

variables:
  p:
    dims: [snapshot]
    bounds: { lower: 0 }

constraints:
  no_faster_than_before:
    dims: [snapshot]
    expression: p <= shift(p, along=snapshot, offset=1)

objective: { sense: minimize, expression: sum(p) }
```

$`p_{t} \le p_{t - 1} \qquad \forall\, t \in \mathcal{T}`$

### `shift(array, along=dim, offset=n, edge='wrap')`

`examples/operators/shift_wrap.yaml`

```yaml
description: >-
  Cyclic translation — the horizon closed on itself, so the first position
  reads the last and nothing is vacated.

dimensions:
  snapshot: { dtype: int }

variables:
  p:
    dims: [snapshot]
    bounds: { lower: 0 }

constraints:
  no_faster_than_before:
    dims: [snapshot]
    expression: p <= shift(p, along=snapshot, offset=1, edge='wrap')

objective: { sense: minimize, expression: sum(p) }
```

$`p_{t} \le p_{t \ominus 1} \qquad \forall\, t \in \mathcal{T}`$

### `shift(array, along=dim, offset=n, edge=v)`

`examples/operators/shift_edge.yaml`

```yaml
description: >-
  Translation with a value at the edge — the vacated position contributes the
  number instead of being absent, so the row survives.

dimensions:
  snapshot: { dtype: int }

variables:
  p:
    dims: [snapshot]
    bounds: { lower: 0 }

constraints:
  no_faster_than_before:
    dims: [snapshot]
    expression: p <= shift(p, along=snapshot, offset=1, edge=0)

objective: { sense: minimize, expression: sum(p) }
```

$`p_{t} \le p_{t \boxminus_{0} 1} \qquad \forall\, t \in \mathcal{T}`$

### `shift(array, along=dim, offset=p, edge=…)`

`examples/operators/shift_by_parameter.yaml`

```yaml
description: >-
  Translation by an offset that differs per entity — `by:` names an integer
  parameter, so each technology is reached by its own lead time rather than by
  one the file had to fix.

dimensions:
  technology: { dtype: str }
  month: { dtype: int }

parameters:
  lead: { dims: [technology], dtype: int }
  demand: { dims: [technology, month] }

variables:
  order:
    dims: [technology, month]
    bounds: { lower: 0 }

constraints:
  arrives_after_its_lead:
    dims: [technology, month]
    expression: shift(order, along=month, offset=lead, edge=0) >= demand

objective: { sense: minimize, expression: sum(order) }
```

$`\mathit{order}_{t,m \boxminus_{0} \mathrm{lead}} \ge \mathrm{demand}_{t,m} \qquad \forall\, t \in \mathcal{T},\ m \in \mathcal{M}`$

### `shift(array, along=dim, offset=n, by=relation)`

`examples/operators/shift_partitioned.yaml`

```yaml
description: >-
  Translation inside a group — each season closed on itself, so a season's first
  snapshot reads that season's last and no level crosses the boundary.

dimensions:
  snapshot: { dtype: int }
  season: { dtype: str }

relations:
  season_of: { columns: [snapshot, season], key: snapshot }

variables:
  p:
    dims: [snapshot]
    bounds: { lower: 0 }

constraints:
  no_faster_than_before_in_season:
    dims: [snapshot]
    expression: p <= shift(p, along=snapshot, offset=1, edge='wrap', by=season_of)

objective: { sense: minimize, expression: sum(p) }
```

$`p_{t} \le p_{t \ominus^{\mathrm{season\_of}(t)} 1} \qquad \forall\, t \in \mathcal{T}`$

### `sum_back(array, along=dim, window=n)`

`examples/operators/sum_back.yaml`

```yaml
description: >-
  A trailing window of a fixed width: a unit that started in the last three
  hours is still on.

dimensions:
  unit: { dtype: str }
  hour: { dtype: int }

parameters:
  min_up: { dims: [unit], dtype: int }

variables:
  started:
    dims: [unit, hour]
    domain: binary
  on:
    dims: [unit, hour]
    domain: binary

constraints:
  stays_up_its_own_time:
    dims: [unit, hour]
    expression: sum_back(started, along=hour, window=3) <= on

objective: { sense: minimize, expression: sum(on) }
```

$`\sum_{h' \in \mathcal{H} \,:\, 0 \le h - h' < 3} \mathit{started}_{u,h'} \le \mathit{on}_{u,h} \qquad \forall\, u \in \mathcal{U},\ h \in \mathcal{H}`$

### `sum_back(array, along=dim, window=p)`

`examples/operators/sum_back_by_parameter.yaml`

```yaml
description: >-
  A trailing window whose width is data — `within:` names an integer parameter,
  so a unit stays up for its *own* minimum time rather than one the file fixed.

dimensions:
  unit: { dtype: str }
  hour: { dtype: int }

parameters:
  min_up: { dims: [unit], dtype: int }

variables:
  started:
    dims: [unit, hour]
    domain: binary
  on:
    dims: [unit, hour]
    domain: binary

constraints:
  stays_up_its_own_time:
    dims: [unit, hour]
    expression: sum_back(started, along=hour, window=min_up) <= on

objective: { sense: minimize, expression: sum(on) }
```

$`\sum_{h' \in \mathcal{H} \,:\, 0 \le h - h' < \mathrm{min\_up}} \mathit{started}_{u,h'} \le \mathit{on}_{u,h} \qquad \forall\, u \in \mathcal{U},\ h \in \mathcal{H}`$

### `sum_back(array, along=dim, window=p, edge='wrap')`

`examples/operators/sum_back_wrap.yaml`

```yaml
description: >-
  A trailing window on a representative period that repeats, so the window at
  the first hour reaches back into the last.

dimensions:
  unit: { dtype: str }
  hour: { dtype: int }

parameters:
  min_up: { dims: [unit], dtype: int }

variables:
  started:
    dims: [unit, hour]
    domain: binary
  on:
    dims: [unit, hour]
    domain: binary

constraints:
  stays_up_its_own_time:
    dims: [unit, hour]
    expression: sum_back(started, along=hour, window=min_up, edge='wrap') <= on

objective: { sense: minimize, expression: sum(on) }
```

$`\sum_{h' \in \mathcal{H} \,:\, 0 \le h \ominus h' < \mathrm{min\_up}} \mathit{started}_{u,h'} \le \mathit{on}_{u,h} \qquad \forall\, u \in \mathcal{U},\ h \in \mathcal{H}`$

### `sum_back(array, along=dim, window=n, by=relation)`

`examples/operators/sum_back_partitioned.yaml`

```yaml
description: >-
  A window that stops at each group's edge: representative days are separate
  samples rather than consecutive hours, so a window must not reach across the
  boundary between two of them.

dimensions:
  unit: { dtype: str }
  hour: { dtype: int }
  day: { dtype: str }

relations:
  day_of: { columns: [hour, day], key: hour }

variables:
  started:
    dims: [unit, hour]
    domain: binary
  on:
    dims: [unit, hour]
    domain: binary

constraints:
  stays_up_inside_its_day:
    dims: [unit, hour]
    expression: sum_back(started, along=hour, window=3, by=day_of) <= on

objective: { sense: minimize, expression: sum(on) }
```

$`\sum_{h' \in \mathcal{H} \,:\, 0 \le h -^{\mathrm{day\_of}(h)} h' < 3} \mathit{started}_{u,h'} \le \mathit{on}_{u,h} \qquad \forall\, u \in \mathcal{U},\ h \in \mathcal{H}`$

### `dual(constraint)`

`examples/operators/dual.yaml`

```yaml
description: The row dual — `dual(constraint)` reads a solved constraint's shadow price over its own frame.

dimensions:
  snapshot: { dtype: int }

parameters:
  load: { dims: [snapshot] }

variables:
  p:
    dims: [snapshot]
    bounds: { lower: 0 }

constraints:
  balance:
    dims: [snapshot]
    expression: p >= load

expressions:
  price: dual(balance)

objective: { sense: minimize, expression: sum(p) }
```

$`\mathit{price}_{t} = \lambda_{\mathrm{balance},t} \qquad \forall\, t \in \mathcal{T}`$
<!-- gallery:end -->

Regenerate with `pixi run python -m tools.gallery`.
