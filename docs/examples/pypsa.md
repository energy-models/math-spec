<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# PyPSA in one file

The model a plain `n.optimize()` builds, stated as one file and grown a rung
at a time towards
[milestone 1](https://github.com/energy-models/math-spec/milestone/1). The
index below lists every row PyPSA emits (PyPSA `1.3.0`,
`pypsa/optimization/`) and links each to its block in the file once it is
there. The blocks are generated, so a row that stops loading or changes its
math fails CI.

Three rules shape the file. Bounds are the explicit rows PyPSA writes, so
their duals are row duals. Regimes are data columns and `where:` masks, never
file variants. Names are PyPSA's, `Component_attribute`, with a symbol table
(`examples/symbols/pypsa.yaml`) making the math read as math.

## Index

A row is **done** and links once the file states it as the one block PyPSA
builds — on this branch, as it stands; a fix still on its way stays
not-done, its PR or issue in the note. Three words say the distance:
**split** — the same feasible region and optimum under a different
statement: several `where:` blocks, or a bookkeeping difference the note
names · **open** — not stated yet · **out** — never stated, deliberately:
emitted only under the keyword, scope or version the note names. A name carrying `{k}` or `{s}` stands for the family PyPSA numbers per segment or scenario.

Each rung's banner below states what PyPSA solved its reference network
to. What an engine makes of the same rung — the objective and prices across
the fence, and the two linopy models label for label — is that engine's own
record: lpspec certifies itself against these rungs under
`differential/pypsa/` in its own tree.

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
| `Bus-meshed-*-nodal_balance`                        | split  | a linopy-speed split of the one balance row here — no fixture triggers it yet, so the row-for-row carry-over is unproven (#123) |
| [`marginal_cost`](#objective)                       | done   |                                                            |
| [`marginal_cost_quadratic`](pypsa_quadratic.md)     | done   | rung 10, a file of its own                                 |
| `objective_constant`                                | split  | an objective shift, compared net of `n._objective_constant` — every fixture's constant is 0, so the netting is untested (#123) |

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
| [`StorageUnit-energy_balance`](#storageunit-energy_balance) | split | three blocks: carried / initial / cyclic, fused by #70; `(1-loss)**eh` is prep |
| [`Store-energy_balance`](#store-energy_balance)       | split  | same                                                          |
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
> ✔ `pypsa 1.3.0` solves this rung's network at objective `7633.908502024291`, 184 rows.

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
| [`{c}-p-ramp_limit_up/down`](#generator-p-ramp_limit_up) | split | fix, ext and first-snapshot blocks, fused by #70; com is rung 7's, big-M rung 8's |

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
| [`Carrier-growth_limit`](pypsa_multi_period.md) | done | rung 15, a file of its own |
| `effect_limit`, priced effects        | open        | `effects.py` not inventoried                      |

<!-- reference:rung_05_global_constraints:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `10282.833333333332`, 102 rows.

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
| [`{c}-status`, `-start_up`, `-shut_down`](#variable-domains) | done | Generator; a committable link is not taken up here |
| [`{c}-com-p-lower/upper`](#generator-com-p-lower) | done |                                                          |
| [`{c}-*-p-fixed-upper`](#generator-status-p-fixed-upper) | done | status, start and stop each at most one, as explicit rows |
| [`{c}-com-transition-start-up/shut-down`](#generator-com-transition-start-up) | split | a first-snapshot block carries the initial status, fused by #70 |
| [`{c}-com-up-time`, `-down-time`](#generator-com-up-time) | done | `sum_back(within=min_up_time)`                    |
| [`{c}-com-status-*-must_stay_up`](#generator-com-status-min_up_time_must_stay_up) | done | the window is a prep mask — `position()` takes a literal, not a parameter |
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
| `{c}-*-p-fixed-upper`, modular                | split  | a fixed modular build is floored in data prep, see X1; its rows are the ordinary fix rows — no fixture fixes one yet, so the floor is unproven (#123) |
| [`{c}-com-mod-p-lower/upper`](#generator-com-mod-p-lower) | done | one module's share, times the status          |
| [`{c}-com-ext-p-*` (big-M)](#generator-com-ext-p-upper-cap) | done | a cap row beside a big-M row; `M` is the build cap at full availability, data prep |
| [`{c}-com-ext-p-lower-nonneg`](#generator-com-ext-p-lower-nonneg) | done | `(p_min_pu >= 0).all()` is prep        |
| [`{c}-p-ramp_limit_*-bigM`](#generator-p-ramp_limit_up-run-bigm) | split | run and start rows up, run and shut rows down, each with an initial block #70 fuses |

<!-- reference:rung_08_modular_big_m:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `19712.5`, 155 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_08_modular_big_m.py`

```python
"""Rung 8: modular and big-M — capacity in whole modules, and a committable unit whose capacity is also built."""

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
    n.add('Load', 'mill_load', bus='mill', p_set=[40, 80, 120, 60])
    return n
```

</details>
<!-- reference:rung_08_modular_big_m:end -->

### Rung 9 — multi-link and delay

| PyPSA                        | status | note                                          |
| ---------------------------- | ------ | --------------------------------------------- |
| [nodal balance, ports 2..n](#bus-nodal_balance) | done | port 2 states the pattern: a partial `Link_bus2` map, one more term per port |
| nodal balance, link delay    | open   | #75, a per-link edge kind                     |

<!-- reference:rung_09_multilink:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `11700.0`, 68 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_09_multilink.py`

```python
"""Rung 9: multi-link and delay — one link with two output buses."""

from __future__ import annotations

import spine


def build():
    """The spine plus this rung's additions, as a ``pypsa.Network``."""
    n = spine.build()
    n.add('Bus', 'gasb')
    n.add('Bus', 'power')
    n.add('Bus', 'heat')
    n.add('Generator', 'well', bus='gasb', p_nom=100, marginal_cost=5)
    n.add('Generator', 'grid_import', bus='power', p_nom=50, marginal_cost=60)
    n.add(
        'Link',
        'chp',
        bus0='gasb',
        bus1='power',
        bus2='heat',
        efficiency=0.4,
        efficiency2=0.45,
        p_nom=60,
        marginal_cost=1,
    )
    n.add('Load', 'homes', bus='power', p_set=20)
    n.add('Load', 'district', bus='heat', p_set=18)
    return n
```

</details>
<!-- reference:rung_09_multilink:end -->

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

### Not on a rung

| PyPSA                          | status | note                                 |
| ------------------------------ | ------ | ------------------------------------ |
| [`{c}-loss*`](pypsa_losses.md) | done   | rung 13, a file of its own; tangent form |
| [`CVaR-*`](pypsa_stochastic.md) | done  | rung 14, a file of its own           |

## Refusals

Where PyPSA refuses to build, parity means refusing too. None is a language
gap; each is a data check not made yet, and where it should live — language,
data prep, or harness — is one open question.

| PyPSA raises                                 | on                                                | here                    | note |
| -------------------------------------------- | ------------------------------------------------- | ----------------------- | ---- |
| `ValueError`, `constraints.py:1449`          | fixed modular `p_nom` not a multiple of `p_nom_mod` | builds a smaller plant | X1   |
| `ValueError`, `constraints.py:1192`          | load on a bus with nothing attached               | row not built, unserved | X2   |
| `ValueError`, `optimize.py:430`              | no component carries a cost                       | feasibility problem     | X3   |
| `NotImplementedError`, `global_constraints.py:339` | depletion with period weightings `!= 1`     | out                     |      |
| `ValueError`/`RuntimeError`, losses          | `s_nom_max = inf`; secant cap                     | out                     |      |

Duals and solutions are read back by the harness on the lpspec side:
`marginal_price` is the balance dual over `w_objective`, `mu_upper` the
concatenation of the regime blocks, `p0`/`p1` derived from `Link-p`.

## The file

<!-- gallery:begin -->
The model a plain `n.optimize()` builds, stated in one file. Every declaration is named `Component_attribute` after the PyPSA statement it stands for, and each constraint's description opens with the linopy name PyPSA gives that row, so the two can be read side by side. PyPSA's regimes — extendable, committable — are data columns and become `where:` masks. Bounds are the explicit rows PyPSA writes, so their duals are row duals. Parameters no PyPSA table carries verbatim are computed in data prep and say so in their description.

#### Sets

| Symbol | Meaning |
|---|---|
| $\mathcal{T}$ | index $t$ — `snapshot` — dispatch periods |
| $\mathcal{N}$ | index $n$ — `bus` — network nodes |
| $\mathcal{G}$ | index $g$ — `generator` with $\mathrm{Generator\_bus}: \mathcal{G} \to \mathcal{N}$ — generating units, each on one bus |
| $\mathcal{L}$ | index $l$ — `link` with $\mathrm{Link\_bus0}: \mathcal{L} \to \mathcal{N},\enspace \mathrm{Link\_bus1}: \mathcal{L} \to \mathcal{N},\enspace \mathrm{Link\_bus2}: \mathcal{L} \to \mathcal{N}$ — controllable connections, each from one bus to another |
| $\mathcal{D}$ | index $d$ — `load` with $\mathrm{Load\_bus}: \mathcal{D} \to \mathcal{N}$ — demands, each on one bus |
| $\mathcal{S}$ | index $s$ — `storage_unit` with $\mathrm{StorageUnit\_bus}: \mathcal{S} \to \mathcal{N}$ — storage units, dispatch and store behind one bus connection |
| $\mathcal{V}$ | index $v$ — `store` with $\mathrm{Store\_bus}: \mathcal{V} \to \mathcal{N}$ — pure energy stores, each on one bus |
| $\mathcal{K}$ | index $k$ — `line` with $\mathrm{Line\_bus0}: \mathcal{K} \to \mathcal{N},\enspace \mathrm{Line\_bus1}: \mathcal{K} \to \mathcal{N}$ — passive branches, each between two buses, their flow set by impedance |
| $\mathcal{C}$ | index $c$ — `cycle` — independent cycles of the passive network graph — the cycle basis, data prep |
| $\mathcal{O}$ | index $o$ — `global_constraint` — PyPSA's `GlobalConstraint` rows, one label per declared limit |

#### Parameters

| Symbol | Meaning |
|---|---|
| $\mathrm{w}$ | `snapshot_weightings_objective` over $\mathcal{T}$ — PyPSA's `snapshot_weightings.objective` — hours a snapshot stands for in the cost |
| $\mathrm{p}^{\mathrm{nom}}$ | `Generator_p_nom` over $\mathcal{G}$ — nominal power |
| $\mathrm{ext}$ | `Generator_p_nom_extendable` over $\mathcal{G}$ — whether the nominal power is a decision |
| $\underline{\mathrm{p}}$ | `Generator_p_min_pu` over $\mathcal{T} \times \mathcal{G}$ — least output, per unit of nominal power |
| $\overline{\mathrm{p}}$ | `Generator_p_max_pu` over $\mathcal{T} \times \mathcal{G}$ — most output, per unit of nominal power — an availability profile |
| $\mathrm{c}$ | `Generator_marginal_cost` over $\mathcal{T} \times \mathcal{G}$ — cost of one unit of output |
| $\mathrm{com}$ | `Generator_committable` over $\mathcal{G}$ — whether output is gated by an on/off status decision |
| $\mathrm{ru}$ | `Generator_ramp_limit_up` over $\mathcal{G}$ — most a generator may raise its output between snapshots, per unit of nominal power; no value means no limit |
| $\mathrm{rd}$ | `Generator_ramp_limit_down` over $\mathcal{G}$ — most a generator may lower its output between snapshots, per unit of nominal power; no value means no limit |
| $\mathrm{ru}^{\mathrm{up}}$ | `Generator_ramp_limit_start_up` over $\mathcal{G}$ — most output in the snapshot a unit starts, per unit of nominal power |
| $\mathrm{rd}^{\mathrm{dn}}$ | `Generator_ramp_limit_shut_down` over $\mathcal{G}$ — most output in the snapshot before a unit stops, per unit of nominal power |
| $\mathrm{UT}$ | `Generator_min_up_time` over $\mathcal{G}$ — least snapshots a unit stays on once started |
| $\mathrm{DT}$ | `Generator_min_down_time` over $\mathcal{G}$ — least snapshots a unit stays off once stopped |
| $\mathrm{u}^{0}$ | `Generator_status_initial` over $\mathcal{G}$ — one where the unit was on before the first snapshot, zero where off — PyPSA's `up_time_before > 0`, data prep |
| $\mathrm{hold}$ | `Generator_must_stay_up` over $\mathcal{T} \times \mathcal{G}$ — true while the up time a unit brought into the horizon still binds — data prep, since `position()` compares against a literal rather than a parameter |
| $\mathrm{c}^{\mathrm{up}}$ | `Generator_start_up_cost` over $\mathcal{G}$ — cost of one start |
| $\mathrm{c}^{\mathrm{dn}}$ | `Generator_shut_down_cost` over $\mathcal{G}$ — cost of one stop |
| $\mathrm{c}^{\mathrm{on}}$ | `Generator_stand_by_cost` over $\mathcal{T} \times \mathcal{G}$ — cost of one snapshot spent on |
| $\mathrm{p}^{\mathrm{mod}}$ | `Generator_p_nom_mod` over $\mathcal{G}$ — the module size a build comes in whole numbers of; no value means the build is continuous |
| $\mathrm{M}$ | `Generator_big_m` over $\mathcal{G}$ — a bound safely above any feasible output — the build cap at full availability, data prep |
| $\mathrm{nonneg}$ | `Generator_p_min_pu_nonneg` over $\mathcal{G}$ — true where none of the generator's own minimums-per-unit is negative — PyPSA's per-unit `(p_min_pu >= 0).all()`, data prep |
| $\mathrm{ru}^{f}$ | `Link_ramp_limit_up` over $\mathcal{L}$ — most a link may raise its flow between snapshots, per unit of nominal power; no value means no limit |
| $\mathrm{rd}^{f}$ | `Link_ramp_limit_down` over $\mathcal{L}$ — most a link may lower its flow between snapshots, per unit of nominal power; no value means no limit |
| $\mathrm{f}^{\mathrm{nom}}$ | `Link_p_nom` over $\mathcal{L}$ — nominal power |
| $\mathrm{ext}^{f}$ | `Link_p_nom_extendable` over $\mathcal{L}$ — whether the nominal power is a decision |
| $\underline{\mathrm{f}}$ | `Link_p_min_pu` over $\mathcal{T} \times \mathcal{L}$ — least flow, per unit of nominal power — negative for a link that carries both ways |
| $\overline{\mathrm{f}}$ | `Link_p_max_pu` over $\mathcal{T} \times \mathcal{L}$ — most flow, per unit of nominal power |
| $\eta$ | `Link_efficiency` over $\mathcal{L}$ — share of the flow that arrives at the link's `Link_bus1` end |
| $\eta^{2}$ | `Link_efficiency2` over $\mathcal{L}$ — share of the flow that arrives at the link's `Link_bus2` end — negative where that port consumes |
| $\mathrm{c}^{f}$ | `Link_marginal_cost` over $\mathcal{T} \times \mathcal{L}$ — cost of one unit of flow |
| $\mathrm{load}$ | `Load_p_set` over $\mathcal{T} \times \mathcal{D}$ — demand |
| $\mathrm{p}^{\mathrm{set}}$ | `Generator_p_set` over $\mathcal{T} \times \mathcal{G}$ — a given output schedule; a generator without one has no row here |
| $\mathrm{f}^{\mathrm{set}}$ | `Link_p_set` over $\mathcal{T} \times \mathcal{L}$ — a given flow schedule; a link without one has no row here |
| $\mathrm{w}^{\mathrm{sto}}$ | `snapshot_weightings_stores` over $\mathcal{T}$ — PyPSA's `snapshot_weightings.stores` — hours a snapshot stands for in a storage balance |
| $\mathrm{w}^{\mathrm{gen}}$ | `snapshot_weightings_generators` over $\mathcal{T}$ — PyPSA's `snapshot_weightings.generators` — hours a snapshot stands for in an energy total |
| $\underline{\mathrm{p}}^{\mathrm{nom}}$ | `Generator_p_nom_min` over $\mathcal{G}$ — least nominal power an extendable generator may be built at |
| $\overline{\mathrm{p}}^{\mathrm{nom}}$ | `Generator_p_nom_max` over $\mathcal{G}$ — most nominal power an extendable generator may be built at |
| $\mathrm{c}^{\mathrm{cap}}$ | `Generator_capital_cost` over $\mathcal{G}$ — cost of one unit of nominal power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $\mathrm{p}^{\mathrm{nom,set}}$ | `Generator_p_nom_set` over $\mathcal{G}$ — a given nominal power for an extendable generator; one without a value has no row here |
| $\underline{\mathrm{E}}$ | `Generator_e_sum_min` over $\mathcal{G}$ — least energy over the horizon; minus infinity where no floor is meant |
| $\overline{\mathrm{E}}$ | `Generator_e_sum_max` over $\mathcal{G}$ — most energy over the horizon — a fuel or emission budget in energy terms; infinity where no cap is meant |
| $\underline{\mathrm{f}}^{\mathrm{nom}}$ | `Link_p_nom_min` over $\mathcal{L}$ — least nominal power an extendable link may be built at |
| $\overline{\mathrm{f}}^{\mathrm{nom}}$ | `Link_p_nom_max` over $\mathcal{L}$ — most nominal power an extendable link may be built at |
| $\mathrm{c}^{\mathrm{cap},f}$ | `Link_capital_cost` over $\mathcal{L}$ — cost of one unit of nominal power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $\mathrm{f}^{\mathrm{nom,set}}$ | `Link_p_nom_set` over $\mathcal{L}$ — a given nominal power for an extendable link; one without a value has no row here |
| $\underline{\mathrm{h}}^{\mathrm{nom}}$ | `StorageUnit_p_nom_min` over $\mathcal{S}$ — least nominal power an extendable storage unit may be built at |
| $\overline{\mathrm{h}}^{\mathrm{nom}}$ | `StorageUnit_p_nom_max` over $\mathcal{S}$ — most nominal power an extendable storage unit may be built at |
| $\mathrm{c}^{\mathrm{cap},h}$ | `StorageUnit_capital_cost` over $\mathcal{S}$ — cost of one unit of nominal power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $\mathrm{h}^{\mathrm{nom,set}}$ | `StorageUnit_p_nom_set` over $\mathcal{S}$ — a given nominal power for an extendable storage unit; one without a value has no row here |
| $\underline{\mathrm{e}}^{\mathrm{nom}}$ | `Store_e_nom_min` over $\mathcal{V}$ — least nominal capacity an extendable store may be built at |
| $\overline{\mathrm{e}}^{\mathrm{nom}}$ | `Store_e_nom_max` over $\mathcal{V}$ — most nominal capacity an extendable store may be built at |
| $\mathrm{c}^{\mathrm{cap},e}$ | `Store_capital_cost` over $\mathcal{V}$ — cost of one unit of nominal capacity — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $\mathrm{e}^{\mathrm{nom,set}}$ | `Store_e_nom_set` over $\mathcal{V}$ — a given nominal capacity for an extendable store; one without a value has no row here |
| $\mathrm{h}^{\mathrm{nom}}$ | `StorageUnit_p_nom` over $\mathcal{S}$ — nominal power |
| $\mathrm{ext}^{h}$ | `StorageUnit_p_nom_extendable` over $\mathcal{S}$ — whether the nominal power is a decision |
| $\underline{\mathrm{h}}$ | `StorageUnit_p_min_pu` over $\mathcal{T} \times \mathcal{S}$ — most storing, per unit of nominal power and negated |
| $\overline{\mathrm{h}}$ | `StorageUnit_p_max_pu` over $\mathcal{T} \times \mathcal{S}$ — most dispatch, per unit of nominal power |
| $\mathrm{T}^{h}$ | `StorageUnit_max_hours` over $\mathcal{S}$ — energy capacity, as hours of dispatch at nominal power |
| $\eta^{-}$ | `StorageUnit_efficiency_store` over $\mathcal{S}$ — share of the power drawn from the bus that becomes charge |
| $\eta^{+}$ | `StorageUnit_efficiency_dispatch` over $\mathcal{S}$ — share of the charge drawn down that reaches the bus |
| $\rho$ | `StorageUnit_retention` over $\mathcal{T} \times \mathcal{S}$ — share of charge kept over a snapshot — PyPSA's `(1 - standing_loss) ** elapsed hours`, data prep |
| $\mathrm{inflow}$ | `StorageUnit_inflow` over $\mathcal{T} \times \mathcal{S}$ — energy arriving per hour, a river into a reservoir |
| $\mathrm{soc}^{0}$ | `StorageUnit_state_of_charge_initial` over $\mathcal{S}$ — charge held before the first snapshot |
| $\mathrm{cyc}$ | `StorageUnit_cyclic_state_of_charge` over $\mathcal{S}$ — whether the horizon closes on itself instead of opening on the initial charge |
| $\mathrm{c}^{h}$ | `StorageUnit_marginal_cost` over $\mathcal{T} \times \mathcal{S}$ — cost of one unit of dispatch |
| $\mathrm{c}^{\mathrm{soc}}$ | `StorageUnit_marginal_cost_storage` over $\mathcal{T} \times \mathcal{S}$ — cost of one unit of charge held over one snapshot |
| $\mathrm{c}^{\mathrm{spill}}$ | `StorageUnit_spill_cost` over $\mathcal{T} \times \mathcal{S}$ — cost of one unit of inflow passed on unused |
| $\mathrm{h}^{\mathrm{set}}$ | `StorageUnit_p_set` over $\mathcal{T} \times \mathcal{S}$ — a given net dispatch schedule; a unit without one has no row here |
| $\mathrm{soc}^{\mathrm{set}}$ | `StorageUnit_state_of_charge_set` over $\mathcal{T} \times \mathcal{S}$ — a given charge schedule; a unit without one has no row here |
| $\mathrm{e}^{\mathrm{nom}}$ | `Store_e_nom` over $\mathcal{V}$ — nominal energy capacity |
| $\mathrm{ext}^{e}$ | `Store_e_nom_extendable` over $\mathcal{V}$ — whether the nominal energy capacity is a decision |
| $\underline{\mathrm{e}}$ | `Store_e_min_pu` over $\mathcal{T} \times \mathcal{V}$ — least energy held, per unit of nominal capacity — negative for a store that may go short |
| $\overline{\mathrm{e}}$ | `Store_e_max_pu` over $\mathcal{T} \times \mathcal{V}$ — most energy held, per unit of nominal capacity |
| $\rho^{e}$ | `Store_retention` over $\mathcal{T} \times \mathcal{V}$ — share of energy kept over a snapshot — PyPSA's `(1 - standing_loss) ** elapsed hours`, data prep |
| $\mathrm{e}^{0}$ | `Store_e_initial` over $\mathcal{V}$ — energy held before the first snapshot |
| $\mathrm{cyc}^{e}$ | `Store_e_cyclic` over $\mathcal{V}$ — whether the horizon closes on itself instead of opening on the initial energy |
| $\mathrm{c}^{q}$ | `Store_marginal_cost` over $\mathcal{T} \times \mathcal{V}$ — cost of one unit of power delivered |
| $\mathrm{c}^{e}$ | `Store_marginal_cost_storage` over $\mathcal{T} \times \mathcal{V}$ — cost of one unit of energy held over one snapshot |
| $\mathrm{e}^{\mathrm{set}}$ | `Store_e_set` over $\mathcal{T} \times \mathcal{V}$ — a given energy schedule; a store without one has no row here |
| $\mathrm{s}^{\mathrm{nom}}$ | `Line_s_nom` over $\mathcal{K}$ — nominal apparent power |
| $\mathrm{ext}^{s}$ | `Line_s_nom_extendable` over $\mathcal{K}$ — whether the nominal apparent power is a decision |
| $\overline{\mathrm{s}}$ | `Line_s_max_pu` over $\mathcal{T} \times \mathcal{K}$ — most flow either way, per unit of nominal apparent power |
| $\underline{\mathrm{s}}^{\mathrm{nom}}$ | `Line_s_nom_min` over $\mathcal{K}$ — least nominal apparent power an extendable line may be built at |
| $\overline{\mathrm{s}}^{\mathrm{nom}}$ | `Line_s_nom_max` over $\mathcal{K}$ — most nominal apparent power an extendable line may be built at |
| $\mathrm{c}^{\mathrm{cap},s}$ | `Line_capital_cost` over $\mathcal{K}$ — cost of one unit of nominal apparent power — PyPSA's `capital_cost`, periodized as an annuity in data prep |
| $\mathrm{s}^{\mathrm{nom,set}}$ | `Line_s_nom_set` over $\mathcal{K}$ — a given nominal apparent power for an extendable line; one without a value has no row here |
| $\mathrm{s}^{\mathrm{set}}$ | `Line_s_set` over $\mathcal{T} \times \mathcal{K}$ — a given flow schedule; a line without one has no row here |
| $\mathrm{x}$ | `Line_cycle_weight` over $\mathcal{K} \times \mathcal{C}$ — the line's series impedance, signed by its orientation in the cycle — the cycle basis, data prep; a line in no cycle has no row |
| $\mathrm{type}$ | `GlobalConstraint_type` over $\mathcal{O}$ — which formula the row takes — `primary_energy`, `operational_limit`, `transmission_volume_expansion_limit`, `transmission_expansion_cost_limit` or `tech_capacity_expansion_limit` |
| $\mathrm{sense}$ | `GlobalConstraint_sense` over $\mathcal{O}$ — which way the row binds — `<=`, `>=` or `==` |
| $\mathrm{K}$ | `GlobalConstraint_constant` over $\mathcal{O}$ — the constant the total is held against; what a variable cannot carry — an initial charge, a non-extendable build — is folded in here by data prep |
| $\mathrm{last}$ | `snapshot_is_last` over $\mathcal{T}$ — one at the horizon's last snapshot, zero elsewhere — data prep, how an expression reads a final level |
| $\mathrm{a}$ | `Generator_primary_energy_weight` over $\mathcal{O} \times \mathcal{G}$ — the constrained attribute per unit of energy at the bus — the carrier's `co2_emissions` over the generator's efficiency, data prep; a generator of an unweighted carrier has no row |
| $\mathrm{a}^{h}$ | `StorageUnit_primary_energy_weight` over $\mathcal{O} \times \mathcal{S}$ — the constrained attribute per unit of charge depleted — data prep; an unweighted unit has no row |
| $\mathrm{a}^{e}$ | `Store_primary_energy_weight` over $\mathcal{O} \times \mathcal{V}$ — the constrained attribute per unit of energy depleted — data prep; an unweighted store has no row |
| $\mathrm{b}$ | `Generator_operational_limit_weight` over $\mathcal{O} \times \mathcal{G}$ — one where the generator is in the row's set — data prep; one outside it has no row |
| $\mathrm{b}^{h}$ | `StorageUnit_operational_limit_weight` over $\mathcal{O} \times \mathcal{S}$ — one where the storage unit is in the row's set — data prep; one outside it has no row |
| $\mathrm{b}^{e}$ | `Store_operational_limit_weight` over $\mathcal{O} \times \mathcal{V}$ — one where the store is in the row's set — data prep; one outside it has no row |
| $\mathrm{len}$ | `Line_volume_weight` over $\mathcal{O} \times \mathcal{K}$ — the line's length where its carrier is in the row's set — data prep; a line outside it has no row |
| $\mathrm{len}^{f}$ | `Link_volume_weight` over $\mathcal{O} \times \mathcal{L}$ — the link's length where its carrier is in the row's set — data prep; a link outside it has no row |
| $\mathrm{cc}$ | `Line_expansion_cost_weight` over $\mathcal{O} \times \mathcal{K}$ — the line's capital cost where its carrier is in the row's set — data prep; a line outside it has no row |
| $\mathrm{cc}^{f}$ | `Link_expansion_cost_weight` over $\mathcal{O} \times \mathcal{L}$ — the link's capital cost where its carrier is in the row's set — data prep; a link outside it has no row |
| $\mathrm{m}$ | `Generator_tech_capacity_weight` over $\mathcal{O} \times \mathcal{G}$ — one where the generator is in the row's carrier-and-bus set — data prep; one outside it has no row |
| $\mathrm{m}^{f}$ | `Link_tech_capacity_weight` over $\mathcal{O} \times \mathcal{L}$ — one where the link is in the row's carrier-and-bus set — data prep; one outside it has no row |
| $\mathrm{m}^{l}$ | `Line_tech_capacity_weight` over $\mathcal{O} \times \mathcal{K}$ — one where the line is in the row's carrier-and-bus set — data prep; one outside it has no row |
| $\mathrm{m}^{h}$ | `StorageUnit_tech_capacity_weight` over $\mathcal{O} \times \mathcal{S}$ — one where the storage unit is in the row's carrier-and-bus set — data prep; one outside it has no row |
| $\mathrm{m}^{e}$ | `Store_tech_capacity_weight` over $\mathcal{O} \times \mathcal{V}$ — one where the store is in the row's carrier-and-bus set — data prep; one outside it has no row |

#### Variables

| Symbol | Meaning |
|---|---|
| $p$ | `Generator_p` over $\mathcal{T} \times \mathcal{G}$ — `Generator-p` — output of a generator in a snapshot |
| $f$ | `Link_p` over $\mathcal{T} \times \mathcal{L}$ — `Link-p` — PyPSA's `p0`, the flow measured at the `Link_bus0` end: a positive value withdraws there and injects at `Link_bus1` |
| $h^{+}$ | `StorageUnit_p_dispatch` over $\mathcal{T} \times \mathcal{S}$ — `StorageUnit-p_dispatch` — power delivered to the bus |
| $h^{-}$ | `StorageUnit_p_store` over $\mathcal{T} \times \mathcal{S}$ — `StorageUnit-p_store` — power drawn from the bus into charge |
| $\mathit{soc}$ | `StorageUnit_state_of_charge` over $\mathcal{T} \times \mathcal{S}$ — `StorageUnit-state_of_charge` — energy held at the end of a snapshot |
| $\mathit{spill}$ | `StorageUnit_spill` over $\mathcal{T} \times \mathcal{S}$ — `StorageUnit-spill` — inflow passed on unused. Zero where there is no inflow, so the balance keeps its row there; the bounds are PyPSA's, on the variable rather than as rows |
| $e$ | `Store_e` over $\mathcal{T} \times \mathcal{V}$ — `Store-e` — energy held at the end of a snapshot |
| $q$ | `Store_p` over $\mathcal{T} \times \mathcal{V}$ — `Store-p` — power delivered to the bus; charging is negative |
| $N$ | `Generator_n_mod` over $\mathcal{G}$ — `Generator-n_mod` — how many modules of an extendable modular build |
| $u$ | `Generator_status` over $\mathcal{T} \times \mathcal{G}$ — `Generator-status` — how much of a committable unit is on: an integer the rows below cap at one, or at the module count where the build is modular |
| $\mathit{up}$ | `Generator_start_up` over $\mathcal{T} \times \mathcal{G}$ — `Generator-start_up` — how much of a committable unit turns on this snapshot, capped as the status is |
| $\mathit{dn}$ | `Generator_shut_down` over $\mathcal{T} \times \mathcal{G}$ — `Generator-shut_down` — how much of a committable unit turns off this snapshot, capped as the status is |
| $s$ | `Line_s` over $\mathcal{T} \times \mathcal{K}$ — `Line-s` — PyPSA's `p0`, the flow measured at the `Line_bus0` end: a positive value withdraws there and injects at `Line_bus1`, lossless |
| $S$ | `Line_s_nom_ext` over $\mathcal{K}$ — `Line-s_nom` — nominal apparent power where it is a decision; the parameter of the same PyPSA name carries the fixed regime |
| $P$ | `Generator_p_nom_ext` over $\mathcal{G}$ — `Generator-p_nom` — nominal power where it is a decision; the parameter of the same PyPSA name carries the fixed regime |
| $F$ | `Link_p_nom_ext` over $\mathcal{L}$ — `Link-p_nom` — nominal power where it is a decision; the parameter of the same PyPSA name carries the fixed regime |
| $H$ | `StorageUnit_p_nom_ext` over $\mathcal{S}$ — `StorageUnit-p_nom` — nominal power where it is a decision; the parameter of the same PyPSA name carries the fixed regime |
| $E$ | `Store_e_nom_ext` over $\mathcal{V}$ — `Store-e_nom` — nominal capacity where it is a decision; the parameter of the same PyPSA name carries the fixed regime |

$t \ominus k$ denotes cyclic translation: index $t-k$ taken modulo the size of the dimension (`roll`). Plain $t-k$ (`shift`) has no wraparound — terms translated past the edge are simply absent.

$\mathrm{pos}(t)$ denotes where index $t$ sits along its dimension's own order — the order `shift` walks, not the order labels sort in — counted from $0$. The index itself stays the coordinate, so $t$ compares against labels and $\mathrm{pos}(t)$ against positions.

### Objective

```yaml
objective:
  sense: minimize
  description: operating cost, each snapshot weighted by the hours it stands for
  expression: >-
    sum(Generator_p * Generator_marginal_cost * snapshot_weightings_objective)
    + sum(Link_p * Link_marginal_cost * snapshot_weightings_objective)
    + sum(StorageUnit_p_dispatch * StorageUnit_marginal_cost * snapshot_weightings_objective)
    + sum(StorageUnit_state_of_charge * StorageUnit_marginal_cost_storage * snapshot_weightings_objective)
    + sum(StorageUnit_spill * StorageUnit_spill_cost * snapshot_weightings_objective)
    + sum(Store_p * Store_marginal_cost * snapshot_weightings_objective)
    + sum(Store_e * Store_marginal_cost_storage * snapshot_weightings_objective)
    + sum(Generator_p_nom_ext * Generator_capital_cost)
    + sum(Link_p_nom_ext * Link_capital_cost)
    + sum(StorageUnit_p_nom_ext * StorageUnit_capital_cost)
    + sum(Store_e_nom_ext * Store_capital_cost)
    + sum(Line_s_nom_ext * Line_capital_cost)
    + sum(Generator_status * Generator_stand_by_cost * snapshot_weightings_objective)
    + sum(Generator_start_up * Generator_start_up_cost)
    + sum(Generator_shut_down * Generator_shut_down_cost)
```

$$\min \sum_{t \in \mathcal{T},\enspace g \in \mathcal{G}} p_{t,g} \cdot \mathrm{c}_{t,g} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\enspace l \in \mathcal{L}} f_{t,l} \cdot \mathrm{c}^{f}_{t,l} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\enspace s \in \mathcal{S}} h^{+}_{t,s} \cdot \mathrm{c}^{h}_{t,s} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\enspace s \in \mathcal{S}} \mathit{soc}_{t,s} \cdot \mathrm{c}^{\mathrm{soc}}_{t,s} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\enspace s \in \mathcal{S}} \mathit{spill}_{t,s} \cdot \mathrm{c}^{\mathrm{spill}}_{t,s} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\enspace v \in \mathcal{V}} q_{t,v} \cdot \mathrm{c}^{q}_{t,v} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\enspace v \in \mathcal{V}} e_{t,v} \cdot \mathrm{c}^{e}_{t,v} \cdot \mathrm{w}_{t} + \sum_{g \in \mathcal{G}} P_{g} \cdot \mathrm{c}^{\mathrm{cap}}_{g} + \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{c}^{\mathrm{cap},f}_{l} + \sum_{s \in \mathcal{S}} H_{s} \cdot \mathrm{c}^{\mathrm{cap},h}_{s} + \sum_{v \in \mathcal{V}} E_{v} \cdot \mathrm{c}^{\mathrm{cap},e}_{v} + \sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{c}^{\mathrm{cap},s}_{k} + \sum_{t \in \mathcal{T},\enspace g \in \mathcal{G}} u_{t,g} \cdot \mathrm{c}^{\mathrm{on}}_{t,g} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\enspace g \in \mathcal{G}} \mathit{up}_{t,g} \cdot \mathrm{c}^{\mathrm{up}}_{g} + \sum_{t \in \mathcal{T},\enspace g \in \mathcal{G}} \mathit{dn}_{t,g} \cdot \mathrm{c}^{\mathrm{dn}}_{g}$$

### `Generator-fix-p-lower`

`Generator_fix_p_lower`

```yaml
Generator_fix_p_lower:
  description: "`Generator-fix-p-lower` — a fixed generator outputs at least its minimum"
  foreach: [snapshot, generator]
  where: not Generator_p_nom_extendable AND not Generator_committable
  expression: Generator_p >= Generator_p_min_pu * Generator_p_nom
```

$$p_{t,g} \ge \underline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \neg \mathrm{ext}_{g} \wedge \neg \mathrm{com}_{g}$$

### `Generator-fix-p-upper`

`Generator_fix_p_upper`

```yaml
Generator_fix_p_upper:
  description: "`Generator-fix-p-upper` — a fixed generator outputs at most what is available"
  foreach: [snapshot, generator]
  where: not Generator_p_nom_extendable AND not Generator_committable
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom
```

$$p_{t,g} \le \overline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \neg \mathrm{ext}_{g} \wedge \neg \mathrm{com}_{g}$$

### `Link-fix-p-lower`

`Link_fix_p_lower`

```yaml
Link_fix_p_lower:
  description: "`Link-fix-p-lower` — a fixed link carries at least its minimum, negative for the other way"
  foreach: [snapshot, link]
  where: not Link_p_nom_extendable
  expression: Link_p >= Link_p_min_pu * Link_p_nom
```

$$f_{t,l} \ge \underline{\mathrm{f}}_{t,l} \cdot \mathrm{f}^{\mathrm{nom}}_{l} \qquad \forall\thinspace t \in \mathcal{T},\enspace l \in \mathcal{L} \thinspace:\thinspace \neg \mathrm{ext}^{f}_{l}$$

### `Link-fix-p-upper`

`Link_fix_p_upper`

```yaml
Link_fix_p_upper:
  description: "`Link-fix-p-upper` — a fixed link carries at most its nominal power"
  foreach: [snapshot, link]
  where: not Link_p_nom_extendable
  expression: Link_p <= Link_p_max_pu * Link_p_nom
```

$$f_{t,l} \le \overline{\mathrm{f}}_{t,l} \cdot \mathrm{f}^{\mathrm{nom}}_{l} \qquad \forall\thinspace t \in \mathcal{T},\enspace l \in \mathcal{L} \thinspace:\thinspace \neg \mathrm{ext}^{f}_{l}$$

### `Generator-ext-p-lower`

`Generator_ext_p_lower`

```yaml
Generator_ext_p_lower:
  description: "`Generator-ext-p-lower` — an extendable generator outputs at least its minimum of the chosen build"
  foreach: [snapshot, generator]
  where: Generator_p_nom_extendable AND not Generator_committable
  expression: Generator_p >= Generator_p_min_pu * Generator_p_nom_ext
```

$$p_{t,g} \ge \underline{\mathrm{p}}_{t,g} \cdot P_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{ext}_{g} \wedge \neg \mathrm{com}_{g}$$

### `Generator-ext-p-upper`

`Generator_ext_p_upper`

```yaml
Generator_ext_p_upper:
  description: "`Generator-ext-p-upper` — an extendable generator outputs at most what is available of the chosen build"
  foreach: [snapshot, generator]
  where: Generator_p_nom_extendable AND not Generator_committable
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom_ext
```

$$p_{t,g} \le \overline{\mathrm{p}}_{t,g} \cdot P_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{ext}_{g} \wedge \neg \mathrm{com}_{g}$$

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

### `Generator-p_nom_set`

`Generator_p_nom_set`

```yaml
Generator_p_nom_set:
  description: "`Generator-p_nom_set` — the chosen build pinned, wherever a value is given"
  foreach: [generator]
  where: Generator_p_nom_extendable AND Generator_p_nom_set
  expression: Generator_p_nom_ext == Generator_p_nom_set
```

$$P_{g} = \mathrm{p}^{\mathrm{nom,set}}_{g} \qquad \forall\thinspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{nom,set}}_{g} \text{ is defined}$$

### `Generator-e_sum_min`

`Generator_e_sum_min`

```yaml
Generator_e_sum_min:
  description: "`Generator-e_sum_min` — energy over the horizon is at least its floor; a floor of minus infinity is no row"
  foreach: [generator]
  where: Generator_e_sum_min
  expression: sum(Generator_p * snapshot_weightings_generators, over=snapshot) >= Generator_e_sum_min
```

$$\sum_{t \in \mathcal{T}} p_{t,g} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \ge \underline{\mathrm{E}}_{g} \qquad \forall\thinspace g \in \mathcal{G} \thinspace:\thinspace \underline{\mathrm{E}}_{g} \text{ is defined}$$

### `Generator-e_sum_max`

`Generator_e_sum_max`

```yaml
Generator_e_sum_max:
  description: "`Generator-e_sum_max` — energy over the horizon is at most its budget; a budget of infinity is no row"
  foreach: [generator]
  where: Generator_e_sum_max
  expression: sum(Generator_p * snapshot_weightings_generators, over=snapshot) <= Generator_e_sum_max
```

$$\sum_{t \in \mathcal{T}} p_{t,g} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \le \overline{\mathrm{E}}_{g} \qquad \forall\thinspace g \in \mathcal{G} \thinspace:\thinspace \overline{\mathrm{E}}_{g} \text{ is defined}$$

### `Link-ext-p-lower`

`Link_ext_p_lower`

```yaml
Link_ext_p_lower:
  description: "`Link-ext-p-lower` — an extendable link carries at least its minimum of the chosen build, negative for the other way"
  foreach: [snapshot, link]
  where: Link_p_nom_extendable
  expression: Link_p >= Link_p_min_pu * Link_p_nom_ext
```

$$f_{t,l} \ge \underline{\mathrm{f}}_{t,l} \cdot F_{l} \qquad \forall\thinspace t \in \mathcal{T},\enspace l \in \mathcal{L} \thinspace:\thinspace \mathrm{ext}^{f}_{l}$$

### `Link-ext-p-upper`

`Link_ext_p_upper`

```yaml
Link_ext_p_upper:
  description: "`Link-ext-p-upper` — an extendable link carries at most the chosen build"
  foreach: [snapshot, link]
  where: Link_p_nom_extendable
  expression: Link_p <= Link_p_max_pu * Link_p_nom_ext
```

$$f_{t,l} \le \overline{\mathrm{f}}_{t,l} \cdot F_{l} \qquad \forall\thinspace t \in \mathcal{T},\enspace l \in \mathcal{L} \thinspace:\thinspace \mathrm{ext}^{f}_{l}$$

### `Link-ext-p_nom-lower`

`Link_ext_p_nom_lower`

```yaml
Link_ext_p_nom_lower:
  description: "`Link-ext-p_nom-lower` — the chosen build is at least its floor"
  foreach: [link]
  where: Link_p_nom_extendable
  expression: Link_p_nom_ext >= Link_p_nom_min
```

$$F_{l} \ge \underline{\mathrm{f}}^{\mathrm{nom}}_{l} \qquad \forall\thinspace l \in \mathcal{L} \thinspace:\thinspace \mathrm{ext}^{f}_{l}$$

### `Link-ext-p_nom-upper`

`Link_ext_p_nom_upper`

```yaml
Link_ext_p_nom_upper:
  description: "`Link-ext-p_nom-upper` — the chosen build is at most its cap; a cap of infinity is no row"
  foreach: [link]
  where: Link_p_nom_extendable AND Link_p_nom_max
  expression: Link_p_nom_ext <= Link_p_nom_max
```

$$F_{l} \le \overline{\mathrm{f}}^{\mathrm{nom}}_{l} \qquad \forall\thinspace l \in \mathcal{L} \thinspace:\thinspace \mathrm{ext}^{f}_{l} \wedge \overline{\mathrm{f}}^{\mathrm{nom}}_{l} \text{ is defined}$$

### `Link-p_nom_set`

`Link_p_nom_set`

```yaml
Link_p_nom_set:
  description: "`Link-p_nom_set` — the chosen build pinned, wherever a value is given"
  foreach: [link]
  where: Link_p_nom_extendable AND Link_p_nom_set
  expression: Link_p_nom_ext == Link_p_nom_set
```

$$F_{l} = \mathrm{f}^{\mathrm{nom,set}}_{l} \qquad \forall\thinspace l \in \mathcal{L} \thinspace:\thinspace \mathrm{ext}^{f}_{l} \wedge \mathrm{f}^{\mathrm{nom,set}}_{l} \text{ is defined}$$

### `StorageUnit-fix-p_dispatch-lower`

`StorageUnit_fix_p_dispatch_lower`

```yaml
StorageUnit_fix_p_dispatch_lower:
  description: "`StorageUnit-fix-p_dispatch-lower` — dispatch is non-negative"
  foreach: [snapshot, storage_unit]
  where: not StorageUnit_p_nom_extendable
  expression: StorageUnit_p_dispatch >= 0
```

$$h^{+}_{t,s} \ge 0 \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \neg \mathrm{ext}^{h}_{s}$$

### `StorageUnit-fix-p_dispatch-upper`

`StorageUnit_fix_p_dispatch_upper`

```yaml
StorageUnit_fix_p_dispatch_upper:
  description: "`StorageUnit-fix-p_dispatch-upper` — a fixed unit dispatches at most its nominal power"
  foreach: [snapshot, storage_unit]
  where: not StorageUnit_p_nom_extendable
  expression: StorageUnit_p_dispatch <= StorageUnit_p_max_pu * StorageUnit_p_nom
```

$$h^{+}_{t,s} \le \overline{\mathrm{h}}_{t,s} \cdot \mathrm{h}^{\mathrm{nom}}_{s} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \neg \mathrm{ext}^{h}_{s}$$

### `StorageUnit-fix-p_store-lower`

`StorageUnit_fix_p_store_lower`

```yaml
StorageUnit_fix_p_store_lower:
  description: "`StorageUnit-fix-p_store-lower` — storing is non-negative"
  foreach: [snapshot, storage_unit]
  where: not StorageUnit_p_nom_extendable
  expression: StorageUnit_p_store >= 0
```

$$h^{-}_{t,s} \ge 0 \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \neg \mathrm{ext}^{h}_{s}$$

### `StorageUnit-fix-p_store-upper`

`StorageUnit_fix_p_store_upper`

```yaml
StorageUnit_fix_p_store_upper:
  description: >-
    `StorageUnit-fix-p_store-upper` — a fixed unit stores at most its
    nominal power, the minimum-per-unit column carrying that cap negated
  foreach: [snapshot, storage_unit]
  where: not StorageUnit_p_nom_extendable
  expression: StorageUnit_p_store <= -StorageUnit_p_min_pu * StorageUnit_p_nom
```

$$h^{-}_{t,s} \le -\underline{\mathrm{h}}_{t,s} \cdot \mathrm{h}^{\mathrm{nom}}_{s} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \neg \mathrm{ext}^{h}_{s}$$

### `StorageUnit-fix-state_of_charge-lower`

`StorageUnit_fix_state_of_charge_lower`

```yaml
StorageUnit_fix_state_of_charge_lower:
  description: "`StorageUnit-fix-state_of_charge-lower` — charge is non-negative"
  foreach: [snapshot, storage_unit]
  where: not StorageUnit_p_nom_extendable
  expression: StorageUnit_state_of_charge >= 0
```

$$\mathit{soc}_{t,s} \ge 0 \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \neg \mathrm{ext}^{h}_{s}$$

### `StorageUnit-fix-state_of_charge-upper`

`StorageUnit_fix_state_of_charge_upper`

```yaml
StorageUnit_fix_state_of_charge_upper:
  description: "`StorageUnit-fix-state_of_charge-upper` — a fixed unit holds at most its hours at nominal power"
  foreach: [snapshot, storage_unit]
  where: not StorageUnit_p_nom_extendable
  expression: StorageUnit_state_of_charge <= StorageUnit_max_hours * StorageUnit_p_nom
```

$$\mathit{soc}_{t,s} \le \mathrm{T}^{h}_{s} \cdot \mathrm{h}^{\mathrm{nom}}_{s} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \neg \mathrm{ext}^{h}_{s}$$

### `Generator-com-p-lower`

`Generator_com_p_lower`

```yaml
Generator_com_p_lower:
  description: "`Generator-com-p-lower` — a committed unit outputs at least its minimum; off, at least nothing"
  foreach: [snapshot, generator]
  where: Generator_committable AND not Generator_p_nom_extendable
  expression: Generator_p >= Generator_p_min_pu * Generator_p_nom * Generator_status
```

$$p_{t,g} \ge \underline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot u_{t,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \neg \mathrm{ext}_{g}$$

### `Generator-com-p-upper`

`Generator_com_p_upper`

```yaml
Generator_com_p_upper:
  description: "`Generator-com-p-upper` — a committed unit outputs at most what is available; off, at most nothing"
  foreach: [snapshot, generator]
  where: Generator_committable AND not Generator_p_nom_extendable
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom * Generator_status
```

$$p_{t,g} \le \overline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot u_{t,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \neg \mathrm{ext}_{g}$$

### `Generator-com-transition-start-up`

`Generator_com_transition_start_up`

```yaml
Generator_com_transition_start_up:
  description: >-
    `Generator-com-transition-start-up` — turning on is a start. The
    translated term vacates the first snapshot; the initial block below
    compares it against the given status instead
  foreach: [snapshot, generator]
  where: Generator_committable
  expression: Generator_start_up >= Generator_status - shift(Generator_status, over=snapshot, offset=1)
```

$$\mathit{up}_{t,g} \ge u_{t,g} - u_{t - 1,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g}$$

### `Generator-com-transition-start-up`

`Generator_com_transition_start_up_initial`

```yaml
Generator_com_transition_start_up_initial:
  description: "`Generator-com-transition-start-up` — the first snapshot turns on against the status the unit brought in"
  foreach: [snapshot, generator]
  where: Generator_committable AND position(snapshot) == 0
  expression: Generator_start_up >= Generator_status - Generator_status_initial
```

$$\mathit{up}_{t,g} \ge u_{t,g} - \mathrm{u}^{0}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{pos}(t) = 0$$

### `Generator-com-transition-shut-down`

`Generator_com_transition_shut_down`

```yaml
Generator_com_transition_shut_down:
  description: "`Generator-com-transition-shut-down` — turning off is a stop; the first snapshot is the initial block's"
  foreach: [snapshot, generator]
  where: Generator_committable
  expression: Generator_shut_down >= shift(Generator_status, over=snapshot, offset=1) - Generator_status
```

$$\mathit{dn}_{t,g} \ge u_{t - 1,g} - u_{t,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g}$$

### `Generator-com-transition-shut-down`

`Generator_com_transition_shut_down_initial`

```yaml
Generator_com_transition_shut_down_initial:
  description: "`Generator-com-transition-shut-down` — the first snapshot turns off against the status the unit brought in"
  foreach: [snapshot, generator]
  where: Generator_committable AND position(snapshot) == 0
  expression: Generator_shut_down >= Generator_status_initial - Generator_status
```

$$\mathit{dn}_{t,g} \ge \mathrm{u}^{0}_{g} - u_{t,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{pos}(t) = 0$$

### `Generator-com-up-time`

`Generator_com_up_time`

```yaml
Generator_com_up_time:
  description: >-
    `Generator-com-up-time` — a unit started within its own minimum up time
    is still on. The first snapshot's share of the window is the brought-in
    up time's, which the must-stay-up mask carries
  foreach: [snapshot, generator]
  where: Generator_committable AND Generator_min_up_time > 0 AND position(snapshot) > 0
  expression: sum_back(Generator_start_up, over=snapshot, within=Generator_min_up_time) <= Generator_status
```

$$\sum_{t' \in \mathcal{T} \thinspace:\thinspace 0 \le t - t' < \mathrm{UT}} \mathit{up}_{t',g} \le u_{t,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{UT}_{g} > 0 \wedge \mathrm{pos}(t) > 0$$

### `Generator-com-down-time`

`Generator_com_down_time`

```yaml
Generator_com_down_time:
  description: "`Generator-com-down-time` — a unit stopped within its own minimum down time is still off"
  foreach: [snapshot, generator]
  where: Generator_committable AND Generator_min_down_time > 0 AND position(snapshot) > 0
  expression: sum_back(Generator_shut_down, over=snapshot, within=Generator_min_down_time) <= 1 - Generator_status
```

$$\sum_{t' \in \mathcal{T} \thinspace:\thinspace 0 \le t - t' < \mathrm{DT}} \mathit{dn}_{t',g} \le 1 - u_{t,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{DT}_{g} > 0 \wedge \mathrm{pos}(t) > 0$$

### `Generator-com-status-min_up_time_must_stay_up`

`Generator_com_status_must_stay_up`

```yaml
Generator_com_status_must_stay_up:
  description: "`Generator-com-status-min_up_time_must_stay_up` — a unit still serving the up time it brought in stays on"
  foreach: [snapshot, generator]
  where: Generator_committable AND Generator_must_stay_up
  expression: Generator_status == 1
```

$$u_{t,g} = 1 \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{hold}_{t,g}$$

### `Generator-p-ramp_limit_up`

`Generator_p_ramp_limit_up_com`

```yaml
Generator_p_ramp_limit_up_com:
  description: >-
    `Generator-p-ramp_limit_up` — a committed unit raises output no faster
    than its limit while it was already on, and no further than its
    start-up ramp in the snapshot it turns on
  foreach: [snapshot, generator]
  where: Generator_committable AND not Generator_p_nom_extendable AND Generator_ramp_limit_up
  expression: >-
    Generator_p - shift(Generator_p, over=snapshot, offset=1) <=
    Generator_ramp_limit_up * Generator_p_nom * shift(Generator_status, over=snapshot, offset=1)
    + Generator_ramp_limit_start_up * Generator_p_nom
    * (Generator_status - shift(Generator_status, over=snapshot, offset=1))
```

$$p_{t,g} - p_{t - 1,g} \le \mathrm{ru}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot u_{t - 1,g} + \mathrm{ru}^{\mathrm{up}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot \left( u_{t,g} - u_{t - 1,g} \right) \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \neg \mathrm{ext}_{g} \wedge \mathrm{ru}_{g} \text{ is defined}$$

### `Generator-p-ramp_limit_up`

`Generator_p_ramp_limit_up_com_initial`

```yaml
Generator_p_ramp_limit_up_com_initial:
  description: >-
    `Generator-p-ramp_limit_up` — a unit that was off ramps its first
    snapshot from an output of nothing; one already on brought an unknown
    output, so it carries no row
  foreach: [snapshot, generator]
  where: >-
    Generator_committable AND not Generator_p_nom_extendable
    AND Generator_ramp_limit_up AND position(snapshot) == 0 AND Generator_status_initial == 0
  expression: >-
    Generator_p <=
    Generator_ramp_limit_up * Generator_p_nom * Generator_status_initial
    + Generator_ramp_limit_start_up * Generator_p_nom * (Generator_status - Generator_status_initial)
```

$$p_{t,g} \le \mathrm{ru}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot \mathrm{u}^{0}_{g} + \mathrm{ru}^{\mathrm{up}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot \left( u_{t,g} - \mathrm{u}^{0}_{g} \right) \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \neg \mathrm{ext}_{g} \wedge \mathrm{ru}_{g} \text{ is defined} \wedge \mathrm{pos}(t) = 0 \wedge \mathrm{u}^{0}_{g} = 0$$

### `Generator-p-ramp_limit_down`

`Generator_p_ramp_limit_down_com`

```yaml
Generator_p_ramp_limit_down_com:
  description: >-
    `Generator-p-ramp_limit_down` — a committed unit lowers output no
    faster than its limit while it stays on, and no further than its
    shut-down ramp in the snapshot it turns off
  foreach: [snapshot, generator]
  where: Generator_committable AND not Generator_p_nom_extendable AND Generator_ramp_limit_down
  expression: >-
    shift(Generator_p, over=snapshot, offset=1) - Generator_p <=
    Generator_ramp_limit_down * Generator_p_nom * Generator_status
    + Generator_ramp_limit_shut_down * Generator_p_nom
    * (shift(Generator_status, over=snapshot, offset=1) - Generator_status)
```

$$p_{t - 1,g} - p_{t,g} \le \mathrm{rd}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot u_{t,g} + \mathrm{rd}^{\mathrm{dn}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot \left( u_{t - 1,g} - u_{t,g} \right) \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \neg \mathrm{ext}_{g} \wedge \mathrm{rd}_{g} \text{ is defined}$$

### `Generator-p-ramp_limit_down`

`Generator_p_ramp_limit_down_com_initial`

```yaml
Generator_p_ramp_limit_down_com_initial:
  description: >-
    `Generator-p-ramp_limit_down` — a unit that was off ramps its first
    snapshot down from an output of nothing; one already on carries no row
  foreach: [snapshot, generator]
  where: >-
    Generator_committable AND not Generator_p_nom_extendable
    AND Generator_ramp_limit_down AND position(snapshot) == 0 AND Generator_status_initial == 0
  expression: >-
    -Generator_p <=
    Generator_ramp_limit_down * Generator_p_nom * Generator_status
    + Generator_ramp_limit_shut_down * Generator_p_nom * (Generator_status_initial - Generator_status)
```

$$-p_{t,g} \le \mathrm{rd}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot u_{t,g} + \mathrm{rd}^{\mathrm{dn}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot \left( \mathrm{u}^{0}_{g} - u_{t,g} \right) \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \neg \mathrm{ext}_{g} \wedge \mathrm{rd}_{g} \text{ is defined} \wedge \mathrm{pos}(t) = 0 \wedge \mathrm{u}^{0}_{g} = 0$$

### `Generator-p-ramp_limit_up-run-bigM`

`Generator_p_ramp_limit_up_run_big_m`

```yaml
Generator_p_ramp_limit_up_run_big_m:
  description: >-
    `Generator-p-ramp_limit_up-run-bigM` — a committed extendable unit
    raises output no faster than its limit of the chosen build; the big M
    releases the row in the snapshot it turns on
  foreach: [snapshot, generator]
  where: Generator_committable AND Generator_p_nom_extendable AND Generator_ramp_limit_up
  expression: >-
    Generator_p - shift(Generator_p, over=snapshot, offset=1) <=
    Generator_ramp_limit_up * Generator_p_nom_ext
    + Generator_big_m - Generator_big_m * shift(Generator_status, over=snapshot, offset=1)
```

$$p_{t,g} - p_{t - 1,g} \le \mathrm{ru}_{g} \cdot P_{g} + \mathrm{M}_{g} - \mathrm{M}_{g} \cdot u_{t - 1,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \mathrm{ru}_{g} \text{ is defined}$$

### `Generator-p-ramp_limit_up-run-bigM`

`Generator_p_ramp_limit_up_run_big_m_initial`

```yaml
Generator_p_ramp_limit_up_run_big_m_initial:
  description: "`Generator-p-ramp_limit_up-run-bigM` — a unit that was off ramps its first snapshot from nothing; one already on carries no row"
  foreach: [snapshot, generator]
  where: >-
    Generator_committable AND Generator_p_nom_extendable
    AND Generator_ramp_limit_up AND position(snapshot) == 0 AND Generator_status_initial == 0
  expression: >-
    Generator_p <=
    Generator_ramp_limit_up * Generator_p_nom_ext
    + Generator_big_m - Generator_big_m * Generator_status_initial
```

$$p_{t,g} \le \mathrm{ru}_{g} \cdot P_{g} + \mathrm{M}_{g} - \mathrm{M}_{g} \cdot \mathrm{u}^{0}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \mathrm{ru}_{g} \text{ is defined} \wedge \mathrm{pos}(t) = 0 \wedge \mathrm{u}^{0}_{g} = 0$$

### `Generator-p-ramp_limit_up-start-bigM`

`Generator_p_ramp_limit_up_start_big_m`

```yaml
Generator_p_ramp_limit_up_start_big_m:
  description: >-
    `Generator-p-ramp_limit_up-start-bigM` — in the snapshot it turns on, a
    committed extendable unit ramps no further than its start-up ramp of
    the chosen build; the big M releases the row everywhere else
  foreach: [snapshot, generator]
  where: Generator_committable AND Generator_p_nom_extendable AND Generator_ramp_limit_up
  expression: >-
    Generator_p - shift(Generator_p, over=snapshot, offset=1) <=
    Generator_ramp_limit_start_up * Generator_p_nom_ext
    + Generator_big_m - Generator_big_m * Generator_start_up
```

$$p_{t,g} - p_{t - 1,g} \le \mathrm{ru}^{\mathrm{up}}_{g} \cdot P_{g} + \mathrm{M}_{g} - \mathrm{M}_{g} \cdot \mathit{up}_{t,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \mathrm{ru}_{g} \text{ is defined}$$

### `Generator-p-ramp_limit_up-start-bigM`

`Generator_p_ramp_limit_up_start_big_m_initial`

```yaml
Generator_p_ramp_limit_up_start_big_m_initial:
  description: "`Generator-p-ramp_limit_up-start-bigM` — a unit that was off ramps its first snapshot from nothing; one already on carries no row"
  foreach: [snapshot, generator]
  where: >-
    Generator_committable AND Generator_p_nom_extendable
    AND Generator_ramp_limit_up AND position(snapshot) == 0 AND Generator_status_initial == 0
  expression: >-
    Generator_p <=
    Generator_ramp_limit_start_up * Generator_p_nom_ext
    + Generator_big_m - Generator_big_m * Generator_start_up
```

$$p_{t,g} \le \mathrm{ru}^{\mathrm{up}}_{g} \cdot P_{g} + \mathrm{M}_{g} - \mathrm{M}_{g} \cdot \mathit{up}_{t,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \mathrm{ru}_{g} \text{ is defined} \wedge \mathrm{pos}(t) = 0 \wedge \mathrm{u}^{0}_{g} = 0$$

### `Generator-p-ramp_limit_down-run-bigM`

`Generator_p_ramp_limit_down_run_big_m`

```yaml
Generator_p_ramp_limit_down_run_big_m:
  description: >-
    `Generator-p-ramp_limit_down-run-bigM` — a committed extendable unit
    lowers output no faster than its limit of the chosen build; the big M
    releases the row in the snapshot it turns off
  foreach: [snapshot, generator]
  where: Generator_committable AND Generator_p_nom_extendable AND Generator_ramp_limit_down
  expression: >-
    shift(Generator_p, over=snapshot, offset=1) - Generator_p <=
    Generator_ramp_limit_down * Generator_p_nom_ext
    + Generator_big_m - Generator_big_m * Generator_status
```

$$p_{t - 1,g} - p_{t,g} \le \mathrm{rd}_{g} \cdot P_{g} + \mathrm{M}_{g} - \mathrm{M}_{g} \cdot u_{t,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \mathrm{rd}_{g} \text{ is defined}$$

### `Generator-p-ramp_limit_down-run-bigM`

`Generator_p_ramp_limit_down_run_big_m_initial`

```yaml
Generator_p_ramp_limit_down_run_big_m_initial:
  description: "`Generator-p-ramp_limit_down-run-bigM` — a unit that was off ramps its first snapshot down from nothing; one already on carries no row"
  foreach: [snapshot, generator]
  where: >-
    Generator_committable AND Generator_p_nom_extendable
    AND Generator_ramp_limit_down AND position(snapshot) == 0 AND Generator_status_initial == 0
  expression: >-
    -Generator_p <=
    Generator_ramp_limit_down * Generator_p_nom_ext
    + Generator_big_m - Generator_big_m * Generator_status
```

$$-p_{t,g} \le \mathrm{rd}_{g} \cdot P_{g} + \mathrm{M}_{g} - \mathrm{M}_{g} \cdot u_{t,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \mathrm{rd}_{g} \text{ is defined} \wedge \mathrm{pos}(t) = 0 \wedge \mathrm{u}^{0}_{g} = 0$$

### `Generator-p-ramp_limit_down-shut-bigM`

`Generator_p_ramp_limit_down_shut_big_m`

```yaml
Generator_p_ramp_limit_down_shut_big_m:
  description: >-
    `Generator-p-ramp_limit_down-shut-bigM` — in the snapshot it turns off,
    a committed extendable unit ramps no further than its shut-down ramp of
    the chosen build; the big M releases the row everywhere else
  foreach: [snapshot, generator]
  where: Generator_committable AND Generator_p_nom_extendable AND Generator_ramp_limit_down
  expression: >-
    shift(Generator_p, over=snapshot, offset=1) - Generator_p <=
    Generator_ramp_limit_shut_down * Generator_p_nom_ext
    + Generator_big_m - Generator_big_m * Generator_shut_down
```

$$p_{t - 1,g} - p_{t,g} \le \mathrm{rd}^{\mathrm{dn}}_{g} \cdot P_{g} + \mathrm{M}_{g} - \mathrm{M}_{g} \cdot \mathit{dn}_{t,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \mathrm{rd}_{g} \text{ is defined}$$

### `Generator-p-ramp_limit_down-shut-bigM`

`Generator_p_ramp_limit_down_shut_big_m_initial`

```yaml
Generator_p_ramp_limit_down_shut_big_m_initial:
  description: "`Generator-p-ramp_limit_down-shut-bigM` — a unit that was off ramps its first snapshot down from nothing; one already on carries no row"
  foreach: [snapshot, generator]
  where: >-
    Generator_committable AND Generator_p_nom_extendable
    AND Generator_ramp_limit_down AND position(snapshot) == 0 AND Generator_status_initial == 0
  expression: >-
    -Generator_p <=
    Generator_ramp_limit_shut_down * Generator_p_nom_ext
    + Generator_big_m - Generator_big_m * Generator_shut_down
```

$$-p_{t,g} \le \mathrm{rd}^{\mathrm{dn}}_{g} \cdot P_{g} + \mathrm{M}_{g} - \mathrm{M}_{g} \cdot \mathit{dn}_{t,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \mathrm{rd}_{g} \text{ is defined} \wedge \mathrm{pos}(t) = 0 \wedge \mathrm{u}^{0}_{g} = 0$$

### `Generator-p_nom_modularity`

`Generator_p_nom_modularity`

```yaml
Generator_p_nom_modularity:
  description: "`Generator-p_nom_modularity` — the chosen build is a whole number of modules"
  foreach: [generator]
  where: Generator_p_nom_extendable AND Generator_p_nom_mod > 0
  expression: Generator_p_nom_ext == Generator_p_nom_mod * Generator_n_mod
```

$$P_{g} = \mathrm{p}^{\mathrm{mod}}_{g} \cdot N_{g} \qquad \forall\thinspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0$$

### `Generator-com-ext-p-upper-cap`

`Generator_com_ext_p_upper_cap`

```yaml
Generator_com_ext_p_upper_cap:
  description: >-
    `Generator-com-ext-p-upper-cap` — a committed extendable unit outputs
    at most what is available of the chosen build, whatever its status
  foreach: [snapshot, generator]
  where: Generator_committable AND Generator_p_nom_extendable AND NOT (Generator_p_nom_mod > 0)
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom_ext
```

$$p_{t,g} \le \overline{\mathrm{p}}_{t,g} \cdot P_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right)$$

### `Generator-com-ext-p-upper-bigM`

`Generator_com_ext_p_upper_big_m`

```yaml
Generator_com_ext_p_upper_big_m:
  description: "`Generator-com-ext-p-upper-bigM` — off, a unit outputs nothing; on, the big M is no bound"
  foreach: [snapshot, generator]
  where: Generator_committable AND Generator_p_nom_extendable AND NOT (Generator_p_nom_mod > 0)
  expression: Generator_p <= Generator_big_m * Generator_status
```

$$p_{t,g} \le \mathrm{M}_{g} \cdot u_{t,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right)$$

### `Generator-com-ext-p-lower`

`Generator_com_ext_p_lower`

```yaml
Generator_com_ext_p_lower:
  description: >-
    `Generator-com-ext-p-lower` — a committed extendable unit outputs at
    least its minimum of the chosen build; off, the big M releases the row
  foreach: [snapshot, generator]
  where: Generator_committable AND Generator_p_nom_extendable AND NOT (Generator_p_nom_mod > 0)
  expression: >-
    Generator_p >=
    Generator_p_min_pu * Generator_p_nom_ext
    + Generator_big_m * Generator_status - Generator_big_m
```

$$p_{t,g} \ge \underline{\mathrm{p}}_{t,g} \cdot P_{g} + \mathrm{M}_{g} \cdot u_{t,g} - \mathrm{M}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right)$$

### `Generator-com-ext-p-lower-nonneg`

`Generator_com_ext_p_lower_nonneg`

```yaml
Generator_com_ext_p_lower_nonneg:
  description: >-
    `Generator-com-ext-p-lower-nonneg` — where no minimum-per-unit is
    negative, output is also plainly non-negative, a row the big-M lower
    cannot assert while the unit is off
  foreach: [snapshot, generator]
  where: >-
    Generator_committable AND Generator_p_nom_extendable
    AND Generator_p_min_pu_nonneg AND NOT (Generator_p_nom_mod > 0)
  expression: Generator_p >= 0
```

$$p_{t,g} \ge 0 \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \mathrm{nonneg}_{g} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right)$$

### `Generator-com-mod-p-lower`

`Generator_com_mod_p_lower`

```yaml
Generator_com_mod_p_lower:
  description: "`Generator-com-mod-p-lower` — a committed modular unit outputs at least its minimum of one module"
  foreach: [snapshot, generator]
  where: Generator_committable AND Generator_p_nom_extendable AND Generator_p_nom_mod > 0
  expression: Generator_p >= Generator_p_min_pu * Generator_p_nom_mod * Generator_status
```

$$p_{t,g} \ge \underline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{mod}}_{g} \cdot u_{t,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0$$

### `Generator-com-mod-p-upper`

`Generator_com_mod_p_upper`

```yaml
Generator_com_mod_p_upper:
  description: "`Generator-com-mod-p-upper` — a committed modular unit outputs at most one module's share"
  foreach: [snapshot, generator]
  where: Generator_committable AND Generator_p_nom_extendable AND Generator_p_nom_mod > 0
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom_mod * Generator_status
```

$$p_{t,g} \le \overline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{mod}}_{g} \cdot u_{t,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0$$

### `Generator-status-p-fixed-upper`

`Generator_status_p_fixed_upper`

```yaml
Generator_status_p_fixed_upper:
  description: "`Generator-status-p-fixed-upper` — a status is at most one, an explicit row as PyPSA writes it"
  foreach: [snapshot, generator]
  where: Generator_committable AND NOT (Generator_p_nom_extendable AND Generator_p_nom_mod > 0)
  expression: Generator_status <= 1
```

$$u_{t,g} \le 1 \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \neg \left( \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right)$$

### `Generator-start_up-p-fixed-upper`

`Generator_start_up_p_fixed_upper`

```yaml
Generator_start_up_p_fixed_upper:
  description: "`Generator-start_up-p-fixed-upper` — a start is at most one, an explicit row as PyPSA writes it"
  foreach: [snapshot, generator]
  where: Generator_committable AND NOT (Generator_p_nom_extendable AND Generator_p_nom_mod > 0)
  expression: Generator_start_up <= 1
```

$$\mathit{up}_{t,g} \le 1 \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \neg \left( \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right)$$

### `Generator-shut_down-p-fixed-upper`

`Generator_shut_down_p_fixed_upper`

```yaml
Generator_shut_down_p_fixed_upper:
  description: "`Generator-shut_down-p-fixed-upper` — a stop is at most one, an explicit row as PyPSA writes it"
  foreach: [snapshot, generator]
  where: Generator_committable AND NOT (Generator_p_nom_extendable AND Generator_p_nom_mod > 0)
  expression: Generator_shut_down <= 1
```

$$\mathit{dn}_{t,g} \le 1 \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \neg \left( \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right)$$

### `Generator-status-p_nom-variable-upper`

`Generator_status_p_nom_variable_upper`

```yaml
Generator_status_p_nom_variable_upper:
  description: "`Generator-status-p_nom-variable-upper` — a modular unit is on only where a module is built"
  foreach: [snapshot, generator]
  where: Generator_committable AND Generator_p_nom_extendable AND Generator_p_nom_mod > 0
  expression: Generator_status <= Generator_n_mod
```

$$u_{t,g} \le N_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0$$

### `Generator-start_up-p_nom-variable-upper`

`Generator_start_up_p_nom_variable_upper`

```yaml
Generator_start_up_p_nom_variable_upper:
  description: "`Generator-start_up-p_nom-variable-upper` — a modular unit starts only where a module is built"
  foreach: [snapshot, generator]
  where: Generator_committable AND Generator_p_nom_extendable AND Generator_p_nom_mod > 0
  expression: Generator_start_up <= Generator_n_mod
```

$$\mathit{up}_{t,g} \le N_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0$$

### `Generator-shut_down-p_nom-variable-upper`

`Generator_shut_down_p_nom_variable_upper`

```yaml
Generator_shut_down_p_nom_variable_upper:
  description: "`Generator-shut_down-p_nom-variable-upper` — a modular unit stops only where a module is built"
  foreach: [snapshot, generator]
  where: Generator_committable AND Generator_p_nom_extendable AND Generator_p_nom_mod > 0
  expression: Generator_shut_down <= Generator_n_mod
```

$$\mathit{dn}_{t,g} \le N_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0$$

### `Line-fix-s-lower`

`Line_fix_s_lower`

```yaml
Line_fix_s_lower:
  description: "`Line-fix-s-lower` — a fixed line carries at least the negative of its rating"
  foreach: [snapshot, line]
  where: not Line_s_nom_extendable
  expression: Line_s >= -Line_s_max_pu * Line_s_nom
```

$$s_{t,k} \ge -\overline{\mathrm{s}}_{t,k} \cdot \mathrm{s}^{\mathrm{nom}}_{k} \qquad \forall\thinspace t \in \mathcal{T},\enspace k \in \mathcal{K} \thinspace:\thinspace \neg \mathrm{ext}^{s}_{k}$$

### `Line-fix-s-upper`

`Line_fix_s_upper`

```yaml
Line_fix_s_upper:
  description: "`Line-fix-s-upper` — a fixed line carries at most its rating"
  foreach: [snapshot, line]
  where: not Line_s_nom_extendable
  expression: Line_s <= Line_s_max_pu * Line_s_nom
```

$$s_{t,k} \le \overline{\mathrm{s}}_{t,k} \cdot \mathrm{s}^{\mathrm{nom}}_{k} \qquad \forall\thinspace t \in \mathcal{T},\enspace k \in \mathcal{K} \thinspace:\thinspace \neg \mathrm{ext}^{s}_{k}$$

### `Line-ext-s-lower`

`Line_ext_s_lower`

```yaml
Line_ext_s_lower:
  description: "`Line-ext-s-lower` — an extendable line carries at least the negative of its rating of the chosen build"
  foreach: [snapshot, line]
  where: Line_s_nom_extendable
  expression: Line_s >= -Line_s_max_pu * Line_s_nom_ext
```

$$s_{t,k} \ge -\overline{\mathrm{s}}_{t,k} \cdot S_{k} \qquad \forall\thinspace t \in \mathcal{T},\enspace k \in \mathcal{K} \thinspace:\thinspace \mathrm{ext}^{s}_{k}$$

### `Line-ext-s-upper`

`Line_ext_s_upper`

```yaml
Line_ext_s_upper:
  description: "`Line-ext-s-upper` — an extendable line carries at most its rating of the chosen build"
  foreach: [snapshot, line]
  where: Line_s_nom_extendable
  expression: Line_s <= Line_s_max_pu * Line_s_nom_ext
```

$$s_{t,k} \le \overline{\mathrm{s}}_{t,k} \cdot S_{k} \qquad \forall\thinspace t \in \mathcal{T},\enspace k \in \mathcal{K} \thinspace:\thinspace \mathrm{ext}^{s}_{k}$$

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

### `Line-s_nom_set`

`Line_s_nom_set`

```yaml
Line_s_nom_set:
  description: "`Line-s_nom_set` — the chosen build pinned, wherever a value is given"
  foreach: [line]
  where: Line_s_nom_extendable AND Line_s_nom_set
  expression: Line_s_nom_ext == Line_s_nom_set
```

$$S_{k} = \mathrm{s}^{\mathrm{nom,set}}_{k} \qquad \forall\thinspace k \in \mathcal{K} \thinspace:\thinspace \mathrm{ext}^{s}_{k} \wedge \mathrm{s}^{\mathrm{nom,set}}_{k} \text{ is defined}$$

### `Line-s_set`

`Line_s_set`

```yaml
Line_s_set:
  description: "`Line-s_set` — flow pinned to the given schedule, wherever one is given"
  foreach: [snapshot, line]
  where: Line_s_set
  expression: Line_s == Line_s_set
```

$$s_{t,k} = \mathrm{s}^{\mathrm{set}}_{t,k} \qquad \forall\thinspace t \in \mathcal{T},\enspace k \in \mathcal{K} \thinspace:\thinspace \mathrm{s}^{\mathrm{set}}_{t,k} \text{ is defined}$$

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

### `Generator-p-ramp_limit_up`

`Generator_p_ramp_limit_up_fix`

```yaml
Generator_p_ramp_limit_up_fix:
  description: >-
    `Generator-p-ramp_limit_up` — a fixed generator raises output no faster
    than its limit. The translated term vacates the first snapshot, where a
    plain optimize builds no row either
  foreach: [snapshot, generator]
  where: not Generator_p_nom_extendable AND not Generator_committable AND Generator_ramp_limit_up
  expression: Generator_p - shift(Generator_p, over=snapshot, offset=1) <= Generator_ramp_limit_up * Generator_p_nom
```

$$p_{t,g} - p_{t - 1,g} \le \mathrm{ru}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \neg \mathrm{ext}_{g} \wedge \neg \mathrm{com}_{g} \wedge \mathrm{ru}_{g} \text{ is defined}$$

### `Generator-p-ramp_limit_down`

`Generator_p_ramp_limit_down_fix`

```yaml
Generator_p_ramp_limit_down_fix:
  description: "`Generator-p-ramp_limit_down` — a fixed generator lowers output no faster than its limit"
  foreach: [snapshot, generator]
  where: not Generator_p_nom_extendable AND not Generator_committable AND Generator_ramp_limit_down
  expression: shift(Generator_p, over=snapshot, offset=1) - Generator_p <= Generator_ramp_limit_down * Generator_p_nom
```

$$p_{t - 1,g} - p_{t,g} \le \mathrm{rd}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \neg \mathrm{ext}_{g} \wedge \neg \mathrm{com}_{g} \wedge \mathrm{rd}_{g} \text{ is defined}$$

### `Generator-p-ramp_limit_up`

`Generator_p_ramp_limit_up_ext`

```yaml
Generator_p_ramp_limit_up_ext:
  description: "`Generator-p-ramp_limit_up` — an extendable generator raises output no faster than its limit of the chosen build"
  foreach: [snapshot, generator]
  where: Generator_p_nom_extendable AND not Generator_committable AND Generator_ramp_limit_up
  expression: Generator_p - shift(Generator_p, over=snapshot, offset=1) <= Generator_ramp_limit_up * Generator_p_nom_ext
```

$$p_{t,g} - p_{t - 1,g} \le \mathrm{ru}_{g} \cdot P_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{ext}_{g} \wedge \neg \mathrm{com}_{g} \wedge \mathrm{ru}_{g} \text{ is defined}$$

### `Generator-p-ramp_limit_down`

`Generator_p_ramp_limit_down_ext`

```yaml
Generator_p_ramp_limit_down_ext:
  description: "`Generator-p-ramp_limit_down` — an extendable generator lowers output no faster than its limit of the chosen build"
  foreach: [snapshot, generator]
  where: Generator_p_nom_extendable AND not Generator_committable AND Generator_ramp_limit_down
  expression: shift(Generator_p, over=snapshot, offset=1) - Generator_p <= Generator_ramp_limit_down * Generator_p_nom_ext
```

$$p_{t - 1,g} - p_{t,g} \le \mathrm{rd}_{g} \cdot P_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{ext}_{g} \wedge \neg \mathrm{com}_{g} \wedge \mathrm{rd}_{g} \text{ is defined}$$

### `Link-p-ramp_limit_up`

`Link_p_ramp_limit_up_fix`

```yaml
Link_p_ramp_limit_up_fix:
  description: "`Link-p-ramp_limit_up` — a fixed link raises flow no faster than its limit"
  foreach: [snapshot, link]
  where: not Link_p_nom_extendable AND Link_ramp_limit_up
  expression: Link_p - shift(Link_p, over=snapshot, offset=1) <= Link_ramp_limit_up * Link_p_nom
```

$$f_{t,l} - f_{t - 1,l} \le \mathrm{ru}^{f}_{l} \cdot \mathrm{f}^{\mathrm{nom}}_{l} \qquad \forall\thinspace t \in \mathcal{T},\enspace l \in \mathcal{L} \thinspace:\thinspace \neg \mathrm{ext}^{f}_{l} \wedge \mathrm{ru}^{f}_{l} \text{ is defined}$$

### `Link-p-ramp_limit_down`

`Link_p_ramp_limit_down_fix`

```yaml
Link_p_ramp_limit_down_fix:
  description: "`Link-p-ramp_limit_down` — a fixed link lowers flow no faster than its limit"
  foreach: [snapshot, link]
  where: not Link_p_nom_extendable AND Link_ramp_limit_down
  expression: shift(Link_p, over=snapshot, offset=1) - Link_p <= Link_ramp_limit_down * Link_p_nom
```

$$f_{t - 1,l} - f_{t,l} \le \mathrm{rd}^{f}_{l} \cdot \mathrm{f}^{\mathrm{nom}}_{l} \qquad \forall\thinspace t \in \mathcal{T},\enspace l \in \mathcal{L} \thinspace:\thinspace \neg \mathrm{ext}^{f}_{l} \wedge \mathrm{rd}^{f}_{l} \text{ is defined}$$

### `Link-p-ramp_limit_up`

`Link_p_ramp_limit_up_ext`

```yaml
Link_p_ramp_limit_up_ext:
  description: "`Link-p-ramp_limit_up` — an extendable link raises flow no faster than its limit of the chosen build"
  foreach: [snapshot, link]
  where: Link_p_nom_extendable AND Link_ramp_limit_up
  expression: Link_p - shift(Link_p, over=snapshot, offset=1) <= Link_ramp_limit_up * Link_p_nom_ext
```

$$f_{t,l} - f_{t - 1,l} \le \mathrm{ru}^{f}_{l} \cdot F_{l} \qquad \forall\thinspace t \in \mathcal{T},\enspace l \in \mathcal{L} \thinspace:\thinspace \mathrm{ext}^{f}_{l} \wedge \mathrm{ru}^{f}_{l} \text{ is defined}$$

### `Link-p-ramp_limit_down`

`Link_p_ramp_limit_down_ext`

```yaml
Link_p_ramp_limit_down_ext:
  description: "`Link-p-ramp_limit_down` — an extendable link lowers flow no faster than its limit of the chosen build"
  foreach: [snapshot, link]
  where: Link_p_nom_extendable AND Link_ramp_limit_down
  expression: shift(Link_p, over=snapshot, offset=1) - Link_p <= Link_ramp_limit_down * Link_p_nom_ext
```

$$f_{t - 1,l} - f_{t,l} \le \mathrm{rd}^{f}_{l} \cdot F_{l} \qquad \forall\thinspace t \in \mathcal{T},\enspace l \in \mathcal{L} \thinspace:\thinspace \mathrm{ext}^{f}_{l} \wedge \mathrm{rd}^{f}_{l} \text{ is defined}$$

### `StorageUnit-ext-p_dispatch-lower`

`StorageUnit_ext_p_dispatch_lower`

```yaml
StorageUnit_ext_p_dispatch_lower:
  description: "`StorageUnit-ext-p_dispatch-lower` — dispatch is non-negative"
  foreach: [snapshot, storage_unit]
  where: StorageUnit_p_nom_extendable
  expression: StorageUnit_p_dispatch >= 0
```

$$h^{+}_{t,s} \ge 0 \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \mathrm{ext}^{h}_{s}$$

### `StorageUnit-ext-p_dispatch-upper`

`StorageUnit_ext_p_dispatch_upper`

```yaml
StorageUnit_ext_p_dispatch_upper:
  description: "`StorageUnit-ext-p_dispatch-upper` — an extendable unit dispatches at most the chosen build"
  foreach: [snapshot, storage_unit]
  where: StorageUnit_p_nom_extendable
  expression: StorageUnit_p_dispatch <= StorageUnit_p_max_pu * StorageUnit_p_nom_ext
```

$$h^{+}_{t,s} \le \overline{\mathrm{h}}_{t,s} \cdot H_{s} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \mathrm{ext}^{h}_{s}$$

### `StorageUnit-ext-p_store-lower`

`StorageUnit_ext_p_store_lower`

```yaml
StorageUnit_ext_p_store_lower:
  description: "`StorageUnit-ext-p_store-lower` — storing is non-negative"
  foreach: [snapshot, storage_unit]
  where: StorageUnit_p_nom_extendable
  expression: StorageUnit_p_store >= 0
```

$$h^{-}_{t,s} \ge 0 \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \mathrm{ext}^{h}_{s}$$

### `StorageUnit-ext-p_store-upper`

`StorageUnit_ext_p_store_upper`

```yaml
StorageUnit_ext_p_store_upper:
  description: >-
    `StorageUnit-ext-p_store-upper` — an extendable unit stores at most the
    chosen build, the minimum-per-unit column carrying that cap negated
  foreach: [snapshot, storage_unit]
  where: StorageUnit_p_nom_extendable
  expression: StorageUnit_p_store <= -StorageUnit_p_min_pu * StorageUnit_p_nom_ext
```

$$h^{-}_{t,s} \le -\underline{\mathrm{h}}_{t,s} \cdot H_{s} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \mathrm{ext}^{h}_{s}$$

### `StorageUnit-ext-state_of_charge-lower`

`StorageUnit_ext_state_of_charge_lower`

```yaml
StorageUnit_ext_state_of_charge_lower:
  description: "`StorageUnit-ext-state_of_charge-lower` — charge is non-negative"
  foreach: [snapshot, storage_unit]
  where: StorageUnit_p_nom_extendable
  expression: StorageUnit_state_of_charge >= 0
```

$$\mathit{soc}_{t,s} \ge 0 \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \mathrm{ext}^{h}_{s}$$

### `StorageUnit-ext-state_of_charge-upper`

`StorageUnit_ext_state_of_charge_upper`

```yaml
StorageUnit_ext_state_of_charge_upper:
  description: "`StorageUnit-ext-state_of_charge-upper` — an extendable unit holds at most its hours at the chosen build"
  foreach: [snapshot, storage_unit]
  where: StorageUnit_p_nom_extendable
  expression: StorageUnit_state_of_charge <= StorageUnit_max_hours * StorageUnit_p_nom_ext
```

$$\mathit{soc}_{t,s} \le \mathrm{T}^{h}_{s} \cdot H_{s} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \mathrm{ext}^{h}_{s}$$

### `StorageUnit-ext-p_nom-lower`

`StorageUnit_ext_p_nom_lower`

```yaml
StorageUnit_ext_p_nom_lower:
  description: "`StorageUnit-ext-p_nom-lower` — the chosen build is at least its floor"
  foreach: [storage_unit]
  where: StorageUnit_p_nom_extendable
  expression: StorageUnit_p_nom_ext >= StorageUnit_p_nom_min
```

$$H_{s} \ge \underline{\mathrm{h}}^{\mathrm{nom}}_{s} \qquad \forall\thinspace s \in \mathcal{S} \thinspace:\thinspace \mathrm{ext}^{h}_{s}$$

### `StorageUnit-ext-p_nom-upper`

`StorageUnit_ext_p_nom_upper`

```yaml
StorageUnit_ext_p_nom_upper:
  description: "`StorageUnit-ext-p_nom-upper` — the chosen build is at most its cap; a cap of infinity is no row"
  foreach: [storage_unit]
  where: StorageUnit_p_nom_extendable AND StorageUnit_p_nom_max
  expression: StorageUnit_p_nom_ext <= StorageUnit_p_nom_max
```

$$H_{s} \le \overline{\mathrm{h}}^{\mathrm{nom}}_{s} \qquad \forall\thinspace s \in \mathcal{S} \thinspace:\thinspace \mathrm{ext}^{h}_{s} \wedge \overline{\mathrm{h}}^{\mathrm{nom}}_{s} \text{ is defined}$$

### `StorageUnit-p_nom_set`

`StorageUnit_p_nom_set`

```yaml
StorageUnit_p_nom_set:
  description: "`StorageUnit-p_nom_set` — the chosen build pinned, wherever a value is given"
  foreach: [storage_unit]
  where: StorageUnit_p_nom_extendable AND StorageUnit_p_nom_set
  expression: StorageUnit_p_nom_ext == StorageUnit_p_nom_set
```

$$H_{s} = \mathrm{h}^{\mathrm{nom,set}}_{s} \qquad \forall\thinspace s \in \mathcal{S} \thinspace:\thinspace \mathrm{ext}^{h}_{s} \wedge \mathrm{h}^{\mathrm{nom,set}}_{s} \text{ is defined}$$

### `StorageUnit-energy_balance`

`StorageUnit_energy_balance`

```yaml
StorageUnit_energy_balance:
  description: >-
    `StorageUnit-energy_balance` — charge carried over less standing loss,
    plus what is stored after its efficiency, less what dispatch draws down
    before its own, plus inflow not spilled. The translated term vacates the
    first snapshot, so this block builds every row but that one; the initial
    block below is the boundary
  foreach: [snapshot, storage_unit]
  where: not StorageUnit_cyclic_state_of_charge
  expression: >-
    StorageUnit_state_of_charge ==
    StorageUnit_retention * shift(StorageUnit_state_of_charge, over=snapshot, offset=1)
    + StorageUnit_efficiency_store * StorageUnit_p_store * snapshot_weightings_stores
    - StorageUnit_p_dispatch * snapshot_weightings_stores / StorageUnit_efficiency_dispatch
    + (StorageUnit_inflow - StorageUnit_spill) * snapshot_weightings_stores
```

$$\mathit{soc}_{t,s} = \rho_{t,s} \cdot \mathit{soc}_{t - 1,s} + \eta^{-}_{s} \cdot h^{-}_{t,s} \cdot \mathrm{w}^{\mathrm{sto}}_{t} - \frac{h^{+}_{t,s} \cdot \mathrm{w}^{\mathrm{sto}}_{t}}{\eta^{+}_{s}} + \left( \mathrm{inflow}_{t,s} - \mathit{spill}_{t,s} \right) \cdot \mathrm{w}^{\mathrm{sto}}_{t} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \neg \mathrm{cyc}_{s}$$

### `StorageUnit-energy_balance`

`StorageUnit_energy_balance_initial`

```yaml
StorageUnit_energy_balance_initial:
  description: "`StorageUnit-energy_balance` — the first snapshot opens on the given initial charge, which no standing loss has touched yet"
  foreach: [snapshot, storage_unit]
  where: not StorageUnit_cyclic_state_of_charge AND position(snapshot) == 0
  expression: >-
    StorageUnit_state_of_charge ==
    StorageUnit_state_of_charge_initial
    + StorageUnit_efficiency_store * StorageUnit_p_store * snapshot_weightings_stores
    - StorageUnit_p_dispatch * snapshot_weightings_stores / StorageUnit_efficiency_dispatch
    + (StorageUnit_inflow - StorageUnit_spill) * snapshot_weightings_stores
```

$$\mathit{soc}_{t,s} = \mathrm{soc}^{0}_{s} + \eta^{-}_{s} \cdot h^{-}_{t,s} \cdot \mathrm{w}^{\mathrm{sto}}_{t} - \frac{h^{+}_{t,s} \cdot \mathrm{w}^{\mathrm{sto}}_{t}}{\eta^{+}_{s}} + \left( \mathrm{inflow}_{t,s} - \mathit{spill}_{t,s} \right) \cdot \mathrm{w}^{\mathrm{sto}}_{t} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \neg \mathrm{cyc}_{s} \wedge \mathrm{pos}(t) = 0$$

### `StorageUnit-energy_balance`

`StorageUnit_energy_balance_cyclic`

```yaml
StorageUnit_energy_balance_cyclic:
  description: "`StorageUnit-energy_balance` — a cyclic unit's first snapshot carries over from its last"
  foreach: [snapshot, storage_unit]
  where: StorageUnit_cyclic_state_of_charge
  expression: >-
    StorageUnit_state_of_charge ==
    StorageUnit_retention * shift(StorageUnit_state_of_charge, over=snapshot, offset=1, edge='wrap')
    + StorageUnit_efficiency_store * StorageUnit_p_store * snapshot_weightings_stores
    - StorageUnit_p_dispatch * snapshot_weightings_stores / StorageUnit_efficiency_dispatch
    + (StorageUnit_inflow - StorageUnit_spill) * snapshot_weightings_stores
```

$$\mathit{soc}_{t,s} = \rho_{t,s} \cdot \mathit{soc}_{t \ominus 1,s} + \eta^{-}_{s} \cdot h^{-}_{t,s} \cdot \mathrm{w}^{\mathrm{sto}}_{t} - \frac{h^{+}_{t,s} \cdot \mathrm{w}^{\mathrm{sto}}_{t}}{\eta^{+}_{s}} + \left( \mathrm{inflow}_{t,s} - \mathit{spill}_{t,s} \right) \cdot \mathrm{w}^{\mathrm{sto}}_{t} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \mathrm{cyc}_{s}$$

### `Store-fix-e-lower`

`Store_fix_e_lower`

```yaml
Store_fix_e_lower:
  description: "`Store-fix-e-lower` — a fixed store holds at least its floor"
  foreach: [snapshot, store]
  where: not Store_e_nom_extendable
  expression: Store_e >= Store_e_min_pu * Store_e_nom
```

$$e_{t,v} \ge \underline{\mathrm{e}}_{t,v} \cdot \mathrm{e}^{\mathrm{nom}}_{v} \qquad \forall\thinspace t \in \mathcal{T},\enspace v \in \mathcal{V} \thinspace:\thinspace \neg \mathrm{ext}^{e}_{v}$$

### `Store-fix-e-upper`

`Store_fix_e_upper`

```yaml
Store_fix_e_upper:
  description: "`Store-fix-e-upper` — a fixed store holds at most its nominal capacity"
  foreach: [snapshot, store]
  where: not Store_e_nom_extendable
  expression: Store_e <= Store_e_max_pu * Store_e_nom
```

$$e_{t,v} \le \overline{\mathrm{e}}_{t,v} \cdot \mathrm{e}^{\mathrm{nom}}_{v} \qquad \forall\thinspace t \in \mathcal{T},\enspace v \in \mathcal{V} \thinspace:\thinspace \neg \mathrm{ext}^{e}_{v}$$

### `Store-ext-e-lower`

`Store_ext_e_lower`

```yaml
Store_ext_e_lower:
  description: "`Store-ext-e-lower` — an extendable store holds at least its floor of the chosen build"
  foreach: [snapshot, store]
  where: Store_e_nom_extendable
  expression: Store_e >= Store_e_min_pu * Store_e_nom_ext
```

$$e_{t,v} \ge \underline{\mathrm{e}}_{t,v} \cdot E_{v} \qquad \forall\thinspace t \in \mathcal{T},\enspace v \in \mathcal{V} \thinspace:\thinspace \mathrm{ext}^{e}_{v}$$

### `Store-ext-e-upper`

`Store_ext_e_upper`

```yaml
Store_ext_e_upper:
  description: "`Store-ext-e-upper` — an extendable store holds at most the chosen build"
  foreach: [snapshot, store]
  where: Store_e_nom_extendable
  expression: Store_e <= Store_e_max_pu * Store_e_nom_ext
```

$$e_{t,v} \le \overline{\mathrm{e}}_{t,v} \cdot E_{v} \qquad \forall\thinspace t \in \mathcal{T},\enspace v \in \mathcal{V} \thinspace:\thinspace \mathrm{ext}^{e}_{v}$$

### `Store-ext-e_nom-lower`

`Store_ext_e_nom_lower`

```yaml
Store_ext_e_nom_lower:
  description: "`Store-ext-e_nom-lower` — the chosen build is at least its floor"
  foreach: [store]
  where: Store_e_nom_extendable
  expression: Store_e_nom_ext >= Store_e_nom_min
```

$$E_{v} \ge \underline{\mathrm{e}}^{\mathrm{nom}}_{v} \qquad \forall\thinspace v \in \mathcal{V} \thinspace:\thinspace \mathrm{ext}^{e}_{v}$$

### `Store-ext-e_nom-upper`

`Store_ext_e_nom_upper`

```yaml
Store_ext_e_nom_upper:
  description: "`Store-ext-e_nom-upper` — the chosen build is at most its cap; a cap of infinity is no row"
  foreach: [store]
  where: Store_e_nom_extendable AND Store_e_nom_max
  expression: Store_e_nom_ext <= Store_e_nom_max
```

$$E_{v} \le \overline{\mathrm{e}}^{\mathrm{nom}}_{v} \qquad \forall\thinspace v \in \mathcal{V} \thinspace:\thinspace \mathrm{ext}^{e}_{v} \wedge \overline{\mathrm{e}}^{\mathrm{nom}}_{v} \text{ is defined}$$

### `Store-e_nom_set`

`Store_e_nom_set`

```yaml
Store_e_nom_set:
  description: "`Store-e_nom_set` — the chosen build pinned, wherever a value is given"
  foreach: [store]
  where: Store_e_nom_extendable AND Store_e_nom_set
  expression: Store_e_nom_ext == Store_e_nom_set
```

$$E_{v} = \mathrm{e}^{\mathrm{nom,set}}_{v} \qquad \forall\thinspace v \in \mathcal{V} \thinspace:\thinspace \mathrm{ext}^{e}_{v} \wedge \mathrm{e}^{\mathrm{nom,set}}_{v} \text{ is defined}$$

### `Store-energy_balance`

`Store_energy_balance`

```yaml
Store_energy_balance:
  description: >-
    `Store-energy_balance` — energy carried over less standing loss, less
    what is delivered to the bus. The translated term vacates the first
    snapshot; the initial block below is the boundary
  foreach: [snapshot, store]
  where: not Store_e_cyclic
  expression: >-
    Store_e ==
    Store_retention * shift(Store_e, over=snapshot, offset=1)
    - Store_p * snapshot_weightings_stores
```

$$e_{t,v} = \rho^{e}_{t,v} \cdot e_{t - 1,v} - q_{t,v} \cdot \mathrm{w}^{\mathrm{sto}}_{t} \qquad \forall\thinspace t \in \mathcal{T},\enspace v \in \mathcal{V} \thinspace:\thinspace \neg \mathrm{cyc}^{e}_{v}$$

### `Store-energy_balance`

`Store_energy_balance_initial`

```yaml
Store_energy_balance_initial:
  description: "`Store-energy_balance` — the first snapshot opens on the given initial energy, which no standing loss has touched yet"
  foreach: [snapshot, store]
  where: not Store_e_cyclic AND position(snapshot) == 0
  expression: >-
    Store_e ==
    Store_e_initial
    - Store_p * snapshot_weightings_stores
```

$$e_{t,v} = \mathrm{e}^{0}_{v} - q_{t,v} \cdot \mathrm{w}^{\mathrm{sto}}_{t} \qquad \forall\thinspace t \in \mathcal{T},\enspace v \in \mathcal{V} \thinspace:\thinspace \neg \mathrm{cyc}^{e}_{v} \wedge \mathrm{pos}(t) = 0$$

### `Store-energy_balance`

`Store_energy_balance_cyclic`

```yaml
Store_energy_balance_cyclic:
  description: "`Store-energy_balance` — a cyclic store's first snapshot carries over from its last"
  foreach: [snapshot, store]
  where: Store_e_cyclic
  expression: >-
    Store_e ==
    Store_retention * shift(Store_e, over=snapshot, offset=1, edge='wrap')
    - Store_p * snapshot_weightings_stores
```

$$e_{t,v} = \rho^{e}_{t,v} \cdot e_{t \ominus 1,v} - q_{t,v} \cdot \mathrm{w}^{\mathrm{sto}}_{t} \qquad \forall\thinspace t \in \mathcal{T},\enspace v \in \mathcal{V} \thinspace:\thinspace \mathrm{cyc}^{e}_{v}$$

### `Generator-p_set`

`Generator_p_set`

```yaml
Generator_p_set:
  description: "`Generator-p_set` — output pinned to the given schedule, wherever one is given"
  foreach: [snapshot, generator]
  where: Generator_p_set
  expression: Generator_p == Generator_p_set
```

$$p_{t,g} = \mathrm{p}^{\mathrm{set}}_{t,g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{p}^{\mathrm{set}}_{t,g} \text{ is defined}$$

### `Link-p_set`

`Link_p_set`

```yaml
Link_p_set:
  description: "`Link-p_set` — flow pinned to the given schedule, wherever one is given"
  foreach: [snapshot, link]
  where: Link_p_set
  expression: Link_p == Link_p_set
```

$$f_{t,l} = \mathrm{f}^{\mathrm{set}}_{t,l} \qquad \forall\thinspace t \in \mathcal{T},\enspace l \in \mathcal{L} \thinspace:\thinspace \mathrm{f}^{\mathrm{set}}_{t,l} \text{ is defined}$$

### `StorageUnit-p_set`

`StorageUnit_p_set`

```yaml
StorageUnit_p_set:
  description: "`StorageUnit-p_set` — net dispatch pinned to the given schedule, wherever one is given"
  foreach: [snapshot, storage_unit]
  where: StorageUnit_p_set
  expression: StorageUnit_p_dispatch - StorageUnit_p_store == StorageUnit_p_set
```

$$h^{+}_{t,s} - h^{-}_{t,s} = \mathrm{h}^{\mathrm{set}}_{t,s} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \mathrm{h}^{\mathrm{set}}_{t,s} \text{ is defined}$$

### `StorageUnit-state_of_charge_set`

`StorageUnit_state_of_charge_set`

```yaml
StorageUnit_state_of_charge_set:
  description: "`StorageUnit-state_of_charge_set` — charge pinned to the given schedule, wherever one is given"
  foreach: [snapshot, storage_unit]
  where: StorageUnit_state_of_charge_set
  expression: StorageUnit_state_of_charge == StorageUnit_state_of_charge_set
```

$$\mathit{soc}_{t,s} = \mathrm{soc}^{\mathrm{set}}_{t,s} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \mathrm{soc}^{\mathrm{set}}_{t,s} \text{ is defined}$$

### `Store-e_set`

`Store_e_set`

```yaml
Store_e_set:
  description: "`Store-e_set` — energy pinned to the given schedule, wherever one is given"
  foreach: [snapshot, store]
  where: Store_e_set
  expression: Store_e == Store_e_set
```

$$e_{t,v} = \mathrm{e}^{\mathrm{set}}_{t,v} \qquad \forall\thinspace t \in \mathcal{T},\enspace v \in \mathcal{V} \thinspace:\thinspace \mathrm{e}^{\mathrm{set}}_{t,v} \text{ is defined}$$

### `primary_energy`

`GlobalConstraint_primary_energy_ub`

```yaml
GlobalConstraint_primary_energy_ub:
  description: "`primary_energy` — its total, at most its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'primary_energy' AND GlobalConstraint_sense == '<='
  expression: primary_energy <= GlobalConstraint_constant
```

$$\sum_{g \in \mathcal{G}} \sum_{t \in \mathcal{T}} p_{t,g} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \cdot \mathrm{a}_{o,g} - \left( \sum_{s \in \mathcal{S}} \sum_{t \in \mathcal{T}} \mathit{soc}_{t,s} \cdot \mathrm{last}_{t} \cdot \mathrm{a}^{h}_{o,s} \right) - \left( \sum_{v \in \mathcal{V}} \sum_{t \in \mathcal{T}} e_{t,v} \cdot \mathrm{last}_{t} \cdot \mathrm{a}^{e}_{o,v} \right) \le \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{'}\mathrm{primary\_energy}\text{'} \wedge \mathrm{sense}_{o} = \text{'}\mathrm{<=}\text{'}$$

### `primary_energy`

`GlobalConstraint_primary_energy_lb`

```yaml
GlobalConstraint_primary_energy_lb:
  description: "`primary_energy` — its total, at least its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'primary_energy' AND GlobalConstraint_sense == '>='
  expression: primary_energy >= GlobalConstraint_constant
```

$$\sum_{g \in \mathcal{G}} \sum_{t \in \mathcal{T}} p_{t,g} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \cdot \mathrm{a}_{o,g} - \left( \sum_{s \in \mathcal{S}} \sum_{t \in \mathcal{T}} \mathit{soc}_{t,s} \cdot \mathrm{last}_{t} \cdot \mathrm{a}^{h}_{o,s} \right) - \left( \sum_{v \in \mathcal{V}} \sum_{t \in \mathcal{T}} e_{t,v} \cdot \mathrm{last}_{t} \cdot \mathrm{a}^{e}_{o,v} \right) \ge \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{'}\mathrm{primary\_energy}\text{'} \wedge \mathrm{sense}_{o} = \text{'}\mathrm{>=}\text{'}$$

### `primary_energy`

`GlobalConstraint_primary_energy_eq`

```yaml
GlobalConstraint_primary_energy_eq:
  description: "`primary_energy` — its total, at its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'primary_energy' AND GlobalConstraint_sense == '=='
  expression: primary_energy == GlobalConstraint_constant
```

$$\sum_{g \in \mathcal{G}} \sum_{t \in \mathcal{T}} p_{t,g} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \cdot \mathrm{a}_{o,g} - \left( \sum_{s \in \mathcal{S}} \sum_{t \in \mathcal{T}} \mathit{soc}_{t,s} \cdot \mathrm{last}_{t} \cdot \mathrm{a}^{h}_{o,s} \right) - \left( \sum_{v \in \mathcal{V}} \sum_{t \in \mathcal{T}} e_{t,v} \cdot \mathrm{last}_{t} \cdot \mathrm{a}^{e}_{o,v} \right) = \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{'}\mathrm{primary\_energy}\text{'} \wedge \mathrm{sense}_{o} = \text{'}\mathrm{==}\text{'}$$

### `operational_limit`

`GlobalConstraint_operational_limit_ub`

```yaml
GlobalConstraint_operational_limit_ub:
  description: "`operational_limit` — its total, at most its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'operational_limit' AND GlobalConstraint_sense == '<='
  expression: operational_limit <= GlobalConstraint_constant
```

$$\sum_{g \in \mathcal{G}} \sum_{t \in \mathcal{T}} p_{t,g} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \cdot \mathrm{b}_{o,g} - \left( \sum_{s \in \mathcal{S}} \sum_{t \in \mathcal{T}} \mathit{soc}_{t,s} \cdot \mathrm{last}_{t} \cdot \mathrm{b}^{h}_{o,s} \right) - \left( \sum_{v \in \mathcal{V}} \sum_{t \in \mathcal{T}} e_{t,v} \cdot \mathrm{last}_{t} \cdot \mathrm{b}^{e}_{o,v} \right) \le \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{'}\mathrm{operational\_limit}\text{'} \wedge \mathrm{sense}_{o} = \text{'}\mathrm{<=}\text{'}$$

### `operational_limit`

`GlobalConstraint_operational_limit_lb`

```yaml
GlobalConstraint_operational_limit_lb:
  description: "`operational_limit` — its total, at least its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'operational_limit' AND GlobalConstraint_sense == '>='
  expression: operational_limit >= GlobalConstraint_constant
```

$$\sum_{g \in \mathcal{G}} \sum_{t \in \mathcal{T}} p_{t,g} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \cdot \mathrm{b}_{o,g} - \left( \sum_{s \in \mathcal{S}} \sum_{t \in \mathcal{T}} \mathit{soc}_{t,s} \cdot \mathrm{last}_{t} \cdot \mathrm{b}^{h}_{o,s} \right) - \left( \sum_{v \in \mathcal{V}} \sum_{t \in \mathcal{T}} e_{t,v} \cdot \mathrm{last}_{t} \cdot \mathrm{b}^{e}_{o,v} \right) \ge \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{'}\mathrm{operational\_limit}\text{'} \wedge \mathrm{sense}_{o} = \text{'}\mathrm{>=}\text{'}$$

### `operational_limit`

`GlobalConstraint_operational_limit_eq`

```yaml
GlobalConstraint_operational_limit_eq:
  description: "`operational_limit` — its total, at its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'operational_limit' AND GlobalConstraint_sense == '=='
  expression: operational_limit == GlobalConstraint_constant
```

$$\sum_{g \in \mathcal{G}} \sum_{t \in \mathcal{T}} p_{t,g} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \cdot \mathrm{b}_{o,g} - \left( \sum_{s \in \mathcal{S}} \sum_{t \in \mathcal{T}} \mathit{soc}_{t,s} \cdot \mathrm{last}_{t} \cdot \mathrm{b}^{h}_{o,s} \right) - \left( \sum_{v \in \mathcal{V}} \sum_{t \in \mathcal{T}} e_{t,v} \cdot \mathrm{last}_{t} \cdot \mathrm{b}^{e}_{o,v} \right) = \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{'}\mathrm{operational\_limit}\text{'} \wedge \mathrm{sense}_{o} = \text{'}\mathrm{==}\text{'}$$

### `transmission_volume_expansion_limit`

`GlobalConstraint_transmission_volume_expansion_limit_ub`

```yaml
GlobalConstraint_transmission_volume_expansion_limit_ub:
  description: "`transmission_volume_expansion_limit` — its total, at most its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'transmission_volume_expansion_limit' AND GlobalConstraint_sense == '<='
  expression: transmission_volume_expansion <= GlobalConstraint_constant
```

$$\sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{len}_{o,k} + \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{len}^{f}_{o,l} \le \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{'}\mathrm{transmission\_volume\_expansion\_limit}\text{'} \wedge \mathrm{sense}_{o} = \text{'}\mathrm{<=}\text{'}$$

### `transmission_volume_expansion_limit`

`GlobalConstraint_transmission_volume_expansion_limit_lb`

```yaml
GlobalConstraint_transmission_volume_expansion_limit_lb:
  description: "`transmission_volume_expansion_limit` — its total, at least its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'transmission_volume_expansion_limit' AND GlobalConstraint_sense == '>='
  expression: transmission_volume_expansion >= GlobalConstraint_constant
```

$$\sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{len}_{o,k} + \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{len}^{f}_{o,l} \ge \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{'}\mathrm{transmission\_volume\_expansion\_limit}\text{'} \wedge \mathrm{sense}_{o} = \text{'}\mathrm{>=}\text{'}$$

### `transmission_volume_expansion_limit`

`GlobalConstraint_transmission_volume_expansion_limit_eq`

```yaml
GlobalConstraint_transmission_volume_expansion_limit_eq:
  description: "`transmission_volume_expansion_limit` — its total, at its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'transmission_volume_expansion_limit' AND GlobalConstraint_sense == '=='
  expression: transmission_volume_expansion == GlobalConstraint_constant
```

$$\sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{len}_{o,k} + \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{len}^{f}_{o,l} = \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{'}\mathrm{transmission\_volume\_expansion\_limit}\text{'} \wedge \mathrm{sense}_{o} = \text{'}\mathrm{==}\text{'}$$

### `transmission_expansion_cost_limit`

`GlobalConstraint_transmission_expansion_cost_limit_ub`

```yaml
GlobalConstraint_transmission_expansion_cost_limit_ub:
  description: "`transmission_expansion_cost_limit` — its total, at most its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'transmission_expansion_cost_limit' AND GlobalConstraint_sense == '<='
  expression: transmission_expansion_cost <= GlobalConstraint_constant
```

$$\sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{cc}_{o,k} + \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{cc}^{f}_{o,l} \le \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{'}\mathrm{transmission\_expansion\_cost\_limit}\text{'} \wedge \mathrm{sense}_{o} = \text{'}\mathrm{<=}\text{'}$$

### `transmission_expansion_cost_limit`

`GlobalConstraint_transmission_expansion_cost_limit_lb`

```yaml
GlobalConstraint_transmission_expansion_cost_limit_lb:
  description: "`transmission_expansion_cost_limit` — its total, at least its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'transmission_expansion_cost_limit' AND GlobalConstraint_sense == '>='
  expression: transmission_expansion_cost >= GlobalConstraint_constant
```

$$\sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{cc}_{o,k} + \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{cc}^{f}_{o,l} \ge \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{'}\mathrm{transmission\_expansion\_cost\_limit}\text{'} \wedge \mathrm{sense}_{o} = \text{'}\mathrm{>=}\text{'}$$

### `transmission_expansion_cost_limit`

`GlobalConstraint_transmission_expansion_cost_limit_eq`

```yaml
GlobalConstraint_transmission_expansion_cost_limit_eq:
  description: "`transmission_expansion_cost_limit` — its total, at its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'transmission_expansion_cost_limit' AND GlobalConstraint_sense == '=='
  expression: transmission_expansion_cost == GlobalConstraint_constant
```

$$\sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{cc}_{o,k} + \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{cc}^{f}_{o,l} = \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{'}\mathrm{transmission\_expansion\_cost\_limit}\text{'} \wedge \mathrm{sense}_{o} = \text{'}\mathrm{==}\text{'}$$

### `tech_capacity_expansion_limit`

`GlobalConstraint_tech_capacity_expansion_limit_ub`

```yaml
GlobalConstraint_tech_capacity_expansion_limit_ub:
  description: "`tech_capacity_expansion_limit` — its total, at most its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'tech_capacity_expansion_limit' AND GlobalConstraint_sense == '<='
  expression: tech_capacity_expansion <= GlobalConstraint_constant
```

$$\sum_{g \in \mathcal{G}} P_{g} \cdot \mathrm{m}_{o,g} + \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{m}^{f}_{o,l} + \sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{m}^{l}_{o,k} + \sum_{s \in \mathcal{S}} H_{s} \cdot \mathrm{m}^{h}_{o,s} + \sum_{v \in \mathcal{V}} E_{v} \cdot \mathrm{m}^{e}_{o,v} \le \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{'}\mathrm{tech\_capacity\_expansion\_limit}\text{'} \wedge \mathrm{sense}_{o} = \text{'}\mathrm{<=}\text{'}$$

### `tech_capacity_expansion_limit`

`GlobalConstraint_tech_capacity_expansion_limit_lb`

```yaml
GlobalConstraint_tech_capacity_expansion_limit_lb:
  description: "`tech_capacity_expansion_limit` — its total, at least its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'tech_capacity_expansion_limit' AND GlobalConstraint_sense == '>='
  expression: tech_capacity_expansion >= GlobalConstraint_constant
```

$$\sum_{g \in \mathcal{G}} P_{g} \cdot \mathrm{m}_{o,g} + \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{m}^{f}_{o,l} + \sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{m}^{l}_{o,k} + \sum_{s \in \mathcal{S}} H_{s} \cdot \mathrm{m}^{h}_{o,s} + \sum_{v \in \mathcal{V}} E_{v} \cdot \mathrm{m}^{e}_{o,v} \ge \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{'}\mathrm{tech\_capacity\_expansion\_limit}\text{'} \wedge \mathrm{sense}_{o} = \text{'}\mathrm{>=}\text{'}$$

### `tech_capacity_expansion_limit`

`GlobalConstraint_tech_capacity_expansion_limit_eq`

```yaml
GlobalConstraint_tech_capacity_expansion_limit_eq:
  description: "`tech_capacity_expansion_limit` — its total, at its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'tech_capacity_expansion_limit' AND GlobalConstraint_sense == '=='
  expression: tech_capacity_expansion == GlobalConstraint_constant
```

$$\sum_{g \in \mathcal{G}} P_{g} \cdot \mathrm{m}_{o,g} + \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{m}^{f}_{o,l} + \sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{m}^{l}_{o,k} + \sum_{s \in \mathcal{S}} H_{s} \cdot \mathrm{m}^{h}_{o,s} + \sum_{v \in \mathcal{V}} E_{v} \cdot \mathrm{m}^{e}_{o,v} = \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{'}\mathrm{tech\_capacity\_expansion\_limit}\text{'} \wedge \mathrm{sense}_{o} = \text{'}\mathrm{==}\text{'}$$

### `Bus-nodal_balance`

`Bus_nodal_balance`

```yaml
Bus_nodal_balance:
  description: >-
    `Bus-nodal_balance` — what is generated at a bus, storage dispatch and
    stores included, less what the links take away, plus what arrives over
    them after losses at every port they deliver to, meets the load there.
    A bus nothing is attached to has no row; PyPSA refuses one that
    carries load, and this file does not yet.
  foreach: [snapshot, bus]
  expression: >-
    sum(Generator_p, by=Generator_bus)
    + sum(StorageUnit_p_dispatch - StorageUnit_p_store, by=StorageUnit_bus)
    + sum(Store_p, by=Store_bus)
    - sum(Link_p, by=Link_bus0)
    + sum(Link_p * Link_efficiency, by=Link_bus1)
    + sum(Link_p * Link_efficiency2, by=Link_bus2)
    - sum(Line_s, by=Line_bus0)
    + sum(Line_s, by=Line_bus1)
    == sum(Load_p_set, by=Load_bus)
```

$$\sum_{g \in \mathcal{G} \thinspace:\thinspace \mathrm{Generator\_bus}(g) = n} p_{t,g} + \sum_{s \in \mathcal{S} \thinspace:\thinspace \mathrm{StorageUnit\_bus}(s) = n} \left( h^{+}_{t,s} - h^{-}_{t,s} \right) + \sum_{v \in \mathcal{V} \thinspace:\thinspace \mathrm{Store\_bus}(v) = n} q_{t,v} - \left( \sum_{l \in \mathcal{L} \thinspace:\thinspace \mathrm{Link\_bus0}(l) = n} f_{t,l} \right) + \sum_{l \in \mathcal{L} \thinspace:\thinspace \mathrm{Link\_bus1}(l) = n} f_{t,l} \cdot \eta_{l} + \sum_{l \in \mathcal{L} \thinspace:\thinspace \mathrm{Link\_bus2}(l) = n} f_{t,l} \cdot \eta^{2}_{l} - \left( \sum_{k \in \mathcal{K} \thinspace:\thinspace \mathrm{Line\_bus0}(k) = n} s_{t,k} \right) + \sum_{k \in \mathcal{K} \thinspace:\thinspace \mathrm{Line\_bus1}(k) = n} s_{t,k} = \sum_{d \in \mathcal{D} \thinspace:\thinspace \mathrm{Load\_bus}(d) = n} \mathrm{load}_{t,d} \qquad \forall\thinspace t \in \mathcal{T},\enspace n \in \mathcal{N}$$

#### Variable domains

**`Generator_p`**

$$p_{t,g} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G}$$

**`Link_p`**

$$f_{t,l} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace l \in \mathcal{L}$$

**`StorageUnit_p_dispatch`**

$$h^{+}_{t,s} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S}$$

**`StorageUnit_p_store`**

$$h^{-}_{t,s} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S}$$

**`StorageUnit_state_of_charge`**

$$\mathit{soc}_{t,s} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S}$$

**`StorageUnit_spill`**

$$0 \le \mathit{spill}_{t,s} \le \mathrm{inflow}_{t,s} \qquad \forall\thinspace t \in \mathcal{T},\enspace s \in \mathcal{S} \thinspace:\thinspace \mathrm{inflow}_{t,s} > 0$$

**`Store_e`**

$$e_{t,v} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace v \in \mathcal{V}$$

**`Store_p`**

$$q_{t,v} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace v \in \mathcal{V}$$

**`Generator_n_mod`**

$$N_{g} \ge 0, N_{g} \in \mathbb{Z} \qquad \forall\thinspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{ext}_{g} \wedge \mathrm{p}^{\mathrm{mod}}_{g} > 0$$

**`Generator_status`**

$$u_{t,g} \ge 0, u_{t,g} \in \mathbb{Z} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g}$$

**`Generator_start_up`**

$$\mathit{up}_{t,g} \ge 0, \mathit{up}_{t,g} \in \mathbb{Z} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g}$$

**`Generator_shut_down`**

$$\mathit{dn}_{t,g} \ge 0, \mathit{dn}_{t,g} \in \mathbb{Z} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g}$$

**`Line_s`**

$$s_{t,k} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace k \in \mathcal{K}$$

**`Line_s_nom_ext`**

$$S_{k} \in \mathbb{R} \qquad \forall\thinspace k \in \mathcal{K} \thinspace:\thinspace \mathrm{ext}^{s}_{k}$$

**`Generator_p_nom_ext`**

$$P_{g} \in \mathbb{R} \qquad \forall\thinspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{ext}_{g}$$

**`Link_p_nom_ext`**

$$F_{l} \in \mathbb{R} \qquad \forall\thinspace l \in \mathcal{L} \thinspace:\thinspace \mathrm{ext}^{f}_{l}$$

**`StorageUnit_p_nom_ext`**

$$H_{s} \in \mathbb{R} \qquad \forall\thinspace s \in \mathcal{S} \thinspace:\thinspace \mathrm{ext}^{h}_{s}$$

**`Store_e_nom_ext`**

$$E_{v} \in \mathbb{R} \qquad \forall\thinspace v \in \mathcal{V} \thinspace:\thinspace \mathrm{ext}^{e}_{v}$$
<!-- gallery:end -->

Regenerate with `pixi run python -m tools.gallery`.
