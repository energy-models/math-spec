<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# The limits of the language

A model can only say what the language has words for. This page says which
words may be added to it, and which may never be.

Read it before you ask for a new operator, a new block or a new keyword. It
gives you three things: the test a new operator has to pass, the reason a
solver's own limits are kept out of the language, and the requests that have
already been refused, each with what to write instead. For the rules a model
itself must obey, read
[the ten rules](../reference/language/index.md#ten-rules-the-language-reduces-to).

Every refusal here carries its evidence. Math that a real model needs and this
language cannot state is recorded against the model that needed it, with the
verdict beside it.

## How a new construct enters

Ask first which of four kinds the request is, because the kind decides what it
costs. Most requests turn out to be one of the two cheap kinds.

**A macro** is a template that takes arguments and is substituted into an
expression before anything reads it. It costs nothing to add, because it can
only compose operators that already exist. Nothing that reads a model has to
learn a macro. See [macros](../reference/language/expressions.md#macros).

**A named expression** is a quantity the file names once and can read back after
a solve. It is substituted wherever it is referenced, so it costs nothing at
build time, and it is turned into rows only when something reads it. See
[named expressions](../reference/language/expressions.md#named-expressions). A
macro is not the same thing: a macro takes arguments, it has no dimensions until
it is called, and no solve can report it.

**A primitive** is an operator built into the language, which no file can add
to. `sum`, `sum(by=)`, `shift` and the `where` predicates are the primitives,
and they set the limit of what the language can express. A new one is the
expensive kind. It has to be written twice, once in each backend. The backends
are the two implementations that build a model from the same syntax tree. Then
it has to be tested against both, and documented in the language reference.

**A formulation** is a block that expands into ordinary declarations before the
model is built. `piecewise:` is the only one. It costs as much as a primitive to
build, and it composes as freely as a macro, because what the rest of the model
sees is plain variables and constraints.

Math that none of the four can state goes in an `escape:` block: Python, named
in the file, that emits the rows the language cannot. It is
[#38](https://github.com/fluxopt/lpspec/issues/38), and it has not shipped.

A new primitive must be **macro-friendly**. Anything a modeller might want to
pass in sits in the _value_ of a keyword argument, such as `over=` or `by=`, and
never in its key. `shift(x, over=snapshot, offset=1)` names its dimension in a
value, so a macro can pass its own argument there. A dimension named in the key
could not be passed in at all.

A candidate primitive is admissible when it is both relational and local:

- **Relational** means one filter, one join, or one group-by aggregation over
  tables.
- **Local** means each output row reads either its own input row, which is
  **pointwise**, or a fixed number of neighbouring rows, which is
  **bounded-halo**. Those two can be built one chunk of rows at a time. An
  operator that reads the whole table at once cannot.

Locality is judged over the data, and not over the coordinates. A reduction over
coordinates, such as "the last snapshot", reads only the small table of
coordinate labels, which is in memory already. So it stays admissible even
though it looks as if it reads everything.

Degree is not a third rule. `variable × variable` is relational and local, since
a product of two variables at the same coordinate is a join of a table with
itself. So the objective takes degree 2. What decides where degree 2 may stand
is what a **sink** can take. A sink is whatever a built model is handed to,
such as a solver's API or a file format. That is the second question, answered
below, and the same holds for SOS, indicator and semi-continuous constructs.

Two things bound the quadratic case, and neither of them is how the model is
built:

- Where the construct stands. A quadratic _objective_ has more sinks to land in
  than a quadratic _constraint_ does. Which sink takes which is a measured fact,
  not an argument. One of the two backends cannot build a quadratic constraint
  at all, so what each backend can build is declared beside what the language
  accepts. Both backends still accept the same file, so the construct ships
  with the gap named instead of hidden.
- A product of two sums. `sum(x, over=i) * sum(y, over=j)` pairs every term of
  one sum against every term of the other, and nothing in the file says how many
  terms that is. This is the one row of the table below that stays rejected. A
  product of two _single_ terms is a join, whatever dimensions they carry, so
  `x[i] * y[j] * a[i, j]` is admissible: the table `a` says which pairs exist.

You do not have to judge relational and local by eye. Write the candidate as a
query over the stream of terms, and read the query back with `.explain()`. The
shape of the query gives the verdict:

| Shape of the query                                     | Locality     | Admissible?                |
| ------------------------------------------------------ | ------------ | -------------------------- |
| filters on a column the rows already carry             | pointwise    | admissible                 |
| joins against a parameter or a lookup table            | pointwise    | admissible                 |
| joins the coordinate table a fixed number of rows away | bounded-halo | admissible                 |
| reads the coordinate table only, and joins no data     | coordinates  | admissible, and free       |
| reads every row, or calls itself                       | whole table  | rejected, with the rewrite |

`_sum_fragment`, `_group_fragment` and `_translate_fragment` are the three
functions that already do this. Each rewrites one fragment of the query on its
own, which is what _pointwise_ and _bounded-halo_ mean in code. So a candidate
that fits none of the shapes above has no engine to be written into.

Two things this test does not answer. It assumes that the final
`sum(coeff)` over `(row, col)` stays the only aggregation a term passes through.
And it says nothing about degree, which is decided on the syntax tree by
`language/degree.py`, before any query exists.

A new primitive is finished when `lowering.py` accepts it, and when it gives the
same answer as linopy on a model built both ways.

Porting a real model also catches a bug that no other test reaches. Both
backends read the same resolved syntax tree, so a misreading they share passes
every test in the project, and only an optimum from outside the project shows
it.

A request the language refuses falls into one of three groups. The group decides
whether it can ever be allowed:

| Group                  | What bounds it                                                          | Members                                                                                                                                                                                         | Can it move?                                   |
| ---------------------- | ----------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| **Capability-bounded** | what one sink can take                                                  | indicator (#220); quadratic, whose verdict moves with its convexity and with what it stands beside. `sos:` entered here, native where a sink has the concept and reformulated where it does not | per sink — the capability table                |
| **Budget-bounded**     | the label budget, a cap on how many rows and columns an `escape:` emits | operators that read a whole table, arbitrary Python, work that is not relational                                                                                                                | already movable — that is what an `escape:` is |
| **Design-bounded**     | where this project has decided the work belongs                         | data preparation, domain helpers, Python that declares structure                                                                                                                                | movable any time; we do not want to            |

Three things can never appear inside one model: a conditional, a loop, and
structure that the data decides. What that protects is the **shape** of the
model, which is which declarations exist and which dimensions each one spans.
The shape is fixed before any data is read.

How many members a dimension has is always the data's to supply.
`foreach: [snapshot]` does not know how many snapshots there are either.

A dimension whose members are _computed_ during data preparation is completely
ordinary. A cycle basis for Kirchhoff's voltage law is one, and so are the
subsets of a subtour-elimination family. A graph algorithm that runs before the
build is design-bounded, which is the last row of the table above.

So the test is when the Python runs, and not what it does. It does not matter
how much work it is, and it does not matter whether the size of its output
depends on the data. The only question is whether it can run before the model is
built.

What no model can hold is work that needs the solver's _answer_ before it can
decide the next row. Cuts generated during a solve are the example, because
there is no "before" for them to happen in.

That work is still open to the engine around the model. One model cannot loop,
but a program may loop over models, and each model has its own shape fixed
before its own data. A rolling horizon has that shape and is in scope
([Track 2](https://github.com/fluxopt/lpspec/issues/471)). So are Benders
decomposition and successive substitution.

Adding rows to a model that is already built also keeps every label it has
handed out, where removing rows would not. A variable's label is its row number
among the rows that survive the `where` mask. So new rows move no column and
renumber no existing row.

What such a scheme still owes an answer on is who writes the cut. The model is
the file you review and diff, so a Python API for building models is refused.
That leaves two ways: ship a driver that reads the model's own tables, or allow
the narrow exception discussed under
[Composition](#composition-component-libraries). That is a question of scope,
and not a question about the limit.

An `escape:` block is exempt from the relational and local rules. A running sum
written as an escape still emits ordinary rows of coefficients, O(T²) of them.
It is never exempt from degree, because rows of coefficients are all it can
return. That refusal rests on what an escape emits, and not on what a sink
takes, so nothing in the next section changes it.

What keeps an escape accountable is its label budget. The budget is declared in
the file and enforced before any Python runs, rather than discovered after the
Python has allocated. Its extent is fixed by the `where` mask in front of it,
nothing reads its output further, and it is named in the file. A Python helper
registered from outside the file has none of those properties, which is why one
is refused where an escape is not.

### What a solver can take is a separate question

The test above asks how a model is built. It does not ask which solver gets the
result. That is a second question, and it is kept apart from the first. Answer
the two together, and one solver's limits end up written into the language,
where every other solver then inherits them.

Two facts keep the questions apart, and a capability table says which sink is
which:

- What a solver does with an SOS varies. One sink has no concept of a set at
  all, and others take one as it stands.
- A quadratic form is bounded twice over on a single sink: once by whether it is
  convex, and again by what stands beside it in the same model.

So one construct does not get one verdict. A sink that takes the whole Hessian
at once is a different implementation of the same language, and it states no new
rule.

`sos:` is that reasoning put to use. The construct entered on the first question
alone, because a set only names columns that a variable has already made. Each
sink then answers for itself, either `native` or `reformulated`. So a gap costs
you a weaker relaxation instead of a refusal. The third answer, `absent`, is
what is left for a construct that no rewrite reaches.

A set is a **declaration** rather than a constraint. That stays true however
many sinks grow native SOS support, because neither way of writing a set as
math is in this language:

- One way says `x_i * x_j == 0` wherever `|i - j| >= k`, which is SOS1 at `k=1`
  and SOS2 at `k=2`. It is degree 2.
- The other bounds how many members are non-zero, which is not affine at all.

So no `expression:` can say a set, whatever a sink can take. Saying it _about_ a
variable is the only spelling left.

A rewrite still does not make the two the same. A set reformulated into binaries
returns no duals, where the native form does. So the difference is declared, and
the caller chooses. A capability table, and a `check` that takes an optional
sink, carry the rest ([#925](https://github.com/fluxopt/lpspec/pull/925),
[#928](https://github.com/fluxopt/lpspec/pull/928)).

## What counts as data preparation

The table below refuses data preparation as a language feature. It does not say
which precomputed column counts as data preparation, and which one is work the
compiler could have done. From inside a model the two look the same: a parameter
arrives, and a constraint reads it. One sentence tells them apart:

> Data preparation computes what the model cannot know. The compiler builds what
> it can derive from data the model already has.

A cycle basis is the first kind. It is a graph algorithm over a topology that
only data supplies. So `pypsa_kvl` carrying `cycle_incidence` as a parameter is
right, and it would be right in any language.

A minimum up time is the second kind. `min_up_time` is a column that the model
already binds, and the window mask over it is a mechanical consequence of that
column. So `within=` reads the width off the column, and the modeller writes no
mask out as data. Minimum up and down times is the witness for this, and
[#849](https://github.com/fluxopt/lpspec/issues/849) is what remains of the
gap.

The first kind is a design decision. The second is work the compiler can do, so
it does. Refusing both under a single rule reads as principle while it charges
the modeller for nothing.

The trade-off is deliberate, and Calliope made it differently. Calliope's
components take a list of `where`-guarded equations. So alternatives that differ
by a regime live in the file, instead of being flattened into data. Calliope has
one block for cyclic and non-cyclic storage, where this language wants the
constraint written twice ([#711](https://github.com/fluxopt/lpspec/issues/711)).

What the difference buys is that the shape of the model stays fixed before any
data is read. That is what makes a streaming engine and a second independent
backend possible at all. So the limit stays. What is worth taking from Calliope
is its checks, and not its machinery: check that the alternatives cover every
row exactly once, and stop making the modeller supply a column the compiler
could derive. Neither of those adds a construct.

## Deliberate non-primitives

The admissibility test above says what _may_ enter. This section records what
has been asked for and refused, with the reason and the rewrite. A request that
has already been answered is answered once here, rather than argued again from
the start.

Parity with another tool is not by itself a reason to add anything.

| Request                                                                  | Why                                                                                                                                                                                                                                                                                                                                                                      | Instead                                                                                                                                                                                                                |
| ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Data preparation: resampling, clustering, file IO, unit conversion       | not math                                                                                                                                                                                                                                                                                                                                                                 | preprocess; pass a parameter                                                                                                                                                                                           |
| Unit _checking_ at load, with conversion staying refused                 | a `unit:` says something about the data that nothing checks against the data. So a clean pass means only that no two annotated operands disagreed, and never that the columns are in the units they claim. It would also open a unit grammar, and a vocabulary of base units, that the language then has to close ([#125](https://github.com/fluxopt/lpspec/issues/125)) | preprocess to one unit system, and name it in the declaration's `description:`                                                                                                                                         |
| Arbitrary array operations (`merge`, `reindex`)                          | there is no end to them, and it would be xarray with extra steps                                                                                                                                                                                                                                                                                                         | data prep                                                                                                                                                                                                              |
| Domain helpers (`reduce_carrier_dim`)                                    | writes one domain's vocabulary into the language                                                                                                                                                                                                                                                                                                                         | component libraries over generic primitives                                                                                                                                                                            |
| A tracked-metric vocabulary: `impacts:`, `effects:`, a `costs` dimension | a named expression already covers it, whether the math reads it or a solve reports it                                                                                                                                                                                                                                                                                    | an `impact` dim and one named expression: cap it with a constraint whose dual is the shadow price, weight it in the objective, read it with `result.expression` ([#124](https://github.com/fluxopt/lpspec/issues/124)) |
| `**` with a _variable_ base or exponent                                  | the exponent would decide the degree, and no data is read at load. `p ** n` is affine at 1, quadratic at 2 and over the limit at 3, so the file would say which only once the numbers arrived                                                                                                                                                                            | `x * x` for a square; above degree 2 there is no rewrite. Over variable-free operands `**` is in the language ([#1175](https://github.com/fluxopt/lpspec/issues/1175))                                                 |
| Normalisation (`x / sum(x)`)                                             | dividing by a variable is not polynomial at any degree, and no sink takes it                                                                                                                                                                                                                                                                                             | state the ratio as a constraint, or fix the denominator                                                                                                                                                                |
| Conditionals, iteration, structure the data decides, inside one model    | the syntax tree could no longer be read without the data                                                                                                                                                                                                                                                                                                                 | `where` masks and `foreach` dimensions. A program may loop over models                                                                                                                                                 |
| A Python API for constructing models                                     | the model is the file you review and diff                                                                                                                                                                                                                                                                                                                                | YAML. Whether Python may _emit_ declarations is [#381](https://github.com/fluxopt/lpspec/issues/381)                                                                                                                   |

Math that this language cannot express goes into an `escape:` block
([#38](https://github.com/fluxopt/lpspec/issues/38)). The block is named in the
file, it is bounded by the `where` in front of it, nothing reads its output
further, and its label budget is checked before any Python runs. It is exempt
from the relational and local rules, and never from degree, because rows of
coefficients are all it returns.

## Composition (component libraries)

A component library is a fixed set of templates that take parameters, such as a
boiler, a battery and a line. The templates agree on one way of naming ports and
flows. Merging them gives one model, wired together by a connectivity table in
the data, and closed by one `sum(by=)` balance.

Topology is data, and not structure. Wiring up one system means rows in a
connectivity table, and never YAML written by a program. So the file grows with
the number of component _types_, and never with the number of components.

Merging therefore happens before building. It produces one `Spec`, which is then
built once. A `merge` built into the package is #30.

Two things are still missing. Qualified names, so that two templates may each
declare a `p`, are #29. Port and flow names stay shared on purpose, because that
is how two templates connect. Signs and bidirectional flows need arithmetic in
`bounds:`, which is #31.

Whatever genuinely is not data belongs in a thin layer above the language. A
component whose number of ports is only known at runtime is the example. That
layer emits more rows, or more templates, and never one block of YAML per
component.

That layer has a supported way in. Every function takes
`str | Path | dict | Spec`. So a model built in Python is validated, expanded,
resolved and dimension-checked exactly as a file is, and `Spec.to_yaml` prints
the copy a reviewer reads.

That is as far as it goes. A dict declares what a file declares, and nothing
more. It is not a Python API for building models, which stays refused, and that
is why this section still forbids YAML written by a program.

Namespacing (#29) and a native schema merge (#30) were closed against this
contract. A library that composes optional features varies its declarations by
data, and a dict is already how you say that.
