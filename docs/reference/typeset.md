<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Typeset the math

`to_latex`, `to_typst` and `to_markdown` print a model as the equations it
stands for, from the file alone. No data binds, and no solver runs.

```python
import math_spec as ms

spec = ms.to_spec('model.yaml')  # read and checked once, then printed three ways

print(ms.to_latex(spec))  # amsmath align
print(ms.to_typst(spec))  # compiles without a TeX toolchain
print(ms.to_markdown(spec))  # renders as-is on GitHub
```

Each function takes what `to_spec` takes: a path, the YAML, a mapping or a
`Spec`. The same three formats come from a shell:

```bash
python -m math_spec latex model.yaml --symbols model.symbols.yaml --standalone -o model.tex
python -m math_spec typst model.yaml --standalone -o model.typ
python -m math_spec markdown model.yaml
```

[Print a model as math](../howto/print.md) is the recipe, and
[every construct, as math](notation.md) shows what each construct prints.

## Options

The three functions take the same keywords, and the command line spells each as
a flag.

|                      |                        |                                                                                                                                 |
| -------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `symbols`            | `--symbols FILE`       | How the names print. See [symbol tables](#symbol-tables). Default: derived from the names in the file                           |
| `standalone`         | `--standalone`         | Emit a document that compiles. Default: a fragment to include                                                                   |
| `legend`             | `--no-legend`          | Print the table of sets, parameters, variables and definitions above the math. Default: on                                      |
| `numbered`           | `--no-numbers`         | Number the equations. Default: on                                                                                               |
| `inline_expressions` | `--inline-expressions` | Substitute each named expression that the math reads into the equations that read it, instead of defining it once. Default: off |
| —                    | `--expand`             | Print the variables and constraints the `piecewise:` and `sos:` blocks state, rather than the blocks. Default: off              |

`-o FILE` writes to a file instead of stdout.

- The model's `description:` opens the document.
- A `piecewise:` block prints as one line: the curve it states, over the frame
  it states one curve per coordinate of. To print the variables and constraints
  it stands for instead, print
  [`spec.expand()`](language/piecewise.md#expanding-a-formulation).
- An [`assumptions:`](language/assumptions.md) entry prints under an
  **Assumptions** heading, last, beside what each curve assumes of its
  breakpoints. A model that assumes nothing of its data prints no such
  heading.
- A [named expression](language/named.md) prints its symbol where it is used
  and its body once, under a **Definitions** heading, in declaration order. A
  `cases:` block and a [reported entry](language/named.md#reported-expressions)
  keep their definition line under either `inline_expressions` setting.
- Wherever the math moves an index, which every `shift` does, the document
  prints a line saying what that notation means.
- A model that does not load does not print.
- Lines are not broken. A wide equation runs off the page.

## Markdown's delimiters

`to_markdown` prints math between the two pairs GitHub and GitLab read
verbatim: ``$`…`$`` inline, and a ` ```math ` fence for a block. It never
prints `$…$` or `$$…$$`. For a renderer that reads `$…$` alone, print with
`to_latex` and write that renderer's delimiters around the result.

## Descriptions

A `description:` is **plain prose, with one piece of notation**. A name in
backticks, such as `` `capital_cost` ``, sets in monospace in every output
format. Everything else is text, and each format escapes whatever its own
syntax would read as markup. The legend prints the description of every
dimension, parameter and variable.

## Printing one declaration on its own

`typeset_declaration` returns the line the document prints for one named
expression, constraint, assumption or variable, with its quantifier and without
a document, a label, a number or math delimiters:

```python
ms.typeset_declaration('model.yaml', 'spend', 'latex')
# \mathit{spend}_{t} = \sum_{g \in \mathcal{G}} \mathit{dispatch}_{t,g} \cdot \mathrm{cost}_{g} \qquad \forall\, t \in \mathcal{T}
ms.typeset_declaration('model.yaml', 'balance', 'latex')
# \sum_{g \in \mathcal{G}} \mathit{dispatch}_{t,g} = \mathrm{load}_{t} \qquad \forall\, t \in \mathcal{T}
```

It takes what the other functions take, plus the name, the format and an
optional `symbols` table. A Markdown line arrives without delimiters too, so put
it inside the inline pair:

```python
line = ms.typeset_declaration('model.yaml', 'balance', 'markdown')
print(f'The balance holds: $`{line}`$')
```

A line on its own has no _Definitions_ section beside it, so the plain named
expressions it uses are substituted. A cased expression prints by symbol, and a
second call with its name prints its block.

A name that is none of the four kinds is refused with the near miss. A name
declared as two of them, such as a constraint and a variable, is refused too,
because one line can print only one of them.

## Printing what a formulation states

A `piecewise:` block and a `sos:` block each state variables and constraints
([formulations](language/piecewise.md#expanding-a-formulation)). Printing
those rows is printing a different model, so it is
[`expand()`](language/piecewise.md#expanding-a-formulation) that produces it
and not an option on the render:

```python
ms.to_latex(spec)  # the curve, and the set beside its variable
ms.to_latex(spec.expand())  # the weights, the convexity row, the binaries
ms.to_latex(spec.expand('sos'))  # the curves as curves, the sets as binaries
```

A shell cannot compose that, so the command line spells it as a flag:

```bash
python -m math_spec latex model.yaml --expand --symbols model.symbols.yaml
```

One symbol table serves both, because a name a formulation emits counts as
declared — which is what lets `<block>_lam` print as $\lambda$ in the expansion
and the same table render the file it came from.

## Symbol tables

With no table, the symbols are **derived** from the names in the file, such as
$\mathrm{load}_t$ and $\mathrm{capacity}_g$. A symbol table makes the output
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
        'capacity': '\\bar p',
    },
}

ms.to_latex('dispatch.yaml', symbols=symbols)
```

Pass a dict, a path to a YAML file, or a `ms.SymbolTable`. As a file:

```yaml
# dispatch.symbols.yaml
notation: latex
dimensions:
  snapshot: { index: s, set: "\\mathcal{S}" }
  generator: { index: g, set: "\\mathcal{G}" }
names:
  cost: c
  load: "\\ell"
  capacity: "\\bar p"
```

| Section      |                                                                                 |
| ------------ | ------------------------------------------------------------------------------- |
| `notation`   | **Required.** `latex` or `typst`: the language the entries are written in       |
| `dimensions` | For each dimension, an `index` letter and a `set` symbol. Either may be omitted |
| `names`      | For each parameter, variable or named expression, its symbol                    |

Every spelling is printed as you wrote it, and nothing translates notation, so
rendering a LaTeX table as Typst is refused. A key that names nothing in the
model, and nothing a formulation of it emits, is an error with the near miss.

Nothing in a symbol table changes what the file means. What a declaration _is_
stays in its own `description:`.
