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
| `sum(array, by=lookup)`                            | The lookup's key column collapses onto its value column                                                                                          |
| `sum(array, by=[lookup, …])`                       | The same, onto every lookup's value column. All the lookups must consume the same dimension                                                       |
| `sum(array, by=lookup, from=a, to=b)`              | Column `a` collapses onto column `b`. The other key columns are joined on, so the array carries them and the result keeps them                    |
| `at(array, by=lookup)`                             | The lookup's value column is replaced by its key column                                                                                          |
| `at(array, by=lookup, from=a, to=b)`               | Column `a` is replaced by column `b`, one value per coordinate, so the key lies in `b` and the joined columns                                     |
| `shift(array, over=dim, offset=n)`                 | The value `n` positions earlier along `dim`. The vacated edge is **absent**                                                                       |
| `shift(array, over=dim, offset=n, edge='wrap')`    | The value `n` positions earlier, counted cyclically, so nothing is vacated                                                                        |
| `shift(array, over=dim, offset=n, edge=v)`         | The value `n` positions earlier, with the number `v` standing where the edge was vacated                                                          |
| `shift(array, over=dim, offset=p, edge=…)`         | `p` is an integer parameter, so each entity is reached by its own offset. Declared over what a `by=` groups into, it gives one lag per group      |
| `shift(array, over=dim, offset=n, by=lookup)`      | The translation walks inside each group that the lookup makes. Neighbours, edges and a wrap all belong to that group                              |
| `sum_back(array, over=dim, within=n)`              | The sum of the last `n` positions along `dim`, ending at the position being written                                                               |
| `sum_back(array, over=dim, within=p)`              | `p` is an integer parameter, so each entity gets its own window length                                                                            |
| `sum_back(array, over=dim, within=p, edge='wrap')` | The window reaches around the axis, instead of stopping short at its start                                                                        |
| `sum_back(array, over=dim, within=n, by=lookup)`   | The window stays inside each group that the lookup makes                                                                                          |

`array` is any expression with the right dimension set, so each operator reads a
parameter as readily as a variable. Dimension arguments are name-checked at load,
so `sum(p, over=snapshto)` is an error rather than a silent no-op.
[Every operator as math](#every-operator-as-math) shows how each row prints.

## `sum`

`sum(x, over=d)` adds up `x` along `d`, and `d` is gone from the result.

`sum(x)` names no dimension and reduces every dimension `x` carries, so its
result is a scalar. It is `sum(sum(x, over=a), over=b)` written once.

An operand that is already scalar, and an `over=` naming a dimension the operand
does not carry, are both errors rather than no-ops.

`sum(x, by=l)` sums along a [lookup](dimensions.md#lookups) and lands the result
on the column it walks to: the value column, where the key draws the arrow, or
the one `to=` names. A nodal balance is one `sum(by=)` per kind of component,
and the network's wiring stays in the lookup tables:

```yaml
dimensions:
  bus: { dtype: str }
  generator: { dtype: str }
  line: { dtype: str }
lookups:
  gen_bus: { over: [generator, bus], key: generator }
  line_from: { over: [line, bus], key: line }
  line_to: { over: [line, bus], key: line }
parameters:
  load: { dims: [bus] }
variables:
  p: { foreach: [generator] }
  f: { foreach: [line] }
constraints:
  nodal_balance:
    foreach: [bus]
    expression: >-
      sum(p, by=gen_bus)
      + sum(f, by=line_to)
      - sum(f, by=line_from)
      == load
```

The same `f` is summed twice through two lookups, once as inflow and once as
outflow, with no adjacency matrix and no join written by hand.

Give **at most one** of `over=` and `by=`. A lookup carries its own dimensions,
so `by=` leaves `over=` nothing to add.

`from=` and `to=` say [which columns the walk runs between](dimensions.md#a-walk-names-its-ends)
where the declaration leaves a choice. Every other key column is joined on, so
the operand carries it, the sum keeps it, and each group is one coordinate of
it. A value column that is not walked is not read. A bare relation, one with no
`key:`, is summed with both ends named, and a row it holds twice counts twice.

The lookup's values are the group labels, checked against their own dimension
when the data binds. A group with no members contributes nothing, and a member
whose lookup value is null belongs to no group. An empty group is a value rather
than a gap: on the constant side of a comparison it reads as zero, where a
coordinate the data never covered is refused. See [absence](absence.md).

## `at`

`at(x, by=l)` walks the same lookup table the other way. `sum(by=)` consumes the
key column and produces the value column. `at` consumes the value column and
produces the key column: it reads one coarse value once for each fine label that
points at it. `from=` and `to=` name the two columns where the key leaves a
choice. A read is one value per coordinate, so the lookup's key must lie inside
`to=` and the columns joined on, and a bare relation is never read by `at`.

`at` reads a variable as readily as a parameter. One decision taken per bus, read
once by every line that touches the bus, is `at(decision, by=line_bus)`.

A fine label whose lookup value is null reads nothing, and its row is absent.
That matches the null group in `sum(by=)`. Through a lookup with a
[column joined on](dimensions.md#a-walk-names-its-ends) `at` reads the coarse
value at the row's own coordinate of that column, which is the price of the zone
this generator sat in that period.

## `sum_back`

`sum_back(x, over=d, within=n)` is the sum of the last `n` positions along `d`,
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
  started: { foreach: [unit, hour], domain: binary }
  on: { foreach: [unit, hour], domain: binary }

constraints:
  stays_up_its_own_time:
    foreach: [unit, hour]
    expression: sum_back(started, over=hour, within=min_up) <= on

objective: { sense: minimize, expression: sum(on) }
```

`within=` takes a number or the name of an integer parameter, and never an
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

`by=` keeps the window inside each group that a lookup makes, so no window
reaches out of its own group. The lookup obeys the rules given for
[`shift(by=)`](#a-translation-that-stops-at-each-groups-edge).

## `shift`

`shift(x, over=d, offset=n)` moves values along one dimension by `n` positions,
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
  soc: { foreach: [snapshot, storage] }
  charge: { foreach: [snapshot, storage] }
  discharge: { foreach: [snapshot, storage] }
constraints:
  storage_balance:
    foreach: [snapshot, storage]
    expression: soc == shift(soc, over=snapshot, offset=1, edge='wrap') + charge * eta - discharge
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
  `x <= shift(dt, over=t, offset=1)` into `x <= 0`. The error names the
  rewrites: `edge='wrap'`, `edge=0`, or `edge=0` together with a `where` that
  excludes the vacated coordinate. A `where` on its own does not lift the
  refusal, and `edge=0` on its own leaves a row at that coordinate bounded by
  zero.

`shift` reads parameters too. `shift(dt, over=t, offset=1, edge=0)` is the
previous snapshot's duration, without a pre-shifted copy of the table.

### A translation that stops at each group's edge

`by=` partitions the axis the operator walks, so the neighbour of a coordinate
is the coordinate before it in its own group. A group can be a season, an
investment period or a representative day:

```yaml
dimensions:
  snapshot: { dtype: int }
  season: { dtype: str }
lookups:
  season_of: { over: [snapshot, season], key: snapshot }
parameters:
  inflow: { dims: [snapshot] }
variables:
  soc: { foreach: [snapshot], bounds: { lower: 0 } }
constraints:
  season_balance:
    foreach: [snapshot]
    expression: soc == shift(soc, over=snapshot, offset=1, edge='wrap', by=season_of) + inflow
objective: { sense: minimize, expression: sum(soc) }
```

Every `edge=` setting then applies one group at a time. Bare, the first
coordinate of each group is vacated and its row drops. `edge='wrap'` closes each
group onto its own last coordinate, which a store that returns to its starting
level every period asks for. `edge=v` puts `v` at the edge of each group.

`by=` takes a lookup with a key column over the dimension being walked, and the
group is the value columns. `from=` says which key column where there are two
over that dimension. The value columns are what a named `offset=` may vary over,
so each group is reached by its own offset.

A coordinate the lookup sends nowhere is in no group, so it reaches nothing, and
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
    foreach: [technology, month]
    bounds: { lower: 0 }
constraints:
  arrives_after_its_lead:
    foreach: [technology, month]
    expression: shift(order, over=month, offset=lead, edge=0) >= demand
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
  lookup groups into.

A named offset may be bare. Its vacated positions differ per entity, and they
are absent exactly as a numeric offset's are. A bare `shift` over an expression
with no variable stays refused, for the reason given [above](#shift).

The sign travels in the values. `offset=-lead` is refused, so a row that points
backwards says so where the data is read.

### A lag that differs per group

`offset=` may name a parameter declared over the dimension that a
[`by=`](#a-translation-that-stops-at-each-groups-edge) lookup groups into. Then
every snapshot of a period moves by that period's own lead time, and no
coordinate reaches out of its own group:

```yaml
dimensions:
  snapshot: { dtype: int }
  period: { dtype: int }
lookups:
  period_of: { over: [snapshot, period], key: snapshot }
parameters:
  lead: { dims: [period], dtype: int }
  demand: { dims: [snapshot] }
variables:
  order:
    foreach: [snapshot]
    bounds: { lower: 0 }
constraints:
  arrives_after_its_periods_lead:
    foreach: [snapshot]
    expression: shift(order, over=snapshot, offset=lead, by=period_of, edge=0) >= demand
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
| `sum(array, by=lookup)` | $`\sum_{g \in \mathcal{G} \,:\, \mathrm{gen\_bus}(g) = b} p_{t,g} \le \mathrm{limit}_{t,b} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B}`$ |
| `sum(array, by=[lookup, …])` | $`\sum_{g \in \mathcal{G} \,:\, \mathrm{gen\_bus}(g) = b \wedge \mathrm{gen\_tech}(g) = e} p_{t,g} \le \mathrm{limit}_{t,b,e} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B},\ e \in \mathcal{E}`$ |
| `at(array, by=lookup)` | $`p_{t} \le \mathrm{cap}_{\mathrm{period\_of}(t)} \qquad \forall\, t \in \mathcal{T}`$ |
| `shift(array, over=dim, offset=n)` | $`p_{t} \le p_{t - 1} \qquad \forall\, t \in \mathcal{T}`$ |
| `shift(array, over=dim, offset=n, edge='wrap')` | $`p_{t} \le p_{t \ominus 1} \qquad \forall\, t \in \mathcal{T}`$ |
| `shift(array, over=dim, offset=n, edge=v)` | $`p_{t} \le p_{t \boxminus_{0} 1} \qquad \forall\, t \in \mathcal{T}`$ |
| `shift(array, over=dim, offset=p, edge=…)` | $`\mathit{order}_{t,m \boxminus_{0} \mathrm{lead}} \ge \mathrm{demand}_{t,m} \qquad \forall\, t \in \mathcal{T},\ m \in \mathcal{M}`$ |
| `shift(array, over=dim, offset=n, by=lookup)` | $`p_{t} \le p_{t \ominus^{\mathrm{season\_of}(t)} 1} \qquad \forall\, t \in \mathcal{T}`$ |
| `sum_back(array, over=dim, within=n)` | $`\sum_{h' \in \mathcal{H} \,:\, 0 \le h - h' < 3} \mathit{started}_{u,h'} \le \mathit{on}_{u,h} \qquad \forall\, u \in \mathcal{U},\ h \in \mathcal{H}`$ |
| `sum_back(array, over=dim, within=p)` | $`\sum_{h' \in \mathcal{H} \,:\, 0 \le h - h' < \mathrm{min\_up}} \mathit{started}_{u,h'} \le \mathit{on}_{u,h} \qquad \forall\, u \in \mathcal{U},\ h \in \mathcal{H}`$ |
| `sum_back(array, over=dim, within=p, edge='wrap')` | $`\sum_{h' \in \mathcal{H} \,:\, 0 \le h \ominus h' < \mathrm{min\_up}} \mathit{started}_{u,h'} \le \mathit{on}_{u,h} \qquad \forall\, u \in \mathcal{U},\ h \in \mathcal{H}`$ |
| `sum_back(array, over=dim, within=n, by=lookup)` | $`\sum_{h' \in \mathcal{H} \,:\, 0 \le h -^{\mathrm{day\_of}(h)} h' < 3} \mathit{started}_{u,h'} \le \mathit{on}_{u,h} \qquad \forall\, u \in \mathcal{U},\ h \in \mathcal{H}`$ |
| `dual(constraint)` | $`\mathit{price}_{t} = \lambda_{\mathrm{balance},t} \qquad \forall\, t \in \mathcal{T}`$ |

$`t \ominus k`$ denotes cyclic translation: index $`t-k`$ taken modulo the size of the dimension (`roll`). Plain $`t-k`$ (`shift`) has no wraparound — terms translated past the edge are simply absent.

$`t \boxminus_{v} k`$ denotes translation with $`v`$ standing where index $`t-k`$ leaves the dimension (`shift(edge=v)`), so the row at that boundary is built and carries $`v`$ rather than being dropped.

$`t \ominus^{\mathrm{lookup}(t)} k`$ denotes a translation counted inside the group a lookup puts $`t`$ in (`shift(by=lookup)`), so a term never crosses out of its own group.
<!-- operator-math:end -->

Regenerate with `pixi run python -m tools.spec_math`.
