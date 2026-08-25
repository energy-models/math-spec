<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# PyPSA feature table

Milestone 1: every row a plain single-period `n.optimize()` emits, against what
math-spec states today in one file with no scripting.

Source: PyPSA `0d7d683` (2026-07-23), `pypsa/optimization/`. Names follow
`Component_attribute`; the first underscore is PyPSA's `-`.

## Rules

- `bounds:` takes a name or a number, like PyPSA; anything else is data prep.
- Bound rows are spelled as PyPSA spells them, as constraints, so `mu_upper`
  and `mu_lower` are row duals.
- No base mask. `active` is all-true in a single-period network.
- One cumulative file. Regimes are data columns and become `where:` masks.
- Gate: solution and per-named-constraint duals against `n.optimize()`. Where
  one PyPSA row is several blocks here, the dual is compared after
  concatenation.

## Legend

### Columns

| column     | contents                                                                                      |
| ---------- | --------------------------------------------------------------------------------------------- |
| `PyPSA`    | the linopy name PyPSA gives the row (`name=` in `pypsa/optimization/`), or the objective term |
| `where`    | the regime that emits it, as the `where:` mask it becomes here; blank means always            |
| `spelling` | the math-spec expression or declaration keys, with component prefixes dropped (see Names)     |
| `status`   | one word from the Status table                                                                |
| `note`     | a note ID below the table, an issue number, or the `n.optimize()` keyword for a `flag`        |

### Status

| status  | meaning                                                   |
| ------- | --------------------------------------------------------- |
| `yes`   | one-to-one in the language                                |
| `prep`  | in the language once a parameter is computed in data prep |
| `split` | one PyPSA row becomes N `where:` blocks                   |
| `not`   | a PyPSA workaround we deliberately do not reproduce       |
| `flag`  | only emitted under an `n.optimize()` keyword; later       |
| `scope` | multi-period or stochastic; later                         |
| `open`  | not stateable yet                                         |

A row can carry two, e.g. `prep, split`.

### Regimes in `where`

| shorthand | full mask                                              |
| --------- | ------------------------------------------------------ |
| `ext`     | `<c>_p_nom_extendable == True`                         |
| `com`     | `<c>_committable == True`                              |
| `mod`     | `<c>_p_nom_mod > 0`                                    |
| `t0`      | `position(snapshot) == 0`                              |
| `cyclic`  | `StorageUnit_cyclic_state_of_charge == True`           |
| bare name | the parameter is defined and finite at that coordinate |
| `…`       | the regime of the row above, continued                 |

### Names

| in the table              | meaning                                                                                          |
| ------------------------- | ------------------------------------------------------------------------------------------------ |
| `{c}`                     | any component the row applies to: Generator, Link, Line, Transformer, Store, StorageUnit         |
| `{attr}`                  | the component's operational attribute: `p`, `s`, `e`, `p_dispatch`, `p_store`, `state_of_charge` |
| `SU`                      | StorageUnit                                                                                      |
| `p`, `p_nom`, `status`, … | the declaration `<c>_<attr>`; the `Component_` prefix is dropped when the row is generic         |
| `soc`                     | `StorageUnit_state_of_charge`                                                                    |
| `eh`                      | `snapshot_weightings.stores`; `w_gen` and `w_objective` the `generators` and `objective` columns |
| `eff_d`, `eff_s`          | `efficiency_dispatch`, `efficiency_store`                                                        |
| `ru`, `r_su`              | `ramp_limit_up`, `ramp_limit_start_up`; `rd`, `r_sd` the down analogues                          |
| `M`                       | the big-M constant, a per-entity parameter from data prep                                        |
| `member`, `glc_*`         | 0/1 membership and weight parameters over a `glc` dimension, from data prep                      |
| `mirror`, `same`          | the row above with the sign or component swapped                                                 |
| `shift(x)`                | `shift(x, over=snapshot, offset=1, edge=0)` unless spelled out                                   |

### Notes

Note IDs are section letter plus a counter: V variables, N nominal, B bounds,
U unit commitment, R ramps, F fixed, W network, G global, O objective.

## Variables

| PyPSA                                                                      | where        | spelling                                               | status | note                  |
| -------------------------------------------------------------------------- | ------------ | ------------------------------------------------------ | ------ | --------------------- |
| `{c}-p`, `-s`, `-e`, `Store-p`, SU `-p_dispatch/-p_store/-state_of_charge` |              | `foreach: [snapshot, c]`, no bounds                    | yes    |                       |
| `{c}-status`, `-start_up`, `-shut_down`                                    | com          | `domain: binary`                                       | yes    | V1                    |
| same, modular committable                                                  | com and mod  | `domain: integer`, `lower: 0`                          | yes    | V2                    |
| `{c}-p_nom`, `-s_nom`, `-e_nom`                                            | ext          | `foreach: [c]`                                         | yes    |                       |
| `{c}-n_mod`                                                                | ext and mod  | `domain: integer`, `lower: 0`                          | yes    |                       |
| `StorageUnit-spill`                                                        | `inflow > 0` | `lower: 0, upper: StorageUnit_inflow`, `absence: zero` | yes    | V3                    |
| `{c}-loss`                                                                 |              |                                                        | flag   | `transmission_losses` |
| `CVaR-a`, `CVaR-theta`, `CVaR`                                             |              |                                                        | scope  | stochastic            |
| `objective_constant`                                                       |              |                                                        | not    | V4                    |

- V1: the continuous [0,1] status of `linearized_unit_commitment` is a flag.
- V2: the upper bound comes from the `-fixed-upper` rows, as in PyPSA.
- V3: PyPSA skips the whole variable when no inflow is positive; `where:` yields
  the same columns.
- V4: bookkeeping so `objective` reports the same number; compare objectives
  net of `n._objective_constant`.

## Nominal-side constraints

| PyPSA                                                | where               | spelling                                    | status | note |
| ---------------------------------------------------- | ------------------- | ------------------------------------------- | ------ | ---- |
| `{c}-ext-p_nom-lower`                                | ext                 | `p_nom >= p_nom_min`                        | yes    |      |
| `{c}-ext-p_nom-upper`                                | ext and `p_nom_max` | `p_nom <= p_nom_max`                        | yes    | N1   |
| `{c}-p_nom_set`                                      | `p_nom_set`         | `p_nom == p_nom_set`                        | yes    |      |
| `{c}-p_nom_modularity`                               | ext and mod         | `p_nom - n_mod * p_nom_mod == 0`            | yes    |      |
| `{c}-status/start_up/shut_down-p_nom-variable-upper` | com and ext and mod | `status - n_mod <= 0`, over `[snapshot, c]` | yes    |      |

- N1: a bare parameter in `where:` means finite, which is PyPSA's
  `mask=(upper != inf)`.

## Operational bounds

These rows carry `mu_upper` and `mu_lower`.

| PyPSA                                         | where                   | spelling                                              | status | note |
| --------------------------------------------- | ----------------------- | ----------------------------------------------------- | ------ | ---- |
| `{c}-fix-{attr}-lower/upper`                  | not ext and not com     | `p >= p_min_pu * p_nom`                               | yes    | B1   |
| `{c}-ext-{attr}-lower/upper`                  | ext and not com         | `p - p_min_pu * p_nom >= 0`                           | yes    |      |
| `{c}-com-p-lower/upper`                       | com, not ext, not mod   | `p - p_min_pu * p_nom * status >= 0`                  | yes    |      |
| `{c}-com-mod-p-lower/upper`                   | com and mod             | same with `p_nom_mod`                                 | yes    |      |
| `{c}-com-ext-p-lower/-upper-bigM/-upper-cap`  | com and ext and not mod | `p - p_min_pu*p_nom - M*status >= -M`, …              | prep   | B2   |
| `{c}-com-ext-p-lower-nonneg`                  | … and `p_min_pu_nonneg` | `p >= 0`                                              | prep   | B3   |
| `{c}-status/start_up/shut_down-p-fixed-upper` | com                     | `status <= 1`; modular: `status <= p_nom / p_nom_mod` | split  | B4   |

- B1: arithmetic is fine in a constraint; PR #81's "multiply it out" existed
  only because it used `bounds:`. PyPSA's `inf * 0 -> 0` policy is data prep.
- B2: `M` per generator is `p_nom_max * p_max_pu` if finite, else PyPSA's
  inferred `big_m_default` (peak load, max `p_nom`), a network-wide reduction.
- B3: PyPSA's mask is `(p_min_pu >= 0).all(snapshot)`; a reduction inside
  `where:` is not in the language, so a per-generator bool.
- B4: PyPSA raises when `p_nom` is not an integer multiple of `p_nom_mod`; we
  would build it. A refusal gap of the #11 kind.

## Unit commitment

| PyPSA                                       | where                          | spelling                                                                  | status | note                         |
| ------------------------------------------- | ------------------------------ | ------------------------------------------------------------------------- | ------ | ---------------------------- |
| `{c}-com-transition-start-up`               | com and not t0                 | `start_up - status + shift(status, over=snapshot, offset=1, edge=0) >= 0` | split  | U1                           |
| same, first snapshot                        | com and t0                     | `start_up - status >= -status_initial`                                    | split  | U1                           |
| `{c}-com-transition-shut-down`              |                                | mirror                                                                    | split  |                              |
| `{c}-com-up-time`                           | `min_up_time > 0` and not t0   | `sum_back(start_up, over=snapshot, within=min_up_time) - status <= 0`     | yes    | U2                           |
| `{c}-com-down-time`                         | `min_down_time > 0` and not t0 | `sum_back(shut_down, …) + status <= 1`                                    | yes    |                              |
| `{c}-com-status-min_up_time_must_stay_up`   | `must_stay_up`                 | `status == 1`                                                             | prep   | U3                           |
| `{c}-com-status-min_down_time_must_stay_up` | `must_stay_down`               | `status == 0`                                                             | prep   | U3                           |
| `{c}-com-p-before/-current/-partly-*`       |                                |                                                                           | flag   | `linearized_unit_commitment` |

- U1: PyPSA puts -1 / +1 into the t0 RHS for units with `up_time_before > 0`;
  here a 0/1 parameter `status_initial` and a second block.
- U2: per-entity `within=` is PyPSA's per-generator rolling width
  (`constraints.py:452`). `min_up_time` must be `dtype: int`.
- U3: PyPSA's mask is `position < min_up_time - up_time_before`; `position()`
  compares to a literal only. Candidate language item:
  `position(dim) OP <int parameter>`.

## Ramps

| PyPSA                              | where                                     | spelling                                                            | status | note |
| ---------------------------------- | ----------------------------------------- | ------------------------------------------------------------------- | ------ | ---- |
| `{c}-p-ramp_limit_up`, fixed       | `ramp_limit_up`, not com, not ext, not t0 | `p - shift(p, edge=0) <= ru * p_nom`                                | split  | R1   |
| same, committable fixed            | … com and not ext                         | `… <= ru*p_nom*shift(status) + r_su*p_nom*(status - shift(status))` | split  | R1   |
| same, extendable                   | … ext and not com                         | `p - shift(p) - ru * p_nom <= 0`                                    | split  | R1   |
| same, first snapshot               | … t0 and `p_initial`                      | `p - p_initial <= …`                                                | split  | R2   |
| `{c}-p-ramp_limit_down`            |                                           | mirror                                                              | split  |      |
| `{c}-p-ramp_limit_*-bigM` (4 rows) | com and ext and not mod                   | as PyPSA, `M` from data prep                                        | prep   | B2   |

- R1: PyPSA emits one row whose terms depend on which regimes exist; here one
  block per regime. `where: ramp_limit_up` is "limit given", PyPSA's
  `~no_up_limit`.
- R2: PyPSA keeps the t0 row only when the initial dispatch is known. A
  numeric `shift` edge over a variable can only be 0, so the initial value is a
  parameter in its own block.

## Fixed operation

| PyPSA               | where   | spelling                        | status | note |
| ------------------- | ------- | ------------------------------- | ------ | ---- |
| `{c}-{attr}_set`    | `p_set` | `p == p_set`                    | yes    | F1   |
| `StorageUnit-p_set` | `p_set` | `p_dispatch - p_store == p_set` | yes    |      |

- F1: PyPSA's mask is `~isnull(fix)`, which is "defined".

## Network

| PyPSA                                                   | where              | spelling                                                                                                                      | status | note                  |
| ------------------------------------------------------- | ------------------ | ----------------------------------------------------------------------------------------------------------------------------- | ------ | --------------------- |
| `Bus-nodal_balance`                                     |                    | `sum(x, by=x_bus)` per component and port, `== -sum(Load_p_set, by=Load_bus)`                                                 | yes    | W1                    |
| `Bus-meshed-{30,100,400}-nodal_balance`                 |                    |                                                                                                                               | not    | W2                    |
| nodal balance, link delay                               |                    | `shift(Link_p, over=snapshot, offset=Link_delay1, edge=…)`                                                                    | open   | W3, #75               |
| `Kirchhoff-Voltage-Law`                                 |                    | `sum(cycle_incidence * Line_x_pu_eff * Line_s * 1e5, over=line) == 0`, over `[snapshot, cycle]`                               | prep   | W4                    |
| `StorageUnit-energy_balance`, cyclic                    | `cyclic`           | `shift(soc, offset=1, edge='wrap') * soc_carry - soc - eh/eff_d * p_dispatch + eh*eff_s * p_store - eh * spill == -inflow*eh` | split  | W5                    |
| same, non-cyclic                                        | not cyclic, not t0 | same with `edge=0`                                                                                                            | split  | W6                    |
| same, non-cyclic first snapshot                         | not cyclic, t0     | `… == -inflow*eh - soc_initial * soc_carry`                                                                                   | split  | W6                    |
| `Store-energy_balance`                                  |                    | same shape with `e`, `Store_p`, `e_cyclic`, `e_initial`                                                                       | split  |                       |
| `Generator-e_sum_min/max`                               | `e_sum_min`        | `sum(Generator_p * w_generators, over=snapshot) >= e_sum_min`                                                                 | yes    | W7                    |
| `{c}-loss_upper`, `-loss_secants-*`, `-loss_tangents-*` |                    |                                                                                                                               | flag   | `transmission_losses` |

- W1: link ports as `- sum(Link_p, by=Link_bus0) + sum(Link_p * Link_efficiency, by=Link_bus1) + sum(Link_p * Link_efficiency2, by=Link_bus2) …`.
  A partial lookup contributes nothing, which is PyPSA's `bus_i == ""` drop.
  Buses with an empty LHS are rows not built; PyPSA raises if such a bus has
  load, a refusal we lack.
- W2: a linopy-speed workaround (`meshed_thresholds`). One `Bus_nodal_balance`;
  `marginal_price` compared over the union.
- W3: per-entity `offset=` is in the language; the per-link edge kind
  (`cyclic_delay1`) is not. Workaround: two shifted sums with 0/1 coefficients.
  Value and dual parity, different structure.
- W4: the cycle basis is topology, so data prep (lpspec `pypsa_kvl.yaml`). Keep
  the `1e5`; PyPSA does not assign the KVL dual.
- W5: `soc_carry = (1 - standing_loss) ** eh` is data prep because `**`
  refuses an additive base. `eh` is `snapshot_weightings.stores`. `spill` is
  `absence: zero`, so the term vanishes as in PyPSA.
- W6: one PyPSA row, three blocks; `mu_energy_balance` compared after
  concatenation. Mixed fleets (lpspec `pypsa_mixed_cycling.yaml`) fall out.
- W7: `-inf` is not "defined", so the mask matches PyPSA's `> -inf`.

## Global constraints

PyPSA names them all `GlobalConstraint-{name}`; type and comparator are data.
A comparator is fixed per block, so each type is three blocks
(`where: sense == "<="`, `">="`, `"=="`). Candidate language item: a
comparator from data.

| PyPSA type                            | spelling                                                                                                                                   | status      | note                |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | ----------- | ------------------- |
| `primary_energy`                      | `sum(Generator_p * w_gen * at(glc_carrier_weight, by=Generator_carrier) / efficiency, over=[snapshot, generator]) + depletion <= constant` | prep, split | G1                  |
| `operational_limit`                   | same without the carrier weight; `glc_member[glc, generator]`                                                                              | prep, split |                     |
| `transmission_volume_expansion_limit` | `sum(Line_length * Line_s_nom * member, over=line) + link term <= constant`                                                                | prep, split | G2                  |
| `transmission_expansion_cost_limit`   | same with `capital_cost`                                                                                                                   | prep, split |                     |
| `tech_capacity_expansion_limit`       | `sum(Generator_p_nom * member, over=generator) …`                                                                                          | prep, split | G3                  |
| `Bus-nom_min_{carrier}` / `nom_max`   |                                                                                                                                            | not         | deprecated in PyPSA |
| `Carrier-growth_limit`                |                                                                                                                                            | scope       | multi-period        |
| `effect_limit`, priced effects        |                                                                                                                                            | open        | G4                  |

- G1: the depletion term needs "soc at the last snapshot"; no indexing in an
  expression, so `sum(soc * is_last, over=snapshot)` with a 0/1 `is_last`.
  Candidate language item: a value at a `position()`. Only non-cyclic units
  contribute, a 0/1 coefficient.
- G2: membership from PyPSA's comma-split carrier string is data prep.
- G3: bus selection folded into `member`.
- G4: `effects.py` is reachable from `create_model` and not inventoried yet.

## Objective

| PyPSA term                        | spelling                                             | status | note |
| --------------------------------- | ---------------------------------------------------- | ------ | ---- |
| `marginal_cost`                   | `sum(Generator_p * marginal_cost * w_objective)`     | yes    | O1   |
| `marginal_cost_storage`           | same on `Store_e`, `state_of_charge`                 | yes    |      |
| `spill_cost`                      | same on `spill`                                      | yes    |      |
| `marginal_cost_quadratic`         | `sum(Generator_p * Generator_p * mcq * w_objective)` | yes    | O2   |
| `stand_by_cost`                   | `sum(status * stand_by_cost * w_objective)`          | yes    |      |
| capital cost, incl. modular       | `sum(Generator_p_nom * capital_cost)`                | prep   | O3   |
| `start_up_cost`, `shut_down_cost` | `sum(start_up * start_up_cost)`                      | yes    | O4   |
| objective constant                |                                                      | not    | V4   |

- O1: `w_objective` is `snapshot_weightings.objective`. Same for Link,
  `Store_p`, `StorageUnit_p_dispatch`.
- O2: degree 2 in the objective is allowed; HiGHS refuses it against
  integrality, a solver matter.
- O3: `periodized_cost` (annuity from `overnight_cost`, `lifetime`,
  `discount_rate`, `fom_cost`) is data prep. The cost sits on the capacity
  variable, not `n_mod`, as in PyPSA.
- O4: unweighted in PyPSA; keep it that way.

## Post-solve

math-spec declares shape; reading back is the consumer's. These live in the
parity harness on the lpspec side.

| PyPSA                                                         | harness                                                  |
| ------------------------------------------------------------- | -------------------------------------------------------- |
| `Bus-nodal_balance` dual / `w_objective` -> `marginal_price`  | normalise the same way before comparing                  |
| five upper rows `combine_first` -> `mu_upper`                 | concatenate our regime blocks; disjoint by construction  |
| `Link-p` -> `p0`, `p1 = -p * efficiency`; `Line-s` -> `p0/p1` | derived; compare `p0`                                    |
| `n_mod` discarded                                             | compare `p_nom_opt` only                                 |
| KVL, `e_sum_*`, `growth_limit` duals                          | PyPSA does not assign them; compare only what it exposes |

## Out of scope for milestone 1

Each is an `n.optimize()` keyword or variant: `multi_investment_periods`,
stochastic scenarios and CVaR, `transmission_losses`,
`linearized_unit_commitment`, rolling horizon, `optimize_mga`, `abstract.py`,
`effects.py`. lpspec ports `pypsa_multi_period`, `pypsa_stochastic`,
`pypsa_cvar`, `pypsa_losses`, `pypsa_linearized_uc`, `pypsa_growth_limit`.

## Summary

Nothing a plain `n.optimize()` emits is unstateable. The debt is three kinds:

1. **Data prep contract.** Parameters the file expects that PyPSA computes:
   `big_M`, `soc_carry`, `periodized_cost`, `cycle_incidence`,
   `p_min_pu_nonneg`, `must_stay_up`, `is_last`, glc membership and weights,
   `status_initial`. One documented function `network -> tables`.
2. **Row splitting.** Regimes, first-snapshot rows and comparators become
   `where:` blocks. Candidate language items, none blocking:
   `position() OP parameter` (U3), a value at a position (G1), a comparator
   from data (global constraints). Plus #75 (W3), the only workaround that
   changes structure.
3. **Refusals PyPSA has and we lack.** Non-integer `p_nom / p_nom_mod` (B4),
   load on an unconnected bus (W1). Both of the #11 kind.

Ladder to grow the one file in, each rung keeping the rows above it green
against a real PyPSA network: transport, storage (cyclic and non-cyclic),
expansion, ramps, global constraints, KVL, commitment (MILP, solution only),
modular and big-M, multi-link and delay.

Spellings seeded from lpspec `examples/ports/pypsa_*.yaml` and PR #81's
`t1`/`t2`.
