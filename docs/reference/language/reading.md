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

| you are                                                                      | take      | because                                       |
| ---------------------------------------------------------------------------- | --------- | --------------------------------------------- |
| building rows — a solver backend, a second front end                         | `Program` | every declaration is there, resolved          |
| reading the file — `points:`, `method:`, what a curve's mask is derived from | `Spec`    | a program has no `piecewise:` left to look at |

**Take a `Program` to build.** A consumer that reads `constraints:` off a
`Spec` still carrying a curve builds a model missing declarations — and a
model missing declarations is a model, so it solves, and the answer is wrong
with nothing to see. `Program` is a different type from `Spec`, so that
mistake is one the signature refuses rather than one the numbers report.

**A program cannot answer what the file wrote.** It has no `piecewise:`, no
`macros:`, no `description:` — those are the `Spec`'s, and anything asking
what curves a file declares, or rendering it, has to be handed what
`to_spec` returned. The projection runs one way on purpose.

**Nothing here is built by hand.** The program's nodes are exported to be
dispatched on with `isinstance` and read, which is why what ships beside them
is the walk (`children()`) and not builders. A mask is the language's own
resolved `where` node rather than a second set spelling the same predicates —
one home, so the two cannot come to disagree about what a comparison is.
