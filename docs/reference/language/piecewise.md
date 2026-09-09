<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Piecewise curves and SOS

This page says what `piecewise:` and `sos:` accept and what each expands
into. The first is a curve through breakpoints; the second is a family of
variables of which at most one, or two neighbours, may be nonzero. Both are
shapes affine arithmetic cannot state.

## `piecewise`

N expressions jointly pinned to a breakpoint-indexed piecewise-linear curve.

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

| Part of a link |                                                                                                                                                                              |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| _expression_   | any affine expression — a bare variable name being the simplest                                                                                                              |
| _values_       | a parameter carrying the `over` dim, and any dims the link _expressions_ carry — so curves may vary per generator where the links do, and a dim they do not carry is refused |
| _sign_         | `<=` or `>=`, at most one per block and only with exactly two links: bounds the link instead of pinning it                                                                   |

A block **expands before building** into plain variables and constraints. Three
of the four methods expand through a λ convex combination: weights in `[0,1]`
with a convexity row, and one link row per tuple. That expansion is what the
rest of the model, and the [typeset output](../typeset.md), sees.

**A curve is supplied everywhere it is built.** The expansion emits one weight
per breakpoint over the whole product of its dims and masks none of them. A
values parameter short of a row is refused when data binds; the
[absence rules](absence.md#what-creates-absence) would otherwise read the
missing row as a breakpoint at the origin.

**A gate is a variable, or there is none.** `activity:` names a binary
variable, and the weights sum to it instead of to 1, so `0` pins the curve
off, columns and all. It names a _declaration_ rather than an expression,
because only a declaration says what a masked gate means where it does not
exist:

<!-- doctest: wrap=variables -->

```yaml
running:
  foreach: [snapshot, generator]
  domain: binary
  where: committable # only some units have a commitment decision
```

**Where the gate does not exist, the curve is ungated.** The block emits the
convexity row twice under complementary masks: `== running` where the gate is
and `== 1` where it is not. The second is what a block with no `activity:`
gets.
With `absence: zero` on the gate the single row reads `== 0` there: no curve
rather than an unconditional one. The row is `sum(lam, over=bp) == (activity)`,
and absence [does not spread out of a reduction](absence.md#how-absence-travels),
so an absent right-hand side would take the whole row and leave the weights
unconstrained. The pair of masked rows is what keeps it.

**The breakpoint order is `over`'s index order**: the order its labels are
first written in, which `shift` walks and `position(bp) == 0` names. The `bp`
index is the curve's x-axis, and a values parameter is a lookup against it, so
the order its rows arrive in means nothing. "Strictly increasing breakpoints"
below is increasing _in that order_. An index written backwards makes the curve
run backwards, which is refused.

**`points:` says how far a curve runs** where it has fewer breakpoints than the
dimension holds. Name one of the block's own values parameters and the curve is
as long as its rows:

<!-- doctest: wrap=piecewise -->

```yaml
cost_curve:
  over: bp
  points: bp_x # this curve runs as far as its own breakpoints do
  links:
    - [p, bp_x]
    - [op_cost, bp_y]
```

The other links are still read against the one named, so a row missing from
`bp_y` is refused. Name a **boolean parameter** instead where the length is its
own data: how much of the curve to use, rather than how long it is.

A breakpoint left out declares no weight and no segment binary, and its values
are not asked for. **The marked breakpoints must be consecutive**, though they
need not start at the head of the axis: a curve numbered from 1 is the same
curve one label along. A gap, or a curve with no points at all, is refused when
data binds. The chord row joins a breakpoint to the one before it, and the two
domain rows sit on the curve's own first and last.

Where the _arity_ is data, and one component ties three expressions where
another ties two, the λ formulation is
[written out directly](#when-the-arity-is-data-the-formulation-is-four-declarations)
([#1101](https://github.com/fluxopt/lpspec/issues/1101)).

**`method` is the one thing that varies.** For the three that share the λ
expansion it varies in one place: how the weights are restricted.

| `method`                | What it adds                                                                   |                                                                  |
| ----------------------- | ------------------------------------------------------------------------------ | ---------------------------------------------------------------- |
| `adjacency` _(default)_ | a binary per segment, and `lam <= seg + shift(seg, over=bp, offset=1, edge=0)` | the curve, built                                                 |
| `sos2`                  | an [`sos:`](#sos) block over the same weights                                  | the curve, _said_ — for a solver that branches on the set itself |
| `convex`                | nothing                                                                        | the hull, which is a pure LP                                     |
| `lp`                    | no weights at all — a row per segment line, and two holding the domain         | the curve as its own lines                                       |

`adjacency` and `sos2` state the same restriction and reach the same optimum.
They differ in what the solver is handed, so which is faster is the solver's
property, not the model's.

`convex` is a **different model**: exact only for a curve of matching
curvature under optimisation pressure, which is checked against the breakpoint
_values_ when data binds. It takes exactly two links and no `activity:`.

### `lp`, the one that declares nothing

`lp` states the curve as its **segment lines** instead of interpolating between
its breakpoints, so it declares no auxiliary variable. The other methods carry
one weight per breakpoint per frame row. It needs exactly two links, one of
them bounded (`<=` or `>=`), and no `activity:`, since there are no weights for
a gate to pin.

<!-- doctest: wrap=piecewise -->

```yaml
cost_curve:
  over: bp
  method: lp
  links:
    - [p, bp_x]
    - [op_cost, bp_y, ">="] # cost bounded below by the curve
```

The trade is **columns for rows**: one row per segment plus the two domain
rows, against K weight columns. On a 20-generator, 48-snapshot, 6-breakpoint
dispatch it is 7680 → 1920 columns and 2928 → 6768 rows, at the same optimum
([#926](https://github.com/fluxopt/lpspec/pull/926)).

Two rules follow from stating lines rather than weights:

- **The curvature has to match the sign.** `>=` requires a convex curve and
  `<=` a concave one, checked against the values when data binds. Lines that
  envelope a convex curve _cut_ a concave one, and unchecked the solve would
  come back optimal with a wrong answer. This is stricter than `convex`'s
  check, which only refuses a _mixed_ curve.
- **A line does not stop where its segment does**, so the block emits the two
  domain rows that hold the pinned link inside the breakpoint range. Without
  them the formulation would extrapolate along the end segments.

### When the arity is data, the formulation is four declarations

`links:` is a list, so how many expressions a block ties is written in the file.
Where that number is a property of the system, a boiler tying two flows and a
CHP unit tying three, write the formulation out:

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
  on_the_curve: # one row per flow — this is where the arity goes
    foreach: [flow, time]
    expression: rate == sum(at(weight, by=converter_of) * bp_rate, over=bp)
```

The tie is a _row_, which is what makes the arity data. A converter with a
fourth flow is a row in a table rather than an edit to the model. `sos: type: 2`
is the restriction `method: sos2` emits, and a solver without SOS is handed
binaries and big-M rows for it either way. The block would save only the
weights and the convexity row, so it is not offered
([#1101](https://github.com/fluxopt/lpspec/issues/1101)).

## `sos`

A **special-ordered set**: one dimension of one variable, and how many of that
family may be nonzero at once.

<!-- doctest: wrap=sos -->

```yaml
pick_one_size:
  variable: build # the variable the set is over
  over: size # the dim it runs along — one set per coordinate of the rest
  type: 1 # 1: at most one nonzero; 2: at most two, and consecutive
  big_m: 500 # optional, and only read by a solver that has to reformulate
```

`type: 1` is a **choice**: at most one member of the family is nonzero.
`type: 2` is an **interpolation**: at most two, and those two _consecutive_,
which is the native spelling of a piecewise-linear curve.

**A set is over one variable, and a variable holds one set.** A second block
naming the same variable is a load error.

**Membership is the variable's own.** Its `where` decides which coordinates
exist, so a masked-out member is not in the set. For `type: 2`, consecutive
means consecutive _among the members present_: a masked coordinate leaves no
hole.

**Order is the `over` dimension's declared order**, the order `shift` walks, so
reordering the set means reordering that index. There is no per-set weight to
supply.

### What a solver without SOS does with it

Where the solver has no SOS concept, the set is handed over as binaries and
big-M rows instead. Two consequences reach the model:

- that rewrite is **mixed-integer**, so a set on an otherwise continuous model
  gives up its duals there;
- **M has to be finite**, so every member needs `bounds.upper` or a `big_m:`,
  and a negative `bounds.lower` is refused. `big_m` caps a loose bound: the
  _tighter_ of the two is used.

Both are conditions of the _rewrite_, so a model that fails them still solves
on a solver that takes the set, and the message says so.
