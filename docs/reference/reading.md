<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Reading a loaded model

This page is for whoever writes an engine that builds models, a renderer, or a
checker. A tool reads the model through two objects, `Spec` and `Program`.

## `Spec` and `Program`

A `Spec` holds the file as written: its `macros:`, its descriptions, and a
`piecewise:` block as one block. A `Program` holds the model the file builds:
every macro expanded, every name typed, every operator resolved to a node, and
every dimension and degree rule already checked. A curve stays one curve there
until [`spec.expand()`](#formulations-written-out) writes it out.
[The file and the program](../about/file-and-program.md) says why the two are
split, and which tool reads which.

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
`sos:` block is a set under `program.sos`. Every parameter the program declares
is one the file declared.

## Formulations written out

`spec.expand(*kinds)` returns a new `Spec` with each `piecewise:` and `sos:`
block replaced by the variables and constraints it states.
[Writing a formulation out](language/piecewise.md#writing-a-formulation-out)
says what those are.

```python
expanded = spec.expand()
expanded == spec  # False
expanded.expand() is expanded  # True
spec.expand('sos') is spec  # True
```

- **The kinds are `'piecewise'` and `'sos'`, and no argument means both.** Any
  other string raises `ValueError`, naming the two. Curves go first whatever
  the order of the arguments, so the set a `method: sos2` curve states is
  written out too.
- **The expansion is a different model.** It declares more variables and
  constraints, so it does not compare equal to the model it came from. It
  declares the same dimensions and parameters, so the same data binds both.
- **A model with nothing to write out comes back as itself.** So does an
  expansion asked for the same kinds again.
- **The spec keeps no expansion.** A second call builds it again.
- **Nothing expands a model unasked.** A program holds its curves until
  `expand()` writes them out. The expansion is a model like any other:
  `to_yaml()` writes it, and its `program` holds the rows and no curve.

```python
sorted(rows.piecewise)  # []
```

## What the data has to satisfy

`program.assumptions` maps a name to an `Assumption`: each entry the file
declared, and each one a curve's method derives
([what a curve assumes](language/assumptions.md#what-a-curve-assumes)). An
`Assumption` carries a `predicate` and the `where` it is checked under, both
masks, and the `description` a refusal ends with. `assumption_message` returns
the message for an assumption the data does not meet:

```python
from math_spec.program import Assumption, assumption_message

sorted(program.assumptions)  # ['cost_is_never_negative', 'curve_complete', 'curve_curvature', 'curve_increasing']
isinstance(program.assumptions['curve_increasing'], Assumption)  # True
message = assumption_message('curve_increasing', program.assumptions['curve_increasing'])
message  # "assumption 'curve_increasing' does not hold for the data attached to 'bp_x' — piecewise 'curve': method: convex requires strictly increasing breakpoints in 'bp_x' along 'bp'"
written = assumption_message('cost_is_never_negative', program.assumptions['cost_is_never_negative'])
written  # "assumption 'cost_is_never_negative' does not hold for the data attached to 'bp_y' — a negative cost is a gain the objective would chase"
```

## Nodes and masks

The node classes live in `math_spec.program`, for `isinstance` tests and field
reads. `children()` walks an expression
node's operands, and `where_children()` walks a predicate's. `walk()` yields
every node under an expression, parents first. `walk_regions()` yields each node
with the `cases:` regions it stands inside, outermost first.

A `Named` stands where an `expressions:` entry is used. Its `body` is the
entry's expression, the same object that `program.expressions[name].expression`
holds, and its value is the body's value. `children()` steps into the body, so
a walk reads through it.

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
both mask the same coordinates.

Three predicates read another predicate rather than a declaration. A
`CountComparison` carries the mask it counts and the dimension it counts away.
A `TranslatedPredicate` carries the mask it reads at a neighbouring
coordinate. A `PulledBackPredicate` carries the mask it reads through a
relation, and the `Direction` it reads in. Each holds that mask as a `Mask`,
where a connective holds a bare predicate, so the walk recurses through a
connective and stops at these. `.names_read` and `.dims` see through all three,
and the relation a `PulledBackPredicate` reads is in its `.names_read`.

`Mask(predicate)` answers the same four questions of any resolved predicate,
and `~`, `&` and `|` combine masks into a mask. A mask folds as it is built, so a boolean literal
stands at a mask's root or nowhere. A `Region`'s `when` is a `Mask` too.

## Asking what a program uses

`program.footprint` says which of the language's constructs one model uses.
It answers for the rows the program holds. A curve still on the program is not
a row, so its constructs count on the program of the expansion:

```python
footprint = rows.footprint

sorted(footprint.quadratic)  # []
sorted(footprint.domains)  # ['continuous']
sorted(footprint.sos_types)  # []
sorted(kind.__name__ for kind in footprint.kinds)  # ['Constant', 'Multiply', 'Parameter', 'Sum', 'Variable']
```

Every field is a set, and an empty field means the model does not use the
construct. Whether a solver takes a construct is the engine's question
([what counts as language](../about/what-counts-as-language.md#what-each-tool-decides-for-itself)).
Convexity is not reported: it depends on the numbers.

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
written out. A `null` and an empty section are left out.
`dims: []` is written, because it says the declaration is a scalar.
