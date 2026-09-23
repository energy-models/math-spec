<!--
SPDX-FileCopyrightText: math-spec contributors
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
scope or version the note names. A name carrying `{k}` or `{s}` stands for the
family PyPSA numbers per segment or scenario.

Each rung's banner states what PyPSA solved its reference network to.

<!-- reference:spine:begin -->
> Every rung's network is `spine.build()` plus the rung's own `n.add` calls, data inline; a keyword not passed is PyPSA's default. A banner states what PyPSA solved the rung to; how an engine binds the network to the file, and what it makes of it, is that engine's own record.

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
| `Bus-meshed-*-nodal_balance`                        | out    | the same balance rows, dealt into linopy containers by how many component columns name a bus — `meshed_thresholds`, an `n.optimize()` keyword defaulting to `[30, 100, 400]`. Same rows, same duals, another name; a modeler whose engine wants the split states it, the file does not (#123) |
| [`marginal_cost`](#objective)                       | done   |                                                            |
| [`marginal_cost_quadratic`](#objective)             | done   | rung 10, below; Generator and Link — PyPSA also carries it on storage units and stores, one more term each of the same shape |
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
| [`StorageUnit-p_set`](#storageunit-p_set), [`{c}-{attr}_set`](#generator-p_set) | done | `Generator-p_set`, `Link-p_set`, `StorageUnit-state_of_charge_set`, `Store-e_set`, `Line-s_set` |
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
| [`primary_energy`](#primary_energy)   | split       | a block per sense — sense as data is beyond #70; carrier weights and the horizon-end charge read are prep |
| [`operational_limit`](#operational_limit) | split   | a block per sense                                 |
| [`transmission_volume_expansion_limit`](#transmission_volume_expansion_limit) | split | a block per sense; membership from PyPSA's carrier string is prep |
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
| [`stand_by_cost`, `start_up_cost`, `shut_down_cost`](#objective) | done |                                           |
| [`{c}-com-p-before/-current/-partly-*`](pypsa_linearized_uc.md) | done | rung 12, a file of its own                          |

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
it stands for. Generator and Link carry it here; PyPSA also carries it on
storage units and stores, one more term each of the same shape. A plain run
feeds zero, so the term vanishes and the objective stays linear.

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
# SPDX-FileCopyrightText: math-spec Contributors
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
# SPDX-FileCopyrightText: math-spec Contributors
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
# SPDX-FileCopyrightText: math-spec Contributors
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
`omega`.

| PyPSA | status | note |
| --- | --- | --- |
| [`Generator-p`, `Link-p`](#variable-domains) | done | over `scenario`; `Generator-p_nom` is not — chosen once |
| [`Generator-fix-p-*`, `-ext-p-*`, `Link-fix-p-*`, `Bus-nodal_balance`](#generator-fix-p-lower) | done | rungs 1 and 3, over `scenario` |
| [`CVaR-a`, `CVaR-theta`, `CVaR`](#variable-domains) | done | |
| [`CVaR-excess-{s}`](#cvar-excess-s) | split | PyPSA names a row per scenario; one block over the dimension |
| [`CVaR-def`](#cvar-def) | done | `1 / (1 - alpha)` is data prep |
| [objective](#objective) | done | capacity once; operation `(1 - omega)` in expectation, `omega` at the tail |

<!-- reference:rung_14_stochastic:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `9267.386666666665`, 87 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_14_stochastic.py`

```python
# SPDX-FileCopyrightText: math-spec Contributors
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
| [objective](#objective) | done | period weight on operation; capacity once per period it stands in |
| [`StorageUnit-energy_balance`](#storageunit-energy_balance), [`Store-energy_balance`](#store-energy_balance) per period, ramps at period starts | done | rung 29 |

<!-- reference:rung_15_multi_period:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `12747.19109626398`, 80 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_15_multi_period.py`

```python
# SPDX-FileCopyrightText: math-spec Contributors
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
# SPDX-FileCopyrightText: math-spec Contributors
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
    (`cyclic_delay`), which is what the model's ``cases:`` block turns on.
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
# SPDX-FileCopyrightText: math-spec Contributors
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
# SPDX-FileCopyrightText: math-spec Contributors
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
# SPDX-FileCopyrightText: math-spec Contributors
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
components that carry a carrier attribute; the spec extends the same limit to
transformers, which PyPSA leaves out.

<!-- reference:rung_21_carrier_growth:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `8452.5`, 74 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_21_carrier_growth.py`

```python
# SPDX-FileCopyrightText: math-spec Contributors
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
# SPDX-FileCopyrightText: math-spec Contributors
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
# SPDX-FileCopyrightText: math-spec Contributors
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
# SPDX-FileCopyrightText: math-spec Contributors
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
# SPDX-FileCopyrightText: math-spec Contributors
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
# SPDX-FileCopyrightText: math-spec Contributors
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
# SPDX-FileCopyrightText: math-spec Contributors
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
# SPDX-FileCopyrightText: math-spec Contributors
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
# SPDX-FileCopyrightText: math-spec Contributors
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

## Refusals

Where PyPSA refuses to build, parity means refusing too. None is a language
gap; each is a data check not made yet, and where it should live — language,
data prep, or harness — is one open question. Line numbers are pinned pypsa
1.3.0, the version the records above are from.

| PyPSA raises                                 | on                                                | here                    | note |
| -------------------------------------------- | ------------------------------------------------- | ----------------------- | ---- |
| `ValueError`, `constraints.py:1850`          | fixed modular `p_nom` not a multiple of `p_nom_mod` | a fractional module cap | X1   |
| `ValueError`, `constraints.py:1557`          | load on a bus with nothing attached               | row not built, unserved | X2   |
| `ValueError`, `optimize.py:436`              | no component carries a cost                       | feasibility problem     | X3   |
| `NotImplementedError`, `global_constraints.py:457` | depletion with period weightings `!= 1`     | out                     |      |
| `ValueError`, `constraints.py:2411`, `:2518` | an extendable lossy branch with `s_nom_max = inf`, either mode | data prep, at `Line_loss_max` and `Transformer_loss_max` | X4   |
| `RuntimeError`, `constraints.py:2561`        | the secant loop passing `max_segments`            | data prep, at the `segment` axis | X4   |

Duals and solutions are read back by the harness on the lpspec side:
`marginal_price` is the balance dual over `w_objective`, `mu_upper` the
concatenation of the regime blocks, `p0`/`p1` derived from `Link-p`.

## The file

<!-- gallery:begin -->
A plain `n.optimize()`, and its multi-period and stochastic classes, in one file. Every second-stage quantity spans a `scenario` (a future dispatch is chosen in) and every asset stands in the investment `period`s its build year and lifetime span. Capacity is chosen once, before the future is known, and paid once per active period; operation is the expectation over the scenarios' weights, with a share priced at the tail through the CVaR rows. A plain run feeds one scenario, one period, all-active masks and unit weights, and the model collapses to the standard one. Which snapshots an asset is active in, and a scenario's weight, are data prep.

#### Sets

| Symbol | Meaning |
|---|---|
| $`\Xi`$ | index $`\xi`$ — `scenario` — the futures dispatch is chosen in, each with a weight |
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` with $`\mathrm{snapshot\_period}: \mathcal{T} \to \mathcal{Y}`$ — dispatch periods |
| $`\mathcal{N}`$ | index $`n`$ — `bus` with $`\mathrm{Generator\_bus}: \mathcal{G} \to \mathcal{N},\ \mathrm{Link\_bus0}: \mathcal{L} \to \mathcal{N},\ \mathrm{Link\_output\_bus}: \mathcal{O} \to \mathcal{N},\ \mathrm{Process\_output\_bus}: \mathcal{R} \to \mathcal{N},\ \mathrm{Load\_bus}: \mathcal{D} \to \mathcal{N},\ \mathrm{StorageUnit\_bus}: \mathcal{S} \to \mathcal{N},\ \mathrm{Line\_bus0}: \mathcal{K} \to \mathcal{N},\ \mathrm{Line\_bus1}: \mathcal{K} \to \mathcal{N},\ \mathrm{Store\_bus}: \mathcal{V} \to \mathcal{N},\ \mathrm{Transformer\_bus0}: \mathcal{M} \to \mathcal{N},\ \mathrm{Transformer\_bus1}: \mathcal{M} \to \mathcal{N}`$ — network nodes |
| $`\mathcal{G}`$ | index $`g`$ — `generator` with $`\mathrm{Generator\_carrier}: \mathcal{G} \to \mathcal{I},\ \mathrm{Generator\_bus}: \mathcal{G} \to \mathcal{N}`$ — generating units, each on one bus |
| $`\mathcal{L}`$ | index $`l`$ — `link` with $`\mathrm{Link\_carrier}: \mathcal{L} \to \mathcal{I},\ \mathrm{Link\_bus0}: \mathcal{L} \to \mathcal{N},\ \mathrm{Link\_output\_link}: \mathcal{O} \to \mathcal{L}`$ — controllable connections, each from one bus to the buses it delivers to |
| $`\mathcal{O}`$ | index $`o`$ — `link_output` with $`\mathrm{Link\_output\_link}: \mathcal{O} \to \mathcal{L},\ \mathrm{Link\_output\_bus}: \mathcal{O} \to \mathcal{N}`$ — a link's output ports, one label per port a link declares — PyPSA's `bus1`, `bus2`, … columns read long, so a link of any number of output ports is one term in the balance, data prep |
| $`\mathcal{J}`$ | index $`j`$ — `process` with $`\mathrm{Process\_carrier}: \mathcal{J} \to \mathcal{I},\ \mathrm{Process\_output\_process}: \mathcal{R} \to \mathcal{J}`$ — generalized multi-port converters, each with an internal power that every port draws or delivers at its own rate |
| $`\mathcal{R}`$ | index $`r`$ — `process_output` with $`\mathrm{Process\_output\_process}: \mathcal{R} \to \mathcal{J},\ \mathrm{Process\_output\_bus}: \mathcal{R} \to \mathcal{N}`$ — a process's ports, one label per port a process declares — PyPSA's `bus0`, `bus1`, … each carry a signed `rate`, so a process of any number of ports is one term in the balance, data prep |
| $`\mathcal{D}`$ | index $`d`$ — `load` with $`\mathrm{Load\_bus}: \mathcal{D} \to \mathcal{N}`$ — demands, each on one bus |
| $`\mathcal{S}`$ | index $`s`$ — `storage_unit` with $`\mathrm{StorageUnit\_carrier}: \mathcal{S} \to \mathcal{I},\ \mathrm{StorageUnit\_bus}: \mathcal{S} \to \mathcal{N}`$ — storage units, dispatch and store behind one bus connection |
| $`\mathcal{V}`$ | index $`v`$ — `store` with $`\mathrm{Store\_carrier}: \mathcal{V} \to \mathcal{I},\ \mathrm{Store\_bus}: \mathcal{V} \to \mathcal{N}`$ — pure energy stores, each on one bus |
| $`\mathcal{K}`$ | index $`k`$ — `line` with $`\mathrm{Line\_carrier}: \mathcal{K} \to \mathcal{I},\ \mathrm{Line\_bus0}: \mathcal{K} \to \mathcal{N},\ \mathrm{Line\_bus1}: \mathcal{K} \to \mathcal{N}`$ — passive branches, each between two buses, their flow set by impedance |
| $`\mathcal{M}`$ | index $`m`$ — `transformer` with $`\mathrm{Transformer\_carrier}: \mathcal{M} \to \mathcal{I},\ \mathrm{Transformer\_bus0}: \mathcal{M} \to \mathcal{N},\ \mathrm{Transformer\_bus1}: \mathcal{M} \to \mathcal{N}`$ — passive branches between two buses, their flow set by impedance and tap ratio, with a phase shift fixed or optimised |
| $`\mathcal{C}`$ | index $`c`$ — `cycle` — independent cycles of the passive network graph — the cycle basis, data prep |
| $`\mathcal{B}`$ | index $`b`$ — `segment` — the cuts a passive branch's loss curve is held above — PyPSA's tangents, as many as its `segments` count, or its secants, as many as its tolerance loop places; none in a lossless run |
| $`\mathcal{I}`$ | index $`i`$ — `global_constraint` — PyPSA's `GlobalConstraint` rows, one label per declared limit |
| $`\mathcal{Y}`$ | index $`y`$ — `period` with $`\mathrm{snapshot\_period}: \mathcal{T} \to \mathcal{Y}`$ — investment periods — PyPSA's `investment_periods` |
| $`\mathcal{I}`$ | index $`i`$ — `carrier` with $`\mathrm{Generator\_carrier}: \mathcal{G} \to \mathcal{I},\ \mathrm{Link\_carrier}: \mathcal{L} \to \mathcal{I},\ \mathrm{Process\_carrier}: \mathcal{J} \to \mathcal{I},\ \mathrm{StorageUnit\_carrier}: \mathcal{S} \to \mathcal{I},\ \mathrm{Line\_carrier}: \mathcal{K} \to \mathcal{I},\ \mathrm{Store\_carrier}: \mathcal{V} \to \mathcal{I},\ \mathrm{Transformer\_carrier}: \mathcal{M} \to \mathcal{I}`$ — energy carriers, what a growth limit is set per |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{w}`$ | `snapshot_weightings_objective` over $`\mathcal{T}`$ — PyPSA's `snapshot_weightings.objective` — hours a snapshot stands for in the cost |
| $`\mathrm{p}^{\mathrm{nom}}`$ | `Generator_p_nom` over $`\mathcal{G}`$ — nominal power |
| $`\mathrm{ext}`$ | `Generator_p_nom_extendable` over $`\mathcal{G}`$ — whether the nominal power is a decision |
| $`\underline{\mathrm{p}}`$ | `Generator_p_min_pu` over $`\mathcal{T} \times \mathcal{G}`$ — least output, per unit of nominal power |
| $`\overline{\mathrm{p}}`$ | `Generator_p_max_pu` over $`\mathcal{T} \times \mathcal{G}`$ — most output, per unit of nominal power — an availability profile |
| $`\mathrm{c}`$ | `Generator_marginal_cost` over $`\mathcal{T} \times \mathcal{G}`$ — cost of one unit of output |
| $`\mathrm{c}^{(2)}`$ | `Generator_marginal_cost_quadratic` over $`\mathcal{T} \times \mathcal{G}`$ — cost of the square of one unit of output |
| $`\mathrm{com}`$ | `Generator_committable` over $`\mathcal{G}`$ — whether output is gated by an on/off status decision |
| $`\mathrm{ru}`$ | `Generator_ramp_limit_up` over $`\mathcal{G}`$ — most a generator may raise its output between snapshots, per unit of nominal power; no value means no limit |
| $`\mathrm{rd}`$ | `Generator_ramp_limit_down` over $`\mathcal{G}`$ — most a generator may lower its output between snapshots, per unit of nominal power; no value means no limit |
| $`\mathrm{ru}^{\mathrm{up}}`$ | `Generator_ramp_limit_start_up` over $`\mathcal{G}`$ — most output in the snapshot a unit starts, per unit of nominal power |
| $`\mathrm{rd}^{\mathrm{dn}}`$ | `Generator_ramp_limit_shut_down` over $`\mathcal{G}`$ — most output in the snapshot before a unit stops, per unit of nominal power |
| $`\mathrm{UT}`$ | `Generator_min_up_time` over $`\mathcal{G}`$ — least snapshots a unit stays on once started |
| $`\mathrm{DT}`$ | `Generator_min_down_time` over $`\mathcal{G}`$ — least snapshots a unit stays off once stopped |
| $`\mathrm{u}^{0}`$ | `Generator_status_initial` over $`\mathcal{G}`$ — one where the unit was on before the first snapshot, zero where off — PyPSA's `up_time_before > 0`, data prep |
| $`\mathrm{hold}`$ | `Generator_must_stay_up` over $`\mathcal{T} \times \mathcal{G}`$ — true while the up time a unit brought into the horizon still binds — data prep, since `position()` compares against a literal rather than a parameter |
| $`\mathrm{rest}`$ | `Generator_must_stay_down` over $`\mathcal{T} \times \mathcal{G}`$ — true while the down time a unit brought into the horizon still binds — PyPSA's `min_down_time - down_time_before` snapshots, where `down_time_before > 0`, data prep for the same reason |
| $`\mathrm{c}^{\mathrm{up}}`$ | `Generator_start_up_cost` over $`\mathcal{G}`$ — cost of one start |
| $`\mathrm{c}^{\mathrm{dn}}`$ | `Generator_shut_down_cost` over $`\mathcal{G}`$ — cost of one stop |
| $`\mathrm{c}^{\mathrm{on}}`$ | `Generator_stand_by_cost` over $`\mathcal{T} \times \mathcal{G}`$ — cost of one snapshot spent on |
| $`\mathrm{p}^{\mathrm{mod}}`$ | `Generator_p_nom_mod` over $`\mathcal{G}`$ — the module size a build comes in whole numbers of; no value means the build is continuous |
| $`\mathrm{N}^{\mathrm{fix}}`$ | `Generator_modules_installed` over $`\mathcal{G}`$ — how many whole modules a committable build has in place: `Generator_p_nom / Generator_p_nom_mod` where a fixed build is modular, one where it is not, data prep. PyPSA refuses a fixed modular build whose nominal power is not a whole number of modules |
| $`\mathrm{M}`$ | `Generator_big_m` over $`\mathcal{G}`$ — a bound safely above any feasible output — the build cap at full availability, data prep |
| $`\mathrm{nonneg}`$ | `Generator_p_min_pu_nonneg` over $`\mathcal{G}`$ — true where none of the generator's own minimums-per-unit is negative — PyPSA's per-unit `(p_min_pu >= 0).all()`, data prep |
| $`\mathrm{ru}^{f}`$ | `Link_ramp_limit_up` over $`\mathcal{L}`$ — most a link may raise its flow between snapshots, per unit of nominal power; no value means no limit |
| $`\mathrm{rd}^{f}`$ | `Link_ramp_limit_down` over $`\mathcal{L}`$ — most a link may lower its flow between snapshots, per unit of nominal power; no value means no limit |
| $`\mathrm{f}^{\mathrm{nom}}`$ | `Link_p_nom` over $`\mathcal{L}`$ — nominal power |
| $`\mathrm{ext}^{f}`$ | `Link_p_nom_extendable` over $`\mathcal{L}`$ — whether the nominal power is a decision |
| $`\underline{\mathrm{f}}`$ | `Link_p_min_pu` over $`\mathcal{T} \times \mathcal{L}`$ — least flow, per unit of nominal power — negative for a link that carries both ways |
| $`\overline{\mathrm{f}}`$ | `Link_p_max_pu` over $`\mathcal{T} \times \mathcal{L}`$ — most flow, per unit of nominal power |
| $`\eta`$ | `Link_efficiency` over $`\mathcal{O}`$ — share of the flow that arrives at an output port, PyPSA's `efficiency`, `efficiency2`, … read long — negative where that port consumes rather than delivers |
| $`\mathrm{d}^{f}`$ | `Link_output_delay` over $`\mathcal{O}`$ — snapshots a port's delivery lags its link's flow — PyPSA's `delay`, `delay2`, … read long, in `snapshot_weightings.generators` units, which the file states as whole snapshots; zero for a port that delivers at once |
| $`\mathrm{cyc}^{f}`$ | `Link_output_cyclic_delay` over $`\mathcal{O}`$ — whether a delayed port's flow wraps from the horizon's end — PyPSA's `cyclic_delay`, `cyclic_delay2`, …; where it does not, the flow still in transit at the first snapshots is lost |
| $`\mathrm{c}^{f}`$ | `Link_marginal_cost` over $`\mathcal{T} \times \mathcal{L}`$ — cost of one unit of flow |
| $`\mathrm{c}^{f,(2)}`$ | `Link_marginal_cost_quadratic` over $`\mathcal{T} \times \mathcal{L}`$ — cost of the square of one unit of flow |
| $`\mathrm{com}^{f}`$ | `Link_committable` over $`\mathcal{L}`$ — whether flow is gated by an on/off status decision |
| $`\mathrm{ru}^{f,\mathrm{up}}`$ | `Link_ramp_limit_start_up` over $`\mathcal{L}`$ — most flow in the snapshot a link starts, per unit of nominal power |
| $`\mathrm{rd}^{f,\mathrm{dn}}`$ | `Link_ramp_limit_shut_down` over $`\mathcal{L}`$ — most flow in the snapshot before a link stops, per unit of nominal power |
| $`\mathrm{UT}^{f}`$ | `Link_min_up_time` over $`\mathcal{L}`$ — least snapshots a link stays on once started |
| $`\mathrm{DT}^{f}`$ | `Link_min_down_time` over $`\mathcal{L}`$ — least snapshots a link stays off once stopped |
| $`\mathrm{u}^{f,0}`$ | `Link_status_initial` over $`\mathcal{L}`$ — one where the link was on before the first snapshot, zero where off — PyPSA's `up_time_before > 0`, data prep |
| $`\mathrm{hold}^{f}`$ | `Link_must_stay_up` over $`\mathcal{T} \times \mathcal{L}`$ — true while the up time a link brought into the horizon still binds — data prep, since `position()` compares against a literal rather than a parameter |
| $`\mathrm{rest}^{f}`$ | `Link_must_stay_down` over $`\mathcal{T} \times \mathcal{L}`$ — true while the down time a link brought into the horizon still binds — PyPSA's `min_down_time - down_time_before` snapshots, where `down_time_before > 0`, data prep for the same reason |
| $`\mathrm{c}^{f,\mathrm{up}}`$ | `Link_start_up_cost` over $`\mathcal{L}`$ — cost of one start |
| $`\mathrm{c}^{f,\mathrm{dn}}`$ | `Link_shut_down_cost` over $`\mathcal{L}`$ — cost of one stop |
| $`\mathrm{c}^{f,\mathrm{on}}`$ | `Link_stand_by_cost` over $`\mathcal{T} \times \mathcal{L}`$ — cost of one snapshot spent on |
| $`\mathrm{f}^{\mathrm{mod}}`$ | `Link_p_nom_mod` over $`\mathcal{L}`$ — the module size a build comes in whole numbers of; no value means the build is continuous |
| $`\mathrm{N}^{f,\mathrm{fix}}`$ | `Link_modules_installed` over $`\mathcal{L}`$ — how many whole modules a committable build has in place: `Link_p_nom / Link_p_nom_mod` where a fixed build is modular, one where it is not, data prep. PyPSA refuses a fixed modular build whose nominal power is not a whole number of modules |
| $`\mathrm{M}^{f}`$ | `Link_big_m` over $`\mathcal{L}`$ — a bound safely above any feasible flow — the build cap at full availability, data prep |
| $`\mathrm{nonneg}^{f}`$ | `Link_p_min_pu_nonneg` over $`\mathcal{L}`$ — true where none of the link's own minimums-per-unit is negative — PyPSA's per-unit `(p_min_pu >= 0).all()`, data prep |
| $`\mathrm{z}^{\mathrm{nom}}`$ | `Process_p_nom` over $`\mathcal{J}`$ — nominal internal power |
| $`\mathrm{ext}^{z}`$ | `Process_p_nom_extendable` over $`\mathcal{J}`$ — whether the nominal internal power is a decision |
| $`\underline{\mathrm{z}}`$ | `Process_p_min_pu` over $`\mathcal{T} \times \mathcal{J}`$ — least internal power, per unit of nominal power — negative for a process that runs both ways |
| $`\overline{\mathrm{z}}`$ | `Process_p_max_pu` over $`\mathcal{T} \times \mathcal{J}`$ — most internal power, per unit of nominal power |
| $`\alpha`$ | `Process_rate` over $`\mathcal{R}`$ — the energy a port draws or delivers per unit of internal power, PyPSA's `rate0`, `rate1`, … read long — negative where the port withdraws, positive where it injects; a link is a process whose `bus0` rate is minus one and whose output rates are its efficiencies |
| $`\mathrm{d}^{z}`$ | `Process_output_delay` over $`\mathcal{R}`$ — snapshots a port's transfer lags its process's internal power — PyPSA's `delay0`, `delay1`, … read long, in `snapshot_weightings.generators` units, which the file states as whole snapshots; zero for a port that transfers at once |
| $`\mathrm{cyc}^{z}`$ | `Process_output_cyclic_delay` over $`\mathcal{R}`$ — whether a delayed port's transfer wraps from the horizon's end — PyPSA's `cyclic_delay0`, `cyclic_delay1`, …; where it does not, the energy still in transit at the first snapshots is lost |
| $`\mathrm{c}^{z}`$ | `Process_marginal_cost` over $`\mathcal{T} \times \mathcal{J}`$ — cost of one unit of internal power |
| $`\mathrm{ru}^{z}`$ | `Process_ramp_limit_up` over $`\mathcal{J}`$ — most a process may raise its internal power between snapshots, per unit of nominal power; no value means no limit |
| $`\mathrm{rd}^{z}`$ | `Process_ramp_limit_down` over $`\mathcal{J}`$ — most a process may lower its internal power between snapshots, per unit of nominal power; no value means no limit |
| $`\mathrm{z}^{\mathrm{set}}`$ | `Process_p_set` over $`\mathcal{T} \times \mathcal{J}`$ — a given internal power schedule; a process without one has no row here |
| $`\underline{\mathrm{z}}^{\mathrm{nom}}`$ | `Process_p_nom_min` over $`\mathcal{J}`$ — least nominal power an extendable process may be built at |
| $`\overline{\mathrm{z}}^{\mathrm{nom}}`$ | `Process_p_nom_max` over $`\mathcal{J}`$ — most nominal power an extendable process may be built at |
| $`\mathrm{c}^{\mathrm{cap},z}`$ | `Process_capital_cost` over $`\mathcal{J}`$ — cost of one unit of nominal power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $`\mathrm{z}^{\mathrm{nom,set}}`$ | `Process_p_nom_set` over $`\mathcal{J}`$ — a given nominal power for an extendable process; one without a value has no row here |
| $`\mathrm{com}^{z}`$ | `Process_committable` over $`\mathcal{J}`$ — whether internal power is gated by an on/off status decision |
| $`\mathrm{ru}^{z,\mathrm{up}}`$ | `Process_ramp_limit_start_up` over $`\mathcal{J}`$ — most internal power in the snapshot a process starts, per unit of nominal power |
| $`\mathrm{rd}^{z,\mathrm{dn}}`$ | `Process_ramp_limit_shut_down` over $`\mathcal{J}`$ — most internal power in the snapshot before a process stops, per unit of nominal power |
| $`\mathrm{UT}^{z}`$ | `Process_min_up_time` over $`\mathcal{J}`$ — least snapshots a process stays on once started |
| $`\mathrm{DT}^{z}`$ | `Process_min_down_time` over $`\mathcal{J}`$ — least snapshots a process stays off once stopped |
| $`\mathrm{u}^{z,0}`$ | `Process_status_initial` over $`\mathcal{J}`$ — one where the process was on before the first snapshot, zero where off — PyPSA's `up_time_before > 0`, data prep |
| $`\mathrm{hold}^{z}`$ | `Process_must_stay_up` over $`\mathcal{T} \times \mathcal{J}`$ — true while the up time a process brought into the horizon still binds — data prep, since `position()` compares against a literal rather than a parameter |
| $`\mathrm{rest}^{z}`$ | `Process_must_stay_down` over $`\mathcal{T} \times \mathcal{J}`$ — true while the down time a process brought into the horizon still binds — PyPSA's `min_down_time - down_time_before` snapshots, where `down_time_before > 0`, data prep for the same reason |
| $`\mathrm{c}^{z,\mathrm{up}}`$ | `Process_start_up_cost` over $`\mathcal{J}`$ — cost of one start |
| $`\mathrm{c}^{z,\mathrm{dn}}`$ | `Process_shut_down_cost` over $`\mathcal{J}`$ — cost of one stop |
| $`\mathrm{c}^{z,\mathrm{on}}`$ | `Process_stand_by_cost` over $`\mathcal{T} \times \mathcal{J}`$ — cost of one snapshot spent on |
| $`\mathrm{z}^{\mathrm{mod}}`$ | `Process_p_nom_mod` over $`\mathcal{J}`$ — the module size a build comes in whole numbers of; no value means the build is continuous |
| $`\mathrm{N}^{z,\mathrm{fix}}`$ | `Process_modules_installed` over $`\mathcal{J}`$ — how many whole modules a committable build has in place: `Process_p_nom / Process_p_nom_mod` where a fixed build is modular, one where it is not, data prep. PyPSA refuses a fixed modular build whose nominal power is not a whole number of modules |
| $`\mathrm{M}^{z}`$ | `Process_big_m` over $`\mathcal{J}`$ — a bound safely above any feasible internal power — the build cap at full availability, data prep |
| $`\mathrm{nonneg}^{z}`$ | `Process_p_min_pu_nonneg` over $`\mathcal{J}`$ — true where none of the process's own minimums-per-unit is negative — PyPSA's per-unit `(p_min_pu >= 0).all()`, data prep |
| $`\mathrm{load}`$ | `Load_p_set` over $`\Xi \times \mathcal{T} \times \mathcal{D}`$ — demand |
| $`\pi`$ | `scenario_weight` over $`\Xi`$ — PyPSA's `scenario_weightings.weight` — the probability of a future |
| $`\omega`$ | `CVaR_omega` (scalar) — PyPSA's `risk_preference['omega']` — the share of operating cost priced at the tail rather than in expectation; zero recovers the risk-neutral model |
| $`\mathrm{v}`$ | `CVaR_inv_tail` (scalar) — PyPSA's `1 / (1 - alpha)` — the tail's own probability, inverted in data prep because a divisor is one factor |
| $`\mathrm{w}^{y}`$ | `period_weight_objective` over $`\mathcal{Y}`$ — PyPSA's `investment_period_weightings.objective` — what a period's cost weighs |
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
| $`\mathrm{new}`$ | `Generator_first_active` over $`\mathcal{Y} \times \mathcal{G}`$ — one in the first period a generator stands in, zero elsewhere — PyPSA's `active.cumsum() == 1`, data prep |
| $`\mathrm{new}^{f}`$ | `Link_first_active` over $`\mathcal{Y} \times \mathcal{L}`$ — one in the first period a link stands in, zero elsewhere — PyPSA's `active.cumsum() == 1`, data prep |
| $`\mathrm{new}^{h}`$ | `StorageUnit_first_active` over $`\mathcal{Y} \times \mathcal{S}`$ — one in the first period a storage unit stands in, zero elsewhere — PyPSA's `active.cumsum() == 1`, data prep |
| $`\mathrm{new}^{e}`$ | `Store_first_active` over $`\mathcal{Y} \times \mathcal{V}`$ — one in the first period a store stands in, zero elsewhere — PyPSA's `active.cumsum() == 1`, data prep |
| $`\mathrm{new}^{s}`$ | `Line_first_active` over $`\mathcal{Y} \times \mathcal{K}`$ — one in the first period a line stands in, zero elsewhere — PyPSA's `active.cumsum() == 1`, data prep |
| $`\mathrm{new}^{z}`$ | `Process_first_active` over $`\mathcal{Y} \times \mathcal{J}`$ — one in the first period a process stands in, zero elsewhere — PyPSA's `active.cumsum() == 1`, data prep |
| $`\mathrm{new}^{\sigma}`$ | `Transformer_first_active` over $`\mathcal{Y} \times \mathcal{M}`$ — one in the first period a transformer stands in, zero elsewhere — the spec extends the carrier growth limit to transformers, which PyPSA does not, so PyPSA has no counterpart, data prep |
| $`\overline{\Delta}`$ | `Carrier_max_growth` over $`\mathcal{I}`$ — most capacity of a carrier that may be added in a period; no value means no limit |
| $`\mathrm{r}`$ | `Carrier_max_relative_growth` over $`\mathcal{I}`$ — share of the previous period's additions that may be added on top |
| $`\mathrm{p}^{\mathrm{set}}`$ | `Generator_p_set` over $`\mathcal{T} \times \mathcal{G}`$ — a given output schedule; a generator without one has no row here |
| $`\mathrm{f}^{\mathrm{set}}`$ | `Link_p_set` over $`\mathcal{T} \times \mathcal{L}`$ — a given flow schedule; a link without one has no row here |
| $`\mathrm{w}^{\mathrm{sto}}`$ | `snapshot_weightings_stores` over $`\mathcal{T}`$ — PyPSA's `snapshot_weightings.stores` — hours a snapshot stands for in a storage balance |
| $`\mathrm{w}^{\mathrm{gen}}`$ | `snapshot_weightings_generators` over $`\mathcal{T}`$ — PyPSA's `snapshot_weightings.generators` — hours a snapshot stands for in an energy total |
| $`\underline{\mathrm{p}}^{\mathrm{nom}}`$ | `Generator_p_nom_min` over $`\mathcal{G}`$ — least nominal power an extendable generator may be built at |
| $`\overline{\mathrm{p}}^{\mathrm{nom}}`$ | `Generator_p_nom_max` over $`\mathcal{G}`$ — most nominal power an extendable generator may be built at |
| $`\mathrm{c}^{\mathrm{cap}}`$ | `Generator_capital_cost` over $`\mathcal{G}`$ — cost of one unit of nominal power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $`\mathrm{p}^{\mathrm{nom,set}}`$ | `Generator_p_nom_set` over $`\mathcal{G}`$ — a given nominal power for an extendable generator; one without a value has no row here |
| $`\underline{\mathrm{E}}`$ | `Generator_e_sum_min` over $`\mathcal{G}`$ — least energy over the horizon; minus infinity where no floor is meant |
| $`\overline{\mathrm{E}}`$ | `Generator_e_sum_max` over $`\mathcal{G}`$ — most energy over the horizon — a fuel or emission budget in energy terms; infinity where no cap is meant |
| $`\underline{\mathrm{f}}^{\mathrm{nom}}`$ | `Link_p_nom_min` over $`\mathcal{L}`$ — least nominal power an extendable link may be built at |
| $`\overline{\mathrm{f}}^{\mathrm{nom}}`$ | `Link_p_nom_max` over $`\mathcal{L}`$ — most nominal power an extendable link may be built at |
| $`\mathrm{c}^{\mathrm{cap},f}`$ | `Link_capital_cost` over $`\mathcal{L}`$ — cost of one unit of nominal power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $`\mathrm{f}^{\mathrm{nom,set}}`$ | `Link_p_nom_set` over $`\mathcal{L}`$ — a given nominal power for an extendable link; one without a value has no row here |
| $`\underline{\mathrm{h}}^{\mathrm{nom}}`$ | `StorageUnit_p_nom_min` over $`\mathcal{S}`$ — least nominal power an extendable storage unit may be built at |
| $`\overline{\mathrm{h}}^{\mathrm{nom}}`$ | `StorageUnit_p_nom_max` over $`\mathcal{S}`$ — most nominal power an extendable storage unit may be built at |
| $`\mathrm{c}^{\mathrm{cap},h}`$ | `StorageUnit_capital_cost` over $`\mathcal{S}`$ — cost of one unit of nominal power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $`\mathrm{h}^{\mathrm{nom,set}}`$ | `StorageUnit_p_nom_set` over $`\mathcal{S}`$ — a given nominal power for an extendable storage unit; one without a value has no row here |
| $`\underline{\mathrm{e}}^{\mathrm{nom}}`$ | `Store_e_nom_min` over $`\mathcal{V}`$ — least nominal capacity an extendable store may be built at |
| $`\overline{\mathrm{e}}^{\mathrm{nom}}`$ | `Store_e_nom_max` over $`\mathcal{V}`$ — most nominal capacity an extendable store may be built at |
| $`\mathrm{c}^{\mathrm{cap},e}`$ | `Store_capital_cost` over $`\mathcal{V}`$ — cost of one unit of nominal capacity — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $`\mathrm{e}^{\mathrm{nom,set}}`$ | `Store_e_nom_set` over $`\mathcal{V}`$ — a given nominal capacity for an extendable store; one without a value has no row here |
| $`\mathrm{h}^{\mathrm{nom}}`$ | `StorageUnit_p_nom` over $`\mathcal{S}`$ — nominal power |
| $`\mathrm{ext}^{h}`$ | `StorageUnit_p_nom_extendable` over $`\mathcal{S}`$ — whether the nominal power is a decision |
| $`\underline{\mathrm{h}}`$ | `StorageUnit_p_min_pu` over $`\mathcal{T} \times \mathcal{S}`$ — most storing, per unit of nominal power and negated |
| $`\overline{\mathrm{h}}`$ | `StorageUnit_p_max_pu` over $`\mathcal{T} \times \mathcal{S}`$ — most dispatch, per unit of nominal power |
| $`\mathrm{T}^{h}`$ | `StorageUnit_max_hours` over $`\mathcal{S}`$ — energy capacity, as hours of dispatch at nominal power |
| $`\eta^{-}`$ | `StorageUnit_efficiency_store` over $`\mathcal{S}`$ — share of the power drawn from the bus that becomes charge |
| $`\eta^{+}`$ | `StorageUnit_efficiency_dispatch` over $`\mathcal{S}`$ — share of the charge drawn down that reaches the bus |
| $`\rho`$ | `StorageUnit_retention` over $`\mathcal{T} \times \mathcal{S}`$ — share of charge kept over a snapshot — PyPSA's `(1 - standing_loss) ** elapsed hours`, data prep |
| $`\mathrm{inflow}`$ | `StorageUnit_inflow` over $`\mathcal{T} \times \mathcal{S}`$ — energy arriving per hour, a river into a reservoir |
| $`\mathrm{soc}^{0}`$ | `StorageUnit_state_of_charge_initial` over $`\mathcal{S}`$ — charge held before the first snapshot |
| $`\mathrm{cyc}`$ | `StorageUnit_cyclic_state_of_charge` over $`\mathcal{S}`$ — whether the horizon closes on itself instead of opening on the initial charge |
| $`\mathrm{cyc}^{y}`$ | `StorageUnit_cyclic_state_of_charge_per_period` over $`\mathcal{S}`$ — whether each investment period closes on itself instead of carrying its charge on to the next; it overrides `cyclic_state_of_charge` and `state_of_charge_initial_per_period`. PyPSA reads it only under `multi_investment_periods`, so data prep feeds false otherwise |
| $`\mathrm{reset}`$ | `StorageUnit_state_of_charge_initial_per_period` over $`\mathcal{S}`$ — whether each investment period opens on the initial charge instead of carrying the previous period's; PyPSA reads it only under `multi_investment_periods`, so data prep feeds false otherwise |
| $`\mathrm{c}^{h}`$ | `StorageUnit_marginal_cost` over $`\mathcal{T} \times \mathcal{S}`$ — cost of one unit of dispatch |
| $`\mathrm{c}^{\mathrm{soc}}`$ | `StorageUnit_marginal_cost_storage` over $`\mathcal{T} \times \mathcal{S}`$ — cost of one unit of charge held over one snapshot |
| $`\mathrm{c}^{\mathrm{spill}}`$ | `StorageUnit_spill_cost` over $`\mathcal{T} \times \mathcal{S}`$ — cost of one unit of inflow passed on unused |
| $`\mathrm{h}^{\mathrm{set}}`$ | `StorageUnit_p_set` over $`\mathcal{T} \times \mathcal{S}`$ — a given net dispatch schedule; a unit without one has no row here |
| $`\mathrm{soc}^{\mathrm{set}}`$ | `StorageUnit_state_of_charge_set` over $`\mathcal{T} \times \mathcal{S}`$ — a given charge schedule; a unit without one has no row here |
| $`\mathrm{e}^{\mathrm{nom}}`$ | `Store_e_nom` over $`\mathcal{V}`$ — nominal energy capacity |
| $`\mathrm{ext}^{e}`$ | `Store_e_nom_extendable` over $`\mathcal{V}`$ — whether the nominal energy capacity is a decision |
| $`\underline{\mathrm{e}}`$ | `Store_e_min_pu` over $`\mathcal{T} \times \mathcal{V}`$ — least energy held, per unit of nominal capacity — negative for a store that may go short |
| $`\overline{\mathrm{e}}`$ | `Store_e_max_pu` over $`\mathcal{T} \times \mathcal{V}`$ — most energy held, per unit of nominal capacity |
| $`\rho^{e}`$ | `Store_retention` over $`\mathcal{T} \times \mathcal{V}`$ — share of energy kept over a snapshot — PyPSA's `(1 - standing_loss) ** elapsed hours`, data prep |
| $`\mathrm{e}^{0}`$ | `Store_e_initial` over $`\mathcal{V}`$ — energy held before the first snapshot |
| $`\mathrm{cyc}^{e}`$ | `Store_e_cyclic` over $`\mathcal{V}`$ — whether the horizon closes on itself instead of opening on the initial energy |
| $`\mathrm{cyc}^{e,y}`$ | `Store_e_cyclic_per_period` over $`\mathcal{V}`$ — whether each investment period closes on itself instead of carrying its energy on to the next; it overrides `e_cyclic` and `e_initial_per_period`. PyPSA reads it only under `multi_investment_periods`, so data prep feeds false otherwise |
| $`\mathrm{reset}^{e}`$ | `Store_e_initial_per_period` over $`\mathcal{V}`$ — whether each investment period opens on the initial energy instead of carrying the previous period's; PyPSA reads it only under `multi_investment_periods`, so data prep feeds false otherwise |
| $`\mathrm{c}^{q}`$ | `Store_marginal_cost` over $`\mathcal{T} \times \mathcal{V}`$ — cost of one unit of power delivered |
| $`\mathrm{c}^{e}`$ | `Store_marginal_cost_storage` over $`\mathcal{T} \times \mathcal{V}`$ — cost of one unit of energy held over one snapshot |
| $`\mathrm{e}^{\mathrm{set}}`$ | `Store_e_set` over $`\mathcal{T} \times \mathcal{V}`$ — a given energy schedule; a store without one has no row here |
| $`\mathrm{s}^{\mathrm{nom}}`$ | `Line_s_nom` over $`\mathcal{K}`$ — nominal apparent power |
| $`\mathrm{ext}^{s}`$ | `Line_s_nom_extendable` over $`\mathcal{K}`$ — whether the nominal apparent power is a decision |
| $`\overline{\mathrm{s}}`$ | `Line_s_max_pu` over $`\mathcal{T} \times \mathcal{K}`$ — most flow either way, per unit of nominal apparent power |
| $`\underline{\mathrm{s}}^{\mathrm{nom}}`$ | `Line_s_nom_min` over $`\mathcal{K}`$ — least nominal apparent power an extendable line may be built at |
| $`\overline{\mathrm{s}}^{\mathrm{nom}}`$ | `Line_s_nom_max` over $`\mathcal{K}`$ — most nominal apparent power an extendable line may be built at |
| $`\mathrm{c}^{\mathrm{cap},s}`$ | `Line_capital_cost` over $`\mathcal{K}`$ — cost of one unit of nominal apparent power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $`\mathrm{s}^{\mathrm{nom,set}}`$ | `Line_s_nom_set` over $`\mathcal{K}`$ — a given nominal apparent power for an extendable line; one without a value has no row here |
| $`\mathrm{s}^{\mathrm{set}}`$ | `Line_s_set` over $`\mathcal{T} \times \mathcal{K}`$ — a given flow schedule; a line without one has no row here |
| $`\mathrm{x}`$ | `Line_cycle_weight` over $`\mathcal{K} \times \mathcal{C}`$ — the line's series impedance, signed by its orientation in the cycle — the cycle basis, data prep; a line in no cycle has no row |
| $`\mathrm{lossy}`$ | `transmission_losses` (scalar) — whether the network dissipates transmission losses — PyPSA's `transmission_losses` read as a flag; its mode, tangents or secants, only decides how data prep fills the `segment` axis, the rows are the same; false with no segments is a lossless run |
| $`\overline{\ell}`$ | `Line_loss_max` over $`\mathcal{T} \times \mathcal{K}`$ — the loss at a line's rating — PyPSA's `r_pu_eff * (s_max_pu * s_nom_max)**2`, data prep |
| $`\mathrm{a}`$ | `Line_loss_slope` over $`\mathcal{T} \times \mathcal{K} \times \mathcal{B}`$ — the slope of a cut to the loss curve — a tangent's `2 * r_pu_eff * p_k` at its segment's flow, a secant's `r_pu_eff * (p_k + p_k+1)` between consecutive breakpoints, data prep |
| $`\mathrm{b}`$ | `Line_loss_offset` over $`\mathcal{T} \times \mathcal{K} \times \mathcal{B}`$ — where that cut meets the loss axis — a tangent's `loss_k - slope_k * p_k`, a secant's `-r_pu_eff * p_k * p_k+1`, negative, data prep |
| $`\sigma^{\mathrm{nom}}`$ | `Transformer_s_nom` over $`\mathcal{M}`$ — nominal apparent power |
| $`\mathrm{ext}^{\sigma}`$ | `Transformer_s_nom_extendable` over $`\mathcal{M}`$ — whether the nominal apparent power is a decision |
| $`\overline{\sigma}`$ | `Transformer_s_max_pu` over $`\mathcal{T} \times \mathcal{M}`$ — most flow either way, per unit of nominal apparent power |
| $`\underline{\sigma}^{\mathrm{nom}}`$ | `Transformer_s_nom_min` over $`\mathcal{M}`$ — least nominal apparent power an extendable transformer may be built at |
| $`\overline{\sigma}^{\mathrm{nom}}`$ | `Transformer_s_nom_max` over $`\mathcal{M}`$ — most nominal apparent power an extendable transformer may be built at |
| $`\mathrm{c}^{\mathrm{cap},\sigma}`$ | `Transformer_capital_cost` over $`\mathcal{M}`$ — cost of one unit of nominal apparent power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $`\sigma^{\mathrm{nom,set}}`$ | `Transformer_s_nom_set` over $`\mathcal{M}`$ — a given nominal apparent power for an extendable transformer; one without a value has no row here |
| $`\sigma^{\mathrm{set}}`$ | `Transformer_s_set` over $`\mathcal{T} \times \mathcal{M}`$ — a given flow schedule; a transformer without one has no row here |
| $`\mathrm{x}^{\sigma}`$ | `Transformer_cycle_weight` over $`\mathcal{M} \times \mathcal{C}`$ — the transformer's effective series reactance, `x` times its tap ratio, signed by its orientation in the cycle — PyPSA's `x_pu_eff`, the cycle basis, data prep; a transformer in no cycle has no row |
| $`\vartheta`$ | `Transformer_phase_shift_weight` over $`\mathcal{M} \times \mathcal{C}`$ — a fixed transformer's phase shift in radians, signed by its orientation in the cycle — a constant added to the cycle sum, data prep; zero for a varying transformer, whose shift is a decision instead, so the constant and the variable term never both count a shift. A transformer with no shift or in no cycle has no row |
| $`\mathrm{Transformer\_phase\_shift\_varying}`$ | `Transformer_phase_shift_varying` over $`\mathcal{M}`$ — whether a transformer's phase shift is a decision — PyPSA's `phase_shift_min < phase_shift_max`, read as a flag in data prep; false is a fixed shift carried by `phase_shift` |
| $`\mathrm{Transformer\_phase\_shift\_min}`$ | `Transformer_phase_shift_min` over $`\mathcal{M}`$ — the least a varying transformer's phase shift may take, in degrees — PyPSA's `phase_shift_min`; where it is below `phase_shift_max` the shift is a decision, otherwise the transformer keeps its fixed `phase_shift` |
| $`\mathrm{Transformer\_phase\_shift\_max}`$ | `Transformer_phase_shift_max` over $`\mathcal{M}`$ — the most a varying transformer's phase shift may take, in degrees — PyPSA's `phase_shift_max`; equal to `phase_shift_min` for a fixed transformer |
| $`\mathrm{Transformer\_phase\_shift\_cycle\_weight}`$ | `Transformer_phase_shift_cycle_weight` over $`\mathcal{M} \times \mathcal{C}`$ — the cycle sign for a varying transformer's phase shift, times π/180 so a shift in degrees enters the cycle sum in radians — data prep; zero for a fixed transformer or one in no cycle |
| $`\overline{\ell}^{\sigma}`$ | `Transformer_loss_max` over $`\mathcal{T} \times \mathcal{M}`$ — the loss at a transformer's rating — PyPSA's `r_pu_eff * (s_max_pu * s_nom_max)**2`, its `r_pu_eff` the resistance over the given `s_nom` times the tap ratio, data prep |
| $`\mathrm{a}^{\sigma}`$ | `Transformer_loss_slope` over $`\mathcal{T} \times \mathcal{M} \times \mathcal{B}`$ — the slope of a cut to a transformer's loss curve — a tangent's `2 * r_pu_eff * p_k`, a secant's `r_pu_eff * (p_k + p_k+1)`, as a line's, over the transformer's own `r_pu_eff` and rating, data prep |
| $`\mathrm{b}^{\sigma}`$ | `Transformer_loss_offset` over $`\mathcal{T} \times \mathcal{M} \times \mathcal{B}`$ — where that cut meets the loss axis — a tangent's `loss_k - slope_k * p_k`, a secant's `-r_pu_eff * p_k * p_k+1`, negative, data prep |
| $`\mathrm{type}`$ | `GlobalConstraint_type` over $`\mathcal{I}`$ — which formula the row takes — `primary_energy`, `operational_limit`, `transmission_volume_expansion_limit`, `transmission_expansion_cost_limit` or `tech_capacity_expansion_limit` |
| $`\mathrm{sense}`$ | `GlobalConstraint_sense` over $`\mathcal{I}`$ — which way the row binds — `<=`, `>=` or `==` |
| $`\mathrm{K}`$ | `GlobalConstraint_constant` over $`\mathcal{I}`$ — the constant the total is held against; what a variable cannot carry — an initial charge, a non-extendable build — is folded in here by data prep |
| $`\mathrm{last}`$ | `snapshot_is_last` over $`\mathcal{T}`$ — one at the horizon's last snapshot, zero elsewhere — data prep, how an expression reads a final level |
| $`\mathrm{a}`$ | `Generator_primary_energy_weight` over $`\mathcal{I} \times \mathcal{G}`$ — the constrained attribute per unit of energy at the bus — the carrier's `co2_emissions` over the generator's efficiency, data prep; a generator of an unweighted carrier has no row |
| $`\mathrm{a}^{h}`$ | `StorageUnit_primary_energy_weight` over $`\mathcal{I} \times \mathcal{S}`$ — the constrained attribute per unit of charge depleted — data prep; an unweighted unit has no row |
| $`\mathrm{a}^{e}`$ | `Store_primary_energy_weight` over $`\mathcal{I} \times \mathcal{V}`$ — the constrained attribute per unit of energy depleted — data prep; an unweighted store has no row |
| $`\mathrm{b}`$ | `Generator_operational_limit_weight` over $`\mathcal{I} \times \mathcal{G}`$ — one where the generator is in the row's set — data prep; one outside it has no row |
| $`\mathrm{b}^{h}`$ | `StorageUnit_operational_limit_weight` over $`\mathcal{I} \times \mathcal{S}`$ — one where the storage unit is in the row's set — data prep; one outside it has no row |
| $`\mathrm{b}^{e}`$ | `Store_operational_limit_weight` over $`\mathcal{I} \times \mathcal{V}`$ — one where the store is in the row's set — data prep; one outside it has no row |
| $`\mathrm{len}`$ | `Line_volume_weight` over $`\mathcal{I} \times \mathcal{K}`$ — the line's length where its carrier is in the row's set — data prep; a line outside it has no row |
| $`\mathrm{len}^{f}`$ | `Link_volume_weight` over $`\mathcal{I} \times \mathcal{L}`$ — the link's length where its carrier is in the row's set — data prep; a link outside it has no row |
| $`\mathrm{cc}`$ | `Line_expansion_cost_weight` over $`\mathcal{I} \times \mathcal{K}`$ — the line's capital cost where its carrier is in the row's set — data prep; a line outside it has no row |
| $`\mathrm{cc}^{f}`$ | `Link_expansion_cost_weight` over $`\mathcal{I} \times \mathcal{L}`$ — the link's capital cost where its carrier is in the row's set — data prep; a link outside it has no row |
| $`\mathrm{m}`$ | `Generator_tech_capacity_weight` over $`\mathcal{I} \times \mathcal{G}`$ — one where the generator is in the row's carrier-and-bus set — data prep; one outside it has no row |
| $`\mathrm{m}^{f}`$ | `Link_tech_capacity_weight` over $`\mathcal{I} \times \mathcal{L}`$ — one where the link is in the row's carrier-and-bus set — data prep; one outside it has no row |
| $`\mathrm{m}^{l}`$ | `Line_tech_capacity_weight` over $`\mathcal{I} \times \mathcal{K}`$ — one where the line is in the row's carrier-and-bus set — data prep; one outside it has no row |
| $`\mathrm{m}^{h}`$ | `StorageUnit_tech_capacity_weight` over $`\mathcal{I} \times \mathcal{S}`$ — one where the storage unit is in the row's carrier-and-bus set — data prep; one outside it has no row |
| $`\mathrm{m}^{e}`$ | `Store_tech_capacity_weight` over $`\mathcal{I} \times \mathcal{V}`$ — one where the store is in the row's carrier-and-bus set — data prep; one outside it has no row |
| $`\mathrm{m}^{z}`$ | `Process_tech_capacity_weight` over $`\mathcal{I} \times \mathcal{J}`$ — one where the process is in the row's carrier-and-bus set — data prep; one outside it has no row |

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
| $`N^{f}`$ | `Link_n_mod` over $`\mathcal{L}`$ — `Link-n_mod` — how many modules of an extendable modular build |
| $`u^{f}`$ | `Link_status` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — `Link-status` — how much of a committable link is on: an integer the rows below cap at one, or at the module count where the build is modular |
| $`\mathit{up}^{f}`$ | `Link_start_up` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — `Link-start_up` — how much of a committable link turns on this snapshot, capped as the status is |
| $`\mathit{dn}^{f}`$ | `Link_shut_down` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — `Link-shut_down` — how much of a committable link turns off this snapshot, capped as the status is |
| $`N^{z}`$ | `Process_n_mod` over $`\mathcal{J}`$ — `Process-n_mod` — how many modules of an extendable modular build |
| $`u^{z}`$ | `Process_status` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — `Process-status` — how much of a committable process is on: an integer the rows below cap at one, or at the module count where the build is modular |
| $`\mathit{up}^{z}`$ | `Process_start_up` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — `Process-start_up` — how much of a committable process turns on this snapshot, capped as the status is |
| $`\mathit{dn}^{z}`$ | `Process_shut_down` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — `Process-shut_down` — how much of a committable process turns off this snapshot, capped as the status is |
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
| $`\overleftarrow{p}`$ | `Generator_previous_p` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — the output a generator carries into a snapshot — nothing at the start of the horizon, which is why a unit that came in running carries no ramp row there |
| $`\widetilde{\mathrm{p}}^{\mathrm{nom}}`$ | `Generator_p_nom_effective` over $`\mathcal{G}`$ — the build a generator's limits are taken against — the chosen one where it is extendable, the given one otherwise |
| $`\widetilde{\mathrm{ru}}`$ | `Generator_ramp_up_rate` over $`\mathcal{G}`$ — the ramp limit a unit's up row reads — PyPSA's `ramp_limit_up`, or the full build where it has none, since a start-up ramp alone builds the row |
| $`\widetilde{\mathrm{rd}}`$ | `Generator_ramp_down_rate` over $`\mathcal{G}`$ — the ramp limit a unit's down row reads — PyPSA's `ramp_limit_down`, or the full build where it has none, since a shut-down ramp alone builds the row |
| $`\widetilde{\mathrm{ru}}^{\mathrm{up}}`$ | `Generator_start_up_rate` over $`\mathcal{G}`$ — the start-up ramp a unit's up row reads — PyPSA's `ramp_limit_start_up`, or the full build where it has none |
| $`\widetilde{\mathrm{rd}}^{\mathrm{dn}}`$ | `Generator_shut_down_rate` over $`\mathcal{G}`$ — the shut-down ramp a unit's down row reads — PyPSA's `ramp_limit_shut_down`, or the full build where it has none |
| $`\widehat{\mathrm{p}}^{\mathrm{nom}}`$ | `Generator_p_nom_committed` over $`\mathcal{G}`$ — the build a committed unit's ramp rows are taken against — one module where the build is extendable and modular, the given build otherwise |
| $`\Delta^{+}`$ | `Generator_ramp_up_allowance` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — how far a generator may raise output between two snapshots — its ramp limit of the build while it stays on, plus its start-up ramp in the snapshot it turns on |
| $`\Delta^{-}`$ | `Generator_ramp_down_allowance` over $`\Xi \times \mathcal{T} \times \mathcal{G}`$ — how far a generator may lower output between two snapshots — its ramp limit of the build while it stays on, plus its shut-down ramp in the snapshot it turns off |
| $`\widetilde{\mathrm{f}}^{\mathrm{nom}}`$ | `Link_p_nom_effective` over $`\mathcal{L}`$ — the build a link's limits are taken against — the chosen one where it is extendable, the given one otherwise |
| $`\overleftarrow{u}^{f}`$ | `Link_previous_status` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — the commitment state a link carries into a snapshot — the state it brought into the horizon at the first, the previous snapshot's after that |
| $`\overleftarrow{f}`$ | `Link_previous_p` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — the flow a link carries into a snapshot — nothing at the start of the horizon, which is why a link that came in running carries no ramp row there |
| $`\widetilde{\mathrm{ru}}^{f}`$ | `Link_ramp_up_rate` over $`\mathcal{L}`$ — the ramp limit a link's up row reads — PyPSA's `ramp_limit_up`, or the full build where it has none, since a start-up ramp alone builds the row |
| $`\widetilde{\mathrm{rd}}^{f}`$ | `Link_ramp_down_rate` over $`\mathcal{L}`$ — the ramp limit a link's down row reads — PyPSA's `ramp_limit_down`, or the full build where it has none, since a shut-down ramp alone builds the row |
| $`\widetilde{\mathrm{ru}}^{f,\mathrm{up}}`$ | `Link_start_up_rate` over $`\mathcal{L}`$ — the start-up ramp a link's up row reads — PyPSA's `ramp_limit_start_up`, or the full build where it has none |
| $`\widetilde{\mathrm{rd}}^{f,\mathrm{dn}}`$ | `Link_shut_down_rate` over $`\mathcal{L}`$ — the shut-down ramp a link's down row reads — PyPSA's `ramp_limit_shut_down`, or the full build where it has none |
| $`\widehat{\mathrm{f}}^{\mathrm{nom}}`$ | `Link_p_nom_committed` over $`\mathcal{L}`$ — the build a committed link's ramp rows are taken against — one module where the build is extendable and modular, the given build otherwise |
| $`\Delta^{f,+}`$ | `Link_ramp_up_allowance` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — how far a link may raise flow between two snapshots — its ramp limit of the build while it stays on, plus its start-up ramp in the snapshot it turns on |
| $`\Delta^{f,-}`$ | `Link_ramp_down_allowance` over $`\Xi \times \mathcal{T} \times \mathcal{L}`$ — how far a link may lower flow between two snapshots — its ramp limit of the build while it stays on, plus its shut-down ramp in the snapshot it turns off |
| $`\widetilde{\mathrm{z}}^{\mathrm{nom}}`$ | `Process_p_nom_effective` over $`\mathcal{J}`$ — the build a process's limits are taken against — the chosen one where it is extendable, the given one otherwise |
| $`\overleftarrow{u}^{z}`$ | `Process_previous_status` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — the commitment state a process carries into a snapshot — the state it brought into the horizon at the first, the previous snapshot's after that |
| $`\overleftarrow{z}`$ | `Process_previous_p` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — the internal power a process carries into a snapshot — nothing at the start of the horizon, which is why a process that came in running carries no ramp row there |
| $`\widetilde{\mathrm{ru}}^{z}`$ | `Process_ramp_up_rate` over $`\mathcal{J}`$ — the ramp limit a process's up row reads — PyPSA's `ramp_limit_up`, or the full build where it has none, since a start-up ramp alone builds the row |
| $`\widetilde{\mathrm{rd}}^{z}`$ | `Process_ramp_down_rate` over $`\mathcal{J}`$ — the ramp limit a process's down row reads — PyPSA's `ramp_limit_down`, or the full build where it has none, since a shut-down ramp alone builds the row |
| $`\widetilde{\mathrm{ru}}^{z,\mathrm{up}}`$ | `Process_start_up_rate` over $`\mathcal{J}`$ — the start-up ramp a process's up row reads — PyPSA's `ramp_limit_start_up`, or the full build where it has none |
| $`\widetilde{\mathrm{rd}}^{z,\mathrm{dn}}`$ | `Process_shut_down_rate` over $`\mathcal{J}`$ — the shut-down ramp a process's down row reads — PyPSA's `ramp_limit_shut_down`, or the full build where it has none |
| $`\widehat{\mathrm{z}}^{\mathrm{nom}}`$ | `Process_p_nom_committed` over $`\mathcal{J}`$ — the build a committed process's ramp rows are taken against — one module where the build is extendable and modular, the given build otherwise |
| $`\Delta^{z,+}`$ | `Process_ramp_up_allowance` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — how far a process may raise internal power between two snapshots — its ramp limit of the build while it stays on, plus its start-up ramp in the snapshot it turns on |
| $`\Delta^{z,-}`$ | `Process_ramp_down_allowance` over $`\Xi \times \mathcal{T} \times \mathcal{J}`$ — how far a process may lower internal power between two snapshots — its ramp limit of the build while it stays on, plus its shut-down ramp in the snapshot it turns off |
| $`\overleftarrow{\mathit{soc}}`$ | `StorageUnit_charge_carried_in` over $`\Xi \times \mathcal{T} \times \mathcal{S}`$ — the charge a unit opens a snapshot with — its last snapshot's less standing loss where it is cyclic, the given initial charge at the start of the horizon, which no standing loss has touched yet, and the previous snapshot's less standing loss otherwise. Per period, the same holds with each investment period as the horizon |
| $`\overleftarrow{e}`$ | `Store_energy_carried_in` over $`\Xi \times \mathcal{T} \times \mathcal{V}`$ — the energy a store opens a snapshot with — its last snapshot's less standing loss where it is cyclic, the given initial energy at the start of the horizon, which no standing loss has touched yet, and the previous snapshot's less standing loss otherwise. Per period, the same holds with each investment period as the horizon |
| $`\overrightarrow{f}`$ | `Link_output_arrival` over $`\Xi \times \mathcal{T} \times \mathcal{O}`$ — what a link delivers to an output port at a snapshot — its flow after the port's efficiency, delayed by the port's `delay`; where the port is `cyclic_delay` the delayed flow wraps from the horizon's end, and where it is not the flow still in transit at the first snapshots is lost. A port that does not delay (`delay` zero) delivers its flow unshifted, cyclic or not |
| $`\overrightarrow{z}`$ | `Process_output_arrival` over $`\Xi \times \mathcal{T} \times \mathcal{R}`$ — what a process transfers at a port at a snapshot — its internal power times the port's rate, delayed by the port's `delay`; where the port is `cyclic_delay` the delayed transfer wraps from the horizon's end, and where it is not the energy still in transit at the first snapshots is lost. A port that does not delay (`delay` zero) transfers at once, cyclic or not |
| $`\mathit{primary\_energy}`$ | `primary_energy` over $`\Xi \times \mathcal{I}`$ — what a `primary_energy` row totals — weighted generator energy, less the charge left in weighted storage at the horizon's end; the initial charge it is compared against is folded into the row's constant |
| $`\mathit{operational\_limit}`$ | `operational_limit` over $`\Xi \times \mathcal{I}`$ — what an `operational_limit` row totals — the weighted energy its generators deliver, plus what its non-cyclic storage draws down; the initial charge it draws from is folded into the row's constant |
| $`\mathit{transmission\_volume\_expansion}`$ | `transmission_volume_expansion` over $`\mathcal{I}`$ — what a `transmission_volume_expansion_limit` row totals — length times the chosen build of the row's branches |
| $`\mathit{transmission\_expansion\_cost}`$ | `transmission_expansion_cost` over $`\mathcal{I}`$ — what a `transmission_expansion_cost_limit` row totals — capital cost times the chosen build of the row's branches |
| $`\mathit{tech\_capacity\_expansion}`$ | `tech_capacity_expansion` over $`\mathcal{I}`$ — what a `tech_capacity_expansion_limit` row totals — the chosen build of the row's carrier-and-bus set |
| $`\mathit{scenario\_opex}`$ | `scenario_opex` over $`\Xi`$ — what a future costs to run — every operating term, weighted by the snapshot's hours and its period, before the scenario's own weight |
| $`\mathit{Carrier\_additions}`$ | `Carrier_additions` over $`\mathcal{Y} \times \mathcal{I}`$ — what a carrier adds in a period — every extendable component of that carrier, counting each build in the first period it stands in. PyPSA sums the components that carry a carrier attribute; the transformer term is the spec's own extension, since PyPSA gives a transformer no carrier |

Upright is what the model is given — a parameter such as $`\mathrm{Transformer\_phase\_shift\_varying}`$, a coordinate map, a label — and italic is what the solver chooses, such as $`\mathit{Transformer\_phase\_shift}`$. An index is italic too, being what a quantifier chooses, and a set is script.

$`t \ominus k`$ denotes cyclic translation: index $`t-k`$ taken modulo the size of the dimension (`roll`). Plain $`t-k`$ (`shift`) has no wraparound — terms translated past the edge are simply absent.

$`t \boxminus_{v} k`$ denotes translation with $`v`$ standing where index $`t-k`$ leaves the dimension (`shift(edge=v)`), so the row at that boundary is built and carries $`v`$ rather than being dropped.

$`t \ominus^{\mathrm{relation}(t)} k`$ denotes a translation counted inside the group a relation puts $`t`$ in (`shift(by=relation)`), so a term never crosses out of its own group. The two modifiers take different slots — the group above, the fill below — so $`t \boxminus_{v}^{\mathrm{relation}(t)} k`$ is both at once.

$`\mathrm{pos}(t)`$ denotes where index $`t`$ sits along its dimension's own order — the order `shift` steps along, not the order labels sort in — counted from $`0`$. The index itself stays the coordinate, so $`t`$ compares against labels and $`\mathrm{pos}(t)`$ against positions.

$`\mathrm{pos}_{\mathrm{relation}(t)}(t)`$ counts within the group a relation puts $`t`$ in: the subscript names the map, $`\mathcal{T}_{\mathrm{relation}(t)}`$ is the group it lands in, and that group has a first position of its own.

### Objective

```yaml
objective:
  sense: minimize
  description: capacity once per active period, operation in expectation over the scenarios, and a share of it at the tail
  expression: >-
    sum(Generator_p_nom_ext * Generator_capital_cost * Generator_capital_weight)
    + sum(Link_p_nom_ext * Link_capital_cost * Link_capital_weight)
    + sum(StorageUnit_p_nom_ext * StorageUnit_capital_cost * StorageUnit_capital_weight)
    + sum(Store_e_nom_ext * Store_capital_cost * Store_capital_weight)
    + sum(Line_s_nom_ext * Line_capital_cost * Line_capital_weight)
    + sum(Process_p_nom_ext * Process_capital_cost * Process_capital_weight)
    + sum(Transformer_s_nom_ext * Transformer_capital_cost * Transformer_capital_weight)
    + (1 - CVaR_omega) * sum(scenario_weight * scenario_opex, over=scenario)
    + CVaR_omega * CVaR
```

```math
\min \sum_{g \in \mathcal{G}} P_{g} \cdot \mathrm{c}^{\mathrm{cap}}_{g} \cdot \mathrm{W}_{g} + \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{c}^{\mathrm{cap},f}_{l} \cdot \mathrm{W}^{f}_{l} + \sum_{s \in \mathcal{S}} H_{s} \cdot \mathrm{c}^{\mathrm{cap},h}_{s} \cdot \mathrm{W}^{h}_{s} + \sum_{v \in \mathcal{V}} E_{v} \cdot \mathrm{c}^{\mathrm{cap},e}_{v} \cdot \mathrm{W}^{e}_{v} + \sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{c}^{\mathrm{cap},s}_{k} \cdot \mathrm{W}^{s}_{k} + \sum_{j \in \mathcal{J}} Z_{j} \cdot \mathrm{c}^{\mathrm{cap},z}_{j} \cdot \mathrm{W}^{z}_{j} + \sum_{m \in \mathcal{M}} \Sigma_{m} \cdot \mathrm{c}^{\mathrm{cap},\sigma}_{m} \cdot \mathrm{W}^{\sigma}_{m} + \left( 1 - \omega \right) \cdot \left( \sum_{\xi \in \Xi} \pi_{\xi} \cdot \mathit{scenario\_opex}_{\xi} \right) + \omega \cdot CVaR
```

### `Generator-fix-p-lower`

`Generator_fix_p_lower`

```yaml
Generator_fix_p_lower:
  description: "`Generator-fix-p-lower` — a fixed generator outputs at least its minimum"
  dims: [scenario, snapshot, generator]
  where: not Generator_p_nom_extendable AND not Generator_committable AND Generator_active
  expression: Generator_p >= Generator_p_min_pu * Generator_p_nom
```

```math
p_{\xi,t,g} \ge \underline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \neg \mathrm{ext}_{g} \wedge \neg \mathrm{com}_{g} \wedge \mathrm{on}_{t,g}
```

### `Generator-fix-p-upper`

`Generator_fix_p_upper`

```yaml
Generator_fix_p_upper:
  description: "`Generator-fix-p-upper` — a fixed generator outputs at most what is available"
  dims: [scenario, snapshot, generator]
  where: not Generator_p_nom_extendable AND not Generator_committable AND Generator_active
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom
```

```math
p_{\xi,t,g} \le \overline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \neg \mathrm{ext}_{g} \wedge \neg \mathrm{com}_{g} \wedge \mathrm{on}_{t,g}
```

### `Link-fix-p-lower`

`Link_fix_p_lower`

```yaml
Link_fix_p_lower:
  description: "`Link-fix-p-lower` — a fixed link carries at least its minimum, negative for the other way"
  dims: [scenario, snapshot, link]
  where: not Link_p_nom_extendable AND not Link_committable AND Link_active
  expression: Link_p >= Link_p_min_pu * Link_p_nom
```

```math
f_{\xi,t,l} \ge \underline{\mathrm{f}}_{t,l} \cdot \mathrm{f}^{\mathrm{nom}}_{l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \neg \mathrm{ext}^{f}_{l} \wedge \neg \mathrm{com}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-fix-p-upper`

`Link_fix_p_upper`

```yaml
Link_fix_p_upper:
  description: "`Link-fix-p-upper` — a fixed link carries at most its nominal power"
  dims: [scenario, snapshot, link]
  where: not Link_p_nom_extendable AND not Link_committable AND Link_active
  expression: Link_p <= Link_p_max_pu * Link_p_nom
```

```math
f_{\xi,t,l} \le \overline{\mathrm{f}}_{t,l} \cdot \mathrm{f}^{\mathrm{nom}}_{l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \neg \mathrm{ext}^{f}_{l} \wedge \neg \mathrm{com}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

### `Generator-ext-p-lower`

`Generator_ext_p_lower`

```yaml
Generator_ext_p_lower:
  description: "`Generator-ext-p-lower` — an extendable generator outputs at least its minimum of the chosen build"
  dims: [scenario, snapshot, generator]
  where: Generator_p_nom_extendable AND not Generator_committable AND Generator_active
  expression: Generator_p >= Generator_p_min_pu * Generator_p_nom_ext
```

```math
p_{\xi,t,g} \ge \underline{\mathrm{p}}_{t,g} \cdot P_{g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{ext}_{g} \wedge \neg \mathrm{com}_{g} \wedge \mathrm{on}_{t,g}
```

### `Generator-ext-p-upper`

`Generator_ext_p_upper`

```yaml
Generator_ext_p_upper:
  description: "`Generator-ext-p-upper` — an extendable generator outputs at most what is available of the chosen build"
  dims: [scenario, snapshot, generator]
  where: Generator_p_nom_extendable AND not Generator_committable AND Generator_active
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom_ext
```

```math
p_{\xi,t,g} \le \overline{\mathrm{p}}_{t,g} \cdot P_{g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{ext}_{g} \wedge \neg \mathrm{com}_{g} \wedge \mathrm{on}_{t,g}
```

### `Generator-ext-p_nom-lower`

`Generator_ext_p_nom_lower`

```yaml
Generator_ext_p_nom_lower:
  description: "`Generator-ext-p_nom-lower` — the chosen build is at least its floor"
  dims: [generator]
  where: Generator_p_nom_extendable
  expression: Generator_p_nom_ext >= Generator_p_nom_min
```

```math
P_{g} \ge \underline{\mathrm{p}}^{\mathrm{nom}}_{g} \qquad \forall\, g \in \mathcal{G} \,:\, \mathrm{ext}_{g}
```

### `Generator-ext-p_nom-upper`

`Generator_ext_p_nom_upper`

```yaml
Generator_ext_p_nom_upper:
  description: "`Generator-ext-p_nom-upper` — the chosen build is at most its cap; a cap of infinity is no row"
  dims: [generator]
  where: Generator_p_nom_extendable AND Generator_p_nom_max
  expression: Generator_p_nom_ext <= Generator_p_nom_max
```

```math
P_{g} \le \overline{\mathrm{p}}^{\mathrm{nom}}_{g} \qquad \forall\, g \in \mathcal{G} \,:\, \mathrm{ext}_{g} \wedge \overline{\mathrm{p}}^{\mathrm{nom}}_{g} \text{ is defined}
```

### `Generator-p_nom_set`

`Generator_p_nom_set`

```yaml
Generator_p_nom_set:
  description: "`Generator-p_nom_set` — the chosen build pinned, wherever a value is given"
  dims: [generator]
  where: Generator_p_nom_extendable AND Generator_p_nom_set
  expression: Generator_p_nom_ext == Generator_p_nom_set
```

```math
P_{g} = \mathrm{p}^{\mathrm{nom,set}}_{g} \qquad \forall\, g \in \mathcal{G} \,:\, \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{nom,set}}_{g} \text{ is defined}
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
\sum_{t \in \mathcal{T}} p_{\xi,t,g} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \ge \underline{\mathrm{E}}_{g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \underline{\mathrm{E}}_{g} \text{ is defined}
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
\sum_{t \in \mathcal{T}} p_{\xi,t,g} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \le \overline{\mathrm{E}}_{g} \qquad \forall\, \xi \in \Xi,\ g \in \mathcal{G} \,:\, \overline{\mathrm{E}}_{g} \text{ is defined}
```

### `Link-ext-p-lower`

`Link_ext_p_lower`

```yaml
Link_ext_p_lower:
  description: "`Link-ext-p-lower` — an extendable link carries at least its minimum of the chosen build, negative for the other way"
  dims: [scenario, snapshot, link]
  where: Link_p_nom_extendable AND not Link_committable AND Link_active
  expression: Link_p >= Link_p_min_pu * Link_p_nom_ext
```

```math
f_{\xi,t,l} \ge \underline{\mathrm{f}}_{t,l} \cdot F_{l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{ext}^{f}_{l} \wedge \neg \mathrm{com}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-ext-p-upper`

`Link_ext_p_upper`

```yaml
Link_ext_p_upper:
  description: "`Link-ext-p-upper` — an extendable link carries at most the chosen build"
  dims: [scenario, snapshot, link]
  where: Link_p_nom_extendable AND not Link_committable AND Link_active
  expression: Link_p <= Link_p_max_pu * Link_p_nom_ext
```

```math
f_{\xi,t,l} \le \overline{\mathrm{f}}_{t,l} \cdot F_{l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{ext}^{f}_{l} \wedge \neg \mathrm{com}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-ext-p_nom-lower`

`Link_ext_p_nom_lower`

```yaml
Link_ext_p_nom_lower:
  description: "`Link-ext-p_nom-lower` — the chosen build is at least its floor"
  dims: [link]
  where: Link_p_nom_extendable
  expression: Link_p_nom_ext >= Link_p_nom_min
```

```math
F_{l} \ge \underline{\mathrm{f}}^{\mathrm{nom}}_{l} \qquad \forall\, l \in \mathcal{L} \,:\, \mathrm{ext}^{f}_{l}
```

### `Link-ext-p_nom-upper`

`Link_ext_p_nom_upper`

```yaml
Link_ext_p_nom_upper:
  description: "`Link-ext-p_nom-upper` — the chosen build is at most its cap; a cap of infinity is no row"
  dims: [link]
  where: Link_p_nom_extendable AND Link_p_nom_max
  expression: Link_p_nom_ext <= Link_p_nom_max
```

```math
F_{l} \le \overline{\mathrm{f}}^{\mathrm{nom}}_{l} \qquad \forall\, l \in \mathcal{L} \,:\, \mathrm{ext}^{f}_{l} \wedge \overline{\mathrm{f}}^{\mathrm{nom}}_{l} \text{ is defined}
```

### `Link-p_nom_set`

`Link_p_nom_set`

```yaml
Link_p_nom_set:
  description: "`Link-p_nom_set` — the chosen build pinned, wherever a value is given"
  dims: [link]
  where: Link_p_nom_extendable AND Link_p_nom_set
  expression: Link_p_nom_ext == Link_p_nom_set
```

```math
F_{l} = \mathrm{f}^{\mathrm{nom,set}}_{l} \qquad \forall\, l \in \mathcal{L} \,:\, \mathrm{ext}^{f}_{l} \wedge \mathrm{f}^{\mathrm{nom,set}}_{l} \text{ is defined}
```

### `Process-fix-p-lower`

`Process_fix_p_lower`

```yaml
Process_fix_p_lower:
  description: "`Process-fix-p-lower` — a fixed process runs at least its minimum, negative for the other way"
  dims: [scenario, snapshot, process]
  where: not Process_p_nom_extendable AND not Process_committable AND Process_active
  expression: Process_p >= Process_p_min_pu * Process_p_nom
```

```math
z_{\xi,t,j} \ge \underline{\mathrm{z}}_{t,j} \cdot \mathrm{z}^{\mathrm{nom}}_{j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \neg \mathrm{ext}^{z}_{j} \wedge \neg \mathrm{com}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-fix-p-upper`

`Process_fix_p_upper`

```yaml
Process_fix_p_upper:
  description: "`Process-fix-p-upper` — a fixed process runs at most its nominal power"
  dims: [scenario, snapshot, process]
  where: not Process_p_nom_extendable AND not Process_committable AND Process_active
  expression: Process_p <= Process_p_max_pu * Process_p_nom
```

```math
z_{\xi,t,j} \le \overline{\mathrm{z}}_{t,j} \cdot \mathrm{z}^{\mathrm{nom}}_{j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \neg \mathrm{ext}^{z}_{j} \wedge \neg \mathrm{com}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-ext-p-lower`

`Process_ext_p_lower`

```yaml
Process_ext_p_lower:
  description: "`Process-ext-p-lower` — an extendable process runs at least its minimum of the chosen build, negative for the other way"
  dims: [scenario, snapshot, process]
  where: Process_p_nom_extendable AND not Process_committable AND Process_active
  expression: Process_p >= Process_p_min_pu * Process_p_nom_ext
```

```math
z_{\xi,t,j} \ge \underline{\mathrm{z}}_{t,j} \cdot Z_{j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{ext}^{z}_{j} \wedge \neg \mathrm{com}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-ext-p-upper`

`Process_ext_p_upper`

```yaml
Process_ext_p_upper:
  description: "`Process-ext-p-upper` — an extendable process runs at most the chosen build"
  dims: [scenario, snapshot, process]
  where: Process_p_nom_extendable AND not Process_committable AND Process_active
  expression: Process_p <= Process_p_max_pu * Process_p_nom_ext
```

```math
z_{\xi,t,j} \le \overline{\mathrm{z}}_{t,j} \cdot Z_{j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{ext}^{z}_{j} \wedge \neg \mathrm{com}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-ext-p_nom-lower`

`Process_ext_p_nom_lower`

```yaml
Process_ext_p_nom_lower:
  description: "`Process-ext-p_nom-lower` — the chosen build is at least its floor"
  dims: [process]
  where: Process_p_nom_extendable
  expression: Process_p_nom_ext >= Process_p_nom_min
```

```math
Z_{j} \ge \underline{\mathrm{z}}^{\mathrm{nom}}_{j} \qquad \forall\, j \in \mathcal{J} \,:\, \mathrm{ext}^{z}_{j}
```

### `Process-ext-p_nom-upper`

`Process_ext_p_nom_upper`

```yaml
Process_ext_p_nom_upper:
  description: "`Process-ext-p_nom-upper` — the chosen build is at most its cap; a cap of infinity is no row"
  dims: [process]
  where: Process_p_nom_extendable AND Process_p_nom_max
  expression: Process_p_nom_ext <= Process_p_nom_max
```

```math
Z_{j} \le \overline{\mathrm{z}}^{\mathrm{nom}}_{j} \qquad \forall\, j \in \mathcal{J} \,:\, \mathrm{ext}^{z}_{j} \wedge \overline{\mathrm{z}}^{\mathrm{nom}}_{j} \text{ is defined}
```

### `Process-p_nom_set`

`Process_p_nom_set`

```yaml
Process_p_nom_set:
  description: "`Process-p_nom_set` — the chosen build pinned, wherever a value is given"
  dims: [process]
  where: Process_p_nom_extendable AND Process_p_nom_set
  expression: Process_p_nom_ext == Process_p_nom_set
```

```math
Z_{j} = \mathrm{z}^{\mathrm{nom,set}}_{j} \qquad \forall\, j \in \mathcal{J} \,:\, \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{nom,set}}_{j} \text{ is defined}
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
h^{+}_{\xi,t,s} \le \overline{\mathrm{h}}_{t,s} \cdot \mathrm{h}^{\mathrm{nom}}_{s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \neg \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
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
h^{-}_{\xi,t,s} \le -\underline{\mathrm{h}}_{t,s} \cdot \mathrm{h}^{\mathrm{nom}}_{s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \neg \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
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
\mathit{soc}_{\xi,t,s} \le \mathrm{T}^{h}_{s} \cdot \mathrm{h}^{\mathrm{nom}}_{s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \neg \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

### `Generator-com-p-lower`

`Generator_com_p_lower`

```yaml
Generator_com_p_lower:
  description: "`Generator-com-p-lower` — a committed unit outputs at least its minimum; off, at least nothing"
  dims: [scenario, snapshot, generator]
  where: Generator_committable AND not Generator_p_nom_extendable AND Generator_active
  expression: Generator_p >= Generator_p_min_pu * Generator_p_nom * Generator_status
```

```math
p_{\xi,t,g} \ge \underline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot u_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \neg \mathrm{ext}_{g} \wedge \mathrm{on}_{t,g}
```

### `Generator-com-p-upper`

`Generator_com_p_upper`

```yaml
Generator_com_p_upper:
  description: "`Generator-com-p-upper` — a committed unit outputs at most what is available; off, at most nothing"
  dims: [scenario, snapshot, generator]
  where: Generator_committable AND not Generator_p_nom_extendable AND Generator_active
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom * Generator_status
```

```math
p_{\xi,t,g} \le \overline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot u_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \neg \mathrm{ext}_{g} \wedge \mathrm{on}_{t,g}
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
\sum_{t' \in \mathcal{T} \,:\, 0 \le t - t' < \mathrm{UT}} \mathit{up}_{\xi,t',g} \le u_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{UT}_{g} > 0 \wedge \mathrm{pos}(t) > 0 \wedge \mathrm{on}_{t,g}
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
\sum_{t' \in \mathcal{T} \,:\, 0 \le t - t' < \mathrm{DT}} \mathit{dn}_{\xi,t',g} \le 1 - u_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{DT}_{g} > 0 \wedge \mathrm{pos}(t) > 0 \wedge \mathrm{on}_{t,g}
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
u_{\xi,t,g} = 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{hold}_{t,g} \wedge \mathrm{on}_{t,g}
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
u_{\xi,t,g} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{rest}_{t,g} \wedge \mathrm{on}_{t,g}
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
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND Generator_status_initial == 0))
    AND Generator_active
  expression: >-
    Generator_p - Generator_previous_p <=
    Generator_ramp_up_rate * Generator_p_nom_ext
    + Generator_big_m - Generator_big_m * Generator_previous_status
```

```math
p_{\xi,t,g} - \overleftarrow{p}_{\xi,t,g} \le \widetilde{\mathrm{ru}}_{g} \cdot P_{g} + \mathrm{M}_{g} - \mathrm{M}_{g} \cdot \overleftarrow{u}_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \left( \mathrm{ru}_{g} \text{ is defined} \vee \mathrm{ru}^{\mathrm{up}}_{g} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \mathrm{u}^{0}_{g} = 0 \right) \wedge \mathrm{on}_{t,g}
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
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND Generator_status_initial == 0))
    AND Generator_active
  expression: >-
    Generator_p - Generator_previous_p <=
    Generator_start_up_rate * Generator_p_nom_ext
    + Generator_big_m - Generator_big_m * Generator_start_up
```

```math
p_{\xi,t,g} - \overleftarrow{p}_{\xi,t,g} \le \widetilde{\mathrm{ru}}^{\mathrm{up}}_{g} \cdot P_{g} + \mathrm{M}_{g} - \mathrm{M}_{g} \cdot \mathit{up}_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \left( \mathrm{ru}_{g} \text{ is defined} \vee \mathrm{ru}^{\mathrm{up}}_{g} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \mathrm{u}^{0}_{g} = 0 \right) \wedge \mathrm{on}_{t,g}
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
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND Generator_status_initial == 0))
    AND Generator_active
  expression: >-
    Generator_previous_p - Generator_p <=
    Generator_ramp_down_rate * Generator_p_nom_ext
    + Generator_big_m - Generator_big_m * Generator_status
```

```math
\overleftarrow{p}_{\xi,t,g} - p_{\xi,t,g} \le \widetilde{\mathrm{rd}}_{g} \cdot P_{g} + \mathrm{M}_{g} - \mathrm{M}_{g} \cdot u_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \left( \mathrm{rd}_{g} \text{ is defined} \vee \mathrm{rd}^{\mathrm{dn}}_{g} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \mathrm{u}^{0}_{g} = 0 \right) \wedge \mathrm{on}_{t,g}
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
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND Generator_status_initial == 0))
    AND Generator_active
  expression: >-
    Generator_previous_p - Generator_p <=
    Generator_shut_down_rate * Generator_p_nom_ext
    + Generator_big_m - Generator_big_m * Generator_shut_down
```

```math
\overleftarrow{p}_{\xi,t,g} - p_{\xi,t,g} \le \widetilde{\mathrm{rd}}^{\mathrm{dn}}_{g} \cdot P_{g} + \mathrm{M}_{g} - \mathrm{M}_{g} \cdot \mathit{dn}_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \left( \mathrm{rd}_{g} \text{ is defined} \vee \mathrm{rd}^{\mathrm{dn}}_{g} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \mathrm{u}^{0}_{g} = 0 \right) \wedge \mathrm{on}_{t,g}
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
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom_ext
```

```math
p_{\xi,t,g} \le \overline{\mathrm{p}}_{t,g} \cdot P_{g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
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
p_{\xi,t,g} \le \mathrm{M}_{g} \cdot u_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
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
    Generator_p_min_pu * Generator_p_nom_ext
    + Generator_big_m * Generator_status - Generator_big_m
```

```math
p_{\xi,t,g} \ge \underline{\mathrm{p}}_{t,g} \cdot P_{g} + \mathrm{M}_{g} \cdot u_{\xi,t,g} - \mathrm{M}_{g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
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
  expression: Generator_p >= Generator_p_min_pu * Generator_p_nom_mod * Generator_status
```

```math
p_{\xi,t,g} \ge \underline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{mod}}_{g} \cdot u_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \wedge \mathrm{on}_{t,g}
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
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom_mod * Generator_status
```

```math
p_{\xi,t,g} \le \overline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{mod}}_{g} \cdot u_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \wedge \mathrm{on}_{t,g}
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
u_{\xi,t,g} \le \mathrm{N}^{\mathrm{fix}}_{g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \neg \left( \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
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
\mathit{up}_{\xi,t,g} \le \mathrm{N}^{\mathrm{fix}}_{g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \neg \left( \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
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
\mathit{dn}_{\xi,t,g} \le \mathrm{N}^{\mathrm{fix}}_{g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \neg \left( \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \wedge \mathrm{on}_{t,g}
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

### `Link-com-p-lower`

`Link_com_p_lower`

```yaml
Link_com_p_lower:
  description: "`Link-com-p-lower` — a committed link flows at least its minimum; off, at least nothing"
  dims: [scenario, snapshot, link]
  where: Link_committable AND not Link_p_nom_extendable AND Link_active
  expression: Link_p >= Link_p_min_pu * Link_p_nom * Link_status
```

```math
f_{\xi,t,l} \ge \underline{\mathrm{f}}_{t,l} \cdot \mathrm{f}^{\mathrm{nom}}_{l} \cdot u^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \neg \mathrm{ext}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-com-p-upper`

`Link_com_p_upper`

```yaml
Link_com_p_upper:
  description: "`Link-com-p-upper` — a committed link flows at most what is available; off, at most nothing"
  dims: [scenario, snapshot, link]
  where: Link_committable AND not Link_p_nom_extendable AND Link_active
  expression: Link_p <= Link_p_max_pu * Link_p_nom * Link_status
```

```math
f_{\xi,t,l} \le \overline{\mathrm{f}}_{t,l} \cdot \mathrm{f}^{\mathrm{nom}}_{l} \cdot u^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \neg \mathrm{ext}^{f}_{l} \wedge \mathrm{on}^{f}_{t,l}
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
\sum_{t' \in \mathcal{T} \,:\, 0 \le t - t' < \mathrm{UT}^{f}} \mathit{up}^{f}_{\xi,t',l} \le u^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{UT}^{f}_{l} > 0 \wedge \mathrm{pos}(t) > 0 \wedge \mathrm{on}^{f}_{t,l}
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
\sum_{t' \in \mathcal{T} \,:\, 0 \le t - t' < \mathrm{DT}^{f}} \mathit{dn}^{f}_{\xi,t',l} \le 1 - u^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{DT}^{f}_{l} > 0 \wedge \mathrm{pos}(t) > 0 \wedge \mathrm{on}^{f}_{t,l}
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
u^{f}_{\xi,t,l} = 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{hold}^{f}_{t,l} \wedge \mathrm{on}^{f}_{t,l}
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
u^{f}_{\xi,t,l} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{rest}^{f}_{t,l} \wedge \mathrm{on}^{f}_{t,l}
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
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND Link_status_initial == 0))
    AND Link_active
  expression: >-
    Link_p - Link_previous_p <=
    Link_ramp_up_rate * Link_p_nom_ext
    + Link_big_m - Link_big_m * Link_previous_status
```

```math
f_{\xi,t,l} - \overleftarrow{f}_{\xi,t,l} \le \widetilde{\mathrm{ru}}^{f}_{l} \cdot F_{l} + \mathrm{M}^{f}_{l} - \mathrm{M}^{f}_{l} \cdot \overleftarrow{u}^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \left( \mathrm{ru}^{f}_{l} \text{ is defined} \vee \mathrm{ru}^{f,\mathrm{up}}_{l} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \mathrm{u}^{f,0}_{l} = 0 \right) \wedge \mathrm{on}^{f}_{t,l}
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
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND Link_status_initial == 0))
    AND Link_active
  expression: >-
    Link_p - Link_previous_p <=
    Link_start_up_rate * Link_p_nom_ext
    + Link_big_m - Link_big_m * Link_start_up
```

```math
f_{\xi,t,l} - \overleftarrow{f}_{\xi,t,l} \le \widetilde{\mathrm{ru}}^{f,\mathrm{up}}_{l} \cdot F_{l} + \mathrm{M}^{f}_{l} - \mathrm{M}^{f}_{l} \cdot \mathit{up}^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \left( \mathrm{ru}^{f}_{l} \text{ is defined} \vee \mathrm{ru}^{f,\mathrm{up}}_{l} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \mathrm{u}^{f,0}_{l} = 0 \right) \wedge \mathrm{on}^{f}_{t,l}
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
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND Link_status_initial == 0))
    AND Link_active
  expression: >-
    Link_previous_p - Link_p <=
    Link_ramp_down_rate * Link_p_nom_ext
    + Link_big_m - Link_big_m * Link_status
```

```math
\overleftarrow{f}_{\xi,t,l} - f_{\xi,t,l} \le \widetilde{\mathrm{rd}}^{f}_{l} \cdot F_{l} + \mathrm{M}^{f}_{l} - \mathrm{M}^{f}_{l} \cdot u^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \left( \mathrm{rd}^{f}_{l} \text{ is defined} \vee \mathrm{rd}^{f,\mathrm{dn}}_{l} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \mathrm{u}^{f,0}_{l} = 0 \right) \wedge \mathrm{on}^{f}_{t,l}
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
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND Link_status_initial == 0))
    AND Link_active
  expression: >-
    Link_previous_p - Link_p <=
    Link_shut_down_rate * Link_p_nom_ext
    + Link_big_m - Link_big_m * Link_shut_down
```

```math
\overleftarrow{f}_{\xi,t,l} - f_{\xi,t,l} \le \widetilde{\mathrm{rd}}^{f,\mathrm{dn}}_{l} \cdot F_{l} + \mathrm{M}^{f}_{l} - \mathrm{M}^{f}_{l} \cdot \mathit{dn}^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \left( \mathrm{rd}^{f}_{l} \text{ is defined} \vee \mathrm{rd}^{f,\mathrm{dn}}_{l} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \mathrm{u}^{f,0}_{l} = 0 \right) \wedge \mathrm{on}^{f}_{t,l}
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
  expression: Link_p <= Link_p_max_pu * Link_p_nom_ext
```

```math
f_{\xi,t,l} \le \overline{\mathrm{f}}_{t,l} \cdot F_{l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \mathrm{on}^{f}_{t,l}
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
f_{\xi,t,l} \le \mathrm{M}^{f}_{l} \cdot u^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \mathrm{on}^{f}_{t,l}
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
    Link_p_min_pu * Link_p_nom_ext
    + Link_big_m * Link_status - Link_big_m
```

```math
f_{\xi,t,l} \ge \underline{\mathrm{f}}_{t,l} \cdot F_{l} + \mathrm{M}^{f}_{l} \cdot u^{f}_{\xi,t,l} - \mathrm{M}^{f}_{l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \mathrm{on}^{f}_{t,l}
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
  expression: Link_p >= Link_p_min_pu * Link_p_nom_mod * Link_status
```

```math
f_{\xi,t,l} \ge \underline{\mathrm{f}}_{t,l} \cdot \mathrm{f}^{\mathrm{mod}}_{l} \cdot u^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \wedge \mathrm{on}^{f}_{t,l}
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
  expression: Link_p <= Link_p_max_pu * Link_p_nom_mod * Link_status
```

```math
f_{\xi,t,l} \le \overline{\mathrm{f}}_{t,l} \cdot \mathrm{f}^{\mathrm{mod}}_{l} \cdot u^{f}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \wedge \mathrm{on}^{f}_{t,l}
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
u^{f}_{\xi,t,l} \le \mathrm{N}^{f,\mathrm{fix}}_{l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \neg \left( \mathrm{ext}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \mathrm{on}^{f}_{t,l}
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
\mathit{up}^{f}_{\xi,t,l} \le \mathrm{N}^{f,\mathrm{fix}}_{l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \neg \left( \mathrm{ext}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \mathrm{on}^{f}_{t,l}
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
\mathit{dn}^{f}_{\xi,t,l} \le \mathrm{N}^{f,\mathrm{fix}}_{l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{com}^{f}_{l} \wedge \neg \left( \mathrm{ext}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \wedge \mathrm{on}^{f}_{t,l}
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

### `Process-com-p-lower`

`Process_com_p_lower`

```yaml
Process_com_p_lower:
  description: "`Process-com-p-lower` — a committed process runs at least its minimum; off, at least nothing"
  dims: [scenario, snapshot, process]
  where: Process_committable AND not Process_p_nom_extendable AND Process_active
  expression: Process_p >= Process_p_min_pu * Process_p_nom * Process_status
```

```math
z_{\xi,t,j} \ge \underline{\mathrm{z}}_{t,j} \cdot \mathrm{z}^{\mathrm{nom}}_{j} \cdot u^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \neg \mathrm{ext}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-com-p-upper`

`Process_com_p_upper`

```yaml
Process_com_p_upper:
  description: "`Process-com-p-upper` — a committed process runs at most what is available; off, at most nothing"
  dims: [scenario, snapshot, process]
  where: Process_committable AND not Process_p_nom_extendable AND Process_active
  expression: Process_p <= Process_p_max_pu * Process_p_nom * Process_status
```

```math
z_{\xi,t,j} \le \overline{\mathrm{z}}_{t,j} \cdot \mathrm{z}^{\mathrm{nom}}_{j} \cdot u^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \neg \mathrm{ext}^{z}_{j} \wedge \mathrm{on}^{z}_{t,j}
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
\sum_{t' \in \mathcal{T} \,:\, 0 \le t - t' < \mathrm{UT}^{z}} \mathit{up}^{z}_{\xi,t',j} \le u^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{UT}^{z}_{j} > 0 \wedge \mathrm{pos}(t) > 0 \wedge \mathrm{on}^{z}_{t,j}
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
\sum_{t' \in \mathcal{T} \,:\, 0 \le t - t' < \mathrm{DT}^{z}} \mathit{dn}^{z}_{\xi,t',j} \le 1 - u^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{DT}^{z}_{j} > 0 \wedge \mathrm{pos}(t) > 0 \wedge \mathrm{on}^{z}_{t,j}
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
u^{z}_{\xi,t,j} = 1 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{hold}^{z}_{t,j} \wedge \mathrm{on}^{z}_{t,j}
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
u^{z}_{\xi,t,j} = 0 \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{rest}^{z}_{t,j} \wedge \mathrm{on}^{z}_{t,j}
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
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND Process_status_initial == 0))
    AND Process_active
  expression: >-
    Process_p - Process_previous_p <=
    Process_ramp_up_rate * Process_p_nom_ext
    + Process_big_m - Process_big_m * Process_previous_status
```

```math
z_{\xi,t,j} - \overleftarrow{z}_{\xi,t,j} \le \widetilde{\mathrm{ru}}^{z}_{j} \cdot Z_{j} + \mathrm{M}^{z}_{j} - \mathrm{M}^{z}_{j} \cdot \overleftarrow{u}^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \left( \mathrm{ru}^{z}_{j} \text{ is defined} \vee \mathrm{ru}^{z,\mathrm{up}}_{j} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \mathrm{u}^{z,0}_{j} = 0 \right) \wedge \mathrm{on}^{z}_{t,j}
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
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND Process_status_initial == 0))
    AND Process_active
  expression: >-
    Process_p - Process_previous_p <=
    Process_start_up_rate * Process_p_nom_ext
    + Process_big_m - Process_big_m * Process_start_up
```

```math
z_{\xi,t,j} - \overleftarrow{z}_{\xi,t,j} \le \widetilde{\mathrm{ru}}^{z,\mathrm{up}}_{j} \cdot Z_{j} + \mathrm{M}^{z}_{j} - \mathrm{M}^{z}_{j} \cdot \mathit{up}^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \left( \mathrm{ru}^{z}_{j} \text{ is defined} \vee \mathrm{ru}^{z,\mathrm{up}}_{j} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \mathrm{u}^{z,0}_{j} = 0 \right) \wedge \mathrm{on}^{z}_{t,j}
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
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND Process_status_initial == 0))
    AND Process_active
  expression: >-
    Process_previous_p - Process_p <=
    Process_ramp_down_rate * Process_p_nom_ext
    + Process_big_m - Process_big_m * Process_status
```

```math
\overleftarrow{z}_{\xi,t,j} - z_{\xi,t,j} \le \widetilde{\mathrm{rd}}^{z}_{j} \cdot Z_{j} + \mathrm{M}^{z}_{j} - \mathrm{M}^{z}_{j} \cdot u^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \left( \mathrm{rd}^{z}_{j} \text{ is defined} \vee \mathrm{rd}^{z,\mathrm{dn}}_{j} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \mathrm{u}^{z,0}_{j} = 0 \right) \wedge \mathrm{on}^{z}_{t,j}
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
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND Process_status_initial == 0))
    AND Process_active
  expression: >-
    Process_previous_p - Process_p <=
    Process_shut_down_rate * Process_p_nom_ext
    + Process_big_m - Process_big_m * Process_shut_down
```

```math
\overleftarrow{z}_{\xi,t,j} - z_{\xi,t,j} \le \widetilde{\mathrm{rd}}^{z,\mathrm{dn}}_{j} \cdot Z_{j} + \mathrm{M}^{z}_{j} - \mathrm{M}^{z}_{j} \cdot \mathit{dn}^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \left( \mathrm{rd}^{z}_{j} \text{ is defined} \vee \mathrm{rd}^{z,\mathrm{dn}}_{j} \text{ is defined} \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \mathrm{u}^{z,0}_{j} = 0 \right) \wedge \mathrm{on}^{z}_{t,j}
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
  expression: Process_p <= Process_p_max_pu * Process_p_nom_ext
```

```math
z_{\xi,t,j} \le \overline{\mathrm{z}}_{t,j} \cdot Z_{j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j}
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
z_{\xi,t,j} \le \mathrm{M}^{z}_{j} \cdot u^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j}
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
    Process_p_min_pu * Process_p_nom_ext
    + Process_big_m * Process_status - Process_big_m
```

```math
z_{\xi,t,j} \ge \underline{\mathrm{z}}_{t,j} \cdot Z_{j} + \mathrm{M}^{z}_{j} \cdot u^{z}_{\xi,t,j} - \mathrm{M}^{z}_{j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j}
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
  expression: Process_p >= Process_p_min_pu * Process_p_nom_mod * Process_status
```

```math
z_{\xi,t,j} \ge \underline{\mathrm{z}}_{t,j} \cdot \mathrm{z}^{\mathrm{mod}}_{j} \cdot u^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \wedge \mathrm{on}^{z}_{t,j}
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
  expression: Process_p <= Process_p_max_pu * Process_p_nom_mod * Process_status
```

```math
z_{\xi,t,j} \le \overline{\mathrm{z}}_{t,j} \cdot \mathrm{z}^{\mathrm{mod}}_{j} \cdot u^{z}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \wedge \mathrm{on}^{z}_{t,j}
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
u^{z}_{\xi,t,j} \le \mathrm{N}^{z,\mathrm{fix}}_{j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \neg \left( \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j}
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
\mathit{up}^{z}_{\xi,t,j} \le \mathrm{N}^{z,\mathrm{fix}}_{j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \neg \left( \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j}
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
\mathit{dn}^{z}_{\xi,t,j} \le \mathrm{N}^{z,\mathrm{fix}}_{j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{com}^{z}_{j} \wedge \neg \left( \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \wedge \mathrm{on}^{z}_{t,j}
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
s_{\xi,t,k} - \ell_{\xi,t,k} \ge -\overline{\mathrm{s}}_{t,k} \cdot \mathrm{s}^{\mathrm{nom}}_{k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K} \,:\, \neg \mathrm{ext}^{s}_{k} \wedge \mathrm{on}^{s}_{t,k}
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
s_{\xi,t,k} + \ell_{\xi,t,k} \le \overline{\mathrm{s}}_{t,k} \cdot \mathrm{s}^{\mathrm{nom}}_{k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K} \,:\, \neg \mathrm{ext}^{s}_{k} \wedge \mathrm{on}^{s}_{t,k}
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
s_{\xi,t,k} - \ell_{\xi,t,k} \ge -\overline{\mathrm{s}}_{t,k} \cdot S_{k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K} \,:\, \mathrm{ext}^{s}_{k} \wedge \mathrm{on}^{s}_{t,k}
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
s_{\xi,t,k} + \ell_{\xi,t,k} \le \overline{\mathrm{s}}_{t,k} \cdot S_{k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K} \,:\, \mathrm{ext}^{s}_{k} \wedge \mathrm{on}^{s}_{t,k}
```

### `Line-ext-s_nom-lower`

`Line_ext_s_nom_lower`

```yaml
Line_ext_s_nom_lower:
  description: "`Line-ext-s_nom-lower` — the chosen build is at least its floor"
  dims: [line]
  where: Line_s_nom_extendable
  expression: Line_s_nom_ext >= Line_s_nom_min
```

```math
S_{k} \ge \underline{\mathrm{s}}^{\mathrm{nom}}_{k} \qquad \forall\, k \in \mathcal{K} \,:\, \mathrm{ext}^{s}_{k}
```

### `Line-ext-s_nom-upper`

`Line_ext_s_nom_upper`

```yaml
Line_ext_s_nom_upper:
  description: "`Line-ext-s_nom-upper` — the chosen build is at most its cap; a cap of infinity is no row"
  dims: [line]
  where: Line_s_nom_extendable AND Line_s_nom_max
  expression: Line_s_nom_ext <= Line_s_nom_max
```

```math
S_{k} \le \overline{\mathrm{s}}^{\mathrm{nom}}_{k} \qquad \forall\, k \in \mathcal{K} \,:\, \mathrm{ext}^{s}_{k} \wedge \overline{\mathrm{s}}^{\mathrm{nom}}_{k} \text{ is defined}
```

### `Line-s_nom_set`

`Line_s_nom_set`

```yaml
Line_s_nom_set:
  description: "`Line-s_nom_set` — the chosen build pinned, wherever a value is given"
  dims: [line]
  where: Line_s_nom_extendable AND Line_s_nom_set
  expression: Line_s_nom_ext == Line_s_nom_set
```

```math
S_{k} = \mathrm{s}^{\mathrm{nom,set}}_{k} \qquad \forall\, k \in \mathcal{K} \,:\, \mathrm{ext}^{s}_{k} \wedge \mathrm{s}^{\mathrm{nom,set}}_{k} \text{ is defined}
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
s_{\xi,t,k} = \mathrm{s}^{\mathrm{set}}_{t,k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K} \,:\, \mathrm{s}^{\mathrm{set}}_{t,k} \text{ is defined} \wedge \mathrm{on}^{s}_{t,k}
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
\ell_{\xi,t,k} \le \overline{\ell}_{t,k} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K} \,:\, \mathrm{lossy} \wedge \mathrm{on}^{s}_{t,k}
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
\ell_{\xi,t,k} + \mathrm{a}_{t,k,b} \cdot s_{\xi,t,k} \ge \mathrm{b}_{t,k,b} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K},\ b \in \mathcal{B} \,:\, \mathrm{lossy} \wedge \mathrm{on}^{s}_{t,k}
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
\ell_{\xi,t,k} - \mathrm{a}_{t,k,b} \cdot s_{\xi,t,k} \ge \mathrm{b}_{t,k,b} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ k \in \mathcal{K},\ b \in \mathcal{B} \,:\, \mathrm{lossy} \wedge \mathrm{on}^{s}_{t,k}
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
\sigma_{\xi,t,m} - \ell^{\sigma}_{\xi,t,m} \ge -\overline{\sigma}_{t,m} \cdot \sigma^{\mathrm{nom}}_{m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M} \,:\, \neg \mathrm{ext}^{\sigma}_{m} \wedge \mathrm{on}^{\sigma}_{t,m}
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
\sigma_{\xi,t,m} + \ell^{\sigma}_{\xi,t,m} \le \overline{\sigma}_{t,m} \cdot \sigma^{\mathrm{nom}}_{m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M} \,:\, \neg \mathrm{ext}^{\sigma}_{m} \wedge \mathrm{on}^{\sigma}_{t,m}
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
\sigma_{\xi,t,m} - \ell^{\sigma}_{\xi,t,m} \ge -\overline{\sigma}_{t,m} \cdot \Sigma_{m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M} \,:\, \mathrm{ext}^{\sigma}_{m} \wedge \mathrm{on}^{\sigma}_{t,m}
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
\sigma_{\xi,t,m} + \ell^{\sigma}_{\xi,t,m} \le \overline{\sigma}_{t,m} \cdot \Sigma_{m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M} \,:\, \mathrm{ext}^{\sigma}_{m} \wedge \mathrm{on}^{\sigma}_{t,m}
```

### `Transformer-ext-s_nom-lower`

`Transformer_ext_s_nom_lower`

```yaml
Transformer_ext_s_nom_lower:
  description: "`Transformer-ext-s_nom-lower` — the chosen build is at least its floor"
  dims: [transformer]
  where: Transformer_s_nom_extendable
  expression: Transformer_s_nom_ext >= Transformer_s_nom_min
```

```math
\Sigma_{m} \ge \underline{\sigma}^{\mathrm{nom}}_{m} \qquad \forall\, m \in \mathcal{M} \,:\, \mathrm{ext}^{\sigma}_{m}
```

### `Transformer-ext-s_nom-upper`

`Transformer_ext_s_nom_upper`

```yaml
Transformer_ext_s_nom_upper:
  description: "`Transformer-ext-s_nom-upper` — the chosen build is at most its cap; a cap of infinity is no row"
  dims: [transformer]
  where: Transformer_s_nom_extendable AND Transformer_s_nom_max
  expression: Transformer_s_nom_ext <= Transformer_s_nom_max
```

```math
\Sigma_{m} \le \overline{\sigma}^{\mathrm{nom}}_{m} \qquad \forall\, m \in \mathcal{M} \,:\, \mathrm{ext}^{\sigma}_{m} \wedge \overline{\sigma}^{\mathrm{nom}}_{m} \text{ is defined}
```

### `Transformer-s_nom_set`

`Transformer_s_nom_set`

```yaml
Transformer_s_nom_set:
  description: "`Transformer-s_nom_set` — the chosen build pinned, wherever a value is given"
  dims: [transformer]
  where: Transformer_s_nom_extendable AND Transformer_s_nom_set
  expression: Transformer_s_nom_ext == Transformer_s_nom_set
```

```math
\Sigma_{m} = \sigma^{\mathrm{nom,set}}_{m} \qquad \forall\, m \in \mathcal{M} \,:\, \mathrm{ext}^{\sigma}_{m} \wedge \sigma^{\mathrm{nom,set}}_{m} \text{ is defined}
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
\sigma_{\xi,t,m} = \sigma^{\mathrm{set}}_{t,m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M} \,:\, \sigma^{\mathrm{set}}_{t,m} \text{ is defined} \wedge \mathrm{on}^{\sigma}_{t,m}
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
\ell^{\sigma}_{\xi,t,m} \le \overline{\ell}^{\sigma}_{t,m} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M} \,:\, \mathrm{lossy} \wedge \mathrm{on}^{\sigma}_{t,m}
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
\ell^{\sigma}_{\xi,t,m} + \mathrm{a}^{\sigma}_{t,m,b} \cdot \sigma_{\xi,t,m} \ge \mathrm{b}^{\sigma}_{t,m,b} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M},\ b \in \mathcal{B} \,:\, \mathrm{lossy} \wedge \mathrm{on}^{\sigma}_{t,m}
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
\ell^{\sigma}_{\xi,t,m} - \mathrm{a}^{\sigma}_{t,m,b} \cdot \sigma_{\xi,t,m} \ge \mathrm{b}^{\sigma}_{t,m,b} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ m \in \mathcal{M},\ b \in \mathcal{B} \,:\, \mathrm{lossy} \wedge \mathrm{on}^{\sigma}_{t,m}
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
  expression: >-
    sum(Line_s * Line_cycle_weight, over=line)
    + sum(Transformer_s * Transformer_cycle_weight, over=transformer)
    + sum(Transformer_phase_shift_weight, over=transformer)
    + sum(Transformer_phase_shift * Transformer_phase_shift_cycle_weight, over=transformer) == 0
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
    horizon running brought an unknown output, so it carries no row at the
    first snapshot, nor at the start of a later investment period — nor does any unit a big M releases instead
  dims: [scenario, snapshot, generator]
  where: >-
    (Generator_ramp_limit_up OR Generator_ramp_limit_start_up)
    AND NOT (Generator_committable AND Generator_p_nom_extendable AND NOT (Generator_p_nom_mod > 0))
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Generator_committable AND Generator_status_initial == 0)))
    AND Generator_active
  expression: Generator_p - Generator_previous_p <= Generator_ramp_up_allowance
```

```math
p_{\xi,t,g} - \overleftarrow{p}_{\xi,t,g} \le \Delta^{+}_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \left( \mathrm{ru}_{g} \text{ is defined} \vee \mathrm{ru}^{\mathrm{up}}_{g} \text{ is defined} \right) \wedge \neg \left( \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \mathrm{com}_{g} \wedge \mathrm{u}^{0}_{g} = 0 \right) \wedge \mathrm{on}_{t,g}
```

### `Generator-p-ramp_limit_down`

`Generator_p_ramp_limit_down`

```yaml
Generator_p_ramp_limit_down:
  description: >-
    `Generator-p-ramp_limit_down` — a generator lowers output no faster than
    its ramp limit of the build, and a committed one no further than its
    shut-down ramp in the snapshot it turns off. A unit that came into the
    horizon running brought an unknown output, so it carries no row at the
    first snapshot, nor at the start of a later investment period — nor does any unit a big M releases instead
  dims: [scenario, snapshot, generator]
  where: >-
    (Generator_ramp_limit_down OR Generator_ramp_limit_shut_down)
    AND NOT (Generator_committable AND Generator_p_nom_extendable AND NOT (Generator_p_nom_mod > 0))
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Generator_committable AND Generator_status_initial == 0)))
    AND Generator_active
  expression: Generator_previous_p - Generator_p <= Generator_ramp_down_allowance
```

```math
\overleftarrow{p}_{\xi,t,g} - p_{\xi,t,g} \le \Delta^{-}_{\xi,t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \left( \mathrm{rd}_{g} \text{ is defined} \vee \mathrm{rd}^{\mathrm{dn}}_{g} \text{ is defined} \right) \wedge \neg \left( \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right) \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \mathrm{com}_{g} \wedge \mathrm{u}^{0}_{g} = 0 \right) \wedge \mathrm{on}_{t,g}
```

### `Link-p-ramp_limit_up`

`Link_p_ramp_limit_up`

```yaml
Link_p_ramp_limit_up:
  description: >-
    `Link-p-ramp_limit_up` — a link raises flow no faster than
    its ramp limit of the build, and a committed one no further than its
    start-up ramp in the snapshot it turns on. A link that came into the
    horizon running brought an unknown flow, so it carries no row at the
    first snapshot, nor at the start of a later investment period — nor does any link a big M releases instead
  dims: [scenario, snapshot, link]
  where: >-
    (Link_ramp_limit_up OR Link_ramp_limit_start_up)
    AND NOT (Link_committable AND Link_p_nom_extendable AND NOT (Link_p_nom_mod > 0))
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Link_committable AND Link_status_initial == 0)))
    AND Link_active
  expression: Link_p - Link_previous_p <= Link_ramp_up_allowance
```

```math
f_{\xi,t,l} - \overleftarrow{f}_{\xi,t,l} \le \Delta^{f,+}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \left( \mathrm{ru}^{f}_{l} \text{ is defined} \vee \mathrm{ru}^{f,\mathrm{up}}_{l} \text{ is defined} \right) \wedge \neg \left( \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \mathrm{com}^{f}_{l} \wedge \mathrm{u}^{f,0}_{l} = 0 \right) \wedge \mathrm{on}^{f}_{t,l}
```

### `Link-p-ramp_limit_down`

`Link_p_ramp_limit_down`

```yaml
Link_p_ramp_limit_down:
  description: >-
    `Link-p-ramp_limit_down` — a link lowers flow no faster than
    its ramp limit of the build, and a committed one no further than its
    shut-down ramp in the snapshot it turns off. A link that came into the
    horizon running brought an unknown flow, so it carries no row at the
    first snapshot, nor at the start of a later investment period — nor does any link a big M releases instead
  dims: [scenario, snapshot, link]
  where: >-
    (Link_ramp_limit_down OR Link_ramp_limit_shut_down)
    AND NOT (Link_committable AND Link_p_nom_extendable AND NOT (Link_p_nom_mod > 0))
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Link_committable AND Link_status_initial == 0)))
    AND Link_active
  expression: Link_previous_p - Link_p <= Link_ramp_down_allowance
```

```math
\overleftarrow{f}_{\xi,t,l} - f_{\xi,t,l} \le \Delta^{f,-}_{\xi,t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \left( \mathrm{rd}^{f}_{l} \text{ is defined} \vee \mathrm{rd}^{f,\mathrm{dn}}_{l} \text{ is defined} \right) \wedge \neg \left( \mathrm{com}^{f}_{l} \wedge \mathrm{ext}^{f}_{l} \wedge \neg \left( \mathrm{f}^{\mathrm{mod}}_{l} > 0 \right) \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \mathrm{com}^{f}_{l} \wedge \mathrm{u}^{f,0}_{l} = 0 \right) \wedge \mathrm{on}^{f}_{t,l}
```

### `Process-p-ramp_limit_up`

`Process_p_ramp_limit_up`

```yaml
Process_p_ramp_limit_up:
  description: >-
    `Process-p-ramp_limit_up` — a process raises internal power no faster than
    its ramp limit of the build, and a committed one no further than its
    start-up ramp in the snapshot it turns on. A process that came into the
    horizon running brought an unknown internal power, so it carries no row at the
    first snapshot, nor at the start of a later investment period — nor does any process a big M releases instead
  dims: [scenario, snapshot, process]
  where: >-
    (Process_ramp_limit_up OR Process_ramp_limit_start_up)
    AND NOT (Process_committable AND Process_p_nom_extendable AND NOT (Process_p_nom_mod > 0))
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Process_committable AND Process_status_initial == 0)))
    AND Process_active
  expression: Process_p - Process_previous_p <= Process_ramp_up_allowance
```

```math
z_{\xi,t,j} - \overleftarrow{z}_{\xi,t,j} \le \Delta^{z,+}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \left( \mathrm{ru}^{z}_{j} \text{ is defined} \vee \mathrm{ru}^{z,\mathrm{up}}_{j} \text{ is defined} \right) \wedge \neg \left( \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \mathrm{com}^{z}_{j} \wedge \mathrm{u}^{z,0}_{j} = 0 \right) \wedge \mathrm{on}^{z}_{t,j}
```

### `Process-p-ramp_limit_down`

`Process_p_ramp_limit_down`

```yaml
Process_p_ramp_limit_down:
  description: >-
    `Process-p-ramp_limit_down` — a process lowers internal power no faster than
    its ramp limit of the build, and a committed one no further than its
    shut-down ramp in the snapshot it turns off. A process that came into the
    horizon running brought an unknown internal power, so it carries no row at the
    first snapshot, nor at the start of a later investment period — nor does any process a big M releases instead
  dims: [scenario, snapshot, process]
  where: >-
    (Process_ramp_limit_down OR Process_ramp_limit_shut_down)
    AND NOT (Process_committable AND Process_p_nom_extendable AND NOT (Process_p_nom_mod > 0))
    AND (position(snapshot, by=snapshot_period, within=period) > 0 OR (position(snapshot) == 0 AND (Process_committable AND Process_status_initial == 0)))
    AND Process_active
  expression: Process_previous_p - Process_p <= Process_ramp_down_allowance
```

```math
\overleftarrow{z}_{\xi,t,j} - z_{\xi,t,j} \le \Delta^{z,-}_{\xi,t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \left( \mathrm{rd}^{z}_{j} \text{ is defined} \vee \mathrm{rd}^{z,\mathrm{dn}}_{j} \text{ is defined} \right) \wedge \neg \left( \mathrm{com}^{z}_{j} \wedge \mathrm{ext}^{z}_{j} \wedge \neg \left( \mathrm{z}^{\mathrm{mod}}_{j} > 0 \right) \right) \wedge \left( \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) > 0 \vee \mathrm{pos}(t) = 0 \wedge \mathrm{com}^{z}_{j} \wedge \mathrm{u}^{z,0}_{j} = 0 \right) \wedge \mathrm{on}^{z}_{t,j}
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
h^{+}_{\xi,t,s} \le \overline{\mathrm{h}}_{t,s} \cdot H_{s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
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
h^{-}_{\xi,t,s} \le -\underline{\mathrm{h}}_{t,s} \cdot H_{s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
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
\mathit{soc}_{\xi,t,s} \le \mathrm{T}^{h}_{s} \cdot H_{s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s} \wedge \mathrm{on}^{h}_{t,s}
```

### `StorageUnit-ext-p_nom-lower`

`StorageUnit_ext_p_nom_lower`

```yaml
StorageUnit_ext_p_nom_lower:
  description: "`StorageUnit-ext-p_nom-lower` — the chosen build is at least its floor"
  dims: [storage_unit]
  where: StorageUnit_p_nom_extendable
  expression: StorageUnit_p_nom_ext >= StorageUnit_p_nom_min
```

```math
H_{s} \ge \underline{\mathrm{h}}^{\mathrm{nom}}_{s} \qquad \forall\, s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s}
```

### `StorageUnit-ext-p_nom-upper`

`StorageUnit_ext_p_nom_upper`

```yaml
StorageUnit_ext_p_nom_upper:
  description: "`StorageUnit-ext-p_nom-upper` — the chosen build is at most its cap; a cap of infinity is no row"
  dims: [storage_unit]
  where: StorageUnit_p_nom_extendable AND StorageUnit_p_nom_max
  expression: StorageUnit_p_nom_ext <= StorageUnit_p_nom_max
```

```math
H_{s} \le \overline{\mathrm{h}}^{\mathrm{nom}}_{s} \qquad \forall\, s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s} \wedge \overline{\mathrm{h}}^{\mathrm{nom}}_{s} \text{ is defined}
```

### `StorageUnit-p_nom_set`

`StorageUnit_p_nom_set`

```yaml
StorageUnit_p_nom_set:
  description: "`StorageUnit-p_nom_set` — the chosen build pinned, wherever a value is given"
  dims: [storage_unit]
  where: StorageUnit_p_nom_extendable AND StorageUnit_p_nom_set
  expression: StorageUnit_p_nom_ext == StorageUnit_p_nom_set
```

```math
H_{s} = \mathrm{h}^{\mathrm{nom,set}}_{s} \qquad \forall\, s \in \mathcal{S} \,:\, \mathrm{ext}^{h}_{s} \wedge \mathrm{h}^{\mathrm{nom,set}}_{s} \text{ is defined}
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
\mathit{soc}_{\xi,t,s} = \overleftarrow{\mathit{soc}}_{\xi,t,s} + \eta^{-}_{s} \cdot h^{-}_{\xi,t,s} \cdot \mathrm{w}^{\mathrm{sto}}_{t} - \frac{h^{+}_{\xi,t,s} \cdot \mathrm{w}^{\mathrm{sto}}_{t}}{\eta^{+}_{s}} + \left( \mathrm{inflow}_{t,s} - \mathit{spill}_{\xi,t,s} \right) \cdot \mathrm{w}^{\mathrm{sto}}_{t} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{on}^{h}_{t,s}
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
e_{\xi,t,v} \ge \underline{\mathrm{e}}_{t,v} \cdot \mathrm{e}^{\mathrm{nom}}_{v} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ v \in \mathcal{V} \,:\, \neg \mathrm{ext}^{e}_{v} \wedge \mathrm{on}^{e}_{t,v}
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
e_{\xi,t,v} \le \overline{\mathrm{e}}_{t,v} \cdot \mathrm{e}^{\mathrm{nom}}_{v} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ v \in \mathcal{V} \,:\, \neg \mathrm{ext}^{e}_{v} \wedge \mathrm{on}^{e}_{t,v}
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
e_{\xi,t,v} \ge \underline{\mathrm{e}}_{t,v} \cdot E_{v} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ v \in \mathcal{V} \,:\, \mathrm{ext}^{e}_{v} \wedge \mathrm{on}^{e}_{t,v}
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
e_{\xi,t,v} \le \overline{\mathrm{e}}_{t,v} \cdot E_{v} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ v \in \mathcal{V} \,:\, \mathrm{ext}^{e}_{v} \wedge \mathrm{on}^{e}_{t,v}
```

### `Store-ext-e_nom-lower`

`Store_ext_e_nom_lower`

```yaml
Store_ext_e_nom_lower:
  description: "`Store-ext-e_nom-lower` — the chosen build is at least its floor"
  dims: [store]
  where: Store_e_nom_extendable
  expression: Store_e_nom_ext >= Store_e_nom_min
```

```math
E_{v} \ge \underline{\mathrm{e}}^{\mathrm{nom}}_{v} \qquad \forall\, v \in \mathcal{V} \,:\, \mathrm{ext}^{e}_{v}
```

### `Store-ext-e_nom-upper`

`Store_ext_e_nom_upper`

```yaml
Store_ext_e_nom_upper:
  description: "`Store-ext-e_nom-upper` — the chosen build is at most its cap; a cap of infinity is no row"
  dims: [store]
  where: Store_e_nom_extendable AND Store_e_nom_max
  expression: Store_e_nom_ext <= Store_e_nom_max
```

```math
E_{v} \le \overline{\mathrm{e}}^{\mathrm{nom}}_{v} \qquad \forall\, v \in \mathcal{V} \,:\, \mathrm{ext}^{e}_{v} \wedge \overline{\mathrm{e}}^{\mathrm{nom}}_{v} \text{ is defined}
```

### `Store-e_nom_set`

`Store_e_nom_set`

```yaml
Store_e_nom_set:
  description: "`Store-e_nom_set` — the chosen build pinned, wherever a value is given"
  dims: [store]
  where: Store_e_nom_extendable AND Store_e_nom_set
  expression: Store_e_nom_ext == Store_e_nom_set
```

```math
E_{v} = \mathrm{e}^{\mathrm{nom,set}}_{v} \qquad \forall\, v \in \mathcal{V} \,:\, \mathrm{ext}^{e}_{v} \wedge \mathrm{e}^{\mathrm{nom,set}}_{v} \text{ is defined}
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
p_{\xi,t,g} = \mathrm{p}^{\mathrm{set}}_{t,g} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{p}^{\mathrm{set}}_{t,g} \text{ is defined} \wedge \mathrm{on}_{t,g}
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
f_{\xi,t,l} = \mathrm{f}^{\mathrm{set}}_{t,l} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L} \,:\, \mathrm{f}^{\mathrm{set}}_{t,l} \text{ is defined} \wedge \mathrm{on}^{f}_{t,l}
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
z_{\xi,t,j} = \mathrm{z}^{\mathrm{set}}_{t,j} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J} \,:\, \mathrm{z}^{\mathrm{set}}_{t,j} \text{ is defined} \wedge \mathrm{on}^{z}_{t,j}
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
h^{+}_{\xi,t,s} - h^{-}_{\xi,t,s} = \mathrm{h}^{\mathrm{set}}_{t,s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{h}^{\mathrm{set}}_{t,s} \text{ is defined} \wedge \mathrm{on}^{h}_{t,s}
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
\mathit{soc}_{\xi,t,s} = \mathrm{soc}^{\mathrm{set}}_{t,s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{soc}^{\mathrm{set}}_{t,s} \text{ is defined} \wedge \mathrm{on}^{h}_{t,s}
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
e_{\xi,t,v} = \mathrm{e}^{\mathrm{set}}_{t,v} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ v \in \mathcal{V} \,:\, \mathrm{e}^{\mathrm{set}}_{t,v} \text{ is defined} \wedge \mathrm{on}^{e}_{t,v}
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
\mathit{primary\_energy}_{\xi,i} \le \mathrm{K}_{i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{primary\_energy}\text{'} \wedge \mathrm{sense}_{i} = \text{'}\mathrm{<=}\text{'}
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
\mathit{primary\_energy}_{\xi,i} \ge \mathrm{K}_{i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{primary\_energy}\text{'} \wedge \mathrm{sense}_{i} = \text{'}\mathrm{>=}\text{'}
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
\mathit{primary\_energy}_{\xi,i} = \mathrm{K}_{i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{primary\_energy}\text{'} \wedge \mathrm{sense}_{i} = \text{'}\mathrm{==}\text{'}
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
\mathit{operational\_limit}_{\xi,i} \le \mathrm{K}_{i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{operational\_limit}\text{'} \wedge \mathrm{sense}_{i} = \text{'}\mathrm{<=}\text{'}
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
\mathit{operational\_limit}_{\xi,i} \ge \mathrm{K}_{i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{operational\_limit}\text{'} \wedge \mathrm{sense}_{i} = \text{'}\mathrm{>=}\text{'}
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
\mathit{operational\_limit}_{\xi,i} = \mathrm{K}_{i} \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{operational\_limit}\text{'} \wedge \mathrm{sense}_{i} = \text{'}\mathrm{==}\text{'}
```

### `transmission_volume_expansion_limit`

`GlobalConstraint_transmission_volume_expansion_limit_ub`

```yaml
GlobalConstraint_transmission_volume_expansion_limit_ub:
  description: "`transmission_volume_expansion_limit` — its total, at most its constant"
  dims: [global_constraint]
  where: GlobalConstraint_type == 'transmission_volume_expansion_limit' AND GlobalConstraint_sense == '<='
  expression: transmission_volume_expansion <= GlobalConstraint_constant
```

```math
\mathit{transmission\_volume\_expansion}_{i} \le \mathrm{K}_{i} \qquad \forall\, i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{transmission\_volume\_expansion\_limit}\text{'} \wedge \mathrm{sense}_{i} = \text{'}\mathrm{<=}\text{'}
```

### `transmission_volume_expansion_limit`

`GlobalConstraint_transmission_volume_expansion_limit_lb`

```yaml
GlobalConstraint_transmission_volume_expansion_limit_lb:
  description: "`transmission_volume_expansion_limit` — its total, at least its constant"
  dims: [global_constraint]
  where: GlobalConstraint_type == 'transmission_volume_expansion_limit' AND GlobalConstraint_sense == '>='
  expression: transmission_volume_expansion >= GlobalConstraint_constant
```

```math
\mathit{transmission\_volume\_expansion}_{i} \ge \mathrm{K}_{i} \qquad \forall\, i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{transmission\_volume\_expansion\_limit}\text{'} \wedge \mathrm{sense}_{i} = \text{'}\mathrm{>=}\text{'}
```

### `transmission_volume_expansion_limit`

`GlobalConstraint_transmission_volume_expansion_limit_eq`

```yaml
GlobalConstraint_transmission_volume_expansion_limit_eq:
  description: "`transmission_volume_expansion_limit` — its total, at its constant"
  dims: [global_constraint]
  where: GlobalConstraint_type == 'transmission_volume_expansion_limit' AND GlobalConstraint_sense == '=='
  expression: transmission_volume_expansion == GlobalConstraint_constant
```

```math
\mathit{transmission\_volume\_expansion}_{i} = \mathrm{K}_{i} \qquad \forall\, i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{transmission\_volume\_expansion\_limit}\text{'} \wedge \mathrm{sense}_{i} = \text{'}\mathrm{==}\text{'}
```

### `transmission_expansion_cost_limit`

`GlobalConstraint_transmission_expansion_cost_limit_ub`

```yaml
GlobalConstraint_transmission_expansion_cost_limit_ub:
  description: "`transmission_expansion_cost_limit` — its total, at most its constant"
  dims: [global_constraint]
  where: GlobalConstraint_type == 'transmission_expansion_cost_limit' AND GlobalConstraint_sense == '<='
  expression: transmission_expansion_cost <= GlobalConstraint_constant
```

```math
\mathit{transmission\_expansion\_cost}_{i} \le \mathrm{K}_{i} \qquad \forall\, i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{transmission\_expansion\_cost\_limit}\text{'} \wedge \mathrm{sense}_{i} = \text{'}\mathrm{<=}\text{'}
```

### `transmission_expansion_cost_limit`

`GlobalConstraint_transmission_expansion_cost_limit_lb`

```yaml
GlobalConstraint_transmission_expansion_cost_limit_lb:
  description: "`transmission_expansion_cost_limit` — its total, at least its constant"
  dims: [global_constraint]
  where: GlobalConstraint_type == 'transmission_expansion_cost_limit' AND GlobalConstraint_sense == '>='
  expression: transmission_expansion_cost >= GlobalConstraint_constant
```

```math
\mathit{transmission\_expansion\_cost}_{i} \ge \mathrm{K}_{i} \qquad \forall\, i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{transmission\_expansion\_cost\_limit}\text{'} \wedge \mathrm{sense}_{i} = \text{'}\mathrm{>=}\text{'}
```

### `transmission_expansion_cost_limit`

`GlobalConstraint_transmission_expansion_cost_limit_eq`

```yaml
GlobalConstraint_transmission_expansion_cost_limit_eq:
  description: "`transmission_expansion_cost_limit` — its total, at its constant"
  dims: [global_constraint]
  where: GlobalConstraint_type == 'transmission_expansion_cost_limit' AND GlobalConstraint_sense == '=='
  expression: transmission_expansion_cost == GlobalConstraint_constant
```

```math
\mathit{transmission\_expansion\_cost}_{i} = \mathrm{K}_{i} \qquad \forall\, i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{transmission\_expansion\_cost\_limit}\text{'} \wedge \mathrm{sense}_{i} = \text{'}\mathrm{==}\text{'}
```

### `tech_capacity_expansion_limit`

`GlobalConstraint_tech_capacity_expansion_limit_ub`

```yaml
GlobalConstraint_tech_capacity_expansion_limit_ub:
  description: "`tech_capacity_expansion_limit` — its total, at most its constant"
  dims: [global_constraint]
  where: GlobalConstraint_type == 'tech_capacity_expansion_limit' AND GlobalConstraint_sense == '<='
  expression: tech_capacity_expansion <= GlobalConstraint_constant
```

```math
\mathit{tech\_capacity\_expansion}_{i} \le \mathrm{K}_{i} \qquad \forall\, i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{tech\_capacity\_expansion\_limit}\text{'} \wedge \mathrm{sense}_{i} = \text{'}\mathrm{<=}\text{'}
```

### `tech_capacity_expansion_limit`

`GlobalConstraint_tech_capacity_expansion_limit_lb`

```yaml
GlobalConstraint_tech_capacity_expansion_limit_lb:
  description: "`tech_capacity_expansion_limit` — its total, at least its constant"
  dims: [global_constraint]
  where: GlobalConstraint_type == 'tech_capacity_expansion_limit' AND GlobalConstraint_sense == '>='
  expression: tech_capacity_expansion >= GlobalConstraint_constant
```

```math
\mathit{tech\_capacity\_expansion}_{i} \ge \mathrm{K}_{i} \qquad \forall\, i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{tech\_capacity\_expansion\_limit}\text{'} \wedge \mathrm{sense}_{i} = \text{'}\mathrm{>=}\text{'}
```

### `tech_capacity_expansion_limit`

`GlobalConstraint_tech_capacity_expansion_limit_eq`

```yaml
GlobalConstraint_tech_capacity_expansion_limit_eq:
  description: "`tech_capacity_expansion_limit` — its total, at its constant"
  dims: [global_constraint]
  where: GlobalConstraint_type == 'tech_capacity_expansion_limit' AND GlobalConstraint_sense == '=='
  expression: tech_capacity_expansion == GlobalConstraint_constant
```

```math
\mathit{tech\_capacity\_expansion}_{i} = \mathrm{K}_{i} \qquad \forall\, i \in \mathcal{I} \,:\, \mathrm{type}_{i} = \text{'}\mathrm{tech\_capacity\_expansion\_limit}\text{'} \wedge \mathrm{sense}_{i} = \text{'}\mathrm{==}\text{'}
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
    either end.
    A bus nothing is attached to has no row; PyPSA refuses one that
    carries load, and this file does not yet.
  dims: [scenario, snapshot, bus]
  expression: >-
    sum(Generator_p, by=Generator_bus, over=generator, into=bus)
    + sum(StorageUnit_p_dispatch - StorageUnit_p_store, by=StorageUnit_bus, over=storage_unit, into=bus)
    + sum(Store_p, by=Store_bus, over=store, into=bus)
    - sum(Link_p, by=Link_bus0, over=link, into=bus)
    + sum(Link_output_arrival, by=Link_output_bus, over=link_output, into=bus)
    + sum(Process_output_arrival, by=Process_output_bus, over=process_output, into=bus)
    - sum(Line_s, by=Line_bus0, over=line, into=bus)
    + sum(Line_s, by=Line_bus1, over=line, into=bus)
    - 0.5 * sum(Line_loss, by=Line_bus0, over=line, into=bus)
    - 0.5 * sum(Line_loss, by=Line_bus1, over=line, into=bus)
    - sum(Transformer_s, by=Transformer_bus0, over=transformer, into=bus)
    + sum(Transformer_s, by=Transformer_bus1, over=transformer, into=bus)
    - 0.5 * sum(Transformer_loss, by=Transformer_bus0, over=transformer, into=bus)
    - 0.5 * sum(Transformer_loss, by=Transformer_bus1, over=transformer, into=bus)
    == sum(Load_p_set, by=Load_bus, over=load, into=bus)
```

```math
\sum_{g \in \mathcal{G} \,:\, \mathrm{Generator\_bus}(g) = n} p_{\xi,t,g} + \sum_{s \in \mathcal{S} \,:\, \mathrm{StorageUnit\_bus}(s) = n} \left( h^{+}_{\xi,t,s} - h^{-}_{\xi,t,s} \right) + \sum_{v \in \mathcal{V} \,:\, \mathrm{Store\_bus}(v) = n} q_{\xi,t,v} - \left( \sum_{l \in \mathcal{L} \,:\, \mathrm{Link\_bus0}(l) = n} f_{\xi,t,l} \right) + \sum_{o \in \mathcal{O} \,:\, \mathrm{Link\_output\_bus}(o) = n} \overrightarrow{f}_{\xi,t,o} + \sum_{r \in \mathcal{R} \,:\, \mathrm{Process\_output\_bus}(r) = n} \overrightarrow{z}_{\xi,t,r} - \left( \sum_{k \in \mathcal{K} \,:\, \mathrm{Line\_bus0}(k) = n} s_{\xi,t,k} \right) + \sum_{k \in \mathcal{K} \,:\, \mathrm{Line\_bus1}(k) = n} s_{\xi,t,k} - 0.5 \cdot \left( \sum_{k \in \mathcal{K} \,:\, \mathrm{Line\_bus0}(k) = n} \ell_{\xi,t,k} \right) - 0.5 \cdot \left( \sum_{k \in \mathcal{K} \,:\, \mathrm{Line\_bus1}(k) = n} \ell_{\xi,t,k} \right) - \left( \sum_{m \in \mathcal{M} \,:\, \mathrm{Transformer\_bus0}(m) = n} \sigma_{\xi,t,m} \right) + \sum_{m \in \mathcal{M} \,:\, \mathrm{Transformer\_bus1}(m) = n} \sigma_{\xi,t,m} - 0.5 \cdot \left( \sum_{m \in \mathcal{M} \,:\, \mathrm{Transformer\_bus0}(m) = n} \ell^{\sigma}_{\xi,t,m} \right) - 0.5 \cdot \left( \sum_{m \in \mathcal{M} \,:\, \mathrm{Transformer\_bus1}(m) = n} \ell^{\sigma}_{\xi,t,m} \right) = \sum_{d \in \mathcal{D} \,:\, \mathrm{Load\_bus}(d) = n} \mathrm{load}_{\xi,t,d} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ n \in \mathcal{N}
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
    - shift(Carrier_additions, along=period, offset=1, edge=0) * Carrier_max_relative_growth
    <= Carrier_max_growth
```

```math
\mathit{Carrier\_additions}_{y,i} - \mathit{Carrier\_additions}_{y \boxminus_{0} 1,i} \cdot \mathrm{r}_{i} \le \overline{\Delta}_{i} \qquad \forall\, i \in \mathcal{I},\ y \in \mathcal{Y} \,:\, \overline{\Delta}_{i} \text{ is defined}
```

### `CVaR-excess-{s}`

`CVaR_excess`

```yaml
CVaR_excess:
  description: "`CVaR-excess-{s}` — a scenario's operating cost beyond the tail's start is its excess; PyPSA names one row per scenario"
  dims: [scenario]
  expression: CVaR_a - scenario_opex + CVaR_theta >= 0
```

```math
a_{\xi} - \mathit{scenario\_opex}_{\xi} + \theta \ge 0 \qquad \forall\, \xi \in \Xi
```

### `CVaR-def`

`CVaR_def`

```yaml
CVaR_def:
  description: "`CVaR-def` — the tail's average is at least where it starts plus the expected excess over the tail's probability"
  dims: []
  expression: CVaR_theta + CVaR_inv_tail * sum(scenario_weight * CVaR_a, over=scenario) <= CVaR
```

```math
\theta + \mathrm{v} \cdot \left( \sum_{\xi \in \Xi} \pi_{\xi} \cdot a_{\xi} \right) \le CVaR
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
\overleftarrow{u}_{\xi,t,g} = \begin{cases} \mathrm{u}^{0}_{g} & \text{if } \mathrm{pos}(t) = 0 \\ u_{\xi,t - 1,g} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G}
```

### `Generator_previous_p`

```yaml
Generator_previous_p:
  description: >-
    the output a generator carries into a snapshot — nothing at the start of
    the horizon, which is why a unit that came in running carries no ramp row
    there
  dims: [scenario, snapshot, generator]
  cases:
    opening: { when: "position(snapshot) == 0", expression: 0 }
  otherwise: shift(Generator_p, along=snapshot, offset=1)
```

```math
\overleftarrow{p}_{\xi,t,g} = \begin{cases} 0 & \text{if } \mathrm{pos}(t) = 0 \\ p_{\xi,t - 1,g} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G}
```

### `Generator_p_nom_effective`

```yaml
Generator_p_nom_effective:
  description: the build a generator's limits are taken against — the chosen one where it is extendable, the given one otherwise
  dims: [generator]
  cases:
    extendable: { when: Generator_p_nom_extendable, expression: Generator_p_nom_ext }
  otherwise: Generator_p_nom
```

```math
\widetilde{\mathrm{p}}^{\mathrm{nom}}_{g} = \begin{cases} P_{g} & \text{if } \mathrm{ext}_{g} \\ \mathrm{p}^{\mathrm{nom}}_{g} & \text{otherwise} \end{cases} \qquad \forall\, g \in \mathcal{G}
```

### `Generator_ramp_up_rate`

```yaml
Generator_ramp_up_rate:
  description: >-
    the ramp limit a unit's up row reads — PyPSA's `ramp_limit_up`, or the
    full build where it has none, since a start-up ramp alone builds the row
  dims: [generator]
  cases:
    given: { when: Generator_ramp_limit_up, expression: Generator_ramp_limit_up }
  otherwise: 1
```

```math
\widetilde{\mathrm{ru}}_{g} = \begin{cases} \mathrm{ru}_{g} & \text{if } \mathrm{ru}_{g} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, g \in \mathcal{G}
```

### `Generator_ramp_down_rate`

```yaml
Generator_ramp_down_rate:
  description: >-
    the ramp limit a unit's down row reads — PyPSA's `ramp_limit_down`, or
    the full build where it has none, since a shut-down ramp alone builds the row
  dims: [generator]
  cases:
    given: { when: Generator_ramp_limit_down, expression: Generator_ramp_limit_down }
  otherwise: 1
```

```math
\widetilde{\mathrm{rd}}_{g} = \begin{cases} \mathrm{rd}_{g} & \text{if } \mathrm{rd}_{g} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, g \in \mathcal{G}
```

### `Generator_start_up_rate`

```yaml
Generator_start_up_rate:
  description: >-
    the start-up ramp a unit's up row reads — PyPSA's `ramp_limit_start_up`,
    or the full build where it has none
  dims: [generator]
  cases:
    given: { when: Generator_ramp_limit_start_up, expression: Generator_ramp_limit_start_up }
  otherwise: 1
```

```math
\widetilde{\mathrm{ru}}^{\mathrm{up}}_{g} = \begin{cases} \mathrm{ru}^{\mathrm{up}}_{g} & \text{if } \mathrm{ru}^{\mathrm{up}}_{g} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, g \in \mathcal{G}
```

### `Generator_shut_down_rate`

```yaml
Generator_shut_down_rate:
  description: >-
    the shut-down ramp a unit's down row reads — PyPSA's
    `ramp_limit_shut_down`, or the full build where it has none
  dims: [generator]
  cases:
    given: { when: Generator_ramp_limit_shut_down, expression: Generator_ramp_limit_shut_down }
  otherwise: 1
```

```math
\widetilde{\mathrm{rd}}^{\mathrm{dn}}_{g} = \begin{cases} \mathrm{rd}^{\mathrm{dn}}_{g} & \text{if } \mathrm{rd}^{\mathrm{dn}}_{g} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, g \in \mathcal{G}
```

### `Generator_p_nom_committed`

```yaml
Generator_p_nom_committed:
  description: >-
    the build a committed unit's ramp rows are taken against — one module
    where the build is extendable and modular, the given build otherwise
  dims: [generator]
  cases:
    modular_build: { when: Generator_p_nom_extendable AND Generator_p_nom_mod > 0, expression: Generator_p_nom_mod }
  otherwise: Generator_p_nom
```

```math
\widehat{\mathrm{p}}^{\mathrm{nom}}_{g} = \begin{cases} \mathrm{p}^{\mathrm{mod}}_{g} & \text{if } \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \\ \mathrm{p}^{\mathrm{nom}}_{g} & \text{otherwise} \end{cases} \qquad \forall\, g \in \mathcal{G}
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
\Delta^{+}_{\xi,t,g} = \begin{cases} \widetilde{\mathrm{ru}}_{g} \cdot \widehat{\mathrm{p}}^{\mathrm{nom}}_{g} \cdot \overleftarrow{u}_{\xi,t,g} + \widetilde{\mathrm{ru}}^{\mathrm{up}}_{g} \cdot \widehat{\mathrm{p}}^{\mathrm{nom}}_{g} \cdot \left( u_{\xi,t,g} - \overleftarrow{u}_{\xi,t,g} \right) & \text{if } \mathrm{com}_{g} \\ \widetilde{\mathrm{ru}}_{g} \cdot \widetilde{\mathrm{p}}^{\mathrm{nom}}_{g} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G}
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
\Delta^{-}_{\xi,t,g} = \begin{cases} \widetilde{\mathrm{rd}}_{g} \cdot \widehat{\mathrm{p}}^{\mathrm{nom}}_{g} \cdot u_{\xi,t,g} + \widetilde{\mathrm{rd}}^{\mathrm{dn}}_{g} \cdot \widehat{\mathrm{p}}^{\mathrm{nom}}_{g} \cdot \left( \overleftarrow{u}_{\xi,t,g} - u_{\xi,t,g} \right) & \text{if } \mathrm{com}_{g} \\ \widetilde{\mathrm{rd}}_{g} \cdot \widetilde{\mathrm{p}}^{\mathrm{nom}}_{g} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ g \in \mathcal{G}
```

### `Link_p_nom_effective`

```yaml
Link_p_nom_effective:
  description: the build a link's limits are taken against — the chosen one where it is extendable, the given one otherwise
  dims: [link]
  cases:
    extendable: { when: Link_p_nom_extendable, expression: Link_p_nom_ext }
  otherwise: Link_p_nom
```

```math
\widetilde{\mathrm{f}}^{\mathrm{nom}}_{l} = \begin{cases} F_{l} & \text{if } \mathrm{ext}^{f}_{l} \\ \mathrm{f}^{\mathrm{nom}}_{l} & \text{otherwise} \end{cases} \qquad \forall\, l \in \mathcal{L}
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
\overleftarrow{u}^{f}_{\xi,t,l} = \begin{cases} \mathrm{u}^{f,0}_{l} & \text{if } \mathrm{pos}(t) = 0 \\ u^{f}_{\xi,t - 1,l} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L}
```

### `Link_previous_p`

```yaml
Link_previous_p:
  description: >-
    the flow a link carries into a snapshot — nothing at the start of
    the horizon, which is why a link that came in running carries no ramp row
    there
  dims: [scenario, snapshot, link]
  cases:
    opening: { when: "position(snapshot) == 0", expression: 0 }
  otherwise: shift(Link_p, along=snapshot, offset=1)
```

```math
\overleftarrow{f}_{\xi,t,l} = \begin{cases} 0 & \text{if } \mathrm{pos}(t) = 0 \\ f_{\xi,t - 1,l} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L}
```

### `Link_ramp_up_rate`

```yaml
Link_ramp_up_rate:
  description: >-
    the ramp limit a link's up row reads — PyPSA's `ramp_limit_up`, or the
    full build where it has none, since a start-up ramp alone builds the row
  dims: [link]
  cases:
    given: { when: Link_ramp_limit_up, expression: Link_ramp_limit_up }
  otherwise: 1
```

```math
\widetilde{\mathrm{ru}}^{f}_{l} = \begin{cases} \mathrm{ru}^{f}_{l} & \text{if } \mathrm{ru}^{f}_{l} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, l \in \mathcal{L}
```

### `Link_ramp_down_rate`

```yaml
Link_ramp_down_rate:
  description: >-
    the ramp limit a link's down row reads — PyPSA's `ramp_limit_down`, or
    the full build where it has none, since a shut-down ramp alone builds the row
  dims: [link]
  cases:
    given: { when: Link_ramp_limit_down, expression: Link_ramp_limit_down }
  otherwise: 1
```

```math
\widetilde{\mathrm{rd}}^{f}_{l} = \begin{cases} \mathrm{rd}^{f}_{l} & \text{if } \mathrm{rd}^{f}_{l} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, l \in \mathcal{L}
```

### `Link_start_up_rate`

```yaml
Link_start_up_rate:
  description: >-
    the start-up ramp a link's up row reads — PyPSA's `ramp_limit_start_up`,
    or the full build where it has none
  dims: [link]
  cases:
    given: { when: Link_ramp_limit_start_up, expression: Link_ramp_limit_start_up }
  otherwise: 1
```

```math
\widetilde{\mathrm{ru}}^{f,\mathrm{up}}_{l} = \begin{cases} \mathrm{ru}^{f,\mathrm{up}}_{l} & \text{if } \mathrm{ru}^{f,\mathrm{up}}_{l} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, l \in \mathcal{L}
```

### `Link_shut_down_rate`

```yaml
Link_shut_down_rate:
  description: >-
    the shut-down ramp a link's down row reads — PyPSA's
    `ramp_limit_shut_down`, or the full build where it has none
  dims: [link]
  cases:
    given: { when: Link_ramp_limit_shut_down, expression: Link_ramp_limit_shut_down }
  otherwise: 1
```

```math
\widetilde{\mathrm{rd}}^{f,\mathrm{dn}}_{l} = \begin{cases} \mathrm{rd}^{f,\mathrm{dn}}_{l} & \text{if } \mathrm{rd}^{f,\mathrm{dn}}_{l} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, l \in \mathcal{L}
```

### `Link_p_nom_committed`

```yaml
Link_p_nom_committed:
  description: >-
    the build a committed link's ramp rows are taken against — one module
    where the build is extendable and modular, the given build otherwise
  dims: [link]
  cases:
    modular_build: { when: Link_p_nom_extendable AND Link_p_nom_mod > 0, expression: Link_p_nom_mod }
  otherwise: Link_p_nom
```

```math
\widehat{\mathrm{f}}^{\mathrm{nom}}_{l} = \begin{cases} \mathrm{f}^{\mathrm{mod}}_{l} & \text{if } \mathrm{ext}^{f}_{l} \wedge \mathrm{f}^{\mathrm{mod}}_{l} > 0 \\ \mathrm{f}^{\mathrm{nom}}_{l} & \text{otherwise} \end{cases} \qquad \forall\, l \in \mathcal{L}
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
\Delta^{f,+}_{\xi,t,l} = \begin{cases} \widetilde{\mathrm{ru}}^{f}_{l} \cdot \widehat{\mathrm{f}}^{\mathrm{nom}}_{l} \cdot \overleftarrow{u}^{f}_{\xi,t,l} + \widetilde{\mathrm{ru}}^{f,\mathrm{up}}_{l} \cdot \widehat{\mathrm{f}}^{\mathrm{nom}}_{l} \cdot \left( u^{f}_{\xi,t,l} - \overleftarrow{u}^{f}_{\xi,t,l} \right) & \text{if } \mathrm{com}^{f}_{l} \\ \widetilde{\mathrm{ru}}^{f}_{l} \cdot \widetilde{\mathrm{f}}^{\mathrm{nom}}_{l} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L}
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
\Delta^{f,-}_{\xi,t,l} = \begin{cases} \widetilde{\mathrm{rd}}^{f}_{l} \cdot \widehat{\mathrm{f}}^{\mathrm{nom}}_{l} \cdot u^{f}_{\xi,t,l} + \widetilde{\mathrm{rd}}^{f,\mathrm{dn}}_{l} \cdot \widehat{\mathrm{f}}^{\mathrm{nom}}_{l} \cdot \left( \overleftarrow{u}^{f}_{\xi,t,l} - u^{f}_{\xi,t,l} \right) & \text{if } \mathrm{com}^{f}_{l} \\ \widetilde{\mathrm{rd}}^{f}_{l} \cdot \widetilde{\mathrm{f}}^{\mathrm{nom}}_{l} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ l \in \mathcal{L}
```

### `Process_p_nom_effective`

```yaml
Process_p_nom_effective:
  description: the build a process's limits are taken against — the chosen one where it is extendable, the given one otherwise
  dims: [process]
  cases:
    extendable: { when: Process_p_nom_extendable, expression: Process_p_nom_ext }
  otherwise: Process_p_nom
```

```math
\widetilde{\mathrm{z}}^{\mathrm{nom}}_{j} = \begin{cases} Z_{j} & \text{if } \mathrm{ext}^{z}_{j} \\ \mathrm{z}^{\mathrm{nom}}_{j} & \text{otherwise} \end{cases} \qquad \forall\, j \in \mathcal{J}
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
\overleftarrow{u}^{z}_{\xi,t,j} = \begin{cases} \mathrm{u}^{z,0}_{j} & \text{if } \mathrm{pos}(t) = 0 \\ u^{z}_{\xi,t - 1,j} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J}
```

### `Process_previous_p`

```yaml
Process_previous_p:
  description: >-
    the internal power a process carries into a snapshot — nothing at the start of
    the horizon, which is why a process that came in running carries no ramp row
    there
  dims: [scenario, snapshot, process]
  cases:
    opening: { when: "position(snapshot) == 0", expression: 0 }
  otherwise: shift(Process_p, along=snapshot, offset=1)
```

```math
\overleftarrow{z}_{\xi,t,j} = \begin{cases} 0 & \text{if } \mathrm{pos}(t) = 0 \\ z_{\xi,t - 1,j} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J}
```

### `Process_ramp_up_rate`

```yaml
Process_ramp_up_rate:
  description: >-
    the ramp limit a process's up row reads — PyPSA's `ramp_limit_up`, or the
    full build where it has none, since a start-up ramp alone builds the row
  dims: [process]
  cases:
    given: { when: Process_ramp_limit_up, expression: Process_ramp_limit_up }
  otherwise: 1
```

```math
\widetilde{\mathrm{ru}}^{z}_{j} = \begin{cases} \mathrm{ru}^{z}_{j} & \text{if } \mathrm{ru}^{z}_{j} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, j \in \mathcal{J}
```

### `Process_ramp_down_rate`

```yaml
Process_ramp_down_rate:
  description: >-
    the ramp limit a process's down row reads — PyPSA's `ramp_limit_down`, or
    the full build where it has none, since a shut-down ramp alone builds the row
  dims: [process]
  cases:
    given: { when: Process_ramp_limit_down, expression: Process_ramp_limit_down }
  otherwise: 1
```

```math
\widetilde{\mathrm{rd}}^{z}_{j} = \begin{cases} \mathrm{rd}^{z}_{j} & \text{if } \mathrm{rd}^{z}_{j} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, j \in \mathcal{J}
```

### `Process_start_up_rate`

```yaml
Process_start_up_rate:
  description: >-
    the start-up ramp a process's up row reads — PyPSA's `ramp_limit_start_up`,
    or the full build where it has none
  dims: [process]
  cases:
    given: { when: Process_ramp_limit_start_up, expression: Process_ramp_limit_start_up }
  otherwise: 1
```

```math
\widetilde{\mathrm{ru}}^{z,\mathrm{up}}_{j} = \begin{cases} \mathrm{ru}^{z,\mathrm{up}}_{j} & \text{if } \mathrm{ru}^{z,\mathrm{up}}_{j} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, j \in \mathcal{J}
```

### `Process_shut_down_rate`

```yaml
Process_shut_down_rate:
  description: >-
    the shut-down ramp a process's down row reads — PyPSA's
    `ramp_limit_shut_down`, or the full build where it has none
  dims: [process]
  cases:
    given: { when: Process_ramp_limit_shut_down, expression: Process_ramp_limit_shut_down }
  otherwise: 1
```

```math
\widetilde{\mathrm{rd}}^{z,\mathrm{dn}}_{j} = \begin{cases} \mathrm{rd}^{z,\mathrm{dn}}_{j} & \text{if } \mathrm{rd}^{z,\mathrm{dn}}_{j} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, j \in \mathcal{J}
```

### `Process_p_nom_committed`

```yaml
Process_p_nom_committed:
  description: >-
    the build a committed process's ramp rows are taken against — one module
    where the build is extendable and modular, the given build otherwise
  dims: [process]
  cases:
    modular_build: { when: Process_p_nom_extendable AND Process_p_nom_mod > 0, expression: Process_p_nom_mod }
  otherwise: Process_p_nom
```

```math
\widehat{\mathrm{z}}^{\mathrm{nom}}_{j} = \begin{cases} \mathrm{z}^{\mathrm{mod}}_{j} & \text{if } \mathrm{ext}^{z}_{j} \wedge \mathrm{z}^{\mathrm{mod}}_{j} > 0 \\ \mathrm{z}^{\mathrm{nom}}_{j} & \text{otherwise} \end{cases} \qquad \forall\, j \in \mathcal{J}
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
\Delta^{z,+}_{\xi,t,j} = \begin{cases} \widetilde{\mathrm{ru}}^{z}_{j} \cdot \widehat{\mathrm{z}}^{\mathrm{nom}}_{j} \cdot \overleftarrow{u}^{z}_{\xi,t,j} + \widetilde{\mathrm{ru}}^{z,\mathrm{up}}_{j} \cdot \widehat{\mathrm{z}}^{\mathrm{nom}}_{j} \cdot \left( u^{z}_{\xi,t,j} - \overleftarrow{u}^{z}_{\xi,t,j} \right) & \text{if } \mathrm{com}^{z}_{j} \\ \widetilde{\mathrm{ru}}^{z}_{j} \cdot \widetilde{\mathrm{z}}^{\mathrm{nom}}_{j} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J}
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
\Delta^{z,-}_{\xi,t,j} = \begin{cases} \widetilde{\mathrm{rd}}^{z}_{j} \cdot \widehat{\mathrm{z}}^{\mathrm{nom}}_{j} \cdot u^{z}_{\xi,t,j} + \widetilde{\mathrm{rd}}^{z,\mathrm{dn}}_{j} \cdot \widehat{\mathrm{z}}^{\mathrm{nom}}_{j} \cdot \left( \overleftarrow{u}^{z}_{\xi,t,j} - u^{z}_{\xi,t,j} \right) & \text{if } \mathrm{com}^{z}_{j} \\ \widetilde{\mathrm{rd}}^{z}_{j} \cdot \widetilde{\mathrm{z}}^{\mathrm{nom}}_{j} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ j \in \mathcal{J}
```

### `StorageUnit_charge_carried_in`

```yaml
StorageUnit_charge_carried_in:
  description: >-
    the charge a unit opens a snapshot with — its last snapshot's less
    standing loss where it is cyclic, the given initial charge at the start
    of the horizon, which no standing loss has touched yet, and the previous
    snapshot's less standing loss otherwise. Per period, the same holds with
    each investment period as the horizon
  dims: [scenario, snapshot, storage_unit]
  cases:
    cyclic:
      when: StorageUnit_cyclic_state_of_charge AND NOT StorageUnit_cyclic_state_of_charge_per_period AND NOT StorageUnit_state_of_charge_initial_per_period
      expression: StorageUnit_retention * shift(StorageUnit_state_of_charge, along=snapshot, offset=1, edge='wrap')
    opening:
      when: >-
        NOT StorageUnit_cyclic_state_of_charge AND NOT StorageUnit_cyclic_state_of_charge_per_period
        AND NOT StorageUnit_state_of_charge_initial_per_period AND position(snapshot) == 0
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
\overleftarrow{\mathit{soc}}_{\xi,t,s} = \begin{cases} \rho_{t,s} \cdot \mathit{soc}_{\xi,t \ominus 1,s} & \text{if } \mathrm{cyc}_{s} \wedge \neg \mathrm{cyc}^{y}_{s} \wedge \neg \mathrm{reset}_{s} \\ \mathrm{soc}^{0}_{s} & \text{if } \neg \mathrm{cyc}_{s} \wedge \neg \mathrm{cyc}^{y}_{s} \wedge \neg \mathrm{reset}_{s} \wedge \mathrm{pos}(t) = 0 \\ \rho_{t,s} \cdot \mathit{soc}_{\xi,t \ominus^{\mathrm{snapshot\_period}(t)} 1,s} & \text{if } \mathrm{cyc}^{y}_{s} \\ \mathrm{soc}^{0}_{s} & \text{if } \mathrm{reset}_{s} \wedge \neg \mathrm{cyc}^{y}_{s} \wedge \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) = 0 \\ \rho_{t,s} \cdot \mathit{soc}_{\xi,t - 1,s} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S}
```

### `Store_energy_carried_in`

```yaml
Store_energy_carried_in:
  description: >-
    the energy a store opens a snapshot with — its last snapshot's less
    standing loss where it is cyclic, the given initial energy at the start
    of the horizon, which no standing loss has touched yet, and the previous
    snapshot's less standing loss otherwise. Per period, the same holds with
    each investment period as the horizon
  dims: [scenario, snapshot, store]
  cases:
    cyclic:
      when: Store_e_cyclic AND NOT Store_e_cyclic_per_period AND NOT Store_e_initial_per_period
      expression: Store_retention * shift(Store_e, along=snapshot, offset=1, edge='wrap')
    opening:
      when: NOT Store_e_cyclic AND NOT Store_e_cyclic_per_period AND NOT Store_e_initial_per_period AND position(snapshot) == 0
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
\overleftarrow{e}_{\xi,t,v} = \begin{cases} \rho^{e}_{t,v} \cdot e_{\xi,t \ominus 1,v} & \text{if } \mathrm{cyc}^{e}_{v} \wedge \neg \mathrm{cyc}^{e,y}_{v} \wedge \neg \mathrm{reset}^{e}_{v} \\ \mathrm{e}^{0}_{v} & \text{if } \neg \mathrm{cyc}^{e}_{v} \wedge \neg \mathrm{cyc}^{e,y}_{v} \wedge \neg \mathrm{reset}^{e}_{v} \wedge \mathrm{pos}(t) = 0 \\ \rho^{e}_{t,v} \cdot e_{\xi,t \ominus^{\mathrm{snapshot\_period}(t)} 1,v} & \text{if } \mathrm{cyc}^{e,y}_{v} \\ \mathrm{e}^{0}_{v} & \text{if } \mathrm{reset}^{e}_{v} \wedge \neg \mathrm{cyc}^{e,y}_{v} \wedge \mathrm{pos}_{\mathrm{snapshot\_period}(t)}(t) = 0 \\ \rho^{e}_{t,v} \cdot e_{\xi,t - 1,v} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ v \in \mathcal{V}
```

### `Link_output_arrival`

```yaml
Link_output_arrival:
  description: >-
    what a link delivers to an output port at a snapshot — its flow after the
    port's efficiency, delayed by the port's `delay`; where the port is
    `cyclic_delay` the delayed flow wraps from the horizon's end, and where it
    is not the flow still in transit at the first snapshots is lost. A port
    that does not delay (`delay` zero) delivers its flow unshifted, cyclic or
    not
  dims: [scenario, snapshot, link_output]
  cases:
    wrapping:
      when: Link_output_cyclic_delay
      expression: shift(at(Link_p, by=Link_output_link, over=link, into=link_output) * Link_efficiency, along=snapshot, offset=Link_output_delay, edge='wrap')
  otherwise: shift(at(Link_p, by=Link_output_link, over=link, into=link_output) * Link_efficiency, along=snapshot, offset=Link_output_delay, edge=0)
```

```math
\overrightarrow{f}_{\xi,t,o} = \begin{cases} f_{\xi,t \ominus \mathrm{d}^{f},\mathrm{Link\_output\_link}(o)} \cdot \eta_{o} & \text{if } \mathrm{cyc}^{f}_{o} \\ f_{\xi,t \boxminus_{0} \mathrm{d}^{f},\mathrm{Link\_output\_link}(o)} \cdot \eta_{o} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ o \in \mathcal{O}
```

### `Process_output_arrival`

```yaml
Process_output_arrival:
  description: >-
    what a process transfers at a port at a snapshot — its internal power
    times the port's rate, delayed by the port's `delay`; where the port is
    `cyclic_delay` the delayed transfer wraps from the horizon's end, and where
    it is not the energy still in transit at the first snapshots is lost. A
    port that does not delay (`delay` zero) transfers at once, cyclic or not
  dims: [scenario, snapshot, process_output]
  cases:
    wrapping:
      when: Process_output_cyclic_delay
      expression: shift(at(Process_p, by=Process_output_process, over=process, into=process_output) * Process_rate, along=snapshot, offset=Process_output_delay, edge='wrap')
  otherwise: shift(at(Process_p, by=Process_output_process, over=process, into=process_output) * Process_rate, along=snapshot, offset=Process_output_delay, edge=0)
```

```math
\overrightarrow{z}_{\xi,t,r} = \begin{cases} z_{\xi,t \ominus \mathrm{d}^{z},\mathrm{Process\_output\_process}(r)} \cdot \alpha_{r} & \text{if } \mathrm{cyc}^{z}_{r} \\ z_{\xi,t \boxminus_{0} \mathrm{d}^{z},\mathrm{Process\_output\_process}(r)} \cdot \alpha_{r} & \text{otherwise} \end{cases} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ r \in \mathcal{R}
```

### `primary_energy`

```yaml
primary_energy:
  description: >-
    what a `primary_energy` row totals — weighted generator energy, less
    the charge left in weighted storage at the horizon's end; the initial
    charge it is compared against is folded into the row's constant
  expression: >-
    sum(sum(Generator_p * snapshot_weightings_generators * Generator_primary_energy_weight, over=snapshot), over=generator)
    - sum(sum(StorageUnit_state_of_charge * snapshot_is_last * StorageUnit_primary_energy_weight, over=snapshot), over=storage_unit)
    - sum(sum(Store_e * snapshot_is_last * Store_primary_energy_weight, over=snapshot), over=store)
```

```math
\mathit{primary\_energy}_{\xi,i} = \sum_{g \in \mathcal{G}} \sum_{t \in \mathcal{T}} p_{\xi,t,g} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \cdot \mathrm{a}_{i,g} - \left( \sum_{s \in \mathcal{S}} \sum_{t \in \mathcal{T}} \mathit{soc}_{\xi,t,s} \cdot \mathrm{last}_{t} \cdot \mathrm{a}^{h}_{i,s} \right) - \left( \sum_{v \in \mathcal{V}} \sum_{t \in \mathcal{T}} e_{\xi,t,v} \cdot \mathrm{last}_{t} \cdot \mathrm{a}^{e}_{i,v} \right) \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I}
```

### `operational_limit`

```yaml
operational_limit:
  description: >-
    what an `operational_limit` row totals — the weighted energy its
    generators deliver, plus what its non-cyclic storage draws down; the
    initial charge it draws from is folded into the row's constant
  expression: >-
    sum(sum(Generator_p * snapshot_weightings_generators * Generator_operational_limit_weight, over=snapshot), over=generator)
    - sum(sum(StorageUnit_state_of_charge * snapshot_is_last * StorageUnit_operational_limit_weight, over=snapshot), over=storage_unit)
    - sum(sum(Store_e * snapshot_is_last * Store_operational_limit_weight, over=snapshot), over=store)
```

```math
\mathit{operational\_limit}_{\xi,i} = \sum_{g \in \mathcal{G}} \sum_{t \in \mathcal{T}} p_{\xi,t,g} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \cdot \mathrm{b}_{i,g} - \left( \sum_{s \in \mathcal{S}} \sum_{t \in \mathcal{T}} \mathit{soc}_{\xi,t,s} \cdot \mathrm{last}_{t} \cdot \mathrm{b}^{h}_{i,s} \right) - \left( \sum_{v \in \mathcal{V}} \sum_{t \in \mathcal{T}} e_{\xi,t,v} \cdot \mathrm{last}_{t} \cdot \mathrm{b}^{e}_{i,v} \right) \qquad \forall\, \xi \in \Xi,\ i \in \mathcal{I}
```

### `transmission_volume_expansion`

```yaml
transmission_volume_expansion:
  description: what a `transmission_volume_expansion_limit` row totals — length times the chosen build of the row's branches
  expression: >-
    sum(Line_s_nom_ext * Line_volume_weight, over=line)
    + sum(Link_p_nom_ext * Link_volume_weight, over=link)
```

```math
\mathit{transmission\_volume\_expansion}_{i} = \sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{len}_{i,k} + \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{len}^{f}_{i,l} \qquad \forall\, i \in \mathcal{I}
```

### `transmission_expansion_cost`

```yaml
transmission_expansion_cost:
  description: what a `transmission_expansion_cost_limit` row totals — capital cost times the chosen build of the row's branches
  expression: >-
    sum(Line_s_nom_ext * Line_expansion_cost_weight, over=line)
    + sum(Link_p_nom_ext * Link_expansion_cost_weight, over=link)
```

```math
\mathit{transmission\_expansion\_cost}_{i} = \sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{cc}_{i,k} + \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{cc}^{f}_{i,l} \qquad \forall\, i \in \mathcal{I}
```

### `tech_capacity_expansion`

```yaml
tech_capacity_expansion:
  description: what a `tech_capacity_expansion_limit` row totals — the chosen build of the row's carrier-and-bus set
  expression: >-
    sum(Generator_p_nom_ext * Generator_tech_capacity_weight, over=generator)
    + sum(Link_p_nom_ext * Link_tech_capacity_weight, over=link)
    + sum(Line_s_nom_ext * Line_tech_capacity_weight, over=line)
    + sum(StorageUnit_p_nom_ext * StorageUnit_tech_capacity_weight, over=storage_unit)
    + sum(Store_e_nom_ext * Store_tech_capacity_weight, over=store)
    + sum(Process_p_nom_ext * Process_tech_capacity_weight, over=process)
```

```math
\mathit{tech\_capacity\_expansion}_{i} = \sum_{g \in \mathcal{G}} P_{g} \cdot \mathrm{m}_{i,g} + \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{m}^{f}_{i,l} + \sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{m}^{l}_{i,k} + \sum_{s \in \mathcal{S}} H_{s} \cdot \mathrm{m}^{h}_{i,s} + \sum_{v \in \mathcal{V}} E_{v} \cdot \mathrm{m}^{e}_{i,v} + \sum_{j \in \mathcal{J}} Z_{j} \cdot \mathrm{m}^{z}_{i,j} \qquad \forall\, i \in \mathcal{I}
```

### `scenario_opex`

```yaml
scenario_opex:
  description: what a future costs to run — every operating term, weighted by the snapshot's hours and its period, before the scenario's own weight
  expression: >-
    sum(sum(Generator_p * Generator_marginal_cost * snapshot_weightings_objective * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=generator), over=snapshot)
    + sum(sum(Generator_p * Generator_p * Generator_marginal_cost_quadratic * snapshot_weightings_objective * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=generator), over=snapshot)
    + sum(sum(Link_p * Link_marginal_cost * snapshot_weightings_objective * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=link), over=snapshot)
    + sum(sum(Link_p * Link_p * Link_marginal_cost_quadratic * snapshot_weightings_objective * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=link), over=snapshot)
    + sum(sum(Process_p * Process_marginal_cost * snapshot_weightings_objective * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=process), over=snapshot)
    + sum(sum(StorageUnit_p_dispatch * StorageUnit_marginal_cost * snapshot_weightings_objective * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=storage_unit), over=snapshot)
    + sum(sum(StorageUnit_state_of_charge * StorageUnit_marginal_cost_storage * snapshot_weightings_objective * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=storage_unit), over=snapshot)
    + sum(sum(StorageUnit_spill * StorageUnit_spill_cost * snapshot_weightings_objective * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=storage_unit), over=snapshot)
    + sum(sum(Store_p * Store_marginal_cost * snapshot_weightings_objective * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=store), over=snapshot)
    + sum(sum(Store_e * Store_marginal_cost_storage * snapshot_weightings_objective * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=store), over=snapshot)
    + sum(sum(Generator_status * Generator_stand_by_cost * snapshot_weightings_objective * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=generator), over=snapshot)
    + sum(sum(Generator_start_up * Generator_start_up_cost * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=generator), over=snapshot)
    + sum(sum(Generator_shut_down * Generator_shut_down_cost * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=generator), over=snapshot)
    + sum(sum(Link_status * Link_stand_by_cost * snapshot_weightings_objective * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=link), over=snapshot)
    + sum(sum(Link_start_up * Link_start_up_cost * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=link), over=snapshot)
    + sum(sum(Link_shut_down * Link_shut_down_cost * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=link), over=snapshot)
    + sum(sum(Process_status * Process_stand_by_cost * snapshot_weightings_objective * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=process), over=snapshot)
    + sum(sum(Process_start_up * Process_start_up_cost * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=process), over=snapshot)
    + sum(sum(Process_shut_down * Process_shut_down_cost * at(period_weight_objective, by=snapshot_period, over=period, into=snapshot), over=process), over=snapshot)
```

```math
\mathit{scenario\_opex}_{\xi} = \sum_{t \in \mathcal{T}} \sum_{g \in \mathcal{G}} p_{\xi,t,g} \cdot \mathrm{c}_{t,g} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{g \in \mathcal{G}} p_{\xi,t,g} \cdot p_{\xi,t,g} \cdot \mathrm{c}^{(2)}_{t,g} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{l \in \mathcal{L}} f_{\xi,t,l} \cdot \mathrm{c}^{f}_{t,l} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{l \in \mathcal{L}} f_{\xi,t,l} \cdot f_{\xi,t,l} \cdot \mathrm{c}^{f,(2)}_{t,l} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{j \in \mathcal{J}} z_{\xi,t,j} \cdot \mathrm{c}^{z}_{t,j} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{s \in \mathcal{S}} h^{+}_{\xi,t,s} \cdot \mathrm{c}^{h}_{t,s} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{s \in \mathcal{S}} \mathit{soc}_{\xi,t,s} \cdot \mathrm{c}^{\mathrm{soc}}_{t,s} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{s \in \mathcal{S}} \mathit{spill}_{\xi,t,s} \cdot \mathrm{c}^{\mathrm{spill}}_{t,s} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{v \in \mathcal{V}} q_{\xi,t,v} \cdot \mathrm{c}^{q}_{t,v} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{v \in \mathcal{V}} e_{\xi,t,v} \cdot \mathrm{c}^{e}_{t,v} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{g \in \mathcal{G}} u_{\xi,t,g} \cdot \mathrm{c}^{\mathrm{on}}_{t,g} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{g \in \mathcal{G}} \mathit{up}_{\xi,t,g} \cdot \mathrm{c}^{\mathrm{up}}_{g} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{g \in \mathcal{G}} \mathit{dn}_{\xi,t,g} \cdot \mathrm{c}^{\mathrm{dn}}_{g} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{l \in \mathcal{L}} u^{f}_{\xi,t,l} \cdot \mathrm{c}^{f,\mathrm{on}}_{t,l} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{l \in \mathcal{L}} \mathit{up}^{f}_{\xi,t,l} \cdot \mathrm{c}^{f,\mathrm{up}}_{l} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{l \in \mathcal{L}} \mathit{dn}^{f}_{\xi,t,l} \cdot \mathrm{c}^{f,\mathrm{dn}}_{l} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{j \in \mathcal{J}} u^{z}_{\xi,t,j} \cdot \mathrm{c}^{z,\mathrm{on}}_{t,j} \cdot \mathrm{w}_{t} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{j \in \mathcal{J}} \mathit{up}^{z}_{\xi,t,j} \cdot \mathrm{c}^{z,\mathrm{up}}_{j} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} + \sum_{t \in \mathcal{T}} \sum_{j \in \mathcal{J}} \mathit{dn}^{z}_{\xi,t,j} \cdot \mathrm{c}^{z,\mathrm{dn}}_{j} \cdot \mathrm{w}^{y}_{\mathrm{snapshot\_period}(t)} \qquad \forall\, \xi \in \Xi
```

### `Carrier_additions`

```yaml
Carrier_additions:
  description: >-
    what a carrier adds in a period — every extendable component of that
    carrier, counting each build in the first period it stands in. PyPSA sums
    the components that carry a carrier attribute; the transformer term is the
    spec's own extension, since PyPSA gives a transformer no carrier
  expression: >-
    sum(Generator_p_nom_ext * Generator_first_active, by=Generator_carrier, over=generator, into=carrier)
    + sum(Link_p_nom_ext * Link_first_active, by=Link_carrier, over=link, into=carrier)
    + sum(StorageUnit_p_nom_ext * StorageUnit_first_active, by=StorageUnit_carrier, over=storage_unit, into=carrier)
    + sum(Store_e_nom_ext * Store_first_active, by=Store_carrier, over=store, into=carrier)
    + sum(Line_s_nom_ext * Line_first_active, by=Line_carrier, over=line, into=carrier)
    + sum(Process_p_nom_ext * Process_first_active, by=Process_carrier, over=process, into=carrier)
    + sum(Transformer_s_nom_ext * Transformer_first_active, by=Transformer_carrier, over=transformer, into=carrier)
```

```math
\mathit{Carrier\_additions}_{y,i} = \sum_{g \in \mathcal{G} \,:\, \mathrm{Generator\_carrier}(g) = i} P_{g} \cdot \mathrm{new}_{y,g} + \sum_{l \in \mathcal{L} \,:\, \mathrm{Link\_carrier}(l) = i} F_{l} \cdot \mathrm{new}^{f}_{y,l} + \sum_{s \in \mathcal{S} \,:\, \mathrm{StorageUnit\_carrier}(s) = i} H_{s} \cdot \mathrm{new}^{h}_{y,s} + \sum_{v \in \mathcal{V} \,:\, \mathrm{Store\_carrier}(v) = i} E_{v} \cdot \mathrm{new}^{e}_{y,v} + \sum_{k \in \mathcal{K} \,:\, \mathrm{Line\_carrier}(k) = i} S_{k} \cdot \mathrm{new}^{s}_{y,k} + \sum_{j \in \mathcal{J} \,:\, \mathrm{Process\_carrier}(j) = i} Z_{j} \cdot \mathrm{new}^{z}_{y,j} + \sum_{m \in \mathcal{M} \,:\, \mathrm{Transformer\_carrier}(m) = i} \Sigma_{m} \cdot \mathrm{new}^{\sigma}_{y,m} \qquad \forall\, y \in \mathcal{Y},\ i \in \mathcal{I}
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
0 \le \mathit{spill}_{\xi,t,s} \le \mathrm{inflow}_{t,s} \qquad \forall\, \xi \in \Xi,\ t \in \mathcal{T},\ s \in \mathcal{S} \,:\, \mathrm{inflow}_{t,s} > 0 \wedge \mathrm{on}^{h}_{t,s}
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
<!-- gallery:end -->

Regenerate with `pixi run python -m tools.gallery`.
