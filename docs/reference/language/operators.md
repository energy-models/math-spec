<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Operators

An operator reduces an expression along a dimension, or moves its values along
one. The set is **closed**: these four, and [`dual`](named.md#reading-a-constraints-dual)
in a reported expression, are all of them. A composition of them goes in
[`macros:`](named.md#macros).

| Operator                                           | Result                                                                                                                                                            |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sum(array)`                                       | Every dimension that `array` carries collapses. The result is a scalar                                                                                            |
| `sum(array, over=dim)`                             | `dim` collapses. `array` must carry `dim`                                                                                                                         |
| `sum(array, by=relation, over=a, into=b)`              | Column `a` collapses onto column `b`. The other key columns are joined on, so the array carries them and the result keeps them                                    |
| `sum(array, by=relation, over=[a, …], into=[b, …])`    | The same with several columns on either side: consumed together, landed on a product                                                                              |
| `at(array, by=relation, over=a, into=b)`               | Column `a` is replaced by column `b`, one value per coordinate. Either may be a list                                                                               |
| `shift(array, along=dim, offset=n)`                 | The value `n` positions earlier along `dim`. The vacated edge is **absent**                                                                                        |
| `shift(array, along=dim, offset=n, edge='wrap')`    | The value `n` positions earlier, counted cyclically, so nothing is vacated                                                                                        |
| `shift(array, along=dim, offset=n, edge=v)`         | The value `n` positions earlier, with the number `v` standing where the edge was vacated                                                                          |
| `shift(array, along=dim, offset=p, edge=…)`         | `p` is an integer parameter, so each entity is reached by its own offset                                                                                          |
| `shift(array, along=dim, offset=n, by=relation, within=c)` | The translation steps inside each group that the relation's column `c` makes. Neighbours, edges and a wrap all belong to that group                        |
| `sum_back(array, along=dim, window=n)`              | The sum of the last `n` positions along `dim`, ending at the position being written                                                                               |
| `sum_back(array, along=dim, window=p)`              | `p` is an integer parameter, so each entity gets its own window length                                                                                            |
| `sum_back(array, along=dim, window=p, edge='wrap')` | The window reaches around the axis, instead of stopping short at its start                                                                                        |
| `sum_back(array, along=dim, window=n, by=relation, within=c)` | The window stays inside each group that the relation's column `c` makes                                                                                     |

`array` is any expression with the right dimension set, a parameter or a
variable. [Every operator as math](#every-operator-as-math) shows how each row
prints.

## `sum`

`sum(x)` on a scalar is an error. A nodal balance is one `sum(by=)` per kind of
component:

```yaml
dimensions:
  bus: { dtype: str }
  generator: { dtype: str }
  line: { dtype: str }
relations:
  gen_bus: { key: generator, values: bus }
  line_from: { key: line, values: bus }
  line_to: { key: line, values: bus }
parameters:
  load: { dims: [bus] }
variables:
  p: { dims: [generator] }
  f: { dims: [line] }
constraints:
  nodal_balance:
    dims: [bus]
    expression: >-
      sum(p, by=gen_bus, over=generator, into=bus)
      + sum(f, by=line_to, over=line, into=bus)
      - sum(f, by=line_from, over=line, into=bus)
      == load
```

What a call through a relation reads and carries is on
[how a relation is used](relations.md#how-a-relation-is-used).

## `at`

`at` reads one coarse value once for each fine label that points at it
([reads](relations.md#aggregates-and-reads)). One decision per bus, read by
every line that touches the bus, is
`at(decision, by=line_bus, over=bus, into=line)`.

## `sum_back`

`sum_back` states a minimum up time, a rolling budget or a delivery horizon.
The dimension **survives**, and a width of `1` is `x` itself.

```yaml
dimensions:
  unit: { dtype: str }
  hour: { dtype: int }

parameters:
  min_up: { dims: [unit], dtype: int }

variables:
  started: { dims: [unit, hour], domain: binary }
  on: { dims: [unit, hour], domain: binary }

constraints:
  stays_up_its_own_time:
    dims: [unit, hour]
    expression: sum_back(started, along=hour, window=min_up) <= on

objective: { sense: minimize, expression: sum(on) }
```

A named width is `dtype: int`, and does not vary along the dimension being
summed.

`edge=` takes `'wrap'` or nothing, and a number is a load error. Without it, a
window that reaches past the start of the axis is **short**, and no row is lost.

`by=` takes a [partition](relations.md#partitions).

## `shift`

`shift` counts positions in the dimension's **declared order**. `edge=` says
what stands where nothing moved in.

```yaml
dimensions:
  snapshot: { dtype: int }
  storage: { dtype: str }
parameters:
  eta: { dims: [storage] }
variables:
  soc: { dims: [snapshot, storage] }
  charge: { dims: [snapshot, storage] }
  discharge: { dims: [snapshot, storage] }
constraints:
  storage_balance:
    dims: [snapshot, storage]
    expression: soc == shift(soc, along=snapshot, offset=1, edge='wrap') + charge * eta - discharge
```

`edge='wrap'` makes the store cyclic: the first snapshot reads the last. Bare,
the row the vacated coordinate would have fed is not built; state the initial
condition in a block of its own ([a rule that differs by regime](../../howto/regimes.md)).

Two rules hold for `edge=`:

- **Over a variable, the only numeric edge is `0`.**
- **A bare `shift` over an expression with no variable is a load error.** The
  error names the rewrites: `edge='wrap'`, `edge=0`, or `edge=0` together with
  a `where` that excludes the vacated coordinate.

### Translation within groups

`by=` takes a [partition](relations.md#partitions), and the neighbour of a
coordinate is the one before it in its own group, such as a season:

```yaml
dimensions:
  snapshot: { dtype: int }
  season: { dtype: str }
relations:
  season_of: { key: snapshot, values: season }
parameters:
  inflow: { dims: [snapshot] }
variables:
  soc: { dims: [snapshot], bounds: { lower: 0 } }
constraints:
  season_balance:
    dims: [snapshot]
    expression: soc == shift(soc, along=snapshot, offset=1, edge='wrap', by=season_of, within=season) + inflow
objective: { sense: minimize, expression: sum(soc) }
```

Every `edge=` setting then applies one group at a time. A coordinate in no
group drops under every `edge=`.

### A parameter as offset

An offset per entity is a construction lead time, a transit time, or any delay
the data carries as a column:

```yaml
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

Each of these is a load error:

- **The parameter is not `dtype: int`.**
- **The parameter varies along the dimension being translated.**
- **The parameter varies over a dimension the shift cannot read.** The shift
  reads the dimensions of the shifted expression, and the dimension a
  [`by=`](#translation-within-groups) relation groups into: `offset=lead`
  with `lead: {dims: [period]}` under `by=period_of` gives one lag per period.

The sign travels in the values: `offset=-lead` is refused.

## Every operator as math

Each row is generated from one model in
[`examples/operators/`](https://github.com/energy-models/math-spec/tree/main/examples/operators),
printed by the [typesetter](../typeset.md). The models themselves are on
[One construct per model](../../examples/operators.md), and the rest of the
language prints on [Every construct, as math](../notation.md).

<!-- operator-math:begin -->
| Operator | Renders as |
|---|---|
| `sum(array)` | $`\sum_{t \in \mathcal{T},\ g \in \mathcal{G}} p_{t,g} \le \mathrm{budget}`$ |
| `sum(array, over=dim)` | $`\sum_{g \in \mathcal{G}} p_{t,g} \le \mathrm{limit}_{t} \qquad \forall\, t \in \mathcal{T}`$ |
| `sum(array, by=relation, over=a, into=b)` | $`\sum_{g \in \mathcal{G} \,:\, \mathrm{gen\_bus}(g) = b} p_{t,g} \le \mathrm{limit}_{t,b} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B}`$ |
| `sum(array, by=relation, over=a, into=b), joining on the rest of the key` | $`\sum_{g \in \mathcal{G} \,:\, \mathrm{zone\_of}(g,\ e) = z} p_{g,e} \ge \mathrm{demand}_{z,e} \qquad \forall\, z \in \mathcal{Z},\ e \in \mathcal{E}`$ |
| `sum(array, by=relation, over=[a, …], into=[b, …])` | $`\sum_{g \in \mathcal{G},\ e \in \mathcal{E} \,:\, \mathrm{slot\_of.bus}(g,\ e) = b \wedge \mathrm{slot\_of.technology}(g,\ e) = t} p_{g,e} \le \mathrm{cap}_{b,t} \qquad \forall\, b \in \mathcal{B},\ t \in \mathcal{T}`$ |
| `at(array, by=relation, over=a, into=b)` | $`p_{t} \le \mathrm{cap}_{\mathrm{period\_of}(t)} \qquad \forall\, t \in \mathcal{T}`$ |
| `at(array, by=relation, over=a, into=b), two columns over one dimension` | $`f_{l} \le \mathrm{cap}_{\mathrm{ends.bus0}(l)} \qquad \forall\, l \in \mathcal{L}`$ |
| `shift(array, along=dim, offset=n)` | $`p_{t} \le p_{t - 1} \qquad \forall\, t \in \mathcal{T}`$ |
| `shift(array, along=dim, offset=n, edge='wrap')` | $`p_{t} \le p_{t \ominus 1} \qquad \forall\, t \in \mathcal{T}`$ |
| `shift(array, along=dim, offset=n, edge=v)` | $`p_{t} \le p_{t \boxminus_{0} 1} \qquad \forall\, t \in \mathcal{T}`$ |
| `shift(array, along=dim, offset=p, edge=…)` | $`\mathit{order}_{t,m \boxminus_{0} \mathrm{lead}} \ge \mathrm{demand}_{t,m} \qquad \forall\, t \in \mathcal{T},\ m \in \mathcal{M}`$ |
| `shift(array, along=dim, offset=n, by=relation, within=c)` | $`p_{t} \le p_{t \ominus^{\mathrm{season\_of}(t)} 1} \qquad \forall\, t \in \mathcal{T}`$ |
| `sum_back(array, along=dim, window=n)` | $`\sum_{h' \in \mathcal{H} \,:\, 0 \le h - h' < 3} \mathit{started}_{u,h'} \le \mathit{on}_{u,h} \qquad \forall\, u \in \mathcal{U},\ h \in \mathcal{H}`$ |
| `sum_back(array, along=dim, window=p)` | $`\sum_{h' \in \mathcal{H} \,:\, 0 \le h - h' < \mathrm{min\_up}} \mathit{started}_{u,h'} \le \mathit{on}_{u,h} \qquad \forall\, u \in \mathcal{U},\ h \in \mathcal{H}`$ |
| `sum_back(array, along=dim, window=p, edge='wrap')` | $`\sum_{h' \in \mathcal{H} \,:\, 0 \le h \ominus h' < \mathrm{min\_up}} \mathit{started}_{u,h'} \le \mathit{on}_{u,h} \qquad \forall\, u \in \mathcal{U},\ h \in \mathcal{H}`$ |
| `sum_back(array, along=dim, window=n, by=relation, within=c)` | $`\sum_{h' \in \mathcal{H} \,:\, 0 \le h -^{\mathrm{day\_of}(h)} h' < 3} \mathit{started}_{u,h'} \le \mathit{on}_{u,h} \qquad \forall\, u \in \mathcal{U},\ h \in \mathcal{H}`$ |
| `dual(constraint)` | $`\mathit{price}_{t} = \lambda_{\mathrm{balance},t} \qquad \forall\, t \in \mathcal{T}`$ |

$`t \ominus k`$ denotes cyclic translation: index $`t-k`$ taken modulo the size of the dimension (`roll`). Plain $`t-k`$ (`shift`) has no wraparound — terms translated past the edge are simply absent.

$`t \boxminus_{v} k`$ denotes translation with $`v`$ standing where index $`t-k`$ leaves the dimension (`shift(edge=v)`), so the row at that boundary is built and carries $`v`$ rather than being dropped.

$`t \ominus^{\mathrm{relation}(t)} k`$ denotes a translation counted inside the group a relation puts $`t`$ in (`shift(by=relation)`), so a term never crosses out of its own group.
<!-- operator-math:end -->

Regenerate with `pixi run python -m tools.spec_math`.
