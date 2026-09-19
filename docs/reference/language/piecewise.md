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

```yaml
piecewise:
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

| Part of a link |                                                                                                                                              |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| _expression_   | Any affine expression. The simplest is a bare variable name                                                                                  |
| _values_       | A parameter that carries the `over` dimension, plus any dimensions the link expressions carry. A dimension the links do not carry is refused |
| _sign_         | `<=` or `>=`. At most one per block, and only in a block with exactly two links. It bounds the link instead of pinning it                    |
| _by_, _over_, _into_ | A relation and the columns the link reads the curve's weights through. The link then sits on a refinement of the frame ([below](#a-link-through-a-relation)) |

| Key        |                                                                                          |                     |
| ---------- | ---------------------------------------------------------------------------------------- | ------------------- |
| `over`     | required. The breakpoint dimension                                                       |                     |
| `links`    | required. Two or more links                                                              |                     |
| `dims`     | the curve's frame ([below](#dims))                                                       | inferred            |
| `where`    | which coordinates have a curve at all ([below](#where))                                  | default `null`      |
| `method`   | `adjacency`, `sos2`, `convex` or `lp`: how the weights are restricted ([below](#method)) | default `adjacency` |
| `activity` | a binary variable that gates the curve ([below](#activity))                              | default `null`      |
| `points`   | how far each curve runs, where the curves are not all the same length ([below](#points)) | default `null`      |

A block expands before building, into plain variables and constraints: one
weight per breakpoint in `[0, 1]`, one row making the weights sum to 1, and one
row per link tying its expression to the weighted breakpoints. That expansion
is what the rest of the model sees, and what the
[typeset output](../typeset.md) prints.

The breakpoint order is the declared order of `over`. A curve whose breakpoints
decrease in that order is refused when the data binds.

!!! warning "A values parameter short of a row does not build a shorter curve"

    The missing row reads as a breakpoint at the origin, and the table is
    refused when the data binds. To say how far a curve runs, use `points:`.

### `dims`

A block builds one curve for every coordinate of its **frame**. `dims:` states
the frame. Where the file writes none, the frame is the union of the dims the
link expressions carry.

A block whose links all sit on the frame needs no `dims:`. Write it where the
links no longer say what the frame is, which is any block with a link through a
relation.

`dims:` may not carry the breakpoint dimension. Every curve runs along that
axis, so it is not something the block builds one curve per.

### `where`

A block builds one curve for every coordinate of its **frame**, which `dims:`
states or the link expressions imply. `where:` says which of those coordinates
have a curve:

```yaml
piecewise:
  cost_curve:
    over: bp
    where: has_curve # only some generators run on a cost curve
    links:
      - [dispatch, bp_x]
      - [op_cost, bp_y]
```

Off the mask the block builds nothing. There are no weights, no convexity row
and no link row, so the linked expressions are left free. The breakpoint values
are not read there either: a generator with no curve needs no row in `bp_x` or
`bp_y`.

`where:` is not [`activity:`](#activity). A coordinate outside the mask has no
curve. A gated coordinate has a curve that the solver may switch off, and its
rows are built either way.

The mask may not carry the breakpoint dimension. It says which coordinates have
a curve, and [`points:`](#points) says how far each curve runs along that axis.
A mask carrying a dimension that no link expression carries is refused as well,
because a mask cannot add coordinates.

### `activity`

`activity:` names a binary variable, and the weights then sum to that variable
instead of to 1. So `0` pins the curve off.

The gate is a declaration:

```yaml
variables:
  running:
    dims: [snapshot, generator]
    domain: binary
    where: committable # only some units have a commitment decision
```

Where the gate does not exist, the curve is ungated. To pin the curve off
there instead, put `absence: zero` on the gate. To build no curve there at all,
use [`where:`](#where).

### `points`

A curve with fewer breakpoints than the dimension holds says so with `points:`.
Name one of the block's own values parameters, and the curve is as long as that
parameter has rows:

```yaml
piecewise:
  cost_curve:
    over: bp
    points: bp_x # this curve runs as far as its own breakpoints do
    links:
      - [p, bp_x]
      - [op_cost, bp_y]
```

The other links are still read against the parameter you named, so a row missing
from `bp_y` is refused. Where the length is its own data, name a boolean
parameter instead.

The marked breakpoints must be consecutive. They need not start at the head of
the axis. A gap, or a curve with no points, is refused when the data binds.

### A link through a relation

`links:` is a list, so the number of *kinds* of link a block ties is written in
the file. The number of **rows** each link builds is data. A link naming `by:`
reads the curve's weights through a relation, so one link entry builds one row
per fine coordinate:

```yaml
relations:
  generator_of: { key: flow, values: generator }

piecewise:
  coupling:
    over: bp
    dims: [generator, snapshot] # one curve per generator
    links:
      - { expression: power, values: bp_power, by: generator_of, over: generator, into: flow }
      - [fuel, bp_fuel]
```

`power` is per flow and the curve is per generator, so the first link builds one
row for each of a generator's flows. A generator with five flows and a generator
with two share the block. A sixth flow is a row in `generator_of`, not an edit to
the model.

`by:`, `over:` and `into:` are the [`at`](operators.md#at) walk, and mean there
what they mean everywhere. The block writes
`at(coupling_lam, by=generator_of, over=generator, into=flow)` into that link's
row, so the weights stay on the curve's frame and the model never names them. A
link's row is built over the frame with the consumed dimension replaced by the
produced one — `[flow, snapshot]` above.

The three are written together. A walk states which columns it consumes and
which it produces, and neither is defaulted.

| A refined link |                                                                                        |
| -------------- | -------------------------------------------------------------------------------------- |
| the block      | declares `dims:`, because the links no longer say what the frame is                    |
| _over_         | names a column over one of the frame's own dimensions                                  |
| _values_       | follows the **link's** frame: `bp_power` is per flow, not per generator                |
| `points:`      | names a values parameter of a link that reads no relation, because raggedness is the curve's |
| `method:`      | `adjacency` or `sos2`. `convex` and `lp` prove a curvature by comparing the two values parameters, which a refinement puts on two frames |

### `method`

`method` says how the weights are restricted once they exist.

| `method`                | What it adds                                                                    |                                                                |
| ----------------------- | ------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| `adjacency` _(default)_ | a binary per segment, and `lam <= seg + shift(seg, along=bp, offset=1, edge=0)` | the curve, built                                               |
| `sos2`                  | an [`sos:`](#sos) block over the same weights                                   | the curve, stated for a solver that branches on the set itself |
| `convex`                | nothing                                                                         | the hull, which is a pure linear program                       |
| `lp`                    | no weights at all: one row per segment line, plus two rows holding the domain   | the curve as its own lines                                     |

`adjacency` and `sos2` state the same restriction and reach the same optimum.
They differ in what the solver is handed.

`convex` is a different model. It is exact only for a curve whose curvature
matches the optimisation pressure, and that match is checked against the
breakpoint values when the data binds. It takes exactly two links and no
`activity:`.

`lp` states the curve as its segment lines. It needs **exactly two links**, one
of them bounded with `<=` or `>=`, and no `activity:`:

```yaml
piecewise:
  cost_curve:
    over: bp
    method: lp
    links:
      - [p, bp_x]
      - [op_cost, bp_y, ">="] # cost bounded below by the curve
```

`>=` requires a convex curve and `<=` a concave one, checked against the values
when the data binds. The two domain rows hold the pinned link inside the
breakpoint range.

## `sos`

An `sos` block declares a **special-ordered set**: one dimension of one
variable, and how many members of that family may be non-zero at once.

```yaml
sos:
  pick_one_size:
    variable: build # the variable the set is over
    over: size # the dimension it runs along — one set per coordinate of the rest
    type: 1 # 1: at most one non-zero; 2: at most two, and consecutive
    big_m: 500 # optional, and only read by a solver that has to reformulate
```

`type: 1` is a choice: at most one member is non-zero. `type: 2` is an
interpolation: at most two members are non-zero, and they are **consecutive**.

A set is over **one** variable, and a variable holds **one** set. A second block
naming the same variable is a load error.

Membership belongs to the variable. Its `where` decides which coordinates exist,
so a masked-out member is not in the set. The order is the declared order of
the `over` dimension.

A solver with no concept of a set is handed binaries and big-M rows instead.
That rewrite is mixed-integer, so it gives up its duals, and it needs a finite
M: every member needs a `bounds.upper` or a `big_m:`, and a negative
`bounds.lower` is refused. A model that fails those conditions still solves on
a solver that takes the set, and the message says so.
