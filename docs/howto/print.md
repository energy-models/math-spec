<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Print a spec as math

Turn a spec file into the math a paper would print, from the file alone, and
keep the document current as the file changes.

1. **Print Markdown first** and read it:

   ```bash
   python -m mathspec markdown spec.yaml
   ```

2. **Give the symbols their conventional spelling** with a symbol table beside
   the spec, `spec.symbols.yaml`. Without one, `load` prints as
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

   A key naming nothing in the spec is an error.

3. **Emit a document that compiles.** `--standalone` wraps the fragment in a
   preamble, so the output builds on its own:

   ```bash
   python -m mathspec latex spec.yaml --symbols spec.symbols.yaml --standalone -o spec.tex
   python -m mathspec typst spec.yaml --standalone -o spec.typ
   ```

   Then `tectonic spec.tex` or `typst compile spec.typ`. A symbol table is
   written for one notation, so the Typst render takes a table with
   `notation: typst` or none. Without `--standalone` the output is a fragment
   to `\input` or `#include` into a paper.

4. **Print the rows a curve or a set states** with `--expand`:

   ```bash
   python -m mathspec markdown spec.yaml --expand
   ```

   The same table serves both renders: a name the expansion emits, such as
   `cost_curve_lam`, may be spelled in it.

5. **Keep it current** with a rule in the paper's build:

   ```make
   spec.tex: spec.yaml spec.symbols.yaml
   	python -m mathspec latex $< --symbols spec.symbols.yaml --standalone -o $@
   ```

[Typeset the math](../reference/typeset.md) lists every option and what a
symbol table may say.
