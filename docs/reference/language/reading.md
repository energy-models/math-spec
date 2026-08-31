<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Reading a loaded model

Every other page here says what a _file_ may declare. This page says what a
program gets when it loads one. It is the contract between the language and
any **consumer**: code that reads a model after it loads, rather than writing
one. A solver backend, a renderer and a second front end are all consumers.

Nothing on this page is needed to write a model. It names the two objects a
consumer works through, and that is the whole seam:

```text
to_spec  →  Spec  →  to_program  →  Program
```

## Spec and Program

**A `Spec` is what the file says. A `Program` is what it means.** Getting from
one to the other expands macros, turns curves into the declarations they stand
for, types every name, resolves operators to nodes, and checks every dim and
degree rule.

**A consumer that builds rows reads the `Program`. One that asks what the file
wrote reads the `Spec`.**

A file may declare a construct whose variables and constraints do not exist
yet. `piecewise:` is that construct. A curve [expands](piecewise.md) into
weights, a convexity row and one link row per tuple, and those declarations
are as much the model as the ones the file typed.

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

**`to_program` takes whatever you have**: a path, the YAML, a mapping, a
`Spec`, or a `Program` already. It is idempotent, so a consumer that does not
know which one it holds can call it and be sure what comes back.

## Choosing Spec or Program

| you are                                                                | take      | because                                       |
| ---------------------------------------------------------------------- | --------- | --------------------------------------------- |
| building rows — a solver backend, a second front end                   | `Program` | every declaration is there, resolved          |
| reading the file — `macros:`, `description:`, a link as it was written | `Spec`    | a program keeps a curve's facts, not its text |

**Take a `Program` to build.** A consumer that reads `constraints:` off a
`Spec` still carrying a curve builds a model with declarations missing. That
model is still a model, so it solves, and the answer is wrong with nothing to
see. `Program` is a different type from `Spec`, so the signature refuses the
mistake instead of the numbers reporting it.

**A program cannot answer what the file wrote.** It has no `macros:`, no
`description:` and no link expression. Those live only on the `Spec`. So a
caller hands rendering what `to_spec` returned, never what `to_program`
returned. The projection runs one way.

**Nothing here is built by hand.** The program's nodes exist to be dispatched
on with `isinstance` and read, so what ships beside them is a walk
(`children()`), not builders. A mask is the language's own resolved `where`
node. There is no second set of predicates, so the two cannot come to disagree
about what a comparison means.

## What a curve leaves behind

A `piecewise:` block leaves `program.piecewise`, which keeps two things:

- **which parameters carry the curve**
- **what the block assumes of the numbers**, as a `checks` tuple. Each check
  names the values it is about, so the consumer holding the data runs it.
  `check_message` gives the sentence to raise when it fails.

**What the expansion built is answered where it is asked.** A parameter the
expansion emitted carries its own `ParameterDeclaration.derivation`, which
says how that parameter is filled. `None` there means the caller binds the
parameter itself.

## Program footprint

`program.footprint` names which of the language's constructs this program
uses. It is a **subset**, never the whole. It is walked once and held, which
is safe because a program cannot change after it is built.

```python
footprint = program.footprint

sorted(footprint.quadratic)  # []
sorted(footprint.variable_types)  # ['continuous']
sorted(footprint.sos_types)  # []
sorted(kind.__name__ for kind in footprint.shapes)  # ['Constant', 'Multiply', 'Parameter', 'Sum', 'Variable']
```

**Every field is a set.** `if footprint.sos_types` asks whether sets appear at
all, and `2 in footprint.sos_types` asks about one kind. An empty field says
this program does not use that construct, never that the construct does not
exist. A construct admitted later widens a set, rather than needing a field no
consumer yet reads.

**The footprint says what the program uses, never what you can do about it.**
What a consumer can ingest is a separate axis, and the ceiling page holds it:
[solver capability](../../about/ceiling.md#solver-capability). A capability
there is neither a flat set nor one verdict per construct. SOS is bounded by
the solver, and quadratic terms are bounded twice over on a single solver, by
convexity and again by what stands beside them. So the footprint gives no
verdict at all, on purpose. Convexity is absent for the same reason: it
depends on the coefficient data, not on anything a program states.

**The footprint stops at the kind.** A consumer that takes a window but not a
wrapped one reads `Window in footprint.shapes`, then walks from there. `wrap`,
`partition` and a named width are refinements without end, and each is one
line once the set has said where to look.
