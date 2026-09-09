---
# SPDX-FileCopyrightText: math-spec contributors
# SPDX-License-Identifier: CC-BY-4.0
hide:
  - navigation
  - toc
---

<div class="hero" markdown>

# math-spec

**The language an optimisation model is written in, and the math it means.**

Write the math in YAML. Everything decidable without data is decided at load,
and the file prints as the math it stands for.

--8<-- "README.md:badges"

[Read the language](reference/language/index.md){ .md-button .md-button--primary }
[See every construct as math](reference/notation.md){ .md-button }

</div>

---

<div class="landing" markdown>

<div class="grid cards" markdown>

<!-- A card is a list item whose body is indented four spaces: python-markdown
     needs that much to read it as the item's content, and prettier would
     realign it to two, which splits every card into a stray rule and a
     paragraph outside the list. -->
<!-- prettier-ignore -->
- :material-file-document-outline: **Declarative math**

    ***

    One file declares the axes, the data, the decisions and the rules. You can
    read it without knowing what builds it, and no Python state changes what it
    means. It diffs in review, and it travels as a research artefact.

- :material-shield-check-outline: **Decided before the data**

    ***

    Every expression, every `where` string and every macro template, called or
    not, is parsed and name-checked at load. A repository of models compiles in
    CI with no data bound to any of them.

- :material-alert-octagon-outline: **Fail early, fail loud**

    ***

    Nothing is guessed and nothing falls back silently. Where a file does not
    decide the answer, loading fails, and the message names the construct and
    its rewrite.

- :material-fence: **A closed language**

    ***

    The operators are a fixed set, and nothing can register another one. A
    composition of them is a macro. Math the language cannot express is refused,
    with the rewrite named.

- :material-function-variant: **The file is the document**

    ***

    LaTeX, Typst or Markdown, printed from the file alone. No data, no solver,
    and no second source of truth. It answers _does this YAML say what I meant_
    before anything is bound or solved.

- :material-source-branch: **One answer per question**

    ***

    An engine, a renderer and a checker read the same file. Wherever they could
    disagree about what it means, the language decides once, and all three read
    the answer. What each solver can take, each engine decides for itself.

</div>

--8<-- "README.md:flow"

## The whole thing, in one model

--8<-- "README.md:model"

### What that file says

Generated from the YAML above, with no data and no solver. Only the notation is a
choice, and **How** shows the one made here.

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
    \item[{$\mathcal{S}$}] index $s$ --- \texttt{snapshot} --- dispatch periods
    \item[{$\mathcal{G}$}] index $g$ --- \texttt{generator} --- generating units
    \end{description}

    \paragraph{Parameters}
    \begin{description}
    \item[{$\bar p$}] \texttt{p\_max} over $\mathcal{G}$ --- installed capacity
    \item[{$\ell$}] \texttt{load} over $\mathcal{S}$ --- demand to be met
    \item[{$c$}] \texttt{cost} over $\mathcal{G}$ --- marginal cost
    \end{description}

    \paragraph{Variables}
    \begin{description}
    \item[{$p$}] \texttt{p} over $\mathcal{S} \times \mathcal{G}$ --- output of a generator in a snapshot
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

    spec = ms.to_spec('dispatch.yaml')  # read and checked once, then printed three ways

    ms.to_latex(spec, symbols=symbols)  # amsmath align
    ms.to_typst(spec)  # compiles without a TeX toolchain
    ms.to_markdown(spec)  # renders as-is on GitHub
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

### How a tool reads it

--8<-- "README.md:load"

[Reading a loaded model](reference/language/reading.md) says what an engine, a
renderer or a checker gets when it loads a model.

## Where to next

<div class="grid cards" markdown>

<!-- prettier-ignore -->
- :material-book-open-page-variant: **The language**

    ***

    What a YAML file may contain, and what it means: ten rules, ten declaration
    keys, one closed set of operators.

    [:octicons-arrow-right-24: The language](reference/language/index.md)

- :material-sigma: **Every construct, as math**

    ***

    All of it at once, beside the notation the typesetter gives it, so the
    notation can be read as one system.

    [:octicons-arrow-right-24: The notation](reference/notation.md)

- :material-format-text: **Typeset the math**

    ***

    LaTeX, Typst and Markdown, the options each takes, and how a symbol table
    turns derived symbols into conventional ones.

    [:octicons-arrow-right-24: Typeset](reference/typeset.md)

- :material-code-braces: **Reading a loaded model**

    ***

    What an engine, a renderer or a checker gets when it loads a model, and
    which of the two objects each should read.

    [:octicons-arrow-right-24: Reading a loaded model](reference/language/reading.md) ·
    [Python API](reference/math_spec/validation.md)

- :material-fence: **What may enter the language**

    ***

    The test a new operator has to pass, why a solver's own limits stay out of
    the language, and what has been refused and why.

    [:octicons-arrow-right-24: The limits](about/limits.md)

- :material-scale-balance: **Who decides what**

    ***

    Which decisions the language makes for every tool that reads a file,
    and which each engine makes for itself.

    [:octicons-arrow-right-24: What counts as language](about/what-counts-as-language.md)

</div>

## Install it

--8<-- "README.md:docs-install-dev"

Or as a dependency, once the project leaves the alpha stream. See
[installation](installation.md) for every package manager.

!!! warning "Alpha, pre-1.0"

    --8<-- "README.md:status"

</div>
