<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# The ceiling

**What may enter the language, and what may never.** The rules a model must
obey are
[the ten rules](../reference/language/index.md#ten-rules-the-language-reduces-to).
This page is the argument in between: the test a
candidate primitive has to pass, why capability is a second axis rather than
part of the ceiling, [what has been refused and why](#deliberate-non-primitives),
and what composition would force.

It is a claim, so it carries evidence — math a ported model needed and this
language could not state becomes a ledger row against the port that needed it,
with its triage verdict beside it.

## Two tiers, and the ceiling

**Primitives** (operators, `sum`, `sum(by=)`, `shift`, `where`
predicates) set the expressive ceiling, and each costs the full two-backend tax:
eager implementation, plan node + locality class, engine case, lowering case,
differential tests, a language-reference entry. **`macros:`** are pure AST substitution — every
composition of primitives at zero marginal cost and zero divergence risk.
**`expressions:`** substitute the same way where referenced and still cost
nothing at build, but they are a tier apart from macros
([named expressions](../reference/language/expressions.md#named-expressions)): a named expression has fixed
dims and an observable identity — readable after a solve via
`result.expression(name)`, lowered on demand at the read through the same
compiler the constraints use, which is what keeps the divergence risk at zero.
A macro is parameterised, has no dims until called, and is never readable.
**Formulations** (`piecewise:`) are taxed like a primitive but
compose like a macro: they emit _new declarations_ before dispatch and never
enter as plan expression nodes.

For any request, triage: **macro, primitive, or escape?** Most are compositions.
New primitives must be **macro-friendly** — anything a user might parameterise
goes in a _value_ position like `over=`/`by=`, never a kwarg key; the
`shift(x, over=snapshot, offset=1)` takes its dimension in a kwarg _value_, so a
macro can pass one as a formal — the dim-as-key design that could not is gone.

A candidate primitive is admissible iff it is **relational** — filter / join /
group-by-aggregate over tidy tables — and **local**, meaning _pointwise_ or
_bounded-halo_, which compose under partition-wise execution where _global_
operators do not. Locality is judged in **data space**: reductions over a
_coordinate_ space ("the last snapshot") read only the small, already
materialised dim tables and stay admissible even though they look global.

**Degree is not the third rule**, and stating it as one was a mistake this page
made for a while. Nothing about `variable × variable` is non-relational or
non-local — a coordinate-aligned product is a pointwise self-join. That
prediction has since been cashed: **the objective takes degree 2**, and what
decided where it could land was not the closure but **what a sink can ingest**,
the second axis below. The same is true of SOS, indicator and semi-continuous.
Read this page as the _streamability_ closure and nothing more.

Two things bound the quadratic case, and neither is streamability:

- **Position — and it has since moved.** A quadratic _objective_ had somewhere
  to land before a quadratic _constraint_ did, and fewer things refuse it —
  which sink takes which being
  measured rather than argued. What kept the
  constraint out is that one _lane_ cannot build one at all, until
  the capability axis grew to cover **lanes** as well as sinks
  (hard rule 3): both lanes still accept the same
  language, what each can _build_ is declared, and the construct ships with the
  gap named rather than hidden. The price is the differential oracle for that
  one construct, which is why the gap is one entry long.
- **One shape, genuinely out.** `sum(x, over=i) * sum(y, over=j)` is every term
  of one against every term of the other — the cross join the old blanket ban
  was really describing, and the one row of the table below that stays
  rejected. A product whose factors are each _one_ term is a join, whatever
  dims they carry: `x[i] * y[j] * a[i, j]` is the honest general bilinear form
  and is admissible, coupled through a declared table.

**Read the verdict off the plan.** Relational and local are one question asked
twice, and the compiler already answers it — write the candidate's query over
the term stream first and read `.explain()`:

| Shape of the emitted query                     | Locality         | Admissible?                  |
| ---------------------------------------------- | ---------------- | ---------------------------- |
| filter on a column already in the frame        | pointwise        | admissible                   |
| equi-join against a parameter or mapping table | pointwise        | admissible                   |
| join on the dim table at `ord ± k`, `k` fixed  | bounded-halo     | admissible                   |
| dim table only, no data join                   | coordinate-space | admissible (free)            |
| window over unbounded rows, or a recursive CTE | global           | **reject**, with the rewrite |

This is the case analysis `_sum_fragment`, `_group_fragment` and
`_translate_fragment` already implement — each rewriting one fragment on its
own, which is what _pointwise_ and _bounded-halo_ mean in code — so a candidate
fitting none of those shapes has no engine to be written into. One limit: it
presumes the terminal `sum(coeff)` over `(row, col)` stays the only aggregate a
_term_ passes through. Degree is decided elsewhere and deliberately — on the
core AST by `language/degree.py`, which both lanes ask and neither states — so
reading it off a query would be reading the wrong artefact. A primitive is
finished when `lowering.py` accepts it and the differential test against the
linopy oracle passes.

**The ceiling is a claim, so it needs evidence.** In the ports ledger, math a
ported model needed and this language could not state becomes a ledger row with
its triage verdict — what the roadmap should be argued from. Those ports also cover a class
no other test reaches: both lanes consume the same resolved AST by rule 1, so a
_shared misreading_ passes the differential suite green, and only an outside
optimum catches it.

What is _outside_ the closure splits three ways, and the split decides whether a
request can ever be met:

| Tier                   | Bounded by                                                                   | Members                                                                                                                                                                                                                                 | Can it move?                                |
| ---------------------- | ---------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| **Capability-bounded** | what a given sink can ingest                                                 | indicator (#220); quadratic, whose verdict moves with its convexity and with what it stands beside. `sos:` **shipped** on this tier, and is what the row predicted: native where a sink has the concept, reformulated where it does not | per sink — the capability table             |
| **Budget-bounded**     | the escape _label_ budget — a cap on the rows and columns an island may emit | global operators, arbitrary Python, non-relational manipulation                                                                                                                                                                         | already movable — that is what an island is |
| **Design-bounded**     | our choice of where work belongs                                             | data prep, domain helpers, Python declaring structure                                                                                                                                                                                   | movable any time; we don't want to          |

Impossible **in the symbolic plan**: conditionals, iteration, any data-dependent
structure inside expressions. What is protected is that the plan's **shape** is
fixed before any data is read — which declarations exist and which dims each
spans. _Cardinality_ is always data's to supply: `foreach: [snapshot]` does not
know how many snapshots there are either.

That distinction decides more than it looks. A dimension whose members are
_computed_ in data prep is completely ordinary — a cycle basis for
KVL, the subsets of a subtour-elimination
family — because a graph algorithm run before the build is design-bounded, the
row above. The line is **temporal, not computational**: it does not matter how
clever the Python is or whether its output size depends on the data, only
whether it can run before the model is built. What is outside **the plan** is
work that needs the solver's _answer_ to decide the next row — lazy cut
generation — because there is no "before" for it to happen in.

**Outside the plan is not outside the engine**, and the difference is the whole
of decomposition. A plan cannot contain a loop; a _process_ may loop over plans,
each with its shape fixed before its own data. Rolling horizon is that shape and
is in scope ([Track 2](https://github.com/fluxopt/lpspec/issues/471)); so are
Benders and successive substitution. Nor does appending a cut cost the label
contract the way removal would: `var_label` is a `ROW_NUMBER()` over the rows
surviving the `where` mask, so adding _rows_ moves no column and renumbers no
existing row, and `addRows` is already how the direct sink feeds the initial
build. What such a scheme still owes an answer on is **who writes the cut** —
rule 5 refuses a Python modeling API, so either a decomposition driver ships
reading the model frames, or the narrow seam for emitting affine rows discussed
under [Composition](#composition-component-libraries) gets blessed. That is a
scope question, not a ceiling one.

This is a different property from how much a build costs, though the two meet at
the escape hatch. That is why an `escape:` island (#38) is admissible where a
registered Python helper was not: its extent is fixed by the preceding `where`
mask, it is terminal, and it is named in the file. Its **label budget is what keeps it
accountable** — an island's cost is bounded by what it may emit, declared and
enforced before any Python runs rather than discovered after it allocates.

An escape buys back the _relational_ and _local_ rules (it returns affine COO
rows — a running-sum island still emits affine rows, just O(T²) of them) but
never **degree**, because affine COO is what it returns. That refusal stands on
what an island _emits_, not on what a sink accepts, so it is unaffected by the
capability findings below.

### Capability is not the ceiling

The ceiling above is about **streamability** and is solver-independent. What a
_sink_ can ingest is a separate axis, and conflating the two let one solver's
limits read as architectural law — "no sink carries the stream" described a
solver, not the architecture. Two findings say why the axis has to be its own,
and the capability table says which sink is which: SOS
is **solver-bounded**, one sink having no concept of a set at all where others
take one natively; and quadratic is bounded **twice over on a single sink**, by
convexity and again by what it stands beside. So a capability is neither a flat
set nor one verdict per construct. The whole-Hessian handoff is an
implementation difference, not a rule-4 violation.

**`sos:` is that finding cashed**, and it says what the axis is worth. The
construct entered on the streamability argument alone — a set names columns a
variable already made, so it is neither an expression node nor a formulation —
and each sink then answers for itself, `native` or `reformulated`, so a
capability gap costs a worse relaxation rather than a refusal. The third value,
`absent`, is what is left for the constructs no rewrite reaches.

It is a **declaration** rather than a constraint for a reason that survives
every sink growing native SOS: neither algebraic statement of a set is in this
language. The complementarity form — `x_i * x_j == 0` wherever `|i - j| >= k`,
which is SOS1 at `k=1` and SOS2 at `k=2` — is degree 2, and the cardinality
form bounds the support, which is not affine at all. So a set is unsayable as
math here whatever a sink can ingest, and saying it _about_ a variable is the
only spelling left.

What a rewrite cannot buy back is the argument _for_ declaring capability: a
set reformulated into binaries returns no duals where the native form does, and
that asymmetry should be visible and the caller's to choose between rather than
papered over. The rest — a capability _table_, and `check` taking an optional
sink — has since shipped
([#925](https://github.com/fluxopt/lpspec/pull/925),
[#928](https://github.com/fluxopt/lpspec/pull/928)).

## Where the data-prep line falls

The table below refuses data preparation as a language feature. It does not say
_which_ precomputation is data prep and which is work the compiler is declining
to do — and from inside a model both look the same: a parameter arrives, a
constraint reads it.

> **Data preparation computes what the model cannot know. The compiler builds
> what it can derive from data the model already has.**

A cycle basis is the first kind: a graph algorithm over a topology only data
supplies, so `pypsa_kvl` carrying `cycle_incidence`
as a parameter is right, and would be in any language. A minimum up time was the
second — `min_up_time` a column the model already binds, the window mask over it
a mechanical consequence the modeller had to write as data — until `within=`
read the width off the column
(minimum up and down times is the witness).
[#849](https://github.com/fluxopt/lpspec/issues/849) is what is left of that
gap.

The first kind is a design, the second a tax, and refusing both under one rule
reads as principle while billing as friction.

**The trade is deliberate, and Calliope made it differently.**
Its components take a list of `where`-guarded equations, so alternatives that
differ by a regime live in the file rather than being flattened into data — one
block for cyclic and non-cyclic storage, where this language wants the
constraint twice ([#711](https://github.com/fluxopt/lpspec/issues/711)). What
buys the difference here is holding the plan's _shape_ fixed before any data is
read, which is what makes a streaming engine and a second independent lane
possible at all. So the ceiling stays, and what is worth importing is the
**checks and the rules, not the machinery**: validate that alternatives cover
their rows exactly once, and stop making a compiler-derivable argument a
literal. Neither widens the closure.

## Deliberate non-primitives

The admissibility test above says what _may_ enter. This is what has been asked
for and refused, with the reason and the rewrite — so a request that has already
been answered is answered once rather than re-argued. Parity with another tool
is not by itself a reason to add anything.

| Request                                                                   | Why                                                                                                                                                                                         | Instead                                                                                                                                                                                                                |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Data prep — resampling, clustering, IO, units                             | not math                                                                                                                                                                                    | preprocess; pass a parameter                                                                                                                                                                                           |
| Arbitrary array ops (`merge`, `reindex`)                                  | unbounded; xarray with extra steps                                                                                                                                                          | data prep                                                                                                                                                                                                              |
| Domain helpers (`reduce_carrier_dim`)                                     | encodes one domain into the language                                                                                                                                                        | component libraries over generic primitives                                                                                                                                                                            |
| A tracked-metric vocabulary — `impacts:`, `effects:`, a `costs` dimension | the three fates are already reference-it-or-don't                                                                                                                                           | an `impact` dim and one named expression: cap it with a constraint whose dual is the shadow price, weight it in the objective, read it with `result.expression` ([#124](https://github.com/fluxopt/lpspec/issues/124)) |
| `**` with a **variable** base or exponent                                 | the exponent would decide the degree, and no data is read at load — `p ** n` is affine at 1, quadratic at 2 and over the ceiling at 3, and the file says which only once the numbers arrive | `x * x` for a square; above degree 2 there is no rewrite. Over variable-free operands `**` **is** in the language ([#1175](https://github.com/fluxopt/lpspec/issues/1175))                                             |
| Normalisation (`x / sum(x)`)                                              | a _variable divisor_ is rational, not polynomial — no sink takes it at any degree                                                                                                           | state the ratio as a constraint, or fix the denominator                                                                                                                                                                |
| Conditionals, iteration, data-dependent structure **inside one plan**     | destroys the closed AST                                                                                                                                                                     | `where` masks + `foreach` dims. A _process_ may loop over plans                                                                                                                                                        |
| A Python API for constructing models                                      | hard rule 5 — the model is the file you review and diff                                                                                                                                     | YAML. Whether Python may _emit_ declarations is [#381](https://github.com/fluxopt/lpspec/issues/381)                                                                                                                   |

Genuinely unsayable math goes to a declared `escape:` island
([#38](https://github.com/fluxopt/lpspec/issues/38)) — named in the file,
bounded by the preceding `where`, terminal, and billed against a label budget
before any Python runs. It buys back _relational_ and _local_; it cannot buy
back degree, since it returns affine COO rows either way.

## Composition (component libraries)

A component library is a fixed set of parametrised templates agreeing on a
port/flow convention, merged into one program, wired through a data connectivity
table and a single `sum(by=)` balance. **Topology is data, not structure** —
wiring a specific system is rows in a connectivity table, never generated YAML,
so structure is bounded by the number of component _types_ while cardinality
lives entirely in data. Schema merge is therefore a pure **compose-then-build**
step producing one `Model` before a single lower/stream pass (native merge is
#30). Namespacing via qualified names is
the missing primitive (#29) — the port/flow surface stays deliberately shared, as
the coupling contract between templates — and signs and bidirectional flows need
bounds-as-expressions (#31).

Whatever genuinely is not data (variable port counts, runtime-unknown component
types) belongs in a thin layer emitting **more rows or more templates, never
per-instance YAML** — and that layer has a supported thing to call. Every
verb takes `str | Path | dict | Model`, so a programmatically built model goes
through validation, expansion, resolution and dim checking exactly as a file
does, and `Model.to_yaml` gives it the review copy rule 5 requires.

That is the whole of the blessed contract, and it is at the schema level rather
than the plan level. It is a narrow way to emit _declarations_, not a Python
modeling API — which rule 5 still refuses, and which is why this section still
forbids generated YAML text. Namespacing (#29) and a native schema merge (#30)
were closed against it: a library composing optional features varies its
declarations by data, and a dict is already how you say that.
