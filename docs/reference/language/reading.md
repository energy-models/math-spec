<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Reading a loaded model

Every other page here says what a _file_ may declare. This one says what a
consumer gets when it loads one. It is the contract between the language and
anything that reads the AST: a solver backend, a renderer, a second front end.
None of it is needed to write a model. These names are the whole of the
seam:

```text
to_spec  →  Spec  →  to_program  →  Program
```

## Two states, and the difference between them

**A `Spec` is what the file says. A `Program` is what it means**: macros
expanded, curves become the declarations they stand for, names typed,
operators resolved to nodes, and every dim and degree rule checked. A consumer
that _builds_ reads the second; one that asks what the file _wrote_ reads the
first.

`piecewise:` is the one construct whose variables and constraints do not exist
in the file. A curve [expands](piecewise.md) into weights, a convexity row and
one link row per tuple, and those declarations are the model as much as the
typed ones.

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

`to_program` takes a path, the YAML, a mapping, a `Spec`, or a `Program`, and
is idempotent. A consumer that does not know which it holds can call it.

## Which one to take

| you are                                                                | take      | because                                       |
| ---------------------------------------------------------------------- | --------- | --------------------------------------------- |
| building rows — a solver backend, a second front end                   | `Program` | every declaration is there, resolved          |
| reading the file — `macros:`, `description:`, a link as it was written | `Spec`    | a program keeps a curve's facts, not its text |

**Take a `Program` to build.** A consumer that reads `constraints:` off a
`Spec` still carrying a curve builds a model missing declarations. Such a model
solves, and the answer is wrong with nothing to see. `Program` is a different
type from `Spec`, so the signature refuses that mistake.

**A program cannot answer what the file wrote.** It has no `macros:`, no
`description:`, and no link expression; those are the `Spec`'s, and rendering
takes what `to_spec` returned. The projection runs one way. Of a `piecewise:`
block a program keeps `program.piecewise`: which parameters carry the curve,
and what the block assumes of the numbers, as a `checks` tuple. Each check
carries the names it is about, so the consumer holding the numbers runs it,
with `check_message` for the sentence to raise. What the expansion emitted is
answered where it is asked: a `ParameterDeclaration.derivation` says how that
parameter is filled, and `None` means the caller binds it.

**Nothing here is built by hand.** The program's nodes are exported to be
dispatched on with `isinstance` and read. What ships beside them is the walk,
`children()` and `where_children()` for a predicate, not builders. A mask is
`Mask`: the language's own resolved `where` as its `.root`, the node an engine
dispatches on, and every question derived from it, the way a dimension carries
`.maps`:

- `.conjuncts` flattens the `AND` spine and stops at an `OR` or a `NOT`;
- `.names_read` gives the declarations the mask names;
- `.atoms` gives its leaves, connectives removed;
- `.dims` gives the dimensions it is read at, read off the leaves, which
  resolution stamped with their declarations' dims.

A predicate a consumer builds from resolved pieces answers as a declaration's
own does: wrap it in `Mask`, or build it there with `~`, `&` and `|`.
Construction folds. A double negation cancels, and a literal flips or is
absorbed rather than buried, so a boolean literal stands at a mask's root or
nowhere. A tree with unresolved leaves is refused. A consumer asks the mask
rather than re-deriving any of these from `.root`, so two cannot disagree
about what a conjunct, a name or a comparison is. A `Region`'s `when` arrives
in the same carrier. The node classes a `.root` is built of live in
`math_spec.program`.

## Asking what a program uses

`program.footprint` is which of the language's constructs one program reaches
for: a **subset**, never the whole. It is walked once and held, since a program
cannot change after it is built.

```python
footprint = program.footprint

sorted(footprint.quadratic)  # []
sorted(footprint.domains)  # ['continuous']
sorted(footprint.sos_types)  # []
sorted(kind.__name__ for kind in footprint.shapes)  # ['Constant', 'Multiply', 'Parameter', 'Sum', 'Variable']
```

Every field is a set, so `if footprint.sos_types` asks whether sets appear at
all and `2 in footprint.sos_types` asks about one kind. An empty field says
this program does not use that construct, never that the construct does not
exist. A construct admitted later widens a set rather than adding a field.

**It answers what the program uses, never what you can do about it.** What a
sink can ingest is a separate axis
([capability is not the ceiling](../../about/ceiling.md)). A capability is
neither a flat set nor one verdict per construct: SOS is solver-bounded, and
quadratic is bounded on a single sink by convexity and by what it stands
beside. So there is no verdict here. Convexity is absent because it depends on
coefficient data rather than on anything a program states.

The footprint stops at the kind. A sink that takes a window but not a wrapped
one reads `Window in footprint.shapes` and then walks: `wrap`, `partition` and
a named width are refinements the set does not report.

## Asking whether an axis can be cut

A driver that solves a horizon in windows, a rolling horizon or a myopic
pathway, needs one thing from the model before it starts. **Is every row it
builds complete inside some window?** Storage carried over a snapshot is, once
the windows overlap by a row. An annual budget never is, and the windows still
solve, so nothing else would say so.

```python
program.separability['bp'].windowable  # False
tied = program.separability['generator'].coupled["constraint 'target'"]
tied.partition(' — ')[0]  # 'sums over generator'
'sum_back(within=n)' in tied  # True
```

Neither axis of the model above may be cut, and the report says which
declaration ties each one. The three declarations the `piecewise:` block
emitted are named under the names the expansion gave them, not under the block.

It is the locality [the ceiling](../../about/ceiling.md) argues in, pointwise,
bounded halo and global, asked about a dimension rather than an operator.
Every declared axis has an entry, walked once and held like
[`footprint`](#asking-what-a-program-uses).

`ahead` is how many coordinates a window must see past its last row: `0` where
every row is pointwise, `2` for a `shift` of `-2`. What a row reads _behind_ is
not reported. A window starts where the driver puts it, and what its first rows
meet there is the driver's edge policy, the opening state a rolling horizon
seeds.

What would break comes in three kinds:

- **`coupled` names each declaration that ties the axis together**: a sum
  over it in a constraint, a grouping that consumes it, a wrapped shift, a
  set. After the dash it names the one modelling change that would lift it: a
  horizon total becomes a rolling `sum_back`, a wrap becomes an opening-state
  seed, a grouping is windowed along the dimension it groups into. The remedy
  is named and not applied, since no rewrite keeps the model's meaning.
- **`undecided` lists each read whose reach only the data can say**, as a
  `Reach`: the declaration, the parameter or lookup, and what it stands as. That
  is an `offset` taken from a parameter, a `partition` a shift is grouped by,
  or a `coordinate` read through `at()`. A driver holding the data reads the
  least value of each named parameter and hands it to `resolved`, which
  returns the same verdict with those reads decided. The rule that a negative
  offset reads ahead and a positive one reads behind has one home. A reach a
  lookup decides is not a value, so it stays undecided and the driver refuses
  or resolves it itself.
- **`restarts` names each declaration counting a `position()` along the
  axis**, which a window restarts at its first row.

`windowable` is false while anything is coupled or undecided; a restart does
not count against it.

**A reduction means opposite things by position.** In a constraint a sum over
the axis ties every window to every other; in the objective it is additively
separable, an objective being a sum already. Two things are not decided here.
Whether the windowed answer is the whole-horizon one: a store carried over one
row windows cleanly, and a rolling solve of it is still a different answer.
And whether you _wanted_ a restart: a `position(t) == 0` seed fires once over
a horizon and once per window, and both are models somebody means.

## Writing a spec back out

**A `Spec` goes back out two ways, and they agree.** `to_dict()` is the spec
as plain data, and `to_yaml()` is that dict as the file a reviewer reads. Both
reproduce the model: `to_spec(spec.to_dict()) == spec`, and the same through
`to_yaml()`. So a model built as a `dict` still gets a file.

**A value is written and an absence is not.** A default is a fact the reviewer
reads, so `domain: continuous` is written out. A null, an infinite bound and a
section that declares nothing are not. An empty list is a value: `foreach: []`
is a scalar declaration and stays.
