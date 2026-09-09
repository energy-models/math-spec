<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# PyPSA, the multi-period class

Rung 15 of [PyPSA in one file](pypsa.md): `n.optimize(multi_investment_periods=True)`, stated on rungs 1 and 3 in a
file of its own — the model's description below says why. Its network is a whole one: eight snapshots over two investment periods, build years and lifetimes on the script.

## Rung 15 — investment periods, with a growth limit

| PyPSA | status | note |
| --- | --- | --- |
| [`Generator-p`](#variable-domains) | done | where the generator stands in the snapshot's period — `active`, data prep |
| [`Generator-fix-p-*`, `-ext-p-*`, `-ext-p_nom-*`](#generator-fix-p-lower) | done | rungs 1 and 3, masked by `active` |
| [`Carrier-growth_limit`](#carrier-growth_limit) | done | counted in the first period a build stands in; `edge=0` at the first period |
| [objective](#objective) | done | period weight on operation; capacity once per period it stands in |
| `StorageUnit-energy_balance` per period, ramps at period starts | out | `shift(…, by=snapshot_period)` has them; a later rung |

<!-- reference:rung_15_multi_period:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `12747.19109626398`, 80 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_15_multi_period.py`

```python
# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 15: two investment periods — build years, lifetimes, period weights and a carrier's growth limit, stated by `pypsa_multi_period.yaml`."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

MODEL = 'pypsa_multi_period.yaml'
OPTIMIZE = {'multi_investment_periods': True}


def build():
    """A whole network, not the spine: eight snapshots over two periods, a unit that retires, two wind builds capped by growth."""
    import pypsa

    n = pypsa.Network()
    n.snapshots = pd.MultiIndex.from_tuples(
        [(2020, datetime(2020, 1, 1, t)) for t in range(4)] + [(2030, datetime(2030, 1, 1, t)) for t in range(4)]
    )
    n.investment_periods = [2020, 2030]
    n.investment_period_weightings['objective'] = [1.0, 0.5]
    n.investment_period_weightings['years'] = [10.0, 10.0]
    n.snapshot_weightings['objective'] = [2.0, 1.5, 2.5, 2.0, 2.0, 1.5, 2.5, 2.0]
    n.add('Bus', ['north', 'south'])
    n.add('Carrier', 'wind', max_growth=50, max_relative_growth=0.5)
    n.add('Carrier', 'gas')
    n.add('Generator', 'old_gas', bus='north', carrier='gas', p_nom=40, marginal_cost=30, build_year=2010, lifetime=15)
    n.add(
        'Generator',
        'wind20',
        bus='north',
        carrier='wind',
        p_nom_extendable=True,
        p_nom_max=200,
        marginal_cost=1,
        capital_cost=100,
        build_year=2020,
        lifetime=30,
        p_max_pu=[0.8, 0.6, 0.7, 0.5, 0.8, 0.6, 0.7, 0.5],
    )
    n.add(
        'Generator',
        'wind30',
        bus='south',
        carrier='wind',
        p_nom_extendable=True,
        p_nom_max=200,
        marginal_cost=1,
        capital_cost=80,
        build_year=2030,
        lifetime=30,
        p_max_pu=[0.9, 0.7, 0.6, 0.8, 0.9, 0.7, 0.6, 0.8],
    )
    n.add(
        'Generator',
        'gas30',
        bus='south',
        carrier='gas',
        p_nom_extendable=True,
        p_nom_max=200,
        marginal_cost=40,
        capital_cost=50,
        build_year=2030,
        lifetime=30,
    )
    n.add('Link', 'wire15', bus0='north', bus1='south', p_nom=60, p_min_pu=-1, efficiency=0.95)
    n.add('Load', 'town15', bus='north', p_set=[20, 30, 25, 20, 35, 45, 40, 30])
    n.add('Load', 'port15', bus='south', p_set=[10, 20, 15, 10, 30, 40, 35, 25])
    return n
```

</details>
<!-- reference:rung_15_multi_period:end -->

## The file

<!-- gallery:begin -->
The multi-period class of a plain `n.optimize()`: `multi_investment_periods`, stated on rungs 1 and 3 in a file of its own. A snapshot belongs to an investment period, an asset stands in the periods its build year and lifetime span, and capacity is paid once per period it stands in, each period weighted; a carrier may grow only so much per period. Which snapshots an asset is active in is data prep, because a `where` reaches only the frame's own dimensions. A dimension a run may not have cannot ride on `examples/pypsa.yaml`, so this class lives here.

#### Sets

| Symbol | Meaning |
|---|---|
| $\mathcal{T}$ | index $t$ — `snapshot` with $\mathrm{snapshot\_period}: \mathcal{T} \to \mathcal{Y}$ — dispatch periods, positions across every investment period |
| $\mathcal{Y}$ | index $y$ — `period` — investment periods — PyPSA's `investment_periods` |
| $\mathcal{N}$ | index $n$ — `bus` — network nodes |
| $\mathcal{G}$ | index $g$ — `generator` with $\mathrm{Generator\_carrier}: \mathcal{G} \to \mathcal{C},\enspace \mathrm{Generator\_bus}: \mathcal{G} \to \mathcal{N}$ — generating units, each on one bus |
| $\mathcal{L}$ | index $l$ — `link` with $\mathrm{Link\_bus0}: \mathcal{L} \to \mathcal{N}$ — controllable connections, each from one bus to the buses it delivers to |
| $\mathcal{O}$ | index $o$ — `link_output` with $\mathrm{Link\_output\_link}: \mathcal{O} \to \mathcal{L},\enspace \mathrm{Link\_output\_bus}: \mathcal{O} \to \mathcal{N}$ — a link's output ports, one label per port a link declares — PyPSA's `bus1`, `bus2`, … columns read long, so a link of any number of output ports is one term in the balance, data prep |
| $\mathcal{D}$ | index $d$ — `load` with $\mathrm{Load\_bus}: \mathcal{D} \to \mathcal{N}$ — demands, each on one bus |
| $\mathcal{C}$ | index $c$ — `carrier` — energy carriers, what a growth limit is set per |

#### Parameters

| Symbol | Meaning |
|---|---|
| $\mathrm{w}$ | `snapshot_weightings_objective` over $\mathcal{T}$ — PyPSA's `snapshot_weightings.objective` — hours a snapshot stands for in the cost |
| $\mathrm{w}^{y}$ | `period_weight_objective` over $\mathcal{Y}$ — PyPSA's `investment_period_weightings.objective` — what a period's cost weighs |
| $\mathrm{on}$ | `Generator_active` over $\mathcal{T} \times \mathcal{G}$ — whether a generator stands in a snapshot's period — PyPSA's `active`, from build year and lifetime, data prep |
| $\mathrm{W}$ | `Generator_capital_weight` over $\mathcal{G}$ — the sum of period weights a generator stands in — PyPSA's `active * period_weighting`, summed, data prep |
| $\mathrm{new}$ | `Generator_first_active` over $\mathcal{Y} \times \mathcal{G}$ — one in the first period a generator stands in, zero elsewhere — PyPSA's `active.cumsum() == 1`, data prep |
| $\overline{\Delta}$ | `Carrier_max_growth` over $\mathcal{C}$ — most capacity of a carrier that may be added in a period; no value means no limit |
| $\mathrm{r}$ | `Carrier_max_relative_growth` over $\mathcal{C}$ — share of the previous period's additions that may be added on top |
| $\mathrm{p}^{\mathrm{nom}}$ | `Generator_p_nom` over $\mathcal{G}$ — nominal power |
| $\mathrm{ext}$ | `Generator_p_nom_extendable` over $\mathcal{G}$ — whether the nominal power is a decision |
| $\underline{\mathrm{p}}^{\mathrm{nom}}$ | `Generator_p_nom_min` over $\mathcal{G}$ — least nominal power an extendable generator may be built at |
| $\overline{\mathrm{p}}^{\mathrm{nom}}$ | `Generator_p_nom_max` over $\mathcal{G}$ — most nominal power an extendable generator may be built at |
| $\mathrm{c}^{\mathrm{cap}}$ | `Generator_capital_cost` over $\mathcal{G}$ — cost of one unit of nominal power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $\underline{\mathrm{p}}$ | `Generator_p_min_pu` over $\mathcal{T} \times \mathcal{G}$ — least output, per unit of nominal power |
| $\overline{\mathrm{p}}$ | `Generator_p_max_pu` over $\mathcal{T} \times \mathcal{G}$ — most output, per unit of nominal power — an availability profile |
| $\mathrm{c}$ | `Generator_marginal_cost` over $\mathcal{T} \times \mathcal{G}$ — cost of one unit of output |
| $\mathrm{f}^{\mathrm{nom}}$ | `Link_p_nom` over $\mathcal{L}$ — nominal power |
| $\underline{\mathrm{f}}$ | `Link_p_min_pu` over $\mathcal{T} \times \mathcal{L}$ — least flow, per unit of nominal power — negative for a link that carries both ways |
| $\overline{\mathrm{f}}$ | `Link_p_max_pu` over $\mathcal{T} \times \mathcal{L}$ — most flow, per unit of nominal power |
| $\eta$ | `Link_efficiency` over $\mathcal{O}$ — share of the flow that arrives at an output port, PyPSA's `efficiency`, `efficiency2`, … read long — negative where that port consumes rather than delivers |
| $\mathrm{c}^{f}$ | `Link_marginal_cost` over $\mathcal{T} \times \mathcal{L}$ — cost of one unit of flow |
| $\mathrm{load}$ | `Load_p_set` over $\mathcal{T} \times \mathcal{D}$ — demand |

#### Variables

| Symbol | Meaning |
|---|---|
| $p$ | `Generator_p` over $\mathcal{T} \times \mathcal{G}$ — `Generator-p` — output of a generator in a snapshot |
| $f$ | `Link_p` over $\mathcal{T} \times \mathcal{L}$ — `Link-p` — PyPSA's `p0`, the flow measured at the `Link_bus0` end: a positive value withdraws there and injects at every bus the link's output ports deliver to |
| $P$ | `Generator_p_nom_ext` over $\mathcal{G}$ — `Generator-p_nom` — nominal power where it is a decision; the parameter of the same PyPSA name carries the fixed regime |

$t \boxminus_{v} k$ denotes translation with $v$ standing where index $t-k$ leaves the dimension (`shift(edge=v)`), so the row at that boundary is built and carries $v$ rather than being dropped.

### Objective

```yaml
objective:
  sense: minimize
  description: operating cost by weighted snapshot and weighted period, and capacity once per period it stands in
  expression: >-
    sum(Generator_p * Generator_marginal_cost * snapshot_weightings_objective * at(period_weight_objective, by=snapshot_period))
    + sum(Link_p * Link_marginal_cost * snapshot_weightings_objective * at(period_weight_objective, by=snapshot_period))
    + sum(Generator_p_nom_ext * Generator_capital_cost * Generator_capital_weight)
```

$$\min \sum_{t \in \mathcal{T},\enspace g \in \mathcal{G}} p_{t,g} \cdot \mathrm{c}_{t,g} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T},\enspace l \in \mathcal{L}} f_{t,l} \cdot \mathrm{c}^{f}_{t,l} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{g \in \mathcal{G}} P_{g} \cdot \mathrm{c}^{\mathrm{cap}}_{g} \cdot \mathrm{W}_{g}$$

### `Generator-fix-p-lower`

`Generator_fix_p_lower`

```yaml
Generator_fix_p_lower:
  description: "`Generator-fix-p-lower` — a generator outputs at least its minimum"
  foreach: [snapshot, generator]
  where: not Generator_p_nom_extendable AND Generator_active
  expression: Generator_p >= Generator_p_min_pu * Generator_p_nom
```

$$p_{t,g} \ge \underline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \neg \mathrm{ext}_{g} \wedge \mathrm{on}_{t,g}$$

### `Generator-fix-p-upper`

`Generator_fix_p_upper`

```yaml
Generator_fix_p_upper:
  description: "`Generator-fix-p-upper` — a generator outputs at most what is available"
  foreach: [snapshot, generator]
  where: not Generator_p_nom_extendable AND Generator_active
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom
```

$$p_{t,g} \le \overline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \neg \mathrm{ext}_{g} \wedge \mathrm{on}_{t,g}$$

### `Generator-ext-p-lower`

`Generator_ext_p_lower`

```yaml
Generator_ext_p_lower:
  description: "`Generator-ext-p-lower` — an extendable generator outputs at least its minimum of the chosen build"
  foreach: [snapshot, generator]
  where: Generator_p_nom_extendable AND Generator_active
  expression: Generator_p >= Generator_p_min_pu * Generator_p_nom_ext
```

$$p_{t,g} \ge \underline{\mathrm{p}}_{t,g} \cdot P_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{ext}_{g} \wedge \mathrm{on}_{t,g}$$

### `Generator-ext-p-upper`

`Generator_ext_p_upper`

```yaml
Generator_ext_p_upper:
  description: "`Generator-ext-p-upper` — an extendable generator outputs at most what is available of the chosen build"
  foreach: [snapshot, generator]
  where: Generator_p_nom_extendable AND Generator_active
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom_ext
```

$$p_{t,g} \le \overline{\mathrm{p}}_{t,g} \cdot P_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{ext}_{g} \wedge \mathrm{on}_{t,g}$$

### `Generator-ext-p_nom-lower`

`Generator_ext_p_nom_lower`

```yaml
Generator_ext_p_nom_lower:
  description: "`Generator-ext-p_nom-lower` — the chosen build is at least its floor"
  foreach: [generator]
  where: Generator_p_nom_extendable
  expression: Generator_p_nom_ext >= Generator_p_nom_min
```

$$P_{g} \ge \underline{\mathrm{p}}^{\mathrm{nom}}_{g} \qquad \forall\thinspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{ext}_{g}$$

### `Generator-ext-p_nom-upper`

`Generator_ext_p_nom_upper`

```yaml
Generator_ext_p_nom_upper:
  description: "`Generator-ext-p_nom-upper` — the chosen build is at most its cap; a cap of infinity is no row"
  foreach: [generator]
  where: Generator_p_nom_extendable AND Generator_p_nom_max
  expression: Generator_p_nom_ext <= Generator_p_nom_max
```

$$P_{g} \le \overline{\mathrm{p}}^{\mathrm{nom}}_{g} \qquad \forall\thinspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{ext}_{g} \wedge \overline{\mathrm{p}}^{\mathrm{nom}}_{g} \text{ is defined}$$

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

### `Bus-nodal_balance`

`Bus_nodal_balance`

```yaml
Bus_nodal_balance:
  description: >-
    `Bus-nodal_balance` — what is generated at a bus, less what the links
    take away, plus what arrives over them after losses, meets the load
    there
  foreach: [snapshot, bus]
  expression: >-
    sum(Generator_p, by=Generator_bus)
    - sum(Link_p, by=Link_bus0)
    + sum(at(Link_p, by=Link_output_link) * Link_efficiency, by=Link_output_bus)
    == sum(Load_p_set, by=Load_bus)
```

$$\sum_{g \in \mathcal{G} \thinspace:\thinspace \mathrm{Generator\_bus}(g) = n} p_{t,g} - \left( \sum_{l \in \mathcal{L} \thinspace:\thinspace \mathrm{Link\_bus0}(l) = n} f_{t,l} \right) + \sum_{o \in \mathcal{O} \thinspace:\thinspace \mathrm{Link\_output\_bus}(o) = n} f_{t,\mathrm{Link\_output\_link}(o)} \cdot \eta_{o} = \sum_{d \in \mathcal{D} \thinspace:\thinspace \mathrm{Load\_bus}(d) = n} \mathrm{load}_{t,d} \qquad \forall\thinspace t \in \mathcal{T},\enspace n \in \mathcal{N}$$

### `Carrier-growth_limit`

`Carrier_growth_limit`

```yaml
Carrier_growth_limit:
  description: >-
    `Carrier-growth_limit` — what a carrier adds in a period, counting each
    build in the first period it stands in, is at most its allowance plus a
    share of what it added the period before; the first period has no
    predecessor, so `edge=0` leaves it the bare allowance
  foreach: [carrier, period]
  where: Carrier_max_growth
  expression: >-
    sum(Generator_p_nom_ext * Generator_first_active, by=Generator_carrier)
    - shift(sum(Generator_p_nom_ext * Generator_first_active, by=Generator_carrier), over=period, offset=1, edge=0)
    * Carrier_max_relative_growth
    <= Carrier_max_growth
```

$$\sum_{g \in \mathcal{G} \thinspace:\thinspace \mathrm{Generator\_carrier}(g) = c} P_{g} \cdot \mathrm{new}_{y,g} - \left( \sum_{g \in \mathcal{G} \thinspace:\thinspace \mathrm{Generator\_carrier}(g) = c} P_{g} \cdot \mathrm{new}_{y \boxminus_{0} 1,g} \right) \cdot \mathrm{r}_{c} \le \overline{\Delta}_{c} \qquad \forall\thinspace c \in \mathcal{C},\enspace y \in \mathcal{Y} \thinspace:\thinspace \overline{\Delta}_{c} \text{ is defined}$$

#### Variable domains

**`Generator_p`**

$$p_{t,g} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{on}_{t,g}$$

**`Link_p`**

$$f_{t,l} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace l \in \mathcal{L}$$

**`Generator_p_nom_ext`**

$$P_{g} \in \mathbb{R} \qquad \forall\thinspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{ext}_{g}$$
<!-- gallery:end -->

Regenerate with `pixi run python -m tools.gallery`.
