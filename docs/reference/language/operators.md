<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Operators

An operator reduces an expression along a dimension, or moves its values along
one. The set is **closed**: these four, and [`dual`](reported.md#reading-a-constraints-dual)
in a reported expression, are all of them. There is no registry to add to, so a
model can never depend on what a caller registered. A composition of them goes in
[`macros:`](expressions.md#macros).

| Operator                                           | Result                                                                                                                                            |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sum(array)`                                       | Every dimension that `array` carries collapses. The result is a scalar                                                                            |
| `sum(array, over=dim)`                             | `dim` collapses. `array` must carry `dim`                                                                                                         |
| `sum(array, by=relation)`                            | The relation's key column collapses onto its value column                                                                                          |
| `sum(array, by=[relation, …])`                       | The same, onto every relation's value column. All the relations must consume the same dimension                                                       |
| `sum(array, by=relation, over=a -> b)`               | Dimension `a` collapses onto column `b`. The other key columns are joined on, so the array carries them and the result keeps them. The key column over `a` leaves, so a value column cannot: reading one is `at`'s |
| `sum(array, by=relation, over=[a, …] -> [b, …])`     | The same with several dimensions and columns at either end: consumed together, landed on a product                                                 |
| `at(array, by=relation)`                             | The relation's value column is replaced by its key column                                                                                          |
| `at(array, by=relation, over=a)`                     | Column `a` is replaced by the key, one value per coordinate. A key column whose dimension `array` carries is read at the array's own coordinate. `a` may be a list |
| `shift(array, along=dim, offset=n)`                 | The value `n` positions earlier along `dim`. The vacated edge is **absent**                                                                       |
| `shift(array, along=dim, offset=n, edge='wrap')`    | The value `n` positions earlier, counted cyclically, so nothing is vacated                                                                        |
| `shift(array, along=dim, offset=n, edge=v)`         | The value `n` positions earlier, with the number `v` standing where the edge was vacated                                                          |
| `shift(array, along=dim, offset=p, edge=…)`         | `p` is an integer parameter, so each entity is reached by its own offset. Declared over what a `by=` groups into, it gives one lag per group      |
| `shift(array, along=dim, offset=n, by=relation[, within=c])` | The translation walks inside each group that the relation makes. Neighbours, edges and a wrap all belong to that group                              |
| `sum_back(array, along=dim, window=n)`              | The sum of the last `n` positions along `dim`, ending at the position being written                                                               |
| `sum_back(array, along=dim, window=p)`              | `p` is an integer parameter, so each entity gets its own window length                                                                            |
| `sum_back(array, along=dim, window=p, edge='wrap')` | The window reaches around the axis, instead of stopping short at its start                                                                        |
| `sum_back(array, along=dim, window=n, by=relation)`   | The window stays inside each group that the relation makes                                                                                          |

`array` is any expression with the right dimension set, so each operator reads a
parameter as readily as a variable. Dimension arguments are name-checked at load,
so `sum(p, over=snapshto)` is an error rather than a silent no-op.
[Every operator as math](#every-operator-as-math) shows how each row prints.

## `sum`

`sum(x, over=d)` adds up `x` along `d`, and `d` is gone from the result.

`sum(x)` names no dimension and reduces every dimension `x` carries, so its
result is a scalar. It is `sum(sum(x, over=a), over=b)` written once.

An operand that is already scalar, and a `over=` naming a dimension the
operand does not carry, are both errors rather than no-ops.

`sum(x, by=l)` sums through a [relation](dimensions.md#relations) and lands the result
on the column it walks to: the value column, where the key draws the arrow, or
the one `over=a -> b` lands on. A nodal balance is one `sum(by=)` per kind of component,
and the network's wiring stays in the relations:

```yaml
dimensions:
  bus: { dtype: str }
  generator: { dtype: str }
  line: { dtype: str }
relations:
  gen_bus: { key: generator, value: bus }
  line_from: { key: line, value: bus }
  line_to: { key: line, value: bus }
parameters:
  load: { dims: [bus] }
variables:
  p: { dims: [generator] }
  f: { dims: [line] }
constraints:
  nodal_balance:
    dims: [bus]
    expression: >-
      sum(p, by=gen_bus)
      + sum(f, by=line_to)
      - sum(f, by=line_from)
      == load
```

The same `f` is summed twice through two relations, once as inflow and once as
outflow, with no adjacency matrix and no join written by hand.

`sum(by=)` consumes a key column and produces a value column. Beside `by=`,
`over=a -> b` names the direction where the relation offers a choice: the
dimension `a` leaves and the column `b` arrives ([walks](dimensions.md#walks)).
Every other key column is joined on, so each group is one coordinate of it.
`over=` on its own is a reduction over a dimension.
A bare relation, one with no `value:`, is summed with both ends named, and a row
it holds twice counts twice.

The relation's values are the group labels, checked against their own dimension
when the data binds. A group with no members contributes nothing, and a member
whose relation value is null belongs to no group. An empty group is a value rather
than a gap: on the constant side of a comparison it reads as zero, where a
coordinate the data never covered is refused. See [absence](absence.md).

## `at`

`at(x, by=l)` walks the same relation the other way. It consumes a value column
and lands on the key, so it reads one coarse value once for each fine label that
points at it, and a bare relation is never read by `at`. `over=` names the value
column where the relation offers two. The key needs no naming: a key column
whose dimension `x` carries is read at the row's own coordinate, and the rest
are produced ([walks](dimensions.md#walks)).

`at` reads a variable as readily as a parameter. One decision taken per bus, read
once by every line that touches the bus, is `at(decision, by=line_bus)`.

A fine label whose relation value is null reads nothing, and its row is absent.
That matches the null group in `sum(by=)`.

## `sum_back`

`sum_back(x, along=d, window=n)` is the sum of the last `n` positions along `d`,
ending at the position being written. It states a minimum up time, a rolling
budget or a delivery horizon. A width of `1` is `x` itself.

The dimension **survives**. `sum` reduces it away, but `sum_back` leaves one
value per position, and each value reads a window of its own.

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

`window=` takes a number or the name of an integer parameter, and never an
expression. With a parameter, each entity gets a window of its own length. A
fixed width can be written as a run of `shift`s; a width that is a column
cannot. Two rules hold for a named width, and breaking either is a load error:

- **The width is integral.** A width counts positions, so the parameter is
  `dtype: int`, and an `int` declaration binds only an integer column.
- **The width does not vary along the dimension being summed.** A width that
  changed along that axis would give a different window at every position.

`edge=` takes `'wrap'` or nothing. A window that reaches past the start of the
axis is **short**, not empty: the position being written is always inside its own
window, so no row is lost and there is nothing vacated to fill. A number here is
a load error, because the expression can add a constant itself. `edge='wrap'`
makes the window reach around the axis, which a representative period that
repeats asks for.

`by=` keeps the window inside each group that a relation makes, so no window
reaches out of its own group. The relation obeys the rules given for
[`shift(by=)`](#a-translation-that-stops-at-each-groups-edge).

## `shift`

`shift(x, along=d, offset=n)` moves values along one dimension by `n` positions,
counted in the dimension's **declared order**. The value at each coordinate
becomes the value that stood `n` places before it. Only the values move, and the
coordinates stay in place. `edge=` says what stands where nothing moved in.

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

`edge='wrap'` makes a battery cyclic without a boundary condition written out:
the first snapshot reads the last.

`edge=` has three settings:

- **Bare.** The vacated coordinate is [absent](absence.md). Absence spreads, so
  the row it would have fed is not built. An acyclic recurrence then has no row
  at its first coordinate, and the model states the initial condition itself
  under a complementary `where`. See
  [two regimes, two blocks](declarations.md#constraints).
- **`'wrap'`.** The translation is cyclic, so nothing is vacated.
- **A number.** That number stands where the slot was vacated, and the row
  survives. It is a number rather than a flag because the identity depends on
  the position: `0` in a sum, and `1` in a product.

Two rules hold across all three:

- **Over a variable, the only numeric edge is `0`.** A vacated slot then
  contributes no term. A non-zero number would be a constant standing where a
  term used to be.
- **A bare `shift` over an expression with no variable is a load error.** A
  parameter's missing row is a zero coefficient, so there is no absence for the
  vacated slot to carry, and inventing one would turn
  `x <= shift(dt, along=t, offset=1)` into `x <= 0`. The error names the
  rewrites: `edge='wrap'`, `edge=0`, or `edge=0` together with a `where` that
  excludes the vacated coordinate. A `where` on its own does not lift the
  refusal, and `edge=0` on its own leaves a row at that coordinate bounded by
  zero.

`shift` reads parameters too. `shift(dt, along=t, offset=1, edge=0)` is the
previous snapshot's duration, without a pre-shifted copy of the table.

### A translation that stops at each group's edge

`by=` partitions the axis the operator walks, so the neighbour of a coordinate
is the coordinate before it in its own group. A group can be a season, an
investment period or a representative day:

```yaml
dimensions:
  snapshot: { dtype: int }
  season: { dtype: str }
relations:
  season_of: { key: snapshot, value: season }
parameters:
  inflow: { dims: [snapshot] }
variables:
  soc: { dims: [snapshot], bounds: { lower: 0 } }
constraints:
  season_balance:
    dims: [snapshot]
    expression: soc == shift(soc, along=snapshot, offset=1, edge='wrap', by=season_of) + inflow
objective: { sense: minimize, expression: sum(soc) }
```

Every `edge=` setting then applies one group at a time. Bare, the first
coordinate of each group is vacated and its row drops. `edge='wrap'` closes each
group onto its own last coordinate, which a store that returns to its starting
level every period asks for. `edge=v` puts `v` at the edge of each group.

`by=` takes a relation with a key column over the dimension being walked, and the
group is the value columns: all of them, or the ones `within=` names, so one
calendar table serves `within=day` and `within=week` alike. The group columns are
what a named `offset=` may vary over, so each group is reached by its own offset.

A coordinate the relation sends nowhere is in no group, so it reaches nothing, and
no `edge=` speaks for it. Its row drops under `edge=0` exactly as it does bare.

Without `by=`, `edge='wrap'` wraps the whole axis: the last coordinate of the
dimension feeds the first.

### An offset that differs per entity

`offset=` may name an integer parameter instead of a number. Then each entity is
reached by its own offset: a construction lead time, a transit time, or any delay
the source data carries as a column:

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

Three rules keep this a translation. Breaking any of them is a load error that
names its rewrite:

- **The parameter is integral.** An offset lands on a coordinate, so it is
  `dtype: int`, and an `int` declaration binds only an integer column.
- **The parameter does not vary along the dimension being translated.** An
  offset that varied along the axis it moves along would be a permutation, not
  a lag.
- **The parameter varies only over dimensions where the shift can read it.**
  Those are the dimensions of the shifted expression, and the dimension a `by=`
  relation groups into.

A named offset may be bare. Its vacated positions differ per entity, and they
are absent exactly as a numeric offset's are. A bare `shift` over an expression
with no variable stays refused, for the reason given [above](#shift).

The sign travels in the values. `offset=-lead` is refused, so a row that points
backwards says so where the data is read.

### A lag that differs per group

`offset=` may name a parameter declared over the dimension that a
[`by=`](#a-translation-that-stops-at-each-groups-edge) relation groups into. Then
every snapshot of a period moves by that period's own lead time, and no
coordinate reaches out of its own group:

```yaml
dimensions:
  snapshot: { dtype: int }
  period: { dtype: int }
relations:
  period_of: { key: snapshot, value: period }
parameters:
  lead: { dims: [period], dtype: int }
  demand: { dims: [snapshot] }
variables:
  order:
    dims: [snapshot]
    bounds: { lower: 0 }
constraints:
  arrives_after_its_periods_lead:
    dims: [snapshot]
    expression: shift(order, along=snapshot, offset=lead, by=period_of, edge=0) >= demand
objective: { sense: minimize, expression: sum(order) }
```

The offset is legal here because the partition puts each snapshot's period within
reach. The two keys compose: `lead: {dims: [technology, period]}` gives one lag
per technology per period.

## Every operator as math

Each row below is generated from one model in
[`examples/operators/`](https://github.com/energy-models/math-spec/tree/main/examples/operators),
printed by the [typesetter](../typeset.md). So a row cannot outlive the operator
it documents, and two operators that print the same way show it here. The three
`shift` rows differ only at the boundary. The models themselves are on
[One construct per model](../../examples/operators.md), and the rest of the
language prints on [Every construct, as math](../notation.md).

<!-- operator-math:begin -->
| Operator | Renders as |
|---|---|
| `sum(array)` | $`\sum_{t \in \mathcal{T},\ g \in \mathcal{G}} p_{t,g} \le \mathrm{budget}`$ |
| `sum(array, over=dim)` | $`\sum_{g \in \mathcal{G}} p_{t,g} \le \mathrm{limit}_{t} \qquad \forall\, t \in \mathcal{T}`$ |
| `sum(array, by=relation)` | $`\sum_{g \in \mathcal{G} \,:\, \mathrm{gen\_bus}(g) = b} p_{t,g} \le \mathrm{limit}_{t,b} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B}`$ |
| `sum(array, by=[relation, …])` | $`\sum_{g \in \mathcal{G} \,:\, \mathrm{gen\_bus}(g) = b \wedge \mathrm{gen\_tech}(g) = e} p_{t,g} \le \mathrm{limit}_{t,b,e} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B},\ e \in \mathcal{E}`$ |
| `sum(array, by=relation, over=a -> b)` | $`\sum_{g \in \mathcal{G} \,:\, \mathrm{zone\_of}(g,\ e) = z} p_{g,e} \ge \mathrm{demand}_{z,e} \qquad \forall\, z \in \mathcal{Z},\ e \in \mathcal{E}`$ |
| `sum(array, by=relation, over=[a, …] -> [b, …])` | $`\sum_{g \in \mathcal{G},\ e \in \mathcal{E} \,:\, \mathrm{slot\_of.bus}(g,\ e) = b \wedge \mathrm{slot\_of.technology}(g,\ e) = t} p_{g,e} \le \mathrm{cap}_{b,t} \qquad \forall\, b \in \mathcal{B},\ t \in \mathcal{T}`$ |
| `at(array, by=relation)` | $`p_{t} \le \mathrm{cap}_{\mathrm{period\_of}(t)} \qquad \forall\, t \in \mathcal{T}`$ |
| `at(array, by=relation, over=a)` | $`f_{l} \le \mathrm{cap}_{\mathrm{ends.bus0}(l)} \qquad \forall\, l \in \mathcal{L}`$ |
| `shift(array, along=dim, offset=n)` | $`p_{t} \le p_{t - 1} \qquad \forall\, t \in \mathcal{T}`$ |
| `shift(array, along=dim, offset=n, edge='wrap')` | $`p_{t} \le p_{t \ominus 1} \qquad \forall\, t \in \mathcal{T}`$ |
| `shift(array, along=dim, offset=n, edge=v)` | $`p_{t} \le p_{t \boxminus_{0} 1} \qquad \forall\, t \in \mathcal{T}`$ |
| `shift(array, along=dim, offset=p, edge=…)` | $`\mathit{order}_{t,m \boxminus_{0} \mathrm{lead}} \ge \mathrm{demand}_{t,m} \qquad \forall\, t \in \mathcal{T},\ m \in \mathcal{M}`$ |
| `shift(array, along=dim, offset=n, by=relation)` | $`p_{t} \le p_{t \ominus^{\mathrm{season\_of}(t)} 1} \qquad \forall\, t \in \mathcal{T}`$ |
| `sum_back(array, along=dim, window=n)` | $`\sum_{h' \in \mathcal{H} \,:\, 0 \le h - h' < 3} \mathit{started}_{u,h'} \le \mathit{on}_{u,h} \qquad \forall\, u \in \mathcal{U},\ h \in \mathcal{H}`$ |
| `sum_back(array, along=dim, window=p)` | $`\sum_{h' \in \mathcal{H} \,:\, 0 \le h - h' < \mathrm{min\_up}} \mathit{started}_{u,h'} \le \mathit{on}_{u,h} \qquad \forall\, u \in \mathcal{U},\ h \in \mathcal{H}`$ |
| `sum_back(array, along=dim, window=p, edge='wrap')` | $`\sum_{h' \in \mathcal{H} \,:\, 0 \le h \ominus h' < \mathrm{min\_up}} \mathit{started}_{u,h'} \le \mathit{on}_{u,h} \qquad \forall\, u \in \mathcal{U},\ h \in \mathcal{H}`$ |
| `sum_back(array, along=dim, window=n, by=relation)` | $`\sum_{h' \in \mathcal{H} \,:\, 0 \le h -^{\mathrm{day\_of}(h)} h' < 3} \mathit{started}_{u,h'} \le \mathit{on}_{u,h} \qquad \forall\, u \in \mathcal{U},\ h \in \mathcal{H}`$ |
| `dual(constraint)` | $`\mathit{price}_{t} = \lambda_{\mathrm{balance},t} \qquad \forall\, t \in \mathcal{T}`$ |

$`t \ominus k`$ denotes cyclic translation: index $`t-k`$ taken modulo the size of the dimension (`roll`). Plain $`t-k`$ (`shift`) has no wraparound — terms translated past the edge are simply absent.

$`t \boxminus_{v} k`$ denotes translation with $`v`$ standing where index $`t-k`$ leaves the dimension (`shift(edge=v)`), so the row at that boundary is built and carries $`v`$ rather than being dropped.

$`t \ominus^{\mathrm{relation}(t)} k`$ denotes a translation counted inside the group a relation puts $`t`$ in (`shift(by=relation)`), so a term never crosses out of its own group.
<!-- operator-math:end -->

Regenerate with `pixi run python -m tools.spec_math`.
