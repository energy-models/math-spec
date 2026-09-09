<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Typeset the math

`to_latex`, `to_typst` and `to_markdown` print a model as the equations it
stands for, from the file alone. No data binds, and no solver runs.

Print a model to check that the YAML says what you meant, and to publish the
math beside the file that states it.

One page shows every construct the language has, beside the math it prints:
[Every construct, as math](notation.md). Look there when your question is
whether the notation is right, rather than how to print it.

```python
import math_spec as ms

spec = ms.to_spec('model.yaml')  # read and checked once, then printed three ways

print(ms.to_latex(spec))  # amsmath align
print(ms.to_typst(spec))  # compiles without a TeX toolchain
print(ms.to_markdown(spec))  # renders as-is on GitHub
```

Each of the three functions takes what `to_spec` takes, which is a path, the
YAML, or a mapping, and reads it.

Hand one of them a `Spec` instead, and the file is read and checked once rather
than once per format. That is also how you print a `Spec` you already hold,
without a second trip through the loader.

The same three formats come from a shell, so a build can print the math beside
the paper:

```bash
python -m math_spec latex model.yaml --symbols model.symbols.yaml --standalone -o model.tex
python -m math_spec typst model.yaml --standalone -o model.typ
python -m math_spec markdown model.yaml
```

## Options

The three functions take the same keywords. The command-line interface spells
each keyword as a flag.

|                      |                        |                                                                                                                                 |
| -------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `symbols`            | `--symbols FILE`       | How the names should print. See [symbol tables](#symbol-tables) below. Default: derived                                         |
| `standalone`         | `--standalone`         | Emit a document that compiles, rather than a fragment to include. Default: a fragment                                           |
| `legend`             | `--no-legend`          | Print the table of sets, parameters, variables and definitions above the math. Default: on                                      |
| `numbered`           | `--no-numbers`         | Number the equations. Default: on                                                                                               |
| `inline_expressions` | `--inline-expressions` | Substitute each named expression that the math reads into the equations that read it, instead of defining it once. Default: off |

`-o FILE` writes to a file instead of stdout.

The model's own `description:` opens the document, whatever the options say. It
is prose from the file, and no symbol table touches it.

A `piecewise:` block prints as the variables and constraints it expands into,
and not as the shorter block that was written, because the expansion is the math
the solver receives.

Inlining reaches only an expression that the math reads. A `cases:` block has no
single body to substitute, and a [reported entry](language/reported.md) is read
by nothing in the math. So both keep their own definition line under either
setting.

Where the math moves an index, which is what every spelling of `shift` does, the
document prints a line saying what that notation means. So a reader never meets
a symbol the document has not defined.

A model that does not load does not print. Typesetting runs the same load-time
checks that everything else runs.

!!! note "Typesetting does not break lines"

    A wide equation runs off the page. That is a formatting decision this
    package does not make for you.

## Printing one declaration on its own

The whole-model functions print the objective, the constraints, the definitions
and the domains.

Sometimes you want one declaration on its own, for a docstring, a table cell, or
a comment beside the value it computes. `typeset_declaration` returns the line
that the document prints for a named expression, a constraint or a variable. It
includes the quantifier. It adds no document, no label, no number, and no math
delimiters:

<!-- doctest: skip -->

```python
ms.typeset_declaration('model.yaml', 'spend', 'latex')
# \mathit{spend}_{t} = \sum_{g \in \mathcal{G}} p_{t,g} \cdot \mathrm{cost}_{g} \qquad \forall\, t \in \mathcal{T}
ms.typeset_declaration('model.yaml', 'balance', 'latex')
# \sum_{g \in \mathcal{G}} p_{t,g} = \mathrm{load}_{t} \qquad \forall\, t \in \mathcal{T}
```

It takes what the other functions take, which is a path, the YAML, a mapping or
a `Spec`. To that it adds the name, the format, and an optional `symbols` table.

A line on its own has no _Definitions_ section beside it. So the plain named
expressions it uses are substituted, which is `inline_expressions=True`, unless
you say otherwise. A cased expression prints by symbol, and a second call with
its name prints its block.

Two names are refused. A name the model declares as none of the three kinds is
refused, with the near miss. A name the model declares as both a constraint and
a variable is refused as well, because one line can print only one of the two.
Constraints sit outside the
[flat namespace](language/expressions.md#name-resolution), so a model may use
one name for both.

## Symbol tables

With no table, the symbols are **derived** from the names in the file, such as
$\mathit{load}_t$ and $p^{\mathrm{max}}_g$. A derived symbol names one
declaration and no other, so a model prints with no setup at all. A `SymbolTable` makes the output
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

You can pass a dict, a path to a YAML file, or a `ms.SymbolTable`. As a sidecar
file it looks like this:

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

| Section      |                                                                                   |
| ------------ | --------------------------------------------------------------------------------- |
| `notation`   | **Required.** Either `latex` or `typst`, the language the entries are written in  |
| `dimensions` | For each dimension, an `index` letter and a `set` symbol. You may omit either one |
| `names`      | For each parameter, variable or named expression, its symbol                      |

Every spelling is printed exactly as you wrote it. Nothing parses or
translates notation. That is why `notation:` is required, and why rendering a
LaTeX table as Typst is refused instead of producing something that nearly
works.

A key that names nothing in the model is an error, and the message gives the
near miss. The alternative would be a symbol that silently never applies, and a
reader who never finds out.

Presentation is not language. Nothing in a symbol table changes what the
file means, and no solver reads it. What a declaration _is_ stays the model's own
`description:`; see [declarations](language/declarations.md). The description
travels with the declaration, and it reaches every consumer.
