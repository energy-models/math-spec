<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Typeset the math

The three renderers, the options each takes, and how a symbol table changes
the spelling. [Print a model as math](../howto/print.md) is the recipe, and
[every construct, as math](notation.md) shows what each construct prints.

```python
import math_spec as ms

spec = ms.to_spec('model.yaml')  # read and checked once, then printed three ways

print(ms.to_latex(spec))  # amsmath align
print(ms.to_typst(spec))  # compiles without a TeX toolchain
print(ms.to_markdown(spec))  # renders as-is on GitHub
```

Each of the three takes what `to_spec` takes: a path, the YAML, a mapping, or
a `Spec`. A `Spec` is read and checked once rather than once per format.

From a shell:

```bash
python -m math_spec latex model.yaml --symbols model.symbols.yaml --standalone -o model.tex
python -m math_spec typst model.yaml --standalone -o model.typ
python -m math_spec markdown model.yaml
```

## Options

The three functions take the same keywords; the CLI spells each as a flag.

|                      |                        |                                                                                                                           |
| -------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `symbols`            | `--symbols FILE`       | how names should print — [below](#symbol-tables). Default: derived                                                        |
| `standalone`         | `--standalone`         | emit a document that compiles, rather than a fragment to include. Default: fragment                                       |
| `legend`             | `--no-legend`          | the sets / parameters / variables / definitions table above the math. Default: on                                         |
| `numbered`           | `--no-numbers`         | number the equations. Default: on                                                                                         |
| `inline_expressions` | `--inline-expressions` | substitute each named expression the math reads into the equations reading it, rather than defining it once. Default: off |

`-o FILE` writes to a file instead of stdout.

The model's own `description:` opens the document under every setting. A
`piecewise:` block prints as the λ-formulation it expands to, which is the math
the solver receives. Inlining reaches only what the math reads: a `cases:`
block has no single body to substitute, and a
[reported entry](language/reported.md) is read by nothing in the math, so both
keep their definition under either setting. Where the math translates an index
(`shift`, in any of its edge spellings) the document prints a line saying what
the notation means, so a reader meets no undefined symbol.

A model that does not load does not print: typesetting runs the same
load-time checks as everything else.

**It does not line-break.** A wide equation runs off the page.

## One declaration

`typeset_declaration` returns the line the document prints for one named
expression, constraint or variable, quantifier included, with no document,
label, number or math delimiters around it:

<!-- doctest: skip -->

```python
ms.typeset_declaration('model.yaml', 'spend', 'latex')
# \mathit{spend}_{t} = \sum_{g \in \mathcal{G}} p_{t,g} \cdot \mathrm{cost}_{g} \qquad \forall\, t \in \mathcal{T}
ms.typeset_declaration('model.yaml', 'balance', 'latex')
# \sum_{g \in \mathcal{G}} p_{t,g} = \mathrm{load}_{t} \qquad \forall\, t \in \mathcal{T}
```

It takes what the others take, plus the name, the format and an optional
`symbols` table. A line on its own has no _Definitions_ section beside it, so
the plain named expressions it uses are substituted (`inline_expressions=True`)
unless told otherwise. A cased one prints by symbol, and a second call with
its name prints its block. A name the model declares as none of the three is
refused with the near miss. One declared as both a constraint and a variable
is refused too: constraints sit outside the
[flat namespace](language/expressions.md#name-resolution), and one line prints
one of them.

## Symbol tables

With no table, symbols are **derived**, so a model prints with no setup:
$\mathit{load}_t$, $p^{\mathrm{max}}_g$. A `SymbolTable` makes them
conventional:

```python
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

ms.to_latex('dispatch.yaml', symbols=symbols)
```

A dict, a YAML path, or a `ms.SymbolTable`. As a sidecar file:

<!-- doctest: skip -->

```yaml
# dispatch.symbols.yaml — not a model, so nothing here is checked against the schema
notation: latex
dimensions:
  snapshot: { index: s, set: "\\mathcal{S}" }
  generator: { index: g, set: "\\mathcal{G}" }
names:
  cost: c
  load: "\\ell"
  p_max: "\\bar p"
```

| Section      |                                                                            |
| ------------ | -------------------------------------------------------------------------- |
| `notation`   | **required** — `latex` or `typst`, the language the entries are written in |
| `dimensions` | per dimension, an `index` letter and a `set` symbol; either may be omitted |
| `names`      | per parameter, variable or named expression, its symbol                    |

**Every spelling is printed verbatim.** Nothing parses or translates notation,
so `notation:` is required, and rendering a LaTeX table as Typst is refused.

**A key naming nothing in the model is an error**, with the near miss.

**Presentation is not language.** A symbol table changes nothing about what
the file means, and no solver reads it. What a declaration _is_ stays the
model's own `description:` ([declarations](language/declarations.md)), which
travels with the declaration and reaches every consumer.
