<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Reading a loaded model

The [language pages](language/index.md) say what a file may declare. This page
says what a tool gets when it loads one. You need none of it to write a model.
It is for whoever writes an engine that builds models, a renderer, or a
checker, and they read the model through two objects:

```text
to_spec  →  Spec  →  to_program  →  Program
```

## `Spec` and `Program`

A `Spec` holds the file as written: its `macros:`, its descriptions, and a
`piecewise:` block as one block. A `Program` holds the model the file builds:
every macro expanded, every curve turned into the variables and constraints it
stands for, every name typed, every operator resolved to a node, and every
dimension and degree rule already checked.

A `piecewise:` block is what makes the two differ. The curve below
[expands](language/piecewise.md) into a weight per breakpoint, a convexity row and one
row per link, and those are as much part of the model as the constraint you
typed:

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
on a `Program`, it returns the same object unchanged, so a function that does not
know which it was handed can call `to_program` and be sure of the result.

| you are                                                                      | take      | because                                       |
| ---------------------------------------------------------------------------- | --------- | --------------------------------------------- |
| building rows, as a solver backend or a second front end does                | `Program` | Every declaration is there, and resolved      |
| reading the file, for `macros:`, `description:`, or a link as it was written | `Spec`    | A program keeps a curve's facts, not its text |

!!! note "A `Program` cannot answer what the file wrote"

    It has no `macros:`, no `description:`, and no link expression. Anything that
    renders is handed what `to_spec` returned.

`program.piecewise` keeps what the block assumed about the numbers, such as
"the breakpoints in `bp_x` increase", as a `checks` tuple. Each check names the
parameters it is about. The engine, which has the numbers, runs the check, and
`check_message` gives it the sentence to raise. `ParameterDeclaration.derivation`
says how a parameter is filled, and `None` means the engine binds it from its
data.

## Nodes and masks

You never build a node yourself. The node classes are exported so that you can
test one with `isinstance` and read its fields. `children()` walks an expression
node's operands, and `where_children()` walks a predicate's. `walk()` yields
every node under an expression, parents first. `walk_regions()` yields each node
with the `cases:` regions it stands inside, outermost first, so an engine that
asks which rows a piece owes data at does not recurse for the answer itself.

Every `where` arrives as a `Mask`. Its `.root` is the resolved predicate, which
is the node an engine tests with `isinstance`. The mask also answers four
questions that every engine would otherwise work out for itself:

- `.conjuncts` flattens the `AND` spine, and stops at an `OR` or a `NOT`.
- `.names_read` gives the declarations the mask names.
- `.atoms` gives its leaves, with the connectives removed.
- `.dims` gives the dimensions the mask is read at.

A predicate you build yourself answers the same four questions: wrap it in `Mask`,
or build it there with `~`, `&` and `|`. A mask folds as it is built: a double
negation cancels, and a `True` or `False` is absorbed rather than buried in the
tree, so a boolean literal stands at a mask's root or nowhere. A tree with an
unresolved leaf is refused. A `Region`'s `when` arrives as a `Mask` too. The node
classes live in `math_spec.program`.

## Asking what a program uses

`program.footprint` says which of the language's constructs one model uses. It
is computed once and then held, because a `Program` cannot change after it is
built.

```python
footprint = program.footprint

sorted(footprint.quadratic)  # []
sorted(footprint.domains)  # ['continuous']
sorted(footprint.sos_types)  # []
sorted(kind.__name__ for kind in footprint.shapes)  # ['Constant', 'Multiply', 'Parameter', 'Sum', 'Variable']
```

Every field is a set. `if footprint.sos_types` asks whether sets appear at all,
and `2 in footprint.sos_types` asks about one kind. An empty field means this
model does not use the construct, not that the construct does not exist.

!!! note "The footprint says what the model uses, and never what to do about it"

    Whether your solver or file format can take a construct is your question.
    See [what a solver can take](../about/limits.md#solver-capability).
    Whether a quadratic form is convex is not reported at all, because it depends
    on the numbers.

The footprint stops at the kind of construct. An engine whose solver accepts a
window but not a wrapped one reads `Window in footprint.shapes`, then walks the
tree for the detail.

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

Every declared axis has an entry, and the report is walked once and held, like
[`footprint`](#asking-what-a-program-uses). A coupling that a `piecewise:`
expansion introduced is named under the declaration the expansion emitted.

- `coupled` names each declaration that ties the whole axis together: a sum over
  the axis in a constraint, a grouping that consumes the axis, a wrapped shift,
  or a set. After the dash, each entry names the one change that would remove
  the tie.
- `undecided` lists each read whose reach only the data can say. Each entry is a
  `Reach`, carrying the declaration, the parameter or relation it reads, and the
  kind of read: an `offset` from a parameter, a `partition` a shift is grouped
  by, or a `coordinate` read through `at()`. A caller that holds the data reads
  the smallest value of each named parameter and hands it to `resolved`, which
  returns the report with those reads decided. A reach that a relation decides is
  not a number, so it stays undecided.
- `restarts` names each declaration that counts a `position()` along the axis,
  because a window restarts that count at its first row.
- `linking_rows` names each constraint that no single window holds. Two shapes
  reach it: a row the axis does not index, which stands in every window, and a
  row that `coupled` also names.
- `linking_columns` names each variable the axis does not index, whose column
  every window reads.
- `ahead` is how many coordinates a window must see past its last row: `0` where
  every row is pointwise, and `2` for a `shift` of `-2`.
- `windowable` is false while anything is coupled or undecided. A restart does
  not count against it.

A sum over the axis in the objective ties nothing, because an objective is a
sum of windows already. The report says nothing about whether the windowed
answer equals the whole-horizon answer, and nothing about whether a restart was
meant.

## Writing a spec back out

`spec.to_dict()` returns the spec as plain data, and `spec.to_yaml()` returns
that data as a file. Both round-trip, so `to_spec(spec.to_dict()) == spec`, and the
same holds through `to_yaml()`. So a model that a library assembled as a `dict` still
gets a file for a reviewer to read.

`to_yaml()` writes every value and omits every absence. `domain: continuous` is
written out, because a reviewer should see the default. A `null`, an infinite
bound and an empty section are left out. `dims: []` is written, because an
empty list is a value: it says the declaration is a scalar.
