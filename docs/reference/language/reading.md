<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Reading a loaded model

Every other page here says what a _file_ may declare. This one says what a
_program_ gets when it loads one: the contract between the language and
anything that reads the AST — a solver backend, a renderer, a second front end.

None of it is needed to write a model: these are the names a **consumer**
reads a model through, and they are the whole of the seam:

```text
to_spec  →  Spec  →  to_program  →  Program
```

## Two states, and the difference between them

**A `Spec` is what the file says. A `Program` is what it means** — macros
expanded, curves become the declarations they stand for, names typed,
operators resolved to nodes, and every dim and degree rule already checked. A
consumer that _builds_ reads the second; one that asks what the file _wrote_
reads the first.

A file may declare a construct whose variables and constraints do not exist
yet. `piecewise:` is the one that does — a curve
[expands](piecewise.md) into weights, a convexity row and one link row per
tuple, and those declarations are the model as much as the ones that were
typed.

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

`to_program` takes whatever you have — a path, the YAML, a mapping, a `Spec`,
or a `Program` already — and is idempotent, so a consumer that does not know
which it holds can call it and be sure.

## Which one to take

| you are                                                                | take      | because                                       |
| ---------------------------------------------------------------------- | --------- | --------------------------------------------- |
| building rows — a solver backend, a second front end                   | `Program` | every declaration is there, resolved          |
| reading the file — `macros:`, `description:`, a link as it was written | `Spec`    | a program keeps a curve's facts, not its text |

**Take a `Program` to build.** A consumer that reads `constraints:` off a
`Spec` still carrying a curve builds a model missing declarations — and a
model missing declarations is a model, so it solves, and the answer is wrong
with nothing to see. `Program` is a different type from `Spec`, so that
mistake is one the signature refuses rather than one the numbers report.

**A program cannot answer what the file wrote.** It has no `macros:`, no
`description:`, and no link expression — those are the `Spec`'s, and
rendering has to be handed what `to_spec` returned. The projection runs one
way on purpose. What it keeps of a `piecewise:` block is `program.piecewise`:
which parameters carry the curve, and what the block assumes of the numbers as
a `checks` tuple — each check carrying the names it is about, so the consumer
holding the numbers runs it, with `check_message` for the sentence to raise.
What the expansion emitted is answered where it is asked instead: a
`ParameterDeclaration.derivation` says how that parameter is filled, and `None`
means the caller binds it.

**Nothing here is built by hand.** The program's nodes are exported to be
dispatched on with `isinstance` and read, which is why what ships beside them
is the walk (`children()`) and not builders. A mask is `Mask`: the language's
own resolved `where` as its `.root` — the node an engine still dispatches on
with `isinstance` — and every question derived from it, the way a dimension
carries `.maps`. `.conjuncts` flattens the `AND` spine and stops at an `OR` or
a `NOT`; `.names_read` gives the declarations the mask names; `.atoms` its
leaves, connectives removed; and `.dims` the dimensions it is read at — read
off the leaves, which resolution stamped with their declarations' dims the way
a lookup leaf carries the dimension it maps out of. So a predicate a consumer
builds from resolved pieces answers exactly as a declaration's own does: wrap
it in `Mask`, or build it there with `~`, `&` and `|`. Construction
folds — a double negation cancels, a literal flips or is absorbed rather than
buried — so a boolean literal stands at a mask's root or nowhere, derived or
carried alike, and a tree with unresolved leaves is refused at the door. A
consumer asks the mask rather than re-deriving any of these from `.root`, so
two cannot come to disagree about what a conjunct, a name or a comparison is.
A `Region`'s `when` arrives in the same carrier, and the node classes a
`.root` is built of live in `math_spec.program` beside every other node a
consumer dispatches on.

## Asking what a program uses

`program.footprint` is which of the language's constructs one program actually
reaches for — a **subset**, never the whole. It is walked once and held, which
is safe because a program cannot change after it is built.

```python
footprint = program.footprint

sorted(footprint.quadratic)  # []
sorted(footprint.variable_types)  # ['continuous']
sorted(footprint.sos_types)  # []
sorted(kind.__name__ for kind in footprint.shapes)  # ['Constant', 'Multiply', 'Parameter', 'Sum', 'Variable']
```

Every field is a set, so `if footprint.sos_types` asks whether sets appear at
all and `2 in footprint.sos_types` asks about one kind. An empty field says
this program does not use that construct — never that the construct does not
exist. A construct admitted later widens a set rather than needing a field no
consumer yet reads.

**It answers what the program uses, never what you can do about it.** What a
sink can ingest is a separate axis — [capability is not the
ceiling](../../about/ceiling.md) — where a capability is neither a flat set nor
one verdict per construct: SOS is solver-bounded, and quadratic is bounded
twice over on a single sink, by convexity and again by what it stands beside.
So there is deliberately no verdict here to read instead of giving one, and
convexity is absent because it depends on coefficient data rather than on
anything a program states.

The footprint stops at the kind. A sink that takes a window but not a wrapped
one reads `Window in footprint.shapes` and then walks: `wrap`, `partition` and
a named width are refinements without end, and each is one line once the set
has said where to look.

## Asking whether an axis can be cut

A driver that solves a horizon in windows — a rolling horizon, a myopic
pathway — needs one thing from the model before it starts: **is every row it
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
declaration ties each one — including the three the `piecewise:` block emitted,
so a coupling introduced by an expansion is named under the name the expansion
gave it rather than under the block a reader wrote.

It is the locality [the ceiling](../../about/ceiling.md) already argues in —
pointwise, bounded halo and global — asked about a dimension rather than about
an operator. Every declared axis has an entry, walked once and held like
[`footprint`](#asking-what-a-program-uses): answering for every axis costs what
answering for one did, since every construct that ties an axis names the axis it
ties.

`behind` and `ahead` are how many coordinates a window must see before its
first row and after its last — `0` where every row is pointwise, `1` behind for
a `shift` of one, `n - 1` behind for a `sum_back` of `n`, `2` ahead for a shift
of `-2`. They are two numbers because a driver supplies them differently: a
lookahead is rows it solves and does not keep, a history is rows it carries
from the window before.

What would break comes in three kinds, so a driver can act on each. `coupled`
names each declaration that ties the axis together — a sum over it in a
constraint, a grouping that consumes it, a wrapped shift, a set — and, after
the dash, the one modelling change that would lift it: a horizon total becomes
a rolling `sum_back`, a wrap becomes an opening-state seed, a grouping is
windowed along the dimension it groups into. No window satisfies a coupling and
no rewrite keeps the model's meaning, so the remedy is named and not applied.
`undecided` names each declaration whose reach only the data can say, to the
parameter or lookup that says it: an offset or width taken from a parameter, a
shift inside the groups a lookup makes, a read through a lookup with `at()`; a
driver holding the data computes the reach from it. `restarts` names each
declaration counting a `position()` along the axis, which a window restarts at
its first row. `windowable` is false while anything is coupled or undecided; a
restart does not count against it.

The same walk answers a second driver. `independent` is whether each
coordinate builds on its own — windowable, reading nothing behind or ahead,
counting no position — which is what a scenario sweep asks before solving one
coordinate per slice, and what licenses solving the slices in any order or at
once. A restart does count against it: with one coordinate per slice a
`position()` holds everywhere, which changes what the mask means.

**A reduction means opposite things by position**, which is the whole of the
care: in a constraint a sum over the axis ties every window to every other, and
in the objective it is additively separable, an objective being a sum already.
What is not decided here is whether the windowed answer is the whole-horizon
one — a store carried over one row windows cleanly and a rolling solve of it is
still a different answer — nor whether the modeller _wanted_ a restart: a
`position(t) == 0` seed fires once over a horizon and once per window, and both
are models somebody means.
