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

math-spec reads that file, checks everything that can be checked without data,
and hands the result on: to an engine that builds and solves the model, or to the
typesetter that prints it as LaTeX, Typst or Markdown. It builds nothing and
solves nothing itself. Every tool reads the file through the same checked syntax
tree, so an engine and a renderer cannot disagree about what the file means
([what counts as language](docs/about/what-counts-as-language.md)).

- **Nothing is guessed.** A misspelled name, a `where` string on an undeclared
  parameter, a constraint whose dimensions do not match its `dims`: each fails
  when the file loads, with a message that names the fix. A repository of models
  checks in CI with no data ([errors](docs/reference/language/errors.md)).
- **The operators are a fixed set.** `sum`, `sum_back`, `at` and `shift`. A file
  cannot add one, so a model never depends on what one engine registered. A
  composition of them goes in `macros:` ([the limits](docs/about/limits.md)).
- **The file is the document.** `to_latex(spec)` prints the model as equations
  from the file alone, so the math you publish is the math you solve
  ([typeset](docs/reference/typeset.md)). The file diffs in review, and no
  Python state changes what it means.

<!--- --8<-- [start:flow] -->

```mermaid
flowchart LR
    Y["model.yaml"] --> S["schema<br/>closed at every level"]
    S --> AST["syntax tree<br/>two grammars"]
    AST --> Q{"inside the<br/>language?"}
    Q -->|"no"| ERR["load error<br/>naming the construct + rewrite"]
    Q -->|"yes"| M["Spec<br/>what the file says"]
    M -->|".program"| P["Program<br/>names, dimensions and operators resolved"]
    P --> ENG["an engine that builds → solver"]
    M --> T["to_latex / to_typst / to_markdown"]

    classDef spec fill:#f0f7f0,stroke:#3a7d44,stroke-width:2px,color:#111
    classDef consumer fill:#eef1fb,stroke:#4a5fc1,stroke-width:2px,color:#111
    classDef err fill:#fdf3e7,stroke:#b7791f,color:#111
    class S,AST,M,P spec
    class ENG,T consumer
    class ERR err
```

<!--- --8<-- [end:flow] -->

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

<details>
<summary>The same document as LaTeX</summary>

```latex
\noindent Least-cost dispatch of a generator fleet against an hourly load.

\paragraph{Sets}
\begin{description}
\item[{$\mathcal{S}$}] index $s$ --- \texttt{snapshot} --- dispatch periods
\item[{$\mathcal{G}$}] index $g$ --- \texttt{generator} --- generating units
\end{description}

\paragraph{Parameters}
\begin{description}
\item[{$\bar p$}] \texttt{capacity} over $\mathcal{G}$ --- installed capacity
\item[{$\ell$}] \texttt{load} over $\mathcal{S}$ --- demand to be met
\item[{$c$}] \texttt{cost} over $\mathcal{G}$ --- marginal cost
\end{description}

\paragraph{Variables}
\begin{description}
\item[{$\mathit{dispatch}$}] \texttt{dispatch} over $\mathcal{S} \times \mathcal{G}$ --- output of a generator in a snapshot
\end{description}

\paragraph{Objective}
\begin{align*}
 && \min & \sum_{s \in \mathcal{S},\ g \in \mathcal{G}} \mathit{dispatch}_{s,g} \cdot c_{g}
\end{align*}

\paragraph{Subject to}
\begin{align*}
\text{power\_balance} && \sum_{g \in \mathcal{G}} \mathit{dispatch}_{s,g} & = \ell_{s} && \forall\, s \in \mathcal{S}
\end{align*}

\paragraph{Variable domains}
\begin{align*}
\text{dispatch} && 0 \le \mathit{dispatch}_{s,g} & \le \bar p_{g} && \forall\, s \in \mathcal{S},\ g \in \mathcal{G} \,:\, \bar p_{g} > 0
\end{align*}
```

</details>

<details>
<summary>The same document as Typst, printed with no symbol table</summary>

```typst
Least-cost dispatch of a generator fleet against an hourly load.

== Sets
/ $cal(T)$: index $t$ --- `snapshot` --- dispatch periods
/ $cal(G)$: index $g$ --- `generator` --- generating units

== Parameters
/ $upright("capacity")$: `capacity` over $cal(G)$ --- installed capacity
/ $upright("load")$: `load` over $cal(T)$ --- demand to be met
/ $upright("cost")$: `cost` over $cal(G)$ --- marginal cost

== Variables
/ $italic("dispatch")$: `dispatch` over $cal(T) times cal(G)$ --- output of a generator in a snapshot

Upright is what the model is given --- a parameter such as $upright("capacity")$, a coordinate map, a label --- and italic is what the solver chooses, such as $italic("dispatch")$. An index is italic too, being what a quantifier chooses, and a set is script.

== Objective
$  & min & sum_(t in cal(T), g in cal(G)) italic("dispatch")_(t,g) dot upright("cost")_(g) $

== Subject to
$ upright("power_balance") & sum_(g in cal(G)) italic("dispatch")_(t,g) & = upright("load")_(t) & forall t in cal(T) $

== Variable domains
$ upright("dispatch") & 0 <= italic("dispatch")_(t,g) & <= upright("capacity")_(g) & forall t in cal(T), g in cal(G) colon upright("capacity")_(g) > 0 $
```

</details>

<!-- readme-math:end -->
<!-- prettier-ignore-end -->

Each format is one call:

```python
import math_spec as ms

spec = ms.to_spec('dispatch.yaml')

ms.to_markdown(spec)  # renders as-is on GitHub, as above
ms.to_latex(spec)  # amsmath align
ms.to_typst(spec)  # compiles without a TeX toolchain
```

A [symbol table](docs/reference/typeset.md#symbol-tables) gives the names their
conventional spelling, as in the first folded block.
[Print a model as math](docs/howto/print.md) does the same from a shell.
`to_spec` returns a `Spec`, and `spec.program` the model it builds
([reading a loaded model](docs/reference/reading.md#spec-and-program)).

## Documentation

The documentation is at <https://math-spec.readthedocs.io>.

## Installation

Nothing is published yet.
[Installation](docs/howto/installation.md) gives the command that installs from
git, and [contributing](docs/contributing.md#setting-up-a-development-environment)
sets up a development clone.

## Prior art

Every file under `src/` was written in [specsolve](https://github.com/fluxopt/specsolve)
and extracted here. The keys themselves,
which are YAML math, a block per component, `dims:` and a `where:` string,
come from [Calliope](https://github.com/calliope-project/calliope).
[linopy](https://github.com/PyPSA/linopy) supplies the vocabulary that
`sum(over=)` and the dimension rules are named against. Issue numbers in these
pages point at specsolve, where the arguments happened.

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

The code is [MIT](LICENSE): everything under `src/`, `tests/`, `tools/`, the
examples, and the generated schema.

The prose is [CC-BY-4.0](LICENSES/CC-BY-4.0.txt): everything under `docs/`, this
README, `CHANGELOG.md`, and the logos in `resources/`. Reuse it freely, with
attribution.
