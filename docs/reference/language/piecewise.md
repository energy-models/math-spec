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
    along: bp # the dimension each curve runs along
    links:
      - [power, power_bp] # [expression, values-parameter]
      - [fuel, fuel_bp]
      - [heat, heat_bp]
    method: adjacency # how the weights are restricted — below
    activity: null # optional: a binary variable that the weights sum to

  # a two-link block may bound one side instead of pinning it
  fuel_cap:
    along: bp
    links:
      - [power, power_bp]
      - [fuel, fuel_bp, "<="]
```

| Part of a link |                                                                                                                                              |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| _expression_   | Any affine expression. The simplest is a bare variable name                                                                                  |
| _values_       | A parameter that carries the `along` dimension, plus any dimensions the link expressions carry. A dimension the links do not carry is refused |
| _sign_         | `<=` or `>=`. It bounds the link by the curve instead of pinning it to it. Any number of links may carry one, as long as at least one link does not ([below](#signs))                    |
| _into_         | A dimension the link's row gains, so every coordinate of it is a tie to the one operating point ([below](#a-link-that-refines-the-curve))                    |
| _by_, _over_   | A relation and the columns the walk consumes, where the refinement is reached through one rather than simply gained                          |

| Key        |                                                                                          |                     |
| ---------- | ---------------------------------------------------------------------------------------- | ------------------- |
| `along`    | required. The dimension each curve runs along                                            |                     |
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

The breakpoint order is the declared order of `along`. A curve whose breakpoints
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

**A link expression carries exactly the dimensions its row is built over**,
which is the frame, or the refinement of it a relation walk names. A dimension
the expression carries and the row does not multiplies the rows the link
builds. A dimension the row carries and the expression does not repeats one row
across it, which pins the expression to a single operating point along a
dimension the curve varies over. Both are refused, and the message names which
one it is.

A quantity that varies along a dimension the curve does not, such as a rate per
period read off a curve that has none, is said by adding that dimension to
`dims:`. The curve then varies along it too. Whether the breakpoint values also
vary along it is the data's business: values that do not carry it give one curve
shape and a per-period operating point.

### `where`

A block builds one curve for every coordinate of its **frame**, which `dims:`
states or the link expressions imply. `where:` says which of those coordinates
have a curve:

```yaml
piecewise:
  cost_curve:
    along: bp
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
    along: bp
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

### A link that refines the curve

`links:` is a list, so the number of *kinds* of link a block ties is written in
the file. The number of **rows** each link builds is data. A link that names
`into:` builds one row per fine coordinate, all reading the one set of weights.

Its row is `(frame - over) | into`, which is the frame law a
[relation](relations.md#how-a-relation-is-used) walk already follows. Two forms
fall out of it:

| written | the row | the weights |
| --- | --- | --- |
| `into: carrier` | the frame, plus `carrier` | broadcast across `carrier` |
| `by: converter_of, over: converter, into: flow` | the frame, less `converter`, plus `flow` | read through the relation |

**`into:` alone names a dimension the row gains.** Every coordinate of it is a
tie to the one operating point, so a converter's carriers move together:

```yaml
piecewise:
  op:
    along: bp
    dims: [converter, snapshot] # one curve per converter
    links:
      - { expression: rate, values: bp_rate, into: carrier }
```

`rate` is over `[converter, carrier, snapshot]` and `bp_rate` over
`[converter, carrier, bp]`, so each carrier has its own breakpoint column and
reads the same weights. The dimension `into:` names may not be one the curve's
`dims:` already carries: the curve builds one per coordinate of those, so they
cannot also index a link's ties.

**`by:`, `over:` and `into:` together** reach the refinement through a relation
instead, which is what a ragged fan-out needs — one converter tying two flows and
another five:

```yaml
relations:
  generator_of: { key: flow, values: generator }

piecewise:
  coupling:
    along: bp
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
what they mean everywhere. A link's `over:` names a relation column the walk
consumes; the block's `along:` names the dimension each curve runs along, and a
walk never consumes that. The block writes
`at(coupling_lam, by=generator_of, over=generator, into=flow)` into that link's
row, so the weights stay on the curve's frame and the model never names them. A
link's row is built over the frame with the consumed dimension replaced by the
produced one — `[flow, snapshot]` above.

The three are written together. A walk states which columns it consumes and
which it produces, and neither is defaulted.

A block whose links are all refined needs only one of them. Two links is what
a curve needs when a link is one row; a refined link is one row per fine
coordinate, so the relation supplies the arity the second link otherwise would.

| A refined link |                                                                                        |
| -------------- | -------------------------------------------------------------------------------------- |
| the block      | declares `dims:`, because the links no longer say what the frame is                    |
| _over_         | names a column over one of the frame's own dimensions, and needs `by:` beside it       |
| _values_       | follows the **link's** frame: `bp_power` is per flow, not per generator                |
| `points:`      | names a values parameter of a link that reads no relation, because raggedness is the curve's |
| `method:`      | `adjacency` or `sos2`. `lp` loses the abscissa its segment line is written against, and `convex` loses the pair of values parameters it reads a shape from |
| `where:`       | reaches a link that only gains a dimension. A walk is refused, because it replaces the frame dimension the mask tests — mask the link's own variable instead |

### Signs

A link with no sign is **pinned** to the curve: its expression equals the
weighted breakpoints. A link carrying `<=` or `>=` is **bounded** by the curve
instead, and each link carries its own.

**At least one link is pinned.** A pinned link fixes the operating point every
other link is read at. With every link bounded the weights are free, and the
block no longer says that its quantities sit together on a curve — it says only
that some point on the curve satisfies the bounds. That is a different model,
so it is refused rather than guessed.

```yaml
piecewise:
  chp:
    along: bp
    links:
      - [power, power_bp] # pinned: it fixes the operating point
      - [fuel, fuel_bp, ">="] # bounded below by the curve
      - [heat, heat_bp, "<="] # bounded above, at that same point
```

`convex` and `lp` take exactly two links, so there a sign is one link's at
most. Under `adjacency` and `sos2` each link is its own row against the shared
weights, so the count is whatever the model needs.

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

`convex` is a different model. It relaxes the weights onto the hull the
breakpoints span, which is exact only for a curve whose curvature matches the
optimisation pressure. That match is checked against the breakpoint values when
the data binds, and the sign on the bounded link is what names the direction to
check it in. So `convex` takes exactly two links: the rows it builds would serve
any number, but past two there is no single direction left to certify the
relaxation against. It takes no `activity:`.

`lp` states the curve as its segment lines. It takes **exactly two links**,
because a line is one quantity against another: one link names the abscissa and
one is bounded by the lines. It takes no `activity:`:

```yaml
piecewise:
  cost_curve:
    along: bp
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
    along: size # the dimension it runs along — one set per coordinate of the rest
    type: 1 # 1: at most one non-zero; 2: at most two, and consecutive
    big_m: 500 # optional, and only read by a solver that has to reformulate
```

`type: 1` is a choice: at most one member is non-zero. `type: 2` is an
interpolation: at most two members are non-zero, and they are **consecutive**.

A set is over **one** variable, and a variable holds **one** set. A second block
naming the same variable is a load error.

Membership belongs to the variable. Its `where` decides which coordinates exist,
so a masked-out member is not in the set. The order is the declared order of
the `along` dimension.

A solver with no concept of a set is handed binaries and big-M rows instead.
That rewrite is mixed-integer, so it gives up its duals, and it needs a finite
M: every member needs a `bounds.upper` or a `big_m:`, and a negative
`bounds.lower` is refused. A model that fails those conditions still solves on
a solver that takes the set, and the message says so.
