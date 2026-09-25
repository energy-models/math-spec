<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# math-spec

<!--- --8<-- [start:badges] -->

[![CI](https://img.shields.io/github/actions/workflow/status/energy-models/math-spec/ci.yml?style=flat-square&branch=main)](https://github.com/energy-models/math-spec/actions/workflows/ci.yml)
[![conda-forge](https://img.shields.io/conda/vn/conda-forge/math-spec?logoColor=white&logo=conda-forge&style=flat-square)](https://prefix.dev/channels/conda-forge/packages/math-spec)
[![pypi-version](https://img.shields.io/pypi/v/math-spec.svg?logo=pypi&logoColor=white&style=flat-square)](https://pypi.org/project/math-spec)
[![python-version](https://img.shields.io/pypi/pyversions/math-spec?logoColor=white&logo=python&style=flat-square)](https://pypi.org/project/math-spec)
[![Documentation build status](https://readthedocs.org/projects/math-spec/badge/?version=latest&style=flat-square)](https://math-spec.readthedocs.io)

<!--- --8<-- [end:badges] -->

**Write an optimisation model as a YAML file. Check it and print it as math,
with no data and no solver.**

A math-spec file declares four things: the axes the model runs over, such as
`snapshot` and `generator`; the data it expects, such as `load` and `cost`; the
decisions the solver makes, such as `dispatch`; and the rules those decisions
obey, such as `sum(dispatch, over=generator) == load`. The file
[below](#example) is a complete model.

<!--- --8<-- [start:engines] -->

math-spec builds nothing and solves nothing itself.
[specsolve](https://github.com/fluxopt/specsolve) and
[linopy](https://github.com/PyPSA/linopy) build and solve a math-spec model.
Support in both is work in progress.

<!--- --8<-- [end:engines] -->

<!--- --8<-- [start:benefits] -->

- **Check models in CI, with no data.** A wrong name or
  dimension fails when the file loads, and the error names the fix.
  [Errors →](https://math-spec.readthedocs.io/en/latest/reference/language/errors/)
- **Publish the math you solve.** The equations in the paper
  print from the file the solver reads.
  [Typeset →](https://math-spec.readthedocs.io/en/latest/reference/typeset/)
- **Switch engines, keep the model.** The operators
  are a fixed set, so every engine reads the file the same way.
  [Limits →](https://math-spec.readthedocs.io/en/latest/about/limits/)
- **Write full-size models.** PyPSA's `n.optimize()` model is
  one file, with stochastic, multi-period and quadratic variants.
  [PyPSA in one file →](https://math-spec.readthedocs.io/en/latest/examples/pypsa/)

<!--- --8<-- [end:benefits] -->

## Example

<!--- --8<-- [start:model] -->

```yaml title="dispatch.yaml"
description: Least-cost dispatch of a generator fleet against an hourly load.

dimensions:
  snapshot: { dtype: int, description: dispatch periods }
  generator: { description: generating units }

parameters:
  capacity: { dims: [generator], description: installed capacity }
  load: { dims: [snapshot], description: demand to be met }
  cost: { dims: [generator], description: marginal cost }

variables:
  dispatch:
    description: output of a generator in a snapshot
    dims: [snapshot, generator]
    where: "capacity > 0"
    bounds: { lower: 0, upper: capacity }

constraints:
  power_balance:
    dims: [snapshot]
    expression: sum(dispatch, over=generator) == load

objective:
  sense: minimize
  expression: sum(dispatch * cost)
```

<!--- --8<-- [end:model] -->

### The math it prints

The typesetter prints the file above as math, with no data and no solver.
Markdown is one of three formats, and GitHub renders it here.

<!-- Prettier pads the legend tables that the generator emits unpadded, so the
     two would rewrite each other forever. The range keeps this file formatted
     and the block below byte-for-byte what the typesetter printed. -->
<!-- prettier-ignore-start -->
<!-- readme-math:begin -->

Least-cost dispatch of a generator fleet against an hourly load.

#### Objective

```math
\min \sum_{t \in \mathcal{T},\ g \in \mathcal{G}} \mathit{dispatch}_{t,g} \cdot \mathrm{cost}_{g}
```

#### Subject to

**`power_balance`**

```math
\sum_{g \in \mathcal{G}} \mathit{dispatch}_{t,g} = \mathrm{load}_{t} \qquad \forall\, t \in \mathcal{T}
```

#### Variable domains

**`dispatch`**

```math
0 \le \mathit{dispatch}_{t,g} \le \mathrm{capacity}_{g} \qquad \forall\, t \in \mathcal{T},\ g \in \mathcal{G} \,:\, \mathrm{capacity}_{g} > 0
```

<details>
<summary>The whole document: a symbol table, and the legend it prints</summary>

Least-cost dispatch of a generator fleet against an hourly load.

#### Sets

| Symbol | Meaning |
|---|---|
| $`\mathcal{S}`$ | index $`s`$ — `snapshot` — dispatch periods |
| $`\mathcal{G}`$ | index $`g`$ — `generator` — generating units |

#### Parameters

| Symbol | Meaning |
|---|---|
| $`\bar p`$ | `capacity` over $`\mathcal{G}`$ — installed capacity |
| $`\ell`$ | `load` over $`\mathcal{S}`$ — demand to be met |
| $`c`$ | `cost` over $`\mathcal{G}`$ — marginal cost |

#### Variables

| Symbol | Meaning |
|---|---|
| $`\mathit{dispatch}`$ | `dispatch` over $`\mathcal{S} \times \mathcal{G}`$ — output of a generator in a snapshot |

#### Objective

$`\min \sum_{s \in \mathcal{S},\ g \in \mathcal{G}} \mathit{dispatch}_{s,g} \cdot c_{g}`$

#### Subject to

**`power_balance`**

$`\sum_{g \in \mathcal{G}} \mathit{dispatch}_{s,g} = \ell_{s} \qquad \forall\, s \in \mathcal{S}`$

#### Variable domains

**`dispatch`**

$`0 \le \mathit{dispatch}_{s,g} \le \bar p_{g} \qquad \forall\, s \in \mathcal{S},\ g \in \mathcal{G} \,:\, \bar p_{g} > 0`$

</details>

<!-- readme-math:end -->
<!-- prettier-ignore-end -->

Each format is one call:

```python
import math_spec as ms

spec = ms.to_spec('dispatch.yaml')

ms.to_markdown(spec)
ms.to_latex(spec)
ms.to_typst(spec)
```

A [symbol table](docs/reference/typeset.md#symbol-tables) gives the names their
conventional spelling, as in the folded block.
[Print a model as math](docs/howto/print.md) does the same from a shell.

## Documentation

The documentation is at <https://math-spec.readthedocs.io>.

## Installation

See [installation](docs/howto/installation.md). To work on math-spec, see
[contributing](docs/contributing.md#setting-up-a-development-environment).

## Prior art

Every file under `src/` was written in [specsolve](https://github.com/fluxopt/specsolve)
and extracted here. The keys themselves,
which are YAML math, a block per component, `dims:` and a `where:` string,
come from [Calliope](https://github.com/calliope-project/calliope).
[linopy](https://github.com/PyPSA/linopy) supplies the vocabulary that
`sum(over=)` and the dimension rules are named against.

## Status

Alpha, pre-1.0.

<!--- --8<-- [start:status] -->

**Breaking changes land without a deprecation cycle.** Pin an exact version if
you depend on this, and read the
[changelog](https://github.com/energy-models/math-spec/blob/main/CHANGELOG.md)
before upgrading. Every construct round-trips through the schema, the parsers
and all three typeset formats, and the LaTeX is compiled. The accepted YAML is
not yet frozen.

<!--- --8<-- [end:status] -->

## Licence

The code is [MIT](LICENSE), and the prose is
[CC-BY-4.0](LICENSES/CC-BY-4.0.txt).
