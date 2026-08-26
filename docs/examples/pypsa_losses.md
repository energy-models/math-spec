<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# PyPSA, the lossy lines

Rung 13 of [PyPSA in one file](pypsa.md): `n.optimize(transmission_losses={'mode': 'tangents', 'segments': K})`, stated on rung 6's lines in a
file of its own — the model's description below says why. Its network is the spine plus the script's own additions.

## Rung 13 — transmission losses

| PyPSA | status | note |
| --- | --- | --- |
| [`Line-loss`](#variable-domains) | done | |
| [`Line-fix-s-*`, `Line-ext-s-*`](#line-fix-s-lower) | done | the loss counted against the rating |
| [`Bus-nodal_balance`](#bus-nodal_balance) | done | half of each incident line's loss at either end |
| [`Line-loss_upper`](#line-loss_upper) | done | `loss_max` is data prep |
| [`Line-loss_tangents-{k}-1`](#line-loss_tangents-k-1) | split | PyPSA names a row per segment; one block over the dimension |
| [`Line-loss_tangents-{k}--1`](#line-loss_tangents-k--1) | split | |
| `Line-loss_secants-*` | out | the secant mode solves for its segment count |

<!-- reference:rung_13_losses:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `10645.51008773467`, 150 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_13_losses.py`

```python
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 13: transmission losses in tangent form — a loss per line, stated by `pypsa_losses.yaml`."""

from __future__ import annotations

import spine

MODEL = 'pypsa_losses.yaml'
OPTIMIZE = {'transmission_losses': {'mode': 'tangents', 'segments': 2}}


def build():
    """The spine plus a lossy triangle of lines, one of them extendable; resistances small enough at 1 kV to keep the loss below the flow."""
    n = spine.build()
    n.add('Bus', ['a', 'b', 'c'])
    n.add('Generator', 'hydro13', bus='a', p_nom=80, marginal_cost=10)
    n.add('Generator', 'diesel13', bus='b', p_nom=80, marginal_cost=50)
    n.add('Line', 'ab13', bus0='a', bus1='b', carrier='AC', x=0.1, r=0.0005, s_nom=60)
    n.add('Line', 'bc13', bus0='b', bus1='c', carrier='AC', x=0.2, r=0.0008, s_nom=60)
    n.add(
        'Line',
        'ca13',
        bus0='c',
        bus1='a',
        carrier='AC',
        x=0.15,
        r=0.0005,
        s_nom=40,
        s_nom_extendable=True,
        s_nom_max=90,
        capital_cost=4,
    )
    n.add('Load', 'town13', bus='c', p_set=[35, 55, 15, 45])
    return n
```

</details>
<!-- reference:rung_13_losses:end -->

## The file

<!-- gallery:begin -->
The lossy class of a plain `n.optimize()`: `transmission_losses` in its tangent form, stated on rung 6's lines in a file of its own. A line dissipates a loss its flow buys along a fan of tangents to the quadratic curve, half at either end — a variable and rows the keyword adds, which no `where:` can add to `examples/pypsa.yaml`. The fan's slopes and offsets are data prep, one per segment.

#### Sets

| Symbol | Meaning |
|---|---|
| $\mathcal{T}$ | index $t$ — `snapshot` — dispatch periods |
| $\mathcal{N}$ | index $n$ — `bus` — network nodes |
| $\mathcal{G}$ | index $g$ — `generator` with $\mathrm{Generator\_bus}: \mathcal{G} \to \mathcal{N}$ — generating units, each on one bus |
| $\mathcal{L}$ | index $l$ — `link` with $\mathrm{Link\_bus0}: \mathcal{L} \to \mathcal{N},\enspace \mathrm{Link\_bus1}: \mathcal{L} \to \mathcal{N}$ — controllable connections, each from one bus to another |
| $\mathcal{K}$ | index $k$ — `line` with $\mathrm{Line\_bus0}: \mathcal{K} \to \mathcal{N},\enspace \mathrm{Line\_bus1}: \mathcal{K} \to \mathcal{N}$ — passive branches, each between two buses, their flow set by impedance |
| $\mathcal{C}$ | index $c$ — `cycle` — independent cycles of the passive network graph — the cycle basis, data prep |
| $\mathcal{K}$ | index $k$ — `segment` — the tangents the loss curve is approximated by, PyPSA's `segments` |
| $\mathcal{D}$ | index $d$ — `load` with $\mathrm{Load\_bus}: \mathcal{D} \to \mathcal{N}$ — demands, each on one bus |

#### Parameters

| Symbol | Meaning |
|---|---|
| $\mathrm{w}$ | `snapshot_weightings_objective` over $\mathcal{T}$ — PyPSA's `snapshot_weightings.objective` — hours a snapshot stands for in the cost |
| $\mathrm{p}^{\mathrm{nom}}$ | `Generator_p_nom` over $\mathcal{G}$ — nominal power |
| $\underline{\mathrm{p}}$ | `Generator_p_min_pu` over $\mathcal{T} \times \mathcal{G}$ — least output, per unit of nominal power |
| $\overline{\mathrm{p}}$ | `Generator_p_max_pu` over $\mathcal{T} \times \mathcal{G}$ — most output, per unit of nominal power — an availability profile |
| $\mathrm{c}$ | `Generator_marginal_cost` over $\mathcal{T} \times \mathcal{G}$ — cost of one unit of output |
| $\mathrm{s}^{\mathrm{nom}}$ | `Line_s_nom` over $\mathcal{K}$ — nominal apparent power |
| $\mathrm{ext}^{s}$ | `Line_s_nom_extendable` over $\mathcal{K}$ — whether the nominal apparent power is a decision |
| $\overline{\mathrm{s}}$ | `Line_s_max_pu` over $\mathcal{T} \times \mathcal{K}$ — most flow either way, per unit of nominal apparent power |
| $\underline{\mathrm{s}}^{\mathrm{nom}}$ | `Line_s_nom_min` over $\mathcal{K}$ — least nominal apparent power an extendable line may be built at |
| $\overline{\mathrm{s}}^{\mathrm{nom}}$ | `Line_s_nom_max` over $\mathcal{K}$ — most nominal apparent power an extendable line may be built at |
| $\mathrm{c}^{\mathrm{cap},s}$ | `Line_capital_cost` over $\mathcal{K}$ — cost of one unit of nominal apparent power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $\mathrm{x}$ | `Line_cycle_weight` over $\mathcal{K} \times \mathcal{C}$ — the line's series impedance, signed by its orientation in the cycle — the cycle basis, data prep; a line in no cycle has no row |
| $\overline{\ell}$ | `Line_loss_max` over $\mathcal{T} \times \mathcal{K}$ — the loss at a line's rating — PyPSA's `r_pu_eff * (s_max_pu * s_nom_max)**2`, data prep |
| $\mathrm{a}$ | `Line_loss_slope` over $\mathcal{T} \times \mathcal{K} \times \mathcal{K}$ — the slope of a tangent to the loss curve at its segment's flow — `2 * r_pu_eff * p_k`, data prep |
| $\mathrm{b}$ | `Line_loss_offset` over $\mathcal{T} \times \mathcal{K} \times \mathcal{K}$ — where that tangent meets the loss axis — `loss_k - slope_k * p_k`, negative, data prep |
| $\mathrm{f}^{\mathrm{nom}}$ | `Link_p_nom` over $\mathcal{L}$ — nominal power |
| $\underline{\mathrm{f}}$ | `Link_p_min_pu` over $\mathcal{T} \times \mathcal{L}$ — least flow, per unit of nominal power — negative for a link that carries both ways |
| $\overline{\mathrm{f}}$ | `Link_p_max_pu` over $\mathcal{T} \times \mathcal{L}$ — most flow, per unit of nominal power |
| $\eta$ | `Link_efficiency` over $\mathcal{L}$ — share of the flow that arrives at the link's `Link_bus1` end |
| $\mathrm{c}^{f}$ | `Link_marginal_cost` over $\mathcal{T} \times \mathcal{L}$ — cost of one unit of flow |
| $\mathrm{load}$ | `Load_p_set` over $\mathcal{T} \times \mathcal{D}$ — demand |

#### Variables

| Symbol | Meaning |
|---|---|
| $p$ | `Generator_p` over $\mathcal{T} \times \mathcal{G}$ — `Generator-p` — output of a generator in a snapshot |
| $s$ | `Line_s` over $\mathcal{T} \times \mathcal{K}$ — `Line-s` — PyPSA's `p0`, the flow measured at the `Line_bus0` end: a positive value withdraws there and injects at `Line_bus1` |
| $S$ | `Line_s_nom_ext` over $\mathcal{K}$ — `Line-s_nom` — nominal apparent power where it is a decision; the parameter of the same PyPSA name carries the fixed regime |
| $f$ | `Link_p` over $\mathcal{T} \times \mathcal{L}$ — `Link-p` — PyPSA's `p0`, the flow measured at the `Link_bus0` end: a positive value withdraws there and injects at `Link_bus1` |
| $\ell$ | `Line_loss` over $\mathcal{T} \times \mathcal{K}$ — `Line-loss` — what a line dissipates carrying its flow, pushed down by the cost and held up by the tangents |

### Objective

```yaml
objective:
  sense: minimize
  description: operating cost by weighted snapshot, plus what the lines cost to build
  expression: >-
    sum(Generator_p * Generator_marginal_cost * snapshot_weightings_objective)
    + sum(Link_p * Link_marginal_cost * snapshot_weightings_objective)
    + sum(Line_s_nom_ext * Line_capital_cost)
```

$$\min \sum_{t \in \mathcal{T},\enspace g \in \mathcal{G}} p_{t,g} \cdot \mathrm{c}_{t,g} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\enspace l \in \mathcal{L}} f_{t,l} \cdot \mathrm{c}^{f}_{t,l} \cdot \mathrm{w}_{t} + \sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{c}^{\mathrm{cap},s}_{k}$$

### `Generator-fix-p-lower`

`Generator_fix_p_lower`

```yaml
Generator_fix_p_lower:
  description: "`Generator-fix-p-lower` — a generator outputs at least its minimum"
  foreach: [snapshot, generator]
  expression: Generator_p >= Generator_p_min_pu * Generator_p_nom
```

$$p_{t,g} \ge \underline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G}$$

### `Generator-fix-p-upper`

`Generator_fix_p_upper`

```yaml
Generator_fix_p_upper:
  description: "`Generator-fix-p-upper` — a generator outputs at most what is available"
  foreach: [snapshot, generator]
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom
```

$$p_{t,g} \le \overline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G}$$

### `Link-fix-p-lower`

`Link_fix_p_lower`

```yaml
Link_fix_p_lower:
  description: "`Link-fix-p-lower` — a link carries at least its minimum, negative for the other way"
  foreach: [snapshot, link]
  expression: Link_p >= Link_p_min_pu * Link_p_nom
```

$$f_{t,l} \ge \underline{\mathrm{f}}_{t,l} \cdot \mathrm{f}^{\mathrm{nom}}_{l} \qquad \forall\thinspace t \in \mathcal{T},\enspace l \in \mathcal{L}$$

### `Link-fix-p-upper`

`Link_fix_p_upper`

```yaml
Link_fix_p_upper:
  description: "`Link-fix-p-upper` — a link carries at most its nominal power"
  foreach: [snapshot, link]
  expression: Link_p <= Link_p_max_pu * Link_p_nom
```

$$f_{t,l} \le \overline{\mathrm{f}}_{t,l} \cdot \mathrm{f}^{\mathrm{nom}}_{l} \qquad \forall\thinspace t \in \mathcal{T},\enspace l \in \mathcal{L}$$

### `Line-fix-s-lower`

`Line_fix_s_lower`

```yaml
Line_fix_s_lower:
  description: "`Line-fix-s-lower` — a fixed line carries at least the negative of its rating, the loss counted against it"
  foreach: [snapshot, line]
  where: not Line_s_nom_extendable
  expression: Line_s - Line_loss >= -Line_s_max_pu * Line_s_nom
```

$$s_{t,k} - \ell_{t,k} \ge -\overline{\mathrm{s}}_{t,k} \cdot \mathrm{s}^{\mathrm{nom}}_{k} \qquad \forall\thinspace t \in \mathcal{T},\enspace k \in \mathcal{K} \thinspace:\thinspace \neg \mathrm{ext}^{s}_{k}$$

### `Line-fix-s-upper`

`Line_fix_s_upper`

```yaml
Line_fix_s_upper:
  description: "`Line-fix-s-upper` — a fixed line carries at most its rating, loss included"
  foreach: [snapshot, line]
  where: not Line_s_nom_extendable
  expression: Line_s + Line_loss <= Line_s_max_pu * Line_s_nom
```

$$s_{t,k} + \ell_{t,k} \le \overline{\mathrm{s}}_{t,k} \cdot \mathrm{s}^{\mathrm{nom}}_{k} \qquad \forall\thinspace t \in \mathcal{T},\enspace k \in \mathcal{K} \thinspace:\thinspace \neg \mathrm{ext}^{s}_{k}$$

### `Line-ext-s-lower`

`Line_ext_s_lower`

```yaml
Line_ext_s_lower:
  description: "`Line-ext-s-lower` — an extendable line carries at least the negative of its rating of the chosen build"
  foreach: [snapshot, line]
  where: Line_s_nom_extendable
  expression: Line_s - Line_loss >= -Line_s_max_pu * Line_s_nom_ext
```

$$s_{t,k} - \ell_{t,k} \ge -\overline{\mathrm{s}}_{t,k} \cdot S_{k} \qquad \forall\thinspace t \in \mathcal{T},\enspace k \in \mathcal{K} \thinspace:\thinspace \mathrm{ext}^{s}_{k}$$

### `Line-ext-s-upper`

`Line_ext_s_upper`

```yaml
Line_ext_s_upper:
  description: "`Line-ext-s-upper` — an extendable line carries at most its rating of the chosen build"
  foreach: [snapshot, line]
  where: Line_s_nom_extendable
  expression: Line_s + Line_loss <= Line_s_max_pu * Line_s_nom_ext
```

$$s_{t,k} + \ell_{t,k} \le \overline{\mathrm{s}}_{t,k} \cdot S_{k} \qquad \forall\thinspace t \in \mathcal{T},\enspace k \in \mathcal{K} \thinspace:\thinspace \mathrm{ext}^{s}_{k}$$

### `Line-ext-s_nom-lower`

`Line_ext_s_nom_lower`

```yaml
Line_ext_s_nom_lower:
  description: "`Line-ext-s_nom-lower` — the chosen build is at least its floor"
  foreach: [line]
  where: Line_s_nom_extendable
  expression: Line_s_nom_ext >= Line_s_nom_min
```

$$S_{k} \ge \underline{\mathrm{s}}^{\mathrm{nom}}_{k} \qquad \forall\thinspace k \in \mathcal{K} \thinspace:\thinspace \mathrm{ext}^{s}_{k}$$

### `Line-ext-s_nom-upper`

`Line_ext_s_nom_upper`

```yaml
Line_ext_s_nom_upper:
  description: "`Line-ext-s_nom-upper` — the chosen build is at most its cap; a cap of infinity is no row"
  foreach: [line]
  where: Line_s_nom_extendable AND Line_s_nom_max
  expression: Line_s_nom_ext <= Line_s_nom_max
```

$$S_{k} \le \overline{\mathrm{s}}^{\mathrm{nom}}_{k} \qquad \forall\thinspace k \in \mathcal{K} \thinspace:\thinspace \mathrm{ext}^{s}_{k} \wedge \overline{\mathrm{s}}^{\mathrm{nom}}_{k} \text{ is defined}$$

### `Kirchhoff-Voltage-Law`

`Kirchhoff_Voltage_Law`

```yaml
Kirchhoff_Voltage_Law:
  description: >-
    `Kirchhoff-Voltage-Law` — around every independent cycle the
    impedance-weighted flows sum to nothing, which is what makes the linear
    power flow physical rather than transport
  foreach: [snapshot, cycle]
  expression: sum(Line_s * Line_cycle_weight, over=line) == 0
```

$$\sum_{k \in \mathcal{K}} s_{t,k} \cdot \mathrm{x}_{k,c} = 0 \qquad \forall\thinspace t \in \mathcal{T},\enspace c \in \mathcal{C}$$

### `Bus-nodal_balance`

`Bus_nodal_balance`

```yaml
Bus_nodal_balance:
  description: >-
    `Bus-nodal_balance` — what is generated at a bus, plus what the links and
    lines bring, meets the load there, less half of every incident line's
    loss — PyPSA dissipates a branch's loss half at either end
  foreach: [snapshot, bus]
  expression: >-
    sum(Generator_p, by=Generator_bus)
    - sum(Link_p, by=Link_bus0)
    + sum(Link_p * Link_efficiency, by=Link_bus1)
    - sum(Line_s, by=Line_bus0)
    + sum(Line_s, by=Line_bus1)
    - 0.5 * sum(Line_loss, by=Line_bus0)
    - 0.5 * sum(Line_loss, by=Line_bus1)
    == sum(Load_p_set, by=Load_bus)
```

$$\sum_{g \in \mathcal{G} \thinspace:\thinspace \mathrm{Generator\_bus}(g) = n} p_{t,g} - \left( \sum_{l \in \mathcal{L} \thinspace:\thinspace \mathrm{Link\_bus0}(l) = n} f_{t,l} \right) + \sum_{l \in \mathcal{L} \thinspace:\thinspace \mathrm{Link\_bus1}(l) = n} f_{t,l} \cdot \eta_{l} - \left( \sum_{k \in \mathcal{K} \thinspace:\thinspace \mathrm{Line\_bus0}(k) = n} s_{t,k} \right) + \sum_{k \in \mathcal{K} \thinspace:\thinspace \mathrm{Line\_bus1}(k) = n} s_{t,k} - 0.5 \cdot \left( \sum_{k \in \mathcal{K} \thinspace:\thinspace \mathrm{Line\_bus0}(k) = n} \ell_{t,k} \right) - 0.5 \cdot \left( \sum_{k \in \mathcal{K} \thinspace:\thinspace \mathrm{Line\_bus1}(k) = n} \ell_{t,k} \right) = \sum_{d \in \mathcal{D} \thinspace:\thinspace \mathrm{Load\_bus}(d) = n} \mathrm{load}_{t,d} \qquad \forall\thinspace t \in \mathcal{T},\enspace n \in \mathcal{N}$$

### `Line-loss_upper`

`Line_loss_upper`

```yaml
Line_loss_upper:
  description: "`Line-loss_upper` — a line dissipates at most the loss at its rating"
  foreach: [snapshot, line]
  expression: Line_loss <= Line_loss_max
```

$$\ell_{t,k} \le \overline{\ell}_{t,k} \qquad \forall\thinspace t \in \mathcal{T},\enspace k \in \mathcal{K}$$

### `Line-loss_tangents-{k}-1`

`Line_loss_tangents_forward`

```yaml
Line_loss_tangents_forward:
  description: >-
    `Line-loss_tangents-{k}-1` — the loss sits above every tangent to its
    curve for flow one way; PyPSA names one row per segment `k`, this block
    states them all over the segment dimension
  foreach: [snapshot, line, segment]
  expression: Line_loss + Line_loss_slope * Line_s >= Line_loss_offset
```

$$\ell_{t,k} + \mathrm{a}_{t,k,k} \cdot s_{t,k} \ge \mathrm{b}_{t,k,k} \qquad \forall\thinspace t \in \mathcal{T},\enspace k \in \mathcal{K},\enspace k \in \mathcal{K}$$

### `Line-loss_tangents-{k}--1`

`Line_loss_tangents_reverse`

```yaml
Line_loss_tangents_reverse:
  description: "`Line-loss_tangents-{k}--1` — the same fan mirrored, the loss depending on the flow's magnitude"
  foreach: [snapshot, line, segment]
  expression: Line_loss - Line_loss_slope * Line_s >= Line_loss_offset
```

$$\ell_{t,k} - \mathrm{a}_{t,k,k} \cdot s_{t,k} \ge \mathrm{b}_{t,k,k} \qquad \forall\thinspace t \in \mathcal{T},\enspace k \in \mathcal{K},\enspace k \in \mathcal{K}$$

#### Variable domains

**`Generator_p`**

$$p_{t,g} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G}$$

**`Line_s`**

$$s_{t,k} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace k \in \mathcal{K}$$

**`Line_s_nom_ext`**

$$S_{k} \in \mathbb{R} \qquad \forall\thinspace k \in \mathcal{K} \thinspace:\thinspace \mathrm{ext}^{s}_{k}$$

**`Link_p`**

$$f_{t,l} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace l \in \mathcal{L}$$

**`Line_loss`**

$$\ell_{t,k} \ge 0 \qquad \forall\thinspace t \in \mathcal{T},\enspace k \in \mathcal{K}$$
<!-- gallery:end -->

Regenerate with `pixi run python -m tools.gallery`.
