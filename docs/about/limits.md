<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# The limits of the language

This page says what is allowed to enter the language, and what is never
allowed. The rules that a model itself must obey are
[the ten rules](../reference/language/index.md#ten-rules-the-language-reduces-to).
This page holds the argument in between. It gives the test that a candidate
primitive must pass. It explains why capability is a second, separate axis
rather than part of the limit. It records
[what has been refused and why](#deliberate-non-primitives). And it says what
composition would force on us.

This page makes a claim, so it carries evidence. When a ported model needs math
that this language cannot state, that becomes a row in a ledger against the port
that needed it, with the triage verdict beside it.

## How a new construct enters

A new construct arrives as one of four kinds, and the kind decides what it
costs.

**Primitives** are the operators, `sum`, `sum(by=)`, `shift` and the `where`
predicates. They set the limit of what the language can express. Each new
primitive must be built in both backends: an eager implementation, a plan node
and a locality class, an engine case, a lowering case, differential tests, and
an entry in the language reference.

**`macros:`** are pure substitution in the syntax tree. They give you every
composition of the primitives at no extra cost and with no risk that the two
backends diverge.

**`expressions:`** substitute in the same way wherever they are referenced, and
they also cost nothing at build time. But they sit in a tier of their own, apart
from macros. See
[named expressions](../reference/language/expressions.md#named-expressions). A
named expression has fixed dimensions and an identity you can observe. You can
read it after a solve with `result.expression(name)`. It is lowered on demand at
the moment you read it, through the same compiler that the constraints use, and
that shared compiler is what keeps the divergence risk at zero. A macro is
different: it takes parameters, it has no dimensions until you call it, and you
can never read it back.

**Formulations**, which today means `piecewise:`, cost as much as a primitive
but compose like a macro. They emit _new declarations_ before dispatch, and they
never enter the plan as expression nodes.

For any request, start with triage: **is this a macro, a primitive, or an
escape?** Most requests turn out to be compositions.

A new primitive must be **macro-friendly**. Anything a user might want to
parameterise has to sit in a _value_ position, such as `over=` or `by=`, and
never as the key of a keyword argument. For example, `shift(x, over=snapshot,
offset=1)` takes its dimension as a keyword argument _value_, so a macro can
pass a formal parameter there. The earlier design, which put the dimension in
the key, could not do this, and it is gone.

A candidate primitive is admissible when it is both relational and
local.

- **Relational** means it is a filter, a join, or a group-by aggregation over
  tidy tables.
- **Local** means it is either _pointwise_ or _bounded-halo_. These two shapes
  compose under partition-wise execution. _Global_ operators do not.

Judge locality in **data space**. A reduction over a _coordinate_ space, such as
"the last snapshot", only reads the small dimension tables that are already
materialised. So it stays admissible even though it looks global.

Degree is not a third rule. This page stated it as one for a while, and that
was a mistake. There is nothing non-relational or non-local about
`variable × variable`. A coordinate-aligned product is a pointwise self-join.
That prediction has since been cashed in: **the objective takes degree 2.** What
decided where degree 2 could land was not the closure at all. It was **what a
sink can ingest**, which is the second axis described below. The same holds for
SOS, indicator and semi-continuous constructs. Read this page as the
_streamability_ closure, and nothing more than that.

Two things bound the quadratic case, and neither of them is streamability:

- **Position, and it has since moved.** A quadratic _objective_ had somewhere to
  land before a quadratic _constraint_ did, and fewer things refuse it. Which
  sink takes which is a measured fact, not an argument. What kept the quadratic
  constraint out is that one _lane_ cannot build one at all. That changed when
  the capability axis grew to cover **lanes** as well as sinks (hard rule 3).
  Both lanes still accept the same language. What each lane can _build_ is
  declared. So the construct ships with the gap named instead of hidden. The
  price is a differential oracle for that one construct, which is why the gap is
  only one entry long.
- **One shape is genuinely out.** `sum(x, over=i) * sum(y, over=j)` pairs every
  term of one sum against every term of the other. That cross join is what the
  old blanket ban was really describing, and it is the one row of the table
  below that stays rejected. A product whose factors are each a _single_ term is
  a join, whatever dimensions they carry. So `x[i] * y[j] * a[i, j]` is the
  honest general bilinear form, and it is admissible, because it is coupled
  through a declared table.

Read the verdict off the plan. Relational and local are one question asked
twice, and the compiler already answers it. Write the candidate's query over the
term stream first, then read `.explain()`:

| Shape of the emitted query                     | Locality         | Admissible?                  |
| ---------------------------------------------- | ---------------- | ---------------------------- |
| filter on a column already in the frame        | pointwise        | admissible                   |
| equi-join against a parameter or mapping table | pointwise        | admissible                   |
| join on the dim table at `ord ± k`, `k` fixed  | bounded-halo     | admissible                   |
| dim table only, no data join                   | coordinate-space | admissible (free)            |
| window over unbounded rows, or a recursive CTE | global           | **reject**, with the rewrite |

This is the same case analysis that `_sum_fragment`, `_group_fragment` and
`_translate_fragment` already implement. Each of them rewrites one fragment on
its own, and that is what _pointwise_ and _bounded-halo_ mean in code. So a
candidate that fits none of these shapes has no engine to be written into.

There is one limit on reading the verdict this way. It assumes that the terminal
`sum(coeff)` over `(row, col)` stays the only aggregate that a _term_ passes
through. Also, degree is decided somewhere else, and deliberately so. It is
decided on the core syntax tree by `language/degree.py`, which both lanes ask
and neither lane states. So reading degree off a query would mean reading the
wrong artefact.

A primitive is finished when `lowering.py` accepts it and the differential test
against the linopy oracle passes.

The limit is a claim, so it needs evidence. In the ports ledger, math that
a ported model needed and this language could not state becomes a ledger row
with its triage verdict beside it. That ledger is what the roadmap should be
argued from.

Those ports also cover a class of bug that no other test reaches. By rule 1,
both lanes consume the same resolved syntax tree. So a _shared misreading_
passes the differential suite green, and only an optimum from outside the
project catches it.

What sits _outside_ the closure splits three ways, and the split decides whether
a request can ever be met:

| Tier                   | Bounded by                                                                   | Members                                                                                                                                                                                                                                 | Can it move?                                |
| ---------------------- | ---------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| **Capability-bounded** | what a given sink can ingest                                                 | indicator (#220); quadratic, whose verdict moves with its convexity and with what it stands beside. `sos:` **shipped** on this tier, and is what the row predicted: native where a sink has the concept, reformulated where it does not | per sink — the capability table             |
| **Budget-bounded**     | the escape _label_ budget — a cap on the rows and columns an island may emit | global operators, arbitrary Python, non-relational manipulation                                                                                                                                                                         | already movable — that is what an island is |
| **Design-bounded**     | our choice of where work belongs                                             | data prep, domain helpers, Python declaring structure                                                                                                                                                                                   | movable any time; we don't want to          |

Some things are impossible **in the symbolic plan**: conditionals, iteration,
and any data-dependent structure inside an expression. What this protects is
that the **shape** of the plan is fixed before any data is read. Shape means
which declarations exist and which dimensions each one spans.

_Cardinality_ is always data's job to supply. `foreach: [snapshot]` does not know
how many snapshots there are either.

That distinction decides more than it looks like it does. A dimension whose
members are _computed_ during data preparation is completely ordinary. A cycle
basis for KVL, or the subsets of a subtour-elimination family, are both fine,
because a graph algorithm that runs before the build is design-bounded, which is
the last row of the table above.

The line here is **temporal, not computational**. It does not matter how clever
the Python is, and it does not matter whether the size of its output depends on
the data. The only question is whether it can run before the model is built.

What is outside **the plan** is work that needs the solver's _answer_ before it
can decide the next row. Lazy cut generation is the example, because there is no
"before" for it to happen in.

Outside the plan is not outside the engine. A plan cannot contain a loop. But a _process_ may loop over
plans, and each plan has its own shape fixed before its own data. A rolling
horizon has exactly that shape and is in scope
([Track 2](https://github.com/fluxopt/lpspec/issues/471)). So are Benders
decomposition and successive substitution.

Appending a cut also does not cost us the label contract, although removing one
would. `var_label` is a `ROW_NUMBER()` over the rows that survive the `where`
mask. So adding _rows_ moves no column and renumbers no existing row, and
`addRows` is already how the direct sink feeds the initial build.

What such a scheme still owes an answer on is **who writes the cut**. Rule 5
refuses a Python modeling API. So either a decomposition driver ships that reads
the model frames, or we allow the narrow exception for emitting affine rows that is
discussed under [Composition](#composition-component-libraries). That is a
question of scope, not a question about the limit.

Streamability is a different property from how much a build costs, though the
two meet at the escape hatch. That is why an `escape:` island (#38) is
admissible where a registered Python helper was not. Its extent is fixed by the
`where` mask in front of it, it is terminal, and it is named in the file. Its
label budget is what keeps it accountable. The cost of an island is bounded
by what it is allowed to emit, and that bound is declared and enforced before
any Python runs, rather than discovered after the Python has allocated.

An escape buys back the _relational_ and _local_ rules. A running-sum island
still emits affine rows, just O(T²) of them. But an escape never buys back
**degree**, because affine COO is what it returns. That refusal rests on what an
island _emits_, not on what a sink accepts, so the capability findings below do
not affect it.

### Capability is not the limit

The limit described above is about **streamability**, and it does not depend on
the solver. What a _sink_ can ingest is a separate axis. Mixing the two axes
together let one solver's limits read as architectural law. The claim that "no
sink carries the stream" described a solver, not the architecture.

Two findings say why capability has to be its own axis, and the capability table
says which sink is which:

- SOS is **solver-bounded**. One sink has no concept of a set at all, while
  others take one natively.
- Quadratic is bounded **twice over on a single sink**: once by convexity, and
  again by what it stands beside.

So a capability is neither a flat set nor a single verdict per construct. The
whole-Hessian handoff is a difference in implementation, not a violation of rule 4.

`sos:` is that finding put to use, and it shows what the axis is worth. The
construct entered on the streamability argument alone, because a set names
columns that a variable has already made, so it is neither an expression node
nor a formulation. Each sink then answers for itself, either `native` or
`reformulated`. A capability gap therefore costs you a worse relaxation instead
of a refusal. The third value, `absent`, is what is left for the constructs that
no rewrite reaches.

A set is a **declaration** rather than a constraint, for a reason that will
survive every sink growing native SOS support: neither algebraic statement of a
set is in this language.

- The complementarity form is `x_i * x_j == 0` wherever `|i - j| >= k`. This is
  SOS1 at `k=1` and SOS2 at `k=2`. It is degree 2.
- The cardinality form bounds the support, which is not affine at all.

So a set cannot be said as math here, whatever a sink can ingest. Saying it
_about_ a variable is the only spelling left.

What a rewrite cannot buy back is the argument _for_ declaring capability. A set
that is reformulated into binaries returns no duals, where the native form does.
That asymmetry should be visible, and the caller should choose between the two,
rather than have the difference papered over. The rest of the machinery, which
is a capability _table_ and a `check` that takes an optional sink, has since
shipped ([#925](https://github.com/fluxopt/lpspec/pull/925),
[#928](https://github.com/fluxopt/lpspec/pull/928)).

## Where the data-prep line falls

The table below refuses data preparation as a language feature. What it does not
say is _which_ precomputation is data preparation, and which is work that the
compiler is simply declining to do. From inside a model the two look identical:
a parameter arrives, and a constraint reads it.

> **Data preparation computes what the model cannot know. The compiler builds
> what it can derive from data the model already has.**

A cycle basis is the first kind. It is a graph algorithm over a topology that
only data supplies. So `pypsa_kvl` carrying `cycle_incidence` as a parameter is
right, and it would be right in any language.

A minimum up time was the second kind. `min_up_time` is a column that the model
already binds, and the window mask over it is a mechanical consequence that the
modeller had to write out as data. That changed when `within=` learned to read
the width off the column. Minimum up and down times is the witness for this.
[#849](https://github.com/fluxopt/lpspec/issues/849) is what remains of that
gap.

The first kind is a design decision. The second kind was a cost we no longer
have to pay. Refusing both under a single rule reads as principle while it
charges the modeller for nothing.

The trade-off is deliberate, and Calliope made it differently. Calliope's
components take a list of `where`-guarded equations. So alternatives that differ
by a regime live in the file, instead of being flattened into data. Calliope has
one block for cyclic and non-cyclic storage, where this language wants the
constraint written twice ([#711](https://github.com/fluxopt/lpspec/issues/711)).

What we buy with the difference is that the _shape_ of the plan stays fixed
before any data is read. That is what makes a streaming engine and a second
independent lane possible at all. So the limit stays. What is worth importing
from Calliope is the **checks and the rules, not the machinery**: validate that
alternatives cover their rows exactly once, and stop making the modeller write
out an argument the compiler could derive. Neither of those widens the closure.

## Deliberate non-primitives

The admissibility test above says what _may_ enter. This section records what
has been asked for and refused, with the reason and the rewrite. The point is
that a request which has already been answered gets answered once, rather than
argued again from the start.

Parity with another tool is not by itself a reason to add anything.

| Request                                                                   | Why                                                                                                                                                                                                                                                                                                                                                                                                              | Instead                                                                                                                                                                                                                |
| ------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Data prep — resampling, clustering, IO, unit conversion                   | not math                                                                                                                                                                                                                                                                                                                                                                                                         | preprocess; pass a parameter                                                                                                                                                                                           |
| Unit _checking_ at load, with conversion staying refused                  | a `unit:` is a claim about data that nothing checks against the data, so a clean pass says "no two annotated operands disagreed" and never "the columns are in these units" — and an unannotated declaration propagating permissively makes even that advice. It would also open a unit grammar and a base-unit vocabulary the language then has to close ([#125](https://github.com/fluxopt/lpspec/issues/125)) | preprocess to one unit system, and name it in the declaration's `description:`                                                                                                                                         |
| Arbitrary array ops (`merge`, `reindex`)                                  | unbounded; xarray with extra steps                                                                                                                                                                                                                                                                                                                                                                               | data prep                                                                                                                                                                                                              |
| Domain helpers (`reduce_carrier_dim`)                                     | encodes one domain into the language                                                                                                                                                                                                                                                                                                                                                                             | component libraries over generic primitives                                                                                                                                                                            |
| A tracked-metric vocabulary — `impacts:`, `effects:`, a `costs` dimension | the three fates are already reference-it-or-don't                                                                                                                                                                                                                                                                                                                                                                | an `impact` dim and one named expression: cap it with a constraint whose dual is the shadow price, weight it in the objective, read it with `result.expression` ([#124](https://github.com/fluxopt/lpspec/issues/124)) |
| `**` with a **variable** base or exponent                                 | the exponent would decide the degree, and no data is read at load — `p ** n` is affine at 1, quadratic at 2 and over the limit at 3, and the file says which only once the numbers arrive                                                                                                                                                                                                                        | `x * x` for a square; above degree 2 there is no rewrite. Over variable-free operands `**` **is** in the language ([#1175](https://github.com/fluxopt/lpspec/issues/1175))                                             |
| Normalisation (`x / sum(x)`)                                              | a _variable divisor_ is rational, not polynomial — no sink takes it at any degree                                                                                                                                                                                                                                                                                                                                | state the ratio as a constraint, or fix the denominator                                                                                                                                                                |
| Conditionals, iteration, data-dependent structure **inside one plan**     | destroys the closed AST                                                                                                                                                                                                                                                                                                                                                                                          | `where` masks + `foreach` dims. A _process_ may loop over plans                                                                                                                                                        |
| A Python API for constructing models                                      | hard rule 5 — the model is the file you review and diff                                                                                                                                                                                                                                                                                                                                                          | YAML. Whether Python may _emit_ declarations is [#381](https://github.com/fluxopt/lpspec/issues/381)                                                                                                                   |

Math that this language cannot express goes into a declared `escape:` island
([#38](https://github.com/fluxopt/lpspec/issues/38)). An island is named in the
file, it is bounded by the `where` in front of it, it is terminal, and it is
billed against a label budget before any Python runs. It buys back _relational_
and _local_. It cannot buy back degree, because it returns affine COO rows
either way.

## Composition (component libraries)

A component library is a fixed set of templates that take parameters. The
templates agree on one convention for ports and flows. They are merged into a
single program, wired together through a connectivity table in the data, and
closed with a single `sum(by=)` balance.

Topology is data, not structure. Wiring up a specific system means rows in a
connectivity table, and never generated YAML. So the amount of structure is
bounded by the number of component _types_, while cardinality lives entirely in
the data.

Schema merge is therefore a pure **compose-then-build** step. It produces one
`Spec` before a single lower-and-stream pass. Native merge is #30.

Two things are still missing. Namespacing through qualified names is the missing
primitive (#29). The port and flow surface stays shared on purpose, because it
is the coupling contract between templates. Signs and bidirectional flows need
bounds-as-expressions (#31).

Whatever genuinely is not data belongs in a thin layer above the language.
Variable port counts and component types that are unknown until runtime are the
examples. That layer must emit **more rows or more templates, and never
per-instance YAML.**

That layer has a supported thing to call. Every function takes
`str | Path | dict | Spec`. So a model built programmatically goes through
validation, expansion, resolution and dimension checking in exactly the same way
a file does, and `Spec.to_yaml` gives it the review copy that rule 5 requires.

The contract stops there. It sits at the schema level rather than at the plan
level, and it is a narrow way to emit _declarations_. It is not a Python
modeling API, which rule 5 still refuses, and that refusal is why this section
still forbids generated YAML text.

Namespacing (#29) and a native schema merge (#30) were closed against this
contract. A library that composes optional features varies its declarations by
data, and a dict is already how you say that.
