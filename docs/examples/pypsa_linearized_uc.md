<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# PyPSA, the relaxed commitment

Rungs 12, 44 and 47 of [PyPSA in one file](pypsa.md): `n.optimize(linearized_unit_commitment=True)`, stated on rungs 1 and 7
in a file of its own. Each network is the spine plus the script's own additions.

The file covers generators, links and loads with a fixed build, in one
scenario, with every asset active in every snapshot. Only a generator is
committable. A committable link or process, an extendable build, scenarios and
`active` are out of this file's scope. [PyPSA in one file](pypsa.md) states
them for the integer run, and the keyword relaxes them in the same way.

## Rung 12 — linearized unit commitment

| PyPSA | status | note |
| --- | --- | --- |
| [`Generator-status`, `-start_up`, `-shut_down`](#variable-domains) | done | shares in [0, 1] |
| [`Generator-com-p-before`](#generator-com-p-before) | done | where start and stop cost the same — a data-prep bool |
| [`Generator-com-p-current`](#generator-com-p-current) | done | |
| [`Generator-com-partly-start-up`](#generator-com-partly-start-up) | done | |
| [`Generator-com-partly-shut-down`](#generator-com-partly-shut-down) | done | |

<!-- reference:rung_12_linearized_uc:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `7775.0`, 128 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_12_linearized_uc.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 12: linearized unit commitment — the status a share in [0, 1], stated by `pypsa_linearized_uc.yaml`."""

from __future__ import annotations

import spine

MODEL = 'pypsa_linearized_uc.yaml'
OPTIMIZE = {'linearized_unit_commitment': True}


def build():
    """The spine plus two committable units, one whose start and stop cost the same, so PyPSA tightens its relaxation."""
    n = spine.build()
    n.add(
        'Generator',
        'uc12',
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
        shut_down_cost=100,
        stand_by_cost=5,
    )
    n.add(
        'Generator',
        'cold12',
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
        ramp_limit_start_up=0.7,
        ramp_limit_shut_down=0.7,
        start_up_cost=80,
        shut_down_cost=40,
    )
    n.add('Load', 'swing12', bus='north', p_set=[25, 45, 45, 10])
    return n
```

</details>
<!-- reference:rung_12_linearized_uc:end -->

## Rung 44 — the integer file's commitment rows, relaxed

`n.optimize(linearized_unit_commitment=True)` builds the same commitment rows as
the integer run, except the four tightening rows: the keyword only relaxes the
status, start and stop to shares in [0, 1] (`variables.py:81-88`) and adds the
tightening rows (`constraints.py:650`). So this file states each row that
[PyPSA in one file](pypsa.md) states for a fixed committable generator:

- A unit still serving the down time it brought in stays off
  (`constraints.py:622-628`).
- A ramp row stands where a unit has a ramp limit or only a start-up or
  shut-down ramp, and a missing limit reads as the full build
  (`constraints.py:1046-1055`). The earlier file built no row for a start-up
  ramp alone, and read a missing start-up or shut-down ramp as `0`, which kept
  a unit that came in off from starting.
- A maintainable unit is taken off for its events. The maintenance start stays
  a binary under the keyword (`variables.py:234-259`), and the product of
  status and maintenance enters the commitment rows through the `maint-status`
  rows (`constraints.py:425-458`). A maintainable unit that is not committable
  loses the same share of its fixed rows (`constraints.py:135-145`).

The rung adds five cheap units under a swinging load. A start costs more than a
stop, so PyPSA does not tighten them and the rung isolates these rows. Each
binds: PyPSA solves to `7400.0`. Without the brought-in down time it solves to
`6540.0`; without the start-up ramp, to `7164.0`; with the missing start-up and
shut-down ramps read as `0`, to `8060.0`; with the committable unit not
maintainable, to `7310.0`; with the fixed unit not maintainable, to `7100.0`.

| PyPSA | status | note |
| --- | --- | --- |
| [`Generator-com-status-min_down_time_must_stay_up`](#generator-com-status-min_down_time_must_stay_up) | done | |
| [`Generator-p-ramp_limit_up`](#generator-p-ramp_limit_up), [`-down`](#generator-p-ramp_limit_down) for a start-up or shut-down ramp alone, and a missing limit | done | `Generator_ramp_up_rate` and the other three rates read a missing limit as `1` |
| [`Generator-maint-*`](#generator-maint-event-count), [`Generator-maint-status-*`](#generator-maint-status-le-status) | done | fixed units only, as the file states no extendable build |
| [`Generator-com-p-lower`](#generator-com-p-lower), [`-upper`](#generator-com-p-upper), [`Generator-fix-p-lower`](#generator-fix-p-lower), [`-upper`](#generator-fix-p-upper) in maintenance | done | |

<!-- reference:rung_44_linearized_commitment:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `7400.0`, 191 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_44_linearized_commitment.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 44: linearized commitment with the rows the integer file has — a unit that must stay down, ramps read at the full build where a limit is missing, and maintenance."""

from __future__ import annotations

import spine

MODEL = 'pypsa_linearized_uc.yaml'
OPTIMIZE = {'linearized_unit_commitment': True}

#: a start costs more than a stop, so PyPSA does not tighten these units and the rung isolates the rows it adds
UNTIGHTENED = {'committable': True, 'up_time_before': 0, 'start_up_cost': 1}


def build():
    """The spine plus five cheap units on a north bus with a swinging load: each carries one of the rows under review."""
    n = spine.build()
    n.add(
        'Generator',
        'down44',
        bus='north',
        p_nom=40,
        marginal_cost=2,
        min_down_time=3,
        down_time_before=1,
        **UNTIGHTENED,
    )
    n.add('Generator', 'pulse44', bus='north', p_nom=40, marginal_cost=3, ramp_limit_start_up=0.4, **UNTIGHTENED)
    n.add(
        'Generator',
        'ramp44',
        bus='north',
        p_nom=40,
        marginal_cost=4,
        ramp_limit_up=0.5,
        ramp_limit_down=0.5,
        **UNTIGHTENED,
    )
    n.add(
        'Generator',
        'maint44',
        bus='north',
        p_nom=40,
        p_min_pu=0.3,
        marginal_cost=5,
        maintainable=True,
        maintenance_duration=2,
        **UNTIGHTENED,
    )
    n.add('Generator', 'fixed44', bus='north', p_nom=20, marginal_cost=1, maintainable=True, maintenance_duration=1)
    n.add('Load', 'swing44', bus='north', p_set=[40, 120, 160, 60])
    return n
```

</details>
<!-- reference:rung_44_linearized_commitment:end -->

## Rung 47 — ramps and signs, as the integer file states them

This rung brings five rows of [PyPSA in one file](pypsa.md) into this file,
each on the fixed builds of this file's surface:

- The four tightening rows read each ramp limit filled to the full build where
  it is missing (`constraints.py:313-318`). They read `Generator_ramp_up_rate`
  and the other three rates. The earlier file read a missing limit as `0`.
- A ramp limit is given per snapshot and read at the later of the two
  snapshots (`constraints.py:1040-1041`). A row is absent at a snapshot where
  neither the limit nor the start-up or shut-down ramp has a value
  (`constraints.py:1046-1047`, `1136`, `1154`).
- A unit that came in running with a `p_init` ramps from it into the first
  snapshot (`constraints.py:1091-1094`, `1102-1104`). Where `p_init` has no
  value, the unit carries no ramp row at the first snapshot.
- A unit that is not committable carries ramp rows with its status fixed at
  `1` (`constraints.py:1073-1079`). The assumption
  `Generator_came_in_running_unless_committable` refuses such a unit that came
  in off, as the integer file does.
- Each generator and load term enters the bus balance with its component's
  `sign` (`constraints.py:1428-1429`, `:1538`).

The rung adds a relax bus with a tightened unit that has only start-up and
shut-down ramps, a committable unit whose ramp limit lifts at the third
snapshot, a dear committable unit that came in running at `p_init=40`, a fixed
unit with ramp limits, a unit of sign `-1`, a load of sign `1` and a dear
backup. Each binds: PyPSA solves to `12862.5`. With the missing limits read as
`0` in the two partly rows, it solves to `14085.64`. With the ramp limit at
`0.25` in every snapshot, it solves to `14554.75`. Without the `p_init`, it
solves to `8437.5`. Without the fixed unit's ramp limits, it solves to
`12800.0`. With the unit's sign at `1`, it solves to `12592.5`. With the load's
sign at `-1`, it solves to `13887.5`.

| PyPSA | status | note |
| --- | --- | --- |
| [`Generator-com-p-before`](#generator-com-p-before), [`-current`](#generator-com-p-current), [`-partly-start-up`](#generator-com-partly-start-up), [`-partly-shut-down`](#generator-com-partly-shut-down) with a missing ramp limit | done | the four rates read a missing limit as `1` |
| [`Generator-p-ramp_limit_up`](#generator-p-ramp_limit_up), [`-down`](#generator-p-ramp_limit_down) per snapshot | done | `Generator_ramp_limit_up` and `-down` over `[snapshot, generator]` |
| [`Generator-p-ramp_limit_up`](#generator-p-ramp_limit_up), [`-down`](#generator-p-ramp_limit_down) at the first snapshot from `p_init` | done | `Generator_previous_p` opens at `Generator_status_initial * Generator_p_init` |
| [`Generator-p-ramp_limit_up`](#generator-p-ramp_limit_up), [`-down`](#generator-p-ramp_limit_down) for a unit that is not committable | done | `Generator_ramp_up_allowance` and `-down` read the status as `1` |
| [`Bus-nodal_balance`](#bus-nodal_balance) with `sign` | done | `Generator_sign` and `Load_sign` |

<!-- reference:rung_47_linearized_ramps:begin -->
> ✔ `pypsa 1.3.0` solves this rung's network at objective `12862.5`, 179 rows.

<details markdown="1">
<summary>The network, as PyPSA code</summary>

`rung_47_linearized_ramps.py`

```python
# SPDX-FileCopyrightText: mathspec Contributors
#
# SPDX-License-Identifier: MIT

"""Rung 47: the relaxed file's ramps and signs — tightening at the full build, a ramp limit per snapshot, a `p_init`, a unit that is not committable, and a sign."""

from __future__ import annotations

import math

import spine

MODEL = 'pypsa_linearized_uc.yaml'
OPTIMIZE = {'linearized_unit_commitment': True}


def build():
    """The spine plus a relax bus: five units that each carry one of the rows under review, a feeding load and a dear backup."""
    n = spine.build()
    n.add('Bus', 'relax')
    n.add(
        'Generator',
        'tight47',
        bus='relax',
        committable=True,
        p_nom=50,
        p_min_pu=0.2,
        marginal_cost=2,
        up_time_before=0,
        ramp_limit_start_up=0.5,
        ramp_limit_shut_down=0.5,
        start_up_cost=10,
        shut_down_cost=10,
    )
    n.add(
        'Generator',
        'steep47',
        bus='relax',
        committable=True,
        p_nom=40,
        marginal_cost=3,
        start_up_cost=1,
        ramp_limit_up=[0.25, 0.25, math.nan, 0.25],
        ramp_limit_down=[0.25, 0.25, 0.25, math.nan],
        ramp_limit_start_up=0.25,
    )
    n.add(
        'Generator',
        'warm47',
        bus='relax',
        committable=True,
        p_nom=40,
        marginal_cost=50,
        start_up_cost=1,
        p_init=40,
        ramp_limit_down=0.25,
        ramp_limit_shut_down=0.5,
    )
    n.add('Generator', 'fixed47', bus='relax', p_nom=60, marginal_cost=1, ramp_limit_up=0.25, ramp_limit_down=0.25)
    n.add('Generator', 'sink47', bus='relax', p_nom=20, p_min_pu=0.5, sign=-1)
    n.add('Generator', 'backup47', bus='relax', p_nom=300, marginal_cost=500)
    n.add('Load', 'feed47', bus='relax', p_set=10, sign=1)
    n.add('Load', 'swing47', bus='relax', p_set=[60, 60, 140, 40])
    return n
```

</details>
<!-- reference:rung_47_linearized_ramps:end -->

## The file

<!-- gallery:begin -->
The relaxed class of a plain `n.optimize()`: `linearized_unit_commitment`, stated on rung 1's transport surface in a file of its own. The status, its starts and its stops are shares in \[0, 1\] rather than binaries — a domain is the model's, not the data's — and four rows PyPSA adds only under the keyword tighten the relaxation where a unit's start and stop cost the same. The surface is generators, links and loads with a fixed build, in one scenario, every asset active in every snapshot, and only a generator committable. `examples/pypsa.yaml` stays the integer one, and states the rest: a committable link or process, an extendable build, scenarios and `active`.

#### Sets

| Symbol | Meaning |
|---|---|
| $`\mathcal{T}`$ | index $`t`$ — `snapshot` with $`\mathrm{Generator\_maintenance\_cover} \subseteq \mathcal{G} \times \mathcal{T} \times \mathcal{T}`$ — dispatch periods |
| $`\mathcal{N}`$ | index $`n`$ — `bus` with $`\mathrm{Generator\_bus}: \mathcal{G} \to \mathcal{N},\ \mathrm{Link\_bus0}: \mathcal{L} \to \mathcal{N},\ \mathrm{Link\_output\_bus}: \mathcal{O} \to \mathcal{N},\ \mathrm{Load\_bus}: \mathcal{D} \to \mathcal{N}`$ — network nodes |
| $`\mathcal{G}`$ | index $`g`$ — `generator` with $`\mathrm{Generator\_bus}: \mathcal{G} \to \mathcal{N},\ \mathrm{Generator\_maintenance\_cover} \subseteq \mathcal{G} \times \mathcal{T} \times \mathcal{T}`$ — generating units, each on one bus |
| $`\mathcal{L}`$ | index $`l`$ — `link` with $`\mathrm{Link\_bus0}: \mathcal{L} \to \mathcal{N},\ \mathrm{Link\_output\_link}: \mathcal{O} \to \mathcal{L}`$ — controllable connections, each from one bus to the buses it delivers to |
| $`\mathcal{O}`$ | index $`o`$ — `link_output` with $`\mathrm{Link\_output\_link}: \mathcal{O} \to \mathcal{L},\ \mathrm{Link\_output\_bus}: \mathcal{O} \to \mathcal{N}`$ — a link's output ports, one label per port a link declares — PyPSA's `bus1`, `bus2`, … columns read long, so a link of any number of output ports is one term in the balance, data prep |
| $`\mathcal{D}`$ | index $`d`$ — `load` with $`\mathrm{Load\_bus}: \mathcal{D} \to \mathcal{N}`$ — demands, each on one bus |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\mathrm{w}`$ | `snapshot_weightings_objective` over $`\mathcal{T}`$ — PyPSA's `snapshot_weightings.objective` — hours a snapshot stands for in the cost |
| $`\mathrm{w}^{\mathrm{gen}}`$ | `snapshot_weightings_generators` over $`\mathcal{T}`$ — PyPSA's `snapshot_weightings.generators` — hours a snapshot stands for in an energy total |
| $`\mathrm{p}^{\mathrm{nom}}`$ | `Generator_p_nom` over $`\mathcal{G}`$ — nominal power |
| $`\underline{\mathrm{p}}`$ | `Generator_p_min_pu` over $`\mathcal{T} \times \mathcal{G}`$ — least output, per unit of nominal power |
| $`\overline{\mathrm{p}}`$ | `Generator_p_max_pu` over $`\mathcal{T} \times \mathcal{G}`$ — most output, per unit of nominal power — an availability profile |
| $`\mathrm{c}`$ | `Generator_marginal_cost` over $`\mathcal{T} \times \mathcal{G}`$ — cost of one unit of output |
| $`\mathrm{sgn}`$ | `Generator_sign` over $`\mathcal{G}`$ — the sign output enters its bus's balance with — PyPSA's `sign`, `1` unless given, `-1` for a unit that draws power |
| $`\mathrm{f}^{\mathrm{nom}}`$ | `Link_p_nom` over $`\mathcal{L}`$ — nominal power |
| $`\underline{\mathrm{f}}`$ | `Link_p_min_pu` over $`\mathcal{T} \times \mathcal{L}`$ — least flow, per unit of nominal power — negative for a link that carries both ways |
| $`\overline{\mathrm{f}}`$ | `Link_p_max_pu` over $`\mathcal{T} \times \mathcal{L}`$ — most flow, per unit of nominal power |
| $`\eta`$ | `Link_efficiency` over $`\mathcal{O}`$ — share of the flow that arrives at an output port, PyPSA's `efficiency`, `efficiency2`, … read long — negative where that port consumes rather than delivers |
| $`\mathrm{c}^{f}`$ | `Link_marginal_cost` over $`\mathcal{T} \times \mathcal{L}`$ — cost of one unit of flow |
| $`\mathrm{load}`$ | `Load_p_set` over $`\mathcal{T} \times \mathcal{D}`$ — demand |
| $`\mathrm{sgn}^{\mathrm{load}}`$ | `Load_sign` over $`\mathcal{D}`$ — the sign a load's demand enters its bus's balance with — PyPSA's `sign`, `-1` unless given, `1` for a load that feeds its bus |
| $`\mathrm{com}`$ | `Generator_committable` over $`\mathcal{G}`$ — whether output is gated by an on/off status decision |
| $`\mathrm{ru}`$ | `Generator_ramp_limit_up` over $`\mathcal{T} \times \mathcal{G}`$ — most a generator may raise its output between snapshots, per unit of nominal power; no value means no limit — read at the later of the two snapshots, so the limit may change over time |
| $`\mathrm{rd}`$ | `Generator_ramp_limit_down` over $`\mathcal{T} \times \mathcal{G}`$ — most a generator may lower its output between snapshots, per unit of nominal power; no value means no limit — read at the later of the two snapshots, so the limit may change over time |
| $`\mathrm{ru}^{\mathrm{up}}`$ | `Generator_ramp_limit_start_up` over $`\mathcal{G}`$ — most output in the snapshot a unit starts, per unit of nominal power |
| $`\mathrm{rd}^{\mathrm{dn}}`$ | `Generator_ramp_limit_shut_down` over $`\mathcal{G}`$ — most output in the snapshot before a unit stops, per unit of nominal power |
| $`\mathrm{UT}`$ | `Generator_min_up_time` over $`\mathcal{G}`$ — least snapshots a unit stays on once started |
| $`\mathrm{DT}`$ | `Generator_min_down_time` over $`\mathcal{G}`$ — least snapshots a unit stays off once stopped |
| $`\mathrm{u}^{0}`$ | `Generator_status_initial` over $`\mathcal{G}`$ — one where the unit was on before the first snapshot, zero where off — PyPSA's `up_time_before > 0`, data prep |
| $`\mathrm{p}^{0}`$ | `Generator_p_init` over $`\mathcal{G}`$ — the output a unit brought into the horizon — PyPSA's `p_init`, read only where the unit came in running; no value means it is unknown, so the unit carries no ramp row at the first snapshot |
| $`\mathrm{hold}`$ | `Generator_must_stay_up` over $`\mathcal{T} \times \mathcal{G}`$ — true while the up time a unit brought into the horizon still binds — data prep, since `position()` compares against a literal rather than a parameter |
| $`\mathrm{rest}`$ | `Generator_must_stay_down` over $`\mathcal{T} \times \mathcal{G}`$ — true while the down time a unit brought into the horizon still binds — PyPSA's `min_down_time - down_time_before` snapshots, where `down_time_before > 0`, data prep for the same reason |
| $`\mathrm{c}^{\mathrm{up}}`$ | `Generator_start_up_cost` over $`\mathcal{G}`$ — cost of one start |
| $`\mathrm{c}^{\mathrm{dn}}`$ | `Generator_shut_down_cost` over $`\mathcal{G}`$ — cost of one stop |
| $`\mathrm{c}^{\mathrm{on}}`$ | `Generator_stand_by_cost` over $`\mathcal{T} \times \mathcal{G}`$ — cost of one snapshot spent on |
| $`\mathrm{tight}`$ | `Generator_partly_tightened` over $`\mathcal{G}`$ — whether the four tightening rows below apply — PyPSA adds them only where a unit's start-up and shut-down costs are equal; two parameters cannot be compared in a `where`, so the equality is data prep |
| $`\mathrm{mnt}`$ | `Generator_maintainable` over $`\mathcal{G}`$ — whether a generator must be taken off for maintenance within the horizon |
| $`\gamma`$ | `Generator_maintenance_pu` over $`\mathcal{G}`$ — the share of the build a maintenance event takes off |
| $`\mathrm{n}^{\mathrm{mnt}}`$ | `Generator_maintenance_events` over $`\mathcal{G}`$ — how many maintenance events the horizon holds |
| $`\tau^{\mathrm{mnt}}`$ | `Generator_maintenance_duration` over $`\mathcal{G}`$ — the hours of generator weightings one maintenance event covers — PyPSA's `maintenance_duration`; no value where the generator is not maintainable. No row reads it: data prep turns it into `Generator_maintenance_cover` and `Generator_maintenance_start_blocked`, and the assumptions hold it to the horizon |
| $`\mathrm{blk}`$ | `Generator_maintenance_start_blocked` over $`\mathcal{T} \times \mathcal{G}`$ — true where no maintenance event may start, because the snapshots it would cover run past the end of the horizon or into one the generator does not stand in — PyPSA's `active & ~valid`, from `maintenance_duration` and the generator weightings, data prep |

#### Variables

| Symbol | Meaning |
|---|---|
| $`p`$ | `Generator_p` over $`\mathcal{T} \times \mathcal{G}`$ — `Generator-p` — output of a generator in a snapshot |
| $`f`$ | `Link_p` over $`\mathcal{T} \times \mathcal{L}`$ — `Link-p` — PyPSA's `p0`, the flow measured at the `Link_bus0` end: a positive value withdraws there and injects at every bus the link's output ports deliver to |
| $`u`$ | `Generator_status` over $`\mathcal{T} \times \mathcal{G}`$ — `Generator-status` — how much of a committable unit is on, a share in \[0, 1\] rather than a binary: the relaxation `linearized_unit_commitment` solves |
| $`\mathit{up}`$ | `Generator_start_up` over $`\mathcal{T} \times \mathcal{G}`$ — `Generator-start_up` — how much of a committable unit turns on this snapshot |
| $`\mathit{dn}`$ | `Generator_shut_down` over $`\mathcal{T} \times \mathcal{G}`$ — `Generator-shut_down` — how much of a committable unit turns off this snapshot |
| $`\mu`$ | `Generator_maintenance` over $`\mathcal{T} \times \mathcal{G}`$ — `Generator-maintenance` — whether a maintainable generator is in maintenance: continuous, and one exactly where an event covers the snapshot |
| $`\mu^{\mathrm{up}}`$ | `Generator_maintenance_start` over $`\mathcal{T} \times \mathcal{G}`$ — `Generator-maintenance_start` — whether a maintenance event starts in this snapshot — a binary, which the keyword does not relax |
| $`\mu^{u}`$ | `Generator_maintenance_status` over $`\mathcal{T} \times \mathcal{G}`$ — `Generator-maintenance_status` — the status while in maintenance, zero otherwise: the product the `maint-status` rows linearize, so a unit in maintenance may also be off |

#### Definitions

| Symbol | Meaning |
|---|---|
| $`\overleftarrow{u}`$ | `Generator_previous_status` over $`\mathcal{T} \times \mathcal{G}`$ — the commitment state a generator carries into a snapshot — the state it brought into the horizon at the first, the previous snapshot's after that |
| $`\overleftarrow{p}`$ | `Generator_previous_p` over $`\mathcal{T} \times \mathcal{G}`$ — the output a generator carries into a snapshot — at the first, the `p_init` it brought in where it came in running and nothing where it came in off; the previous snapshot's after that |
| $`\widetilde{\mathrm{ru}}`$ | `Generator_ramp_up_rate` over $`\mathcal{T} \times \mathcal{G}`$ — the ramp limit a unit's up row reads — PyPSA's `ramp_limit_up`, or the full build where it has none, since a start-up ramp alone builds the row |
| $`\widetilde{\mathrm{rd}}`$ | `Generator_ramp_down_rate` over $`\mathcal{T} \times \mathcal{G}`$ — the ramp limit a unit's down row reads — PyPSA's `ramp_limit_down`, or the full build where it has none, since a shut-down ramp alone builds the row |
| $`\widetilde{\mathrm{ru}}^{\mathrm{up}}`$ | `Generator_start_up_rate` over $`\mathcal{G}`$ — the start-up ramp a unit's up row reads — PyPSA's `ramp_limit_start_up`, or the full build where it has none |
| $`\widetilde{\mathrm{rd}}^{\mathrm{dn}}`$ | `Generator_shut_down_rate` over $`\mathcal{G}`$ — the shut-down ramp a unit's down row reads — PyPSA's `ramp_limit_shut_down`, or the full build where it has none |
| $`\Delta^{+}`$ | `Generator_ramp_up_allowance` over $`\mathcal{T} \times \mathcal{G}`$ — how far a generator may raise output between two snapshots — its ramp limit of the build while it stays on, plus its start-up ramp in the snapshot it turns on |
| $`\Delta^{-}`$ | `Generator_ramp_down_allowance` over $`\mathcal{T} \times \mathcal{G}`$ — how far a generator may lower output between two snapshots — its ramp limit of the build while it stays on, plus its shut-down ramp in the snapshot it turns off |

$`\mathrm{pos}(t)`$ denotes where index $`t`$ sits along its dimension's own order — the order `shift` steps along, not the order labels sort in — counted from $`0`$. The index itself stays the coordinate, so $`t`$ compares against labels and $`\mathrm{pos}(t)`$ against positions.

### Objective

```yaml
objective:
  sense: minimize
  description: operating cost by weighted snapshot, plus what starts, stops and standing by cost
  expression: >-
    sum(Generator_p * Generator_marginal_cost * snapshot_weightings_objective)
    + sum(Link_p * Link_marginal_cost * snapshot_weightings_objective)
    + sum(Generator_status * Generator_stand_by_cost * snapshot_weightings_objective)
    + sum(Generator_start_up * Generator_start_up_cost)
    + sum(Generator_shut_down * Generator_shut_down_cost)
```

```math
\min \sum_{t \in \mathcal{T},\ g \in \mathcal{G}} p_{t,g} \cdot \mathrm{c}_{t,g} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\ l \in \mathcal{L}} f_{t,l} \cdot \mathrm{c}^{f}_{t,l} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\ g \in \mathcal{G}} u_{t,g} \cdot \mathrm{c}^{\mathrm{on}}_{t,g} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\ g \in \mathcal{G}} \mathit{up}_{t,g} \cdot \mathrm{c}^{\mathrm{up}}_{g} + \sum_{t \in \mathcal{T},\ g \in \mathcal{G}} \mathit{dn}_{t,g} \cdot \mathrm{c}^{\mathrm{dn}}_{g}
```

### `Generator-fix-p-lower`

`Generator_fix_p_lower`

```yaml
Generator_fix_p_lower:
  description: "`Generator-fix-p-lower` — a generator outputs at least its minimum"
  dims: [snapshot, generator]
  where: not Generator_committable
  expression: Generator_p >= Generator_p_min_pu * Generator_p_nom * (1 - Generator_maintenance_pu * Generator_maintenance)
```

```math
p_{t,g} \ge \underline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot \left( 1 - \gamma_{g} \cdot \mu_{t,g} \right) \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \neg \mathrm{com}_{g}
```

### `Generator-fix-p-upper`

`Generator_fix_p_upper`

```yaml
Generator_fix_p_upper:
  description: "`Generator-fix-p-upper` — a generator outputs at most what is available"
  dims: [snapshot, generator]
  where: not Generator_committable
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom * (1 - Generator_maintenance_pu * Generator_maintenance)
```

```math
p_{t,g} \le \overline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot \left( 1 - \gamma_{g} \cdot \mu_{t,g} \right) \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \neg \mathrm{com}_{g}
```

### `Link-fix-p-lower`

`Link_fix_p_lower`

```yaml
Link_fix_p_lower:
  description: "`Link-fix-p-lower` — a link carries at least its minimum, negative for the other way"
  dims: [snapshot, link]
  expression: Link_p >= Link_p_min_pu * Link_p_nom
```

```math
f_{t,l} \ge \underline{\mathrm{f}}_{t,l} \cdot \mathrm{f}^{\mathrm{nom}}_{l} \qquad \forall\, t \in \mathcal{T},\ l \in \mathcal{L}
```

### `Link-fix-p-upper`

`Link_fix_p_upper`

```yaml
Link_fix_p_upper:
  description: "`Link-fix-p-upper` — a link carries at most its nominal power"
  dims: [snapshot, link]
  expression: Link_p <= Link_p_max_pu * Link_p_nom
```

```math
f_{t,l} \le \overline{\mathrm{f}}_{t,l} \cdot \mathrm{f}^{\mathrm{nom}}_{l} \qquad \forall\, t \in \mathcal{T},\ l \in \mathcal{L}
```

### `Bus-nodal_balance`

`Bus_nodal_balance`

```yaml
Bus_nodal_balance:
  description: >-
    `Bus-nodal_balance` — what is generated at a bus, less what the links
    take away, plus what arrives over them after losses, meets the load
    there. Each generator and load term enters with its component's `sign`
    (`constraints.py:1428-1429`, `:1538`)
  dims: [snapshot, bus]
  expression: >-
    sum(Generator_sign * Generator_p, by=Generator_bus, over=generator, into=bus)
    - sum(Link_p, by=Link_bus0, over=link, into=bus)
    + sum(at(Link_p, by=Link_output_link, over=link, into=link_output) * Link_efficiency, by=Link_output_bus, over=link_output, into=bus)
    == -sum(Load_sign * Load_p_set, by=Load_bus, over=load, into=bus)
```

```math
\sum_{g \in \mathcal{G} \,:\, \mathrm{Generator\_bus}(g) = n} \mathrm{sgn}_{g} \cdot p_{t,g} - \left( \sum_{l \in \mathcal{L} \,:\, \mathrm{Link\_bus0}(l) = n} f_{t,l} \right) + \sum_{o \in \mathcal{O} \,:\, \mathrm{Link\_output\_bus}(o) = n} f_{t,\mathrm{Link\_output\_link}(o)} \cdot \eta_{o} = -\left( \sum_{d \in \mathcal{D} \,:\, \mathrm{Load\_bus}(d) = n} \mathrm{sgn}^{\mathrm{load}}_{d} \cdot \mathrm{load}_{t,d} \right) \qquad \forall\, t \in \mathcal{T},\ n \in \mathcal{N}
```

### `Generator-com-p-lower`

`Generator_com_p_lower`

```yaml
Generator_com_p_lower:
  description: "`Generator-com-p-lower` — a committed unit outputs at least its minimum; off, at least nothing"
  dims: [snapshot, generator]
  where: Generator_committable
  expression: Generator_p >= Generator_p_min_pu * Generator_p_nom * (Generator_status - Generator_maintenance_pu * Generator_maintenance_status)
```

```math
p_{t,g} \ge \underline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot \left( u_{t,g} - \gamma_{g} \cdot \mu^{u}_{t,g} \right) \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g}
```

### `Generator-com-p-upper`

`Generator_com_p_upper`

```yaml
Generator_com_p_upper:
  description: "`Generator-com-p-upper` — a committed unit outputs at most what is available; off, at most nothing"
  dims: [snapshot, generator]
  where: Generator_committable
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom * (Generator_status - Generator_maintenance_pu * Generator_maintenance_status)
```

```math
p_{t,g} \le \overline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot \left( u_{t,g} - \gamma_{g} \cdot \mu^{u}_{t,g} \right) \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g}
```

### `Generator-com-transition-start-up`

`Generator_com_transition_start_up`

```yaml
Generator_com_transition_start_up:
  description: "`Generator-com-transition-start-up` — turning on is a start, counted against the state the unit carried into the snapshot"
  dims: [snapshot, generator]
  where: Generator_committable
  expression: Generator_start_up >= Generator_status - Generator_previous_status
```

```math
\mathit{up}_{t,g} \ge u_{t,g} - \overleftarrow{u}_{t,g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g}
```

### `Generator-com-transition-shut-down`

`Generator_com_transition_shut_down`

```yaml
Generator_com_transition_shut_down:
  description: "`Generator-com-transition-shut-down` — turning off is a stop, counted against the state the unit carried into the snapshot"
  dims: [snapshot, generator]
  where: Generator_committable
  expression: Generator_shut_down >= Generator_previous_status - Generator_status
```

```math
\mathit{dn}_{t,g} \ge \overleftarrow{u}_{t,g} - u_{t,g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g}
```

### `Generator-com-up-time`

`Generator_com_up_time`

```yaml
Generator_com_up_time:
  description: >-
    `Generator-com-up-time` — a unit started within its own minimum up time
    is still on. The first snapshot's share of the window is the brought-in
    up time's, which the must-stay-up mask carries
  dims: [snapshot, generator]
  where: Generator_committable AND Generator_min_up_time > 0 AND position(snapshot) > 0
  expression: sum_back(Generator_start_up, along=snapshot, window=Generator_min_up_time) <= Generator_status
```

```math
\sum_{t' \in \mathcal{T} \,:\, 0 \le t - t' < \mathrm{UT}} \mathit{up}_{t',g} \le u_{t,g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{UT}_{g} > 0 \wedge \mathrm{pos}(t) > 0
```

### `Generator-com-down-time`

`Generator_com_down_time`

```yaml
Generator_com_down_time:
  description: >-
    `Generator-com-down-time` — a unit stopped within its own minimum down
    time is still off. The first snapshot's share of the window is the
    brought-in down time's, which the must-stay-down mask carries
  dims: [snapshot, generator]
  where: Generator_committable AND Generator_min_down_time > 0 AND position(snapshot) > 0
  expression: sum_back(Generator_shut_down, along=snapshot, window=Generator_min_down_time) <= 1 - Generator_status
```

```math
\sum_{t' \in \mathcal{T} \,:\, 0 \le t - t' < \mathrm{DT}} \mathit{dn}_{t',g} \le 1 - u_{t,g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{DT}_{g} > 0 \wedge \mathrm{pos}(t) > 0
```

### `Generator-com-status-min_up_time_must_stay_up`

`Generator_com_status_must_stay_up`

```yaml
Generator_com_status_must_stay_up:
  description: "`Generator-com-status-min_up_time_must_stay_up` — a unit still serving the up time it brought in stays on"
  dims: [snapshot, generator]
  where: Generator_committable AND Generator_must_stay_up
  expression: Generator_status == 1
```

```math
u_{t,g} = 1 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{hold}_{t,g}
```

### `Generator-com-status-min_down_time_must_stay_up`

`Generator_com_status_must_stay_down`

```yaml
Generator_com_status_must_stay_down:
  description: >-
    `Generator-com-status-min_down_time_must_stay_up` — a unit still serving
    the down time it brought in stays off; PyPSA names the row `_must_stay_up`
  dims: [snapshot, generator]
  where: Generator_committable AND Generator_must_stay_down
  expression: Generator_status == 0
```

```math
u_{t,g} = 0 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{rest}_{t,g}
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
    `p_init` gives the output it brought in
  dims: [snapshot, generator]
  where: >-
    (Generator_ramp_limit_up OR Generator_ramp_limit_start_up)
    AND (position(snapshot) > 0 OR Generator_status_initial == 0 OR Generator_p_init)
  expression: Generator_p - Generator_previous_p <= Generator_ramp_up_allowance
```

```math
p_{t,g} - \overleftarrow{p}_{t,g} \le \Delta^{+}_{t,g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \left( \mathrm{ru}_{t,g} \text{ is defined} \vee \mathrm{ru}^{\mathrm{up}}_{g} \text{ is defined} \right) \wedge \left( \mathrm{pos}(t) > 0 \vee \mathrm{u}^{0}_{g} = 0 \vee \mathrm{p}^{0}_{g} \text{ is defined} \right)
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
    `p_init` gives the output it brought in
  dims: [snapshot, generator]
  where: >-
    (Generator_ramp_limit_down OR Generator_ramp_limit_shut_down)
    AND (position(snapshot) > 0 OR Generator_status_initial == 0 OR Generator_p_init)
  expression: Generator_previous_p - Generator_p <= Generator_ramp_down_allowance
```

```math
\overleftarrow{p}_{t,g} - p_{t,g} \le \Delta^{-}_{t,g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \left( \mathrm{rd}_{t,g} \text{ is defined} \vee \mathrm{rd}^{\mathrm{dn}}_{g} \text{ is defined} \right) \wedge \left( \mathrm{pos}(t) > 0 \vee \mathrm{u}^{0}_{g} = 0 \vee \mathrm{p}^{0}_{g} \text{ is defined} \right)
```

### `Generator-status-p-fixed-upper`

`Generator_status_p_fixed_upper`

```yaml
Generator_status_p_fixed_upper:
  description: "`Generator-status-p-fixed-upper` — a status is at most one, an explicit row as PyPSA writes it"
  dims: [snapshot, generator]
  where: Generator_committable
  expression: Generator_status <= 1
```

```math
u_{t,g} \le 1 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g}
```

### `Generator-start_up-p-fixed-upper`

`Generator_start_up_p_fixed_upper`

```yaml
Generator_start_up_p_fixed_upper:
  description: "`Generator-start_up-p-fixed-upper` — a start is at most one, an explicit row as PyPSA writes it"
  dims: [snapshot, generator]
  where: Generator_committable
  expression: Generator_start_up <= 1
```

```math
\mathit{up}_{t,g} \le 1 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g}
```

### `Generator-shut_down-p-fixed-upper`

`Generator_shut_down_p_fixed_upper`

```yaml
Generator_shut_down_p_fixed_upper:
  description: "`Generator-shut_down-p-fixed-upper` — a stop is at most one, an explicit row as PyPSA writes it"
  dims: [snapshot, generator]
  where: Generator_committable
  expression: Generator_shut_down <= 1
```

```math
\mathit{dn}_{t,g} \le 1 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g}
```

### `Generator-maint-event-count`

`Generator_maint_event_count`

```yaml
Generator_maint_event_count:
  description: "`Generator-maint-event-count` — a maintainable generator holds its number of maintenance events over the horizon"
  dims: [generator]
  where: Generator_maintainable
  expression: sum(Generator_maintenance_start, over=snapshot) == Generator_maintenance_events
```

```math
\sum_{t \in \mathcal{T}} \mu^{\mathrm{up}}_{t,g} = \mathrm{n}^{\mathrm{mnt}}_{g} \qquad \forall\, g \in \mathcal{G} \,:\, \mathrm{mnt}_{g}
```

### `Generator-maint-window`

`Generator_maint_window`

```yaml
Generator_maint_window:
  description: >-
    `Generator-maint-window` — a generator is in maintenance exactly where an event it
    started covers the snapshot; two events do not overlap, since the
    maintenance status is at most one
  dims: [snapshot, generator]
  where: Generator_maintainable
  expression: Generator_maintenance == sum(Generator_maintenance_start, by=Generator_maintenance_cover, over=start, into=covered)
```

```math
\mu_{t,g} = \sum_{t' \in \mathcal{T} \,:\, \left( g,\ t',\ t \right) \in \mathrm{Generator\_maintenance\_cover}} \mu^{\mathrm{up}}_{t',g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g}
```

### `Generator-maint-start-horizon`

`Generator_maint_start_horizon`

```yaml
Generator_maint_start_horizon:
  description: "`Generator-maint-start-horizon` — no event starts where it could not run its whole duration"
  dims: [snapshot, generator]
  where: Generator_maintainable AND Generator_maintenance_start_blocked
  expression: Generator_maintenance_start == 0
```

```math
\mu^{\mathrm{up}}_{t,g} = 0 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{blk}_{t,g}
```

### `Generator-maint-status-le-status`

`Generator_maint_status_le_status`

```yaml
Generator_maint_status_le_status:
  description: "`Generator-maint-status-le-status` — the status in maintenance is at most the status"
  dims: [snapshot, generator]
  where: Generator_maintainable AND Generator_committable
  expression: Generator_maintenance_status <= Generator_status
```

```math
\mu^{u}_{t,g} \le u_{t,g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{com}_{g}
```

### `Generator-maint-status-le-maint`

`Generator_maint_status_le_maint`

```yaml
Generator_maint_status_le_maint:
  description: "`Generator-maint-status-le-maint` — out of maintenance, the status in maintenance is zero"
  dims: [snapshot, generator]
  where: Generator_maintainable AND Generator_committable
  expression: Generator_maintenance_status <= Generator_maintenance
```

```math
\mu^{u}_{t,g} \le \mu_{t,g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{com}_{g}
```

### `Generator-maint-status-lb`

`Generator_maint_status_lb`

```yaml
Generator_maint_status_lb:
  description: "`Generator-maint-status-lb` — on and in maintenance, the status in maintenance is one"
  dims: [snapshot, generator]
  where: Generator_maintainable AND Generator_committable
  expression: Generator_maintenance_status >= Generator_status + Generator_maintenance - 1
```

```math
\mu^{u}_{t,g} \ge u_{t,g} + \mu_{t,g} - 1 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{com}_{g}
```

### `Generator-com-p-before`

`Generator_com_p_before`

```yaml
Generator_com_p_before:
  description: >-
    `Generator-com-p-before` — the output a unit had entering this snapshot
    fits the share of it still on, less the share it is shutting down at
    the shut-down ramp. The translated term vacates the first snapshot, as
    PyPSA's `sns[1:]` does
  dims: [snapshot, generator]
  where: Generator_committable AND Generator_partly_tightened
  expression: >-
    shift(Generator_p, along=snapshot, offset=1)
    - Generator_shut_down_rate * Generator_p_nom * shift(Generator_status, along=snapshot, offset=1)
    - (Generator_p_max_pu * Generator_p_nom - Generator_shut_down_rate * Generator_p_nom)
    * (Generator_status - Generator_start_up) <= 0
```

```math
p_{t - 1,g} - \widetilde{\mathrm{rd}}^{\mathrm{dn}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot u_{t - 1,g} - \left( \overline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} - \widetilde{\mathrm{rd}}^{\mathrm{dn}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \right) \cdot \left( u_{t,g} - \mathit{up}_{t,g} \right) \le 0 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{tight}_{g}
```

### `Generator-com-p-current`

`Generator_com_p_current`

```yaml
Generator_com_p_current:
  description: "`Generator-com-p-current` — output fits the share on, and the share starting up only up to the start-up ramp"
  dims: [snapshot, generator]
  where: Generator_committable AND Generator_partly_tightened AND position(snapshot) > 0
  expression: >-
    Generator_p - Generator_p_max_pu * Generator_p_nom * Generator_status
    + (Generator_p_max_pu * Generator_p_nom - Generator_start_up_rate * Generator_p_nom) * Generator_start_up <= 0
```

```math
p_{t,g} - \overline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot u_{t,g} + \left( \overline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} - \widetilde{\mathrm{ru}}^{\mathrm{up}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \right) \cdot \mathit{up}_{t,g} \le 0 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{tight}_{g} \wedge \mathrm{pos}(t) > 0
```

### `Generator-com-partly-start-up`

`Generator_com_partly_start_up`

```yaml
Generator_com_partly_start_up:
  description: "`Generator-com-partly-start-up` — raising output while a share is starting up is bounded by the ramp of the share on and the start-up ramp of the share coming on"
  dims: [snapshot, generator]
  where: Generator_committable AND Generator_partly_tightened
  expression: >-
    Generator_p - shift(Generator_p, along=snapshot, offset=1)
    - (Generator_p_min_pu * Generator_p_nom + Generator_ramp_up_rate * Generator_p_nom) * Generator_status
    + Generator_p_min_pu * Generator_p_nom * shift(Generator_status, along=snapshot, offset=1)
    + (Generator_p_min_pu * Generator_p_nom + Generator_ramp_up_rate * Generator_p_nom - Generator_start_up_rate * Generator_p_nom)
    * Generator_start_up <= 0
```

```math
p_{t,g} - p_{t - 1,g} - \left( \underline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} + \widetilde{\mathrm{ru}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \right) \cdot u_{t,g} + \underline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot u_{t - 1,g} + \left( \underline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} + \widetilde{\mathrm{ru}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} - \widetilde{\mathrm{ru}}^{\mathrm{up}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \right) \cdot \mathit{up}_{t,g} \le 0 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{tight}_{g}
```

### `Generator-com-partly-shut-down`

`Generator_com_partly_shut_down`

```yaml
Generator_com_partly_shut_down:
  description: "`Generator-com-partly-shut-down` — lowering output while a share is shutting down is bounded likewise, by the shut-down ramp"
  dims: [snapshot, generator]
  where: Generator_committable AND Generator_partly_tightened
  expression: >-
    shift(Generator_p, along=snapshot, offset=1) - Generator_p
    - Generator_shut_down_rate * Generator_p_nom * shift(Generator_status, along=snapshot, offset=1)
    + (Generator_shut_down_rate * Generator_p_nom - Generator_ramp_down_rate * Generator_p_nom) * Generator_status
    - (Generator_p_min_pu * Generator_p_nom + Generator_ramp_down_rate * Generator_p_nom - Generator_shut_down_rate * Generator_p_nom)
    * Generator_start_up <= 0
```

```math
p_{t - 1,g} - p_{t,g} - \widetilde{\mathrm{rd}}^{\mathrm{dn}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot u_{t - 1,g} + \left( \widetilde{\mathrm{rd}}^{\mathrm{dn}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} - \widetilde{\mathrm{rd}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \right) \cdot u_{t,g} - \left( \underline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} + \widetilde{\mathrm{rd}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} - \widetilde{\mathrm{rd}}^{\mathrm{dn}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \right) \cdot \mathit{up}_{t,g} \le 0 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g} \wedge \mathrm{tight}_{g}
```

### `Generator_previous_status`

```yaml
Generator_previous_status:
  description: >-
    the commitment state a generator carries into a snapshot — the state it
    brought into the horizon at the first, the previous snapshot's after that
  dims: [snapshot, generator]
  cases:
    opening: { when: "position(snapshot) == 0", expression: Generator_status_initial }
  otherwise: shift(Generator_status, along=snapshot, offset=1)
```

```math
\overleftarrow{u}_{t,g} = \begin{cases} \mathrm{u}^{0}_{g} & \text{if } \mathrm{pos}(t) = 0 \\ u_{t - 1,g} & \text{otherwise} \end{cases} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

### `Generator_previous_p`

```yaml
Generator_previous_p:
  description: >-
    the output a generator carries into a snapshot — at the first, the
    `p_init` it brought in where it came in running and nothing where it
    came in off; the previous snapshot's after that
  dims: [snapshot, generator]
  cases:
    opening: { when: "position(snapshot) == 0", expression: Generator_status_initial * Generator_p_init }
  otherwise: shift(Generator_p, along=snapshot, offset=1)
```

```math
\overleftarrow{p}_{t,g} = \begin{cases} \mathrm{u}^{0}_{g} \cdot \mathrm{p}^{0}_{g} & \text{if } \mathrm{pos}(t) = 0 \\ p_{t - 1,g} & \text{otherwise} \end{cases} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

### `Generator_ramp_up_rate`

```yaml
Generator_ramp_up_rate:
  description: >-
    the ramp limit a unit's up row reads — PyPSA's `ramp_limit_up`, or the
    full build where it has none, since a start-up ramp alone builds the row
  dims: [snapshot, generator]
  cases:
    given: { when: Generator_ramp_limit_up, expression: Generator_ramp_limit_up }
  otherwise: 1
```

```math
\widetilde{\mathrm{ru}}_{t,g} = \begin{cases} \mathrm{ru}_{t,g} & \text{if } \mathrm{ru}_{t,g} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

### `Generator_ramp_down_rate`

```yaml
Generator_ramp_down_rate:
  description: >-
    the ramp limit a unit's down row reads — PyPSA's `ramp_limit_down`, or
    the full build where it has none, since a shut-down ramp alone builds the row
  dims: [snapshot, generator]
  cases:
    given: { when: Generator_ramp_limit_down, expression: Generator_ramp_limit_down }
  otherwise: 1
```

```math
\widetilde{\mathrm{rd}}_{t,g} = \begin{cases} \mathrm{rd}_{t,g} & \text{if } \mathrm{rd}_{t,g} \text{ is defined} \\ 1 & \text{otherwise} \end{cases} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
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

### `Generator_ramp_up_allowance`

```yaml
Generator_ramp_up_allowance:
  description: >-
    how far a generator may raise output between two snapshots — its ramp
    limit of the build while it stays on, plus its start-up ramp in the
    snapshot it turns on
  dims: [snapshot, generator]
  cases:
    committed:
      when: Generator_committable
      expression: >-
        Generator_ramp_up_rate * Generator_p_nom * Generator_previous_status
        + Generator_start_up_rate * Generator_p_nom
        * (Generator_status - Generator_previous_status)
  otherwise: Generator_ramp_up_rate * Generator_p_nom
```

```math
\Delta^{+}_{t,g} = \begin{cases} \widetilde{\mathrm{ru}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot \overleftarrow{u}_{t,g} + \widetilde{\mathrm{ru}}^{\mathrm{up}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot \left( u_{t,g} - \overleftarrow{u}_{t,g} \right) & \text{if } \mathrm{com}_{g} \\ \widetilde{\mathrm{ru}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} & \text{otherwise} \end{cases} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

### `Generator_ramp_down_allowance`

```yaml
Generator_ramp_down_allowance:
  description: >-
    how far a generator may lower output between two snapshots — its ramp
    limit of the build while it stays on, plus its shut-down ramp in the
    snapshot it turns off
  dims: [snapshot, generator]
  cases:
    committed:
      when: Generator_committable
      expression: >-
        Generator_ramp_down_rate * Generator_p_nom * Generator_status
        + Generator_shut_down_rate * Generator_p_nom
        * (Generator_previous_status - Generator_status)
  otherwise: Generator_ramp_down_rate * Generator_p_nom
```

```math
\Delta^{-}_{t,g} = \begin{cases} \widetilde{\mathrm{rd}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot u_{t,g} + \widetilde{\mathrm{rd}}^{\mathrm{dn}}_{g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \cdot \left( \overleftarrow{u}_{t,g} - u_{t,g} \right) & \text{if } \mathrm{com}_{g} \\ \widetilde{\mathrm{rd}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} & \text{otherwise} \end{cases} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

#### Variable domains

**`Generator_p`**

```math
p_{t,g} \in \mathbb{R} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G}
```

**`Link_p`**

```math
f_{t,l} \in \mathbb{R} \qquad \forall\, t \in \mathcal{T},\ l \in \mathcal{L}
```

**`Generator_status`**

```math
u_{t,g} \ge 0 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g}
```

**`Generator_start_up`**

```math
\mathit{up}_{t,g} \ge 0 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g}
```

**`Generator_shut_down`**

```math
\mathit{dn}_{t,g} \ge 0 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{com}_{g}
```

**`Generator_maintenance`**

```math
0 \le \mu_{t,g} \le 1 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g}
```

**`Generator_maintenance_start`**

```math
\mu^{\mathrm{up}}_{t,g} \in \{0, 1\} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g}
```

**`Generator_maintenance_status`**

```math
\mu^{u}_{t,g} \ge 0 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{mnt}_{g} \wedge \mathrm{com}_{g}
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
    it. The spec does not state that row, so it refuses the data
```

```math
\mathrm{u}^{0}_{g} = 1 \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \neg \mathrm{com}_{g} \wedge \left( \mathrm{ru}_{t,g} \text{ is defined} \vee \mathrm{rd}_{t,g} \text{ is defined} \right)
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
\mathrm{n}^{\mathrm{mnt}}_{g} > 0 \qquad \forall\, g \in \mathcal{G} \,:\, \mathrm{mnt}_{g}
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
\tau^{\mathrm{mnt}}_{g} > 0 \qquad \forall\, g \in \mathcal{G} \,:\, \mathrm{mnt}_{g}
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
\tau^{\mathrm{mnt}}_{g} \le \sum_{t \in \mathcal{T}} \mathrm{w}^{\mathrm{gen}}_{t} \qquad \forall\, g \in \mathcal{G} \,:\, \mathrm{mnt}_{g}
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
\tau^{\mathrm{mnt}}_{g} \cdot \mathrm{n}^{\mathrm{mnt}}_{g} \le \sum_{t \in \mathcal{T}} \mathrm{w}^{\mathrm{gen}}_{t} \qquad \forall\, g \in \mathcal{G} \,:\, \mathrm{mnt}_{g}
```
<!-- gallery:end -->

Regenerate with `pixi run python -m tools.gallery`.
