<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Piecewise curves and SOS

Two blocks state shapes that no `expression:` can, because an expression is
affine. `piecewise:` states a curve through breakpoints. `sos:` states a family
of variables of which only one, or only two neighbours, may be non-zero.

Both are **formulations**: each states plain variables and constraints rather
than being one, and [`spec.expand()`](#writing-a-formulation-out) writes them
out.

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

| Key        |                                                                                          |                     |
| ---------- | ---------------------------------------------------------------------------------------- | ------------------- |
| `over`     | required. The breakpoint dimension                                                       |                     |
| `links`    | required. Two or more links                                                              |                     |
| `method`   | `adjacency`, `sos2`, `convex` or `lp`: how the weights are restricted ([below](#method)) | default `adjacency` |
| `activity` | a binary variable that gates the curve ([below](#activity))                              | default `null`      |
| `points`   | how far each curve runs, where the curves are not all the same length ([below](#points)) | default `null`      |

A block states plain variables and constraints: one weight per breakpoint in
`[0, 1]`, one row making the weights sum to 1, and one row per link tying its
expression to the weighted breakpoints. A `Program` holds those rows, because a
consumer builds them; the [typeset output](../typeset.md) prints the curve
itself, and [`spec.expand()`](#writing-a-formulation-out) is what writes the
rows into a model of their own.

The breakpoint order is the declared order of `over`. A curve whose breakpoints
decrease in that order is refused when the data binds.

Every condition this page says is checked "when the data binds" is an
[assumption](assumptions.md), written in the same grammar as one the file
states. The `method:` implies it rather than the file writing it, so
[`expand()`](#writing-a-formulation-out) writes it into `assumptions:` under
the block's own name, and a model that still declares the block derives the
same text when it loads. Both print under one heading, and the consumer that
binds the numbers runs them.

!!! warning "A values parameter short of a row does not build a shorter curve"

    The missing row reads as a breakpoint at the origin. Every block states
    `<block>_complete` for this, whatever its `method:`, so the table is
    refused when the data binds and the refusal names `points:` as the way to
    say how far a curve runs.

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

Where the gate does not exist, the curve is ungated. To have no curve there
instead, put `absence: zero` on the gate.

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

### `method`

`method` says how the weights are restricted once they exist.

| `method`                | What it adds                                                                  |                                                                |
| ----------------------- | ----------------------------------------------------------------------------- | -------------------------------------------------------------- |
| `adjacency` _(default)_ | an [`sos:`](#sos) block over the weights, written out as binaries             | the curve, built                                               |
| `sos2`                  | an [`sos:`](#sos) block over the weights, left as a set                       | the curve, stated for a solver that branches on the set itself |
| `convex`                | nothing                                                                       | the hull, which is a pure linear program                       |
| `lp`                    | no weights at all: one row per segment line, plus two rows holding the domain | the curve as its own lines                                     |

`adjacency` and `sos2` state the same restriction and reach the same optimum.
They differ in what the solver is handed: `adjacency` **is** `sos2` with the set
written out, so the two emit the same rows under the same names.

`convex` is a different model: the weights range over the hull the breakpoints
span rather than over the curve itself. It takes exactly two links and no
`activity:`.

A bounded link binds from one side, and that side is the part of the hull the
weights are driven onto. `>=` requires a convex curve and `<=` a concave one.
With both links pinned the weights reach the whole hull. What drives them
within it is the rest of the model rather than the block, so the curve must
bend one way only. Each of the three conditions is checked against the
breakpoint values when the data binds.

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

The bounded link decides the shape, as it does under `convex` above. The two
domain rows hold the pinned link inside the breakpoint range: under `points:`,
each sits where the mask holds and does not one breakpoint outward, which is
the first and the last breakpoint of each curve.

`links:` is a list, so the number of expressions a block ties is written in the
file. Where that number is data, write the formulation out
([a curve by hand](../../howto/curve-by-hand.md)).

## `sos`

An `sos` block declares a **special-ordered set**: one dimension of one
variable, and how many members of that family may be non-zero at once.

```yaml
sos:
  pick_one_size:
    variable: build # the variable the set is over
    over: size # the dimension it runs along — one set per coordinate of the rest
    type: 1 # 1: at most one non-zero; 2: at most two, and consecutive
```

`type: 1` is a choice: at most one member is non-zero. `type: 2` is an
interpolation: at most two members are non-zero, and they are **consecutive**.

A set is over **one** variable, and a variable holds **one** set. A second block
naming the same variable is a load error.

Membership belongs to the variable. Its `where` decides which coordinates exist,
so a masked-out member is not in the set. The order is the declared order of
the `over` dimension.

### What a set is written out as

`spec.expand('sos')` states the set as binaries: one per member for `type: 1`,
one per segment for `type: 2`. A member the binaries do not admit is held at
zero, from above and from below. The names are the block's own, and the rows are
these, for a set `s` over variable `x` along `d`, writing `admitted` for
`(s_seg)` at `type: 1` and `(s_seg + shift(s_seg, along=d, offset=1, edge=0))`
at `type: 2`:

| Emitted                                            |                                                   |
| -------------------------------------------------- | ------------------------------------------------- |
| `s_seg`                                            | a binary over `x`'s own dims, masked as `x` is    |
| `s_pick`: `sum(s_seg, over=d) <= 1`                | at most one is picked                             |
| `s_nonzero` (`type: 1`), `s_adjacency` (`type: 2`) | `x <= upper * admitted`                           |
| the same name plus `_below`                        | `x >= lower * admitted`, where `lower` is not `0` |

Each coefficient is read off the member's own `bounds:`. A binary member's are
`0` and `1`, from its domain. A row multiplies by its coefficient rather than
reading it, so a bound the data carries is a coefficient like any other:
`bounds: {lower: floor, upper: cap}` states `x >= floor * admitted` and
`x <= cap * admitted`.

Two coefficients are left out rather than printed, because the row would state
what another row already does: a `1` above, and a `lower` of `0`, which the
variable's own bound states.

So each side needs a coefficient, and a model is refused at load without one:

- `bounds.lower`, a number or a parameter. An omitted lower bound leaves the
  member free below zero, which no row can pull back.
- `bounds.upper`, a number or a parameter, or `domain: binary`.

The set carries no coefficient of its own. A number below the member's bound
would cap a picked member the set does not cap, and one above it is a looser
row than the bound already states, so there is no value of such a key that
states the set and nothing else.

A positive `bounds.lower` loads and is infeasible, as it is on a solver that
takes the set: an unpicked member has to be `0`, and its own bound says it is
above that.

A name the expansion writes that the file already declares is refused at load
too.

## Writing a formulation out

`Spec.expand()` returns the same math with its formulations stated as plain
variables and constraints:

```python
from math_spec import to_spec

spec = to_spec('curve.yaml')
spec.expand()  # every formulation
spec.expand('sos')  # only the sets
spec.expand('piecewise')  # only the curves
```

[See what a curve or a set expands to](../../howto/see-an-expansion.md) shows
a model before and after, as whole files.

- **The kinds are `'piecewise'` and `'sos'`, and no argument means both.** Any
  other string is refused, naming the two. Curves go first whatever order they
  are asked in, because a `method: sos2` curve states a set and no set states a
  curve.
- **A model with nothing to write out is the model that comes back.** So is a
  second call with the same kinds.
- **The same data binds a model and its expansion.** Neither a set nor a curve
  emits a parameter. A curve under `points:` sits its rows on `where:`
  predicates over the mask the file named, and the expansion is a file like any
  other: `to_yaml()` writes it, and loading it back changes nothing.
- **`to_program()` writes nothing out.** A model still carrying a curve is
  refused, naming `spec.expand('piecewise')`. A program carries a set, because
  a consumer with the concept takes one; a consumer without it refuses the
  model and names `spec.expand()`.
