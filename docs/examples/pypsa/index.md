<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# PyPSA in 24 files

[PyPSA in one file](../pypsa.md) is `examples/pypsa.yaml`, one spec of some
four thousand lines. This is the same spec as 24 files under
`examples/pypsa/`, one per topic, and `merge` gives the one file back: the
two have one [canonical form](../../howto/compare.md).

Every fragment loads, prints and gets advice on its own. What it reads and does
not declare, it states under
[`given`](../../reference/language/declarations.md#given). A component that
puts something into a sum every component adds to, such as the bus balance or
the operating cost, names its share as an expression of its own and adds it
with a [`term`](../../reference/language/declarations.md#a-term-a-file-adds).
One fragment reads each sum with its description, so a term always lands. A
new component is one new file, and the network does not change.

The split is written by `tools/pypsa_split.py` from the one file and checked
against it, so the two cannot drift. It is a proof of concept: a decision on
which of the two is the source comes after both land.

## What each file says

Three kinds of file. A **component** owns PyPSA's class of that name: its
dimension, its data, its columns, its rows, and its share of each sum. The
committable classes, `Generator`, `Link` and `Process`, are cut by feature into
a file each for the class, its commitment, its ramping and its maintenance,
and the three sets read alike because PyPSA's rows do. A **reader** owns a sum
and the row that reads it: the network reads `Bus_injection`, power flow reads
`Cycle_angle_sum`. **Settings** holds what every topic reads, the weightings
and the flags, and the readings of the totals whose own readers, the cost, the
carriers and the global constraints, a model may leave out.

<!-- gallery:begin -->
### The sums

| Sum | Over | Read in | The terms, by the fragment that adds each |
| --- | --- | --- | --- |
| `scenario_opex` | `scenario` | [settings](settings.md) | [`Generator_opex`](generator.md), [`Generator_commitment_opex`](generator_commitment.md), [`Link_opex`](link.md), [`Link_commitment_opex`](link_commitment.md), [`Process_opex`](process.md), [`Process_commitment_opex`](process_commitment.md), [`StorageUnit_opex`](storage_unit.md), [`Store_opex`](store.md) |
| `Bus_injection` | `scenario, snapshot, bus` | [network](network.md) | [`Generator_injection`](generator.md), [`Line_injection`](line.md), [`Link_injection`](link.md), [`Load_injection`](load.md), [`Process_injection`](process.md), [`StorageUnit_injection`](storage_unit.md), [`Store_injection`](store.md), [`Transformer_injection`](transformer.md) |
| `tech_capacity_expansion` | `global_constraint` | [settings](settings.md) | [`Generator_tech_capacity_expansion`](generator.md), [`Line_tech_capacity_expansion`](line.md), [`Link_tech_capacity_expansion`](link.md), [`Process_tech_capacity_expansion`](process.md), [`StorageUnit_tech_capacity_expansion`](storage_unit.md), [`Store_tech_capacity_expansion`](store.md) |
| `Carrier_additions` | `period, carrier` | [settings](settings.md) | [`Generator_additions`](generator.md), [`Line_additions`](line.md), [`Link_additions`](link.md), [`Process_additions`](process.md), [`StorageUnit_additions`](storage_unit.md), [`Store_additions`](store.md) |
| `primary_energy` | `scenario, global_constraint` | [settings](settings.md) | [`Generator_primary_energy`](generator.md), [`StorageUnit_primary_energy`](storage_unit.md), [`Store_primary_energy`](store.md) |
| `operational_limit` | `scenario, global_constraint` | [settings](settings.md) | [`Generator_operational_limit`](generator.md), [`StorageUnit_operational_limit`](storage_unit.md), [`Store_operational_limit`](store.md) |
| `transmission_volume_expansion` | `scenario, global_constraint` | [settings](settings.md) | [`Line_transmission_volume_expansion`](line.md), [`Link_transmission_volume_expansion`](link.md) |
| `transmission_expansion_cost` | `scenario, global_constraint` | [settings](settings.md) | [`Line_transmission_expansion_cost`](line.md), [`Link_transmission_expansion_cost`](link.md) |
| `Cycle_angle_sum` | `scenario, snapshot, cycle` | [power_flow](power_flow.md) | [`Line_angle_sum`](line.md), [`Transformer_angle_sum`](transformer.md) |

### The fragments

| Fragment | Parameters | Variables | Constraints | Reads | Adds to |
| --- | --- | --- | --- | --- | --- |
| [carrier](carrier.md) | 2 | 0 | 1 | 1 |  |
| [cost](cost.md) | 1 | 3 | 2 | 3 |  |
| [generator](generator.md) | 23 | 3 | 11 | 16 | `primary_energy`, `operational_limit`, `tech_capacity_expansion`, `scenario_opex`, `Carrier_additions`, `Bus_injection` |
| [generator_commitment](generator_commitment.md) | 10 | 3 | 20 | 17 | `scenario_opex` |
| [generator_maintenance](generator_maintenance.md) | 5 | 4 | 13 | 9 |  |
| [generator_ramping](generator_ramping.md) | 5 | 0 | 6 | 14 |  |
| [global_constraints](global_constraints.md) | 3 | 0 | 15 | 6 |  |
| [line](line.md) | 18 | 3 | 11 | 8 | `transmission_volume_expansion`, `transmission_expansion_cost`, `tech_capacity_expansion`, `Carrier_additions`, `Bus_injection`, `Cycle_angle_sum` |
| [link](link.md) | 23 | 3 | 9 | 14 | `transmission_volume_expansion`, `transmission_expansion_cost`, `tech_capacity_expansion`, `scenario_opex`, `Carrier_additions`, `Bus_injection` |
| [link_commitment](link_commitment.md) | 10 | 3 | 20 | 17 | `scenario_opex` |
| [link_maintenance](link_maintenance.md) | 5 | 4 | 13 | 9 |  |
| [link_ramping](link_ramping.md) | 5 | 0 | 6 | 14 |  |
| [load](load.md) | 3 | 0 | 0 | 1 | `Bus_injection` |
| [network](network.md) | 0 | 0 | 1 | 1 |  |
| [power_flow](power_flow.md) | 0 | 0 | 1 | 1 |  |
| [process](process.md) | 21 | 3 | 9 | 12 | `tech_capacity_expansion`, `scenario_opex`, `Carrier_additions`, `Bus_injection` |
| [process_commitment](process_commitment.md) | 10 | 3 | 20 | 17 | `scenario_opex` |
| [process_maintenance](process_maintenance.md) | 5 | 4 | 13 | 9 |  |
| [process_ramping](process_ramping.md) | 5 | 0 | 6 | 14 |  |
| [security](security.md) | 2 | 0 | 8 | 10 |  |
| [settings](settings.md) | 9 | 0 | 0 | 7 |  |
| [storage_unit](storage_unit.md) | 34 | 5 | 20 | 14 | `primary_energy`, `operational_limit`, `tech_capacity_expansion`, `scenario_opex`, `Carrier_additions`, `Bus_injection` |
| [store](store.md) | 27 | 3 | 10 | 14 | `primary_energy`, `operational_limit`, `tech_capacity_expansion`, `scenario_opex`, `Carrier_additions`, `Bus_injection` |
| [transformer](transformer.md) | 19 | 4 | 11 | 4 | `Bus_injection`, `Cycle_angle_sum` |
<!-- gallery:end -->

## Leaving a file out

A model may leave a component family out, or the cost, the carriers, the
global constraints or security, and what is left is a whole model: nothing
stays under `given:`. It may not leave the network or power flow out while a
component is in, because the component's terms would land on no name, and
`merge` says so.
