<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Reading a loaded model

The other pages say what a file may declare. This page says what a program gets
when it loads one. You need none of it to write a model. A **consumer** is a
program that reads a loaded model, such as a solver backend, a renderer or a
checker, and it reads the model through these names:

```text
to_spec  →  Spec  →  to_program  →  Program
```

## `Spec` and `Program`

A `Spec` is what the file says. A `Program` is what the file means. In a
`Program`, the macros are expanded, each curve has become the declarations it
stands for, the names are typed, the operators are resolved to nodes, and every
dimension rule and degree rule is already checked.

A `piecewise:` block is the construct that makes the two differ. A curve
[expands](piecewise.md) into weights, a convexity row and one link row per
tuple, and those declarations are part of the model as much as the typed ones:

```yaml title="curve.yaml"
dimensions:
  generator: { dtype: str }
  bp: { dtype: int }
parameters:
  bp_x: { dims: [generator, bp] }
  bp_y: { dims: [generator, bp] }
variables:
  p:
    foreach: [generator]
    bounds: { lower: 0 }
  cost:
    foreach: [generator]
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
    foreach: []
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
on a `Program`, it returns the same object unchanged, so a consumer that does not
know which it holds can call `to_program` and be sure of the result.

| you are                                                                      | take      | because                                       |
| ---------------------------------------------------------------------------- | --------- | --------------------------------------------- |
| building rows, as a solver backend or a second front end does                | `Program` | Every declaration is there, and resolved      |
| reading the file, for `macros:`, `description:`, or a link as it was written | `Spec`    | A program keeps a curve's facts, not its text |

A consumer that built from a `Spec` still carrying a curve would build a model
with declarations missing, and that model solves, with a wrong answer and
nothing to show why. `Program` is a different type from `Spec`, so the signature
refuses that mistake.

!!! note "A program cannot answer what the file wrote"

    It has no `macros:`, no `description:`, and no link expression. Anything that
    renders is handed what `to_spec` returned.

What a program keeps of a `piecewise:` block is `program.piecewise`: which
parameters carry the curve, and what the block assumes about the numbers, as a
`checks` tuple. Each check names the parameters it is about, so the consumer that
holds the numbers runs it, and `check_message` gives the sentence to raise.
`ParameterDeclaration.derivation` says how a parameter is filled, and `None`
means the caller binds it.

## Nodes and masks

You never build a node yourself. The node classes are exported so that you can
test one with `isinstance` and read it. `children()` walks an expression node's
operands, and `where_children()` walks a predicate's. No builders ship.

Every `where` arrives as a `Mask`. Its `.root` is the resolved predicate, which
is the node an engine tests with `isinstance`. The mask answers four more
questions, so that no consumer works them out again:

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

`program.footprint` says which of the language's constructs one program uses. It
is walked once and then held, because a program cannot change after it is built.

```python
footprint = program.footprint

sorted(footprint.quadratic)  # []
sorted(footprint.domains)  # ['continuous']
sorted(footprint.sos_types)  # []
sorted(kind.__name__ for kind in footprint.shapes)  # ['Constant', 'Multiply', 'Parameter', 'Sum', 'Variable']
```

Every field is a set. `if footprint.sos_types` asks whether sets appear at all,
and `2 in footprint.sos_types` asks about one kind. An empty field says that this
program does not use the construct, never that the construct does not exist. A
construct admitted to the language later widens one of these sets.

!!! note "The footprint says what the program uses, and never what to do about it"

    Whether your **sink**, which is the solver API or file format a built model is
    handed to, can take a construct is your question. See
    [what a solver can take](../../about/limits.md#what-a-solver-can-take-is-a-separate-question).
    Whether a quadratic form is convex is not reported at all, because it depends
    on the numbers.

The footprint stops at the kind of construct. A sink that accepts a window but
not a wrapped one reads `Window in footprint.shapes`, then walks the tree for the
detail.

## Asking whether an axis can be cut

A program that solves one long horizon in short windows has to know whether every
row of the model is complete inside a single window. Storage carried from one
snapshot to the next is, as long as neighbouring windows overlap by one row. An
annual budget never is. The windows solve either way, so nothing later would tell
you.

```python
program.separability['bp'].windowable  # False
tied = program.separability['generator'].coupled["constraint 'target'"]
tied.partition(' — ')[0]  # 'sums over generator'
'sum_back(within=n)' in tied  # True
```

Every declared axis has an entry, and the report is walked once and held, like
[`footprint`](#asking-what-a-program-uses). A coupling that a `piecewise:`
expansion introduced is named under the declaration the expansion emitted.

- `coupled` names each declaration that ties the whole axis together: a sum over
  the axis in a constraint, a grouping that consumes the axis, a wrapped shift,
  or a set. After the dash, each entry names the one change that would remove the
  tie: a horizon total becomes a rolling `sum_back`, a wrap becomes an opening
  state the caller seeds, and a grouping is windowed along the dimension it
  groups into. The report names the change and never applies it.
- `undecided` lists each read whose reach only the data can say. Each entry is a
  `Reach`, carrying the declaration, the parameter or lookup it reads, and the
  kind of read: an `offset` from a parameter, a `partition` a shift is grouped
  by, or a `coordinate` read through `at()`. A caller that holds the data reads
  the smallest value of each named parameter and hands it to `resolved`, which
  returns the report with those reads decided. A reach that a lookup decides is
  not a number, so it stays undecided.
- `restarts` names each declaration that counts a `position()` along the axis,
  because a window restarts that count at its first row.
- `ahead` is how many coordinates a window must see past its last row: `0` where
  every row is pointwise, and `2` for a `shift` of `-2`. What a row reads behind
  is not reported, because what a window's first rows meet is the opening state
  the driver seeds.
- `windowable` is false while anything is coupled or undecided. A restart does
  not count against it.

A sum over the axis ties every window to every other window in a constraint, and
not in the objective, because an objective is a sum of windows already.

The report does not say whether the windowed answer equals the whole-horizon
answer: a store carried over one row windows cleanly, and a rolling solve of it
is still a different answer. It does not say whether the modeller wanted a
restart, because a `position(t) == 0` seed fires once over a horizon and once per
window, and both are models somebody means.

## Writing a spec back out

A `Spec` goes back out two ways, and they agree. `to_dict()` is the spec as plain
data, and `to_yaml()` is that dict as the file a reviewer reads. Both reproduce
the model: `to_spec(spec.to_dict()) == spec`, and the same through `to_yaml()`.
So a model built as a `dict` still gets a file.

A value is written and an absence is not. A default is a fact the reviewer reads,
so `domain: continuous` is written out. A null, an infinite bound and a section
that declares nothing are not. An empty list is a value: `foreach: []` is a
scalar declaration, and it stays.
