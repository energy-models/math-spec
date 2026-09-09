<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Typeset the math

`to_latex`, `to_typst` and `to_markdown` print a model as the equations it
stands for, from the file alone. No data binds, and no solver runs. Print a model
to check that the YAML says what you meant, and to publish the math beside the
file that states it.

```python
import math_spec as ms

spec = ms.to_spec('model.yaml')  # read and checked once, then printed three ways

print(ms.to_latex(spec))  # amsmath align
print(ms.to_typst(spec))  # compiles without a TeX toolchain
print(ms.to_markdown(spec))  # renders as-is on GitHub
```

Each function takes what `to_spec` takes: a path, the YAML, a mapping or a
`Spec`. Hand it a `Spec` to read and check the file once rather than once per
format.

The same three formats come from a shell:

```bash
python -m math_spec latex model.yaml --symbols model.symbols.yaml --standalone -o model.tex
python -m math_spec typst model.yaml --standalone -o model.typ
python -m math_spec markdown model.yaml
```

[Every construct, as math](notation.md) shows every construct the language has
beside the math it prints. Look there when the question is whether the notation
is right.

## Options

The three functions take the same keywords, and the command line spells each as
a flag.

|                      |                        |                                                                                                                                 |
| -------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `symbols`            | `--symbols FILE`       | How the names print. See [symbol tables](#symbol-tables). Default: derived from the names in the file                           |
| `standalone`         | `--standalone`         | Emit a document that compiles, rather than a fragment to include. Default: a fragment                                           |
| `legend`             | `--no-legend`          | Print the table of sets, parameters, variables and definitions above the math. Default: on                                      |
| `numbered`           | `--no-numbers`         | Number the equations. Default: on                                                                                               |
| `inline_expressions` | `--inline-expressions` | Substitute each named expression that the math reads into the equations that read it, instead of defining it once. Default: off |

`-o FILE` writes to a file instead of stdout.

- The model's `description:` opens the document, whatever the options say. No
  symbol table touches it.
- A `piecewise:` block prints as the variables and constraints it expands into,
  because the expansion is the math the solver receives.
- Inlining reaches only an expression that the math reads. A `cases:` block has
  no single body to substitute, and a [reported entry](language/reported.md) is
  read by nothing, so both keep their definition line under either setting.
- Wherever the math moves an index, which every `shift` does, the document
  prints a line saying what that notation means.
- A model that does not load does not print. Typesetting runs the same
  load-time checks as everything else.
- Lines are not broken. A wide equation runs off the page.

## Printing one declaration on its own

`typeset_declaration` returns the line the document prints for one named
expression, constraint or variable, with its quantifier and without a document,
a label, a number or math delimiters. Use it for a docstring, a table cell or a
comment beside the value it computes:

<!-- doctest: skip -->

```python
ms.typeset_declaration('model.yaml', 'spend', 'latex')
# \mathit{spend}_{t} = \sum_{g \in \mathcal{G}} p_{t,g} \cdot \mathrm{cost}_{g} \qquad \forall\, t \in \mathcal{T}
ms.typeset_declaration('model.yaml', 'balance', 'latex')
# \sum_{g \in \mathcal{G}} p_{t,g} = \mathrm{load}_{t} \qquad \forall\, t \in \mathcal{T}
```

It takes what the other functions take, plus the name, the format and an
optional `symbols` table.

A line on its own has no _Definitions_ section beside it, so the plain named
expressions it uses are substituted unless you say otherwise. A cased expression
prints by symbol, and a second call with its name prints its block.

A name that is none of the three kinds is refused with the near miss. A name that
is both a constraint and a variable is refused too, because one line can print
only one of them. Constraints sit outside the
[flat namespace](language/expressions.md#name-resolution), so a model may use one
name for both.

## Symbol tables

With no table, the symbols are **derived** from the names in the file, such as
$\mathit{load}_t$ and $p^{\mathrm{max}}_g$. A derived symbol names one
declaration and no other, so a model prints with no setup. A symbol table makes
the output conventional:

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

Pass a dict, a path to a YAML file, or a `ms.SymbolTable`. As a file:

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

| Section      |                                                                                 |
| ------------ | ------------------------------------------------------------------------------- |
| `notation`   | **Required.** `latex` or `typst`: the language the entries are written in       |
| `dimensions` | For each dimension, an `index` letter and a `set` symbol. Either may be omitted |
| `names`      | For each parameter, variable or named expression, its symbol                    |

Every spelling is printed as you wrote it, and nothing translates notation. That
is why `notation:` is required, and why rendering a LaTeX table as Typst is
refused.

A key that names nothing in the model is an error with the near miss. The
alternative is a symbol that silently never applies.

Nothing in a symbol table changes what the file means, and no solver reads it.
What a declaration _is_ stays in its own `description:`, which every tool that
reads the model can print. See [declarations](language/declarations.md).
