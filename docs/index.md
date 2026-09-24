---
# SPDX-FileCopyrightText: math-spec contributors
# SPDX-License-Identifier: CC-BY-4.0
hide:
  - navigation
  - toc
---

<div class="hero" markdown>

# math-spec

**Write an optimisation model as a YAML file. Check it and print it as math,
with no data and no solver.**

--8<-- "README.md:badges"

[Read the language](reference/language/index.md){ .md-button .md-button--primary }
[See the examples](examples/index.md){ .md-button }

</div>

---

<div class="landing" markdown>

## A model is one file

A file declares four things: the axes the model runs over, the data it
expects, the decisions the solver makes, and the rules those decisions obey.
The file below is a complete model.

--8<-- "README.md:model"

Everything that can be checked without data is checked when the file loads. A
misspelled name, a `where:` on an undeclared parameter, or a constraint whose
dimensions do not match its `dims:` is refused with a message that names the
fix.

## The math it prints

Printed from the file above, with no data and no solver. **How** shows the
call.

<!-- home-math:begin -->

=== "The math"

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

    ```math
    \min \sum_{s \in \mathcal{S},\ g \in \mathcal{G}} \mathit{dispatch}_{s,g} \cdot c_{g}
    ```

    #### Subject to

    **`power_balance`**

    ```math
    \sum_{g \in \mathcal{G}} \mathit{dispatch}_{s,g} = \ell_{s} \qquad \forall\, s \in \mathcal{S}
    ```

    #### Variable domains

    **`dispatch`**

    ```math
    0 \le \mathit{dispatch}_{s,g} \le \bar p_{g} \qquad \forall\, s \in \mathcal{S},\ g \in \mathcal{G} \,:\, \bar p_{g} > 0
    ```

=== "LaTeX"

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

=== "How"

    ```python
    import math_spec as ms

    symbols = {
        'notation': 'latex',
        'dimensions': {
            'snapshot': {'index': 's', 'set': '\\mathcal{S}'},
            'generator': {'index': 'g', 'set': '\\mathcal{G}'},
        },
        'names': {
            'cost': 'c',
            'load': '\\ell',
            'capacity': '\\bar p',
        },
    }

    spec = ms.to_spec('dispatch.yaml')  # read and checked once, then printed three ways

    ms.to_latex(spec, symbols=symbols)  # amsmath align
    ms.to_typst(spec)  # compiles without a TeX toolchain
    ms.to_markdown(spec)  # renders as-is on GitHub
    ```

    `symbols` gives every name its conventional spelling. Pass a dict, a YAML path
    or a `SymbolTable`. It is optional: drop it and the same model prints from the
    names in the file, as $\mathrm{load}_t$ and $\mathrm{capacity}_g$.

    Or from a shell, where the table is that same YAML on disk. `--standalone` emits
    a document that compiles, rather than a fragment to `\input`:

    ```bash
    python -m math_spec latex dispatch.yaml --symbols dispatch.symbols.yaml
    python -m math_spec typst dispatch.yaml --standalone -o dispatch.typ
    ```

    [Typeset the math](reference/typeset.md) documents the three functions, their
    options and symbol tables. Each reads the same file every other page here
    loads.

<!-- home-math:end -->

## Where to next

- [Your first model](first-model.md): write the file above one block at a
  time, check it and print it.
- [The language](reference/language/index.md): what a file may contain, and
  what it means.
- [Examples](examples/index.md): whole models, each beside the math it prints.
- [Print a model as math](howto/print.md): LaTeX, Typst or Markdown, from the
  file alone.
- [Check a model without data](howto/check.md): on your machine and in CI.
- [Reading a loaded model](reference/reading.md): for whoever writes an engine
  or a renderer.

## Install it

Nothing is published yet. [Installation](howto/installation.md) gives the
command that installs from git.

!!! warning "Alpha, pre-1.0"

    --8<-- "README.md:status"

</div>
