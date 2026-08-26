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
there. The blocks are the file — PyPSA's name for the row, the YAML, the
equation the typesetter prints — and are generated, so a row that stops
loading or changes its math fails CI.

Three rules shape the file. Bounds are the explicit rows PyPSA writes, so
their duals are row duals. Regimes are data columns and `where:` masks, never
file variants. Names are PyPSA's, `Component_attribute`, with a symbol table
(`examples/symbols/pypsa.yaml`) making the math read as math.

## Index

A row is **done** and links once it is in the file. Under each rung's table
sits its reference network — the shared spine below plus the rung's own
folder of additions under `examples/references/pypsa/data/`, solved out of
band by the pinned scripts beside it — with the objective and row counts a
parity gate will compare, so the YAML and the data it binds read side by
side. A blank status is a row
expected to state one-to-one; a word is the catch: **prep** needs a parameter computed in
data prep · **split** one PyPSA row is several `where:` blocks · **not** a
PyPSA workaround not reproduced · **flag** only under an `n.optimize()`
keyword · **scope** multi-period or stochastic · **open** not stateable yet.

<!-- reference:spine:begin -->
> Every rung's network is the spine below plus the rung's own folder of additions, read by `examples/references/pypsa/instances.py`. Folders combine by appending rows, table by table: each row keeps its own file's columns and becomes one `n.add`, so no table is column-joined and no empty cells are invented — a blank cell is an attribute the row does not set, PyPSA's default. The one cross-folder touch is `timeseries.csv`, which may put a schedule on a spine component.

<details markdown="1">
<summary>The shared spine, <code>data/base/</code></summary>

`data/base/buses.csv`

```csv
name
north
south
```

`data/base/generators.csv`

```csv
name,bus,p_nom,marginal_cost
coal,north,100.0,10.0
gas,south,100.0,30.0
```

`data/base/links.csv`

```csv
name,bus0,bus1,p_nom,p_min_pu,efficiency
wire,north,south,40.0,-1.0,0.9
```

`data/base/loads.csv`

```csv
name,bus,p_set
north_load,north,30.0
south_load,south,40.0
```

`data/base/snapshots.csv`

```csv
snapshot,objective,stores,generators
0,1.0,1.0,1.0
1,1.0,1.0,1.0
2,1.0,1.0,1.0
3,1.0,1.0,1.0
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
| `Bus-meshed-*-nodal_balance`                        | not    | a linopy-speed split; one row here                         |
| [`marginal_cost`](#objective)                       | done   |                                                            |
| [`marginal_cost_quadratic`](pypsa_quadratic.md)     | done   | rung 10, a file of its own — one model cannot carry a quadratic objective beside rung 7's integers and keep a HiGHS lane |
| `objective_constant`                                | not    | compare objectives net of `n._objective_constant`          |

<!-- reference:rung1_transport:begin -->
> ✔ `pypsa 1.3.0` solves this rung's reference network through its own linopy model at objective `3246.666666666667`, 45 rows — recorded by `examples/references/pypsa/rung1_transport.py`. `lpspec 0.0.1a259` binds `examples/pypsa.yaml` against the same network and lands on the same objective (`parity.py`). Its instance is `data/base/` plus `data/rung1_transport/`.

<details markdown="1">
<summary>What this rung adds, as data</summary>

Rung 1's transport: the spine as it stands, plus a must-run its schedule pins.

Coal in the north is cheap and the wire loses a tenth on the way south, so
the south's load splits between imports, a small must-run pinned by its
given schedule, and its own gas at the link's rating.

`data/rung1_transport/generators.csv`

```csv
name,bus,p_nom,marginal_cost
must_run,south,10.0,0.0
```

`data/rung1_transport/timeseries.csv`

```csv
component,name,attribute,snapshot,value
Generator,must_run,p_set,0,5.0
Generator,must_run,p_set,1,5.0
Generator,must_run,p_set,2,5.0
Generator,must_run,p_set,3,5.0
Link,wire,p_set,0,10.0
```

</details>
<!-- reference:rung1_transport:end -->

### Rung 2 — storage

| PyPSA                                                 | status | note                                                          |
| ----------------------------------------------------- | ------ | ------------------------------------------------------------- |
| [`StorageUnit-p_dispatch`, `-p_store`, `-state_of_charge`, `Store-e`, `Store-p`](#variable-domains) | done |                                 |
| [`StorageUnit-spill`](#variable-domains)              | done   | `where: inflow > 0`, `absence: zero`; bounds on the variable, as PyPSA's |
| [`StorageUnit-fix-*`](#storageunit-fix-p_dispatch-lower), [`Store-fix-e-*`](#store-fix-e-lower) | done |                                 |
| [`StorageUnit-energy_balance`](#storageunit-energy_balance) | done | three blocks: carried / initial / cyclic; `(1-loss)**eh` is prep |
| [`Store-energy_balance`](#store-energy_balance)       | done   | same                                                          |
| [`StorageUnit-p_set`](#storageunit-p_set), [`{c}-{attr}_set`](#generator-p_set) | done | `Generator-p_set`, `Link-p_set`, `StorageUnit-state_of_charge_set`, `Store-e_set`, `Line-s_set` |
| [`marginal_cost_storage`, `spill_cost`](#objective)   | done   |                                                               |

<!-- reference:rung2_storage:begin -->
> ✔ `pypsa 1.3.0` solves this rung's reference network through its own linopy model at objective `2488.903629000791`, 103 rows — recorded by `examples/references/pypsa/rung2_storage.py`. `lpspec 0.0.1a259` binds `examples/pypsa.yaml` against the same network and lands on the same objective (`parity.py`). Its instance is `data/base/` plus `data/rung2_storage/`.

<details markdown="1">
<summary>What this rung adds, as data</summary>

Rung 2's storage: a cyclic battery, a reservoir that can spill, a cavern store.

The generator is cheap for two snapshots and dear for two, so the battery
buys low and sells high and its horizon closes on itself; the reservoir
opens on a given charge and spills the inflow it cannot hold; the cavern
drains from its initial fill.

`data/rung2_storage/storage_units.csv`

```csv
name,bus,p_nom,max_hours,efficiency_store,efficiency_dispatch,standing_loss,cyclic_state_of_charge,marginal_cost,spill_cost,state_of_charge_initial,marginal_cost_storage
battery,south,20.0,4.0,0.95,0.9,0.01,True,0.5,,,
reservoir,south,10.0,2.0,,,,,,2.0,5.0,0.1
```

`data/rung2_storage/stores.csv`

```csv
name,bus,e_nom,e_initial,standing_loss,marginal_cost
cavern,south,40.0,25.0,0.005,0.2
```

`data/rung2_storage/timeseries.csv`

```csv
component,name,attribute,snapshot,value
Generator,gas,marginal_cost,0,15.0
Generator,gas,marginal_cost,1,15.0
Generator,gas,marginal_cost,2,60.0
Generator,gas,marginal_cost,3,60.0
StorageUnit,battery,p_set,0,0.0
StorageUnit,reservoir,inflow,0,12.0
StorageUnit,reservoir,inflow,1,12.0
StorageUnit,reservoir,inflow,2,12.0
StorageUnit,reservoir,inflow,3,12.0
StorageUnit,reservoir,state_of_charge_set,3,10.0
Store,cavern,e_set,3,20.0
```

</details>
<!-- reference:rung2_storage:end -->

### Rung 3 — expansion

| PyPSA                            | status | note                                        |
| -------------------------------- | ------ | ------------------------------------------- |
| [`{c}-p_nom`, `-s_nom`, `-e_nom`](#variable-domains) | done | `{c}_p_nom_ext` here — the fixed regime keeps the parameter |
| [`{c}-ext-{attr}-lower/upper`](#generator-ext-p-lower) | done |                                           |
| [`{c}-ext-p_nom-lower/upper`](#generator-ext-p_nom-lower) | done | a cap of infinity is no row            |
| [`{c}-p_nom_set`](#generator-p_nom_set) | done |                                                      |
| [`Generator-e_sum_min/max`](#generator-e_sum_min) | done | no row where the bound is not finite       |
| [capital cost](#objective)       | done   | `periodized_cost` is an annuity, data prep  |

<!-- reference:rung3_expansion:begin -->
> ✔ `pypsa 1.3.0` solves this rung's reference network through its own linopy model at objective `5646.0526315789475`, 124 rows — recorded by `examples/references/pypsa/rung3_expansion.py`. `lpspec 0.0.1a259` binds `examples/pypsa.yaml` against the same network and lands on the same objective (`parity.py`). Its instance is `data/base/` plus `data/rung3_expansion/`.

<details markdown="1">
<summary>What this rung adds, as data</summary>

Rung 3's expansion: a wind build decided by the solver against a fixed gas fleet.

Wind is free to run but costs capacity, its availability varies, and its
build is floored and capped; gas is fixed, dear, and budgeted in energy
over the horizon, so the optimum has to buy some wind — at least the
energy floor it also carries. The cable to the island is the extendable
link, and the pump and tank are the extendable storage.

`data/rung3_expansion/buses.csv`

```csv
name
island
```

`data/rung3_expansion/generators.csv`

```csv
name,bus,p_nom_extendable,capital_cost,p_nom_min,p_nom_max,marginal_cost,e_sum_min,p_nom_set,p_nom,e_sum_max
wind,north,True,50.0,5.0,80.0,0.0,40.0,,,
solar,north,True,60.0,,40.0,0.0,,15.0,,
diesel,island,,,,,40.0,,,60.0,70.0
```

`data/rung3_expansion/links.csv`

```csv
name,bus0,bus1,p_nom_extendable,capital_cost,p_nom_max,efficiency,p_nom_set
cable,north,island,True,20.0,30.0,0.95,25.0
```

`data/rung3_expansion/loads.csv`

```csv
name,bus,p_set
island_load,island,10.0
```

`data/rung3_expansion/storage_units.csv`

```csv
name,bus,p_nom_extendable,capital_cost,p_nom_max,max_hours,efficiency_store,efficiency_dispatch,cyclic_state_of_charge,p_nom_set
pump,north,True,15.0,30.0,4.0,0.9,0.9,True,20.0
```

`data/rung3_expansion/stores.csv`

```csv
name,bus,e_nom_extendable,capital_cost,e_nom_max,e_cyclic,e_nom_set
tank,north,True,2.0,80.0,True,50.0
```

`data/rung3_expansion/timeseries.csv`

```csv
component,name,attribute,snapshot,value
Generator,wind,p_max_pu,0,0.3
Generator,wind,p_max_pu,1,0.8
Generator,wind,p_max_pu,2,0.5
Generator,wind,p_max_pu,3,0.9
Generator,solar,p_max_pu,0,0.5
Generator,solar,p_max_pu,1,0.6
Generator,solar,p_max_pu,2,0.4
Generator,solar,p_max_pu,3,0.2
```

</details>
<!-- reference:rung3_expansion:end -->

### Rung 4 — ramps

| PyPSA                          | status | note                                                       |
| ------------------------------ | ------ | ---------------------------------------------------------- |
| [`{c}-p-ramp_limit_up/down`](#generator-p-ramp_limit_up) | done | fix and ext blocks; com is rung 7's, big-M rung 8's; the first snapshot's row is rolling horizon's, a flag |

<!-- reference:rung4_ramps:begin -->
> ✔ `pypsa 1.3.0` solves this rung's reference network through its own linopy model at objective `3950.0`, 64 rows — recorded by `examples/references/pypsa/rung4_ramps.py`. `lpspec 0.0.1a259` binds `examples/pypsa.yaml` against the same network and lands on the same objective (`parity.py`). Its instance is `data/base/` plus `data/rung4_ramps/`.

<details markdown="1">
<summary>What this rung adds, as data</summary>

Rung 4's ramps: a slow cheap unit against a fast dear one, chasing a swinging load.

Coal may move a fifth of its capacity per snapshot, so the swings belong
to the peaker however dear it is; the tie line east ramps too.

`data/rung4_ramps/buses.csv`

```csv
name
east
```

`data/rung4_ramps/generators.csv`

```csv
name,bus,p_nom,marginal_cost,ramp_limit_up,ramp_limit_down
coal_slow,north,80.0,8.0,0.2,0.2
```

`data/rung4_ramps/links.csv`

```csv
name,bus0,bus1,p_nom,efficiency,ramp_limit_up,ramp_limit_down
tie,north,east,50.0,1.0,0.4,0.4
```

`data/rung4_ramps/loads.csv`

```csv
name,bus
east_load,east
swing,north
```

`data/rung4_ramps/timeseries.csv`

```csv
component,name,attribute,snapshot,value
Load,east_load,p_set,0,5.0
Load,east_load,p_set,1,20.0
Load,east_load,p_set,2,25.0
Load,east_load,p_set,3,10.0
Load,swing,p_set,0,0.0
Load,swing,p_set,1,25.0
Load,swing,p_set,2,45.0
Load,swing,p_set,3,0.0
```

</details>
<!-- reference:rung4_ramps:end -->

### Rung 5 — global constraints

`GlobalConstraint-{name}` for all; the type and the comparator are data, so
each type is three blocks by sense.

| PyPSA type                            | status      | note                                              |
| ------------------------------------- | ----------- | ------------------------------------------------- |
| [`primary_energy`](#primary_energy)   | done        | carrier weights and the horizon-end charge read are prep |
| [`operational_limit`](#operational_limit) | done    |                                                   |
| [`transmission_volume_expansion_limit`](#transmission_volume_expansion_limit) | done | membership from PyPSA's carrier string is prep |
| [`transmission_expansion_cost_limit`](#transmission_expansion_cost_limit) | done |                                       |
| [`tech_capacity_expansion_limit`](#tech_capacity_expansion_limit) | done |                                               |
| `Bus-nom_min/max_{carrier}`           | not         | deprecated in PyPSA                               |
| `Carrier-growth_limit`                | scope       | multi-period                                      |
| `effect_limit`, priced effects        | open        | `effects.py` not inventoried                      |

<!-- reference:rung5_global_constraints:begin -->
> ✔ `pypsa 1.3.0` solves this rung's reference network through its own linopy model at objective `5590.0`, 57 rows — recorded by `examples/references/pypsa/rung5_global_constraints.py`. `lpspec 0.0.1a259` binds `examples/pypsa.yaml` against the same network and lands on the same objective (`parity.py`). Its instance is `data/base/` plus `data/rung5_global_constraints/`.

<details markdown="1">
<summary>What this rung adds, as data</summary>

Rung 5's global constraint: a primary-energy CO2 cap over three carriers.

Coal is cheap and dirty, gas dearer and cleaner, wind clean and dearest to
run here; the cap decides the mix, and its shadow price is the carbon
price.

`data/rung5_global_constraints/carriers.csv`

```csv
name,co2_emissions
coalc,0.9
gasc,0.4
windc,
```

`data/rung5_global_constraints/generators.csv`

```csv
name,bus,carrier,p_nom,marginal_cost,efficiency
coal5,north,coalc,60.0,9.0,0.35
gas5,north,gasc,60.0,25.0,0.5
wind5,north,windc,60.0,40.0,
```

`data/rung5_global_constraints/global_constraints.csv`

```csv
name,type,carrier_attribute,sense,constant
co2_cap,primary_energy,co2_emissions,<=,150.0
```

`data/rung5_global_constraints/loads.csv`

```csv
name,bus,p_set
extra5,north,50.0
```

</details>
<!-- reference:rung5_global_constraints:end -->

### Rung 6 — KVL

| PyPSA                   | status | note                              |
| ----------------------- | ------ | --------------------------------- |
| [`Line-s`](#variable-domains), [`Line-fix-s-*`](#line-fix-s-lower) | done | the ext and nominal rows sit under rung 3's pattern |
| [`Kirchhoff-Voltage-Law`](#kirchhoff-voltage-law) | done | the cycle basis is data prep      |

<!-- reference:rung6_kvl:begin -->
> ✔ `pypsa 1.3.0` solves this rung's reference network through its own linopy model at objective `5740.0`, 104 rows — recorded by `examples/references/pypsa/rung6_kvl.py`. `lpspec 0.0.1a259` binds `examples/pypsa.yaml` against the same network and lands on the same objective (`parity.py`). Its instance is `data/base/` plus `data/rung6_kvl/`.

<details markdown="1">
<summary>What this rung adds, as data</summary>

Rung 6's voltage law: three buses in a triangle of lines.

Two generators and one load; with a cycle in the graph the flows split by
impedance rather than by cost, which is what the KVL row enforces; one
line is extendable, so its rating is a decision.

`data/rung6_kvl/buses.csv`

```csv
name
a
b
c
```

`data/rung6_kvl/generators.csv`

```csv
name,bus,p_nom,marginal_cost
hydro,a,80.0,10.0
diesel6,b,80.0,50.0
```

`data/rung6_kvl/lines.csv`

```csv
name,bus0,bus1,x,r,s_nom,s_nom_extendable,capital_cost,s_nom_max,s_nom_set
ab,a,b,0.1,0.01,60.0,,,,
bc,b,c,0.2,0.01,60.0,,,,
ca,c,a,0.1,0.01,60.0,,,,
ca2,c,a,0.15,0.01,,True,10.0,40.0,30.0
```

`data/rung6_kvl/loads.csv`

```csv
name,bus,p_set
town,c,45.0
```

`data/rung6_kvl/timeseries.csv`

```csv
component,name,attribute,snapshot,value
Line,bc,s_set,0,10.0
```

</details>
<!-- reference:rung6_kvl:end -->

### Rung 7 — commitment

| PyPSA                                        | status | note                                                          |
| -------------------------------------------- | ------ | ------------------------------------------------------------- |
| [`{c}-status`, `-start_up`, `-shut_down`](#variable-domains) | done | Generator; a committable link is not taken up here |
| [`{c}-com-p-lower/upper`](#generator-com-p-lower) | done |                                                          |
| [`{c}-*-p-fixed-upper`](#generator-status-p-fixed-upper) | done | status, start and stop each at most one, as explicit rows |
| [`{c}-com-transition-start-up/shut-down`](#generator-com-transition-start-up) | done | first snapshot carries the initial status |
| [`{c}-com-up-time`, `-down-time`](#generator-com-up-time) | done | `sum_back(within=min_up_time)`                    |
| [`{c}-com-status-*-must_stay_up`](#generator-com-status-min_up_time_must_stay_up) | done | the window is a prep mask — `position()` takes a literal, not a parameter |
| [`stand_by_cost`, `start_up_cost`, `shut_down_cost`](#objective) | done |                                           |
| `{c}-com-p-before/-current/-partly-*`        | flag   | `linearized_unit_commitment`                                  |

<!-- reference:rung7_commitment:begin -->
> ✔ `pypsa 1.3.0` solves this rung's reference network through its own linopy model at objective `3550.0`, 74 rows — recorded by `examples/references/pypsa/rung7_commitment.py`. `lpspec 0.0.1a259` binds `examples/pypsa.yaml` against the same network and lands on the same objective (`parity.py`). Its instance is `data/base/` plus `data/rung7_commitment/`.

<details markdown="1">
<summary>What this rung adds, as data</summary>

Rung 7's commitment: a unit that pays to start, to stop, and to idle.

The base unit may not run below forty percent, was already on with two
snapshots of its minimum up time left to serve, pays for each start, and
ramps against its previous status — so the swing between it and the
peaker is a schedule, not a dispatch.

`data/rung7_commitment/generators.csv`

```csv
name,bus,committable,p_nom,marginal_cost,p_min_pu,min_up_time,min_down_time,up_time_before,ramp_limit_up,ramp_limit_down,ramp_limit_start_up,ramp_limit_shut_down,start_up_cost,shut_down_cost,stand_by_cost
uc,north,True,50.0,5.0,0.4,3,2,1,0.5,0.5,0.6,0.6,100.0,50.0,5.0
```

`data/rung7_commitment/loads.csv`

```csv
name,bus
swing7,north
```

`data/rung7_commitment/timeseries.csv`

```csv
component,name,attribute,snapshot,value
Load,swing7,p_set,0,25.0
Load,swing7,p_set,1,45.0
Load,swing7,p_set,2,45.0
Load,swing7,p_set,3,10.0
```

</details>
<!-- reference:rung7_commitment:end -->

### Rung 8 — modular and big-M

| PyPSA                                         | status | note                                                       |
| --------------------------------------------- | ------ | ---------------------------------------------------------- |
| [`{c}-n_mod`, `{c}-p_nom_modularity`](#generator-p_nom_modularity) | done |                                       |
| [`{c}-*-p_nom-variable-upper`](#generator-status-p_nom-variable-upper) | done | a modular unit is on only where a module is built |
| `{c}-*-p-fixed-upper`, modular                | not    | a fixed modular build is floored in data prep, see X1; its rows are the ordinary fix rows |
| [`{c}-com-mod-p-lower/upper`](#generator-com-mod-p-lower) | done | one module's share, times the status          |
| [`{c}-com-ext-p-*` (big-M)](#generator-com-ext-p-upper-cap) | done | a cap row beside a big-M row; `M` is the build cap at full availability, data prep |
| [`{c}-com-ext-p-lower-nonneg`](#generator-com-ext-p-lower-nonneg) | done | `(p_min_pu >= 0).all()` is prep        |
| [`{c}-p-ramp_limit_*-bigM`](#generator-p-ramp_limit_up-run-bigm) | done | run and start rows up, run and shut rows down, each with its initial block |

<!-- reference:rung8_modular_big_m:begin -->
> ✔ `pypsa 1.3.0` solves this rung's reference network through its own linopy model at objective `12005.0`, 129 rows — recorded by `examples/references/pypsa/rung8_modular_big_m.py`. `lpspec 0.0.1a259` binds `examples/pypsa.yaml` against the same network and lands on the same objective (`parity.py`). Its instance is `data/base/` plus `data/rung8_modular_big_m/`.

<details markdown="1">
<summary>What this rung adds, as data</summary>

Rung 8's modular and big-M builds: whole modules, and a build gated by a status.

The block plant is bought twenty-five megawatts at a time and gated by a
status, so its bounds are one module's share; the flexible plant is
extendable and committable with ramps, which is the pairing PyPSA's big-M
rows linearize.

`data/rung8_modular_big_m/buses.csv`

```csv
name
mill
```

`data/rung8_modular_big_m/generators.csv`

```csv
name,bus,p_nom_extendable,committable,p_nom_mod,p_nom_max,capital_cost,marginal_cost,p_min_pu,up_time_before,ramp_limit_up,ramp_limit_down,p_nom
block,mill,True,True,25.0,100.0,30.0,20.0,0.2,0,,,
flex,mill,True,True,,80.0,50.0,10.0,0.3,0,0.25,0.25,
backstop,mill,,,,,,300.0,,,,,200.0
```

`data/rung8_modular_big_m/loads.csv`

```csv
name,bus
mill_load,mill
```

`data/rung8_modular_big_m/timeseries.csv`

```csv
component,name,attribute,snapshot,value
Load,mill_load,p_set,0,40.0
Load,mill_load,p_set,1,80.0
Load,mill_load,p_set,2,120.0
Load,mill_load,p_set,3,60.0
```

</details>
<!-- reference:rung8_modular_big_m:end -->

### Rung 9 — multi-link and delay

| PyPSA                        | status | note                                          |
| ---------------------------- | ------ | --------------------------------------------- |
| [nodal balance, ports 2..n](#bus-nodal_balance) | done | port 2 states the pattern: a partial `Link_bus2` map, one more term per port |
| nodal balance, link delay    | open   | #75, a per-link edge kind                     |

<!-- reference:rung9_multilink:begin -->
> ✔ `pypsa 1.3.0` solves this rung's reference network through its own linopy model at objective `5200.0`, 68 rows — recorded by `examples/references/pypsa/rung9_multilink.py`. `lpspec 0.0.1a259` binds `examples/pypsa.yaml` against the same network and lands on the same objective (`parity.py`). Its instance is `data/base/` plus `data/rung9_multilink/`.

<details markdown="1">
<summary>What this rung adds, as data</summary>

Rung 9's multi-link: one gas flow delivering power and heat at two ports.

The CHP link withdraws gas at its first bus and injects at the other two
by its two efficiencies; the heat bus has no other supply, so the link
runs and the power bus tops up from imports.

`data/rung9_multilink/buses.csv`

```csv
name
gasb
power
heat
```

`data/rung9_multilink/generators.csv`

```csv
name,bus,p_nom,marginal_cost
well,gasb,100.0,5.0
grid_import,power,50.0,60.0
```

`data/rung9_multilink/links.csv`

```csv
name,bus0,bus1,bus2,efficiency,efficiency2,p_nom,marginal_cost
chp,gasb,power,heat,0.4,0.45,60.0,1.0
```

`data/rung9_multilink/loads.csv`

```csv
name,bus,p_set
homes,power,20.0
district,heat,18.0
```

</details>
<!-- reference:rung9_multilink:end -->

### Not on a rung

| PyPSA                          | status | note                                 |
| ------------------------------ | ------ | ------------------------------------ |
| `{c}-loss*`                    | flag   | `transmission_losses`                |
| `CVaR-*`                       | scope  | stochastic                           |

## Refusals

Where PyPSA refuses to build, parity means refusing too. None is a language
gap; each is a data check not made yet, and where it should live — language,
data prep, or harness — is one open question.

| PyPSA raises                                 | on                                                | here                    | note |
| -------------------------------------------- | ------------------------------------------------- | ----------------------- | ---- |
| `ValueError`, `constraints.py:1449`          | fixed modular `p_nom` not a multiple of `p_nom_mod` | builds a smaller plant | X1   |
| `ValueError`, `constraints.py:1192`          | load on a bus with nothing attached               | row not built, unserved | X2   |
| `ValueError`, `optimize.py:430`              | no component carries a cost                       | feasibility problem     | X3   |
| `NotImplementedError`, `global_constraints.py:339` | depletion with period weightings `!= 1`     | scope                   |      |
| `ValueError`/`RuntimeError`, losses          | `s_nom_max = inf`; secant cap                     | flag                    |      |

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
| $\mathrm{nonneg}$ | `Generator_p_min_pu_nonneg` (scalar) — true where no committable extendable generator's minimum-per-unit is negative — PyPSA's `(p_min_pu >= 0).all()`, data prep, one answer for the whole network |
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

$$p_{t,g} \ge 0 \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \mathrm{com}_{g} \wedge \mathrm{ext}_{g} \wedge \mathrm{nonneg} \wedge \neg \left( \mathrm{p}^{\mathrm{mod}}_{g} > 0 \right)$$

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
  description: "`primary_energy` — a `GlobalConstraint-{name}` row of this type holds its total at most its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'primary_energy' AND GlobalConstraint_sense == '<='
  expression: primary_energy <= GlobalConstraint_constant
```

$$\sum_{g \in \mathcal{G}} \sum_{t \in \mathcal{T}} p_{t,g} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \cdot \mathrm{a}_{o,g} - \left( \sum_{s \in \mathcal{S}} \sum_{t \in \mathcal{T}} \mathit{soc}_{t,s} \cdot \mathrm{last}_{t} \cdot \mathrm{a}^{h}_{o,s} \right) - \left( \sum_{v \in \mathcal{V}} \sum_{t \in \mathcal{T}} e_{t,v} \cdot \mathrm{last}_{t} \cdot \mathrm{a}^{e}_{o,v} \right) \le \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{primary\_energy} \wedge \mathrm{sense}_{o} = \text{<=}$$

### `primary_energy`

`GlobalConstraint_primary_energy_lb`

```yaml
GlobalConstraint_primary_energy_lb:
  description: "`primary_energy` — a `GlobalConstraint-{name}` row of this type holds its total at least its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'primary_energy' AND GlobalConstraint_sense == '>='
  expression: primary_energy >= GlobalConstraint_constant
```

$$\sum_{g \in \mathcal{G}} \sum_{t \in \mathcal{T}} p_{t,g} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \cdot \mathrm{a}_{o,g} - \left( \sum_{s \in \mathcal{S}} \sum_{t \in \mathcal{T}} \mathit{soc}_{t,s} \cdot \mathrm{last}_{t} \cdot \mathrm{a}^{h}_{o,s} \right) - \left( \sum_{v \in \mathcal{V}} \sum_{t \in \mathcal{T}} e_{t,v} \cdot \mathrm{last}_{t} \cdot \mathrm{a}^{e}_{o,v} \right) \ge \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{primary\_energy} \wedge \mathrm{sense}_{o} = \text{>=}$$

### `primary_energy`

`GlobalConstraint_primary_energy_eq`

```yaml
GlobalConstraint_primary_energy_eq:
  description: "`primary_energy` — a `GlobalConstraint-{name}` row of this type holds its total at its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'primary_energy' AND GlobalConstraint_sense == '=='
  expression: primary_energy == GlobalConstraint_constant
```

$$\sum_{g \in \mathcal{G}} \sum_{t \in \mathcal{T}} p_{t,g} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \cdot \mathrm{a}_{o,g} - \left( \sum_{s \in \mathcal{S}} \sum_{t \in \mathcal{T}} \mathit{soc}_{t,s} \cdot \mathrm{last}_{t} \cdot \mathrm{a}^{h}_{o,s} \right) - \left( \sum_{v \in \mathcal{V}} \sum_{t \in \mathcal{T}} e_{t,v} \cdot \mathrm{last}_{t} \cdot \mathrm{a}^{e}_{o,v} \right) = \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{primary\_energy} \wedge \mathrm{sense}_{o} = \text{==}$$

### `operational_limit`

`GlobalConstraint_operational_limit_ub`

```yaml
GlobalConstraint_operational_limit_ub:
  description: "`operational_limit` — a `GlobalConstraint-{name}` row of this type holds its total at most its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'operational_limit' AND GlobalConstraint_sense == '<='
  expression: operational_limit <= GlobalConstraint_constant
```

$$\sum_{g \in \mathcal{G}} \sum_{t \in \mathcal{T}} p_{t,g} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \cdot \mathrm{b}_{o,g} + \sum_{s \in \mathcal{S}} \sum_{t \in \mathcal{T}} h^{+}_{t,s} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \cdot \mathrm{b}^{h}_{o,s} + \sum_{v \in \mathcal{V}} \sum_{t \in \mathcal{T}} q_{t,v} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \cdot \mathrm{b}^{e}_{o,v} \le \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{operational\_limit} \wedge \mathrm{sense}_{o} = \text{<=}$$

### `operational_limit`

`GlobalConstraint_operational_limit_lb`

```yaml
GlobalConstraint_operational_limit_lb:
  description: "`operational_limit` — a `GlobalConstraint-{name}` row of this type holds its total at least its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'operational_limit' AND GlobalConstraint_sense == '>='
  expression: operational_limit >= GlobalConstraint_constant
```

$$\sum_{g \in \mathcal{G}} \sum_{t \in \mathcal{T}} p_{t,g} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \cdot \mathrm{b}_{o,g} + \sum_{s \in \mathcal{S}} \sum_{t \in \mathcal{T}} h^{+}_{t,s} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \cdot \mathrm{b}^{h}_{o,s} + \sum_{v \in \mathcal{V}} \sum_{t \in \mathcal{T}} q_{t,v} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \cdot \mathrm{b}^{e}_{o,v} \ge \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{operational\_limit} \wedge \mathrm{sense}_{o} = \text{>=}$$

### `operational_limit`

`GlobalConstraint_operational_limit_eq`

```yaml
GlobalConstraint_operational_limit_eq:
  description: "`operational_limit` — a `GlobalConstraint-{name}` row of this type holds its total at its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'operational_limit' AND GlobalConstraint_sense == '=='
  expression: operational_limit == GlobalConstraint_constant
```

$$\sum_{g \in \mathcal{G}} \sum_{t \in \mathcal{T}} p_{t,g} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \cdot \mathrm{b}_{o,g} + \sum_{s \in \mathcal{S}} \sum_{t \in \mathcal{T}} h^{+}_{t,s} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \cdot \mathrm{b}^{h}_{o,s} + \sum_{v \in \mathcal{V}} \sum_{t \in \mathcal{T}} q_{t,v} \cdot \mathrm{w}^{\mathrm{gen}}_{t} \cdot \mathrm{b}^{e}_{o,v} = \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{operational\_limit} \wedge \mathrm{sense}_{o} = \text{==}$$

### `transmission_volume_expansion_limit`

`GlobalConstraint_transmission_volume_expansion_limit_ub`

```yaml
GlobalConstraint_transmission_volume_expansion_limit_ub:
  description: "`transmission_volume_expansion_limit` — a `GlobalConstraint-{name}` row of this type holds its total at most its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'transmission_volume_expansion_limit' AND GlobalConstraint_sense == '<='
  expression: transmission_volume_expansion <= GlobalConstraint_constant
```

$$\sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{len}_{o,k} + \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{len}^{f}_{o,l} \le \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{transmission\_volume\_expansion\_limit} \wedge \mathrm{sense}_{o} = \text{<=}$$

### `transmission_volume_expansion_limit`

`GlobalConstraint_transmission_volume_expansion_limit_lb`

```yaml
GlobalConstraint_transmission_volume_expansion_limit_lb:
  description: "`transmission_volume_expansion_limit` — a `GlobalConstraint-{name}` row of this type holds its total at least its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'transmission_volume_expansion_limit' AND GlobalConstraint_sense == '>='
  expression: transmission_volume_expansion >= GlobalConstraint_constant
```

$$\sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{len}_{o,k} + \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{len}^{f}_{o,l} \ge \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{transmission\_volume\_expansion\_limit} \wedge \mathrm{sense}_{o} = \text{>=}$$

### `transmission_volume_expansion_limit`

`GlobalConstraint_transmission_volume_expansion_limit_eq`

```yaml
GlobalConstraint_transmission_volume_expansion_limit_eq:
  description: "`transmission_volume_expansion_limit` — a `GlobalConstraint-{name}` row of this type holds its total at its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'transmission_volume_expansion_limit' AND GlobalConstraint_sense == '=='
  expression: transmission_volume_expansion == GlobalConstraint_constant
```

$$\sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{len}_{o,k} + \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{len}^{f}_{o,l} = \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{transmission\_volume\_expansion\_limit} \wedge \mathrm{sense}_{o} = \text{==}$$

### `transmission_expansion_cost_limit`

`GlobalConstraint_transmission_expansion_cost_limit_ub`

```yaml
GlobalConstraint_transmission_expansion_cost_limit_ub:
  description: "`transmission_expansion_cost_limit` — a `GlobalConstraint-{name}` row of this type holds its total at most its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'transmission_expansion_cost_limit' AND GlobalConstraint_sense == '<='
  expression: transmission_expansion_cost <= GlobalConstraint_constant
```

$$\sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{cc}_{o,k} + \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{cc}^{f}_{o,l} \le \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{transmission\_expansion\_cost\_limit} \wedge \mathrm{sense}_{o} = \text{<=}$$

### `transmission_expansion_cost_limit`

`GlobalConstraint_transmission_expansion_cost_limit_lb`

```yaml
GlobalConstraint_transmission_expansion_cost_limit_lb:
  description: "`transmission_expansion_cost_limit` — a `GlobalConstraint-{name}` row of this type holds its total at least its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'transmission_expansion_cost_limit' AND GlobalConstraint_sense == '>='
  expression: transmission_expansion_cost >= GlobalConstraint_constant
```

$$\sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{cc}_{o,k} + \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{cc}^{f}_{o,l} \ge \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{transmission\_expansion\_cost\_limit} \wedge \mathrm{sense}_{o} = \text{>=}$$

### `transmission_expansion_cost_limit`

`GlobalConstraint_transmission_expansion_cost_limit_eq`

```yaml
GlobalConstraint_transmission_expansion_cost_limit_eq:
  description: "`transmission_expansion_cost_limit` — a `GlobalConstraint-{name}` row of this type holds its total at its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'transmission_expansion_cost_limit' AND GlobalConstraint_sense == '=='
  expression: transmission_expansion_cost == GlobalConstraint_constant
```

$$\sum_{k \in \mathcal{K}} S_{k} \cdot \mathrm{cc}_{o,k} + \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{cc}^{f}_{o,l} = \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{transmission\_expansion\_cost\_limit} \wedge \mathrm{sense}_{o} = \text{==}$$

### `tech_capacity_expansion_limit`

`GlobalConstraint_tech_capacity_expansion_limit_ub`

```yaml
GlobalConstraint_tech_capacity_expansion_limit_ub:
  description: "`tech_capacity_expansion_limit` — a `GlobalConstraint-{name}` row of this type holds its total at most its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'tech_capacity_expansion_limit' AND GlobalConstraint_sense == '<='
  expression: tech_capacity_expansion <= GlobalConstraint_constant
```

$$\sum_{g \in \mathcal{G}} P_{g} \cdot \mathrm{m}_{o,g} + \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{m}^{f}_{o,l} + \sum_{s \in \mathcal{S}} H_{s} \cdot \mathrm{m}^{h}_{o,s} + \sum_{v \in \mathcal{V}} E_{v} \cdot \mathrm{m}^{e}_{o,v} \le \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{tech\_capacity\_expansion\_limit} \wedge \mathrm{sense}_{o} = \text{<=}$$

### `tech_capacity_expansion_limit`

`GlobalConstraint_tech_capacity_expansion_limit_lb`

```yaml
GlobalConstraint_tech_capacity_expansion_limit_lb:
  description: "`tech_capacity_expansion_limit` — a `GlobalConstraint-{name}` row of this type holds its total at least its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'tech_capacity_expansion_limit' AND GlobalConstraint_sense == '>='
  expression: tech_capacity_expansion >= GlobalConstraint_constant
```

$$\sum_{g \in \mathcal{G}} P_{g} \cdot \mathrm{m}_{o,g} + \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{m}^{f}_{o,l} + \sum_{s \in \mathcal{S}} H_{s} \cdot \mathrm{m}^{h}_{o,s} + \sum_{v \in \mathcal{V}} E_{v} \cdot \mathrm{m}^{e}_{o,v} \ge \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{tech\_capacity\_expansion\_limit} \wedge \mathrm{sense}_{o} = \text{>=}$$

### `tech_capacity_expansion_limit`

`GlobalConstraint_tech_capacity_expansion_limit_eq`

```yaml
GlobalConstraint_tech_capacity_expansion_limit_eq:
  description: "`tech_capacity_expansion_limit` — a `GlobalConstraint-{name}` row of this type holds its total at its constant"
  foreach: [global_constraint]
  where: GlobalConstraint_type == 'tech_capacity_expansion_limit' AND GlobalConstraint_sense == '=='
  expression: tech_capacity_expansion == GlobalConstraint_constant
```

$$\sum_{g \in \mathcal{G}} P_{g} \cdot \mathrm{m}_{o,g} + \sum_{l \in \mathcal{L}} F_{l} \cdot \mathrm{m}^{f}_{o,l} + \sum_{s \in \mathcal{S}} H_{s} \cdot \mathrm{m}^{h}_{o,s} + \sum_{v \in \mathcal{V}} E_{v} \cdot \mathrm{m}^{e}_{o,v} = \mathrm{K}_{o} \qquad \forall\thinspace o \in \mathcal{O} \thinspace:\thinspace \mathrm{type}_{o} = \text{tech\_capacity\_expansion\_limit} \wedge \mathrm{sense}_{o} = \text{==}$$

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
