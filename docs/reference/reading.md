<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Reading a loaded model

This page is for whoever writes an engine that builds models, a renderer, or a
checker. You need none of it to write a model. A tool reads the model through
two objects:

```text
to_spec  →  Spec  →  to_program  →  Program
```

## `Spec` and `Program`

A `Spec` holds the file as written: its `macros:`, its descriptions, and a
`piecewise:` block as one block. A `Program` holds the model the file builds:
every macro expanded, every curve turned into the variables and constraints it
stands for, every name typed, every operator resolved to a node, and every
dimension and degree rule already checked.

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
constraints:
  target:
    dims: []
    expression: sum(p, over=generator) >= 100
objective:
  sense: minimize
  expression: sum(cost)
```

```python
from math_spec import to_spec, to_program

spec = to_spec('curve.yaml')
sorted(spec.constraints)  # ['target']

program = to_program(spec)
sorted(program.constraints)  # ['curve_convexity', 'curve_link0', 'curve_link1', 'target']
sorted(program.variables)  # ['cost', 'curve_lam', 'p']
```

`to_program` takes a path, the YAML, a mapping, a `Spec` or a `Program`. Called
on a `Program`, it returns the same object unchanged.

| you are                                                                      | take      | because                                  |
| ---------------------------------------------------------------------------- | --------- | ---------------------------------------- |
| building rows, as a solver backend or a second front end does                | `Program` | Every declaration is there, and resolved |
| reading the file, for `macros:`, `description:`, or a link as it was written | `Spec`    | A program keeps a curve's facts          |

`program.piecewise` keeps what the block assumed about the numbers, such as
"the breakpoints in `bp_x` increase", as a `checks` tuple. The engine, which has
the numbers, runs each check, and `check_message` gives it the sentence to
raise. `ParameterDeclaration.derivation` says how a parameter is filled, and
`None` means the engine binds it from its data.

## Nodes and masks

You never build a node yourself. The node classes are exported so that you can
test one with `isinstance` and read its fields. `children()` walks an expression
node's operands, and `where_children()` walks a predicate's. `walk()` yields
every node under an expression, parents first. `walk_regions()` yields each node
with the `cases:` regions it stands inside, outermost first.

Every `where` arrives as a `Mask`. Its `.root` is the resolved predicate. One
member of the `Predicate` union never reaches you. Lowering rewrites every
`ArithmeticComparison` into an `ExpressionComparison`. The
mask also answers four questions:

- `.conjuncts` flattens the `AND` spine, and stops at an `OR` or a `NOT`.
- `.names_read` gives the declarations the mask names.
- `.atoms` gives its leaves, with the connectives removed.
- `.dims` gives the dimensions the mask is read at.

A comparison of expressions arrives as an `ExpressionComparison`. Its two
sides are program expressions like a constraint's, and its `dims` are every
dimension either side carries. Its `names_read` are every parameter and relation
the sides read, the relation a grouping reads through included.

A predicate you build yourself answers the same four questions: wrap it in
`Mask`, or build it there with `~`, `&` and `|`. A mask folds as it is built,
so a boolean literal stands at a mask's root or nowhere. A `Region`'s `when`
arrives as a `Mask` too. The node classes live in `math_spec.program`.

## Asking what a program uses

`program.footprint` says which of the language's constructs one model uses.

```python
footprint = program.footprint

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
does, and an annual emissions cap does not.

```python
program.separability['bp'].windowable  # False
program.separability['generator'].linking_rows  # ('target',)
program.separability['generator'].linking_columns  # ()
tied = program.separability['generator'].coupled["constraint 'target'"]
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
