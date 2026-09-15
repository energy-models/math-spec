<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Print a model as math

Turn a model file into the math a paper would print, from the file alone, and
keep the document current as the file changes.

1. **Print Markdown first** and read it. It is the quickest way to see that
   the YAML says what you meant:

   ```bash
   python -m math_spec markdown model.yaml
   ```

2. **Give the symbols their conventional spelling** with a symbol table beside
   the model, `model.symbols.yaml`. Without one, `load` prints as
   $\mathrm{load}_t$; with one it prints as whatever you write:

   <!-- doctest: skip -->

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

   A key naming nothing in the model is an error, so a table cannot drift
   from its model silently.

3. **Emit a document that compiles.** `--standalone` wraps the fragment in a
   preamble, so the output builds on its own:

   ```bash
   python -m math_spec latex model.yaml --symbols model.symbols.yaml --standalone -o model.tex
   python -m math_spec typst model.yaml --standalone -o model.typ
   ```

   Then `tectonic model.tex` or `typst compile model.typ`. Typst needs no TeX
   toolchain. A symbol table is written for one notation, so the Typst render
   takes a table with `notation: typst` or none; a LaTeX table is refused
   there. Without `--standalone` the output is a fragment to `\input` or
   `#include` into a paper.

4. **Keep it current** with a rule in the paper's build:

   ```make
   model.tex: model.yaml model.symbols.yaml
   	python -m math_spec latex $< --symbols model.symbols.yaml --standalone -o $@
   ```

The options each renderer takes, what a symbol table may say, and how one
declaration is printed on its own are under
[typeset the math](../reference/typeset.md).
