---
# SPDX-FileCopyrightText: math-spec contributors
# SPDX-License-Identifier: CC-BY-4.0
hide:
  - navigation
  - toc
---

<div class="hero" markdown>

# math-spec

**The language an optimisation model is written in — and the math it means.**

Write the math in YAML. Everything decidable without data is decided without
data — and the file prints as the math it stands for.

--8<-- "README.md:badges"

[Read the language](reference/language/index.md){ .md-button .md-button--primary }
[See every construct as math](reference/notation.md){ .md-button }

</div>

---

<div class="landing" markdown>

<div class="grid cards" markdown>

- :material-file-document-outline: **Declarative math**

  ***

  One file declares the axes, the data, the decisions and the rules.
  Readable without knowing any implementation, and self-contained: no Python
  state changes what it means. It diffs cleanly in review and travels as a
  research artefact.

- :material-shield-check-outline: **Decided before the data**

  ***

  Every expression, every `where` string and even an _uncalled_ macro
  template is parsed and name-checked at load. A repository of models
  compiles in CI with nothing bound to any of them.

- :material-alert-octagon-outline: **Fail early, fail loud**

  ***

  Nothing is guessed and nothing falls back silently. Where a file does not
  determine the answer, loading fails and the message names the construct
  _and_ its rewrite.

- :material-fence: **A finite language, with a priced way out**

  ***

  The ceiling is a closure — relational ∩ local — not a feature race.
  Genuinely unsayable math goes in an `escape:` island: visible in the file,
  billed before it runs.

- :material-function-variant: **The file is the document**

  ***

  LaTeX, Typst or Markdown, printed from the file alone. No data, no solver,
  no second source of truth — the cheapest review tool there is for _does
  this YAML say what I meant_.

- :material-source-branch: **One rule per question**

  ***

  A rule is language iff two consumers answering it separately would be a
  bug. That test is what decides who owns a question — the language, or the
  engine reading it.

</div>

--8<-- "README.md:flow"

## The whole thing, in one model

--8<-- "README.md:model"

### And that file says, exactly this

Generated from the YAML above — no data, no solver, no second source of truth.
Only the notation is a choice, and **How** shows the one that was made here.

<!-- home-math:begin -->

=== "The math"

    Least-cost dispatch of a generator fleet against an hourly load.

    #### Sets

    | Symbol | Meaning |
    |---|---|
    | $\mathcal{S}$ | index $s$ — `snapshot` — dispatch periods |
    | $\mathcal{G}$ | index $g$ — `generator` — generating units |

    #### Parameters

    | Symbol | Meaning |
    |---|---|
    | $\bar p$ | `p_max` over $\mathcal{G}$ — installed capacity |
    | $\ell$ | `load` over $\mathcal{S}$ — demand to be met |
    | $c$ | `cost` over $\mathcal{G}$ — marginal cost |

    #### Variables

    | Symbol | Meaning |
    |---|---|
    | $p$ | `p` over $\mathcal{S} \times \mathcal{G}$ — output of a generator in a snapshot |

    #### Objective

    $$\min \sum_{s \in \mathcal{S},\enspace g \in \mathcal{G}} p_{s,g} \cdot c_{g}$$

    #### Subject to

    **`power_balance`**

    $$\sum_{g \in \mathcal{G}} p_{s,g} = \ell_{s} \qquad \forall\thinspace s \in \mathcal{S}$$

    #### Variable domains

    **`p`**

    $$0 \le p_{s,g} \le \bar p_{g} \qquad \forall\thinspace s \in \mathcal{S},\enspace g \in \mathcal{G} \thinspace:\thinspace \bar p_{g} > 0$$

=== "LaTeX"

    ```latex
    \noindent Least-cost dispatch of a generator fleet against an hourly load.

    \paragraph{Sets}
    \begin{description}
    \item[$\mathcal{S}$] index $s$ --- \texttt{snapshot} --- dispatch periods
    \item[$\mathcal{G}$] index $g$ --- \texttt{generator} --- generating units
    \end{description}

    \paragraph{Parameters}
    \begin{description}
    \item[$\bar p$] \texttt{p\_max} over $\mathcal{G}$ --- installed capacity
    \item[$\ell$] \texttt{load} over $\mathcal{S}$ --- demand to be met
    \item[$c$] \texttt{cost} over $\mathcal{G}$ --- marginal cost
    \end{description}

    \paragraph{Variables}
    \begin{description}
    \item[$p$] \texttt{p} over $\mathcal{S} \times \mathcal{G}$ --- output of a generator in a snapshot
    \end{description}

    \paragraph{Objective}
    \begin{align*}
     && \min & \sum_{s \in \mathcal{S},\ g \in \mathcal{G}} p_{s,g} \cdot c_{g}
    \end{align*}

    \paragraph{Subject to}
    \begin{align*}
    \text{power\_balance} && \sum_{g \in \mathcal{G}} p_{s,g} & = \ell_{s} && \forall\, s \in \mathcal{S}
    \end{align*}

    \paragraph{Variable domains}
    \begin{align*}
    \text{p} && 0 \le p_{s,g} & \le \bar p_{g} && \forall\, s \in \mathcal{S},\ g \in \mathcal{G} \,:\, \bar p_{g} > 0
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
            'p_max': '\\bar p',
        },
    }

    ms.to_latex('dispatch.yaml', symbols=symbols)  # amsmath align
    ms.to_typst('dispatch.yaml')  # compiles without a TeX toolchain
    ms.to_markdown('dispatch.yaml')  # renders as-is on GitHub
    ```

    `symbols` is optional — drop it and the same model prints as
    $\mathit{load}_t$, $p^{\mathrm{max}}_g$. A dict, a YAML path or a
    `SymbolTable`; a key naming nothing in the model is an error, not a symbol that
    silently never applies. Every spelling is printed verbatim — `notation` says
    which language they are, and a render in the other one refuses.

    Or from a shell, where the table is that same YAML on disk and `--standalone`
    emits a document that compiles rather than a fragment to `\input`:

    ```bash
    python -m math_spec latex dispatch.yaml --symbols dispatch.symbols.yaml
    python -m math_spec typst dispatch.yaml --standalone -o dispatch.typ
    ```

    The renderer is [the typesetter](reference/typeset.md), and it reads the same
    file every other page here loads.

<!-- home-math:end -->

### And a consumer reads it like this

--8<-- "README.md:load"

That seam is [one page](reference/language/reading.md), and it is the whole of
it: what a program gets when it loads a model, and nothing a program does
changes what the file means.

## Where to next

<div class="grid cards" markdown>

- :material-book-open-page-variant: **The language**

  ***

  What a YAML file may contain, and what it means — ten rules, ten
  declaration keys, one closed set of operators.

  [:octicons-arrow-right-24: The language](reference/language/index.md)

- :material-sigma: **Every construct, as math**

  ***

  All of it at once, beside the notation the typesetter gives it — so the
  notation can be read as the one system it has to be.

  [:octicons-arrow-right-24: The notation](reference/notation.md)

- :material-format-text: **Typeset the math**

  ***

  LaTeX, Typst and Markdown, the options each takes, and how a symbol table
  turns derived symbols into conventional ones.

  [:octicons-arrow-right-24: Typeset](reference/typeset.md)

- :material-code-braces: **Reading a loaded model**

  ***

  The contract between the language and anything that reads the AST — a
  solver backend, a renderer, a second front end.

  [:octicons-arrow-right-24: The seam](reference/language/reading.md) ·
  [Python API](reference/math_spec/validation.md)

- :material-fence: **What may enter the language**

  ***

  The test a candidate primitive has to pass, why capability is a second
  axis, and what has been refused and why.

  [:octicons-arrow-right-24: The ceiling](about/ceiling.md)

- :material-scale-balance: **Who owns a rule**

  ***

  A rule is language iff two consumers answering it separately would be a
  bug — and the sharp edge that keeps that from swallowing everything.

  [:octicons-arrow-right-24: What counts as language](about/what-counts-as-language.md)

</div>

## Install it

--8<-- "README.md:docs-install-dev"

Or as a dependency, once the project leaves the alpha stream — see
[installation](installation.md) for every package manager.

!!! warning "Alpha, pre-1.0"

    --8<-- "README.md:status"

</div>
