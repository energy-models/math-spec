<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Reading a loaded model

This page is for whoever writes an engine that builds models, a renderer, or a
checker. You need none of it to write a model. A tool reads the model through
two objects, and one door:

```text
to_spec  →  Spec  →  .program  →  Program
```

## `Spec` and `Program`

A `Spec` holds the file as written: its `macros:`, its descriptions, and a
`piecewise:` block as one block. A `Program` holds the model the file builds:
every macro expanded, every name typed, every operator resolved to a node, and
every dimension and degree rule already checked. A curve stays one curve there;
`spec.expand('piecewise')` turns it into the variables and constraints it
stands for. [The file and the program](../about/file-and-program.md) says why
the two are split, and which tool reads which.

The curve below [expands](language/piecewise.md) into a weight per breakpoint,
a convexity row and one row per link:

```yaml title="curve.yaml"
dimensions:
  generator: { dtype: str }
  bp: { dtype: int }
parameters:
  bp_x: { dims: [generator, bp] }
  bp_y: { dims: [generator, bp] }
variables:
  p:
    dims: [generator]
    bounds: { lower: 0 }
  cost:
    dims: [generator]
    bounds: { lower: 0 }
piecewise:
  curve:
    over: bp
    links:
      - [p, bp_x]
      - [cost, bp_y, ">="]
    method: convex
assumptions:
  cost_is_never_negative:
    holds: "bp_y >= 0"
    description: a negative cost is a gain the objective would chase
constraints:
  target:
    dims: []
    expression: sum(p, over=generator) >= 100
objective:
  sense: minimize
  expression: sum(cost)
```

```python
from math_spec import to_spec

spec = to_spec('curve.yaml')
program = spec.program
sorted(program.constraints)  # ['target']
sorted(program.piecewise)  # ['curve']

rows = spec.expand('piecewise').program
sorted(rows.constraints)  # ['curve_convexity', 'curve_link0', 'curve_link1', 'target']
sorted(rows.variables)  # ['cost', 'curve_lam', 'p']
```

`to_spec` takes a path, the YAML, a mapping or a `Spec`. `spec.program` is the
program built when the model loaded, so every ask on one model returns one
object. A `piecewise:` block is a curve under `program.piecewise`, typed, and a
`sos:` block is a set under `program.sos`. `spec.expand('piecewise')` is the
model with each curve written out as rows, and `spec.expand()` writes the sets
out too.

Nothing in the package expands a model unasked. A consumer that builds rows
calls `spec.expand('piecewise')` at its own door. A consumer that cannot take a
curve refuses it in its own words, naming that call:

```python
def rows_of(program):
    if program.piecewise:
        raise ValueError(f"{sorted(program.piecewise)} are curves; pass spec.expand('piecewise')")
    return program


rows_of(rows) is rows  # True
```

## Formulations written out

`Spec.expand()` returns a `Spec` whose formulations — `piecewise:` and `sos:` —
are stated as the variables and constraints they stand for. It is the same math,
bound by the same data, and it is what to print for a reader who wants the rows
rather than the curve:

```python
sorted(spec.expand().variables)  # ['cost', 'curve_lam', 'p']
sorted(spec.expand().constraints)  # ['curve_convexity', 'curve_link0', 'curve_link1', 'target']
spec.expand() == spec.expand()  # True
```

A consumer that takes a set reads the program of `spec.expand('piecewise')`,
and one that does not reads the program of `spec.expand()`. The
[piecewise page](language/piecewise.md#what-a-set-is-written-out-as) says what a
set is written out as.

Every parameter the program declares is one the file declared, and the engine
binds each from its data. The program of an expansion keeps no curve: the
rows, the weights and the conditions the method states are declarations like
any other.

Each parameter and relation says what its table must carry, as `coverage`.
Under `total` the engine refuses a missing row and names the coordinate. Under
`masked` it reads a missing row as the value that contributes nothing. A
parameter a curve reads has `coverage` `None` on the program of the file,
because the block owns its shape. The expansion's program declares it `masked`
where the curve has `points:`
([coverage](language/declarations.md#coverage)).

## What the data has to satisfy

`program.assumptions` holds every fact the numbers have to meet, by the name a
refusal quotes. The engine, which has the numbers, runs each one and raises
`assumption_message` where it fails:

```python
from math_spec.program import Assumption, assumption_message

sorted(program.assumptions)  # ['cost_is_never_negative', 'curve_complete', 'curve_curvature', 'curve_increasing']
isinstance(program.assumptions['curve_increasing'], Assumption)  # True
message = assumption_message('curve_increasing', program.assumptions['curve_increasing'])
message  # "assumption 'curve_increasing' does not hold for the data bound to 'bp_x' — piecewise 'curve': method: convex requires strictly increasing breakpoints in 'bp_x' along 'bp'"
written = assumption_message('cost_is_never_negative', program.assumptions['cost_is_never_negative'])
written  # "assumption 'cost_is_never_negative' does not hold for the data bound to 'bp_y' — a negative cost is a gain the objective would chase"
```

One kind stands in that mapping. An `Assumption` carries a predicate as two masks —
`predicate`, and the `where` it is checked under — and the sentence a refusal
trails under `description`. What a `piecewise:` block's method implies about
its breakpoints is written in the same language and stands beside what the
file wrote: `expand()` emits those entries, and a model that still declares
the block derives the same text at load. So a consumer reads one kind, and a
condition a method adds later is a row in that mapping rather than a case to
handle.

## Nodes and masks

You never build a node yourself. The node classes are exported so that you can
test one with `isinstance` and read its fields. `children()` walks an expression
node's operands, and `where_children()` walks a predicate's. `walk()` yields
every node under an expression, parents first. `walk_regions()` yields each node
with the `cases:` regions it stands inside, outermost first.

A `Named` stands where an `expressions:` entry is used. Its `body` is the
entry's expression, the same object that `program.expressions[name].expression`
holds, and its value is the body's value. `children()` steps into the body, so
a walk reads through it; a renderer prints the name where the file wrote it.

Every `where` arrives as a `Mask`. Its `.root` is the resolved predicate. The
mask also answers four questions:

- `.conjuncts` flattens the `AND` spine, and stops at an `OR` or a `NOT`.
- `.names_read` gives the declarations the mask names.
- `.atoms` gives its leaves, with the connectives removed.
- `.dims` gives the dimensions the mask is read at.

A comparison of expressions arrives as an `ExpressionComparison`. Its two
sides are program expressions like a constraint's, and its `dims` are every
dimension either side carries. Its `names_read` are every parameter and relation
the sides read, the relation a grouping reads through included.

A name compared against a literal does not arrive this way. `p_max > 5` is a
`ParameterComparison` and `1 * p_max > 5` is an `ExpressionComparison`, though
both mask the same coordinates. Match both where you read a comparison over
parameters.

Three predicates read another predicate rather than a declaration. A
`CountComparison` carries the mask it counts and the dimension it counts away.
A `TranslatedPredicate` carries the mask it reads at a neighbouring
coordinate. A `PulledBackPredicate` carries the mask it reads through a
relation, and the `Direction` it reads in. Each holds that mask as a `Mask`,
where a connective holds a bare predicate: the walk recurses through a
connective and stops at these, so read the field where you need what is
inside. `.names_read` and `.dims` already see through all three, and the
relation a `PulledBackPredicate` reads is in its `.names_read`.

A predicate you build yourself answers the same four questions: wrap it in
`Mask`, or build it there with `~`, `&` and `|`. A mask folds as it is built,
so a boolean literal stands at a mask's root or nowhere. A `Region`'s `when`
arrives as a `Mask` too. The node classes live in `math_spec.program`.

## Asking what a program uses

`program.footprint` says which of the language's constructs one model uses.
It answers for the rows the program holds, and a curve still on the program is
not a row. Ask it of the rows a solver takes, since a curve written out uses
more of the language than the block did:

```python
footprint = rows.footprint

sorted(footprint.quadratic)  # []
sorted(footprint.domains)  # ['continuous']
sorted(footprint.sos_types)  # []
sorted(kind.__name__ for kind in footprint.kinds)  # ['Constant', 'Multiply', 'Parameter', 'Sum', 'Variable']
```

Every field is a set. An empty field means this model does not use the
construct. The footprint says what the model uses. Whether your solver or
file format can take a construct is your question
([what a solver can take](../about/limits.md#solver-capability)). Whether a
quadratic form is convex is not reported, because it depends on the numbers.

## Asking whether an axis can be cut

`program.separability` says, per axis, whether every row of the model fits
inside one window along it: a storage balance that reads the previous snapshot
does, and an annual emissions cap does not. Like the footprint, it answers for
the rows the program holds. The curve's rows sum over `bp`, so only the rows
show that tie:

```python
program.separability['bp'].windowable  # True
rows.separability['bp'].windowable  # False
rows.separability['generator'].linking_rows  # ('target',)
rows.separability['generator'].linking_columns  # ()
tied = rows.separability['generator'].coupled["constraint 'target'"]
tied.partition(' — ')[0]  # 'sums over generator'
'sum_back(window=n)' in tied  # True
```

Every declared axis has an entry. A coupling that a `piecewise:` expansion
introduced is named under the declaration the expansion emitted.

- `coupled` names each declaration that ties the whole axis together: a sum
  over the axis in a constraint, a grouping that consumes the axis, a wrapped
  shift, or a set. After the dash, each entry names the one change that would
  remove the tie.
- `undecided` lists each read whose reach only the data can say, as a `Reach`:
  the declaration, the parameter or relation it reads, and the kind of read. A
  caller that holds the data hands the smallest value of each named parameter
  to `resolved`, which returns the report with those reads decided.
- `restarts` names each declaration that counts a `position()` along the axis.
- `linking_rows` names each constraint that no single window holds.
- `linking_columns` names each variable the axis does not index, whose column
  every window reads.
- `ahead` is how many coordinates a window must see past its last row: `0`
  where every row is pointwise, and `2` for a `shift` of `-2`.
- `windowable` is false while anything is coupled or undecided.

A sum over the axis in the objective ties nothing. The report says nothing
about whether the windowed answer equals the whole-horizon answer.

## Writing a spec back out

`spec.to_dict()` returns the spec as plain data, and `spec.to_yaml()` returns
that data as a file. Both round-trip, so `to_spec(spec.to_dict()) == spec`.

`to_yaml()` writes every value and omits every absence. `domain: continuous` is
written out. A `null`, an infinite bound and an empty section are left out.
`dims: []` is written, because it says the declaration is a scalar.
