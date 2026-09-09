<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Operators

An operator reduces an expression along a dimension, or re-indexes it. These
are the operators the language has:

| Operator                                           | Result                                                                                                                                            |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sum(array)`                                       | Every dimension that `array` carries collapses. The result is a scalar                                                                            |
| `sum(array, over=dim)`                             | `dim` collapses. `array` must carry `dim`                                                                                                         |
| `sum(array, by=lookup)`                            | The dimension that the lookup is over collapses onto the dimension it maps into                                                                   |
| `sum(array, by=[lookup, …])`                       | The same, onto every dimension that the lookups map into. All the lookups must be over the same dimension                                         |
| `at(array, by=lookup)`                             | The dimension that the lookup maps into is replaced by the dimension it is over                                                                   |
| `shift(array, over=dim, offset=n)`                 | The value `n` positions earlier along `dim`. The vacated edge is **absent**                                                                           |
| `shift(array, over=dim, offset=n, edge='wrap')`    | The value `n` positions earlier, counted cyclically, so nothing is vacated                                                                        |
| `shift(array, over=dim, offset=n, edge=v)`         | The value `n` positions earlier, with the number `v` standing where the edge was vacated                                                          |
| `shift(array, over=dim, offset=p, edge=…)`         | Here `p` is an integer parameter, so each entity is reached by its own offset. Declared over what a `by=` groups into, it gives one lag per group |
| `shift(array, over=dim, offset=n, by=lookup)`      | The translation walks inside each group that the lookup makes. Neighbours, edges and a wrap all belong to that group                              |
| `sum_back(array, over=dim, within=n)`              | The sum of the last `n` positions along `dim`, ending at the position being written                                                               |
| `sum_back(array, over=dim, within=p)`              | Here `p` is an integer parameter, so each entity gets its own window length                                                                       |
| `sum_back(array, over=dim, within=p, edge='wrap')` | The window reaches around the axis, instead of stopping short at its start                                                                        |

`array` is any expression with the right dimension set, so each of these
operators reads a parameter just as readily as a variable. Dimension
arguments are name-checked at load, so `sum(p, over=snapshto)` is an error
rather than a silent no-op. To see how the typesetter prints each row, see
[Every operator as math](#every-operator-as-math) below.

!!! note "The operator set is closed"

    The table above is all of them. There is no registry to add to, so a model
    can never depend on what a caller registered.

## `sum`

`sum(x, over=d)` is the ordinary reduction. It adds up `x` along `d`, and `d`
is gone from the result.

`sum(x)` names no dimension, and it takes every dimension that `x` carries. So
its result is a scalar. It is the nested form, `sum(sum(x, over=a), over=b)`,
written once. It is how a file states a reduction that a declaration would
otherwise leave implied.

Two things are errors rather than no-ops here: an operand that is already
scalar, and an `over=` that names a dimension the operand does not carry.

`sum(x, by=l)` sums along a lookup, and it lands the result on the
dimension that the lookup maps into. See [lookups](dimensions.md#lookups). This
is the membership sum that makes topology into data rather than structure:

```yaml
dimensions:
  bus: { dtype: str }
  generator: { dtype: str }
  line: { dtype: str }
lookups:
  gen_bus: { over: generator, into: bus }
  line_from: { over: line, into: bus }
  line_to: { over: line, into: bus }
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

The same `f` is summed twice, through two different lookups: once as inflow and
once as outflow. There is no adjacency matrix, and no join written by hand.

Give **at most one** of `over=` and `by=`. A lookup carries its own dimensions,
so `by=` leaves `over=` nothing to add. If you give neither, you get the bare
form shown above.

The values of the lookup are the group labels, and they are checked against the
target dimension when the data binds. A group with no members contributes
nothing. A member whose lookup value is null belongs to no group.

An empty group holds a value rather than a gap. On the constant side of a
comparison it reads as zero, whereas a coordinate that the data never covered
is refused. See [absence](absence.md).

## `at`

`at(x, by=l)` is the adjoint of `sum(by=)`, and it deliberately takes the
same single argument. The lookup names one mapping table, and the operator says
which way that table is walked.

`sum(by=)` consumes the dimension the lookup is over, and produces the target
dimension. `at` goes the other way: it consumes the target and produces the
dimension the lookup is over. It reads one coarse value once for each fine
label that points at it.

`at` reads a _variable_ just as readily as a parameter. That is what you need
for a per-component decision that gates its own flows: one decision taken per
bus, read once by every line that touches that bus.

A fine label whose lookup value is null reads nothing, and its row is absent.
That matches the null group in `sum(by=)`.

## `sum_back`

`sum_back(x, over=d, within=n)` is the sum of the last `n` positions along `d`,
ending at the position being written. Use it for a minimum up time, a rolling
budget, or a delivery horizon. A width of `1` gives you `x` itself.

The dimension **survives** this operator. `sum` reduces the dimension away, but
`sum_back` leaves one value per position, and each of those values reads a
window of its own.

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

`within=` takes a number or the name of an integer parameter. Those two
forms and nothing else, so never an expression. With a named parameter, each
entity gets a window of its own length, and that is the case with no
workaround. You can write a fixed width as a run of `shift`s. You cannot write
a width that is a column that way, and the alternative would be an incidence
table over the dimension twice, built outside the model and shipped with it.

Two rules make a named width mean one thing, and breaking either is a load
error:

- The width is integral. A width counts positions; it does not measure a
  distance. `dtype: int` says so at load, and an `int` declaration binds only
  an integer column, so a width of `2.5` has nowhere to arrive from.
- The width does not span the dimension being summed over. A width that
  changed along that axis would give a different window at every position, and
  that is no longer "the last _n_".

`edge=` takes `'wrap'` or nothing at all.

A window that reaches past the start of the axis is **short**, and not empty. The
position being written is always inside its own window, so no row is lost and
there is nothing vacated to fill. A number here is a load error, because the
expression can add a constant for itself.

`edge='wrap'` makes the window reach around the axis instead. That is what a
representative period that repeats asks for.

## `shift`

`shift(x, over=d, offset=n)` moves values along one dimension by a given
offset, counted in the dimension's **declared order**: the value at each
coordinate becomes the value that stood _n_ places before it. Only the values
move, and the coordinates stay where they are. An `edge=` argument says what
stands where nothing moved in.

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

`edge='wrap'` is what makes a battery cyclic without you writing the boundary
condition out: the first snapshot reads the last.

There are three settings, and two further rules that hold across all of them:

- Bare. The vacated coordinate is **absent**. Absence propagates, and the
  row it would have fed is not built. See [absence](absence.md). So an acyclic
  recurrence has no row at its first coordinate, instead of a row asserting
  that the quantity starts at zero. The model then states an initial condition
  itself, under a complementary `where`. See
  [two regimes, two blocks](declarations.md#constraints).
- `'wrap'`. The translation is cyclic. Coordinates stay put and values wrap
  around, so nothing is vacated.
- A number. That number stands where the slot was vacated, and the row
  survives. It is a number rather than a flag because the identity depends on
  the position: `0` for a sum, and `1` for a product. The library cannot see
  which position it is in, and the model can.
- Over a variable, the only numeric edge that can be represented is **`0`**. A
  vacated slot there contributes no term at all. A non-zero edge would be a
  constant standing where a term used to be.
- A bare `shift` over a variable-free expression is a load error. A
  parameter's missing row is a zero coefficient, so there is no absence for the
  vacated slot to carry. Inventing one would silently turn
  `x <= shift(dt, over=t, offset=1)` into `x <= 0`.

  The error names what you could have meant: `edge='wrap'`, `edge=0`, or
  `edge=0` together with a `where` that excludes the vacated coordinate.
  Those last two go together; they are not two alternatives. A `where` on its
  own does not remove the refusal, and `edge=0` on its own leaves a row at that
  coordinate whose bound is the zero.

### A translation that stops at each group's edge

`by=` partitions the axis that the operator walks. So the neighbour of a
coordinate is the coordinate before it in its own group. A group can be a
season, an investment period, or a representative day:

```yaml
dimensions:
  snapshot: { dtype: int }
  season: { dtype: str }
lookups:
  season_of: { over: snapshot, into: season }
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

Every `edge=` rule then reads the same way, one group at a time:

- Bare, the first coordinate of each group is vacated, and its row drops.
- `edge='wrap'` closes each group onto its own last coordinate. That is what
  a store which must return to its starting level every period asks for.
- `edge=v` puts `v` at the edge of each group.

`by=` takes a **groupable** lookup, which means one that declares `into:`. The
lookup must be over the dimension being walked, so that its groups are groups a
row of that dimension is in.

The target of the lookup is what a named `offset=` may vary over, so each group
can be reached by its own offset. A label space targets nothing, so a label
space is refused
([#280](https://github.com/energy-models/math-spec/issues/280)).

A coordinate that the lookup sends nowhere is in no group, so it reaches
nothing, and no `edge=` speaks for it. Reaching off the start of a group is what
an `edge=` policy answers. Belonging to no group is the null that a partial
lookup gives everywhere else, so the row drops under `edge=0` exactly as it does
bare.

Without a `by=`, `edge='wrap'` wraps the _axis_. The last coordinate of the
whole dimension feeds the first, which across periods means one period opening
on what another period left behind.

`shift` reads parameters too. So `shift(dt, over=t, offset=1, edge=0)` gives you
the previous snapshot's duration, without shipping a pre-shifted copy of a table
the model already has.

### An offset that differs per entity

`offset=` may name an integer parameter instead of a number. Then each
entity is reached by its own offset. Use this for a construction lead time, a
transit time, or any delay that the source data already carries as a column:

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

Three rules keep this a translation and not something else. Breaking any of
them is a load error, and each error names its rewrite:

- The parameter is integral. An offset lands on a coordinate, so it counts
  positions rather than measuring a distance. `dtype: int` says so at load, and
  an `int` declaration binds only an integer column, so a value of `1.5` has
  nowhere to arrive from.
- The parameter does not span the dimension being translated. An offset that
  varied along the axis it moves along would be a permutation, not a lag.
- The parameter varies only over dimensions where the shift can read it.
  Those are the dimensions of the shifted expression itself, and the dimension
  that a `by=` lookup groups into, which is covered below. An offset is read at
  the coordinate it moves. A dimension that the coordinate does not have is no
  coordinate at all.

`edge=` is not one of these rules. A named offset may be bare, and its vacated
positions are absent in exactly the way a numeric offset's are. Its vacated
positions differ per entity, and the edge frame is keyed by the offset's own
dimensions, so every consumer reads the same edge.

What stays refused is a bare `shift` over a variable-free operand, for the
separate reason given [above](#shift): a parameter's missing row is a zero
coefficient, so there is no absence for the vacated slot to carry.

A named offset also carries its sign in the values. `lag=-lead` is refused.
So a row that points backwards says so where the data is read.

### A lag that differs per group

The second half of the third rule above is a formulation in its own right.
`offset=` may name a parameter that is declared over the dimension which a
[`by=`](#a-translation-that-stops-at-each-groups-edge) lookup groups into. Then
the lag belongs to the group.

Every snapshot of an investment period moves by that period's own lead time. The
opening rows of each period vacate by that period's own distance. And no
coordinate reaches out of its own group:

```yaml
dimensions:
  snapshot: { dtype: int }
  period: { dtype: int }
lookups:
  period_of: { over: snapshot, into: period }
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

This is the one thing that a `(period, timestep)` grid can say and a flat
`snapshot` axis with lookups could not. On the grid, the offset is declared over
`period`, and it is legal because `period` is not the axis being walked. Here it
is legal because the partition puts each snapshot's period within reach.

The two keys compose. `lead: {dims: [technology, period]}` gives one lag per
technology per period.

## Composing operators

Anything you can build out of these operators belongs in
[`macros:`](expressions.md#macros). The operator set does not grow to hold it.

## Every operator as math

This table shows each operator above as the [typesetter](../typeset.md) prints
it. The table is generated from one model per row, in
[`examples/operators/`](https://github.com/energy-models/math-spec/tree/main/examples/operators).
So a row cannot outlive the operator it documents. And if two operators render
the same way, you see that here rather than in somebody's paper.

Read the three `shift` rows together. They differ only at the boundary, which
is where the identity rule for this position applies.

Each row comes from a model of its own, and those models are on
[One construct per model](../../examples/operators.md). The rest of the language
is rendered the same way, on one page:
[Every construct, as math](../notation.md).

<!-- operator-math:begin -->
| Operator | Renders as |
|---|---|
| `sum(array)` | $\sum_{t \in \mathcal{T},\enspace g \in \mathcal{G}} p_{t,g} \le \mathrm{budget}$ |
| `sum(array, over=dim)` | $\sum_{g \in \mathcal{G}} p_{t,g} \le \mathrm{limit}_{t} \qquad \forall\thinspace t \in \mathcal{T}$ |
| `sum(array, by=lookup)` | $\sum_{g \in \mathcal{G} \thinspace:\thinspace \mathrm{gen\_bus}(g) = b} p_{t,g} \le \mathrm{limit}_{t,b} \qquad \forall\thinspace t \in \mathcal{T},\enspace b \in \mathcal{B}$ |
| `sum(array, by=[lookup, …])` | $\sum_{g \in \mathcal{G} \thinspace:\thinspace \mathrm{gen\_bus}(g) = b \wedge \mathrm{gen\_tech}(g) = e} p_{t,g} \le \mathrm{limit}_{t,b,e} \qquad \forall\thinspace t \in \mathcal{T},\enspace b \in \mathcal{B},\enspace e \in \mathcal{E}$ |
| `at(array, by=lookup)` | $p_{t} \le \mathrm{cap}_{\mathrm{period\_of}(t)} \qquad \forall\thinspace t \in \mathcal{T}$ |
| `shift(array, over=dim, offset=n)` | $p_{t} \le p_{t - 1} \qquad \forall\thinspace t \in \mathcal{T}$ |
| `shift(array, over=dim, offset=n, edge='wrap')` | $p_{t} \le p_{t \ominus 1} \qquad \forall\thinspace t \in \mathcal{T}$ |
| `shift(array, over=dim, offset=n, edge=v)` | $p_{t} \le p_{t \boxminus_{0} 1} \qquad \forall\thinspace t \in \mathcal{T}$ |
| `shift(array, over=dim, offset=p, edge=…)` | $\mathit{order}_{t,m \boxminus_{0} \mathrm{lead}} \ge \mathrm{demand}_{t,m} \qquad \forall\thinspace t \in \mathcal{T},\enspace m \in \mathcal{M}$ |
| `shift(array, over=dim, offset=n, by=lookup)` | $p_{t} \le p_{t \ominus^{\mathrm{season\_of}(t)} 1} \qquad \forall\thinspace t \in \mathcal{T}$ |
| `sum_back(array, over=dim, within=n)` | $\sum_{h' \in \mathcal{H} \thinspace:\thinspace 0 \le h - h' < 3} \mathit{started}_{u,h'} \le \mathit{on}_{u,h} \qquad \forall\thinspace u \in \mathcal{U},\enspace h \in \mathcal{H}$ |
| `sum_back(array, over=dim, within=p)` | $\sum_{h' \in \mathcal{H} \thinspace:\thinspace 0 \le h - h' < \mathrm{min\_up}} \mathit{started}_{u,h'} \le \mathit{on}_{u,h} \qquad \forall\thinspace u \in \mathcal{U},\enspace h \in \mathcal{H}$ |
| `sum_back(array, over=dim, within=p, edge='wrap')` | $\sum_{h' \in \mathcal{H} \thinspace:\thinspace 0 \le h \ominus h' < \mathrm{min\_up}} \mathit{started}_{u,h'} \le \mathit{on}_{u,h} \qquad \forall\thinspace u \in \mathcal{U},\enspace h \in \mathcal{H}$ |
| `sum_back(array, over=dim, within=n, by=lookup)` | $\sum_{h' \in \mathcal{H} \thinspace:\thinspace 0 \le h -^{\mathrm{day\_of}(h)} h' < 3} \mathit{started}_{u,h'} \le \mathit{on}_{u,h} \qquad \forall\thinspace u \in \mathcal{U},\enspace h \in \mathcal{H}$ |
| `dual(constraint)` | $\mathit{price}_{t} = \lambda_{\mathrm{balance},t} \qquad \forall\thinspace t \in \mathcal{T}$ |

$t \ominus k$ denotes cyclic translation: index $t-k$ taken modulo the size of the dimension (`roll`). Plain $t-k$ (`shift`) has no wraparound — terms translated past the edge are simply absent.

$t \boxminus_{v} k$ denotes translation with $v$ standing where index $t-k$ leaves the dimension (`shift(edge=v)`), so the row at that boundary is built and carries $v$ rather than being dropped.

$t \ominus^{\mathrm{lookup}(t)} k$ denotes a translation counted inside the group a lookup puts $t$ in (`shift(by=lookup)`), so a term never crosses out of its own group.
<!-- operator-math:end -->

Regenerate with `pixi run python -m tools.spec_math`.
