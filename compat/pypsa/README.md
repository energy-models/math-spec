<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# PyPSA parity

What `n.optimize` emits, in the order we take it on, and what it takes for
lpspec to state the same thing. The aim is lpspec, or its core, building the
model PyPSA solves — so this is **compatibility groundwork**, and every rung is
a claim about parity. Nothing here is timed. Every number in this directory is
a count of something in a model, never a duration.

One tier = one YAML model in `compat/pypsa/models/`, one PyPSA network built by
`compat/pypsa/network.py`, one construct `n.optimize` emits that lpspec has to
be able to state.

A tier is _conquered_ when five things hold:

1. `compat/pypsa/models/tN_*.yaml` builds and solves through lpspec,
2. the same instance solves through `n.optimize(solver_name='highs')`,
3. the two objectives agree to `1e-9` relative — which also compares the column
   count,
4. the two lanes state one LP: as two linopy models, and as the two populated
   `highspy.Highs` a solver would be handed, and
5. every answer the rung produces lands where PyPSA reads it — the
   [return trip](#the-return-trip).

Rung 4 is what keeps the claim honest past the optimum, because an objective is
one number and two different models reach it whenever the difference does not
bind: swap a store's charge and discharge efficiencies and the optimum does not
move, so rungs 1 to 3 stay green and rung 4 is the one that refuses it. Rung 5
is the only one that leaves the model behind and looks at the answer.

## The ladder

| tier              | adds                                                               | PyPSA statements                                                             | YAML constructs                                                  | class | port to crib from                                      |
| ----------------- | ------------------------------------------------------------------ | ---------------------------------------------------------------------------- | ---------------------------------------------------------------- | ----- | ------------------------------------------------------ |
| **T1** transport  | generator dispatch, controllable links, nodal balance, linear cost | `Generator-fix-p-lower/upper`, `Link-fix-p-lower/upper`, `Bus-nodal_balance` | `bounds`, `sum(by=)`, three lookups                              | LP    | `examples/ports/pypsa_transport.yaml`                  |
| **T2** storage    | a store carrying energy between snapshots, cyclic                  | `StorageUnit-energy_balance`, `StorageUnit-fix-p_dispatch/p_store-*`         | `shift(over=snapshot, wrap)` — the self-join                     | LP    | `pypsa_cyclic_storage.yaml`                            |
| **T3** ramps      | output may only move so far between snapshots; link efficiency     | `Generator-fix-p-ramp_limit_up/down`                                         | `shift(offset=1)` on a variable, a coefficient on a lookup sum   | LP    | `pypsa_ramp.yaml`                                      |
| **T4** expansion  | capacity is a variable, not a parameter                            | `Generator-ext-p-lower/upper`, `Generator-ext-p_nom-*`                       | a variable in a bound's place, so the bound becomes a constraint | LP    | `pypsa_fixed.yaml`, `pypsa_growth_limit.yaml`          |
| **T5** KVL        | lines with reactance, flows around a cycle                         | `Kirchhoff-Voltage-Law`                                                      | a cycle-incidence parameter and a `sum(by=)` over it             | LP    | `pypsa_kvl.yaml`                                       |
| **T6** budgets    | a CO2 cap priced through the carrier map                           | `GlobalConstraint-primary_energy`                                            | two coordinates on one dimension, `sum` over all                 | LP    | `pypsa_global_limits.yaml`, `pypsa_ac_dc.yaml`         |
| **T7** commitment | dispatch gated by a binary status, minimum up and down time        | `Generator-com-p-lower/upper`, `Generator-com-status-min_up_time`            | `vtype: binary`, windowed `sum`                                  | MILP  | `pypsa_unit_commitment.yaml`, `pypsa_min_up_down.yaml` |

The order is the order of difficulty, not of importance: T4 makes the model's
row count depend on a decision and T7 makes it a MILP, so each is a separate
claim about what lpspec can state, and a rung that fails is a gap in the
language rather than a bad number.

**Rungs are independent.** Every tier above T1 is T1 plus exactly one
construct, and T1 is the control. The alternative — T2 = T1 + storage, T3 =
that + ramps, up to a T7 carrying all seven — leaves a parity failure at T7
with seven candidate causes and no way to bisect it.

That independence is a debugging property and **not a coverage claim**: a real
network carries storage and ramps and expansion at once, and parity breaks most
easily where two constructs meet — a ramp limit on an extendable generator, a
store whose energy ceiling is itself a variable. So a cumulative rung on top of
the ladder is owed, once enough of the independent ones stand to make its
failures readable. Until it exists, this ladder says nothing about interactions.

The rule the independence imposes on the code: **both lanes read the same
rung.** A tier that adds storage to the YAML and not to `network.py` is a tier
whose two lanes solve different problems, and rung 4 above is what refuses it.
What a rung asks for is therefore not written twice: `Tier.components` reads the
components off the model's own declaration names — the half before the first
underscore — and `build_network` builds those and refuses one it has no lane
for, so a rung's PyPSA network cannot fall behind its YAML.

## What is not on the ladder yet

Multi-period investment, stochastic and CVaR formulations, losses, link delay,
modular capacity, spill, multi-link. Every one has a port under
`examples/ports/`, so lpspec can state them; none is on the ladder because none
is what a plain `n.optimize` on a plain network emits, and the ladder is
ordered by what an integration meets first. They are **gaps in the sequence,
not exclusions** — an integration eventually owes parity on each, and on the
`n.optimize` variants no rung reaches at all: multi-investment periods,
scenarios, and rolling horizons.

## Naming

Every declaration a rung makes is named `<Component>_<attribute>` after the
PyPSA statement it stands for — `Generator_p`, `Link_p`, `Bus_nodal_balance`,
`Generator_marginal_cost`, `Load_p_set` — and so is every parquet table, since
a table is a parameter's source and takes its name. Dimensions keep their bare
lowercase names: a dimension is an index set rather than an attribute of a
component, and PyPSA's own linopy model calls all of them `name` regardless.

PyPSA joins the two halves with `-`; lpspec cannot, its expression parser
reading a hyphen as subtraction (`Generator-p` parses as `Generator` minus
`p`). **The first underscore is the join**, so `Generator_p` is
`Generator-p` and `Bus_nodal_balance` is `Bus-nodal_balance` — one replacement,
not all, which is why the rule is written that way and not as a blanket swap.

That convention is doing more work than making two models diffable: it is a
first sketch of the mapping an integration needs in code, from a PyPSA
component and attribute to a declaration and back. `Tier.components` already
reads it in one direction, which is why a rung's network cannot fall behind its
model.

## Three models, and which gate holds which

There are three of them per rung, not two, and naming them is what keeps the
gates straight:

| model                           | built by                          | gated by                                                        |
| ------------------------------- | --------------------------------- | --------------------------------------------------------------- |
| PyPSA's linopy model            | `n.optimize.create_model()`       | the oracle for both structural gates                            |
| lpspec's **eager** linopy model | `lpspec.linopy.build`             | `..._builds_the_linopy_model_pypsa_builds`, keyed by coordinate |
| lpspec's **relational** model   | `lps.build`, streamed to the sink | `..._hands_highs_the_model_pypsa_hands_it`                      |

The middle one asks whether lpspec states PyPSA's model _through PyPSA's own
backend_; the bottom one asks whether the streaming core, which is what an
integration would actually put underneath PyPSA, hands a solver the same LP.
Until that second gate landed the relational lane was tied to PyPSA by an
objective and a column count and nothing about what it had written.

Neither lane names anything it loads into HiGHS — `build_highs` sets no names
and `to_highspy(set_names=False)` asks for none — so that comparison cannot key
on a coordinate: a column is identified by what it says, `(cost, lower, upper,
integrality)`, and a row by its coefficients each paired with the signature of
the column it multiplies, both sorted. That is weaker than the
coordinate-keyed gate exactly where two columns share a signature, and it is
the only gate on the object a solver receives — which is why both exist rather
than one.

## Where the two lanes differ: a bound is not a row

The gates compare the optimum, the columns, and every row that has two or more
terms in it. They do not compare the raw row count, because the two lanes do
not agree on it and both are right:

|                  | columns | lpspec rows | PyPSA / linopy rows |
| ---------------- | ------- | ----------- | ------------------- |
| **T1** transport | 384     | 96          | 864                 |
| **T2** storage   | 672     | 192         | 1536                |

PyPSA emits every bound as an explicit constraint row — `Generator-fix-p-lower`
and `-upper` over 12 generators x 24 snapshots, the same pair over 4 links,
768 rows before T1's 96 nodal balances, and another 576 over T2's three storage
variables — where lpspec carries them on the columns and leaves PyPSA's own
columns at `+-inf`. **Those bound rows are the whole difference**, which is not
an assumption: both structural gates fold every single-variable row into the
column it constrains, and after that fold the two models are equal term for
term. The HiGHS gate then compares the row counts too, there being nothing left
to excuse a row the other lane does not have.

This is the first real consequence for an integration, and it is not about
size. PyPSA reads shadow prices off its rows _by name_: `Bus-nodal_balance`
becomes `n.buses_t.marginal_price`, and `Generator-fix-p-upper` becomes
`n.generators_t.mu_upper`. Prices survive a swap of the backend, because a
nodal balance is a real row on both sides. The bound duals do not: with the
bound on the column there is no row to take a dual from, and `mu_upper` can
only come from a reduced cost, which lpspec does not expose
([api.md](../../docs/reference/api.md)). By default PyPSA leaves those
attributes empty and logs what it skipped, so nothing breaks until a caller
asks for `assign_all_duals=True` — at which point the answer has to come from
somewhere else.

## Shape

The tier fixes the _constructs_; `Shape` fixes the _size_ — snapshots x buses x
generators per bus, 24 snapshots at the bottom rung, one store per bus. Parity
does not need a size ladder: one small instance either states the same LP or
does not. A second, differently proportioned shape is worth having for a
different reason — alignment and broadcasting bugs are shape-dependent, and a
dimension of length one, or as many generators as buses, is where a lane
quietly transposes something.

`Shape` grows a field when a tier needs one, and that field goes into the seed
of the stream that reads it and never into `Shape.key`: a rung's instance must
not move when a rung above it is added, or a failure found once stops being
reproducible and the rungs below start failing for reasons that are not theirs.
`network._seed` takes the stream name for the same reason.

## The return trip

The three gates above are all about the model going _in_. An integration also
has to get the answer back out, into the frames PyPSA's readers, its statistics
module and its plots take it from — `n.generators_t.p`, `n.links_t.p0`,
`n.storage_units_t.state_of_charge`, `n.buses_t.marginal_price`. That is a
mapping from a declaration to a place, and `..._answers_where_pypsa_reads`
gates it **both ways**: every declaration the rung makes has a slot, every slot
PyPSA fills has a declaration answering it, and the two agree coordinate for
coordinate.

The naming convention carries it, read a third way. `_as_pypsa` turns
`Generator_p` into the linopy name `Generator-p`; `_slot` turns either spelling
into `(Generator, p)`, the component and the _dynamic attribute_, with one small
table of exceptions taken from `assign_solution` and `assign_duals`: a link's
flow is reported at its `bus0` end as `p0`, and a nodal balance's shadow price
as `marginal_price`.

**Values are deliberately not compared.** An LP with alternative optima has many
optimal primal solutions, so the two lanes may legitimately sit on different
vertices and a value comparison would be flaky about the wrong thing.
`tests/test_corpus_parity.py` is where values are pinned, against recordings
rather than across lanes.

What this gate sees that no structural gate can: **a frame is not the model.**
PyPSA reindexes a dynamic frame over every component it holds, so a bus that
carries nothing gets a `marginal_price` column while `Bus-nodal_balance` gets no
row for it — a slot a reader looks in and neither lane fills. All three
structural gates stay green on that and this one does not. Where it is weaker:
two attributes of one component that lay out over the same coordinates are
interchangeable to it, `Link.p` and `Link.p0` being exactly that pair, so the
gate proves a place with the right shape exists rather than that it is the only
right one. It happens not to matter for that pair — `assign_solution` writes the
same numbers to both — and it is the same kind of weakness the HiGHS gate has
where two columns share a signature.

## Known gaps against `n.optimize`

A line-by-line reading of PyPSA's `pypsa/optimization/` — `variables.py`,
`constraints.py`, `global_constraints.py`, the objective in `optimize.py`, and
the `n.optimize` variants in `abstract.py`, `mga.py` and `piecewise.py` —
against what mathspec's language and lpspec's build/solve engine can state
today. One entry per construct PyPSA emits that neither can yet. Nothing here
is measured; where a claim was not checked against the code it says so. Issue
numbers are lpspec's.

### The big-M ramp lane

Committable ∧ extendable ∧ non-modular. Where its neighbouring regimes emit one
constraint, this one emits four named constraints over a big-M relaxation
(`constraints.py:893`). The row _count_ changes with the regime, so no
case-split syntax reaches it — the regimes do not share a shape. For now this
will be written as two different constraints.

### A window width that varies along the axis it sums over — #73

`define_maintenance_constraints` (`constraints.py:725`). The event-count and
start-validity rows are ordinary; the coverage row is a rolling sum whose width
is a per-`(name, snapshot)` value, which PyPSA handles by enumerating every
distinct width and masking:

```python
coverage = [
    maintenance_start.rolling(snapshot=int(w), min_periods=1).sum() * (width == w) for w in unique(width.values)
]
```

The maintenance _variables_ are ordinary binaries; it is only this row that
blocks them.

### Piecewise-linked coefficients in the nodal balance — #77

Members carrying a curve contribute an auxiliary variable where the rest
contribute `var * coeff`, split by name at `constraints.py:1483`. This is not
the case split above: the two branches have different _arity_, not different
coefficients, so #711 cannot reach it. #1133 and #496 are the same block's
other limits, and they are what PyPSA's `piecewise.py` API needs in full.

### A mixed `edge=` kind in one `shift` — #75

`cyclic_delay` is a per-link column, so one network wraps some links and
zero-fills others inside a single `shift`. `examples/ports/pypsa_link_delay.yaml`
ports one regime. #1041 already recorded the per-entity edge _kind_ as out of
scope and pointed at #849; the link-delay witness is on it.

A per-entity numeric edge is a different idea and not the answer here: a
numeric edge over a variable is restricted to `0`, because a nonzero constant
would stand where a term was.

### A data combination that cannot be built has no load-time refusal — #11

Continuous depletion combined with unequal period weightings: PyPSA raises
`NotImplementedError` (`global_constraints.py:430` and `:635`). mathspec would
build it and return a wrong number. **The only gap in this document whose
absence is a wrong answer rather than an error.**

### `bounds:` takes no `where:` — #1220

A fleet where some entities have a fixed value and the rest are free needs one
merged column built in data preparation, because the equal-bounds pin has no
way to apply to part of an index. Two things land here: PyPSA's phase-shift
variables, created only where `phase_shift_min < phase_shift_max` and constant
elsewhere, and the parameter-vs-variable half of the committable ramp regimes.

Not necessarily needed: this can be mirrored logically by fixing the variables
via an additional constraint for the fixed set, at the cost of a different
formulation of the same optimization problem.

### Parsing of duals and creation of post-solve expressions — #74, #8

PyPSA extracts duals and composed expressions as results. mathspec has no way
to state this yet.

### Supported, but not yet on the ladder

| PyPSA                                  | note                                                                                                                                                                                                                                                                                   |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `marginal_cost_quadratic`              | quadratic landed: `sum(p * p, over=g)` builds on both lanes and through the LP file. HiGHS takes a Hessian but **excludes it against integrality and against SOS**, so a quadratic-cost committable network needs gurobi — declared in the sink descriptor, so the refusal names both. |
| `define_tech_capacity_expansion_limit` | one grouped sum against a per-`(carrier, period)` cap — a shape `pypsa_global_limits` already states three times.                                                                                                                                                                      |

### More abstract routines, low priority for now

| routine                                              | note                                                                                                                                                                                                                                 |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `optimize_with_rolling_horizon`                      | `solve_over` / `rebind` is exactly this loop. A rung would prove it.                                                                                                                                                                 |
| `optimize_transmission_expansion_iteratively`        | the same loop with per-line numbers updated between solves; PyPSA's discretisation helper stays outside.                                                                                                                             |
| `optimize_security_constrained`                      | contingency rows are one more parameter — the branch-outage distribution factors — and one grouped sum. Computing them is data preparation.                                                                                          |
| `optimize_mga`                                       | the cost budget is a row with a parameter right-hand side; the direction weights are parameters in the objective. Open question: whether `rebind` may move an objective coefficient and a right-hand side in one call. _Unverified._ |
| several global limits summing across component types | one term per component type written out, since `sum(by=)` reduces one variable along one dim. A repetition cost, not a defect.                                                                                                       |

`optimize_and_run_non_linear_powerflow` is **out of scope**: the power flow is
not an LP, and only the LP half is this project's.

### False positives

- **Not aimed for reproduction.** With `cyclic_state_of_charge=True` and
  `state_of_charge_initial_per_period=True` (same for `Store`), PyPSA resets
  the level to `state_of_charge_initial` at every period start while warning
  that `state_of_charge_initial` would be ignored — the docs said the same.
  A user would conclude their initial level had no effect, when it was
  actually seeding energy into every period.
- `include_objective_constant` in PyPSA is deprecated; not worth porting —
  keep the objective without constants.

## What is not gated at all

- **Bound duals.** `marginal_price` is gated above, being a real row in both
  lanes. `mu_upper` and `mu_lower` are out of reach by construction — with the
  bound on the column there is no row to take a dual from — and stay a stated
  gap, per the section above.
- **Reduced costs**, likewise.
- **The values themselves**, per the section above: the mapping is gated, the
  numbers in it are not.
