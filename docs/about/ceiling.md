<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# The ceiling

What may enter the language, and what may never. Read this page when you want
math the language does not say today, or when you want to know why a construct
was refused. The rules a model file must obey are
[the ten rules](../reference/language/index.md#ten-rules-the-language-reduces-to);
this page is the argument behind them.

The ceiling is one property: a construct must be **streamable**. Everything
else that can stop a model is a separate axis: which solver takes it, how much
a build costs, and where we decided the work belongs. This page keeps the axes
apart.

## Three ways to add math

Every request is triaged into one of three answers before anything is
designed. Most requests are the first.

| Tier                                                               | What it is                                           | What it costs                                                                                    |
| ------------------------------------------------------------------ | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| **A composition** (`macros:`, `expressions:`)                      | existing operators, spelled once and reused          | nothing at build time                                                                            |
| **A primitive** (an operator, `sum`, `shift`, …)                   | a new leaf the compiler has to understand            | an implementation in every consumer, a locality verdict, tests against a reference, a docs entry |
| **An escape** ([#38](https://github.com/fluxopt/lpspec/issues/38)) | math the language does not say, fenced off and named | a declared budget on what it may emit                                                            |

**A macro is pure substitution.** It takes formals, has no dimensions until it
is called, and disappears into the tree at load. It can compose any primitives
at no risk of two consumers disagreeing, because after expansion there is
nothing new for them to read.

**A named expression is a macro's opposite in one respect: it has an
identity.** It takes no arguments and has fixed dims, the axes it spans. It is readable
after a solve, through the same compiler that builds the constraints.
See [named expressions](../reference/language/expressions.md#named-expressions).

**A formulation (`piecewise:`) is taxed like a primitive and composes like a
macro.** It emits new declarations before the model is built, so it never
becomes a node in the expression tree.

**A new primitive must be macro-friendly.** Anything a caller might want to
parameterise goes in a value position, never a keyword name. `shift(x,
over=snapshot, offset=1)` takes its dimension as a value, so a macro can pass
a formal there. A design that took the dimension as the keyword itself could
not.

## The test a primitive must pass

A candidate primitive is admissible if it is **relational** and **local**.

- **Relational** means it is filter, join, or group-by-aggregate over tidy
  tables — one row per coordinate, one column per field.
- **Local** means each output row depends on its own input row (_pointwise_)
  or on a fixed number of neighbours (_bounded halo_). Both survive being run
  one partition at a time. A _global_ operator does not.

**Locality is judged in data space, not in how the operator reads.** A
reduction over a coordinate space, such as "the last snapshot", touches only
the small dimension table already in memory. It stays admissible even
though it sounds global.

**Write the query before arguing about the operator.** Relational and local
are the same question asked twice, and the query plan answers both.

| Shape of the emitted query                          | Locality         | Verdict                      |
| --------------------------------------------------- | ---------------- | ---------------------------- |
| filter on a column already in the frame             | pointwise        | admissible                   |
| equi-join against a parameter or mapping table      | pointwise        | admissible                   |
| join on the dimension table at `ord ± k`, `k` fixed | bounded halo     | admissible                   |
| dimension table only, no data join                  | coordinate space | admissible, and free         |
| window over unbounded rows, or a recursive CTE      | global           | **rejected**, with a rewrite |

A candidate that fits none of these shapes has no engine to be written into.
The test presumes one thing: the final sum of coefficients per row and column
stays the only aggregate a term passes through.

**A primitive is finished when the whole chain takes it**, and that is the
verdict, not the admissibility argument: the schema accepts the spelling, the
dimension and degree checks answer for it, `lowering.py` lowers it, the
typesetter prints it in all three formats, and a differential test shows two
consumers building the same rows from it. Anything short of that is a
construct the language admits and something downstream cannot read.

## Degree is not part of the test

**Nothing about `variable × variable` is non-relational or non-local.** A
product of two variables aligned on the same coordinates is a pointwise
self-join. Degree is decided separately from streamability, before any query
plan exists, and the language admits degree 2 in the objective and in
constraints
([rule 9](../reference/language/index.md#ten-rules-the-language-reduces-to)).

**One product shape is genuinely out.** `sum(x, over=i) * sum(y, over=j)`
pairs every term of one sum with every term of the other. That is a cross
join, and it is rejected. A product whose factors are each a single term is a join, whatever dimensions
they carry. `x[i] * y[j] * a[i, j]` is the general bilinear form, coupled
through a table the file declares, and it is admissible.

## Solver capability

**What a solver can accept is a second axis, and it is not the ceiling.** The
ceiling is solver-independent. Treating one solver's limits as an
architectural rule would make every consumer inherit the narrowest one's
refusals.

Two constructs show why the axis has to be its own:

- **SOS sets are solver-bounded.** One solver has no concept of a set at all,
  where others take one natively.
- **Quadratic terms are bounded twice over on a single solver**, by convexity
  and again by what else the model states. So a capability is neither a flat
  set nor one verdict per construct.

**`sos:` shows what the split buys.** The construct entered on the
streamability argument alone: a set names columns a variable already made, so
it is neither an expression node nor a formulation. Each consumer then answers
for itself, `native` or `reformulated`, and a gap costs a worse relaxation
rather than a refusal. The third answer, `absent`, is left for constructs no
rewrite reaches. One thing no rewrite buys back is the reason capability is
declared at all. A set reformulated into binaries returns no duals where the
native form does. That difference is the caller's to weigh, so the capability
table and a `check` that takes a consumer are what carry it
([#925](https://github.com/fluxopt/lpspec/pull/925),
[#928](https://github.com/fluxopt/lpspec/pull/928)).

**A set is a declaration rather than a constraint**, and this holds however
many solvers gain native support. Neither algebraic form is sayable here. The
complementarity form, `x_i * x_j == 0` wherever `|i - j| >= k`, is degree 2.
The cardinality form bounds the support, which is not affine at all. Saying it
_about_ a variable is the only spelling left. See
[piecewise curves and SOS](../reference/language/piecewise.md).

## Outside the ceiling

What sits outside splits three ways, and the split decides whether a request
can ever be met.

| Tier                   | Bounded by                                          | Members                                                                                                                                                            | Can it move?                              |
| ---------------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------- |
| **Capability-bounded** | what a solver can ingest                            | indicator constraints ([#220](https://github.com/fluxopt/lpspec/issues/220)); quadratic terms, whose verdict moves with convexity and with what stands beside them | per solver, through the capability table  |
| **Budget-bounded**     | the label budget, a cap on rows and columns emitted | global operators, arbitrary Python, non-relational manipulation                                                                                                    | already movable, through an escape island |
| **Design-bounded**     | our choice of where work belongs                    | data preparation, domain helpers, Python that declares structure                                                                                                   | movable any time, and we do not want to   |

## What a plan cannot contain

**Conditionals, iteration and data-dependent structure are impossible inside
one plan.** What this protects is the plan's _shape_: which declarations exist,
and which dimensions each one spans, fixed before any data is read.

**Cardinality is always data's to supply.** `foreach: [snapshot]` does not know
how many snapshots there are either, and that is not a limit.

**The line is temporal, not computational.** A dimension whose members are
_computed_ in data preparation is ordinary. A cycle basis for Kirchhoff's
voltage law, or the subsets of a subtour-elimination family, come from graph
algorithms that run before the build. It does not matter how clever that
Python is, or whether its output size depends on the data. It matters only
that it can run before the model is built. Outside the plan is work that needs the solver's _answer_ to decide the next
row, such as lazy cut generation. There is no "before" for it to happen in.

**Outside the plan is not outside the engine.** A plan cannot contain a loop.
A _process_ may loop over plans, each with its own shape fixed before its own
data. A rolling horizon is that shape and is in scope
([#471](https://github.com/fluxopt/lpspec/issues/471)), and so are Benders
decomposition and successive substitution. Appending a cut also costs nothing in labels. A variable's label is a row
number over the rows that survive the `where` mask, so adding rows moves no
column and renumbers no existing row. What such a
scheme still owes an answer on is who writes the cut, because
[rule 5](../reference/language/index.md#ten-rules-the-language-reduces-to)
refuses a Python modelling API. That is a scope question, not a ceiling one.

## Escape islands

`escape:` is the fence for math that is genuinely unsayable
([#38](https://github.com/fluxopt/lpspec/issues/38)). An island is named in
the file, its extent is fixed by the preceding `where` mask, and it is
terminal. Its **budget is what keeps it accountable**: a cap on the rows and
columns it may emit, declared and enforced before any Python runs rather than
discovered after it allocates. That is why an island is admissible where a
registered Python helper is not.

**An island buys back relational and local, never degree.** It returns affine
coefficient rows, so a running-sum island is admissible and merely emits O(T²)
of them. The refusal of degree stands on what an island _emits_, so no solver
capability changes it.

## Where data preparation ends

Refusing data preparation as a language feature does not say _which_
precomputation is data preparation. From inside a model, data preparation and
work the compiler declines to do look the same: a parameter arrives, a
constraint reads it. The line:

> **Data preparation computes what the model cannot know. The compiler builds
> what it can derive from data the model already has.**

**A cycle basis is the first kind.** It is a graph algorithm over a topology
only data supplies. Carrying `cycle_incidence` as a parameter is right here,
and would be right in any language.

**A minimum up time was the second kind.** The model already binds
`min_up_time` as a column. The window mask over it is a mechanical
consequence, and the modeller had to ship it as data. `within=` now reads the
width off the column. [#849](https://github.com/fluxopt/lpspec/issues/849) is what
is left of that gap.

The first kind is a design; the second was a tax. Refusing both under one rule
reads as principle while billing as friction.

**Calliope makes the trade differently, and the difference is deliberate.**
Its components take a list of `where`-guarded equations. Alternatives that
differ by a regime then live in the file: one block covers cyclic and
non-cyclic storage, where this language wants the constraint written twice
([#711](https://github.com/fluxopt/lpspec/issues/711)). Holding the plan's
shape fixed before any data is read is what makes a streaming engine and a
second independent consumer possible. What is worth importing from that design
is the checks, not the machinery. Validate that alternatives cover their rows
exactly once, and stop making a compiler-derivable argument a literal. Neither
widens the ceiling.

## Deliberate non-primitives

What has been asked for and refused, with the reason and the rewrite. A
request answered here is answered once. Parity with another tool is not by
itself a reason to add anything.

| Request                                                                   | Why                                                                                                                                                                                         | Instead                                                                                                                                                                                                                |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Data preparation — resampling, clustering, IO, units                      | not math                                                                                                                                                                                    | preprocess, and pass a parameter                                                                                                                                                                                       |
| Arbitrary array operations (`merge`, `reindex`)                           | unbounded, and xarray with extra steps                                                                                                                                                      | data preparation                                                                                                                                                                                                       |
| Domain helpers (`reduce_carrier_dim`)                                     | encodes one domain into the language                                                                                                                                                        | component libraries over generic primitives                                                                                                                                                                            |
| A tracked-metric vocabulary — `impacts:`, `effects:`, a `costs` dimension | the three fates are already reference-it-or-don't                                                                                                                                           | an `impact` dimension and one named expression: cap it with a constraint whose dual is the shadow price, weight it in the objective, read it back after a solve ([#124](https://github.com/fluxopt/lpspec/issues/124)) |
| `**` with a **variable** base or exponent                                 | the exponent would decide the degree, and no data is read at load — `p ** n` is affine at 1, quadratic at 2 and over the ceiling at 3, and the file says which only once the numbers arrive | `x * x` for a square; above degree 2 there is no rewrite. Over variable-free operands `**` **is** in the language ([#1175](https://github.com/fluxopt/lpspec/issues/1175))                                             |
| Normalisation (`x / sum(x)`)                                              | a _variable divisor_ is rational, not polynomial, and no solver takes it at any degree                                                                                                      | state the ratio as a constraint, or fix the denominator                                                                                                                                                                |
| Conditionals, iteration, data-dependent structure **inside one plan**     | destroys the closed expression tree                                                                                                                                                         | `where` masks and `foreach` dimensions. A _process_ may loop over plans                                                                                                                                                |
| A Python API for constructing models                                      | rule 5 — the model is the file you review and diff                                                                                                                                          | YAML. Whether Python may _emit_ declarations is [#381](https://github.com/fluxopt/lpspec/issues/381)                                                                                                                   |

## Component libraries

A component library is a fixed set of parametrised templates that agree on a
port and flow convention. They merge into one program, wired through a
connectivity table and a single `sum(by=)` balance.

**Topology is data, not structure.** Wiring a specific system is rows in a
connectivity table, never generated YAML. So structure is bounded by the
number of component _types_, while cardinality lives entirely in data. Merging
schemas is therefore a compose-then-build step that produces one `Spec` before
a single build pass ([#30](https://github.com/fluxopt/lpspec/issues/30)).
Qualified names are the missing primitive
([#29](https://github.com/fluxopt/lpspec/issues/29)); the port and flow
surface stays shared on purpose, as the coupling contract between templates.
Signs and bidirectional flows need bounds that may be expressions
([#31](https://github.com/fluxopt/lpspec/issues/31)).

**Whatever is genuinely not data belongs in a thin layer that emits more rows
or more templates**, never per-instance YAML. Variable port counts and
component types unknown until run time are the cases. That layer has a
supported thing to call. Every verb takes `str | Path | dict | Spec`, so a
model built in Python goes through validation, expansion, resolution and
dimension checking exactly as a file does. `Spec.to_yaml` then gives it the
review copy rule 5 requires.

That is the whole of the contract, and it sits at the schema level rather than
the plan level. It is a narrow way to emit _declarations_, not a Python
modelling API.
