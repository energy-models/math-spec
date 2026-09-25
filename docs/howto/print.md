<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Print a model as math

Turn a model file into the math a paper would print, from the file alone, and
keep the document current as the file changes.

1. **Print Markdown first** and read it:

   ```bash
   python -m mathspec markdown model.yaml
   ```

2. **Give the symbols their conventional spelling** with a symbol table beside
   the model, `model.symbols.yaml`. Without one, `load` prints as
   $\mathrm{load}_t$; with one it prints as whatever you write:

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

   A key naming nothing in the model is an error.

3. **Emit a document that compiles.** `--standalone` wraps the fragment in a
   preamble, so the output builds on its own:

   ```bash
   python -m mathspec latex model.yaml --symbols model.symbols.yaml --standalone -o model.tex
   python -m mathspec typst model.yaml --standalone -o model.typ
   ```

   Then `tectonic model.tex` or `typst compile model.typ`. A symbol table is
   written for one notation, so the Typst render takes a table with
   `notation: typst` or none. Without `--standalone` the output is a fragment
   to `\input` or `#include` into a paper.

4. **Print the rows a curve or a set states** with `--expand`:

   ```bash
   python -m mathspec markdown model.yaml --expand
   ```

   The same table serves both renders: a name the expansion emits, such as
   `cost_curve_lam`, may be spelled in it.

5. **Keep it current** with a rule in the paper's build:

   ```make
   model.tex: model.yaml model.symbols.yaml
   	python -m mathspec latex $< --symbols model.symbols.yaml --standalone -o $@
   ```

[Typeset the math](../reference/typeset.md) lists every option and what a
symbol table may say.
