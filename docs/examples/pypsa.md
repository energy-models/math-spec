<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# PyPSA in one file

The model a plain `n.optimize()` builds, stated as one file and grown a rung
at a time. The file also carries the two classes PyPSA switches on with a
keyword: the two-stage stochastic class over a `scenario` axis (rung 14), and
the multi-period investment class over a `period` axis (rung 15). A plain run
feeds one scenario and one all-active period, so every extra axis collapses and
the standard model returns. The index below lists every row PyPSA emits (PyPSA
`1.3.0`, `pypsa/optimization/`) and links each to its block in the file.

Three rules shape the file. Bounds are the explicit rows PyPSA writes, so
their duals are row duals. Regimes are data columns and `where:` masks. Names
are PyPSA's, `Component_attribute`, with a symbol table
(`examples/symbols/pypsa.yaml`) making the math read as math.

## Index

A row is **done** once the file states it as the one block PyPSA builds.
**split** means the same feasible region and optimum under a different
statement, such as several `where:` blocks. **open** means not stated yet.
**out** means never stated, deliberately: emitted only under the keyword,
scope or version the note names. **diverges** means the file states the
intended math where PyPSA `1.3.0` has a bug; the note names the issue, and the
rung records the intended objective and what PyPSA gives until the fix ships. A name carrying `{k}`, `{s}`, `{c}` or `{n}` stands
for the family PyPSA numbers per segment, scenario, outaged component or
sub-network.

Each rung's banner states what PyPSA solved its reference network to. A
rung that records a PyPSA bug, marked ✘, states what PyPSA gives beside the
intended objective.

<!-- reference:spine:begin -->
> Every rung's network is `spine.build()` plus the rung's own `n.add` calls, data inline; a keyword not passed is PyPSA's default. A banner states what PyPSA solved the rung to; how an engine attaches the network to the file, and what it makes of it, is that engine's own record.

<details markdown="1">
<summary>The shared spine, <code>spine.py</code></summary>

`spine.py`

```python
"""The spine every rung starts from: two buses, a coal and a gas unit, one link, two loads.

Four hourly snapshots with three different weighting columns, none of them constant
and none 1.0, so a factor a formula drops or swaps cannot pass as identity.
"""

from __future__ import annotations

from datetime import datetime

#: Four hourly stamps — snapshots are timestamps, as PyPSA's are in practice and as the file declares them.
SNAPSHOTS = [datetime(2015, 1, 1, hour) for hour in range(4)]
WEIGHTINGS = {'objective': [2.0, 1.5, 2.5, 3.0], 'stores': [0.5, 2.0, 1.5, 2.5], 'generators': [1.5, 0.5, 3.0, 2.0]}


def build():
    """The spine as a fresh ``pypsa.Network``; each rung adds to what this returns."""
    import pypsa

    n = pypsa.Network()
    n.set_snapshots(SNAPSHOTS)
    for column, values in WEIGHTINGS.items():
        n.snapshot_weightings[column] = values
    n.add('Bus', 'north')
    n.add('Bus', 'south')
    n.add('Generator', 'coal', bus='north', p_nom=100, marginal_cost=10)
    n.add('Generator', 'gas', bus='south', p_nom=100, marginal_cost=30)
    n.add('Link', 'wire', bus0='north', bus1='south', p_nom=40, p_min_pu=-1, efficiency=0.9)
    n.add('Load', 'north_load', bus='north', p_set=30)
    n.add('Load', 'south_load', bus='south', p_set=40)
    return n
```

</details>
<!-- reference:spine:end -->

### Rung 1 — transport

| PyPSA                                               | status | note                                                       |
| --------------------------------------------------- | ------ | ---------------------------------------------------------- |
| [`Generator-p`, `Link-p`](#variable-domains)        | done   |                                                            |
| [`Generator-fix-p-lower`](#generator-fix-p-lower)   | done   |                                                            |
| [`Generator-fix-p-upper`](#generator-fix-p-upper)   | done   |                                                            |
| [`Link-fix-p-lower`](#link-fix-p-lower)             | done   |                                                            |
| [`Link-fix-p-upper`](#link-fix-p-upper)             | done   |                                                            |
| [`Bus-nodal_balance`](#bus-nodal_balance)           | done   | a loaded bus with nothing attached: PyPSA refuses, see X2  |
| [`Bus-nodal_balance`](#bus-nodal_balance) with a component `sign` | done | rung 43 |
| [`Bus-nodal_balance`](#bus-nodal_balance) with a load that is not `active` | done | rung 50; `Load_demand` is zero where `Load_active` is false |
| `Bus-meshed-*-nodal_balance`                        | out    | the same balance rows, dealt into linopy containers by how many component columns name a bus — `meshed_thresholds`, an `n.optimize()` keyword defaulting to `[30, 100, 400]`. Same rows, same duals, another name; a modeler whose engine wants the split states it, the file does not (#123) |
| [`marginal_cost`](#objective)                       | done   |                                                            |
| [`marginal_cost_quadratic`](#objective)             | done   | rungs 10 and 36, below; Generator and Link `p`, Process `p`, StorageUnit `p_dispatch` only, and Store net `p` |
| `objective_constant`                                | split  | an objective shift, compared net of `n._objective_constant` — rungs 11 and 13 carry a nonzero one, `21915277.52` and `160.0`, so the netting is under test |

<!-- reference:rung_01_transport:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `7182.222222222223`, 45 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_01_transport.py`

```python
"""Rung 1: transport — two buses, two generators, one controllable link."""

from __future__ import annotations

from math import nan

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.links_t.p_set['wire'] = [10, nan, nan, nan]
    n.add('Generator', 'must_run', bus='south', p_nom=10, marginal_cost=0, p_set=[5, 5, 5, 5])
    return n
```

</details>
<!-- reference:rung_01_transport:end -->

### Rung 2 — storage

| PyPSA                                                 | status | note                                                          |
| ----------------------------------------------------- | ------ | ------------------------------------------------------------- |
| [`StorageUnit-p_dispatch`, `-p_store`, `-state_of_charge`, `Store-e`, `Store-p`](#variable-domains) | done |                                 |
| [`StorageUnit-spill`](#variable-domains)              | done   | `where: inflow > 0`, `absence: zero`; bounds on the variable, as PyPSA's |
| [`StorageUnit-fix-*`](#storageunit-fix-p_dispatch-lower), [`Store-fix-e-*`](#store-fix-e-lower) | done |                                 |
| [`StorageUnit-energy_balance`](#storageunit-energy_balance) | done | the charge carried into a snapshot is a cased quantity — cyclic, opening, carried; `(1-loss)**eh` is prep |
| [`Store-energy_balance`](#store-energy_balance)       | done   | same                                                          |
| [`StorageUnit-p_set`](#storageunit-p_set), [`{c}-{attr}_set`](#generator-p_set) | done | `Generator-p_set`, `Link-p_set`, `StorageUnit-state_of_charge_set`, `Store-e_set`, `Line-s_set`; `Store-p_set`, `StorageUnit-p_dispatch_set`, `-p_store_set` in rung 37 |
| [`marginal_cost_storage`, `spill_cost`](#objective)   | done   |                                                               |

<!-- reference:rung_02_storage:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `4456.659315422356`, 103 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_02_storage.py`

```python
"""Rung 2: storage — a cyclic battery, an inflow reservoir with a set state of charge, and a store."""

from __future__ import annotations

from math import nan

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.generators_t.marginal_cost['gas'] = [15, 15, 60, 60]
    n.add(
        'StorageUnit',
        'battery',
        bus='south',
        p_nom=20,
        max_hours=4,
        efficiency_store=0.95,
        efficiency_dispatch=0.9,
        standing_loss=0.01,
        cyclic_state_of_charge=True,
        marginal_cost=0.5,
        p_set=[0, nan, nan, nan],
    )
    n.add(
        'StorageUnit',
        'reservoir',
        bus='south',
        p_nom=10,
        max_hours=2,
        spill_cost=2,
        state_of_charge_initial=5,
        marginal_cost_storage=0.1,
        inflow=[12, 12, 12, 12],
        state_of_charge_set=[nan, nan, nan, 10],
    )
    n.add(
        'Store',
        'cavern',
        bus='south',
        e_nom=40,
        e_initial=25,
        standing_loss=0.005,
        marginal_cost=0.2,
        e_set=[nan, nan, nan, 20],
    )
    return n
```

</details>
<!-- reference:rung_02_storage:end -->

### Rung 3 — expansion

| PyPSA                            | status | note                                        |
| -------------------------------- | ------ | ------------------------------------------- |
| [`{c}-p_nom`, `-s_nom`, `-e_nom`](#variable-domains) | done | `{c}_p_nom_ext` here — the fixed regime keeps the parameter |
| [`{c}-ext-{attr}-lower/upper`](#generator-ext-p-lower) | done |                                           |
| [`{c}-ext-p_nom-lower/upper`](#generator-ext-p_nom-lower) | done |                                        |
| [`{c}-p_nom_set`](#generator-p_nom_set) | done |                                                      |
| [`Generator-e_sum_min/max`](#generator-e_sum_min) | done |                                            |
| [capital cost](#objective)       | done   | `periodized_cost` is an annuity, data prep  |

<!-- reference:rung_03_expansion:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `7633.908502024292`, 184 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_03_expansion.py`

```python
"""Rung 3: expansion — extendable capacity, energy-sum bounds, fixed and set nominal capacities."""

from __future__ import annotations

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', 'island')
    n.add('Carrier', 'onwind')
    n.add('Carrier', 'solarpv')
    n.add('Carrier', 'dc')
    n.add('Carrier', 'phs')
    n.add('Carrier', 'h2')
    n.add(
        'Generator',
        'wind',
        bus='north',
        carrier='onwind',
        p_nom_extendable=True,
        capital_cost=50,
        p_nom_min=5,
        p_nom_max=80,
        marginal_cost=0,
        e_sum_min=40,
        ramp_limit_up=0.4,
        ramp_limit_down=0.4,
        p_max_pu=[0.3, 0.8, 0.5, 0.9],
    )
    n.add(
        'Generator',
        'solar',
        bus='north',
        carrier='solarpv',
        p_nom_extendable=True,
        capital_cost=60,
        p_nom_max=40,
        marginal_cost=0,
        p_nom_set=15,
        p_max_pu=[0.5, 0.6, 0.4, 0.2],
    )
    n.add('Generator', 'diesel', bus='island', marginal_cost=40, p_nom=60, e_sum_max=70)
    n.add(
        'Link',
        'cable',
        bus0='north',
        bus1='island',
        carrier='dc',
        length=120,
        p_nom_extendable=True,
        capital_cost=20,
        p_nom_max=30,
        efficiency=0.95,
        p_nom_set=25,
        ramp_limit_up=0.3,
        ramp_limit_down=0.3,
    )
    n.add('Load', 'island_load', bus='island', p_set=10)
    n.add(
        'StorageUnit',
        'pump',
        bus='north',
        carrier='phs',
        p_nom_extendable=True,
        capital_cost=15,
        p_nom_max=30,
        max_hours=4,
        efficiency_store=0.9,
        efficiency_dispatch=0.9,
        cyclic_state_of_charge=True,
        p_nom_set=20,
    )
    n.add('StorageUnit', 'ice', bus='island', max_hours=2, p_nom=8, state_of_charge_initial=6)
    n.add(
        'Store',
        'tank',
        bus='north',
        carrier='h2',
        e_nom_extendable=True,
        capital_cost=2,
        e_nom_max=80,
        e_cyclic=True,
        e_nom_set=50,
    )
    n.add('Store', 'keg', bus='island', e_nom=15, e_initial=5)
    n.add(
        'GlobalConstraint',
        'tech_wind',
        type='tech_capacity_expansion_limit',
        carrier_attribute='onwind',
        sense='==',
        constant=50,
    )
    n.add(
        'GlobalConstraint',
        'tech_solar',
        type='tech_capacity_expansion_limit',
        carrier_attribute='solarpv',
        sense='>=',
        constant=10,
    )
    n.add(
        'GlobalConstraint',
        'tech_dc',
        type='tech_capacity_expansion_limit',
        carrier_attribute='dc',
        sense='<=',
        constant=28,
    )
    n.add(
        'GlobalConstraint',
        'tech_phs',
        type='tech_capacity_expansion_limit',
        carrier_attribute='phs',
        sense='<=',
        constant=25,
    )
    n.add(
        'GlobalConstraint',
        'tech_h2',
        type='tech_capacity_expansion_limit',
        carrier_attribute='h2',
        sense='>=',
        constant=30,
    )
    n.add(
        'GlobalConstraint',
        'vol_dc',
        type='transmission_volume_expansion_limit',
        carrier_attribute='dc',
        sense='<=',
        constant=3500,
    )
    n.add(
        'GlobalConstraint',
        'cost_dc',
        type='transmission_expansion_cost_limit',
        carrier_attribute='dc',
        sense='>=',
        constant=400,
    )
    n.add(
        'GlobalConstraint',
        'cost_dc_exact',
        type='transmission_expansion_cost_limit',
        carrier_attribute='dc',
        sense='==',
        constant=500,
    )
    return n
```

</details>
<!-- reference:rung_03_expansion:end -->

### Rung 4 — ramps

| PyPSA                          | status | note                                                       |
| ------------------------------ | ------ | ---------------------------------------------------------- |
| [`{c}-p-ramp_limit_up/down`](#generator-p-ramp_limit_up) | done | the build, the allowance and the output carried in are cased quantities, so fixed, extendable and committed are one block; big-M is rung 8's. A missing limit reads as the full build, and a start-up or shut-down ramp alone builds the row, rung 28 |
| [`{c}-p-ramp_limit_up/down`](#generator-p-ramp_limit_up) with a limit per snapshot | done | rung 45 |
| [`{c}-p-ramp_limit_*`](#generator-p-ramp_limit_up), `-bigM`, at the first snapshot from `p_init` | done | rung 46 |

<!-- reference:rung_04_ramps:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `8785.0`, 64 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_04_ramps.py`

```python
"""Rung 4: ramps — ramp limits on fixed and extendable generators and links."""

from __future__ import annotations

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', 'east')
    n.add('Generator', 'coal_slow', bus='north', p_nom=80, marginal_cost=8, ramp_limit_up=0.2, ramp_limit_down=0.2)
    n.add('Link', 'tie', bus0='north', bus1='east', p_nom=50, efficiency=1, ramp_limit_up=0.4, ramp_limit_down=0.4)
    n.add('Load', 'east_load', bus='east', p_set=[5, 20, 25, 10])
    n.add('Load', 'swing', bus='north', p_set=[0, 25, 45, 0])
    return n
```

</details>
<!-- reference:rung_04_ramps:end -->

### Rung 5 — global constraints

`GlobalConstraint-{name}` for all; the type and the comparator are data, so
each type is three blocks by sense.

| PyPSA type                            | status      | note                                              |
| ------------------------------------- | ----------- | ------------------------------------------------- |
| [`primary_energy`](#primary_energy)   | split       | a block per sense — sense as data is beyond #70; carrier weights are prep; one period in rung 35; per scenario in rung 40 |
| [`operational_limit`](#operational_limit) | split   | a block per sense; one period in rung 35; per scenario in rung 40 |
| [`transmission_volume_expansion_limit`](#transmission_volume_expansion_limit) | split | a block per sense; membership from PyPSA's carrier string is prep; per scenario in rung 40 |
| [`transmission_expansion_cost_limit`](#transmission_expansion_cost_limit) | split | a block per sense                     |
| [`tech_capacity_expansion_limit`](#tech_capacity_expansion_limit) | split | a block per sense                             |
| `Bus-nom_min/max_{carrier}`           | out         | deprecated in PyPSA                               |
| [`Carrier-growth_limit`](#carrier-growth_limit) | done | generators in rung 15, every extendable component in rung 21, below |

<!-- reference:rung_05_global_constraints:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `10282.833333333334`, 102 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_05_global_constraints.py`

```python
"""Rung 5: global constraints — one row per limit type and sense."""

from __future__ import annotations

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Carrier', 'coalc', co2_emissions=0.9)
    n.add('Carrier', 'gasc', co2_emissions=0.4)
    n.add('Carrier', 'windc')
    n.add('Generator', 'coal5', bus='north', carrier='coalc', p_nom=60, marginal_cost=9, efficiency=0.35)
    n.add('Generator', 'gas5', bus='north', carrier='gasc', p_nom=60, marginal_cost=25, efficiency=0.5)
    n.add('Generator', 'wind5', bus='north', carrier='windc', p_nom=60, marginal_cost=40)
    n.add('Load', 'extra5', bus='north', p_set=50)
    n.add('StorageUnit', 'res5', bus='north', carrier='gasc', p_nom=20, max_hours=4, state_of_charge_initial=30)
    n.add('Store', 'tank5', bus='north', carrier='coalc', e_nom=40, e_initial=25)
    n.add(
        'GlobalConstraint',
        'co2_cap',
        type='primary_energy',
        carrier_attribute='co2_emissions',
        sense='<=',
        constant=150,
    )
    n.add(
        'GlobalConstraint',
        'co2_floor',
        type='primary_energy',
        carrier_attribute='co2_emissions',
        sense='>=',
        constant=20,
    )
    n.add(
        'GlobalConstraint',
        'co2_exact',
        type='primary_energy',
        carrier_attribute='co2_emissions',
        sense='==',
        constant=120,
    )
    n.add('GlobalConstraint', 'op_wind', type='operational_limit', carrier_attribute='windc', sense='==', constant=30)
    n.add('GlobalConstraint', 'op_coal', type='operational_limit', carrier_attribute='coalc', sense='<=', constant=200)
    n.add('GlobalConstraint', 'op_gas', type='operational_limit', carrier_attribute='gasc', sense='>=', constant=10)
    return n
```

</details>
<!-- reference:rung_05_global_constraints:end -->

### Rung 6 — KVL

| PyPSA                   | status | note                              |
| ----------------------- | ------ | --------------------------------- |
| [`Line-s`](#variable-domains), [`Line-fix-s-*`](#line-fix-s-lower) | done | the ext and nominal rows sit under rung 3's pattern |
| [`Kirchhoff-Voltage-Law`](#kirchhoff-voltage-law) | done | the cycle basis is data prep      |

<!-- reference:rung_06_kvl:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `23962.0`, 123 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_06_kvl.py`

```python
"""Rung 6: KVL — passive lines under Kirchhoff's voltage law."""

from __future__ import annotations

from math import nan

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', 'a')
    n.add('Bus', 'b')
    n.add('Bus', 'c')
    n.add('Generator', 'hydro', bus='a', p_nom=80, marginal_cost=10)
    n.add('Generator', 'diesel6', bus='b', p_nom=80, marginal_cost=50)
    n.add('Load', 'town', bus='c', p_set=45)
    n.add('Line', 'ab', bus0='a', bus1='b', carrier='AC', length=30, x=0.1, r=0.01, s_nom=60)
    n.add('Line', 'bc', bus0='b', bus1='c', carrier='AC', length=40, x=0.2, r=0.01, s_nom=60, s_set=[16, nan, nan, nan])
    n.add('Line', 'ca', bus0='c', bus1='a', carrier='AC', length=35, x=0.1, r=0.01, s_nom=60)
    n.add(
        'Line',
        'ca2',
        bus0='c',
        bus1='a',
        carrier='AC',
        length=50,
        x=0.15,
        r=0.01,
        s_nom_extendable=True,
        capital_cost=10,
        s_nom_max=40,
        s_nom_set=30,
    )
    n.add(
        'Line',
        'ca3',
        bus0='c',
        bus1='a',
        carrier='AC',
        length=80,
        x=0.12,
        r=0.01,
        s_nom_extendable=True,
        capital_cost=8,
        s_nom_max=40,
    )
    n.add(
        'GlobalConstraint',
        'vol_ac',
        type='transmission_volume_expansion_limit',
        carrier_attribute='AC',
        sense='==',
        constant=2300,
    )
    n.add(
        'GlobalConstraint',
        'vol_ac_floor',
        type='transmission_volume_expansion_limit',
        carrier_attribute='AC',
        sense='>=',
        constant=1000,
    )
    n.add(
        'GlobalConstraint',
        'cost_ac',
        type='transmission_expansion_cost_limit',
        carrier_attribute='AC',
        sense='<=',
        constant=500,
    )
    n.add(
        'GlobalConstraint',
        'cost_ac_floor',
        type='transmission_expansion_cost_limit',
        carrier_attribute='AC',
        sense='>=',
        constant=100,
    )
    n.add(
        'GlobalConstraint',
        'tech_ac',
        type='tech_capacity_expansion_limit',
        carrier_attribute='AC',
        sense='<=',
        constant=60,
    )
    return n
```

</details>
<!-- reference:rung_06_kvl:end -->

### Rung 7 — commitment

| PyPSA                                        | status | note                                                          |
| -------------------------------------------- | ------ | ------------------------------------------------------------- |
| [`{c}-status`, `-start_up`, `-shut_down`](#variable-domains) | done | Generator; Link in rung 25, Process in rung 26 |
| [`{c}-com-p-lower/upper`](#generator-com-p-lower) | done |                                                          |
| [`{c}-*-p-fixed-upper`](#generator-status-p-fixed-upper) | done | status, start and stop each at most one, as explicit rows |
| [`{c}-com-transition-start-up/shut-down`](#generator-com-transition-start-up) | done | the state carried into a snapshot is a cased quantity, so the first snapshot needs no block of its own |
| [`{c}-com-up-time`, `-down-time`](#generator-com-up-time) | done | `sum_back(window=min_up_time)`                    |
| [`{c}-com-status-min_up_time_must_stay_up`](#generator-com-status-min_up_time_must_stay_up) | done | the window is a prep mask — `position()` takes a literal |
| [`{c}-com-status-min_down_time_must_stay_up`](#generator-com-status-min_down_time_must_stay_up) | done | the same prep mask over the down time brought in, status zero; PyPSA's name says `_must_stay_up`; rung 24 records it |
| [`stand_by_cost`, `start_up_cost`, `shut_down_cost`](#objective) | done | a start and a stop carry no snapshot or period weight, rung 48 |
| [`{c}-com-p-before/-current/-partly-*`](pypsa_linearized_uc.md) | done | rungs 12, 44 and 47, a file of its own: Generator commitment on fixed builds |

<!-- reference:rung_07_commitment:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `7775.0`, 116 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_07_commitment.py`

```python
"""Rung 7: commitment — committable units with up and down times and ramp limits at the transitions."""

from __future__ import annotations

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add(
        'Generator',
        'uc',
        bus='north',
        committable=True,
        p_nom=50,
        marginal_cost=5,
        p_min_pu=0.4,
        min_up_time=3,
        min_down_time=2,
        up_time_before=1,
        ramp_limit_up=0.5,
        ramp_limit_down=0.5,
        ramp_limit_start_up=0.6,
        ramp_limit_shut_down=0.6,
        start_up_cost=100,
        shut_down_cost=50,
        stand_by_cost=5,
    )
    n.add(
        'Generator',
        'cold',
        bus='south',
        committable=True,
        p_nom=30,
        marginal_cost=60,
        p_min_pu=0.3,
        min_up_time=2,
        min_down_time=1,
        up_time_before=0,
        ramp_limit_up=0.5,
        ramp_limit_down=0.5,
        start_up_cost=80,
    )
    n.add('Load', 'swing7', bus='north', p_set=[25, 45, 45, 10])
    return n
```

</details>
<!-- reference:rung_07_commitment:end -->

### Rung 8 — modular and big-M

| PyPSA                                         | status | note                                                       |
| --------------------------------------------- | ------ | ---------------------------------------------------------- |
| [`{c}-n_mod`, `{c}-p_nom_modularity`](#generator-p_nom_modularity) | done |                                       |
| [`{c}-*-p_nom-variable-upper`](#generator-status-p_nom-variable-upper) | done | a modular unit is on only where a module is built |
| [`{c}-*-p-fixed-upper`, modular](#generator-status-p-fixed-upper) | done | the cap is the build's whole count of modules, `p_nom / p_nom_mod` in data prep, see X1; rung 8's `array` fixes one (#123) |
| [`{c}-com-mod-p-lower/upper`](#generator-com-mod-p-lower) | done | one module's share, times the status — a fixed build too, beside its ordinary `com-p-*` rows |
| [`{c}-com-ext-p-*` (big-M)](#generator-com-ext-p-upper-cap) | done | a cap row beside a big-M row; `M` is the build cap at full availability, data prep |
| [`{c}-com-ext-p-lower-nonneg`](#generator-com-ext-p-lower-nonneg) | done | `(p_min_pu >= 0).all()` is prep        |
| [`{c}-p-ramp_limit_*-bigM`](#generator-p-ramp_limit_up-run-bigm) | done | run and start rows up, run and shut rows down; the output carried in is a cased quantity, so each is one block. A modular build takes the ordinary rows against one module instead, rung 27 |

<!-- reference:rung_08_modular_big_m:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `15915.0`, 191 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_08_modular_big_m.py`

```python
"""Rung 8: modular and big-M — capacity in whole modules, built or already standing, and a committable unit whose capacity is also built."""

from __future__ import annotations

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', 'mill')
    n.add(
        'Generator',
        'block',
        bus='mill',
        p_nom_extendable=True,
        committable=True,
        p_nom_mod=25,
        p_nom_max=100,
        capital_cost=30,
        marginal_cost=20,
        p_min_pu=0.2,
        up_time_before=0,
    )
    n.add(
        'Generator',
        'flex',
        bus='mill',
        p_nom_extendable=True,
        committable=True,
        p_nom_max=80,
        capital_cost=50,
        marginal_cost=10,
        p_min_pu=0.3,
        up_time_before=0,
        ramp_limit_up=0.25,
        ramp_limit_down=0.25,
    )
    n.add(
        'Generator',
        'sink',
        bus='mill',
        p_nom_extendable=True,
        committable=True,
        p_nom_max=30,
        capital_cost=40,
        marginal_cost=15,
        p_min_pu=-0.2,
        up_time_before=0,
    )
    n.add(
        'Generator',
        'array',
        bus='mill',
        committable=True,
        p_nom=90,
        p_nom_mod=30,
        marginal_cost=12,
        p_min_pu=0.2,
        up_time_before=0,
    )
    n.add('Load', 'mill_load', bus='mill', p_set=[40, 80, 120, 60])
    return n
```

</details>
<!-- reference:rung_08_modular_big_m:end -->

### Rung 9 — multi-link

| PyPSA                        | status | note                                          |
| ---------------------------- | ------ | --------------------------------------------- |
| [nodal balance, ports 1..n](#bus-nodal_balance) | done | one term over `link_output`, so a link of any number of output ports needs no further declaration (#124) |

<!-- reference:rung_09_multilink:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `11714.4`, 92 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_09_multilink.py`

```python
"""Rung 9: a multi-link with four output ports — power and heat sold, waste heat vented, and a station service the link draws back."""

from __future__ import annotations

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', 'gasb')
    n.add('Bus', 'power')
    n.add('Bus', 'heat')
    n.add('Bus', 'flue')
    n.add('Bus', 'aux')
    n.add('Generator', 'well', bus='gasb', p_nom=100, marginal_cost=5)
    n.add('Generator', 'grid_import', bus='power', p_nom=50, marginal_cost=60)
    n.add('Generator', 'vent', bus='flue', p_nom=100, p_min_pu=-1, p_max_pu=0)
    n.add('Generator', 'aux_supply', bus='aux', p_nom=10, marginal_cost=2)
    n.add(
        'Link',
        'chp',
        bus0='gasb',
        bus1='power',
        bus2='heat',
        bus3='flue',
        bus4='aux',
        efficiency=0.4,
        efficiency2=0.45,
        efficiency3=0.1,
        efficiency4=-0.02,
        p_nom=60,
        marginal_cost=1,
    )
    n.add('Load', 'homes', bus='power', p_set=20)
    n.add('Load', 'district', bus='heat', p_set=18)
    return n
```

</details>
<!-- reference:rung_09_multilink:end -->

### Rung 10 — quadratic costs

A marginal cost quadratic in output: PyPSA's `marginal_cost_quadratic`, one
squared term per component in the objective, each snapshot weighted by the hours
it stands for. Generator and Link carry it here; rung 36 puts it on a process,
a storage unit and a store. A plain run feeds zero, so the term vanishes and
the objective stays linear.

| PyPSA | status | note |
| --- | --- | --- |
| [`marginal_cost_quadratic`](#objective) | done | degree 2 in the objective; Generator and Link here |

<!-- reference:rung_10_quadratic_costs:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `12587.437500000098`, 60 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_10_quadratic_costs.py`

```python
"""Rung 10: quadratic costs — a marginal cost quadratic in output."""

from __future__ import annotations

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', 'village')
    n.add('Generator', 'steam', bus='north', p_nom=80, marginal_cost=5, marginal_cost_quadratic=0.08)
    n.add('Generator', 'engine', bus='north', p_nom=80, marginal_cost=20, marginal_cost_quadratic=0.01)
    n.add(
        'Link',
        'wire2',
        bus0='north',
        bus1='village',
        p_nom=40,
        p_min_pu=-1,
        efficiency=0.9,
        marginal_cost=1,
        marginal_cost_quadratic=0.02,
    )
    n.add('Load', 'village_load', bus='village', p_set=15)
    n.add('Load', 'extra10', bus='north', p_set=[30, 50, 40, 60])
    return n
```

</details>
<!-- reference:rung_10_quadratic_costs:end -->

### Rung 11 — ac-dc-meshed

PyPSA's `ac_dc_meshed` example, whole: meshed AC and DC, extendable lines,
links and generators, carriers, a CO2 budget. Every statement above,
composed; the first rung with an objective constant.

<!-- reference:rung_11_ac_dc_meshed:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `-3474256.0405499237`, 468 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_11_ac_dc_meshed.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 11: PyPSA's own `ac_dc_meshed` example, whole — meshed AC and DC, extendable lines, links and generators, carriers, a CO2 budget."""

from __future__ import annotations

from datetime import datetime

#: Ten hourly stamps, the example's own. Every weighting column there is 1.0, which is
#: also the default, so no row below sets one.
SNAPSHOTS = [datetime(2015, 1, 1, hour) for hour in range(10)]

#: Wind availability per snapshot, for the three generators that carry a profile.
P_MAX_PU = {
    'Manchester Wind': [0.930019875, 0.4857475804, 0.2336917351, 0.2576042221, 0.6269055694, 0.6035984088, 0.6789075462, 0.3613026112, 0.6216040549, 0.5215183715],
    'Norway Wind': [0.9745832033, 0.4812903778, 0.4072258018, 0.5999649628, 0.524468219, 0.0096927054, 0.2204533621, 0.8239185004, 0.5562297265, 0.4394160378],
    'Frankfurt Wind': [0.5590784039, 0.7529103711, 0.1234650887, 0.9666766524, 0.8590078044, 0.5261537924, 0.077893008, 0.0590234716, 0.2485544952, 0.1080601728],
}  # fmt: skip

#: Demand per snapshot, for each of the six loads.
P_SET = {
    'London': [35.7962441027, 976.8245614698, 250.5873120464, 130.7531445827, 151.1001686, 931.857051942, 289.8482871447, 864.3433217147, 689.5772637703, 627.8789859434],
    'Frankfurt': [398.0478469638, 432.4361062425, 379.8039282662, 868.3617642835, 548.7707546221, 828.6652426012, 449.2907519075, 699.1637663734, 915.8667802518, 414.8876464034],
    'Norway': [820.035835936, 854.8340468618, 42.550744351, 647.5482327851, 884.0738733306, 509.0624485516, 595.6079648147, 291.6424496984, 2.1534925491, 760.7401765038],
    'Norwich': [415.4625642653, 262.6061464526, 418.4763531902, 552.9595393098, 218.159858091, 791.9762655836, 531.8706808219, 23.5134667186, 970.0590684572, 0.9248336907],
    'Bremen': [640.0863775411, 703.554333706, 440.8361303183, 612.5763056818, 803.4367808051, 605.4006873582, 641.0905902397, 408.0085411725, 912.2477761646, 898.0530916423],
    'Manchester': [857.5514402011, 750.5996237166, 156.5648760141, 527.8708221189, 83.8977589634, 676.6233193474, 731.1371004827, 553.3448891847, 298.338082262, 768.2905859888],
}  # fmt: skip


def build():
    """The example network, stated as the calls that build it.

    A rung states its data inline, so that the PyPSA model under review is the
    script — ``reference.py`` says so and ``test_pypsa_references.py`` checks
    it. The numbers here are PyPSA's own ``ac_dc_meshed``, which is where this
    rung's published objective comes from; ``reference.py`` pins the version
    they were read at.
    """
    import pypsa

    n = pypsa.Network()
    n.set_snapshots(SNAPSHOTS)
    # Bus
    n.add('Bus', 'London', v_nom=380.0, x=-0.13, y=51.5)
    n.add('Bus', 'Norwich', v_nom=380.0, x=1.3, y=52.6)
    n.add('Bus', 'Norwich DC', v_nom=200.0, x=1.3, y=52.5, carrier='DC')
    n.add('Bus', 'Manchester', v_nom=380.0, x=-2.2, y=53.47)
    n.add('Bus', 'Bremen', v_nom=380.0, x=8.8, y=53.08)
    n.add('Bus', 'Bremen DC', v_nom=200.0, x=8.8, y=52.98, carrier='DC')
    n.add('Bus', 'Frankfurt', v_nom=380.0, x=8.7, y=50.12)
    n.add('Bus', 'Norway', v_nom=380.0, x=10.75, y=60.0)
    n.add('Bus', 'Norway DC', v_nom=200.0, x=10.75, y=60.0, carrier='DC')
    # Carrier
    n.add('Carrier', 'gas', co2_emissions=0.24, color='red')
    n.add('Carrier', 'wind', color='blue')
    n.add('Carrier', 'battery', color='green')
    n.add('Carrier', 'load', color='black')
    n.add('Carrier', 'AC', color='orange')
    n.add('Carrier', 'DC', color='purple')
    # Generator
    n.add(
        'Generator',
        'Manchester Wind',
        bus='Manchester',
        p_nom=80.0,
        p_nom_extendable=True,
        p_nom_min=100.0,
        p_max_pu=P_MAX_PU['Manchester Wind'],
        carrier='wind',
        marginal_cost=0.11,
        capital_cost=2793.6516029328,
    )
    n.add(
        'Generator',
        'Manchester Gas',
        bus='Manchester',
        p_nom=50000.0,
        p_nom_extendable=True,
        carrier='gas',
        marginal_cost=4.5323676307,
        capital_cost=196.6151679691,
        efficiency=0.3500264336,
    )
    n.add(
        'Generator',
        'Norway Wind',
        bus='Norway',
        p_nom=100.0,
        p_nom_extendable=True,
        p_nom_min=100.0,
        p_max_pu=P_MAX_PU['Norway Wind'],
        carrier='wind',
        marginal_cost=0.09,
        capital_cost=2184.3747960912,
    )
    n.add(
        'Generator',
        'Norway Gas',
        bus='Norway',
        p_nom=20000.0,
        p_nom_extendable=True,
        carrier='gas',
        marginal_cost=5.8928445406,
        capital_cost=158.2512497168,
        efficiency=0.3568363832,
    )
    n.add(
        'Generator',
        'Frankfurt Wind',
        bus='Frankfurt',
        p_nom=110.0,
        p_nom_extendable=True,
        p_nom_min=100.0,
        p_max_pu=P_MAX_PU['Frankfurt Wind'],
        carrier='wind',
        marginal_cost=0.1,
        capital_cost=2129.4561224763,
    )
    n.add(
        'Generator',
        'Frankfurt Gas',
        bus='Frankfurt',
        p_nom=80000.0,
        p_nom_extendable=True,
        carrier='gas',
        marginal_cost=4.0863219899,
        capital_cost=102.6769530076,
        efficiency=0.3516658529,
    )
    # Line
    n.add(
        'Line',
        '0',
        bus0='London',
        bus1='Manchester',
        x=0.7968782824,
        s_nom=40000.0,
        s_nom_extendable=True,
        capital_cost=0.1367157553,
        carrier='AC',
    )
    n.add(
        'Line',
        '1',
        bus0='Manchester',
        bus1='Norwich',
        x=0.3915599178,
        s_nom=40000.0,
        s_nom_extendable=True,
        capital_cost=0.1334916779,
        carrier='AC',
    )
    n.add(
        'Line',
        '2',
        bus0='Bremen DC',
        bus1='Norwich DC',
        r=0.2126041927,
        s_nom=40000.0,
        s_nom_extendable=True,
        capital_cost=0.0086734246,
        carrier='AC',
    )
    n.add(
        'Line',
        '3',
        bus0='Norwich DC',
        bus1='Norway DC',
        r=0.4861637504,
        s_nom=40000.0,
        s_nom_extendable=True,
        capital_cost=0.1291260515,
        carrier='AC',
    )
    n.add(
        'Line',
        '4',
        bus0='Norway DC',
        bus1='Bremen DC',
        r=0.4287266497,
        s_nom=40000.0,
        s_nom_extendable=True,
        capital_cost=0.0624298729,
        carrier='AC',
    )
    n.add(
        'Line',
        '5',
        bus0='Norwich',
        bus1='London',
        x=0.2388003463,
        s_nom=40000.0,
        s_nom_extendable=True,
        capital_cost=0.0218524519,
        carrier='AC',
    )
    n.add(
        'Line',
        '6',
        bus0='Bremen',
        bus1='Frankfurt',
        x=0.4,
        s_nom=40000.0,
        s_nom_extendable=True,
        capital_cost=0.2,
        carrier='AC',
    )
    # Link
    n.add(
        'Link',
        'Norwich Converter',
        bus0='Norwich',
        bus1='Norwich DC',
        carrier='DC',
        p_nom=1000.0,
        p_nom_extendable=True,
        p_min_pu=-0.9,
        p_max_pu=0.9,
        capital_cost=0.21,
    )
    n.add(
        'Link',
        'Norway Converter',
        bus0='Norway',
        bus1='Norway DC',
        carrier='DC',
        p_nom=1000.0,
        p_nom_extendable=True,
        p_min_pu=-0.9,
        p_max_pu=0.9,
        capital_cost=0.2,
    )
    n.add(
        'Link',
        'Bremen Converter',
        bus0='Bremen',
        bus1='Bremen DC',
        carrier='DC',
        p_nom=1000.0,
        p_nom_extendable=True,
        p_min_pu=-0.9,
        p_max_pu=0.9,
        capital_cost=0.19,
    )
    n.add(
        'Link',
        'DC link',
        bus0='London',
        bus1='Bremen',
        carrier='DC',
        p_nom=1000.0,
        p_nom_extendable=True,
        p_min_pu=-0.9,
        p_max_pu=0.9,
        capital_cost=0.8765342,
    )
    # Load
    n.add('Load', 'London', bus='London', carrier='load', p_set=P_SET['London'])
    n.add('Load', 'Frankfurt', bus='Frankfurt', carrier='load', p_set=P_SET['Frankfurt'])
    n.add('Load', 'Norway', bus='Norway', carrier='load', p_set=P_SET['Norway'])
    n.add('Load', 'Norwich', bus='Norwich', carrier='load', p_set=P_SET['Norwich'])
    n.add('Load', 'Bremen', bus='Bremen', carrier='load', p_set=P_SET['Bremen'])
    n.add('Load', 'Manchester', bus='Manchester', carrier='load', p_set=P_SET['Manchester'])
    # GlobalConstraint
    n.add('GlobalConstraint', 'co2_limit', sense='<=', constant=1000.0)
    return n
```

</details>
<!-- reference:rung_11_ac_dc_meshed:end -->

### Rung 13 — transmission losses

`n.optimize(transmission_losses=...)`: a line dissipates a loss its flow buys,
held above a fan of cuts to the quadratic loss curve `r_pu_eff * p**2`, half
charged at either end of the line. PyPSA has two modes, and both build the same
rows `loss + slope * flow >= offset` and `loss - slope * flow >= offset`, one
pair per cut: `{'mode': 'tangents', 'segments': K}` takes `K` tangents at
`p_k = k / K` of the rating, slope `2 r p_k`; `True`, or
`{'mode': 'secants', 'atol': 1, 'rtol': 0.1, 'max_segments': 20}`, takes the
secants between consecutive breakpoints `p_k, p_k+1`, slope `r (p_k + p_k+1)`
and offset `-r p_k p_k+1`, the breakpoints placed from `p_0 = 0` by a step
`max(k / (k - 1), 1 + 2 (rtol + sqrt(rtol + rtol**2)))` until the rating is
covered (`constraints.py:2545`). The mode therefore only decides how data prep
fills `Line_loss_slope` and `Line_loss_offset` over the `segment` axis, and the
breakpoint loop is data prep with them. The loss variable, its cap and the cut
rows exist only where `transmission_losses` is on. A plain run leaves the flag
off and supplies no segments, so the loss is absent and reads as zero in the
balance, and the model collapses to the lossless one.

| PyPSA | status | note |
| --- | --- | --- |
| [`Line-loss`, `Transformer-loss`](#variable-domains) | done | absent, and zero in the balance, where lossless |
| [`Line-fix-s-*`, `Line-ext-s-*`](#line-fix-s-lower), [`Transformer-fix-s-*`, `Transformer-ext-s-*`](#transformer-fix-s-lower) | done | the loss counted against the rating |
| [`Bus-nodal_balance`](#bus-nodal_balance) | done | half of each incident line's and transformer's loss at either end |
| [`Line-loss_upper`](#line-loss_upper), [`Transformer-loss_upper`](#transformer-loss_upper) | done | `loss_max` is data prep, see X4 |
| [`Line-loss_tangents-{k}-1`](#line-loss_tangents-k-1), [`Transformer-loss_tangents-{k}-1`](#transformer-loss_tangents-k-1) | split | PyPSA names a row per segment; one block over the dimension |
| [`Line-loss_tangents-{k}--1`](#line-loss_tangents-k--1), [`Transformer-loss_tangents-{k}--1`](#transformer-loss_tangents-k--1) | split | |
| [`Line-loss_secants-pos`, `Line-loss_secants-neg`](#line-loss_tangents-k-1), [`Transformer-loss_secants-pos`, `Transformer-loss_secants-neg`](#transformer-loss_tangents-k-1) | done | the same two blocks in the secant mode; slope, offset and the breakpoint loop are data prep; rungs 19 and 23 record it |

<!-- reference:rung_13_losses:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `10645.295879552297`, 150 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_13_losses.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 13: transmission losses in tangent form — a loss per line."""

from __future__ import annotations

import spine

OPTIMIZE = {'transmission_losses': {'mode': 'tangents', 'segments': 2}}


def build():
    """The spine plus a 110 kV triangle of lines, one of them extendable — ohms a real line has, so the loss stays a few percent of the flow."""
    n = spine.build()
    n.add('Bus', ['a', 'b', 'c'], v_nom=110)
    n.add('Generator', 'hydro13', bus='a', p_nom=80, marginal_cost=10)
    n.add('Generator', 'diesel13', bus='b', p_nom=80, marginal_cost=50)
    n.add('Line', 'ab13', bus0='a', bus1='b', carrier='AC', x=30, r=6, s_nom=60)
    n.add('Line', 'bc13', bus0='b', bus1='c', carrier='AC', x=60, r=9.7, s_nom=60)
    n.add(
        'Line',
        'ca13',
        bus0='c',
        bus1='a',
        carrier='AC',
        x=45,
        r=6,
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

The same triangle solved in the secant mode records the identical loss rows,
its cuts placed by PyPSA's tolerance loop rather than fixed per segment.

<!-- reference:rung_19_losses_secants:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `10840.926895402912`, 150 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_19_losses_secants.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 19: transmission losses in secant form — the same loss per line, its cuts placed by PyPSA's tolerance loop."""

from __future__ import annotations

import spine

OPTIMIZE = {'transmission_losses': {'mode': 'secants', 'atol': 1, 'rtol': 0.1, 'max_segments': 20}}


def build():
    """Rung 13's 110 kV triangle, unchanged, so the two modes differ only in the cuts."""
    n = spine.build()
    n.add('Bus', ['a', 'b', 'c'], v_nom=110)
    n.add('Generator', 'hydro19', bus='a', p_nom=80, marginal_cost=10)
    n.add('Generator', 'diesel19', bus='b', p_nom=80, marginal_cost=50)
    n.add('Line', 'ab19', bus0='a', bus1='b', carrier='AC', x=30, r=6, s_nom=60)
    n.add('Line', 'bc19', bus0='b', bus1='c', carrier='AC', x=60, r=9.7, s_nom=60)
    n.add(
        'Line',
        'ca19',
        bus0='c',
        bus1='a',
        carrier='AC',
        x=45,
        r=6,
        s_nom=40,
        s_nom_extendable=True,
        s_nom_max=90,
        capital_cost=4,
    )
    n.add('Load', 'town19', bus='c', p_set=[35, 55, 15, 45])
    return n
```

</details>
<!-- reference:rung_19_losses_secants:end -->

### Rung 14 — two-stage stochastic

Two futures and a risk preference: `n.set_scenarios(...)` with
`n.set_risk_preference(alpha, omega)`. Everything over a snapshot spans a
scenario as well. Capacity does not, because it is chosen once before the
future is known. The operating cost is the expectation over the scenarios'
weights. A risk preference adds the CVaR (conditional value at risk) rows: an
excess per scenario and the tail's average, blended into the objective at
`omega`. PyPSA builds neither row without a risk preference
(`optimize.py:458`). The file builds them only where `omega` is positive, so a
plain run, and a risk preference with `omega = 0`, has none.

A parameter spans `scenario` exactly when PyPSA reads it per scenario. PyPSA
reads component data through `c.da`, one value per scenario
(`components/array.py:332-395`), so almost every parameter spans one. It
refuses a difference in the attributes that fix the network's shape, such as
`bus`, `carrier`, `lifetime`, `active`, `committable` or `p_nom_extendable`
(`consistency.py:1174-1195`), and these parameters and what data prep derives
from them span none. Some other parameters span none either. PyPSA reduces
`maintainable` to a union over the scenarios, `(p_min_pu >= 0).all()` over
them, and a carrier's growth limits to their least value
(`components.py:1016-1019`, `constraints.py:397-401`,
`global_constraints.py:226-230`). It builds the cycle basis from the first
scenario (`networks.py:1354-1361`). A link's delay and a transformer's phase
shift span none, because PyPSA `1.3.0` mishandles them over scenarios (rung
41). A branch's `BODF` spans none, because PyPSA refuses a
security-constrained run over scenarios. This rung's wind `p_max_pu` differs by scenario, and the file states it over
`scenario`. Rungs 41 and 42 make operating data and first-stage data differ.

| PyPSA | status | note |
| --- | --- | --- |
| [`Generator-p`, `Link-p`](#variable-domains) | done | over `scenario`; `Generator-p_nom` is not — chosen once |
| [`Generator-fix-p-*`, `-ext-p-*`, `Link-fix-p-*`, `Bus-nodal_balance`](#generator-fix-p-lower) | done | rungs 1 and 3, over `scenario` |
| [`CVaR-a`, `CVaR-theta`, `CVaR`](#variable-domains) | done | |
| [`CVaR-excess-{s}`](#cvar-excess-s) | split | PyPSA names a row per scenario; one block over the dimension; none where `omega` is zero |
| [`CVaR-def`](#cvar-def) | done | `1 / (1 - alpha)` is data prep; none where `omega` is zero |
| [objective](#objective) | done | capacity once, at its capital cost in expectation over the scenarios; operation `(1 - omega)` in expectation, `omega` at the tail |
| `Generator-p_max_pu` and other component data per scenario | done | every parameter PyPSA reads per scenario spans `scenario`; operating data in rung 41, first-stage bounds and capital cost in rung 42 |

<!-- reference:rung_14_stochastic:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `9267.386666666665`, 87 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_14_stochastic.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 14: two futures and a risk preference — capacity chosen once, dispatch per scenario."""

from __future__ import annotations

import spine


def build():
    """The spine plus an extendable wind unit whose availability and the south's load differ between a calm and a stormy future."""
    n = spine.build()
    n.add('Generator', 'wind14', bus='south', p_nom_extendable=True, p_nom_max=100, marginal_cost=1, capital_cost=20)
    n.add('Load', 'port14', bus='south')
    n.set_scenarios({'calm': 0.6, 'stormy': 0.4})
    n.c.loads.dynamic.p_set[('calm', 'port14')] = [10, 20, 15, 10]
    n.c.loads.dynamic.p_set[('stormy', 'port14')] = [40, 60, 50, 30]
    n.c.generators.dynamic.p_max_pu[('calm', 'wind14')] = [0.9, 0.7, 0.8, 0.6]
    n.c.generators.dynamic.p_max_pu[('stormy', 'wind14')] = [0.3, 0.2, 0.4, 0.1]
    n.set_risk_preference(alpha=0.5, omega=0.3)
    return n
```

</details>
<!-- reference:rung_14_stochastic:end -->

### Rung 15 — investment periods

`n.optimize(multi_investment_periods=True)`. A snapshot belongs to an
investment period. An asset stands in the periods its build year and lifetime
span. Capacity is paid once per period the asset stands in, and each period
carries a weight. A carrier may grow only so much per period. Which snapshots
an asset is active in is data prep, because a `where` reaches only the frame's
own dimensions.

| PyPSA | status | note |
| --- | --- | --- |
| [`Generator-p`](#variable-domains) | done | where the generator stands in the snapshot's period — `active`, data prep |
| [`Generator-fix-p-*`, `-ext-p-*`, `-ext-p_nom-*`](#generator-fix-p-lower) | done | rungs 1 and 3, masked by `active` |
| [`Carrier-growth_limit`](#carrier-growth_limit) | done | every extendable component of the carrier, counted in the first period a build stands in; `edge=0` at the first period |
| [`Carrier-growth_limit`](#carrier-growth_limit) with a negative `max_relative_growth` | done | rung 39 |
| [`Carrier-growth_limit`](#carrier-growth_limit) without `multi_investment_periods` | done | rung 49; not built, so data prep feeds no `max_growth` |
| [objective](#objective) | done | period weight on operation; capacity once per period it stands in |
| [`StorageUnit-energy_balance`](#storageunit-energy_balance), [`Store-energy_balance`](#store-energy_balance) per period, ramps at period starts | done | rung 29 |
| [`StorageUnit-energy_balance`](#storageunit-energy_balance), [`Store-energy_balance`](#store-energy_balance) for storage built in a later period or retired early | done | rung 32 |
| [`primary_energy`](#primary_energy), [`operational_limit`](#operational_limit) for one investment period, weighted by period years | done | rung 35 |
| [link and process `delay`, `cyclic_delay`](#bus-nodal_balance) per investment period | done | rung 38 |

<!-- reference:rung_15_multi_period:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `12747.19109626398`, 80 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_15_multi_period.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 15: two investment periods — build years, lifetimes, period weights and a carrier's growth limit."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

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

### Rung 16 — link delay

A source feeding two sinks over links whose energy arrives late. PyPSA's
`delay` lags a port's delivery by a number of snapshots, and `cyclic_delay`
says whether the flow still in transit at the horizon's edge wraps to the start
or is lost. The two are a per-link number and a per-link kind, so the balance
turns them on with a `cases:` block over `shift(…, offset=Link_output_delay,
edge=…)` — one arm wrapping (`edge='wrap'`), the other vacating (`edge=0`).

This is the one rung whose `generators` weighting is uniform. PyPSA measures
`delay` in those units, so a uniform column makes a delay of `n` a shift of
exactly `n` snapshot positions, which a positional `shift` reproduces. Under a
non-uniform column PyPSA resamples by elapsed time rather than by position — a
shift that varies along the snapshot axis, above what `shift` states (#299).

| PyPSA                     | status | note                                            |
| ------------------------- | ------ | ----------------------------------------------- |
| [link `delay`, `cyclic_delay`](#bus-nodal_balance) | done | a `cases:` on `cyclic_delay` over `shift(offset=delay)`, at uniform `generators` weighting; supersedes #75 |

<!-- reference:rung_16_link_delay:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `5262.5`, 52 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_16_link_delay.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 16: link delay — a source feeding two sinks over links whose energy arrives late, one wrapping cyclically and one losing what is still in transit at the horizon's edge."""

from __future__ import annotations

from datetime import datetime

#: Four hourly stamps. The `generators` weighting is uniform here, and only here
#: on the ladder, because PyPSA measures `delay` in those units: a uniform column
#: makes a delay of `n` a shift of exactly `n` snapshot positions, which is what a
#: positional `shift(offset=n)` reproduces. The `objective` and `stores` columns
#: stay non-uniform, so no cost or storage factor passes as identity.
SNAPSHOTS = [datetime(2015, 1, 1, hour) for hour in range(4)]
WEIGHTINGS = {'objective': [2.0, 1.5, 2.5, 3.0], 'stores': [0.5, 2.0, 1.5, 2.5], 'generators': [1.0, 1.0, 1.0, 1.0]}

#: Each sink carries the same demand, so the only thing that separates their cost
#: is how each link treats the horizon's edge.
DEMAND = [20.0, 15.0, 25.0, 10.0]


def build():
    """A source, two delayed links, and two sinks, stated as the calls that build it.

    ``pipe_wrap`` delays by two snapshots and wraps cyclically, so every unit the
    cheap source sends reaches its sink and the expensive backup stays dark.
    ``pipe_lose`` delays by one and does not wrap, so the flow that would arrive
    in the first snapshot is lost and that snapshot's demand falls to the backup.
    The two links differ in both a per-link number (`delay`) and a per-link kind
    (`cyclic_delay`), which is what the spec's ``cases:`` block turns on.
    """
    import pypsa

    n = pypsa.Network()
    n.set_snapshots(SNAPSHOTS)
    for column, values in WEIGHTINGS.items():
        n.snapshot_weightings[column] = values
    n.add('Bus', 'source')
    n.add('Bus', 'sink_wrap')
    n.add('Bus', 'sink_lose')
    n.add('Generator', 'spring', bus='source', p_nom=200, marginal_cost=5)
    n.add('Generator', 'backup_wrap', bus='sink_wrap', p_nom=200, marginal_cost=100)
    n.add('Generator', 'backup_lose', bus='sink_lose', p_nom=200, marginal_cost=100)
    n.add('Link', 'pipe_wrap', bus0='source', bus1='sink_wrap', p_nom=100, delay=2, cyclic_delay=True)
    n.add('Link', 'pipe_lose', bus0='source', bus1='sink_lose', p_nom=100, delay=1, cyclic_delay=False)
    n.add('Load', 'load_wrap', bus='sink_wrap', p_set=DEMAND)
    n.add('Load', 'load_lose', bus='sink_lose', p_set=DEMAND)
    return n
```

</details>
<!-- reference:rung_16_link_delay:end -->

### Rung 17 — process

A process is a generalized converter. It moves an internal power from `bus0` to
the buses it feeds, and each port draws or delivers at its own `rate`. A
non-extendable process carries a fixed capacity. An extendable one chooses its
capacity between `p_nom_min` and `p_nom_max`. A ramp limit caps the change in
internal power between snapshots. A `p_set` fixes an internal power schedule. A
`p_nom_set` fixes an extendable process's built capacity. The machinery is the
generator's and the link's, read over a converter.

| PyPSA | status | note |
| --- | --- | --- |
| [`Process-p`, `Process-p_nom`](#variable-domains) | done | internal power and capacity, as a link |
| [`Process-fix-p-*`, `-ext-p-*`, `-ext-p_nom-*`](#process-fix-p-lower) | done | rungs 1 and 3, over a converter |
| [`Process-p-ramp_limit_*`](#process-p-ramp_limit_up) | done | rung 4, on a non-committable converter; committed in rung 26 |
| [`Process-p_set`](#process-p_set) | done | a fixed internal power schedule |
| [`Process-p_nom_set`](#process-p_nom_set) | done | a fixed built capacity |
| [`Bus-nodal_balance`](#bus-nodal_balance) | done | each port enters at its `rate` |
| [objective](#objective) | done | marginal cost on internal power; capital on capacity |

<!-- reference:rung_17_process:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `9730.0`, 70 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_17_process.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 17: process — generalized converters, one fixed and ramping, one extendable, one on a set schedule, all feeding a hub."""

from __future__ import annotations

from math import nan

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', 'hub')
    n.add(
        'Process',
        'conv_fix',
        bus0='north',
        bus1='hub',
        p_nom=50,
        marginal_cost=2,
        ramp_limit_up=0.3,
        ramp_limit_down=0.3,
    )
    n.add(
        'Process',
        'conv_ext',
        bus0='south',
        bus1='hub',
        p_nom_extendable=True,
        capital_cost=20,
        p_nom_min=5,
        p_nom_max=40,
        marginal_cost=1,
        p_nom_set=25,
    )
    n.add('Process', 'conv_set', bus0='north', bus1='hub', p_nom=20, marginal_cost=3, p_set=[10, nan, nan, nan])
    n.add('Load', 'hub_load', bus='hub', p_set=[15, 20, 25, 10])
    return n
```

</details>
<!-- reference:rung_17_process:end -->

### Rung 18 — transformer

A transformer is a passive branch between two buses, as a line is, but its flow
follows its effective series reactance and a phase shift, fixed or optimised. It
obeys the Kirchhoff voltage law (KVL) around every independent cycle, so it
builds no flow outside a mesh. A non-extendable transformer carries a fixed
nominal apparent power. An extendable one chooses it between `s_nom_min` and
`s_nom_max`. An `s_set` fixes a flow schedule. An `s_nom_set` fixes an extendable
transformer's built capacity.

| PyPSA | status | note |
| --- | --- | --- |
| [`Transformer-s`, `Transformer-s_nom`](#variable-domains) | done | flow and capacity, as a line |
| [`Transformer-fix-s-*`, `-ext-s-*`, `-ext-s_nom-*`](#transformer-fix-s-lower) | done | rungs 1 and 3, over a transformer |
| [`Transformer-s_set`](#transformer-s_set) | done | a fixed flow schedule |
| [`Transformer-s_nom_set`](#transformer-s_nom_set) | done | a fixed built capacity |
| [`Kirchhoff-Voltage-Law`](#kirchhoff-voltage-law) | done | rung 6, over `x_pu_eff` and a phase shift |
| [`Transformer-phase_shift`](#variable-domains) | done | rung 20, an optimised phase shift |
| [objective](#objective) | done | capital on capacity |

<!-- reference:rung_18_transformer:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `12274.401472395122`, 106 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_18_transformer.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 18: transformer — passive branches under KVL in a meshed triangle, one fixed and on a set flow, two extendable in parallel."""

from __future__ import annotations

from math import nan

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', 'a')
    n.add('Bus', 'b')
    n.add('Bus', 'c')
    n.add('Generator', 'hydro18', bus='a', p_nom=80, marginal_cost=10)
    n.add('Generator', 'diesel18', bus='b', p_nom=80, marginal_cost=50)
    n.add('Load', 'town18', bus='c', p_set=45)
    n.add('Line', 'ab', bus0='a', bus1='b', carrier='AC', length=30, x=0.1, r=0.01, s_nom=60)
    n.add(
        'Transformer',
        'bc',
        bus0='b',
        bus1='c',
        x=0.1,
        r=0.01,
        s_nom=60,
        phase_shift=10,
        s_set=[16, nan, nan, nan],
    )
    n.add(
        'Transformer',
        'ca',
        bus0='c',
        bus1='a',
        x=0.15,
        r=0.01,
        s_nom=60,
        s_nom_extendable=True,
        capital_cost=10,
        s_nom_min=5,
        s_nom_max=40,
        s_nom_set=30,
        tap_ratio=1.05,
    )
    n.add(
        'Transformer',
        'ca2',
        bus0='c',
        bus1='a',
        x=0.12,
        r=0.01,
        s_nom=60,
        s_nom_extendable=True,
        capital_cost=8,
        s_nom_min=5,
        s_nom_max=40,
    )
    return n
```

</details>
<!-- reference:rung_18_transformer:end -->

### Rung 20 — phase shifter

A phase-shifting transformer's voltage angle shift is a per-snapshot decision
where its `phase_shift_min` sits below its `phase_shift_max`, bounded between the
two in degrees. The shift enters the same KVL cycle sum as a fixed one, so it
redistributes the flows around a cycle without moving active power. Here the
shift holds the transformer at its rating while the upstream unit serves the
whole varying load, and the fixed `phase_shift` gives way to it.

<!-- reference:rung_20_phase_shifter:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `16455.0`, 88 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_20_phase_shifter.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 20: phase shifter — a transformer whose per-snapshot phase shift is optimised, holding it at its rating and rerouting the surplus around the cycle.

The parallel lines carry low reactance, so a few degrees of shift move tens of
megawatts: the phase-shifting transformer keeps its flow at its ``s_nom`` while
the upstream hydro serves the whole varying load, and the costly local unit
stays off. A fixed shift could not follow the load, so the shift is a decision.
"""

from __future__ import annotations

import spine


def build():
    """The spine plus a triangle where a phase-shifting transformer reroutes cheap power around a binding leg, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', ['a', 'b', 'c'])
    n.add('Generator', 'hydro20', bus='a', p_nom=300, marginal_cost=10)
    n.add('Generator', 'diesel20', bus='c', p_nom=300, marginal_cost=200)
    n.add('Load', 'town20', bus='c', p_set=[90, 75, 120, 105])
    n.add('Line', 'ab20', bus0='a', bus1='b', carrier='AC', x=0.002, r=0.0002, s_nom=120)
    n.add('Line', 'bc20', bus0='b', bus1='c', carrier='AC', x=0.002, r=0.0002, s_nom=120)
    n.add(
        'Transformer',
        'ca20',
        bus0='c',
        bus1='a',
        x=0.002,
        r=0.0002,
        s_nom=40,
        phase_shift_min=-30,
        phase_shift_max=30,
    )
    return n
```

</details>
<!-- reference:rung_20_phase_shifter:end -->

### Rung 21 — carrier growth

A carrier's `max_growth` caps what it adds in an investment period, across every
extendable component of that carrier, not the generators alone. Here a battery
carrier caps a storage unit and a store built in the first period, and the two
builds fill the cap together. A store built in the later period adds its
allowance plus half of what the carrier added before. PyPSA counts the
components that carry a carrier attribute, and so does the spec, so a
transformer counts in no carrier.

<!-- reference:rung_21_carrier_growth:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `8452.5`, 74 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_21_carrier_growth.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 21: a carrier's growth limit binds its non-generator builds — a storage unit and two stores over two periods."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

OPTIMIZE = {'multi_investment_periods': True}


def build():
    """A whole network, not the spine: cheap solar only at the first snapshot of each period, so battery capacity pays off but its growth is capped."""
    import pypsa

    n = pypsa.Network()
    n.snapshots = pd.MultiIndex.from_tuples(
        [(2020, datetime(2020, 1, 1, t)) for t in range(2)] + [(2030, datetime(2030, 1, 1, t)) for t in range(2)]
    )
    n.investment_periods = [2020, 2030]
    n.investment_period_weightings['objective'] = [1.0, 0.5]
    n.investment_period_weightings['years'] = [10.0, 10.0]
    n.snapshot_weightings['objective'] = [2.0, 1.5, 2.5, 2.0]
    n.add('Bus', 'grid')
    n.add('Carrier', 'solar')
    n.add('Carrier', 'gas')
    n.add('Carrier', 'battery', max_growth=20, max_relative_growth=0.5)
    n.add('Generator', 'solar', bus='grid', carrier='solar', p_nom=100, marginal_cost=1, p_max_pu=[1, 0, 1, 0])
    n.add('Generator', 'backup', bus='grid', carrier='gas', p_nom=200, marginal_cost=80)
    n.add(
        'StorageUnit',
        'bat20',
        bus='grid',
        carrier='battery',
        p_nom_extendable=True,
        p_nom_max=100,
        max_hours=4,
        capital_cost=50,
        build_year=2020,
        lifetime=30,
    )
    n.add(
        'Store',
        'tank20',
        bus='grid',
        carrier='battery',
        e_nom_extendable=True,
        e_nom_max=10,
        capital_cost=10,
        build_year=2020,
        lifetime=30,
    )
    n.add(
        'Store',
        'tank30',
        bus='grid',
        carrier='battery',
        e_nom_extendable=True,
        e_nom_max=100,
        capital_cost=8,
        build_year=2030,
        lifetime=30,
    )
    n.add('Load', 'town', bus='grid', p_set=[40, 60, 40, 80])
    return n
```

</details>
<!-- reference:rung_21_carrier_growth:end -->

### Rung 22 — transformer losses

PyPSA applies the loss of rung 13 to every passive branch, so a transformer
dissipates a loss as a line does: its own loss variable, the loss counted
against its rating, its cap and its fan of cuts, and half of it at either end
in the balance. The loss curve is `r_pu_eff * p**2`, where a transformer's
`r_pu_eff` is its resistance over its given `s_nom`, times its tap ratio
(`power_flow.py:815`). The given `s_nom` sets it also for an extendable
transformer, whose build does not move the curve. Here the loss of the
extendable transformer is counted against its rating, so it builds more than
the flow it carries.

<!-- reference:rung_22_transformer_losses:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `10643.477135410736`, 174 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_22_transformer_losses.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 22: transformer losses in tangent form — a loss per transformer, as per line."""

from __future__ import annotations

import spine

OPTIMIZE = {'transmission_losses': {'mode': 'tangents', 'segments': 3}}


def build():
    """The spine plus a triangle of one 110 kV line and two transformers, one extendable and off-nominal tap, per-unit resistances a real transformer has, so its loss stays a few percent of the flow."""
    n = spine.build()
    n.add('Bus', ['a', 'b', 'c'], v_nom=110)
    n.add('Generator', 'hydro22', bus='a', p_nom=80, marginal_cost=10)
    n.add('Generator', 'diesel22', bus='b', p_nom=80, marginal_cost=50)
    n.add('Line', 'ab22', bus0='a', bus1='b', carrier='AC', x=30, r=6, s_nom=60)
    n.add('Transformer', 'bc22', bus0='b', bus1='c', x=0.1, r=0.03, s_nom=60)
    n.add(
        'Transformer',
        'ca22',
        bus0='c',
        bus1='a',
        x=0.12,
        r=0.02,
        s_nom=40,
        s_nom_extendable=True,
        s_nom_max=90,
        capital_cost=4,
        tap_ratio=1.05,
    )
    n.add('Load', 'town22', bus='c', p_set=[35, 55, 15, 45])
    return n
```

</details>
<!-- reference:rung_22_transformer_losses:end -->

The same triangle solved in the secant mode records the identical loss rows,
its cuts placed by PyPSA's tolerance loop.

<!-- reference:rung_23_transformer_losses_secants:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `10821.999155213578`, 142 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_23_transformer_losses_secants.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 23: transformer losses in secant form — the same loss per transformer, its cuts placed by PyPSA's tolerance loop."""

from __future__ import annotations

import spine

OPTIMIZE = {'transmission_losses': {'mode': 'secants', 'atol': 1, 'rtol': 0.1, 'max_segments': 20}}


def build():
    """Rung 22's triangle, unchanged, so the two modes differ only in the cuts."""
    n = spine.build()
    n.add('Bus', ['a', 'b', 'c'], v_nom=110)
    n.add('Generator', 'hydro23', bus='a', p_nom=80, marginal_cost=10)
    n.add('Generator', 'diesel23', bus='b', p_nom=80, marginal_cost=50)
    n.add('Line', 'ab23', bus0='a', bus1='b', carrier='AC', x=30, r=6, s_nom=60)
    n.add('Transformer', 'bc23', bus0='b', bus1='c', x=0.1, r=0.03, s_nom=60)
    n.add(
        'Transformer',
        'ca23',
        bus0='c',
        bus1='a',
        x=0.12,
        r=0.02,
        s_nom=40,
        s_nom_extendable=True,
        s_nom_max=90,
        capital_cost=4,
        tap_ratio=1.05,
    )
    n.add('Load', 'town23', bus='c', p_set=[35, 55, 15, 45])
    return n
```

</details>
<!-- reference:rung_23_transformer_losses_secants:end -->

### Rung 24 — must stay down

A committable unit that stopped `down_time_before` snapshots before the horizon
stays off until its `min_down_time` has passed. PyPSA fixes its status to zero
in the first `min_down_time - down_time_before` snapshots. Here the cheapest
unit in the network brought one snapshot of a three-snapshot down time into
the horizon, so it stays off for two snapshots and the dearer coal unit serves
the load.

<!-- reference:rung_24_must_stay_down:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `9007.5`, 65 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_24_must_stay_down.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 24: must stay down — a committable unit still serving the down time it brought in stays off."""

from __future__ import annotations

import spine


def build():
    """The spine plus a cheap committable unit that stopped one snapshot before the horizon and must stay off for three."""
    n = spine.build()
    n.add(
        'Generator',
        'warm',
        bus='north',
        committable=True,
        p_nom=50,
        marginal_cost=5,
        p_min_pu=0.2,
        min_down_time=3,
        up_time_before=0,
        down_time_before=1,
        start_up_cost=20,
    )
    n.add('Load', 'swing24', bus='north', p_set=[25, 45, 45, 10])
    return n
```

</details>
<!-- reference:rung_24_must_stay_down:end -->

### Rung 25 — committable links

A committable link carries the generator's whole unit commitment over its flow.
PyPSA builds the same status, transition, up time, down time, must-stay,
big-M, modular and ramp rows for a `Link` as for a `Generator`, and prices its
starts, stops and stand-by snapshots the same way. Here an east bus is served
only by committable links. `hvdc` brought one snapshot of a three-snapshot up
time into the horizon, so it stays on for two snapshots although a cheaper link
could carry the load. `cold_tie` brought one snapshot of a three-snapshot down
time, so it stays off for two snapshots. Its own two-snapshot up time would
then hold it on into the last snapshot, where the load is below its minimum, so
it does not start at all. The other links are committable builds that are
extendable, modular, or both.

| PyPSA | status | note |
| --- | --- | --- |
| [`Link-status`, `-start_up`, `-shut_down`, `-n_mod`](#variable-domains) | done | as the generator's, rung 7 and 8 |
| [`Link-com-p-*`, `-com-mod-p-*`, `-com-ext-p-*`](#link-com-p-lower) | done | a committable link leaves the `Link-fix-p-*` and `Link-ext-p-*` rows, as a generator does |
| [`Link-*-p-fixed-upper`, `-*-p_nom-variable-upper`](#link-status-p-fixed-upper) | done | |
| [`Link-com-transition-*`, `-com-up-time`, `-com-down-time`](#link-com-transition-start-up) | done | |
| [`Link-com-status-min_up_time_must_stay_up`, `-min_down_time_must_stay_up`](#link-com-status-min_up_time_must_stay_up) | done | prep masks, as the generator's |
| [`Link-p-ramp_limit_*`, `-*-bigM`](#link-p-ramp_limit_up) | done | the generator's cased allowance and big-M rows over flow |
| [`Link-p_nom_modularity`](#link-p_nom_modularity) | done | |
| [`stand_by_cost`, `start_up_cost`, `shut_down_cost`](#objective) | done | |

<!-- reference:rung_25_committable_link:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `14013.0`, 235 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_25_committable_link.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 25: committable links — a link held on by the up time it brought in, one held off by its down time, one kept on by its own up time, and committable builds that are extendable, modular or both."""

from __future__ import annotations

import spine


def build():
    """The spine plus an east bus that only committable links serve."""
    n = spine.build()
    n.add('Bus', 'east')
    n.add(
        'Link',
        'hvdc',
        bus0='north',
        bus1='east',
        committable=True,
        p_nom=60,
        p_min_pu=0.3,
        marginal_cost=8,
        min_up_time=3,
        min_down_time=2,
        up_time_before=1,
        ramp_limit_up=0.5,
        ramp_limit_down=0.5,
        ramp_limit_start_up=0.6,
        ramp_limit_shut_down=0.6,
        start_up_cost=100,
        shut_down_cost=50,
        stand_by_cost=5,
    )
    n.add(
        'Link',
        'cold_tie',
        bus0='north',
        bus1='east',
        committable=True,
        p_nom=40,
        p_min_pu=0.2,
        min_up_time=2,
        min_down_time=3,
        up_time_before=0,
        down_time_before=1,
        start_up_cost=20,
    )
    n.add(
        'Link',
        'ext_tie',
        bus0='north',
        bus1='east',
        committable=True,
        p_nom_extendable=True,
        p_nom_max=30,
        capital_cost=5,
        p_min_pu=0.2,
        marginal_cost=2,
        up_time_before=0,
        ramp_limit_up=0.5,
        ramp_limit_down=0.5,
    )
    n.add(
        'Link',
        'mod_tie',
        bus0='south',
        bus1='east',
        committable=True,
        p_nom_extendable=True,
        p_nom_mod=10,
        p_nom_max=40,
        capital_cost=3,
        p_min_pu=0.5,
    )
    n.add(
        'Link',
        'mod_fix',
        bus0='north',
        bus1='east',
        committable=True,
        p_nom=20,
        p_nom_mod=10,
        p_min_pu=0.5,
        marginal_cost=1,
    )
    n.add('Load', 'east_load', bus='east', p_set=[20, 70, 60, 5])
    return n
```

</details>
<!-- reference:rung_25_committable_link:end -->

### Rung 26 — committable processes

A committable process carries the same unit commitment over its internal power
`p`. The status gates `p`, not a port, so every port follows the status at its
own `rate`. This rung restates rung 25's links as processes that draw a quarter
more from the north than they deliver to the east. The same must-stay and up
time rules bind.

| PyPSA | status | note |
| --- | --- | --- |
| [`Process-status`, `-start_up`, `-shut_down`, `-n_mod`](#variable-domains) | done | as the link's, rung 25 |
| [`Process-com-p-*`, `-com-mod-p-*`, `-com-ext-p-*`](#process-com-p-lower) | done | a committable process leaves the `Process-fix-p-*` and `Process-ext-p-*` rows |
| [`Process-*-p-fixed-upper`, `-*-p_nom-variable-upper`](#process-status-p-fixed-upper) | done | |
| [`Process-com-transition-*`, `-com-up-time`, `-com-down-time`](#process-com-transition-start-up) | done | |
| [`Process-com-status-min_up_time_must_stay_up`, `-min_down_time_must_stay_up`](#process-com-status-min_up_time_must_stay_up) | done | prep masks, as the generator's |
| [`Process-p-ramp_limit_*`, `-*-bigM`](#process-p-ramp_limit_up) | done | the generator's cased allowance and big-M rows over internal power |
| [`Process-p_nom_modularity`](#process-p_nom_modularity) | done | |
| [`stand_by_cost`, `start_up_cost`, `shut_down_cost`](#objective) | done | |

<!-- reference:rung_26_committable_process:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `15956.125`, 235 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_26_committable_process.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 26: committable processes — rung 25's committable links restated as processes that draw a quarter more than they deliver."""

from __future__ import annotations

import spine


def build():
    """The spine plus an east bus that only committable processes serve."""
    n = spine.build()
    n.add('Bus', 'east')
    n.add(
        'Process',
        'warm_conv',
        bus0='north',
        bus1='east',
        rate0=-1.25,
        committable=True,
        p_nom=60,
        p_min_pu=0.3,
        marginal_cost=8,
        min_up_time=3,
        min_down_time=2,
        up_time_before=1,
        ramp_limit_up=0.5,
        ramp_limit_down=0.5,
        ramp_limit_start_up=0.6,
        ramp_limit_shut_down=0.6,
        start_up_cost=100,
        shut_down_cost=50,
        stand_by_cost=5,
    )
    n.add(
        'Process',
        'cold_conv',
        bus0='north',
        bus1='east',
        rate0=-1.25,
        committable=True,
        p_nom=40,
        p_min_pu=0.2,
        min_up_time=2,
        min_down_time=3,
        up_time_before=0,
        down_time_before=1,
        start_up_cost=20,
    )
    n.add(
        'Process',
        'ext_conv',
        bus0='north',
        bus1='east',
        rate0=-1.25,
        committable=True,
        p_nom_extendable=True,
        p_nom_max=30,
        capital_cost=5,
        p_min_pu=0.2,
        marginal_cost=2,
        up_time_before=0,
        ramp_limit_up=0.5,
        ramp_limit_down=0.5,
    )
    n.add(
        'Process',
        'mod_conv',
        bus0='south',
        bus1='east',
        rate0=-1.25,
        committable=True,
        p_nom_extendable=True,
        p_nom_mod=10,
        p_nom_max=40,
        capital_cost=3,
        p_min_pu=0.5,
    )
    n.add(
        'Process',
        'mod_fix',
        bus0='north',
        bus1='east',
        rate0=-1.25,
        committable=True,
        p_nom=20,
        p_nom_mod=10,
        p_min_pu=0.5,
        marginal_cost=1,
    )
    n.add('Load', 'east_load', bus='east', p_set=[20, 70, 60, 5])
    return n
```

</details>
<!-- reference:rung_26_committable_process:end -->

### Rung 27 — modular ramps

A committable, extendable and modular unit gets no big-M ramp rows. PyPSA gives
it the ordinary `{c}-p-ramp_limit_*` rows of a committed unit, with one module
`p_nom_mod` in place of `p_nom`. The status counts the modules that are on, so
the allowance grows with each module. This rung has one such generator, link
and process on a peak bus, each with a ramp limit of one half and a start-up
and shut-down ramp of 0.6. The ramp rows bind at the rise and at the fall of
the load.

| PyPSA | status | note |
| --- | --- | --- |
| [`{c}-p-ramp_limit_up/down`, modular](#generator-p-ramp_limit_up) | done | the committed allowance reads `p_nom_committed`: one module where the build is extendable and modular, `p_nom` otherwise |
| [`{c}-p-ramp_limit_*-bigM`, modular](#generator-p-ramp_limit_up-run-bigm) | done | not built for a modular build |

<!-- reference:rung_27_modular_ramp:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `45469.49999999998`, 161 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_27_modular_ramp.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 27: modular ramps — a committable extendable modular unit ramps against one module through the ordinary ramp rows, not the big-M ones."""

from __future__ import annotations

import spine


def build():
    """The spine plus a peak bus served by a committable modular generator, link and process, each ramp-limited, with a dear backup."""
    n = spine.build()
    n.add('Bus', 'peak')
    common = {
        'committable': True,
        'p_nom_extendable': True,
        'p_nom_mod': 20,
        'p_nom_max': 60,
        'capital_cost': 2,
        'p_min_pu': 0.2,
        'up_time_before': 0,
        'ramp_limit_up': 0.5,
        'ramp_limit_down': 0.5,
        'ramp_limit_start_up': 0.6,
        'ramp_limit_shut_down': 0.6,
    }
    n.add('Generator', 'mod_gen', bus='peak', marginal_cost=3, **common)
    n.add('Link', 'mod_link', bus0='north', bus1='peak', marginal_cost=4, **common)
    n.add('Process', 'mod_proc', bus0='south', bus1='peak', rate0=-1.25, marginal_cost=5, **common)
    n.add('Generator', 'peak_backup', bus='peak', p_nom=200, marginal_cost=500)
    n.add('Load', 'peak_load', bus='peak', p_set=[10, 90, 150, 20])
    return n
```

</details>
<!-- reference:rung_27_modular_ramp:end -->

### Rung 28 — a start-up ramp alone

PyPSA builds a ramp row where either the ramp limit or the start-up ramp is
given, and reads the missing one as `1.0`, the full build. The down row is the
same with the shut-down ramp. This rung has a committable generator, link and
process that carry only a start-up ramp of 0.4 and a shut-down ramp of 0.5. The
start-up ramp caps the snapshot each unit turns on, and the shut-down ramp caps
the snapshot before it turns off.

| PyPSA | status | note |
| --- | --- | --- |
| [`{c}-p-ramp_limit_up/down`, start-up or shut-down ramp alone](#generator-p-ramp_limit_up) | done | the `where:` reads either limit; `ramp_up_rate` and its three siblings read a missing one as `1` |

<!-- reference:rung_28_start_up_ramp:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `83282.99999999983`, 152 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_28_start_up_ramp.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 28: a start-up ramp alone — a committable unit with only a start-up and a shut-down ramp still gets ramp rows, at the full build between them."""

from __future__ import annotations

import spine


def build():
    """The spine plus a pulse bus served by committable generator, link and process that carry only start-up and shut-down ramps, with a dear backup."""
    n = spine.build()
    n.add('Bus', 'pulse')
    common = {
        'committable': True,
        'p_nom': 40,
        'p_min_pu': 0.1,
        'up_time_before': 0,
        'ramp_limit_start_up': 0.4,
        'ramp_limit_shut_down': 0.5,
    }
    n.add('Generator', 'pulse_gen', bus='pulse', marginal_cost=3, **common)
    n.add('Link', 'pulse_link', bus0='north', bus1='pulse', marginal_cost=4, **common)
    n.add('Process', 'pulse_proc', bus0='south', bus1='pulse', rate0=-1.25, marginal_cost=5, **common)
    n.add('Generator', 'pulse_backup', bus='pulse', p_nom=200, marginal_cost=500)
    n.add('Load', 'pulse_load', bus='pulse', p_set=[0, 60, 110, 0])
    return n
```

</details>
<!-- reference:rung_28_start_up_ramp:end -->

### Rung 29 — storage per investment period

`n.optimize(multi_investment_periods=True)` with storage that treats each
investment period as a horizon of its own. A storage unit with
`cyclic_state_of_charge_per_period` and a store with `e_cyclic_per_period`
close each period on itself: the first snapshot of a period carries in the
level of that period's last snapshot. A storage unit with
`state_of_charge_initial_per_period` and a store with `e_initial_per_period`
open each period on their initial level. The per-period cyclic flag overrides
the global one and the per-period initial flag. PyPSA reads the four flags only
under `multi_investment_periods`, so data prep feeds false on a plain run.

PyPSA also builds no ramp row at the first snapshot of a later period, with or
without these flags. The ramp-limited coal unit in this rung raises its output
from 59.2 to 90 across the period boundary, above its limit of 10 per
snapshot, while its ramp rows bind inside each period.

| PyPSA | status | note |
| --- | --- | --- |
| [`StorageUnit-energy_balance`](#storageunit-energy_balance), [`Store-energy_balance`](#store-energy_balance), per period | done | two more cases in the charge carried in: a `shift(…, edge='wrap', by=snapshot_period, within=period)` and the initial level at `position(snapshot, by=snapshot_period, within=period) == 0` |
| [`{c}-p-ramp_limit_*`, `-bigM`, at a period start](#generator-p-ramp_limit_up) | done | the `where:` drops every period start but the horizon's first |

<!-- reference:rung_29_storage_per_period:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `7438.461538461539`, 212 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_29_storage_per_period.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 29: storage per investment period — a storage unit and a store that cycle within each period, two that reopen on their initial level, and a ramp that restarts at a period start."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

OPTIMIZE = {'multi_investment_periods': True}


def build():
    """A whole network, not the spine: eight snapshots over two periods, four storages that each close or reopen per period, a ramp-limited coal unit."""
    import pypsa

    n = pypsa.Network()
    n.snapshots = pd.MultiIndex.from_tuples(
        [(2020, datetime(2020, 1, 1, t)) for t in range(4)] + [(2030, datetime(2030, 1, 1, t)) for t in range(4)]
    )
    n.investment_periods = [2020, 2030]
    n.investment_period_weightings['objective'] = [1.0, 0.5]
    n.investment_period_weightings['years'] = [10.0, 10.0]
    n.snapshot_weightings['objective'] = [2.0, 1.5, 2.5, 2.0, 2.0, 1.5, 2.5, 2.0]
    n.snapshot_weightings['stores'] = [0.5, 2.0, 1.5, 2.5, 0.5, 2.0, 1.5, 2.5]
    n.add('Bus', 'hub')
    n.add('Generator', 'coal29', bus='hub', p_nom=100, marginal_cost=10, ramp_limit_up=0.1, ramp_limit_down=0.1)
    n.add('Generator', 'peak29', bus='hub', p_nom=200, marginal_cost=[80, 20, 90, 30, 80, 20, 90, 30])
    n.add('StorageUnit', 'su_cycle', bus='hub', p_nom=15, max_hours=4, cyclic_state_of_charge_per_period=True)
    n.add(
        'StorageUnit',
        'su_reset',
        bus='hub',
        p_nom=15,
        max_hours=4,
        state_of_charge_initial=20,
        state_of_charge_initial_per_period=True,
    )
    n.add('Store', 'e_cycle', bus='hub', e_nom=30, e_cyclic_per_period=True)
    n.add('Store', 'e_reset', bus='hub', e_nom=30, e_initial=10, e_initial_per_period=True)
    n.add('Load', 'hub_load', bus='hub', p_set=[40, 60, 70, 40, 90, 110, 120, 90])
    return n
```

</details>
<!-- reference:rung_29_storage_per_period:end -->

### Rung 30 — security-constrained

`n.optimize.optimize_security_constrained(branch_outages=...)`: after any one
outage of a listed passive branch, every branch of the same sub-network carries
its flow within its rating. PyPSA computes the sub-network's branch outage
distribution factors (BODF) and copies each flow limit row with the outaged
branch's flow, times its factor, added to the left-hand side
(`abstract.py:443-489`). The copy keeps the row's sense, right-hand side and
extendable rating. It carries no loss term: PyPSA builds the model without
`transmission_losses` and `linearized_unit_commitment` (`abstract.py:437-441`)
and hands any other keyword to the solver (`abstract.py:491`), so a security
run is lossless and integer. Data prep feeds `transmission_losses` false there.
A network with no passive branch is the exception: PyPSA runs a plain
`n.optimize()` with every keyword (`abstract.py:429-435`), and no outage
exists. An outage is a line or a transformer, and
a plain list names lines. The outaged branch is monitored too, at the factor
`-1`. The file states the copies over an `outage` axis, with the factors as
data prep, `Line_BODF` and `Transformer_BODF`. A plain run supplies no outage,
so no copy is built and the model collapses to the standard one.

The rung outages two lines and a transformer of a meshed triangle and leaves
the third line monitored only. A plain `n.optimize()` solves the same network
at objective `17380.0`; the outages raise it to `22113.33` (#620). The cheap
unit at `a` falls to 32 in every snapshot, the unit at `b` covers the rest, and
the extendable line `ca` builds 20.7 instead of 2. Six of the 120 copied rows
bind, in `Transformer-fix-s-lower` against a line outage and in
`Line-ext-s-lower` against a transformer outage.

| PyPSA | status | note |
| --- | --- | --- |
| [`Line-fix-s-*-security-for-{c}-outage-in-sub-network-{n}`](#line-fix-s-lower-security-for-c-outage-in-sub-network-n), [`Line-ext-s-*-security-…`](#line-ext-s-lower-security-for-c-outage-in-sub-network-n) | split | PyPSA names a row per outaged component and sub-network; one block over the `outage` axis |
| [`Transformer-fix-s-*-security-…`](#transformer-fix-s-lower-security-for-c-outage-in-sub-network-n), [`Transformer-ext-s-*-security-…`](#transformer-ext-s-lower-security-for-c-outage-in-sub-network-n) | split | the same for a transformer |
| a branch not active in a period | done | PyPSA keeps the copy with that branch's flow dropped, so the file reads its flow as zero there; a copy left with no variable is not built here, where linopy counts it; no rung records it |
| a security-constrained run over scenarios | diverges | rung 56, [PyPSA/PyPSA#1942](https://github.com/PyPSA/PyPSA/issues/1942) |
| `transmission_losses`, `linearized_unit_commitment` in a security-constrained run | done | PyPSA builds neither, so the copies carry no loss term and data prep feeds `transmission_losses` false; no rung, since rung 30 is lossless |

<!-- reference:rung_30_security_constrained:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `22113.333333333332`, 240 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_30_security_constrained.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 30: security-constrained — a meshed triangle of lines and two transformers, one extendable, that must carry their flow within their rating after any one of three outages."""

from __future__ import annotations

import pandas as pd
import spine

BRANCH_OUTAGES = pd.MultiIndex.from_tuples([('Line', 'ab'), ('Line', 'ca'), ('Transformer', 'ca_t')])


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', 'a')
    n.add('Bus', 'b')
    n.add('Bus', 'c')
    n.add('Generator', 'hydro30', bus='a', p_nom=100, marginal_cost=10)
    n.add('Generator', 'diesel30', bus='b', p_nom=100, marginal_cost=50)
    n.add('Generator', 'peak30', bus='c', p_nom=100, marginal_cost=200)
    n.add('Load', 'town30', bus='c', p_set=[40, 60, 80, 50])
    n.add('Line', 'ab', bus0='a', bus1='b', x=0.1, s_nom=60)
    n.add('Line', 'bc', bus0='b', bus1='c', x=0.1, s_nom=60, s_max_pu=0.9)
    n.add('Line', 'ca', bus0='c', bus1='a', x=0.1, s_nom_extendable=True, capital_cost=5, s_nom_max=200)
    n.add('Transformer', 'ca_t', bus0='c', bus1='a', x=0.2, s_nom=30)
    n.add('Transformer', 'bc_t', bus0='b', bus1='c', x=0.3, s_nom_extendable=True, capital_cost=3, s_nom_max=50)
    return n
```

</details>
<!-- reference:rung_30_security_constrained:end -->

### Rung 32 — storage that stands in one period only

`n.optimize(multi_investment_periods=True)` with storage that is not per period
and does not stand in every period. PyPSA opens such a storage at the first
snapshot it stands in: on its initial level where it is not cyclic, and on the
level of the last snapshot it stands in where it is cyclic
(`constraints.py:2095-2097`, `2270-2273`). It reads the previous level through
a forward fill over the snapshots the storage does not stand in. Because a
build year and a lifetime make those snapshots one run at each end of the
horizon, the file states the same rows with two data-prep parameters. The
opening snapshot past the horizon's first is `{c}_opens_late`. The number of
snapshots the storage does not stand in is `{c}_inactive_snapshots`, and a
cyclic storage reaches back that many snapshots further. A plain run feeds
false and zero, so the rows collapse to the standard ones. The assumptions
[`StorageUnit_stands_in_one_run`](#storageunit_stands_in_one_run),
[`-opens_late_only_where_it_opens`](#storageunit_opens_late_only_where_it_opens)
and [`-opens_late_where_it_opens`](#storageunit_opens_late_where_it_opens), and
the `Store` ones, state the run and the opening snapshot. No
assumption ties `{c}_inactive_snapshots` to the count of inactive snapshots,
because a `count` compares against a whole number and not against a
parameter.

The rung builds a cyclic storage unit and a store with an initial level of 5 in
2030, and a cyclic store that retires after 2020. The earlier file read the
level before 2030 as absent and dropped the opening row, so each storage
opened on any level it chose. With the same rows, the objective falls to
`5620.61` (#620).

| PyPSA | status | note |
| --- | --- | --- |
| [`StorageUnit-energy_balance`](#storageunit-energy_balance), [`Store-energy_balance`](#store-energy_balance), at the first snapshot a storage stands in | done | the `cyclic` and `opening` cases hold at `position(snapshot) == 0` or at `{c}_opens_late`; the cyclic one shifts one snapshot and then `{c}_inactive_snapshots` more, `edge='wrap'` |

<!-- reference:rung_32_storage_later_period:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `7230.4866975671375`, 92 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_32_storage_later_period.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 32: storage that stands in one period only — two built in the later period open at its first snapshot, and a cyclic one that retires closes on its own last snapshot."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

OPTIMIZE = {'multi_investment_periods': True}


def build():
    """A whole network, not the spine: eight snapshots over two periods, two storages built in 2030, one cyclic store that retires after 2020."""
    import pypsa

    n = pypsa.Network()
    n.snapshots = pd.MultiIndex.from_tuples(
        [(2020, datetime(2020, 1, 1, t)) for t in range(4)] + [(2030, datetime(2030, 1, 1, t)) for t in range(4)]
    )
    n.investment_periods = [2020, 2030]
    n.investment_period_weightings['objective'] = [1.0, 0.5]
    n.investment_period_weightings['years'] = [10.0, 10.0]
    n.snapshot_weightings['objective'] = [2.0, 1.5, 2.5, 2.0, 2.0, 1.5, 2.5, 2.0]
    n.snapshot_weightings['stores'] = [0.5, 2.0, 1.5, 2.5, 0.5, 2.0, 1.5, 2.5]
    n.add('Bus', 'hub')
    n.add('Generator', 'base32', bus='hub', p_nom=100, marginal_cost=10)
    n.add('Generator', 'peak32', bus='hub', p_nom=200, marginal_cost=[80, 20, 90, 30, 80, 20, 90, 30])
    n.add(
        'StorageUnit',
        'su_late',
        bus='hub',
        p_nom=15,
        max_hours=4,
        standing_loss=0.02,
        cyclic_state_of_charge=True,
        build_year=2030,
        lifetime=30,
    )
    n.add('Store', 'e_late', bus='hub', e_nom=30, e_initial=5, build_year=2030, lifetime=30)
    n.add('Store', 'e_retire', bus='hub', e_nom=30, standing_loss=0.01, e_cyclic=True, build_year=2020, lifetime=10)
    n.add('Load', 'hub_load', bus='hub', p_set=[40, 60, 70, 40, 90, 110, 120, 90])
    return n
```

</details>
<!-- reference:rung_32_storage_later_period:end -->

### Rung 33 — maintenance

A `Generator`, `Link` or `Process` with `maintainable=True` is taken off for
`maintenance_events` events (default 1) within the horizon. Each event covers
the snapshot it starts in and the snapshots after it, until their
`generators` weightings reach `maintenance_duration` hours
(`constraints.py:767-800`). While it is in maintenance, the component loses the
share `maintenance_pu` (default 1) of its build from both of its bounds
(`constraints.py:135-145`, `221-234`). The status `maintenance` is continuous in
[0, 1], and the binary starts make it whole (`variables.py:202-259`). An
extendable build multiplies a variable by a variable. PyPSA writes that product
as `maintenance_capacity` and holds it with four McCormick rows against
`p_nom_min` and `p_nom_max` (`constraints.py:810-845`), so PyPSA refuses an
extendable maintainable build with an infinite `p_nom_max`.

The window of an event depends on the weightings, so its width varies along
`snapshot`. `sum_back` takes a width that does not vary along the dimension it
sums. So the file reads the windows as data: the relation
`*_maintenance_cover` pairs each start with the snapshots it covers. The mask
`*_maintenance_start_blocked` marks the starts whose window runs past the end
of the horizon or into a snapshot the component does not stand in. Both come
from `maintenance_duration`, the weightings and `active`. With them, each row
is the one PyPSA builds. Across investment periods an event may cross a period
boundary, and the count is over the whole horizon, as in PyPSA. Over scenarios
every maintenance variable is second stage, one schedule per scenario.

Here every maintainable component is new, and a peaker at 60 covers the east
bus. With the same network and no `maintainable`, PyPSA solves to
`5388.833333333333`.

| PyPSA | status | note |
| --- | --- | --- |
| [`Generator-maintenance`, `-maintenance_start`, `-maintenance_capacity`](#variable-domains), and the `Link` and `Process` ones | done | zero where the component is not maintainable |
| [`Generator-maint-event-count`](#generator-maint-event-count), [`-maint-window`](#generator-maint-window), [`-maint-start-horizon`](#generator-maint-start-horizon), and the `Link` and `Process` ones | done | the window and the blocked starts are data prep |
| [`Generator-maintcap_*`](#generator-maintcap_upper), and the `Link` and `Process` ones | done | `-maintcap_lower_nommin` only where `p_nom_min > 0` |
| [`Generator-fix-p-*`](#generator-fix-p-lower), [`-ext-p-*`](#generator-ext-p-lower), and the `Link` and `Process` ones, in maintenance | done | the bound less `maintenance_pu` of the build |

<!-- reference:rung_33_maintenance:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `7367.560185185185`, 179 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_33_maintenance.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 33: maintenance — a fixed and an extendable generator, link and process, each taken off for events that the generator weightings time."""

from __future__ import annotations

import spine


def build():
    """The spine plus an east bus and six maintainable components, fixed and extendable, with a dear peaker to cover them."""
    n = spine.build()
    n.add('Bus', 'east')
    n.add('Generator', 'hydro', bus='north', p_nom=50, marginal_cost=2, maintainable=True, maintenance_duration=3)
    n.add(
        'Generator',
        'wind_ext',
        bus='south',
        p_nom_extendable=True,
        p_nom_min=10,
        p_nom_max=60,
        capital_cost=20,
        marginal_cost=1,
        p_max_pu=[0.9, 0.6, 0.8, 0.7],
        maintainable=True,
        maintenance_duration=2,
        maintenance_pu=0.5,
    )
    n.add(
        'Link',
        'tie_fix',
        bus0='north',
        bus1='east',
        p_nom=30,
        efficiency=0.95,
        maintainable=True,
        maintenance_duration=1,
        maintenance_events=2,
    )
    n.add(
        'Link',
        'tie_ext',
        bus0='south',
        bus1='east',
        p_nom_extendable=True,
        p_nom_min=5,
        p_nom_max=40,
        capital_cost=4,
        efficiency=0.9,
        p_min_pu=-1,
        maintainable=True,
        maintenance_duration=3,
    )
    n.add(
        'Process',
        'conv_fix',
        bus0='north',
        bus1='east',
        rate0=-1.25,
        p_nom=25,
        maintainable=True,
        maintenance_duration=3,
        maintenance_pu=0.6,
    )
    n.add(
        'Process',
        'conv_ext',
        bus0='south',
        bus1='east',
        rate0=-1.25,
        p_nom_extendable=True,
        p_nom_min=5,
        p_nom_max=30,
        capital_cost=3,
        maintainable=True,
        maintenance_duration=1,
    )
    n.add('Generator', 'east_peak', bus='east', p_nom=100, marginal_cost=60)
    n.add('Load', 'east_load', bus='east', p_set=[50, 60, 40, 55])
    return n
```

</details>
<!-- reference:rung_33_maintenance:end -->

### Rung 34 — maintenance of committable units

A committable build scales its bounds by the status, so maintenance takes its
share off the status. PyPSA writes the product of the status and `maintenance`
as `maintenance_status`, with three McCormick rows, so a unit in maintenance
can also be off (`variables.py:301-338`, `constraints.py:425-458`). A modular
committable build uses the same product, bounded by the module count
`p_nom_max / p_nom_mod` (`constraints.py:498-533`). An extendable committable
build that is not modular uses `maintenance_capacity` in its big-M rows
instead (`constraints.py:363-373`). `-com-ext-p-upper-bigM` does not change.
Ramps, the up and down times and the storage rows do not read maintenance.

With the same network and no `maintainable`, PyPSA solves to `5370.0`.

| PyPSA | status | note |
| --- | --- | --- |
| [`Generator-maintenance_status`](#variable-domains), and the `Link` and `Process` ones | done | |
| [`Generator-maint-status-*`](#generator-maint-status-le-status), [`-maint-modstatus-*`](#generator-maint-modstatus-le-status), and the `Link` and `Process` ones | done | a fixed build's status, and a modular build's module count |
| [`Generator-com-p-*`](#generator-com-p-lower), [`-com-mod-p-*`](#generator-com-mod-p-lower), [`-com-ext-p-lower`](#generator-com-ext-p-lower), [`-com-ext-p-upper-cap`](#generator-com-ext-p-upper-cap), and the `Link` and `Process` ones, in maintenance | done | |

<!-- reference:rung_34_committable_maintenance:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `6420.048611111111`, 503 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_34_committable_maintenance.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 34: maintenance of committable units — a fixed, an extendable and a modular committable generator, link and process, each taken off for one event."""

from __future__ import annotations

import spine


def build():
    """The spine plus an east bus and nine maintainable committable components, with a dear peaker to cover them."""
    n = spine.build()
    n.add('Bus', 'east')
    committable = {'committable': True, 'maintainable': True}
    n.add(
        'Generator',
        'unit',
        bus='north',
        p_nom=60,
        p_min_pu=0.3,
        marginal_cost=5,
        start_up_cost=10,
        maintenance_duration=2,
        **committable,
    )
    n.add(
        'Generator',
        'unit_ext',
        bus='south',
        p_nom_extendable=True,
        p_nom_min=5,
        p_nom_max=50,
        capital_cost=10,
        p_min_pu=0.2,
        marginal_cost=4,
        maintenance_duration=3,
        maintenance_pu=0.5,
        **committable,
    )
    n.add(
        'Generator',
        'unit_mod',
        bus='south',
        p_nom_extendable=True,
        p_nom_mod=10,
        p_nom_max=30,
        capital_cost=8,
        p_min_pu=0.5,
        marginal_cost=3,
        maintenance_duration=1,
        **committable,
    )
    for component, ports in (('Link', {}), ('Process', {'rate0': -1.25})):
        n.add(
            component,
            f'{component.lower()}_unit',
            bus0='north',
            bus1='east',
            p_nom=40,
            p_min_pu=0.2,
            marginal_cost=1,
            maintenance_duration=2,
            **ports,
            **committable,
        )
        n.add(
            component,
            f'{component.lower()}_ext',
            bus0='south',
            bus1='east',
            p_nom_extendable=True,
            p_nom_min=5,
            p_nom_max=30,
            capital_cost=5,
            p_min_pu=0.2,
            maintenance_duration=3,
            maintenance_pu=0.5,
            **ports,
            **committable,
        )
        n.add(
            component,
            f'{component.lower()}_mod',
            bus0='north',
            bus1='east',
            p_nom_extendable=True,
            p_nom_mod=10,
            p_nom_max=20,
            capital_cost=3,
            p_min_pu=0.5,
            maintenance_duration=1,
            **ports,
            **committable,
        )
    n.add('Generator', 'east_peak', bus='east', p_nom=100, marginal_cost=60)
    n.add('Load', 'east_load', bus='east', p_set=[50, 60, 40, 55])
    return n
```

</details>
<!-- reference:rung_34_committable_maintenance:end -->

### Rung 35 — a global constraint for one investment period

`n.optimize(multi_investment_periods=True)` with `primary_energy` and
`operational_limit` rows that name an `investment_period`. PyPSA sums such a
row over the snapshots of that period only, and over the whole horizon where
the row names none (`global_constraints.py:373-378`, `600-606`). Each snapshot
counts with its generator weighting times the `years` weighting of its period
(`:326`, `:615`). A storage unit or store that reopens per period closes at the
last snapshot of each counted period, weighted by that period's years
(`:474-477`, `:673-676`). One that carries its level across periods closes
once, at the last counted snapshot (`:459-470`, `:658-668`). The file states
the counted snapshots as `GlobalConstraint_counts_snapshot`, data prep, and
the years as `period_weight_years`. A plain run feeds all true and one, so the
rows collapse to the standard ones.

The rung caps CO2 in 2030 alone, caps it again over the horizon, and limits a
hydro carrier with a per-period storage unit and store in 2020. The years
weightings are 5 and 10. With the same network and no `investment_period`,
PyPSA solves to `10675.0`.

| PyPSA | status | note |
| --- | --- | --- |
| [`primary_energy`](#primary_energy), [`operational_limit`](#operational_limit) over one investment period | done | `GlobalConstraint_energy_weight` is zero outside the counted snapshots, and the years weigh each snapshot |
| the closing level of storage in those rows | done | `StorageUnit_closing_weight`, `Store_closing_weight`: each counted period's last snapshot where the storage reopens per period, the last counted snapshot otherwise |
| a `primary_energy` row for one period over storage that reopens per period | refused, as PyPSA | assumed: [`StorageUnit_primary_energy_per_period_closes_over_the_horizon`](#storageunit_primary_energy_per_period_closes_over_the_horizon), and the `Store` one |

<!-- reference:rung_35_period_global_constraints:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `4886.764705882353`, 155 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_35_period_global_constraints.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 35: a global constraint for one investment period — a CO2 cap on 2030 alone, one over the horizon, and a 2020 limit on a carrier with storage that reopens per period."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

OPTIMIZE = {'multi_investment_periods': True}


def build():
    """A whole network, not the spine: eight snapshots over two periods of unequal years, two emitting units, a hydro carrier with a unit and storage."""
    import pypsa

    n = pypsa.Network()
    n.snapshots = pd.MultiIndex.from_tuples(
        [(2020, datetime(2020, 1, 1, t)) for t in range(4)] + [(2030, datetime(2030, 1, 1, t)) for t in range(4)]
    )
    n.investment_periods = [2020, 2030]
    n.investment_period_weightings['objective'] = [1.0, 0.5]
    n.investment_period_weightings['years'] = [5.0, 10.0]
    n.snapshot_weightings['generators'] = [1.0, 2.0, 1.0, 2.0, 1.0, 2.0, 1.0, 2.0]
    n.add('Carrier', 'coal35', co2_emissions=1.0)
    n.add('Carrier', 'gas35', co2_emissions=0.4)
    n.add('Carrier', 'hydro35')
    n.add('Bus', 'hub')
    n.add('Generator', 'coal35', bus='hub', carrier='coal35', p_nom=100, marginal_cost=10, efficiency=0.4)
    n.add('Generator', 'gas35', bus='hub', carrier='gas35', p_nom=100, marginal_cost=30, efficiency=0.5)
    n.add('Generator', 'clean35', bus='hub', p_nom=200, marginal_cost=60)
    n.add('Generator', 'river35', bus='hub', carrier='hydro35', p_nom=30, marginal_cost=5)
    n.add(
        'StorageUnit',
        'dam35',
        bus='hub',
        carrier='hydro35',
        p_nom=15,
        max_hours=4,
        state_of_charge_initial=20,
        state_of_charge_initial_per_period=True,
    )
    n.add('Store', 'pond35', bus='hub', carrier='hydro35', e_nom=30, e_initial=10, e_initial_per_period=True)
    n.add('Load', 'town35', bus='hub', p_set=[60, 80, 70, 50, 90, 110, 100, 80])
    n.add(
        'GlobalConstraint',
        'co2_2030',
        type='primary_energy',
        carrier_attribute='co2_emissions',
        sense='<=',
        constant=3500,
        investment_period=2030,
    )
    n.add(
        'GlobalConstraint',
        'co2_all',
        type='primary_energy',
        carrier_attribute='co2_emissions',
        sense='<=',
        constant=6000,
    )
    n.add(
        'GlobalConstraint',
        'hydro_2020',
        type='operational_limit',
        carrier_attribute='hydro35',
        sense='<=',
        constant=600,
        investment_period=2020,
    )
    return n
```

</details>
<!-- reference:rung_35_period_global_constraints:end -->

### Rung 36 — quadratic costs on a process and on storage

PyPSA's `marginal_cost_quadratic` on the three other components that carry it
(`variables.csv:22`, `:30`, `:33`): a process pays on its internal power `p`, a
storage unit on `p_dispatch` only, and a store on its net `p`, so charging
costs as much as delivering. Each term is the square times the cost, weighted
as the linear term is (`optimize.py:317-334`). A plain run feeds zero, so the
terms vanish.

The rung puts a quadratic cost on a process, a storage unit, with a cost that
changes per snapshot, and a store. With the same network and no quadratic
cost, PyPSA solves to `17641.666666666668`.

| PyPSA | status | note |
| --- | --- | --- |
| [`marginal_cost_quadratic`](#objective) on Process, StorageUnit and Store | done | degree 2 in the objective; `p_store` is not charged |
| a quadratic cost under a risk preference | refused, as PyPSA | assumed: [`Generator_marginal_cost_quadratic_without_risk_preference`](#generator_marginal_cost_quadratic_without_risk_preference), and the `Link`, `Process`, `StorageUnit` and `Store` ones |

<!-- reference:rung_36_quadratic_storage_process:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `19185.241281403858`, 84 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_36_quadratic_storage_process.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 36: quadratic costs on a process, a storage unit and a store — the storage unit pays on dispatch only, the store on its net power both ways."""

from __future__ import annotations

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', 'hub')
    n.add('Process', 'conv36', bus0='north', bus1='hub', p_nom=60, marginal_cost=1, marginal_cost_quadratic=0.05)
    n.add(
        'StorageUnit',
        'battery36',
        bus='south',
        p_nom=20,
        max_hours=4,
        state_of_charge_initial=40,
        marginal_cost=0.5,
        marginal_cost_quadratic=[0.2, 0.1, 0.3, 0.1],
    )
    n.add('Store', 'tank36', bus='hub', e_nom=60, e_initial=20, marginal_cost_quadratic=0.4)
    n.add('Load', 'hub_load', bus='hub', p_set=[20, 45, 30, 50])
    n.add('Load', 'peak36', bus='south', p_set=[10, 40, 20, 60])
    return n
```

</details>
<!-- reference:rung_36_quadratic_storage_process:end -->

### Rung 37 — storage dispatch pinned to a schedule

PyPSA pins a store's power delivered to `p_set`, and a storage unit's dispatch
and charging to `p_dispatch_set` and `p_store_set`, each on its own
(`optimize.py:846`, `:851`; `constraints.py:1961-2019`). A row stands only
where a value is given and the storage is active. A plain run gives no value,
so no row stands.

The rung pins a store to deliver 10 in the first snapshot and to take 5 in the
last, and pins a storage unit's dispatch in the first snapshot and its
charging in the second. With the same network and no pins, PyPSA solves to
`5811.111111111111`.

| PyPSA | status | note |
| --- | --- | --- |
| [`Store-p_set`](#store-p_set), [`StorageUnit-p_dispatch_set`](#storageunit-p_dispatch_set), [`StorageUnit-p_store_set`](#storageunit-p_store_set) | done | `where:` a value is given and the storage is active |

<!-- reference:rung_37_fixed_storage_dispatch:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `6395.833333333333`, 76 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_37_fixed_storage_dispatch.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 37: storage dispatch pinned — a store's power delivered, and a storage unit's dispatch and charging, each on its own schedule."""

from __future__ import annotations

from math import nan

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.generators_t.marginal_cost['gas'] = [15, 60, 15, 60]
    n.add('Store', 'tank37', bus='south', e_nom=40, e_initial=20, p_set=[10, nan, nan, -5])
    n.add(
        'StorageUnit',
        'battery37',
        bus='south',
        p_nom=20,
        max_hours=2,
        state_of_charge_initial=10,
        p_dispatch_set=[6, nan, nan, nan],
        p_store_set=[nan, 4, nan, nan],
    )
    return n
```

</details>
<!-- reference:rung_37_fixed_storage_dispatch:end -->

### Rung 38 — delays per investment period

`n.optimize(multi_investment_periods=True)` with delayed ports. PyPSA applies
a link's or a process's `delay` in each investment period on its own
(`constraints.py:1324-1332`; `multiports.py:212-219`). A `cyclic_delay` port
wraps from the end of its own period. A port that is not cyclic loses the flow
still in transit at the first snapshots of every period. PyPSA measures the
delay in `generators` weighting per period and rounds it down to a snapshot
start (`multiports.py:106-123`). Scenarios do not change the source snapshot.
`Link_output_arrival` and `Process_output_arrival` therefore shift with
`by=snapshot_period, within=period`. A plain run has one period, so the shift
is the flat one.

The rung builds a link that delays by two and wraps, and a process that
delays by one and does not wrap, on two periods of four snapshots. The earlier
file shifted over the flat horizon, so 2030 read the flow sent in 2020. With
that flat shift patched into PyPSA's source index, the network solves to
`10543.75` (#620).

| PyPSA | status | note |
| --- | --- | --- |
| [link and process `delay`, `cyclic_delay`](#bus-nodal_balance) per investment period | done | `shift(offset=delay, by=snapshot_period, within=period)`; `edge='wrap'` closes each period, `edge=0` vacates each period's first snapshots |

<!-- reference:rung_38_delay_per_period:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `12918.75`, 104 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_38_delay_per_period.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 38: delays per investment period — a link that wraps its delayed flow within each period, and a process that loses what is still in transit at each period's start."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

OPTIMIZE = {'multi_investment_periods': True}

#: The `generators` weighting is uniform, as on rung 16, so a delay of `n` is a
#: shift of exactly `n` positions. The `objective` column stays non-uniform.
WEIGHTINGS = {'objective': [2.0, 1.5, 2.5, 3.0, 2.0, 1.5, 2.5, 3.0], 'generators': [1.0] * 8}

#: Demand differs from snapshot to snapshot, so which snapshot a delayed flow is
#: read from changes what it costs.
DEMAND = [20.0, 15.0, 25.0, 10.0, 30.0, 35.0, 5.0, 40.0]


def build():
    """A whole network, not the spine: eight snapshots over two periods, a source, a delayed link and a delayed process.

    ``pipe_wrap`` delays by two snapshots and wraps cyclically, so the first two
    snapshots of each period read the last two of that same period, never the
    other period. ``conv_lose`` delays by one and does not wrap, so the first
    snapshot of each period, 2030 included, receives nothing and its demand falls
    to the backup. The source is capped, so where each delayed flow is read from
    decides how much of the backup runs.
    """
    import pypsa

    n = pypsa.Network()
    n.snapshots = pd.MultiIndex.from_tuples(
        [(2020, datetime(2020, 1, 1, t)) for t in range(4)] + [(2030, datetime(2030, 1, 1, t)) for t in range(4)]
    )
    n.investment_periods = [2020, 2030]
    n.investment_period_weightings['objective'] = [1.0, 0.5]
    n.investment_period_weightings['years'] = [10.0, 10.0]
    for column, values in WEIGHTINGS.items():
        n.snapshot_weightings[column] = values
    n.add('Bus', ['source', 'sink_wrap', 'sink_lose'])
    n.add('Generator', 'spring38', bus='source', p_nom=60, marginal_cost=5)
    n.add('Generator', 'backup_wrap38', bus='sink_wrap', p_nom=200, marginal_cost=100)
    n.add('Generator', 'backup_lose38', bus='sink_lose', p_nom=200, marginal_cost=100)
    n.add('Link', 'pipe_wrap', bus0='source', bus1='sink_wrap', p_nom=30, delay=2, cyclic_delay=True)
    n.add('Process', 'conv_lose', bus0='source', bus1='sink_lose', p_nom=30, delay1=1, cyclic_delay1=False)
    n.add('Load', 'load_wrap', bus='sink_wrap', p_set=DEMAND)
    n.add('Load', 'load_lose', bus='sink_lose', p_set=DEMAND)
    return n
```

</details>
<!-- reference:rung_38_delay_per_period:end -->

### Rung 39 — a negative relative growth

`n.optimize(multi_investment_periods=True)` with a carrier whose
`max_relative_growth` is negative. PyPSA clips the share at zero before it
builds `Carrier-growth_limit` (`global_constraints.py:237`), so a negative
share adds nothing and does not tighten the limit. `Carrier_relative_growth`
states the clip as a case: the given share where it is positive, zero
otherwise. A plain run has one period and builds no growth row.

The rung builds a battery carrier with `max_growth=20` and
`max_relative_growth=-0.5`, and two stores built in 2020 and 2030. The earlier
file read the share as given, so the 2030 row added half of the 2020 build to
the left side. With that row patched into PyPSA through `extra_functionality`,
the network solves to `9347.5` (#620).

| PyPSA | status | note |
| --- | --- | --- |
| [`Carrier-growth_limit`](#carrier-growth_limit), `max_relative_growth.clip(min=0)` | done | `Carrier_relative_growth` is `Carrier_max_relative_growth` where it is positive, `0` otherwise |

<!-- reference:rung_39_negative_relative_growth:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `8600.0`, 44 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_39_negative_relative_growth.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 39: a negative relative growth adds nothing to a carrier's growth limit — PyPSA clips it at zero."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

OPTIMIZE = {'multi_investment_periods': True}


def build():
    """A whole network, not the spine: a battery carrier with `max_relative_growth=-0.5` builds in both periods."""
    import pypsa

    n = pypsa.Network()
    n.snapshots = pd.MultiIndex.from_tuples(
        [(2020, datetime(2020, 1, 1, t)) for t in range(2)] + [(2030, datetime(2030, 1, 1, t)) for t in range(2)]
    )
    n.investment_periods = [2020, 2030]
    n.investment_period_weightings['objective'] = [1.0, 0.5]
    n.investment_period_weightings['years'] = [10.0, 10.0]
    n.snapshot_weightings['objective'] = [2.0, 1.5, 2.5, 2.0]
    n.add('Bus', 'grid')
    n.add('Carrier', 'solar')
    n.add('Carrier', 'gas')
    n.add('Carrier', 'battery', max_growth=20, max_relative_growth=-0.5)
    n.add('Generator', 'solar', bus='grid', carrier='solar', p_nom=100, marginal_cost=1, p_max_pu=[1, 0, 1, 0])
    n.add('Generator', 'backup', bus='grid', carrier='gas', p_nom=200, marginal_cost=80)
    n.add(
        'Store',
        'tank20',
        bus='grid',
        carrier='battery',
        e_nom_extendable=True,
        e_nom_max=100,
        capital_cost=10,
        build_year=2020,
        lifetime=30,
    )
    n.add(
        'Store',
        'tank30',
        bus='grid',
        carrier='battery',
        e_nom_extendable=True,
        e_nom_max=100,
        capital_cost=8,
        build_year=2030,
        lifetime=30,
    )
    n.add('Load', 'town', bus='grid', p_set=[40, 60, 40, 80])
    return n
```

</details>
<!-- reference:rung_39_negative_relative_growth:end -->

### Rung 40 — a global constraint per scenario

`n.set_scenarios(...)` with `GlobalConstraint` rows whose `constant` and
`sense` differ between the scenarios. PyPSA builds one `GlobalConstraint-{name}`
row per scenario for `primary_energy`, `operational_limit` and
`transmission_volume_expansion_limit`, and reads each scenario's own sense and
constant (`global_constraints.py:361-371`, `:556-557`, `:748-749`,
`:786-795`, `:860-861`). The file states `GlobalConstraint_constant` and
`GlobalConstraint_sense` over `scenario` as well, so each row takes its own
value in each future. A row with no scenario axis in its total, such as the
transmission volume, repeats the same capacity sum under each scenario's
constant. A plain run feeds one scenario, and the rows collapse to the standard
ones.

The rung puts an extendable line under a volume limit of `60` in the calm
future and `20` in the stormy one, and a CO2 row that is at most `250` in the
calm future and exactly `200` in the stormy one. All three bind. With the same
network and the calm values in both futures, PyPSA solves to
`12943.333333333334`.

| PyPSA | status | note |
| --- | --- | --- |
| [`primary_energy`](#primary_energy), [`operational_limit`](#operational_limit), [`transmission_volume_expansion_limit`](#transmission_volume_expansion_limit) with a constant and sense per scenario | done | `GlobalConstraint_constant` and `GlobalConstraint_sense` over `scenario` |
| `transmission_expansion_cost_limit` on a network with scenarios | diverges | rung 52, [PyPSA/PyPSA#1939](https://github.com/PyPSA/PyPSA/issues/1939) |
| `transmission_volume_expansion_limit` on a network with scenarios and `multi_investment_periods` | diverges | rung 53, [PyPSA/PyPSA#1939](https://github.com/PyPSA/PyPSA/issues/1939) |
| a `carrier_attribute` or `investment_period` per scenario | done | PyPSA reads both per scenario (`global_constraints.py:797-802`); the weights and `GlobalConstraint_counts_snapshot` span `scenario` |

<!-- reference:rung_40_scenario_global_constraints:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `15106.666666666666`, 86 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_40_scenario_global_constraints.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 40: a global constraint takes its own constant and sense in each scenario."""

from __future__ import annotations

import spine

#: each scenario's own constant and sense, per row
PER_SCENARIO = {
    ('calm', 'volume40'): {'constant': 60},
    ('stormy', 'volume40'): {'constant': 20},
    ('calm', 'co2_40'): {'constant': 250, 'sense': '<='},
    ('stormy', 'co2_40'): {'constant': 200, 'sense': '=='},
}


def build():
    """The spine over two futures, with an extendable line under a volume limit and a CO2 row that differ by scenario."""
    n = spine.build()
    n.add('Carrier', 'AC')
    n.add('Carrier', 'coalc', co2_emissions=0.5)
    n.c.generators.static.loc['coal', 'carrier'] = 'coalc'
    n.add(
        'Line',
        'tie40',
        bus0='north',
        bus1='south',
        x=0.1,
        carrier='AC',
        length=2,
        s_nom_extendable=True,
        capital_cost=1,
    )
    n.add('Load', 'port40', bus='south', p_set=30)
    n.add(
        'GlobalConstraint',
        'volume40',
        type='transmission_volume_expansion_limit',
        carrier_attribute='AC',
        sense='<=',
        constant=60,
    )
    n.add(
        'GlobalConstraint', 'co2_40', type='primary_energy', carrier_attribute='co2_emissions', sense='<=', constant=250
    )
    n.set_scenarios({'calm': 0.6, 'stormy': 0.4})
    for row, values in PER_SCENARIO.items():
        for column, value in values.items():
            n.c.global_constraints.static.loc[row, column] = value
    return n
```

</details>
<!-- reference:rung_40_scenario_global_constraints:end -->

### Rung 41 — operating data per scenario

`n.set_scenarios(...)` with a gas unit's `marginal_cost` and a link's
`efficiency` set per scenario. PyPSA reads both through `c.da`, one value per
scenario, into the objective and into `Bus-nodal_balance`
(`components/array.py:332-395`). The file states `Generator_marginal_cost` and
`Link_efficiency` over `scenario`, as it states every parameter PyPSA reads per
scenario. A plain run feeds one scenario, and the rows collapse to the standard
ones.

The rung adds a gas unit that costs `20` in the calm future and `80` in the
stormy one, and a second link that delivers `0.9` and `0.6` of its flow. Each
binds. With the calm cost in both futures, PyPSA solves to `16308.0`; with the
calm efficiency in both, to `16992.0`; with both calm values in both, to
`15660.0`.

| PyPSA | status | note |
| --- | --- | --- |
| [objective](#objective), [`Bus-nodal_balance`](#bus-nodal_balance) with a cost and an efficiency per scenario | done | `Generator_marginal_cost` and `Link_efficiency` over `scenario` |
| a link `delay` or `cyclic_delay` that differs by scenario | diverges | rung 54, [PyPSA/PyPSA#1941](https://github.com/PyPSA/PyPSA/issues/1941) |
| a transformer in a cycle on a network with scenarios | diverges | rung 55, [PyPSA/PyPSA#1942](https://github.com/PyPSA/PyPSA/issues/1942) |
| a committable component on a network with scenarios | diverges | rung 58, [PyPSA/PyPSA#1913](https://github.com/PyPSA/PyPSA/issues/1913) |
| [`{c}-p_nom_set`](#generator-p_nom_set) on a network with scenarios | diverges | rung 57, [PyPSA/PyPSA#1942](https://github.com/PyPSA/PyPSA/issues/1942) |

<!-- reference:rung_41_scenario_operational_data:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `17964.0`, 96 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_41_scenario_operational_data.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 41: a unit's cost and a link's efficiency differ by scenario."""

from __future__ import annotations

import spine

#: each scenario's own value, per component and attribute
PER_SCENARIO = {
    ('calm', 'gas41'): {'marginal_cost': 20},
    ('stormy', 'gas41'): {'marginal_cost': 80},
    ('calm', 'wire41'): {'efficiency': 0.9},
    ('stormy', 'wire41'): {'efficiency': 0.6},
}


def build():
    """The spine over two futures, with a gas unit that costs more and a link that delivers less in the stormy one."""
    n = spine.build()
    n.add('Generator', 'gas41', bus='south', p_nom=100, marginal_cost=20)
    n.add('Link', 'wire41', bus0='north', bus1='south', p_nom=40, efficiency=0.9)
    n.add('Load', 'port41', bus='south', p_set=60)
    n.set_scenarios({'calm': 0.6, 'stormy': 0.4})
    for (scenario, name), values in PER_SCENARIO.items():
        component = n.c.generators if name == 'gas41' else n.c.links
        for column, value in values.items():
            component.static.loc[(scenario, name), column] = value
    return n
```

</details>
<!-- reference:rung_41_scenario_operational_data:end -->

### Rung 42 — first-stage data per scenario

`n.set_scenarios(...)` with an extendable unit whose `capital_cost` and
`p_nom_max` differ between the scenarios. The build is chosen once, but PyPSA
reads its bounds per scenario and writes `Generator-ext-p_nom-lower` and
`-upper` once per scenario, so the tightest cap binds
(`constraints.py:885-895`). It prices the build at each scenario's capital
cost and weights the terms by the scenario weights (`optimize.py:405-412`,
`:448-454`), so the build pays its capital cost in expectation. The file states
`Generator_p_nom_max` and `Generator_capital_cost` over `scenario`, the bound
rows over `scenario`, and the capital terms of the objective under
`scenario_weight`. A plain run feeds one scenario of weight one, and the rows
and the objective collapse to the standard ones.

The rung's wind unit costs `20` in the calm future and `60` in the stormy one,
weighted `0.6` and `0.4`, and may be built to `100` and `30`. PyPSA builds `30`
at the expected cost of `36`: the same network with a cost of `36` and a cap of
`30` in both futures solves to the same objective. With the calm values in both
futures, PyPSA solves to `1943.0`.

| PyPSA | status | note |
| --- | --- | --- |
| [`{c}-ext-p_nom-lower/upper`](#generator-ext-p_nom-lower) with a bound per scenario | done | one row per scenario, over `scenario`; the tightest binds |
| [capital cost](#objective) per scenario | done | `scenario_weight` times each scenario's capital cost |

<!-- reference:rung_42_scenario_first_stage:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `5049.999999999999`, 84 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_42_scenario_first_stage.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 42: an extendable unit's capital cost and build cap differ by scenario."""

from __future__ import annotations

import spine

#: each scenario's own value, per attribute of the extendable unit
PER_SCENARIO = {
    'calm': {'capital_cost': 20, 'p_nom_max': 100},
    'stormy': {'capital_cost': 60, 'p_nom_max': 30},
}


def build():
    """The spine over two futures, with an extendable wind unit that costs more and may be built less in the stormy one."""
    n = spine.build()
    n.add('Generator', 'wind42', bus='south', p_nom_extendable=True, p_nom_max=100, marginal_cost=1, capital_cost=20)
    n.set_scenarios({'calm': 0.6, 'stormy': 0.4})
    for scenario, values in PER_SCENARIO.items():
        for column, value in values.items():
            n.c.generators.static.loc[(scenario, 'wind42'), column] = value
    return n
```

</details>
<!-- reference:rung_42_scenario_first_stage:end -->

### Rung 43 — a component's sign

`n.optimize()` with a generator, a load, a storage unit and a store whose
`sign` is not PyPSA's default. PyPSA multiplies each of their terms in
`Bus-nodal_balance` by that `sign`: a generator's `p`, a storage unit's
`p_dispatch` and `p_store`, a store's `p` (`constraints.py:1428-1429`), and a
load's `p_set` on the constant side (`constraints.py:1538`). It reads `sign`
nowhere else in the model. The default is `1` for a generator, a storage unit
and a store, and `-1` for a load. PyPSA refuses a `sign` that differs by
scenario (`consistency.py:1187`), so the file states `Generator_sign`,
`Load_sign`, `StorageUnit_sign` and `Store_sign` without `scenario`. A plain run
feeds PyPSA's defaults, and the row collapses to the standard one.

The rung adds a unit that draws `20` from its bus at a cost of `-50`, a storage
unit that opens full and a full store, each with a `sign` of `-1`, and a load of
`10` with a `sign` of `1`, which feeds its bus. Each sign binds. With the default sign on the
unit, PyPSA solves to `-5652.78`; on the load, to `3925.0`; on the storage unit,
to `1187.5`; on the store, to `925.0`; on all four, to `-5255.56`.

| PyPSA | status | note |
| --- | --- | --- |
| [`Bus-nodal_balance`](#bus-nodal_balance) with a component `sign` | done | `Generator_sign`, `StorageUnit_sign` and `Store_sign` times each term, and `Load_sign` times the load, negated |

<!-- reference:rung_43_sign:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `2125.0`, 80 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_43_sign.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 43: a component's `sign` turns its term in the bus balance around."""

from __future__ import annotations

import spine

#: the sign each component enters the bus balance with, against PyPSA's default
SIGNS = {'generators': ('flex43', -1), 'loads': ('feed43', 1), 'storage_units': ('su43', -1), 'stores': ('e43', -1)}


def build():
    """The spine with a unit that draws power, a load that feeds it, and a storage unit and a store drawn the other way round."""
    n = spine.build()
    n.add('Generator', 'flex43', bus='south', p_nom=20, marginal_cost=-50, sign=-1)
    n.add('Load', 'feed43', bus='north', p_set=10, sign=1)
    n.add('StorageUnit', 'su43', bus='south', p_nom=10, max_hours=2, state_of_charge_initial=20, sign=-1)
    n.add('Store', 'e43', bus='north', e_nom=30, e_initial=30, sign=-1)
    return n
```

</details>
<!-- reference:rung_43_sign:end -->

### Rung 45 — ramp limits per snapshot

`n.optimize()` with a generator, a link and a process whose `ramp_limit_up`
and `ramp_limit_down` change over time. PyPSA declares both `static or series`
for all three components, and `ramp_limit_start_up` and `ramp_limit_shut_down`
static. The row between two snapshots reads the limit at the later snapshot
(`constraints.py:1040-1041`, `1109-1110`, `1139-1140`). The "no limit" test is
made per snapshot (`constraints.py:1046-1047`), and a missing value reads as
the full build there (`constraints.py:1052-1055`). So the file states
`{c}_ramp_limit_up` and `{c}_ramp_limit_down` over `snapshot`, and
`{c}_ramp_up_rate` and `{c}_ramp_down_rate` with them. A snapshot without a
value has no row in the table, so the `where:` drops the row there unless a
start-up or shut-down ramp builds it. A plain run feeds the same value at each
snapshot, and the rows collapse to the standard ones.

The rung adds a steep bus with a load of `90` at the third snapshot. Each unit
may raise its output by `0.1` of its build, and by `0.5` into the third
snapshot. It may lower its output by `0.1`, and without a limit into the last
snapshot. With the constant limit `0.1` in each direction, the backup covers
the peak, and PyPSA solves to `90871.0` (#620).

| PyPSA | status | note |
| --- | --- | --- |
| [`{c}-p-ramp_limit_up/down`](#generator-p-ramp_limit_up) with a limit per snapshot | done | `{c}_ramp_limit_up`, `{c}_ramp_limit_down` and their rates span `snapshot`; a snapshot without a value drops the row unless a start-up or shut-down ramp builds it |

<!-- reference:rung_45_ramp_per_snapshot:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `10996.0`, 83 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_45_ramp_per_snapshot.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 45: ramp limits per snapshot — a generator, a link and a process whose ramp limits change over time, and lift at one snapshot."""

from __future__ import annotations

import math

import spine


def build():
    """The spine plus a steep bus served by a generator, a link and a process with ramp limits per snapshot, with a dear backup."""
    n = spine.build()
    n.add('Bus', 'steep')
    up = [0.1, 0.1, 0.5, 0.1]
    down = [0.1, 0.1, 0.1, math.nan]
    n.add('Generator', 'steep_gen', bus='steep', p_nom=60, marginal_cost=3, ramp_limit_up=up, ramp_limit_down=down)
    n.add(
        'Link',
        'steep_link',
        bus0='north',
        bus1='steep',
        p_nom=40,
        marginal_cost=4,
        ramp_limit_up=up,
        ramp_limit_down=down,
    )
    n.add(
        'Process',
        'steep_proc',
        bus0='south',
        bus1='steep',
        rate0=-1.25,
        p_nom=40,
        marginal_cost=5,
        ramp_limit_up=up,
        ramp_limit_down=down,
    )
    n.add('Generator', 'steep_backup', bus='steep', p_nom=200, marginal_cost=500)
    n.add('Load', 'steep_load', bus='steep', p_set=[10, 20, 90, 10])
    return n
```

</details>
<!-- reference:rung_45_ramp_per_snapshot:end -->

### Rung 46 — the output brought in

`n.optimize()` with units that carry `p_init`, the output they brought into the
horizon. PyPSA reads `p_init` only where a unit came in running
(`up_time_before > 0`), and reads zero where it came in off
(`constraints.py:1091-1092`). It builds the ramp rows at the first snapshot
where that value exists (`constraints.py:1094`), so a unit that came in running
without `p_init` has none there, as before. It carries the value into the first
snapshot's rows with the status the unit came in with (`constraints.py:1101-1106`).
This is the same for a Generator, a Link and a Process. It holds for a fixed,
an extendable and a committable build, and for the big-M rows of a committable
extendable build (`constraints.py:937-946`). PyPSA reads `p_init` per scenario.
Under `multi_investment_periods` it reads it only at the horizon's first
snapshot, because no ramp row stands at a later period start
(`constraints.py:1097-1099`). The file states `{c}_p_init`, and the output
carried in at the first snapshot is `{c}_status_initial * {c}_p_init`. The
first-snapshot `where:` reads `{c}_status_initial == 0 OR {c}_p_init`. A
plain run feeds no `p_init`, and the rows collapse to the standard ones.

PyPSA warns where a committable generator came in off and has a `p_init`, and
ignores the value (`consistency.py:669-680`). The product with
`{c}_status_initial` ignores it too. A unit that is not committable and came in
off is refused: see [Refusals](#refusals). PyPSA sets the first-snapshot mask
without its `active` mask, so a unit that does not stand at the first snapshot
still gets a row there, with no variable in it. The file does not state that
row.

The rung adds a warm bus with a load of `150`, then `60`, served by six
ramp-limited units: a fixed generator, a link from `p_init = 0`, a dear process
that came in at full output, an extendable generator, a committable generator
and a committable extendable generator. Each `p_init` binds. Without any of
them, PyPSA solves to `9921.0` (#620).

| PyPSA | status | note |
| --- | --- | --- |
| [`{c}-p-ramp_limit_*`](#generator-p-ramp_limit_up), [`-bigM`](#generator-p-ramp_limit_up-run-bigm), at the first snapshot | done | `{c}_previous_p` opens on `{c}_status_initial * {c}_p_init`; the row stands where `{c}_status_initial == 0 OR {c}_p_init` |

<!-- reference:rung_46_initial_output:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `101294.125`, 200 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_46_initial_output.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 46: the output brought in — units that came in running with a given `p_init` ramp from it into the first snapshot."""

from __future__ import annotations

import spine


def build():
    """The spine plus a warm bus served by fixed, extendable and committable units that each carry a `p_init`, with a dear backup."""
    n = spine.build()
    n.add('Bus', 'warm')
    ramps = {'ramp_limit_up': 0.25, 'ramp_limit_down': 0.25}
    n.add('Generator', 'warm_gen', bus='warm', p_nom=60, marginal_cost=3, p_init=10, **ramps)
    n.add('Link', 'warm_link', bus0='north', bus1='warm', p_nom=40, marginal_cost=4, p_init=0, **ramps)
    n.add(
        'Process', 'warm_proc', bus0='south', bus1='warm', rate0=-1.25, p_nom=40, marginal_cost=600, p_init=40, **ramps
    )
    n.add(
        'Generator',
        'warm_ext',
        bus='warm',
        p_nom_extendable=True,
        p_nom_max=40,
        capital_cost=5,
        marginal_cost=2,
        p_init=5,
        **ramps,
    )
    n.add(
        'Generator',
        'warm_com',
        bus='warm',
        committable=True,
        p_nom=50,
        p_min_pu=0.2,
        marginal_cost=2.5,
        p_init=30,
        ramp_limit_start_up=0.4,
        ramp_limit_shut_down=0.4,
        **ramps,
    )
    n.add(
        'Generator',
        'warm_com_ext',
        bus='warm',
        committable=True,
        p_nom_extendable=True,
        p_nom_max=40,
        capital_cost=5,
        marginal_cost=2.2,
        p_init=5,
        **ramps,
    )
    n.add('Generator', 'warm_backup', bus='warm', p_nom=300, marginal_cost=500)
    n.add('Load', 'warm_load', bus='warm', p_set=[150, 150, 60, 60])
    return n
```

</details>
<!-- reference:rung_46_initial_output:end -->

### Rung 48 — a start and a stop, unweighted

`n.optimize(multi_investment_periods=True)` with a committable unit that starts
and stops. PyPSA adds `start_up_cost * start_up` and
`shut_down_cost * shut_down` to the objective without the snapshot's objective
weight and without the period's weight (`optimize.py:414-429`). It weights every
other operating term by both (`optimize.py:262-264`). Over scenarios, it weights
the start and stop costs by the scenario's weight, as every operating term
(`optimize.py:448-452`). The file states the two terms in `scenario_opex`
without a weight, so the scenario weight is the only one they carry.

The rung builds a committable peaker that starts once and stops once in each of
two periods, with period weights `1.0` and `0.5` and snapshot weights that are
not `1.0`. PyPSA solves to `7325.0`, and to `6525.0` without the start and stop
costs. The difference is `800.0`, the four events at their unweighted cost. The
earlier file weighted them by the period, which reads `600.0` (#620).

| PyPSA | status | note |
| --- | --- | --- |
| [`start_up_cost`, `shut_down_cost`](#objective) under `multi_investment_periods` and snapshot weights | done | no snapshot weight and no period weight; the scenario weight only |

<!-- reference:rung_48_unweighted_start_up:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `7325.0`, 72 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_48_unweighted_start_up.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 48: a start and a stop cost what they cost — no snapshot weight and no period weight on them, over two weighted periods."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

OPTIMIZE = {'multi_investment_periods': True}


def build():
    """A whole network, not the spine: a committable peaker that starts and stops once in each period."""
    import pypsa

    n = pypsa.Network()
    n.snapshots = pd.MultiIndex.from_tuples(
        [(2020, datetime(2020, 1, 1, t)) for t in range(3)] + [(2030, datetime(2030, 1, 1, t)) for t in range(3)]
    )
    n.investment_periods = [2020, 2030]
    n.investment_period_weightings['objective'] = [1.0, 0.5]
    n.investment_period_weightings['years'] = [10.0, 10.0]
    n.snapshot_weightings['objective'] = [2.0, 1.5, 2.5, 2.0, 1.5, 2.5]
    n.add('Bus', 'grid')
    n.add('Generator', 'base48', bus='grid', p_nom=60, marginal_cost=10)
    n.add('Generator', 'dear48', bus='grid', p_nom=100, marginal_cost=90)
    n.add(
        'Generator',
        'peak48',
        bus='grid',
        p_nom=50,
        marginal_cost=20,
        committable=True,
        p_min_pu=0.4,
        start_up_cost=300,
        shut_down_cost=100,
        up_time_before=0,
    )
    n.add('Load', 'town48', bus='grid', p_set=[50, 100, 50, 50, 100, 50])
    return n
```

</details>
<!-- reference:rung_48_unweighted_start_up:end -->

### Rung 49 — a growth limit in one period

`n.optimize()` with a carrier that carries `max_growth`. PyPSA builds
`Carrier-growth_limit` only under `multi_investment_periods`, and returns
before it reads the carrier otherwise (`global_constraints.py:219-220`). A
single-period run has no growth limit. The file states the row where
`Carrier_max_growth` has a value, so data prep feeds no value on a
single-period run, and no row is built.

The rung adds a cheap extendable wind unit with `max_growth = 10` to the spine.
PyPSA builds it to `67` and solves to `335.0`, the same as without the limit.
The same network as one investment period under `multi_investment_periods`
caps the build at `10` and solves to `2583.33` (#620).

| PyPSA | status | note |
| --- | --- | --- |
| [`Carrier-growth_limit`](#carrier-growth_limit) without `multi_investment_periods` | done | not built; data prep feeds no `Carrier_max_growth` |

<!-- reference:rung_49_single_period_growth:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `335.0`, 42 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_49_single_period_growth.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 49: a carrier's growth limit without `multi_investment_periods` — PyPSA builds no row, so the build passes the cap."""

from __future__ import annotations

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Carrier', 'wind', max_growth=10)
    n.add('Generator', 'wind49', bus='south', carrier='wind', p_nom_extendable=True, p_nom_max=100, capital_cost=5)
    return n
```

</details>
<!-- reference:rung_49_single_period_growth:end -->

### Rung 50 — a load that is not active

`n.optimize()` with a load whose `active` is false. PyPSA masks the load side
of `Bus-nodal_balance` by `active` (`constraints.py:1537-1538`), so an inactive
load draws nothing. A load has no build year and no lifetime, so its `active` is
the static flag alone, in every snapshot and every period
(`descriptors.py:135-136`). PyPSA refuses an `active` that differs by scenario
(`consistency.py:1195`). The file states `Load_active` over the load and
`Load_demand`, the load's signed demand where it is active and zero where it
is not. The balance reads `Load_demand`. A plain run feeds every load active,
and the row collapses to the standard one.

The rung adds an inactive load to the spine's south bus. PyPSA solves to
`7380.0`, the same as without the load. With the load active, it solves to
`14730.0` (#620).

| PyPSA | status | note |
| --- | --- | --- |
| [`Bus-nodal_balance`](#bus-nodal_balance) with a load that is not `active` | done | `Load_demand` is zero where `Load_active` is false |

<!-- reference:rung_50_inactive_load:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `7380.0`, 32 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_50_inactive_load.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 50: a load that is not `active` — PyPSA drops it from its bus's balance."""

from __future__ import annotations

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Load', 'idle50', bus='south', p_set=[30, 10, 20, 40], active=False)
    return n
```

</details>
<!-- reference:rung_50_inactive_load:end -->

### Rung 51 — a growth limit after an asset retires

`n.optimize(multi_investment_periods=True)` with a carrier that carries
`max_growth`, and an extendable asset of that carrier that retires before the
last period. The file counts a build in the first period it stands in only:
`{c}_first_active` is one there and zero elsewhere. PyPSA `1.3.0` takes
`active.cumsum() == 1`, which stays true after the asset retires, so it counts
the asset again in every later period (`global_constraints.py:276`,
[PyPSA/PyPSA#1938](https://github.com/PyPSA/PyPSA/issues/1938)).

The rung builds two solar units under one carrier with `max_growth = 10`. The
old one stands in 2020 only, the new one in 2030 only. Both build to `10` in
the file. PyPSA holds the new one at `10` minus the old one's build, so it
builds nothing in 2030 and solves to `5185.0`. The oracle is the same network
with a carrier per unit, each with the same limit: each carrier has one asset,
and the repeated row PyPSA builds for the old one repeats its own bound. It
solves to `3432.5`. Without `max_growth`, the network solves to `248.75`.

| PyPSA | status | note |
| --- | --- | --- |
| [`Carrier-growth_limit`](#carrier-growth_limit) with an asset that retires | diverges | [PyPSA/PyPSA#1938](https://github.com/PyPSA/PyPSA/issues/1938); `{c}_first_active` is zero after the first period an asset stands in |

<!-- reference:rung_51_growth_retired_asset:begin -->
> ✘ `pypsa 1.3.0` solves this rung's network at objective `5185.0`, 26 rows, [PyPSA/PyPSA#1938](https://github.com/PyPSA/PyPSA/issues/1938). The intended objective is `3432.5`.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_51_growth_retired_asset.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 51: a carrier's growth limit counts an asset in the first period it stands in only, not again after it retires.

PyPSA 1.3.0 counts an asset that retires in every later period too (PyPSA/PyPSA#1938).
The oracle gives each build its own carrier with the same limit: each carrier
then has one asset, which PyPSA counts in its first period, and a retired one
counted again repeats a row it already has.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

ISSUE = 1938
OPTIMIZE = {'multi_investment_periods': True}


def network(carriers: dict[str, str]):
    """Two periods, a solar unit that stands in 2020 only and one built in 2030, each under the carrier named for it."""
    import pypsa

    n = pypsa.Network()
    n.snapshots = pd.MultiIndex.from_tuples(
        [(2020, datetime(2020, 1, 1, t)) for t in range(2)] + [(2030, datetime(2030, 1, 1, t)) for t in range(2)]
    )
    n.investment_periods = [2020, 2030]
    n.investment_period_weightings['objective'] = [1.0, 0.5]
    n.investment_period_weightings['years'] = [10.0, 10.0]
    n.snapshot_weightings['objective'] = [2.0, 1.5, 2.5, 2.0]
    n.add('Bus', 'grid')
    n.add('Carrier', 'gas')
    for carrier in sorted(set(carriers.values())):
        n.add('Carrier', carrier, max_growth=10)
    for name, build_year in (('solar_old', 2020), ('solar_new', 2030)):
        n.add(
            'Generator',
            name,
            bus='grid',
            carrier=carriers[name],
            p_nom_extendable=True,
            p_nom_max=50,
            marginal_cost=1,
            capital_cost=5,
            build_year=build_year,
            lifetime=10,
        )
    n.add('Generator', 'backup', bus='grid', carrier='gas', p_nom=100, marginal_cost=80)
    n.add('Load', 'town', bus='grid', p_set=[15, 20, 15, 20])
    return n


def build():
    """Both solar units under one carrier with `max_growth = 10`; the old one retires after 2020."""
    return network({'solar_old': 'solar', 'solar_new': 'solar'})


def oracle():
    """The same network with a carrier per build: PyPSA counts each build in its first period only."""
    return [(1.0, network({'solar_old': 'solar20', 'solar_new': 'solar30'}))]
```

</details>
<!-- reference:rung_51_growth_retired_asset:end -->

### Rung 52 — a transmission cost limit per scenario

`n.set_scenarios(...)` with a `transmission_expansion_cost_limit` row. The
file builds the row in every scenario, as it builds every global constraint.
PyPSA `1.3.0` builds no row: it matches the extendable names against a table
indexed by scenario and name, and finds none (`global_constraints.py:916`,
[PyPSA/PyPSA#1939](https://github.com/PyPSA/PyPSA/issues/1939)).

The rung adds an extendable DC link to the spine under a cost limit of `150`,
so the link builds `15`. The two futures are identical. The oracle is the same
network without scenarios, which PyPSA solves with the row to `15630.0`. With
scenarios, PyPSA solves to `11890.0`, the objective of the network without the
row.

| PyPSA | status | note |
| --- | --- | --- |
| [`transmission_expansion_cost_limit`](#transmission_expansion_cost_limit) on a network with scenarios | diverges | [PyPSA/PyPSA#1939](https://github.com/PyPSA/PyPSA/issues/1939); the row per scenario |

<!-- reference:rung_52_scenario_cost_limit:begin -->
> ✘ `pypsa 1.3.0` solves this rung's network at objective `11890.0`, 84 rows, [PyPSA/PyPSA#1939](https://github.com/PyPSA/PyPSA/issues/1939). The intended objective is `15630.0`.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_52_scenario_cost_limit.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 52: a `transmission_expansion_cost_limit` row holds in every scenario.

PyPSA 1.3.0 builds no such row on a network with scenarios (PyPSA/PyPSA#1939).
The two futures are identical, so the oracle is the same network without
scenarios, which PyPSA solves with the row.
"""

from __future__ import annotations

import spine

ISSUE = 1939


def network():
    """The spine plus an extendable DC link whose build a cost limit of 150 caps."""
    n = spine.build()
    n.add('Carrier', 'DC')
    n.add(
        'Link',
        'hvdc52',
        bus0='north',
        bus1='south',
        carrier='DC',
        p_nom_extendable=True,
        p_nom_max=100,
        capital_cost=10,
    )
    n.add('Load', 'port52', bus='south', p_set=40)
    n.add(
        'GlobalConstraint',
        'cost52',
        type='transmission_expansion_cost_limit',
        carrier_attribute='DC',
        sense='<=',
        constant=150,
    )
    return n


def build():
    """The same network over two identical futures."""
    n = network()
    n.set_scenarios({'calm': 0.6, 'stormy': 0.4})
    return n


def oracle():
    """The network without scenarios: the futures are identical, so the expected cost is its cost."""
    return [(1.0, network())]
```

</details>
<!-- reference:rung_52_scenario_cost_limit:end -->

### Rung 53 — a transmission volume limit per scenario and period

`n.set_scenarios(...)` and `n.optimize(multi_investment_periods=True)` with a
`transmission_volume_expansion_limit` row. The file builds the row in every
scenario. PyPSA `1.3.0` builds no row: the active-asset filter reindexes a table
indexed by scenario and name by the names alone, and keeps none
(`global_constraints.py:828`, `descriptors.py:263`,
[PyPSA/PyPSA#1939](https://github.com/PyPSA/PyPSA/issues/1939)). Without
periods, PyPSA builds the row (rung 40).

The rung is two periods with an extendable line of length `3` under a volume
limit of `60`, so the line builds `20`. The two futures are identical. The
oracle is the same network without scenarios, which PyPSA solves with the row to
`15005.0`. With scenarios, PyPSA solves to `1465.0`, the objective of the
network without the row.

| PyPSA | status | note |
| --- | --- | --- |
| [`transmission_volume_expansion_limit`](#transmission_volume_expansion_limit) on a network with scenarios and `multi_investment_periods` | diverges | [PyPSA/PyPSA#1939](https://github.com/PyPSA/PyPSA/issues/1939); the row per scenario |

<!-- reference:rung_53_scenario_period_volume_limit:begin -->
> ✘ `pypsa 1.3.0` solves this rung's network at objective `1465.0`, 68 rows, [PyPSA/PyPSA#1939](https://github.com/PyPSA/PyPSA/issues/1939). The intended objective is `15005.0`.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_53_scenario_period_volume_limit.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 53: a `transmission_volume_expansion_limit` row holds in every scenario under `multi_investment_periods`.

PyPSA 1.3.0 builds no such row on a network with scenarios and investment
periods (PyPSA/PyPSA#1939). The two futures are identical, so the oracle is the
same network without scenarios, which PyPSA solves with the row.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

ISSUE = 1939
OPTIMIZE = {'multi_investment_periods': True}


def network():
    """Two periods, a cheap unit behind an extendable line whose volume a limit of 60 caps."""
    import pypsa

    n = pypsa.Network()
    n.snapshots = pd.MultiIndex.from_tuples(
        [(2020, datetime(2020, 1, 1, t)) for t in range(2)] + [(2030, datetime(2030, 1, 1, t)) for t in range(2)]
    )
    n.investment_periods = [2020, 2030]
    n.investment_period_weightings['objective'] = [1.0, 0.5]
    n.investment_period_weightings['years'] = [10.0, 10.0]
    n.snapshot_weightings['objective'] = [2.0, 1.5, 2.5, 2.0]
    n.add('Bus', ['hill', 'town'])
    n.add('Carrier', 'AC')
    n.add('Generator', 'hydro53', bus='hill', p_nom=100, marginal_cost=5)
    n.add('Generator', 'diesel53', bus='town', p_nom=100, marginal_cost=90)
    n.add(
        'Line',
        'tie53',
        bus0='hill',
        bus1='town',
        x=0.1,
        carrier='AC',
        length=3,
        s_nom_extendable=True,
        s_nom_max=100,
        capital_cost=1,
        build_year=2020,
        lifetime=30,
    )
    n.add('Load', 'town_load', bus='town', p_set=[40, 50, 60, 45])
    n.add(
        'GlobalConstraint',
        'volume53',
        type='transmission_volume_expansion_limit',
        carrier_attribute='AC',
        sense='<=',
        constant=60,
    )
    return n


def build():
    """The same network over two identical futures."""
    n = network()
    n.set_scenarios({'calm': 0.6, 'stormy': 0.4})
    return n


def oracle():
    """The network without scenarios: the futures are identical, so the expected cost is its cost."""
    return [(1.0, network())]
```

</details>
<!-- reference:rung_53_scenario_period_volume_limit:end -->

### Rung 54 — a delay per scenario

`n.set_scenarios(...)` with a link `delay` and a process `delay1` that differ
by scenario. The file states `Link_output_delay`, `Link_output_cyclic_delay`,
`Process_output_delay` and `Process_output_cyclic_delay` over `scenario`, so
each future shifts a port's flow by its own delay. The shifted flow already
spans `scenario`, so the offset may too. PyPSA `1.3.0` groups the ports by
delay over all scenarios and shifts each group in every scenario, so a port
whose delay differs by scenario delivers its flow once per group
(`constraints.py:1269-1276`,
[PyPSA/PyPSA#1941](https://github.com/PyPSA/PyPSA/issues/1941)). A plain run
feeds one scenario, and the rows collapse to the standard ones.

The rung is a capped source feeding two sinks, one through a link and one
through a process. The calm future delivers at once. The stormy one delivers a
snapshot late, cyclically on the link and with the first snapshot lost on the
process. Nothing is extendable, so the futures do not interact. The oracle is
each future solved alone, `7650.0` calm and `11500.0` stormy, weighted `0.6`
and `0.4`: `9190.0`. PyPSA solves to `9300.0`.

| PyPSA | status | note |
| --- | --- | --- |
| [`Link_output_arrival`](#link_output_arrival), [`Process_output_arrival`](#process_output_arrival) with a `delay` or `cyclic_delay` that differs by scenario | diverges | [PyPSA/PyPSA#1941](https://github.com/PyPSA/PyPSA/issues/1941); the delays span `scenario` |

<!-- reference:rung_54_scenario_delay:begin -->
> ✘ `pypsa 1.3.0` solves this rung's network at objective `9300.0`, 104 rows, [PyPSA/PyPSA#1941](https://github.com/PyPSA/PyPSA/issues/1941). The intended objective is `9190.0`.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_54_scenario_delay.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 54: each scenario delays a link's and a process's flow by its own `delay`.

PyPSA 1.3.0 groups the ports by delay over all scenarios and shifts every group
in every scenario, so a port whose delay differs by scenario delivers twice
(PyPSA/PyPSA#1941). Nothing is extendable, so the scenarios do not interact: the
oracle is each future solved alone, weighted by its probability.
"""

from __future__ import annotations

from datetime import datetime

ISSUE = 1941

#: The `generators` weighting is uniform, as on rung 16, so a delay of `n` is a
#: shift of exactly `n` positions. The `objective` column stays non-uniform.
WEIGHTINGS = {'objective': [2.0, 1.5, 2.5, 3.0], 'generators': [1.0] * 4}
DEMAND = [20.0, 35.0, 5.0, 30.0]
SCENARIOS = {'calm': 0.6, 'stormy': 0.4}

#: each future's own delay, per port: the calm one delivers at once, the stormy one a snapshot late
DELAYS = {
    'calm': {'pipe54': {'delay': 0, 'cyclic_delay': True}, 'conv54': {'delay1': 0, 'cyclic_delay1': True}},
    'stormy': {'pipe54': {'delay': 1, 'cyclic_delay': True}, 'conv54': {'delay1': 1, 'cyclic_delay1': False}},
}


def network(delays: dict[str, dict[str, object]]):
    """A capped source feeding two sinks, one through a link and one through a process, with the given delays."""
    import pypsa

    n = pypsa.Network()
    n.set_snapshots([datetime(2015, 1, 1, hour) for hour in range(4)])
    for column, values in WEIGHTINGS.items():
        n.snapshot_weightings[column] = values
    n.add('Bus', ['source', 'sink_link', 'sink_process'])
    n.add('Generator', 'spring54', bus='source', p_nom=50, marginal_cost=5)
    n.add('Generator', 'backup_link54', bus='sink_link', p_nom=200, marginal_cost=100)
    n.add('Generator', 'backup_process54', bus='sink_process', p_nom=200, marginal_cost=100)
    n.add('Link', 'pipe54', bus0='source', bus1='sink_link', p_nom=30, **delays['pipe54'])
    n.add('Process', 'conv54', bus0='source', bus1='sink_process', p_nom=30, **delays['conv54'])
    n.add('Load', 'load_link54', bus='sink_link', p_set=DEMAND)
    n.add('Load', 'load_process54', bus='sink_process', p_set=DEMAND)
    return n


def build():
    """The network over two futures, each with its own delays."""
    n = network(DELAYS['calm'])
    n.set_scenarios(SCENARIOS)
    for scenario, ports in DELAYS.items():
        for name, values in ports.items():
            component = n.c.links if name == 'pipe54' else n.c.processes
            for column, value in values.items():
                component.static.loc[(scenario, name), column] = value
    return n


def oracle():
    """Each future alone, with its own delays, weighted by its probability."""
    return [(weight, network(DELAYS[scenario])) for scenario, weight in SCENARIOS.items()]
```

</details>
<!-- reference:rung_54_scenario_delay:end -->

### Rung 55 — a transformer cycle per scenario

`n.set_scenarios(...)` with two transformers in parallel, a cycle. The file
builds the Kirchhoff voltage row in every scenario. PyPSA `1.3.0` raises
`KeyError`: it selects the transformers of a cycle by name from a table indexed
by scenario and name (`constraints.py:1654`,
[PyPSA/PyPSA#1942](https://github.com/PyPSA/PyPSA/issues/1942)).

The rung adds two transformers of reactance `0.1` and `0.2`, each rated `30`,
to the spine. The row splits the flow two to one, so the first caps the pair at
`45`. The two futures are identical. The oracle is the same network without
scenarios, which PyPSA solves to `13105.0`. One transformer rated `60` solves to
`11705.0`.

| PyPSA | status | note |
| --- | --- | --- |
| [`Kirchhoff-Voltage-Law`](#kirchhoff-voltage-law) with a transformer on a network with scenarios | diverges | [PyPSA/PyPSA#1942](https://github.com/PyPSA/PyPSA/issues/1942); the row per scenario. The file holds one phase shift for every scenario |

<!-- reference:rung_55_scenario_transformer_cycle:begin -->
> ✘ `pypsa 1.3.0` raises `KeyError` on this rung's network, [PyPSA/PyPSA#1942](https://github.com/PyPSA/PyPSA/issues/1942). The intended objective is `13105.0`.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_55_scenario_transformer_cycle.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 55: a cycle of two transformers takes its Kirchhoff voltage row in every scenario.

PyPSA 1.3.0 raises on a transformer in a cycle on a network with scenarios
(PyPSA/PyPSA#1942). The two futures are identical, so the oracle is the same
network without scenarios.
"""

from __future__ import annotations

import spine

ISSUE = 1942


def network():
    """The spine plus two parallel transformers of unequal reactance, so the one that takes more flow caps the pair."""
    n = spine.build()
    n.add('Bus', ['a', 'b'])
    n.add('Generator', 'hydro55', bus='a', p_nom=100, marginal_cost=10)
    n.add('Generator', 'diesel55', bus='b', p_nom=100, marginal_cost=50)
    n.add('Load', 'town55', bus='b', p_set=[50, 40, 55, 45])
    n.add('Transformer', 't55', bus0='a', bus1='b', x=0.1, s_nom=30)
    n.add('Transformer', 't55_2', bus0='a', bus1='b', x=0.2, s_nom=30)
    return n


def build():
    """The same network over two identical futures."""
    n = network()
    n.set_scenarios({'calm': 0.6, 'stormy': 0.4})
    return n


def oracle():
    """The network without scenarios: the futures are identical, so the expected cost is its cost."""
    return [(1.0, network())]
```

</details>
<!-- reference:rung_55_scenario_transformer_cycle:end -->

### Rung 56 — a security-constrained run per scenario

`n.optimize.optimize_security_constrained(...)` on a network with scenarios.
The file builds the outage copies in every scenario. PyPSA `1.3.0` raises
`ValueError`. With outages named as a list, it finds none of them in the
network (`abstract.py:427`). With no outages named, it fails to intersect the
branches (`abstract.py:445`,
[PyPSA/PyPSA#1942](https://github.com/PyPSA/PyPSA/issues/1942)). With outages
named as `(component, name)` pairs, it builds no copy and solves without them.

The rung adds two parallel lines rated `30` and `35` to the spine, and outages
each. Each line must carry the whole import alone, so the import falls to `30`.
The two futures are identical. The oracle is the same network without
scenarios, which PyPSA solves to `18205.0`. A plain `n.optimize()` solves to
`11705.0`.

| PyPSA | status | note |
| --- | --- | --- |
| [`Line-fix-s-*-security-for-{c}-outage-in-sub-network-{n}`](#line-fix-s-lower-security-for-c-outage-in-sub-network-n) on a network with scenarios | diverges | [PyPSA/PyPSA#1942](https://github.com/PyPSA/PyPSA/issues/1942); the copies per scenario |

<!-- reference:rung_56_scenario_security_constrained:begin -->
> ✘ `pypsa 1.3.0` raises `ValueError` on this rung's network, [PyPSA/PyPSA#1942](https://github.com/PyPSA/PyPSA/issues/1942). The intended objective is `18205.0`.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_56_scenario_security_constrained.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 56: a security-constrained run over scenarios copies its rows into every scenario.

PyPSA 1.3.0 raises on a security-constrained run on a network with scenarios
(PyPSA/PyPSA#1942). The two futures are identical, so the oracle is the same
network without scenarios.
"""

from __future__ import annotations

import spine

ISSUE = 1942
BRANCH_OUTAGES = ['l56', 'l56_2']


def network():
    """The spine plus two parallel lines, so each must carry the whole import alone when the other is out."""
    n = spine.build()
    n.add('Bus', ['a', 'b'])
    n.add('Generator', 'hydro56', bus='a', p_nom=100, marginal_cost=10)
    n.add('Generator', 'diesel56', bus='b', p_nom=100, marginal_cost=50)
    n.add('Load', 'town56', bus='b', p_set=[50, 40, 55, 45])
    n.add('Line', 'l56', bus0='a', bus1='b', x=0.1, s_nom=30)
    n.add('Line', 'l56_2', bus0='a', bus1='b', x=0.1, s_nom=35)
    return n


def build():
    """The same network over two identical futures."""
    n = network()
    n.set_scenarios({'calm': 0.6, 'stormy': 0.4})
    return n


def oracle():
    """The network without scenarios: the futures are identical, so the expected cost is its cost."""
    return [(1.0, network())]
```

</details>
<!-- reference:rung_56_scenario_security_constrained:end -->

### Rung 57 — a fixed build per scenario

`n.set_scenarios(...)` with `p_nom_set` on an extendable unit. The file builds
`Generator-p_nom_set` in every scenario. PyPSA `1.3.0` raises `TypeError`: it
renames the scenario-and-name index of the set build with one name
(`constraints.py:1708`,
[PyPSA/PyPSA#1942](https://github.com/PyPSA/PyPSA/issues/1942)). The same holds
for every `*_nom_set`.

The rung adds a cheap extendable wind unit to the spine, pinned to `20`. The
two futures are identical. The oracle is the same network without scenarios,
which PyPSA solves to `4800.0`. Without `p_nom_set`, the unit builds `67` and
the network solves to `335.0`.

| PyPSA | status | note |
| --- | --- | --- |
| [`{c}-p_nom_set`](#generator-p_nom_set) on a network with scenarios | diverges | [PyPSA/PyPSA#1942](https://github.com/PyPSA/PyPSA/issues/1942); the row per scenario |

<!-- reference:rung_57_scenario_nom_set:begin -->
> ✘ `pypsa 1.3.0` raises `TypeError` on this rung's network, [PyPSA/PyPSA#1942](https://github.com/PyPSA/PyPSA/issues/1942). The intended objective is `4800.0`.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_57_scenario_nom_set.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 57: `p_nom_set` pins an extendable build on a network with scenarios.

PyPSA 1.3.0 raises on any `*_nom_set` on a network with scenarios
(PyPSA/PyPSA#1942). The two futures are identical, so the oracle is the same
network without scenarios.
"""

from __future__ import annotations

import spine

ISSUE = 1942


def network():
    """The spine plus a cheap extendable wind unit whose build is pinned below what it would choose."""
    n = spine.build()
    n.add(
        'Generator',
        'wind57',
        bus='south',
        p_nom_extendable=True,
        p_nom_max=100,
        capital_cost=5,
        p_nom_set=20,
    )
    return n


def build():
    """The same network over two identical futures."""
    n = network()
    n.set_scenarios({'calm': 0.6, 'stormy': 0.4})
    return n


def oracle():
    """The network without scenarios: the futures are identical, so the expected cost is its cost."""
    return [(1.0, network())]
```

</details>
<!-- reference:rung_57_scenario_nom_set:end -->

### Rung 58 — a committable unit per scenario

`n.set_scenarios(...)` with a committable unit. The file builds the status
rows in every scenario. PyPSA `1.3.0` raises `KeyError`: it selects the status
by snapshot and name where the first dimension is the scenario
(`constraints.py:1872`,
[PyPSA/PyPSA#1913](https://github.com/PyPSA/PyPSA/issues/1913)).

The rung adds a cheap committable unit to the spine that cannot run below `40`
% of its build, with a start-up cost of `100`. The two futures are identical.
The oracle is the same network without scenarios, which PyPSA solves to
`7430.0`. The same unit, not committable, solves to `7330.0`.

| PyPSA | status | note |
| --- | --- | --- |
| a committable component on a network with scenarios | diverges | [PyPSA/PyPSA#1913](https://github.com/PyPSA/PyPSA/issues/1913); the rows per scenario |

<!-- reference:rung_58_scenario_committable:begin -->
> ✘ `pypsa 1.3.0` raises `KeyError` on this rung's network, [PyPSA/PyPSA#1913](https://github.com/PyPSA/PyPSA/issues/1913). The intended objective is `7430.0`.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_58_scenario_committable.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 58: a committable unit takes its status rows in every scenario.

PyPSA 1.3.0 raises on a committable component on a network with scenarios
(PyPSA/PyPSA#1913). The two futures are identical, so the oracle is the same
network without scenarios.
"""

from __future__ import annotations

import spine

ISSUE = 1913


def network():
    """The spine plus a cheap committable unit that cannot run below 40 % of its build."""
    n = spine.build()
    n.add(
        'Generator',
        'uc58',
        bus='north',
        committable=True,
        p_nom=50,
        marginal_cost=5,
        p_min_pu=0.4,
        min_up_time=2,
        up_time_before=0,
        start_up_cost=100,
    )
    n.add('Load', 'swing58', bus='north', p_set=[5, 45, 45, 10])
    return n


def build():
    """The same network over two identical futures."""
    n = network()
    n.set_scenarios({'calm': 0.6, 'stormy': 0.4})
    return n


def oracle():
    """The network without scenarios: the futures are identical, so the expected cost is its cost."""
    return [(1.0, network())]
```

</details>
<!-- reference:rung_58_scenario_committable:end -->

## Refusals

Where PyPSA refuses to build, parity means refusing too. None is a language
gap. The maintenance checks are assumptions of the file, which the consumer
that binds the data runs. Each other one is a data check not made yet, and
where it should live — language, data prep, or harness — is one open question. Line numbers are pinned pypsa
1.3.0, the version the records above are from.

| PyPSA raises                                 | on                                                | here                    | note |
| -------------------------------------------- | ------------------------------------------------- | ----------------------- | ---- |
| `ValueError`, `optimize.py:467-474`          | a nonzero `marginal_cost_quadratic` on any Generator, Link, Process, StorageUnit or Store under a risk preference | assumed where `omega > 0`: [`Generator_marginal_cost_quadratic_without_risk_preference`](#generator_marginal_cost_quadratic_without_risk_preference), and the `Link`, `Process`, `StorageUnit` and `Store` ones. The file cannot tell no risk preference from `omega = 0`, which PyPSA also refuses | |
| `ValueError`, `constraints.py:1850`          | fixed modular `p_nom` not a multiple of `p_nom_mod` | a fractional module cap | X1   |
| `ValueError`, `constraints.py:1557`          | load on a bus with nothing attached               | row not built, unserved | X2   |
| `ValueError`, `optimize.py:436`              | no component carries a cost                       | feasibility problem     | X3   |
| `NotImplementedError`, `global_constraints.py:457`, `:509`, `:656`, `:704` | storage that carries its level across periods in a `primary_energy` or `operational_limit` row, with period `years` `!= 1` | assumed: [`StorageUnit_primary_energy_carried_over_has_unit_years`](#storageunit_primary_energy_carried_over_has_unit_years), [`StorageUnit_operational_limit_carried_over_has_unit_years`](#storageunit_operational_limit_carried_over_has_unit_years), and the `Store` ones | |
| `KeyError`, `global_constraints.py:474`, `:526` | a `primary_energy` row for one period over storage that reopens per period | assumed: [`StorageUnit_primary_energy_per_period_closes_over_the_horizon`](#storageunit_primary_energy_per_period_closes_over_the_horizon), and the `Store` one | |
| `UnboundLocalError`, `global_constraints.py:375`, `:602` | a `primary_energy` or `operational_limit` row that names an `investment_period` without `multi_investment_periods` | data prep, at `GlobalConstraint_counts_snapshot` | |
| `ValueError`, `constraints.py:2411`, `:2518` | an extendable lossy branch with `s_nom_max = inf`, either mode | data prep, at `Line_loss_max` and `Transformer_loss_max` | X4   |
| `RuntimeError`, `constraints.py:2561`        | the secant loop passing `max_segments`            | data prep, at the `segment` axis | X4   |
| `ValueError`, `abstract.py:427`, `:445`      | a security-constrained run over scenarios         | rows per scenario, not refused: a PyPSA bug, [PyPSA/PyPSA#1942](https://github.com/PyPSA/PyPSA/issues/1942), rung 56 | |
| `NotImplementedError`, `global_constraints.py:66-68` | a `tech_capacity_expansion_limit` row on a network with scenarios | assumed where there is more than one scenario: [`GlobalConstraint_tech_capacity_expansion_limit_without_scenarios`](#globalconstraint_tech_capacity_expansion_limit_without_scenarios). The file cannot tell one scenario from none, which PyPSA also refuses | |
| `ConsistencyError`, `consistency.py:1506-1560` | a maintainable component whose `maintenance_duration` or `maintenance_events` is not positive, whose events do not fit the weighted horizon, or that is extendable with `p_nom_max = inf` | assumed: [`Generator_maintenance_events_positive`](#generator_maintenance_events_positive), [`-duration_positive`](#generator_maintenance_duration_positive), [`-duration_fits_the_horizon`](#generator_maintenance_duration_fits_the_horizon), [`-events_fit_the_horizon`](#generator_maintenance_events_fit_the_horizon), [`-build_cap_is_finite`](#generator_maintenance_build_cap_is_finite), and the `Link` and `Process` ones | |
| nothing; HiGHS refuses the model, `constraints.py:500-503` | a fixed modular committable maintainable build, whose module count `p_nom_max / p_nom_mod` is infinite | assumed: [`Generator_maintenance_module_count_is_finite`](#generator_maintenance_module_count_is_finite), and the `Link` and `Process` ones | |
| nothing; PyPSA builds the row, `constraints.py:1091-1094`, `1110-1112` | a ramp-limited Generator, Link or Process that is not committable, with `up_time_before = 0` | assumed: [`Generator_came_in_running_unless_committable`](#generator_came_in_running_unless_committable), and the `Link` and `Process` ones. PyPSA caps the unit at zero in the first snapshot, or at its start-up ramp where another unit of the component is committable with a fixed build, and documents `up_time_before` as read only for a committable unit | |

Duals and solutions are read back by the harness on the specsolve side:
`marginal_price` is the balance dual over `w_objective`, `mu_upper` the
concatenation of the regime blocks, `p0`/`p1` derived from `Link-p`.

## The file

<!-- gallery:begin -->
A plain `n.optimize()`, and its multi-period and stochastic classes, in one file. Every second-stage quantity spans a `scenario` (a future dispatch is chosen in) and every asset stands in the investment `period`s its build year and lifetime span. A parameter spans `scenario` exactly when PyPSA reads it per scenario. Capacity is chosen once, before the future is known, and paid once per active period at its cost in expectation over the scenarios; operation is the expectation over the scenarios' weights, with a share priced at the tail through the CVaR rows, which stand only where that share is positive. A plain run feeds one scenario, one period, all-active masks and unit weights, and the model collapses to the standard one. A security-constrained run copies each branch flow limit once per outage in an `outage` set that a plain run leaves empty. Which snapshots an asset is active in, a scenario's weight, and the outage factors are data prep.

#### Sets

| Symbol | Meaning |
|---|---|
| $`\Xi`$ | index $`\xi`$ — `scenario` with $`\mathrm{Generator\_maintenance\_cover} \subseteq \Xi \times \mathcal{G} \times \mathcal{T} \times \mathcal{T},\ \mathrm{Link\_maintenance\_cover} \subseteq \Xi \times \mathcal{L} \times \mathcal{T} \times \mathcal{T},\ \mathrm{Process\_maintenance\_cover} \subseteq \Xi \times \mathcal{J} \times \mathcal{T} \times \mathcal{T}`$ — the futures dispatch is chosen in, each with a weight |
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` with $`\mathrm{snapshot\_period}: \mathcal{T} \to \mathcal{Y},\ \mathrm{Generator\_maintenance\_cover} \subseteq \Xi \times \mathcal{G} \times \mathcal{T} \times \mathcal{T},\ \mathrm{Link\_maintenance\_cover} \subseteq \Xi \times \mathcal{L} \times \mathcal{T} \times \mathcal{T},\ \mathrm{Process\_maintenance\_cover} \subseteq \Xi \times \mathcal{J} \times \mathcal{T} \times \mathcal{T}`$ — dispatch periods |
| $`\mathcal{N}`$ | index $`n`$ — `bus` with $`\mathrm{Generator\_bus}: \mathcal{G} \to \mathcal{N},\ \mathrm{Link\_bus0}: \mathcal{L} \to \mathcal{N},\ \mathrm{Link\_output\_bus}: \mathcal{O} \to \mathcal{N},\ \mathrm{Process\_output\_bus}: \mathcal{R} \to \mathcal{N},\ \mathrm{Load\_bus}: \mathcal{D} \to \mathcal{N},\ \mathrm{StorageUnit\_bus}: \mathcal{S} \to \mathcal{N},\ \mathrm{Line\_bus0}: \mathcal{K} \to \mathcal{N},\ \mathrm{Line\_bus1}: \mathcal{K} \to \mathcal{N},\ \mathrm{Store\_bus}: \mathcal{V} \to \mathcal{N},\ \mathrm{Transformer\_bus0}: \mathcal{M} \to \mathcal{N},\ \mathrm{Transformer\_bus1}: \mathcal{M} \to \mathcal{N}`$ — network nodes |
| $`\mathcal{G}`$ | index $`g`$ — `generator` with $`\mathrm{Generator\_carrier}: \mathcal{G} \to \mathcal{I},\ \mathrm{Generator\_bus}: \mathcal{G} \to \mathcal{N},\ \mathrm{Generator\_maintenance\_cover} \subseteq \Xi \times \mathcal{G} \times \mathcal{T} \times \mathcal{T}`$ — generating units, each on one bus |
| $`\mathcal{L}`$ | index $`l`$ — `link` with $`\mathrm{Link\_carrier}: \mathcal{L} \to \mathcal{I},\ \mathrm{Link\_bus0}: \mathcal{L} \to \mathcal{N},\ \mathrm{Link\_output\_link}: \mathcal{O} \to \mathcal{L},\ \mathrm{Link\_maintenance\_cover} \subseteq \Xi \times \mathcal{L} \times \mathcal{T} \times \mathcal{T}`$ — controllable connections, each from one bus to the buses it delivers to |
| $`\mathcal{O}`$ | index $`o`$ — `link_output` with $`\mathrm{Link\_output\_link}: \mathcal{O} \to \mathcal{L},\ \mathrm{Link\_output\_bus}: \mathcal{O} \to \mathcal{N}`$ — a link's output ports, one label per port a link declares — PyPSA's `bus1`, `bus2`, … columns read long, so a link of any number of output ports is one term in the balance, data prep |
| $`\mathcal{J}`$ | index $`j`$ — `process` with $`\mathrm{Process\_carrier}: \mathcal{J} \to \mathcal{I},\ \mathrm{Process\_output\_process}: \mathcal{R} \to \mathcal{J},\ \mathrm{Process\_maintenance\_cover} \subseteq \Xi \times \mathcal{J} \times \mathcal{T} \times \mathcal{T}`$ — generalized multi-port converters, each with an internal power that every port draws or delivers at its own rate |
| $`\mathcal{R}`$ | index $`r`$ — `process_output` with $`\mathrm{Process\_output\_process}: \mathcal{R} \to \mathcal{J},\ \mathrm{Process\_output\_bus}: \mathcal{R} \to \mathcal{N}`$ — a process's ports, one label per port a process declares — PyPSA's `bus0`, `bus1`, … each carry a signed `rate`, so a process of any number of ports is one term in the balance, data prep |
| $`\mathcal{D}`$ | index $`d`$ — `load` with $`\mathrm{Load\_bus}: \mathcal{D} \to \mathcal{N}`$ — demands, each on one bus |
| $`\mathcal{S}`$ | index $`s`$ — `storage_unit` with $`\mathrm{StorageUnit\_carrier}: \mathcal{S} \to \mathcal{I},\ \mathrm{StorageUnit\_bus}: \mathcal{S} \to \mathcal{N}`$ — storage units, dispatch and store behind one bus connection |
| $`\mathcal{V}`$ | index $`v`$ — `store` with $`\mathrm{Store\_carrier}: \mathcal{V} \to \mathcal{I},\ \mathrm{Store\_bus}: \mathcal{V} \to \mathcal{N}`$ — pure energy stores, each on one bus |
| $`\mathcal{K}`$ | index $`k`$ — `line` with $`\mathrm{Line\_carrier}: \mathcal{K} \to \mathcal{I},\ \mathrm{Line\_bus0}: \mathcal{K} \to \mathcal{N},\ \mathrm{Line\_bus1}: \mathcal{K} \to \mathcal{N},\ \mathrm{Outage\_line}: \mathcal{K}^{\mathrm{out}} \to \mathcal{K}`$ — passive branches, each between two buses, their flow set by impedance |
| $`\mathcal{M}`$ | index $`m`$ — `transformer` with $`\mathrm{Transformer\_bus0}: \mathcal{M} \to \mathcal{N},\ \mathrm{Transformer\_bus1}: \mathcal{M} \to \mathcal{N},\ \mathrm{Outage\_transformer}: \mathcal{K}^{\mathrm{out}} \to \mathcal{M}`$ — passive branches between two buses, their flow set by impedance and tap ratio, with a phase shift fixed or optimised |
| $`\mathcal{C}`$ | index $`c`$ — `cycle` — independent cycles of the passive network graph — the cycle basis, data prep |
| $`\mathcal{K}^{\mathrm{out}}`$ | index $`\kappa`$ — `outage` with $`\mathrm{Outage\_line}: \mathcal{K}^{\mathrm{out}} \to \mathcal{K},\ \mathrm{Outage\_transformer}: \mathcal{K}^{\mathrm{out}} \to \mathcal{M}`$ — the passive branches a security-constrained run takes out one at a time — PyPSA's `branch_outages`, each a line or a transformer; none on a plain run |
| $`\mathcal{B}`$ | index $`b`$ — `segment` — the cuts a passive branch's loss curve is held above — PyPSA's tangents, as many as its `segments` count, or its secants, as many as its tolerance loop places; none in a lossless run |
| $`\mathcal{I}`$ | index $`i`$ — `global_constraint` — PyPSA's `GlobalConstraint` rows, one label per declared limit |
| $`\mathcal{Y}`$ | index $`y`$ — `period` with $`\mathrm{snapshot\_period}: \mathcal{T} \to \mathcal{Y}`$ — investment periods — PyPSA's `investment_periods` |
| $`\mathcal{I}`$ | index $`i`$ — `carrier` with $`\mathrm{Generator\_carrier}: \mathcal{G} \to \mathcal{I},\ \mathrm{Link\_carrier}: \mathcal{L} \to \mathcal{I},\ \mathrm{Process\_carrier}: \mathcal{J} \to \mathcal{I},\ \mathrm{StorageUnit\_carrier}: \mathcal{S} \to \mathcal{I},\ \mathrm{Line\_carrier}: \mathcal{K} \to \mathcal{I},\ \mathrm{Store\_carrier}: \mathcal{V} \to \mathcal{I}`$ — energy carriers, what a growth limit is set per |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{w}`$ | `snapshot_weightings_objective` over $`\mathcal{T}`$ — PyPSA's `snapshot_weightings.objective` — hours a snapshot stands for in the cost |
| $`\mathrm{p}^{\mathrm{nom}}`$ | `Generator_p_nom` over $`\Xi \times \mathcal{G}`$ — nominal power |
| $`\mathrm{ext}`$ | `Generator_p_nom_extendable` over $`\mathcal{G}`$ — whether the nominal power is a decision |
| $`\underline{\mathrm{p}}`$ | `Generator_p_min_pu` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — least output, per unit of nominal power |
| $`\overline{\mathrm{p}}`$ | `Generator_p_max_pu` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — most output, per unit of nominal power — an availability profile |
| $`\mathrm{c}`$ | `Generator_marginal_cost` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — cost of one unit of output |
| $`\mathrm{c}^{(2)}`$ | `Generator_marginal_cost_quadratic` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — cost of the square of one unit of output |
| $`\mathrm{sgn}`$ | `Generator_sign` over $`\mathcal{G}`$ — the sign output enters its bus's balance with — PyPSA's `sign`, `1` unless given, `-1` for a unit that draws power. PyPSA refuses one that differs by scenario (`consistency.py:1187`) |
| $`\mathrm{com}`$ | `Generator_committable` over $`\mathcal{G}`$ — whether output is gated by an on/off status decision |
| $`\mathrm{ru}`$ | `Generator_ramp_limit_up` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — most a generator may raise its output between snapshots, per unit of nominal power; no value means no limit — read at the later of the two snapshots, so the limit may change over time |
| $`\mathrm{rd}`$ | `Generator_ramp_limit_down` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — most a generator may lower its output between snapshots, per unit of nominal power; no value means no limit — read at the later of the two snapshots, so the limit may change over time |
| $`\mathrm{ru}^{\mathrm{up}}`$ | `Generator_ramp_limit_start_up` over $`\Xi \times \mathcal{G}`$ — most output in the snapshot a unit starts, per unit of nominal power |
| $`\mathrm{rd}^{\mathrm{dn}}`$ | `Generator_ramp_limit_shut_down` over $`\Xi \times \mathcal{G}`$ — most output in the snapshot before a unit stops, per unit of nominal power |
| $`\mathrm{UT}`$ | `Generator_min_up_time` over $`\Xi \times \mathcal{G}`$ — least snapshots a unit stays on once started |
| $`\mathrm{DT}`$ | `Generator_min_down_time` over $`\Xi \times \mathcal{G}`$ — least snapshots a unit stays off once stopped |
| $`\mathrm{u}^{0}`$ | `Generator_status_initial` over $`\Xi \times \mathcal{G}`$ — one where the unit was on before the first snapshot, zero where off — PyPSA's `up_time_before > 0`, data prep |
| $`\mathrm{p}^{0}`$ | `Generator_p_init` over $`\Xi \times \mathcal{G}`$ — the output a unit brought into the horizon — PyPSA's `p_init`, read only where the unit came in running; no value means it is unknown, so the unit carries no ramp row at the first snapshot |
| $`\mathrm{hold}`$ | `Generator_must_stay_up` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — true while the up time a unit brought into the horizon still binds — data prep, since `position()` compares against a literal rather than a parameter |
| $`\mathrm{rest}`$ | `Generator_must_stay_down` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — true while the down time a unit brought into the horizon still binds — PyPSA's `min_down_time - down_time_before` snapshots, where `down_time_before > 0`, data prep for the same reason |
| $`\mathrm{c}^{\mathrm{up}}`$ | `Generator_start_up_cost` over $`\Xi \times \mathcal{G}`$ — cost of one start |
| $`\mathrm{c}^{\mathrm{dn}}`$ | `Generator_shut_down_cost` over $`\Xi \times \mathcal{G}`$ — cost of one stop |
| $`\mathrm{c}^{\mathrm{on}}`$ | `Generator_stand_by_cost` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — cost of one snapshot spent on |
| $`\mathrm{p}^{\mathrm{mod}}`$ | `Generator_p_nom_mod` over $`\mathcal{G}`$ — the module size a build comes in whole numbers of; no value means the build is continuous |
| $`\mathrm{N}^{\mathrm{fix}}`$ | `Generator_modules_installed` over $`\Xi \times \mathcal{G}`$ — how many whole modules a committable build has in place: `Generator_p_nom / Generator_p_nom_mod` where a fixed build is modular, one where it is not, data prep. PyPSA refuses a fixed modular build whose nominal power is not a whole number of modules |
| $`\mathrm{M}`$ | `Generator_big_m` over $`\Xi \times \mathcal{G}`$ — a bound safely above any feasible output — the build cap at full availability, data prep |
| $`\mathrm{nonneg}`$ | `Generator_p_min_pu_nonneg` over $`\mathcal{G}`$ — true where none of the generator's own minimums-per-unit is negative — PyPSA's per-unit `(p_min_pu >= 0).all()` over every snapshot and scenario, data prep |
| $`\mathrm{mnt}`$ | `Generator_maintainable` over $`\mathcal{G}`$ — whether a generator must be taken off for maintenance within the horizon — in any scenario, as PyPSA takes the union over them (`components.py:1016-1019`) |
| $`\gamma`$ | `Generator_maintenance_pu` over $`\Xi \times \mathcal{G}`$ — the share of the build a maintenance event takes off |
| $`\mathrm{n}^{\mathrm{mnt}}`$ | `Generator_maintenance_events` over $`\Xi \times \mathcal{G}`$ — how many maintenance events the horizon holds |
| $`\tau^{\mathrm{mnt}}`$ | `Generator_maintenance_duration` over $`\Xi \times \mathcal{G}`$ — the hours of generator weightings one maintenance event covers — PyPSA's `maintenance_duration`; no value where the generator is not maintainable. No row reads it: data prep turns it into `Generator_maintenance_cover` and `Generator_maintenance_start_blocked`, and the assumptions hold it to the horizon |
| $`\mathrm{blk}`$ | `Generator_maintenance_start_blocked` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — true where no maintenance event may start, because the snapshots it would cover run past the end of the horizon or into one the generator does not stand in — PyPSA's `active & ~valid`, from `maintenance_duration` and the generator weightings, data prep |
| $`\mathrm{ru}^{f}`$ | `Link_ramp_limit_up` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — most a link may raise its flow between snapshots, per unit of nominal power; no value means no limit — read at the later of the two snapshots, so the limit may change over time |
| $`\mathrm{rd}^{f}`$ | `Link_ramp_limit_down` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — most a link may lower its flow between snapshots, per unit of nominal power; no value means no limit — read at the later of the two snapshots, so the limit may change over time |
| $`\mathrm{f}^{\mathrm{nom}}`$ | `Link_p_nom` over $`\Xi \times \mathcal{L}`$ — nominal power |
| $`\mathrm{ext}^{f}`$ | `Link_p_nom_extendable` over $`\mathcal{L}`$ — whether the nominal power is a decision |
| $`\underline{\mathrm{f}}`$ | `Link_p_min_pu` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — least flow, per unit of nominal power — negative for a link that carries both ways |
| $`\overline{\mathrm{f}}`$ | `Link_p_max_pu` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — most flow, per unit of nominal power |
| $`\eta`$ | `Link_efficiency` over $`\Xi \times \mathcal{O}`$ — share of the flow that arrives at an output port, PyPSA's `efficiency`, `efficiency2`, … read long — negative where that port consumes rather than delivers |
| $`\mathrm{d}^{f}`$ | `Link_output_delay` over $`\Xi \times \mathcal{O}`$ — snapshots a port's delivery lags its link's flow — PyPSA's `delay`, `delay2`, … read long, in `snapshot_weightings.generators` units, which the file states as whole snapshots; zero for a port that delivers at once. Each scenario takes its own. PyPSA `1.3.0` groups the ports by delay over all scenarios and shifts each group in every one, so a delay that differs by scenario delivers the flow twice (`constraints.py:1269-1276`, PyPSA/PyPSA\#1941) |
| $`\mathrm{cyc}^{f}`$ | `Link_output_cyclic_delay` over $`\Xi \times \mathcal{O}`$ — whether a delayed port's flow wraps from the end of its investment period — PyPSA's `cyclic_delay`, `cyclic_delay2`, …; where it does not, the flow still in transit at each period's first snapshots is lost. Each scenario takes its own, as the delay |
| $`\mathrm{c}^{f}`$ | `Link_marginal_cost` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — cost of one unit of flow |
| $`\mathrm{c}^{f,(2)}`$ | `Link_marginal_cost_quadratic` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — cost of the square of one unit of flow |
| $`\mathrm{com}^{f}`$ | `Link_committable` over $`\mathcal{L}`$ — whether flow is gated by an on/off status decision |
| $`\mathrm{ru}^{f,\mathrm{up}}`$ | `Link_ramp_limit_start_up` over $`\Xi \times \mathcal{L}`$ — most flow in the snapshot a link starts, per unit of nominal power |
| $`\mathrm{rd}^{f,\mathrm{dn}}`$ | `Link_ramp_limit_shut_down` over $`\Xi \times \mathcal{L}`$ — most flow in the snapshot before a link stops, per unit of nominal power |
| $`\mathrm{UT}^{f}`$ | `Link_min_up_time` over $`\Xi \times \mathcal{L}`$ — least snapshots a link stays on once started |
| $`\mathrm{DT}^{f}`$ | `Link_min_down_time` over $`\Xi \times \mathcal{L}`$ — least snapshots a link stays off once stopped |
| $`\mathrm{u}^{f,0}`$ | `Link_status_initial` over $`\Xi \times \mathcal{L}`$ — one where the link was on before the first snapshot, zero where off — PyPSA's `up_time_before > 0`, data prep |
| $`\mathrm{f}^{0}`$ | `Link_p_init` over $`\Xi \times \mathcal{L}`$ — the flow a link brought into the horizon — PyPSA's `p_init`, read only where the link came in running; no value means it is unknown, so the link carries no ramp row at the first snapshot |
| $`\mathrm{hold}^{f}`$ | `Link_must_stay_up` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — true while the up time a link brought into the horizon still binds — data prep, since `position()` compares against a literal rather than a parameter |
| $`\mathrm{rest}^{f}`$ | `Link_must_stay_down` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — true while the down time a link brought into the horizon still binds — PyPSA's `min_down_time - down_time_before` snapshots, where `down_time_before > 0`, data prep for the same reason |
| $`\mathrm{c}^{f,\mathrm{up}}`$ | `Link_start_up_cost` over $`\Xi \times \mathcal{L}`$ — cost of one start |
| $`\mathrm{c}^{f,\mathrm{dn}}`$ | `Link_shut_down_cost` over $`\Xi \times \mathcal{L}`$ — cost of one stop |
| $`\mathrm{c}^{f,\mathrm{on}}`$ | `Link_stand_by_cost` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — cost of one snapshot spent on |
| $`\mathrm{f}^{\mathrm{mod}}`$ | `Link_p_nom_mod` over $`\mathcal{L}`$ — the module size a build comes in whole numbers of; no value means the build is continuous |
| $`\mathrm{N}^{f,\mathrm{fix}}`$ | `Link_modules_installed` over $`\Xi \times \mathcal{L}`$ — how many whole modules a committable build has in place: `Link_p_nom / Link_p_nom_mod` where a fixed build is modular, one where it is not, data prep. PyPSA refuses a fixed modular build whose nominal power is not a whole number of modules |
| $`\mathrm{M}^{f}`$ | `Link_big_m` over $`\Xi \times \mathcal{L}`$ — a bound safely above any feasible flow — the build cap at full availability, data prep |
| $`\mathrm{nonneg}^{f}`$ | `Link_p_min_pu_nonneg` over $`\mathcal{L}`$ — true where none of the link's own minimums-per-unit is negative — PyPSA's per-unit `(p_min_pu >= 0).all()` over every snapshot and scenario, data prep |
| $`\mathrm{mnt}^{f}`$ | `Link_maintainable` over $`\mathcal{L}`$ — whether a link must be taken off for maintenance within the horizon — in any scenario, as PyPSA takes the union over them (`components.py:1016-1019`) |
| $`\gamma^{f}`$ | `Link_maintenance_pu` over $`\Xi \times \mathcal{L}`$ — the share of the build a maintenance event takes off |
| $`\mathrm{n}^{f,\mathrm{mnt}}`$ | `Link_maintenance_events` over $`\Xi \times \mathcal{L}`$ — how many maintenance events the horizon holds |
| $`\tau^{f,\mathrm{mnt}}`$ | `Link_maintenance_duration` over $`\Xi \times \mathcal{L}`$ — the hours of generator weightings one maintenance event covers — PyPSA's `maintenance_duration`; no value where the link is not maintainable. No row reads it: data prep turns it into `Link_maintenance_cover` and `Link_maintenance_start_blocked`, and the assumptions hold it to the horizon |
| $`\mathrm{blk}^{f}`$ | `Link_maintenance_start_blocked` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — true where no maintenance event may start, because the snapshots it would cover run past the end of the horizon or into one the link does not stand in — PyPSA's `active & ~valid`, from `maintenance_duration` and the generator weightings, data prep |
| $`\mathrm{z}^{\mathrm{nom}}`$ | `Process_p_nom` over $`\Xi \times \mathcal{J}`$ — nominal internal power |
| $`\mathrm{ext}^{z}`$ | `Process_p_nom_extendable` over $`\mathcal{J}`$ — whether the nominal internal power is a decision |
| $`\underline{\mathrm{z}}`$ | `Process_p_min_pu` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — least internal power, per unit of nominal power — negative for a process that runs both ways |
| $`\overline{\mathrm{z}}`$ | `Process_p_max_pu` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — most internal power, per unit of nominal power |
| $`\alpha`$ | `Process_rate` over $`\Xi \times \mathcal{R}`$ — the energy a port draws or delivers per unit of internal power, PyPSA's `rate0`, `rate1`, … read long — negative where the port withdraws, positive where it injects; a link is a process whose `bus0` rate is minus one and whose output rates are its efficiencies |
| $`\mathrm{d}^{z}`$ | `Process_output_delay` over $`\Xi \times \mathcal{R}`$ — snapshots a port's transfer lags its process's internal power — PyPSA's `delay0`, `delay1`, … read long, in `snapshot_weightings.generators` units, which the file states as whole snapshots; zero for a port that transfers at once. Each scenario takes its own, as a link's |
| $`\mathrm{cyc}^{z}`$ | `Process_output_cyclic_delay` over $`\Xi \times \mathcal{R}`$ — whether a delayed port's transfer wraps from the end of its investment period — PyPSA's `cyclic_delay0`, `cyclic_delay1`, …; where it does not, the energy still in transit at each period's first snapshots is lost. Each scenario takes its own, as the delay |
| $`\mathrm{c}^{z}`$ | `Process_marginal_cost` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — cost of one unit of internal power |
| $`\mathrm{c}^{z,(2)}`$ | `Process_marginal_cost_quadratic` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — cost of the square of one unit of internal power |
| $`\mathrm{ru}^{z}`$ | `Process_ramp_limit_up` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — most a process may raise its internal power between snapshots, per unit of nominal power; no value means no limit — read at the later of the two snapshots, so the limit may change over time |
| $`\mathrm{rd}^{z}`$ | `Process_ramp_limit_down` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — most a process may lower its internal power between snapshots, per unit of nominal power; no value means no limit — read at the later of the two snapshots, so the limit may change over time |
| $`\mathrm{z}^{\mathrm{set}}`$ | `Process_p_set` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — a given internal power schedule; a process without one has no row here |
| $`\underline{\mathrm{z}}^{\mathrm{nom}}`$ | `Process_p_nom_min` over $`\Xi \times \mathcal{J}`$ — least nominal power an extendable process may be built at |
| $`\overline{\mathrm{z}}^{\mathrm{nom}}`$ | `Process_p_nom_max` over $`\Xi \times \mathcal{J}`$ — most nominal power an extendable process may be built at |
| $`\mathrm{c}^{\mathrm{cap},z}`$ | `Process_capital_cost` over $`\Xi \times \mathcal{J}`$ — cost of one unit of nominal power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $`\mathrm{z}^{\mathrm{nom,set}}`$ | `Process_p_nom_set` over $`\Xi \times \mathcal{J}`$ — a given nominal power for an extendable process; one without a value has no row here |
| $`\mathrm{com}^{z}`$ | `Process_committable` over $`\mathcal{J}`$ — whether internal power is gated by an on/off status decision |
| $`\mathrm{ru}^{z,\mathrm{up}}`$ | `Process_ramp_limit_start_up` over $`\Xi \times \mathcal{J}`$ — most internal power in the snapshot a process starts, per unit of nominal power |
| $`\mathrm{rd}^{z,\mathrm{dn}}`$ | `Process_ramp_limit_shut_down` over $`\Xi \times \mathcal{J}`$ — most internal power in the snapshot before a process stops, per unit of nominal power |
| $`\mathrm{UT}^{z}`$ | `Process_min_up_time` over $`\Xi \times \mathcal{J}`$ — least snapshots a process stays on once started |
| $`\mathrm{DT}^{z}`$ | `Process_min_down_time` over $`\Xi \times \mathcal{J}`$ — least snapshots a process stays off once stopped |
| $`\mathrm{u}^{z,0}`$ | `Process_status_initial` over $`\Xi \times \mathcal{J}`$ — one where the process was on before the first snapshot, zero where off — PyPSA's `up_time_before > 0`, data prep |
| $`\mathrm{z}^{0}`$ | `Process_p_init` over $`\Xi \times \mathcal{J}`$ — the internal power a process brought into the horizon — PyPSA's `p_init`, read only where the process came in running; no value means it is unknown, so the process carries no ramp row at the first snapshot |
| $`\mathrm{hold}^{z}`$ | `Process_must_stay_up` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — true while the up time a process brought into the horizon still binds — data prep, since `position()` compares against a literal rather than a parameter |
| $`\mathrm{rest}^{z}`$ | `Process_must_stay_down` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — true while the down time a process brought into the horizon still binds — PyPSA's `min_down_time - down_time_before` snapshots, where `down_time_before > 0`, data prep for the same reason |
| $`\mathrm{c}^{z,\mathrm{up}}`$ | `Process_start_up_cost` over $`\Xi \times \mathcal{J}`$ — cost of one start |
| $`\mathrm{c}^{z,\mathrm{dn}}`$ | `Process_shut_down_cost` over $`\Xi \times \mathcal{J}`$ — cost of one stop |
| $`\mathrm{c}^{z,\mathrm{on}}`$ | `Process_stand_by_cost` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — cost of one snapshot spent on |
| $`\mathrm{z}^{\mathrm{mod}}`$ | `Process_p_nom_mod` over $`\mathcal{J}`$ — the module size a build comes in whole numbers of; no value means the build is continuous |
| $`\mathrm{N}^{z,\mathrm{fix}}`$ | `Process_modules_installed` over $`\Xi \times \mathcal{J}`$ — how many whole modules a committable build has in place: `Process_p_nom / Process_p_nom_mod` where a fixed build is modular, one where it is not, data prep. PyPSA refuses a fixed modular build whose nominal power is not a whole number of modules |
| $`\mathrm{M}^{z}`$ | `Process_big_m` over $`\Xi \times \mathcal{J}`$ — a bound safely above any feasible internal power — the build cap at full availability, data prep |
| $`\mathrm{nonneg}^{z}`$ | `Process_p_min_pu_nonneg` over $`\mathcal{J}`$ — true where none of the process's own minimums-per-unit is negative — PyPSA's per-unit `(p_min_pu >= 0).all()` over every snapshot and scenario, data prep |
| $`\mathrm{mnt}^{z}`$ | `Process_maintainable` over $`\mathcal{J}`$ — whether a process must be taken off for maintenance within the horizon — in any scenario, as PyPSA takes the union over them (`components.py:1016-1019`) |
| $`\gamma^{z}`$ | `Process_maintenance_pu` over $`\Xi \times \mathcal{J}`$ — the share of the build a maintenance event takes off |
| $`\mathrm{n}^{z,\mathrm{mnt}}`$ | `Process_maintenance_events` over $`\Xi \times \mathcal{J}`$ — how many maintenance events the horizon holds |
| $`\tau^{z,\mathrm{mnt}}`$ | `Process_maintenance_duration` over $`\Xi \times \mathcal{J}`$ — the hours of generator weightings one maintenance event covers — PyPSA's `maintenance_duration`; no value where the process is not maintainable. No row reads it: data prep turns it into `Process_maintenance_cover` and `Process_maintenance_start_blocked`, and the assumptions hold it to the horizon |
| $`\mathrm{blk}^{z}`$ | `Process_maintenance_start_blocked` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — true where no maintenance event may start, because the snapshots it would cover run past the end of the horizon or into one the process does not stand in — PyPSA's `active & ~valid`, from `maintenance_duration` and the generator weightings, data prep |
| $`\mathrm{load}`$ | `Load_p_set` over $`\Xi \times \mathcal{T} \times \mathcal{D}`$ — demand |
| $`\mathrm{sgn}^{\mathrm{load}}`$ | `Load_sign` over $`\mathcal{D}`$ — the sign a load's demand enters its bus's balance with — PyPSA's `sign`, `-1` unless given, `1` for a load that feeds its bus. PyPSA refuses one that differs by scenario (`consistency.py:1187`) |
| $`\mathrm{on}^{\mathrm{load}}`$ | `Load_active` over $`\mathcal{D}`$ — whether a load stands in the model — PyPSA's `active`. A load has no build year and no lifetime, so the flag holds in every snapshot. PyPSA refuses one that differs by scenario (`consistency.py:1195`) |
| $`\pi`$ | `scenario_weight` over $`\Xi`$ — PyPSA's `scenario_weightings.weight` — the probability of a future |
| $`\omega`$ | `CVaR_omega` (scalar) — PyPSA's `risk_preference['omega']` — the share of operating cost priced at the tail rather than in expectation; zero recovers the risk-neutral model |
| $`\mathrm{v}`$ | `CVaR_inv_tail` (scalar) — PyPSA's `1 / (1 - alpha)` — the tail's own probability, inverted in data prep because a divisor is one factor |
| $`\mathrm{w}^{y}`$ | `period_weight_objective` over $`\mathcal{Y}`$ — PyPSA's `investment_period_weightings.objective` — what a period's cost weighs |
| $`\mathrm{w}^{\mathrm{yr}}`$ | `period_weight_years` over $`\mathcal{Y}`$ — PyPSA's `investment_period_weightings.years` — what a period's energy weighs in a `primary_energy` or `operational_limit` row; PyPSA reads it only under `multi_investment_periods`, so data prep feeds one otherwise |
| $`\mathrm{on}`$ | `Generator_active` over $`\mathcal{T} \times \mathcal{G}`$ — whether a generator stands in a snapshot's period — PyPSA's `active`, from build year and lifetime, data prep |
| $`\mathrm{on}^{f}`$ | `Link_active` over $`\mathcal{T} \times \mathcal{L}`$ — whether a link stands in a snapshot's period — PyPSA's `active`, data prep |
| $`\mathrm{on}^{h}`$ | `StorageUnit_active` over $`\mathcal{T} \times \mathcal{S}`$ — whether a storage unit stands in a snapshot's period — PyPSA's `active`, data prep |
| $`\mathrm{on}^{e}`$ | `Store_active` over $`\mathcal{T} \times \mathcal{V}`$ — whether a store stands in a snapshot's period — PyPSA's `active`, data prep |
| $`\mathrm{on}^{s}`$ | `Line_active` over $`\mathcal{T} \times \mathcal{K}`$ — whether a line stands in a snapshot's period — PyPSA's `active`, data prep |
| $`\mathrm{on}^{z}`$ | `Process_active` over $`\mathcal{T} \times \mathcal{J}`$ — whether a process stands in a snapshot's period — PyPSA's `active`, data prep |
| $`\mathrm{on}^{\sigma}`$ | `Transformer_active` over $`\mathcal{T} \times \mathcal{M}`$ — whether a transformer stands in a snapshot's period — PyPSA's `active`, data prep |
| $`\mathrm{W}`$ | `Generator_capital_weight` over $`\mathcal{G}`$ — the sum of period weights a generator stands in — PyPSA's `active * period_weighting`, summed, data prep |
| $`\mathrm{W}^{f}`$ | `Link_capital_weight` over $`\mathcal{L}`$ — the sum of period weights a link stands in — PyPSA's `active * period_weighting`, summed, data prep |
| $`\mathrm{W}^{h}`$ | `StorageUnit_capital_weight` over $`\mathcal{S}`$ — the sum of period weights a storage unit stands in — PyPSA's `active * period_weighting`, summed, data prep |
| $`\mathrm{W}^{e}`$ | `Store_capital_weight` over $`\mathcal{V}`$ — the sum of period weights a store stands in — PyPSA's `active * period_weighting`, summed, data prep |
| $`\mathrm{W}^{s}`$ | `Line_capital_weight` over $`\mathcal{K}`$ — the sum of period weights a line stands in — PyPSA's `active * period_weighting`, summed, data prep |
| $`\mathrm{W}^{z}`$ | `Process_capital_weight` over $`\mathcal{J}`$ — the sum of period weights a process stands in — PyPSA's `active * period_weighting`, summed, data prep |
| $`\mathrm{W}^{\sigma}`$ | `Transformer_capital_weight` over $`\mathcal{M}`$ — the sum of period weights a transformer stands in — PyPSA's `active * period_weighting`, summed, data prep |
| $`\mathrm{new}`$ | `Generator_first_active` over $`\mathcal{Y} \times \mathcal{G}`$ — one in the first period a generator stands in, zero elsewhere, data prep. PyPSA `1.3.0` takes `active.cumsum() == 1`, which also counts a generator that has retired in every later period (`global_constraints.py:276`, PyPSA/PyPSA\#1938) |
| $`\mathrm{new}^{f}`$ | `Link_first_active` over $`\mathcal{Y} \times \mathcal{L}`$ — one in the first period a link stands in, zero elsewhere, data prep. PyPSA `1.3.0` takes `active.cumsum() == 1`, which also counts a link that has retired in every later period (`global_constraints.py:276`, PyPSA/PyPSA\#1938) |
| $`\mathrm{new}^{h}`$ | `StorageUnit_first_active` over $`\mathcal{Y} \times \mathcal{S}`$ — one in the first period a storage unit stands in, zero elsewhere, data prep. PyPSA `1.3.0` takes `active.cumsum() == 1`, which also counts a storage unit that has retired in every later period (`global_constraints.py:276`, PyPSA/PyPSA\#1938) |
| $`\mathrm{new}^{e}`$ | `Store_first_active` over $`\mathcal{Y} \times \mathcal{V}`$ — one in the first period a store stands in, zero elsewhere, data prep. PyPSA `1.3.0` takes `active.cumsum() == 1`, which also counts a store that has retired in every later period (`global_constraints.py:276`, PyPSA/PyPSA\#1938) |
| $`\mathrm{new}^{s}`$ | `Line_first_active` over $`\mathcal{Y} \times \mathcal{K}`$ — one in the first period a line stands in, zero elsewhere, data prep. PyPSA `1.3.0` takes `active.cumsum() == 1`, which also counts a line that has retired in every later period (`global_constraints.py:276`, PyPSA/PyPSA\#1938) |
| $`\mathrm{new}^{z}`$ | `Process_first_active` over $`\mathcal{Y} \times \mathcal{J}`$ — one in the first period a process stands in, zero elsewhere, data prep. PyPSA `1.3.0` takes `active.cumsum() == 1`, which also counts a process that has retired in every later period (`global_constraints.py:276`, PyPSA/PyPSA\#1938) |
| $`\overline{\Delta}`$ | `Carrier_max_growth` over $`\mathcal{I}`$ — most capacity of a carrier that may be added in a period; no value means no limit. The least over the scenarios, as PyPSA takes it (`global_constraints.py:226-230`), data prep. PyPSA reads it only under `multi_investment_periods` (`global_constraints.py:219-220`), so data prep feeds no value otherwise |
| $`\mathrm{r}`$ | `Carrier_max_relative_growth` over $`\mathcal{I}`$ — share of the previous period's additions that may be added on top — the least over the scenarios, as PyPSA takes it, data prep |
| $`\mathrm{p}^{\mathrm{set}}`$ | `Generator_p_set` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — a given output schedule; a generator without one has no row here |
| $`\mathrm{f}^{\mathrm{set}}`$ | `Link_p_set` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — a given flow schedule; a link without one has no row here |
| $`\mathrm{w}^{\mathrm{sto}}`$ | `snapshot_weightings_stores` over $`\mathcal{T}`$ — PyPSA's `snapshot_weightings.stores` — hours a snapshot stands for in a storage balance |
| $`\mathrm{w}^{\mathrm{gen}}`$ | `snapshot_weightings_generators` over $`\mathcal{T}`$ — PyPSA's `snapshot_weightings.generators` — hours a snapshot stands for in an energy total |
| $`\underline{\mathrm{p}}^{\mathrm{nom}}`$ | `Generator_p_nom_min` over $`\Xi \times \mathcal{G}`$ — least nominal power an extendable generator may be built at |
| $`\overline{\mathrm{p}}^{\mathrm{nom}}`$ | `Generator_p_nom_max` over $`\Xi \times \mathcal{G}`$ — most nominal power an extendable generator may be built at |
| $`\mathrm{c}^{\mathrm{cap}}`$ | `Generator_capital_cost` over $`\Xi \times \mathcal{G}`$ — cost of one unit of nominal power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $`\mathrm{p}^{\mathrm{nom,set}}`$ | `Generator_p_nom_set` over $`\Xi \times \mathcal{G}`$ — a given nominal power for an extendable generator; one without a value has no row here |
| $`\underline{\mathrm{E}}`$ | `Generator_e_sum_min` over $`\Xi \times \mathcal{G}`$ — least energy over the horizon; minus infinity where no floor is meant |
| $`\overline{\mathrm{E}}`$ | `Generator_e_sum_max` over $`\Xi \times \mathcal{G}`$ — most energy over the horizon — a fuel or emission budget in energy terms; infinity where no cap is meant |
| $`\underline{\mathrm{f}}^{\mathrm{nom}}`$ | `Link_p_nom_min` over $`\Xi \times \mathcal{L}`$ — least nominal power an extendable link may be built at |
| $`\overline{\mathrm{f}}^{\mathrm{nom}}`$ | `Link_p_nom_max` over $`\Xi \times \mathcal{L}`$ — most nominal power an extendable link may be built at |
| $`\mathrm{c}^{\mathrm{cap},f}`$ | `Link_capital_cost` over $`\Xi \times \mathcal{L}`$ — cost of one unit of nominal power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $`\mathrm{f}^{\mathrm{nom,set}}`$ | `Link_p_nom_set` over $`\Xi \times \mathcal{L}`$ — a given nominal power for an extendable link; one without a value has no row here |
| $`\underline{\mathrm{h}}^{\mathrm{nom}}`$ | `StorageUnit_p_nom_min` over $`\Xi \times \mathcal{S}`$ — least nominal power an extendable storage unit may be built at |
| $`\overline{\mathrm{h}}^{\mathrm{nom}}`$ | `StorageUnit_p_nom_max` over $`\Xi \times \mathcal{S}`$ — most nominal power an extendable storage unit may be built at |
| $`\mathrm{c}^{\mathrm{cap},h}`$ | `StorageUnit_capital_cost` over $`\Xi \times \mathcal{S}`$ — cost of one unit of nominal power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $`\mathrm{h}^{\mathrm{nom,set}}`$ | `StorageUnit_p_nom_set` over $`\Xi \times \mathcal{S}`$ — a given nominal power for an extendable storage unit; one without a value has no row here |
| $`\underline{\mathrm{e}}^{\mathrm{nom}}`$ | `Store_e_nom_min` over $`\Xi \times \mathcal{V}`$ — least nominal capacity an extendable store may be built at |
| $`\overline{\mathrm{e}}^{\mathrm{nom}}`$ | `Store_e_nom_max` over $`\Xi \times \mathcal{V}`$ — most nominal capacity an extendable store may be built at |
| $`\mathrm{c}^{\mathrm{cap},e}`$ | `Store_capital_cost` over $`\Xi \times \mathcal{V}`$ — cost of one unit of nominal capacity — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $`\mathrm{e}^{\mathrm{nom,set}}`$ | `Store_e_nom_set` over $`\Xi \times \mathcal{V}`$ — a given nominal capacity for an extendable store; one without a value has no row here |
| $`\mathrm{h}^{\mathrm{nom}}`$ | `StorageUnit_p_nom` over $`\Xi \times \mathcal{S}`$ — nominal power |
| $`\mathrm{ext}^{h}`$ | `StorageUnit_p_nom_extendable` over $`\mathcal{S}`$ — whether the nominal power is a decision |
| $`\underline{\mathrm{h}}`$ | `StorageUnit_p_min_pu` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — most storing, per unit of nominal power and negated |
| $`\overline{\mathrm{h}}`$ | `StorageUnit_p_max_pu` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — most dispatch, per unit of nominal power |
| $`\mathrm{T}^{h}`$ | `StorageUnit_max_hours` over $`\Xi \times \mathcal{S}`$ — energy capacity, as hours of dispatch at nominal power |
| $`\eta^{-}`$ | `StorageUnit_efficiency_store` over $`\Xi \times \mathcal{S}`$ — share of the power drawn from the bus that becomes charge |
| $`\eta^{+}`$ | `StorageUnit_efficiency_dispatch` over $`\Xi \times \mathcal{S}`$ — share of the charge drawn down that reaches the bus |
| $`\mathrm{sgn}^{h}`$ | `StorageUnit_sign` over $`\mathcal{S}`$ — the sign net dispatch enters its bus's balance with — PyPSA's `sign`, `1` unless given. PyPSA refuses one that differs by scenario (`consistency.py:1187`) |
| $`\rho`$ | `StorageUnit_retention` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — share of charge kept over a snapshot — PyPSA's `(1 - standing_loss) ** elapsed hours`, data prep |
| $`\mathrm{inflow}`$ | `StorageUnit_inflow` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — energy arriving per hour, a river into a reservoir |
| $`\mathrm{soc}^{0}`$ | `StorageUnit_state_of_charge_initial` over $`\Xi \times \mathcal{S}`$ — charge held before the first snapshot |
| $`\mathrm{cyc}`$ | `StorageUnit_cyclic_state_of_charge` over $`\Xi \times \mathcal{S}`$ — whether the horizon closes on itself instead of opening on the initial charge |
| $`\mathrm{cyc}^{y}`$ | `StorageUnit_cyclic_state_of_charge_per_period` over $`\Xi \times \mathcal{S}`$ — whether each investment period closes on itself instead of carrying its charge on to the next; it overrides `cyclic_state_of_charge` and `state_of_charge_initial_per_period`. PyPSA reads it only under `multi_investment_periods`, so data prep feeds false otherwise |
| $`\mathrm{reset}`$ | `StorageUnit_state_of_charge_initial_per_period` over $`\Xi \times \mathcal{S}`$ — whether each investment period opens on the initial charge instead of carrying the previous period's; PyPSA reads it only under `multi_investment_periods`, so data prep feeds false otherwise |
| $`\mathrm{open}`$ | `StorageUnit_opens_late` over $`\mathcal{T} \times \mathcal{S}`$ — whether a snapshot is the first a storage unit stands in, where that is not the first of the horizon — PyPSA's `active.cumsum() == 1` over the snapshots it stands in, past the first snapshot, data prep; false in a run where every unit stands throughout |
| $`\mathrm{idle}`$ | `StorageUnit_inactive_snapshots` over $`\mathcal{S}`$ — how many snapshots a storage unit does not stand in — PyPSA's `(~active).sum()`, data prep. A cyclic unit reaches back this many snapshots further, so it closes on the last snapshot it stands in |
| $`\mathrm{c}^{h}`$ | `StorageUnit_marginal_cost` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — cost of one unit of dispatch |
| $`\mathrm{c}^{h,(2)}`$ | `StorageUnit_marginal_cost_quadratic` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — cost of the square of one unit of dispatch; storing is not charged |
| $`\mathrm{c}^{\mathrm{soc}}`$ | `StorageUnit_marginal_cost_storage` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — cost of one unit of charge held over one snapshot |
| $`\mathrm{c}^{\mathrm{spill}}`$ | `StorageUnit_spill_cost` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — cost of one unit of inflow passed on unused |
| $`\mathrm{h}^{\mathrm{set}}`$ | `StorageUnit_p_set` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — a given net dispatch schedule; a unit without one has no row here |
| $`\mathrm{h}^{+,\mathrm{set}}`$ | `StorageUnit_p_dispatch_set` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — a given dispatch schedule; a unit without one has no row here |
| $`\mathrm{h}^{-,\mathrm{set}}`$ | `StorageUnit_p_store_set` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — a given charging schedule; a unit without one has no row here |
| $`\mathrm{soc}^{\mathrm{set}}`$ | `StorageUnit_state_of_charge_set` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — a given charge schedule; a unit without one has no row here |
| $`\mathrm{e}^{\mathrm{nom}}`$ | `Store_e_nom` over $`\Xi \times \mathcal{V}`$ — nominal energy capacity |
| $`\mathrm{ext}^{e}`$ | `Store_e_nom_extendable` over $`\mathcal{V}`$ — whether the nominal energy capacity is a decision |
| $`\underline{\mathrm{e}}`$ | `Store_e_min_pu` over $`\Xi \times \mathcal{T} \times \mathcal{V}`$ — least energy held, per unit of nominal capacity — negative for a store that may go short |
| $`\overline{\mathrm{e}}`$ | `Store_e_max_pu` over $`\Xi \times \mathcal{T} \times \mathcal{V}`$ — most energy held, per unit of nominal capacity |
| $`\mathrm{sgn}^{q}`$ | `Store_sign` over $`\mathcal{V}`$ — the sign the power a store delivers enters its bus's balance with — PyPSA's `sign`, `1` unless given. PyPSA refuses one that differs by scenario (`consistency.py:1187`) |
| $`\rho^{e}`$ | `Store_retention` over $`\Xi \times \mathcal{T} \times \mathcal{V}`$ — share of energy kept over a snapshot — PyPSA's `(1 - standing_loss) ** elapsed hours`, data prep |
| $`\mathrm{e}^{0}`$ | `Store_e_initial` over $`\Xi \times \mathcal{V}`$ — energy held before the first snapshot |
| $`\mathrm{cyc}^{e}`$ | `Store_e_cyclic` over $`\Xi \times \mathcal{V}`$ — whether the horizon closes on itself instead of opening on the initial energy |
| $`\mathrm{cyc}^{e,y}`$ | `Store_e_cyclic_per_period` over $`\Xi \times \mathcal{V}`$ — whether each investment period closes on itself instead of carrying its energy on to the next; it overrides `e_cyclic` and `e_initial_per_period`. PyPSA reads it only under `multi_investment_periods`, so data prep feeds false otherwise |
| $`\mathrm{reset}^{e}`$ | `Store_e_initial_per_period` over $`\Xi \times \mathcal{V}`$ — whether each investment period opens on the initial energy instead of carrying the previous period's; PyPSA reads it only under `multi_investment_periods`, so data prep feeds false otherwise |
| $`\mathrm{open}^{e}`$ | `Store_opens_late` over $`\mathcal{T} \times \mathcal{V}`$ — whether a snapshot is the first a store stands in, where that is not the first of the horizon — PyPSA's `active.cumsum() == 1` over the snapshots it stands in, past the first snapshot, data prep; false in a run where every store stands throughout |
| $`\mathrm{idle}^{e}`$ | `Store_inactive_snapshots` over $`\mathcal{V}`$ — how many snapshots a store does not stand in — PyPSA's `(~active).sum()`, data prep. A cyclic store reaches back this many snapshots further, so it closes on the last snapshot it stands in |
| $`\mathrm{c}^{q}`$ | `Store_marginal_cost` over $`\Xi \times \mathcal{T} \times \mathcal{V}`$ — cost of one unit of power delivered |
| $`\mathrm{c}^{q,(2)}`$ | `Store_marginal_cost_quadratic` over $`\Xi \times \mathcal{T} \times \mathcal{V}`$ — cost of the square of the net power delivered, so charging costs as much as delivering |
| $`\mathrm{c}^{e}`$ | `Store_marginal_cost_storage` over $`\Xi \times \mathcal{T} \times \mathcal{V}`$ — cost of one unit of energy held over one snapshot |
| $`\mathrm{e}^{\mathrm{set}}`$ | `Store_e_set` over $`\Xi \times \mathcal{T} \times \mathcal{V}`$ — a given energy schedule; a store without one has no row here |
| $`\mathrm{q}^{\mathrm{set}}`$ | `Store_p_set` over $`\Xi \times \mathcal{T} \times \mathcal{V}`$ — a given schedule of power delivered; a store without one has no row here |
| $`\mathrm{s}^{\mathrm{nom}}`$ | `Line_s_nom` over $`\Xi \times \mathcal{K}`$ — nominal apparent power |
| $`\mathrm{ext}^{s}`$ | `Line_s_nom_extendable` over $`\mathcal{K}`$ — whether the nominal apparent power is a decision |
| $`\overline{\mathrm{s}}`$ | `Line_s_max_pu` over $`\Xi \times \mathcal{T} \times \mathcal{K}`$ — most flow either way, per unit of nominal apparent power |
| $`\underline{\mathrm{s}}^{\mathrm{nom}}`$ | `Line_s_nom_min` over $`\Xi \times \mathcal{K}`$ — least nominal apparent power an extendable line may be built at |
| $`\overline{\mathrm{s}}^{\mathrm{nom}}`$ | `Line_s_nom_max` over $`\Xi \times \mathcal{K}`$ — most nominal apparent power an extendable line may be built at |
| $`\mathrm{c}^{\mathrm{cap},s}`$ | `Line_capital_cost` over $`\Xi \times \mathcal{K}`$ — cost of one unit of nominal apparent power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $`\mathrm{s}^{\mathrm{nom,set}}`$ | `Line_s_nom_set` over $`\Xi \times \mathcal{K}`$ — a given nominal apparent power for an extendable line; one without a value has no row here |
| $`\mathrm{s}^{\mathrm{set}}`$ | `Line_s_set` over $`\Xi \times \mathcal{T} \times \mathcal{K}`$ — a given flow schedule; a line without one has no row here |
| $`\mathrm{x}`$ | `Line_cycle_weight` over $`\mathcal{K} \times \mathcal{C}`$ — the line's series impedance, signed by its orientation in the cycle — the cycle basis, data prep; a line in no cycle has no row. PyPSA builds the cycle basis from the first scenario only (`networks.py:1354-1361`) |
| $`\beta`$ | `Line_BODF` over $`\mathcal{K} \times \mathcal{K}^{\mathrm{out}}`$ — the share of an outaged branch's flow a line takes on when that branch goes out — PyPSA's `BODF`, from the sub-network's PTDF, data prep; a row only where the line and the outage share a sub-network, -1 at the outaged line itself |
| $`\mathrm{lossy}`$ | `transmission_losses` (scalar) — whether the network dissipates transmission losses — PyPSA's `transmission_losses` read as a flag; its mode, tangents or secants, only decides how data prep fills the `segment` axis, the rows are the same; false with no segments is a lossless run. A security-constrained run over a network with passive branches builds no loss: PyPSA does not hand the keyword to `create_model` (`abstract.py:437-441`) but to the solver (`:491`), so data prep feeds false there |
| $`\overline{\ell}`$ | `Line_loss_max` over $`\Xi \times \mathcal{T} \times \mathcal{K}`$ — the loss at a line's rating — PyPSA's `r_pu_eff * (s_max_pu * s_nom_max)**2`, data prep |
| $`\mathrm{a}`$ | `Line_loss_slope` over $`\Xi \times \mathcal{T} \times \mathcal{K} \times \mathcal{B}`$ — the slope of a cut to the loss curve — a tangent's `2 * r_pu_eff * p_k` at its segment's flow, a secant's `r_pu_eff * (p_k + p_k+1)` between consecutive breakpoints, data prep |
| $`\mathrm{b}`$ | `Line_loss_offset` over $`\Xi \times \mathcal{T} \times \mathcal{K} \times \mathcal{B}`$ — where that cut meets the loss axis — a tangent's `loss_k - slope_k * p_k`, a secant's `-r_pu_eff * p_k * p_k+1`, negative, data prep |
| $`\sigma^{\mathrm{nom}}`$ | `Transformer_s_nom` over $`\Xi \times \mathcal{M}`$ — nominal apparent power |
| $`\mathrm{ext}^{\sigma}`$ | `Transformer_s_nom_extendable` over $`\mathcal{M}`$ — whether the nominal apparent power is a decision |
| $`\overline{\sigma}`$ | `Transformer_s_max_pu` over $`\Xi \times \mathcal{T} \times \mathcal{M}`$ — most flow either way, per unit of nominal apparent power |
| $`\underline{\sigma}^{\mathrm{nom}}`$ | `Transformer_s_nom_min` over $`\Xi \times \mathcal{M}`$ — least nominal apparent power an extendable transformer may be built at |
| $`\overline{\sigma}^{\mathrm{nom}}`$ | `Transformer_s_nom_max` over $`\Xi \times \mathcal{M}`$ — most nominal apparent power an extendable transformer may be built at |
| $`\mathrm{c}^{\mathrm{cap},\sigma}`$ | `Transformer_capital_cost` over $`\Xi \times \mathcal{M}`$ — cost of one unit of nominal apparent power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $`\sigma^{\mathrm{nom,set}}`$ | `Transformer_s_nom_set` over $`\Xi \times \mathcal{M}`$ — a given nominal apparent power for an extendable transformer; one without a value has no row here |
| $`\sigma^{\mathrm{set}}`$ | `Transformer_s_set` over $`\Xi \times \mathcal{T} \times \mathcal{M}`$ — a given flow schedule; a transformer without one has no row here |
| $`\mathrm{x}^{\sigma}`$ | `Transformer_cycle_weight` over $`\mathcal{M} \times \mathcal{C}`$ — the transformer's effective series reactance, `x` times its tap ratio, signed by its orientation in the cycle — PyPSA's `x_pu_eff`, the cycle basis, data prep; a transformer in no cycle has no row. From the first scenario only, as a line's |
| $`\beta^{\sigma}`$ | `Transformer_BODF` over $`\mathcal{M} \times \mathcal{K}^{\mathrm{out}}`$ — the share of an outaged branch's flow a transformer takes on when that branch goes out, as a line's; a row only where the transformer and the outage share a sub-network |
| $`\vartheta`$ | `Transformer_phase_shift_weight` over $`\mathcal{M} \times \mathcal{C}`$ — a fixed transformer's phase shift in radians, signed by its orientation in the cycle — a constant added to the cycle sum, data prep; zero for a varying transformer, whose shift is a decision instead, so the constant and the variable term never both count a shift. A transformer with no shift or in no cycle has no row |
| $`\mathrm{Transformer\_phase\_shift\_varying}`$ | `Transformer_phase_shift_varying` over $`\mathcal{M}`$ — whether a transformer's phase shift is a decision — PyPSA's `phase_shift_min < phase_shift_max`, read as a flag in data prep; false is a fixed shift carried by `phase_shift`. The shift parameters carry no scenario: only a cycle row reads them, and PyPSA fails on a transformer in a cycle on a network with scenarios (`constraints.py:1654`) |
| $`\mathrm{Transformer\_phase\_shift\_min}`$ | `Transformer_phase_shift_min` over $`\mathcal{M}`$ — the least a varying transformer's phase shift may take, in degrees — PyPSA's `phase_shift_min`; where it is below `phase_shift_max` the shift is a decision, otherwise the transformer keeps its fixed `phase_shift` |
| $`\mathrm{Transformer\_phase\_shift\_max}`$ | `Transformer_phase_shift_max` over $`\mathcal{M}`$ — the most a varying transformer's phase shift may take, in degrees — PyPSA's `phase_shift_max`; equal to `phase_shift_min` for a fixed transformer |
| $`\mathrm{Transformer\_phase\_shift\_cycle\_weight}`$ | `Transformer_phase_shift_cycle_weight` over $`\mathcal{M} \times \mathcal{C}`$ — the cycle sign for a varying transformer's phase shift, times π/180 so a shift in degrees enters the cycle sum in radians — data prep; zero for a fixed transformer or one in no cycle |
| $`\overline{\ell}^{\sigma}`$ | `Transformer_loss_max` over $`\Xi \times \mathcal{T} \times \mathcal{M}`$ — the loss at a transformer's rating — PyPSA's `r_pu_eff * (s_max_pu * s_nom_max)**2`, its `r_pu_eff` the resistance over the given `s_nom` times the tap ratio, data prep |
| $`\mathrm{a}^{\sigma}`$ | `Transformer_loss_slope` over $`\Xi \times \mathcal{T} \times \mathcal{M} \times \mathcal{B}`$ — the slope of a cut to a transformer's loss curve — a tangent's `2 * r_pu_eff * p_k`, a secant's `r_pu_eff * (p_k + p_k+1)`, as a line's, over the transformer's own `r_pu_eff` and rating, data prep |
| $`\mathrm{b}^{\sigma}`$ | `Transformer_loss_offset` over $`\Xi \times \mathcal{T} \times \mathcal{M} \times \mathcal{B}`$ — where that cut meets the loss axis — a tangent's `loss_k - slope_k * p_k`, a secant's `-r_pu_eff * p_k * p_k+1`, negative, data prep |
| $`\mathrm{type}`$ | `GlobalConstraint_type` over $`\mathcal{I}`$ — which formula the row takes — `primary_energy`, `operational_limit`, `transmission_volume_expansion_limit`, `transmission_expansion_cost_limit` or `tech_capacity_expansion_limit` |
| $`\mathrm{sense}`$ | `GlobalConstraint_sense` over $`\Xi \times \mathcal{I}`$ — which way the row binds in each scenario — `<=`, `>=` or `==`; PyPSA reads a row's sense per scenario (`global_constraints.py:556`, `:748`, `:860`) |
| $`\mathrm{K}`$ | `GlobalConstraint_constant` over $`\Xi \times \mathcal{I}`$ — the constant the total is held against; what a variable cannot carry — an initial charge, times its period's years for each counted period where the storage reopens per period, or a non-extendable build — is folded in here by data prep. PyPSA reads it per scenario (`global_constraints.py:557`, `:749`, `:861`) |
| $`\mathrm{in}`$ | `GlobalConstraint_counts_snapshot` over $`\Xi \times \mathcal{I} \times \mathcal{T}`$ — whether a row counts a snapshot in a scenario — PyPSA's `investment_period`: every snapshot where the row names none, and only that period's where it names one, data prep. A row that names a period the run does not model has no label here, as PyPSA skips it (`global_constraints.py:377`); PyPSA reads the column only under `multi_investment_periods`, and fails on a row that names a period without it (`global_constraints.py:375`) |
| $`\mathrm{a}`$ | `Generator_primary_energy_weight` over $`\Xi \times \mathcal{I} \times \mathcal{G}`$ — the constrained attribute per unit of energy at the bus — the carrier's `co2_emissions` over the generator's efficiency, data prep; a generator of an unweighted carrier has no row |
| $`\mathrm{a}^{h}`$ | `StorageUnit_primary_energy_weight` over $`\Xi \times \mathcal{I} \times \mathcal{S}`$ — the constrained attribute per unit of charge depleted — data prep; an unweighted unit has no row |
| $`\mathrm{a}^{e}`$ | `Store_primary_energy_weight` over $`\Xi \times \mathcal{I} \times \mathcal{V}`$ — the constrained attribute per unit of energy depleted — data prep; an unweighted store has no row |
| $`\mathrm{b}`$ | `Generator_operational_limit_weight` over $`\Xi \times \mathcal{I} \times \mathcal{G}`$ — one where the generator is in the row's set — data prep; one outside it has no row |
| $`\mathrm{b}^{h}`$ | `StorageUnit_operational_limit_weight` over $`\Xi \times \mathcal{I} \times \mathcal{S}`$ — one where the storage unit is in the row's set — data prep; one outside it has no row |
| $`\mathrm{b}^{e}`$ | `Store_operational_limit_weight` over $`\Xi \times \mathcal{I} \times \mathcal{V}`$ — one where the store is in the row's set — data prep; one outside it has no row |
| $`\mathrm{len}`$ | `Line_volume_weight` over $`\Xi \times \mathcal{I} \times \mathcal{K}`$ — the line's length where its carrier is in the row's set, the first scenario's length as PyPSA reads it (`global_constraints.py:835-836`) — data prep; a line outside it, or one that does not stand in the row's `investment_period`, has no row |
| $`\mathrm{len}^{f}`$ | `Link_volume_weight` over $`\Xi \times \mathcal{I} \times \mathcal{L}`$ — the link's length where its carrier is in the row's set, the first scenario's length as PyPSA reads it (`global_constraints.py:835-836`) — data prep; a link outside it, or one that does not stand in the row's `investment_period`, has no row |
| $`\mathrm{cc}`$ | `Line_expansion_cost_weight` over $`\Xi \times \mathcal{I} \times \mathcal{K}`$ — the line's capital cost where its carrier is in the row's set, times the objective weights of the periods it stands in where the row names no `investment_period` under `multi_investment_periods` — data prep; a line outside the set, or one that does not stand in the row's period, has no row |
| $`\mathrm{cc}^{f}`$ | `Link_expansion_cost_weight` over $`\Xi \times \mathcal{I} \times \mathcal{L}`$ — the link's capital cost where its carrier is in the row's set, times the objective weights of the periods it stands in where the row names no `investment_period` under `multi_investment_periods` — data prep; a link outside the set, or one that does not stand in the row's period, has no row |
| $`\mathrm{m}`$ | `Generator_tech_capacity_weight` over $`\mathcal{I} \times \mathcal{G}`$ — one where the generator is in the row's carrier-and-bus set — data prep; one outside it, or one that does not stand in the row's `investment_period`, has no row |
| $`\mathrm{m}^{f}`$ | `Link_tech_capacity_weight` over $`\mathcal{I} \times \mathcal{L}`$ — one where the link is in the row's carrier-and-bus set — data prep; one outside it, or one that does not stand in the row's `investment_period`, has no row |
| $`\mathrm{m}^{l}`$ | `Line_tech_capacity_weight` over $`\mathcal{I} \times \mathcal{K}`$ — one where the line is in the row's carrier-and-bus set — data prep; one outside it, or one that does not stand in the row's `investment_period`, has no row |
| $`\mathrm{m}^{h}`$ | `StorageUnit_tech_capacity_weight` over $`\mathcal{I} \times \mathcal{S}`$ — one where the storage unit is in the row's carrier-and-bus set — data prep; one outside it, or one that does not stand in the row's `investment_period`, has no row |
| $`\mathrm{m}^{e}`$ | `Store_tech_capacity_weight` over $`\mathcal{I} \times \mathcal{V}`$ — one where the store is in the row's carrier-and-bus set — data prep; one outside it, or one that does not stand in the row's `investment_period`, has no row |
| $`\mathrm{m}^{z}`$ | `Process_tech_capacity_weight` over $`\mathcal{I} \times \mathcal{J}`$ — one where the process is in the row's carrier-and-bus set — data prep; one outside it, or one that does not stand in the row's `investment_period`, has no row |

#### Variables

| Symbol | Meaning |
|---|---|
| $`p`$ | `Generator_p` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — `Generator-p` — output of a generator in a snapshot |
| $`f`$ | `Link_p` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — `Link-p` — PyPSA's `p0`, the flow measured at the `Link_bus0` end: a positive value withdraws there and injects at every bus the link's output ports deliver to |
| $`z`$ | `Process_p` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — `Process-p` — PyPSA's internal power `p`: a positive value drives every port at its own rate, withdrawing where the rate is negative and injecting where it is positive |
| $`h^{+}`$ | `StorageUnit_p_dispatch` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — `StorageUnit-p_dispatch` — power delivered to the bus |
| $`h^{-}`$ | `StorageUnit_p_store` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — `StorageUnit-p_store` — power drawn from the bus into charge |
| $`\mathit{soc}`$ | `StorageUnit_state_of_charge` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — `StorageUnit-state_of_charge` — energy held at the end of a snapshot |
| $`\mathit{spill}`$ | `StorageUnit_spill` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — `StorageUnit-spill` — inflow passed on unused. Zero where there is no inflow, so the balance keeps its row there; the bounds are PyPSA's, on the variable rather than as rows |
| $`e`$ | `Store_e` over $`\Xi \times \mathcal{T} \times \mathcal{V}`$ — `Store-e` — energy held at the end of a snapshot |
| $`q`$ | `Store_p` over $`\Xi \times \mathcal{T} \times \mathcal{V}`$ — `Store-p` — power delivered to the bus; charging is negative |
| $`N`$ | `Generator_n_mod` over $`\mathcal{G}`$ — `Generator-n_mod` — how many modules of an extendable modular build |
| $`u`$ | `Generator_status` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — `Generator-status` — how much of a committable unit is on: an integer the rows below cap at one, or at the module count where the build is modular |
| $`\mathit{up}`$ | `Generator_start_up` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — `Generator-start_up` — how much of a committable unit turns on this snapshot, capped as the status is |
| $`\mathit{dn}`$ | `Generator_shut_down` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — `Generator-shut_down` — how much of a committable unit turns off this snapshot, capped as the status is |
| $`\mu`$ | `Generator_maintenance` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — `Generator-maintenance` — whether a maintainable generator is in maintenance: continuous, and one exactly where an event covers the snapshot |
| $`\mu^{\mathrm{up}}`$ | `Generator_maintenance_start` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — `Generator-maintenance_start` — whether a maintenance event starts in this snapshot |
| $`\mu^{\mathrm{nom}}`$ | `Generator_maintenance_capacity` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — `Generator-maintenance_capacity` — the chosen build while in maintenance, zero otherwise: the product the `maintcap` rows linearize |
| $`\mu^{u}`$ | `Generator_maintenance_status` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — `Generator-maintenance_status` — the status while in maintenance, zero otherwise: the product the `maint-status` rows linearize, so a unit in maintenance may also be off |
| $`N^{f}`$ | `Link_n_mod` over $`\mathcal{L}`$ — `Link-n_mod` — how many modules of an extendable modular build |
| $`u^{f}`$ | `Link_status` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — `Link-status` — how much of a committable link is on: an integer the rows below cap at one, or at the module count where the build is modular |
| $`\mathit{up}^{f}`$ | `Link_start_up` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — `Link-start_up` — how much of a committable link turns on this snapshot, capped as the status is |
| $`\mathit{dn}^{f}`$ | `Link_shut_down` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — `Link-shut_down` — how much of a committable link turns off this snapshot, capped as the status is |
| $`\mu^{f}`$ | `Link_maintenance` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — `Link-maintenance` — whether a maintainable link is in maintenance: continuous, and one exactly where an event covers the snapshot |
| $`\mu^{f,\mathrm{up}}`$ | `Link_maintenance_start` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — `Link-maintenance_start` — whether a maintenance event starts in this snapshot |
| $`\mu^{f,\mathrm{nom}}`$ | `Link_maintenance_capacity` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — `Link-maintenance_capacity` — the chosen build while in maintenance, zero otherwise: the product the `maintcap` rows linearize |
| $`\mu^{f,u}`$ | `Link_maintenance_status` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — `Link-maintenance_status` — the status while in maintenance, zero otherwise: the product the `maint-status` rows linearize, so a unit in maintenance may also be off |
| $`N^{z}`$ | `Process_n_mod` over $`\mathcal{J}`$ — `Process-n_mod` — how many modules of an extendable modular build |
| $`u^{z}`$ | `Process_status` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — `Process-status` — how much of a committable process is on: an integer the rows below cap at one, or at the module count where the build is modular |
| $`\mathit{up}^{z}`$ | `Process_start_up` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — `Process-start_up` — how much of a committable process turns on this snapshot, capped as the status is |
| $`\mathit{dn}^{z}`$ | `Process_shut_down` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — `Process-shut_down` — how much of a committable process turns off this snapshot, capped as the status is |
| $`\mu^{z}`$ | `Process_maintenance` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — `Process-maintenance` — whether a maintainable process is in maintenance: continuous, and one exactly where an event covers the snapshot |
| $`\mu^{z,\mathrm{up}}`$ | `Process_maintenance_start` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — `Process-maintenance_start` — whether a maintenance event starts in this snapshot |
| $`\mu^{z,\mathrm{nom}}`$ | `Process_maintenance_capacity` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — `Process-maintenance_capacity` — the chosen build while in maintenance, zero otherwise: the product the `maintcap` rows linearize |
| $`\mu^{z,u}`$ | `Process_maintenance_status` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — `Process-maintenance_status` — the status while in maintenance, zero otherwise: the product the `maint-status` rows linearize, so a unit in maintenance may also be off |
| $`s`$ | `Line_s` over $`\Xi \times \mathcal{T} \times \mathcal{K}`$ — `Line-s` — PyPSA's `p0`, the flow measured at the `Line_bus0` end: a positive value withdraws there and injects at `Line_bus1`, lossless |
| $`\ell`$ | `Line_loss` over $`\Xi \times \mathcal{T} \times \mathcal{K}`$ — `Line-loss` — what a line dissipates carrying its flow, pushed down by the cost and held up by the cuts; absent, and zero in the balance, where the network is lossless |
| $`\sigma`$ | `Transformer_s` over $`\Xi \times \mathcal{T} \times \mathcal{M}`$ — `Transformer-s` — PyPSA's `p0`, the flow measured at the `Transformer_bus0` end: a positive value withdraws there and injects at `Transformer_bus1`, lossless |
| $`\ell^{\sigma}`$ | `Transformer_loss` over $`\Xi \times \mathcal{T} \times \mathcal{M}`$ — `Transformer-loss` — what a transformer dissipates carrying its flow, as a line does; absent, and zero in the balance, where the network is lossless |
| $`\mathit{Transformer\_phase\_shift}`$ | `Transformer_phase_shift` over $`\Xi \times \mathcal{T} \times \mathcal{M}`$ — `Transformer-phase_shift` — a phase-shifting transformer's voltage angle shift in degrees, chosen per snapshot to redistribute the flows around its cycles without moving active power; absent, and zero in the cycle sum, where the shift is fixed |
| $`S`$ | `Line_s_nom_ext` over $`\mathcal{K}`$ — `Line-s_nom` — nominal apparent power where it is a decision; the parameter of the same PyPSA name carries the fixed regime |
| $`P`$ | `Generator_p_nom_ext` over $`\mathcal{G}`$ — `Generator-p_nom` — nominal power where it is a decision; the parameter of the same PyPSA name carries the fixed regime |
| $`F`$ | `Link_p_nom_ext` over $`\mathcal{L}`$ — `Link-p_nom` — nominal power where it is a decision; the parameter of the same PyPSA name carries the fixed regime |
| $`Z`$ | `Process_p_nom_ext` over $`\mathcal{J}`$ — `Process-p_nom` — nominal internal power where it is a decision; the parameter of the same PyPSA name carries the fixed regime |
| $`\Sigma`$ | `Transformer_s_nom_ext` over $`\mathcal{M}`$ — `Transformer-s_nom` — nominal apparent power where it is a decision; the parameter of the same PyPSA name carries the fixed regime |
| $`H`$ | `StorageUnit_p_nom_ext` over $`\mathcal{S}`$ — `StorageUnit-p_nom` — nominal power where it is a decision; the parameter of the same PyPSA name carries the fixed regime |
| $`E`$ | `Store_e_nom_ext` over $`\mathcal{V}`$ — `Store-e_nom` — nominal capacity where it is a decision; the parameter of the same PyPSA name carries the fixed regime |
| $`a`$ | `CVaR_a` over $`\Xi`$ — `CVaR-a` — how far a scenario's operating cost exceeds the tail's start; nothing where it does not |
| $`\theta`$ | `CVaR_theta` (scalar) — `CVaR-theta` — where the tail starts, the value at risk |
| $`CVaR`$ | `CVaR` (scalar) — `CVaR` — the tail's average cost, what the objective prices at `omega` |

#### Definitions

| Symbol | Meaning |
|---|---|
| $`\overleftarrow{u}`$ | `Generator_previous_status` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — the commitment state a generator carries into a snapshot — the state it brought into the horizon at the first, the previous snapshot's after that |
| $`\overleftarrow{p}`$ | `Generator_previous_p` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — the output a generator carries into a snapshot — at the first, the `p_init` it brought in where it came in running and nothing where it came in off; the previous snapshot's after that |
| $`\widetilde{\mathrm{p}}^{\mathrm{nom}}`$ | `Generator_p_nom_effective` over $`\Xi \times \mathcal{G}`$ — the build a generator's limits are taken against — the chosen one where it is extendable, the given one otherwise |
| $`\widetilde{\mathrm{ru}}`$ | `Generator_ramp_up_rate` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — the ramp limit a unit's up row reads — PyPSA's `ramp_limit_up`, or the full build where it has none, since a start-up ramp alone builds the row |
| $`\widetilde{\mathrm{rd}}`$ | `Generator_ramp_down_rate` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — the ramp limit a unit's down row reads — PyPSA's `ramp_limit_down`, or the full build where it has none, since a shut-down ramp alone builds the row |
| $`\widetilde{\mathrm{ru}}^{\mathrm{up}}`$ | `Generator_start_up_rate` over $`\Xi \times \mathcal{G}`$ — the start-up ramp a unit's up row reads — PyPSA's `ramp_limit_start_up`, or the full build where it has none |
| $`\widetilde{\mathrm{rd}}^{\mathrm{dn}}`$ | `Generator_shut_down_rate` over $`\Xi \times \mathcal{G}`$ — the shut-down ramp a unit's down row reads — PyPSA's `ramp_limit_shut_down`, or the full build where it has none |
| $`\widehat{\mathrm{p}}^{\mathrm{nom}}`$ | `Generator_p_nom_committed` over $`\Xi \times \mathcal{G}`$ — the build a committed unit's ramp rows are taken against — one module where the build is extendable and modular, the given build otherwise |
| $`\Delta^{+}`$ | `Generator_ramp_up_allowance` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — how far a generator may raise output between two snapshots — its ramp limit of the build while it stays on, plus its start-up ramp in the snapshot it turns on |
| $`\Delta^{-}`$ | `Generator_ramp_down_allowance` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — how far a generator may lower output between two snapshots — its ramp limit of the build while it stays on, plus its shut-down ramp in the snapshot it turns off |
| $`\widetilde{\mathrm{f}}^{\mathrm{nom}}`$ | `Link_p_nom_effective` over $`\Xi \times \mathcal{L}`$ — the build a link's limits are taken against — the chosen one where it is extendable, the given one otherwise |
| $`\overleftarrow{u}^{f}`$ | `Link_previous_status` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — the commitment state a link carries into a snapshot — the state it brought into the horizon at the first, the previous snapshot's after that |
| $`\overleftarrow{f}`$ | `Link_previous_p` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — the flow a link carries into a snapshot — at the first, the `p_init` it brought in where it came in running and nothing where it came in off; the previous snapshot's after that |
| $`\widetilde{\mathrm{ru}}^{f}`$ | `Link_ramp_up_rate` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — the ramp limit a link's up row reads — PyPSA's `ramp_limit_up`, or the full build where it has none, since a start-up ramp alone builds the row |
| $`\widetilde{\mathrm{rd}}^{f}`$ | `Link_ramp_down_rate` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — the ramp limit a link's down row reads — PyPSA's `ramp_limit_down`, or the full build where it has none, since a shut-down ramp alone builds the row |
| $`\widetilde{\mathrm{ru}}^{f,\mathrm{up}}`$ | `Link_start_up_rate` over $`\Xi \times \mathcal{L}`$ — the start-up ramp a link's up row reads — PyPSA's `ramp_limit_start_up`, or the full build where it has none |
| $`\widetilde{\mathrm{rd}}^{f,\mathrm{dn}}`$ | `Link_shut_down_rate` over $`\Xi \times \mathcal{L}`$ — the shut-down ramp a link's down row reads — PyPSA's `ramp_limit_shut_down`, or the full build where it has none |
| $`\widehat{\mathrm{f}}^{\mathrm{nom}}`$ | `Link_p_nom_committed` over $`\Xi \times \mathcal{L}`$ — the build a committed link's ramp rows are taken against — one module where the build is extendable and modular, the given build otherwise |
| $`\Delta^{f,+}`$ | `Link_ramp_up_allowance` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — how far a link may raise flow between two snapshots — its ramp limit of the build while it stays on, plus its start-up ramp in the snapshot it turns on |
| $`\Delta^{f,-}`$ | `Link_ramp_down_allowance` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — how far a link may lower flow between two snapshots — its ramp limit of the build while it stays on, plus its shut-down ramp in the snapshot it turns off |
| $`\widetilde{\mathrm{z}}^{\mathrm{nom}}`$ | `Process_p_nom_effective` over $`\Xi \times \mathcal{J}`$ — the build a process's limits are taken against — the chosen one where it is extendable, the given one otherwise |
| $`\overleftarrow{u}^{z}`$ | `Process_previous_status` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — the commitment state a process carries into a snapshot — the state it brought into the horizon at the first, the previous snapshot's after that |
| $`\overleftarrow{z}`$ | `Process_previous_p` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — the internal power a process carries into a snapshot — at the first, the `p_init` it brought in where it came in running and nothing where it came in off; the previous snapshot's after that |
| $`\widetilde{\mathrm{ru}}^{z}`$ | `Process_ramp_up_rate` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — the ramp limit a process's up row reads — PyPSA's `ramp_limit_up`, or the full build where it has none, since a start-up ramp alone builds the row |
| $`\widetilde{\mathrm{rd}}^{z}`$ | `Process_ramp_down_rate` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — the ramp limit a process's down row reads — PyPSA's `ramp_limit_down`, or the full build where it has none, since a shut-down ramp alone builds the row |
| $`\widetilde{\mathrm{ru}}^{z,\mathrm{up}}`$ | `Process_start_up_rate` over $`\Xi \times \mathcal{J}`$ — the start-up ramp a process's up row reads — PyPSA's `ramp_limit_start_up`, or the full build where it has none |
| $`\widetilde{\mathrm{rd}}^{z,\mathrm{dn}}`$ | `Process_shut_down_rate` over $`\Xi \times \mathcal{J}`$ — the shut-down ramp a process's down row reads — PyPSA's `ramp_limit_shut_down`, or the full build where it has none |
| $`\widehat{\mathrm{z}}^{\mathrm{nom}}`$ | `Process_p_nom_committed` over $`\Xi \times \mathcal{J}`$ — the build a committed process's ramp rows are taken against — one module where the build is extendable and modular, the given build otherwise |
| $`\Delta^{z,+}`$ | `Process_ramp_up_allowance` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — how far a process may raise internal power between two snapshots — its ramp limit of the build while it stays on, plus its start-up ramp in the snapshot it turns on |
| $`\Delta^{z,-}`$ | `Process_ramp_down_allowance` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — how far a process may lower internal power between two snapshots — its ramp limit of the build while it stays on, plus its shut-down ramp in the snapshot it turns off |
| $`\overleftarrow{\mathit{soc}}`$ | `StorageUnit_charge_carried_in` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — the charge a unit opens a snapshot with — at the first snapshot it stands in, its last such snapshot's less standing loss where it is cyclic and the given initial charge, which no standing loss has touched yet, where it is not; the previous snapshot's less standing loss otherwise. A unit built in a later period opens in that period, and a cyclic one that retires closes on its own last snapshot. Per period, the same holds with each investment period as the horizon |
| $`\overleftarrow{e}`$ | `Store_energy_carried_in` over $`\Xi \times \mathcal{T} \times \mathcal{V}`$ — the energy a store opens a snapshot with — at the first snapshot it stands in, its last such snapshot's less standing loss where it is cyclic and the given initial energy, which no standing loss has touched yet, where it is not; the previous snapshot's less standing loss otherwise. A store built in a later period opens in that period, and a cyclic one that retires closes on its own last snapshot. Per period, the same holds with each investment period as the horizon |
| $`\overrightarrow{f}`$ | `Link_output_arrival` over $`\Xi \times \mathcal{T} \times \mathcal{O}`$ — what a link delivers to an output port at a snapshot — its flow after the port's efficiency, delayed by the port's `delay` within its investment period; where the port is `cyclic_delay` the delayed flow wraps from the period's end, and where it is not the flow still in transit at the period's first snapshots is lost. A port that does not delay (`delay` zero) delivers its flow unshifted, cyclic or not |
| $`\overrightarrow{z}`$ | `Process_output_arrival` over $`\Xi \times \mathcal{T} \times \mathcal{R}`$ — what a process transfers at a port at a snapshot — its internal power times the port's rate, delayed by the port's `delay` within its investment period; where the port is `cyclic_delay` the delayed transfer wraps from the period's end, and where it is not the energy still in transit at the period's first snapshots is lost. A port that does not delay (`delay` zero) transfers at once, cyclic or not |
| $`\mathit{w}^{\mathrm{gc}}`$ | `GlobalConstraint_energy_weight` over $`\Xi \times \mathcal{I} \times \mathcal{T}`$ — what one unit of power at a snapshot counts for in a row — the generator weighting times the years of the snapshot's period, where the row counts the snapshot, and nothing where it does not |
| $`\mathit{last}`$ | `GlobalConstraint_snapshot_closes` over $`\Xi \times \mathcal{I} \times \mathcal{T}`$ — one at the last snapshot a row counts, and zero elsewhere |
| $`\mathit{w}^{h}`$ | `StorageUnit_closing_weight` over $`\Xi \times \mathcal{I} \times \mathcal{T} \times \mathcal{S}`$ — what the charge a unit holds at a snapshot counts for in a row as its closing level — the years of the period at the last snapshot of each counted period where the unit reopens per period, one at the last counted snapshot where it does not, and nothing elsewhere |
| $`\mathit{w}^{e}`$ | `Store_closing_weight` over $`\Xi \times \mathcal{I} \times \mathcal{T} \times \mathcal{V}`$ — what the energy a store holds at a snapshot counts for in a row as its closing level — the years of the period at the last snapshot of each counted period where the store reopens per period, one at the last counted snapshot where it does not, and nothing elsewhere |
| $`\mathit{Generator\_primary\_energy}`$ | `Generator_primary_energy` over $`\Xi \times \mathcal{I}`$ |
| $`\mathit{StorageUnit\_primary\_energy}`$ | `StorageUnit_primary_energy` over $`\Xi \times \mathcal{I}`$ |
| $`\mathit{Store\_primary\_energy}`$ | `Store_primary_energy` over $`\Xi \times \mathcal{I}`$ |
| $`\mathit{primary\_energy}`$ | `primary_energy` over $`\Xi \times \mathcal{I}`$ — what a `primary_energy` row totals — weighted generator energy over the snapshots it counts, less the charge left in weighted storage at the close; the initial charge it is compared against is folded into the row's constant |
| $`\mathit{Generator\_operational\_limit}`$ | `Generator_operational_limit` over $`\Xi \times \mathcal{I}`$ |
| $`\mathit{StorageUnit\_operational\_limit}`$ | `StorageUnit_operational_limit` over $`\Xi \times \mathcal{I}`$ |
| $`\mathit{Store\_operational\_limit}`$ | `Store_operational_limit` over $`\Xi \times \mathcal{I}`$ |
| $`\mathit{operational\_limit}`$ | `operational_limit` over $`\Xi \times \mathcal{I}`$ — what an `operational_limit` row totals — the weighted energy its generators deliver over the snapshots it counts, plus what its non-cyclic storage draws down; the initial charge it draws from is folded into the row's constant |
| $`\mathit{Line\_transmission\_volume\_expansion}`$ | `Line_transmission_volume_expansion` over $`\Xi \times \mathcal{I}`$ |
| $`\mathit{Link\_transmission\_volume\_expansion}`$ | `Link_transmission_volume_expansion` over $`\Xi \times \mathcal{I}`$ |
| $`\mathit{transmission\_volume\_expansion}`$ | `transmission_volume_expansion` over $`\Xi \times \mathcal{I}`$ — what a `transmission_volume_expansion_limit` row totals — length times the chosen build of the row's branches |
| $`\mathit{Line\_transmission\_expansion\_cost}`$ | `Line_transmission_expansion_cost` over $`\Xi \times \mathcal{I}`$ |
| $`\mathit{Link\_transmission\_expansion\_cost}`$ | `Link_transmission_expansion_cost` over $`\Xi \times \mathcal{I}`$ |
| $`\mathit{transmission\_expansion\_cost}`$ | `transmission_expansion_cost` over $`\Xi \times \mathcal{I}`$ — what a `transmission_expansion_cost_limit` row totals — capital cost times the chosen build of the row's branches |
| $`\mathit{Generator\_tech\_capacity\_expansion}`$ | `Generator_tech_capacity_expansion` over $`\mathcal{I}`$ |
| $`\mathit{Line\_tech\_capacity\_expansion}`$ | `Line_tech_capacity_expansion` over $`\mathcal{I}`$ |
| $`\mathit{Link\_tech\_capacity\_expansion}`$ | `Link_tech_capacity_expansion` over $`\mathcal{I}`$ |
| $`\mathit{Process\_tech\_capacity\_expansion}`$ | `Process_tech_capacity_expansion` over $`\mathcal{I}`$ |
| $`\mathit{StorageUnit\_tech\_capacity\_expansion}`$ | `StorageUnit_tech_capacity_expansion` over $`\mathcal{I}`$ |
| $`\mathit{Store\_tech\_capacity\_expansion}`$ | `Store_tech_capacity_expansion` over $`\mathcal{I}`$ |
| $`\mathit{tech\_capacity\_expansion}`$ | `tech_capacity_expansion` over $`\mathcal{I}`$ — what a `tech_capacity_expansion_limit` row totals — the chosen build of the row's carrier-and-bus set |
| $`\mathit{Generator\_opex}`$ | `Generator_opex` over $`\Xi`$ |
| $`\mathit{Generator\_commitment\_opex}`$ | `Generator_commitment_opex` over $`\Xi`$ |
| $`\mathit{Link\_opex}`$ | `Link_opex` over $`\Xi`$ |
| $`\mathit{Link\_commitment\_opex}`$ | `Link_commitment_opex` over $`\Xi`$ |
| $`\mathit{Process\_opex}`$ | `Process_opex` over $`\Xi`$ |
| $`\mathit{Process\_commitment\_opex}`$ | `Process_commitment_opex` over $`\Xi`$ |
| $`\mathit{StorageUnit\_opex}`$ | `StorageUnit_opex` over $`\Xi`$ |
| $`\mathit{Store\_opex}`$ | `Store_opex` over $`\Xi`$ |
| $`\mathit{scenario\_opex}`$ | `scenario_opex` over $`\Xi`$ — what a future costs to run — every operating term, weighted by the snapshot's hours and its period, before the scenario's own weight; a start and a stop cost what they cost, unweighted, as PyPSA adds them (`optimize.py:414-429`) |
| $`\mathit{Generator\_additions}`$ | `Generator_additions` over $`\mathcal{Y} \times \mathcal{I}`$ |
| $`\mathit{Line\_additions}`$ | `Line_additions` over $`\mathcal{Y} \times \mathcal{I}`$ |
| $`\mathit{Link\_additions}`$ | `Link_additions` over $`\mathcal{Y} \times \mathcal{I}`$ |
| $`\mathit{Process\_additions}`$ | `Process_additions` over $`\mathcal{Y} \times \mathcal{I}`$ |
| $`\mathit{StorageUnit\_additions}`$ | `StorageUnit_additions` over $`\mathcal{Y} \times \mathcal{I}`$ |
| $`\mathit{Store\_additions}`$ | `Store_additions` over $`\mathcal{Y} \times \mathcal{I}`$ |
| $`\mathit{Carrier\_additions}`$ | `Carrier_additions` over $`\mathcal{Y} \times \mathcal{I}`$ — what a carrier adds in a period — every extendable component of that carrier, counting each build in the first period it stands in. Like PyPSA, it sums only the components that carry a carrier attribute, so a transformer, which has none, counts in no carrier |
| $`\mathrm{r}^{+}`$ | `Carrier_relative_growth` over $`\mathcal{I}`$ — the share of the previous period's additions a carrier's growth limit reads — PyPSA's `max_relative_growth` clipped at zero, so a negative share adds nothing and never tightens the limit |
| $`\check{\mathrm{load}}`$ | `Load_demand` over $`\Xi \times \mathcal{T} \times \mathcal{D}`$ — what a load draws from its bus's balance — its demand times its sign where it is active, nothing where it is not, since PyPSA drops an inactive load from the balance (`constraints.py:1537-1538`) |
| $`\check{s}`$ | `Line_s_monitored` over $`\Xi \times \mathcal{T} \times \mathcal{K}`$ — the flow a line's post-contingency rows read — its flow where it stands, nothing where it does not, since PyPSA builds those rows for every branch of the sub-network in every snapshot |
| $`\check{\sigma}`$ | `Transformer_s_monitored` over $`\Xi \times \mathcal{T} \times \mathcal{M}`$ — the flow a transformer's post-contingency rows read, as a line's |
| $`\hat{s}`$ | `Outage_s` over $`\Xi \times \mathcal{T} \times \mathcal{K}^{\mathrm{out}}`$ — the flow an outage takes off its branch — the outaged line's or transformer's flow before it goes out |
| $`\mathit{Generator\_injection}`$ | `Generator_injection` over $`\Xi \times \mathcal{T} \times \mathcal{N}`$ |
| $`\mathit{Line\_injection}`$ | `Line_injection` over $`\Xi \times \mathcal{T} \times \mathcal{N}`$ |
| $`\mathit{Link\_injection}`$ | `Link_injection` over $`\Xi \times \mathcal{T} \times \mathcal{N}`$ |
| $`\mathrm{Load\_injection}`$ | `Load_injection` over $`\Xi \times \mathcal{T} \times \mathcal{N}`$ |
| $`\mathit{Process\_injection}`$ | `Process_injection` over $`\Xi \times \mathcal{T} \times \mathcal{N}`$ |
| $`\mathit{StorageUnit\_injection}`$ | `StorageUnit_injection` over $`\Xi \times \mathcal{T} \times \mathcal{N}`$ |
| $`\mathit{Store\_injection}`$ | `Store_injection` over $`\Xi \times \mathcal{T} \times \mathcal{N}`$ |
| $`\mathit{Transformer\_injection}`$ | `Transformer_injection` over $`\Xi \times \mathcal{T} \times \mathcal{N}`$ |
| $`\mathit{Bus\_injection}`$ | `Bus_injection` over $`\Xi \times \mathcal{T} \times \mathcal{N}`$ — what every component puts into a bus, less what it takes out of it; PyPSA writes each term into the balance, and a load on its right-hand side |
| $`\mathit{Line\_angle\_sum}`$ | `Line_angle_sum` over $`\Xi \times \mathcal{T} \times \mathcal{C}`$ |
| $`\mathit{Transformer\_angle\_sum}`$ | `Transformer_angle_sum` over $`\Xi \times \mathcal{T} \times \mathcal{C}`$ |
| $`\mathit{Cycle\_angle\_sum}`$ | `Cycle_angle_sum` over $`\Xi \times \mathcal{T} \times \mathcal{C}`$ — the voltage angle differences around a cycle: every branch flow times its cycle weight, and every transformer phase shift |

Upright is what the data supplies — a parameter such as $`\mathrm{Transformer\_phase\_shift\_varying}`$, a coordinate map, a label — and italic is what the solver chooses, such as $`\mathit{Transformer\_phase\_shift}`$. An index is italic too, being what a quantifier chooses, and a set is script.

$`t \ominus k`$ denotes cyclic translation: index $`t-k`$ taken modulo the size of the dimension (`roll`). Plain $`t-k`$ (`shift`) has no wraparound — terms translated past the edge are simply absent.

$`t \boxminus_{v} k`$ denotes translation with $`v`$ standing where index $`t-k`$ leaves the dimension (`shift(edge=v)`), so the row at that boundary is built and carries $`v`$ rather than being dropped.

$`t \ominus^{\mathrm{relation}(t)} k`$ denotes a translation counted inside the group a relation puts $`t`$ in (`shift(by=relation)`), so a term never crosses out of its own group. The two modifiers take different slots — the group above, the fill below — so $`t \boxminus_{v}^{\mathrm{relation}(t)} k`$ is both at once.

$`\mathrm{pos}(t)`$ denotes where index $`t`$ sits along its dimension's own order — the order `shift` steps along, not the order labels sort in — counted from $`0`$. The index itself stays the coordinate, so $`t`$ compares against labels and $`\mathrm{pos}(t)`$ against positions.

$`\mathrm{pos}_{\mathrm{relation}(t)}(t)`$ counts within the group a relation puts $`t`$ in: the subscript names the map, $`\mathcal{T}_{\mathrm{relation}(t)}`$ is the group it lands in, and that group has a first position of its own.

$`\lvert \mathcal{T} \rvert`$ denotes the size of the set being counted along, and a position counted from the end prints against it — $`\lvert \mathcal{T} \rvert - 1`$ is the last position, one less than the size because the first is $`0`$.

### Objective

```yaml
objective:
  sense: minimize
  description: >-
    capacity once per active period at its expected cost over the scenarios, operation in
    expectation over the scenarios, and a share of it at the tail
  expression: >-
    sum(scenario_weight * Generator_p_nom_ext * Generator_capital_cost * Generator_capital_weight)
    + sum(scenario_weight * Link_p_nom_ext * Link_capital_cost * Link_capital_weight)
    + sum(scenario_weight * StorageUnit_p_nom_ext * StorageUnit_capital_cost * StorageUnit_capital_weight)
    + sum(scenario_weight * Store_e_nom_ext * Store_capital_cost * Store_capital_weight)
    + sum(scenario_weight * Line_s_nom_ext * Line_capital_cost * Line_capital_weight)
    + sum(scenario_weight * Process_p_nom_ext * Process_capital_cost * Process_capital_weight)
    + sum(scenario_weight * Transformer_s_nom_ext * Transformer_capital_cost * Transformer_capital_weight)
    + (1 - CVaR_omega) * sum(scenario_weight * scenario_opex, over=scenario)
    + CVaR_omega * CVaR
```

```math
\min \sum_{\xi \in \Xi,\ g \in \mathcal{G}} \pi_{\xi} \cdot P_{g} \cdot \mathrm{c}^{\mathrm{cap}}_{\xi,g} \cdot \mathrm{W}_{g} + \sum_{\xi \in \Xi,\ l \in \mathcal{L}} \pi_{\xi} \cdot F_{l} \cdot \mathrm{c}^{\mathrm{cap},f}_{\xi,l} \cdot \mathrm{W}^{f}_{l} + \sum_{\xi \in \Xi,\ s \in \mathcal{S}} \pi_{\xi} \cdot H_{s} \cdot \mathrm{c}^{\mathrm{cap},h}_{\xi,s} \cdot \mathrm{W}^{h}_{s} + \sum_{\xi \in \Xi,\ v \in \mathcal{V}} \pi_{\xi} \cdot E_{v} \cdot \mathrm{c}^{\mathrm{cap},e}_{\xi,v} \cdot \mathrm{W}^{e}_{v} + \sum_{\xi \in \Xi,\ k \in \mathcal{K}} \pi_{\xi} \cdot S_{k} \cdot \mathrm{c}^{\mathrm{cap},s}_{\xi,k} \cdot \mathrm{W}^{s}_{k} + \sum_{\xi \in \Xi,\ j \in \mathcal{J}} \pi_{\xi} \cdot Z_{j} \cdot \mathrm{c}^{\mathrm{cap},z}_{\xi,j} \cdot \mathrm{W}^{z}_{j} + \sum_{\xi \in \Xi,\ m \in \mathcal{M}} \pi_{\xi} \cdot \Sigma_{m} \cdot \mathrm{c}^{\mathrm{cap},\sigma}_{\xi,m} \cdot \mathrm{W}^{\sigma}_{m} + \left( 1 - \omega \right) \cdot \left( \sum_{\xi \in \Xi} \pi_{\xi} \cdot \mathit{scenario\_opex}_{\xi} \right) + \omega \cdot CVaR
```

### `Generator-fix-p-lower`

`Generator_fix_p_lower`

```yaml
Generator_fix_p_lower:
  description: "`Generator-fix-p-lower` — a fixed generator outputs at least its minimum"
  dims: [scenario, snapshot, generator]
  where: not Generator_p_nom_extendable AND not Generator_committable AND Generator_active
  expression: Generator_p >= Generator_p_min_pu * Generator_p_nom * (1 - Generator_maintenance_pu * Generator_maintenance)
```

```math
p_{\xi,t,g} \ge \underline{\mathrm{p}}_{\xi,t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{\xi,g} \cdot \left( 1 - \gamma_{\xi,g} \cdot \mu_{\xi,t,g} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \neg \mathrm{ext}_{g} \wedge \neg \mathrm{com}_{g} \wedge \mathrm{on}_{t,g}
```

### `Generator-fix-p-upper`

`Generator_fix_p_upper`

```yaml
Generator_fix_p_upper:
  description: "`Generator-fix-p-upper` — a fixed generator outputs at most what is available"
  dims: [scenario, snapshot, generator]
  where: not Generator_p_nom_extendable AND not Generator_committable AND Generator_active
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom * (1 - Generator_maintenance_pu * Generator_maintenance)
```

```math
p_{\xi,t,g} \le \overline{\mathrm{p}}_{\xi,t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{\xi,g} \cdot \left( 1 - \gamma_{\xi,g} \cdot \mu_{\xi,t,g} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \neg \mathrm{ext}_{g} \wedge \neg \mathrm{com}_{g} \wedge \mathrm{on}_{t,g}
```

### `Link-fix-p-lower`

`Link_fix_p_lower`

```yaml
Link_fix_p_lower:
  description: "`Link-fix-p-lower` — a fixed link carries at least its minimum, negative for the other way"
  dims: [scenario, snapshot, link]
  where: not Link_p_nom_extendable AND not Link_committable AND Link_active
  expression: Link_p >= Link_p_min_pu * Link_p_nom * (1 - Link_maintenance_pu * Link_maintenance)
```

```math
f_{\xi,t,l} \ge \underline{\mathrm{f}}_{\xi,t,l} \cdot \mathrm{f}^{\mathrm{nom}}_{\xi,l} \cdot \left( 1 - \gamma^{f}_{\xi,l} \cdot \mu^{f}_{\xi,t,l} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \neg \mathrm{ext}^{f}_{l} \wedge \neg \mathrm{com}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-fix-p-upper`

`Link_fix_p_upper`

```yaml
Link_fix_p_upper:
  description: "`Link-fix-p-upper` — a fixed link carries at most its nominal power"
  dims: [scenario, snapshot, link]
  where: not Link_p_nom_extendable AND not Link_committable AND Link_active
  expression: Link_p <= Link_p_max_pu * Link_p_nom * (1 - Link_maintenance_pu * Link_maintenance)
```

```math
f_{\xi,t,l} \le \overline{\mathrm{f}}_{\xi,t,l} \cdot \mathrm{f}^{\mathrm{nom}}_{\xi,l} \cdot \left( 1 - \gamma^{f}_{\xi,l} \cdot \mu^{f}_{\xi,t,l} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \neg \mathrm{ext}^{f}_{l} \wedge \neg \mathrm{com}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

### `Generator-ext-p-lower`

`Generator_ext_p_lower`

```yaml
Generator_ext_p_lower:
  description: "`Generator-ext-p-lower` — an extendable generator outputs at least its minimum of the chosen build"
  dims: [scenario, snapshot, generator]
  where: Generator_p_nom_extendable AND not Generator_committable AND Generator_active
  expression: Generator_p >= Generator_p_min_pu * (Generator_p_nom_ext - Generator_maintenance_pu * Generator_maintenance_capacity)
```

```math
p_{\xi,t,g} \ge \underline{\mathrm{p}}_{\xi,t,g} \cdot \left( P_{g} - \gamma_{\xi,g} \cdot \mu^{\mathrm{nom}}_{\xi,t,g} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{ext}_{g} \wedge \neg \mathrm{com}_{g} \wedge \mathrm{on}_{t,g}
```

### `Generator-ext-p-upper`

`Generator_ext_p_upper`

```yaml
Generator_ext_p_upper:
  description: "`Generator-ext-p-upper` — an extendable generator outputs at most what is available of the chosen build"
  dims: [scenario, snapshot, generator]
  where: Generator_p_nom_extendable AND not Generator_committable AND Generator_active
  expression: Generator_p <= Generator_p_max_pu * (Generator_p_nom_ext - Generator_maintenance_pu * Generator_maintenance_capacity)
```

```math
p_{\xi,t,g} \le \overline{\mathrm{p}}_{\xi,t,g} \cdot \left( P_{g} - \gamma_{\xi,g} \cdot \mu^{\mathrm{nom}}_{\xi,t,g} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{ext}_{g} \wedge \neg \mathrm{com}_{g} \wedge \mathrm{on}_{t,g}
```

### `Generator-ext-p_nom-lower`

`Generator_ext_p_nom_lower`

```yaml
Generator_ext_p_nom_lower:
  description: "`Generator-ext-p_nom-lower` — the chosen build is at least its floor in every scenario"
  dims: [scenario, generator]
  where: Generator_p_nom_extendable
  expression: Generator_p_nom_ext >= Generator_p_nom_min
```

```math
P_{g} \ge \underline{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{ext}_{g}
```

### `Generator-ext-p_nom-upper`

`Generator_ext_p_nom_upper`

```yaml
Generator_ext_p_nom_upper:
  description: "`Generator-ext-p_nom-upper` — the chosen build is at most its cap in every scenario; a cap of infinity is no row"
  dims: [scenario, generator]
  where: Generator_p_nom_extendable AND Generator_p_nom_max
  expression: Generator_p_nom_ext <= Generator_p_nom_max
```

```math
P_{g} \le \overline{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{ext}_{g} \wedge \overline{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} \text{ is defined}
```

### `Generator-p_nom_set`

`Generator_p_nom_set`

```yaml
Generator_p_nom_set:
  description: "`Generator-p_nom_set` — the chosen build pinned, wherever a value is given"
  dims: [scenario, generator]
  where: Generator_p_nom_extendable AND Generator_p_nom_set
  expression: Generator_p_nom_ext == Generator_p_nom_set
```

```math
P_{g} = \mathrm{p}^{\mathrm{nom,set}}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{nom,set}}_{\xi,g} \text{ is defined}
```

### `Generator-e_sum_min`

`Generator_e_sum_min`

```yaml
Generator_e_sum_min:
  description: "`Generator-e_sum_min` — energy over the horizon is at least its floor; a floor of minus infinity is no row"
  dims: [scenario, generator]
  where: Generator_e_sum_min
  expression: sum(Generator_p * snapshot_weightings_generators, over=snapshot) >= Generator_e_sum_min
```

```math
\sum_{t \in \mathcal{T}} p_{\xi,t,g} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \ge \underline{\mathrm{E}}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \underline{\mathrm{E}}_{\xi,g} \text{ is defined}
```

### `Generator-e_sum_max`

`Generator_e_sum_max`

```yaml
Generator_e_sum_max:
  description: "`Generator-e_sum_max` — energy over the horizon is at most its budget; a budget of infinity is no row"
  dims: [scenario, generator]
  where: Generator_e_sum_max
  expression: sum(Generator_p * snapshot_weightings_generators, over=snapshot) <= Generator_e_sum_max
```

```math
\sum_{t \in \mathcal{T}} p_{\xi,t,g} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \le \overline{\mathrm{E}}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \overline{\mathrm{E}}_{\xi,g} \text{ is defined}
```

### `Link-ext-p-lower`

`Link_ext_p_lower`

```yaml
Link_ext_p_lower:
  description: "`Link-ext-p-lower` — an extendable link carries at least its minimum of the chosen build, negative for the other way"
  dims: [scenario, snapshot, link]
  where: Link_p_nom_extendable AND not Link_committable AND Link_active
  expression: Link_p >= Link_p_min_pu * (Link_p_nom_ext - Link_maintenance_pu * Link_maintenance_capacity)
```

```math
f_{\xi,t,l} \ge \underline{\mathrm{f}}_{\xi,t,l} \cdot \left( F_{l} - \gamma^{f}_{\xi,l} \cdot \mu^{f,\mathrm{nom}}_{\xi,t,l} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{ext}^{f}_{l} \wedge \neg \mathrm{com}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-ext-p-upper`

`Link_ext_p_upper`

```yaml
Link_ext_p_upper:
  description: "`Link-ext-p-upper` — an extendable link carries at most the chosen build"
  dims: [scenario, snapshot, link]
  where: Link_p_nom_extendable AND not Link_committable AND Link_active
  expression: Link_p <= Link_p_max_pu * (Link_p_nom_ext - Link_maintenance_pu * Link_maintenance_capacity)
```

```math
f_{\xi,t,l} \le \overline{\mathrm{f}}_{\xi,t,l} \cdot \left( F_{l} - \gamma^{f}_{\xi,l} \cdot \mu^{f,\mathrm{nom}}_{\xi,t,l} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{ext}^{f}_{l} \wedge \neg \mathrm{com}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-ext-p_nom-lower`

`Link_ext_p_nom_lower`

```yaml
Link_ext_p_nom_lower:
  description: "`Link-ext-p_nom-lower` — the chosen build is at least its floor in every scenario"
  dims: [scenario, link]
  where: Link_p_nom_extendable
  expression: Link_p_nom_ext >= Link_p_nom_min
```

```math
F_{l} \ge \underline{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L} \,:\, \mathrm{ext}^{f}_{l}
```

### `Link-ext-p_nom-upper`

`Link_ext_p_nom_upper`

```yaml
Link_ext_p_nom_upper:
  description: "`Link-ext-p_nom-upper` — the chosen build is at most its cap in every scenario; a cap of infinity is no row"
  dims: [scenario, link]
  where: Link_p_nom_extendable AND Link_p_nom_max
  expression: Link_p_nom_ext <= Link_p_nom_max
```

```math
F_{l} \le \overline{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L} \,:\, \mathrm{ext}^{f}_{l} \wedge \overline{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} \text{ is defined}
```

### `Link-p_nom_set`

`Link_p_nom_set`

```yaml
Link_p_nom_set:
  description: "`Link-p_nom_set` — the chosen build pinned, wherever a value is given"
  dims: [scenario, link]
  where: Link_p_nom_extendable AND Link_p_nom_set
  expression: Link_p_nom_ext == Link_p_nom_set
```

```math
F_{l} = \mathrm{f}^{\mathrm{nom,set}}_{\xi,l} \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L} \,:\, \mathrm{ext}^{f}_{l} \wedge \mathrm{f}^{\mathrm{nom,set}}_{\xi,l} \text{ is defined}
```

### `Process-fix-p-lower`

`Process_fix_p_lower`

```yaml
Process_fix_p_lower:
  description: "`Process-fix-p-lower` — a fixed process runs at least its minimum, negative for the other way"
  dims: [scenario, snapshot, process]
  where: not Process_p_nom_extendable AND not Process_committable AND Process_active
  expression: Process_p >= Process_p_min_pu * Process_p_nom * (1 - Process_maintenance_pu * Process_maintenance)
```

```math
z_{\xi,t,j} \ge \underline{\mathrm{z}}_{\xi,t,j} \cdot \mathrm{z}^{\mathrm{nom}}_{\xi,j} \cdot \left( 1 - \gamma^{z}_{\xi,j} \cdot \mu^{z}_{\xi,t,j} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \neg \mathrm{ext}^{z}_{j} \wedge \neg \mathrm{com}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-fix-p-upper`

`Process_fix_p_upper`

```yaml
Process_fix_p_upper:
  description: "`Process-fix-p-upper` — a fixed process runs at most its nominal power"
  dims: [scenario, snapshot, process]
  where: not Process_p_nom_extendable AND not Process_committable AND Process_active
  expression: Process_p <= Process_p_max_pu * Process_p_nom * (1 - Process_maintenance_pu * Process_maintenance)
```

```math
z_{\xi,t,j} \le \overline{\mathrm{z}}_{\xi,t,j} \cdot \mathrm{z}^{\mathrm{nom}}_{\xi,j} \cdot \left( 1 - \gamma^{z}_{\xi,j} \cdot \mu^{z}_{\xi,t,j} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \neg \mathrm{ext}^{z}_{j} \wedge \neg \mathrm{com}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-ext-p-lower`

`Process_ext_p_lower`

```yaml
Process_ext_p_lower:
  description: "`Process-ext-p-lower` — an extendable process runs at least its minimum of the chosen build, negative for the other way"
  dims: [scenario, snapshot, process]
  where: Process_p_nom_extendable AND not Process_committable AND Process_active
  expression: Process_p >= Process_p_min_pu * (Process_p_nom_ext - Process_maintenance_pu * Process_maintenance_capacity)
```

```math
z_{\xi,t,j} \ge \underline{\mathrm{z}}_{\xi,t,j} \cdot \left( Z_{j} - \gamma^{z}_{\xi,j} \cdot \mu^{z,\mathrm{nom}}_{\xi,t,j} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{ext}^{z}_{j} \wedge \neg \mathrm{com}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-ext-p-upper`

`Process_ext_p_upper`

```yaml
Process_ext_p_upper:
  description: "`Process-ext-p-upper` — an extendable process runs at most the chosen build"
  dims: [scenario, snapshot, process]
  where: Process_p_nom_extendable AND not Process_committable AND Process_active
  expression: Process_p <= Process_p_max_pu * (Process_p_nom_ext - Process_maintenance_pu * Process_maintenance_capacity)
```

```math
z_{\xi,t,j} \le \overline{\mathrm{z}}_{\xi,t,j} \cdot \left( Z_{j} - \gamma^{z}_{\xi,j} \cdot \mu^{z,\mathrm{nom}}_{\xi,t,j} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{ext}^{z}_{j} \wedge \neg \mathrm{com}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-ext-p_nom-lower`

`Process_ext_p_nom_lower`

```yaml
Process_ext_p_nom_lower:
  description: "`Process-ext-p_nom-lower` — the chosen build is at least its floor in every scenario"
  dims: [scenario, process]
  where: Process_p_nom_extendable
  expression: Process_p_nom_ext >= Process_p_nom_min
```

```math
Z_{j} \ge \underline{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} \qquad \forall\, \xi \in \Xi,\ j \in \mathcal{J} \,:\, \mathrm{ext}^{z}_{j}
```

### `Process-ext-p_nom-upper`

`Process_ext_p_nom_upper`

```yaml
Process_ext_p_nom_upper:
  description: "`Process-ext-p_nom-upper` — the chosen build is at most its cap in every scenario; a cap of infinity is no row"
  dims: [scenario, process]
  where: Process_p_nom_extendable AND Process_p_nom_max
  expression: Process_p_nom_ext <= Process_p_nom_max
```

```math
Z_{j} \le \overline{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} \qquad \forall\, \xi \in \Xi,\ j \in \mathcal{J} \,:\, \mathrm{ext}^{z}_{j} \wedge \overline{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} \text{ is defined}
```

### `Process-p_nom_set`

`Process_p_nom_set`

```yaml
Process_p_nom_set:
  description: "`Process-p_nom_set` — the chosen build pinned, wherever a value is given"
  dims: [scenario, process]
  where: Process_p_nom_extendable AND Process_p_nom_set
  expression: Process_p_nom_ext == Process_p_nom_set
```

```math
Z_{j} = \mathrm{z}^{\mathrm{nom,set}}_{\xi,j} \qquad \forall\, \xi \in \Xi,\ j \in \mathcal{J} \,:\, \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{nom,set}}_{\xi,j} \text{ is defined}
```

### `StorageUnit-fix-p_dispatch-lower`

`StorageUnit_fix_p_dispatch_lower`

```yaml
StorageUnit_fix_p_dispatch_lower:
  description: "`StorageUnit-fix-p_dispatch-lower` — dispatch is non-negative"
  dims: [scenario, snapshot, storage_unit]
  where: not StorageUnit_p_nom_extendable AND StorageUnit_active
  expression: StorageUnit_p_dispatch >= 0
```

```math
h^{+}_{\xi,t,s} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \neg \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

### `StorageUnit-fix-p_dispatch-upper`

`StorageUnit_fix_p_dispatch_upper`

```yaml
StorageUnit_fix_p_dispatch_upper:
  description: "`StorageUnit-fix-p_dispatch-upper` — a fixed unit dispatches at most its nominal power"
  dims: [scenario, snapshot, storage_unit]
  where: not StorageUnit_p_nom_extendable AND StorageUnit_active
  expression: StorageUnit_p_dispatch <= StorageUnit_p_max_pu * StorageUnit_p_nom
```

```math
h^{+}_{\xi,t,s} \le \overline{\mathrm{h}}_{\xi,t,s} \cdot \mathrm{h}^{\mathrm{nom}}_{\xi,s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \neg \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

### `StorageUnit-fix-p_store-lower`

`StorageUnit_fix_p_store_lower`

```yaml
StorageUnit_fix_p_store_lower:
  description: "`StorageUnit-fix-p_store-lower` — storing is non-negative"
  dims: [scenario, snapshot, storage_unit]
  where: not StorageUnit_p_nom_extendable AND StorageUnit_active
  expression: StorageUnit_p_store >= 0
```

```math
h^{-}_{\xi,t,s} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \neg \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

### `StorageUnit-fix-p_store-upper`

`StorageUnit_fix_p_store_upper`

```yaml
StorageUnit_fix_p_store_upper:
  description: >-
    `StorageUnit-fix-p_store-upper` — a fixed unit stores at most its
    nominal power, the minimum-per-unit column carrying that cap negated
  dims: [scenario, snapshot, storage_unit]
  where: not StorageUnit_p_nom_extendable AND StorageUnit_active
  expression: StorageUnit_p_store <= -StorageUnit_p_min_pu * StorageUnit_p_nom
```

```math
h^{-}_{\xi,t,s} \le -\underline{\mathrm{h}}_{\xi,t,s} \cdot \mathrm{h}^{\mathrm{nom}}_{\xi,s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \neg \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

### `StorageUnit-fix-state_of_charge-lower`

`StorageUnit_fix_state_of_charge_lower`

```yaml
StorageUnit_fix_state_of_charge_lower:
  description: "`StorageUnit-fix-state_of_charge-lower` — charge is non-negative"
  dims: [scenario, snapshot, storage_unit]
  where: not StorageUnit_p_nom_extendable AND StorageUnit_active
  expression: StorageUnit_state_of_charge >= 0
```

```math
\mathit{soc}_{\xi,t,s} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \neg \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

### `StorageUnit-fix-state_of_charge-upper`

`StorageUnit_fix_state_of_charge_upper`

```yaml
StorageUnit_fix_state_of_charge_upper:
  description: "`StorageUnit-fix-state_of_charge-upper` — a fixed unit holds at most its hours at nominal power"
  dims: [scenario, snapshot, storage_unit]
  where: not StorageUnit_p_nom_extendable AND StorageUnit_active
  expression: StorageUnit_state_of_charge <= StorageUnit_max_hours * StorageUnit_p_nom
```

```math
\mathit{soc}_{\xi,t,s} \le \mathrm{T}^{h}_{\xi,s} \cdot \mathrm{h}^{\mathrm{nom}}_{\xi,s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \neg \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

### `Generator-com-p-lower`

`Generator_com_p_lower`

```yaml
Generator_com_p_lower:
  description: "`Generator-com-p-lower` — a committed unit outputs at least its minimum; off, at least nothing"
  dims: [scenario, snapshot, generator]
  where: Generator_committable AND not Generator_p_nom_extendable AND Generator_active
  expression: Generator_p >= Generator_p_min_pu * Generator_p_nom * (Generator_status - Generator_maintenance_pu * Generator_maintenance_status)
```

```math
p_{\xi,t,g} \ge \underline{\mathrm{p}}_{\xi,t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{\xi,g} \cdot \left( u_{\xi,t,g} - \gamma_{\xi,g} \cdot \mu^{u}_{\xi,t,g} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \neg \mathrm{ext}_{g} \wedge \mathrm{on}_{t,g}
```

### `Generator-com-p-upper`

`Generator_com_p_upper`

```yaml
Generator_com_p_upper:
  description: "`Generator-com-p-upper` — a committed unit outputs at most what is available; off, at most nothing"
  dims: [scenario, snapshot, generator]
  where: Generator_committable AND not Generator_p_nom_extendable AND Generator_active
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom * (Generator_status - Generator_maintenance_pu * Generator_maintenance_status)
```

```math
p_{\xi,t,g} \le \overline{\mathrm{p}}_{\xi,t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{\xi,g} \cdot \left( u_{\xi,t,g} - \gamma_{\xi,g} \cdot \mu^{u}_{\xi,t,g} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \neg \mathrm{ext}_{g} \wedge \mathrm{on}_{t,g}
```

### `Generator-com-transition-start-up`

`Generator_com_transition_start_up`

```yaml
Generator_com_transition_start_up:
  description: "`Generator-com-transition-start-up` — turning on is a start, counted against the state the unit carried into the snapshot"
  dims: [scenario, snapshot, generator]
  where: Generator_committable AND Generator_active
  expression: Generator_start_up >= Generator_status - Generator_previous_status
```

```math
\mathit{up}_{\xi,t,g} \ge u_{\xi,t,g} - \overleftarrow{u}_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{on}_{t,g}
```

### `Generator-com-transition-shut-down`

`Generator_com_transition_shut_down`

```yaml
Generator_com_transition_shut_down:
  description: "`Generator-com-transition-shut-down` — turning off is a stop, counted against the state the unit carried into the snapshot"
  dims: [scenario, snapshot, generator]
  where: Generator_committable AND Generator_active
  expression: Generator_shut_down >= Generator_previous_status - Generator_status
```

```math
\mathit{dn}_{\xi,t,g} \ge \overleftarrow{u}_{\xi,t,g} - u_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{on}_{t,g}
```

### `Generator-com-up-time`

`Generator_com_up_time`

```yaml
Generator_com_up_time:
  description: >-
    `Generator-com-up-time` — a unit started within its own minimum up time
    is still on. The first snapshot's share of the window is the brought-in
    up time's, which the must-stay-up mask carries
  dims: [scenario, snapshot, generator]
  where: Generator_committable AND Generator_min_up_time > 0 AND position(snapshot) > 0 AND Generator_active
  expression: sum_back(Generator_start_up, along=snapshot, window=Generator_min_up_time) <= Generator_status
```

```math
\sum_{t' \in \mathcal{T} \,:\, 0 \le t - t' < \mathrm{UT}} \mathit{up}_{\xi,t',g} \le u_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{UT}_{\xi,g} > 0 \wedge \mathrm{pos}(t) > 0 \wedge \mathrm{on}_{t,g}
```

### `Generator-com-down-time`

`Generator_com_down_time`

```yaml
Generator_com_down_time:
  description: >-
    `Generator-com-down-time` — a unit stopped within its own minimum down
    time is still off. The first snapshot's share of the window is the
    brought-in down time's, which the must-stay-down mask carries
  dims: [scenario, snapshot, generator]
  where: Generator_committable AND Generator_min_down_time > 0 AND position(snapshot) > 0 AND Generator_active
  expression: sum_back(Generator_shut_down, along=snapshot, window=Generator_min_down_time) <= 1 - Generator_status
```

```math
\sum_{t' \in \mathcal{T} \,:\, 0 \le t - t' < \mathrm{DT}} \mathit{dn}_{\xi,t',g} \le 1 - u_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{DT}_{\xi,g} > 0 \wedge \mathrm{pos}(t) > 0 \wedge \mathrm{on}_{t,g}
```

### `Generator-com-status-min_up_time_must_stay_up`

`Generator_com_status_must_stay_up`

```yaml
Generator_com_status_must_stay_up:
  description: "`Generator-com-status-min_up_time_must_stay_up` — a unit still serving the up time it brought in stays on"
  dims: [scenario, snapshot, generator]
  where: Generator_committable AND Generator_must_stay_up AND Generator_active
  expression: Generator_status == 1
```

```math
u_{\xi,t,g} = 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{hold}_{\xi,t,g} \wedge \mathrm{on}_{t,g}
```

### `Generator-com-status-min_down_time_must_stay_up`

`Generator_com_status_must_stay_down`

```yaml
Generator_com_status_must_stay_down:
  description: >-
    `Generator-com-status-min_down_time_must_stay_up` — a unit still serving
    the down time it brought in stays off; PyPSA names the row `_must_stay_up`
  dims: [scenario, snapshot, generator]
  where: Generator_committable AND Generator_must_stay_down AND Generator_active
  expression: Generator_status == 0
```

```math
u_{\xi,t,g} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{rest}_{\xi,t,g} \wedge \mathrm{on}_{t,g}
```

### `Generator-p-ramp_limit_up-run-bigM`

`Generator_p_ramp_limit_up_run_big_m`

```yaml
Generator_p_ramp_limit_up_run_big_m:
  description: >-
    `Generator-p-ramp_limit_up-run-bigM` — a committed extendable unit
    raises output no faster than its limit of the chosen build; the big M
    releases the row in the snapshot it turns on
  dims: [scenario, snapshot, generator]
  where: >-
    Generator_committable AND Generator_p_nom_extendable AND NOT (Generator_p_nom_mod > 0)
    AND (Generator_ramp_limit_up OR Generator_ramp_limit_start_up)
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Generator_status_initial == 0 OR Generator_p_init)))
    AND Generator_active
  expression: >-
    Generator_p - Generator_previous_p <=
    Generator_ramp_up_rate * Generator_p_nom_ext
    + Generator_big_m - Generator_big_m * Generator_previous_status
```

```math
p_{\xi,t,g} - \overleftarrow{p}_{\xi,t,g} \le \widetilde{\mathrm{ru}}_{\xi,t,g} \cdot P_{g} + \mathrm{M}_{\xi,g} - \mathrm{M}_{\xi,g} \cdot \overleftarrow{u}_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \left( \mathrm{ru}_{\xi,t,g} \text{ is defined} \vee \mathrm{ru}^{\mathrm{up}}_{\xi,g} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{0}_{\xi,g} = 0 \vee \mathrm{p}^{0}_{\xi,g} \text{ is defined} \right) \right) \wedge \mathrm{on}_{t,g}
```

### `Generator-p-ramp_limit_up-start-bigM`

`Generator_p_ramp_limit_up_start_big_m`

```yaml
Generator_p_ramp_limit_up_start_big_m:
  description: >-
    `Generator-p-ramp_limit_up-start-bigM` — in the snapshot it turns on, a
    committed extendable unit ramps no further than its start-up ramp of
    the chosen build; the big M releases the row everywhere else
  dims: [scenario, snapshot, generator]
  where: >-
    Generator_committable AND Generator_p_nom_extendable AND NOT (Generator_p_nom_mod > 0)
    AND (Generator_ramp_limit_up OR Generator_ramp_limit_start_up)
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Generator_status_initial == 0 OR Generator_p_init)))
    AND Generator_active
  expression: >-
    Generator_p - Generator_previous_p <=
    Generator_start_up_rate * Generator_p_nom_ext
    + Generator_big_m - Generator_big_m * Generator_start_up
```

```math
p_{\xi,t,g} - \overleftarrow{p}_{\xi,t,g} \le \widetilde{\mathrm{ru}}^{\mathrm{up}}_{\xi,g} \cdot P_{g} + \mathrm{M}_{\xi,g} - \mathrm{M}_{\xi,g} \cdot \mathit{up}_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \left( \mathrm{ru}_{\xi,t,g} \text{ is defined} \vee \mathrm{ru}^{\mathrm{up}}_{\xi,g} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{0}_{\xi,g} = 0 \vee \mathrm{p}^{0}_{\xi,g} \text{ is defined} \right) \right) \wedge \mathrm{on}_{t,g}
```

### `Generator-p-ramp_limit_down-run-bigM`

`Generator_p_ramp_limit_down_run_big_m`

```yaml
Generator_p_ramp_limit_down_run_big_m:
  description: >-
    `Generator-p-ramp_limit_down-run-bigM` — a committed extendable unit
    lowers output no faster than its limit of the chosen build; the big M
    releases the row in the snapshot it turns off
  dims: [scenario, snapshot, generator]
  where: >-
    Generator_committable AND Generator_p_nom_extendable AND NOT (Generator_p_nom_mod > 0)
    AND (Generator_ramp_limit_down OR Generator_ramp_limit_shut_down)
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Generator_status_initial == 0 OR Generator_p_init)))
    AND Generator_active
  expression: >-
    Generator_previous_p - Generator_p <=
    Generator_ramp_down_rate * Generator_p_nom_ext
    + Generator_big_m - Generator_big_m * Generator_status
```

```math
\overleftarrow{p}_{\xi,t,g} - p_{\xi,t,g} \le \widetilde{\mathrm{rd}}_{\xi,t,g} \cdot P_{g} + \mathrm{M}_{\xi,g} - \mathrm{M}_{\xi,g} \cdot u_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \left( \mathrm{rd}_{\xi,t,g} \text{ is defined} \vee \mathrm{rd}^{\mathrm{dn}}_{\xi,g} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{0}_{\xi,g} = 0 \vee \mathrm{p}^{0}_{\xi,g} \text{ is defined} \right) \right) \wedge \mathrm{on}_{t,g}
```

### `Generator-p-ramp_limit_down-shut-bigM`

`Generator_p_ramp_limit_down_shut_big_m`

```yaml
Generator_p_ramp_limit_down_shut_big_m:
  description: >-
    `Generator-p-ramp_limit_down-shut-bigM` — in the snapshot it turns off,
    a committed extendable unit ramps no further than its shut-down ramp of
    the chosen build; the big M releases the row everywhere else
  dims: [scenario, snapshot, generator]
  where: >-
    Generator_committable AND Generator_p_nom_extendable AND NOT (Generator_p_nom_mod > 0)
    AND (Generator_ramp_limit_down OR Generator_ramp_limit_shut_down)
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Generator_status_initial == 0 OR Generator_p_init)))
    AND Generator_active
  expression: >-
    Generator_previous_p - Generator_p <=
    Generator_shut_down_rate * Generator_p_nom_ext
    + Generator_big_m - Generator_big_m * Generator_shut_down
```

```math
\overleftarrow{p}_{\xi,t,g} - p_{\xi,t,g} \le \widetilde{\mathrm{rd}}^{\mathrm{dn}}_{\xi,g} \cdot P_{g} + \mathrm{M}_{\xi,g} - \mathrm{M}_{\xi,g} \cdot \mathit{dn}_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \left( \mathrm{rd}_{\xi,t,g} \text{ is defined} \vee \mathrm{rd}^{\mathrm{dn}}_{\xi,g} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{0}_{\xi,g} = 0 \vee \mathrm{p}^{0}_{\xi,g} \text{ is defined} \right) \right) \wedge \mathrm{on}_{t,g}
```

### `Generator-p_nom_modularity`

`Generator_p_nom_modularity`

```yaml
Generator_p_nom_modularity:
  description: "`Generator-p_nom_modularity` — the chosen build is a whole number of modules"
  dims: [generator]
  where: Generator_p_nom_extendable AND Generator_p_nom_mod > 0
  expression: Generator_p_nom_ext == Generator_p_nom_mod * Generator_n_mod
```

```math
P_{g} = \mathrm{p}^{\mathrm{mod}}_{g} \cdot N_{g} \qquad \forall\, g \in \mathcal{G} \,:\, \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0
```

### `Generator-com-ext-p-upper-cap`

`Generator_com_ext_p_upper_cap`

```yaml
Generator_com_ext_p_upper_cap:
  description: >-
    `Generator-com-ext-p-upper-cap` — a committed extendable unit outputs
    at most what is available of the chosen build, whatever its status
  dims: [scenario, snapshot, generator]
  where: Generator_committable AND Generator_p_nom_extendable AND NOT (Generator_p_nom_mod > 0) AND Generator_active
  expression: Generator_p <= Generator_p_max_pu * (Generator_p_nom_ext - Generator_maintenance_pu * Generator_maintenance_capacity)
```

```math
p_{\xi,t,g} \le \overline{\mathrm{p}}_{\xi,t,g} \cdot \left( P_{g} - \gamma_{\xi,g} \cdot \mu^{\mathrm{nom}}_{\xi,t,g} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
```

### `Generator-com-ext-p-upper-bigM`

`Generator_com_ext_p_upper_big_m`

```yaml
Generator_com_ext_p_upper_big_m:
  description: "`Generator-com-ext-p-upper-bigM` — off, a unit outputs nothing; on, the big M is no bound"
  dims: [scenario, snapshot, generator]
  where: Generator_committable AND Generator_p_nom_extendable AND NOT (Generator_p_nom_mod > 0) AND Generator_active
  expression: Generator_p <= Generator_big_m * Generator_status
```

```math
p_{\xi,t,g} \le \mathrm{M}_{\xi,g} \cdot u_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
```

### `Generator-com-ext-p-lower`

`Generator_com_ext_p_lower`

```yaml
Generator_com_ext_p_lower:
  description: >-
    `Generator-com-ext-p-lower` — a committed extendable unit outputs at
    least its minimum of the chosen build; off, the big M releases the row
  dims: [scenario, snapshot, generator]
  where: Generator_committable AND Generator_p_nom_extendable AND NOT (Generator_p_nom_mod > 0) AND Generator_active
  expression: >-
    Generator_p >=
    Generator_p_min_pu * (Generator_p_nom_ext - Generator_maintenance_pu * Generator_maintenance_capacity)
    + Generator_big_m * Generator_status - Generator_big_m
```

```math
p_{\xi,t,g} \ge \underline{\mathrm{p}}_{\xi,t,g} \cdot \left( P_{g} - \gamma_{\xi,g} \cdot \mu^{\mathrm{nom}}_{\xi,t,g} \right) + \mathrm{M}_{\xi,g} \cdot u_{\xi,t,g} - \mathrm{M}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
```

### `Generator-com-ext-p-lower-nonneg`

`Generator_com_ext_p_lower_nonneg`

```yaml
Generator_com_ext_p_lower_nonneg:
  description: >-
    `Generator-com-ext-p-lower-nonneg` — where no minimum-per-unit is
    negative, output is also plainly non-negative, a row the big-M lower
    cannot assert while the unit is off
  dims: [scenario, snapshot, generator]
  where: >-
    Generator_committable AND Generator_p_nom_extendable
    AND Generator_p_min_pu_nonneg AND NOT (Generator_p_nom_mod > 0) AND Generator_active
  expression: Generator_p >= 0
```

```math
p_{\xi,t,g} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \mathrm{nonneg}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
```

### `Generator-com-mod-p-lower`

`Generator_com_mod_p_lower`

```yaml
Generator_com_mod_p_lower:
  description: >-
    `Generator-com-mod-p-lower` — a committed modular unit outputs at least
    its minimum of one module, whether the build is fixed or a decision
  dims: [scenario, snapshot, generator]
  where: Generator_committable AND Generator_p_nom_mod > 0 AND Generator_active
  expression: Generator_p >= Generator_p_min_pu * Generator_p_nom_mod * (Generator_status - Generator_maintenance_pu * Generator_maintenance_status)
```

```math
p_{\xi,t,g} \ge \underline{\mathrm{p}}_{\xi,t,g} \cdot \mathrm{p}^{\mathrm{mod}}_{g} \cdot \left( u_{\xi,t,g} - \gamma_{\xi,g} \cdot \mu^{u}_{\xi,t,g} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \wedge \mathrm{on}_{t,g}
```

### `Generator-com-mod-p-upper`

`Generator_com_mod_p_upper`

```yaml
Generator_com_mod_p_upper:
  description: >-
    `Generator-com-mod-p-upper` — a committed modular unit outputs at most
    one module's share, whether the build is fixed or a decision
  dims: [scenario, snapshot, generator]
  where: Generator_committable AND Generator_p_nom_mod > 0 AND Generator_active
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom_mod * (Generator_status - Generator_maintenance_pu * Generator_maintenance_status)
```

```math
p_{\xi,t,g} \le \overline{\mathrm{p}}_{\xi,t,g} \cdot \mathrm{p}^{\mathrm{mod}}_{g} \cdot \left( u_{\xi,t,g} - \gamma_{\xi,g} \cdot \mu^{u}_{\xi,t,g} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \wedge \mathrm{on}_{t,g}
```

### `Generator-status-p-fixed-upper`

`Generator_status_p_fixed_upper`

```yaml
Generator_status_p_fixed_upper:
  description: >-
    `Generator-status-p-fixed-upper` — a status is at most the modules in
    place, an explicit row as PyPSA writes it: one where the build is not
    modular, and the fixed build's whole count of modules where it is
  dims: [scenario, snapshot, generator]
  where: Generator_committable AND NOT (Generator_p_nom_extendable AND Generator_p_nom_mod > 0) AND Generator_active
  expression: Generator_status <= Generator_modules_installed
```

```math
u_{\xi,t,g} \le \mathrm{N}^{\mathrm{fix}}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \neg \left( \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
```

### `Generator-start_up-p-fixed-upper`

`Generator_start_up_p_fixed_upper`

```yaml
Generator_start_up_p_fixed_upper:
  description: >-
    `Generator-start_up-p-fixed-upper` — a start is at most the modules in
    place, an explicit row as PyPSA writes it: one where the build is not
    modular, and the fixed build's whole count of modules where it is
  dims: [scenario, snapshot, generator]
  where: Generator_committable AND NOT (Generator_p_nom_extendable AND Generator_p_nom_mod > 0) AND Generator_active
  expression: Generator_start_up <= Generator_modules_installed
```

```math
\mathit{up}_{\xi,t,g} \le \mathrm{N}^{\mathrm{fix}}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \neg \left( \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
```

### `Generator-shut_down-p-fixed-upper`

`Generator_shut_down_p_fixed_upper`

```yaml
Generator_shut_down_p_fixed_upper:
  description: >-
    `Generator-shut_down-p-fixed-upper` — a stop is at most the modules in
    place, an explicit row as PyPSA writes it: one where the build is not
    modular, and the fixed build's whole count of modules where it is
  dims: [scenario, snapshot, generator]
  where: Generator_committable AND NOT (Generator_p_nom_extendable AND Generator_p_nom_mod > 0) AND Generator_active
  expression: Generator_shut_down <= Generator_modules_installed
```

```math
\mathit{dn}_{\xi,t,g} \le \mathrm{N}^{\mathrm{fix}}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \neg \left( \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
```

### `Generator-status-p_nom-variable-upper`

`Generator_status_p_nom_variable_upper`

```yaml
Generator_status_p_nom_variable_upper:
  description: "`Generator-status-p_nom-variable-upper` — a modular unit is on only where a module is built"
  dims: [scenario, snapshot, generator]
  where: Generator_committable AND Generator_p_nom_extendable AND Generator_p_nom_mod > 0 AND Generator_active
  expression: Generator_status <= Generator_n_mod
```

```math
u_{\xi,t,g} \le N_{g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \wedge \mathrm{on}_{t,g}
```

### `Generator-start_up-p_nom-variable-upper`

`Generator_start_up_p_nom_variable_upper`

```yaml
Generator_start_up_p_nom_variable_upper:
  description: "`Generator-start_up-p_nom-variable-upper` — a modular unit starts only where a module is built"
  dims: [scenario, snapshot, generator]
  where: Generator_committable AND Generator_p_nom_extendable AND Generator_p_nom_mod > 0 AND Generator_active
  expression: Generator_start_up <= Generator_n_mod
```

```math
\mathit{up}_{\xi,t,g} \le N_{g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \wedge \mathrm{on}_{t,g}
```

### `Generator-shut_down-p_nom-variable-upper`

`Generator_shut_down_p_nom_variable_upper`

```yaml
Generator_shut_down_p_nom_variable_upper:
  description: "`Generator-shut_down-p_nom-variable-upper` — a modular unit stops only where a module is built"
  dims: [scenario, snapshot, generator]
  where: Generator_committable AND Generator_p_nom_extendable AND Generator_p_nom_mod > 0 AND Generator_active
  expression: Generator_shut_down <= Generator_n_mod
```

```math
\mathit{dn}_{\xi,t,g} \le N_{g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \wedge \mathrm{on}_{t,g}
```

### `Generator-maint-event-count`

`Generator_maint_event_count`

```yaml
Generator_maint_event_count:
  description: "`Generator-maint-event-count` — a maintainable generator holds its number of maintenance events over the horizon"
  dims: [scenario, generator]
  where: Generator_maintainable
  expression: sum(Generator_maintenance_start, over=snapshot) == Generator_maintenance_events
```

```math
\sum_{t \in \mathcal{T}} \mu^{\mathrm{up}}_{\xi,t,g} = \mathrm{n}^{\mathrm{mnt}}_{\xi,g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g}
```

### `Generator-maint-window`

`Generator_maint_window`

```yaml
Generator_maint_window:
  description: >-
    `Generator-maint-window` — a generator is in maintenance exactly where an event it
    started covers the snapshot; two events do not overlap, since the
    maintenance status is at most one
  dims: [scenario, snapshot, generator]
  where: Generator_maintainable AND Generator_active
  expression: Generator_maintenance == sum(Generator_maintenance_start, by=Generator_maintenance_cover, over=start, into=covered)
```

```math
\mu_{\xi,t,g} = \sum_{t' \in \mathcal{T} \,:\, \left( \xi,\ g,\ t',\ t \right) \in \mathrm{Generator\_maintenance\_cover}} \mu^{\mathrm{up}}_{\xi,t',g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{on}_{t,g}
```

### `Generator-maint-start-horizon`

`Generator_maint_start_horizon`

```yaml
Generator_maint_start_horizon:
  description: "`Generator-maint-start-horizon` — no event starts where it could not run its whole duration"
  dims: [scenario, snapshot, generator]
  where: Generator_maintainable AND Generator_active AND Generator_maintenance_start_blocked
  expression: Generator_maintenance_start == 0
```

```math
\mu^{\mathrm{up}}_{\xi,t,g} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{on}_{t,g} \wedge \mathrm{blk}_{\xi,t,g}
```

### `Generator-maintcap_upper`

`Generator_maintcap_upper`

```yaml
Generator_maintcap_upper:
  description: >-
    `Generator-maintcap_upper` — the build taken off is at most the chosen build in
    maintenance, and at most the build less its floor out of it
  dims: [scenario, snapshot, generator]
  where: Generator_maintainable AND Generator_p_nom_extendable AND NOT (Generator_committable AND Generator_p_nom_mod > 0) AND Generator_active
  expression: Generator_maintenance_capacity <= Generator_p_nom_ext - Generator_p_nom_min * (1 - Generator_maintenance)
```

```math
\mu^{\mathrm{nom}}_{\xi,t,g} \le P_{g} - \underline{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} \cdot \left( 1 - \mu_{\xi,t,g} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{com}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
```

### `Generator-maintcap_upper_nommax`

`Generator_maintcap_upper_nommax`

```yaml
Generator_maintcap_upper_nommax:
  description: "`Generator-maintcap_upper_nommax` — out of maintenance, no build is taken off"
  dims: [scenario, snapshot, generator]
  where: Generator_maintainable AND Generator_p_nom_extendable AND NOT (Generator_committable AND Generator_p_nom_mod > 0) AND Generator_active
  expression: Generator_maintenance_capacity <= Generator_p_nom_max * Generator_maintenance
```

```math
\mu^{\mathrm{nom}}_{\xi,t,g} \le \overline{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} \cdot \mu_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{com}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
```

### `Generator-maintcap_lower_nommax`

`Generator_maintcap_lower_nommax`

```yaml
Generator_maintcap_lower_nommax:
  description: "`Generator-maintcap_lower_nommax` — in maintenance, the whole chosen build is taken off"
  dims: [scenario, snapshot, generator]
  where: Generator_maintainable AND Generator_p_nom_extendable AND NOT (Generator_committable AND Generator_p_nom_mod > 0) AND Generator_active
  expression: Generator_maintenance_capacity >= Generator_p_nom_ext - Generator_p_nom_max * (1 - Generator_maintenance)
```

```math
\mu^{\mathrm{nom}}_{\xi,t,g} \ge P_{g} - \overline{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} \cdot \left( 1 - \mu_{\xi,t,g} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{com}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
```

### `Generator-maintcap_lower_nommin`

`Generator_maintcap_lower_nommin`

```yaml
Generator_maintcap_lower_nommin:
  description: "`Generator-maintcap_lower_nommin` — in maintenance, at least the floor of the build is taken off"
  dims: [scenario, snapshot, generator]
  where: Generator_maintainable AND Generator_p_nom_extendable AND NOT (Generator_committable AND Generator_p_nom_mod > 0) AND Generator_active AND Generator_p_nom_min > 0
  expression: Generator_maintenance_capacity >= Generator_p_nom_min * Generator_maintenance
```

```math
\mu^{\mathrm{nom}}_{\xi,t,g} \ge \underline{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} \cdot \mu_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{com}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g} \wedge \underline{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} > 0
```

### `Generator-maint-status-le-status`

`Generator_maint_status_le_status`

```yaml
Generator_maint_status_le_status:
  description: "`Generator-maint-status-le-status` — the status in maintenance is at most the status"
  dims: [scenario, snapshot, generator]
  where: Generator_maintainable AND Generator_committable AND NOT Generator_p_nom_extendable AND Generator_active
  expression: Generator_maintenance_status <= Generator_status
```

```math
\mu^{u}_{\xi,t,g} \le u_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{com}_{g} \wedge \neg \mathrm{ext}_{g} \wedge \mathrm{on}_{t,g}
```

### `Generator-maint-status-le-maint`

`Generator_maint_status_le_maint`

```yaml
Generator_maint_status_le_maint:
  description: "`Generator-maint-status-le-maint` — out of maintenance, the status in maintenance is zero"
  dims: [scenario, snapshot, generator]
  where: Generator_maintainable AND Generator_committable AND NOT Generator_p_nom_extendable AND Generator_active
  expression: Generator_maintenance_status <= Generator_maintenance
```

```math
\mu^{u}_{\xi,t,g} \le \mu_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{com}_{g} \wedge \neg \mathrm{ext}_{g} \wedge \mathrm{on}_{t,g}
```

### `Generator-maint-status-lb`

`Generator_maint_status_lb`

```yaml
Generator_maint_status_lb:
  description: "`Generator-maint-status-lb` — on and in maintenance, the status in maintenance is one"
  dims: [scenario, snapshot, generator]
  where: Generator_maintainable AND Generator_committable AND NOT Generator_p_nom_extendable AND Generator_active
  expression: Generator_maintenance_status >= Generator_status + Generator_maintenance - 1
```

```math
\mu^{u}_{\xi,t,g} \ge u_{\xi,t,g} + \mu_{\xi,t,g} - 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{com}_{g} \wedge \neg \mathrm{ext}_{g} \wedge \mathrm{on}_{t,g}
```

### `Generator-maint-modstatus-le-status`

`Generator_maint_modstatus_le_status`

```yaml
Generator_maint_modstatus_le_status:
  description: "`Generator-maint-modstatus-le-status` — the modules on in maintenance are at most the modules on"
  dims: [scenario, snapshot, generator]
  where: Generator_maintainable AND Generator_committable AND Generator_p_nom_mod > 0 AND Generator_active
  expression: Generator_maintenance_status <= Generator_status
```

```math
\mu^{u}_{\xi,t,g} \le u_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{com}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \wedge \mathrm{on}_{t,g}
```

### `Generator-maint-modstatus-le-maint`

`Generator_maint_modstatus_le_maint`

```yaml
Generator_maint_modstatus_le_maint:
  description: >-
    `Generator-maint-modstatus-le-maint` — out of maintenance, no module is on in
    maintenance; in it, at most the modules the build cap holds
  dims: [scenario, snapshot, generator]
  where: Generator_maintainable AND Generator_committable AND Generator_p_nom_mod > 0 AND Generator_active
  expression: Generator_maintenance_status <= Generator_p_nom_max / Generator_p_nom_mod * Generator_maintenance
```

```math
\mu^{u}_{\xi,t,g} \le \frac{\overline{\mathrm{p}}^{\mathrm{nom}}_{\xi,g}}{\mathrm{p}^{\mathrm{mod}}_{g}} \cdot \mu_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{com}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \wedge \mathrm{on}_{t,g}
```

### `Generator-maint-modstatus-lb`

`Generator_maint_modstatus_lb`

```yaml
Generator_maint_modstatus_lb:
  description: "`Generator-maint-modstatus-lb` — in maintenance, every module on is on in maintenance"
  dims: [scenario, snapshot, generator]
  where: Generator_maintainable AND Generator_committable AND Generator_p_nom_mod > 0 AND Generator_active
  expression: Generator_maintenance_status >= Generator_status - Generator_p_nom_max / Generator_p_nom_mod * (1 - Generator_maintenance)
```

```math
\mu^{u}_{\xi,t,g} \ge u_{\xi,t,g} - \frac{\overline{\mathrm{p}}^{\mathrm{nom}}_{\xi,g}}{\mathrm{p}^{\mathrm{mod}}_{g}} \cdot \left( 1 - \mu_{\xi,t,g} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{com}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \wedge \mathrm{on}_{t,g}
```

### `Link-com-p-lower`

`Link_com_p_lower`

```yaml
Link_com_p_lower:
  description: "`Link-com-p-lower` — a committed link flows at least its minimum; off, at least nothing"
  dims: [scenario, snapshot, link]
  where: Link_committable AND not Link_p_nom_extendable AND Link_active
  expression: Link_p >= Link_p_min_pu * Link_p_nom * (Link_status - Link_maintenance_pu * Link_maintenance_status)
```

```math
f_{\xi,t,l} \ge \underline{\mathrm{f}}_{\xi,t,l} \cdot \mathrm{f}^{\mathrm{nom}}_{\xi,l} \cdot \left( u^{f}_{\xi,t,l} - \gamma^{f}_{\xi,l} \cdot \mu^{f,u}_{\xi,t,l} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \neg \mathrm{ext}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-com-p-upper`

`Link_com_p_upper`

```yaml
Link_com_p_upper:
  description: "`Link-com-p-upper` — a committed link flows at most what is available; off, at most nothing"
  dims: [scenario, snapshot, link]
  where: Link_committable AND not Link_p_nom_extendable AND Link_active
  expression: Link_p <= Link_p_max_pu * Link_p_nom * (Link_status - Link_maintenance_pu * Link_maintenance_status)
```

```math
f_{\xi,t,l} \le \overline{\mathrm{f}}_{\xi,t,l} \cdot \mathrm{f}^{\mathrm{nom}}_{\xi,l} \cdot \left( u^{f}_{\xi,t,l} - \gamma^{f}_{\xi,l} \cdot \mu^{f,u}_{\xi,t,l} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \neg \mathrm{ext}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-com-transition-start-up`

`Link_com_transition_start_up`

```yaml
Link_com_transition_start_up:
  description: "`Link-com-transition-start-up` — turning on is a start, counted against the state the link carried into the snapshot"
  dims: [scenario, snapshot, link]
  where: Link_committable AND Link_active
  expression: Link_start_up >= Link_status - Link_previous_status
```

```math
\mathit{up}^{f}_{\xi,t,l} \ge u^{f}_{\xi,t,l} - \overleftarrow{u}^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-com-transition-shut-down`

`Link_com_transition_shut_down`

```yaml
Link_com_transition_shut_down:
  description: "`Link-com-transition-shut-down` — turning off is a stop, counted against the state the link carried into the snapshot"
  dims: [scenario, snapshot, link]
  where: Link_committable AND Link_active
  expression: Link_shut_down >= Link_previous_status - Link_status
```

```math
\mathit{dn}^{f}_{\xi,t,l} \ge \overleftarrow{u}^{f}_{\xi,t,l} - u^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-com-up-time`

`Link_com_up_time`

```yaml
Link_com_up_time:
  description: >-
    `Link-com-up-time` — a link started within its own minimum up time
    is still on. The first snapshot's share of the window is the brought-in
    up time's, which the must-stay-up mask carries
  dims: [scenario, snapshot, link]
  where: Link_committable AND Link_min_up_time > 0 AND position(snapshot) > 0 AND Link_active
  expression: sum_back(Link_start_up, along=snapshot, window=Link_min_up_time) <= Link_status
```

```math
\sum_{t' \in \mathcal{T} \,:\, 0 \le t - t' < \mathrm{UT}^{f}} \mathit{up}^{f}_{\xi,t',l} \le u^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{UT}^{f}_{\xi,l} > 0 \wedge \mathrm{pos}(t) > 0 \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-com-down-time`

`Link_com_down_time`

```yaml
Link_com_down_time:
  description: >-
    `Link-com-down-time` — a link stopped within its own minimum down
    time is still off. The first snapshot's share of the window is the
    brought-in down time's, which the must-stay-down mask carries
  dims: [scenario, snapshot, link]
  where: Link_committable AND Link_min_down_time > 0 AND position(snapshot) > 0 AND Link_active
  expression: sum_back(Link_shut_down, along=snapshot, window=Link_min_down_time) <= 1 - Link_status
```

```math
\sum_{t' \in \mathcal{T} \,:\, 0 \le t - t' < \mathrm{DT}^{f}} \mathit{dn}^{f}_{\xi,t',l} \le 1 - u^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{DT}^{f}_{\xi,l} > 0 \wedge \mathrm{pos}(t) > 0 \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-com-status-min_up_time_must_stay_up`

`Link_com_status_must_stay_up`

```yaml
Link_com_status_must_stay_up:
  description: "`Link-com-status-min_up_time_must_stay_up` — a link still serving the up time it brought in stays on"
  dims: [scenario, snapshot, link]
  where: Link_committable AND Link_must_stay_up AND Link_active
  expression: Link_status == 1
```

```math
u^{f}_{\xi,t,l} = 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{hold}^{f}_{\xi,t,l} \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-com-status-min_down_time_must_stay_up`

`Link_com_status_must_stay_down`

```yaml
Link_com_status_must_stay_down:
  description: >-
    `Link-com-status-min_down_time_must_stay_up` — a link still serving
    the down time it brought in stays off; PyPSA names the row `_must_stay_up`
  dims: [scenario, snapshot, link]
  where: Link_committable AND Link_must_stay_down AND Link_active
  expression: Link_status == 0
```

```math
u^{f}_{\xi,t,l} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{rest}^{f}_{\xi,t,l} \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-p-ramp_limit_up-run-bigM`

`Link_p_ramp_limit_up_run_big_m`

```yaml
Link_p_ramp_limit_up_run_big_m:
  description: >-
    `Link-p-ramp_limit_up-run-bigM` — a committed extendable link
    raises flow no faster than its limit of the chosen build; the big M
    releases the row in the snapshot it turns on
  dims: [scenario, snapshot, link]
  where: >-
    Link_committable AND Link_p_nom_extendable AND NOT (Link_p_nom_mod > 0)
    AND (Link_ramp_limit_up OR Link_ramp_limit_start_up)
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Link_status_initial == 0 OR Link_p_init)))
    AND Link_active
  expression: >-
    Link_p - Link_previous_p <=
    Link_ramp_up_rate * Link_p_nom_ext
    + Link_big_m - Link_big_m * Link_previous_status
```

```math
f_{\xi,t,l} - \overleftarrow{f}_{\xi,t,l} \le \widetilde{\mathrm{ru}}^{f}_{\xi,t,l} \cdot F_{l} + \mathrm{M}^{f}_{\xi,l} - \mathrm{M}^{f}_{\xi,l} \cdot \overleftarrow{u}^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \left( \mathrm{ru}^{f}_{\xi,t,l} \text{ is defined} \vee \mathrm{ru}^{f,\mathrm{up}}_{\xi,l} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{f,0}_{\xi,l} = 0 \vee \mathrm{f}^{0}_{\xi,l} \text{ is defined} \right) \right) \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-p-ramp_limit_up-start-bigM`

`Link_p_ramp_limit_up_start_big_m`

```yaml
Link_p_ramp_limit_up_start_big_m:
  description: >-
    `Link-p-ramp_limit_up-start-bigM` — in the snapshot it turns on, a
    committed extendable link ramps no further than its start-up ramp of
    the chosen build; the big M releases the row everywhere else
  dims: [scenario, snapshot, link]
  where: >-
    Link_committable AND Link_p_nom_extendable AND NOT (Link_p_nom_mod > 0)
    AND (Link_ramp_limit_up OR Link_ramp_limit_start_up)
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Link_status_initial == 0 OR Link_p_init)))
    AND Link_active
  expression: >-
    Link_p - Link_previous_p <=
    Link_start_up_rate * Link_p_nom_ext
    + Link_big_m - Link_big_m * Link_start_up
```

```math
f_{\xi,t,l} - \overleftarrow{f}_{\xi,t,l} \le \widetilde{\mathrm{ru}}^{f,\mathrm{up}}_{\xi,l} \cdot F_{l} + \mathrm{M}^{f}_{\xi,l} - \mathrm{M}^{f}_{\xi,l} \cdot \mathit{up}^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \left( \mathrm{ru}^{f}_{\xi,t,l} \text{ is defined} \vee \mathrm{ru}^{f,\mathrm{up}}_{\xi,l} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{f,0}_{\xi,l} = 0 \vee \mathrm{f}^{0}_{\xi,l} \text{ is defined} \right) \right) \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-p-ramp_limit_down-run-bigM`

`Link_p_ramp_limit_down_run_big_m`

```yaml
Link_p_ramp_limit_down_run_big_m:
  description: >-
    `Link-p-ramp_limit_down-run-bigM` — a committed extendable link
    lowers flow no faster than its limit of the chosen build; the big M
    releases the row in the snapshot it turns off
  dims: [scenario, snapshot, link]
  where: >-
    Link_committable AND Link_p_nom_extendable AND NOT (Link_p_nom_mod > 0)
    AND (Link_ramp_limit_down OR Link_ramp_limit_shut_down)
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Link_status_initial == 0 OR Link_p_init)))
    AND Link_active
  expression: >-
    Link_previous_p - Link_p <=
    Link_ramp_down_rate * Link_p_nom_ext
    + Link_big_m - Link_big_m * Link_status
```

```math
\overleftarrow{f}_{\xi,t,l} - f_{\xi,t,l} \le \widetilde{\mathrm{rd}}^{f}_{\xi,t,l} \cdot F_{l} + \mathrm{M}^{f}_{\xi,l} - \mathrm{M}^{f}_{\xi,l} \cdot u^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \left( \mathrm{rd}^{f}_{\xi,t,l} \text{ is defined} \vee \mathrm{rd}^{f,\mathrm{dn}}_{\xi,l} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{f,0}_{\xi,l} = 0 \vee \mathrm{f}^{0}_{\xi,l} \text{ is defined} \right) \right) \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-p-ramp_limit_down-shut-bigM`

`Link_p_ramp_limit_down_shut_big_m`

```yaml
Link_p_ramp_limit_down_shut_big_m:
  description: >-
    `Link-p-ramp_limit_down-shut-bigM` — in the snapshot it turns off,
    a committed extendable link ramps no further than its shut-down ramp of
    the chosen build; the big M releases the row everywhere else
  dims: [scenario, snapshot, link]
  where: >-
    Link_committable AND Link_p_nom_extendable AND NOT (Link_p_nom_mod > 0)
    AND (Link_ramp_limit_down OR Link_ramp_limit_shut_down)
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Link_status_initial == 0 OR Link_p_init)))
    AND Link_active
  expression: >-
    Link_previous_p - Link_p <=
    Link_shut_down_rate * Link_p_nom_ext
    + Link_big_m - Link_big_m * Link_shut_down
```

```math
\overleftarrow{f}_{\xi,t,l} - f_{\xi,t,l} \le \widetilde{\mathrm{rd}}^{f,\mathrm{dn}}_{\xi,l} \cdot F_{l} + \mathrm{M}^{f}_{\xi,l} - \mathrm{M}^{f}_{\xi,l} \cdot \mathit{dn}^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \left( \mathrm{rd}^{f}_{\xi,t,l} \text{ is defined} \vee \mathrm{rd}^{f,\mathrm{dn}}_{\xi,l} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{f,0}_{\xi,l} = 0 \vee \mathrm{f}^{0}_{\xi,l} \text{ is defined} \right) \right) \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-p_nom_modularity`

`Link_p_nom_modularity`

```yaml
Link_p_nom_modularity:
  description: "`Link-p_nom_modularity` — the chosen build is a whole number of modules"
  dims: [link]
  where: Link_p_nom_extendable AND Link_p_nom_mod > 0
  expression: Link_p_nom_ext == Link_p_nom_mod * Link_n_mod
```

```math
F_{l} = \mathrm{f}^{\mathrm{mod}}_{l} \cdot N^{f}_{l} \qquad \forall\, l \in \mathcal{L} \,:\, \mathrm{ext}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0
```

### `Link-com-ext-p-upper-cap`

`Link_com_ext_p_upper_cap`

```yaml
Link_com_ext_p_upper_cap:
  description: >-
    `Link-com-ext-p-upper-cap` — a committed extendable link flows
    at most what is available of the chosen build, whatever its status
  dims: [scenario, snapshot, link]
  where: Link_committable AND Link_p_nom_extendable AND NOT (Link_p_nom_mod > 0) AND Link_active
  expression: Link_p <= Link_p_max_pu * (Link_p_nom_ext - Link_maintenance_pu * Link_maintenance_capacity)
```

```math
f_{\xi,t,l} \le \overline{\mathrm{f}}_{\xi,t,l} \cdot \left( F_{l} - \gamma^{f}_{\xi,l} \cdot \mu^{f,\mathrm{nom}}_{\xi,t,l} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-com-ext-p-upper-bigM`

`Link_com_ext_p_upper_big_m`

```yaml
Link_com_ext_p_upper_big_m:
  description: "`Link-com-ext-p-upper-bigM` — off, a link flows nothing; on, the big M is no bound"
  dims: [scenario, snapshot, link]
  where: Link_committable AND Link_p_nom_extendable AND NOT (Link_p_nom_mod > 0) AND Link_active
  expression: Link_p <= Link_big_m * Link_status
```

```math
f_{\xi,t,l} \le \mathrm{M}^{f}_{\xi,l} \cdot u^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-com-ext-p-lower`

`Link_com_ext_p_lower`

```yaml
Link_com_ext_p_lower:
  description: >-
    `Link-com-ext-p-lower` — a committed extendable link flows at
    least its minimum of the chosen build; off, the big M releases the row
  dims: [scenario, snapshot, link]
  where: Link_committable AND Link_p_nom_extendable AND NOT (Link_p_nom_mod > 0) AND Link_active
  expression: >-
    Link_p >=
    Link_p_min_pu * (Link_p_nom_ext - Link_maintenance_pu * Link_maintenance_capacity)
    + Link_big_m * Link_status - Link_big_m
```

```math
f_{\xi,t,l} \ge \underline{\mathrm{f}}_{\xi,t,l} \cdot \left( F_{l} - \gamma^{f}_{\xi,l} \cdot \mu^{f,\mathrm{nom}}_{\xi,t,l} \right) + \mathrm{M}^{f}_{\xi,l} \cdot u^{f}_{\xi,t,l} - \mathrm{M}^{f}_{\xi,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-com-ext-p-lower-nonneg`

`Link_com_ext_p_lower_nonneg`

```yaml
Link_com_ext_p_lower_nonneg:
  description: >-
    `Link-com-ext-p-lower-nonneg` — where no minimum-per-unit is
    negative, flow is also plainly non-negative, a row the big-M lower
    cannot assert while the link is off
  dims: [scenario, snapshot, link]
  where: >-
    Link_committable AND Link_p_nom_extendable
    AND Link_p_min_pu_nonneg AND NOT (Link_p_nom_mod > 0) AND Link_active
  expression: Link_p >= 0
```

```math
f_{\xi,t,l} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \mathrm{nonneg}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-com-mod-p-lower`

`Link_com_mod_p_lower`

```yaml
Link_com_mod_p_lower:
  description: >-
    `Link-com-mod-p-lower` — a committed modular link flows at least
    its minimum of one module, whether the build is fixed or a decision
  dims: [scenario, snapshot, link]
  where: Link_committable AND Link_p_nom_mod > 0 AND Link_active
  expression: Link_p >= Link_p_min_pu * Link_p_nom_mod * (Link_status - Link_maintenance_pu * Link_maintenance_status)
```

```math
f_{\xi,t,l} \ge \underline{\mathrm{f}}_{\xi,t,l} \cdot \mathrm{f}^{\mathrm{mod}}_{l} \cdot \left( u^{f}_{\xi,t,l} - \gamma^{f}_{\xi,l} \cdot \mu^{f,u}_{\xi,t,l} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-com-mod-p-upper`

`Link_com_mod_p_upper`

```yaml
Link_com_mod_p_upper:
  description: >-
    `Link-com-mod-p-upper` — a committed modular link flows at most
    one module's share, whether the build is fixed or a decision
  dims: [scenario, snapshot, link]
  where: Link_committable AND Link_p_nom_mod > 0 AND Link_active
  expression: Link_p <= Link_p_max_pu * Link_p_nom_mod * (Link_status - Link_maintenance_pu * Link_maintenance_status)
```

```math
f_{\xi,t,l} \le \overline{\mathrm{f}}_{\xi,t,l} \cdot \mathrm{f}^{\mathrm{mod}}_{l} \cdot \left( u^{f}_{\xi,t,l} - \gamma^{f}_{\xi,l} \cdot \mu^{f,u}_{\xi,t,l} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-status-p-fixed-upper`

`Link_status_p_fixed_upper`

```yaml
Link_status_p_fixed_upper:
  description: >-
    `Link-status-p-fixed-upper` — a status is at most the modules in
    place, an explicit row as PyPSA writes it: one where the build is not
    modular, and the fixed build's whole count of modules where it is
  dims: [scenario, snapshot, link]
  where: Link_committable AND NOT (Link_p_nom_extendable AND Link_p_nom_mod > 0) AND Link_active
  expression: Link_status <= Link_modules_installed
```

```math
u^{f}_{\xi,t,l} \le \mathrm{N}^{f,\mathrm{fix}}_{\xi,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \neg \left( \mathrm{ext}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-start_up-p-fixed-upper`

`Link_start_up_p_fixed_upper`

```yaml
Link_start_up_p_fixed_upper:
  description: >-
    `Link-start_up-p-fixed-upper` — a start is at most the modules in
    place, an explicit row as PyPSA writes it: one where the build is not
    modular, and the fixed build's whole count of modules where it is
  dims: [scenario, snapshot, link]
  where: Link_committable AND NOT (Link_p_nom_extendable AND Link_p_nom_mod > 0) AND Link_active
  expression: Link_start_up <= Link_modules_installed
```

```math
\mathit{up}^{f}_{\xi,t,l} \le \mathrm{N}^{f,\mathrm{fix}}_{\xi,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \neg \left( \mathrm{ext}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-shut_down-p-fixed-upper`

`Link_shut_down_p_fixed_upper`

```yaml
Link_shut_down_p_fixed_upper:
  description: >-
    `Link-shut_down-p-fixed-upper` — a stop is at most the modules in
    place, an explicit row as PyPSA writes it: one where the build is not
    modular, and the fixed build's whole count of modules where it is
  dims: [scenario, snapshot, link]
  where: Link_committable AND NOT (Link_p_nom_extendable AND Link_p_nom_mod > 0) AND Link_active
  expression: Link_shut_down <= Link_modules_installed
```

```math
\mathit{dn}^{f}_{\xi,t,l} \le \mathrm{N}^{f,\mathrm{fix}}_{\xi,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \neg \left( \mathrm{ext}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-status-p_nom-variable-upper`

`Link_status_p_nom_variable_upper`

```yaml
Link_status_p_nom_variable_upper:
  description: "`Link-status-p_nom-variable-upper` — a modular link is on only where a module is built"
  dims: [scenario, snapshot, link]
  where: Link_committable AND Link_p_nom_extendable AND Link_p_nom_mod > 0 AND Link_active
  expression: Link_status <= Link_n_mod
```

```math
u^{f}_{\xi,t,l} \le N^{f}_{l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-start_up-p_nom-variable-upper`

`Link_start_up_p_nom_variable_upper`

```yaml
Link_start_up_p_nom_variable_upper:
  description: "`Link-start_up-p_nom-variable-upper` — a modular link starts only where a module is built"
  dims: [scenario, snapshot, link]
  where: Link_committable AND Link_p_nom_extendable AND Link_p_nom_mod > 0 AND Link_active
  expression: Link_start_up <= Link_n_mod
```

```math
\mathit{up}^{f}_{\xi,t,l} \le N^{f}_{l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-shut_down-p_nom-variable-upper`

`Link_shut_down_p_nom_variable_upper`

```yaml
Link_shut_down_p_nom_variable_upper:
  description: "`Link-shut_down-p_nom-variable-upper` — a modular link stops only where a module is built"
  dims: [scenario, snapshot, link]
  where: Link_committable AND Link_p_nom_extendable AND Link_p_nom_mod > 0 AND Link_active
  expression: Link_shut_down <= Link_n_mod
```

```math
\mathit{dn}^{f}_{\xi,t,l} \le N^{f}_{l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-maint-event-count`

`Link_maint_event_count`

```yaml
Link_maint_event_count:
  description: "`Link-maint-event-count` — a maintainable link holds its number of maintenance events over the horizon"
  dims: [scenario, link]
  where: Link_maintainable
  expression: sum(Link_maintenance_start, over=snapshot) == Link_maintenance_events
```

```math
\sum_{t \in \mathcal{T}} \mu^{f,\mathrm{up}}_{\xi,t,l} = \mathrm{n}^{f,\mathrm{mnt}}_{\xi,l} \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l}
```

### `Link-maint-window`

`Link_maint_window`

```yaml
Link_maint_window:
  description: >-
    `Link-maint-window` — a link is in maintenance exactly where an event it
    started covers the snapshot; two events do not overlap, since the
    maintenance status is at most one
  dims: [scenario, snapshot, link]
  where: Link_maintainable AND Link_active
  expression: Link_maintenance == sum(Link_maintenance_start, by=Link_maintenance_cover, over=start, into=covered)
```

```math
\mu^{f}_{\xi,t,l} = \sum_{t' \in \mathcal{T} \,:\, \left( \xi,\ l,\ t',\ t \right) \in \mathrm{Link\_maintenance\_cover}} \mu^{f,\mathrm{up}}_{\xi,t',l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-maint-start-horizon`

`Link_maint_start_horizon`

```yaml
Link_maint_start_horizon:
  description: "`Link-maint-start-horizon` — no event starts where it could not run its whole duration"
  dims: [scenario, snapshot, link]
  where: Link_maintainable AND Link_active AND Link_maintenance_start_blocked
  expression: Link_maintenance_start == 0
```

```math
\mu^{f,\mathrm{up}}_{\xi,t,l} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l} \wedge \mathrm{blk}^{f}_{\xi,t,l}
```

### `Link-maintcap_upper`

`Link_maintcap_upper`

```yaml
Link_maintcap_upper:
  description: >-
    `Link-maintcap_upper` — the build taken off is at most the chosen build in
    maintenance, and at most the build less its floor out of it
  dims: [scenario, snapshot, link]
  where: Link_maintainable AND Link_p_nom_extendable AND NOT (Link_committable AND Link_p_nom_mod > 0) AND Link_active
  expression: Link_maintenance_capacity <= Link_p_nom_ext - Link_p_nom_min * (1 - Link_maintenance)
```

```math
\mu^{f,\mathrm{nom}}_{\xi,t,l} \le F_{l} - \underline{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} \cdot \left( 1 - \mu^{f}_{\xi,t,l} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{com}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-maintcap_upper_nommax`

`Link_maintcap_upper_nommax`

```yaml
Link_maintcap_upper_nommax:
  description: "`Link-maintcap_upper_nommax` — out of maintenance, no build is taken off"
  dims: [scenario, snapshot, link]
  where: Link_maintainable AND Link_p_nom_extendable AND NOT (Link_committable AND Link_p_nom_mod > 0) AND Link_active
  expression: Link_maintenance_capacity <= Link_p_nom_max * Link_maintenance
```

```math
\mu^{f,\mathrm{nom}}_{\xi,t,l} \le \overline{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} \cdot \mu^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{com}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-maintcap_lower_nommax`

`Link_maintcap_lower_nommax`

```yaml
Link_maintcap_lower_nommax:
  description: "`Link-maintcap_lower_nommax` — in maintenance, the whole chosen build is taken off"
  dims: [scenario, snapshot, link]
  where: Link_maintainable AND Link_p_nom_extendable AND NOT (Link_committable AND Link_p_nom_mod > 0) AND Link_active
  expression: Link_maintenance_capacity >= Link_p_nom_ext - Link_p_nom_max * (1 - Link_maintenance)
```

```math
\mu^{f,\mathrm{nom}}_{\xi,t,l} \ge F_{l} - \overline{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} \cdot \left( 1 - \mu^{f}_{\xi,t,l} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{com}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-maintcap_lower_nommin`

`Link_maintcap_lower_nommin`

```yaml
Link_maintcap_lower_nommin:
  description: "`Link-maintcap_lower_nommin` — in maintenance, at least the floor of the build is taken off"
  dims: [scenario, snapshot, link]
  where: Link_maintainable AND Link_p_nom_extendable AND NOT (Link_committable AND Link_p_nom_mod > 0) AND Link_active AND Link_p_nom_min > 0
  expression: Link_maintenance_capacity >= Link_p_nom_min * Link_maintenance
```

```math
\mu^{f,\mathrm{nom}}_{\xi,t,l} \ge \underline{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} \cdot \mu^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{com}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \mathrm{on}^{f}_{t,l} \wedge \underline{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} > 0
```

### `Link-maint-status-le-status`

`Link_maint_status_le_status`

```yaml
Link_maint_status_le_status:
  description: "`Link-maint-status-le-status` — the status in maintenance is at most the status"
  dims: [scenario, snapshot, link]
  where: Link_maintainable AND Link_committable AND NOT Link_p_nom_extendable AND Link_active
  expression: Link_maintenance_status <= Link_status
```

```math
\mu^{f,u}_{\xi,t,l} \le u^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{com}^{f}_{l} \wedge \neg \mathrm{ext}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-maint-status-le-maint`

`Link_maint_status_le_maint`

```yaml
Link_maint_status_le_maint:
  description: "`Link-maint-status-le-maint` — out of maintenance, the status in maintenance is zero"
  dims: [scenario, snapshot, link]
  where: Link_maintainable AND Link_committable AND NOT Link_p_nom_extendable AND Link_active
  expression: Link_maintenance_status <= Link_maintenance
```

```math
\mu^{f,u}_{\xi,t,l} \le \mu^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{com}^{f}_{l} \wedge \neg \mathrm{ext}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-maint-status-lb`

`Link_maint_status_lb`

```yaml
Link_maint_status_lb:
  description: "`Link-maint-status-lb` — on and in maintenance, the status in maintenance is one"
  dims: [scenario, snapshot, link]
  where: Link_maintainable AND Link_committable AND NOT Link_p_nom_extendable AND Link_active
  expression: Link_maintenance_status >= Link_status + Link_maintenance - 1
```

```math
\mu^{f,u}_{\xi,t,l} \ge u^{f}_{\xi,t,l} + \mu^{f}_{\xi,t,l} - 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{com}^{f}_{l} \wedge \neg \mathrm{ext}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-maint-modstatus-le-status`

`Link_maint_modstatus_le_status`

```yaml
Link_maint_modstatus_le_status:
  description: "`Link-maint-modstatus-le-status` — the modules on in maintenance are at most the modules on"
  dims: [scenario, snapshot, link]
  where: Link_maintainable AND Link_committable AND Link_p_nom_mod > 0 AND Link_active
  expression: Link_maintenance_status <= Link_status
```

```math
\mu^{f,u}_{\xi,t,l} \le u^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{com}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-maint-modstatus-le-maint`

`Link_maint_modstatus_le_maint`

```yaml
Link_maint_modstatus_le_maint:
  description: >-
    `Link-maint-modstatus-le-maint` — out of maintenance, no module is on in
    maintenance; in it, at most the modules the build cap holds
  dims: [scenario, snapshot, link]
  where: Link_maintainable AND Link_committable AND Link_p_nom_mod > 0 AND Link_active
  expression: Link_maintenance_status <= Link_p_nom_max / Link_p_nom_mod * Link_maintenance
```

```math
\mu^{f,u}_{\xi,t,l} \le \frac{\overline{\mathrm{f}}^{\mathrm{nom}}_{\xi,l}}{\mathrm{f}^{\mathrm{mod}}_{l}} \cdot \mu^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{com}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-maint-modstatus-lb`

`Link_maint_modstatus_lb`

```yaml
Link_maint_modstatus_lb:
  description: "`Link-maint-modstatus-lb` — in maintenance, every module on is on in maintenance"
  dims: [scenario, snapshot, link]
  where: Link_maintainable AND Link_committable AND Link_p_nom_mod > 0 AND Link_active
  expression: Link_maintenance_status >= Link_status - Link_p_nom_max / Link_p_nom_mod * (1 - Link_maintenance)
```

```math
\mu^{f,u}_{\xi,t,l} \ge u^{f}_{\xi,t,l} - \frac{\overline{\mathrm{f}}^{\mathrm{nom}}_{\xi,l}}{\mathrm{f}^{\mathrm{mod}}_{l}} \cdot \left( 1 - \mu^{f}_{\xi,t,l} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{com}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \wedge \mathrm{on}^{f}_{t,l}
```

### `Process-com-p-lower`

`Process_com_p_lower`

```yaml
Process_com_p_lower:
  description: "`Process-com-p-lower` — a committed process runs at least its minimum; off, at least nothing"
  dims: [scenario, snapshot, process]
  where: Process_committable AND not Process_p_nom_extendable AND Process_active
  expression: Process_p >= Process_p_min_pu * Process_p_nom * (Process_status - Process_maintenance_pu * Process_maintenance_status)
```

```math
z_{\xi,t,j} \ge \underline{\mathrm{z}}_{\xi,t,j} \cdot \mathrm{z}^{\mathrm{nom}}_{\xi,j} \cdot \left( u^{z}_{\xi,t,j} - \gamma^{z}_{\xi,j} \cdot \mu^{z,u}_{\xi,t,j} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \neg \mathrm{ext}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-com-p-upper`

`Process_com_p_upper`

```yaml
Process_com_p_upper:
  description: "`Process-com-p-upper` — a committed process runs at most what is available; off, at most nothing"
  dims: [scenario, snapshot, process]
  where: Process_committable AND not Process_p_nom_extendable AND Process_active
  expression: Process_p <= Process_p_max_pu * Process_p_nom * (Process_status - Process_maintenance_pu * Process_maintenance_status)
```

```math
z_{\xi,t,j} \le \overline{\mathrm{z}}_{\xi,t,j} \cdot \mathrm{z}^{\mathrm{nom}}_{\xi,j} \cdot \left( u^{z}_{\xi,t,j} - \gamma^{z}_{\xi,j} \cdot \mu^{z,u}_{\xi,t,j} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \neg \mathrm{ext}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-com-transition-start-up`

`Process_com_transition_start_up`

```yaml
Process_com_transition_start_up:
  description: "`Process-com-transition-start-up` — turning on is a start, counted against the state the process carried into the snapshot"
  dims: [scenario, snapshot, process]
  where: Process_committable AND Process_active
  expression: Process_start_up >= Process_status - Process_previous_status
```

```math
\mathit{up}^{z}_{\xi,t,j} \ge u^{z}_{\xi,t,j} - \overleftarrow{u}^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-com-transition-shut-down`

`Process_com_transition_shut_down`

```yaml
Process_com_transition_shut_down:
  description: "`Process-com-transition-shut-down` — turning off is a stop, counted against the state the process carried into the snapshot"
  dims: [scenario, snapshot, process]
  where: Process_committable AND Process_active
  expression: Process_shut_down >= Process_previous_status - Process_status
```

```math
\mathit{dn}^{z}_{\xi,t,j} \ge \overleftarrow{u}^{z}_{\xi,t,j} - u^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-com-up-time`

`Process_com_up_time`

```yaml
Process_com_up_time:
  description: >-
    `Process-com-up-time` — a process started within its own minimum up time
    is still on. The first snapshot's share of the window is the brought-in
    up time's, which the must-stay-up mask carries
  dims: [scenario, snapshot, process]
  where: Process_committable AND Process_min_up_time > 0 AND position(snapshot) > 0 AND Process_active
  expression: sum_back(Process_start_up, along=snapshot, window=Process_min_up_time) <= Process_status
```

```math
\sum_{t' \in \mathcal{T} \,:\, 0 \le t - t' < \mathrm{UT}^{z}} \mathit{up}^{z}_{\xi,t',j} \le u^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{UT}^{z}_{\xi,j} > 0 \wedge \mathrm{pos}(t) > 0 \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-com-down-time`

`Process_com_down_time`

```yaml
Process_com_down_time:
  description: >-
    `Process-com-down-time` — a process stopped within its own minimum down
    time is still off. The first snapshot's share of the window is the
    brought-in down time's, which the must-stay-down mask carries
  dims: [scenario, snapshot, process]
  where: Process_committable AND Process_min_down_time > 0 AND position(snapshot) > 0 AND Process_active
  expression: sum_back(Process_shut_down, along=snapshot, window=Process_min_down_time) <= 1 - Process_status
```

```math
\sum_{t' \in \mathcal{T} \,:\, 0 \le t - t' < \mathrm{DT}^{z}} \mathit{dn}^{z}_{\xi,t',j} \le 1 - u^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{DT}^{z}_{\xi,j} > 0 \wedge \mathrm{pos}(t) > 0 \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-com-status-min_up_time_must_stay_up`

`Process_com_status_must_stay_up`

```yaml
Process_com_status_must_stay_up:
  description: "`Process-com-status-min_up_time_must_stay_up` — a process still serving the up time it brought in stays on"
  dims: [scenario, snapshot, process]
  where: Process_committable AND Process_must_stay_up AND Process_active
  expression: Process_status == 1
```

```math
u^{z}_{\xi,t,j} = 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{hold}^{z}_{\xi,t,j} \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-com-status-min_down_time_must_stay_up`

`Process_com_status_must_stay_down`

```yaml
Process_com_status_must_stay_down:
  description: >-
    `Process-com-status-min_down_time_must_stay_up` — a process still serving
    the down time it brought in stays off; PyPSA names the row `_must_stay_up`
  dims: [scenario, snapshot, process]
  where: Process_committable AND Process_must_stay_down AND Process_active
  expression: Process_status == 0
```

```math
u^{z}_{\xi,t,j} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{rest}^{z}_{\xi,t,j} \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-p-ramp_limit_up-run-bigM`

`Process_p_ramp_limit_up_run_big_m`

```yaml
Process_p_ramp_limit_up_run_big_m:
  description: >-
    `Process-p-ramp_limit_up-run-bigM` — a committed extendable process
    raises internal power no faster than its limit of the chosen build; the big M
    releases the row in the snapshot it turns on
  dims: [scenario, snapshot, process]
  where: >-
    Process_committable AND Process_p_nom_extendable AND NOT (Process_p_nom_mod > 0)
    AND (Process_ramp_limit_up OR Process_ramp_limit_start_up)
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Process_status_initial == 0 OR Process_p_init)))
    AND Process_active
  expression: >-
    Process_p - Process_previous_p <=
    Process_ramp_up_rate * Process_p_nom_ext
    + Process_big_m - Process_big_m * Process_previous_status
```

```math
z_{\xi,t,j} - \overleftarrow{z}_{\xi,t,j} \le \widetilde{\mathrm{ru}}^{z}_{\xi,t,j} \cdot Z_{j} + \mathrm{M}^{z}_{\xi,j} - \mathrm{M}^{z}_{\xi,j} \cdot \overleftarrow{u}^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \left( \mathrm{ru}^{z}_{\xi,t,j} \text{ is defined} \vee \mathrm{ru}^{z,\mathrm{up}}_{\xi,j} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{z,0}_{\xi,j} = 0 \vee \mathrm{z}^{0}_{\xi,j} \text{ is defined} \right) \right) \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-p-ramp_limit_up-start-bigM`

`Process_p_ramp_limit_up_start_big_m`

```yaml
Process_p_ramp_limit_up_start_big_m:
  description: >-
    `Process-p-ramp_limit_up-start-bigM` — in the snapshot it turns on, a
    committed extendable process ramps no further than its start-up ramp of
    the chosen build; the big M releases the row everywhere else
  dims: [scenario, snapshot, process]
  where: >-
    Process_committable AND Process_p_nom_extendable AND NOT (Process_p_nom_mod > 0)
    AND (Process_ramp_limit_up OR Process_ramp_limit_start_up)
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Process_status_initial == 0 OR Process_p_init)))
    AND Process_active
  expression: >-
    Process_p - Process_previous_p <=
    Process_start_up_rate * Process_p_nom_ext
    + Process_big_m - Process_big_m * Process_start_up
```

```math
z_{\xi,t,j} - \overleftarrow{z}_{\xi,t,j} \le \widetilde{\mathrm{ru}}^{z,\mathrm{up}}_{\xi,j} \cdot Z_{j} + \mathrm{M}^{z}_{\xi,j} - \mathrm{M}^{z}_{\xi,j} \cdot \mathit{up}^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \left( \mathrm{ru}^{z}_{\xi,t,j} \text{ is defined} \vee \mathrm{ru}^{z,\mathrm{up}}_{\xi,j} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{z,0}_{\xi,j} = 0 \vee \mathrm{z}^{0}_{\xi,j} \text{ is defined} \right) \right) \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-p-ramp_limit_down-run-bigM`

`Process_p_ramp_limit_down_run_big_m`

```yaml
Process_p_ramp_limit_down_run_big_m:
  description: >-
    `Process-p-ramp_limit_down-run-bigM` — a committed extendable process
    lowers internal power no faster than its limit of the chosen build; the big M
    releases the row in the snapshot it turns off
  dims: [scenario, snapshot, process]
  where: >-
    Process_committable AND Process_p_nom_extendable AND NOT (Process_p_nom_mod > 0)
    AND (Process_ramp_limit_down OR Process_ramp_limit_shut_down)
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Process_status_initial == 0 OR Process_p_init)))
    AND Process_active
  expression: >-
    Process_previous_p - Process_p <=
    Process_ramp_down_rate * Process_p_nom_ext
    + Process_big_m - Process_big_m * Process_status
```

```math
\overleftarrow{z}_{\xi,t,j} - z_{\xi,t,j} \le \widetilde{\mathrm{rd}}^{z}_{\xi,t,j} \cdot Z_{j} + \mathrm{M}^{z}_{\xi,j} - \mathrm{M}^{z}_{\xi,j} \cdot u^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \left( \mathrm{rd}^{z}_{\xi,t,j} \text{ is defined} \vee \mathrm{rd}^{z,\mathrm{dn}}_{\xi,j} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{z,0}_{\xi,j} = 0 \vee \mathrm{z}^{0}_{\xi,j} \text{ is defined} \right) \right) \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-p-ramp_limit_down-shut-bigM`

`Process_p_ramp_limit_down_shut_big_m`

```yaml
Process_p_ramp_limit_down_shut_big_m:
  description: >-
    `Process-p-ramp_limit_down-shut-bigM` — in the snapshot it turns off,
    a committed extendable process ramps no further than its shut-down ramp of
    the chosen build; the big M releases the row everywhere else
  dims: [scenario, snapshot, process]
  where: >-
    Process_committable AND Process_p_nom_extendable AND NOT (Process_p_nom_mod > 0)
    AND (Process_ramp_limit_down OR Process_ramp_limit_shut_down)
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Process_status_initial == 0 OR Process_p_init)))
    AND Process_active
  expression: >-
    Process_previous_p - Process_p <=
    Process_shut_down_rate * Process_p_nom_ext
    + Process_big_m - Process_big_m * Process_shut_down
```

```math
\overleftarrow{z}_{\xi,t,j} - z_{\xi,t,j} \le \widetilde{\mathrm{rd}}^{z,\mathrm{dn}}_{\xi,j} \cdot Z_{j} + \mathrm{M}^{z}_{\xi,j} - \mathrm{M}^{z}_{\xi,j} \cdot \mathit{dn}^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \left( \mathrm{rd}^{z}_{\xi,t,j} \text{ is defined} \vee \mathrm{rd}^{z,\mathrm{dn}}_{\xi,j} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{z,0}_{\xi,j} = 0 \vee \mathrm{z}^{0}_{\xi,j} \text{ is defined} \right) \right) \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-p_nom_modularity`

`Process_p_nom_modularity`

```yaml
Process_p_nom_modularity:
  description: "`Process-p_nom_modularity` — the chosen build is a whole number of modules"
  dims: [process]
  where: Process_p_nom_extendable AND Process_p_nom_mod > 0
  expression: Process_p_nom_ext == Process_p_nom_mod * Process_n_mod
```

```math
Z_{j} = \mathrm{z}^{\mathrm{mod}}_{j} \cdot N^{z}_{j} \qquad \forall\, j \in \mathcal{J} \,:\, \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0
```

### `Process-com-ext-p-upper-cap`

`Process_com_ext_p_upper_cap`

```yaml
Process_com_ext_p_upper_cap:
  description: >-
    `Process-com-ext-p-upper-cap` — a committed extendable process runs
    at most what is available of the chosen build, whatever its status
  dims: [scenario, snapshot, process]
  where: Process_committable AND Process_p_nom_extendable AND NOT (Process_p_nom_mod > 0) AND Process_active
  expression: Process_p <= Process_p_max_pu * (Process_p_nom_ext - Process_maintenance_pu * Process_maintenance_capacity)
```

```math
z_{\xi,t,j} \le \overline{\mathrm{z}}_{\xi,t,j} \cdot \left( Z_{j} - \gamma^{z}_{\xi,j} \cdot \mu^{z,\mathrm{nom}}_{\xi,t,j} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-com-ext-p-upper-bigM`

`Process_com_ext_p_upper_big_m`

```yaml
Process_com_ext_p_upper_big_m:
  description: "`Process-com-ext-p-upper-bigM` — off, a process does not run; on, the big M is no bound"
  dims: [scenario, snapshot, process]
  where: Process_committable AND Process_p_nom_extendable AND NOT (Process_p_nom_mod > 0) AND Process_active
  expression: Process_p <= Process_big_m * Process_status
```

```math
z_{\xi,t,j} \le \mathrm{M}^{z}_{\xi,j} \cdot u^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-com-ext-p-lower`

`Process_com_ext_p_lower`

```yaml
Process_com_ext_p_lower:
  description: >-
    `Process-com-ext-p-lower` — a committed extendable process runs at
    least its minimum of the chosen build; off, the big M releases the row
  dims: [scenario, snapshot, process]
  where: Process_committable AND Process_p_nom_extendable AND NOT (Process_p_nom_mod > 0) AND Process_active
  expression: >-
    Process_p >=
    Process_p_min_pu * (Process_p_nom_ext - Process_maintenance_pu * Process_maintenance_capacity)
    + Process_big_m * Process_status - Process_big_m
```

```math
z_{\xi,t,j} \ge \underline{\mathrm{z}}_{\xi,t,j} \cdot \left( Z_{j} - \gamma^{z}_{\xi,j} \cdot \mu^{z,\mathrm{nom}}_{\xi,t,j} \right) + \mathrm{M}^{z}_{\xi,j} \cdot u^{z}_{\xi,t,j} - \mathrm{M}^{z}_{\xi,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-com-ext-p-lower-nonneg`

`Process_com_ext_p_lower_nonneg`

```yaml
Process_com_ext_p_lower_nonneg:
  description: >-
    `Process-com-ext-p-lower-nonneg` — where no minimum-per-unit is
    negative, internal power is also plainly non-negative, a row the big-M lower
    cannot assert while the process is off
  dims: [scenario, snapshot, process]
  where: >-
    Process_committable AND Process_p_nom_extendable
    AND Process_p_min_pu_nonneg AND NOT (Process_p_nom_mod > 0) AND Process_active
  expression: Process_p >= 0
```

```math
z_{\xi,t,j} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \mathrm{nonneg}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-com-mod-p-lower`

`Process_com_mod_p_lower`

```yaml
Process_com_mod_p_lower:
  description: >-
    `Process-com-mod-p-lower` — a committed modular process runs at least
    its minimum of one module, whether the build is fixed or a decision
  dims: [scenario, snapshot, process]
  where: Process_committable AND Process_p_nom_mod > 0 AND Process_active
  expression: Process_p >= Process_p_min_pu * Process_p_nom_mod * (Process_status - Process_maintenance_pu * Process_maintenance_status)
```

```math
z_{\xi,t,j} \ge \underline{\mathrm{z}}_{\xi,t,j} \cdot \mathrm{z}^{\mathrm{mod}}_{j} \cdot \left( u^{z}_{\xi,t,j} - \gamma^{z}_{\xi,j} \cdot \mu^{z,u}_{\xi,t,j} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-com-mod-p-upper`

`Process_com_mod_p_upper`

```yaml
Process_com_mod_p_upper:
  description: >-
    `Process-com-mod-p-upper` — a committed modular process runs at most
    one module's share, whether the build is fixed or a decision
  dims: [scenario, snapshot, process]
  where: Process_committable AND Process_p_nom_mod > 0 AND Process_active
  expression: Process_p <= Process_p_max_pu * Process_p_nom_mod * (Process_status - Process_maintenance_pu * Process_maintenance_status)
```

```math
z_{\xi,t,j} \le \overline{\mathrm{z}}_{\xi,t,j} \cdot \mathrm{z}^{\mathrm{mod}}_{j} \cdot \left( u^{z}_{\xi,t,j} - \gamma^{z}_{\xi,j} \cdot \mu^{z,u}_{\xi,t,j} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-status-p-fixed-upper`

`Process_status_p_fixed_upper`

```yaml
Process_status_p_fixed_upper:
  description: >-
    `Process-status-p-fixed-upper` — a status is at most the modules in
    place, an explicit row as PyPSA writes it: one where the build is not
    modular, and the fixed build's whole count of modules where it is
  dims: [scenario, snapshot, process]
  where: Process_committable AND NOT (Process_p_nom_extendable AND Process_p_nom_mod > 0) AND Process_active
  expression: Process_status <= Process_modules_installed
```

```math
u^{z}_{\xi,t,j} \le \mathrm{N}^{z,\mathrm{fix}}_{\xi,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \neg \left( \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-start_up-p-fixed-upper`

`Process_start_up_p_fixed_upper`

```yaml
Process_start_up_p_fixed_upper:
  description: >-
    `Process-start_up-p-fixed-upper` — a start is at most the modules in
    place, an explicit row as PyPSA writes it: one where the build is not
    modular, and the fixed build's whole count of modules where it is
  dims: [scenario, snapshot, process]
  where: Process_committable AND NOT (Process_p_nom_extendable AND Process_p_nom_mod > 0) AND Process_active
  expression: Process_start_up <= Process_modules_installed
```

```math
\mathit{up}^{z}_{\xi,t,j} \le \mathrm{N}^{z,\mathrm{fix}}_{\xi,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \neg \left( \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-shut_down-p-fixed-upper`

`Process_shut_down_p_fixed_upper`

```yaml
Process_shut_down_p_fixed_upper:
  description: >-
    `Process-shut_down-p-fixed-upper` — a stop is at most the modules in
    place, an explicit row as PyPSA writes it: one where the build is not
    modular, and the fixed build's whole count of modules where it is
  dims: [scenario, snapshot, process]
  where: Process_committable AND NOT (Process_p_nom_extendable AND Process_p_nom_mod > 0) AND Process_active
  expression: Process_shut_down <= Process_modules_installed
```

```math
\mathit{dn}^{z}_{\xi,t,j} \le \mathrm{N}^{z,\mathrm{fix}}_{\xi,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \neg \left( \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-status-p_nom-variable-upper`

`Process_status_p_nom_variable_upper`

```yaml
Process_status_p_nom_variable_upper:
  description: "`Process-status-p_nom-variable-upper` — a modular process is on only where a module is built"
  dims: [scenario, snapshot, process]
  where: Process_committable AND Process_p_nom_extendable AND Process_p_nom_mod > 0 AND Process_active
  expression: Process_status <= Process_n_mod
```

```math
u^{z}_{\xi,t,j} \le N^{z}_{j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-start_up-p_nom-variable-upper`

`Process_start_up_p_nom_variable_upper`

```yaml
Process_start_up_p_nom_variable_upper:
  description: "`Process-start_up-p_nom-variable-upper` — a modular process starts only where a module is built"
  dims: [scenario, snapshot, process]
  where: Process_committable AND Process_p_nom_extendable AND Process_p_nom_mod > 0 AND Process_active
  expression: Process_start_up <= Process_n_mod
```

```math
\mathit{up}^{z}_{\xi,t,j} \le N^{z}_{j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-shut_down-p_nom-variable-upper`

`Process_shut_down_p_nom_variable_upper`

```yaml
Process_shut_down_p_nom_variable_upper:
  description: "`Process-shut_down-p_nom-variable-upper` — a modular process stops only where a module is built"
  dims: [scenario, snapshot, process]
  where: Process_committable AND Process_p_nom_extendable AND Process_p_nom_mod > 0 AND Process_active
  expression: Process_shut_down <= Process_n_mod
```

```math
\mathit{dn}^{z}_{\xi,t,j} \le N^{z}_{j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-maint-event-count`

`Process_maint_event_count`

```yaml
Process_maint_event_count:
  description: "`Process-maint-event-count` — a maintainable process holds its number of maintenance events over the horizon"
  dims: [scenario, process]
  where: Process_maintainable
  expression: sum(Process_maintenance_start, over=snapshot) == Process_maintenance_events
```

```math
\sum_{t \in \mathcal{T}} \mu^{z,\mathrm{up}}_{\xi,t,j} = \mathrm{n}^{z,\mathrm{mnt}}_{\xi,j} \qquad \forall\, \xi \in \Xi,\ j \in \mathcal{J} \,:\, \mathrm{mnt}^{z}_{j}
```

### `Process-maint-window`

`Process_maint_window`

```yaml
Process_maint_window:
  description: >-
    `Process-maint-window` — a process is in maintenance exactly where an event it
    started covers the snapshot; two events do not overlap, since the
    maintenance status is at most one
  dims: [scenario, snapshot, process]
  where: Process_maintainable AND Process_active
  expression: Process_maintenance == sum(Process_maintenance_start, by=Process_maintenance_cover, over=start, into=covered)
```

```math
\mu^{z}_{\xi,t,j} = \sum_{t' \in \mathcal{T} \,:\, \left( \xi,\ j,\ t',\ t \right) \in \mathrm{Process\_maintenance\_cover}} \mu^{z,\mathrm{up}}_{\xi,t',j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{mnt}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-maint-start-horizon`

`Process_maint_start_horizon`

```yaml
Process_maint_start_horizon:
  description: "`Process-maint-start-horizon` — no event starts where it could not run its whole duration"
  dims: [scenario, snapshot, process]
  where: Process_maintainable AND Process_active AND Process_maintenance_start_blocked
  expression: Process_maintenance_start == 0
```

```math
\mu^{z,\mathrm{up}}_{\xi,t,j} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{mnt}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j} \wedge \mathrm{blk}^{z}_{\xi,t,j}
```

### `Process-maintcap_upper`

`Process_maintcap_upper`

```yaml
Process_maintcap_upper:
  description: >-
    `Process-maintcap_upper` — the build taken off is at most the chosen build in
    maintenance, and at most the build less its floor out of it
  dims: [scenario, snapshot, process]
  where: Process_maintainable AND Process_p_nom_extendable AND NOT (Process_committable AND Process_p_nom_mod > 0) AND Process_active
  expression: Process_maintenance_capacity <= Process_p_nom_ext - Process_p_nom_min * (1 - Process_maintenance)
```

```math
\mu^{z,\mathrm{nom}}_{\xi,t,j} \le Z_{j} - \underline{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} \cdot \left( 1 - \mu^{z}_{\xi,t,j} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{mnt}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{com}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-maintcap_upper_nommax`

`Process_maintcap_upper_nommax`

```yaml
Process_maintcap_upper_nommax:
  description: "`Process-maintcap_upper_nommax` — out of maintenance, no build is taken off"
  dims: [scenario, snapshot, process]
  where: Process_maintainable AND Process_p_nom_extendable AND NOT (Process_committable AND Process_p_nom_mod > 0) AND Process_active
  expression: Process_maintenance_capacity <= Process_p_nom_max * Process_maintenance
```

```math
\mu^{z,\mathrm{nom}}_{\xi,t,j} \le \overline{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} \cdot \mu^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{mnt}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{com}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-maintcap_lower_nommax`

`Process_maintcap_lower_nommax`

```yaml
Process_maintcap_lower_nommax:
  description: "`Process-maintcap_lower_nommax` — in maintenance, the whole chosen build is taken off"
  dims: [scenario, snapshot, process]
  where: Process_maintainable AND Process_p_nom_extendable AND NOT (Process_committable AND Process_p_nom_mod > 0) AND Process_active
  expression: Process_maintenance_capacity >= Process_p_nom_ext - Process_p_nom_max * (1 - Process_maintenance)
```

```math
\mu^{z,\mathrm{nom}}_{\xi,t,j} \ge Z_{j} - \overline{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} \cdot \left( 1 - \mu^{z}_{\xi,t,j} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{mnt}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{com}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-maintcap_lower_nommin`

`Process_maintcap_lower_nommin`

```yaml
Process_maintcap_lower_nommin:
  description: "`Process-maintcap_lower_nommin` — in maintenance, at least the floor of the build is taken off"
  dims: [scenario, snapshot, process]
  where: Process_maintainable AND Process_p_nom_extendable AND NOT (Process_committable AND Process_p_nom_mod > 0) AND Process_active AND Process_p_nom_min > 0
  expression: Process_maintenance_capacity >= Process_p_nom_min * Process_maintenance
```

```math
\mu^{z,\mathrm{nom}}_{\xi,t,j} \ge \underline{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} \cdot \mu^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{mnt}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{com}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j} \wedge \underline{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} > 0
```

### `Process-maint-status-le-status`

`Process_maint_status_le_status`

```yaml
Process_maint_status_le_status:
  description: "`Process-maint-status-le-status` — the status in maintenance is at most the status"
  dims: [scenario, snapshot, process]
  where: Process_maintainable AND Process_committable AND NOT Process_p_nom_extendable AND Process_active
  expression: Process_maintenance_status <= Process_status
```

```math
\mu^{z,u}_{\xi,t,j} \le u^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{mnt}^{z}_{j} \wedge \mathrm{com}^{z}_{j} \wedge \neg \mathrm{ext}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-maint-status-le-maint`

`Process_maint_status_le_maint`

```yaml
Process_maint_status_le_maint:
  description: "`Process-maint-status-le-maint` — out of maintenance, the status in maintenance is zero"
  dims: [scenario, snapshot, process]
  where: Process_maintainable AND Process_committable AND NOT Process_p_nom_extendable AND Process_active
  expression: Process_maintenance_status <= Process_maintenance
```

```math
\mu^{z,u}_{\xi,t,j} \le \mu^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{mnt}^{z}_{j} \wedge \mathrm{com}^{z}_{j} \wedge \neg \mathrm{ext}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-maint-status-lb`

`Process_maint_status_lb`

```yaml
Process_maint_status_lb:
  description: "`Process-maint-status-lb` — on and in maintenance, the status in maintenance is one"
  dims: [scenario, snapshot, process]
  where: Process_maintainable AND Process_committable AND NOT Process_p_nom_extendable AND Process_active
  expression: Process_maintenance_status >= Process_status + Process_maintenance - 1
```

```math
\mu^{z,u}_{\xi,t,j} \ge u^{z}_{\xi,t,j} + \mu^{z}_{\xi,t,j} - 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{mnt}^{z}_{j} \wedge \mathrm{com}^{z}_{j} \wedge \neg \mathrm{ext}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-maint-modstatus-le-status`

`Process_maint_modstatus_le_status`

```yaml
Process_maint_modstatus_le_status:
  description: "`Process-maint-modstatus-le-status` — the modules on in maintenance are at most the modules on"
  dims: [scenario, snapshot, process]
  where: Process_maintainable AND Process_committable AND Process_p_nom_mod > 0 AND Process_active
  expression: Process_maintenance_status <= Process_status
```

```math
\mu^{z,u}_{\xi,t,j} \le u^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{mnt}^{z}_{j} \wedge \mathrm{com}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-maint-modstatus-le-maint`

`Process_maint_modstatus_le_maint`

```yaml
Process_maint_modstatus_le_maint:
  description: >-
    `Process-maint-modstatus-le-maint` — out of maintenance, no module is on in
    maintenance; in it, at most the modules the build cap holds
  dims: [scenario, snapshot, process]
  where: Process_maintainable AND Process_committable AND Process_p_nom_mod > 0 AND Process_active
  expression: Process_maintenance_status <= Process_p_nom_max / Process_p_nom_mod * Process_maintenance
```

```math
\mu^{z,u}_{\xi,t,j} \le \frac{\overline{\mathrm{z}}^{\mathrm{nom}}_{\xi,j}}{\mathrm{z}^{\mathrm{mod}}_{j}} \cdot \mu^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{mnt}^{z}_{j} \wedge \mathrm{com}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-maint-modstatus-lb`

`Process_maint_modstatus_lb`

```yaml
Process_maint_modstatus_lb:
  description: "`Process-maint-modstatus-lb` — in maintenance, every module on is on in maintenance"
  dims: [scenario, snapshot, process]
  where: Process_maintainable AND Process_committable AND Process_p_nom_mod > 0 AND Process_active
  expression: Process_maintenance_status >= Process_status - Process_p_nom_max / Process_p_nom_mod * (1 - Process_maintenance)
```

```math
\mu^{z,u}_{\xi,t,j} \ge u^{z}_{\xi,t,j} - \frac{\overline{\mathrm{z}}^{\mathrm{nom}}_{\xi,j}}{\mathrm{z}^{\mathrm{mod}}_{j}} \cdot \left( 1 - \mu^{z}_{\xi,t,j} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{mnt}^{z}_{j} \wedge \mathrm{com}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \wedge \mathrm{on}^{z}_{t,j}
```

### `Line-fix-s-lower`

`Line_fix_s_lower`

```yaml
Line_fix_s_lower:
  description: "`Line-fix-s-lower` — a fixed line carries at least the negative of its rating, the loss counted against it"
  dims: [scenario, snapshot, line]
  where: not Line_s_nom_extendable AND Line_active
  expression: Line_s - Line_loss >= -Line_s_max_pu * Line_s_nom
```

```math
s_{\xi,t,k} - \ell_{\xi,t,k} \ge -\overline{\mathrm{s}}_{\xi,t,k} \cdot \mathrm{s}^{\mathrm{nom}}_{\xi,k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K} \,:\, \neg \mathrm{ext}^{s}_{k} \wedge \mathrm{on}^{s}_{t,k}
```

### `Line-fix-s-upper`

`Line_fix_s_upper`

```yaml
Line_fix_s_upper:
  description: "`Line-fix-s-upper` — a fixed line carries at most its rating, the loss included"
  dims: [scenario, snapshot, line]
  where: not Line_s_nom_extendable AND Line_active
  expression: Line_s + Line_loss <= Line_s_max_pu * Line_s_nom
```

```math
s_{\xi,t,k} + \ell_{\xi,t,k} \le \overline{\mathrm{s}}_{\xi,t,k} \cdot \mathrm{s}^{\mathrm{nom}}_{\xi,k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K} \,:\, \neg \mathrm{ext}^{s}_{k} \wedge \mathrm{on}^{s}_{t,k}
```

### `Line-ext-s-lower`

`Line_ext_s_lower`

```yaml
Line_ext_s_lower:
  description: "`Line-ext-s-lower` — an extendable line carries at least the negative of its rating of the chosen build, the loss counted against it"
  dims: [scenario, snapshot, line]
  where: Line_s_nom_extendable AND Line_active
  expression: Line_s - Line_loss >= -Line_s_max_pu * Line_s_nom_ext
```

```math
s_{\xi,t,k} - \ell_{\xi,t,k} \ge -\overline{\mathrm{s}}_{\xi,t,k} \cdot S_{k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K} \,:\, \mathrm{ext}^{s}_{k} \wedge \mathrm{on}^{s}_{t,k}
```

### `Line-ext-s-upper`

`Line_ext_s_upper`

```yaml
Line_ext_s_upper:
  description: "`Line-ext-s-upper` — an extendable line carries at most its rating of the chosen build, the loss included"
  dims: [scenario, snapshot, line]
  where: Line_s_nom_extendable AND Line_active
  expression: Line_s + Line_loss <= Line_s_max_pu * Line_s_nom_ext
```

```math
s_{\xi,t,k} + \ell_{\xi,t,k} \le \overline{\mathrm{s}}_{\xi,t,k} \cdot S_{k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K} \,:\, \mathrm{ext}^{s}_{k} \wedge \mathrm{on}^{s}_{t,k}
```

### `Line-ext-s_nom-lower`

`Line_ext_s_nom_lower`

```yaml
Line_ext_s_nom_lower:
  description: "`Line-ext-s_nom-lower` — the chosen build is at least its floor in every scenario"
  dims: [scenario, line]
  where: Line_s_nom_extendable
  expression: Line_s_nom_ext >= Line_s_nom_min
```

```math
S_{k} \ge \underline{\mathrm{s}}^{\mathrm{nom}}_{\xi,k} \qquad \forall\, \xi \in \Xi,\ k \in \mathcal{K} \,:\, \mathrm{ext}^{s}_{k}
```

### `Line-ext-s_nom-upper`

`Line_ext_s_nom_upper`

```yaml
Line_ext_s_nom_upper:
  description: "`Line-ext-s_nom-upper` — the chosen build is at most its cap in every scenario; a cap of infinity is no row"
  dims: [scenario, line]
  where: Line_s_nom_extendable AND Line_s_nom_max
  expression: Line_s_nom_ext <= Line_s_nom_max
```

```math
S_{k} \le \overline{\mathrm{s}}^{\mathrm{nom}}_{\xi,k} \qquad \forall\, \xi \in \Xi,\ k \in \mathcal{K} \,:\, \mathrm{ext}^{s}_{k} \wedge \overline{\mathrm{s}}^{\mathrm{nom}}_{\xi,k} \text{ is defined}
```

### `Line-s_nom_set`

`Line_s_nom_set`

```yaml
Line_s_nom_set:
  description: "`Line-s_nom_set` — the chosen build pinned, wherever a value is given"
  dims: [scenario, line]
  where: Line_s_nom_extendable AND Line_s_nom_set
  expression: Line_s_nom_ext == Line_s_nom_set
```

```math
S_{k} = \mathrm{s}^{\mathrm{nom,set}}_{\xi,k} \qquad \forall\, \xi \in \Xi,\ k \in \mathcal{K} \,:\, \mathrm{ext}^{s}_{k} \wedge \mathrm{s}^{\mathrm{nom,set}}_{\xi,k} \text{ is defined}
```

### `Line-s_set`

`Line_s_set`

```yaml
Line_s_set:
  description: "`Line-s_set` — flow pinned to the given schedule, wherever one is given"
  dims: [scenario, snapshot, line]
  where: Line_s_set AND Line_active
  expression: Line_s == Line_s_set
```

```math
s_{\xi,t,k} = \mathrm{s}^{\mathrm{set}}_{\xi,t,k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K} \,:\, \mathrm{s}^{\mathrm{set}}_{\xi,t,k} \text{ is defined} \wedge \mathrm{on}^{s}_{t,k}
```

### `Line-loss_upper`

`Line_loss_upper`

```yaml
Line_loss_upper:
  description: "`Line-loss_upper` — a line dissipates at most the loss at its rating"
  dims: [scenario, snapshot, line]
  where: transmission_losses AND Line_active
  expression: Line_loss <= Line_loss_max
```

```math
\ell_{\xi,t,k} \le \overline{\ell}_{\xi,t,k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K} \,:\, \mathrm{lossy} \wedge \mathrm{on}^{s}_{t,k}
```

### `Line-loss_tangents-{k}-1`

`Line_loss_tangents_forward`

```yaml
Line_loss_tangents_forward:
  description: >-
    `Line-loss_tangents-{k}-1`, `Line-loss_secants-pos` — the loss sits above
    every cut to its curve for flow one way; PyPSA names one row per tangent
    `k`, or one row stacked over its `secant` axis, and this block states them
    all over the segment dimension
  dims: [scenario, snapshot, line, segment]
  where: transmission_losses AND Line_active
  expression: Line_loss + Line_loss_slope * Line_s >= Line_loss_offset
```

```math
\ell_{\xi,t,k} + \mathrm{a}_{\xi,t,k,b} \cdot s_{\xi,t,k} \ge \mathrm{b}_{\xi,t,k,b} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K},\ b \in \mathcal{B} \,:\, \mathrm{lossy} \wedge \mathrm{on}^{s}_{t,k}
```

### `Line-loss_tangents-{k}--1`

`Line_loss_tangents_reverse`

```yaml
Line_loss_tangents_reverse:
  description: >-
    `Line-loss_tangents-{k}--1`, `Line-loss_secants-neg` — the same fan
    mirrored, the loss depending on the flow's magnitude
  dims: [scenario, snapshot, line, segment]
  where: transmission_losses AND Line_active
  expression: Line_loss - Line_loss_slope * Line_s >= Line_loss_offset
```

```math
\ell_{\xi,t,k} - \mathrm{a}_{\xi,t,k,b} \cdot s_{\xi,t,k} \ge \mathrm{b}_{\xi,t,k,b} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K},\ b \in \mathcal{B} \,:\, \mathrm{lossy} \wedge \mathrm{on}^{s}_{t,k}
```

### `Transformer-fix-s-lower`

`Transformer_fix_s_lower`

```yaml
Transformer_fix_s_lower:
  description: "`Transformer-fix-s-lower` — a fixed transformer carries at least the negative of its rating, the loss counted against it"
  dims: [scenario, snapshot, transformer]
  where: not Transformer_s_nom_extendable AND Transformer_active
  expression: Transformer_s - Transformer_loss >= -Transformer_s_max_pu * Transformer_s_nom
```

```math
\sigma_{\xi,t,m} - \ell^{\sigma}_{\xi,t,m} \ge -\overline{\sigma}_{\xi,t,m} \cdot \sigma^{\mathrm{nom}}_{\xi,m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M} \,:\, \neg \mathrm{ext}^{\sigma}_{m} \wedge \mathrm{on}^{\sigma}_{t,m}
```

### `Transformer-fix-s-upper`

`Transformer_fix_s_upper`

```yaml
Transformer_fix_s_upper:
  description: "`Transformer-fix-s-upper` — a fixed transformer carries at most its rating, the loss included"
  dims: [scenario, snapshot, transformer]
  where: not Transformer_s_nom_extendable AND Transformer_active
  expression: Transformer_s + Transformer_loss <= Transformer_s_max_pu * Transformer_s_nom
```

```math
\sigma_{\xi,t,m} + \ell^{\sigma}_{\xi,t,m} \le \overline{\sigma}_{\xi,t,m} \cdot \sigma^{\mathrm{nom}}_{\xi,m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M} \,:\, \neg \mathrm{ext}^{\sigma}_{m} \wedge \mathrm{on}^{\sigma}_{t,m}
```

### `Transformer-ext-s-lower`

`Transformer_ext_s_lower`

```yaml
Transformer_ext_s_lower:
  description: "`Transformer-ext-s-lower` — an extendable transformer carries at least the negative of its rating of the chosen build, the loss counted against it"
  dims: [scenario, snapshot, transformer]
  where: Transformer_s_nom_extendable AND Transformer_active
  expression: Transformer_s - Transformer_loss >= -Transformer_s_max_pu * Transformer_s_nom_ext
```

```math
\sigma_{\xi,t,m} - \ell^{\sigma}_{\xi,t,m} \ge -\overline{\sigma}_{\xi,t,m} \cdot \Sigma_{m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M} \,:\, \mathrm{ext}^{\sigma}_{m} \wedge \mathrm{on}^{\sigma}_{t,m}
```

### `Transformer-ext-s-upper`

`Transformer_ext_s_upper`

```yaml
Transformer_ext_s_upper:
  description: "`Transformer-ext-s-upper` — an extendable transformer carries at most its rating of the chosen build, the loss included"
  dims: [scenario, snapshot, transformer]
  where: Transformer_s_nom_extendable AND Transformer_active
  expression: Transformer_s + Transformer_loss <= Transformer_s_max_pu * Transformer_s_nom_ext
```

```math
\sigma_{\xi,t,m} + \ell^{\sigma}_{\xi,t,m} \le \overline{\sigma}_{\xi,t,m} \cdot \Sigma_{m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M} \,:\, \mathrm{ext}^{\sigma}_{m} \wedge \mathrm{on}^{\sigma}_{t,m}
```

### `Transformer-ext-s_nom-lower`

`Transformer_ext_s_nom_lower`

```yaml
Transformer_ext_s_nom_lower:
  description: "`Transformer-ext-s_nom-lower` — the chosen build is at least its floor in every scenario"
  dims: [scenario, transformer]
  where: Transformer_s_nom_extendable
  expression: Transformer_s_nom_ext >= Transformer_s_nom_min
```

```math
\Sigma_{m} \ge \underline{\sigma}^{\mathrm{nom}}_{\xi,m} \qquad \forall\, \xi \in \Xi,\ m \in \mathcal{M} \,:\, \mathrm{ext}^{\sigma}_{m}
```

### `Transformer-ext-s_nom-upper`

`Transformer_ext_s_nom_upper`

```yaml
Transformer_ext_s_nom_upper:
  description: "`Transformer-ext-s_nom-upper` — the chosen build is at most its cap in every scenario; a cap of infinity is no row"
  dims: [scenario, transformer]
  where: Transformer_s_nom_extendable AND Transformer_s_nom_max
  expression: Transformer_s_nom_ext <= Transformer_s_nom_max
```

```math
\Sigma_{m} \le \overline{\sigma}^{\mathrm{nom}}_{\xi,m} \qquad \forall\, \xi \in \Xi,\ m \in \mathcal{M} \,:\, \mathrm{ext}^{\sigma}_{m} \wedge \overline{\sigma}^{\mathrm{nom}}_{\xi,m} \text{ is defined}
```

### `Transformer-s_nom_set`

`Transformer_s_nom_set`

```yaml
Transformer_s_nom_set:
  description: "`Transformer-s_nom_set` — the chosen build pinned, wherever a value is given"
  dims: [scenario, transformer]
  where: Transformer_s_nom_extendable AND Transformer_s_nom_set
  expression: Transformer_s_nom_ext == Transformer_s_nom_set
```

```math
\Sigma_{m} = \sigma^{\mathrm{nom,set}}_{\xi,m} \qquad \forall\, \xi \in \Xi,\ m \in \mathcal{M} \,:\, \mathrm{ext}^{\sigma}_{m} \wedge \sigma^{\mathrm{nom,set}}_{\xi,m} \text{ is defined}
```

### `Transformer-s_set`

`Transformer_s_set`

```yaml
Transformer_s_set:
  description: "`Transformer-s_set` — flow pinned to the given schedule, wherever one is given"
  dims: [scenario, snapshot, transformer]
  where: Transformer_s_set AND Transformer_active
  expression: Transformer_s == Transformer_s_set
```

```math
\sigma_{\xi,t,m} = \sigma^{\mathrm{set}}_{\xi,t,m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M} \,:\, \sigma^{\mathrm{set}}_{\xi,t,m} \text{ is defined} \wedge \mathrm{on}^{\sigma}_{t,m}
```

### `Transformer-loss_upper`

`Transformer_loss_upper`

```yaml
Transformer_loss_upper:
  description: "`Transformer-loss_upper` — a transformer dissipates at most the loss at its rating"
  dims: [scenario, snapshot, transformer]
  where: transmission_losses AND Transformer_active
  expression: Transformer_loss <= Transformer_loss_max
```

```math
\ell^{\sigma}_{\xi,t,m} \le \overline{\ell}^{\sigma}_{\xi,t,m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M} \,:\, \mathrm{lossy} \wedge \mathrm{on}^{\sigma}_{t,m}
```

### `Transformer-loss_tangents-{k}-1`

`Transformer_loss_tangents_forward`

```yaml
Transformer_loss_tangents_forward:
  description: >-
    `Transformer-loss_tangents-{k}-1`, `Transformer-loss_secants-pos` — the
    loss sits above every cut to its curve for flow one way, as a line's
    does, over the segment dimension
  dims: [scenario, snapshot, transformer, segment]
  where: transmission_losses AND Transformer_active
  expression: Transformer_loss + Transformer_loss_slope * Transformer_s >= Transformer_loss_offset
```

```math
\ell^{\sigma}_{\xi,t,m} + \mathrm{a}^{\sigma}_{\xi,t,m,b} \cdot \sigma_{\xi,t,m} \ge \mathrm{b}^{\sigma}_{\xi,t,m,b} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M},\ b \in \mathcal{B} \,:\, \mathrm{lossy} \wedge \mathrm{on}^{\sigma}_{t,m}
```

### `Transformer-loss_tangents-{k}--1`

`Transformer_loss_tangents_reverse`

```yaml
Transformer_loss_tangents_reverse:
  description: >-
    `Transformer-loss_tangents-{k}--1`, `Transformer-loss_secants-neg` — the
    same fan mirrored, the loss depending on the flow's magnitude
  dims: [scenario, snapshot, transformer, segment]
  where: transmission_losses AND Transformer_active
  expression: Transformer_loss - Transformer_loss_slope * Transformer_s >= Transformer_loss_offset
```

```math
\ell^{\sigma}_{\xi,t,m} - \mathrm{a}^{\sigma}_{\xi,t,m,b} \cdot \sigma_{\xi,t,m} \ge \mathrm{b}^{\sigma}_{\xi,t,m,b} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M},\ b \in \mathcal{B} \,:\, \mathrm{lossy} \wedge \mathrm{on}^{\sigma}_{t,m}
```

### `Line-fix-s-lower-security-for-{c}-outage-in-sub-network-{n}`

`Line_fix_s_lower_security`

```yaml
Line_fix_s_lower_security:
  description: >-
    `Line-fix-s-lower-security-for-{c}-outage-in-sub-network-{n}` —
    after any one outage, a fixed line carries at least the negative
    of its rating: its flow takes on its share of the outaged branch's
    flow. PyPSA names one row per outaged component `c` and
    sub-network `n`; this block states them all over the outage
    dimension
  dims: [scenario, snapshot, line, outage]
  where: not Line_s_nom_extendable AND Line_BODF
  expression: Line_s_monitored + Line_BODF * Outage_s >= -Line_s_max_pu * Line_s_nom
```

```math
\check{s}_{\xi,t,k} + \beta_{k,\kappa} \cdot \hat{s}_{\xi,t,\kappa} \ge -\overline{\mathrm{s}}_{\xi,t,k} \cdot \mathrm{s}^{\mathrm{nom}}_{\xi,k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K},\ \kappa \in \mathcal{K}^{\mathrm{out}} \,:\, \neg \mathrm{ext}^{s}_{k} \wedge \beta_{k,\kappa} \text{ is defined}
```

### `Line-fix-s-upper-security-for-{c}-outage-in-sub-network-{n}`

`Line_fix_s_upper_security`

```yaml
Line_fix_s_upper_security:
  description: >-
    `Line-fix-s-upper-security-for-{c}-outage-in-sub-network-{n}` —
    after any one outage, a fixed line carries at most its rating: its
    flow takes on its share of the outaged branch's flow. PyPSA names
    one row per outaged component `c` and sub-network `n`; this block
    states them all over the outage dimension
  dims: [scenario, snapshot, line, outage]
  where: not Line_s_nom_extendable AND Line_BODF
  expression: Line_s_monitored + Line_BODF * Outage_s <= Line_s_max_pu * Line_s_nom
```

```math
\check{s}_{\xi,t,k} + \beta_{k,\kappa} \cdot \hat{s}_{\xi,t,\kappa} \le \overline{\mathrm{s}}_{\xi,t,k} \cdot \mathrm{s}^{\mathrm{nom}}_{\xi,k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K},\ \kappa \in \mathcal{K}^{\mathrm{out}} \,:\, \neg \mathrm{ext}^{s}_{k} \wedge \beta_{k,\kappa} \text{ is defined}
```

### `Line-ext-s-lower-security-for-{c}-outage-in-sub-network-{n}`

`Line_ext_s_lower_security`

```yaml
Line_ext_s_lower_security:
  description: >-
    `Line-ext-s-lower-security-for-{c}-outage-in-sub-network-{n}` —
    after any one outage, an extendable line carries at least the
    negative of its rating of the chosen build: its flow takes on its
    share of the outaged branch's flow. PyPSA names one row per
    outaged component `c` and sub-network `n`; this block states them
    all over the outage dimension
  dims: [scenario, snapshot, line, outage]
  where: Line_s_nom_extendable AND Line_BODF
  expression: Line_s_monitored + Line_BODF * Outage_s >= -Line_s_max_pu * Line_s_nom_ext
```

```math
\check{s}_{\xi,t,k} + \beta_{k,\kappa} \cdot \hat{s}_{\xi,t,\kappa} \ge -\overline{\mathrm{s}}_{\xi,t,k} \cdot S_{k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K},\ \kappa \in \mathcal{K}^{\mathrm{out}} \,:\, \mathrm{ext}^{s}_{k} \wedge \beta_{k,\kappa} \text{ is defined}
```

### `Line-ext-s-upper-security-for-{c}-outage-in-sub-network-{n}`

`Line_ext_s_upper_security`

```yaml
Line_ext_s_upper_security:
  description: >-
    `Line-ext-s-upper-security-for-{c}-outage-in-sub-network-{n}` —
    after any one outage, an extendable line carries at most its rating
    of the chosen build: its flow takes on its share of the outaged
    branch's flow. PyPSA names one row per outaged component `c` and
    sub-network `n`; this block states them all over the outage
    dimension
  dims: [scenario, snapshot, line, outage]
  where: Line_s_nom_extendable AND Line_BODF
  expression: Line_s_monitored + Line_BODF * Outage_s <= Line_s_max_pu * Line_s_nom_ext
```

```math
\check{s}_{\xi,t,k} + \beta_{k,\kappa} \cdot \hat{s}_{\xi,t,\kappa} \le \overline{\mathrm{s}}_{\xi,t,k} \cdot S_{k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K},\ \kappa \in \mathcal{K}^{\mathrm{out}} \,:\, \mathrm{ext}^{s}_{k} \wedge \beta_{k,\kappa} \text{ is defined}
```

### `Transformer-fix-s-lower-security-for-{c}-outage-in-sub-network-{n}`

`Transformer_fix_s_lower_security`

```yaml
Transformer_fix_s_lower_security:
  description: >-
    `Transformer-fix-s-lower-security-for-{c}-outage-in-sub-network-{n}`
    — after any one outage, a fixed transformer carries at least the
    negative of its rating: its flow takes on its share of the outaged
    branch's flow. PyPSA names one row per outaged component `c` and
    sub-network `n`; this block states them all over the outage
    dimension
  dims: [scenario, snapshot, transformer, outage]
  where: not Transformer_s_nom_extendable AND Transformer_BODF
  expression: Transformer_s_monitored + Transformer_BODF * Outage_s >= -Transformer_s_max_pu * Transformer_s_nom
```

```math
\check{\sigma}_{\xi,t,m} + \beta^{\sigma}_{m,\kappa} \cdot \hat{s}_{\xi,t,\kappa} \ge -\overline{\sigma}_{\xi,t,m} \cdot \sigma^{\mathrm{nom}}_{\xi,m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M},\ \kappa \in \mathcal{K}^{\mathrm{out}} \,:\, \neg \mathrm{ext}^{\sigma}_{m} \wedge \beta^{\sigma}_{m,\kappa} \text{ is defined}
```

### `Transformer-fix-s-upper-security-for-{c}-outage-in-sub-network-{n}`

`Transformer_fix_s_upper_security`

```yaml
Transformer_fix_s_upper_security:
  description: >-
    `Transformer-fix-s-upper-security-for-{c}-outage-in-sub-network-{n}`
    — after any one outage, a fixed transformer carries at most its
    rating: its flow takes on its share of the outaged branch's flow.
    PyPSA names one row per outaged component `c` and sub-network `n`;
    this block states them all over the outage dimension
  dims: [scenario, snapshot, transformer, outage]
  where: not Transformer_s_nom_extendable AND Transformer_BODF
  expression: Transformer_s_monitored + Transformer_BODF * Outage_s <= Transformer_s_max_pu * Transformer_s_nom
```

```math
\check{\sigma}_{\xi,t,m} + \beta^{\sigma}_{m,\kappa} \cdot \hat{s}_{\xi,t,\kappa} \le \overline{\sigma}_{\xi,t,m} \cdot \sigma^{\mathrm{nom}}_{\xi,m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M},\ \kappa \in \mathcal{K}^{\mathrm{out}} \,:\, \neg \mathrm{ext}^{\sigma}_{m} \wedge \beta^{\sigma}_{m,\kappa} \text{ is defined}
```

### `Transformer-ext-s-lower-security-for-{c}-outage-in-sub-network-{n}`

`Transformer_ext_s_lower_security`

```yaml
Transformer_ext_s_lower_security:
  description: >-
    `Transformer-ext-s-lower-security-for-{c}-outage-in-sub-network-{n}`
    — after any one outage, an extendable transformer carries at least
    the negative of its rating of the chosen build: its flow takes on
    its share of the outaged branch's flow. PyPSA names one row per
    outaged component `c` and sub-network `n`; this block states them
    all over the outage dimension
  dims: [scenario, snapshot, transformer, outage]
  where: Transformer_s_nom_extendable AND Transformer_BODF
  expression: Transformer_s_monitored + Transformer_BODF * Outage_s >= -Transformer_s_max_pu * Transformer_s_nom_ext
```

```math
\check{\sigma}_{\xi,t,m} + \beta^{\sigma}_{m,\kappa} \cdot \hat{s}_{\xi,t,\kappa} \ge -\overline{\sigma}_{\xi,t,m} \cdot \Sigma_{m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M},\ \kappa \in \mathcal{K}^{\mathrm{out}} \,:\, \mathrm{ext}^{\sigma}_{m} \wedge \beta^{\sigma}_{m,\kappa} \text{ is defined}
```

### `Transformer-ext-s-upper-security-for-{c}-outage-in-sub-network-{n}`

`Transformer_ext_s_upper_security`

```yaml
Transformer_ext_s_upper_security:
  description: >-
    `Transformer-ext-s-upper-security-for-{c}-outage-in-sub-network-{n}`
    — after any one outage, an extendable transformer carries at most
    its rating of the chosen build: its flow takes on its share of the
    outaged branch's flow. PyPSA names one row per outaged component
    `c` and sub-network `n`; this block states them all over the
    outage dimension
  dims: [scenario, snapshot, transformer, outage]
  where: Transformer_s_nom_extendable AND Transformer_BODF
  expression: Transformer_s_monitored + Transformer_BODF * Outage_s <= Transformer_s_max_pu * Transformer_s_nom_ext
```

```math
\check{\sigma}_{\xi,t,m} + \beta^{\sigma}_{m,\kappa} \cdot \hat{s}_{\xi,t,\kappa} \le \overline{\sigma}_{\xi,t,m} \cdot \Sigma_{m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M},\ \kappa \in \mathcal{K}^{\mathrm{out}} \,:\, \mathrm{ext}^{\sigma}_{m} \wedge \beta^{\sigma}_{m,\kappa} \text{ is defined}
```

### `Kirchhoff-Voltage-Law`

`Kirchhoff_Voltage_Law`

```yaml
Kirchhoff_Voltage_Law:
  description: >-
    `Kirchhoff-Voltage-Law` — around every independent cycle the
    impedance-weighted flows sum to nothing, which is what makes the linear
    power flow physical rather than transport. A transformer's flow weighs its
    effective reactance, and its phase shift enters the cycle sum too: a
    constant where the shift is fixed, or the shift decision times its cycle
    weight where the shift is a phase-shifting transformer's to choose
  dims: [scenario, snapshot, cycle]
  expression: Cycle_angle_sum == 0
```

```math
\sum_{k \in \mathcal{K}} s_{\xi,t,k} \cdot \mathrm{x}_{k,c} + \sum_{m \in \mathcal{M}} \sigma_{\xi,t,m} \cdot \mathrm{x}^{\sigma}_{m,c} + \sum_{m \in \mathcal{M}} \vartheta_{m,c} + \sum_{m \in \mathcal{M}} \mathit{Transformer\_phase\_shift}_{\xi,t,m} \cdot \mathrm{Transformer\_phase\_shift\_cycle\_weight}_{m,c} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ c \in \mathcal{C}
```

### `Generator-p-ramp_limit_up`

`Generator_p_ramp_limit_up`

```yaml
Generator_p_ramp_limit_up:
  description: >-
    `Generator-p-ramp_limit_up` — a generator raises output no faster than
    its ramp limit of the build, and a committed one no further than its
    start-up ramp in the snapshot it turns on. A unit that came into the
    horizon running carries a row at the first snapshot only where its
    `p_init` gives the output it brought in, and no unit carries one at
    the start of a later investment period — nor does any unit a big M releases instead
  dims: [scenario, snapshot, generator]
  where: >-
    (Generator_ramp_limit_up OR Generator_ramp_limit_start_up)
    AND NOT (Generator_committable AND Generator_p_nom_extendable AND NOT (Generator_p_nom_mod > 0))
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Generator_status_initial == 0 OR Generator_p_init)))
    AND Generator_active
  expression: Generator_p - Generator_previous_p <= Generator_ramp_up_allowance
```

```math
p_{\xi,t,g} - \overleftarrow{p}_{\xi,t,g} \le \Delta^{+}_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \left( \mathrm{ru}_{\xi,t,g} \text{ is defined} \vee \mathrm{ru}^{\mathrm{up}}_{\xi,g} \text{ is defined} \right) \wedge \neg \left( \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{0}_{\xi,g} = 0 \vee \mathrm{p}^{0}_{\xi,g} \text{ is defined} \right) \right) \wedge \mathrm{on}_{t,g}
```

### `Generator-p-ramp_limit_down`

`Generator_p_ramp_limit_down`

```yaml
Generator_p_ramp_limit_down:
  description: >-
    `Generator-p-ramp_limit_down` — a generator lowers output no faster than
    its ramp limit of the build, and a committed one no further than its
    shut-down ramp in the snapshot it turns off. A unit that came into the
    horizon running carries a row at the first snapshot only where its
    `p_init` gives the output it brought in, and no unit carries one at
    the start of a later investment period — nor does any unit a big M releases instead
  dims: [scenario, snapshot, generator]
  where: >-
    (Generator_ramp_limit_down OR Generator_ramp_limit_shut_down)
    AND NOT (Generator_committable AND Generator_p_nom_extendable AND NOT (Generator_p_nom_mod > 0))
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Generator_status_initial == 0 OR Generator_p_init)))
    AND Generator_active
  expression: Generator_previous_p - Generator_p <= Generator_ramp_down_allowance
```

```math
\overleftarrow{p}_{\xi,t,g} - p_{\xi,t,g} \le \Delta^{-}_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \left( \mathrm{rd}_{\xi,t,g} \text{ is defined} \vee \mathrm{rd}^{\mathrm{dn}}_{\xi,g} \text{ is defined} \right) \wedge \neg \left( \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{0}_{\xi,g} = 0 \vee \mathrm{p}^{0}_{\xi,g} \text{ is defined} \right) \right) \wedge \mathrm{on}_{t,g}
```

### `Link-p-ramp_limit_up`

`Link_p_ramp_limit_up`

```yaml
Link_p_ramp_limit_up:
  description: >-
    `Link-p-ramp_limit_up` — a link raises flow no faster than
    its ramp limit of the build, and a committed one no further than its
    start-up ramp in the snapshot it turns on. A link that came into the
    horizon running carries a row at the first snapshot only where its
    `p_init` gives the flow it brought in, and no link carries one at
    the start of a later investment period — nor does any link a big M releases instead
  dims: [scenario, snapshot, link]
  where: >-
    (Link_ramp_limit_up OR Link_ramp_limit_start_up)
    AND NOT (Link_committable AND Link_p_nom_extendable AND NOT (Link_p_nom_mod > 0))
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Link_status_initial == 0 OR Link_p_init)))
    AND Link_active
  expression: Link_p - Link_previous_p <= Link_ramp_up_allowance
```

```math
f_{\xi,t,l} - \overleftarrow{f}_{\xi,t,l} \le \Delta^{f,+}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \left( \mathrm{ru}^{f}_{\xi,t,l} \text{ is defined} \vee \mathrm{ru}^{f,\mathrm{up}}_{\xi,l} \text{ is defined} \right) \wedge \neg \left( \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{f,0}_{\xi,l} = 0 \vee \mathrm{f}^{0}_{\xi,l} \text{ is defined} \right) \right) \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-p-ramp_limit_down`

`Link_p_ramp_limit_down`

```yaml
Link_p_ramp_limit_down:
  description: >-
    `Link-p-ramp_limit_down` — a link lowers flow no faster than
    its ramp limit of the build, and a committed one no further than its
    shut-down ramp in the snapshot it turns off. A link that came into the
    horizon running carries a row at the first snapshot only where its
    `p_init` gives the flow it brought in, and no link carries one at
    the start of a later investment period — nor does any link a big M releases instead
  dims: [scenario, snapshot, link]
  where: >-
    (Link_ramp_limit_down OR Link_ramp_limit_shut_down)
    AND NOT (Link_committable AND Link_p_nom_extendable AND NOT (Link_p_nom_mod > 0))
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Link_status_initial == 0 OR Link_p_init)))
    AND Link_active
  expression: Link_previous_p - Link_p <= Link_ramp_down_allowance
```

```math
\overleftarrow{f}_{\xi,t,l} - f_{\xi,t,l} \le \Delta^{f,-}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \left( \mathrm{rd}^{f}_{\xi,t,l} \text{ is defined} \vee \mathrm{rd}^{f,\mathrm{dn}}_{\xi,l} \text{ is defined} \right) \wedge \neg \left( \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{f,0}_{\xi,l} = 0 \vee \mathrm{f}^{0}_{\xi,l} \text{ is defined} \right) \right) \wedge \mathrm{on}^{f}_{t,l}
```

### `Process-p-ramp_limit_up`

`Process_p_ramp_limit_up`

```yaml
Process_p_ramp_limit_up:
  description: >-
    `Process-p-ramp_limit_up` — a process raises internal power no faster than
    its ramp limit of the build, and a committed one no further than its
    start-up ramp in the snapshot it turns on. A process that came into the
    horizon running carries a row at the first snapshot only where its
    `p_init` gives the internal power it brought in, and no process carries one at
    the start of a later investment period — nor does any process a big M releases instead
  dims: [scenario, snapshot, process]
  where: >-
    (Process_ramp_limit_up OR Process_ramp_limit_start_up)
    AND NOT (Process_committable AND Process_p_nom_extendable AND NOT (Process_p_nom_mod > 0))
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Process_status_initial == 0 OR Process_p_init)))
    AND Process_active
  expression: Process_p - Process_previous_p <= Process_ramp_up_allowance
```

```math
z_{\xi,t,j} - \overleftarrow{z}_{\xi,t,j} \le \Delta^{z,+}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \left( \mathrm{ru}^{z}_{\xi,t,j} \text{ is defined} \vee \mathrm{ru}^{z,\mathrm{up}}_{\xi,j} \text{ is defined} \right) \wedge \neg \left( \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{z,0}_{\xi,j} = 0 \vee \mathrm{z}^{0}_{\xi,j} \text{ is defined} \right) \right) \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-p-ramp_limit_down`

`Process_p_ramp_limit_down`

```yaml
Process_p_ramp_limit_down:
  description: >-
    `Process-p-ramp_limit_down` — a process lowers internal power no faster than
    its ramp limit of the build, and a committed one no further than its
    shut-down ramp in the snapshot it turns off. A process that came into the
    horizon running carries a row at the first snapshot only where its
    `p_init` gives the internal power it brought in, and no process carries one at
    the start of a later investment period — nor does any process a big M releases instead
  dims: [scenario, snapshot, process]
  where: >-
    (Process_ramp_limit_down OR Process_ramp_limit_shut_down)
    AND NOT (Process_committable AND Process_p_nom_extendable AND NOT (Process_p_nom_mod > 0))
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Process_status_initial == 0 OR Process_p_init)))
    AND Process_active
  expression: Process_previous_p - Process_p <= Process_ramp_down_allowance
```

```math
\overleftarrow{z}_{\xi,t,j} - z_{\xi,t,j} \le \Delta^{z,-}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \left( \mathrm{rd}^{z}_{\xi,t,j} \text{ is defined} \vee \mathrm{rd}^{z,\mathrm{dn}}_{\xi,j} \text{ is defined} \right) \wedge \neg \left( \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \left( \mathrm{u}^{z,0}_{\xi,j} = 0 \vee \mathrm{z}^{0}_{\xi,j} \text{ is defined} \right) \right) \wedge \mathrm{on}^{z}_{t,j}
```

### `StorageUnit-ext-p_dispatch-lower`

`StorageUnit_ext_p_dispatch_lower`

```yaml
StorageUnit_ext_p_dispatch_lower:
  description: "`StorageUnit-ext-p_dispatch-lower` — dispatch is non-negative"
  dims: [scenario, snapshot, storage_unit]
  where: StorageUnit_p_nom_extendable AND StorageUnit_active
  expression: StorageUnit_p_dispatch >= 0
```

```math
h^{+}_{\xi,t,s} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

### `StorageUnit-ext-p_dispatch-upper`

`StorageUnit_ext_p_dispatch_upper`

```yaml
StorageUnit_ext_p_dispatch_upper:
  description: "`StorageUnit-ext-p_dispatch-upper` — an extendable unit dispatches at most the chosen build"
  dims: [scenario, snapshot, storage_unit]
  where: StorageUnit_p_nom_extendable AND StorageUnit_active
  expression: StorageUnit_p_dispatch <= StorageUnit_p_max_pu * StorageUnit_p_nom_ext
```

```math
h^{+}_{\xi,t,s} \le \overline{\mathrm{h}}_{\xi,t,s} \cdot H_{s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

### `StorageUnit-ext-p_store-lower`

`StorageUnit_ext_p_store_lower`

```yaml
StorageUnit_ext_p_store_lower:
  description: "`StorageUnit-ext-p_store-lower` — storing is non-negative"
  dims: [scenario, snapshot, storage_unit]
  where: StorageUnit_p_nom_extendable AND StorageUnit_active
  expression: StorageUnit_p_store >= 0
```

```math
h^{-}_{\xi,t,s} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

### `StorageUnit-ext-p_store-upper`

`StorageUnit_ext_p_store_upper`

```yaml
StorageUnit_ext_p_store_upper:
  description: >-
    `StorageUnit-ext-p_store-upper` — an extendable unit stores at most the
    chosen build, the minimum-per-unit column carrying that cap negated
  dims: [scenario, snapshot, storage_unit]
  where: StorageUnit_p_nom_extendable AND StorageUnit_active
  expression: StorageUnit_p_store <= -StorageUnit_p_min_pu * StorageUnit_p_nom_ext
```

```math
h^{-}_{\xi,t,s} \le -\underline{\mathrm{h}}_{\xi,t,s} \cdot H_{s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

### `StorageUnit-ext-state_of_charge-lower`

`StorageUnit_ext_state_of_charge_lower`

```yaml
StorageUnit_ext_state_of_charge_lower:
  description: "`StorageUnit-ext-state_of_charge-lower` — charge is non-negative"
  dims: [scenario, snapshot, storage_unit]
  where: StorageUnit_p_nom_extendable AND StorageUnit_active
  expression: StorageUnit_state_of_charge >= 0
```

```math
\mathit{soc}_{\xi,t,s} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

### `StorageUnit-ext-state_of_charge-upper`

`StorageUnit_ext_state_of_charge_upper`

```yaml
StorageUnit_ext_state_of_charge_upper:
  description: "`StorageUnit-ext-state_of_charge-upper` — an extendable unit holds at most its hours at the chosen build"
  dims: [scenario, snapshot, storage_unit]
  where: StorageUnit_p_nom_extendable AND StorageUnit_active
  expression: StorageUnit_state_of_charge <= StorageUnit_max_hours * StorageUnit_p_nom_ext
```

```math
\mathit{soc}_{\xi,t,s} \le \mathrm{T}^{h}_{\xi,s} \cdot H_{s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

### `StorageUnit-ext-p_nom-lower`

`StorageUnit_ext_p_nom_lower`

```yaml
StorageUnit_ext_p_nom_lower:
  description: "`StorageUnit-ext-p_nom-lower` — the chosen build is at least its floor in every scenario"
  dims: [scenario, storage_unit]
  where: StorageUnit_p_nom_extendable
  expression: StorageUnit_p_nom_ext >= StorageUnit_p_nom_min
```

```math
H_{s} \ge \underline{\mathrm{h}}^{\mathrm{nom}}_{\xi,s} \qquad \forall\, \xi \in \Xi,\ s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s}
```

### `StorageUnit-ext-p_nom-upper`

`StorageUnit_ext_p_nom_upper`

```yaml
StorageUnit_ext_p_nom_upper:
  description: "`StorageUnit-ext-p_nom-upper` — the chosen build is at most its cap in every scenario; a cap of infinity is no row"
  dims: [scenario, storage_unit]
  where: StorageUnit_p_nom_extendable AND StorageUnit_p_nom_max
  expression: StorageUnit_p_nom_ext <= StorageUnit_p_nom_max
```

```math
H_{s} \le \overline{\mathrm{h}}^{\mathrm{nom}}_{\xi,s} \qquad \forall\, \xi \in \Xi,\ s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s} \wedge \overline{\mathrm{h}}^{\mathrm{nom}}_{\xi,s} \text{ is defined}
```

### `StorageUnit-p_nom_set`

`StorageUnit_p_nom_set`

```yaml
StorageUnit_p_nom_set:
  description: "`StorageUnit-p_nom_set` — the chosen build pinned, wherever a value is given"
  dims: [scenario, storage_unit]
  where: StorageUnit_p_nom_extendable AND StorageUnit_p_nom_set
  expression: StorageUnit_p_nom_ext == StorageUnit_p_nom_set
```

```math
H_{s} = \mathrm{h}^{\mathrm{nom,set}}_{\xi,s} \qquad \forall\, \xi \in \Xi,\ s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s} \wedge \mathrm{h}^{\mathrm{nom,set}}_{\xi,s} \text{ is defined}
```

### `StorageUnit-energy_balance`

`StorageUnit_energy_balance`

```yaml
StorageUnit_energy_balance:
  description: >-
    `StorageUnit-energy_balance` — the charge carried in, plus what is
    stored after its efficiency, less what dispatch draws down before its
    own, plus inflow not spilled
  dims: [scenario, snapshot, storage_unit]
  where: StorageUnit_active
  expression: >-
    StorageUnit_state_of_charge ==
    StorageUnit_charge_carried_in
    + StorageUnit_efficiency_store * StorageUnit_p_store * snapshot_weightings_stores
    - StorageUnit_p_dispatch * snapshot_weightings_stores / StorageUnit_efficiency_dispatch
    + (StorageUnit_inflow - StorageUnit_spill) * snapshot_weightings_stores
```

```math
\mathit{soc}_{\xi,t,s} = \overleftarrow{\mathit{soc}}_{\xi,t,s} + \eta^{-}_{\xi,s} \cdot h^{-}_{\xi,t,s} \cdot \mathrm{w}^{\mathrm{sto}}_{t} - \frac{h^{+}_{\xi,t,s} \cdot \mathrm{w}^{\mathrm{sto}}_{t}}{\eta^{+}_{\xi,s}} + \left( \mathrm{inflow}_{\xi,t,s} - \mathit{spill}_{\xi,t,s} \right) \cdot \mathrm{w}^{\mathrm{sto}}_{t} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{on}^{h}_{t,s}
```

### `Store-fix-e-lower`

`Store_fix_e_lower`

```yaml
Store_fix_e_lower:
  description: "`Store-fix-e-lower` — a fixed store holds at least its floor"
  dims: [scenario, snapshot, store]
  where: not Store_e_nom_extendable AND Store_active
  expression: Store_e >= Store_e_min_pu * Store_e_nom
```

```math
e_{\xi,t,v} \ge \underline{\mathrm{e}}_{\xi,t,v} \cdot \mathrm{e}^{\mathrm{nom}}_{\xi,v} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ v \in \mathcal{V} \,:\, \neg \mathrm{ext}^{e}_{v} \wedge \mathrm{on}^{e}_{t,v}
```

### `Store-fix-e-upper`

`Store_fix_e_upper`

```yaml
Store_fix_e_upper:
  description: "`Store-fix-e-upper` — a fixed store holds at most its nominal capacity"
  dims: [scenario, snapshot, store]
  where: not Store_e_nom_extendable AND Store_active
  expression: Store_e <= Store_e_max_pu * Store_e_nom
```

```math
e_{\xi,t,v} \le \overline{\mathrm{e}}_{\xi,t,v} \cdot \mathrm{e}^{\mathrm{nom}}_{\xi,v} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ v \in \mathcal{V} \,:\, \neg \mathrm{ext}^{e}_{v} \wedge \mathrm{on}^{e}_{t,v}
```

### `Store-ext-e-lower`

`Store_ext_e_lower`

```yaml
Store_ext_e_lower:
  description: "`Store-ext-e-lower` — an extendable store holds at least its floor of the chosen build"
  dims: [scenario, snapshot, store]
  where: Store_e_nom_extendable AND Store_active
  expression: Store_e >= Store_e_min_pu * Store_e_nom_ext
```

```math
e_{\xi,t,v} \ge \underline{\mathrm{e}}_{\xi,t,v} \cdot E_{v} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ v \in \mathcal{V} \,:\, \mathrm{ext}^{e}_{v} \wedge \mathrm{on}^{e}_{t,v}
```

### `Store-ext-e-upper`

`Store_ext_e_upper`

```yaml
Store_ext_e_upper:
  description: "`Store-ext-e-upper` — an extendable store holds at most the chosen build"
  dims: [scenario, snapshot, store]
  where: Store_e_nom_extendable AND Store_active
  expression: Store_e <= Store_e_max_pu * Store_e_nom_ext
```

```math
e_{\xi,t,v} \le \overline{\mathrm{e}}_{\xi,t,v} \cdot E_{v} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ v \in \mathcal{V} \,:\, \mathrm{ext}^{e}_{v} \wedge \mathrm{on}^{e}_{t,v}
```

### `Store-ext-e_nom-lower`

`Store_ext_e_nom_lower`

```yaml
Store_ext_e_nom_lower:
  description: "`Store-ext-e_nom-lower` — the chosen build is at least its floor in every scenario"
  dims: [scenario, store]
  where: Store_e_nom_extendable
  expression: Store_e_nom_ext >= Store_e_nom_min
```

```math
E_{v} \ge \underline{\mathrm{e}}^{\mathrm{nom}}_{\xi,v} \qquad \forall\, \xi \in \Xi,\ v \in \mathcal{V} \,:\, \mathrm{ext}^{e}_{v}
```

### `Store-ext-e_nom-upper`

`Store_ext_e_nom_upper`

```yaml
Store_ext_e_nom_upper:
  description: "`Store-ext-e_nom-upper` — the chosen build is at most its cap in every scenario; a cap of infinity is no row"
  dims: [scenario, store]
  where: Store_e_nom_extendable AND Store_e_nom_max
  expression: Store_e_nom_ext <= Store_e_nom_max
```

```math
E_{v} \le \overline{\mathrm{e}}^{\mathrm{nom}}_{\xi,v} \qquad \forall\, \xi \in \Xi,\ v \in \mathcal{V} \,:\, \mathrm{ext}^{e}_{v} \wedge \overline{\mathrm{e}}^{\mathrm{nom}}_{\xi,v} \text{ is defined}
```

### `Store-e_nom_set`

`Store_e_nom_set`

```yaml
Store_e_nom_set:
  description: "`Store-e_nom_set` — the chosen build pinned, wherever a value is given"
  dims: [scenario, store]
  where: Store_e_nom_extendable AND Store_e_nom_set
  expression: Store_e_nom_ext == Store_e_nom_set
```

```math
E_{v} = \mathrm{e}^{\mathrm{nom,set}}_{\xi,v} \qquad \forall\, \xi \in \Xi,\ v \in \mathcal{V} \,:\, \mathrm{ext}^{e}_{v} \wedge \mathrm{e}^{\mathrm{nom,set}}_{\xi,v} \text{ is defined}
```

### `Store-energy_balance`

`Store_energy_balance`

```yaml
Store_energy_balance:
  description: "`Store-energy_balance` — the energy carried in, less what is delivered to the bus"
  dims: [scenario, snapshot, store]
  where: Store_active
  expression: >-
    Store_e ==
    Store_energy_carried_in
    - Store_p * snapshot_weightings_stores
```

```math
e_{\xi,t,v} = \overleftarrow{e}_{\xi,t,v} - q_{\xi,t,v} \cdot \mathrm{w}^{\mathrm{sto}}_{t} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ v \in \mathcal{V} \,:\, \mathrm{on}^{e}_{t,v}
```

### `Generator-p_set`

`Generator_p_set`

```yaml
Generator_p_set:
  description: "`Generator-p_set` — output pinned to the given schedule, wherever one is given"
  dims: [scenario, snapshot, generator]
  where: Generator_p_set AND Generator_active
  expression: Generator_p == Generator_p_set
```

```math
p_{\xi,t,g} = \mathrm{p}^{\mathrm{set}}_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{p}^{\mathrm{set}}_{\xi,t,g} \text{ is defined} \wedge \mathrm{on}_{t,g}
```

### `Link-p_set`

`Link_p_set`

```yaml
Link_p_set:
  description: "`Link-p_set` — flow pinned to the given schedule, wherever one is given"
  dims: [scenario, snapshot, link]
  where: Link_p_set AND Link_active
  expression: Link_p == Link_p_set
```

```math
f_{\xi,t,l} = \mathrm{f}^{\mathrm{set}}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{f}^{\mathrm{set}}_{\xi,t,l} \text{ is defined} \wedge \mathrm{on}^{f}_{t,l}
```

### `Process-p_set`

`Process_p_set`

```yaml
Process_p_set:
  description: "`Process-p_set` — internal power pinned to the given schedule, wherever one is given"
  dims: [scenario, snapshot, process]
  where: Process_p_set AND Process_active
  expression: Process_p == Process_p_set
```

```math
z_{\xi,t,j} = \mathrm{z}^{\mathrm{set}}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{z}^{\mathrm{set}}_{\xi,t,j} \text{ is defined} \wedge \mathrm{on}^{z}_{t,j}
```

### `StorageUnit-p_set`

`StorageUnit_p_set`

```yaml
StorageUnit_p_set:
  description: "`StorageUnit-p_set` — net dispatch pinned to the given schedule, wherever one is given"
  dims: [scenario, snapshot, storage_unit]
  where: StorageUnit_p_set AND StorageUnit_active
  expression: StorageUnit_p_dispatch - StorageUnit_p_store == StorageUnit_p_set
```

```math
h^{+}_{\xi,t,s} - h^{-}_{\xi,t,s} = \mathrm{h}^{\mathrm{set}}_{\xi,t,s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{h}^{\mathrm{set}}_{\xi,t,s} \text{ is defined} \wedge \mathrm{on}^{h}_{t,s}
```

### `StorageUnit-p_dispatch_set`

`StorageUnit_p_dispatch_set`

```yaml
StorageUnit_p_dispatch_set:
  description: "`StorageUnit-p_dispatch_set` — dispatch pinned to the given schedule, wherever one is given"
  dims: [scenario, snapshot, storage_unit]
  where: StorageUnit_p_dispatch_set AND StorageUnit_active
  expression: StorageUnit_p_dispatch == StorageUnit_p_dispatch_set
```

```math
h^{+}_{\xi,t,s} = \mathrm{h}^{+,\mathrm{set}}_{\xi,t,s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{h}^{+,\mathrm{set}}_{\xi,t,s} \text{ is defined} \wedge \mathrm{on}^{h}_{t,s}
```

### `StorageUnit-p_store_set`

`StorageUnit_p_store_set`

```yaml
StorageUnit_p_store_set:
  description: "`StorageUnit-p_store_set` — charging pinned to the given schedule, wherever one is given"
  dims: [scenario, snapshot, storage_unit]
  where: StorageUnit_p_store_set AND StorageUnit_active
  expression: StorageUnit_p_store == StorageUnit_p_store_set
```

```math
h^{-}_{\xi,t,s} = \mathrm{h}^{-,\mathrm{set}}_{\xi,t,s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{h}^{-,\mathrm{set}}_{\xi,t,s} \text{ is defined} \wedge \mathrm{on}^{h}_{t,s}
```

### `StorageUnit-state_of_charge_set`

`StorageUnit_state_of_charge_set`

```yaml
StorageUnit_state_of_charge_set:
  description: "`StorageUnit-state_of_charge_set` — charge pinned to the given schedule, wherever one is given"
  dims: [scenario, snapshot, storage_unit]
  where: StorageUnit_state_of_charge_set AND StorageUnit_active
  expression: StorageUnit_state_of_charge == StorageUnit_state_of_charge_set
```

```math
\mathit{soc}_{\xi,t,s} = \mathrm{soc}^{\mathrm{set}}_{\xi,t,s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{soc}^{\mathrm{set}}_{\xi,t,s} \text{ is defined} \wedge \mathrm{on}^{h}_{t,s}
```

### `Store-e_set`

`Store_e_set`

```yaml
Store_e_set:
  description: "`Store-e_set` — energy pinned to the given schedule, wherever one is given"
  dims: [scenario, snapshot, store]
  where: Store_e_set AND Store_active
  expression: Store_e == Store_e_set
```

```math
e_{\xi,t,v} = \mathrm{e}^{\mathrm{set}}_{\xi,t,v} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ v \in \mathcal{V} \,:\, \mathrm{e}^{\mathrm{set}}_{\xi,t,v} \text{ is defined} \wedge \mathrm{on}^{e}_{t,v}
```

### `Store-p_set`

`Store_p_set`

```yaml
Store_p_set:
  description: "`Store-p_set` — power delivered pinned to the given schedule, wherever one is given"
  dims: [scenario, snapshot, store]
  where: Store_p_set AND Store_active
  expression: Store_p == Store_p_set
```

```math
q_{\xi,t,v} = \mathrm{q}^{\mathrm{set}}_{\xi,t,v} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ v \in \mathcal{V} \,:\, \mathrm{q}^{\mathrm{set}}_{\xi,t,v} \text{ is defined} \wedge \mathrm{on}^{e}_{t,v}
```

### `primary_energy`

`GlobalConstraint_primary_energy_ub`

```yaml
GlobalConstraint_primary_energy_ub:
  description: "`primary_energy` — its total, at most its constant"
  dims: [scenario, global_constraint]
  where: GlobalConstraint_type == 'primary_energy' AND GlobalConstraint_sense == '<='
  expression: primary_energy <= GlobalConstraint_constant
```

```math
\mathit{primary\_energy}_{\xi,i} \le \mathrm{K}_{\xi,i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{primary\_energy}\text{'} \wedge \mathrm{sense}_{\xi,i} = \text{'}\mathrm{<=}\text{'}
```

### `primary_energy`

`GlobalConstraint_primary_energy_lb`

```yaml
GlobalConstraint_primary_energy_lb:
  description: "`primary_energy` — its total, at least its constant"
  dims: [scenario, global_constraint]
  where: GlobalConstraint_type == 'primary_energy' AND GlobalConstraint_sense == '>='
  expression: primary_energy >= GlobalConstraint_constant
```

```math
\mathit{primary\_energy}_{\xi,i} \ge \mathrm{K}_{\xi,i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{primary\_energy}\text{'} \wedge \mathrm{sense}_{\xi,i} = \text{'}\mathrm{>=}\text{'}
```

### `primary_energy`

`GlobalConstraint_primary_energy_eq`

```yaml
GlobalConstraint_primary_energy_eq:
  description: "`primary_energy` — its total, at its constant"
  dims: [scenario, global_constraint]
  where: GlobalConstraint_type == 'primary_energy' AND GlobalConstraint_sense == '=='
  expression: primary_energy == GlobalConstraint_constant
```

```math
\mathit{primary\_energy}_{\xi,i} = \mathrm{K}_{\xi,i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{primary\_energy}\text{'} \wedge \mathrm{sense}_{\xi,i} = \text{'}\mathrm{==}\text{'}
```

### `operational_limit`

`GlobalConstraint_operational_limit_ub`

```yaml
GlobalConstraint_operational_limit_ub:
  description: "`operational_limit` — its total, at most its constant"
  dims: [scenario, global_constraint]
  where: GlobalConstraint_type == 'operational_limit' AND GlobalConstraint_sense == '<='
  expression: operational_limit <= GlobalConstraint_constant
```

```math
\mathit{operational\_limit}_{\xi,i} \le \mathrm{K}_{\xi,i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{operational\_limit}\text{'} \wedge \mathrm{sense}_{\xi,i} = \text{'}\mathrm{<=}\text{'}
```

### `operational_limit`

`GlobalConstraint_operational_limit_lb`

```yaml
GlobalConstraint_operational_limit_lb:
  description: "`operational_limit` — its total, at least its constant"
  dims: [scenario, global_constraint]
  where: GlobalConstraint_type == 'operational_limit' AND GlobalConstraint_sense == '>='
  expression: operational_limit >= GlobalConstraint_constant
```

```math
\mathit{operational\_limit}_{\xi,i} \ge \mathrm{K}_{\xi,i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{operational\_limit}\text{'} \wedge \mathrm{sense}_{\xi,i} = \text{'}\mathrm{>=}\text{'}
```

### `operational_limit`

`GlobalConstraint_operational_limit_eq`

```yaml
GlobalConstraint_operational_limit_eq:
  description: "`operational_limit` — its total, at its constant"
  dims: [scenario, global_constraint]
  where: GlobalConstraint_type == 'operational_limit' AND GlobalConstraint_sense == '=='
  expression: operational_limit == GlobalConstraint_constant
```

```math
\mathit{operational\_limit}_{\xi,i} = \mathrm{K}_{\xi,i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{operational\_limit}\text{'} \wedge \mathrm{sense}_{\xi,i} = \text{'}\mathrm{==}\text{'}
```

### `transmission_volume_expansion_limit`

`GlobalConstraint_transmission_volume_expansion_limit_ub`

```yaml
GlobalConstraint_transmission_volume_expansion_limit_ub:
  description: "`transmission_volume_expansion_limit` — its total, at most its constant"
  dims: [scenario, global_constraint]
  where: GlobalConstraint_type == 'transmission_volume_expansion_limit' AND GlobalConstraint_sense == '<='
  expression: transmission_volume_expansion <= GlobalConstraint_constant
```

```math
\mathit{transmission\_volume\_expansion}_{\xi,i} \le \mathrm{K}_{\xi,i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{transmission\_volume\_expansion\_limit}\text{'} \wedge \mathrm{sense}_{\xi,i} = \text{'}\mathrm{<=}\text{'}
```

### `transmission_volume_expansion_limit`

`GlobalConstraint_transmission_volume_expansion_limit_lb`

```yaml
GlobalConstraint_transmission_volume_expansion_limit_lb:
  description: "`transmission_volume_expansion_limit` — its total, at least its constant"
  dims: [scenario, global_constraint]
  where: GlobalConstraint_type == 'transmission_volume_expansion_limit' AND GlobalConstraint_sense == '>='
  expression: transmission_volume_expansion >= GlobalConstraint_constant
```

```math
\mathit{transmission\_volume\_expansion}_{\xi,i} \ge \mathrm{K}_{\xi,i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{transmission\_volume\_expansion\_limit}\text{'} \wedge \mathrm{sense}_{\xi,i} = \text{'}\mathrm{>=}\text{'}
```

### `transmission_volume_expansion_limit`

`GlobalConstraint_transmission_volume_expansion_limit_eq`

```yaml
GlobalConstraint_transmission_volume_expansion_limit_eq:
  description: "`transmission_volume_expansion_limit` — its total, at its constant"
  dims: [scenario, global_constraint]
  where: GlobalConstraint_type == 'transmission_volume_expansion_limit' AND GlobalConstraint_sense == '=='
  expression: transmission_volume_expansion == GlobalConstraint_constant
```

```math
\mathit{transmission\_volume\_expansion}_{\xi,i} = \mathrm{K}_{\xi,i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{transmission\_volume\_expansion\_limit}\text{'} \wedge \mathrm{sense}_{\xi,i} = \text{'}\mathrm{==}\text{'}
```

### `transmission_expansion_cost_limit`

`GlobalConstraint_transmission_expansion_cost_limit_ub`

```yaml
GlobalConstraint_transmission_expansion_cost_limit_ub:
  description: "`transmission_expansion_cost_limit` — its total, at most its constant"
  dims: [scenario, global_constraint]
  where: GlobalConstraint_type == 'transmission_expansion_cost_limit' AND GlobalConstraint_sense == '<='
  expression: transmission_expansion_cost <= GlobalConstraint_constant
```

```math
\mathit{transmission\_expansion\_cost}_{\xi,i} \le \mathrm{K}_{\xi,i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{transmission\_expansion\_cost\_limit}\text{'} \wedge \mathrm{sense}_{\xi,i} = \text{'}\mathrm{<=}\text{'}
```

### `transmission_expansion_cost_limit`

`GlobalConstraint_transmission_expansion_cost_limit_lb`

```yaml
GlobalConstraint_transmission_expansion_cost_limit_lb:
  description: "`transmission_expansion_cost_limit` — its total, at least its constant"
  dims: [scenario, global_constraint]
  where: GlobalConstraint_type == 'transmission_expansion_cost_limit' AND GlobalConstraint_sense == '>='
  expression: transmission_expansion_cost >= GlobalConstraint_constant
```

```math
\mathit{transmission\_expansion\_cost}_{\xi,i} \ge \mathrm{K}_{\xi,i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{transmission\_expansion\_cost\_limit}\text{'} \wedge \mathrm{sense}_{\xi,i} = \text{'}\mathrm{>=}\text{'}
```

### `transmission_expansion_cost_limit`

`GlobalConstraint_transmission_expansion_cost_limit_eq`

```yaml
GlobalConstraint_transmission_expansion_cost_limit_eq:
  description: "`transmission_expansion_cost_limit` — its total, at its constant"
  dims: [scenario, global_constraint]
  where: GlobalConstraint_type == 'transmission_expansion_cost_limit' AND GlobalConstraint_sense == '=='
  expression: transmission_expansion_cost == GlobalConstraint_constant
```

```math
\mathit{transmission\_expansion\_cost}_{\xi,i} = \mathrm{K}_{\xi,i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{transmission\_expansion\_cost\_limit}\text{'} \wedge \mathrm{sense}_{\xi,i} = \text{'}\mathrm{==}\text{'}
```

### `tech_capacity_expansion_limit`

`GlobalConstraint_tech_capacity_expansion_limit_ub`

```yaml
GlobalConstraint_tech_capacity_expansion_limit_ub:
  description: "`tech_capacity_expansion_limit` — its total, at most its constant"
  dims: [scenario, global_constraint]
  where: GlobalConstraint_type == 'tech_capacity_expansion_limit' AND GlobalConstraint_sense == '<='
  expression: tech_capacity_expansion <= GlobalConstraint_constant
```

```math
\mathit{tech\_capacity\_expansion}_{i} \le \mathrm{K}_{\xi,i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{tech\_capacity\_expansion\_limit}\text{'} \wedge \mathrm{sense}_{\xi,i} = \text{'}\mathrm{<=}\text{'}
```

### `tech_capacity_expansion_limit`

`GlobalConstraint_tech_capacity_expansion_limit_lb`

```yaml
GlobalConstraint_tech_capacity_expansion_limit_lb:
  description: "`tech_capacity_expansion_limit` — its total, at least its constant"
  dims: [scenario, global_constraint]
  where: GlobalConstraint_type == 'tech_capacity_expansion_limit' AND GlobalConstraint_sense == '>='
  expression: tech_capacity_expansion >= GlobalConstraint_constant
```

```math
\mathit{tech\_capacity\_expansion}_{i} \ge \mathrm{K}_{\xi,i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{tech\_capacity\_expansion\_limit}\text{'} \wedge \mathrm{sense}_{\xi,i} = \text{'}\mathrm{>=}\text{'}
```

### `tech_capacity_expansion_limit`

`GlobalConstraint_tech_capacity_expansion_limit_eq`

```yaml
GlobalConstraint_tech_capacity_expansion_limit_eq:
  description: "`tech_capacity_expansion_limit` — its total, at its constant"
  dims: [scenario, global_constraint]
  where: GlobalConstraint_type == 'tech_capacity_expansion_limit' AND GlobalConstraint_sense == '=='
  expression: tech_capacity_expansion == GlobalConstraint_constant
```

```math
\mathit{tech\_capacity\_expansion}_{i} = \mathrm{K}_{\xi,i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{tech\_capacity\_expansion\_limit}\text{'} \wedge \mathrm{sense}_{\xi,i} = \text{'}\mathrm{==}\text{'}
```

### `Bus-nodal_balance`

`Bus_nodal_balance`

```yaml
Bus_nodal_balance:
  description: >-
    `Bus-nodal_balance` — what is generated at a bus, storage dispatch and
    stores included, less what the links take away, plus what arrives over
    them after losses and any delay at every port they deliver to, each
    process port drawing or delivering at its own rate and each passive branch
    carrying its flow, meets the load there, less half of every incident
    line's and transformer's loss — PyPSA dissipates a branch's loss half at
    either end. Each generator, storage unit, store and load term enters
    with its component's `sign` (`constraints.py:1428-1429`, `:1538`), and
    an inactive load not at all. A bus nothing is attached to has no row; PyPSA refuses one that
    carries load, and this file does not yet.
  dims: [scenario, snapshot, bus]
  expression: Bus_injection == 0
```

```math
\sum_{g \in \mathcal{G} \,:\, \mathrm{Generator\_bus}(g) = n} \mathrm{sgn}_{g} \cdot p_{\xi,t,g} - \left( \sum_{k \in \mathcal{K} \,:\, \mathrm{Line\_bus0}(k) = n} s_{\xi,t,k} \right) + \sum_{k \in \mathcal{K} \,:\, \mathrm{Line\_bus1}(k) = n} s_{\xi,t,k} - 0.5 \cdot \left( \sum_{k \in \mathcal{K} \,:\, \mathrm{Line\_bus0}(k) = n} \ell_{\xi,t,k} \right) - 0.5 \cdot \left( \sum_{k \in \mathcal{K} \,:\, \mathrm{Line\_bus1}(k) = n} \ell_{\xi,t,k} \right) - \left( \sum_{l \in \mathcal{L} \,:\, \mathrm{Link\_bus0}(l) = n} f_{\xi,t,l} \right) + \sum_{o \in \mathcal{O} \,:\, \mathrm{Link\_output\_bus}(o) = n} \overrightarrow{f}_{\xi,t,o} + \sum_{d \in \mathcal{D} \,:\, \mathrm{Load\_bus}(d) = n} \check{\mathrm{load}}_{\xi,t,d} + \sum_{r \in \mathcal{R} \,:\, \mathrm{Process\_output\_bus}(r) = n} \overrightarrow{z}_{\xi,t,r} + \sum_{s \in \mathcal{S} \,:\, \mathrm{StorageUnit\_bus}(s) = n} \mathrm{sgn}^{h}_{s} \cdot \left( h^{+}_{\xi,t,s} - h^{-}_{\xi,t,s} \right) + \sum_{v \in \mathcal{V} \,:\, \mathrm{Store\_bus}(v) = n} \mathrm{sgn}^{q}_{v} \cdot q_{\xi,t,v} - \left( \sum_{m \in \mathcal{M} \,:\, \mathrm{Transformer\_bus0}(m) = n} \sigma_{\xi,t,m} \right) + \sum_{m \in \mathcal{M} \,:\, \mathrm{Transformer\_bus1}(m) = n} \sigma_{\xi,t,m} - 0.5 \cdot \left( \sum_{m \in \mathcal{M} \,:\, \mathrm{Transformer\_bus0}(m) = n} \ell^{\sigma}_{\xi,t,m} \right) - 0.5 \cdot \left( \sum_{m \in \mathcal{M} \,:\, \mathrm{Transformer\_bus1}(m) = n} \ell^{\sigma}_{\xi,t,m} \right) = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ n \in \mathcal{N}
```

### `Carrier-growth_limit`

`Carrier_growth_limit`

```yaml
Carrier_growth_limit:
  description: >-
    `Carrier-growth_limit` — what a carrier adds across its extendable components in a period,
    counting each build in the first period it stands in, is at most its allowance plus a share of
    what it added the period before; the first period has no predecessor, so `edge=0` leaves it the
    bare allowance
  dims: [carrier, period]
  where: Carrier_max_growth
  expression: >-
    Carrier_additions
    - shift(Carrier_additions, along=period, offset=1, edge=0) * Carrier_relative_growth
    <= Carrier_max_growth
```

```math
\mathit{Carrier\_additions}_{y,i} - \mathit{Carrier\_additions}_{y \boxminus_{0} 1,i} \cdot \mathrm{r}^{+}_{i} \le \overline{\Delta}_{i} \qquad \forall\, i \in \mathcal{I},\ y \in \mathcal{Y} \,:\, \overline{\Delta}_{i} \text{ is defined}
```

### `CVaR-excess-{s}`

`CVaR_excess`

```yaml
CVaR_excess:
  description: "`CVaR-excess-{s}` — a scenario's operating cost beyond the tail's start is its excess; PyPSA names one row per scenario"
  dims: [scenario]
  where: CVaR_omega > 0
  expression: CVaR_a - scenario_opex + CVaR_theta >= 0
```

```math
a_{\xi} - \mathit{scenario\_opex}_{\xi} + \theta \ge 0 \qquad \forall\, \xi \in \Xi \,:\, \omega > 0
```

### `CVaR-def`

`CVaR_def`

```yaml
CVaR_def:
  description: "`CVaR-def` — the tail's average is at least where it starts plus the expected excess over the tail's probability"
  dims: []
  where: CVaR_omega > 0
  expression: CVaR_theta + CVaR_inv_tail * sum(scenario_weight * CVaR_a, over=scenario) <= CVaR
```

```math
\theta + \mathrm{v} \cdot \left( \sum_{\xi \in \Xi} \pi_{\xi} \cdot a_{\xi} \right) \le CVaR \qquad \text{where } \omega > 0
```

### `Generator_previous_status`

```yaml
Generator_previous_status:
  description: >-
    the commitment state a generator carries into a snapshot — the state it
    brought into the horizon at the first, the previous snapshot's after that
  dims: [scenario, snapshot, generator]
  cases:
    opening: { when: "position(snapshot) == 0", expression: Generator_status_initial }
  otherwise: shift(Generator_status, along=snapshot, offset=1)
```

```math
\overleftarrow{u}_{\xi,t,g} = \begin{cases} \mathrm{u}^{0}_{\xi,g} & \text{if } \mathrm{pos}(t) = 0 \\ u_{\xi,t - 1,g} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G}
```

### `Generator_previous_p`

```yaml
Generator_previous_p:
  description: >-
    the output a generator carries into a snapshot — at the first, the
    `p_init` it brought in where it came in running and nothing where it
    came in off; the previous snapshot's after that
  dims: [scenario, snapshot, generator]
  cases:
    opening: { when: "position(snapshot) == 0", expression: Generator_status_initial * Generator_p_init }
  otherwise: shift(Generator_p, along=snapshot, offset=1)
```

```math
\overleftarrow{p}_{\xi,t,g} = \begin{cases} \mathrm{u}^{0}_{\xi,g} \cdot \mathrm{p}^{0}_{\xi,g} & \text{if } \mathrm{pos}(t) = 0 \\ p_{\xi,t - 1,g} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G}
```

### `Generator_p_nom_effective`

```yaml
Generator_p_nom_effective:
  description: the build a generator's limits are taken against — the chosen one where it is extendable, the given one otherwise
  dims: [scenario, generator]
  cases:
    extendable: { when: Generator_p_nom_extendable, expression: Generator_p_nom_ext }
  otherwise: Generator_p_nom
```

```math
\widetilde{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} = \begin{cases} P_{g} & \text{if } \mathrm{ext}_{g} \\ \mathrm{p}^{\mathrm{nom}}_{\xi,g} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G}
```

### `Generator_ramp_up_rate`

```yaml
Generator_ramp_up_rate:
  description: >-
    the ramp limit a unit's up row reads — PyPSA's `ramp_limit_up`, or the
    full build where it has none, since a start-up ramp alone builds the row
  dims: [scenario, snapshot, generator]
  cases:
    given: { when: Generator_ramp_limit_up, expression: Generator_ramp_limit_up }
  otherwise: 1
```

```math
\widetilde{\mathrm{ru}}_{\xi,t,g} = \begin{cases} \mathrm{ru}_{\xi,t,g} & \text{if } \mathrm{ru}_{\xi,t,g} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G}
```

### `Generator_ramp_down_rate`

```yaml
Generator_ramp_down_rate:
  description: >-
    the ramp limit a unit's down row reads — PyPSA's `ramp_limit_down`, or
    the full build where it has none, since a shut-down ramp alone builds the row
  dims: [scenario, snapshot, generator]
  cases:
    given: { when: Generator_ramp_limit_down, expression: Generator_ramp_limit_down }
  otherwise: 1
```

```math
\widetilde{\mathrm{rd}}_{\xi,t,g} = \begin{cases} \mathrm{rd}_{\xi,t,g} & \text{if } \mathrm{rd}_{\xi,t,g} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G}
```

### `Generator_start_up_rate`

```yaml
Generator_start_up_rate:
  description: >-
    the start-up ramp a unit's up row reads — PyPSA's `ramp_limit_start_up`,
    or the full build where it has none
  dims: [scenario, generator]
  cases:
    given: { when: Generator_ramp_limit_start_up, expression: Generator_ramp_limit_start_up }
  otherwise: 1
```

```math
\widetilde{\mathrm{ru}}^{\mathrm{up}}_{\xi,g} = \begin{cases} \mathrm{ru}^{\mathrm{up}}_{\xi,g} & \text{if } \mathrm{ru}^{\mathrm{up}}_{\xi,g} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G}
```

### `Generator_shut_down_rate`

```yaml
Generator_shut_down_rate:
  description: >-
    the shut-down ramp a unit's down row reads — PyPSA's
    `ramp_limit_shut_down`, or the full build where it has none
  dims: [scenario, generator]
  cases:
    given: { when: Generator_ramp_limit_shut_down, expression: Generator_ramp_limit_shut_down }
  otherwise: 1
```

```math
\widetilde{\mathrm{rd}}^{\mathrm{dn}}_{\xi,g} = \begin{cases} \mathrm{rd}^{\mathrm{dn}}_{\xi,g} & \text{if } \mathrm{rd}^{\mathrm{dn}}_{\xi,g} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G}
```

### `Generator_p_nom_committed`

```yaml
Generator_p_nom_committed:
  description: >-
    the build a committed unit's ramp rows are taken against — one module
    where the build is extendable and modular, the given build otherwise
  dims: [scenario, generator]
  cases:
    modular_build: { when: Generator_p_nom_extendable AND Generator_p_nom_mod > 0, expression: Generator_p_nom_mod }
  otherwise: Generator_p_nom
```

```math
\widehat{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} = \begin{cases} \mathrm{p}^{\mathrm{mod}}_{g} & \text{if } \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \\ \mathrm{p}^{\mathrm{nom}}_{\xi,g} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G}
```

### `Generator_ramp_up_allowance`

```yaml
Generator_ramp_up_allowance:
  description: >-
    how far a generator may raise output between two snapshots — its ramp
    limit of the build while it stays on, plus its start-up ramp in the
    snapshot it turns on
  dims: [scenario, snapshot, generator]
  cases:
    committed:
      when: Generator_committable
      expression: >-
        Generator_ramp_up_rate * Generator_p_nom_committed * Generator_previous_status
        + Generator_start_up_rate * Generator_p_nom_committed
        * (Generator_status - Generator_previous_status)
  otherwise: Generator_ramp_up_rate * Generator_p_nom_effective
```

```math
\Delta^{+}_{\xi,t,g} = \begin{cases} \widetilde{\mathrm{ru}}_{\xi,t,g} \cdot \widehat{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} \cdot \overleftarrow{u}_{\xi,t,g} + \widetilde{\mathrm{ru}}^{\mathrm{up}}_{\xi,g} \cdot \widehat{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} \cdot \left( u_{\xi,t,g} - \overleftarrow{u}_{\xi,t,g} \right) & \text{if } \mathrm{com}_{g} \\ \widetilde{\mathrm{ru}}_{\xi,t,g} \cdot \widetilde{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G}
```

### `Generator_ramp_down_allowance`

```yaml
Generator_ramp_down_allowance:
  description: >-
    how far a generator may lower output between two snapshots — its ramp
    limit of the build while it stays on, plus its shut-down ramp in the
    snapshot it turns off
  dims: [scenario, snapshot, generator]
  cases:
    committed:
      when: Generator_committable
      expression: >-
        Generator_ramp_down_rate * Generator_p_nom_committed * Generator_status
        + Generator_shut_down_rate * Generator_p_nom_committed
        * (Generator_previous_status - Generator_status)
  otherwise: Generator_ramp_down_rate * Generator_p_nom_effective
```

```math
\Delta^{-}_{\xi,t,g} = \begin{cases} \widetilde{\mathrm{rd}}_{\xi,t,g} \cdot \widehat{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} \cdot u_{\xi,t,g} + \widetilde{\mathrm{rd}}^{\mathrm{dn}}_{\xi,g} \cdot \widehat{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} \cdot \left( \overleftarrow{u}_{\xi,t,g} - u_{\xi,t,g} \right) & \text{if } \mathrm{com}_{g} \\ \widetilde{\mathrm{rd}}_{\xi,t,g} \cdot \widetilde{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G}
```

### `Link_p_nom_effective`

```yaml
Link_p_nom_effective:
  description: the build a link's limits are taken against — the chosen one where it is extendable, the given one otherwise
  dims: [scenario, link]
  cases:
    extendable: { when: Link_p_nom_extendable, expression: Link_p_nom_ext }
  otherwise: Link_p_nom
```

```math
\widetilde{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} = \begin{cases} F_{l} & \text{if } \mathrm{ext}^{f}_{l} \\ \mathrm{f}^{\mathrm{nom}}_{\xi,l} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L}
```

### `Link_previous_status`

```yaml
Link_previous_status:
  description: >-
    the commitment state a link carries into a snapshot — the state it
    brought into the horizon at the first, the previous snapshot's after that
  dims: [scenario, snapshot, link]
  cases:
    opening: { when: "position(snapshot) == 0", expression: Link_status_initial }
  otherwise: shift(Link_status, along=snapshot, offset=1)
```

```math
\overleftarrow{u}^{f}_{\xi,t,l} = \begin{cases} \mathrm{u}^{f,0}_{\xi,l} & \text{if } \mathrm{pos}(t) = 0 \\ u^{f}_{\xi,t - 1,l} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L}
```

### `Link_previous_p`

```yaml
Link_previous_p:
  description: >-
    the flow a link carries into a snapshot — at the first, the
    `p_init` it brought in where it came in running and nothing where it
    came in off; the previous snapshot's after that
  dims: [scenario, snapshot, link]
  cases:
    opening: { when: "position(snapshot) == 0", expression: Link_status_initial * Link_p_init }
  otherwise: shift(Link_p, along=snapshot, offset=1)
```

```math
\overleftarrow{f}_{\xi,t,l} = \begin{cases} \mathrm{u}^{f,0}_{\xi,l} \cdot \mathrm{f}^{0}_{\xi,l} & \text{if } \mathrm{pos}(t) = 0 \\ f_{\xi,t - 1,l} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L}
```

### `Link_ramp_up_rate`

```yaml
Link_ramp_up_rate:
  description: >-
    the ramp limit a link's up row reads — PyPSA's `ramp_limit_up`, or the
    full build where it has none, since a start-up ramp alone builds the row
  dims: [scenario, snapshot, link]
  cases:
    given: { when: Link_ramp_limit_up, expression: Link_ramp_limit_up }
  otherwise: 1
```

```math
\widetilde{\mathrm{ru}}^{f}_{\xi,t,l} = \begin{cases} \mathrm{ru}^{f}_{\xi,t,l} & \text{if } \mathrm{ru}^{f}_{\xi,t,l} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L}
```

### `Link_ramp_down_rate`

```yaml
Link_ramp_down_rate:
  description: >-
    the ramp limit a link's down row reads — PyPSA's `ramp_limit_down`, or
    the full build where it has none, since a shut-down ramp alone builds the row
  dims: [scenario, snapshot, link]
  cases:
    given: { when: Link_ramp_limit_down, expression: Link_ramp_limit_down }
  otherwise: 1
```

```math
\widetilde{\mathrm{rd}}^{f}_{\xi,t,l} = \begin{cases} \mathrm{rd}^{f}_{\xi,t,l} & \text{if } \mathrm{rd}^{f}_{\xi,t,l} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L}
```

### `Link_start_up_rate`

```yaml
Link_start_up_rate:
  description: >-
    the start-up ramp a link's up row reads — PyPSA's `ramp_limit_start_up`,
    or the full build where it has none
  dims: [scenario, link]
  cases:
    given: { when: Link_ramp_limit_start_up, expression: Link_ramp_limit_start_up }
  otherwise: 1
```

```math
\widetilde{\mathrm{ru}}^{f,\mathrm{up}}_{\xi,l} = \begin{cases} \mathrm{ru}^{f,\mathrm{up}}_{\xi,l} & \text{if } \mathrm{ru}^{f,\mathrm{up}}_{\xi,l} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L}
```

### `Link_shut_down_rate`

```yaml
Link_shut_down_rate:
  description: >-
    the shut-down ramp a link's down row reads — PyPSA's
    `ramp_limit_shut_down`, or the full build where it has none
  dims: [scenario, link]
  cases:
    given: { when: Link_ramp_limit_shut_down, expression: Link_ramp_limit_shut_down }
  otherwise: 1
```

```math
\widetilde{\mathrm{rd}}^{f,\mathrm{dn}}_{\xi,l} = \begin{cases} \mathrm{rd}^{f,\mathrm{dn}}_{\xi,l} & \text{if } \mathrm{rd}^{f,\mathrm{dn}}_{\xi,l} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L}
```

### `Link_p_nom_committed`

```yaml
Link_p_nom_committed:
  description: >-
    the build a committed link's ramp rows are taken against — one module
    where the build is extendable and modular, the given build otherwise
  dims: [scenario, link]
  cases:
    modular_build: { when: Link_p_nom_extendable AND Link_p_nom_mod > 0, expression: Link_p_nom_mod }
  otherwise: Link_p_nom
```

```math
\widehat{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} = \begin{cases} \mathrm{f}^{\mathrm{mod}}_{l} & \text{if } \mathrm{ext}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \\ \mathrm{f}^{\mathrm{nom}}_{\xi,l} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L}
```

### `Link_ramp_up_allowance`

```yaml
Link_ramp_up_allowance:
  description: >-
    how far a link may raise flow between two snapshots — its ramp
    limit of the build while it stays on, plus its start-up ramp in the
    snapshot it turns on
  dims: [scenario, snapshot, link]
  cases:
    committed:
      when: Link_committable
      expression: >-
        Link_ramp_up_rate * Link_p_nom_committed * Link_previous_status
        + Link_start_up_rate * Link_p_nom_committed
        * (Link_status - Link_previous_status)
  otherwise: Link_ramp_up_rate * Link_p_nom_effective
```

```math
\Delta^{f,+}_{\xi,t,l} = \begin{cases} \widetilde{\mathrm{ru}}^{f}_{\xi,t,l} \cdot \widehat{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} \cdot \overleftarrow{u}^{f}_{\xi,t,l} + \widetilde{\mathrm{ru}}^{f,\mathrm{up}}_{\xi,l} \cdot \widehat{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} \cdot \left( u^{f}_{\xi,t,l} - \overleftarrow{u}^{f}_{\xi,t,l} \right) & \text{if } \mathrm{com}^{f}_{l} \\ \widetilde{\mathrm{ru}}^{f}_{\xi,t,l} \cdot \widetilde{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L}
```

### `Link_ramp_down_allowance`

```yaml
Link_ramp_down_allowance:
  description: >-
    how far a link may lower flow between two snapshots — its ramp
    limit of the build while it stays on, plus its shut-down ramp in the
    snapshot it turns off
  dims: [scenario, snapshot, link]
  cases:
    committed:
      when: Link_committable
      expression: >-
        Link_ramp_down_rate * Link_p_nom_committed * Link_status
        + Link_shut_down_rate * Link_p_nom_committed
        * (Link_previous_status - Link_status)
  otherwise: Link_ramp_down_rate * Link_p_nom_effective
```

```math
\Delta^{f,-}_{\xi,t,l} = \begin{cases} \widetilde{\mathrm{rd}}^{f}_{\xi,t,l} \cdot \widehat{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} \cdot u^{f}_{\xi,t,l} + \widetilde{\mathrm{rd}}^{f,\mathrm{dn}}_{\xi,l} \cdot \widehat{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} \cdot \left( \overleftarrow{u}^{f}_{\xi,t,l} - u^{f}_{\xi,t,l} \right) & \text{if } \mathrm{com}^{f}_{l} \\ \widetilde{\mathrm{rd}}^{f}_{\xi,t,l} \cdot \widetilde{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L}
```

### `Process_p_nom_effective`

```yaml
Process_p_nom_effective:
  description: the build a process's limits are taken against — the chosen one where it is extendable, the given one otherwise
  dims: [scenario, process]
  cases:
    extendable: { when: Process_p_nom_extendable, expression: Process_p_nom_ext }
  otherwise: Process_p_nom
```

```math
\widetilde{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} = \begin{cases} Z_{j} & \text{if } \mathrm{ext}^{z}_{j} \\ \mathrm{z}^{\mathrm{nom}}_{\xi,j} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ j \in \mathcal{J}
```

### `Process_previous_status`

```yaml
Process_previous_status:
  description: >-
    the commitment state a process carries into a snapshot — the state it
    brought into the horizon at the first, the previous snapshot's after that
  dims: [scenario, snapshot, process]
  cases:
    opening: { when: "position(snapshot) == 0", expression: Process_status_initial }
  otherwise: shift(Process_status, along=snapshot, offset=1)
```

```math
\overleftarrow{u}^{z}_{\xi,t,j} = \begin{cases} \mathrm{u}^{z,0}_{\xi,j} & \text{if } \mathrm{pos}(t) = 0 \\ u^{z}_{\xi,t - 1,j} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J}
```

### `Process_previous_p`

```yaml
Process_previous_p:
  description: >-
    the internal power a process carries into a snapshot — at the first, the
    `p_init` it brought in where it came in running and nothing where it
    came in off; the previous snapshot's after that
  dims: [scenario, snapshot, process]
  cases:
    opening: { when: "position(snapshot) == 0", expression: Process_status_initial * Process_p_init }
  otherwise: shift(Process_p, along=snapshot, offset=1)
```

```math
\overleftarrow{z}_{\xi,t,j} = \begin{cases} \mathrm{u}^{z,0}_{\xi,j} \cdot \mathrm{z}^{0}_{\xi,j} & \text{if } \mathrm{pos}(t) = 0 \\ z_{\xi,t - 1,j} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J}
```

### `Process_ramp_up_rate`

```yaml
Process_ramp_up_rate:
  description: >-
    the ramp limit a process's up row reads — PyPSA's `ramp_limit_up`, or the
    full build where it has none, since a start-up ramp alone builds the row
  dims: [scenario, snapshot, process]
  cases:
    given: { when: Process_ramp_limit_up, expression: Process_ramp_limit_up }
  otherwise: 1
```

```math
\widetilde{\mathrm{ru}}^{z}_{\xi,t,j} = \begin{cases} \mathrm{ru}^{z}_{\xi,t,j} & \text{if } \mathrm{ru}^{z}_{\xi,t,j} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J}
```

### `Process_ramp_down_rate`

```yaml
Process_ramp_down_rate:
  description: >-
    the ramp limit a process's down row reads — PyPSA's `ramp_limit_down`, or
    the full build where it has none, since a shut-down ramp alone builds the row
  dims: [scenario, snapshot, process]
  cases:
    given: { when: Process_ramp_limit_down, expression: Process_ramp_limit_down }
  otherwise: 1
```

```math
\widetilde{\mathrm{rd}}^{z}_{\xi,t,j} = \begin{cases} \mathrm{rd}^{z}_{\xi,t,j} & \text{if } \mathrm{rd}^{z}_{\xi,t,j} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J}
```

### `Process_start_up_rate`

```yaml
Process_start_up_rate:
  description: >-
    the start-up ramp a process's up row reads — PyPSA's `ramp_limit_start_up`,
    or the full build where it has none
  dims: [scenario, process]
  cases:
    given: { when: Process_ramp_limit_start_up, expression: Process_ramp_limit_start_up }
  otherwise: 1
```

```math
\widetilde{\mathrm{ru}}^{z,\mathrm{up}}_{\xi,j} = \begin{cases} \mathrm{ru}^{z,\mathrm{up}}_{\xi,j} & \text{if } \mathrm{ru}^{z,\mathrm{up}}_{\xi,j} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ j \in \mathcal{J}
```

### `Process_shut_down_rate`

```yaml
Process_shut_down_rate:
  description: >-
    the shut-down ramp a process's down row reads — PyPSA's
    `ramp_limit_shut_down`, or the full build where it has none
  dims: [scenario, process]
  cases:
    given: { when: Process_ramp_limit_shut_down, expression: Process_ramp_limit_shut_down }
  otherwise: 1
```

```math
\widetilde{\mathrm{rd}}^{z,\mathrm{dn}}_{\xi,j} = \begin{cases} \mathrm{rd}^{z,\mathrm{dn}}_{\xi,j} & \text{if } \mathrm{rd}^{z,\mathrm{dn}}_{\xi,j} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ j \in \mathcal{J}
```

### `Process_p_nom_committed`

```yaml
Process_p_nom_committed:
  description: >-
    the build a committed process's ramp rows are taken against — one module
    where the build is extendable and modular, the given build otherwise
  dims: [scenario, process]
  cases:
    modular_build: { when: Process_p_nom_extendable AND Process_p_nom_mod > 0, expression: Process_p_nom_mod }
  otherwise: Process_p_nom
```

```math
\widehat{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} = \begin{cases} \mathrm{z}^{\mathrm{mod}}_{j} & \text{if } \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \\ \mathrm{z}^{\mathrm{nom}}_{\xi,j} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ j \in \mathcal{J}
```

### `Process_ramp_up_allowance`

```yaml
Process_ramp_up_allowance:
  description: >-
    how far a process may raise internal power between two snapshots — its ramp
    limit of the build while it stays on, plus its start-up ramp in the
    snapshot it turns on
  dims: [scenario, snapshot, process]
  cases:
    committed:
      when: Process_committable
      expression: >-
        Process_ramp_up_rate * Process_p_nom_committed * Process_previous_status
        + Process_start_up_rate * Process_p_nom_committed
        * (Process_status - Process_previous_status)
  otherwise: Process_ramp_up_rate * Process_p_nom_effective
```

```math
\Delta^{z,+}_{\xi,t,j} = \begin{cases} \widetilde{\mathrm{ru}}^{z}_{\xi,t,j} \cdot \widehat{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} \cdot \overleftarrow{u}^{z}_{\xi,t,j} + \widetilde{\mathrm{ru}}^{z,\mathrm{up}}_{\xi,j} \cdot \widehat{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} \cdot \left( u^{z}_{\xi,t,j} - \overleftarrow{u}^{z}_{\xi,t,j} \right) & \text{if } \mathrm{com}^{z}_{j} \\ \widetilde{\mathrm{ru}}^{z}_{\xi,t,j} \cdot \widetilde{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J}
```

### `Process_ramp_down_allowance`

```yaml
Process_ramp_down_allowance:
  description: >-
    how far a process may lower internal power between two snapshots — its ramp
    limit of the build while it stays on, plus its shut-down ramp in the
    snapshot it turns off
  dims: [scenario, snapshot, process]
  cases:
    committed:
      when: Process_committable
      expression: >-
        Process_ramp_down_rate * Process_p_nom_committed * Process_status
        + Process_shut_down_rate * Process_p_nom_committed
        * (Process_previous_status - Process_status)
  otherwise: Process_ramp_down_rate * Process_p_nom_effective
```

```math
\Delta^{z,-}_{\xi,t,j} = \begin{cases} \widetilde{\mathrm{rd}}^{z}_{\xi,t,j} \cdot \widehat{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} \cdot u^{z}_{\xi,t,j} + \widetilde{\mathrm{rd}}^{z,\mathrm{dn}}_{\xi,j} \cdot \widehat{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} \cdot \left( \overleftarrow{u}^{z}_{\xi,t,j} - u^{z}_{\xi,t,j} \right) & \text{if } \mathrm{com}^{z}_{j} \\ \widetilde{\mathrm{rd}}^{z}_{\xi,t,j} \cdot \widetilde{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J}
```

### `StorageUnit_charge_carried_in`

```yaml
StorageUnit_charge_carried_in:
  description: >-
    the charge a unit opens a snapshot with — at the first snapshot it
    stands in, its last such snapshot's less standing loss where it is
    cyclic and the given initial charge, which no standing loss has touched
    yet, where it is not; the previous snapshot's less standing loss
    otherwise. A unit built in a later period opens in that period, and a
    cyclic one that retires closes on its own last snapshot. Per period, the
    same holds with each investment period as the horizon
  dims: [scenario, snapshot, storage_unit]
  cases:
    cyclic:
      when: >-
        StorageUnit_cyclic_state_of_charge AND NOT StorageUnit_cyclic_state_of_charge_per_period
        AND NOT StorageUnit_state_of_charge_initial_per_period
        AND (position(snapshot) == 0 OR StorageUnit_opens_late)
      expression: >-
        StorageUnit_retention
        * shift(shift(StorageUnit_state_of_charge, along=snapshot, offset=1, edge='wrap'), along=snapshot, offset=StorageUnit_inactive_snapshots, edge='wrap')
    opening:
      when: >-
        NOT StorageUnit_cyclic_state_of_charge AND NOT StorageUnit_cyclic_state_of_charge_per_period
        AND NOT StorageUnit_state_of_charge_initial_per_period
        AND (position(snapshot) == 0 OR StorageUnit_opens_late)
      expression: StorageUnit_state_of_charge_initial
    period_cyclic:
      when: StorageUnit_cyclic_state_of_charge_per_period
      expression: >-
        StorageUnit_retention
        * shift(StorageUnit_state_of_charge, along=snapshot, offset=1, edge='wrap', by=snapshot_period, within=period)
    period_opening:
      when: >-
        StorageUnit_state_of_charge_initial_per_period AND NOT StorageUnit_cyclic_state_of_charge_per_period
        AND position(snapshot, by=snapshot_period, within=period) == 0
      expression: StorageUnit_state_of_charge_initial
  otherwise: StorageUnit_retention * shift(StorageUnit_state_of_charge, along=snapshot, offset=1)
```

```math
\overleftarrow{\mathit{soc}}_{\xi,t,s} = \begin{cases} \rho_{\xi,t,s} \cdot \mathit{soc}_{\xi,\left( t \ominus \mathrm{idle} \right) \ominus 1,s} & \text{if } \mathrm{cyc}_{\xi,s} \wedge \neg \mathrm{cyc}^{y}_{\xi,s} \wedge \neg \mathrm{reset}_{\xi,s} \wedge \left( \mathrm{pos}(t) = 0 \vee \mathrm{open}_{t,s} \right) \\ \mathrm{soc}^{0}_{\xi,s} & \text{if } \neg \mathrm{cyc}_{\xi,s} \wedge \neg \mathrm{cyc}^{y}_{\xi,s} \wedge \neg \mathrm{reset}_{\xi,s} \wedge \left( \mathrm{pos}(t) = 0 \vee \mathrm{open}_{t,s} \right) \\ \rho_{\xi,t,s} \cdot \mathit{soc}_{\xi,t \ominus^{\mathrm{snapshot\_period}(t)} 1,s} & \text{if } \mathrm{cyc}^{y}_{\xi,s} \\ \mathrm{soc}^{0}_{\xi,s} & \text{if } \mathrm{reset}_{\xi,s} \wedge \neg \mathrm{cyc}^{y}_{\xi,s} \wedge \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) = 0 \\ \rho_{\xi,t,s} \cdot \mathit{soc}_{\xi,t - 1,s} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S}
```

### `Store_energy_carried_in`

```yaml
Store_energy_carried_in:
  description: >-
    the energy a store opens a snapshot with — at the first snapshot it
    stands in, its last such snapshot's less standing loss where it is
    cyclic and the given initial energy, which no standing loss has touched
    yet, where it is not; the previous snapshot's less standing loss
    otherwise. A store built in a later period opens in that period, and a
    cyclic one that retires closes on its own last snapshot. Per period, the
    same holds with each investment period as the horizon
  dims: [scenario, snapshot, store]
  cases:
    cyclic:
      when: >-
        Store_e_cyclic AND NOT Store_e_cyclic_per_period AND NOT Store_e_initial_per_period
        AND (position(snapshot) == 0 OR Store_opens_late)
      expression: >-
        Store_retention
        * shift(shift(Store_e, along=snapshot, offset=1, edge='wrap'), along=snapshot, offset=Store_inactive_snapshots, edge='wrap')
    opening:
      when: >-
        NOT Store_e_cyclic AND NOT Store_e_cyclic_per_period AND NOT Store_e_initial_per_period
        AND (position(snapshot) == 0 OR Store_opens_late)
      expression: Store_e_initial
    period_cyclic:
      when: Store_e_cyclic_per_period
      expression: Store_retention * shift(Store_e, along=snapshot, offset=1, edge='wrap', by=snapshot_period, within=period)
    period_opening:
      when: Store_e_initial_per_period AND NOT Store_e_cyclic_per_period AND position(snapshot, by=snapshot_period, within=period) == 0
      expression: Store_e_initial
  otherwise: Store_retention * shift(Store_e, along=snapshot, offset=1)
```

```math
\overleftarrow{e}_{\xi,t,v} = \begin{cases} \rho^{e}_{\xi,t,v} \cdot e_{\xi,\left( t \ominus \mathrm{idle}^{e} \right) \ominus 1,v} & \text{if } \mathrm{cyc}^{e}_{\xi,v} \wedge \neg \mathrm{cyc}^{e,y}_{\xi,v} \wedge \neg \mathrm{reset}^{e}_{\xi,v} \wedge \left( \mathrm{pos}(t) = 0 \vee \mathrm{open}^{e}_{t,v} \right) \\ \mathrm{e}^{0}_{\xi,v} & \text{if } \neg \mathrm{cyc}^{e}_{\xi,v} \wedge \neg \mathrm{cyc}^{e,y}_{\xi,v} \wedge \neg \mathrm{reset}^{e}_{\xi,v} \wedge \left( \mathrm{pos}(t) = 0 \vee \mathrm{open}^{e}_{t,v} \right) \\ \rho^{e}_{\xi,t,v} \cdot e_{\xi,t \ominus^{\mathrm{snapshot\_period}(t)} 1,v} & \text{if } \mathrm{cyc}^{e,y}_{\xi,v} \\ \mathrm{e}^{0}_{\xi,v} & \text{if } \mathrm{reset}^{e}_{\xi,v} \wedge \neg \mathrm{cyc}^{e,y}_{\xi,v} \wedge \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) = 0 \\ \rho^{e}_{\xi,t,v} \cdot e_{\xi,t - 1,v} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ v \in \mathcal{V}
```

### `Link_output_arrival`

```yaml
Link_output_arrival:
  description: >-
    what a link delivers to an output port at a snapshot — its flow after the
    port's efficiency, delayed by the port's `delay` within its investment
    period; where the port is `cyclic_delay` the delayed flow wraps from the
    period's end, and where it is not the flow still in transit at the
    period's first snapshots is lost. A port that does not delay (`delay`
    zero) delivers its flow unshifted, cyclic or not
  dims: [scenario, snapshot, link_output]
  cases:
    wrapping:
      when: Link_output_cyclic_delay
      expression: shift(at(Link_p, by=Link_output_link, over=link, into=link_output) * Link_efficiency, along=snapshot, offset=Link_output_delay, edge='wrap', by=snapshot_period, within=period)
  otherwise: shift(at(Link_p, by=Link_output_link, over=link, into=link_output) * Link_efficiency, along=snapshot, offset=Link_output_delay, edge=0, by=snapshot_period, within=period)
```

```math
\overrightarrow{f}_{\xi,t,o} = \begin{cases} f_{\xi,t \ominus^{\mathrm{snapshot\_period}(t)} \mathrm{d}^{f},\mathrm{Link\_output\_link}(o)} \cdot \eta_{\xi,o} & \text{if } \mathrm{cyc}^{f}_{\xi,o} \\ f_{\xi,t \boxminus_{0}^{\mathrm{snapshot\_period}(t)} \mathrm{d}^{f},\mathrm{Link\_output\_link}(o)} \cdot \eta_{\xi,o} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ o \in \mathcal{O}
```

### `Process_output_arrival`

```yaml
Process_output_arrival:
  description: >-
    what a process transfers at a port at a snapshot — its internal power
    times the port's rate, delayed by the port's `delay` within its
    investment period; where the port is `cyclic_delay` the delayed transfer
    wraps from the period's end, and where it is not the energy still in
    transit at the period's first snapshots is lost. A port that does not
    delay (`delay` zero) transfers at once, cyclic or not
  dims: [scenario, snapshot, process_output]
  cases:
    wrapping:
      when: Process_output_cyclic_delay
      expression: shift(at(Process_p, by=Process_output_process, over=process, into=process_output) * Process_rate, along=snapshot, offset=Process_output_delay, edge='wrap', by=snapshot_period, within=period)
  otherwise: shift(at(Process_p, by=Process_output_process, over=process, into=process_output) * Process_rate, along=snapshot, offset=Process_output_delay, edge=0, by=snapshot_period, within=period)
```

```math
\overrightarrow{z}_{\xi,t,r} = \begin{cases} z_{\xi,t \ominus^{\mathrm{snapshot\_period}(t)} \mathrm{d}^{z},\mathrm{Process\_output\_process}(r)} \cdot \alpha_{\xi,r} & \text{if } \mathrm{cyc}^{z}_{\xi,r} \\ z_{\xi,t \boxminus_{0}^{\mathrm{snapshot\_period}(t)} \mathrm{d}^{z},\mathrm{Process\_output\_process}(r)} \cdot \alpha_{\xi,r} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ r \in \mathcal{R}
```

### `GlobalConstraint_energy_weight`

```yaml
GlobalConstraint_energy_weight:
  description: >-
    what one unit of power at a snapshot counts for in a row — the
    generator weighting times the years of the snapshot's period, where the
    row counts the snapshot, and nothing where it does not
  dims: [scenario, global_constraint, snapshot]
  cases:
    counted:
      when: GlobalConstraint_counts_snapshot
      expression: snapshot_weightings_generators * at(period_weight_years, by=snapshot_period, over=period, into=snapshot)
  otherwise: 0
```

```math
\mathit{w}^{\mathrm{gc}}_{\xi,i,t} = \begin{cases} \mathrm{w}^{\mathrm{gen}}_{t} \cdot \mathrm{w}^{\mathrm{yr}}_{\mathrm{snapshot\_period}(t)} & \text{if } \mathrm{in}_{\xi,i,t} \\ 0 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I},\ t \in \mathcal{T}
```

### `GlobalConstraint_snapshot_closes`

```yaml
GlobalConstraint_snapshot_closes:
  description: one at the last snapshot a row counts, and zero elsewhere
  dims: [scenario, global_constraint, snapshot]
  cases:
    last_counted:
      when: GlobalConstraint_counts_snapshot AND NOT shift(GlobalConstraint_counts_snapshot, along=snapshot, offset=-1)
      expression: 1
  otherwise: 0
```

```math
\mathit{last}_{\xi,i,t} = \begin{cases} 1 & \text{if } \mathrm{in}_{\xi,i,t} \wedge \neg \mathrm{in}_{\xi,i,t + 1} \\ 0 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I},\ t \in \mathcal{T}
```

### `StorageUnit_closing_weight`

```yaml
StorageUnit_closing_weight:
  description: >-
    what the charge a unit holds at a snapshot counts for in a row as its
    closing level — the years of the period at the last snapshot of each
    counted period where the unit reopens per period, one at the last
    counted snapshot where it does not, and nothing elsewhere
  dims: [scenario, global_constraint, snapshot, storage_unit]
  cases:
    per_period:
      when: StorageUnit_state_of_charge_initial_per_period AND GlobalConstraint_counts_snapshot AND position(snapshot, by=snapshot_period, within=period) == -1
      expression: at(period_weight_years, by=snapshot_period, over=period, into=snapshot)
    carried_over:
      when: NOT StorageUnit_state_of_charge_initial_per_period
      expression: GlobalConstraint_snapshot_closes
  otherwise: 0
```

```math
\mathit{w}^{h}_{\xi,i,t,s} = \begin{cases} \mathrm{w}^{\mathrm{yr}}_{\mathrm{snapshot\_period}(t)} & \text{if } \mathrm{reset}_{\xi,s} \wedge \mathrm{in}_{\xi,i,t} \wedge \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) = \lvert \mathcal{T}_{\mathrm{snapshot\_period}(t)} \rvert - 1 \\ \mathit{last}_{\xi,i,t} & \text{if } \neg \mathrm{reset}_{\xi,s} \\ 0 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I},\ t \in \mathcal{T},\ s \in \mathcal{S}
```

### `Store_closing_weight`

```yaml
Store_closing_weight:
  description: >-
    what the energy a store holds at a snapshot counts for in a row as its
    closing level — the years of the period at the last snapshot of each
    counted period where the store reopens per period, one at the last
    counted snapshot where it does not, and nothing elsewhere
  dims: [scenario, global_constraint, snapshot, store]
  cases:
    per_period:
      when: Store_e_initial_per_period AND GlobalConstraint_counts_snapshot AND position(snapshot, by=snapshot_period, within=period) == -1
      expression: at(period_weight_years, by=snapshot_period, over=period, into=snapshot)
    carried_over:
      when: NOT Store_e_initial_per_period
      expression: GlobalConstraint_snapshot_closes
  otherwise: 0
```

```math
\mathit{w}^{e}_{\xi,i,t,v} = \begin{cases} \mathrm{w}^{\mathrm{yr}}_{\mathrm{snapshot\_period}(t)} & \text{if } \mathrm{reset}^{e}_{\xi,v} \wedge \mathrm{in}_{\xi,i,t} \wedge \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) = \lvert \mathcal{T}_{\mathrm{snapshot\_period}(t)} \rvert - 1 \\ \mathit{last}_{\xi,i,t} & \text{if } \neg \mathrm{reset}^{e}_{\xi,v} \\ 0 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I},\ t \in \mathcal{T},\ v \in \mathcal{V}
```

### `Generator_primary_energy`

```yaml
Generator_primary_energy:
  expression: >-
    sum(sum((Generator_p * GlobalConstraint_energy_weight) * Generator_primary_energy_weight, over=snapshot), over=generator)
```

```math
\mathit{Generator\_primary\_energy}_{\xi,i} = \sum_{g \in \mathcal{G}} \sum_{t \in \mathcal{T}} p_{\xi,t,g} \cdot \mathit{w}^{\mathrm{gc}}_{\xi,i,t} \cdot \mathrm{a}_{\xi,i,g} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I}
```

### `StorageUnit_primary_energy`

```yaml
StorageUnit_primary_energy:
  expression: >-
    -sum(sum((StorageUnit_state_of_charge * StorageUnit_closing_weight) * StorageUnit_primary_energy_weight, over=snapshot), over=storage_unit)
```

```math
\mathit{StorageUnit\_primary\_energy}_{\xi,i} = -\left( \sum_{s \in \mathcal{S}} \sum_{t \in \mathcal{T}} \mathit{soc}_{\xi,t,s} \cdot \mathit{w}^{h}_{\xi,i,t,s} \cdot \mathrm{a}^{h}_{\xi,i,s} \right) \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I}
```

### `Store_primary_energy`

```yaml
Store_primary_energy:
  expression: >-
    -sum(sum((Store_e * Store_closing_weight) * Store_primary_energy_weight, over=snapshot), over=store)
```

```math
\mathit{Store\_primary\_energy}_{\xi,i} = -\left( \sum_{v \in \mathcal{V}} \sum_{t \in \mathcal{T}} e_{\xi,t,v} \cdot \mathit{w}^{e}_{\xi,i,t,v} \cdot \mathrm{a}^{e}_{\xi,i,v} \right) \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I}
```

### `primary_energy`

```yaml
primary_energy:
  dims: [scenario, global_constraint]
  expression: Generator_primary_energy + StorageUnit_primary_energy + Store_primary_energy
  description: >-
    what a `primary_energy` row totals — weighted generator energy over the
    snapshots it counts, less the charge left in weighted storage at the
    close; the initial charge it is compared against is folded into the
    row's constant
```

```math
\mathit{primary\_energy}_{\xi,i} = \mathit{Generator\_primary\_energy}_{\xi,i} + \mathit{StorageUnit\_primary\_energy}_{\xi,i} + \mathit{Store\_primary\_energy}_{\xi,i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I}
```

### `Generator_operational_limit`

```yaml
Generator_operational_limit:
  expression: >-
    sum(sum((Generator_p * GlobalConstraint_energy_weight) * Generator_operational_limit_weight, over=snapshot), over=generator)
```

```math
\mathit{Generator\_operational\_limit}_{\xi,i} = \sum_{g \in \mathcal{G}} \sum_{t \in \mathcal{T}} p_{\xi,t,g} \cdot \mathit{w}^{\mathrm{gc}}_{\xi,i,t} \cdot \mathrm{b}_{\xi,i,g} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I}
```

### `StorageUnit_operational_limit`

```yaml
StorageUnit_operational_limit:
  expression: >-
    -sum(sum((StorageUnit_state_of_charge * StorageUnit_closing_weight) * StorageUnit_operational_limit_weight, over=snapshot), over=storage_unit)
```

```math
\mathit{StorageUnit\_operational\_limit}_{\xi,i} = -\left( \sum_{s \in \mathcal{S}} \sum_{t \in \mathcal{T}} \mathit{soc}_{\xi,t,s} \cdot \mathit{w}^{h}_{\xi,i,t,s} \cdot \mathrm{b}^{h}_{\xi,i,s} \right) \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I}
```

### `Store_operational_limit`

```yaml
Store_operational_limit:
  expression: >-
    -sum(sum((Store_e * Store_closing_weight) * Store_operational_limit_weight, over=snapshot), over=store)
```

```math
\mathit{Store\_operational\_limit}_{\xi,i} = -\left( \sum_{v \in \mathcal{V}} \sum_{t \in \mathcal{T}} e_{\xi,t,v} \cdot \mathit{w}^{e}_{\xi,i,t,v} \cdot \mathrm{b}^{e}_{\xi,i,v} \right) \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I}
```

### `operational_limit`

```yaml
operational_limit:
  dims: [scenario, global_constraint]
  expression: >-
    Generator_operational_limit
    + StorageUnit_operational_limit
    + Store_operational_limit
  description: >-
    what an `operational_limit` row totals — the weighted energy its
    generators deliver over the snapshots it counts, plus what its
    non-cyclic storage draws down; the initial charge it draws from is
    folded into the row's constant
```

```math
\mathit{operational\_limit}_{\xi,i} = \mathit{Generator\_operational\_limit}_{\xi,i} + \mathit{StorageUnit\_operational\_limit}_{\xi,i} + \mathit{Store\_operational\_limit}_{\xi,i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I}
```

### `Line_transmission_volume_expansion`

```yaml
Line_transmission_volume_expansion:
  expression: sum(Line_s_nom_ext * Line_volume_weight, over=line)
```

```math
\mathit{Line\_transmission\_volume\_expansion}_{\xi,i} = \sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{len}_{\xi,i,k} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I}
```

### `Link_transmission_volume_expansion`

```yaml
Link_transmission_volume_expansion:
  expression: sum(Link_p_nom_ext * Link_volume_weight, over=link)
```

```math
\mathit{Link\_transmission\_volume\_expansion}_{\xi,i} = \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{len}^{f}_{\xi,i,l} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I}
```

### `transmission_volume_expansion`

```yaml
transmission_volume_expansion:
  dims: [scenario, global_constraint]
  expression: Line_transmission_volume_expansion + Link_transmission_volume_expansion
  description: >-
    what a `transmission_volume_expansion_limit` row totals — length times
    the chosen build of the row's branches
```

```math
\mathit{transmission\_volume\_expansion}_{\xi,i} = \mathit{Line\_transmission\_volume\_expansion}_{\xi,i} + \mathit{Link\_transmission\_volume\_expansion}_{\xi,i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I}
```

### `Line_transmission_expansion_cost`

```yaml
Line_transmission_expansion_cost:
  expression: sum(Line_s_nom_ext * Line_expansion_cost_weight, over=line)
```

```math
\mathit{Line\_transmission\_expansion\_cost}_{\xi,i} = \sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{cc}_{\xi,i,k} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I}
```

### `Link_transmission_expansion_cost`

```yaml
Link_transmission_expansion_cost:
  expression: sum(Link_p_nom_ext * Link_expansion_cost_weight, over=link)
```

```math
\mathit{Link\_transmission\_expansion\_cost}_{\xi,i} = \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{cc}^{f}_{\xi,i,l} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I}
```

### `transmission_expansion_cost`

```yaml
transmission_expansion_cost:
  dims: [scenario, global_constraint]
  expression: Line_transmission_expansion_cost + Link_transmission_expansion_cost
  description: >-
    what a `transmission_expansion_cost_limit` row totals — capital cost
    times the chosen build of the row's branches
```

```math
\mathit{transmission\_expansion\_cost}_{\xi,i} = \mathit{Line\_transmission\_expansion\_cost}_{\xi,i} + \mathit{Link\_transmission\_expansion\_cost}_{\xi,i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I}
```

### `Generator_tech_capacity_expansion`

```yaml
Generator_tech_capacity_expansion:
  expression: sum(Generator_p_nom_ext * Generator_tech_capacity_weight, over=generator)
```

```math
\mathit{Generator\_tech\_capacity\_expansion}_{i} = \sum_{g \in \mathcal{G}} P_{g} \cdot \mathrm{m}_{i,g} \qquad \forall\, i \in \mathcal{I}
```

### `Line_tech_capacity_expansion`

```yaml
Line_tech_capacity_expansion:
  expression: sum(Line_s_nom_ext * Line_tech_capacity_weight, over=line)
```

```math
\mathit{Line\_tech\_capacity\_expansion}_{i} = \sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{m}^{l}_{i,k} \qquad \forall\, i \in \mathcal{I}
```

### `Link_tech_capacity_expansion`

```yaml
Link_tech_capacity_expansion:
  expression: sum(Link_p_nom_ext * Link_tech_capacity_weight, over=link)
```

```math
\mathit{Link\_tech\_capacity\_expansion}_{i} = \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{m}^{f}_{i,l} \qquad \forall\, i \in \mathcal{I}
```

### `Process_tech_capacity_expansion`

```yaml
Process_tech_capacity_expansion:
  expression: sum(Process_p_nom_ext * Process_tech_capacity_weight, over=process)
```

```math
\mathit{Process\_tech\_capacity\_expansion}_{i} = \sum_{j \in \mathcal{J}} Z_{j} \cdot \mathrm{m}^{z}_{i,j} \qquad \forall\, i \in \mathcal{I}
```

### `StorageUnit_tech_capacity_expansion`

```yaml
StorageUnit_tech_capacity_expansion:
  expression: sum(StorageUnit_p_nom_ext * StorageUnit_tech_capacity_weight, over=storage_unit)
```

```math
\mathit{StorageUnit\_tech\_capacity\_expansion}_{i} = \sum_{s \in \mathcal{S}} H_{s} \cdot \mathrm{m}^{h}_{i,s} \qquad \forall\, i \in \mathcal{I}
```

### `Store_tech_capacity_expansion`

```yaml
Store_tech_capacity_expansion:
  expression: sum(Store_e_nom_ext * Store_tech_capacity_weight, over=store)
```

```math
\mathit{Store\_tech\_capacity\_expansion}_{i} = \sum_{v \in \mathcal{V}} E_{v} \cdot \mathrm{m}^{e}_{i,v} \qquad \forall\, i \in \mathcal{I}
```

### `tech_capacity_expansion`

```yaml
tech_capacity_expansion:
  dims: [global_constraint]
  expression: >-
    Generator_tech_capacity_expansion
    + Line_tech_capacity_expansion
    + Link_tech_capacity_expansion
    + Process_tech_capacity_expansion
    + StorageUnit_tech_capacity_expansion
    + Store_tech_capacity_expansion
  description: >-
    what a `tech_capacity_expansion_limit` row totals — the chosen build of
    the row's carrier-and-bus set
```

```math
\mathit{tech\_capacity\_expansion}_{i} = \mathit{Generator\_tech\_capacity\_expansion}_{i} + \mathit{Line\_tech\_capacity\_expansion}_{i} + \mathit{Link\_tech\_capacity\_expansion}_{i} + \mathit{Process\_tech\_capacity\_expansion}_{i} + \mathit{StorageUnit\_tech\_capacity\_expansion}_{i} + \mathit{Store\_tech\_capacity\_expansion}_{i} \qquad \forall\, i \in \mathcal{I}
```

### `Generator_opex`

```yaml
Generator_opex:
  expression: >-
    sum(sum(((Generator_p * Generator_marginal_cost) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=generator), over=snapshot)
    + sum(sum((((Generator_p * Generator_p) * Generator_marginal_cost_quadratic) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=generator), over=snapshot)
```

```math
\mathit{Generator\_opex}_{\xi} = \sum_{t \in \mathcal{T}} \sum_{g \in \mathcal{G}} p_{\xi,t,g} \cdot \mathrm{c}_{\xi,t,g} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{g \in \mathcal{G}} p_{\xi,t,g} \cdot p_{\xi,t,g} \cdot \mathrm{c}^{(2)}_{\xi,t,g} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} \qquad \forall\, \xi \in \Xi
```

### `Generator_commitment_opex`

```yaml
Generator_commitment_opex:
  expression: >-
    sum(sum(((Generator_status * Generator_stand_by_cost) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=generator), over=snapshot)
    + sum(sum(Generator_start_up * Generator_start_up_cost, over=generator), over=snapshot)
    + sum(sum(Generator_shut_down * Generator_shut_down_cost, over=generator), over=snapshot)
```

```math
\mathit{Generator\_commitment\_opex}_{\xi} = \sum_{t \in \mathcal{T}} \sum_{g \in \mathcal{G}} u_{\xi,t,g} \cdot \mathrm{c}^{\mathrm{on}}_{\xi,t,g} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{g \in \mathcal{G}} \mathit{up}_{\xi,t,g} \cdot \mathrm{c}^{\mathrm{up}}_{\xi,g} + \sum_{t \in \mathcal{T}} \sum_{g \in \mathcal{G}} \mathit{dn}_{\xi,t,g} \cdot \mathrm{c}^{\mathrm{dn}}_{\xi,g} \qquad \forall\, \xi \in \Xi
```

### `Link_opex`

```yaml
Link_opex:
  expression: >-
    sum(sum(((Link_p * Link_marginal_cost) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=link), over=snapshot)
    + sum(sum((((Link_p * Link_p) * Link_marginal_cost_quadratic) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=link), over=snapshot)
```

```math
\mathit{Link\_opex}_{\xi} = \sum_{t \in \mathcal{T}} \sum_{l \in \mathcal{L}} f_{\xi,t,l} \cdot \mathrm{c}^{f}_{\xi,t,l} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{l \in \mathcal{L}} f_{\xi,t,l} \cdot f_{\xi,t,l} \cdot \mathrm{c}^{f,(2)}_{\xi,t,l} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} \qquad \forall\, \xi \in \Xi
```

### `Link_commitment_opex`

```yaml
Link_commitment_opex:
  expression: >-
    sum(sum(((Link_status * Link_stand_by_cost) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=link), over=snapshot)
    + sum(sum(Link_start_up * Link_start_up_cost, over=link), over=snapshot)
    + sum(sum(Link_shut_down * Link_shut_down_cost, over=link), over=snapshot)
```

```math
\mathit{Link\_commitment\_opex}_{\xi} = \sum_{t \in \mathcal{T}} \sum_{l \in \mathcal{L}} u^{f}_{\xi,t,l} \cdot \mathrm{c}^{f,\mathrm{on}}_{\xi,t,l} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{l \in \mathcal{L}} \mathit{up}^{f}_{\xi,t,l} \cdot \mathrm{c}^{f,\mathrm{up}}_{\xi,l} + \sum_{t \in \mathcal{T}} \sum_{l \in \mathcal{L}} \mathit{dn}^{f}_{\xi,t,l} \cdot \mathrm{c}^{f,\mathrm{dn}}_{\xi,l} \qquad \forall\, \xi \in \Xi
```

### `Process_opex`

```yaml
Process_opex:
  expression: >-
    sum(sum(((Process_p * Process_marginal_cost) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=process), over=snapshot)
    + sum(sum((((Process_p * Process_p) * Process_marginal_cost_quadratic) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=process), over=snapshot)
```

```math
\mathit{Process\_opex}_{\xi} = \sum_{t \in \mathcal{T}} \sum_{j \in \mathcal{J}} z_{\xi,t,j} \cdot \mathrm{c}^{z}_{\xi,t,j} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{j \in \mathcal{J}} z_{\xi,t,j} \cdot z_{\xi,t,j} \cdot \mathrm{c}^{z,(2)}_{\xi,t,j} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} \qquad \forall\, \xi \in \Xi
```

### `Process_commitment_opex`

```yaml
Process_commitment_opex:
  expression: >-
    sum(sum(((Process_status * Process_stand_by_cost) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=process), over=snapshot)
    + sum(sum(Process_start_up * Process_start_up_cost, over=process), over=snapshot)
    + sum(sum(Process_shut_down * Process_shut_down_cost, over=process), over=snapshot)
```

```math
\mathit{Process\_commitment\_opex}_{\xi} = \sum_{t \in \mathcal{T}} \sum_{j \in \mathcal{J}} u^{z}_{\xi,t,j} \cdot \mathrm{c}^{z,\mathrm{on}}_{\xi,t,j} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{j \in \mathcal{J}} \mathit{up}^{z}_{\xi,t,j} \cdot \mathrm{c}^{z,\mathrm{up}}_{\xi,j} + \sum_{t \in \mathcal{T}} \sum_{j \in \mathcal{J}} \mathit{dn}^{z}_{\xi,t,j} \cdot \mathrm{c}^{z,\mathrm{dn}}_{\xi,j} \qquad \forall\, \xi \in \Xi
```

### `StorageUnit_opex`

```yaml
StorageUnit_opex:
  expression: >-
    sum(sum(((StorageUnit_p_dispatch * StorageUnit_marginal_cost) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=storage_unit), over=snapshot)
    + sum(sum((((StorageUnit_p_dispatch * StorageUnit_p_dispatch) * StorageUnit_marginal_cost_quadratic) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=storage_unit), over=snapshot)
    + sum(sum(((StorageUnit_state_of_charge * StorageUnit_marginal_cost_storage) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=storage_unit), over=snapshot)
    + sum(sum(((StorageUnit_spill * StorageUnit_spill_cost) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=storage_unit), over=snapshot)
```

```math
\mathit{StorageUnit\_opex}_{\xi} = \sum_{t \in \mathcal{T}} \sum_{s \in \mathcal{S}} h^{+}_{\xi,t,s} \cdot \mathrm{c}^{h}_{\xi,t,s} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{s \in \mathcal{S}} h^{+}_{\xi,t,s} \cdot h^{+}_{\xi,t,s} \cdot \mathrm{c}^{h,(2)}_{\xi,t,s} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{s \in \mathcal{S}} \mathit{soc}_{\xi,t,s} \cdot \mathrm{c}^{\mathrm{soc}}_{\xi,t,s} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{s \in \mathcal{S}} \mathit{spill}_{\xi,t,s} \cdot \mathrm{c}^{\mathrm{spill}}_{\xi,t,s} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} \qquad \forall\, \xi \in \Xi
```

### `Store_opex`

```yaml
Store_opex:
  expression: >-
    sum(sum(((Store_p * Store_marginal_cost) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=store), over=snapshot)
    + sum(sum((((Store_p * Store_p) * Store_marginal_cost_quadratic) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=store), over=snapshot)
    + sum(sum(((Store_e * Store_marginal_cost_storage) * snapshot_weightings_objective) * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=store), over=snapshot)
```

```math
\mathit{Store\_opex}_{\xi} = \sum_{t \in \mathcal{T}} \sum_{v \in \mathcal{V}} q_{\xi,t,v} \cdot \mathrm{c}^{q}_{\xi,t,v} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{v \in \mathcal{V}} q_{\xi,t,v} \cdot q_{\xi,t,v} \cdot \mathrm{c}^{q,(2)}_{\xi,t,v} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{v \in \mathcal{V}} e_{\xi,t,v} \cdot \mathrm{c}^{e}_{\xi,t,v} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} \qquad \forall\, \xi \in \Xi
```

### `scenario_opex`

```yaml
scenario_opex:
  dims: [scenario]
  expression: >-
    Generator_opex
    + Generator_commitment_opex
    + Link_opex
    + Link_commitment_opex
    + Process_opex
    + Process_commitment_opex
    + StorageUnit_opex
    + Store_opex
  description: >-
    what a future costs to run — every operating term, weighted by the
    snapshot's hours and its period, before the scenario's own weight; a
    start and a stop cost what they cost, unweighted, as PyPSA adds them
    (`optimize.py:414-429`)
```

```math
\mathit{scenario\_opex}_{\xi} = \mathit{Generator\_opex}_{\xi} + \mathit{Generator\_commitment\_opex}_{\xi} + \mathit{Link\_opex}_{\xi} + \mathit{Link\_commitment\_opex}_{\xi} + \mathit{Process\_opex}_{\xi} + \mathit{Process\_commitment\_opex}_{\xi} + \mathit{StorageUnit\_opex}_{\xi} + \mathit{Store\_opex}_{\xi} \qquad \forall\, \xi \in \Xi
```

### `Generator_additions`

```yaml
Generator_additions:
  expression: >-
    sum(Generator_p_nom_ext * Generator_first_active, by=Generator_carrier, over=generator, into=carrier)
```

```math
\mathit{Generator\_additions}_{y,i} = \sum_{g \in \mathcal{G} \,:\, \mathrm{Generator\_carrier}(g) = i} P_{g} \cdot \mathrm{new}_{y,g} \qquad \forall\, y \in \mathcal{Y},\ i \in \mathcal{I}
```

### `Line_additions`

```yaml
Line_additions:
  expression: >-
    sum(Line_s_nom_ext * Line_first_active, by=Line_carrier, over=line, into=carrier)
```

```math
\mathit{Line\_additions}_{y,i} = \sum_{k \in \mathcal{K} \,:\, \mathrm{Line\_carrier}(k) = i} S_{k} \cdot \mathrm{new}^{s}_{y,k} \qquad \forall\, y \in \mathcal{Y},\ i \in \mathcal{I}
```

### `Link_additions`

```yaml
Link_additions:
  expression: >-
    sum(Link_p_nom_ext * Link_first_active, by=Link_carrier, over=link, into=carrier)
```

```math
\mathit{Link\_additions}_{y,i} = \sum_{l \in \mathcal{L} \,:\, \mathrm{Link\_carrier}(l) = i} F_{l} \cdot \mathrm{new}^{f}_{y,l} \qquad \forall\, y \in \mathcal{Y},\ i \in \mathcal{I}
```

### `Process_additions`

```yaml
Process_additions:
  expression: >-
    sum(Process_p_nom_ext * Process_first_active, by=Process_carrier, over=process, into=carrier)
```

```math
\mathit{Process\_additions}_{y,i} = \sum_{j \in \mathcal{J} \,:\, \mathrm{Process\_carrier}(j) = i} Z_{j} \cdot \mathrm{new}^{z}_{y,j} \qquad \forall\, y \in \mathcal{Y},\ i \in \mathcal{I}
```

### `StorageUnit_additions`

```yaml
StorageUnit_additions:
  expression: >-
    sum(StorageUnit_p_nom_ext * StorageUnit_first_active, by=StorageUnit_carrier, over=storage_unit, into=carrier)
```

```math
\mathit{StorageUnit\_additions}_{y,i} = \sum_{s \in \mathcal{S} \,:\, \mathrm{StorageUnit\_carrier}(s) = i} H_{s} \cdot \mathrm{new}^{h}_{y,s} \qquad \forall\, y \in \mathcal{Y},\ i \in \mathcal{I}
```

### `Store_additions`

```yaml
Store_additions:
  expression: >-
    sum(Store_e_nom_ext * Store_first_active, by=Store_carrier, over=store, into=carrier)
```

```math
\mathit{Store\_additions}_{y,i} = \sum_{v \in \mathcal{V} \,:\, \mathrm{Store\_carrier}(v) = i} E_{v} \cdot \mathrm{new}^{e}_{y,v} \qquad \forall\, y \in \mathcal{Y},\ i \in \mathcal{I}
```

### `Carrier_additions`

```yaml
Carrier_additions:
  dims: [period, carrier]
  expression: >-
    Generator_additions
    + Line_additions
    + Link_additions
    + Process_additions
    + StorageUnit_additions
    + Store_additions
  description: >-
    what a carrier adds in a period — every extendable component of that
    carrier, counting each build in the first period it stands in. Like
    PyPSA, it sums only the components that carry a carrier attribute, so a
    transformer, which has none, counts in no carrier
```

```math
\mathit{Carrier\_additions}_{y,i} = \mathit{Generator\_additions}_{y,i} + \mathit{Line\_additions}_{y,i} + \mathit{Link\_additions}_{y,i} + \mathit{Process\_additions}_{y,i} + \mathit{StorageUnit\_additions}_{y,i} + \mathit{Store\_additions}_{y,i} \qquad \forall\, y \in \mathcal{Y},\ i \in \mathcal{I}
```

### `Carrier_relative_growth`

```yaml
Carrier_relative_growth:
  description: >-
    the share of the previous period's additions a carrier's growth limit
    reads — PyPSA's `max_relative_growth` clipped at zero, so a negative
    share adds nothing and never tightens the limit
  dims: [carrier]
  cases:
    positive: { when: Carrier_max_relative_growth > 0, expression: Carrier_max_relative_growth }
  otherwise: 0
```

```math
\mathrm{r}^{+}_{i} = \begin{cases} \mathrm{r}_{i} & \text{if } \mathrm{r}_{i} > 0 \\ 0 & \text{otherwise} \end{cases} \qquad \forall\, i \in \mathcal{I}
```

### `Load_demand`

```yaml
Load_demand:
  description: >-
    what a load draws from its bus's balance — its demand times its sign
    where it is active, nothing where it is not, since PyPSA drops an
    inactive load from the balance (`constraints.py:1537-1538`)
  dims: [scenario, snapshot, load]
  cases:
    active: { when: Load_active, expression: Load_sign * Load_p_set }
  otherwise: 0
```

```math
\check{\mathrm{load}}_{\xi,t,d} = \begin{cases} \mathrm{sgn}^{\mathrm{load}}_{d} \cdot \mathrm{load}_{\xi,t,d} & \text{if } \mathrm{on}^{\mathrm{load}}_{d} \\ 0 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ d \in \mathcal{D}
```

### `Line_s_monitored`

```yaml
Line_s_monitored:
  description: >-
    the flow a line's post-contingency rows read — its flow where it stands,
    nothing where it does not, since PyPSA builds those rows for every
    branch of the sub-network in every snapshot
  dims: [scenario, snapshot, line]
  cases:
    standing: { when: Line_active, expression: Line_s }
  otherwise: 0
```

```math
\check{s}_{\xi,t,k} = \begin{cases} s_{\xi,t,k} & \text{if } \mathrm{on}^{s}_{t,k} \\ 0 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K}
```

### `Transformer_s_monitored`

```yaml
Transformer_s_monitored:
  description: the flow a transformer's post-contingency rows read, as a line's
  dims: [scenario, snapshot, transformer]
  cases:
    standing: { when: Transformer_active, expression: Transformer_s }
  otherwise: 0
```

```math
\check{\sigma}_{\xi,t,m} = \begin{cases} \sigma_{\xi,t,m} & \text{if } \mathrm{on}^{\sigma}_{t,m} \\ 0 & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M}
```

### `Outage_s`

```yaml
Outage_s:
  description: >-
    the flow an outage takes off its branch — the outaged line's or
    transformer's flow before it goes out
  dims: [scenario, snapshot, outage]
  cases:
    line: { when: Outage_line, expression: "at(Line_s_monitored, by=Outage_line, over=line, into=outage)" }
  otherwise: at(Transformer_s_monitored, by=Outage_transformer, over=transformer, into=outage)
```

```math
\hat{s}_{\xi,t,\kappa} = \begin{cases} \check{s}_{\xi,t,\mathrm{Outage\_line}(\kappa)} & \text{if } \mathrm{Outage\_line}(\kappa) \text{ is defined} \\ \check{\sigma}_{\xi,t,\mathrm{Outage\_transformer}(\kappa)} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ \kappa \in \mathcal{K}^{\mathrm{out}}
```

### `Generator_injection`

```yaml
Generator_injection:
  expression: sum(Generator_sign * Generator_p, by=Generator_bus, over=generator, into=bus)
```

```math
\mathit{Generator\_injection}_{\xi,t,n} = \sum_{g \in \mathcal{G} \,:\, \mathrm{Generator\_bus}(g) = n} \mathrm{sgn}_{g} \cdot p_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ n \in \mathcal{N}
```

### `Line_injection`

```yaml
Line_injection:
  expression: >-
    -sum(Line_s, by=Line_bus0, over=line, into=bus)
    + sum(Line_s, by=Line_bus1, over=line, into=bus)
    - (0.5 * sum(Line_loss, by=Line_bus0, over=line, into=bus))
    - (0.5 * sum(Line_loss, by=Line_bus1, over=line, into=bus))
```

```math
\mathit{Line\_injection}_{\xi,t,n} = -\left( \sum_{k \in \mathcal{K} \,:\, \mathrm{Line\_bus0}(k) = n} s_{\xi,t,k} \right) + \sum_{k \in \mathcal{K} \,:\, \mathrm{Line\_bus1}(k) = n} s_{\xi,t,k} - 0.5 \cdot \left( \sum_{k \in \mathcal{K} \,:\, \mathrm{Line\_bus0}(k) = n} \ell_{\xi,t,k} \right) - 0.5 \cdot \left( \sum_{k \in \mathcal{K} \,:\, \mathrm{Line\_bus1}(k) = n} \ell_{\xi,t,k} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ n \in \mathcal{N}
```

### `Link_injection`

```yaml
Link_injection:
  expression: >-
    -sum(Link_p, by=Link_bus0, over=link, into=bus)
    + sum(Link_output_arrival, by=Link_output_bus, over=link_output, into=bus)
```

```math
\mathit{Link\_injection}_{\xi,t,n} = -\left( \sum_{l \in \mathcal{L} \,:\, \mathrm{Link\_bus0}(l) = n} f_{\xi,t,l} \right) + \sum_{o \in \mathcal{O} \,:\, \mathrm{Link\_output\_bus}(o) = n} \overrightarrow{f}_{\xi,t,o} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ n \in \mathcal{N}
```

### `Load_injection`

```yaml
Load_injection: sum(Load_demand, by=Load_bus, over=load, into=bus)
```

```math
\mathrm{Load\_injection}_{\xi,t,n} = \sum_{d \in \mathcal{D} \,:\, \mathrm{Load\_bus}(d) = n} \check{\mathrm{load}}_{\xi,t,d} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ n \in \mathcal{N}
```

### `Process_injection`

```yaml
Process_injection:
  expression: >-
    sum(Process_output_arrival, by=Process_output_bus, over=process_output, into=bus)
```

```math
\mathit{Process\_injection}_{\xi,t,n} = \sum_{r \in \mathcal{R} \,:\, \mathrm{Process\_output\_bus}(r) = n} \overrightarrow{z}_{\xi,t,r} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ n \in \mathcal{N}
```

### `StorageUnit_injection`

```yaml
StorageUnit_injection:
  expression: >-
    sum(StorageUnit_sign * (StorageUnit_p_dispatch - StorageUnit_p_store), by=StorageUnit_bus, over=storage_unit, into=bus)
```

```math
\mathit{StorageUnit\_injection}_{\xi,t,n} = \sum_{s \in \mathcal{S} \,:\, \mathrm{StorageUnit\_bus}(s) = n} \mathrm{sgn}^{h}_{s} \cdot \left( h^{+}_{\xi,t,s} - h^{-}_{\xi,t,s} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ n \in \mathcal{N}
```

### `Store_injection`

```yaml
Store_injection: sum(Store_sign * Store_p, by=Store_bus, over=store, into=bus)
```

```math
\mathit{Store\_injection}_{\xi,t,n} = \sum_{v \in \mathcal{V} \,:\, \mathrm{Store\_bus}(v) = n} \mathrm{sgn}^{q}_{v} \cdot q_{\xi,t,v} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ n \in \mathcal{N}
```

### `Transformer_injection`

```yaml
Transformer_injection:
  expression: >-
    -sum(Transformer_s, by=Transformer_bus0, over=transformer, into=bus)
    + sum(Transformer_s, by=Transformer_bus1, over=transformer, into=bus)
    - (0.5 * sum(Transformer_loss, by=Transformer_bus0, over=transformer, into=bus))
    - (0.5 * sum(Transformer_loss, by=Transformer_bus1, over=transformer, into=bus))
```

```math
\mathit{Transformer\_injection}_{\xi,t,n} = -\left( \sum_{m \in \mathcal{M} \,:\, \mathrm{Transformer\_bus0}(m) = n} \sigma_{\xi,t,m} \right) + \sum_{m \in \mathcal{M} \,:\, \mathrm{Transformer\_bus1}(m) = n} \sigma_{\xi,t,m} - 0.5 \cdot \left( \sum_{m \in \mathcal{M} \,:\, \mathrm{Transformer\_bus0}(m) = n} \ell^{\sigma}_{\xi,t,m} \right) - 0.5 \cdot \left( \sum_{m \in \mathcal{M} \,:\, \mathrm{Transformer\_bus1}(m) = n} \ell^{\sigma}_{\xi,t,m} \right) \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ n \in \mathcal{N}
```

### `Bus_injection`

```yaml
Bus_injection:
  dims: [scenario, snapshot, bus]
  expression: >-
    Generator_injection
    + Line_injection
    + Link_injection
    + Load_injection
    + Process_injection
    + StorageUnit_injection
    + Store_injection
    + Transformer_injection
  description: >-
    what every component puts into a bus, less what it takes out of it;
    PyPSA writes each term into the balance, and a load on its right-hand
    side
```

```math
\mathit{Bus\_injection}_{\xi,t,n} = \mathit{Generator\_injection}_{\xi,t,n} + \mathit{Line\_injection}_{\xi,t,n} + \mathit{Link\_injection}_{\xi,t,n} + \mathrm{Load\_injection}_{\xi,t,n} + \mathit{Process\_injection}_{\xi,t,n} + \mathit{StorageUnit\_injection}_{\xi,t,n} + \mathit{Store\_injection}_{\xi,t,n} + \mathit{Transformer\_injection}_{\xi,t,n} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ n \in \mathcal{N}
```

### `Line_angle_sum`

```yaml
Line_angle_sum: sum(Line_s * Line_cycle_weight, over=line)
```

```math
\mathit{Line\_angle\_sum}_{\xi,t,c} = \sum_{k \in \mathcal{K}} s_{\xi,t,k} \cdot \mathrm{x}_{k,c} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ c \in \mathcal{C}
```

### `Transformer_angle_sum`

```yaml
Transformer_angle_sum:
  expression: >-
    sum(Transformer_s * Transformer_cycle_weight, over=transformer)
    + sum(Transformer_phase_shift_weight, over=transformer)
    + sum(Transformer_phase_shift * Transformer_phase_shift_cycle_weight, over=transformer)
```

```math
\mathit{Transformer\_angle\_sum}_{\xi,t,c} = \sum_{m \in \mathcal{M}} \sigma_{\xi,t,m} \cdot \mathrm{x}^{\sigma}_{m,c} + \sum_{m \in \mathcal{M}} \vartheta_{m,c} + \sum_{m \in \mathcal{M}} \mathit{Transformer\_phase\_shift}_{\xi,t,m} \cdot \mathrm{Transformer\_phase\_shift\_cycle\_weight}_{m,c} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ c \in \mathcal{C}
```

### `Cycle_angle_sum`

```yaml
Cycle_angle_sum:
  dims: [scenario, snapshot, cycle]
  expression: Line_angle_sum + Transformer_angle_sum
  description: >-
    the voltage angle differences around a cycle: every branch flow times
    its cycle weight, and every transformer phase shift
```

```math
\mathit{Cycle\_angle\_sum}_{\xi,t,c} = \mathit{Line\_angle\_sum}_{\xi,t,c} + \mathit{Transformer\_angle\_sum}_{\xi,t,c} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ c \in \mathcal{C}
```

#### Variable domains

**`Generator_p`**

```math
p_{\xi,t,g} \in \mathbb{R} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{on}_{t,g}
```

**`Link_p`**

```math
f_{\xi,t,l} \in \mathbb{R} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{on}^{f}_{t,l}
```

**`Process_p`**

```math
z_{\xi,t,j} \in \mathbb{R} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{on}^{z}_{t,j}
```

**`StorageUnit_p_dispatch`**

```math
h^{+}_{\xi,t,s} \in \mathbb{R} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{on}^{h}_{t,s}
```

**`StorageUnit_p_store`**

```math
h^{-}_{\xi,t,s} \in \mathbb{R} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{on}^{h}_{t,s}
```

**`StorageUnit_state_of_charge`**

```math
\mathit{soc}_{\xi,t,s} \in \mathbb{R} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{on}^{h}_{t,s}
```

**`StorageUnit_spill`**

```math
0 \le \mathit{spill}_{\xi,t,s} \le \mathrm{inflow}_{\xi,t,s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{inflow}_{\xi,t,s} > 0 \wedge \mathrm{on}^{h}_{t,s}
```

**`Store_e`**

```math
e_{\xi,t,v} \in \mathbb{R} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ v \in \mathcal{V} \,:\, \mathrm{on}^{e}_{t,v}
```

**`Store_p`**

```math
q_{\xi,t,v} \in \mathbb{R} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ v \in \mathcal{V} \,:\, \mathrm{on}^{e}_{t,v}
```

**`Generator_n_mod`**

```math
N_{g} \ge 0, N_{g} \in \mathbb{Z} \qquad \forall\, g \in \mathcal{G} \,:\, \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0
```

**`Generator_status`**

```math
u_{\xi,t,g} \ge 0, u_{\xi,t,g} \in \mathbb{Z} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{on}_{t,g}
```

**`Generator_start_up`**

```math
\mathit{up}_{\xi,t,g} \ge 0, \mathit{up}_{\xi,t,g} \in \mathbb{Z} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{on}_{t,g}
```

**`Generator_shut_down`**

```math
\mathit{dn}_{\xi,t,g} \ge 0, \mathit{dn}_{\xi,t,g} \in \mathbb{Z} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{on}_{t,g}
```

**`Generator_maintenance`**

```math
0 \le \mu_{\xi,t,g} \le 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{on}_{t,g}
```

**`Generator_maintenance_start`**

```math
\mu^{\mathrm{up}}_{\xi,t,g} \in \{0, 1\} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{on}_{t,g}
```

**`Generator_maintenance_capacity`**

```math
\mu^{\mathrm{nom}}_{\xi,t,g} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{com}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
```

**`Generator_maintenance_status`**

```math
\mu^{u}_{\xi,t,g} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{com}_{g} \wedge \neg \left( \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \right) \wedge \mathrm{on}_{t,g}
```

**`Link_n_mod`**

```math
N^{f}_{l} \ge 0, N^{f}_{l} \in \mathbb{Z} \qquad \forall\, l \in \mathcal{L} \,:\, \mathrm{ext}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0
```

**`Link_status`**

```math
u^{f}_{\xi,t,l} \ge 0, u^{f}_{\xi,t,l} \in \mathbb{Z} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_start_up`**

```math
\mathit{up}^{f}_{\xi,t,l} \ge 0, \mathit{up}^{f}_{\xi,t,l} \in \mathbb{Z} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_shut_down`**

```math
\mathit{dn}^{f}_{\xi,t,l} \ge 0, \mathit{dn}^{f}_{\xi,t,l} \in \mathbb{Z} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_maintenance`**

```math
0 \le \mu^{f}_{\xi,t,l} \le 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_maintenance_start`**

```math
\mu^{f,\mathrm{up}}_{\xi,t,l} \in \{0, 1\} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_maintenance_capacity`**

```math
\mu^{f,\mathrm{nom}}_{\xi,t,l} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{com}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \mathrm{on}^{f}_{t,l}
```

**`Link_maintenance_status`**

```math
\mu^{f,u}_{\xi,t,l} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{com}^{f}_{l} \wedge \neg \left( \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \right) \wedge \mathrm{on}^{f}_{t,l}
```

**`Process_n_mod`**

```math
N^{z}_{j} \ge 0, N^{z}_{j} \in \mathbb{Z} \qquad \forall\, j \in \mathcal{J} \,:\, \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0
```

**`Process_status`**

```math
u^{z}_{\xi,t,j} \ge 0, u^{z}_{\xi,t,j} \in \mathbb{Z} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_start_up`**

```math
\mathit{up}^{z}_{\xi,t,j} \ge 0, \mathit{up}^{z}_{\xi,t,j} \in \mathbb{Z} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_shut_down`**

```math
\mathit{dn}^{z}_{\xi,t,j} \ge 0, \mathit{dn}^{z}_{\xi,t,j} \in \mathbb{Z} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_maintenance`**

```math
0 \le \mu^{z}_{\xi,t,j} \le 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{mnt}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_maintenance_start`**

```math
\mu^{z,\mathrm{up}}_{\xi,t,j} \in \{0, 1\} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{mnt}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_maintenance_capacity`**

```math
\mu^{z,\mathrm{nom}}_{\xi,t,j} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{mnt}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{com}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j}
```

**`Process_maintenance_status`**

```math
\mu^{z,u}_{\xi,t,j} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{mnt}^{z}_{j} \wedge \mathrm{com}^{z}_{j} \wedge \neg \left( \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \right) \wedge \mathrm{on}^{z}_{t,j}
```

**`Line_s`**

```math
s_{\xi,t,k} \in \mathbb{R} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K} \,:\, \mathrm{on}^{s}_{t,k}
```

**`Line_loss`**

```math
\ell_{\xi,t,k} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K} \,:\, \mathrm{lossy} \wedge \mathrm{on}^{s}_{t,k}
```

**`Transformer_s`**

```math
\sigma_{\xi,t,m} \in \mathbb{R} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M} \,:\, \mathrm{on}^{\sigma}_{t,m}
```

**`Transformer_loss`**

```math
\ell^{\sigma}_{\xi,t,m} \ge 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M} \,:\, \mathrm{lossy} \wedge \mathrm{on}^{\sigma}_{t,m}
```

**`Transformer_phase_shift`**

```math
\mathrm{Transformer\_phase\_shift\_min}_{m} \le \mathit{Transformer\_phase\_shift}_{\xi,t,m} \le \mathrm{Transformer\_phase\_shift\_max}_{m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M} \,:\, \mathrm{Transformer\_phase\_shift\_varying}_{m} \wedge \mathrm{on}^{\sigma}_{t,m}
```

**`Line_s_nom_ext`**

```math
S_{k} \in \mathbb{R} \qquad \forall\, k \in \mathcal{K} \,:\, \mathrm{ext}^{s}_{k}
```

**`Generator_p_nom_ext`**

```math
P_{g} \in \mathbb{R} \qquad \forall\, g \in \mathcal{G} \,:\, \mathrm{ext}_{g}
```

**`Link_p_nom_ext`**

```math
F_{l} \in \mathbb{R} \qquad \forall\, l \in \mathcal{L} \,:\, \mathrm{ext}^{f}_{l}
```

**`Process_p_nom_ext`**

```math
Z_{j} \in \mathbb{R} \qquad \forall\, j \in \mathcal{J} \,:\, \mathrm{ext}^{z}_{j}
```

**`Transformer_s_nom_ext`**

```math
\Sigma_{m} \in \mathbb{R} \qquad \forall\, m \in \mathcal{M} \,:\, \mathrm{ext}^{\sigma}_{m}
```

**`StorageUnit_p_nom_ext`**

```math
H_{s} \in \mathbb{R} \qquad \forall\, s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s}
```

**`Store_e_nom_ext`**

```math
E_{v} \in \mathbb{R} \qquad \forall\, v \in \mathcal{V} \,:\, \mathrm{ext}^{e}_{v}
```

**`CVaR_a`**

```math
a_{\xi} \ge 0 \qquad \forall\, \xi \in \Xi
```

**`CVaR_theta`**

```math
\theta \in \mathbb{R}
```

**`CVaR`**

```math
CVaR \in \mathbb{R}
```

### `Generator_maintenance_events_positive`

```yaml
Generator_maintenance_events_positive:
  holds: "Generator_maintenance_events > 0"
  where: "Generator_maintainable"
  description: >-
    a maintainable generator with no event schedules no maintenance —
    PyPSA refuses it (`consistency.py:1516`)
```

```math
\mathrm{n}^{\mathrm{mnt}}_{\xi,g} > 0 \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g}
```

### `Generator_maintenance_duration_positive`

```yaml
Generator_maintenance_duration_positive:
  holds: "Generator_maintenance_duration > 0"
  where: "Generator_maintainable"
  description: >-
    an event that covers no hours is no maintenance window — PyPSA
    refuses it (`consistency.py:1506`)
```

```math
\tau^{\mathrm{mnt}}_{\xi,g} > 0 \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g}
```

### `Generator_maintenance_duration_fits_the_horizon`

```yaml
Generator_maintenance_duration_fits_the_horizon:
  holds: "Generator_maintenance_duration <= sum(snapshot_weightings_generators, over=snapshot)"
  where: "Generator_maintainable"
  description: >-
    one event longer than the horizon, in generator weightings, blocks
    every start and makes the event count infeasible — PyPSA refuses it
    (`consistency.py:1527`)
```

```math
\tau^{\mathrm{mnt}}_{\xi,g} \le \sum_{t \in \mathcal{T}} \mathrm{w}^{\mathrm{gen}}_{t} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g}
```

### `Generator_maintenance_events_fit_the_horizon`

```yaml
Generator_maintenance_events_fit_the_horizon:
  holds: "Generator_maintenance_duration * Generator_maintenance_events <= sum(snapshot_weightings_generators, over=snapshot)"
  where: "Generator_maintainable"
  description: >-
    the events together longer than the horizon, in generator
    weightings, cannot all be scheduled — PyPSA refuses it
    (`consistency.py:1539`)
```

```math
\tau^{\mathrm{mnt}}_{\xi,g} \cdot \mathrm{n}^{\mathrm{mnt}}_{\xi,g} \le \sum_{t \in \mathcal{T}} \mathrm{w}^{\mathrm{gen}}_{t} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g}
```

### `Generator_maintenance_build_cap_is_finite`

```yaml
Generator_maintenance_build_cap_is_finite:
  holds: "Generator_p_nom_max < inf"
  where: "Generator_maintainable AND Generator_p_nom_extendable"
  description: >-
    the `maintcap` rows hold the chosen build in maintenance against
    `p_nom_max`, so an infinite cap is an infinite coefficient — PyPSA
    refuses it (`consistency.py:1551`)
```

```math
\overline{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} < \infty \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{ext}_{g}
```

### `Generator_maintenance_module_count_is_finite`

```yaml
Generator_maintenance_module_count_is_finite:
  holds: "Generator_p_nom_max < inf"
  where: "Generator_maintainable AND Generator_committable AND NOT Generator_p_nom_extendable AND Generator_p_nom_mod > 0"
  description: >-
    the `maint-modstatus` rows bound the modules on in maintenance by
    `p_nom_max / p_nom_mod`, so an infinite cap is an infinite
    coefficient. PyPSA does not check it, and HiGHS refuses the model
    (`constraints.py:500-503`)
```

```math
\overline{\mathrm{p}}^{\mathrm{nom}}_{\xi,g} < \infty \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{com}_{g} \wedge \neg \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0
```

### `Link_maintenance_events_positive`

```yaml
Link_maintenance_events_positive:
  holds: "Link_maintenance_events > 0"
  where: "Link_maintainable"
  description: >-
    a maintainable link with no event schedules no maintenance —
    PyPSA refuses it (`consistency.py:1516`)
```

```math
\mathrm{n}^{f,\mathrm{mnt}}_{\xi,l} > 0 \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l}
```

### `Link_maintenance_duration_positive`

```yaml
Link_maintenance_duration_positive:
  holds: "Link_maintenance_duration > 0"
  where: "Link_maintainable"
  description: >-
    an event that covers no hours is no maintenance window — PyPSA
    refuses it (`consistency.py:1506`)
```

```math
\tau^{f,\mathrm{mnt}}_{\xi,l} > 0 \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l}
```

### `Link_maintenance_duration_fits_the_horizon`

```yaml
Link_maintenance_duration_fits_the_horizon:
  holds: "Link_maintenance_duration <= sum(snapshot_weightings_generators, over=snapshot)"
  where: "Link_maintainable"
  description: >-
    one event longer than the horizon, in generator weightings, blocks
    every start and makes the event count infeasible — PyPSA refuses it
    (`consistency.py:1527`)
```

```math
\tau^{f,\mathrm{mnt}}_{\xi,l} \le \sum_{t \in \mathcal{T}} \mathrm{w}^{\mathrm{gen}}_{t} \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l}
```

### `Link_maintenance_events_fit_the_horizon`

```yaml
Link_maintenance_events_fit_the_horizon:
  holds: "Link_maintenance_duration * Link_maintenance_events <= sum(snapshot_weightings_generators, over=snapshot)"
  where: "Link_maintainable"
  description: >-
    the events together longer than the horizon, in generator
    weightings, cannot all be scheduled — PyPSA refuses it
    (`consistency.py:1539`)
```

```math
\tau^{f,\mathrm{mnt}}_{\xi,l} \cdot \mathrm{n}^{f,\mathrm{mnt}}_{\xi,l} \le \sum_{t \in \mathcal{T}} \mathrm{w}^{\mathrm{gen}}_{t} \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l}
```

### `Link_maintenance_build_cap_is_finite`

```yaml
Link_maintenance_build_cap_is_finite:
  holds: "Link_p_nom_max < inf"
  where: "Link_maintainable AND Link_p_nom_extendable"
  description: >-
    the `maintcap` rows hold the chosen build in maintenance against
    `p_nom_max`, so an infinite cap is an infinite coefficient — PyPSA
    refuses it (`consistency.py:1551`)
```

```math
\overline{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} < \infty \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{ext}^{f}_{l}
```

### `Link_maintenance_module_count_is_finite`

```yaml
Link_maintenance_module_count_is_finite:
  holds: "Link_p_nom_max < inf"
  where: "Link_maintainable AND Link_committable AND NOT Link_p_nom_extendable AND Link_p_nom_mod > 0"
  description: >-
    the `maint-modstatus` rows bound the modules on in maintenance by
    `p_nom_max / p_nom_mod`, so an infinite cap is an infinite
    coefficient. PyPSA does not check it, and HiGHS refuses the model
    (`constraints.py:500-503`)
```

```math
\overline{\mathrm{f}}^{\mathrm{nom}}_{\xi,l} < \infty \qquad \forall\, \xi \in \Xi,\ l \in \mathcal{L} \,:\, \mathrm{mnt}^{f}_{l} \wedge \mathrm{com}^{f}_{l} \wedge \neg \mathrm{ext}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0
```

### `Process_maintenance_events_positive`

```yaml
Process_maintenance_events_positive:
  holds: "Process_maintenance_events > 0"
  where: "Process_maintainable"
  description: >-
    a maintainable process with no event schedules no maintenance —
    PyPSA refuses it (`consistency.py:1516`)
```

```math
\mathrm{n}^{z,\mathrm{mnt}}_{\xi,j} > 0 \qquad \forall\, \xi \in \Xi,\ j \in \mathcal{J} \,:\, \mathrm{mnt}^{z}_{j}
```

### `Process_maintenance_duration_positive`

```yaml
Process_maintenance_duration_positive:
  holds: "Process_maintenance_duration > 0"
  where: "Process_maintainable"
  description: >-
    an event that covers no hours is no maintenance window — PyPSA
    refuses it (`consistency.py:1506`)
```

```math
\tau^{z,\mathrm{mnt}}_{\xi,j} > 0 \qquad \forall\, \xi \in \Xi,\ j \in \mathcal{J} \,:\, \mathrm{mnt}^{z}_{j}
```

### `Process_maintenance_duration_fits_the_horizon`

```yaml
Process_maintenance_duration_fits_the_horizon:
  holds: "Process_maintenance_duration <= sum(snapshot_weightings_generators, over=snapshot)"
  where: "Process_maintainable"
  description: >-
    one event longer than the horizon, in generator weightings, blocks
    every start and makes the event count infeasible — PyPSA refuses it
    (`consistency.py:1527`)
```

```math
\tau^{z,\mathrm{mnt}}_{\xi,j} \le \sum_{t \in \mathcal{T}} \mathrm{w}^{\mathrm{gen}}_{t} \qquad \forall\, \xi \in \Xi,\ j \in \mathcal{J} \,:\, \mathrm{mnt}^{z}_{j}
```

### `Process_maintenance_events_fit_the_horizon`

```yaml
Process_maintenance_events_fit_the_horizon:
  holds: "Process_maintenance_duration * Process_maintenance_events <= sum(snapshot_weightings_generators, over=snapshot)"
  where: "Process_maintainable"
  description: >-
    the events together longer than the horizon, in generator
    weightings, cannot all be scheduled — PyPSA refuses it
    (`consistency.py:1539`)
```

```math
\tau^{z,\mathrm{mnt}}_{\xi,j} \cdot \mathrm{n}^{z,\mathrm{mnt}}_{\xi,j} \le \sum_{t \in \mathcal{T}} \mathrm{w}^{\mathrm{gen}}_{t} \qquad \forall\, \xi \in \Xi,\ j \in \mathcal{J} \,:\, \mathrm{mnt}^{z}_{j}
```

### `Process_maintenance_build_cap_is_finite`

```yaml
Process_maintenance_build_cap_is_finite:
  holds: "Process_p_nom_max < inf"
  where: "Process_maintainable AND Process_p_nom_extendable"
  description: >-
    the `maintcap` rows hold the chosen build in maintenance against
    `p_nom_max`, so an infinite cap is an infinite coefficient — PyPSA
    refuses it (`consistency.py:1551`)
```

```math
\overline{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} < \infty \qquad \forall\, \xi \in \Xi,\ j \in \mathcal{J} \,:\, \mathrm{mnt}^{z}_{j} \wedge \mathrm{ext}^{z}_{j}
```

### `Process_maintenance_module_count_is_finite`

```yaml
Process_maintenance_module_count_is_finite:
  holds: "Process_p_nom_max < inf"
  where: "Process_maintainable AND Process_committable AND NOT Process_p_nom_extendable AND Process_p_nom_mod > 0"
  description: >-
    the `maint-modstatus` rows bound the modules on in maintenance by
    `p_nom_max / p_nom_mod`, so an infinite cap is an infinite
    coefficient. PyPSA does not check it, and HiGHS refuses the model
    (`constraints.py:500-503`)
```

```math
\overline{\mathrm{z}}^{\mathrm{nom}}_{\xi,j} < \infty \qquad \forall\, \xi \in \Xi,\ j \in \mathcal{J} \,:\, \mathrm{mnt}^{z}_{j} \wedge \mathrm{com}^{z}_{j} \wedge \neg \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0
```

### `StorageUnit_stands_in_one_run`

```yaml
StorageUnit_stands_in_one_run:
  holds: "count(StorageUnit_active AND NOT shift(StorageUnit_active, along=snapshot, offset=1), over=snapshot) <= 1"
  description: >-
    the snapshots a storage unit stands in are one unbroken run, as a build
    year and a lifetime make them. The opening row holds at the first
    of them only, and a cyclic storage unit reaches back
    `StorageUnit_inactive_snapshots` further to the last of them
```

```math
\lvert \{ t \in \mathcal{T} \,:\, \mathrm{on}^{h}_{t,s} \wedge \neg \mathrm{on}^{h}_{t - 1,s} \} \rvert \le 1 \qquad \forall\, s \in \mathcal{S}
```

### `StorageUnit_opens_late_only_where_it_opens`

```yaml
StorageUnit_opens_late_only_where_it_opens:
  holds: "StorageUnit_active AND NOT shift(StorageUnit_active, along=snapshot, offset=1) AND position(snapshot) > 0"
  where: "StorageUnit_opens_late"
  description: >-
    `StorageUnit_opens_late` marks the first snapshot the storage unit stands in, past
    the first of the horizon, and no other
```

```math
\mathrm{on}^{h}_{t,s} \wedge \neg \mathrm{on}^{h}_{t - 1,s} \wedge \mathrm{pos}(t) > 0 \qquad \forall\, t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{open}_{t,s}
```

### `StorageUnit_opens_late_where_it_opens`

```yaml
StorageUnit_opens_late_where_it_opens:
  holds: "StorageUnit_opens_late"
  where: "StorageUnit_active AND NOT shift(StorageUnit_active, along=snapshot, offset=1) AND position(snapshot) > 0"
  description: >-
    a storage unit that opens past the first snapshot of the horizon opens on
    its initial level, or its last level where it is cyclic, only where
    `StorageUnit_opens_late` marks the snapshot
```

```math
\mathrm{open}_{t,s} \qquad \forall\, t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{on}^{h}_{t,s} \wedge \neg \mathrm{on}^{h}_{t - 1,s} \wedge \mathrm{pos}(t) > 0
```

### `Store_stands_in_one_run`

```yaml
Store_stands_in_one_run:
  holds: "count(Store_active AND NOT shift(Store_active, along=snapshot, offset=1), over=snapshot) <= 1"
  description: >-
    the snapshots a store stands in are one unbroken run, as a build
    year and a lifetime make them. The opening row holds at the first
    of them only, and a cyclic store reaches back
    `Store_inactive_snapshots` further to the last of them
```

```math
\lvert \{ t \in \mathcal{T} \,:\, \mathrm{on}^{e}_{t,v} \wedge \neg \mathrm{on}^{e}_{t - 1,v} \} \rvert \le 1 \qquad \forall\, v \in \mathcal{V}
```

### `Store_opens_late_only_where_it_opens`

```yaml
Store_opens_late_only_where_it_opens:
  holds: "Store_active AND NOT shift(Store_active, along=snapshot, offset=1) AND position(snapshot) > 0"
  where: "Store_opens_late"
  description: >-
    `Store_opens_late` marks the first snapshot the store stands in, past
    the first of the horizon, and no other
```

```math
\mathrm{on}^{e}_{t,v} \wedge \neg \mathrm{on}^{e}_{t - 1,v} \wedge \mathrm{pos}(t) > 0 \qquad \forall\, t \in \mathcal{T},\ v \in \mathcal{V} \,:\, \mathrm{open}^{e}_{t,v}
```

### `Store_opens_late_where_it_opens`

```yaml
Store_opens_late_where_it_opens:
  holds: "Store_opens_late"
  where: "Store_active AND NOT shift(Store_active, along=snapshot, offset=1) AND position(snapshot) > 0"
  description: >-
    a store that opens past the first snapshot of the horizon opens on
    its initial level, or its last level where it is cyclic, only where
    `Store_opens_late` marks the snapshot
```

```math
\mathrm{open}^{e}_{t,v} \qquad \forall\, t \in \mathcal{T},\ v \in \mathcal{V} \,:\, \mathrm{on}^{e}_{t,v} \wedge \neg \mathrm{on}^{e}_{t - 1,v} \wedge \mathrm{pos}(t) > 0
```

### `StorageUnit_primary_energy_per_period_closes_over_the_horizon`

```yaml
StorageUnit_primary_energy_per_period_closes_over_the_horizon:
  holds: "count(NOT GlobalConstraint_counts_snapshot, over=snapshot) == 0"
  where: "StorageUnit_primary_energy_weight AND StorageUnit_state_of_charge_initial_per_period"
  description: >-
    PyPSA reads the closing charge of a unit that reopens per period at
    the last snapshot of every period, and fails on a `primary_energy` row
    that names an `investment_period` (`global_constraints.py:474`)
```

```math
\lvert \{ t \in \mathcal{T} \,:\, \neg \mathrm{in}_{\xi,i,t} \} \rvert = 0 \qquad \forall\, \xi \in \Xi,\ s \in \mathcal{S},\ i \in \mathcal{I} \,:\, \mathrm{a}^{h}_{\xi,i,s} \text{ is defined} \wedge \mathrm{reset}_{\xi,s}
```

### `StorageUnit_primary_energy_carried_over_has_unit_years`

```yaml
StorageUnit_primary_energy_carried_over_has_unit_years:
  holds: "period_weight_years == 1"
  where: "StorageUnit_primary_energy_weight AND NOT StorageUnit_state_of_charge_initial_per_period"
  description: >-
    a unit that carries its charge from one period to the next closes
    once, at the last counted snapshot, and no period's years weighs that
    level — PyPSA refuses it where any period's years is not one
    (`global_constraints.py:448`)
```

```math
\mathrm{w}^{\mathrm{yr}}_{y} = 1 \qquad \forall\, \xi \in \Xi,\ s \in \mathcal{S},\ i \in \mathcal{I},\ y \in \mathcal{Y} \,:\, \mathrm{a}^{h}_{\xi,i,s} \text{ is defined} \wedge \neg \mathrm{reset}_{\xi,s}
```

### `StorageUnit_operational_limit_carried_over_has_unit_years`

```yaml
StorageUnit_operational_limit_carried_over_has_unit_years:
  holds: "at(period_weight_years == 1, by=snapshot_period, over=period, into=snapshot)"
  where: "StorageUnit_operational_limit_weight AND NOT StorageUnit_state_of_charge_initial_per_period AND GlobalConstraint_counts_snapshot"
  description: >-
    the same for an `operational_limit` row, over the periods it counts —
    PyPSA refuses it (`global_constraints.py:647`)
```

```math
\mathrm{w}^{\mathrm{yr}}_{\mathrm{snapshot\_period}(t)} = 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S},\ i \in \mathcal{I} \,:\, \mathrm{b}^{h}_{\xi,i,s} \text{ is defined} \wedge \neg \mathrm{reset}_{\xi,s} \wedge \mathrm{in}_{\xi,i,t}
```

### `Store_primary_energy_per_period_closes_over_the_horizon`

```yaml
Store_primary_energy_per_period_closes_over_the_horizon:
  holds: "count(NOT GlobalConstraint_counts_snapshot, over=snapshot) == 0"
  where: "Store_primary_energy_weight AND Store_e_initial_per_period"
  description: >-
    PyPSA reads the closing energy of a store that reopens per period at
    the last snapshot of every period, and fails on a `primary_energy` row
    that names an `investment_period` (`global_constraints.py:526`)
```

```math
\lvert \{ t \in \mathcal{T} \,:\, \neg \mathrm{in}_{\xi,i,t} \} \rvert = 0 \qquad \forall\, \xi \in \Xi,\ v \in \mathcal{V},\ i \in \mathcal{I} \,:\, \mathrm{a}^{e}_{\xi,i,v} \text{ is defined} \wedge \mathrm{reset}^{e}_{\xi,v}
```

### `Store_primary_energy_carried_over_has_unit_years`

```yaml
Store_primary_energy_carried_over_has_unit_years:
  holds: "period_weight_years == 1"
  where: "Store_primary_energy_weight AND NOT Store_e_initial_per_period"
  description: >-
    a store that carries its energy from one period to the next closes
    once, at the last counted snapshot, and no period's years weighs that
    level — PyPSA refuses it where any period's years is not one
    (`global_constraints.py:500`)
```

```math
\mathrm{w}^{\mathrm{yr}}_{y} = 1 \qquad \forall\, \xi \in \Xi,\ v \in \mathcal{V},\ i \in \mathcal{I},\ y \in \mathcal{Y} \,:\, \mathrm{a}^{e}_{\xi,i,v} \text{ is defined} \wedge \neg \mathrm{reset}^{e}_{\xi,v}
```

### `Store_operational_limit_carried_over_has_unit_years`

```yaml
Store_operational_limit_carried_over_has_unit_years:
  holds: "at(period_weight_years == 1, by=snapshot_period, over=period, into=snapshot)"
  where: "Store_operational_limit_weight AND NOT Store_e_initial_per_period AND GlobalConstraint_counts_snapshot"
  description: >-
    the same for an `operational_limit` row, over the periods it counts —
    PyPSA refuses it (`global_constraints.py:695`)
```

```math
\mathrm{w}^{\mathrm{yr}}_{\mathrm{snapshot\_period}(t)} = 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ v \in \mathcal{V},\ i \in \mathcal{I} \,:\, \mathrm{b}^{e}_{\xi,i,v} \text{ is defined} \wedge \neg \mathrm{reset}^{e}_{\xi,v} \wedge \mathrm{in}_{\xi,i,t}
```

### `Generator_marginal_cost_quadratic_without_risk_preference`

```yaml
Generator_marginal_cost_quadratic_without_risk_preference:
  holds: "Generator_marginal_cost_quadratic == 0"
  where: "CVaR_omega > 0"
  description: >-
    a quadratic cost puts a square into every `CVaR-excess` row, and PyPSA
    refuses quadratic costs under any risk preference
    (`optimize.py:467-474`). The spec cannot tell no risk preference from
    one with `omega = 0`, so it refuses only where `omega` is positive
```

```math
\mathrm{c}^{(2)}_{\xi,t,g} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \omega > 0
```

### `Link_marginal_cost_quadratic_without_risk_preference`

```yaml
Link_marginal_cost_quadratic_without_risk_preference:
  holds: "Link_marginal_cost_quadratic == 0"
  where: "CVaR_omega > 0"
  description: >-
    a quadratic cost puts a square into every `CVaR-excess` row, and PyPSA
    refuses quadratic costs under any risk preference
    (`optimize.py:467-474`). The spec cannot tell no risk preference from
    one with `omega = 0`, so it refuses only where `omega` is positive
```

```math
\mathrm{c}^{f,(2)}_{\xi,t,l} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \omega > 0
```

### `Process_marginal_cost_quadratic_without_risk_preference`

```yaml
Process_marginal_cost_quadratic_without_risk_preference:
  holds: "Process_marginal_cost_quadratic == 0"
  where: "CVaR_omega > 0"
  description: >-
    a quadratic cost puts a square into every `CVaR-excess` row, and PyPSA
    refuses quadratic costs under any risk preference
    (`optimize.py:467-474`). The spec cannot tell no risk preference from
    one with `omega = 0`, so it refuses only where `omega` is positive
```

```math
\mathrm{c}^{z,(2)}_{\xi,t,j} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \omega > 0
```

### `StorageUnit_marginal_cost_quadratic_without_risk_preference`

```yaml
StorageUnit_marginal_cost_quadratic_without_risk_preference:
  holds: "StorageUnit_marginal_cost_quadratic == 0"
  where: "CVaR_omega > 0"
  description: >-
    a quadratic cost puts a square into every `CVaR-excess` row, and PyPSA
    refuses quadratic costs under any risk preference
    (`optimize.py:467-474`). The spec cannot tell no risk preference from
    one with `omega = 0`, so it refuses only where `omega` is positive
```

```math
\mathrm{c}^{h,(2)}_{\xi,t,s} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \omega > 0
```

### `Store_marginal_cost_quadratic_without_risk_preference`

```yaml
Store_marginal_cost_quadratic_without_risk_preference:
  holds: "Store_marginal_cost_quadratic == 0"
  where: "CVaR_omega > 0"
  description: >-
    a quadratic cost puts a square into every `CVaR-excess` row, and PyPSA
    refuses quadratic costs under any risk preference
    (`optimize.py:467-474`). The spec cannot tell no risk preference from
    one with `omega = 0`, so it refuses only where `omega` is positive
```

```math
\mathrm{c}^{q,(2)}_{\xi,t,v} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ v \in \mathcal{V} \,:\, \omega > 0
```

### `GlobalConstraint_tech_capacity_expansion_limit_without_scenarios`

```yaml
GlobalConstraint_tech_capacity_expansion_limit_without_scenarios:
  holds: "GlobalConstraint_type != 'tech_capacity_expansion_limit'"
  where: "count(scenario_weight, over=scenario) > 1"
  description: >-
    PyPSA does not build a `tech_capacity_expansion_limit` row on a
    network with scenarios and refuses it
    (`global_constraints.py:66-68`). The spec cannot tell a network with
    one scenario from one with none, so it refuses only where there is
    more than one scenario
```

```math
\mathrm{type}_{i} \neq \text{'}\mathrm{tech\_capacity\_expansion\_limit}\text{'} \qquad \forall\, i \in \mathcal{I} \,:\, \lvert \{ \xi \in \Xi \,:\, \pi_{\xi} \text{ is defined} \} \rvert > 1
```

### `Generator_came_in_running_unless_committable`

```yaml
Generator_came_in_running_unless_committable:
  holds: "Generator_status_initial == 1"
  where: "NOT Generator_committable AND (Generator_ramp_limit_up OR Generator_ramp_limit_down)"
  description: >-
    PyPSA reads `up_time_before` of a unit that is not committable in its
    ramp rows. Where it is zero, PyPSA builds a row at the first snapshot
    with nothing carried in, and caps the unit there at zero, or at its
    start-up ramp where another unit of the component is committable with a
    fixed build (`constraints.py:1091-1094`, `1110-1112`). PyPSA documents
    the attribute as read only for a committable unit and does not check
    it. PyPSA has not decided which row is intended (PyPSA/PyPSA#1943). The
    spec does not state that row, so it refuses the data
```

```math
\mathrm{u}^{0}_{\xi,g} = 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \neg \mathrm{com}_{g} \wedge \left( \mathrm{ru}_{\xi,t,g} \text{ is defined} \vee \mathrm{rd}_{\xi,t,g} \text{ is defined} \right)
```

### `Link_came_in_running_unless_committable`

```yaml
Link_came_in_running_unless_committable:
  holds: "Link_status_initial == 1"
  where: "NOT Link_committable AND (Link_ramp_limit_up OR Link_ramp_limit_down)"
  description: >-
    PyPSA reads `up_time_before` of a link that is not committable in its
    ramp rows. Where it is zero, PyPSA builds a row at the first snapshot
    with nothing carried in, and caps the link there at zero, or at its
    start-up ramp where another link of the component is committable with a
    fixed build (`constraints.py:1091-1094`, `1110-1112`). PyPSA documents
    the attribute as read only for a committable link and does not check
    it. PyPSA has not decided which row is intended (PyPSA/PyPSA#1943). The
    spec does not state that row, so it refuses the data
```

```math
\mathrm{u}^{f,0}_{\xi,l} = 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \neg \mathrm{com}^{f}_{l} \wedge \left( \mathrm{ru}^{f}_{\xi,t,l} \text{ is defined} \vee \mathrm{rd}^{f}_{\xi,t,l} \text{ is defined} \right)
```

### `Process_came_in_running_unless_committable`

```yaml
Process_came_in_running_unless_committable:
  holds: "Process_status_initial == 1"
  where: "NOT Process_committable AND (Process_ramp_limit_up OR Process_ramp_limit_down)"
  description: >-
    PyPSA reads `up_time_before` of a process that is not committable in its
    ramp rows. Where it is zero, PyPSA builds a row at the first snapshot
    with nothing carried in, and caps the process there at zero, or at its
    start-up ramp where another process of the component is committable with a
    fixed build (`constraints.py:1091-1094`, `1110-1112`). PyPSA documents
    the attribute as read only for a committable process and does not check
    it. PyPSA has not decided which row is intended (PyPSA/PyPSA#1943). The
    spec does not state that row, so it refuses the data
```

```math
\mathrm{u}^{z,0}_{\xi,j} = 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \neg \mathrm{com}^{z}_{j} \wedge \left( \mathrm{ru}^{z}_{\xi,t,j} \text{ is defined} \vee \mathrm{rd}^{z}_{\xi,t,j} \text{ is defined} \right)
```
<!-- gallery:end -->

Regenerate with `pixi run python -m tools.gallery`.
