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

A `piecewise` block ties expressions to one piecewise-linear curve for every
coordinate of its `dims:`. The curve is given as breakpoints: the corner values
each expression takes together.

```yaml
piecewise:
  chp:
    along: bp # the dimension each curve runs along
    dims: [generator, snapshot] # one curve per coordinate of these
    links: # each link by the name of the row it writes, chp_<link>
      power: [power, power_bp] # [expression, values-parameter]
      fuel: [fuel, fuel_bp]
      heat: [heat, heat_bp]
    method: adjacency # how the weights are restricted — below
    activity: null # optional: a binary variable that the weights sum to

  # a link may be bounded by the curve instead of pinned to it
  fuel_cap:
    along: bp
    dims: [generator, snapshot]
    links:
      power: [power, power_bp]
      fuel: [fuel, fuel_bp, "<="]
```

| Part of a link       |                                                                                                                                                                       |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| _name_               | The key. The link's row in the expansion is `<block>_<name>`                                                                                                          |
| _expression_         | Any affine expression over the link's row. The simplest is a bare variable name                                                                                       |
| _values_             | A parameter that carries the `along` dimension. Every other dimension it carries is one the link's row carries                                                        |
| _sign_               | `<=` or `>=`. It bounds the link by the curve instead of pinning it to it. Any number of links may carry one, as long as at least one link does not ([below](#signs)) |
| _by_, _over_, _into_ | A relation walk from the curve's `dims:` to the link's row ([below](#a-link-that-walks-a-relation))                                                                   |

| Key        |                                                                                          |                     |
| ---------- | ---------------------------------------------------------------------------------------- | ------------------- |
| `along`    | required. The dimension each curve runs along                                            |                     |
| `dims`     | required. The dimensions the block builds one curve per coordinate of ([below](#dims))   |                     |
| `links`    | required. Two or more links, or one that walks a relation                                |                     |
| `where`    | which coordinates have a curve, and how far each runs ([below](#where))                  | default `null`      |
| `method`   | `adjacency`, `sos2`, `convex` or `lp`: how the weights are restricted ([below](#method)) | default `adjacency` |
| `activity` | a binary variable that gates the curve ([below](#activity))                              | default `null`      |

A block states plain variables and constraints: one weight per breakpoint in
`[0, 1]`, one row making the weights sum to 1, and one row per link tying its
expression to the weighted breakpoints. A `Program` holds those rows, because a
consumer builds them; the [typeset output](../typeset.md) prints the curve
itself, and [`spec.expand()`](#writing-a-formulation-out) is what writes the
rows into a model of their own.

A link names the row it writes, so a link may not take a name the block
already writes for itself, such as `convexity` or `lam`.

The breakpoint order is the declared order of `along`. A curve whose breakpoints
decrease in that order is refused when the data binds.

Every condition this page says is checked "when the data binds" is an
[assumption](assumptions.md), written in the same grammar as one the file
states. The `method:` implies it rather than the file writing it, so
[`expand()`](#writing-a-formulation-out) writes it into `assumptions:` under
the block's own name, and a model that still declares the block derives the
same text when it loads. Both print under one heading, and the consumer that
binds the numbers runs them. Each one is asked only where the block's
[`where:`](#where) says a curve runs.

!!! warning "A values parameter short of a row does not build a shorter curve"

    The missing row reads as a breakpoint at the origin. Every block states
    `<block>_complete` for this, whatever its `method:`, so the table is
    refused when the data binds and the refusal names `where:` as the way to
    say how far a curve runs.

### `dims`

A block builds one curve for every coordinate of `dims:`. Each curve is one set
of weights. `dims:` may not carry the breakpoint dimension, because every curve
runs along it.

**A link expression carries exactly the dimensions of its row.** The row of a
link is `dims:`, or the dimensions a [walk](#a-link-that-walks-a-relation)
reaches. A dimension the expression carries and the row does not multiplies the
rows the link builds. A dimension the row carries and the expression does not
repeats one row across it, which pins the expression to a single operating point
along a dimension the curve varies over. Both are refused, and the message
names which one it is.

A quantity that varies along a dimension the curve does not, such as a rate per
period read off a curve that has none, is said by adding that dimension to
`dims:`. The curve then varies along it too. Whether the breakpoint values also
vary along it is the data's business: values that do not carry it give one curve
shape and a per-period operating point.

An [`activity:`](#activity) gate carries no dimension that `dims:` does not. A
gate over fewer dimensions switches every curve it covers: a gate per generator
switches that generator's curve in every snapshot.

### `where`

`where:` says which coordinates of `dims:` have a curve:

```yaml
piecewise:
  cost_curve:
    along: bp
    dims: [generator]
    where: has_curve # only some generators run on a cost curve
    links:
      dispatch: [dispatch, bp_x]
      op_cost: [op_cost, bp_y]
```

Off the mask the block builds nothing. There are no weights, no convexity row
and no link row, so the linked expressions are left free. The breakpoint values
are not read there either: a generator with no curve needs no row in `bp_x` or
`bp_y`.

`where:` is not [`activity:`](#activity). A coordinate outside the mask has no
curve. A gated coordinate has a curve that the solver may switch off, and its
rows are built either way.

A mask carrying a dimension that `dims:` does not carry is refused, because a
mask cannot add coordinates. The breakpoint dimension is the one exception, and
reading it is how a block says how far each curve runs.

#### Curves of unequal length

A curve with fewer breakpoints than the dimension holds says so with a `where:`
that reads the breakpoint dimension. Name one of the block's own values
parameters, and the curve is as long as that parameter has rows:

```yaml
piecewise:
  cost_curve:
    along: bp
    dims: [generator]
    where: bp_x # this curve runs as far as its own breakpoints do
    links:
      p: [p, bp_x]
      op_cost: [op_cost, bp_y]
```

The other links are still read against the parameter you named, so a row missing
from `bp_y` is refused. Where the length is its own data, name a boolean
parameter over `dims:` and the breakpoint dimension instead. Either composes
with a mask over `dims:`: `has_curve AND bp_x` says which generators have a
curve and how far each one runs.

The marked breakpoints must be consecutive. They need not start at the head of
the axis. A gap is refused when the data binds, and a coordinate the mask
leaves with no breakpoint has no curve.

The rows a block writes over `dims:` alone, such as the one making the weights
sum to 1, cannot read the breakpoint dimension. There the mask reads as
`count(where, over=bp) > 0`: a curve exists where it admits at least one
breakpoint.

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

### A link that walks a relation

A link that names `by:`, `over:` and `into:` reads the curve's weights through a
[relation](relations.md#how-a-relation-is-used), as [`at`](operators.md#at)
does. It builds one row per coordinate that the walk reaches, and every row
reads the curve of the coordinate it maps back to. So the number of **rows** a
link builds is data. A converter with two flows and a converter with five share
one block:

```yaml
relations:
  generator_of: { key: flow, values: generator }

piecewise:
  coupling:
    along: bp
    dims: [generator, snapshot] # one curve per generator
    links:
      power: { expression: power, values: bp_power, by: generator_of, over: generator, into: flow }
      fuel: [fuel, bp_fuel]
```

`power` is per flow and the curve is per generator, so the `power` link builds
one row for each flow of a generator. A sixth flow is a row in `generator_of`,
not an edit to the model.

The row of a walked link is `dims:` with the dimension that `over:` consumes
replaced by the one that `into:` produces: `[flow, snapshot]` above. The block
writes `at(coupling_lam, by=generator_of, over=generator, into=flow)` into that
row, so the weights stay on `dims:` and the model never names them.

`by:`, `over:` and `into:` are written together. A walk states the relation, the
columns it consumes and the columns it produces, and none is defaulted. A link
whose row is finer than `dims:` is always a walk: a link that names only
`into:` is refused.

A block whose only link walks a relation is a curve. Two links is what a curve
needs when a link is one row; a walked link is one row per fine coordinate, so
the relation supplies the second.

| A walked link |                                                                                                                                                            |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| _over_        | names a column over a dimension of `dims:`                                                                                                                 |
| _into_        | names a column over a dimension that `dims:` does not carry, and that is not `along`                                                                       |
| _values_      | follows the **link's** row: `bp_power` is per flow, not per generator                                                                                      |
| `where:`      | is refused on the block, because the walk replaces the dimension of `dims:` that the mask tests. Mask the link's own variable instead                      |
| `method:`     | `adjacency` or `sos2`. `lp` loses the abscissa its segment line is written against, and `convex` loses the pair of values parameters it reads a shape from |

### Signs

A link with no sign is **pinned** to the curve: its expression equals the
weighted breakpoints. A link carrying `<=` or `>=` is **bounded** by the curve
instead, and each link carries its own.

**At least one link is pinned.** A pinned link fixes the operating point every
other link is read at. With every link bounded the weights are free, and the
block no longer says that its quantities sit together on a curve. It says only
that some point on the curve satisfies the bounds. That is a different model,
so it is refused.

```yaml
piecewise:
  chp:
    along: bp
    dims: [generator, snapshot]
    links:
      power: [power, power_bp] # pinned: it fixes the operating point
      fuel: [fuel, fuel_bp, ">="] # bounded below by the curve
      heat: [heat, heat_bp, "<="] # bounded above, at that same point
```

The typeset line prints this block as the point `(power, fuel, heat)` on the
curve plus `{0} × ℝ≥0 × ℝ≤0`: the pinned coordinate moves by nothing, and each
bounded one by the half-line its sign allows. A block with exactly two links
prints its bounded link as a function of the pinned one instead.

`convex` and `lp` take exactly two links, so there a sign is one link's at
most. Under `adjacency` and `sos2` each link is its own row against the shared
weights, so the count is whatever the model needs.

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

`convex` is a different model. It relaxes the weights onto the hull the
breakpoints span, which is exact only for a curve whose curvature matches the
optimisation pressure. That match is checked against the breakpoint values when
the data binds, and the sign on the bounded link is what names the direction to
check it in. So `convex` takes exactly two links: the rows it builds would serve
any number, but past two there is no single direction left to certify the
relaxation against. It takes no `activity:`.

A bounded link binds from one side, and that side is the part of the hull the
weights are driven onto: `>=` requires a convex curve and `<=` a concave one.
With both links pinned the weights reach the whole hull, so the curve must bend
one way only.

`lp` states the curve as its segment lines. It takes **exactly two links**,
because a line is one quantity against another: one link names the abscissa and
one is bounded by the lines. It takes no `activity:`:

```yaml
piecewise:
  cost_curve:
    along: bp
    dims: [generator]
    method: lp
    links:
      p: [p, bp_x]
      op_cost: [op_cost, bp_y, ">="] # cost bounded below by the curve
```

The bounded link decides the shape, as it does under `convex` above. The two
domain rows hold the pinned link inside the breakpoint range: under a `where:`
that reads the breakpoint dimension, each sits where the mask holds and does
not one breakpoint outward, which is the first and the last breakpoint of each
curve.

## `sos`

An `sos` block declares a **special-ordered set**: one dimension of one
variable, and how many members of that family may be non-zero at once.

```yaml
sos:
  pick_one_size:
    variable: build # the variable the set is over
    along: size # the dimension it runs along — one set per coordinate of the rest
    type: 1 # 1: at most one non-zero; 2: at most two, and consecutive
```

`type: 1` is a choice: at most one member is non-zero. `type: 2` is an
interpolation: at most two members are non-zero, and they are **consecutive**.

A set is over **one** variable, and a variable holds **one** set. A second block
naming the same variable is a load error.

Membership belongs to the variable. Its `where` decides which coordinates exist,
so a masked-out member is not in the set. The order is the declared order of
the `along` dimension.

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
  emits a parameter. A curve of unequal lengths sits its rows on `where:`
  predicates over the mask the file wrote, and the expansion is a file like any
  other: `to_yaml()` writes it, and loading it back changes nothing.
- **`to_program()` writes nothing out.** A model still carrying a curve is
  refused, naming `spec.expand('piecewise')`. A program carries a set, because
  a consumer with the concept takes one; a consumer without it refuses the
  model and names `spec.expand()`.
