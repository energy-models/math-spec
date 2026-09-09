<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Reading a loaded model

Every other page here says what a _file_ may declare. This page says what a
_program_ gets when it loads one. It is the contract between the language and
anything that reads the syntax tree, such as a solver backend, a renderer, or a
second front end.

You need none of this to write a model. These are the names that a **consumer**
reads a model through, and they are the whole of the seam:

```text
to_spec  →  Spec  →  to_program  →  Program
```

## Two states, and the difference between them

**A `Spec` is what the file says. A `Program` is what the file means.** In a
`Program`, the macros are expanded, each curve has become the declarations it
stands for, the names are typed, the operators are resolved to nodes, and every
dimension rule and degree rule is already checked.

A consumer that _builds_ reads the `Program`. A consumer that asks what the file
_wrote_ reads the `Spec`.

A file may declare a construct whose variables and constraints do not exist yet.
`piecewise:` is the construct that does this. A curve
[expands](piecewise.md) into weights, a convexity row, and one link row per
tuple. Those declarations are part of the model just as much as the ones
somebody typed.

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

`to_program` takes whatever you have: a path, the YAML, a mapping, a `Spec`, or
a `Program` that already exists. It is idempotent. So a consumer that does not
know which of these it holds can call `to_program` and be sure of the result.

## Which one to take

| you are                                                                      | take      | because                                       |
| ---------------------------------------------------------------------------- | --------- | --------------------------------------------- |
| building rows, as a solver backend or a second front end does                | `Program` | Every declaration is there, and resolved      |
| reading the file, for `macros:`, `description:`, or a link as it was written | `Spec`    | A program keeps a curve's facts, not its text |

**Take a `Program` to build.** Suppose a consumer reads `constraints:` off a
`Spec` that still carries a curve. It then builds a model with declarations
missing. A model with declarations missing is still a model, so it solves, and
the answer is wrong with nothing to show you why. `Program` is a different type
from `Spec`, so the signature refuses that mistake instead of the numbers
reporting it later.

**A program cannot answer what the file wrote.** It has no `macros:`, no
`description:`, and no link expression. Those belong to the `Spec`, so anything
that renders has to be handed what `to_spec` returned. The projection runs one
way on purpose.

What a program keeps of a `piecewise:` block is `program.piecewise`. That holds
which parameters carry the curve, and what the block assumes about the numbers,
as a `checks` tuple. Each check carries the names it is about. So the consumer
that holds the numbers runs the check, and `check_message` gives the sentence to
raise.

What the expansion emitted is answered where you ask it instead. A
`ParameterDeclaration.derivation` says how that parameter is filled, and `None`
means the caller binds it.

**Nothing here is built by hand.** The program's nodes are exported so that you
dispatch on them with `isinstance` and read them. That is why what ships beside
them is the walk, `children()`, and not a set of builders.

A mask is a `Mask`. Its `.root` is the language's own resolved `where`, which is
the node an engine still dispatches on with `isinstance`. Every other question
is derived from that root and carried on the mask, in the way a dimension
carries `.maps`:

- `.conjuncts` flattens the `AND` spine, and stops at an `OR` or a `NOT`.
- `.names_read` gives the declarations that the mask names.
- `.atoms` gives its leaves, with the connectives removed.
- `.dims` gives the dimensions the mask is read at. These are read off the
  leaves, which resolution stamped with their declarations' dimensions, in the
  same way a lookup leaf carries the dimension it maps out of.

So a predicate that a consumer builds from resolved pieces answers exactly as a
declaration's own predicate does. Wrap it in `Mask`, or build it there with `~`,
`&` and `|`.

Construction folds as it goes. A double negation cancels. A literal flips or is
absorbed, rather than being buried in the tree. So a boolean literal stands at a
mask's root or nowhere at all, whether the mask was derived or carried. A tree
with unresolved leaves is refused at the door.

A consumer asks the mask rather than re-deriving any of this from `.root`. So two
consumers cannot come to disagree about what a conjunct, a name or a comparison
is.

A `Region`'s `when` arrives in the same carrier. The node classes that a `.root`
is built from live in `math_spec.program`, beside every other node a consumer
dispatches on.

## Asking what a program uses

`program.footprint` tells you which of the language's constructs one program
actually reaches for. It is a **subset**, and never the whole language. It is
walked once and then held, which is safe because a program cannot change after
it is built.

```python
footprint = program.footprint

sorted(footprint.quadratic)  # []
sorted(footprint.variable_types)  # ['continuous']
sorted(footprint.sos_types)  # []
sorted(kind.__name__ for kind in footprint.shapes)  # ['Constant', 'Multiply', 'Parameter', 'Sum', 'Variable']
```

Every field is a set. So `if footprint.sos_types` asks whether sets appear at
all, and `2 in footprint.sos_types` asks about one kind of set.

An empty field says that this program does not use that construct. It never says
that the construct does not exist. When a construct is admitted to the language
later, it widens one of these sets, rather than needing a new field that no
consumer yet reads.

**The footprint answers what the program uses, and never what you can do about
it.** What a sink can ingest is a separate axis; see
[capability is not the ceiling](../../about/ceiling.md). On that axis, a
capability is neither a flat set nor a single verdict per construct. SOS is
solver-bounded. Quadratic is bounded twice over on a single sink, once by
convexity and again by what it stands beside.

So there is deliberately no verdict here for you to read in place of giving one.
Convexity is absent for a different reason: it depends on coefficient data,
rather than on anything a program states.

The footprint stops at the kind of construct. Take a sink that accepts a window
but not a wrapped window. It reads `Window in footprint.shapes`, and then it
walks the tree. Refinements such as `wrap`, `partition` and a named width go on
without end, and each one is a single line of code once the set has said where
to look.

## Asking whether an axis can be cut

A driver that solves a horizon in windows needs one thing from the model before
it starts. A rolling horizon and a myopic pathway are both such drivers, and the
question is: **is every row it builds complete inside some window?**

Storage carried over a snapshot is complete inside a window, once the windows
overlap by one row. An annual budget never is. And the windows still solve, so
nothing else in the pipeline would tell you.

```python
program.separability['bp'].windowable  # False
tied = program.separability['generator'].coupled["constraint 'target'"]
tied.partition(' — ')[0]  # 'sums over generator'
'sum_back(within=n)' in tied  # True
```

Neither axis of the model above may be cut. The report says which declaration
ties each one. That includes the three declarations that the `piecewise:` block
emitted, so a coupling introduced by an expansion is named under the name the
expansion gave it, rather than under the block that a reader wrote.

This is the same locality that [the ceiling](../../about/ceiling.md) already
argues in, which is pointwise, bounded halo and global. Here the question is
asked about a dimension rather than about an operator.

Every declared axis has an entry. The report is walked once and held, like
[`footprint`](#asking-what-a-program-uses). Answering for every axis costs what
answering for one axis did, because every construct that ties an axis also names
the axis it ties.

`ahead` is how many coordinates a window must see past its last row. It is `0`
where every row is pointwise, and `2` for a `shift` of `-2`.

What a row reads _behind_ is not reported. A window starts where the driver puts
it, and what its first rows meet there is a matter of edge policy. That policy is
the opening state a rolling horizon seeds, and it is the driver's to carry.

What would break comes in three kinds, so that a driver can act on each one.

`coupled` names each declaration that ties the axis together. Such a declaration
can be a sum over the axis in a constraint, a grouping that consumes the axis, a
wrapped shift, or a set. After the dash, it names the one modelling change that
would lift the coupling: a horizon total becomes a rolling `sum_back`, a wrap
becomes an opening-state seed, and a grouping is windowed along the dimension it
groups into. No window satisfies a coupling, and no rewrite keeps the meaning of
the model, so the remedy is named and not applied.

`undecided` lists each read whose reach only the data can say. Each entry is a
`Reach`, carrying the declaration, the parameter or lookup, and what that stands
as. It stands as an `offset` taken from a parameter, a `partition` that a shift
is grouped by, or a `coordinate` read through `at()`.

A driver that holds the data reads the least value of each named parameter and
hands it to `resolved`. That folds the value in, and returns the same verdict
with those reads decided. One rule has one home there: a negative offset reads
ahead, and a positive offset reads behind and asks nothing.

A reach that a lookup decides is not a value. So it stays undecided, and the
driver either refuses it or resolves it itself.

`restarts` names each declaration that counts a `position()` along the axis,
because a window restarts that count at its first row.

`windowable` is false while anything is coupled or undecided. A restart does not
count against it.

**A reduction means opposite things depending on its position**, and that is the
whole of the care needed here. In a constraint, a sum over the axis ties every
window to every other window. In the objective, the same sum is additively
separable, because an objective is a sum already.

Two things are not decided here. The first is whether the windowed answer is the
whole-horizon answer. A store carried over one row windows cleanly, and a
rolling solve of it is still a different answer. The second is whether the
modeller _wanted_ a restart. A `position(t) == 0` seed fires once over a
horizon, and once per window, and both of those are models that somebody
means.
