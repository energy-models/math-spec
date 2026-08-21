# Reading a loaded model

Every other page here says what a *file* may declare. This one says what a
*program* gets when it loads one: the contract between the language and
anything that reads the AST — a solver backend, a renderer, a second front end.

None of it is needed to write a model. [The Python API](../api.md) is what a
modeller calls; these are the names a **consumer** reads a model through, and
they are the whole of the seam:

```text
load_model  →  Model  →  expand_piecewise  →  Buildable
```

## Two models, and the difference between them

A file may declare a construct whose variables and constraints do not exist
yet. `piecewise:` is the one that does — a curve
[expands](piecewise.md) into weights, a convexity row and one link row per
tuple, and those declarations are the model as much as the ones that were
typed.

```yaml title="curve.yaml"
dimensions:
  generator: {dtype: str}
  bp: {dtype: int}
parameters:
  bp_x: {dims: [generator, bp]}
  bp_y: {dims: [generator, bp]}
variables:
  p:
    foreach: [generator]
    bounds: {lower: 0}
  cost:
    foreach: [generator]
    bounds: {lower: 0}
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
from lpspec.language import expand_piecewise, load_model

model = load_model('curve.yaml')
sorted(model.constraints)  # ['target']

buildable = expand_piecewise(model)
sorted(buildable.constraints)  # ['curve_convexity', 'curve_link0', 'curve_link1', 'target']
sorted(buildable.variables)  # ['cost', 'curve_lam', 'p']
```

**A `Model` is the file as written.** It still carries `piecewise:`, and its
`constraints:` are the ones somebody typed.

**A `Buildable` is what rows are built from.** `variables:` and `constraints:`
hold the whole model, so the rows built from one are the rows the file asked
for. `piecewise:` is empty, every block having become declarations.

`expand_piecewise` is idempotent and costs nothing to ask twice: the expansion
is built once, while the model validates, and every later call hands back that
same object — including when it is handed a `Buildable`, which is its own
expansion.

## Which one to take

| you are | take | because |
|---|---|---|
| building rows — a lowering pass, a solver backend, a renderer | `Buildable` | the declarations are all there |
| reading the file — `points:`, `method:`, what a curve's mask is derived from | `Model` | the expansion has cleared `piecewise:` |

**Take a `Buildable` to build.** A consumer that reads `constraints:` off a
`Model` still carrying a curve builds a model missing declarations — and a
model missing declarations is a model, so it solves, and the answer is wrong
with nothing to see. Saying `Buildable` in the signature is what makes that a
type error rather than a number.

**Reading the file off an expansion finds no curves, and says nothing.** A
`Buildable` *is* a `Model`, so it is accepted wherever the file is wanted and
the types cannot catch this one. Anything that asks a model what curves it
declares — where they run, which method states them, which parameter a mask is
derived from — has to be handed what `load_model` returned. An expansion
answers "none", which is indistinguishable from a model that has none.

**The promise is about declarations, not expressions.** `macros:` and
`expressions:` are still text inside the declarations a `Buildable` holds, and
are substituted where they are read, not up front. That asymmetry is the reason
the type exists: an expression is needed only when someone reads it, where the
*set of declarations* is needed before anything can be read at all.
