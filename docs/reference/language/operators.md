<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Operators

The built-in set is **closed**: these are all of them, and there is no registry
to add to. A model therefore cannot depend on what a caller registered.
[Dimension](dimensions.md) arguments are name-checked at load time, so
`sum(p, over=snapshto)` is an error rather than a no-op.

| Operator                                           | Result                                                                                           |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `sum(array)`                                       | every dimension `array` carries collapses; the result is scalar                                  |
| `sum(array, over=dim)`                             | `dim` collapses; `array` must carry it                                                           |
| `sum(array, by=lookup)`                            | the dimension the lookup is over collapses onto the dimension it maps into                       |
| `sum(array, by=[lookup, …])`                       | the same, onto every dimension the lookups map into; they must share the dimension they are over |
| `at(array, by=lookup)`                             | the dimension the lookup maps into is replaced by the dimension it is over                       |
| `shift(array, over=dim, offset=n)`                 | the value at _t−n_ along `dim`; the vacated edge is **absent**                                   |
| `shift(array, over=dim, offset=n, edge='wrap')`    | the value at _t−n_, cyclic: nothing is vacated                                                   |
| `shift(array, over=dim, offset=n, edge=v)`         | the value at _t−n_, with the number `v` where the edge was vacated                               |
| `shift(array, over=dim, offset=p, edge=…)`         | `p` an integer parameter: each entity is reached by **its own** offset                           |
| `shift(array, over=dim, offset=n, by=lookup)`      | the translation walks **inside each group** the lookup makes                                     |
| `sum_back(array, over=dim, within=n)`              | the sum of the last `n` positions along `dim`, ending at _t_                                     |
| `sum_back(array, over=dim, within=p)`              | `p` an integer parameter: each entity gets **its own** window length                             |
| `sum_back(array, over=dim, within=p, edge='wrap')` | the window reaches around the axis rather than stopping short at its start                       |
| `sum_back(array, over=dim, within=n, by=lookup)`   | the window stops at each group's edge rather than reaching across it                             |

`array` is any expression of the right dimensions, so these read a
**parameter** as readily as a variable. Each row as the typesetter prints it is
[below](#as-math).

## `sum`

`sum(x, over=d)` is the ordinary reduction. It adds `x` up along `d`, and `d`
is gone from the result.

`sum(x)` names no dimension and takes every dimension `x` carries, so its
result is a scalar. It is `sum(sum(x, over=a), over=b)` written once. An
operand that is already scalar is an error rather than a no-op, and so is
`over=` naming a dimension the operand does not carry.

`sum(x, by=l)` sums **along a lookup** and lands the result on the dimension
that lookup maps into ([lookups](dimensions.md#lookups)). This is the
membership sum that makes topology data rather than structure:

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

The same `f` is summed twice through two different lookups, once as inflow and
once as outflow. No adjacency matrix, and no join written by hand.

**At most one of `over=` and `by=`**: a lookup carries its own dimensions, so
`by=` leaves `over=` nothing to add. Giving neither is the bare form above. The
lookup's values are the group labels, and they are checked against the target
dimension when data binds. A group with no members contributes nothing, and a
member whose lookup value is null belongs to no group. An empty group holds a
**value** rather than a gap: on a comparison's constant side it reads zero. A
coordinate the data never covered is refused instead ([absence](absence.md)).

## `at`

`at(x, by=l)` is the **adjoint of `sum(by=)`**. It takes the same single
lookup, and the operator says which way that mapping table is walked.
`sum(by=)` consumes the dimension the lookup is over and produces its target.
`at` consumes the target and produces that dimension, reading one coarse value
once per fine label that points at it.

It reads a variable as readily as a parameter, which is what a per-component
decision gating its own flows needs: one decision taken per bus, read once by
every line that touches it. A fine label whose lookup value is null reads
nothing and its row is absent, matching `sum(by=)`'s null group.

## `sum_back`

`sum_back(x, over=d, within=n)` is the sum of the last `n` positions along `d`,
ending at the one being written — a minimum up time, a rolling budget, a
delivery horizon. A width of `1` is `x` itself.

The dimension **survives**. Unlike `sum`, which reduces it away, this leaves
one value per position, each reading a window of its own.

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

`within=` may name an **integer parameter** instead of a number — those two and
nothing else, never an expression. Each entity then gets a window of its own
length. A fixed width can be written as a run of `shift`s; a width that is a
column cannot.

Two rules make a named width mean one thing, and both are load errors:

- **It is integral.** A width counts positions rather than measuring a
  distance. `dtype: int` says so at load, and an `int` declaration binds only
  an integer column, so a width of `2.5` has nowhere to arrive from.
- **It does not span the dimension being summed over.** A width that changes
  along that axis is a different window at every position, which is no longer
  "the last _n_".

`edge=` takes `'wrap'` or nothing. A window that reaches past the start of the
axis is **short**, not empty. The position being written is always inside its
own window, so no row is lost and there is nothing vacated to fill. A number
there is a load error, because adding a constant is something the expression
can say for itself. `edge='wrap'` makes the window reach around instead, which
is what a representative period that repeats asks for.

`by=` partitions the axis the same way it does on `shift`
([below](#a-translation-that-stops-at-each-groups-edge)): the window stops at
each group's edge rather than reaching across it.

## `shift`

`shift(x, over=d, offset=n)` reaches along an axis. It is the value at _t−n_,
in the dimension's **declared order**. `edge=` says what happens at the
boundary.

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

`edge='wrap'` is what makes a battery cyclic without writing the boundary
condition out: the first snapshot reads the last.

Three settings, and two rules that hold across them:

- **Bare — the vacated coordinate is absent.** Absence propagates, so the row
  it would have fed is not built ([absence](absence.md)). An acyclic recurrence
  has no row at its first coordinate, rather than a row asserting that the
  quantity starts at zero. State an initial condition under a complementary
  `where` ([two regimes, two blocks](declarations.md#constraints)).
- **`'wrap'` — the translation is cyclic.** Coordinates stay put and values
  wrap, so nothing is vacated.
- **Numeric — the number stands where the slot was vacated**, and the row
  survives.
- **Over a variable the only representable numeric edge is `0`.** A vacated
  slot there contributes no term at all, and a nonzero one would be a constant
  standing where a term was.
- **A bare `shift` over a variable-free expression is a load error.** A
  parameter's missing row is a zero coefficient, so there is no absence for the
  vacated slot to carry, and inventing one would silently turn
  `x <= shift(dt, over=t, offset=1)` into `x <= 0`. The error says which of
  three things to write instead:

  ```text
  shift() over a variable-free expression leaves vacated positions with no value, and inventing one is what silently pinned a bound to zero. Say which you mean:
    shift(x, over=d, offset=n, edge='wrap')   the dimension really is cyclic
    shift(x, over=d, offset=n, edge=0)        the vacated positions contribute zero
    ...and a where: excluding them        the vacated rows should not exist at all
  A where: alone does not lift this — it is decided on the expression, before any mask is read — and edge=0 alone leaves a row whose bound is that zero.
  ```

### A translation that stops at each group's edge

`by=` partitions the axis the operator walks, so a coordinate's neighbour is
the one before it **in its own group** — a season, an investment period, a
representative day:

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

Every `edge=` rule then reads the same, one group at a time. Bare, each group's
first coordinate is vacated and its row drops. `edge='wrap'` closes **each
group** onto its own last, which is what a store that must return to its
starting level every period asks for. `edge=v` puts `v` at each group's edge.

It is the same `by=` as [`sum(by=)` and `at(by=)`](#sum), and it takes a lookup
**over the dimension being walked**: the lookup's value at a row says which
group that row is in. A coordinate the lookup sends nowhere is in no group, so
it reaches nothing, and no `edge=` speaks for it. That row drops under
`edge=0` exactly as it does bare.

Without `by=`, `edge='wrap'` wraps the whole _axis_: the last coordinate of the
dimension feeds the first, which across periods means one period opening on
what another left.

Because `shift` reads parameters too, `shift(dt, over=t, offset=1, edge=0)` is
the previous snapshot's duration, without shipping a pre-shifted copy of a
table the model already has.

### An offset that differs per entity

`offset=` may name an **integer parameter** instead of a number, and then each
entity is reached by its own offset — a construction lead time, a transit time,
a delay the source data already carries as a column:

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

Three rules keep that a translation rather than something else, each a load
error naming its rewrite:

- **The parameter is integral.** An offset lands on a coordinate, so it counts
  positions rather than measuring a distance. `dtype: int` says so at load, and
  an `int` declaration binds only an integer column, so a `1.5` has nowhere to
  arrive from.
- **It does not span the dimension being translated.** An offset that varied
  along the axis it moves is a permutation, not a lag.
- **It varies only over dimensions the shift can read it at** — the shifted
  expression's own, or the one a `by=` lookup groups into (below). An offset is
  read at the coordinate it moves, and a dimension that coordinate does not
  have is no coordinate at all.

A named offset also carries an `edge=`. Written bare it is a load error:

```text
shift(offset=lead) leaves the vacated positions absent, which a per-entity
offset cannot say yet.
Add edge='wrap' for a cyclic translation, or edge=<number> for what the
vacated positions contribute.
```

A named offset carries its **sign in the values**: `lag=-lead` is refused, so
one row that points backwards says so where the data is read.

### A lag that differs per group

`offset=` may name a parameter declared over the dimension a
[`by=`](#a-translation-that-stops-at-each-groups-edge) lookup groups into, and
then the lag is **the group's**. Every snapshot of an investment period moves
by that period's own lead time, and no coordinate reaches out of its group:

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

The offset is declared over `period`, which is legal because `period` is not
the axis being walked, and the partition puts each snapshot's period within
reach. The two keys compose: `lead: {dims: [technology, period]}` is one lag
per technology per period.

## Composing

Anything you can build out of these belongs in
[`macros:`](expressions.md#macros) — the operator set does not grow to hold it.

## As math

Each operator above as the [typesetter](../typeset.md) prints it, **generated**
from one model per row in
[`examples/operators/`](https://github.com/energy-models/math-spec/tree/main/examples/operators),
so a row cannot outlive the operator it documents. The models themselves are on
[One construct per model](../../examples/operators.md), and the rest of the
language is rendered the same way on
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

$t \ominus k$ denotes cyclic translation: index $t-k$ taken modulo the size of the dimension (`roll`). Plain $t-k$ (`shift`) has no wraparound — terms translated past the edge are simply absent.

$t \boxminus_{v} k$ denotes translation with $v$ standing where index $t-k$ leaves the dimension (`shift(edge=v)`), so the row at that boundary is built and carries $v$ rather than being dropped.

$t \ominus^{\mathrm{lookup}(t)} k$ denotes a translation counted inside the group a lookup puts $t$ in (`shift(by=lookup)`), so a term never crosses out of its own group.
<!-- operator-math:end -->

Regenerate with `pixi run python -m tools.spec_math`.
