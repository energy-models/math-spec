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
    foreach: [snapshot, generator]
    bounds: { lower: 0 }

constraints:
  fleet_budget:
    foreach: []
    expression: sum(p) <= budget

objective: { sense: minimize, expression: sum(p) }
```

$`\sum_{t \in \mathcal{T},\ g \in \mathcal{G}} p_{t,g} \le \mathrm{budget}`$

### `sum(array, consume=dim)`

`examples/operators/sum.yaml`

```yaml
description: The plain reduction — `sum(array, consume=dim)` collapses one dimension.

dimensions:
  snapshot: { dtype: int }
  generator: { dtype: str }

parameters:
  limit: { dims: [snapshot] }

variables:
  p:
    foreach: [snapshot, generator]
    bounds: { lower: 0 }

constraints:
  fleet_total:
    foreach: [snapshot]
    expression: sum(p, consume=generator) <= limit

objective: { sense: minimize, expression: sum(p) }
```

$`\sum_{g \in \mathcal{G}} p_{t,g} \le \mathrm{limit}_{t} \qquad \forall\, t \in \mathcal{T}`$

### `sum(array, by=lookup)`

`examples/operators/sum_by.yaml`

```yaml
description: >-
  The membership reduction — `sum(array, by=lookup)` lands the result on the
  column the lookup is walked to, which is what makes topology data rather than
  structure.

dimensions:
  snapshot: { dtype: int }
  generator: { dtype: str }
  bus: { dtype: str }

lookups:
  gen_bus: { columns: [generator, bus], key: generator }

parameters:
  limit: { dims: [snapshot, bus] }

variables:
  p:
    foreach: [snapshot, generator]
    bounds: { lower: 0 }

constraints:
  bus_total:
    foreach: [snapshot, bus]
    expression: sum(p, by=gen_bus) <= limit

objective: { sense: minimize, expression: sum(p) }
```

$`\sum_{g \in \mathcal{G} \,:\, \mathrm{gen\_bus}(g) = b} p_{t,g} \le \mathrm{limit}_{t,b} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B}`$

### `sum(array, by=[lookup, …])`

`examples/operators/sum_by_lookups.yaml`

```yaml
description: >-
  Grouping through several maps at once — `sum(array, by=[lookup, …])` lands
  the result on every dimension the lookups map into, which is one grouping
  rather than a composition of two: the generator dimension is consumed once.

dimensions:
  snapshot: { dtype: int }
  generator: { dtype: str }
  bus: { dtype: str }
  technology: { dtype: str }

lookups:
  gen_bus: { columns: [generator, bus], key: generator }
  gen_tech: { columns: [generator, technology], key: generator }

parameters:
  limit: { dims: [snapshot, bus, technology] }

variables:
  p:
    foreach: [snapshot, generator]
    bounds: { lower: 0 }

constraints:
  bus_technology_total:
    foreach: [snapshot, bus, technology]
    expression: sum(p, by=[gen_bus, gen_tech]) <= limit

objective: { sense: minimize, expression: sum(p) }
```

$`\sum_{g \in \mathcal{G} \,:\, \mathrm{gen\_bus}(g) = b \wedge \mathrm{gen\_tech}(g) = e} p_{t,g} \le \mathrm{limit}_{t,b,e} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B},\ e \in \mathcal{E}`$

### `at(array, by=lookup)`

`examples/operators/at.yaml`

```yaml
description: >-
  The adjoint of the membership reduction — `at(array, by=lookup)` reads one
  coarse value once per fine label pointing at it.

dimensions:
  snapshot: { dtype: int }
  period: { dtype: int }

lookups:
  period_of: { columns: [snapshot, period], key: snapshot }

parameters:
  cap: { dims: [period] }

variables:
  p:
    foreach: [snapshot]
    bounds: { lower: 0 }

constraints:
  within_cap:
    foreach: [snapshot]
    expression: p <= at(cap, by=period_of)

objective: { sense: minimize, expression: sum(p) }
```

$`p_{t} \le \mathrm{cap}_{\mathrm{period\_of}(t)} \qquad \forall\, t \in \mathcal{T}`$

### `shift(array, over=dim, offset=n)`

`examples/operators/shift.yaml`

```yaml
description: >-
  Translation with no edge policy — the vacated position is absent, so the row
  it would have fed is not built.

dimensions:
  snapshot: { dtype: int }

variables:
  p:
    foreach: [snapshot]
    bounds: { lower: 0 }

constraints:
  no_faster_than_before:
    foreach: [snapshot]
    expression: p <= shift(p, over=snapshot, offset=1)

objective: { sense: minimize, expression: sum(p) }
```

$`p_{t} \le p_{t - 1} \qquad \forall\, t \in \mathcal{T}`$

### `shift(array, over=dim, offset=n, edge='wrap')`

`examples/operators/shift_wrap.yaml`

```yaml
description: >-
  Cyclic translation — the horizon closed on itself, so the first position
  reads the last and nothing is vacated.

dimensions:
  snapshot: { dtype: int }

variables:
  p:
    foreach: [snapshot]
    bounds: { lower: 0 }

constraints:
  no_faster_than_before:
    foreach: [snapshot]
    expression: p <= shift(p, over=snapshot, offset=1, edge='wrap')

objective: { sense: minimize, expression: sum(p) }
```

$`p_{t} \le p_{t \ominus 1} \qquad \forall\, t \in \mathcal{T}`$

### `shift(array, over=dim, offset=n, edge=v)`

`examples/operators/shift_edge.yaml`

```yaml
description: >-
  Translation with a value at the edge — the vacated position contributes the
  number instead of being absent, so the row survives.

dimensions:
  snapshot: { dtype: int }

variables:
  p:
    foreach: [snapshot]
    bounds: { lower: 0 }

constraints:
  no_faster_than_before:
    foreach: [snapshot]
    expression: p <= shift(p, over=snapshot, offset=1, edge=0)

objective: { sense: minimize, expression: sum(p) }
```

$`p_{t} \le p_{t \boxminus_{0} 1} \qquad \forall\, t \in \mathcal{T}`$

### `shift(array, over=dim, offset=p, edge=…)`

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
    foreach: [technology, month]
    bounds: { lower: 0 }

constraints:
  arrives_after_its_lead:
    foreach: [technology, month]
    expression: shift(order, over=month, offset=lead, edge=0) >= demand

objective: { sense: minimize, expression: sum(order) }
```

$`\mathit{order}_{t,m \boxminus_{0} \mathrm{lead}} \ge \mathrm{demand}_{t,m} \qquad \forall\, t \in \mathcal{T},\ m \in \mathcal{M}`$

### `shift(array, over=dim, offset=n, by=lookup)`

`examples/operators/shift_partitioned.yaml`

```yaml
description: >-
  Translation inside a group — each season closed on itself, so a season's first
  snapshot reads that season's last and no level crosses the boundary.

dimensions:
  snapshot: { dtype: int }
  season: { dtype: str }

lookups:
  season_of: { columns: [snapshot, season], key: snapshot }

variables:
  p:
    foreach: [snapshot]
    bounds: { lower: 0 }

constraints:
  no_faster_than_before_in_season:
    foreach: [snapshot]
    expression: p <= shift(p, over=snapshot, offset=1, edge='wrap', by=season_of)

objective: { sense: minimize, expression: sum(p) }
```

$`p_{t} \le p_{t \ominus^{\mathrm{season\_of}(t)} 1} \qquad \forall\, t \in \mathcal{T}`$

### `sum_back(array, over=dim, window=n)`

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
    foreach: [unit, hour]
    domain: binary
  on:
    foreach: [unit, hour]
    domain: binary

constraints:
  stays_up_its_own_time:
    foreach: [unit, hour]
    expression: sum_back(started, over=hour, window=3) <= on

objective: { sense: minimize, expression: sum(on) }
```

$`\sum_{h' \in \mathcal{H} \,:\, 0 \le h - h' < 3} \mathit{started}_{u,h'} \le \mathit{on}_{u,h} \qquad \forall\, u \in \mathcal{U},\ h \in \mathcal{H}`$

### `sum_back(array, over=dim, window=p)`

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
    foreach: [unit, hour]
    domain: binary
  on:
    foreach: [unit, hour]
    domain: binary

constraints:
  stays_up_its_own_time:
    foreach: [unit, hour]
    expression: sum_back(started, over=hour, window=min_up) <= on

objective: { sense: minimize, expression: sum(on) }
```

$`\sum_{h' \in \mathcal{H} \,:\, 0 \le h - h' < \mathrm{min\_up}} \mathit{started}_{u,h'} \le \mathit{on}_{u,h} \qquad \forall\, u \in \mathcal{U},\ h \in \mathcal{H}`$

### `sum_back(array, over=dim, window=p, edge='wrap')`

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
    foreach: [unit, hour]
    domain: binary
  on:
    foreach: [unit, hour]
    domain: binary

constraints:
  stays_up_its_own_time:
    foreach: [unit, hour]
    expression: sum_back(started, over=hour, window=min_up, edge='wrap') <= on

objective: { sense: minimize, expression: sum(on) }
```

$`\sum_{h' \in \mathcal{H} \,:\, 0 \le h \ominus h' < \mathrm{min\_up}} \mathit{started}_{u,h'} \le \mathit{on}_{u,h} \qquad \forall\, u \in \mathcal{U},\ h \in \mathcal{H}`$

### `sum_back(array, over=dim, window=n, by=lookup)`

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

lookups:
  day_of: { columns: [hour, day], key: hour }

variables:
  started:
    foreach: [unit, hour]
    domain: binary
  on:
    foreach: [unit, hour]
    domain: binary

constraints:
  stays_up_inside_its_day:
    foreach: [unit, hour]
    expression: sum_back(started, over=hour, window=3, by=day_of) <= on

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
    foreach: [snapshot]
    bounds: { lower: 0 }

constraints:
  balance:
    foreach: [snapshot]
    expression: p >= load

expressions:
  price: dual(balance)

objective: { sense: minimize, expression: sum(p) }
```

$`\mathit{price}_{t} = \lambda_{\mathrm{balance},t} \qquad \forall\, t \in \mathcal{T}`$
<!-- gallery:end -->

Regenerate with `pixi run python -m tools.gallery`.
