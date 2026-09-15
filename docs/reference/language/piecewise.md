<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Piecewise curves and SOS

Two blocks state shapes that no `expression:` can, because an expression is
affine. `piecewise:` states a curve through breakpoints. `sos:` states a family
of variables of which only one, or only two neighbours, may be non-zero.

## `piecewise`

A `piecewise` block ties two or more expressions to one piecewise-linear curve.
The curve is given as breakpoints: the corner values each expression takes
together.

<!-- doctest: wrap=piecewise -->

```yaml
chp:
  over: bp # breakpoint dimension
  links:
    - [power, power_bp] # [expression, values-parameter]
    - [fuel, fuel_bp]
    - [heat, heat_bp]
  method: adjacency # how the weights are restricted — below
  activity: null # optional: a binary variable that the weights sum to

# a two-link block may bound one side instead of pinning it
fuel_cap:
  over: bp
  links:
    - [power, power_bp]
    - [fuel, fuel_bp, "<="]
```

| Part of a link |                                                                                                                                                                                                       |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| _expression_   | Any affine expression. The simplest is a bare variable name                                                                                                                                           |
| _values_       | A parameter that carries the `over` dimension, plus any dimensions the link expressions carry. So a curve may vary per generator wherever the links do. A dimension the links do not carry is refused |
| _sign_         | `<=` or `>=`. At most one per block, and only in a block with exactly two links. It bounds the link instead of pinning it                                                                             |

| Key        |                                                                                                                    |                     |
| ---------- | ------------------------------------------------------------------------------------------------------------------ | ------------------- |
| `over`     | required. The breakpoint dimension                                                                                 |                     |
| `links`    | required. Two or more links                                                                                        |                     |
| `method`   | `adjacency`, `sos2`, `convex` or `lp`: how the weights are restricted ([below](#method))                           | default `adjacency` |
| `activity` | a binary variable that gates the curve ([below](#activity-gates-the-curve))                                        | default `null`      |
| `points`   | how far each curve runs, where the curves are not all the same length ([below](#points-says-how-far-a-curve-runs)) | default `null`      |

### What the block expands into

A block expands before building, into plain variables and constraints. Three of
the four methods expand the same way: one weight per breakpoint in `[0, 1]`, one
row making the weights sum to 1, and one row per link tying its expression to the
weighted breakpoints. That expansion is what the rest of the model sees, and
what the [typeset output](../typeset.md) prints.

Without `points:`, the expansion emits one weight per breakpoint over the whole
product of its dimensions, and masks none of them.

!!! warning "A values parameter short of a row does not build a shorter curve"

    The [absence rules](absence.md#what-creates-absence) read the missing row as
    a zero coefficient, which is a breakpoint at the origin that the file never
    declared. Such a table is refused when the data binds. To say how far a curve
    runs, use `points:`.

The breakpoint order is the declared order of `over`, which is the order `shift`
walks and the order `position(bp) == 0` names. "Strictly increasing
breakpoints" below means increasing in that order, so an index written backwards
is a curve that runs backwards, and it is refused.

### `activity:` gates the curve

`activity:` names a binary variable, and the weights then sum to that variable
instead of to 1. So `0` pins the curve off, columns and all.

The gate is a declaration, not an expression, because a masked gate has
coordinates where it does not exist, and only a declaration says what that
means:

<!-- doctest: wrap=variables -->

```yaml
running:
  dims: [snapshot, generator]
  domain: binary
  where: committable # only some units have a commitment decision
```

Where the gate does not exist, the curve is ungated. The block emits the
convexity row twice, under complementary masks: `== running` where the gate
exists, and `== 1` where it does not. The row cannot be allowed to drop, because
it is `sum(lam, over=bp) == (activity)`, and
[absence](absence.md#how-absence-travels) does not spread out of a reduction: an
absent right-hand side would take the whole row, and leave the weights with
nothing to make them a curve.

To say the opposite, put `absence: zero` on the gate. Then the single row reads
`== 0` where the gate is masked, which gives no curve rather than an
unconditional one.

### `points:` says how far a curve runs

A curve with fewer breakpoints than the dimension holds says so with `points:`.
Name one of the block's own values parameters, and the curve is as long as that
parameter has rows:

<!-- doctest: wrap=piecewise -->

```yaml
cost_curve:
  over: bp
  points: bp_x # this curve runs as far as its own breakpoints do
  links:
    - [p, bp_x]
    - [op_cost, bp_y]
```

The other links are still read against the parameter you named, so a row missing
from `bp_y` is refused. Where the length is its own data, name a boolean
parameter instead: that says how much of the curve to use, rather than how long
it is.

A breakpoint that is left out declares no weight and no segment binary, and its
values are not asked for. The marked breakpoints must be consecutive. They need
not start at the head of the axis, so a curve numbered from 1 is the same curve
one label along. A gap, or a curve with no points, is refused when the data
binds.

### `method`

`method` varies one thing: how the weights are restricted once they exist.

| `method`                | What it adds                                                                   |                                                                |
| ----------------------- | ------------------------------------------------------------------------------ | -------------------------------------------------------------- |
| `adjacency` _(default)_ | a binary per segment, and `lam <= seg + shift(seg, over=bp, offset=1, edge=0)` | the curve, built                                               |
| `sos2`                  | an [`sos:`](#sos) block over the same weights                                  | the curve, stated for a solver that branches on the set itself |
| `convex`                | nothing                                                                        | the hull, which is a pure linear program                       |
| `lp`                    | no weights at all: one row per segment line, plus two rows holding the domain  | the curve as its own lines                                     |

`adjacency` and `sos2` state the same restriction and reach the same optimum.
They differ in what the solver is handed, so which is faster is a property of the
solver.

`convex` is a different model. It is exact only for a curve whose curvature
matches the optimisation pressure, and that match is checked against the
breakpoint values when the data binds. It takes exactly two links and no
`activity:`.

`lp` states the curve as its segment lines instead of interpolating between
breakpoints, so it declares no auxiliary variable. It needs **exactly two
links**, one of them bounded with `<=` or `>=`, and no `activity:`, because there
are no weights for a gate to pin:

<!-- doctest: wrap=piecewise -->

```yaml
cost_curve:
  over: bp
  method: lp
  links:
    - [p, bp_x]
    - [op_cost, bp_y, ">="] # cost bounded below by the curve
```

`lp` trades columns for rows: one row per segment plus the two domain rows, in
place of one weight column per breakpoint. On a dispatch model with 20
generators, 48 snapshots and 6 breakpoints, that is 7680 columns down to 1920
and 2928 rows up to 6768, at the same optimum
([#926](https://github.com/fluxopt/lpspec/pull/926)). Two things follow from
stating lines rather than weights:

- **The curvature has to match the sign.** Lines that envelope a convex curve
  cut a concave one, and the solve then comes back optimal with a wrong answer.
  So `>=` requires a convex curve and `<=` a concave one, checked against the
  values when the data binds. This check is stricter than the one `convex` runs,
  which only refuses a mixed curve.
- **A line does not stop where its segment does.** The two domain rows hold the
  pinned link inside the breakpoint range, so the formulation cannot extrapolate
  along the end segments. They are the same rows that `linopy`'s own `lp` method
  emits.

### Writing the curve out by hand

`links:` is a list, so the number of expressions a block ties is written in the
file. Where that number is data, as when a boiler ties two flows and a CHP unit
ties three, write the formulation out:

<!-- doctest: skip -->

```yaml
variables:
  weight: # the convex combination, one per converter and period
    dims: [converter, time, bp]
    where: bp_present # how far each curve runs
    bounds: { lower: 0, upper: 1 }

sos:
  on_one_segment: { variable: weight, over: bp, type: 2, big_m: 1 }

constraints:
  one_operating_point:
    dims: [converter, time]
    expression: sum(weight, over=bp) == 1
  on_the_curve: # one row per flow — this is where the count goes
    dims: [flow, time]
    expression: rate == sum(at(weight, by=converter_of) * bp_rate, over=bp)
```

Making the tie a row turns the count into data: a converter with a fourth flow is
a row in a table, not an edit to the model. `sos: type: 2` states the same
restriction that `method: sos2` emits. The block would only have saved the
weights and the convexity row, so no block is offered for this case
([#1101](https://github.com/fluxopt/lpspec/issues/1101)).

## `sos`

An `sos` block declares a **special-ordered set**: one dimension of one
variable, and how many members of that family may be non-zero at once.

<!-- doctest: wrap=sos -->

```yaml
pick_one_size:
  variable: build # the variable the set is over
  over: size # the dimension it runs along — one set per coordinate of the rest
  type: 1 # 1: at most one non-zero; 2: at most two, and consecutive
  big_m: 500 # optional, and only read by a solver that has to reformulate
```

`type: 1` is a choice: at most one member is non-zero. `type: 2` is an
interpolation: at most two members are non-zero, and they are **consecutive**,
which is the native spelling of a piecewise-linear curve.

A set is over **one** variable, and a variable holds **one** set. A second block
naming the same variable is a load error.

Membership belongs to the variable. Its `where` decides which coordinates exist,
so a masked-out member is not in the set, and for `type: 2` consecutive means
consecutive among the members present. The order is the declared order of the
`over` dimension. To reorder the set, reorder that index.

### What a solver without SOS does with it

A solver with no concept of a set is handed binaries and big-M rows instead. Two
consequences of that rewrite reach the model:

- **The rewrite is mixed-integer.** A set on an otherwise continuous model gives
  up its duals.
- **M has to be finite.** Every member needs a `bounds.upper` or a `big_m:`, and
  a negative `bounds.lower` is refused. `big_m` caps a loose bound, and the
  tighter of the two is used, because tighter gives a better relaxation.

Both are conditions of the rewrite. A model that fails them still solves on a
solver that takes the set, and the message says so.
