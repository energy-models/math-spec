<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Typeset the math

A model is a declaration, so it can be printed the way a paper prints it — from
the file itself, with no data and no solver. It is the cheapest review tool
available for _"does this YAML say what I meant"_, and it is how a model
states its math with nothing but the file.

Every construct the language has, beside the math it prints, is one page:
[Every construct, as math](notation.md) — which is where to look when the
question is whether the notation is right, rather than how to print it.

```python
import math_spec as ms

spec = ms.to_spec('model.yaml')  # read and checked once, then printed three ways

print(ms.to_latex(spec))  # amsmath align
print(ms.to_typst(spec))  # compiles without a TeX toolchain
print(ms.to_markdown(spec))  # renders as-is on GitHub
```

Each of the three takes what `to_spec` takes — a path, the YAML, a mapping —
and reads it. Hand it the `Spec` instead and the file is read and checked once
rather than once per format, which is also how a `Spec` you already hold gets
printed without a second trip through the loader.

Or from a shell, where this belongs in a Makefile next to `pdflatex`:

```bash
python -m math_spec latex model.yaml --symbols model.symbols.yaml --standalone -o model.tex
python -m math_spec typst model.yaml --standalone -o model.typ
python -m math_spec markdown model.yaml
```

## Options

The three functions take the same keywords; the CLI spells each as a flag.

|              |                  |                                                                                               |
| ------------ | ---------------- | --------------------------------------------------------------------------------------------- |
| `symbols`    | `--symbols FILE` | how names should print — [below](#symbol-tables). Default: derived                            |
| `standalone` | `--standalone`   | emit a document that compiles, rather than a fragment to include. Default: fragment           |
| `legend`     | `--no-legend`    | the sets / parameters / variables / expressions table above the math. Default: on             |
| `numbered`   | `--no-numbers`   | number the equations. Default: on                                                             |
| `inline`     | `--inline`       | substitute each named expression where it is used, rather than defining it once. Default: off |

`-o FILE` writes to a file instead of stdout.

The model's own `description:` opens the document either way — it is what the
file says it is, not a symbol table. A `piecewise:` block prints as the
λ-formulation it _expands to_ rather than the sugar it was written as, because
that is the math the solver receives. Where the math translates an index —
`shift`, in any of its edge spellings — the document also prints a line saying
what the notation for it means, so a reader meets no symbol the page has not
defined.

A model that does not compile does not print: typesetting runs the same
load-time checks everything else does.

**It does not line-break.** A wide equation runs off the page; that is a
formatting decision this package does not make for you.

## One equation

The whole-model functions print objective, constraints, definitions and
domains. To pull one equation out on its own — for a docstring, a table cell, a
comment beside the value it computes — `typeset_equation` returns the line the
document prints for a named expression, a constraint or a variable, quantifier
included, with no document, label, number or math delimiters around it:

<!-- doctest: skip -->

```python
ms.typeset_equation('model.yaml', 'spend', 'latex')
# \mathit{spend}_{t} = \sum_{g \in \mathcal{G}} p_{t,g} \cdot \mathrm{cost}_{g} \qquad \forall\, t \in \mathcal{T}
ms.typeset_equation('model.yaml', 'balance', 'latex')
# \sum_{g \in \mathcal{G}} p_{t,g} = \mathrm{load}_{t} \qquad \forall\, t \in \mathcal{T}
```

It takes what the others take — a path, the YAML, a mapping, a `Spec` — plus
the name, the format and an optional `symbols` table. A name the model declares
as none of the three is refused with the near miss; one it declares as both a
constraint and a variable is refused too, since constraints sit outside the
[flat namespace](language/expressions.md#name-resolution) and one line prints
one of them.

## Symbol tables

With no table, symbols are **derived** — unambiguous rather than beautiful, so
a model prints with no setup at all: $\mathit{load}_t$, $p^{\mathrm{max}}_g$. A
`SymbolTable` makes it conventional:

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
which is why `notation:` is required and why rendering a LaTeX table as Typst
refuses rather than producing something that nearly works.

**A key naming nothing in the model is an error**, with the near miss — not a
symbol that silently never applies and a reader who never finds out.

**Presentation is not language.** Nothing in a symbol table changes what the
file means, no solver reads it, and what a declaration _is_ stays the model's
own `description:` ([declarations](language/declarations.md)), which travels
with the declaration and reaches every consumer.
