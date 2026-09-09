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
reads a model through:

```text
to_spec  →  Spec  →  to_program  →  Program
```

## `Spec` and `Program`

A `Spec` is what the file says. A `Program` is what the file means. In a
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
a `Program` that already exists. Calling it again returns the same program
unchanged. So a consumer that does not know which of these it holds can call
`to_program` and be sure of the result.

## Which of the two a consumer takes

| you are                                                                      | take      | because                                       |
| ---------------------------------------------------------------------------- | --------- | --------------------------------------------- |
| building rows, as a solver backend or a second front end does                | `Program` | Every declaration is there, and resolved      |
| reading the file, for `macros:`, `description:`, or a link as it was written | `Spec`    | A program keeps a curve's facts, not its text |

A consumer that builds takes a `Program`. Suppose one reads `constraints:` off a
`Spec` that still carries a curve. It then builds a model with declarations
missing. A model with declarations missing is still a model, so it solves, and
the answer is wrong with nothing to show you why. `Program` is a different type
from `Spec`, so the signature refuses that mistake instead of the numbers
reporting it later.

!!! note "A program cannot answer what the file wrote"

    It has no `macros:`, no `description:`, and no link expression. Those
    belong to the `Spec`, so anything that renders has to be handed what
    `to_spec` returned. The projection runs one way on purpose.

What a program keeps of a `piecewise:` block is `program.piecewise`. That holds
which parameters carry the curve, and what the block assumes about the numbers,
as a `checks` tuple. Each check carries the names it is about. So the consumer
that holds the numbers runs the check, and `check_message` gives the sentence to
raise.

To find out where a declaration came from, ask the declaration.
`ParameterDeclaration.derivation` says how a parameter is filled, and `None`
means the caller binds it.

You never build a node yourself. The node classes are exported so that you can
test one with `isinstance` and read it. That is why `children()`, which walks a
node's operands, ships beside them, and no builders do.

Every `where` arrives as a `Mask`. Its `.root` is the resolved predicate, which
is the node an engine tests with `isinstance`. The mask answers four more
questions about that root, so that no consumer works them out again:

- `.conjuncts` flattens the `AND` spine, and stops at an `OR` or a `NOT`.
- `.names_read` gives the declarations that the mask names.
- `.atoms` gives its leaves, with the connectives removed.
- `.dims` gives the dimensions the mask is read at. These are read off the
  leaves, which resolution stamped with their declarations' dimensions, in the
  same way a lookup leaf carries the dimension it maps out of.

A predicate you build yourself answers the same four questions. Wrap it in
`Mask`, or build it there with `~`, `&` and `|`.

A mask folds as it is built. A double negation cancels, and a `True` or `False`
is absorbed instead of being buried in the tree. So a boolean literal stands at
a mask's root or nowhere at all. A tree with an unresolved leaf is refused.

Ask the mask rather than reading `.root` again yourself. Then two consumers
cannot disagree about what a conjunct, a name or a comparison is.

A `Region`'s `when` arrives as a `Mask` too. The node classes a `.root` is built
from live in `math_spec.program`, beside every other node a consumer reads.

## Asking what a program uses

`program.footprint` tells you which of the language's constructs one program
uses. It is walked once and then held, which is safe because a program cannot
change after it is built.

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

!!! note "The footprint says what the program uses, and never what to do about it"

    Whether your sink can take a construct is your question, and not the
    footprint's. See
    [what a solver can take](../../about/limits.md#what-a-solver-can-take-is-a-separate-question).
    One construct can have more than one answer on one sink: a quadratic form is
    bounded once by whether it is convex, and again by what stands beside it in
    the model.

Whether a form is convex is not reported at all, because it depends on the
numbers rather than on anything the file states.

The footprint stops at the kind of construct. Take a sink that accepts a window
but not a wrapped one. It reads `Window in footprint.shapes`, and then walks the
tree for the detail. There is no end to such details, and each is one line of
code once the footprint has said where to look.

## Asking whether an axis can be cut

A program that solves one long horizon in short windows has to know one thing
first: whether every row of the model is complete inside a single window. A
rolling horizon and a myopic pathway both need that answer.

Storage carried from one snapshot to the next is complete inside a window, as
long as neighbouring windows overlap by one row. An annual budget never is. The
windows still solve either way, so nothing later would tell you.

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

[The limits](../../about/limits.md) asks the same question about one operator.
Here it is asked about one dimension of one model.

Every declared axis has an entry. The report is walked once and held, like
[`footprint`](#asking-what-a-program-uses). Answering for every axis costs no
more than answering for one, because a construct that ties an axis names that
axis.

`ahead` is how many coordinates a window must see past its last row. It is `0`
where every row is pointwise, and `2` for a `shift` of `-2`.

What a row reads _behind_ is not reported. A window starts where the driver puts
it, and what its first rows meet there is a matter of edge policy. That policy is
the opening state a rolling horizon seeds, and it is the driver's to carry.

What stops an axis being cut comes in three kinds, and each one asks something
different of the caller.

`coupled` names each declaration that ties the whole axis together. That can be
a sum over the axis in a constraint, a grouping that consumes the axis, a
wrapped shift, or a set. After the dash, each entry names the one change to the
model that would remove the tie: a horizon total becomes a rolling `sum_back`, a
wrap becomes an opening state that the caller seeds, and a grouping is windowed
along the dimension it groups into. No window size satisfies a tie, and no
rewrite keeps the model's meaning, so the report names the change and never
applies it.

`undecided` lists each read whose reach only the data can say. Each entry is a
`Reach`, and it carries the declaration, the parameter or lookup it reads, and
which kind of read it is: an `offset` taken from a parameter, a `partition` that
a shift is grouped by, or a `coordinate` read through `at()`.

A caller that holds the data reads the smallest value of each named parameter
and hands it to `resolved`. That returns the same report with those reads
decided. A negative offset reads ahead; a positive offset reads behind, and asks
for nothing.

A reach that a lookup decides is not a number, so it stays undecided. The caller
either refuses it or resolves it itself.

`restarts` names each declaration that counts a `position()` along the axis,
because a window restarts that count at its first row.

`windowable` is false while anything is coupled or undecided. A restart does not
count against it.

The same sum means opposite things in the two places it can stand. In a
constraint, a sum over the axis ties every window to every other window. In the
objective, it does not, because an objective is a sum of windows already.

Two things this report does not decide. It does not say whether the windowed
answer equals the whole-horizon answer: a store carried over one row windows
cleanly, and a rolling solve of it is still a different answer. And it does not
say whether the modeller wanted a restart, because a `position(t) == 0` seed
fires once over a horizon and once per window, and both are models that somebody
means.
