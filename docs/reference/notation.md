<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Every construct, as math

This page shows every construct of the language beside the math that
[the typesetter](typeset.md) prints for it. Use it to find how a construct
prints, or which construct printed a symbol.

Each section shows the YAML of one construct, then its equation. Most fragments
come from one test spec,
[`tests/typesetting/golden/model.yaml`](https://github.com/energy-models/mathspec/blob/main/tests/typesetting/golden/model.yaml),
which holds every construct and is not a sensible spec. The curves come from
the example specs that their section names. What each operator does is on
[Operators](language/operators.md).

The symbols are **derived** from the names in the file, so you see
$\mathrm{load}_{t}$ rather than $\ell_t$. A
[symbol table](typeset.md#symbol-tables) replaces the symbols and changes
nothing else.

<!-- notation:begin -->
### Legend

A dimension, a relation and a parameter declare no equation; what they print is the legend every spec opens with.

```yaml
dimensions:
  snapshot: { dtype: int }
  generator: { dtype: str }
  bus: { dtype: str }
  zone: { dtype: str }
  season: { dtype: str }
  technology: { dtype: str }
  bp: { dtype: int } # the breakpoints every curve below runs through

relations:
  gen_bus: { key: generator, values: bus }
  zone_of: { key: bus, values: zone }
  area_of: { key: bus, values: zone } # a second map into the same set, to compare against
  season_of: { key: snapshot, values: season }
  gen_zone: { key: [generator, snapshot], values: zone } # a map keyed by two dimensions: a call consumes one and joins on the other
  rep_of: { key: snapshot, values: { rep: snapshot } } # a map into its own dimension: the representative snapshot
  connection: { key: [generator, bus] } # a bare relation, with no value columns: many-to-many, read only by sum with both ends named
  gen_bt: { key: generator, values: [bus, technology] } # one table with two value columns, read to both at once

parameters:
  p_max: { dims: [generator] }
  p_min: { dims: [generator] }
  cost: { dims: [generator] }
  load: { dims: [snapshot, bus] }
  is_flexible: { dims: [generator], dtype: bool }
  zone_cap: { dims: [zone] }
  tech_cap: { dims: [bus, technology] }
  min_up: { dims: [generator], dtype: int }
  eta: { dims: [generator] } # a Greek name that is *given*, so the rule wins and it prints as the word
  lead: { dims: [generator], dtype: int }
  budget: { dims: [] } # scalar: the legend says so rather than printing an empty product
  growth: { dims: [] } # the base of a power; the exponent is `lead`, a column
  bp_x: { dims: [generator, bp] } # the x-axis of every curve below, and what a derived mask is read from
  bp_y: { dims: [generator, bp] }
  bp_heat: { dims: [generator, bp] }
  bp_run: { dims: [generator, bp], dtype: bool } # how far each curve runs, so a block has a mask to print
```

#### Sets

| Symbol | Meaning |
|---|---|
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` (`int` coordinates) with $`\mathrm{season\_of}: \mathcal{T} \to \mathcal{S},\ \mathrm{gen\_zone}: \mathcal{G} \times \mathcal{T} \to \mathcal{Z},\ \mathrm{rep\_of}: \mathcal{T} \to \mathcal{T}`$ |
| $`\mathcal{G}`$ | index $`g`$ — `generator` with $`\mathrm{gen\_bus}: \mathcal{G} \to \mathcal{B},\ \mathrm{gen\_zone}: \mathcal{G} \times \mathcal{T} \to \mathcal{Z},\ \mathrm{connection} \subseteq \mathcal{G} \times \mathcal{B},\ \mathrm{gen\_bt}: \mathcal{G} \to \mathcal{B} \times \mathcal{E}`$ |
| $`\mathcal{B}`$ | index $`b`$ — `bus` with $`\mathrm{gen\_bus}: \mathcal{G} \to \mathcal{B},\ \mathrm{zone\_of}: \mathcal{B} \to \mathcal{Z},\ \mathrm{area\_of}: \mathcal{B} \to \mathcal{Z},\ \mathrm{connection} \subseteq \mathcal{G} \times \mathcal{B},\ \mathrm{gen\_bt}: \mathcal{G} \to \mathcal{B} \times \mathcal{E}`$ |
| $`\mathcal{Z}`$ | index $`z`$ — `zone` with $`\mathrm{zone\_of}: \mathcal{B} \to \mathcal{Z},\ \mathrm{area\_of}: \mathcal{B} \to \mathcal{Z},\ \mathrm{gen\_zone}: \mathcal{G} \times \mathcal{T} \to \mathcal{Z}`$ |
| $`\mathcal{S}`$ | index $`s`$ — `season` with $`\mathrm{season\_of}: \mathcal{T} \to \mathcal{S}`$ |
| $`\mathcal{E}`$ | index $`e`$ — `technology` with $`\mathrm{gen\_bt}: \mathcal{G} \to \mathcal{B} \times \mathcal{E}`$ |
| $`\mathcal{A}`$ | index $`a`$ — `bp` |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{p}^{\mathrm{max}}`$ | `p_max` over $`\mathcal{G}`$ |
| $`\mathrm{p}^{\mathrm{min}}`$ | `p_min` over $`\mathcal{G}`$ |
| $`\mathrm{cost}`$ | `cost` over $`\mathcal{G}`$ |
| $`\mathrm{load}`$ | `load` over $`\mathcal{T} \times \mathcal{B}`$ |
| $`\mathrm{is\_flexible}`$ | `is_flexible` over $`\mathcal{G}`$ |
| $`\mathrm{zone\_cap}`$ | `zone_cap` over $`\mathcal{Z}`$ |
| $`\mathrm{tech\_cap}`$ | `tech_cap` over $`\mathcal{B} \times \mathcal{E}`$ |
| $`\mathrm{min\_up}`$ | `min_up` over $`\mathcal{G}`$ |
| $`\mathrm{eta}`$ | `eta` over $`\mathcal{G}`$ |
| $`\mathrm{lead}`$ | `lead` over $`\mathcal{G}`$ |
| $`\mathrm{budget}`$ | `budget` (scalar) |
| $`\mathrm{growth}`$ | `growth` (scalar) |
| $`\mathrm{bp\_x}`$ | `bp_x` over $`\mathcal{G} \times \mathcal{A}`$ |
| $`\mathrm{bp\_y}`$ | `bp_y` over $`\mathcal{G} \times \mathcal{A}`$ |
| $`\mathrm{bp\_heat}`$ | `bp_heat` over $`\mathcal{G} \times \mathcal{A}`$ |
| $`\mathrm{bp\_run}`$ | `bp_run` over $`\mathcal{G} \times \mathcal{A}`$ |

#### Variables

| Symbol | Meaning |
|---|---|
| $`p`$ | `p` over $`\mathcal{T} \times \mathcal{G}`$ |
| $`\mathit{spill}`$ | `spill` over $`\mathcal{T}`$ |
| $`\mathit{slack}`$ | `slack` over $`\mathcal{T}`$ |
| $`\theta`$ | `theta` over $`\mathcal{B}`$ |
| $`\mathit{on}`$ | `on` over $`\mathcal{T} \times \mathcal{G}`$ |
| $`\mathit{units}`$ | `units` over $`\mathcal{G}`$ |
| $`\mathit{spare}`$ | `spare` over $`\mathcal{G}`$ |
| $`\mathit{reserve}`$ | `reserve` (scalar) |
| $`\mathit{headroom}`$ | `headroom` (scalar) |
| $`\mathit{weight}`$ | `weight` over $`\mathcal{T} \times \mathcal{G}`$ |
| $`\mathit{fuel}`$ | `fuel` over $`\mathcal{T} \times \mathcal{G}`$ |
| $`\mathit{heat}`$ | `heat` over $`\mathcal{T} \times \mathcal{G}`$ |
| $`\mathit{op\_cost}`$ | `op_cost` over $`\mathcal{T} \times \mathcal{G}`$ |
| $`\mathit{warm}`$ | `warm` over $`\mathcal{T} \times \mathcal{G}`$ |

#### Given

| Symbol | Meaning |
|---|---|
| $`\mathit{withdrawal}`$ | `withdrawal` over $`\mathcal{T} \times \mathcal{G}`$, an expression this file adds a term to |

#### Definitions

| Symbol | Meaning |
|---|---|
| $`\mathrm{leak}`$ | `leak` over $`\mathcal{G}`$ |
| $`\mathrm{spend}^{\mathrm{cap}}`$ | `spend_cap` over $`\mathcal{G}`$ |
| $`\mathit{spend}`$ | `spend` over $`\mathcal{T}`$ — what a snapshot's dispatch costs |
| $`\mathit{lcoe}`$ | `lcoe` (scalar) |
| $`\mathit{marginal\_price}`$ | `marginal_price` over $`\mathcal{T} \times \mathcal{B}`$ |
| $`\mathrm{startup\_cost}`$ | `startup_cost` over $`\mathcal{T} \times \mathcal{G}`$ — what starting a unit in this snapshot costs, which the horizon's edge changes |

Upright is what the data supplies — a parameter such as $`\mathrm{p}^{\mathrm{max}}`$, a coordinate map, a label — and italic is what the solver chooses, such as $`p`$. An index is italic too, being what a quantifier chooses, and a set is script.

$`t \ominus k`$ denotes cyclic translation: index $`t-k`$ taken modulo the size of the dimension (`roll`). Plain $`t-k`$ (`shift`) has no wraparound — terms translated past the edge are simply absent.

$`t \boxminus_{v} k`$ denotes translation with $`v`$ standing where index $`t-k`$ leaves the dimension (`shift(edge=v)`), so the row at that boundary is built and carries $`v`$ rather than being dropped.

$`t \ominus^{\mathrm{relation}(t)} k`$ denotes a translation counted inside the group a relation puts $`t`$ in (`shift(by=relation)`), so a term never crosses out of its own group. The two modifiers take different slots — the group above, the fill below — so $`t \boxminus_{v}^{\mathrm{relation}(t)} k`$ is both at once.

$`\mathrm{pos}(t)`$ denotes where index $`t`$ sits along its dimension's own order — the order `shift` steps along, not the order labels sort in — counted from $`0`$. The index itself stays the coordinate, so $`t`$ compares against labels and $`\mathrm{pos}(t)`$ against positions.

$`\mathrm{pos}_{\mathrm{relation}(t)}(t)`$ counts within the group a relation puts $`t`$ in: the subscript names the map, $`\mathcal{T}_{\mathrm{relation}(t)}`$ is the group it lands in, and that group has a first position of its own.

$`\lvert \mathcal{T} \rvert`$ denotes the size of the set being counted along, and a position counted from the end prints against it — $`\lvert \mathcal{T} \rvert - 1`$ is the last position, one less than the size because the first is $`0`$.

### Variable domains

#### Lower and upper bounds

both bounds, and a where with all three connectives

```yaml
variables:
  p:
    dims: [snapshot, generator]
    where: "p_max > 0 AND NOT is_flexible OR p_min > 0"
    bounds: { lower: p_min, upper: p_max }
```

```math
\mathrm{p}^{\mathrm{min}}_{g} \le p_{t,g} \le \mathrm{p}^{\mathrm{max}}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{p}^{\mathrm{max}}_{g} > 0 \wedge \neg \mathrm{is\_flexible}_{g} \vee \mathrm{p}^{\mathrm{min}}_{g} > 0
```

#### Lower bound only

```yaml
variables:
  spill:
    dims: [snapshot]
    bounds: { lower: 0 }
```

```math
\mathit{spill}_{t} \ge 0 \qquad \forall\, t \in \mathcal{T}
```

#### Upper bound only

```yaml
variables:
  slack:
    dims: [snapshot]
    bounds: { upper: 100 }
```

```math
\mathit{slack}_{t} \le 100 \qquad \forall\, t \in \mathcal{T}
```

#### Unbounded variable

```yaml
variables:
  theta:
    dims: [bus]
```

```math
\theta_{b} \in \mathbb{R} \qquad \forall\, b \in \mathcal{B}
```

#### Binary domain

a binary domain, which is a set rather than a pair of bounds

```yaml
variables:
  on:
    dims: [snapshot, generator]
    domain: binary
```

```math
\mathit{on}_{t,g} \in \{0, 1\} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Bounded integer domain

an integer domain, which is both: bounds, and where the values live

```yaml
variables:
  units:
    dims: [generator]
    domain: integer
    bounds: { lower: 0, upper: 10 }
```

```math
0 \le \mathit{units}_{g} \le 10, \mathit{units}_{g} \in \mathbb{Z} \qquad \forall\, g \in \mathcal{G}
```

#### Unbounded integer domain

integer with neither bound: the domain is the whole line

```yaml
variables:
  spare:
    dims: [generator]
    domain: integer
```

```math
\mathit{spare}_{g} \in \mathbb{Z} \qquad \forall\, g \in \mathcal{G}
```

#### Scalar variable

an empty dims: a scalar declaration, whose line carries no quantifier

```yaml
variables:
  reserve:
    dims: []
    bounds: { lower: 0 }
```

```math
\mathit{reserve} \ge 0
```

#### Scalar variable with a condition

scalar too, but masked, so the condition stands with no set beside it

```yaml
variables:
  headroom:
    dims: []
    where: "budget"
    bounds: { lower: 0 }
```

```math
\mathit{headroom} \ge 0 \qquad \text{where } \mathrm{budget} \text{ is defined}
```

#### Variable in a special ordered set

the family a sos runs along

```yaml
variables:
  weight:
    dims: [snapshot, generator]
    bounds: { lower: 0, upper: 1 }
```

```math
0 \le \mathit{weight}_{t,g} \le 1 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Second axis of a curve

a curve's second axis

```yaml
variables:
  fuel:
    dims: [snapshot, generator]
    bounds: { lower: 0 }
```

```math
\mathit{fuel}_{t,g} \ge 0 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Third axis of a curve

its third, so one curve ties three expressions

```yaml
variables:
  heat:
    dims: [snapshot, generator]
    bounds: { lower: 0 }
```

```math
\mathit{heat}_{t,g} \ge 0 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Variable bounded by a curve

bounded by a curve rather than pinned to it

```yaml
variables:
  op_cost:
    dims: [snapshot, generator]
    bounds: { lower: 0 }
```

```math
\mathit{op\_cost}_{t,g} \ge 0 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Binary variable with a condition

a gate not every unit has, so the curve it gates is ungated where it does not exist

```yaml
variables:
  warm:
    dims: [snapshot, generator]
    domain: binary
    where: "is_flexible"
```

```math
\mathit{warm}_{t,g} \in \{0, 1\} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{is\_flexible}_{g}
```

### Objective

#### Products and powers in the objective

a sense, a product of two variables, a power over two parameters, a power of one of those, and the summations a scalar objective spells out beside two scalar terms

```yaml
objective:
  sense: maximize
  expression: sum(p * cost) + sum(p * p * cost) + sum(p * cost * growth ** lead) + sum(p * (growth ** lead) ** 2) + sum(p * p_max) - reserve + -headroom
```

```math
\max \sum_{t \in \mathcal{T},\ g \in \mathcal{G}} p_{t,g} \cdot \mathrm{cost}_{g} + \sum_{t \in \mathcal{T},\ g \in \mathcal{G}} p_{t,g} \cdot p_{t,g} \cdot \mathrm{cost}_{g} + \sum_{t \in \mathcal{T},\ g \in \mathcal{G}} p_{t,g} \cdot \mathrm{cost}_{g} \cdot \mathrm{growth}^{\mathrm{lead}_{g}} + \sum_{t \in \mathcal{T},\ g \in \mathcal{G}} p_{t,g} \cdot \left( \mathrm{growth}^{\mathrm{lead}_{g}} \right)^{2} + \sum_{t \in \mathcal{T},\ g \in \mathcal{G}} p_{t,g} \cdot \mathrm{p}^{\mathrm{max}}_{g} - \mathit{reserve} - \mathit{headroom}
```

### Relations

#### Sum through a relation

```yaml
constraints:
  balance:
    dims: [snapshot, bus]
    expression: sum(p, by=gen_bus, over=generator, into=bus) + spill - slack == load
```

```math
\sum_{g \in \mathcal{G} \,:\, \mathrm{gen\_bus}(g) = b} p_{t,g} + \mathit{spill}_{t} - \mathit{slack}_{t} = \mathrm{load}_{t,b} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B}
```

#### Sum over every dimension

a sum naming no dim, whose domain is the one place the dims it took are said

```yaml
constraints:
  total:
    dims: []
    expression: sum(p) <= budget
```

```math
\sum_{t \in \mathcal{T},\ g \in \mathcal{G}} p_{t,g} \le \mathrm{budget}
```

#### `at` through a relation

at(), which re-indexes through a relation instead of an offset

```yaml
constraints:
  pullback:
    dims: [snapshot, bus]
    expression: spill <= at(zone_cap, by=zone_of, over=zone, into=bus)
```

```math
\mathit{spill}_{t} \le \mathrm{zone\_cap}_{\mathrm{zone\_of}(b)} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B}
```

#### Sum into two value columns

one table read to two value columns: the domain carries a condition per column

```yaml
constraints:
  grouped_once:
    dims: [snapshot, bus, technology]
    expression: sum(p, by=gen_bt, into=[bus, technology], over=generator) <= tech_cap
```

```math
\sum_{g \in \mathcal{G} \,:\, \mathrm{gen\_bt.bus}(g) = b \wedge \mathrm{gen\_bt.technology}(g) = e} p_{t,g} \le \mathrm{tech\_cap}_{b,e} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B},\ e \in \mathcal{E}
```

#### `at` through two value columns

its adjoint, reading one slot through two columns of one table

```yaml
constraints:
  pulled_back_once:
    dims: [generator]
    expression: units <= at(tech_cap, by=gen_bt, over=[bus, technology], into=generator)
```

```math
\mathit{units}_{g} \le \mathrm{tech\_cap}_{\mathrm{gen\_bt.bus}(g),\mathrm{gen\_bt.technology}(g)} \qquad \forall\, g \in \mathcal{G}
```

#### Shift within one value column

a partition grouped by one named value column of a two-value table, and a position within both

```yaml
constraints:
  within_bus:
    dims: [generator]
    where: "position(generator, by=gen_bt, within=[bus, technology]) == 0"
    expression: units <= shift(units, along=generator, offset=1, edge=0, by=gen_bt, within=bus)
```

```math
\mathit{units}_{g} \le \mathit{units}_{g \boxminus_{0}^{\mathrm{gen\_bt.bus}(g)} 1} \qquad \forall\, g \in \mathcal{G} \,:\, \mathrm{pos}_{\left( \mathrm{gen\_bt.bus}(g),\ \mathrm{gen\_bt.technology}(g) \right)}(g) = 0
```

#### Sum through a bare relation

a sum through a bare relation: the domain is a row of the relation rather than a function's value

```yaml
constraints:
  relational:
    dims: [snapshot, bus]
    expression: sum(p, by=connection, over=generator, into=bus) <= load
```

```math
\sum_{g \in \mathcal{G} \,:\, \left( g,\ b \right) \in \mathrm{connection}} p_{t,g} \le \mathrm{load}_{t,b} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B}
```

#### Bare relation as a condition

a bare relation as a where: the row of the frame has to be a member of the relation

```yaml
constraints:
  connected:
    dims: [snapshot, generator, bus]
    where: "connection"
    expression: p <= load
```

```math
p_{t,g} \le \mathrm{load}_{t,b} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G},\ b \in \mathcal{B} \,:\, \left( g,\ b \right) \in \mathrm{connection}
```

#### Map into its own dimension

a map into its own dimension, read both ways: the frame is unchanged and the index is primed

```yaml
constraints:
  representative:
    dims: [snapshot]
    expression: sum(spill, by=rep_of, over=snapshot, into=rep) <= at(spill, by=rep_of, over=rep, into=snapshot)
```

```math
\sum_{t' \in \mathcal{T} \,:\, \mathrm{rep\_of}(t') = t} \mathit{spill}_{t'} \le \mathit{spill}_{\mathrm{rep\_of}(t)} \qquad \forall\, t \in \mathcal{T}
```

#### Sum through a two-key map

a grouping through a two-key map, consuming one key: the condition reads the other, and the row keeps it

```yaml
constraints:
  zonal:
    dims: [snapshot, zone]
    expression: sum(p, by=gen_zone, over=generator, into=zone) <= zone_cap
```

```math
\sum_{g \in \mathcal{G} \,:\, \mathrm{gen\_zone}(g,\ t) = z} p_{t,g} \le \mathrm{zone\_cap}_{z} \qquad \forall\, t \in \mathcal{T},\ z \in \mathcal{Z}
```

#### Sum over the other key of a two-key map

the same table consuming its other key

```yaml
constraints:
  zonal_history:
    dims: [generator, zone]
    expression: sum(p, by=gen_zone, over=snapshot, into=zone) <= zone_cap
```

```math
\sum_{t \in \mathcal{T} \,:\, \mathrm{gen\_zone}(g,\ t) = z} p_{t,g} \le \mathrm{zone\_cap}_{z} \qquad \forall\, g \in \mathcal{G},\ z \in \mathcal{Z}
```

#### Sum between the two keys of a map

the same table read between its two key columns: no value column is read, so the domain asks only that the row is there

```yaml
constraints:
  zonal_membership:
    dims: [snapshot]
    expression: sum(units, by=gen_zone, over=generator, into=snapshot) <= budget
```

```math
\sum_{g \in \mathcal{G} \,:\, \mathrm{gen\_zone}(g,\ t) \text{ is defined}} \mathit{units}_{g} \le \mathrm{budget} \qquad \forall\, t \in \mathcal{T}
```

#### `at` through a two-key map

its adjoint, reading the slot the row's own snapshot puts the generator in

```yaml
constraints:
  zonal_pullback:
    dims: [snapshot, generator]
    where: "gen_zone == 'north' AND position(generator, by=gen_zone, within=zone) == 0"
    expression: p <= at(spill * zone_cap, by=gen_zone, into=generator, over=zone)
```

```math
p_{t,g} \le \mathit{spill}_{t} \cdot \mathrm{zone\_cap}_{\mathrm{gen\_zone}(g,\ t)} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{gen\_zone}(g,\ t) = \text{'}\mathrm{north}\text{'} \wedge \mathrm{pos}_{\mathrm{gen\_zone}(g,\ t)}(g) = 0
```

### Arithmetic and literals

#### Signs, division and number literals

division, both unary signs, a sign beside a sign, floats with and without an exponent, bracketing

```yaml
constraints:
  arithmetic:
    dims: [snapshot]
    expression: >-
      sum(p / 2 + -cost - -1e-5 * p + 2.5e-7 * cost + 0.5 * p, over=generator)
      >= -sum(+p, over=generator) * -3
```

```math
\sum_{g \in \mathcal{G}} \left( \frac{p_{t,g}}{2} - \mathrm{cost}_{g} + 10^{-5} \cdot p_{t,g} + 2.5 \times 10^{-7} \cdot \mathrm{cost}_{g} + 0.5 \cdot p_{t,g} \right) \ge -\left( \sum_{g \in \mathcal{G}} p_{t,g} \right) \cdot \left( -3 \right) \qquad \forall\, t \in \mathcal{T}
```

#### Greek parameter name

a Greek-named parameter, which is given — so the convention wins and it prints as the word

```yaml
constraints:
  efficiency:
    dims: [snapshot, generator]
    expression: p <= eta * p_max
```

```math
p_{t,g} \le \mathrm{eta}_{g} \cdot \mathrm{p}^{\mathrm{max}}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Infinity literal

the infinity literal, which is the one way infinity prints

```yaml
constraints:
  ceiling:
    dims: [bus]
    expression: theta <= inf
```

```math
\theta_{b} \le \infty \qquad \forall\, b \in \mathcal{B}
```

### Named expressions

#### Plain expression in a constraint

names the plain expression: its symbol prints here, its definition once below

```yaml
constraints:
  budgeted:
    dims: [snapshot]
    expression: spend <= budget
```

```math
\mathit{spend}_{t} \le \mathrm{budget} \qquad \forall\, t \in \mathcal{T}
```

#### Cased expression in a constraint

names the cased expression: its symbol prints here, its block once below

```yaml
constraints:
  starts:
    dims: [snapshot, generator]
    expression: p <= startup_cost
```

```math
p_{t,g} \le \mathrm{startup\_cost}_{t,g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Plain named expression

a plain named expression: its symbol prints where it is used, its body once as a definition

```yaml
expressions:
  spend:
    expression: sum(p * cost, over=generator)
```

```math
\mathit{spend}_{t} = \sum_{g \in \mathcal{G}} p_{t,g} \cdot \mathrm{cost}_{g} \qquad \forall\, t \in \mathcal{T}
```

#### Expression defined by cases

a quantity defined by region: no two cases overlap, and `otherwise` is the rest

```yaml
expressions:
  startup_cost:
    dims: [snapshot, generator]
    cases:
      opening: { when: "position(snapshot) == 0", expression: cost }
      winter: { when: "position(snapshot) > 0 and season_of == 'winter'", expression: cost * 2 }
    otherwise: 0
```

```math
\mathrm{startup\_cost}_{t,g} = \begin{cases} \mathrm{cost}_{g} & \text{if } \mathrm{pos}(t) = 0 \\ \mathrm{cost}_{g} \cdot 2 & \text{if } \mathrm{pos}(t) > 0 \wedge \mathrm{season\_of}(t) = \text{'}\mathrm{winter}\text{'} \\ 0 & \text{otherwise} \end{cases} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Data-only expression

a data-only entry, so a where may compare it

```yaml
expressions:
  spend_cap: cost * 2
```

```math
\mathrm{spend}^{\mathrm{cap}}_{g} = \mathrm{cost}_{g} \cdot 2 \qquad \forall\, g \in \mathcal{G}
```

#### Named expression in a condition

an expressions: entry on a side, read by the name the file gave it

```yaml
constraints:
  capped:
    dims: [snapshot, generator]
    where: "spend_cap > 0 OR NOT is_flexible"
    expression: p <= p_max
```

```math
p_{t,g} \le \mathrm{p}^{\mathrm{max}}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{spend}^{\mathrm{cap}}_{g} > 0 \vee \neg \mathrm{is\_flexible}_{g}
```

#### Reported expression

nothing in the math reads it, so its divisor may carry a variable

```yaml
expressions:
  lcoe: sum(p * cost) / sum(p)
```

```math
\mathit{lcoe} = \frac{\sum_{t \in \mathcal{T},\ g \in \mathcal{G}} p_{t,g} \cdot \mathrm{cost}_{g}}{\sum_{t \in \mathcal{T},\ g \in \mathcal{G}} p_{t,g}}
```

#### Dual of a constraint

the row dual of a constraint, the one builtin only an entry the math never reads may call

```yaml
expressions:
  marginal_price: dual(balance)
```

```math
\mathit{marginal\_price}_{t,b} = \lambda_{\mathrm{balance},t,b} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B}
```

#### Term a given expression names

the term: an ordinary named expression, which a given expression names

```yaml
expressions:
  leak: -eta
```

```math
\mathrm{leak}_{g} = -\mathrm{eta}_{g} \qquad \forall\, g \in \mathcal{G}
```

### Shifts

#### Cyclic and acyclic shift

roll (cyclic) and shift (acyclic) in one equation

```yaml
constraints:
  ramp:
    dims: [snapshot, generator]
    expression: p - shift(p, along=snapshot, offset=1, edge='wrap') <= shift(p, along=snapshot, offset=1) + p_max
```

```math
p_{t,g} - p_{t \ominus 1,g} \le p_{t - 1,g} + \mathrm{p}^{\mathrm{max}}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Filled and forward shifts

the two translations `ramp` leaves out: a fill, and forwards

```yaml
constraints:
  edges:
    dims: [snapshot, generator]
    expression: >-
      shift(p, along=snapshot, offset=1, edge=0)
      <= shift(p, along=snapshot, offset=-1, edge=0) + p_max
```

```math
p_{t \boxminus_{0} 1,g} \le p_{t \boxplus_{0} 1,g} + \mathrm{p}^{\mathrm{max}}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Cyclic forward shift

the cyclic translation forwards, which is a fourth symbol again

```yaml
constraints:
  ahead:
    dims: [snapshot, generator]
    expression: p <= shift(p, along=snapshot, offset=-1, edge='wrap')
```

```math
p_{t,g} \le p_{t \oplus 1,g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Composed shifts

two steps of one policy are one step; a zero step is none at all

```yaml
constraints:
  composed:
    dims: [snapshot, generator]
    expression: shift(shift(p, along=snapshot, offset=1), along=snapshot, offset=1) <= shift(p_max, along=generator, offset=0)
```

```math
p_{t - 2,g} \le \mathrm{p}^{\mathrm{max}}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Nested shifts that do not compose

a named offset under a numbered one stays two steps, not their sum

```yaml
constraints:
  uncomposed:
    dims: [snapshot, generator]
    expression: shift(shift(p, along=snapshot, offset=lead, edge=0), along=snapshot, offset=1) <= p_max
```

```math
p_{\left( t - 1 \right) \boxminus_{0} \mathrm{lead},g} \le \mathrm{p}^{\mathrm{max}}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Shift along two dimensions

two dimensions translated at one leaf, each with its own policy

```yaml
constraints:
  crossed:
    dims: [snapshot, generator]
    expression: shift(shift(p, along=snapshot, offset=1, edge='wrap'), along=generator, offset=-1) <= p_max
```

```math
p_{t \ominus 1,g + 1} \le \mathrm{p}^{\mathrm{max}}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Shift by a parameter offset

an offset the data carries, so it prints as a symbol rather than a number

```yaml
constraints:
  lead_time:
    dims: [snapshot, generator]
    expression: shift(p, along=snapshot, offset=lead, edge=0) <= p_max
```

```math
p_{t \boxminus_{0} \mathrm{lead},g} \le \mathrm{p}^{\mathrm{max}}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Cyclic shift within a group

a translation partitioned by a relation: the group rides on the operator

```yaml
constraints:
  in_season:
    dims: [snapshot, generator]
    expression: p <= shift(p, along=snapshot, offset=1, edge='wrap', by=season_of, within=season)
```

```math
p_{t,g} \le p_{t \ominus^{\mathrm{season\_of}(t)} 1,g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Filled shift within a group

the same group, with a fill: each season's opening row is kept and given a zero

```yaml
constraints:
  held_in_season:
    dims: [snapshot, generator]
    expression: p <= shift(p, along=snapshot, offset=1, edge=0, by=season_of, within=season)
```

```math
p_{t,g} \le p_{t \boxminus_{0}^{\mathrm{season\_of}(t)} 1,g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

### Trailing windows

#### Window of fixed width

a trailing window of fixed width

```yaml
constraints:
  window:
    dims: [snapshot, generator]
    expression: sum_back(on, along=snapshot, window=3) <= units
```

```math
\sum_{t' \in \mathcal{T} \,:\, 0 \le t - t' < 3} \mathit{on}_{t',g} \le \mathit{units}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Window with a parameter width

the same window, its width in the data and its edge wrapped

```yaml
constraints:
  history:
    dims: [snapshot, generator]
    expression: sum_back(on, along=snapshot, window=min_up, edge='wrap') <= units
```

```math
\sum_{t' \in \mathcal{T} \,:\, 0 \le t \ominus t' < \mathrm{min\_up}} \mathit{on}_{t',g} \le \mathit{units}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Window within a group

a window partitioned by a relation: the group rides on the operator

```yaml
constraints:
  seasonal_window:
    dims: [snapshot, generator]
    expression: sum_back(on, along=snapshot, window=3, by=season_of, within=season) <= units
```

```math
\sum_{t' \in \mathcal{T} \,:\, 0 \le t -^{\mathrm{season\_of}(t)} t' < 3} \mathit{on}_{t',g} \le \mathit{units}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

### Piecewise curves

A curve prints as the curve it states, over the frame the block builds one per coordinate of, and its expansion prints the rows that curve stands for. One row per `method:`, each from the spec named under it, so the symbols in this section are that spec's.

#### Adjacency method

`method: adjacency` — a binary per segment, and a row making the two nonzero weights neighbours, in `examples/ports/transport_pwl.yaml`.

Rendered with the sidecar symbol table `examples/symbols/transport_pwl.yaml`, which is what the breakpoints print as:

```yaml
notation: latex

names:
  economies_of_scale_lam: "\\lambda"
  economies_of_scale_seg: "\\delta"
  bp_x: "\\mathrm{x}"
  bp_y: "\\mathrm{y}"
```

```yaml
piecewise:
  economies_of_scale:
    over: bp
    links:
      - [shipment, bp_x]
      - [scaled, bp_y]
```

```math
\left( \mathit{shipment}_{p,m},\ \mathit{scaled}_{p,m} \right) \in \mathrm{pwl}_{b \in \mathcal{B}}(\mathrm{x}_{b},\ \mathrm{y}_{b}) \qquad \forall\, p \in \mathcal{P},\ m \in \mathcal{M}
```

Written out by `spec.expand()`:

```math
\sum_{b \in \mathcal{B}} \lambda_{p,m,b} = 1 \qquad \forall\, p \in \mathcal{P},\ m \in \mathcal{M}
```

```math
\mathit{shipment}_{p,m} = \sum_{b \in \mathcal{B}} \lambda_{p,m,b} \cdot \mathrm{x}_{b} \qquad \forall\, p \in \mathcal{P},\ m \in \mathcal{M}
```

```math
\mathit{scaled}_{p,m} = \sum_{b \in \mathcal{B}} \lambda_{p,m,b} \cdot \mathrm{y}_{b} \qquad \forall\, p \in \mathcal{P},\ m \in \mathcal{M}
```

```math
\sum_{b \in \mathcal{B}} \delta_{p,m,b} \le 1 \qquad \forall\, p \in \mathcal{P},\ m \in \mathcal{M}
```

```math
\lambda_{p,m,b} \le \delta_{p,m,b} + \delta_{p,m,b \boxminus_{0} 1} \qquad \forall\, p \in \mathcal{P},\ m \in \mathcal{M},\ b \in \mathcal{B}
```

```math
0 \le \lambda_{p,m,b} \le 1 \qquad \forall\, p \in \mathcal{P},\ m \in \mathcal{M},\ b \in \mathcal{B}
```

```math
\delta_{p,m,b} \in \{0, 1\} \qquad \forall\, p \in \mathcal{P},\ m \in \mathcal{M},\ b \in \mathcal{B}
```

```math
\mathrm{x}_{b} \text{ is defined} \wedge \mathrm{y}_{b} \text{ is defined} \qquad \forall\, b \in \mathcal{B}
```

#### SOS2 method

`method: sos2` — the same weights, restricted by a set the solver branches on (the sos rules), in `examples/sos.yaml`.

Rendered with the sidecar symbol table `examples/symbols/sos.yaml`, which is what the breakpoints print as:

```yaml
notation: latex

names:
  cost_curve_lam: "\\lambda"
  bp_x: "\\mathrm{x}"
  bp_y: "\\mathrm{y}"
```

```yaml
piecewise:
  cost_curve:
    over: bp
    links:
      - [dispatch, bp_x]
      - [op_cost, bp_y]
    method: sos2
```

```math
\left( \mathit{dispatch}_{t,g},\ \mathit{op\_cost}_{t,g} \right) \in \mathrm{pwl}_{b \in \mathcal{B}}(\mathrm{x}_{g,b},\ \mathrm{y}_{g,b}) \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

Written out by `spec.expand()`:

```math
\sum_{b \in \mathcal{B}} \lambda_{t,g,b} = 1 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

```math
\mathit{dispatch}_{t,g} = \sum_{b \in \mathcal{B}} \lambda_{t,g,b} \cdot \mathrm{x}_{g,b} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

```math
\mathit{op\_cost}_{t,g} = \sum_{b \in \mathcal{B}} \lambda_{t,g,b} \cdot \mathrm{y}_{g,b} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

```math
0 \le \lambda_{t,g,b} \le 1 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G},\ b \in \mathcal{B}
```

```math
\left( \lambda_{t,g,b} \right)_{b \in \mathcal{B}} \in \mathrm{SOS}2 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

```math
\mathrm{x}_{g,b} \text{ is defined} \wedge \mathrm{y}_{g,b} \text{ is defined} \qquad \forall\, g \in \mathcal{G},\ b \in \mathcal{B}
```

#### Convex method

`method: convex` — nothing — the weights range over the hull, which is a pure LP, in `examples/piecewise.yaml`.

Rendered with the sidecar symbol table `examples/symbols/piecewise.yaml`, which is what the breakpoints print as:

```yaml
notation: latex

names:
  cost_curve_lam: "\\lambda"
  bp_x: "\\mathrm{x}"
  bp_y: "\\mathrm{y}"
```

```yaml
piecewise:
  cost_curve:
    over: bp
    links:
      - [dispatch, bp_x]
      - [op_cost, bp_y]
    method: convex
```

```math
\left( \mathit{dispatch}_{t,g},\ \mathit{op\_cost}_{t,g} \right) \in \mathrm{conv}_{b \in \mathcal{B}}(\mathrm{x}_{g,b},\ \mathrm{y}_{g,b}) \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

Written out by `spec.expand()`:

```math
\sum_{b \in \mathcal{B}} \lambda_{t,g,b} = 1 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

```math
\mathit{dispatch}_{t,g} = \sum_{b \in \mathcal{B}} \lambda_{t,g,b} \cdot \mathrm{x}_{g,b} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

```math
\mathit{op\_cost}_{t,g} = \sum_{b \in \mathcal{B}} \lambda_{t,g,b} \cdot \mathrm{y}_{g,b} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

```math
0 \le \lambda_{t,g,b} \le 1 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G},\ b \in \mathcal{B}
```

```math
\mathrm{x}_{g,b} \text{ is defined} \wedge \mathrm{y}_{g,b} \text{ is defined} \qquad \forall\, g \in \mathcal{G},\ b \in \mathcal{B}
```

```math
\mathrm{x}_{g,b \boxminus_{0} 1} < \mathrm{x}_{g,b} \qquad \forall\, g \in \mathcal{G},\ b \in \mathcal{B} \,:\, \mathrm{pos}(b) > 0
```

```math
\lvert \{ b \in \mathcal{B} \,:\, \left( \mathrm{y}_{g,b} - \mathrm{y}_{g,b \boxminus_{0} 1} \right) \cdot \left( \mathrm{x}_{g,b \boxplus_{0} 1} - \mathrm{x}_{g,b} \right) > \left( \mathrm{y}_{g,b \boxplus_{0} 1} - \mathrm{y}_{g,b} \right) \cdot \left( \mathrm{x}_{g,b} - \mathrm{x}_{g,b \boxminus_{0} 1} \right) \wedge \mathrm{pos}(b) > 0 \wedge \mathrm{pos}(b) \neq \lvert \mathcal{B} \rvert - 1 \} \rvert = 0 \vee \lvert \{ b \in \mathcal{B} \,:\, \left( \mathrm{y}_{g,b} - \mathrm{y}_{g,b \boxminus_{0} 1} \right) \cdot \left( \mathrm{x}_{g,b \boxplus_{0} 1} - \mathrm{x}_{g,b} \right) < \left( \mathrm{y}_{g,b \boxplus_{0} 1} - \mathrm{y}_{g,b} \right) \cdot \left( \mathrm{x}_{g,b} - \mathrm{x}_{g,b \boxminus_{0} 1} \right) \wedge \mathrm{pos}(b) > 0 \wedge \mathrm{pos}(b) \neq \lvert \mathcal{B} \rvert - 1 \} \rvert = 0 \qquad \forall\, g \in \mathcal{G}
```

#### LP method

`method: lp` — no weights at all — one row per segment line, plus the two rows holding the domain, in `examples/piecewise_lp.yaml`.

Rendered with the sidecar symbol table `examples/symbols/piecewise_lp.yaml`, which is what the breakpoints print as:

```yaml
notation: latex

names:
  bp_x: "\\mathrm{x}"
  bp_y: "\\mathrm{y}"
```

```yaml
piecewise:
  cost_curve:
    over: bp
    links:
      - [dispatch, bp_x]
      - [op_cost, bp_y, ">="]
    method: lp
```

```math
\mathit{op\_cost}_{t,g} \ge \mathrm{pwl}_{b \in \mathcal{B}}(\mathrm{x}_{g,b},\ \mathrm{y}_{g,b})(\mathit{dispatch}_{t,g}) \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

Written out by `spec.expand()`:

```math
\mathit{op\_cost}_{t,g} \cdot \left( \mathrm{x}_{g,b} - \mathrm{x}_{g,b \boxminus_{0} 1} \right) \ge \left( \mathrm{y}_{g,b} - \mathrm{y}_{g,b \boxminus_{0} 1} \right) \cdot \left( \mathit{dispatch}_{t,g} - \mathrm{x}_{g,b} \right) + \mathrm{y}_{g,b} \cdot \left( \mathrm{x}_{g,b} - \mathrm{x}_{g,b \boxminus_{0} 1} \right) \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G},\ b \in \mathcal{B} \,:\, \mathrm{pos}(b) > 0
```

```math
\mathit{dispatch}_{t,g} \ge \mathrm{x}_{g,b} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G},\ b \in \mathcal{B} \,:\, \mathrm{pos}(b) = 0
```

```math
\mathit{dispatch}_{t,g} \le \mathrm{x}_{g,b} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G},\ b \in \mathcal{B} \,:\, \mathrm{pos}(b) = \lvert \mathcal{B} \rvert - 1
```

```math
\mathrm{x}_{g,b} \text{ is defined} \wedge \mathrm{y}_{g,b} \text{ is defined} \qquad \forall\, g \in \mathcal{G},\ b \in \mathcal{B}
```

```math
\mathrm{x}_{g,b \boxminus_{0} 1} < \mathrm{x}_{g,b} \qquad \forall\, g \in \mathcal{G},\ b \in \mathcal{B} \,:\, \mathrm{pos}(b) > 0
```

```math
\left( \mathrm{y}_{g,b} - \mathrm{y}_{g,b \boxminus_{0} 1} \right) \cdot \left( \mathrm{x}_{g,b \boxplus_{0} 1} - \mathrm{x}_{g,b} \right) \le \left( \mathrm{y}_{g,b \boxplus_{0} 1} - \mathrm{y}_{g,b} \right) \cdot \left( \mathrm{x}_{g,b} - \mathrm{x}_{g,b \boxminus_{0} 1} \right) \qquad \forall\, g \in \mathcal{G},\ b \in \mathcal{B} \,:\, \mathrm{pos}(b) > 0 \wedge \mathrm{pos}(b) \neq \lvert \mathcal{B} \rvert - 1
```

```math
\lvert \{ b \in \mathcal{B} \,:\, \mathrm{x}_{g,b} \text{ is defined} \} \rvert \ge 2 \qquad \forall\, g \in \mathcal{G}
```

### Special ordered sets

A set prints beside the variable it restricts, because it restricts that variable rather than adding a row of its own. Under it are the rows it is written out as.

#### Special ordered set of type 2

at most two adjacent members nonzero, one set per snapshot

```yaml
sos:
  adjacent:
    variable: weight
    along: generator
    type: 2
```

```math
\left( \mathit{weight}_{t,g} \right)_{g \in \mathcal{G}} \in \mathrm{SOS}2 \qquad \forall\, t \in \mathcal{T}
```

Written out by `spec.expand()`:

```math
\sum_{g \in \mathcal{G}} \mathit{adjacent\_seg}_{t,g} \le 1 \qquad \forall\, t \in \mathcal{T}
```

```math
\mathit{weight}_{t,g} \le \mathit{adjacent\_seg}_{t,g} + \mathit{adjacent\_seg}_{t,g \boxminus_{0} 1} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

```math
\mathit{adjacent\_seg}_{t,g} \in \{0, 1\} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

### Assumptions

#### Two parameters compared

two parameters, which is arithmetic like any other

```yaml
assumptions:
  bounds_do_not_cross: "p_min <= p_max"
```

```math
\mathrm{p}^{\mathrm{min}}_{g} \le \mathrm{p}^{\mathrm{max}}_{g} \qquad \forall\, g \in \mathcal{G}
```

#### Connective in an assumption

a connective, so the line has no relation to align on

```yaml
assumptions:
  efficiency_is_a_fraction: "eta > 0 AND eta <= 1"
```

```math
\mathrm{eta}_{g} > 0 \wedge \mathrm{eta}_{g} \le 1 \qquad \forall\, g \in \mathcal{G}
```

#### Parameter compared to a literal

one parameter against a literal

```yaml
assumptions:
  lead_times_are_short: "lead <= 3"
```

```math
\mathrm{lead}_{g} \le 3 \qquad \forall\, g \in \mathcal{G}
```

#### Two relations compared

two maps into one set, compared row by row

```yaml
assumptions:
  zones_agree: "zone_of == area_of"
```

```math
\mathrm{zone\_of}(b) = \mathrm{area\_of}(b) \qquad \forall\, b \in \mathcal{B}
```

#### Reduction in an assumption

a reduction on a side, leaving nothing to quantify

```yaml
assumptions:
  budget_covers_the_peak: "sum(p_max, over=generator) >= budget"
```

```math
\sum_{g \in \mathcal{G}} \mathrm{p}^{\mathrm{max}}_{g} \ge \mathrm{budget}
```

#### Shift in an assumption

a translation inside arithmetic, and a position keeping the vacated row out

```yaml
assumptions:
  ramps_are_gentle:
    holds: "load - shift(load, along=snapshot, offset=1, edge=0) <= budget"
    where: "position(snapshot) > 0"
```

```math
\mathrm{load}_{t,b} - \mathrm{load}_{t \boxminus_{0} 1,b} \le \mathrm{budget} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B} \,:\, \mathrm{pos}(t) > 0
```

#### Assumption with a boolean condition

a bare bool parameter as the where

```yaml
assumptions:
  flexible_units_have_headroom:
    holds: "p_min < p_max"
    where: "is_flexible"
```

```math
\mathrm{p}^{\mathrm{min}}_{g} < \mathrm{p}^{\mathrm{max}}_{g} \qquad \forall\, g \in \mathcal{G} \,:\, \mathrm{is\_flexible}_{g}
```

#### Assumption with a relation condition

a relation comparison as the where, over a frame two dims wide

```yaml
assumptions:
  northern_demand_is_real:
    holds: "load >= 0"
    where: "zone_of == 'north'"
```

```math
\mathrm{load}_{t,b} \ge 0 \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B} \,:\, \mathrm{zone\_of}(b) = \text{'}\mathrm{north}\text{'}
```

### Where conditions

#### Parameter as a condition

a parameter over nothing, and a mask that is a bare parameter

```yaml
constraints:
  scalar:
    dims: [generator]
    where: "cost"
    expression: units <= budget
```

```math
\mathit{units}_{g} \le \mathrm{budget} \qquad \forall\, g \in \mathcal{G} \,:\, \mathrm{cost}_{g} \text{ is defined}
```

#### Variable and label conditions

a mask on a variable's existence, and one on a dimension's label

```yaml
constraints:
  running:
    dims: [snapshot, bus]
    where: "theta AND snapshot >= 3"
    expression: theta <= load
```

```math
\theta_{b} \le \mathrm{load}_{t,b} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B} \,:\, \theta_{b} \text{ exists} \wedge t \ge 3
```

#### Position in a dimension

a position in a dimension, and the same position within a group

```yaml
constraints:
  first:
    dims: [snapshot, generator]
    where: "position(snapshot) == 0 OR position(snapshot, by=season_of, within=season) == 0"
    expression: on == 1
```

```math
\mathit{on}_{t,g} = 1 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{pos}(t) = 0 \vee \mathrm{pos}_{\mathrm{season\_of}(t)}(t) = 0
```

#### Position counted from the end

the same two counted from the end, which print against a size rather than as themselves

```yaml
constraints:
  last:
    dims: [snapshot, generator]
    where: "position(snapshot) == -1 OR position(snapshot, by=season_of, within=season) == -1"
    expression: on == 0
```

```math
\mathit{on}_{t,g} = 0 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{pos}(t) = \lvert \mathcal{T} \rvert - 1 \vee \mathrm{pos}_{\mathrm{season\_of}(t)}(t) = \lvert \mathcal{T}_{\mathrm{season\_of}(t)} \rvert - 1
```

#### Relation compared to a label

a relation compared to a label, to another relation, and to nothing

```yaml
constraints:
  northern:
    dims: [snapshot, bus]
    where: "zone_of == 'north' AND zone_of != area_of AND zone_of"
    expression: slack <= load
```

```math
\mathit{slack}_{t} \le \mathrm{load}_{t,b} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B} \,:\, \mathrm{zone\_of}(b) = \text{'}\mathrm{north}\text{'} \wedge \mathrm{zone\_of}(b) \neq \mathrm{area\_of}(b) \wedge \mathrm{zone\_of}(b) \text{ is defined}
```

#### Constant true condition

a mask that is only the constant true, which the language says is no mask at all — so none prints

```yaml
constraints:
  always:
    dims: [snapshot]
    where: "true"
    expression: spill >= 0
```

```math
\mathit{spill}_{t} \ge 0 \qquad \forall\, t \in \mathcal{T}
```

#### Constant true inside a condition

the same constant *inside* a mask, where it is what the file says and prints

```yaml
constraints:
  redundant:
    dims: [snapshot]
    where: "True AND spill"
    expression: spill >= 0
```

```math
\mathit{spill}_{t} \ge 0 \qquad \forall\, t \in \mathcal{T} \,:\, \mathit{spill}_{t} \text{ exists}
```

#### Constant false condition

the other constant mask, which says the rows are none and is worth seeing

```yaml
constraints:
  never:
    dims: [snapshot]
    where: "false"
    expression: slack >= 0
```

```math
\mathit{slack}_{t} \ge 0 \qquad \forall\, t \in \mathcal{T} \,:\, \bot
```

#### Comparison of two expressions

a mask comparing two expressions, which prints as the arithmetic it is

```yaml
constraints:
  margin:
    dims: [snapshot, generator]
    where: "p_max - p_min > cost / 2"
    expression: p <= p_max
```

```math
p_{t,g} \le \mathrm{p}^{\mathrm{max}}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{p}^{\mathrm{max}}_{g} - \mathrm{p}^{\mathrm{min}}_{g} > \frac{\mathrm{cost}_{g}}{2}
```

#### Shift and pullback in a condition

a translation under a comparison names its edge, a pullback reads through a relation, and the position keeps the vacated row out

```yaml
constraints:
  ramped:
    dims: [snapshot, bus]
    where: "load - shift(load, along=snapshot, offset=1, edge=0) <= at(zone_cap, by=zone_of, over=zone, into=bus) AND position(snapshot) > 0"
    expression: slack <= load
```

```math
\mathit{slack}_{t} \le \mathrm{load}_{t,b} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B} \,:\, \mathrm{load}_{t,b} - \mathrm{load}_{t \boxminus_{0} 1,b} \le \mathrm{zone\_cap}_{\mathrm{zone\_of}(b)} \wedge \mathrm{pos}(t) > 0
```

#### Reduction in a scalar condition

a reduction on a side of a scalar mask, so nothing is left to quantify

```yaml
constraints:
  covered:
    dims: []
    where: "sum(p_max, over=generator) >= budget"
    expression: sum(p) <= budget
```

```math
\sum_{t \in \mathcal{T},\ g \in \mathcal{G}} p_{t,g} \le \mathrm{budget} \qquad \text{where } \sum_{g \in \mathcal{G}} \mathrm{p}^{\mathrm{max}}_{g} \ge \mathrm{budget}
```

#### Count over a dimension

a count of the coordinates a predicate admits, which reduces one dim away

```yaml
constraints:
  counted:
    dims: [bus]
    where: "count(tech_cap > 0, over=technology) >= 2"
    expression: theta <= budget
```

```math
\theta_{b} \le \mathrm{budget} \qquad \forall\, b \in \mathcal{B} \,:\, \lvert \{ e \in \mathcal{E} \,:\, \mathrm{tech\_cap}_{b,e} > 0 \} \rvert \ge 2
```

#### Count along a dimension of the frame

the same count along a dim the frame carries, so the set takes a primed dummy

```yaml
constraints:
  counted_here:
    dims: [bus, technology]
    where: "count(tech_cap > 0, over=technology) >= 2"
    expression: theta <= tech_cap
```

```math
\theta_{b} \le \mathrm{tech\_cap}_{b,e} \qquad \forall\, b \in \mathcal{B},\ e \in \mathcal{E} \,:\, \lvert \{ e' \in \mathcal{E} \,:\, \mathrm{tech\_cap}_{b,e'} > 0 \} \rvert \ge 2
```

#### Predicate at the previous coordinate

a predicate read one coordinate back, which is false where the translation vacates

```yaml
constraints:
  run_start:
    dims: [snapshot, bus]
    where: "load AND NOT shift(load, along=snapshot, offset=1)"
    expression: slack <= load
```

```math
\mathit{slack}_{t} \le \mathrm{load}_{t,b} \qquad \forall\, t \in \mathcal{T},\ b \in \mathcal{B} \,:\, \mathrm{load}_{t,b} \text{ is defined} \wedge \neg \left( \mathrm{load}_{t - 1,b} \text{ is defined} \right)
```

#### Predicate through a relation

a predicate read through a relation: a bus is held only where its zone has a cap at all

```yaml
constraints:
  zoned:
    dims: [bus]
    where: "at(zone_cap, by=zone_of, over=zone, into=bus)"
    expression: theta <= budget
```

```math
\theta_{b} \le \mathrm{budget} \qquad \forall\, b \in \mathcal{B} \,:\, \mathrm{zone\_cap}_{\mathrm{zone\_of}(b)} \text{ is defined}
```
<!-- notation:end -->
