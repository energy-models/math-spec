<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# PyPSA in one file

The model a plain `n.optimize()` builds, stated as one file and grown a rung
at a time towards
[milestone 1](https://github.com/energy-models/math-spec/milestone/1). The
page has two halves. The **table** is every row PyPSA emits, by rung, with
where it stands here; the **blocks** below it are the file itself, a
declaration at a time — PyPSA's name for the row, the YAML that states it,
the equation the typesetter prints. A table row links to its block once it
is in the file; until then its `spelling` is a proposal.

Nothing below the table is typed: a constraint that stops loading, or starts
printing different math, fails CI. Source for the table: PyPSA `0d7d683`
(2026-07-23), `pypsa/optimization/`.

## Rules

- `bounds:` takes a name or a number, like PyPSA; anything else is data prep.
- Bound rows are spelled as PyPSA spells them, as constraints, so `mu_upper`
  and `mu_lower` are row duals. No `bounds:` on an operational variable.
- No base mask. `active` is all-true in a single-period network.
- One cumulative file. Regimes are data columns and become `where:` masks;
  the file never forks.
- Names are PyPSA's: every declaration is `Component_attribute` after the
  statement it stands for, and a constraint's description opens with the
  linopy name of the row. A symbol table, `examples/symbols/pypsa.yaml`,
  makes the math read as math.
- Gate: solution and per-named-constraint duals against `n.optimize()`. Where
  one PyPSA row is several blocks here, the dual is compared after
  concatenation.

## Legend

| column     | contents                                                                                              |
| ---------- | ----------------------------------------------------------------------------------------------------- |
| `PyPSA`    | the linopy name PyPSA gives the row, or the objective term; a link once the row is in the file        |
| `where`    | the regime that emits it, as the `where:` mask it becomes here; blank means always                    |
| `spelling` | the declaration, with component prefixes dropped — a proposal until the row links                     |
| `status`   | `yes` one-to-one · `prep` needs a data-prep parameter · `split` one row becomes N blocks · `not` a PyPSA workaround we do not reproduce · `flag` only under an `n.optimize()` keyword · `scope` multi-period or stochastic · `open` not stateable yet |
| `note`     | a note under the table (letter = rung), an issue, or the keyword for a `flag`                         |

Regime shorthands in `where`: `ext` is the bool `<c>_p_nom_extendable` used
bare (`not ext` for fixed); `com` is `<c>_committable`; `mod` is
`<c>_p_nom_mod > 0`; `cyclic` is `StorageUnit_cyclic_state_of_charge`; `t0` is
`position(snapshot) == 0`; a bare number parameter means defined and finite;
`…` continues the row above.

Names in `spelling`: `{c}` any component the row applies to; `{attr}` its
operational attribute (`p`, `s`, `e`, `p_dispatch`, `p_store`,
`state_of_charge`); `SU` StorageUnit; `soc` the state of charge; `eh` is
`snapshot_weightings.stores`, `w_gen` and `w_objective` the other two columns;
`eff_d`/`eff_s` the storage efficiencies; `ru`, `r_su`, `rd`, `r_sd` the ramp
limits; `M` a per-entity big-M from data prep; `member`, `glc_*` 0/1 membership
and weights over a `glc` dimension from data prep; `mirror`/`same` the row
above with a sign or component swapped; `shift(x)` is
`shift(x, over=snapshot, offset=1, edge=0)` unless spelled out.

## Rows by rung

### Rung 1 — transport

Generator dispatch, controllable links, the nodal balance, a linear cost.
**In the file.**

| PyPSA                                                | where     | spelling                                                                   | status | note |
| ---------------------------------------------------- | --------- | -------------------------------------------------------------------------- | ------ | ---- |
| [`Generator-p`, `Link-p`](#variable-domains)         |           | `foreach: [snapshot, c]`, no bounds                                        | yes    |      |
| [`Generator-fix-p-lower`](#generator-fix-p-lower)    | `not ext` | `p >= p_min_pu * p_nom`                                                    | yes    | A1   |
| [`Generator-fix-p-upper`](#generator-fix-p-upper)    | `not ext` | `p <= p_max_pu * p_nom`                                                    | yes    |      |
| [`Link-fix-p-lower`](#link-fix-p-lower)              | `not ext` | `p >= p_min_pu * p_nom`                                                    | yes    |      |
| [`Link-fix-p-upper`](#link-fix-p-upper)              | `not ext` | `p <= p_max_pu * p_nom`                                                    | yes    |      |
| [`Bus-nodal_balance`](#bus-nodal_balance)            |           | `sum(x, by=x_bus)` per component and port `== sum(Load_p_set, by=Load_bus)` | yes    | A2   |
| `Bus-meshed-{30,100,400}-nodal_balance`              |           |                                                                            | not    | A3   |
| [`marginal_cost` (Generator, Link)](#objective)      |           | `sum(p * marginal_cost * w_objective)`                                     | yes    |      |
| `objective_constant`                                 |           |                                                                            | not    | A4   |

- A1: arithmetic is fine in a constraint; PR #81's "multiply it out" existed
  only because it used `bounds:`. PyPSA's `inf * 0 -> 0` policy is data prep.
  These rows are also `Line-fix-s-*` and `Transformer-fix-s-*` once lines
  arrive on rung 6.
- A2: a partial lookup contributes nothing, which is PyPSA's `bus_i == ""`
  drop. A bus with an empty LHS is a row not built; PyPSA raises if it carries
  load. See Refusals, X2.
- A3: a linopy-speed workaround (`meshed_thresholds`). One `Bus_nodal_balance`;
  `marginal_price` compared over the union.
- A4: bookkeeping so `objective` reports the same number; compare objectives
  net of `n._objective_constant`.

### Rung 2 — storage

Stores carrying energy between snapshots, cyclic and not. **Next.**

| PyPSA                                                  | where                     | spelling                                                                                                                 | status | note |
| ------------------------------------------------------ | ------------------------- | ------------------------------------------------------------------------------------------------------------------------ | ------ | ---- |
| SU `-p_dispatch`, `-p_store`, `-state_of_charge`, `Store-e`, `Store-p` |           | `foreach: [snapshot, c]`, no bounds                                                                                      | yes    |      |
| `StorageUnit-spill`                                    | `inflow > 0`              | `lower: 0, upper: StorageUnit_inflow`, `absence: zero`                                                                   | yes    | B1   |
| SU `-fix-*-lower/upper`, `Store-fix-e-*`               | `not ext`                 | as rung 1, with `max_hours` for the level                                                                                | yes    |      |
| `StorageUnit-energy_balance`, cyclic                   | `cyclic`                  | `shift(soc, offset=1, edge='wrap') * soc_carry - soc - eh/eff_d * p_dispatch + eh*eff_s * p_store - eh * spill == -inflow*eh` | split | B2 |
| same, non-cyclic                                       | `not cyclic and not t0`   | same with `edge=0`                                                                                                       | split  | B3   |
| same, non-cyclic first snapshot                        | `not cyclic and t0`       | `… == -inflow*eh - soc_initial * soc_carry`                                                                              | split  | B3   |
| `Store-energy_balance`                                 |                           | same shape with `e`, `Store_p`, `e_cyclic`, `e_initial`                                                                  | split  |      |
| `StorageUnit-p_set`, `{c}-{attr}_set`                  | `p_set`                   | `p_dispatch - p_store == p_set`; `p == p_set`                                                                            | yes    | B4   |
| `marginal_cost_storage`, `spill_cost`                  |                           | `sum(soc * marginal_cost_storage * w_objective)`; same on `spill`                                                        | yes    |      |

- B1: PyPSA skips the whole variable when no inflow is positive; `where:`
  yields the same columns.
- B2: `soc_carry = (1 - standing_loss) ** eh` is data prep because `**`
  refuses an additive base. `spill` is `absence: zero`, so the term vanishes
  as in PyPSA.
- B3: one PyPSA row, three blocks; `mu_energy_balance` compared after
  concatenation. Mixed fleets (lpspec `pypsa_mixed_cycling.yaml`) fall out.
- B4: PyPSA's mask is `~isnull(fix)`, which is "defined".

### Rung 3 — expansion

Nominal power as a decision.

| PyPSA                                     | where                 | spelling                                          | status | note |
| ----------------------------------------- | --------------------- | ------------------------------------------------- | ------ | ---- |
| `{c}-p_nom`, `-s_nom`, `-e_nom`           | `ext`                 | `foreach: [c]`                                    | yes    |      |
| `{c}-ext-{attr}-lower/upper`              | `ext and not com`     | `p - p_min_pu * p_nom >= 0`                       | yes    |      |
| `{c}-ext-p_nom-lower`                     | `ext`                 | `p_nom >= p_nom_min`                              | yes    |      |
| `{c}-ext-p_nom-upper`                     | `ext and p_nom_max`   | `p_nom <= p_nom_max`                              | yes    | C1   |
| `{c}-p_nom_set`                           | `p_nom_set`           | `p_nom == p_nom_set`                              | yes    |      |
| `Generator-e_sum_min/max`                 | `e_sum_min`           | `sum(p * w_gen, over=snapshot) >= e_sum_min`      | yes    | C2   |
| capital cost                              |                       | `sum(p_nom * capital_cost)`                       | prep   | C3   |

- C1: a bare parameter in `where:` means finite, which is PyPSA's
  `mask=(upper != inf)`.
- C2: `-inf` is not "defined", so the mask matches PyPSA's `> -inf`.
- C3: `periodized_cost` (annuity from `overnight_cost`, `lifetime`,
  `discount_rate`, `fom_cost`) is data prep. The cost sits on the capacity
  variable, not `n_mod`, as in PyPSA.

### Rung 4 — ramps

Limits on how far output moves between snapshots.

| PyPSA                            | where                                        | spelling                                                                | status | note |
| -------------------------------- | -------------------------------------------- | ----------------------------------------------------------------------- | ------ | ---- |
| `{c}-p-ramp_limit_up`, fixed     | `ramp_limit_up and not com and not ext and not t0` | `p - shift(p) <= ru * p_nom`                                      | split  | D1   |
| same, committable fixed          | `… com and not ext`                          | `… <= ru*p_nom*shift(status) + r_su*p_nom*(status - shift(status))`     | split  | D1   |
| same, extendable                 | `… ext and not com`                          | `p - shift(p) - ru * p_nom <= 0`                                        | split  | D1   |
| same, first snapshot             | `… t0 and p_initial`                         | `p - p_initial <= …`                                                    | split  | D2   |
| `{c}-p-ramp_limit_down`          |                                              | mirror                                                                  | split  |      |

- D1: PyPSA emits one row whose terms depend on which regimes exist; here one
  block per regime. `where: ramp_limit_up` is "limit given", PyPSA's
  `~no_up_limit`.
- D2: PyPSA keeps the t0 row only when the initial dispatch is known. A
  numeric `shift` edge over a variable can only be 0, so the initial value is
  a parameter in its own block.

### Rung 5 — global constraints

Emission and expansion budgets. PyPSA names them all
`GlobalConstraint-{name}`; type and comparator are data. A comparator is
fixed per block, so each type is three blocks (`where: sense == "<="`, `">="`,
`"=="`). Candidate language item: a comparator from data.

| PyPSA type                            | spelling                                                                                                                                  | status      | note |
| ------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ----------- | ---- |
| `primary_energy`                      | `sum(p * w_gen * at(glc_carrier_weight, by=Generator_carrier) / efficiency, over=[snapshot, generator]) + depletion <= constant`           | prep, split | E1   |
| `operational_limit`                   | same without the carrier weight; `glc_member[glc, generator]`                                                                             | prep, split |      |
| `transmission_volume_expansion_limit` | `sum(Line_length * Line_s_nom * member, over=line) + link term <= constant`                                                               | prep, split | E2   |
| `transmission_expansion_cost_limit`   | same with `capital_cost`                                                                                                                  | prep, split |      |
| `tech_capacity_expansion_limit`       | `sum(p_nom * member, over=generator) …`                                                                                                   | prep, split | E3   |
| `Bus-nom_min_{carrier}` / `nom_max`   |                                                                                                                                           | not         | deprecated in PyPSA |
| `Carrier-growth_limit`                |                                                                                                                                           | scope       | multi-period |
| `effect_limit`, priced effects        |                                                                                                                                           | open        | E4   |

- E1: the depletion term needs "soc at the last snapshot"; no indexing in an
  expression, so `sum(soc * is_last, over=snapshot)` with a 0/1 `is_last`.
  Candidate language item: a value at a `position()`. Only non-cyclic units
  contribute, a 0/1 coefficient.
- E2: membership from PyPSA's comma-split carrier string is data prep.
- E3: bus selection folded into `member`.
- E4: `effects.py` is reachable from `create_model` and not inventoried yet.

### Rung 6 — KVL

Lines with reactance, flows around cycles.

| PyPSA                   | where | spelling                                                                                        | status | note |
| ----------------------- | ----- | ----------------------------------------------------------------------------------------------- | ------ | ---- |
| `Line-s`, `Line-fix-s-*` |      | as rung 1                                                                                       | yes    |      |
| `Kirchhoff-Voltage-Law` |       | `sum(cycle_incidence * Line_x_pu_eff * Line_s * 1e5, over=line) == 0`, over `[snapshot, cycle]` | prep   | F1   |

- F1: the cycle basis is topology, so data prep (lpspec `pypsa_kvl.yaml`).
  Keep the `1e5`; PyPSA does not assign the KVL dual.

### Rung 7 — commitment

Binary status, minimum up and down times — a MILP, solution only.

| PyPSA                                       | where                          | spelling                                                                  | status | note |
| ------------------------------------------- | ------------------------------ | ------------------------------------------------------------------------- | ------ | ---- |
| `{c}-status`, `-start_up`, `-shut_down`     | `com`                          | `domain: binary`                                                          | yes    | G1   |
| `{c}-com-p-lower/upper`                     | `com and not ext and not mod`  | `p - p_min_pu * p_nom * status >= 0`                                      | yes    |      |
| `{c}-status/start_up/shut_down-p-fixed-upper` | `com`                        | `status <= 1`                                                             | yes    |      |
| `{c}-com-transition-start-up`               | `com and not t0`               | `start_up - status + shift(status, over=snapshot, offset=1, edge=0) >= 0` | split  | G2   |
| same, first snapshot                        | `com and t0`                   | `start_up - status >= -status_initial`                                    | split  | G2   |
| `{c}-com-transition-shut-down`              |                                | mirror                                                                    | split  |      |
| `{c}-com-up-time`                           | `min_up_time > 0 and not t0`   | `sum_back(start_up, over=snapshot, within=min_up_time) - status <= 0`     | yes    | G3   |
| `{c}-com-down-time`                         | `min_down_time > 0 and not t0` | `sum_back(shut_down, …) + status <= 1`                                    | yes    |      |
| `{c}-com-status-min_up_time_must_stay_up`   | `must_stay_up`                 | `status == 1`                                                             | prep   | G4   |
| `{c}-com-status-min_down_time_must_stay_up` | `must_stay_down`               | `status == 0`                                                             | prep   | G4   |
| `stand_by_cost`                             |                                | `sum(status * stand_by_cost * w_objective)`                               | yes    |      |
| `start_up_cost`, `shut_down_cost`           |                                | `sum(start_up * start_up_cost)`                                           | yes    | G5   |
| `{c}-com-p-before/-current/-partly-*`       |                                |                                                                           | flag   | `linearized_unit_commitment` |

- G1: the continuous [0,1] status of `linearized_unit_commitment` is a flag.
- G2: PyPSA puts -1 / +1 into the t0 RHS for units with `up_time_before > 0`;
  here a 0/1 parameter `status_initial` and a second block.
- G3: per-entity `within=` is PyPSA's per-generator rolling width
  (`constraints.py:452`). `min_up_time` must be `dtype: int`.
- G4: PyPSA's mask is `position < min_up_time - up_time_before`; `position()`
  compares to a literal only. Candidate language item:
  `position(dim) OP <int parameter>`.
- G5: unweighted in PyPSA; keep it that way.

### Rung 8 — modular and big-M

Integer module counts; committable and extendable at once.

| PyPSA                                                 | where                     | spelling                                             | status | note |
| ----------------------------------------------------- | ------------------------- | ---------------------------------------------------- | ------ | ---- |
| `{c}-n_mod`                                           | `ext and mod`             | `domain: integer`, `lower: 0`                        | yes    |      |
| `{c}-status`, … modular committable                   | `com and mod`             | `domain: integer`, `lower: 0`                        | yes    | H1   |
| `{c}-p_nom_modularity`                                | `ext and mod`             | `p_nom - n_mod * p_nom_mod == 0`                     | yes    |      |
| `{c}-status/start_up/shut_down-p_nom-variable-upper`  | `com and ext and mod`     | `status - n_mod <= 0`, over `[snapshot, c]`          | yes    |      |
| `{c}-status/…-p-fixed-upper`, fixed modular           | `com and mod and not ext` | `status <= p_nom / p_nom_mod`                        | split  | H2   |
| `{c}-com-mod-p-lower/upper`                           | `com and mod`             | `p - p_min_pu * p_nom_mod * status >= 0`             | yes    |      |
| `{c}-com-ext-p-lower/-upper-bigM/-upper-cap`          | `com and ext and not mod` | `p - p_min_pu*p_nom - M*status >= -M`, …             | prep   | H3   |
| `{c}-com-ext-p-lower-nonneg`                          | `… and p_min_pu_nonneg`   | `p >= 0`                                             | prep   | H4   |
| `{c}-p-ramp_limit_*-bigM` (4 rows)                    | `com and ext and not mod` | as PyPSA, `M` from data prep                         | prep   | H3   |

- H1: the upper bound comes from the `-fixed-upper` rows, as in PyPSA.
- H2: division by a variable-free factor is allowed. PyPSA raises when
  `p_nom` is not an integer multiple of `p_nom_mod`; we would build it. See
  Refusals, X1.
- H3: `M` per generator is `p_nom_max * p_max_pu` if finite, else PyPSA's
  inferred `big_m_default` (peak load, max `p_nom`), a network-wide reduction.
- H4: PyPSA's mask is `(p_min_pu >= 0).all(snapshot)`; a reduction inside
  `where:` is not in the language, so a per-generator bool.

### Rung 9 — multi-link and delay

Links with more than two ports; flow that arrives later.

| PyPSA                        | spelling                                                                       | status  | note |
| ---------------------------- | ------------------------------------------------------------------------------ | ------- | ---- |
| nodal balance, ports 2..n    | `+ sum(Link_p * Link_efficiency2, by=Link_bus2) …`                             | yes     | I1   |
| nodal balance, link delay    | `sum(shift(Link_p, over=snapshot, offset=Link_delay1, edge=…) * eff, by=bus1)` | open    | I2, #75 |

- I1: a partial lookup (`Link_bus2` null for two-port links) contributes
  nothing.
- I2: per-entity `offset=` is in the language; the per-link edge kind
  (`cyclic_delay1`) is not. Workaround: two shifted sums with 0/1
  coefficients. Value and dual parity, different structure.

### Not on a rung

| PyPSA                                                   | status | note                                          |
| ------------------------------------------------------- | ------ | --------------------------------------------- |
| `{c}-loss`, `{c}-loss_upper`, `-loss_secants-*`, `-loss_tangents-*` | flag | `transmission_losses`; the secant count is solved for by a while-loop |
| `marginal_cost_quadratic`                               | yes    | `sum(p * p * mcq * w_objective)`; HiGHS refuses it against integrality, a solver matter |
| `CVaR-a`, `CVaR-theta`, `CVaR`                          | scope  | stochastic                                    |

## Refusals

Where PyPSA refuses to build, parity means refusing too: on these inputs PyPSA
has no solution to agree with. None is a language gap; each is a check on the
data that we do not make yet. Whether a check lives in the language, in the
data-prep contract, or in the harness is one design question, argued here
once.

| PyPSA raises                                          | at                                          | on what data                                                      | status | today                                     | note |
| ----------------------------------------------------- | ------------------------------------------- | ----------------------------------------------------------------- | ------ | ----------------------------------------- | ---- |
| `ValueError`, `constraints.py:1449`                   | `{c}-status-p-fixed-upper` (H2)             | committable, modular, fixed `p_nom` not a multiple of `p_nom_mod` | open   | builds; `status <= 2.5` caps at 2 modules | X1   |
| `ValueError`, `constraints.py:1192`                   | `Bus-nodal_balance` (A2)                    | load on a bus with no attached variable                           | open   | row not built; the load is unserved       | X2   |
| `ValueError`, `optimize.py:430`                       | objective                                   | no component carries a cost                                       | open   | objective `0`; solves                     | X3   |
| `NotImplementedError`, `global_constraints.py:339,618` | `primary_energy`, `operational_limit` (E1) | non-cyclic storage depletion with period weightings `!= 1`        | scope  | multi-period; #11                         |      |
| `ValueError`, `constraints.py:2008`                   | `{c}-loss_upper`                            | `s_nom_max = inf` on a lossy branch                               | flag   | `transmission_losses`                     |      |
| `RuntimeError`, `constraints.py:2175`                 | `{c}-loss_secants-*`                        | secant count reaches `max_segments`                               | flag   | `transmission_losses`                     |      |
| warning, `check_big_m_exceeded`                       | post-solve                                  | a solution sitting on the big-M                                   | —      | harness                                   | X4   |

- X1: an integer `status` under a fractional cap is a quietly smaller plant,
  not an error.
- X2: a constraint row with no variable terms is not built and shows in
  `diagnostics().omissions`; `0 == -load` vanishes instead of failing.
- X3: PyPSA refuses a costless model; we would accept a feasibility problem.
  Arguably not worth mirroring.
- X4: not a refusal; PyPSA warns after solving. The harness runs the same
  check when comparing.

## Post-solve

math-spec declares shape; reading back is the consumer's. These live in the
parity harness on the lpspec side.

| PyPSA                                                        | harness                                                 |
| ------------------------------------------------------------ | ------------------------------------------------------- |
| `Bus-nodal_balance` dual / `w_objective` -> `marginal_price` | normalise the same way before comparing                 |
| five upper rows `combine_first` -> `mu_upper`                | concatenate our regime blocks; disjoint by construction |
| `Link-p` -> `p0`, `p1 = -p * efficiency`; `Line-s` -> `p0/p1` | derived; compare `p0`                                  |
| `n_mod` discarded                                            | compare `p_nom_opt` only                                |
| KVL, `e_sum_*`, `growth_limit` duals                         | PyPSA does not assign them; compare only what it exposes |

Out of scope for milestone 1, each an `n.optimize()` keyword or variant:
`multi_investment_periods`, stochastic scenarios and CVaR,
`transmission_losses`, `linearized_unit_commitment`, rolling horizon,
`optimize_mga`, `abstract.py`, `effects.py`. lpspec ports
`pypsa_multi_period`, `pypsa_stochastic`, `pypsa_cvar`, `pypsa_losses`,
`pypsa_linearized_uc`, `pypsa_growth_limit`.

## What the table says

Nothing a plain `n.optimize()` emits is unstateable. The debt is three kinds:

1. **Data prep contract.** Parameters the file expects that PyPSA computes:
   `big_M`, `soc_carry`, `periodized_cost`, `cycle_incidence`,
   `p_min_pu_nonneg`, `must_stay_up`, `is_last`, glc membership and weights,
   `status_initial`. One documented function `network -> tables`.
2. **Row splitting.** Regimes, first-snapshot rows and comparators become
   `where:` blocks. Candidate language items, none blocking:
   `position() OP parameter` (G4), a value at a position (E1), a comparator
   from data (rung 5). Plus #75 (I2), the only workaround that changes
   structure.
3. **Refusals PyPSA has and we lack.** Three reachable in a single-period
   run (X1 to X3), of the #11 kind: we would build a wrong model silently.

Spellings seeded from lpspec `examples/ports/pypsa_*.yaml` and PR #81.

## The file

<!-- gallery:begin -->
The model a plain `n.optimize()` builds, stated in one file. Every declaration is named `Component_attribute` after the PyPSA statement it stands for, and each constraint's description opens with the linopy name PyPSA gives that row, so the two can be read side by side. PyPSA's regimes — extendable, committable — are data columns and become `where:` masks. Rung 1, transport: generator dispatch, controllable links, a nodal balance, a linear cost. Bounds are the explicit rows PyPSA writes, so their duals are row duals.

#### Sets

| Symbol | Meaning |
|---|---|
| $\mathcal{T}$ | index $t$ — `snapshot` — dispatch periods |
| $\mathcal{N}$ | index $n$ — `bus` — network nodes |
| $\mathcal{G}$ | index $g$ — `generator` with $\mathrm{Generator\_bus}: \mathcal{G} \to \mathcal{N}$ — generating units, each on one bus |
| $\mathcal{L}$ | index $l$ — `link` with $\mathrm{Link\_bus0}: \mathcal{L} \to \mathcal{N},\enspace \mathrm{Link\_bus1}: \mathcal{L} \to \mathcal{N}$ — controllable connections, each from one bus to another |
| $\mathcal{D}$ | index $d$ — `load` with $\mathrm{Load\_bus}: \mathcal{D} \to \mathcal{N}$ — demands, each on one bus |

#### Parameters

| Symbol | Meaning |
|---|---|
| $\mathrm{w}$ | `snapshot_weightings_objective` over $\mathcal{T}$ — PyPSA's `snapshot_weightings.objective` — hours a snapshot stands for in the cost |
| $\mathrm{p}^{\mathrm{nom}}$ | `Generator_p_nom` over $\mathcal{G}$ — nominal power |
| $\mathrm{ext}$ | `Generator_p_nom_extendable` over $\mathcal{G}$ — whether the nominal power is a decision; false on this rung |
| $\underline{\mathrm{p}}$ | `Generator_p_min_pu` over $\mathcal{T} \times \mathcal{G}$ — least output, per unit of nominal power |
| $\overline{\mathrm{p}}$ | `Generator_p_max_pu` over $\mathcal{T} \times \mathcal{G}$ — most output, per unit of nominal power — an availability profile |
| $\mathrm{c}$ | `Generator_marginal_cost` over $\mathcal{T} \times \mathcal{G}$ — cost of one unit of output |
| $\mathrm{f}^{\mathrm{nom}}$ | `Link_p_nom` over $\mathcal{L}$ — nominal power |
| $\mathrm{ext}^{f}$ | `Link_p_nom_extendable` over $\mathcal{L}$ — whether the nominal power is a decision; false on this rung |
| $\underline{\mathrm{f}}$ | `Link_p_min_pu` over $\mathcal{T} \times \mathcal{L}$ — least flow, per unit of nominal power — negative for a link that carries both ways |
| $\overline{\mathrm{f}}$ | `Link_p_max_pu` over $\mathcal{T} \times \mathcal{L}$ — most flow, per unit of nominal power |
| $\eta$ | `Link_efficiency` over $\mathcal{L}$ — share of the flow that arrives at the link's `Link_bus1` end |
| $\mathrm{c}^{f}$ | `Link_marginal_cost` over $\mathcal{T} \times \mathcal{L}$ — cost of one unit of flow |
| $\mathrm{load}$ | `Load_p_set` over $\mathcal{T} \times \mathcal{D}$ — demand |

#### Variables

| Symbol | Meaning |
|---|---|
| $p$ | `Generator_p` over $\mathcal{T} \times \mathcal{G}$ — `Generator-p` — output of a generator in a snapshot |
| $f$ | `Link_p` over $\mathcal{T} \times \mathcal{L}$ — `Link-p` — PyPSA's `p0`, the flow measured at the `Link_bus0` end: a positive value withdraws there and injects at `Link_bus1` |

### Objective

```yaml
objective:
  sense: minimize
  description: operating cost, each snapshot weighted by the hours it stands for
  expression: >-
    sum(Generator_p * Generator_marginal_cost * snapshot_weightings_objective)
    + sum(Link_p * Link_marginal_cost * snapshot_weightings_objective)
```

$$\min \sum_{t \in \mathcal{T},\enspace g \in \mathcal{G}} p_{t,g} \cdot \mathrm{c}_{t,g} \cdot \mathrm{w}_{t} + \sum_{t \in \mathcal{T},\enspace l \in \mathcal{L}} f_{t,l} \cdot \mathrm{c}^{f}_{t,l} \cdot \mathrm{w}_{t}$$

### `Generator-fix-p-lower`

`Generator_fix_p_lower`

```yaml
Generator_fix_p_lower:
  description: "`Generator-fix-p-lower` — a fixed generator outputs at least its minimum"
  foreach: [snapshot, generator]
  where: not Generator_p_nom_extendable
  expression: Generator_p >= Generator_p_min_pu * Generator_p_nom
```

$$p_{t,g} \ge \underline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \neg \mathrm{ext}_{g}$$

### `Generator-fix-p-upper`

`Generator_fix_p_upper`

```yaml
Generator_fix_p_upper:
  description: "`Generator-fix-p-upper` — a fixed generator outputs at most what is available"
  foreach: [snapshot, generator]
  where: not Generator_p_nom_extendable
  expression: Generator_p <= Generator_p_max_pu * Generator_p_nom
```

$$p_{t,g} \le \overline{\mathrm{p}}_{t,g} \cdot \mathrm{p}^{\mathrm{nom}}_{g} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G} \thinspace:\thinspace \neg \mathrm{ext}_{g}$$

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

### `Bus-nodal_balance`

`Bus_nodal_balance`

```yaml
Bus_nodal_balance:
  description: >-
    `Bus-nodal_balance` — what is generated at a bus, less what the links
    take away, plus what arrives over them after losses, meets the load
    there. A bus nothing is attached to has no row; PyPSA refuses one that
    carries load, and this file does not yet.
  foreach: [snapshot, bus]
  expression: >-
    sum(Generator_p, by=Generator_bus)
    - sum(Link_p, by=Link_bus0)
    + sum(Link_p * Link_efficiency, by=Link_bus1)
    == sum(Load_p_set, by=Load_bus)
```

$$\sum_{g \in \mathcal{G} \thinspace:\thinspace \mathrm{Generator\_bus}(g) = n} p_{t,g} - \left( \sum_{l \in \mathcal{L} \thinspace:\thinspace \mathrm{Link\_bus0}(l) = n} f_{t,l} \right) + \sum_{l \in \mathcal{L} \thinspace:\thinspace \mathrm{Link\_bus1}(l) = n} f_{t,l} \cdot \eta_{l} = \sum_{d \in \mathcal{D} \thinspace:\thinspace \mathrm{Load\_bus}(d) = n} \mathrm{load}_{t,d} \qquad \forall\thinspace t \in \mathcal{T},\enspace n \in \mathcal{N}$$

#### Variable domains

**`Generator_p`**

$$p_{t,g} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace g \in \mathcal{G}$$

**`Link_p`**

$$f_{t,l} \in \mathbb{R} \qquad \forall\thinspace t \in \mathcal{T},\enspace l \in \mathcal{L}$$
<!-- gallery:end -->

Regenerate with `pixi run python -m tools.gallery`.
