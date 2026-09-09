<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Piecewise curves and SOS

These are two blocks for shapes that a purely affine language cannot state
directly. The first is a curve through breakpoints. The second is a family of
variables of which only one, or only two neighbours, may be non-zero.

## `piecewise`

A `piecewise` block pins several expressions together to a piecewise-linear
curve that is indexed by breakpoints.

<!-- doctest: wrap=piecewise -->

```yaml
chp:
  over: bp # breakpoint dimension
  links:
    - [power, power_bp] # [expression, values-parameter]
    - [fuel, fuel_bp]
    - [heat, heat_bp]
  method: adjacency # how the weights are restricted — below
  activity: null # optional: what the weights sum to, so 0 pins the formulation off

# a two-link block may bound one side instead of pinning it
fuel_cap:
  over: bp
  links:
    - [power, power_bp]
    - [fuel, fuel_bp, "<="]
```

| Part of a link |                                                                                                                                                                                                              |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| _expression_   | Any affine expression. The simplest one is a bare variable name                                                                                                                                              |
| _values_       | A parameter that carries the `over` dimension, plus any dimensions that the link _expressions_ carry. So a curve may vary per generator wherever the links do. A dimension the links do not carry is refused |
| _sign_         | `<=` or `>=`. At most one per block, and only in a block with exactly two links. It bounds the link instead of pinning it                                                                                    |

Use `points:` where the curves are not all the same length; it says how far each
curve runs, and it is described below. `activity:` answers a different question
again: not how long a curve is, but whether the curve _applies_ at all, gated by
a variable.

A block **expands before building**, into plain variables and constraints. For
three of the four methods it expands through a λ convex combination: weights in
`[0,1]`, a convexity row, and one link row per tuple. That expansion is what the
rest of the model sees, and it is what the
[typeset output](../typeset.md) shows.

A curve is supplied everywhere it is built. The expansion emits one weight per
breakpoint over the whole product of its dimensions, and it masks none of them.

!!! warning "A values parameter short of a row does not build a shorter curve"

    The [absence rules](absence.md#what-creates-absence) read the missing row
    as a zero coefficient, which is a breakpoint at the origin that the file
    never declared. Such a table is refused when the data binds. To say how far
    a curve runs, use `points:`.

A gate is a variable, or there is no gate. `activity:` names a binary
variable, and then the weights sum to that variable instead of to 1. So `0` pins
the curve off, columns and all.

The gate has to be a _declaration_ rather than an expression. A masked gate has
coordinates where it does not exist, and only a declaration says what that
means:

<!-- doctest: wrap=variables -->

```yaml
running:
  foreach: [snapshot, generator]
  domain: binary
  where: committable # only some units have a commitment decision
```

Where the gate does not exist, the curve is ungated. The block emits the
convexity row twice, under complementary masks: `== running` where the gate
exists, and `== 1` where it does not. That second row is what a block with no
`activity:` at all gets.

To say the opposite, put `absence: zero` on the gate. Then the single row reads
`== 0` there, which gives you no curve rather than an unconditional one. Both
readings belong to the file, and neither is inferred.

The reason for the pair of rows is that the row cannot be allowed to drop. The
row is `sum(lam, over=bp) == (activity)`, and
[absence](absence.md#how-absence-travels) does not spread out of a reduction. So
an absent right-hand side would take the whole row with it, and leave the
weights with nothing to make them a curve.

The breakpoint order is the index order of `over`. That is the order every
dimension has: the order in which its labels are first written. It is the order
`shift` walks, and the order that `position(bp) == 0` names.

So the `bp` index is the x-axis of the curve, and a values parameter is a lookup
against that index. A table is a function of its coordinates, and the order its
rows arrive in means nothing, on either lane.

"Strictly increasing breakpoints" below means increasing _in that index order_.
Write the index backwards, and the curve really does run backwards, which is
refused.

A curve with fewer breakpoints than the dimension holds says how far it runs,
using `points:`. Name one of the block's own values parameters, and the curve
is as long as that parameter's rows:

<!-- doctest: wrap=piecewise -->

```yaml
cost_curve:
  over: bp
  points: bp_x # this curve runs as far as its own breakpoints do
  links:
    - [p, bp_x]
    - [op_cost, bp_y]
```

A length is a fact about the curve, so this keeps the length there. The other
links are still read against the parameter you named, so a row missing from
`bp_y` is refused.

Where the length is its own data, name a **boolean parameter** instead. That
answers a different question: not _how long the curve is_, but _how much of it
to use_.

A breakpoint that is left out declares no weight and no segment binary, and its
values are not asked for.

The marked breakpoints must be consecutive. They need not start at the head
of the axis, so a curve numbered from 1 is the same curve one label along. A
gap, or a curve with no points at all, is refused when the data binds. The chord
row joins each breakpoint to the one before it, and the two domain rows sit on
the curve's own first and last breakpoints.

Sometimes the number of tied expressions is data: one component ties three
where another ties two. Then you
[write the λ formulation out directly](#when-the-number-of-tied-expressions-is-data-the-formulation-is-four-declarations)
instead of using this block
([#1101](https://github.com/fluxopt/lpspec/issues/1101)).

`method` is the one thing that varies. For the three methods that share the
λ expansion, it varies in exactly one place: how the weights are restricted,
once they exist.

| `method`                | What it adds                                                                   |                                                                 |
| ----------------------- | ------------------------------------------------------------------------------ | --------------------------------------------------------------- |
| `adjacency` _(default)_ | a binary per segment, and `lam <= seg + shift(seg, over=bp, offset=1, edge=0)` | the curve, built                                                |
| `sos2`                  | an [`sos:`](#sos) block over the same weights                                  | the curve, _said_, for a solver that branches on the set itself |
| `convex`                | nothing                                                                        | the hull, which is a pure linear program                        |
| `lp`                    | no weights at all: one row per segment line, plus two rows holding the domain  | the curve as its own lines                                      |

`adjacency` and `sos2` state the same restriction and reach the same optimum.
They differ in what the solver is handed. So which one is faster is a property
of the solver, not of the model.

`convex` is a **different model**. It is exact only for a curve whose curvature
matches the optimisation pressure, and that match is checked against the
breakpoint _values_ when the data binds. It takes exactly two links, and no
`activity:`.

### `lp`, which declares no auxiliary variable

`lp` states the curve as its **segment lines**, instead of interpolating between
its breakpoints. So it declares no auxiliary variable at all, where the other
methods carry one weight per breakpoint per frame row.

It needs exactly two links, and one of the two must be bounded with `<=` or
`>=`. It takes no `activity:`, because there are no weights for a gate to pin
down.

<!-- doctest: wrap=piecewise -->

```yaml
cost_curve:
  over: bp
  method: lp
  links:
    - [p, bp_x]
    - [op_cost, bp_y, ">="] # cost bounded below by the curve
```

The trade is **columns for rows**. You get one row per segment plus the two
domain rows, in place of K weight columns. On a dispatch model with 20
generators, 48 snapshots and 6 breakpoints, that is 7680 columns down to 1920,
and 2928 rows up to 6768, at the same optimum
([#926](https://github.com/fluxopt/lpspec/pull/926)).

Two things follow from stating lines rather than weights:

- **The curvature has to match the sign**, and getting it wrong is silent. Lines
  that envelope a convex curve _cut_ a concave one, and the solve then comes
  back optimal with a wrong answer. So `>=` requires a convex curve, and `<=`
  requires a concave one. Both are checked against the values when the data
  binds. This check is stricter than the one `convex` runs, which only refuses a
  _mixed_ curve.
- **A line does not stop where its segment does.** So the block emits the two
  domain rows that hold the pinned link inside the breakpoint range. Without
  those rows, the formulation would extrapolate along the end segments, where the
  weight forms cannot go. These are the same rows that `linopy`'s own `lp`
  method emits.

### When the number of tied expressions is data, the formulation is four declarations

`links:` is a list, so the number of expressions a block ties is written in the
file. Sometimes that number is a property of the system, as when a boiler ties
two flows and a CHP unit ties three. Then you write the formulation out instead,
and it is not much to write:

<!-- doctest: skip -->

```yaml
variables:
  weight: # the convex combination, one per converter and period
    foreach: [converter, time, bp]
    where: bp_present # how far each curve runs
    bounds: { lower: 0, upper: 1 }

sos:
  on_one_segment: { variable: weight, over: bp, type: 2, big_m: 1 }

constraints:
  one_operating_point:
    foreach: [converter, time]
    expression: sum(weight, over=bp) == 1
  on_the_curve: # one row per flow — this is where the count goes
    foreach: [flow, time]
    expression: rate == sum(at(weight, by=converter_of) * bp_rate, over=bp)
```

Making the tie a _row_ is what turns that count into data. A converter with a
fourth flow is then a row in a table, rather than an edit to the model.

`sos: type: 2` states the same restriction that `method: sos2` emits. A solver
without SOS support is handed binaries and big-M rows either way.

The block would only have saved the weights and the convexity row, which is two
declarations. So the block is not offered.
[#1101](https://github.com/fluxopt/lpspec/issues/1101) records what was
weighed.

## `sos`

An `sos` block declares a **special-ordered set**. It names one dimension of one
variable, and says how many of that family may be non-zero at once.

<!-- doctest: wrap=sos -->

```yaml
pick_one_size:
  variable: build # the variable the set is over
  over: size # the dim it runs along — one set per coordinate of the rest
  type: 1 # 1: at most one nonzero; 2: at most two, and consecutive
  big_m: 500 # optional, and only read by a solver that has to reformulate
```

`type: 1` is a **choice**: at most one member of the family is non-zero.

`type: 2` is an **interpolation**: at most two members are non-zero, and those
two must be _consecutive_. That is what makes `type: 2` the native spelling of a
piecewise-linear curve.

A set is over one variable, and a variable holds one set. A second block
that names the same variable is a load error.

Membership belongs to the variable. The variable's `where` decides which
coordinates exist, so a masked-out member is not in the set. For `type: 2`,
consecutive means consecutive _among the members that are present_, so a
coordinate that was masked away leaves no hole.

The order is the declared order of the `over` dimension, which is the same
order `shift` walks. So to reorder the set, reorder that index. There is no
per-set weight to supply.

### What a solver without SOS does with it

Where the chosen solver has no concept of an SOS, the set is handed over as
binaries and big-M rows instead. Two consequences of that rewrite reach the
model, so neither one is silent:

- The rewrite is **mixed-integer**. So a set on an otherwise continuous model
  gives up its duals.
- **M has to be finite.** So every member needs either a `bounds.upper` or a
  `big_m:`, and a negative `bounds.lower` is refused. `big_m` caps a loose
  bound, and the _tighter_ of the two values is used, because tighter gives a
  better relaxation.

Both of these are conditions of the _rewrite_. So a model that fails them still
solves on a solver that takes the set, and the message says so. HiGHS, which
ships with the package, reformulates. Gurobi branches on the set itself.
