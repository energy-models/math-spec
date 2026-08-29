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
is the walk (`children()`) and not builders. A mask is the language's own
resolved `where` node rather than a second set spelling the same predicates —
one home, so the two cannot come to disagree about what a comparison is.

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
pathway — needs one thing from the model before it starts: **would windowing
change the answer?** Storage carried over a snapshot survives being cut into
windows that overlap by a row. An annual budget does not survive it at all, and
the windows still solve, so nothing else would say so.

```python
from math_spec import separable

separable(program, 'bp').windowable  # False
separable(program, 'generator').coupled["constraint 'target'"]  # 'sums over generator'
```

Neither axis of the model above may be cut, and the report says which
declaration ties each one — including the three the `piecewise:` block emitted,
so a coupling introduced by an expansion is named under the name the expansion
gave it rather than under the block a reader wrote.

It is the locality [the ceiling](../../about/ceiling.md) already argues in —
pointwise, bounded halo, global — asked about a dimension rather than about an
operator. `halo` is how many coordinates two neighbouring windows must share:
`0` where every row is pointwise, `1` for a `shift` of one, `n - 1` for a
`sum_back` of `n`. `coupled` is empty where the model separates, and otherwise
names each declaration and the construct that ties the axis together — a sum
over it, a wrapped shift, an offset only the data knows, or a `position()` a
window would restart.

**A reduction means opposite things by position**, which is the whole of the
care: in a constraint a sum over the axis ties every window to every other, and
in the objective it is additively separable, an objective being a sum already.
What is not decided here is whether the modeller _wanted_ the window — a
`position(t) == 0` seed fires once over a horizon and once per window, and both
are models somebody means.
