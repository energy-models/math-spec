<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Print the math

Turn a model file into the equations for a paper, a report or a review. The
math comes from the file alone, so it always matches the model you solve.

## Print Markdown

Start with Markdown, and read it:

```bash
python -m mathspec markdown model.yaml
```

The output has tables of symbols, the objective, the constraints and the
variable domains. [Your first model](../first-model.md#the-math) shows a full
example.

## Choose your own symbols

By default a name prints as itself: `load` prints as $\mathrm{load}_t$. To use
the symbols of your field, write a symbol table beside the model, for example
`model.symbols.yaml`:

```yaml
notation: latex

dimensions:
  snapshot: { index: s, set: "\\mathcal{S}" }
  generator: { index: g, set: "\\mathcal{G}" }

names:
  cost: c
  load: "\\ell"
  capacity: "\\bar p"
```

Pass it with `--symbols`:

```bash
python -m mathspec markdown model.yaml --symbols model.symbols.yaml
```

A key that names nothing in the model is an error.

## Make a document that compiles

`--standalone` adds a preamble, so the output builds on its own:

```bash
python -m mathspec latex model.yaml --symbols model.symbols.yaml --standalone -o model.tex
python -m mathspec typst model.yaml --standalone -o model.typ
```

Then run `tectonic model.tex` or `typst compile model.typ`.

- **Without `--standalone`, the output is a fragment.** Put it into your paper
  with `\input` or `#include`.
- **A symbol table is for one notation.** The Typst render takes a table with
  `notation: typst`, or no table.

## Show what a curve or a set means

A `piecewise:` or `sos:` block prints as one compact line. `--expand` prints
the plain constraints it stands for:

```bash
python -m mathspec markdown model.yaml --expand
```

The same symbol table serves both renders. It may also spell a name that the
expansion adds, such as `cost_curve_lam`. See
[expand curves and sets](see-an-expansion.md).

## Keep the document current

Add a rule to the build of your paper, so the math prints again when the model
changes:

```make
model.tex: model.yaml model.symbols.yaml
	python -m mathspec latex $< --symbols model.symbols.yaml --standalone -o $@
```

[Typeset the math](../reference/typeset.md) lists every option and everything
a symbol table may say.
