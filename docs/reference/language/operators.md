# Operators

The built-in set is **closed**: these are all of them, there is no registry to
add to, and a model therefore cannot depend on what a caller registered.
Dimension arguments are name-checked at load time, so
`sum(p, over=snapshto)` is an error rather than a no-op.

| Operator | Result |
|---|---|
| `sum(array, over=dim)` | `dim` collapses; `array` must carry it |
| `sum(array, by=lookup)` | the dim the lookup is over collapses onto the dim it maps into |
| `at(array, by=lookup)` | the dim the lookup maps into is replaced by the dim it is over |
| `shift(array, over=dim, by=n)` | the value at *t−n* along `dim`; the vacated edge is **absent** |
| `shift(array, over=dim, by=n, edge='wrap')` | the value at *t−n*, cyclic: nothing is vacated |
| `shift(array, over=dim, by=n, edge=v)` | the value at *t−n*, with the number `v` where the edge was vacated |
| `shift(array, over=dim, by=p, edge=…)` | `p` an integer parameter: each entity is reached by **its own** offset |

`array` is any expression of the right dim set, so these read a **parameter**
as readily as a variable. Each row as the typesetter prints it is
[below](#as-math).

## `sum`

`sum(x, over=d)` is the ordinary reduction: it adds up `x` along `d` and `d` is
gone from the result.

`sum(x, by=l)` sums **along a lookup** and lands the result on the dimension
that lookup maps into ([lookups](dimensions.md#lookups)). This is the
membership sum that makes topology data rather than structure:

```yaml
dimensions:
  bus: {dtype: str}
  generator: {dtype: str}
  line: {dtype: str}
lookups:
  gen_bus: {over: generator, into: bus}
  from: {over: line, into: bus}
  to: {over: line, into: bus}
parameters:
  load: {dims: [bus]}
variables:
  p: {foreach: [generator]}
  f: {foreach: [line]}
constraints:
  nodal_balance:
    foreach: [bus]
    expression: >-
      sum(p, by=gen_bus)
      + sum(f, by=to)
      - sum(f, by=from)
      == load
```

The same `f` is summed twice through two different lookups — once as inflow,
once as outflow. No adjacency matrix, and no join written by hand.

**Exactly one of `over=` and `by=`**: a lookup carries its own dimensions, so
`by=` leaves `over=` nothing to add. The lookup's values are the group labels,
and they are checked against the target dimension when data binds. Groups with
no members contribute nothing, and a member whose lookup value is null belongs
to no group.

## `at`

`at(x, by=l)` is the **adjoint of `sum(by=)`**, and deliberately takes the same
single argument: the lookup names one mapping table, and the operator says
which way it is walked. `sum(by=)` consumes the dimension the lookup is over
and produces its target; `at` consumes the target and produces that dimension,
reading one coarse value once per fine label that points at it.

It reads a *variable* as readily as a parameter, which is what a per-component
decision gating its own flows needs — one decision taken per bus, read once by
every line that touches it. A fine label whose lookup value is null reads
nothing and its row is absent, matching `sum(by=)`'s null group.

## `shift`

`shift(x, over=d, by=n)` reaches along an axis: it is the value at *t−n*, in
the dimension's **declared order** ([data binding](data.md)). `edge=` says what
happens at the boundary, and it is the whole of the operator's subtlety.

Bare, the vacated position is **absent**: it propagates absence and the row it
would have fed is not built ([absence](absence.md)). `edge='wrap'` is cyclic —
coordinates stay put and values wrap, so nothing is vacated. `edge=v` puts the
number `v` there instead, and the row survives.

```yaml
dimensions:
  snapshot: {dtype: int}
  storage: {dtype: str}
parameters:
  eta: {dims: [storage]}
variables:
  soc: {foreach: [snapshot, storage]}
  charge: {foreach: [snapshot, storage]}
  discharge: {foreach: [snapshot, storage]}
constraints:
  storage_balance:
    foreach: [snapshot, storage]
    expression: soc == shift(soc, over=snapshot, by=1, edge='wrap') + charge * eta - discharge
```

`edge='wrap'` is what makes a battery cyclic without writing the boundary
condition out: the first snapshot reads the last.

Four rules govern `edge=`:

- **Bare** — the vacated coordinate is absent, so an acyclic recurrence has no
  row at its first coordinate rather than a row asserting that the quantity
  starts at zero. An initial condition is then something the model states,
  under a complementary `where`
  ([two regimes, two blocks](declarations.md#constraints)).
- **Numeric** — asks for a value back. It is a number rather than a flag
  because the identity is positional: `0` for a sum, `1` for a product. The
  library cannot see which position it is in, and the model can.
- **Over a variable the only representable numeric edge is `0`** — a vacated
  slot there contributes no term at all, and a nonzero one would be a constant
  standing where a term was.
- **A bare `shift` over a variable-free expression is a load error.** A
  parameter's missing row is a zero coefficient, so there is no absence for the
  vacated slot to carry, and inventing one would silently turn
  `x <= shift(dt, over=t, by=1)` into `x <= 0`. The error names what it could
  have meant: `edge='wrap'`, `edge=0`, or `edge=0` **together with** a `where`
  excluding the vacated coordinate. Those last two are a pair, not a choice: a
  `where` alone does not lift the refusal, and `edge=0` alone leaves a row at
  that coordinate whose bound is the zero.

Because `shift` reads parameters too, `shift(dt, over=t, by=1, edge=0)` is the
previous snapshot's duration without shipping a pre-shifted copy of a table the
model already has.

### An offset that differs per entity

`by=` may name an **integer parameter** instead of a number, and then each
entity is reached by its own offset — a construction lead time, a transit time,
a delay that the source data already carries as a column:

```yaml
dimensions:
  technology: {dtype: str}
  month: {dtype: int}
parameters:
  lead: {dims: [technology], dtype: int}
  demand: {dims: [technology, month]}
variables:
  order:
    foreach: [technology, month]
    bounds: {lower: 0}
constraints:
  arrives_after_its_lead:
    foreach: [technology, month]
    expression: shift(order, over=month, by=lead, edge=0) >= demand
objective: {sense: minimize, expression: order}
```

Three rules keep that a translation rather than something else, each a load
error naming its rewrite:

- **the parameter is integral** — an offset lands on a coordinate, so it counts
  positions rather than measuring a distance;
- **it does not span the dimension being translated** — an offset that varied
  along the axis it moves is a permutation, not a lag;
- **it says what the vacated positions contribute** — `edge='wrap'` or a
  number. The bare form's *absence* is carried by a frame keyed by the
  translated dimension alone, and a per-entity offset vacates a different slot
  for each entity, which that frame cannot yet say.

A named offset also carries its **sign in the values**: `by=-lead` is refused,
so one row that points backwards says so where the data is read.

This is the one construct whose cost is not obviously linear in model size.

## Composing

Anything you can build out of these belongs in
[`macros:`](expressions.md#macros) — the operator set does not grow to hold it.

## As math

Each operator above as the [typesetter](../typeset.md) prints it, **generated**
from one model per row in
[`examples/operators/`](https://github.com/fluxopt/lpspec/blob/main/examples/operators)
— so a row cannot outlive the operator it documents, and two operators that
render the same are visible here rather than in somebody's paper.

The three `shift` rows are the ones to read together: they differ only at the
boundary, and that difference is the whole of the identity rule in this
position.

<!-- operator-math:begin -->
| Operator | Renders as |
|---|---|
| `sum(array, over=dim)` | $\sum_{g \in \mathcal{G}} p_{t,g} \le \mathit{limit}_{t} \qquad \forall\thinspace t \in \mathcal{T}$ |
| `sum(array, by=lookup)` | $\sum_{g \in \mathcal{G} \thinspace:\thinspace \mathrm{gen\_bus}(g) = b} p_{t,g} \le \mathit{limit}_{t,b} \qquad \forall\thinspace t \in \mathcal{T},\enspace b \in \mathcal{B}$ |
| `at(array, by=lookup)` | $p_{t} \le \mathit{cap}_{\mathrm{period\_of}(t)} \qquad \forall\thinspace t \in \mathcal{T}$ |
| `shift(array, over=dim, by=n)` | $p_{t} \le p_{t - 1} \qquad \forall\thinspace t \in \mathcal{T}$ |
| `shift(array, over=dim, by=n, edge='wrap')` | $p_{t} \le p_{t \ominus 1} \qquad \forall\thinspace t \in \mathcal{T}$ |
| `shift(array, over=dim, by=n, edge=v)` | $p_{t} \le p_{t \boxminus_{0} 1} \qquad \forall\thinspace t \in \mathcal{T}$ |
| `shift(array, over=dim, by=p, edge=…)` | $\mathit{order}_{t,m \boxminus_{0} \mathit{lead}} \ge \mathit{demand}_{t,m} \qquad \forall\thinspace t \in \mathcal{T},\enspace m \in \mathcal{M}$ |

$t \ominus k$ denotes cyclic translation: index $t-k$ taken modulo the size of the dimension (`roll`). Plain $t-k$ (`shift`) has no wraparound --- terms translated past the edge are simply absent.

$t \boxminus_{v} k$ denotes translation with $v$ standing where index $t-k$ leaves the dimension (`shift(edge=v)`), so the row at that boundary is built and carries $v$ rather than being dropped.
<!-- operator-math:end -->

Regenerate with `uv run python -m tools.spec_math`.
